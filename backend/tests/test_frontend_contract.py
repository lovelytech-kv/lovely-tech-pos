from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"


def test_frontend_package_has_reproducible_build_scripts_and_no_latest_versions():
    package = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    scripts = package["scripts"]
    assert scripts["build"] == "tsc -b && vite build"
    assert scripts["e2e"] == "playwright test"
    all_versions = {}
    all_versions.update(package.get("dependencies", {}))
    all_versions.update(package.get("devDependencies", {}))
    assert all_versions
    assert all(v != "latest" for v in all_versions.values())


def test_frontend_env_example_does_not_hardcode_shop_ip():
    env = (FRONTEND / ".env.example").read_text(encoding="utf-8")
    assert "CASHIER-LAPTOP-IP" in env
    assert "192.168.1.10" not in env


def test_client_build_script_accepts_server_url_and_prefers_lockfile():
    script = (ROOT / "scripts" / "windows" / "Build-LovelyTechClient.ps1").read_text(encoding="utf-8")
    assert "$ServerUrl" in script
    assert "npm ci" in script
    assert "npm install" in script
    assert 'VITE_API_BASE' in script
    assert 'cargo tauri build' in script


def test_playwright_smoke_uses_login_screen_contract():
    spec = (FRONTEND / "tests" / "e2e" / "smoke.spec.ts").read_text(encoding="utf-8")
    assert "Lovely Tech" in spec
    assert "getByRole('button', { name: 'Login' })" in spec
