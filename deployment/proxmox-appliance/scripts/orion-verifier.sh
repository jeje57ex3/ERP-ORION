#!/usr/bin/env bash
# Orion ERP Appliance — vérification d'une installation.
#
# Lancé en dernière étape du provisioning, et réutilisable à tout moment :
#
#   bash /opt/orion/scripts/orion-verifier.sh
#   qm guest exec <vmid> -- /bin/bash /opt/orion/scripts/orion-verifier.sh
#
# Pourquoi ce script existe : TOUTES les pannes de provisioning rencontrées ont
# été découvertes par l'exploitant dans son navigateur — 502 Bad Gateway, puis
# erreur 500 sur chaque page — alors que le provisioning s'était déclaré
# « Terminé » dans les deux cas. Entre la cause et le symptôme, il y avait
# jusqu'à trois étapes, et le symptôme ne désignait jamais la cause.
#
# Chaque contrôle ci-dessous correspond à une panne réellement survenue. Ils
# vérifient ce qu'un utilisateur constate (une page qui répond), pas ce que le
# script croit avoir fait.
#
# Sortie : 0 si l'ERP est utilisable, 1 sinon. Les composants optionnels absents
# sont des avertissements, pas des échecs.

set -uo pipefail

# commun.sh suit le script : dans le payload pendant le provisioning, dans
# /opt/orion/scripts après installation (07-backup-cron.sh et update_orion.sh
# l'y copient tous deux).
ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for candidat in \
  "$ICI/commun.sh" \
  /opt/orion/scripts/commun.sh \
  /opt/orion-appliance/provisioning/lib/commun.sh \
  /opt/orion/backend/deployment/proxmox-appliance/provisioning/lib/commun.sh
do
  if [ -f "$candidat" ]; then . "$candidat"; break; fi
done
if ! declare -f charger_env >/dev/null 2>&1; then
  echo "ERREUR : commun.sh introuvable — vérification impossible." >&2
  exit 2
fi

ORION_ETAPE='08'
ORION_HOME='/opt/orion'
ENV_FILE="$ORION_HOME/backend/.env"
VENV_PY="$ORION_HOME/backend/.venv/bin/python"
MANAGE="$ORION_HOME/backend/manage.py"

CRITIQUES=()
AVERTISSEMENTS=()
grave()   { CRITIQUES+=("$1"); printf '  ECHEC  %s\n' "$1"; }
leger()   { AVERTISSEMENTS+=("$1"); printf '  note   %s\n' "$1"; }
bon()     { printf '  ok     %s\n' "$1"; }

titre() { printf '\n--- %s\n' "$1"; }

echo '======================================================================'
echo " Orion ERP — vérification de l'installation — $(date -u +%FT%TZ)"
echo '======================================================================'

# ─── 1. Fichier d'environnement ───────────────────────────────────────────────
titre "Environnement ($ENV_FILE)"
if [ ! -f "$ENV_FILE" ]; then
  grave ".env absent — l'ERP ne peut pas démarrer. Rejouez l'étape 02."
else
  if ( charger_env "$ENV_FILE" ) >/dev/null 2>&1; then
    bon '.env lisible'
    charger_env "$ENV_FILE"
  else
    grave ".env illisible — « bash /opt/orion/scripts/orion-verifier.sh » après normalisation."
  fi
  # Une valeur à espaces non citée a déjà tué tout le provisioning en exit 127,
  # sur un message qui ne nommait ni la clé ni le fichier.
  nues="$(grep -cE '^[A-Za-z_]+=[^"]*[[:space:]]' "$ENV_FILE" 2>/dev/null || true)"
  if [ "${nues:-0}" -gt 0 ]; then
    grave "$nues valeur(s) à espaces non citée(s) dans .env — les scripts shell qui le lisent échoueront. Corrigez : normaliser_env."
  else
    bon 'aucune valeur à espaces non citée'
  fi
  for cle in SECRET_KEY ALLOWED_HOSTS DB_NAME DB_USER DB_PASSWORD \
             ORION_SECRET_ENCRYPTION_KEY ORION_NODE_ID; do
    if [ -z "$(valeur_env "$ENV_FILE" "$cle")" ]; then
      grave "clé $cle vide ou absente dans .env"
    fi
  done
  # Chaque machine d'une grappe doit avoir un identifiant distinct : la
  # protection anti-divergence le compare au verrou de grappe, et toutes les
  # machines portant « orion-primary » se croyaient titulaires de la main.
  bon "identité du nœud : $(valeur_env "$ENV_FILE" ORION_NODE_ID) (rang $(valeur_env "$ENV_FILE" ORION_NODE_PRIORITY))"
fi

# ─── 2. Droits d'exécution des scripts ────────────────────────────────────────
titre 'Scripts opérationnels'
# git conserve le mode : un script committé en 100644 arrive non exécutable et
# échoue en « command not found ». Tous les boutons de la page Réseau privé
# renvoyaient cette erreur pour orion-mesh.sh.
if [ ! -d "$ORION_HOME/scripts" ]; then
  grave "$ORION_HOME/scripts absent — l'étape 07 n'a pas tourné."
fi
non_exec=0
for script in "$ORION_HOME"/scripts/*.sh; do
  [ -f "$script" ] || continue
  [ -x "$script" ] || { leger "non exécutable : $script"; non_exec=$((non_exec + 1)); }
done
if [ ! -d "$ORION_HOME/scripts" ]; then
  : # déjà signalé ci-dessus
elif [ "$non_exec" -eq 0 ]; then
  bon 'tous les scripts de /opt/orion/scripts sont exécutables'
else
  grave "$non_exec script(s) non exécutable(s) — « chmod +x /opt/orion/scripts/*.sh »"
fi
for requis in wait_for_port.sh refresh_allowed_hosts.sh; do
  if [ -x "$ORION_HOME/scripts/$requis" ]; then
    bon "$requis en place"
  else
    # Ces deux-là sont des ExecStartPre d'orion-backend et d'orion-frontend :
    # absents, systemd échoue en 203/EXEC, les services restent morts et nginx
    # répond 502 sans jamais mentionner un script manquant.
    grave "$requis manquant ou non exécutable — orion-backend et orion-frontend ne démarreront pas (502)."
  fi
done

# ─── 3. Services ──────────────────────────────────────────────────────────────
titre 'Services systemd'
for unite in orion-db-stack orion-backend orion-frontend orion-celery orion-celery-beat nginx; do
  if systemctl is-active --quiet "$unite" 2>/dev/null; then
    bon "$unite actif"
  else
    etat="$(systemctl is-active "$unite" 2>/dev/null || true)"
    etat="${etat:-inconnu}"
    grave "$unite : $etat — « journalctl -u $unite -n 50 --no-pager »"
  fi
done
# Boutiques et tunnel : présents seulement si un domaine a été fourni.
for unite in siecle-frontend lunea-frontend cloudflared; do
  if systemctl list-unit-files "$unite.service" >/dev/null 2>&1 \
     && systemctl is-enabled --quiet "$unite" 2>/dev/null; then
    systemctl is-active --quiet "$unite" 2>/dev/null \
      && bon "$unite actif" \
      || grave "$unite activé mais arrêté — « journalctl -u $unite -n 50 --no-pager »"
  else
    leger "$unite non activé (composant optionnel)"
  fi
done

# ─── 4. Infrastructure ────────────────────────────────────────────────────────
titre 'Ports et base de données'
for couple in '3306 MySQL' '6379 Redis' '9000 backend Django' '80 nginx'; do
  port="${couple%% *}"; quoi="${couple#* }"
  if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
    exec 3<&- 2>/dev/null || true
    bon "port $port ouvert ($quoi)"
  else
    grave "port $port fermé ($quoi)"
  fi
done

if [ -x "$VENV_PY" ] && [ -f "$MANAGE" ]; then
  # « migrate --check » sort non nul s'il reste des migrations à appliquer : le
  # cas exact où l'ERP démarre et répond « Table ... doesn't exist » à chaque
  # page, ce qui n'évoque en rien un provisioning incomplet.
  if sudo -u orion -E "$VENV_PY" "$MANAGE" migrate --check >/dev/null 2>&1; then
    bon 'schéma de base à jour'
  else
    grave "migrations non appliquées — « sudo -u orion -E $VENV_PY $MANAGE migrate --noinput »"
  fi
else
  grave "environnement Python absent ($VENV_PY) — l'étape 02 a échoué."
fi

# ─── 5. Fichiers statiques ────────────────────────────────────────────────────
titre 'Fichiers statiques'
# Le stockage à manifeste lève une erreur à chaque {% static %} sans entrée :
# staticfiles.json manquant, TOUTE page renvoie 500 et les statiques 404. La
# cause était un collectstatic sauté deux étapes plus tôt.
MANIFESTE="$ORION_HOME/backend/staticfiles/staticfiles.json"
if [ -s "$MANIFESTE" ]; then
  bon "manifeste présent ($(find "$ORION_HOME/backend/staticfiles" -type f 2>/dev/null | wc -l) fichiers collectés)"
else
  grave "staticfiles.json absent — toutes les pages renverraient 500. « sudo -u orion -E $VENV_PY $MANAGE collectstatic --noinput »"
fi

# ─── 6. Ce que voit un navigateur ─────────────────────────────────────────────
titre 'Réponses HTTP (ce que voit réellement un navigateur)'
# Le seul contrôle qui aurait attrapé les DEUX pannes : le 502 (services morts)
# et le 500 (statiques manquants). Les deux fois, tout le reste semblait normal
# et le provisioning avait annoncé « Terminé ».
verifier_url() {
  local url="$1" attendus="$2" quoi="$3" code
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "$url" 2>/dev/null || true)"
  code="${code:-000}"
  case " $attendus " in
    *" $code "*) bon "$quoi -> HTTP $code" ;;
    *) grave "$quoi -> HTTP $code (attendu $attendus) — $url" ;;
  esac
}
verifier_url 'http://127.0.0.1/' '200 301 302' 'accueil via nginx'
verifier_url 'http://127.0.0.1:9000/' '200 301 302' 'backend Django en direct'
# /setup/ est la porte d'entrée tant qu'aucune entreprise n'existe. Elle doit
# répondre, sinon l'appliance est inutilisable même parfaitement installée.
verifier_url 'http://127.0.0.1/setup/' '200 301 302' 'assistant de premier accès'
# Sonde de haute disponibilité : les autres nœuds l'interrogent. Un 400 ici
# signifie que le domaine du nœud manque d'ALLOWED_HOSTS, et tous les nœuds se
# croient alors mutuellement hors ligne.
verifier_url 'http://127.0.0.1/ha/public-health/' '200' 'sonde de santé HA'

NODE_DOMAINE="$(valeur_env "$ENV_FILE" ORION_NODE_DOMAIN)"
if [ -n "$NODE_DOMAINE" ]; then
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 \
    -H "Host: $NODE_DOMAINE" 'http://127.0.0.1/ha/public-health/' 2>/dev/null || true)"
  code="${code:-000}"
  if [ "$code" = '200' ]; then
    bon "sonde HA sous son vrai nom d'hôte ($NODE_DOMAINE) -> 200"
  else
    grave "sonde HA en Host: $NODE_DOMAINE -> HTTP $code — ce nom manque probablement d'ALLOWED_HOSTS (400 DisallowedHost), et les autres nœuds croiront celui-ci hors ligne."
  fi
fi

# ─── 7. Traductions ───────────────────────────────────────────────────────────
titre 'Catalogues de traduction'
# Les .po sont versionnés, les .mo non. Sans compilation, le sélecteur de
# langue enregistre bien la préférence mais aucune chaîne n'est traduite — et
# rien dans l'interface ne le signale.
nb_mo="$(find "$ORION_HOME/backend/locale" -name '*.mo' 2>/dev/null | wc -l)"
if [ "${nb_mo:-0}" -gt 0 ]; then
  bon "$nb_mo catalogue(s) compilé(s)"
else
  leger "aucun .mo — l'interface restera en français. « sudo -u orion -E $VENV_PY $MANAGE compilemessages »"
fi

# ─── 8. IA locale ─────────────────────────────────────────────────────────────
titre 'Moteur IA local (Orion)'
# Le daemon debout SANS modèle téléchargé renvoyait « 404 Not Found for url
# .../api/chat », message qui laisse croire à un point d'entrée absent alors que
# c'est le MODÈLE qui manque.
if command -v ollama >/dev/null 2>&1 || curl -fsS --max-time 5 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  if tags="$(curl -fsS --max-time 10 http://127.0.0.1:11434/api/tags 2>/dev/null)"; then
    bon 'moteur local joignable'
    if printf '%s' "$tags" | grep -q '"name"'; then
      bon "modèle(s) présent(s) : $(printf '%s' "$tags" | grep -o '"name":"[^"]*"' | cut -d'"' -f4 | tr '\n' ' ')"
    else
      grave "aucun modèle téléchargé — l'assistant répondrait 404 sur chaque question. « /opt/orion/scripts/orion-ai.sh pull qwen2.5:3b-instruct »"
    fi
  else
    leger "ollama installé mais le daemon ne répond pas — « /opt/orion/scripts/orion-ai.sh status »"
  fi
else
  leger "moteur IA local non installé (optionnel) — « /opt/orion/scripts/orion-ai.sh install »"
fi

# ─── 9. git utilisable par root ───────────────────────────────────────────────
titre 'Dépôt et mises à jour'
# Le provisioning clone en root puis chown vers orion : sans safe.directory,
# toute commande git lancée par root est refusée pour « dubious ownership » —
# y compris les mises à jour depuis l'interface.
if [ -d "$ORION_HOME/backend/.git" ]; then
  if HOME="${HOME:-/root}" git -C "$ORION_HOME/backend" rev-parse --short HEAD >/dev/null 2>&1; then
    bon "dépôt lisible — révision $(HOME="${HOME:-/root}" git -C "$ORION_HOME/backend" rev-parse --short HEAD 2>/dev/null)"
  else
    grave "git refuse de lire $ORION_HOME/backend — « git config --system --add safe.directory '*' »"
  fi
else
  grave "$ORION_HOME/backend/.git absent — le clone de l'étape 02 a échoué."
fi

# ─── Verdict ──────────────────────────────────────────────────────────────────
echo ''
echo '======================================================================'
if [ ${#CRITIQUES[@]} -eq 0 ] && [ ${#AVERTISSEMENTS[@]} -eq 0 ]; then
  echo ' Installation vérifiée : rien à signaler.'
  echo '======================================================================'
  exit 0
fi

if [ ${#AVERTISSEMENTS[@]} -gt 0 ]; then
  printf " %d point(s) d'attention (composants optionnels) :\n" "${#AVERTISSEMENTS[@]}"
  for ligne in "${AVERTISSEMENTS[@]}"; do printf '   - %s\n' "$ligne"; done
  echo ''
fi

if [ ${#CRITIQUES[@]} -eq 0 ]; then
  echo " L'ERP est utilisable. Aucun défaut bloquant."
  echo '======================================================================'
  exit 0
fi

printf " %d DEFAUT(S) BLOQUANT(S) — l'ERP n'est pas utilisable en l'état :\n" "${#CRITIQUES[@]}"
for ligne in "${CRITIQUES[@]}"; do printf '   - %s\n' "$ligne"; done
echo ''
echo " Journal du provisioning : $ORION_LOG"
echo '======================================================================'
exit 1
