$ErrorActionPreference = "Stop"
New-NetFirewallRule -DisplayName "Lovely Tech POS FastAPI 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private -ErrorAction SilentlyContinue | Out-Null
Write-Host "Private-network TCP 8000 rule configured."
