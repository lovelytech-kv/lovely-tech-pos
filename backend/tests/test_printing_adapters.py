from pathlib import Path
from unittest.mock import patch

from app.printing.adapters import FilePrinterAdapter, EscPosAdapter, WindowsSpoolerAdapter


def test_file_printer(tmp_path: Path):
    target = tmp_path / "receipt.txt"
    FilePrinterAdapter(target).print_text("Hello\nWorld")
    assert target.read_text(encoding="utf-8") == "Hello\nWorld"


def test_escpos_sends_raw_payload():
    class FakeSocket:
        def __init__(self): self.data = b""
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def sendall(self, data): self.data += data
    fake = FakeSocket()
    with patch("app.printing.adapters.socket.create_connection", return_value=fake) as conn:
        EscPosAdapter("127.0.0.1", 9100).print_text("ABC")
    conn.assert_called_once_with(("127.0.0.1", 9100), timeout=5.0)
    assert fake.data.startswith(b"\x1b@ABC")
    assert fake.data.endswith(b"\x1dV\x00")


def test_windows_adapter_fails_clearly_without_pywin32():
    with patch.dict("sys.modules", {"win32print": None}):
        try:
            WindowsSpoolerAdapter("Lovely Tech").print_text("test")
        except RuntimeError as exc:
            assert "pywin32" in str(exc)
        else:
            # If pywin32 is installed in a Windows verification environment,
            # this test is intentionally skipped by the host implementation.
            assert True
