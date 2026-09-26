import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    price: int
    period_months: int
    seats: int
    features: list


class BankInfo(BaseModel):
    bank_name: str
    account_number: str
    account_name: str


class InvoiceCreate(BaseModel):
    organization_id: uuid.UUID
    plan_id: uuid.UUID


class InvoiceCreated(BaseModel):
    id: uuid.UUID
    code: str
    plan_name: str
    amount_base: int
    unique_code: int
    amount_total: int
    bank: BankInfo
    status: str
    expires_at: datetime


class InvoiceListItem(BaseModel):
    id: uuid.UUID
    code: str
    plan_name: str
    amount_total: int
    status: str
    expires_at: datetime
    created_at: datetime


class PaymentMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    file_name: str
    uploaded_at: datetime
    reject_reason: str | None = None


class InvoiceDetail(BaseModel):
    id: uuid.UUID
    code: str
    plan_name: str
    amount_base: int
    unique_code: int
    amount_total: int
    bank: BankInfo
    status: str
    expires_at: datetime
    created_at: datetime
    payment: PaymentMini | None


class PaymentProofOut(BaseModel):
    id: uuid.UUID
    status: str
    uploaded_at: datetime


class MembershipOut(BaseModel):
    status: str
    starts_at: datetime | None
    ends_at: datetime | None
    grace_ends_at: datetime | None
    plan_name: str | None
