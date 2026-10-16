import os, subprocess

root = r"C:\Lovely Tech POS"
test_path = os.path.join(root, "backend", "tests", "test_import_staging_models.py")

test_code = """import pytest
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
"""

# Overwrite the test file with the fixed tests
with open(test_path, 'w', encoding='utf-8') as f:
    f.write(test_code)

print("Fixed tests/test_import_staging_models.py")

backend_dir = os.path.join(root, "backend")
pytest_exe = os.path.join(backend_dir, ".venv", "Scripts", "pytest.exe")
if not os.path.exists(pytest_exe): pytest_exe = "pytest"

print("\n========== RUNNING FIXED TESTS ==========")
env = os.environ.copy()
env["PYTHONPATH"] = backend_dir

res_test = subprocess.run([pytest_exe, "-v", "tests/test_import_staging_models.py"], cwd=backend_dir, capture_output=True, text=True, env=env)
print(res_test.stdout)
if res_test.stderr:
    print(res_test.stderr)