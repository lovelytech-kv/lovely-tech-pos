from pathlib import Path


def test_customer_history_includes_warranty_claims():
    """Customer history should include warranty claims."""
    route_code = Path(__file__).parents[1] / "app" / "api" / "routes" / "customers.py"
    content = route_code.read_text()
    
    # Check that warranty claims are queried
    assert "claims=db.execute(" in content
    assert "select(WarrantyClaim, ProductWarranty, Sale, SaleLine)" in content
    assert ".join(ProductWarranty, ProductWarranty.id==WarrantyClaim.product_warranty_id)" in content
    assert ".join(SaleLine, SaleLine.id==ProductWarranty.sale_line_id)" in content
    assert ".join(Sale, Sale.id==SaleLine.sale_id)" in content
    assert "Sale.customer_id==customer.id" in content
    
    # Check that warranty claims are returned in response
    assert '"warranty_claims"' in content
    assert '"claim_id":str(c.id)' in content
    assert '"claim_no":c.claim_no' in content
    assert '"decision":c.admin_decision' in content


def test_customer_history_respects_branch_isolation():
    """Customer history should respect branch isolation for warranty claims."""
    route_code = Path(__file__).parents[1] / "app" / "api" / "routes" / "customers.py"
    content = route_code.read_text()
    
    assert "WarrantyClaim.branch_id==user.branch_id" in content


def test_customer_history_excludes_sensitive_cost_data():
    """Customer history should not expose sensitive cost/profit data."""
    route_code = Path(__file__).parents[1] / "app" / "api" / "routes" / "customers.py"
    content = route_code.read_text()
    
    # Check sales response - should not include cost
    sales_response = content.find('"sales"')
    sales_section = content[sales_response:sales_response+500]
    assert "cost" not in sales_section.lower()
    assert "profit" not in sales_section.lower()
    
    # Check warranty claims response - should not include cost
    claims_response = content.find('"warranty_claims"')
    claims_section = content[claims_response:claims_response+500]
    assert "cost" not in claims_section.lower()
    assert "profit" not in claims_section.lower()


def test_customer_history_includes_repairs():
    """Customer history should include repairs."""
    route_code = Path(__file__).parents[1] / "app" / "api" / "routes" / "customers.py"
    content = route_code.read_text()
    
    assert "repairs=db.scalars(select(Repair)" in content
    assert "Repair.customer_id==customer.id" in content
    assert '"repairs"' in content


def test_customer_history_includes_settlements():
    """Customer history should include credit settlements."""
    route_code = Path(__file__).parents[1] / "app" / "api" / "routes" / "customers.py"
    content = route_code.read_text()
    
    assert "settlements=db.scalars(select(CreditSettlement)" in content
    assert "CreditSettlement.customer_id==customer.id" in content
    assert '"settlements"' in content


def test_customer_history_limit_on_results():
    """Customer history should limit results to prevent performance issues."""
    route_code = Path(__file__).parents[1] / "app" / "api" / "routes" / "customers.py"
    content = route_code.read_text()
    
    assert ".limit(100)" in content
