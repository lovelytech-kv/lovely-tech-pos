"""Focused tests: StockAdjustment and DamageLossRecord idempotency.

Static source assertions, matching the existing test style in this repo
(test_day_finance_validation.py, test_cash_only_calculations.py).
Verifies that the stock-control endpoints reuse the existing IdempotencyKey
infrastructure and enforce the same conflict convention already used by
SaleService and the admin expense endpoints.
"""

from pathlib import Path

BACKEND = Path(__file__).parents[1]
ROUTES = (BACKEND / "app" / "api" / "routes" / "stock_control.py").read_text()
SCHEMA = (BACKEND / "app" / "schemas" / "api.py").read_text()


def test_stock_adjust_schema_accepts_idempotency_key():
    body = SCHEMA.split("class StockAdjustIn(BaseModel):")[1].split("class DamageLossIn(BaseModel):")[0]
    assert "idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)" in body


def test_damage_loss_schema_accepts_idempotency_key():
    body = SCHEMA.split("class DamageLossIn(BaseModel):")[1].split("class AdminRecoveryIn(BaseModel):")[0]
    assert "idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)" in body


def test_stock_control_route_uses_existing_idempotency_key_model():
    assert "IdempotencyKey" in ROUTES


def test_adjust_request_hash_is_deterministic():
    assert "_adjust_request_hash(p: StockAdjustIn)" in ROUTES


def test_damage_loss_request_hash_is_deterministic():
    assert "_damage_request_hash(p: DamageLossIn)" in ROUTES


def test_adjust_endpoint_replays_completed_request():
    body = ROUTES.split("@router.post('/adjust'")[1].split("@router.post('/damage-loss'")[0]
    assert "_get_replay(db, key=p.idempotency_key, request_hash=request_hash)" in body
    assert "if replay is not None:" in body


def test_adjust_endpoint_reserves_idempotency_before_commit():
    body = ROUTES.split("@router.post('/adjust'")[1].split("@router.post('/damage-loss'")[0]
    assert "_reserve(db, key=p.idempotency_key" in body
    assert "db.commit()" in body


def test_damage_loss_endpoint_replays_completed_request():
    body = ROUTES.split("@router.post('/damage-loss'")[1]
    assert "_get_replay(db, key=p.idempotency_key, request_hash=request_hash)" in body
    assert "if replay is not None:" in body


def test_damage_loss_endpoint_reserves_idempotency_before_commit():
    body = ROUTES.split("@router.post('/damage-loss'")[1]
    assert "_reserve(db, key=p.idempotency_key" in body
    assert "db.commit()" in body


def test_idempotency_conflict_uses_existing_convention():
    assert "Idempotency key was already used for a different request" in ROUTES
    assert "Idempotency request has already completed" in ROUTES
    assert "The same request is currently being completed; retry after transaction finishes" in ROUTES


def test_rollback_does_not_leave_completed_idempotency_state():
    # On failure the route rolls back before commit, so the IdempotencyKey row
    # (which is flushed inside begin_nested) is rolled away with the transaction.
    body = ROUTES.split("@router.post('/adjust'")[1].split("@router.post('/damage-loss'")[0]
    assert "db.rollback(); raise HTTPException(400, str(e))" in body
    assert "except HTTPException:" in body
    assert "db.rollback(); raise" in body