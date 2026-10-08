"""Live API smoke test (no extra packages). Run against STAGING first.

  python scripts/smoke_api.py http://127.0.0.1:8001 admin 'AdminPass' cashier 'CashierPass'
Checks: health/readiness, admin+cashier login, and that a Cashier is refused Admin-only endpoints
(requirements: Cashier must never reach cost/backup/restore data through the API).
"""
import json, sys, urllib.request, urllib.error

def call(base, method, path, token=None, body=None):
    req = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Content-Type", "application/json")
    if token: req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=15) as r: return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")

def check(name, ok):
    print(("PASS  " if ok else "FAIL  ") + name); return ok

def main():
    if len(sys.argv) < 6: raise SystemExit(__doc__)
    base, au, ap, cu, cp = sys.argv[1:6]; base = base.rstrip("/"); results = []
    results.append(check("health", call(base, "GET", "/health")[0] == 200))
    results.append(check("readiness (DB)", call(base, "GET", "/health/readiness")[0] == 200))
    s, a = call(base, "POST", "/api/v1/auth/login", body={"username": au, "password": ap})
    results.append(check("admin login", s == 200)); at = a.get("access_token")
    s, c = call(base, "POST", "/api/v1/auth/login", body={"username": cu, "password": cp})
    results.append(check("cashier login", s == 200)); ct = c.get("access_token")
    results.append(check("no token -> 401", call(base, "GET", "/api/v1/auth/me")[0] == 401))
    for path in ("/api/v1/backup/points", "/api/v1/purchases/pending-costs"):
        results.append(check(f"cashier blocked (403) {path}", call(base, "GET", path, ct)[0] == 403))
        results.append(check(f"admin allowed {path}", call(base, "GET", path, at)[0] == 200))
    s, r = call(base, "POST", "/api/v1/reports/sales-summary", ct, {"start": "2026-01-01", "end": "2026-12-31"})
    results.append(check("cashier sales-summary hides profit", s == 200 and r.get("gross_profit") is None and r.get("cost_total") is None))
    print("\nALL PASS" if all(results) else "\nSOME CHECKS FAILED"); sys.exit(0 if all(results) else 1)

main()
