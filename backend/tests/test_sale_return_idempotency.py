"""Focused tests: Sale and Return idempotency.

Static source assertions, matching the existing test style in this repo
(test_day_finance_validation.py, test_cash_only_calculations.py).
Verifies that SaleService and ReturnService reuse the existing IdempotencyKey
architecture and enforce the same conflict convention already used by
SaleService.
"""

from pathlib import Path

BACKEND = Path(__file__).parents[1]
SALES = (BACKEND / "app" / "services" / "sales.py").read_text()
RETURNS = (BACKEND / "app" / "services" / "returns.py").read_text()
SALES_ROUTE = (BACKEND / "app" / "api" / "routes" / "sales.py").read_text()
RETURNS_ROUTE = (BACKEND / "app" / "api" / "routes" / "returns.py").read_text()
SCHEMA = (BACKEND / "app" / "schemas" / "api.py").read_text()


# ---------------------------------------------------------------------------
# Sale
# ---------------------------------------------------------------------------

def test_sale_service_has_idempotent_replay():
    assert "def _get_idempotent_replay(self, request: SaleRequest, request_hash: str) -> SaleResult | None:" in SALES


def test_sale_service_has_idempotent_reserve():
    assert "def _reserve_idempotency(self, request: SaleRequest, request_hash: str) -> None:" in SALES


def test_sale_service_rejects_different_request_with_same_key():
    assert "Idempotency key was already used for a different request" in SALES


def test_sale_service_rejects_in_flight_request():
    assert "The same request is currently being completed; retry after transaction finishes" in SALES


def test_sale_service_canonical_hash_is_deterministic():
    assert "def canonical_request_hash(request: SaleRequest) -> str:" in SALES


def test_sale_route_passes_idempotency_key():
    assert "idempotency_key=payload.idempotency_key" in SALES_ROUTE


def test_sale_schema_carries_idempotency_key():
    assert "idempotency_key: str | None = Field(default=None, max_length=120)" in SCHEMA.split("class SaleIn(BaseModel):")[1].split("class SaleOut(BaseModel):")[0]


def test_sale_result_carries_replayed_flag():
    assert "replayed: bool = False" in SALES


# ---------------------------------------------------------------------------
# Return
# ---------------------------------------------------------------------------

def test_return_request_accepts_idempotency_key():
    assert "idempotency_key: str | None = None" in RETURNS.split("class ReturnRequest")[1].split("class ReturnResult")[0]


def test_return_service_has_canonical_request_hash():
    assert "def canonical_request_hash(request: ReturnRequest) -> str:" in RETURNS


def test_return_service_has_idempotent_replay():
    assert "def _get_idempotent_replay(self, request: ReturnRequest, request_hash: str) -> ReturnResult | None:" in RETURNS


def test_return_service_has_idempotent_reserve():
    assert "def _reserve_idempotency(self, request: ReturnRequest, request_hash: str, result: ReturnResult) -> None:" in RETURNS


def test_return_service_rejects_different_request_with_same_key():
    assert "Idempotency key was already used for a different request" in RETURNS


def test_return_service_rejects_in_flight_request():
    assert "The same request is currently being completed; retry after transaction finishes" in RETURNS


def test_return_service_reserves_idempotency_after_flush():
    complete_body = RETURNS.split("def complete(self, request: ReturnRequest")[1].split("class ExchangeService")[0]
    assert "self.session.flush()" in complete_body
    assert "self._reserve_idempotency(request, request_hash, result)" in complete_body


def test_return_route_passes_idempotency_key():
    assert "idempotency_key=payload.idempotency_key" in RETURNS_ROUTE


def test_return_schema_carries_idempotency_key():
    assert "idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)" in SCHEMA.split("class ReturnIn(BaseModel):")[1].split("class ReturnPaymentIn(BaseModel):")[0]


def test_return_result_carries_version():
    assert "version: int = 1" in RETURNS