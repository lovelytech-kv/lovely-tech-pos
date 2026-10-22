from sqlalchemy import text

class NumberingService:
    """Atomic human-facing number allocation; numbers are never reused."""
    @staticmethod
    def next_number(db, prefix: str, branch_id: str, *, label: str | None = None, sep: str = "-", width: int = 6) -> str:
        """Allocate the next number. ``prefix`` is the counter key; ``label``/``sep``/``width``
        only change how it is displayed (e.g. item codes such as LVT0001)."""
        shown = label or prefix
        # Counter table is introduced by the initial migration. SELECT FOR UPDATE
        # serializes allocation and permits gaps after rollback/cancel by policy.
        row = db.execute(text("SELECT next_value FROM document_counters WHERE prefix=:prefix AND branch_id IS NOT DISTINCT FROM :branch_id FOR UPDATE"), {"prefix": prefix, "branch_id": branch_id}).mappings().first()
        if row is None:
            db.execute(text("INSERT INTO document_counters(prefix, branch_id, next_value) VALUES (:prefix, :branch_id, 2)"), {"prefix": prefix, "branch_id": branch_id})
            return f"{shown}{sep}{1:0{width}d}"
        value = int(row["next_value"])
        db.execute(text("UPDATE document_counters SET next_value=:next WHERE prefix=:prefix AND branch_id IS NOT DISTINCT FROM :branch_id"), {"next": value + 1, "prefix": prefix, "branch_id": branch_id})
        return f"{shown}{sep}{value:0{width}d}"
