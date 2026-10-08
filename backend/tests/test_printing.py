from decimal import Decimal
from app.printing.templates import render_receipt_text, render_a5_warranty_text

def test_receipt_template_contains_totals_and_payments():
    out = render_receipt_text(shop_name='Lovely Tech', invoice_no='INV-0001', lines=[{'description':'USB Cable','quantity':2,'final_total':Decimal('500')}], subtotal=Decimal('500'), discount_total=Decimal('0'), grand_total=Decimal('500'), payments=[{'method':'CASH','amount':Decimal('500')}])
    assert 'Lovely Tech' in out and 'INV-0001' in out and 'Rs. 500.00' in out and 'CASH' in out

def test_a5_warranty_template_contains_expiry():
    out = render_a5_warranty_text(shop_name='Lovely Tech', claim_no='WCL-1', invoice_no='INV-1', item_description='Display', serial_number='123', purchase_date='2026-09-23', warranty_expiry='2027-09-23')
    assert 'WARRANTY DOCUMENT' in out and 'Warranty Expiry: 2027-09-23' in out
