import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class QueuePaymentMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    uploaded_at: datetime
    file_name: str


class QueueInvoiceMini(BaseModel):
    id: uuid.UUID
    code: str
    plan_name: str | None
    amount_total: int
    status: str
    expires_at: datetime


class QueueUserMini(BaseModel):
    id: uuid.UUID
    name: str
    email: str


class QueueOrgMini(BaseModel):
    id: uuid.UUID
    name: str


class PaymentQueueItem(BaseModel):
    payment: QueuePaymentMini
    invoice: QueueInvoiceMini
    user: QueueUserMini | None
    organization: QueueOrgMini


class RejectPaymentRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    is_active: bool
    is_superadmin: bool
    email_verified: bool
    created_at: datetime


class MembershipExtendRequest(BaseModel):
    months: int = Field(default=12, ge=1, le=60)


class MembershipAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    plan_id: uuid.UUID | None
    status: str
    starts_at: datetime | None
    ends_at: datetime | None
    grace_ends_at: datetime | None


class AuditLogOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    actor_name: str | None
    action: str
    entity_type: str
    entity_id: str | None
    organization_id: uuid.UUID | None
    meta: dict | None
