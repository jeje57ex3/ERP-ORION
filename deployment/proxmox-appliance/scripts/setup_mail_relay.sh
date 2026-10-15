#!/usr/bin/env bash
# Orion ERP Appliance — Relais SMTP sortant auto-hébergé (Postfix + OpenDKIM).
#
# But : permettre à l'app Django (orion-backend, tourne en natif sur cette
# machine) d'envoyer de vrais emails transactionnels (confirmation
# d'inscription, invitation espace client, notifications RH, etc.) sans
# dépendre d'un service tiers (Brevo/Mailgun/SES...).
#
# Postfix est configuré en mode "send-only" : il n'écoute QUE sur
# 127.0.0.1:25 (jamais exposé publiquement, ne peut donc pas devenir un relais
# ouvert) et sert uniquement à relayer vers l'extérieur les mails soumis
# localement par Django.
#
# Prérequis AVANT de lancer ce script :
#   1. Un VPS avec IP fixe (pas une ligne résidentielle) — cf. discussion.
#   2. Un enregistrement DNS A pour $MAIL_HOSTNAME pointant vers l'IP publique
#      du VPS, en DNS-only (PAS proxifié Cloudflare orange-cloud — SMTP ne
#      passe pas par le proxy Cloudflare standard).
#   3. Un enregistrement PTR (reverse DNS) sur cette même IP pointant vers
#      $MAIL_HOSTNAME — à demander à l'hébergeur (OVH/Scaleway/Hetzner ont
#      tous un panneau ou un ticket support pour ça). C'est la condition la
#      plus souvent bloquante pour la délivrabilité vers Gmail/Outlook.
#
# Usage :
#   sudo DOMAIN=elysiums.fr MAIL_HOSTNAME=mail.elysiums.fr ./setup_mail_relay.sh
#
# Après exécution, le script affiche les enregistrements DNS SPF/DKIM/DMARC
# exacts à ajouter. Tant qu'ils ne sont pas en place, le mail partira mais
# finira très probablement en spam ou sera rejeté.

set -euo pipefail

DOMAIN="${DOMAIN:-elysiums.fr}"
MAIL_HOSTNAME="${MAIL_HOSTNAME:-mail.$DOMAIN}"
DKIM_SELECTOR="${DKIM_SELECTOR:-orion}"
FROM_ADDRESS="${FROM_ADDRESS:-no-reply@$DOMAIN}"
ENV_FILE="${ENV_FILE:-/opt/orion/backend/.env}"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERREUR: ce script doit être lancé en root (sudo)." >&2
  exit 1
fi

echo "=== Relais SMTP sortant Orion — domaine=$DOMAIN, hostname=$MAIL_HOSTNAME ==="

echo "[1/6] Installation Postfix + OpenDKIM..."
export DEBIAN_FRONTEND=noninteractive
debconf-set-selections <<EOF
postfix postfix/main_mailer_type select Internet Site
postfix postfix/mailname string $MAIL_HOSTNAME
EOF
apt-get update -qq
apt-get install -y -qq postfix opendkim opendkim-tools mailutils >/dev/null

echo "[2/6] Configuration Postfix (send-only, loopback uniquement)..."
postconf -e "myhostname = $MAIL_HOSTNAME"
postconf -e "mydestination = localhost"
postconf -e "inet_interfaces = loopback-only"
postconf -e "inet_protocols = ipv4"
postconf -e "smtp_helo_name = $MAIL_HOSTNAME"
postconf -e "smtpd_banner = \$myhostname ESMTP"
postconf -e "smtpd_milters = inet:localhost:12301"
postconf -e "non_smtpd_milters = inet:localhost:12301"
postconf -e "milter_default_action = accept"
postconf -e "milter_protocol = 6"

echo "[3/6] Génération de la clé DKIM (sélecteur: $DKIM_SELECTOR)..."
mkdir -p "/etc/opendkim/keys/$DOMAIN"
if [ ! -f "/etc/opendkim/keys/$DOMAIN/$DKIM_SELECTOR.private" ]; then
  opendkim-genkey -b 2048 -d "$DOMAIN" -s "$DKIM_SELECTOR" -D "/etc/opendkim/keys/$DOMAIN"
fi
chown -R opendkim:opendkim /etc/opendkim
chmod 600 "/etc/opendkim/keys/$DOMAIN/$DKIM_SELECTOR.private"

echo "[4/6] Configuration OpenDKIM..."
cat > /etc/opendkim.conf <<EOF
Syslog          yes
UMask           002
Domain          $DOMAIN
KeyFile         /etc/opendkim/keys/$DOMAIN/$DKIM_SELECTOR.private
Selector        $DKIM_SELECTOR
Socket          inet:12301@localhost
PidFile         /run/opendkim/opendkim.pid
Mode            s
SubDomains      no
EOF
sed -i 's/^SOCKET=.*/SOCKET="inet:12301@localhost"/' /etc/default/opendkim 2>/dev/null \
  || echo 'SOCKET="inet:12301@localhost"' >> /etc/default/opendkim

echo "[5/6] Redémarrage des services..."
systemctl enable opendkim postfix >/dev/null
systemctl restart opendkim
systemctl restart postfix

echo "[6/6] Mise à jour de $ENV_FILE..."
if [ -f "$ENV_FILE" ]; then
  for pair in \
    "EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend" \
    "EMAIL_HOST=127.0.0.1" \
    "EMAIL_PORT=25" \
    "EMAIL_USE_TLS=False" \
    "EMAIL_HOST_USER=" \
    "EMAIL_HOST_PASSWORD=" \
    "DEFAULT_FROM_EMAIL=$FROM_ADDRESS"
  do
    key="${pair%%=*}"
    if grep -q "^$key=" "$ENV_FILE"; then
      sed -i "s|^$key=.*|$pair|" "$ENV_FILE"
    else
      echo "$pair" >> "$ENV_FILE"
    fi
  done
  echo "  -> $ENV_FILE mis à jour. Redémarre orion-backend :"
  echo "     systemctl restart orion-backend"
else
  echo "  ATTENTION: $ENV_FILE introuvable, valeurs à ajouter manuellement :"
  echo "    EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend"
  echo "    EMAIL_HOST=127.0.0.1"
  echo "    EMAIL_PORT=25"
  echo "    EMAIL_USE_TLS=False"
  echo "    DEFAULT_FROM_EMAIL=$FROM_ADDRESS"
fi

echo
echo "=== Terminé. Enregistrements DNS à ajouter sur $DOMAIN ==="
echo
echo "1) A (DNS-only, PAS de proxy Cloudflare orange-cloud) :"
echo "   $MAIL_HOSTNAME.  A  <IP_PUBLIQUE_DU_VPS>"
echo
echo "2) PTR (reverse DNS) — à demander à l'hébergeur du VPS :"
echo "   <IP_PUBLIQUE_DU_VPS>  ->  $MAIL_HOSTNAME"
echo
echo "3) SPF (TXT sur $DOMAIN) :"
echo "   v=spf1 ip4:<IP_PUBLIQUE_DU_VPS> -all"
echo
echo "4) DKIM (TXT sur $DKIM_SELECTOR._domainkey.$DOMAIN) :"
cat "/etc/opendkim/keys/$DOMAIN/$DKIM_SELECTOR.txt"
echo
echo "5) DMARC (TXT sur _dmarc.$DOMAIN) — commencer en mode observation :"
echo "   v=DMARC1; p=none; rua=mailto:$FROM_ADDRESS; adkim=s; aspf=s"
echo "   (une fois SPF/DKIM validés sur quelques jours, passer p=none -> p=quarantine)"
echo
echo "Test local une fois les DNS propagés (depuis le VPS) :"
echo "   echo 'Test Orion ERP' | mail -s 'Test relais SMTP' -a From:$FROM_ADDRESS ton-adresse-reelle@gmail.com"
echo
echo "Vérifier la note de spam / DKIM / SPF avec un outil comme mail-tester.com"
echo "en s'envoyant un email de test vers l'adresse qu'il fournit."
