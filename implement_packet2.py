import os, subprocess

root = r"C:\Lovely Tech POS"
models_dir = os.path.join(root, "backend", "app", "models")
migration_dir = os.path.join(root, "backend", "alembic", "versions")
test_path = os.path.join(root, "backend", "tests", "test_import_staging_models.py")

model_path = os.path.join(models_dir, "import_staging.py")
migration_path = os.path.join(migration_dir, "0033_historical_import_staging.py")

model_code = """from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.db.session import Base

class ImportBatch(Base):
    __tablename__ = "import_batches"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    branch_id = Column(String(36), ForeignKey("branches.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    uploaded_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    uploaded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    status = Column(String(50), default="PENDING_APPROVAL", nullable=False)
    approved_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    rows = relationship("ImportStagingRow", back_populates="batch", cascade="all, delete-orphan")

class ImportStagingRow(Base):
    __tablename__ = "import_staging_rows"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_id = Column(String(36), ForeignKey("import_batches.id"), nullable=False)
    row_number = Column(Integer, nullable=False)
    row_type = Column(String(50), nullable=False)
    raw_data = Column(JSON, nullable=False)
    validation_status = Column(String(50), default="PENDING", nullable=False)
    error_details = Column(Text, nullable=True)
    reference_id = Column(String(36), nullable=True)

    batch = relationship("ImportBatch", back_populates="rows")
"""

migration_code = '''"""historical import staging

Revision ID: 0033_historical_import_staging
Revises: 0032_shop_identity_metadata
Create Date: 2026-10-13 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '0033_historical_import_staging'
down_revision = '0032_shop_identity_metadata'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table('import_batches',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('uploaded_by', sa.String(length=36), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('approved_by', sa.String(length=36), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('import_staging_rows',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('batch_id', sa.String(length=36), nullable=False),
        sa.Column('row_number', sa.Integer(), nullable=False),
        sa.Column('row_type', sa.String(length=50), nullable=False),
        sa.Column('raw_data', sa.JSON(), nullable=False),
        sa.Column('validation_status', sa.String(length=50), nullable=False),
        sa.Column('error_details', sa.Text(), nullable=True),
        sa.Column('reference_id', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(['batch_id'], ['import_batches.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade() -> None:
    op.drop_table('import_staging_rows')
    op.drop_table('import_batches')
'''

test_code = """import pytest
from app.models.import_staging import ImportBatch, ImportStagingRow

def test_import_batch_initialization():
    batch = ImportBatch(branch_id="test-branch", filename="test.xlsx", uploaded_by="test-user")
    assert batch.status == "PENDING_APPROVAL"
    assert batch.filename == "test.xlsx"

def test_import_staging_row_initialization():
    row = ImportStagingRow(batch_id="test-batch", row_number=1, row_type="ITEM", raw_data={"CODE": "A"})
    assert row.validation_status == "PENDING"
    assert row.row_type == "ITEM"
    assert row.raw_data["CODE"] == "A"
"""

with open(model_path, 'w', encoding='utf-8') as f:
    f.write(model_code)

with open(migration_path, 'w', encoding='utf-8') as f:
    f.write(migration_code)

with open(test_path, 'w', encoding='utf-8') as f:
    f.write(test_code)

print("Created app/models/import_staging.py")
print("Created alembic/versions/0033_historical_import_staging.py")
print("Created tests/test_import_staging_models.py")

backend_dir = os.path.join(root, "backend")
pytest_exe = os.path.join(backend_dir, ".venv", "Scripts", "pytest.exe")
if not os.path.exists(pytest_exe): pytest_exe = "pytest"

print("\n========== RUNNING TESTS AND ALEMBIC CHECK FOR PACKET 2 ==========")
env = os.environ.copy()
env["PYTHONPATH"] = backend_dir

res_test = subprocess.run([pytest_exe, "-v", "tests/test_import_staging_models.py"], cwd=backend_dir, capture_output=True, text=True, env=env)
print(res_test.stdout)

python_exe = os.path.join(backend_dir, ".venv", "Scripts", "python.exe")
res_alembic = subprocess.run([python_exe, "-m", "alembic", "heads"], cwd=backend_dir, capture_output=True, text=True, env=env)
print("\n========== ALEMBIC HEADS ==========")
print(res_alembic.stdout)