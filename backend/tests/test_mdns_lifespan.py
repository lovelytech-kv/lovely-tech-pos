"""Regression: zeroconf's sync API must never run on the event-loop thread.

Running ``register_service`` on the loop thread raises EventLoopBlocked after a long
timeout, which made LAN discovery silently fail and delayed server startup.
"""
import asyncio
import threading
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as main_module


def _on_event_loop_thread() -> bool:
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


def test_mdns_start_and_stop_run_off_the_event_loop_thread():
    on_loop: dict[str, bool] = {}

    def fake_start():
        on_loop["start"] = _on_event_loop_thread()

    def fake_stop():
        on_loop["stop"] = _on_event_loop_thread()

    with patch.object(main_module, "start_mdns_advertisement", fake_start), \
         patch.object(main_module, "stop_mdns_advertisement", fake_stop):
        with TestClient(main_module.app) as client:
            assert client.get("/health").status_code == 200

    assert on_loop == {"start": False, "stop": False}


def test_startup_does_not_wait_for_slow_mdns_registration():
    release = threading.Event()

    def slow_start():
        release.wait(timeout=10)

    try:
        with patch.object(main_module, "start_mdns_advertisement", slow_start), \
             patch.object(main_module, "stop_mdns_advertisement", lambda: None):
            with TestClient(main_module.app) as client:
                # Server answers while mDNS registration is still "in progress".
                assert client.get("/health").status_code == 200
                release.set()
    finally:
        release.set()
