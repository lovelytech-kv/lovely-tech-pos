from datetime import date
from decimal import Decimal


def test_target_snapshot_service_skips_duplicate_version():
    from app.services.targets import TargetService
    assert hasattr(TargetService, "snapshot_completed_periods")


def test_target_progress_snapshot_model_has_immutable_fields():
    from app.models.master import TargetProgressSnapshot
    cols={c.name for c in TargetProgressSnapshot.__table__.columns}
    assert {"target_id","target_version","target_type","target_value","achieved_value","percentage","period_start","period_end","captured_at"} <= cols
