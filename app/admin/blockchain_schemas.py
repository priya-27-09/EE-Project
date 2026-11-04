from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field


class BlockchainStatusResponse(BaseModel):
    configured: bool
    available: bool
    status_message: str
    rpc_url: str
    chain_id: Optional[int] = None
    contract_address: Optional[str] = None
    account_address: Optional[str] = None
    latest_block: Optional[int] = None
    balance_eth: Optional[str] = None


class BlockchainRecordBriefResponse(BaseModel):
    id: int
    complaint_id: int
    complaint_public_id: Optional[str] = None
    event_type: str
    event_hash: str
    data_hash: str
    blockchain_network: str
    chain_id: Optional[int] = None
    contract_address: Optional[str] = None
    transaction_hash: Optional[str] = None
    block_number: Optional[int] = None
    blockchain_timestamp: Optional[datetime] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    confirmed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BlockchainRecordListResponse(BaseModel):
    total: int
    records: List[BlockchainRecordBriefResponse]


class BlockchainVerificationResponse(BaseModel):
    verified: bool
    record_id: int
    complaint_id: Optional[int] = None
    event_type: Optional[str] = None
    event_hash: Optional[str] = None
    data_hash: Optional[str] = None
    transaction_hash: Optional[str] = None
    block_number: Optional[int] = None
    onchain_verified: Optional[bool] = None
    onchain_data_hash: Optional[str] = None
    onchain_timestamp: Optional[int] = None
    reason: str


class ComplaintBlockchainIntegrityResponse(BaseModel):
    complaint_id: str
    records: List[BlockchainRecordBriefResponse]
