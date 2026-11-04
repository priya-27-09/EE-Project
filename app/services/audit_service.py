from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog

FORBIDDEN_AUDIT_KEYS = {
    "password",
    "password_hash",
    "token",
    "access_token",
    "jwt",
    "secret",
    "key",
    "authorization",
    "bearer",
    "private_key",
}


def sanitize_audit_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Sanitize audit metadata dict to ensure NO passwords, tokens,
    or secret credentials are ever written to the audit log table.
    """
    if not metadata:
        return {}
    clean = {}
    for k, v in metadata.items():
        k_lower = str(k).lower()
        if any(forbidden in k_lower for forbidden in FORBIDDEN_AUDIT_KEYS):
            clean[k] = "[REDACTED]"
        elif isinstance(v, dict):
            clean[k] = sanitize_audit_metadata(v)
        else:
            clean[k] = v
    return clean


def record_audit_log(
    action: str,
    entity_type: str,
    entity_id: str,
    user_id: Optional[int],
    db: Session,
    metadata: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """
    Record an immutable audit log entry in PostgreSQL.
    Strictly prevents secret or credential leakage.
    """
    clean_metadata = sanitize_audit_metadata(metadata)

    log_entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        timestamp=datetime.now(timezone.utc),
        metadata_=clean_metadata,
    )
    db.add(log_entry)
    return log_entry
