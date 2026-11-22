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
# ─── DEUX MODES, ET IL FAUT CHOISIR LE BON ──────────────────────────────────
#
# MODE 1 — REMISE DIRECTE (le mode d'origine, sans RELAYHOST).
#   Postfix parle lui-même aux serveurs de messagerie des destinataires, sur
#   le port 25 SORTANT. Exige les trois prérequis ci-dessus, et notamment une
#   IP publique fixe avec un PTR.
#
#   NE MARCHE PAS SUR UNE LIGNE RÉSIDENTIELLE, et le mot « pas » est
#   important : la plupart des fournisseurs d'accès bloquent le port 25
#   sortant, et sans IP fixe aucun PTR n'est possible -- or Gmail et Outlook
#   rejettent d'emblée un expéditeur sans PTR. Le script VÉRIFIE désormais
#   ce port avant d'annoncer quoi que ce soit (voir l'étape 7).
#
# MODE 2 — RELAIS SORTANT (RELAYHOST renseigné).
#   Postfix reste le point de dépôt local sur 127.0.0.1:25 -- l'ERP ne voit
#   aucune différence -- mais confie la remise à un service d'envoi
#   (Brevo, Mailjet, Scaleway, OVH...). C'est le mode à employer dès que la
#   machine n'a pas d'IP publique fixe.
#
#   On garde ainsi ce qu'un relais local apporte vraiment : la file
#   d'attente et les réessais. Un envoi déclenché pendant une coupure du
#   fournisseur n'est pas perdu, alors que Django, qui parle au service en
#   direct, lèverait et abandonnerait.
#
#   sudo DOMAIN=elysiums.fr \
#        RELAYHOST='[smtp-relay.brevo.com]:587' \
#        RELAY_USER='xxxxx@smtp-brevo.com' \
#        RELAY_PASSWORD='votre-cle-smtp' \
#        SKIP_DKIM=1 \
#        ./setup_mail_relay.sh
#
#   SKIP_DKIM=1 en mode relais, SAUF si vous publiez l'enregistrement DKIM
#   affiché à la fin. Une signature DKIM dont l'enregistrement DNS est absent
#   vaut MOINS que pas de signature du tout : le destinataire constate une
#   signature invalide, ce qui est un signal négatif franc. Votre service
#   d'envoi signe déjà avec son propre domaine.
#
# Usage (mode 1) :
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
RELAYHOST="${RELAYHOST:-}"
RELAY_USER="${RELAY_USER:-}"
RELAY_PASSWORD="${RELAY_PASSWORD:-}"
SKIP_DKIM="${SKIP_DKIM:-0}"

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
postconf -e "milter_default_action = accept"
postconf -e "milter_protocol = 6"

if [ "$SKIP_DKIM" = "1" ]; then
  # Les milters sont RETIRÉS, et pas seulement laissés de côté : une
  # exécution précédente a pu les écrire dans main.cf. Les y laisser avec
  # OpenDKIM arrêté ferait attendre Postfix sur chaque message, puis
  # accepter sans signer (milter_default_action = accept) -- une lenteur
  # inexplicable à chaque envoi.
  postconf -X smtpd_milters non_smtpd_milters 2>/dev/null || true
  echo "      (DKIM local désactivé : SKIP_DKIM=1)"
else
  postconf -e "smtpd_milters = inet:localhost:12301"
  postconf -e "non_smtpd_milters = inet:localhost:12301"
fi

if [ -n "$RELAYHOST" ]; then
  echo "      Mode RELAIS : remise confiée à $RELAYHOST"
  postconf -e "relayhost = $RELAYHOST"
  # `encrypt` et non `may` : avec `may`, un intermédiaire qui supprime
  # l'annonce STARTTLS fait repartir l'identifiant et la clef EN CLAIR, et
  # rien ne le signale. On refuse plutôt d'envoyer.
  postconf -e "smtp_tls_security_level = encrypt"

  if [ -n "$RELAY_USER" ]; then
    postconf -e "smtp_sasl_auth_enable = yes"
    postconf -e "smtp_sasl_password_maps = hash:/etc/postfix/sasl_passwd"
    postconf -e "smtp_sasl_security_options = noanonymous"
    postconf -e "smtp_sasl_tls_security_options = noanonymous"

    # Écrit avec un umask restrictif, et non « chmod après » : entre la
    # création et le chmod, le fichier porterait la clef SMTP en lecture
    # pour tout le monde.
    ( umask 077
      printf '%s %s:%s\n' "$RELAYHOST" "$RELAY_USER" "$RELAY_PASSWORD" \
        > /etc/postfix/sasl_passwd )
    postmap /etc/postfix/sasl_passwd
    chmod 600 /etc/postfix/sasl_passwd /etc/postfix/sasl_passwd.db
  fi
else
  postconf -X relayhost 2>/dev/null || true
fi

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

echo "[5/7] Redémarrage des services..."
systemctl enable postfix >/dev/null
if [ "$SKIP_DKIM" = "1" ]; then
  # Arrêté plutôt que laissé tourner inutilisé : un service qui écoute sans
  # que rien ne lui parle se fait oublier, puis réapparaît dans un
  # diagnostic comme une cause possible qu'il faut écarter.
  systemctl disable --now opendkim >/dev/null 2>&1 || true
else
  systemctl enable opendkim >/dev/null
  # `|| true` puis vérification : avec `set -e`, un OpenDKIM qui refuse de
  # démarrer tuerait le script ICI, après avoir configuré Postfix pour lui
  # parler -- donc en laissant une machine qui accepte les messages et les
  # fait attendre. On veut aller jusqu'au diagnostic final.
  systemctl restart opendkim || true
  if ! systemctl is-active --quiet opendkim; then
    echo "  ERREUR: OpenDKIM n'a pas démarré. Postfix est configuré pour lui" >&2
    echo "  parler, donc chaque envoi attendra son délai avant de partir NON" >&2
    echo "  signé. Relancez avec SKIP_DKIM=1, ou lisez :" >&2
    echo "    journalctl -u opendkim -n 50 --no-pager" >&2
  fi
fi
systemctl restart postfix

echo "[6/7] Mise à jour de $ENV_FILE..."
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

# ─── [7/7] LA VÉRIFICATION QUI MANQUAIT ─────────────────────────────────────
#
# POURQUOI ELLE EST INDISPENSABLE, et c'est le défaut le plus coûteux que ce
# script avait : Postfix ACCEPTE le message sur 127.0.0.1:25 et rend un
# succès immédiat. Django lit donc « envoyé », l'ERP affiche « code
# provisoire envoyé », l'écran est vert -- et si le port 25 sortant est
# bloqué, le message dort dans la file et n'arrive JAMAIS.
#
# C'est la pire panne possible : elle se présente comme une réussite. Un
# compte créé reste inutilisable, son titulaire n'a rien reçu, et aucun
# écran ne dit pourquoi. Le script annonçait pourtant « Terminé ».
#
# On mesure donc, au lieu de supposer.

echo "[7/7] Vérification de la remise..."

verifier_le_port() {
  # /dev/tcp plutôt que nc : bash l'a toujours, nc n'est pas installé par
  # défaut sur une image minimale -- et un outil manquant se lirait comme un
  # port fermé, donc comme un diagnostic faux.
  local hote="$1" port="$2"
  timeout 10 bash -c "exec 3<>/dev/tcp/$hote/$port" 2>/dev/null
}

REMISE_SURE=0

if [ -n "$RELAYHOST" ]; then
  cible_hote="${RELAYHOST#[}"; cible_hote="${cible_hote%%]*}"
  cible_port="${RELAYHOST##*:}"
  [ "$cible_port" = "$RELAYHOST" ] && cible_port=25

  if verifier_le_port "$cible_hote" "$cible_port"; then
    echo "  OK : $cible_hote:$cible_port est joignable."
    REMISE_SURE=1
  else
    echo "  ECHEC : $cible_hote:$cible_port est INJOIGNABLE depuis cette" >&2
    echo "  machine. Les messages seront acceptes puis mis en file sans" >&2
    echo "  jamais partir, et l'ERP affichera « envoye »." >&2
  fi
else
  # Un vrai serveur de messagerie entrant sert de temoin. Gmail convient :
  # il est joignable de partout OU le port est ouvert, et refuse la
  # connexion la ou il est bloque.
  if verifier_le_port "gmail-smtp-in.l.google.com" 25; then
    echo "  OK : le port 25 sortant est ouvert."
    REMISE_SURE=1
  else
    echo >&2
    echo "  ========================================================" >&2
    echo "  LE PORT 25 SORTANT EST BLOQUE. RIEN NE PARTIRA." >&2
    echo "  ========================================================" >&2
    echo >&2
    echo "  Postfix acceptera chaque message et le gardera en file : l'ERP" >&2
    echo "  affichera « envoye » et personne ne recevra rien. C'est le cas" >&2
    echo "  normal sur une ligne residentielle et chez beaucoup" >&2
    echo "  d'hebergeurs." >&2
    echo >&2
    echo "  La correction est de relayer par un service d'envoi, en gardant" >&2
    echo "  ce meme relais local -- l'ERP ne verra aucune difference :" >&2
    echo >&2
    echo "    sudo DOMAIN=$DOMAIN \\" >&2
    echo "         RELAYHOST='[smtp-relay.brevo.com]:587' \\" >&2
    echo "         RELAY_USER='<identifiant SMTP du service>' \\" >&2
    echo "         RELAY_PASSWORD='<cle SMTP du service>' \\" >&2
    echo "         SKIP_DKIM=1 \\" >&2
    echo "         \$0" >&2
    echo >&2
  fi
fi

# Ce qui attend deja dans la file, s'il y a lieu : un nombre non nul ici
# apres une tentative d'envoi est la preuve que la remise ne se fait pas.
en_attente="$(mailq 2>/dev/null | grep -c '^[A-F0-9]' || true)"
if [ "${en_attente:-0}" -gt 0 ]; then
  echo "  ATTENTION : $en_attente message(s) deja en attente dans la file."
  echo "  Detail : mailq   |   relancer : postqueue -f"
fi

echo
if [ "$REMISE_SURE" = "1" ]; then
  echo "=== Relais en place. Enregistrements DNS à ajouter sur $DOMAIN ==="
else
  echo "=== Relais INSTALLÉ MAIS NON FONCTIONNEL (voir ci-dessus) ==="
fi
echo
if [ -n "$RELAYHOST" ]; then
  # EN MODE RELAIS, LES ENREGISTREMENTS NE SONT PAS LES MEMES, et donner
  # ceux du mode direct serait une erreur active : « v=spf1 ip4:<votre IP>
  # -all » autoriserait VOTRE machine et INTERDIRAIT le service d'envoi qui
  # expédie réellement. Tous vos courriels échoueraient SPF, et le « -all »
  # demande explicitement au destinataire de les rejeter.
  echo "1) Aucun enregistrement A ni PTR n'est nécessaire : votre machine ne"
  echo "   parle plus aux destinataires, c'est le service d'envoi qui le fait."
  echo
  echo "2) SPF (TXT sur $DOMAIN) — celui de VOTRE SERVICE, pas votre IP."
  echo "   Brevo    : v=spf1 include:spf.brevo.com -all"
  echo "   Mailjet  : v=spf1 include:spf.mailjet.com -all"
  echo "   Scaleway : v=spf1 include:_spf.tem.scaleway.com -all"
  echo "   (en cas de doute, prenez la valeur donnée par votre service)"
  echo
  echo "3) DKIM : suivez l'assistant de votre service d'envoi, qui vous"
  echo "   donnera un ou deux enregistrements CNAME à publier. C'est LUI"
  echo "   qui signe."
  if [ "$SKIP_DKIM" != "1" ]; then
    echo
    echo "   ATTENTION : vous avez laissé la signature DKIM locale active"
    echo "   (SKIP_DKIM n'est pas à 1). Publiez l'enregistrement ci-dessous,"
    echo "   ou relancez avec SKIP_DKIM=1 : une signature dont la clef"
    echo "   publique est introuvable vaut MOINS que pas de signature."
    echo
    echo "   TXT sur $DKIM_SELECTOR._domainkey.$DOMAIN :"
    cat "/etc/opendkim/keys/$DOMAIN/$DKIM_SELECTOR.txt"
  fi
  echo
else
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
fi
echo "4bis) À FAIRE DANS L'ERP, et sans quoi la page reste muette :"
echo "   Ouvrez /orion-admin/courriels/ et renseignez"
echo "     Serveur SMTP        : 127.0.0.1"
echo "     Port                : 25"
echo "     Chiffrement         : Aucun (relais local sur 127.0.0.1:25)"
echo "     Identifiant         : (vide)"
echo "     Adresse d'expédition: $FROM_ADDRESS"
echo "   puis cochez « Envoyer réellement les courriels » et enregistrez."
echo "   Le bouton de test de cette page devient alors utilisable, et"
echo "   l'écran de diagnostic cesse d'annoncer « aucun envoi réel »."
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
