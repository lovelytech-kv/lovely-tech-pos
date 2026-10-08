from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
import socket

class PrinterAdapter(Protocol):
    def print_text(self, text: str) -> None: ...

@dataclass
class FilePrinterAdapter:
    target: Path
    def print_text(self, text: str) -> None:
        self.target.parent.mkdir(parents=True, exist_ok=True)
        self.target.write_text(text, encoding="utf-8")

@dataclass
class WindowsSpoolerAdapter:
    printer_name: str
    def print_text(self, text: str) -> None:
        # Optional Windows dependency. Import lazily so the server remains
        # portable during development and tests.
        try:
            import win32print  # type: ignore
        except ImportError as exc:
            raise RuntimeError("Windows printing requires pywin32 on the Windows host") from exc
        handle = win32print.OpenPrinter(self.printer_name)
        try:
            job = win32print.StartDocPrinter(handle, 1, ("Lovely Tech POS", None, "RAW"))
            try:
                win32print.StartPagePrinter(handle)
                try:
                    data = text.replace("\n", "\r\n").encode("cp437", errors="replace")
                    win32print.WritePrinter(handle, data)
                finally:
                    win32print.EndPagePrinter(handle)
            finally:
                win32print.EndDocPrinter(handle)
        finally:
            win32print.ClosePrinter(handle)

@dataclass
class EscPosAdapter:
    printer_host: str
    printer_port: int = 9100
    timeout_seconds: float = 5.0
    cut_paper: bool = True
    def print_text(self, text: str) -> None:
        payload = bytearray()
        payload += b"\x1b@"  # initialize
        payload += text.replace("\n", "\r\n").encode("cp437", errors="replace")
        payload += b"\n\n\n"
        if self.cut_paper:
            payload += b"\x1dV\x00"
        with socket.create_connection((self.printer_host, self.printer_port), timeout=self.timeout_seconds) as sock:
            sock.sendall(payload)
