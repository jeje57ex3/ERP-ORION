#!/usr/bin/env bash
# Orion ERP Appliance — fonctions communes à toutes les étapes de provisioning
# et aux scripts d'exploitation.
#
# Ce fichier existe parce que les mêmes quatre causes ont produit, séparément,
# cinq pannes de provisioning qui n'avaient AUCUN symptôme commun :
#
#   1. $HOME absent. « qm guest exec » — le seul accès à une appliance sans clé
#      SSH — n'en définit aucun, et cloud-init ne le garantit pas non plus.
#      git refuse alors de lire sa configuration, la CLI Ollama panique
#      (« panic: $HOME is not defined »), npm écrit son cache dans /.npm.
#   2. .env sourcé par le shell. Une seule valeur contenant un espace sans
#      guillemets rendait l'étape fatale ET muette : bash lisait « VAR=sudo »
#      puis exécutait « -n », d'où « -n: command not found » et un exit 127 qui
#      ne nommait ni la clé ni le fichier. Sourcer un fichier de configuration,
#      c'est en exécuter le contenu ; on le PARSE désormais.
#   3. git exécuté par root sur un dépôt appartenant à orion
#      (« detected dubious ownership »), parce que le provisioning clone en root
#      puis chown vers orion.
#   4. Échecs tolérés mais jamais vérifiés. Un collectstatic manqué ne se voyait
#      qu'à trois étapes en aval, sous la forme de « toutes les pages en 500 ».
#
# Chaque fonction ci-dessous supprime une de ces causes, au lieu d'en traiter
# les symptômes un par un.

# ─── 1. Environnement minimal garanti ─────────────────────────────────────────
# $HOME n'est PAS garanti : ni par « qm guest exec », ni par les runcmd de
# cloud-init, ni par une unité systemd. Beaucoup d'outils en dépendent sans le
# dire — et aucun ne nomme la variable manquante dans son message d'erreur.
export HOME="${HOME:-/root}"
export DEBIAN_FRONTEND=noninteractive
# npm, sans HOME exploitable, écrit son cache à la racine du disque.
export npm_config_cache="${npm_config_cache:-/root/.npm}"

ORION_LOG="${ORION_LOG:-/var/log/orion-provision.log}"
ORION_ETAT="${ORION_ETAT:-/var/log/orion-provision-etat.env}"

# ─── Journalisation visible à deux endroits ───────────────────────────────────
# Les étapes redirigeaient tout vers un fichier (« exec >> ... 2>&1 »). Pratique
# pour l'archive, désastreux pour le diagnostic : la console de la VM et la
# sortie de « qm guest exec » ne montraient plus RIEN, pas même l'échec. On
# duplique donc vers les deux.
journaliser_vers_fichier_et_console() {
  mkdir -p "$(dirname "$ORION_LOG")" 2>/dev/null || true
  exec > >(tee -a "$ORION_LOG") 2>&1
}

dire()      { printf '[%s] %s\n' "${ORION_ETAPE:-orion}" "$*"; }
avertir()   { printf '[%s] ATTENTION : %s\n' "${ORION_ETAPE:-orion}" "$*" >&2; }
echouer()   { printf '[%s] ERREUR : %s\n' "${ORION_ETAPE:-orion}" "$*" >&2; return 1; }

# Mémorise un défaut sans interrompre l'étape, pour un verdict groupé à la fin.
# Un provisioning qui s'arrête à la première anomalie laisse une appliance à
# moitié installée dont plus rien ne dit ce qui manque.
ORION_DEFAUTS=()
retenir_defaut() { ORION_DEFAUTS+=("$1"); avertir "$1"; }

verdict_etape() {
  if [ ${#ORION_DEFAUTS[@]} -eq 0 ]; then
    dire 'Terminé, sans anomalie.'
    return 0
  fi
  printf '\n[%s] %d anomalie(s) :\n' "${ORION_ETAPE:-orion}" "${#ORION_DEFAUTS[@]}" >&2
  local d
  for d in "${ORION_DEFAUTS[@]}"; do printf '  - %s\n' "$d" >&2; done
  return 1
}

# ─── 2. Lecture du .env SANS l'exécuter ───────────────────────────────────────
# `set -a; . fichier` exécute le fichier. Toute valeur non citée contenant un
# espace, un `$`, une parenthèse ou un accent grave est au mieux déformée, au
# pire exécutée. Ce parseur ne fait qu'affecter des variables : aucune valeur
# n'est jamais interprétée, et une ligne malformée est signalée au lieu de tuer
# le script.
charger_env() {
  local fichier="$1"
  [ -f "$fichier" ] || { echouer "fichier d'environnement introuvable : $fichier"; return 1; }

  local ligne cle valeur
  while IFS= read -r ligne || [ -n "$ligne" ]; do
    ligne="${ligne%$'\r'}"          # fichier passé par Windows
    ligne="${ligne#"${ligne%%[![:space:]]*}"}"   # espaces de tête
    case "$ligne" in ''|'#'*) continue ;; esac
    ligne="${ligne#export }"
    case "$ligne" in *=*) ;; *) continue ;; esac

    cle="${ligne%%=*}"
    valeur="${ligne#*=}"
    case "$cle" in ''|*[!A-Za-z0-9_]*) continue ;; esac

    if [ ${#valeur} -ge 2 ]; then
      case "$valeur" in
        '"'*'"') valeur="${valeur:1:${#valeur}-2}" ;;
        "'"*"'") valeur="${valeur:1:${#valeur}-2}" ;;
      esac
    fi
    export "$cle=$valeur"
  done < "$fichier"
}

# Lit UNE clé sans rien exporter. Remplace le « grep | head | cut » qui, sous
# `set -o pipefail`, faisait échouer tout le script sur une clé simplement
# ABSENTE du fichier — c'est ce défaut qui a mis nginx en 502, les deux
# services refusant de démarrer à cause de leur ExecStartPre.
valeur_env() {
  local fichier="$1" cle="$2" ligne valeur=''
  [ -f "$fichier" ] || { printf '%s' ''; return 0; }
  while IFS= read -r ligne || [ -n "$ligne" ]; do
    ligne="${ligne%$'\r'}"
    case "$ligne" in
      "$cle"=*)
        valeur="${ligne#*=}"
        if [ ${#valeur} -ge 2 ]; then
          case "$valeur" in
            '"'*'"') valeur="${valeur:1:${#valeur}-2}" ;;
            "'"*"'") valeur="${valeur:1:${#valeur}-2}" ;;
          esac
        fi
        break
        ;;
    esac
  done < "$fichier"
  printf '%s' "$valeur"
}

# Toute valeur écrite dans un .env l'est entre guillemets doubles. Vérifié :
# python-decouple et l'EnvironmentFile de systemd rendent la même chaîne avec ou
# sans guillemets, et aucun des deux n'interprète « $ » — citer
# systématiquement est donc sans effet de bord, et rend impossible la panne
# d'une valeur à espaces.
#
# Ce que des guillemets doubles ne font PAS : rendre le fichier sûr à sourcer.
# « $X » et « `cmd` » y restent interprétés par bash, et la seconde forme y
# serait EXÉCUTÉE. charger_env est donc le seul lecteur shell admis pour ce
# fichier ; ne jamais revenir à « set -a; . .env ».
citer_env() {
  local valeur="$1"
  valeur="${valeur//\\/\\\\}"
  valeur="${valeur//\"/\\\"}"
  printf '"%s"' "$valeur"
}

# Remplace la ligne si la clé existe, l'ajoute sinon. N'utilise PAS sed : le
# délimiteur d'une substitution sed se retrouve dans les valeurs réelles
# (« # », « & », « / »), et le remplacement y est réinterprété.
ecrire_env() {
  local fichier="$1" cle="$2" valeur="$3"
  local temporaire ligne trouve=0
  temporaire="$(mktemp)"
  if [ -f "$fichier" ]; then
    while IFS= read -r ligne || [ -n "$ligne" ]; do
      case "${ligne%$'\r'}" in
        "$cle"=*)
          if [ "$trouve" -eq 0 ]; then
            printf '%s=%s\n' "$cle" "$(citer_env "$valeur")" >> "$temporaire"
            trouve=1
          fi
          ;;
        *) printf '%s\n' "${ligne%$'\r'}" >> "$temporaire" ;;
      esac
    done < "$fichier"
  fi
  [ "$trouve" -eq 1 ] || printf '%s=%s\n' "$cle" "$(citer_env "$valeur")" >> "$temporaire"
  # `cat >` et non `mv` : le .env est en 600 orion:orion, et un mv lui
  # substituerait les droits du fichier temporaire (600 root), rendant le
  # fichier illisible par le service.
  cat "$temporaire" > "$fichier"
  rm -f "$temporaire"
}

# Répare une installation existante dont le .env contient des valeurs à espaces
# non citées. Idempotent : ne réécrit que ce qui doit l'être.
normaliser_env() {
  local fichier="$1" ligne cle valeur modifie=0 temporaire
  [ -f "$fichier" ] || return 0
  temporaire="$(mktemp)"
  while IFS= read -r ligne || [ -n "$ligne" ]; do
    ligne="${ligne%$'\r'}"
    case "$ligne" in
      ''|'#'*|*'="'*) printf '%s\n' "$ligne" >> "$temporaire"; continue ;;
    esac
    case "$ligne" in
      *=*)
        cle="${ligne%%=*}"
        valeur="${ligne#*=}"
        case "$cle" in ''|*[!A-Za-z0-9_]*) printf '%s\n' "$ligne" >> "$temporaire"; continue ;; esac
        case "$valeur" in
          *[[:space:]]*|*'#'*|*'$'*|*'`'*|*'('*)
            printf '%s=%s\n' "$cle" "$(citer_env "$valeur")" >> "$temporaire"
            modifie=1
            ;;
          *) printf '%s\n' "$ligne" >> "$temporaire" ;;
        esac
        ;;
      *) printf '%s\n' "$ligne" >> "$temporaire" ;;
    esac
  done < "$fichier"
  if [ "$modifie" -eq 1 ]; then
    cat "$temporaire" > "$fichier"
    dire ".env normalisé : valeurs à espaces protégées par des guillemets."
  fi
  rm -f "$temporaire"
}

# ─── 3. git utilisable par root sur les dépôts d'orion ────────────────────────
# Le provisioning clone en root puis chown vers orion ; toute commande git
# ultérieure lancée par root (mise à jour, diagnostic) est refusée pour
# « dubious ownership ». La configuration système lève l'objection une fois pour
# toutes, au lieu d'exiger un « -c safe.directory » sur chaque appel — oubli
# déjà constaté.
autoriser_git_systeme() {
  command -v git >/dev/null 2>&1 || return 0
  git config --system --get-all safe.directory 2>/dev/null | grep -qx '\*' && return 0
  git config --system --add safe.directory '*' 2>/dev/null \
    || avertir "impossible d'enregistrer safe.directory dans la configuration git système."
}

# ─── 4. Vérifier au lieu de supposer ─────────────────────────────────────────
# Chaque vérification porte le motif de son existence : la propriété contrôlée
# ici est précisément celle dont l'absence a produit une panne dont le symptôme
# désignait autre chose.

verifier_fichier() {
  local chemin="$1" pourquoi="$2"
  if [ -s "$chemin" ]; then dire "ok   $chemin"; return 0; fi
  retenir_defaut "$chemin absent ou vide — $pourquoi"
  return 1
}

verifier_service() {
  local unite="$1"
  if systemctl is-active --quiet "$unite"; then dire "ok   $unite actif"; return 0; fi
  local detail
  detail="$(systemctl is-active "$unite" 2>&1 || true)"
  retenir_defaut "$unite n'est pas actif (état : $detail) — « journalctl -u $unite -n 50 »"
  return 1
}

# Teste l'URL telle qu'un navigateur la verrait. C'est la seule vérification qui
# aurait attrapé à la fois le 502 (services morts) et le 500 (statiques
# manquants) : les deux fois, le provisioning s'est déclaré « Terminé ».
verifier_http() {
  local url="$1" attendus="${2:-200 301 302}"
  local code
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "$url" 2>/dev/null || echo 000)"
  case " $attendus " in
    *" $code "*) dire "ok   $url -> HTTP $code"; return 0 ;;
  esac
  retenir_defaut "$url répond HTTP $code (attendu : $attendus)"
  return 1
}
