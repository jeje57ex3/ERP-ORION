# ============================================================
# Orion ERP — Script de démarrage développement
# Lance : MySQL (XAMPP) + Django + SIÈCLE Store + LUNEA Store
# Usage : .\start-dev.ps1
# ============================================================

$ROOT = $PSScriptRoot

# ── Couleurs console ──────────────────────────────────────────
function Write-Step($msg) { Write-Host "`n[>>] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  [!!] $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "  [XX] $msg" -ForegroundColor Red }

# Teste si un port est ouvert (IPv4 puis IPv6, avec AddressFamily correct)
function Test-Port($port) {
    # IPv4
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient([System.Net.Sockets.AddressFamily]::InterNetwork)
        $tcp.Connect([System.Net.IPAddress]::Parse("127.0.0.1"), $port)
        $tcp.Close()
        return $true
    } catch {}
    # IPv6
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient([System.Net.Sockets.AddressFamily]::InterNetworkV6)
        $tcp.Connect([System.Net.IPAddress]::Parse("::1"), $port)
        $tcp.Close()
        return $true
    } catch {}
    return $false
}

# ────────────────────────────────────────────────────────────
# 1. MySQL / XAMPP
# ────────────────────────────────────────────────────────────
Write-Step "MySQL (XAMPP)..."

$mysqlRunning = (Test-Port 3306)

if ($mysqlRunning) {
    Write-Ok "MySQL déjà en cours d'exécution (port 3306)"
} else {
    $mysqld = "C:\xampp\mysql\bin\mysqld.exe"
    if (Test-Path $mysqld) {
        Start-Process $mysqld -ArgumentList "--defaults-file=C:\xampp\mysql\bin\my.ini","--standalone" -WindowStyle Hidden
        Write-Host "  Attente démarrage MySQL..." -ForegroundColor DarkGray
        $timeout = 15
        $elapsed = 0
        while ($elapsed -lt $timeout) {
            Start-Sleep -Seconds 1
            $elapsed++
            if (Test-Port 3306) {
                Write-Ok "MySQL démarré ($elapsed s)"
                break
            }
        }
        if ($elapsed -ge $timeout) { Write-Fail "MySQL n'a pas démarré en $timeout s — vérifiez XAMPP" }
    } else {
        Write-Fail "mysqld.exe introuvable à $mysqld"
    }
}

# ────────────────────────────────────────────────────────────
# 1bis. Redis (broker Celery / cache) — port 6379
# ────────────────────────────────────────────────────────────
Write-Step "Redis (port 6379)..."

$redisExe = "C:\Redis\redis-server.exe"
$redisConf = "C:\Redis\redis-orion.conf"

if (Test-Port 6379) {
    Write-Ok "Redis déjà en cours d'exécution (port 6379)"
} elseif (Test-Path $redisExe) {
    Start-Process $redisExe -ArgumentList $redisConf -WorkingDirectory "C:\Redis" -WindowStyle Hidden
    Start-Sleep -Seconds 2
    if (Test-Port 6379) { Write-Ok "Redis démarré" } else { Write-Fail "Redis n'a pas démarré" }
} else {
    Write-Fail "redis-server.exe introuvable à $redisExe"
}

# ────────────────────────────────────────────────────────────
# 2. Django ERP — port 9000 (login.elysiums.fr)
# ────────────────────────────────────────────────────────────
Write-Step "Django ERP (port 9000 — login.elysiums.fr)..."

$python = Join-Path $ROOT ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = Join-Path $ROOT "venv\Scripts\python.exe" }
$manage  = Join-Path $ROOT "manage.py"

if (-not (Test-Path (Join-Path $ROOT "logs"))) { New-Item -ItemType Directory -Force (Join-Path $ROOT "logs") | Out-Null }

$djangoErpUp = (Test-Port 9000)
if ($djangoErpUp) {
    Write-Warn "Port 9000 déjà occupé — Django ERP probablement déjà lancé"
} else {
    $logErp    = Join-Path $ROOT "logs\django_erp.log"
    $logErpErr = Join-Path $ROOT "logs\django_erp.err.log"
    Start-Process $python `
        -ArgumentList $manage,"runserver","9000" `
        -WorkingDirectory $ROOT `
        -WindowStyle Normal `
        -RedirectStandardOutput $logErp `
        -RedirectStandardError  $logErpErr
    Write-Ok "Django ERP lancé → http://localhost:9000  (log: logs\django_erp.log)"
}

# ────────────────────────────────────────────────────────────
# 3. Django Vitrine — port 5172 (orion.elysiums.fr)
# ────────────────────────────────────────────────────────────
Write-Step "Django Vitrine Orion (port 5172 — orion.elysiums.fr)..."

$djangoOrionUp = (Test-Port 5172)
if ($djangoOrionUp) {
    Write-Warn "Port 5172 déjà occupé — Django Vitrine probablement déjà lancé"
} else {
    $logOrion    = Join-Path $ROOT "logs\django_orion.log"
    $logOrionErr = Join-Path $ROOT "logs\django_orion.err.log"
    Start-Process $python `
        -ArgumentList $manage,"runserver","5172" `
        -WorkingDirectory $ROOT `
        -WindowStyle Normal `
        -RedirectStandardOutput $logOrion `
        -RedirectStandardError  $logOrionErr
    Write-Ok "Django Vitrine lancé → http://localhost:5172  (log: logs\django_orion.log)"
}

# ────────────────────────────────────────────────────────────
# 4. SIÈCLE Store (port 5173)
# ────────────────────────────────────────────────────────────
Write-Step "SIÈCLE Store — Vite (port 5173)..."

$siecleUp = (Test-Port 5173)
if ($siecleUp) {
    Write-Warn "Port 5173 déjà occupé — SIÈCLE probablement déjà lancé"
} else {
    $siecleDir = Join-Path $ROOT "frontend\siecle-store"
    Start-Process "cmd.exe" `
        -ArgumentList "/k","cd /d `"$siecleDir`" && npm run dev" `
        -WindowStyle Normal
    Write-Ok "SIÈCLE Store lancé → http://localhost:5173"
}

# ────────────────────────────────────────────────────────────
# 5. LUNEA Store (port 5174)
# ────────────────────────────────────────────────────────────
Write-Step "LUNEA Store — Vite (port 5174)..."

$luneaUp = (Test-Port 5174)
if ($luneaUp) {
    Write-Warn "Port 5174 déjà occupé — LUNEA probablement déjà lancé"
} else {
    $luneaDir = Join-Path $ROOT "frontend\lunea-store"
    Start-Process "cmd.exe" `
        -ArgumentList "/k","cd /d `"$luneaDir`" && npm run dev" `
        -WindowStyle Normal
    Write-Ok "LUNEA Store lancé → http://localhost:5174"
}

# ────────────────────────────────────────────────────────────
# 5bis. NÉOSTRUCTURA Site — port 5175 (ns.elysiums.fr)
# ────────────────────────────────────────────────────────────
Write-Step "NÉOSTRUCTURA Site — Vite (port 5175)..."

$neostructuraUp = (Test-Port 5175)
if ($neostructuraUp) {
    Write-Warn "Port 5175 déjà occupé — NÉOSTRUCTURA probablement déjà lancé"
} else {
    $neostructuraDir = Join-Path $ROOT "frontend\neostructura-site"
    Start-Process "cmd.exe" `
        -ArgumentList "/k","cd /d `"$neostructuraDir`" && npm run dev" `
        -WindowStyle Normal
    Write-Ok "NÉOSTRUCTURA Site lancé → http://localhost:5175"
}

# ────────────────────────────────────────────────────────────
# 6. Cloudflare Tunnel — orion.elysiums.fr → localhost:5172
# ────────────────────────────────────────────────────────────
Write-Step "Cloudflare Tunnel (orion.elysiums.fr → port 5172)..."

$cfExe    = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
$cfConfig = "$env:USERPROFILE\.cloudflared\config.yml"

$cloudflaredRunning = Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue

if (-not (Test-Path $cfExe)) {
    Write-Fail "cloudflared.exe introuvable à $cfExe"
} elseif (-not (Test-Path $cfConfig)) {
    Write-Fail "config.yml introuvable à $cfConfig"
} elseif ($cloudflaredRunning) {
    Write-Warn "cloudflared déjà en cours d'exécution (PID $($cloudflaredRunning.Id -join ', ')) — pas relancé"
} else {
    Start-Process $cfExe `
        -ArgumentList "tunnel","--config",$cfConfig,"run" `
        -WindowStyle Minimized
    Write-Ok "Tunnel lance -> https://orion.elysiums.fr"
}

# ────────────────────────────────────────────────────────────
# 6bis. Celery worker + beat (tâches planifiées : capteurs santé,
# checks observabilité, OpsV2...)
# ────────────────────────────────────────────────────────────
Write-Step "Celery worker + beat..."

function Test-CeleryProcess($match) {
    try {
        return [bool](Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction Stop |
            Where-Object { $_.CommandLine -match $match })
    } catch { return $false }
}

if (Test-CeleryProcess 'celery.*worker') {
    Write-Warn "Celery worker déjà en cours d'exécution — pas relancé"
} else {
    Start-Process $python `
        -ArgumentList "-m","celery","-A","erp_btp","worker","--pool=solo","--loglevel=info" `
        -WorkingDirectory $ROOT -WindowStyle Normal `
        -RedirectStandardOutput (Join-Path $ROOT "logs\celery_worker.log") `
        -RedirectStandardError  (Join-Path $ROOT "logs\celery_worker.err.log")
    Write-Ok "Celery worker lancé (log: logs\celery_worker.log)"
}

if (Test-CeleryProcess 'celery.*beat') {
    Write-Warn "Celery beat déjà en cours d'exécution — pas relancé"
} else {
    Start-Process $python `
        -ArgumentList "-m","celery","-A","erp_btp","beat","--loglevel=info" `
        -WorkingDirectory $ROOT -WindowStyle Normal `
        -RedirectStandardOutput (Join-Path $ROOT "logs\celery_beat.log") `
        -RedirectStandardError  (Join-Path $ROOT "logs\celery_beat.err.log")
    Write-Ok "Celery beat lancé (log: logs\celery_beat.log)"
}

# ────────────────────────────────────────────────────────────
# 7. Résumé & ouverture navigateur
# ────────────────────────────────────────────────────────────
Write-Host "`n============================================" -ForegroundColor DarkGray
Write-Host "  Services Orion ERP" -ForegroundColor White
Write-Host "============================================" -ForegroundColor DarkGray
Write-Host "  ERP Login  http://localhost:9000  -> https://login.elysiums.fr" -ForegroundColor White
Write-Host "  ERP Orion  http://localhost:5172  -> https://orion.elysiums.fr" -ForegroundColor White
Write-Host "  SIECLE     http://localhost:5173  -> https://siecle.elysiums.fr" -ForegroundColor White
Write-Host "  LUNEA      http://localhost:5174  -> https://lunea.elysiums.fr" -ForegroundColor White
Write-Host "  NEOSTRUCTURA http://localhost:5175  -> https://ns.elysiums.fr" -ForegroundColor White
Write-Host "============================================`n" -ForegroundColor DarkGray

$open = Read-Host "Ouvrir les URLs dans le navigateur ? [O/n]"
if ($open -ne 'n' -and $open -ne 'N') {
    Start-Sleep -Seconds 3
    Start-Process "http://localhost:9000"
    Start-Sleep -Milliseconds 500
    Start-Process "http://localhost:5173"
    Start-Sleep -Milliseconds 500
    Start-Process "http://localhost:5174"
    Start-Sleep -Milliseconds 500
    Start-Process "http://localhost:5175"
}
