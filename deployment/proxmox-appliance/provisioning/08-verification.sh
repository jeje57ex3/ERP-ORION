#!/usr/bin/env bash
# Orion ERP Appliance — Stage A / 08
# Dernière étape : vérifie que l'appliance est réellement utilisable, au lieu
# de se contenter d'avoir exécuté les étapes précédentes.
#
# Le travail est fait par scripts/orion-verifier.sh, installé dans
# /opt/orion/scripts par l'étape 07 : la même vérification doit pouvoir être
# relancée à tout moment par l'exploitant, pas seulement au premier démarrage.
# La dupliquer ici garantirait qu'une des deux copies dérive.

set -uo pipefail

# shellcheck source=lib/commun.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib/commun.sh"
ORION_ETAPE='08'

PAYLOAD_DIR="${PAYLOAD_DIR:-/opt/orion-appliance}"

for candidat in \
  /opt/orion/scripts/orion-verifier.sh \
  "$PAYLOAD_DIR/scripts/orion-verifier.sh"
do
  if [ -f "$candidat" ]; then
    # Les services viennent d'être démarrés : gunicorn, Celery et les SPA
    # mettent quelques secondes à accepter des connexions. Vérifier
    # immédiatement produirait des 502 qui ne reflètent rien.
    dire 'attente de 20 s pour laisser les services accepter des connexions...'
    sleep 20
    exec bash "$candidat"
  fi
done

echo "[08] ERREUR : orion-verifier.sh introuvable — rien n'a été vérifié." >&2
exit 1
