Write-Host "========================================"
Write-Host " Orion ERP Desktop - Build Installer"
Write-Host "========================================"

$Root          = Split-Path -Parent $MyInvocation.MyCommand.Path
$InnoCompiler  = if (Test-Path "C:\Program Files (x86)\Inno Setup 6\ISCC.exe") {
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
} else {
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
}
$InnoScript     = Join-Path $Root "installer\orion_desktop_setup.iss"
$InnoScriptUser = Join-Path $Root "installer\orion_desktop_setup_user.iss"
$OutputDir      = Join-Path $Root "output\installers"
$Installer      = Join-Path $OutputDir "OrionERP-Desktop-Setup.exe"
$InstallerUser  = Join-Path $OutputDir "OrionERP-Desktop-User-Setup.exe"

# -- Environnement virtuel ------------------------------------------------------
if (-not (Test-Path (Join-Path $Root ".venv\Scripts\python.exe"))) {
    Write-Host ""
    Write-Host "Creation de l'environnement virtuel..."
    python -m venv (Join-Path $Root ".venv")
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"

Write-Host ""
Write-Host "Installation des dependances..."
& $Python -m pip install --upgrade pip --quiet
& $Python -m pip install -r (Join-Path $Root "requirements.txt") --quiet

# -- Nettoyage prealable (tue le processus si en cours) -------------------------
Write-Host ""
Write-Host "Arret de OrionERP-Desktop si en cours..."
Stop-Process -Name "OrionERP-Desktop" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Remove-Item (Join-Path $Root "dist")  -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $Root "build") -Recurse -Force -ErrorAction SilentlyContinue

# -- PyInstaller ----------------------------------------------------------------
Write-Host ""
Write-Host "Compilation PyInstaller..."
& $Python (Join-Path $Root "build_exe.py")
if (-not $?) { Write-Host "ERREUR : PyInstaller a echoue."; exit 1 }

# -- Nettoyage artefacts Qt -----------------------------------------------------
Write-Host ""
Write-Host "Nettoyage artefacts Qt..."
$DistPath = Join-Path $Root "dist\OrionERP-Desktop"
Get-ChildItem $DistPath -Recurse -Include "*.prl","*.lib","*.obj","*.pdb" -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem $DistPath -Recurse -Directory -Filter "objects-*" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force

# -- Verification Inno Setup ----------------------------------------------------
if (-not (Test-Path $InnoCompiler)) {
    Write-Host ""
    Write-Host "ERREUR : Inno Setup introuvable : $InnoCompiler"
    Write-Host "Installez Inno Setup 6 : https://jrsoftware.org/isinfo.php"
    exit 1
}

if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
}

# -- Build installateur entreprise (Program Files) ------------------------------
Write-Host ""
Write-Host "Creation installateur entreprise (Program Files)..."
& $InnoCompiler $InnoScript
if (-not $?) { Write-Host "ERREUR : Inno Setup a echoue (entreprise)."; exit 1 }

# -- Build installateur utilisateur (AppData) -----------------------------------
Write-Host ""
Write-Host "Creation installateur utilisateur (AppData, sans admin)..."
& $InnoCompiler $InnoScriptUser
if (-not $?) { Write-Host "ERREUR : Inno Setup a echoue (utilisateur)."; exit 1 }

# -- Resultat -------------------------------------------------------------------
Write-Host ""
Write-Host "========================================"
Write-Host " INSTALLATEURS GENERES"
Write-Host "========================================"

foreach ($f in @($Installer, $InstallerUser)) {
    if (Test-Path $f) {
        $mb = [math]::Round((Get-Item $f).Length / 1MB, 1)
        Write-Host "  OK  $(Split-Path $f -Leaf) ($mb MB)"
        Write-Host "      $f"
    } else {
        Write-Host "  MANQUANT : $f"
    }
}

Write-Host "========================================"
