from app.services.numbering import NumberingService


class _Result:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row


class _FakeDb:
    def __init__(self, next_value=None):
        self.next_value = next_value
        self.statements = []

    def execute(self, stmt, params=None):
        sql = str(stmt)
        self.statements.append(sql)
        if sql.startswith("SELECT"):
            return _Result(None if self.next_value is None else {"next_value": self.next_value})
        return _Result(None)


def test_default_format_unchanged_for_documents():
    assert NumberingService.next_number(_FakeDb(), "INV", "b") == "INV-000001"
    assert NumberingService.next_number(_FakeDb(41), "REP", "b") == "REP-000041"


def test_item_code_format_matches_requirements_lvt0001():
    assert NumberingService.next_number(_FakeDb(), "ITEM", "b", label="LVT", sep="", width=4) == "LVT0001"
    assert NumberingService.next_number(_FakeDb(12), "ITEM", "b", label="LVT", sep="", width=4) == "LVT0012"
    # grows past four digits instead of truncating or reusing codes
    assert NumberingService.next_number(_FakeDb(10000), "ITEM", "b", label="LVT", sep="", width=4) == "LVT10000"
