param([Parameter(Mandatory=$true)][string]$ServerUrl,[switch]$Devtools)
$ErrorActionPreference = "Stop"
$root=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

try { $uri = [Uri]$ServerUrl } catch { throw "ServerUrl must be a valid absolute URL, for example http://192.168.1.50:8000" }
if (-not $uri.IsAbsoluteUri -or [string]::IsNullOrWhiteSpace($uri.Host)) { throw "ServerUrl must be an absolute URL." }
if ($uri.Scheme -notin @("http","https")) { throw "ServerUrl must use http or https." }

$base = $uri.AbsoluteUri.TrimEnd('/')

# Build-time reachability check only. The packaged client does NOT embed this
# address: production Tauri builds resolve the server at runtime via mDNS +
# /discovery/info identity verification, falling back to Admin manual override.
try { $h = Invoke-WebRequest -Uri "$base/health" -UseBasicParsing -TimeoutSec 5; Write-Host "Server reachable: $base/health -> $($h.StatusCode)" }
catch { Write-Warning "Cannot reach $base/health from this PC. The exe will build, but login will fail until the server is reachable (check IP, server running, firewall)." }

$frontend = Join-Path $root "frontend"
Set-Location $frontend
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw "npm was not found. Install Node.js/npm before building the POS client." }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "node was not found. Install Node.js before building the POS client." }

# Production builds intentionally do NOT inject an absolute VITE_API_BASE.
# The runtime client discovers the POS server via mDNS; a relative /api/v1
# keeps Vite dev proxy working without baking a LAN IP into the bundle.
$env:VITE_API_BASE="/api/v1"
$env:VITE_API_TIMEOUT_MS="15000"

if (Test-Path "package-lock.json") {
    npm ci
} else {
    npm install
}
if ($LASTEXITCODE -ne 0) { throw "npm install failed." }
npm run build
if ($LASTEXITCODE -ne 0) { throw "Frontend build FAILED (see the errors above). No exe was produced." }

# Safety check: the built client must NOT contain a hardcoded absolute server
# address. It must rely on runtime discovery instead.
$bundle = Get-ChildItem (Join-Path $frontend "dist\assets") -Filter *.js | Select-String -SimpleMatch "$base/api/v1" -List
if ($bundle) { throw "Server address $base/api/v1 was found in the built client. Production builds must NOT bake in a LAN IP; remove the absolute VITE_API_BASE injection." }
Write-Host "Verified: client is built WITHOUT a hardcoded server address (runtime mDNS discovery)."

$desktop = Join-Path $root "desktop\tauri"
if (-not (Test-Path (Join-Path $desktop "tauri.conf.json"))) { throw "Tauri configuration not found under $desktop." }
Set-Location $desktop
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) { throw "cargo was not found. Install Rust/Tauri build prerequisites before packaging the desktop client." }
if (-not (Get-Command cargo-tauri -ErrorAction SilentlyContinue) -and -not (cargo tauri --version 2>$null)) { throw "Tauri CLI missing. Run: cargo install tauri-cli --version `"^2`" --locked" }
if ($Devtools) { cargo tauri build --features devtools } else { cargo tauri build }
if ($LASTEXITCODE -ne 0) { throw "cargo tauri build FAILED (see errors above)." }