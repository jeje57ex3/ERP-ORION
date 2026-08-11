#!/usr/bin/env python3
"""
Orion ERP Appliance — orion-health.service (toutes les 60s)

Vérifie 8 services, redémarre ce qui est en panne, journalise, notifie.
Structure calquée sur server_tools/orion_cloudflare_guard.py (même dépôt) pour
rester cohérent avec l'outil de garde déjà utilisé en production — étendue ici
à l'infrastructure complète de l'appliance (DB/Redis/Nginx inclus).

Usage :
  python3 orion_health_check.py                  # vérifie + répare
  python3 orion_health_check.py --dry-run         # vérifie seulement
  python3 orion_health_check.py --no-restart --json
"""

import argparse
import datetime
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ORION_HOME = Path("/opt/orion")
ENV_FILE = ORION_HOME / "backend" / ".env"
LOG_DIR = ORION_HOME / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "orion_health.log"
REPORT_FILE = LOG_DIR / "orion_health_report.json"
LOCK_FILE = Path("/tmp/orion_health_check.lock")
COMPOSE_FILE = ORION_HOME / "docker" / "docker-compose.yml"


def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


ENV = load_env()

# SIÈCLE/LUNEA ne sont construits et démarrés (03-systemd-units.sh) que si un
# domaine Login a été fourni au déploiement (deploy.sh) — leur build Vite a
# besoin de VITE_API_BASE_URL=https://<login-domain>/api/v1. Sans domaine
# (accès par IP), ces services n'existent tout simplement pas : les compter
# comme "required" ferait échouer orion-health.service en boucle.
_FRONTENDS_BUILT = bool(ENV.get("ORION_LOGIN_DOMAIN", "").strip())

CHECKS = [
    {"name": "Cloudflare Tunnel", "kind": "systemd", "unit": "cloudflared", "required": False},
    {"name": "Nginx", "kind": "systemd", "unit": "nginx", "port": 80, "required": True},
    {"name": "MySQL", "kind": "docker", "container": "orion-db", "port": 3306, "required": True},
    {"name": "Redis", "kind": "docker", "container": "orion-redis", "port": 6379, "required": True},
    {"name": "Orion Backend (login)", "kind": "systemd", "unit": "orion-backend",
     "port": 9000, "url": "http://127.0.0.1:9000/", "required": True},
    {"name": "Orion Frontend (vitrine)", "kind": "systemd", "unit": "orion-frontend",
     "port": 5172, "url": "http://127.0.0.1:5172/", "required": True},
    {"name": "SIÈCLE Store", "kind": "systemd", "unit": "siecle-frontend",
     "port": 5173, "url": "http://127.0.0.1:5173/", "required": _FRONTENDS_BUILT},
    {"name": "LUNEA Store", "kind": "systemd", "unit": "lunea-frontend",
     "port": 5174, "url": "http://127.0.0.1:5174/", "required": _FRONTENDS_BUILT},
]


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def log(message):
    line = f"[{now_iso()}] {message}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(command, timeout=30):
    try:
        result = subprocess.run(
            command, shell=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
        )
        return {"ok": result.returncode == 0, "returncode": result.returncode,
                 "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": -1, "stdout": "", "stderr": "timeout"}


def check_port(host, port, timeout=4):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def check_http(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "OrionHealthCheck/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.getcode() < 500
    except urllib.error.HTTPError as exc:
        return 200 <= exc.code < 500
    except Exception:
        return False


def systemd_active(unit):
    return run(f"systemctl is-active {unit}", timeout=10)["stdout"].strip() == "active"


def systemd_exists(unit):
    result = run(f"systemctl status {unit} --no-pager", timeout=10)
    text = f"{result['stdout']} {result['stderr']}".lower()
    return "could not be found" not in text and "loaded: not-found" not in text


def restart_systemd(unit, dry_run=False):
    if dry_run:
        log(f"DRY-RUN restart skipped: {unit}")
        return True
    log(f"Restart systemd unit: {unit}")
    result = run(f"systemctl restart {unit}", timeout=90)
    time.sleep(3)
    return result["ok"] and systemd_active(unit)


def restart_docker(container, dry_run=False):
    if dry_run:
        log(f"DRY-RUN restart skipped (docker): {container}")
        return True
    log(f"Restart docker container: {container}")
    result = run(f"docker compose -f {COMPOSE_FILE} restart {container}", timeout=120)
    time.sleep(5)
    return result["ok"]


def acquire_lock():
    if LOCK_FILE.exists():
        age = time.time() - LOCK_FILE.stat().st_mtime
        if age < 240:
            log("Une autre vérification est déjà en cours. Stop.")
            return False
        LOCK_FILE.unlink(missing_ok=True)
    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
    return True


def release_lock():
    LOCK_FILE.unlink(missing_ok=True)


def notify(critical):
    webhook = ENV.get("ORION_HEALTH_NOTIFY_WEBHOOK", "").strip()
    if not webhook or not critical:
        return
    payload = json.dumps({
        "text": f"Orion ERP Appliance — {len(critical)} service(s) en échec",
        "critical": critical,
        "generated_at": now_iso(),
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            webhook, data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as exc:
        log(f"Notification webhook échouée : {exc}")


def evaluate_check(check):
    if check["kind"] == "systemd":
        exists = systemd_exists(check["unit"])
        active = systemd_active(check["unit"]) if exists else False
        port_ok = check_port("127.0.0.1", check["port"]) if "port" in check and active else (not check.get("port"))
        http_ok = check_http(check["url"]) if "url" in check and port_ok else True
        healthy = exists and active and port_ok and http_ok
    elif check["kind"] == "docker":
        port_ok = check_port("127.0.0.1", check["port"])
        healthy = port_ok
    else:
        healthy = False

    return {"name": check["name"], "kind": check["kind"], "required": check["required"], "healthy": healthy}


def repair(check, dry_run):
    if check["kind"] == "systemd":
        return restart_systemd(check["unit"], dry_run=dry_run)
    if check["kind"] == "docker":
        return restart_docker(check["container"], dry_run=dry_run)
    return False


def build_report(dry_run=False, no_restart=False):
    if not acquire_lock():
        return {"ok": False, "skipped": True, "reason": "lock_active"}

    try:
        log("Démarrage orion-health — 8 services (nginx/mysql/redis/cloudflared/backend/frontend/siecle/lunea)")

        results = [evaluate_check(c) for c in CHECKS]
        repairs = []

        if not no_restart:
            for check, result in zip(CHECKS, results):
                if not result["healthy"] and result["required"]:
                    ok = repair(check, dry_run=dry_run)
                    repairs.append({"name": check["name"], "ok": ok})

            if repairs:
                time.sleep(8)
                results = [evaluate_check(c) for c in CHECKS]

        critical = [r["name"] for r in results if r["required"] and not r["healthy"]]

        report = {
            "generated_at": now_iso(),
            "ok": len(critical) == 0,
            "dry_run": dry_run,
            "no_restart": no_restart,
            "checks": results,
            "repairs": repairs,
            "critical": critical,
        }
        REPORT_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

        if report["ok"]:
            log("Tous les services requis sont sains.")
        else:
            log(f"{len(critical)} service(s) requis en échec : {', '.join(critical)}")
            notify(critical)

        return report
    finally:
        release_lock()


def main():
    parser = argparse.ArgumentParser(description="Orion ERP Appliance — vérification de santé")
    parser.add_argument("--dry-run", action="store_true", help="Vérifie seulement, ne redémarre rien")
    parser.add_argument("--no-restart", action="store_true", help="Collecte le rapport sans réparer")
    parser.add_argument("--json", action="store_true", dest="json_out", help="Affiche le rapport JSON")
    args = parser.parse_args()

    report = build_report(dry_run=args.dry_run, no_restart=args.no_restart)

    if args.json_out:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
