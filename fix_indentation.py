import os
import subprocess
import json
import re
from datetime import datetime

root = r"C:\Lovely Tech POS"
backend_dir = os.path.join(root, "backend")
router_file = os.path.join(backend_dir, "app", "api", "router.py")
timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

# Fix the IndentationError in router.py
try:
    with open(router_file, "r", encoding="utf-8") as f:
        router_code = f.read()
    
    # Remove the extra spaces before api_router.include_router(historical_import.router)
    fixed_code = router_code.replace("    api_router.include_router(historical_import.router)", "api_router.include_router(historical_import.router)")
    
    with open(router_file, "w", encoding="utf-8") as f:
        f.write(fixed_code)
    print("Indentation fixed in router.py. Running tests...\n")
except Exception as e:
    print(f"Error modifying router.py: {e}")

pytest_exe = os.path.join(backend_dir, ".venv", "Scripts", "pytest.exe")
if not os.path.exists(pytest_exe): pytest_exe = "pytest"

env = os.environ.copy()
env["PYTHONPATH"] = backend_dir
res = subprocess.run([pytest_exe, "-v", "tests/test_historical_import_api.py"], cwd=backend_dir, capture_output=True, text=True, env=env)
print(res.stdout)
if res.stderr:
    print(res.stderr)

if res.returncode == 0:
    print("\n========== UPDATING DASHBOARD ==========")
    s_json = os.path.join(root, "docs", "project-status.json")
    s_html = os.path.join(root, "docs", "project-dashboard.html")
    
    with open(s_json, 'r', encoding='utf-8') as f:
        d = json.load(f)
    for task in d.get("tasks", []):
        if task.get("id") == "T-004":
            task["status"] = "IN PROGRESS"
            task["evidence"] = "Packet 1 (Schemas), Packet 2 (Staging Models), and Packet 3 (Backend Upload/Preview API) implemented and tested. Support limited to CSV uploads due to missing openpyxl/pandas dependencies."
    
    j_str = json.dumps(d, indent=4)
    with open(s_json, 'w', encoding='utf-8') as f: f.write(j_str)
    
    try:
        with open(s_html, 'r', encoding='utf-8') as f: h_data = f.read()
        h_new = re.sub(r'(<script\s+id="project-data"\s+type="application/json">).*?(</script>)', lambda m: f"{m.group(1)}\n{j_str}\n{m.group(2)}", h_data, flags=re.DOTALL)
        with open(s_html, 'w', encoding='utf-8') as f: f.write(h_new)
    except: pass
    print("Dashboard updated successfully. T-004 status set to IN PROGRESS.")