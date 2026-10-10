# ============================================================================
# Orion ERP — Export des données vers l'appliance Proxmox
#
# Produit une archive unique (base MySQL + médias + manifeste) à transférer sur
# la VM Proxmox, où install_orion_data.sh la restaure.
#
# L'appliance (build.sh) installe le CODE depuis Git mais démarre avec une base
# VIDE : ce script apporte les données réelles de ce poste.
#
# Usage :
#   .\deployment\proxmox-appliance\scripts\export_orion_data.ps1
#   .\deployment\proxmox-appliance\scripts\export_orion_data.ps1 -IncludeMobileBuilds
#   .\deployment\proxmox-appliance\scripts\export_orion_data.ps1 -OutputDir D:\transfert
#
# Les APK mobiles (~1 Go, artefacts reconstructibles) sont EXCLUS par défaut.
# ============================================================================
[CmdletBinding()]
param(
    [string]$OutputDir,
    [string]$EnvFile,
    [string]$MysqlBin = 'C:\xampp\mysql\bin',
    [switch]$IncludeMobileBuilds,
    [switch]$SkipMedia
)

$ErrorActionPreference = 'Stop'

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
if (-not $OutputDir) { $OutputDir = Join-Path $RootDir 'build' }
if (-not $EnvFile)   { $EnvFile   = Join-Path $RootDir '.env' }

function Write-Step($m) { Write-Host "`n[>>] $m" -ForegroundColor Cyan }
function Write-Ok($m)   { Write-Host "  [OK] $m" -ForegroundColor Green }
function Write-Warn($m) { Write-Host "  [!!] $m" -ForegroundColor Yellow }

# ── Lecture de la configuration base de données ────────────────────────────
Write-Step 'Lecture de la configuration'

if (-not (Test-Path $EnvFile)) { throw "Fichier .env introuvable : $EnvFile" }

$cfg = @{}
foreach ($line in Get-Content $EnvFile) {
    if ($line -match '^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$') {
        $cfg[$Matches[1]] = $Matches[2].Trim().Trim('"').Trim("'")
    }
}

$dbName = $cfg['DB_NAME']; $dbUser = $cfg['DB_USER']
$dbPass = $cfg['DB_PASSWORD']; $dbHost = $cfg['DB_HOST']; $dbPort = $cfg['DB_PORT']
if (-not $dbName) { throw 'DB_NAME absent du .env' }
if (-not $dbUser) { $dbUser = 'root' }
# 'localhost' force le named pipe sous Windows ; 127.0.0.1 force TCP.
if (-not $dbHost -or $dbHost -eq 'localhost') { $dbHost = '127.0.0.1' }
if (-not $dbPort) { $dbPort = '3306' }
Write-Ok "Base « $dbName » sur ${dbHost}:${dbPort} (utilisateur $dbUser)"

$mysqldump = Join-Path $MysqlBin 'mysqldump.exe'
if (-not (Test-Path $mysqldump)) { throw "mysqldump introuvable : $mysqldump (utilisez -MysqlBin)" }

$tar = Join-Path $env:SystemRoot 'System32\tar.exe'
if (-not (Test-Path $tar)) { throw "tar.exe introuvable — Windows 10 1803+ requis." }

# ── Préparation ─────────────────────────────────────────────────────────────
$stamp    = Get-Date -Format 'yyyyMMdd-HHmmss'
$bundle   = "orion-data-$stamp"
$workDir  = Join-Path $OutputDir $bundle
New-Item -ItemType Directory -Force -Path $workDir | Out-Null

# Le mot de passe ne doit jamais transiter par la ligne de commande (visible
# dans la liste des processus) : on passe par un fichier d'options temporaire.
$optFile = Join-Path $env:TEMP "orion-dump-$stamp.cnf"
@"
[client]
host=$dbHost
port=$dbPort
user=$dbUser
password="$dbPass"
"@ | Set-Content -Path $optFile -Encoding ASCII

try {
    # ── 1. Dump de la base ──────────────────────────────────────────────────
    Write-Step 'Export de la base MySQL'
    $sqlFile = Join-Path $workDir 'database.sql'

    # --single-transaction : dump cohérent sans verrouiller les tables.
    # --routines/--triggers : embarque procédures et déclencheurs.
    # --no-tablespaces : évite d'exiger le privilège PROCESS à la restauration.
    #
    # Start-Process -RedirectStandardOutput écrit les octets bruts de
    # mysqldump. Un simple « | Out-File » passerait par le pipeline
    # PowerShell, qui ajoute un BOM (refusé par MySQL : « ERROR 1064 near
    # '﻿' ») et ré-encode le texte, abîmant les accents au passage.
    $dumpErr = Join-Path $env:TEMP "orion-dump-$stamp.err"
    $proc = Start-Process -FilePath $mysqldump -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $sqlFile -RedirectStandardError $dumpErr `
        -ArgumentList @(
            "--defaults-file=$optFile", '--single-transaction', '--routines',
            '--triggers', '--no-tablespaces', '--default-character-set=utf8mb4', $dbName
        )
    if ($proc.ExitCode -ne 0) {
        $detail = if (Test-Path $dumpErr) { Get-Content $dumpErr -Raw } else { '' }
        throw "mysqldump a échoué (code $($proc.ExitCode)) : $detail"
    }
    Remove-Item -Force $dumpErr -ErrorAction SilentlyContinue

    $sqlSize = (Get-Item $sqlFile).Length
    if ($sqlSize -lt 1024) { throw "Dump suspicieusement vide ($sqlSize octets)" }

    # Garde-fou : un dump restaurable ne doit pas commencer par un BOM.
    $firstBytes = [System.IO.File]::ReadAllBytes($sqlFile)[0..2]
    if ($firstBytes[0] -eq 0xEF -and $firstBytes[1] -eq 0xBB -and $firstBytes[2] -eq 0xBF) {
        throw 'Le dump commence par un BOM UTF-8 — il serait rejeté par MySQL.'
    }
    $tableCount = (Select-String -Path $sqlFile -Pattern '^CREATE TABLE' -AllMatches).Count
    Write-Ok ("database.sql — {0:N1} Mo, {1} tables" -f ($sqlSize / 1MB), $tableCount)

    # ── 2. Médias ───────────────────────────────────────────────────────────
    $mediaFiles = 0; $mediaBytes = 0
    if (-not $SkipMedia) {
        Write-Step 'Export des médias'
        $mediaSrc = Join-Path $RootDir 'media'
        if (Test-Path $mediaSrc) {
            $mediaDst = Join-Path $workDir 'media'
            New-Item -ItemType Directory -Force -Path $mediaDst | Out-Null

            $items = Get-ChildItem -Path $mediaSrc -Recurse -File
            if (-not $IncludeMobileBuilds) {
                # Les APK sont des artefacts de build reconstructibles (~1 Go) :
                # les embarquer alourdirait l'archive sans apporter de donnée.
                $skipped = @($items | Where-Object { $_.Extension -in '.apk', '.aab' })
                if ($skipped.Count -gt 0) {
                    $items = $items | Where-Object { $_.Extension -notin '.apk', '.aab' }
                    $skippedMb = ($skipped | Measure-Object Length -Sum).Sum / 1MB
                    Write-Warn ("{0} build(s) mobile ignoré(s) ({1:N0} Mo) — -IncludeMobileBuilds pour les inclure" -f $skipped.Count, $skippedMb)
                }
            }

            foreach ($f in $items) {
                $rel = $f.FullName.Substring($mediaSrc.Length).TrimStart('\')
                $target = Join-Path $mediaDst $rel
                New-Item -ItemType Directory -Force -Path (Split-Path $target) | Out-Null
                Copy-Item $f.FullName $target
                $mediaFiles++; $mediaBytes += $f.Length
            }
            Write-Ok ("media/ — {0} fichier(s), {1:N1} Mo" -f $mediaFiles, ($mediaBytes / 1MB))
        } else {
            Write-Warn 'Dossier media/ absent — ignoré'
        }
    }

    # ── 3. Manifeste ────────────────────────────────────────────────────────
    Write-Step 'Génération du manifeste'
    $gitCommit = (& git -C $RootDir rev-parse --short HEAD 2>$null)
    if ($LASTEXITCODE -ne 0) { $gitCommit = 'inconnu' }
    $gitBranch = (& git -C $RootDir rev-parse --abbrev-ref HEAD 2>$null)
    if ($LASTEXITCODE -ne 0) { $gitBranch = 'inconnu' }

    # Le nom de la base diffère entre le poste de dev (erp_btp) et l'appliance
    # (orion_core) : install_orion_data.sh restaure dans la base cible définie
    # par le .env de la VM, le dump ne contient donc pas de CREATE DATABASE.
    $manifest = [ordered]@{
        format_version  = 1
        created_at      = (Get-Date -Format 'o')
        source_host     = $env:COMPUTERNAME
        source_db       = $dbName
        git_commit      = $gitCommit
        git_branch      = $gitBranch
        database_bytes  = $sqlSize
        database_tables = $tableCount
        media_files     = $mediaFiles
        media_bytes     = $mediaBytes
        mobile_builds   = [bool]$IncludeMobileBuilds
        database_sha256 = (Get-FileHash $sqlFile -Algorithm SHA256).Hash.ToLower()
    }
    $manifest | ConvertTo-Json | Set-Content -Path (Join-Path $workDir 'manifest.json') -Encoding utf8
    Write-Ok "manifest.json (commit $gitCommit / $gitBranch)"

    # ── 4. Archive ──────────────────────────────────────────────────────────
    Write-Step 'Compression'
    $archive = Join-Path $OutputDir "$bundle.tar.gz"
    & $tar -czf $archive -C $OutputDir $bundle
    if ($LASTEXITCODE -ne 0) { throw "tar a échoué (code $LASTEXITCODE)" }
    Remove-Item -Recurse -Force $workDir

    $archiveMb = (Get-Item $archive).Length / 1MB
    $sha = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLower()
    "$sha  $bundle.tar.gz" | Set-Content -Path "$archive.sha256" -Encoding ASCII

    Write-Host ''
    Write-Host '============================================================' -ForegroundColor Green
    Write-Host ' Archive de données prête' -ForegroundColor Green
    Write-Host '============================================================' -ForegroundColor Green
    Write-Host ("  Fichier : {0}" -f $archive)
    Write-Host ("  Taille  : {0:N1} Mo" -f $archiveMb)
    Write-Host ("  SHA-256 : {0}" -f $sha)
    Write-Host ''
    Write-Host '  Étapes suivantes :' -ForegroundColor Cyan
    Write-Host "    scp `"$archive`" root@<ip-vm>:/tmp/"
    Write-Host '    ssh root@<ip-vm>'
    Write-Host "    /opt/orion/backend/deployment/proxmox-appliance/scripts/install_orion_data.sh /tmp/$bundle.tar.gz"
    Write-Host ''
}
finally {
    Remove-Item -Force $optFile -ErrorAction SilentlyContinue
}
