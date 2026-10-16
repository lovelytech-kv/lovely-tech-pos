import os, json, re

root = r"C:\Lovely Tech POS"

def log(m=""):
    print(m)

log("\n========== 1. PROJECT AND TASK STATUS ==========")
log(f"Current Directory: {root}")

files_to_check = [
    r"docs\project-status.json",
    r"docs\project-dashboard.html",
    r"docs\REQUIREMENTS.md",
    r"docs\PROJECT_STATUS.md",
    r"docs\DATA_IMPORT_AND_MIGRATION.md",
    r"docs\ARCHITECTURE.md"
]

for rel in files_to_check:
    f = os.path.join(root, rel)
    if os.path.exists(f):
        log(f"\n--- {f} ---")
        if f.endswith(".json"):
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    j = json.load(file)
                if "project-status.json" in f:
                    log(json.dumps(j, indent=2))
            except Exception as e:
                log(f"JSON parse error: {e}")
        elif "project-dashboard.html" in f:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    for line in file:
                        if re.search(r"const SEED|T-004|Historical spreadsheet|Historical data import", line, re.I):
                            log(line.strip())
            except: pass
        else:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    lines = file.readlines()
                    for i, line in enumerate(lines):
                        if re.search(r"historical|spreadsheet|import|staging|duplicate|reconcil|provenance|approval|stock|FIFO|financial|R-07|T-004", line, re.I):
                            log(f"Line {i+1}: {line.strip()}")
            except: pass
    else:
        log(f"NOT FOUND: {f}")

log("\n========== 2. IMPORT-RELATED SOURCE FILES ==========")
roots2 = [
    os.path.join(root, "backend", "app"),
    os.path.join(root, "backend", "tests"),
    os.path.join(root, "frontend", "src"),
    os.path.join(root, "frontend", "tests"),
    os.path.join(root, "docs")
]
patt2 = re.compile(r"historical import|spreadsheet import|import preview|import staging|provenance|duplicate detection|import batch|import reconciliation|DATA_IMPORT_AND_MIGRATION", re.I)
for r in roots2:
    if os.path.exists(r):
        log(f"\n--- Searching {r} ---")
        for dp, dn, fn in os.walk(r):
            if any(x in dp for x in ['node_modules', '.venv', 'dist', 'build', 'target', '__pycache__']): continue
            for f in fn:
                if f.endswith(('.py', '.ts', '.tsx', '.json', '.md', '.sql')):
                    path = os.path.join(dp, f)
                    try:
                        with open(path, 'r', encoding='utf-8') as file:
                            if patt2.search(file.read()):
                                log(path)
                    except: pass

log("\n========== 3. BACKEND IMPORT, STOCK AND FINANCIAL STRUCTURE ==========")
backend_app = os.path.join(root, "backend", "app")
if os.path.exists(backend_app):
    for item in os.listdir(backend_app):
        p = os.path.join(backend_app, item)
        if os.path.isdir(p): log(p)
    for item in ["api", "models", "schemas", "services", "core", "db"]:
        p = os.path.join(backend_app, item)
        if os.path.exists(p):
            for dp, dn, fn in os.walk(p):
                for f in fn:
                    if f.endswith(".py"): log(os.path.join(dp, f))

log("\n--- Existing import and reconciliation references ---")
patt3 = re.compile(r"UploadFile|multipart|openpyxl|pandas|csv|import_id|idempotency|FIFO|stock_movement|inventory|opening balance|ledger|reconciliation", re.I)
if os.path.exists(backend_app):
    for dp, dn, fn in os.walk(backend_app):
        if '__pycache__' in dp or '.venv' in dp: continue
        for f in fn:
            if f.endswith(".py"):
                path = os.path.join(dp, f)
                try:
                    with open(path, 'r', encoding='utf-8') as file:
                        for i, line in enumerate(file):
                            if patt3.search(line):
                                log(f"{path}:{i+1}: {line.strip()}")
                except: pass

log("\n========== 4. FRONTEND ROUTES AND PERMISSIONS ==========")
frontend_src = os.path.join(root, "frontend", "src")
patt4 = re.compile(r"BACKUP_MANAGE|PRODUCT_MANAGE|STOCK|IMPORT|permission|ProtectedRoute|Admin|upload", re.I)
if os.path.exists(frontend_src):
    for dp, dn, fn in os.walk(frontend_src):
        if any(x in dp for x in ['node_modules', 'dist', 'build']): continue
        for f in fn:
            if f.endswith(('.ts', '.tsx')):
                path = os.path.join(dp, f)
                try:
                    with open(path, 'r', encoding='utf-8') as file:
                        for i, line in enumerate(file):
                            if patt4.search(line):
                                log(f"{path}:{i+1}: {line.strip()}")
                except: pass

log("\n========== 5. MIGRATION AND TEST INVENTORY ==========")
versions_dir = os.path.join(root, "backend", "alembic", "versions")
if os.path.exists(versions_dir):
    migs = sorted([f for f in os.listdir(versions_dir) if f.endswith(".py")])
    for m in migs[-8:]: log(m)

tests_dir = os.path.join(root, "backend", "tests")
if os.path.exists(tests_dir):
    for f in os.listdir(tests_dir):
        if "import" in f.lower() or "stock" in f.lower() or "fifo" in f.lower():
            log(f)

log("\n========== 6. SPREADSHEET FILE DISCOVERY ==========")
log("List spreadsheet filenames only; do not read spreadsheet contents or expose private business data.")
search_roots = [root, os.path.expanduser("~/Documents")]
for r in search_roots:
    if os.path.exists(r):
        for dp, dn, fn in os.walk(r):
            if any(x in dp for x in ['node_modules', '.venv', 'dist', 'build', 'target', 'AppData', '.git']): continue
            for f in fn:
                if f.endswith(('.xlsx', '.xls', '.csv', '.ods')) and not f.startswith("~$"):
                    log(os.path.join(dp, f))

log("\n========== PHASE 1 INSPECTION COMPLETE ==========")