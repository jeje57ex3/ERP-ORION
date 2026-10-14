#!/usr/bin/env bash
# Orion ERP Appliance — Stage A / 07
# Installe les scripts opérationnels dans /opt/orion/scripts et programme la
# sauvegarde quotidienne à 2 h.
#
# Exécutée AVANT l'étape 03 (voir 00-provisionner.sh) : les ExecStartPre
# d'orion-backend et d'orion-frontend invoquent /opt/orion/scripts/
# wait_for_port.sh et refresh_allowed_hosts.sh. Absents, systemd échoue en
# 203/EXEC, les deux services restent morts, et nginx répond 502 sans jamais
# mentionner un script manquant.

set -euo pipefail

# shellcheck source=lib/commun.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib/commun.sh"
ORION_ETAPE='07'
journaliser_vers_fichier_et_console

echo "=== [07] Scripts + cron sauvegarde — $(date -u +%FT%TZ) ==="

PAYLOAD_DIR="${PAYLOAD_DIR:-/opt/orion-appliance}"
ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p /opt/orion/scripts
cp "$PAYLOAD_DIR"/scripts/*.sh /opt/orion/scripts/
cp "$PAYLOAD_DIR"/scripts/*.py /opt/orion/scripts/

# commun.sh accompagne les scripts d'exploitation : orion-verifier.sh et les
# autres en dépendent, et doivent rester lançables sans le payload de
# provisioning (qu'une machine remise à jour peut ne plus avoir).
cp "$ICI/lib/commun.sh" /opt/orion/scripts/commun.sh

# git conserve le mode des fichiers : un script committé en 100644 arrive ici
# non exécutable et échoue en « command not found » — message qui laisse croire
# à un script absent plutôt qu'à un droit manquant. Tous les boutons de la page
# Réseau privé renvoyaient cette erreur pour orion-mesh.sh.
chmod +x /opt/orion/scripts/*.sh /opt/orion/scripts/*.py
chown -R orion:orion /opt/orion/scripts

# Vérifié, pas supposé : ces deux scripts conditionnent le démarrage des
# services applicatifs. Mieux vaut échouer ici, où la cause est nommée, qu'à
# l'étape 03 sous la forme d'un service mort.
for requis in wait_for_port.sh refresh_allowed_hosts.sh; do
  if [ -x "/opt/orion/scripts/$requis" ]; then
    dire "ok   $requis installé et exécutable"
  else
    echo "[07] ERREUR : /opt/orion/scripts/$requis manquant ou non exécutable." >&2
    echo "[07] orion-backend et orion-frontend ne démarreraient pas (nginx 502)." >&2
    exit 1
  fi
done

cat > /etc/cron.d/orion-backup <<'EOF'
# Orion ERP Appliance — sauvegarde quotidienne (DB + uploads + config)
0 2 * * * root /opt/orion/scripts/backup.sh >> /opt/orion/logs/backup.log 2>&1
EOF
chmod 0644 /etc/cron.d/orion-backup

echo "[07] Terminé."
