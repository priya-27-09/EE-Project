from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.complaint import Complaint
from app.models.blockchain_record import BlockchainRecord
from app.auth.dependencies import get_current_user, require_roles
from app.services.blockchain_service import BlockchainService
from app.admin.blockchain_schemas import (
    BlockchainStatusResponse,
    BlockchainRecordBriefResponse,
    BlockchainRecordListResponse,
    BlockchainVerificationResponse,
    ComplaintBlockchainIntegrityResponse,
)

admin_router = APIRouter(prefix="/api/v1/admin/blockchain", tags=["Admin - Blockchain"])
public_router = APIRouter(prefix="/api/v1/blockchain", tags=["Blockchain Integrity"])


@admin_router.get(
    "/status",
    response_model=BlockchainStatusResponse,
    summary="Get real-time blockchain node and contract status (Admin only)",
)
def get_blockchain_status(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Returns live diagnostics for Ganache RPC, chain ID, account balance,
    and deployed contract address. Never leaks private keys.
    """
    info = BlockchainService.get_network_info()
    return BlockchainStatusResponse(**info)


@admin_router.get(
    "/records",
    response_model=BlockchainRecordListResponse,
    summary="List blockchain audit records (Admin only)",
)
def list_blockchain_records(
    complaint_ref: Optional[str] = Query(None, description="Filter by complaint reference (e.g. CG-2026-000001)"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (CONFIRMED, FAILED, etc.)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """List all blockchain audit records with optional filters and pagination."""
    query = db.query(BlockchainRecord).join(Complaint, BlockchainRecord.complaint_id == Complaint.id)

    if complaint_ref:
        query = query.filter(Complaint.complaint_id.ilike(f"%{complaint_ref.strip()}%"))
    if event_type:
        query = query.filter(BlockchainRecord.event_type == event_type.strip())
    if status_filter:
        query = query.filter(BlockchainRecord.status == status_filter.strip())

    total = query.count()
    records = query.order_by(desc(BlockchainRecord.created_at)).offset(offset).limit(limit).all()

    record_briefs = []
    for r in records:
        record_briefs.append(
            BlockchainRecordBriefResponse(
                id=r.id,
                complaint_id=r.complaint_id,
                complaint_public_id=r.complaint.complaint_id if r.complaint else None,
                event_type=r.event_type,
                event_hash=r.event_hash,
                data_hash=r.data_hash,
                blockchain_network=r.blockchain_network,
                chain_id=r.chain_id,
                contract_address=r.contract_address,
                transaction_hash=r.transaction_hash,
                block_number=r.block_number,
                blockchain_timestamp=r.blockchain_timestamp,
                status=r.status,
                error_message=r.error_message,
                created_at=r.created_at,
                confirmed_at=r.confirmed_at,
            )
        )

    return BlockchainRecordListResponse(total=total, records=record_briefs)


@admin_router.post(
    "/{record_id}/retry",
    response_model=BlockchainRecordBriefResponse,
    summary="Retry a failed or unconfigured blockchain record (Admin only)",
)
def retry_blockchain_record(
    record_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Retries transaction submission to Ganache reusing the exact same event_hash and data_hash.
    Only accessible by ADMIN.
    """
    record = db.query(BlockchainRecord).filter(BlockchainRecord.id == record_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blockchain record #{record_id} not found.",
        )

    try:
        updated = BlockchainService.retry_anchor(record_id=record_id, db=db, user_id=current_user.id)
        return BlockchainRecordBriefResponse(
            id=updated.id,
            complaint_id=updated.complaint_id,
            complaint_public_id=updated.complaint.complaint_id if updated.complaint else None,
            event_type=updated.event_type,
            event_hash=updated.event_hash,
            data_hash=updated.data_hash,
            blockchain_network=updated.blockchain_network,
            chain_id=updated.chain_id,
            contract_address=updated.contract_address,
            transaction_hash=updated.transaction_hash,
            block_number=updated.block_number,
            blockchain_timestamp=updated.blockchain_timestamp,
            status=updated.status,
            error_message=updated.error_message,
            created_at=updated.created_at,
            confirmed_at=updated.confirmed_at,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Retry failed: {str(exc)}",
        )


@public_router.get(
    "/complaints/{complaint_id}",
    response_model=ComplaintBlockchainIntegrityResponse,
    summary="Get blockchain audit trail for a complaint",
)
def get_complaint_blockchain_records(
    complaint_id: str,
    db: Session = Depends(get_db),
):
    """
    Public / Citizen / Officer audit trail retrieval.
    Returns all anchored blockchain events for a complaint reference (e.g. CG-2026-000001).
    """
    clean_id = complaint_id.strip()
    complaint = (
        db.query(Complaint)
        .filter(Complaint.complaint_id == clean_id)
        .first()
    )
    if not complaint and clean_id.isdigit():
        complaint = (
            db.query(Complaint)
            .filter(Complaint.id == int(clean_id))
            .first()
        )
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{clean_id}' not found.",
        )

    records = (
        db.query(BlockchainRecord)
        .filter(BlockchainRecord.complaint_id == complaint.id)
        .order_by(BlockchainRecord.created_at.asc())
        .all()
    )

    record_briefs = [
        BlockchainRecordBriefResponse(
            id=r.id,
            complaint_id=r.complaint_id,
            complaint_public_id=complaint.complaint_id,
            event_type=r.event_type,
            event_hash=r.event_hash,
            data_hash=r.data_hash,
            blockchain_network=r.blockchain_network,
            chain_id=r.chain_id,
            contract_address=r.contract_address,
            transaction_hash=r.transaction_hash,
            block_number=r.block_number,
            blockchain_timestamp=r.blockchain_timestamp,
            status=r.status,
            error_message=r.error_message,
            created_at=r.created_at,
            confirmed_at=r.confirmed_at,
        )
        for r in records
    ]

    return ComplaintBlockchainIntegrityResponse(
        complaint_id=complaint.complaint_id,
        records=record_briefs,
    )


@public_router.get(
    "/records/{record_id}/verify",
    response_model=BlockchainVerificationResponse,
    summary="Cryptographically verify a blockchain audit record",
)
def verify_blockchain_record(
    record_id: int,
    db: Session = Depends(get_db),
):
    """
    Live cryptographic verification:
    1. Loads PostgreSQL record.
    2. Recalculates SHA-256 of canonical payload.
    3. Calls verifyAudit(eventHash, dataHash) on smart contract.
    4. Confirms whether database matches on-chain state.
    """
    res = BlockchainService.verify_record(record_id=record_id, db=db)
    return BlockchainVerificationResponse(**res)
