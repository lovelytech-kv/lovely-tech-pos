import pytest
from app.models.import_staging import ImportBatch, ImportStagingRow

def test_import_batch_attributes():
    batch = ImportBatch(branch_id="test-branch", filename="test.xlsx", uploaded_by="test-user")
    assert batch.filename == "test.xlsx"
    assert batch.branch_id == "test-branch"
    assert batch.uploaded_by == "test-user"

def test_import_staging_row_attributes():
    row = ImportStagingRow(batch_id="test-batch", row_number=1, row_type="ITEM", raw_data={"CODE": "A"})
    assert row.batch_id == "test-batch"
    assert row.row_type == "ITEM"
    assert row.raw_data["CODE"] == "A"
