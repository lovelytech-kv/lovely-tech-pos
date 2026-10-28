from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)

class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user_id: UUID
    username: str
    display_name: str
    role: str
    branch_id: UUID
    must_change_password: bool

class SaleLineIn(BaseModel):
    item_id: UUID
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal | None = Field(default=None, ge=0)
    discount: Decimal = Field(default=Decimal("0"), ge=0)
    serialized_unit_id: UUID | None = None
    warranty_type: Literal["NONE", "DAYS", "MONTHS", "CHECKING ONLY", "CUSTOM"] | None = None
    warranty_duration_value: int | None = Field(default=None, ge=1)
    warranty_custom_rule: str | None = None

class PaymentIn(BaseModel):
    method: Literal["CASH", "CARD", "ONLINE"]
    amount: Decimal = Field(gt=0)
    reference: str | None = None

class SaleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lines: list[SaleLineIn] = Field(min_length=1)
    payments: list[PaymentIn] = Field(default_factory=list)
    cash_received: Decimal | None = Field(default=None, ge=0)
    credit_sale: bool = False
    document_type: Literal["SYSTEM_PRINTED", "MANUAL", "NO_PRINT"] = "SYSTEM_PRINTED"
    manual_invoice_ref: str | None = None
    customer_id: UUID | None = None
    sale_datetime: datetime | None = None
    idempotency_key: str | None = Field(default=None, max_length=120)
    admin_discount_approval_id: UUID | None = None
    version: int | None = None

class SaleOut(BaseModel):
    sale_id: UUID
    invoice_no: str
    grand_total: Decimal
    change_amount: Decimal = Decimal("0")
    total_cost: Decimal | None = None
    negative_stock: bool
    warranty_ids: list[UUID]
    replayed: bool
    version: int = 1

class DateRangeIn(BaseModel):
    start: date
    end: date

class ReportOut(BaseModel):
    start: date
    end: date
    sales_count: int
    sales_total: Decimal
    cash_total: Decimal
    card_total: Decimal
    online_total: Decimal
    cost_total: Decimal | None = None
    gross_profit: Decimal | None = None
    expenses_total: Decimal | None = None
    other_income_total: Decimal | None = None
    net_profit: Decimal | None = None
    refunds_total: Decimal | None = None
    return_charge_total: Decimal | None = None
    repair_income: Decimal | None = None
    repair_profit: Decimal | None = None
    damage_loss_total: Decimal | None = None

class PermissionOut(BaseModel):
    code: str
    name: str
    description: str | None

class RepairCreateIn(BaseModel):
    device_brand: str | None = None; model: str | None = None; given_accessories: str | None = None
    special_note: str | None = None; customer_id: UUID | None = None; customer_name: str | None = None
    contact_no: str | None = None; reported_fault: str | None = None; estimated_amount: Decimal | None = Field(default=None, ge=0)
    warranty_period: str | None = None

class RepairStatusIn(BaseModel):
    status: str
    version: int | None = None

class RepairPaymentIn(BaseModel):
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)
    method: Literal["CASH","CARD","ONLINE"]; amount: Decimal = Field(gt=0); reference: str | None = None; proof_reference: str | None = None; payment_type: str = "RECEIPT"

class RepairFinalizeIn(BaseModel):
    version: int | None = None
    final_amount: Decimal = Field(ge=0); labour_amount: Decimal = Field(ge=0); repair_invoice_ref: str | None = None
    description_amount: str | None = None; hand_over_date: date | None = None

class RepairCancelIn(BaseModel):
    version: int | None = None
    reason: str = Field(min_length=3, max_length=500)

class ApprovalCreateIn(BaseModel):
    action_type: str; payload: dict | None = None; source_transaction_id: UUID | None = None
class ApprovalReviewIn(BaseModel):
    version: int | None = None
    approve: bool; reject_reason: str | None = None

class SettlementIn(BaseModel):
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)
    customer_id: UUID; amount: Decimal = Field(gt=0); payment_method: Literal["CASH","CARD","ONLINE"]
    sale_id: UUID | None = None; reference: str | None = None; proof_reference: str | None = None

class DayStartIn(BaseModel):
    business_date: date
    opening_cash: Decimal = Field(ge=0)
    denominations: dict[str, int] = Field(default_factory=dict)
    note: str | None = None
class DayOpeningCorrectionIn(BaseModel):
    day_session_id: UUID
    opening_cash: Decimal = Field(ge=0)
    denominations: dict[str,int] = Field(default_factory=dict)
    reason: str = Field(min_length=3)
    version: int | None = None

class DayEndIn(BaseModel):
    version: int | None = None
    actual_cash: Decimal = Field(ge=0)
    denominations: dict[str, int] = Field(default_factory=dict)
    reason: str
    note: str | None = None
class CashInIn(BaseModel):
    amount: Decimal = Field(gt=0); note: str | None = None
class ReloadIn(BaseModel):
    day_session_id: UUID
    provider: Literal["Dialog", "Airtel", "Mobitel", "Hutch"]
    amount: Decimal = Field(gt=0)
    note: str | None = None


class ReturnLineIn(BaseModel):
    sale_line_id: UUID
    quantity: Decimal = Field(gt=0)
    condition: Literal["GOOD", "DAMAGED"] = "GOOD"
    refund_amount: Decimal | None = Field(default=None, ge=0)
    serialized_unit_id: UUID | None = None

class ReturnIn(BaseModel):
    original_sale_id: UUID
    lines: list[ReturnLineIn] = Field(min_length=1)
    return_charge: Decimal = Field(default=Decimal("0"), ge=0)
    reason: str | None = None
    return_datetime: datetime | None = None
    admin_override: bool = False
    version: int | None = None
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)

class ReturnPaymentIn(BaseModel):
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)
    payment_method: Literal["CASH", "CARD", "ONLINE"]
    amount: Decimal = Field(gt=0)
    payment_datetime: datetime | None = None
    reference: str | None = None

class ExchangeIn(BaseModel):
    return_id: UUID
    replacement_sale_id: UUID
    exchange_datetime: datetime | None = None
    version: int | None = None

class WarrantyClaimIn(BaseModel):
    item_id: UUID
    product_warranty_id: UUID | None = None
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    notes: str | None = None

class WarrantyDecisionIn(BaseModel):
    version: int | None = None
    notes: str | None = None
    supplier_process: str = "SUPPLIER_WARRANTY_CLAIM"

class WarrantyReplacementIn(BaseModel):
    version: int | None = None
    quantity: Decimal | None = Field(default=None, gt=0)

class PurchaseCostIn(BaseModel):
    version: int | None = None
    purchase_version: int | None = None
    purchase_id: UUID
    purchase_line_id: UUID
    unit_cost: Decimal = Field(ge=0)


class RepairPartRemoveIn(BaseModel):
    condition: Literal["GOOD", "DAMAGED"]
    reason: str = Field(min_length=3, max_length=500)

class RepairPartIn(BaseModel):
    item_id: UUID
    quantity: Decimal = Field(gt=0)
    charge_amount: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = None

class RepairFinalizeOut(BaseModel):
    repair_id: UUID
    repair_no: str
    status: str
    total_amount: Decimal
    labour_amount: Decimal
    outstanding: Decimal

class DayStatusOut(BaseModel):
    day_session_id: UUID | None
    business_date: date
    status: str
    opening_cash: Decimal
    expected_cash: Decimal | None = None
    version: int | None = None

class PendingPurchaseLineOut(BaseModel):
    version: int | None = None
    purchase_version: int | None = None
    purchase_id: UUID
    purchase_line_id: UUID
    purchase_date: date
    reference_no: str | None
    item_id: UUID
    quantity: Decimal
    unit_cost: Decimal | None

class WarrantyClaimOut(BaseModel):
    claim_id: UUID
    claim_no: str
    item_id: UUID
    quantity: Decimal
    admin_decision: str
    replacement_outcome: str | None
    notes: str | None


class ExpenseIn(BaseModel):
    category_id: UUID
    expense_date: date
    amount: Decimal = Field(gt=0)
    payment_method: Literal["CASH","CARD","ONLINE"]
    description: str | None = None
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)

class OtherIncomeIn(BaseModel):
    income_date: date
    amount: Decimal = Field(gt=0)
    payment_method: Literal["CASH","CARD","ONLINE"]
    description: str | None = None
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)

class TargetIn(BaseModel):
    target_type: Literal["SALES_AMOUNT","ITEM_SALES_PROFIT","REPAIR_INCOME","REPAIR_PROFIT","BILLS_COUNT","ITEMS_SOLD_COUNT"]
    target_value: Decimal = Field(gt=0)
    period_type: Literal["DAILY","MONTHLY"]
    period_start: date
    period_end: date

class RolePermissionUpdateIn(BaseModel):
    permission_codes: list[str]

class UserRoleUpdateIn(BaseModel):
    version: int | None = None
    role_code: str

class BackupCreateIn(BaseModel):
    filename: str = Field(min_length=1, max_length=200)

class BackupOut(BaseModel):
    backup_id: UUID
    state: str
    filename: str
    sha256: str | None
    verified_at: datetime | None
    sync_state: str = "LOCAL_ONLY"
    remote_path: str | None = None

class DocumentSearchOut(BaseModel):
    document_type: str
    document_id: UUID
    document_no: str
    document_datetime: datetime | date
    status: str

class StockAdjustIn(BaseModel):
    item_id: UUID
    quantity_delta: Decimal
    reason: str = Field(min_length=1)
    serialized_unit_ids: list[UUID] | None = None   # required for IMEI-tracked items when stock goes DOWN
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)
class DamageLossIn(BaseModel):
    item_id: UUID
    quantity: Decimal = Field(gt=0)
    reason: str = Field(min_length=1)
    serialized_unit_ids: list[UUID] | None = None   # required for IMEI-tracked items: which phones are damaged/lost
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)



class AdminRecoveryIn(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    recovery_code: str = Field(min_length=3, max_length=200)
    new_password: str = Field(min_length=10, max_length=200)

class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=10, max_length=200)

class CashierResetIn(BaseModel):
    user_id: UUID
    admin_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=10, max_length=200)

class PurchaseCostCorrectionIn(BaseModel):
    purchase_line_id: UUID
    version: int | None = None
    unit_cost: Decimal = Field(ge=0)
    reason: str = Field(min_length=3)

class PurchaseDateCorrectionIn(BaseModel):
    purchase_line_id: UUID
    version: int | None = None
    line_date: date
    reason: str = Field(min_length=3)

class PurchaseReferenceCorrectionIn(BaseModel):
    purchase_id: UUID
    version: int | None = None
    reference_no: str | None = None
    reason: str = Field(min_length=3)

class PurchaseQuantityCorrectionIn(BaseModel):
    purchase_line_id: UUID
    version: int | None = None
    quantity: Decimal = Field(gt=0)
    reason: str = Field(min_length=3)

class CustomerIn(BaseModel):
    name: str | None = None
    contact_no: str | None = None
    notes: str | None = None

class CustomerUpdateIn(CustomerIn):
    version: int

class UserDiscountLimitIn(BaseModel):
    version: int | None = None
    discount_limit_percent: Decimal = Field(ge=0, le=100)

class ReauthIn(BaseModel):
    admin_password: str = Field(min_length=1, max_length=200)

class ManualWarrantyRegistrationIn(BaseModel):
    reference_no: str = Field(min_length=1, max_length=100)
    customer_name: str | None = None
    item_description: str | None = None
    notes: str | None = None
    start_date: date
    expiry_date: date | None = None
    warranty_type: str = "CUSTOM"

class WarrantySupplierOutcomeIn(BaseModel):
    version: int | None = None
    outcome: Literal["REPLACEMENT", "SHOP_HELD_DAMAGE", "CUSTOMER_KEEPS_ITEM"]
    quantity: Decimal | None = Field(default=None, gt=0)
    notes: str | None = None


class ProvisioningIn(BaseModel):
    branch_code: str = Field(min_length=1, max_length=30)
    branch_name: str = Field(min_length=1, max_length=150)


class ProvisioningOut(BaseModel):
    status: str
    instance_id: str
    branch_code: str
    branch_name: str
    branch_id: UUID
    app_version: str
    protocol_version: str
    api_version: str
    setup_state: str
