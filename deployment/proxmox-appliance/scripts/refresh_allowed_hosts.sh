#!/usr/bin/env bash
# Orion ERP Appliance — recalcule ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS et
# CORS_ALLOWED_ORIGINS à CHAQUE démarrage du service (ExecStartPre de
# orion-backend/orion-frontend), pas seulement pendant le provisioning : le
# bail DHCP de la VM peut changer entre deux redémarrages, et ces variables ne
# sont lues qu'une fois par gunicorn (EnvironmentFile) — une IP figée au
# premier boot casserait l'accès par IP après un simple reboot.
#
# Les trois variables sont traitées ensemble parce qu'elles dérivent des mêmes
# domaines. N'en rafraîchir qu'une menait à un enchaînement d'erreurs
# déroutant, constaté en production : un domaine ajouté après coup passait
# bien ALLOWED_HOSTS (plus de 400 DisallowedHost) mais restait absent de
# CSRF_TRUSTED_ORIGINS, et la soumission du formulaire de connexion échouait
# alors en 403 CSRF.
#
# Ce script est un ExecStartPre : tout ce qu'il peut rater doit rester sans
# conséquence sur le démarrage. Une version précédente mourait sur une clé
# simplement ABSENTE du .env (« grep | head | cut » sous `set -o pipefail`,
# dont l'affectation héritait du code d'erreur, puis `set -e`) ; les deux
# services refusaient alors de démarrer et nginx répondait 502. D'où
# l'absence de `set -e` ici, et la lecture par valeur_env.

set -uo pipefail

ENV_FILE="${ENV_FILE:-/opt/orion/backend/.env}"
[ -f "$ENV_FILE" ] || exit 0

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for candidat in \
  "$ICI/commun.sh" \
  /opt/orion/scripts/commun.sh \
  /opt/orion-appliance/provisioning/lib/commun.sh
do
  if [ -f "$candidat" ]; then . "$candidat"; break; fi
done
# Sans la bibliothèque, on ne touche à rien : un .env laissé en place est
# toujours préférable à un .env à moitié réécrit, et le service démarre avec
# les valeurs du provisioning.
if ! declare -f valeur_env >/dev/null 2>&1; then
  echo "refresh_allowed_hosts: commun.sh introuvable — .env laissé inchangé." >&2
  exit 0
fi

LOGIN="$(valeur_env "$ENV_FILE" ORION_LOGIN_DOMAIN)"
ORION="$(valeur_env "$ENV_FILE" ORION_FRONTEND_DOMAIN)"
SIECLE="$(valeur_env "$ENV_FILE" SIECLE_STORE_DOMAIN)"
LUNEA="$(valeur_env "$ENV_FILE" LUNEA_STORE_DOMAIN)"
NS="$(valeur_env "$ENV_FILE" ORION_NS_DOMAIN)"
# Sous-domaine propre à CETTE machine (haute disponibilité) : les autres nœuds
# interrogent /ha/health/ sur ce nom. Absent d'ALLOWED_HOSTS, Django rejette
# chaque battement de cœur en 400 DisallowedHost — tous les nœuds se croient
# alors mutuellement hors ligne, ce qui est exactement l'inverse du but.
NODE="$(valeur_env "$ENV_FILE" ORION_NODE_DOMAIN)"

# L'IP est un bonus, pas une condition. La version précédente sortait sans rien
# faire quand la route par défaut n'était pas encore là (démarrage avant que le
# réseau soit prêt) : les domaines n'étaient alors PAS réécrits, et un domaine
# ajouté après coup restait inconnu de Django jusqu'au prochain redémarrage
# réussi — panne intermittente, donc la pire à diagnostiquer.
VM_IP="$(ip route get 1.1.1.1 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i=="src") print $(i+1)}' | head -1)" || true

# ─── ALLOWED_HOSTS : tous les domaines + l'IP courante ────────────────────────
# Ce script RÉÉCRIT la variable en entier : tout domaine absent de cette liste
# serait effacé au premier redémarrage de service, même correctement posé au
# provisioning.
HOSTS="localhost,127.0.0.1"
for domaine in "$LOGIN" "$ORION" "$SIECLE" "$LUNEA" "$NS" "$NODE"; do
  [ -n "$domaine" ] && HOSTS="$HOSTS,$domaine"
done
[ -n "${VM_IP:-}" ] && HOSTS="$HOSTS,$VM_IP"
ecrire_env "$ENV_FILE" ALLOWED_HOSTS "$HOSTS"

# ─── CSRF_TRUSTED_ORIGINS : tous les domaines, en https ──────────────────────
# Obligatoire dès qu'un formulaire est soumis depuis un domaine : Django
# refuse sinon la requête en 403, même si l'hôte est autorisé.
CSRF=""
for domaine in "$LOGIN" "$ORION" "$SIECLE" "$LUNEA" "$NS" "$NODE"; do
  [ -n "$domaine" ] && CSRF="${CSRF:+$CSRF,}https://$domaine"
done
ecrire_env "$ENV_FILE" CSRF_TRUSTED_ORIGINS "$CSRF"

# ─── CORS_ALLOWED_ORIGINS : seulement les boutiques ──────────────────────────
# Les SPA SIÈCLE et LUNEA appellent l'API depuis une AUTRE origine que celle
# qui la sert. NÉOSTRUCTURA n'y figure pas : Nginx sert son build et proxifie
# /api sur la même origine, aucune requête croisée n'a lieu.
CORS=""
for domaine in "$SIECLE" "$LUNEA"; do
  [ -n "$domaine" ] && CORS="${CORS:+$CORS,}https://$domaine"
done
ecrire_env "$ENV_FILE" CORS_ALLOWED_ORIGINS "$CORS"

exit 0
