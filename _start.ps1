$ErrorActionPreference = "SilentlyContinue"
$root = "C:\Users\Suriyaprakash\Desktop\Deepseek_Test"

# --- Backend (FastAPI / uvicorn) ---
Set-Location (Join-Path $root "apps\backend")
$env:PYTHONPATH = "."
Start-Process -FilePath "python" -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","3001" `
    -RedirectStandardOutput "backend.log" -RedirectStandardError "backend.err.log" -WindowStyle Hidden

# --- Frontend (Next.js dev) ---
Set-Location (Join-Path $root "apps\frontend")
Start-Process -FilePath "npm.cmd" -ArgumentList "run","dev" `
    -RedirectStandardOutput "frontend.log" -RedirectStandardError "frontend.err.log" -WindowStyle Hidden

Start-Sleep -Seconds 12

$b = @(Get-NetTCPConnection -LocalPort 3001 -State Listen -ErrorAction SilentlyContinue)
$f = @(Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue)
Write-Output ("backend  3001 listening: " + $b.Count + $(if ($b.Count) { " (pid " + $b[0].OwningProcess + ")" }))
Write-Output ("frontend 3000 listening: " + $f.Count + $(if ($f.Count) { " (pid " + $f[0].OwningProcess + ")" }))