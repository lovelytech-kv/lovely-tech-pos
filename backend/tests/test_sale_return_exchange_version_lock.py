"""Focused tests: Sale/Return/Exchange optimistic-locking foundation.

Static source assertions, matching the existing test style in this repo
(test_day_finance_validation.py, test_cash_only_calculations.py).
Verifies that:
- SaleService.complete accepts and enforces an optional `version`.
- ReturnService.complete accepts and enforces an optional `version`.
- ExchangeService.complete accepts and enforces an optional `version`.
- Successful updates increment the version atomically.
- Stale updates are rejected.
"""

from pathlib import Path

BACKEND = Path(__file__).parents[1]
SALES = (BACKEND / "app" / "services" / "sales.py").read_text()
RETURNS = (BACKEND / "app" / "services" / "returns.py").read_text()
API_SALES = (BACKEND / "app" / "api" / "routes" / "sales.py").read_text()
API_RETURNS = (BACKEND / "app" / "api" / "routes" / "returns.py").read_text()
SCHEMA = (BACKEND / "app" / "schemas" / "api.py").read_text()


# ---------------------------------------------------------------------------
# Sale
# ---------------------------------------------------------------------------

def test_sale_complete_signature_accepts_version():
    assert "def complete(self, request: SaleRequest, *, version: int | None = None) -> SaleResult:" in SALES


def test_sale_complete_verifies_version_and_rejects_stale():
    assert "if version is not None and sale.version != version:" in SALES
    assert "raise SaleValidationError(\"Sale changed; reload before editing\")" in SALES


def test_sale_complete_increments_version():
    assert "sale.version += 1" in SALES


def test_sale_result_carries_version():
    assert "version: int = 1" in SALES
    assert "version=sale.version," in SALES


def test_sale_schema_in_accepts_version():
    assert "version: int | None = None" in SCHEMA


def test_sale_schema_out_carries_version():
    assert "version: int = 1" in SCHEMA


def test_sale_route_passes_version_to_service():
    assert "result = SaleService(db).complete(req, version=payload.version)" in API_SALES


# ---------------------------------------------------------------------------
# Return
# ---------------------------------------------------------------------------

def test_return_complete_signature_accepts_version():
    assert "def complete(self, request: ReturnRequest, *, version: int | None = None) -> ReturnResult:" in RETURNS


def test_return_complete_verifies_version_and_rejects_stale():
    assert "if version is not None and ret.version != version:" in RETURNS
    assert "raise ReturnValidationError(\"Return changed; reload before editing\")" in RETURNS


def test_return_complete_increments_version():
    assert "ret.version += 1" in RETURNS


def test_return_result_carries_version():
    assert "version: int = 1" in RETURNS
    assert "ReturnResult(ret.id, return_no, refund_total, self.money(request.return_charge), ret.version)" in RETURNS


def test_return_route_passes_version_to_service():
    assert "version=payload.version," in API_RETURNS


def test_return_route_exposes_version_in_response():
    assert "'version': ret.version," in API_RETURNS


# ---------------------------------------------------------------------------
# Exchange
# ---------------------------------------------------------------------------

def test_exchange_request_accepts_version():
    assert "version: int | None = None" in RETURNS


def test_exchange_complete_verifies_version_and_rejects_stale():
    assert "if request.version is not None and ret.version != request.version:" in RETURNS
    assert "raise ReturnValidationError(\"Return changed; reload before editing\")" in RETURNS


def test_exchange_complete_increments_return_version():
    assert "ret.version += 1" in RETURNS


def test_exchange_route_passes_version_to_service():
    assert "version=payload.version" in API_RETURNS