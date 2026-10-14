#!/usr/bin/env bash
# Orion ERP Appliance — orchestrateur du provisioning.
#
# Un seul point d'entrée pour toutes les étapes, appelé par une unique ligne de
# cloud-init. Ce fichier existe parce que la liste des étapes vivait dans le
# gabarit cloud-init, ce qui a coûté cher trois fois :
#
#   - l'ordre réel (07 AVANT 03) n'était qu'un commentaire YAML ; rien ne
#     l'imposait, et l'inverser laissait les services sans leurs ExecStartPre,
#     donc morts, donc nginx en 502 ;
#   - chaque ligne refaisait « set -a; . build-info.env; . deploy-info.env »,
#     c'est-à-dire exécutait ces fichiers — dont l'un contient des jetons
#     (CF_TUNNEL_TOKEN, GITHUB_TOKEN) aux caractères quelconques ;
#   - l'échec d'une étape ne se voyait nulle part : chaque étape redirigeait sa
#     sortie vers un fichier, et plus rien ne disait laquelle avait manqué. Les
#     pannes ont toutes été découvertes dans un navigateur, plusieurs étapes en
#     aval, sous un symptôme qui ne désignait pas leur cause.
#
# Ici : l'ordre est du code, l'environnement est lu sans être exécuté, aucune
# étape n'est sautée à cause d'une précédente, et le verdict final est écrit à
# un endroit lisible (console, journal, /etc/motd).

# Volontairement PAS « set -e » : l'orchestrateur doit survivre à l'échec d'une
# étape pour exécuter les suivantes et rendre son verdict. Les étapes, elles,
# gardent « set -e » chacune pour son propre compte.
set -uo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/commun.sh
. "$ICI/lib/commun.sh"
ORION_ETAPE='00'
journaliser_vers_fichier_et_console

PAYLOAD_DIR="${PAYLOAD_DIR:-/opt/orion-appliance}"

echo ''
echo '======================================================================'
echo " Orion ERP — provisioning de l'appliance — $(date -u +%FT%TZ)"
echo '======================================================================'

# ─── Bits d'exécution ─────────────────────────────────────────────────────────
# git conserve le mode des fichiers : un script committé en 100644 arrive ici
# non exécutable, et l'appel échoue en « command not found » — message qui
# laisse croire à un script absent, pas à un droit manquant. Constaté sur
# orion-mesh.sh, dont TOUS les boutons de la page Réseau privé renvoyaient
# cette erreur. On le corrige à la source, pour tous les scripts à la fois.
chmod +x "$ICI"/*.sh "$PAYLOAD_DIR"/scripts/*.sh "$PAYLOAD_DIR"/scripts/*.py 2>/dev/null || true

# ─── Environnement du déploiement, lu sans être exécuté ───────────────────────
# build-info.env : valeurs figées à la construction de l'image.
# deploy-info.env : valeurs propres à CETTE VM (domaines, jetons).
# charger_env exporte chaque clé sans jamais interpréter sa valeur — un jeton
# contenant un espace, un « $ » ou une parenthèse ne peut plus rien casser.
for fichier in "$PAYLOAD_DIR/build-info.env" "$PAYLOAD_DIR/deploy-info.env"; do
  if [ -f "$fichier" ]; then
    charger_env "$fichier" && dire "environnement chargé : $fichier"
  else
    avertir "$fichier absent — les valeurs qu'il porte prendront leur défaut."
  fi
done

# ─── Les étapes, dans leur ordre d'exécution réel ─────────────────────────────
# 07 avant 03, et ce n'est pas une coquille : 07 installe
# /opt/orion/scripts/wait_for_port.sh et refresh_allowed_hosts.sh, que les
# ExecStartPre d'orion-backend et d'orion-frontend exigent. Dans l'autre ordre,
# systemd échoue en 203/EXEC, les deux services restent morts et nginx répond
# 502 — sans que rien ne mentionne un script manquant.
#
# 08 est la vérification finale : elle doit rester en dernier, et s'exécuter
# même si une étape précédente a échoué, puisque son rôle est précisément de
# dire ce qui ne marche pas.
ETAPES=(
  '01-system-packages.sh'
  '02-deploy-orion.sh'
  '07-backup-cron.sh'
  '03-systemd-units.sh'
  '04-nginx-config.sh'
  '05-cloudflared-config.sh'
  '06-ufw-fail2ban.sh'
  '08-verification.sh'
)

: > "$ORION_ETAT"
RESULTATS=()
EN_ECHEC=()

for etape in "${ETAPES[@]}"; do
  chemin="$ICI/$etape"
  nom="${etape%.sh}"
  if [ ! -f "$chemin" ]; then
    avertir "étape introuvable, ignorée : $chemin"
    RESULTATS+=("$nom ABSENTE")
    EN_ECHEC+=("$nom (fichier absent)")
    continue
  fi

  echo ''
  echo "----------------------------------------------------------------------"
  echo " étape $nom"
  echo "----------------------------------------------------------------------"
  # « bash <chemin> » et non « $chemin » : fonctionne même si le bit
  # d'exécution manque, pour la même raison que le chmod ci-dessus.
  bash "$chemin"
  code=$?
  # Le préfixe numérique seul : « tr -dc 0-9 » ramassait tous les chiffres du
  # nom, et « 06-ufw-fail2ban » devenait ETAPE_062 à cause du 2 de fail2ban.
  printf 'ETAPE_%s=%s\n' "${nom%%-*}" "$code" >> "$ORION_ETAT"
  if [ "$code" -eq 0 ]; then
    RESULTATS+=("$nom ok")
  else
    RESULTATS+=("$nom ECHEC (code $code)")
    EN_ECHEC+=("$nom (code $code)")
    # On continue : une étape manquée ne doit pas priver la machine de tout le
    # reste, et surtout pas de la vérification finale.
    avertir "l'étape $nom a échoué (code $code) — on poursuit."
  fi
done

# ─── Verdict ──────────────────────────────────────────────────────────────────
echo ''
echo '======================================================================'
echo ' Récapitulatif du provisioning'
echo '======================================================================'
for ligne in "${RESULTATS[@]}"; do printf '  %s\n' "$ligne"; done
echo ''

RAPPORT="${ORION_RAPPORT:-/opt/orion/logs/provisioning.txt}"
# Surchargeable pour les essais ; /etc/motd en production.
MOTD="${ORION_MOTD:-/etc/motd}"
mkdir -p "$(dirname "$RAPPORT")" 2>/dev/null || true
{
  printf 'Provisioning Orion ERP — %s\n\n' "$(date -u +%FT%TZ)"
  for ligne in "${RESULTATS[@]}"; do printf '  %s\n' "$ligne"; done
} > "$RAPPORT" 2>/dev/null || true

if [ ${#EN_ECHEC[@]} -eq 0 ]; then
  echo ' Provisioning terminé — aucune étape en échec.'
  cat > "$MOTD" <<'FIN' || true

  Orion ERP — appliance prête.

  Ouvrez un navigateur sur le domaine (ou l'IP) de cette machine pour créer
  votre compte administrateur : /setup/

  Détail du provisioning : /opt/orion/logs/provisioning.txt
  Vérification à tout moment : /opt/orion/scripts/orion-verifier.sh

FIN
  exit 0
fi

echo " $(printf '%s' "${#EN_ECHEC[@]}") étape(s) en échec :" >&2
for ligne in "${EN_ECHEC[@]}"; do printf '  - %s\n' "$ligne" >&2; done
# Le message d'accueil de la VM dit la vérité : une appliance à moitié
# installée qui affiche « prête » envoie l'exploitant chercher la panne dans
# son navigateur, à trois étapes de sa cause.
{
  printf '\n  Orion ERP — provisioning INCOMPLET.\n\n'
  printf '  Étapes en échec :\n'
  for ligne in "${EN_ECHEC[@]}"; do printf '    - %s\n' "$ligne"; done
  printf '\n  Journal complet   : %s\n' "$ORION_LOG"
  printf '  Récapitulatif     : %s\n' "$RAPPORT"
  printf '  Revérifier        : bash /opt/orion/scripts/orion-verifier.sh\n\n'
} > "$MOTD" 2>/dev/null || true
exit 1
