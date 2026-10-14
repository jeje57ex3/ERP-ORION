#!/usr/bin/env bash
# Vérifie provisioning/lib/commun.sh contre les pannes réelles qu'il supprime.
#
# Chaque bloc nomme la panne de production correspondante : ces tests ne sont
# pas des vérifications d'API, ce sont des régressions. Lancé aussi par
# tests/test_installation_appliance.py.
#
#   bash deployment/proxmox-appliance/tests/test_commun.sh

set -uo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../provisioning/lib/commun.sh
. "$ICI/../provisioning/lib/commun.sh"

TRAVAIL="$(mktemp -d)"
trap 'rm -rf "$TRAVAIL"' EXIT

ko=0
verifie() {
  if [ "$2" = "$3" ]; then
    printf '  ok     %s\n' "$1"
  else
    printf '  ECHEC  %s : attendu [%s], obtenu [%s]\n' "$1" "$3" "$2"
    ko=1
  fi
}

CAS="$TRAVAIL/cas.env"
cat > "$CAS" <<'ENV'
# commentaire

NU=sudo -n systemctl restart orion-celery
CITE="sudo -n systemctl restart orion-celery"
SIMPLE=localhost,127.0.0.1
VIDE=
DOLLAR=a$bc
PARENTH=echo (bizarre)
BACKTICK=`hostname`
  INDENTE=valeur
ENV
printf 'CRLF=valeur\r\n' >> "$CAS"

echo '--- 1. le sourçage shell meurt sur ce fichier (cause du exit 127 en prod)'
# ORION_UPDATE_CELERY_RESTART_COMMAND=sudo -n ... non cité : bash lisait
# « VAR=sudo » puis exécutait « -n ». Tout le provisioning d'une VM neuve s'est
# arrêté là, sur un message qui ne nommait ni la clé ni le fichier.
if ( set -euo pipefail; set -a; . "$CAS"; set +a ) >/dev/null 2>&1; then
  echo '  ECHEC  le sourçage a réussi : le cas de test ne reproduit plus la panne'
  ko=1
else
  echo '  ok     le sourçage échoue bien, charger_env est donc nécessaire'
fi

echo '--- 2. charger_env lit tout, sans jamais rien exécuter'
charger_env "$CAS"
verifie 'valeur à espaces non citée' "$NU" 'sudo -n systemctl restart orion-celery'
verifie 'valeur à espaces citée'     "$CITE" 'sudo -n systemctl restart orion-celery'
verifie 'valeur simple'              "$SIMPLE" 'localhost,127.0.0.1'
verifie 'valeur vide'                "$VIDE" ''
verifie 'dollar non interprété'      "$DOLLAR" 'a$bc'
verifie 'parenthèses'                "$PARENTH" 'echo (bizarre)'
verifie 'accent grave non exécuté'   "$BACKTICK" '`hostname`'
verifie 'retour chariot retiré'      "$CRLF" 'valeur'
verifie 'ligne indentée'             "$INDENTE" 'valeur'

echo '--- 3. une clé ABSENTE ne tue pas le script (cause du 502 nginx)'
# L'ancien « grep | head | cut » dans refresh_allowed_hosts.sh héritait du code
# d'erreur de grep sous pipefail ; set -e tuait alors le script sur une clé
# simplement absente. Ce script étant un ExecStartPre d'orion-backend ET
# d'orion-frontend, les deux services refusaient de démarrer.
manquante="$(valeur_env "$CAS" ORION_NODE_DOMAIN)"
verifie 'clé absente -> chaîne vide' "$manquante" ''
verifie 'clé présente'               "$(valeur_env "$CAS" CITE)" 'sudo -n systemctl restart orion-celery'
verifie 'le script vit toujours'     'vivant' 'vivant'

echo '--- 4. ecrire_env survit aux caractères qui cassent sed'
ECR="$TRAVAIL/ecrire.env"
printf 'A=1\nB=2\n' > "$ECR"
ecrire_env "$ECR" B 'x#y&z/w'
ecrire_env "$ECR" NOUVELLE 'valeur avec espaces'
verifie 'valeur contenant # & /' "$(valeur_env "$ECR" B)" 'x#y&z/w'
verifie 'clé ajoutée'            "$(valeur_env "$ECR" NOUVELLE)" 'valeur avec espaces'
verifie 'clé voisine intacte'    "$(valeur_env "$ECR" A)" '1'
# Le .env est en 600 orion:orion. La propriété visée est la réécriture EN PLACE
# (même inode) : un « mv » depuis mktemp y substituerait 600 root, et le
# service ne pourrait plus lire son environnement. L'inode est vérifiable
# partout, contrairement aux droits POSIX sous Git Bash.
avant="$(stat -c %i "$ECR")"
ecrire_env "$ECR" A '9'
verifie 'réécriture en place (inode)' "$(stat -c %i "$ECR")" "$avant"

echo '--- 5. normaliser_env répare, et ne fait rien la seconde fois'
NORM="$TRAVAIL/norm.env"
cp "$CAS" "$NORM"
normaliser_env "$NORM" >/dev/null
empreinte="$(md5sum < "$NORM")"
normaliser_env "$NORM" >/dev/null
verifie 'seconde passe sans effet' "$(md5sum < "$NORM")" "$empreinte"
# La valeur doit survivre intacte à la normalisation.
( charger_env "$NORM"; verifie 'valeur préservée' "$NU" 'sudo -n systemctl restart orion-celery' ) || ko=1
verifie 'valeur désormais citée' \
  "$(grep -c '^NU="sudo -n systemctl restart orion-celery"$' "$NORM")" '1'

echo '--- 6. HOME garanti même quand rien ne le définit'
# « qm guest exec » n'en définit aucun : git refuse sa config, la CLI Ollama
# panique (« panic: $HOME is not defined »).
vu="$( unset HOME; . "$ICI/../provisioning/lib/commun.sh"; printf '%s' "$HOME" )"
verifie 'HOME retombe sur /root' "$vu" '/root'

echo '--- 7. verdict_etape distingue « rien à signaler » de « des anomalies »'
( ORION_DEFAUTS=(); verdict_etape >/dev/null 2>&1 ) \
  && echo '  ok     aucun défaut -> succès' \
  || { echo '  ECHEC  aucun défaut devrait réussir'; ko=1; }
( ORION_DEFAUTS=('un défaut'); verdict_etape >/dev/null 2>&1 ) \
  && { echo '  ECHEC  un défaut devrait échouer'; ko=1; } \
  || echo '  ok     un défaut -> échec signalé'

if [ "$ko" -eq 0 ]; then
  echo 'TOUT PASSE'
else
  echo 'DES TESTS ECHOUENT' >&2
fi
exit "$ko"
