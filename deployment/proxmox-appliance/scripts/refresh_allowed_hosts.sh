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
set -euo pipefail

ENV_FILE="/opt/orion/backend/.env"
[ -f "$ENV_FILE" ] || exit 0

VM_IP="$(ip route get 1.1.1.1 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i=="src") print $(i+1)}' | head -1)" || true
[ -n "${VM_IP:-}" ] || exit 0

# Le « || true » final n'est pas une précaution de style, il est
# indispensable. Avec `set -o pipefail`, un grep sans correspondance fait
# échouer tout le pipeline ; l'affectation `X="$(get_field ...)"` hérite de ce
# code, et `set -e` tue alors le script sur une clé simplement ABSENTE du
# .env. Ce script étant un ExecStartPre d'orion-backend et d'orion-frontend,
# cela a empêché les deux services de démarrer et fait répondre 502 à nginx —
# constaté en production à l'ajout d'ORION_NODE_DOMAIN, clé que les anciennes
# installations n'ont pas dans leur .env.
get_field() { grep "^$1=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true; }

# Remplace la ligne si la clé existe, l'ajoute sinon.
set_field() {
  local cle="$1" valeur="$2"
  if grep -q "^${cle}=" "$ENV_FILE"; then
    sed -i "s#^${cle}=.*#${cle}=${valeur}#" "$ENV_FILE"
  else
    echo "${cle}=${valeur}" >> "$ENV_FILE"
  fi
}

LOGIN="$(get_field ORION_LOGIN_DOMAIN)"
ORION="$(get_field ORION_FRONTEND_DOMAIN)"
SIECLE="$(get_field SIECLE_STORE_DOMAIN)"
LUNEA="$(get_field LUNEA_STORE_DOMAIN)"
NS="$(get_field ORION_NS_DOMAIN)"
# Sous-domaine propre à CETTE machine (haute disponibilité) : les autres nœuds
# interrogent /ha/health/ sur ce nom. Absent d'ALLOWED_HOSTS, Django rejette
# chaque battement de cœur en 400 DisallowedHost — tous les nœuds se croient
# alors mutuellement hors ligne, ce qui est exactement l'inverse du but.
NODE="$(get_field ORION_NODE_DOMAIN)"

# ─── ALLOWED_HOSTS : tous les domaines + l'IP courante ────────────────────────
# Ce script RÉÉCRIT la variable en entier : tout domaine absent de cette liste
# serait effacé au premier redémarrage de service, même correctement posé au
# provisioning.
HOSTS="localhost,127.0.0.1"
for domaine in "$LOGIN" "$ORION" "$SIECLE" "$LUNEA" "$NS" "$NODE"; do
  [ -n "$domaine" ] && HOSTS="$HOSTS,$domaine"
done
HOSTS="$HOSTS,$VM_IP"
set_field ALLOWED_HOSTS "$HOSTS"

# ─── CSRF_TRUSTED_ORIGINS : tous les domaines, en https ──────────────────────
# Obligatoire dès qu'un formulaire est soumis depuis un domaine : Django
# refuse sinon la requête en 403, même si l'hôte est autorisé.
CSRF=""
for domaine in "$LOGIN" "$ORION" "$SIECLE" "$LUNEA" "$NS" "$NODE"; do
  [ -n "$domaine" ] && CSRF="${CSRF:+$CSRF,}https://$domaine"
done
set_field CSRF_TRUSTED_ORIGINS "$CSRF"

# ─── CORS_ALLOWED_ORIGINS : seulement les boutiques ──────────────────────────
# Les SPA SIÈCLE et LUNEA appellent l'API depuis une AUTRE origine que celle
# qui la sert. NÉOSTRUCTURA n'y figure pas : Nginx sert son build et proxifie
# /api sur la même origine, aucune requête croisée n'a lieu.
CORS=""
for domaine in "$SIECLE" "$LUNEA"; do
  [ -n "$domaine" ] && CORS="${CORS:+$CORS,}https://$domaine"
done
set_field CORS_ALLOWED_ORIGINS "$CORS"
