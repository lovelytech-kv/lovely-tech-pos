import os, json, re

root = r"C:\Lovely Tech POS"

def log(msg=""):
    print(msg)

log("\n========== A1. CURRENT TASK STATUS ==========")
status_path = os.path.join(root, "docs", "project-status.json")
if os.path.exists(status_path):
    try:
        with open(status_path, 'r', encoding='utf-8') as f:
            j = json.load(f)
            log(json.dumps(j, indent=2))
    except Exception as e:
        log(f"Status JSON parse error: {e}")
else:
    log("Status JSON not found.")

log("\n========== A2. PACKET 1/2 IMPLEMENTATION FILES ==========")
backend_app = os.path.join(root, "backend", "app")
patt_a2 = re.compile(r"ImportBatch|ImportStagingRow|Import.*Schema|Item.*Import|Purchase.*Import|Sale.*Import|staging|import batch", re.I)
if os.path.exists(backend_app):
    for dp, dn, fn in os.walk(backend_app):
        if any(x in dp for x in ['__pycache__', '.venv']): continue
        for f in fn:
            if f.endswith('.py'):
                path = os.path.join(dp, f)
                try:
                    with open(path, 'r', encoding='utf-8') as file:
                        for i, line in enumerate(file):
                            if patt_a2.search(line):
                                log(f"{path}:{i+1}: {line.strip()}")
                except: pass

log("\n--- Migration 0033 ---")
versions_dir = os.path.join(root, "backend", "alembic", "versions")
if os.path.exists(versions_dir):
    for f in os.listdir(versions_dir):
        if "0033" in f:
            log(os.path.join(versions_dir, f))

log("\n========== A3. ROUTER REGISTRATION AND AUTHORIZATION PATTERNS ==========")
patt_a3 = re.compile(r"include_router|APIRouter|UploadFile|File\(|multipart|current_user|require_permission|permission_required|IMPORT|PRODUCT_MANAGE|BACKUP_MANAGE|reauth")
if os.path.exists(backend_app):
    for dp, dn, fn in os.walk(backend_app):
        if any(x in dp for x in ['__pycache__', '.venv']): continue
        for f in fn:
            if f.endswith('.py'):
                path = os.path.join(dp, f)
                try:
                    with open(path, 'r', encoding='utf-8') as file:
                        for i, line in enumerate(file):
                            if patt_a3.search(line):
                                log(f"{path}:{i+1}: {line.strip()}")
                except: pass

log("\n========== A4. SPREADSHEET DEPENDENCIES ==========")
toml_path = os.path.join(root, "backend", "pyproject.toml")
if os.path.exists(toml_path):
    patt_a4 = re.compile(r"openpyxl|pandas|xlrd|python-multipart|csv|pytest|httpx")
    try:
        with open(toml_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            for i, line in enumerate(lines):
                if patt_a4.search(line):
                    log(f"Line {i+1}: {line.strip()}")
    except: pass

log("\n========== A5. TEST FIXTURES AND EXISTING API TEST PATTERNS ==========")
backend_tests = os.path.join(root, "backend", "tests")
patt_a5 = re.compile(r"TestClient|AsyncClient|client\.post|dependency_overrides|db_session|session_factory|permission|override")
if os.path.exists(backend_tests):
    for f in os.listdir(backend_tests):
        if f.endswith('.py'): log(os.path.join(backend_tests, f))
    
    match_count = 0
    for dp, dn, fn in os.walk(backend_tests):
        if any(x in dp for x in ['__pycache__', '.venv']): continue
        for f in fn:
            if f.endswith('.py'):
                path = os.path.join(dp, f)
                try:
                    with open(path, 'r', encoding='utf-8') as file:
                        for i, line in enumerate(file):
                            if patt_a5.search(line):
                                if match_count < 100:
                                    log(f"{path}:{i+1}: {line.strip()}")
                                    match_count += 1
                except: pass

log("\n========== A6. IMPORT DOCUMENTATION ==========")
docs = [
    os.path.join(root, "docs", "DATA_IMPORT_AND_MIGRATION.md"),
    os.path.join(root, "docs", "REQUIREMENTS.md"),
    os.path.join(root, "docs", "OPERATIONS_AND_RECOVERY.md")
]
patt_a6 = re.compile(r"historical|spreadsheet|import|staging|duplicate|preview|reconciliation", re.I)
for doc in docs:
    if os.path.exists(doc):
        log(f"\n--- {doc} ---")
        try:
            with open(doc, 'r', encoding='utf-8') as file:
                for i, line in enumerate(file):
                    if patt_a6.search(line):
                        log(f"Line {i+1}: {line.strip()}")
        except: pass

log("\n========== PHASE A COMPLETE ==========")