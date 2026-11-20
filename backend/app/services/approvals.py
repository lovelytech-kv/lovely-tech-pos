from __future__ import annotations
import uuid, secrets
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.models.security import ApprovalRequest, AuditLog
class ApprovalError(ValueError): pass
class ApprovalService:
    def __init__(self,session:Session): self.session=session
    def request(self, *, branch_id, action_type, requester_user_id, payload=None, source_transaction_id=None):
        row=ApprovalRequest(branch_id=branch_id,action_type=action_type,source_transaction_id=source_transaction_id,requester_user_id=requester_user_id,payload_json=payload,status='PENDING',requested_at=datetime.now(timezone.utc),approval_action_id=secrets.token_urlsafe(24))
        self.session.add(row); self.session.flush(); return row
    def review(self, approval_id, *, branch_id, reviewer_user_id, approve:bool, reject_reason=None):
        row=self.session.scalar(select(ApprovalRequest).where(ApprovalRequest.id==approval_id,ApprovalRequest.branch_id==branch_id).with_for_update())
        if not row: raise ApprovalError('Approval request not found')
        if row.status!='PENDING': raise ApprovalError('Approval request already reviewed')
        if row.requester_user_id==reviewer_user_id: raise ApprovalError('Requester cannot approve own request')
        row.status='APPROVED' if approve else 'REJECTED'; row.version += 1; row.reviewer_user_id=reviewer_user_id; row.reviewed_at=datetime.now(timezone.utc); row.reject_reason=None if approve else (reject_reason or 'Rejected')
        self.session.add(AuditLog(branch_id=branch_id,actor_user_id=reviewer_user_id,action_type='APPROVAL_REVIEWED',entity_type='APPROVAL_REQUEST',entity_id=row.id,timestamp=datetime.now(timezone.utc),after_json={'status':row.status,'action_type':row.action_type},source_transaction_id=row.source_transaction_id))
        self.session.flush(); return row
    def consume_for_sale(self, approval_id, *, branch_id, sale_id) -> bool:
        """H8 — atomically mark a discount approval single-use and bind it to one sale."""
        result = self.session.execute(
            update(ApprovalRequest)
            .where(
                ApprovalRequest.id == approval_id,
                ApprovalRequest.branch_id == branch_id,
                ApprovalRequest.action_type == 'DISCOUNT_OVERRIDE',
                ApprovalRequest.status == 'APPROVED',
            )
            .values(status='CONSUMED', source_transaction_id=sale_id)
        )
        return result.rowcount == 1
