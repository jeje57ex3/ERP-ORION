#!/usr/bin/env bash
# ============================================================================
# Orion ERP Appliance — Mise à jour complète (OS + Docker + Node + Python + ERP)
#
# Trois modes, parce que la voie applicative ne doit pas être la seule.
# `manage.py run_system_update` apporte la trace d'audit, le point de rollback
# et les vérifications post-update, mais sa PREMIÈRE instruction est une
# lecture en base (SystemUpdateSettings). Elle est donc indisponible
# précisément quand on en a le plus besoin : base injoignable, migration
# cassée, Django qui ne démarre pas, ou simplement `update_enabled` à faux.
#
#   --direct       git pull + migrations + statiques + builds, SANS Django.
#                  Aucune dépendance à la base ni au mécanisme applicatif.
#                  À utiliser quand l'ERP est en panne.
#   --django-only  n'utilise que le mécanisme applicatif, sans repli.
#   (par défaut)   mécanisme applicatif, repli direct s'il échoue, puis
#                  nouvelle tentative pour restaurer la trace d'audit.
#
# Rollback applicatif : manage.py rollback_system_update
# ============================================================================

set -euo pipefail

# commun.sh : $HOME garanti (la CLI Ollama et git en dependent, et
# « qm guest exec » n'en definit aucun), lecture du .env sans l'executer,
# verifications. Suit les scripts dans /opt/orion/scripts.
ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for candidat in   "$ICI/commun.sh"   /opt/orion/scripts/commun.sh   /opt/orion/backend/deployment/proxmox-appliance/provisioning/lib/commun.sh
do
  if [ -f "$candidat" ]; then . "$candidat"; break; fi
done
if ! declare -f charger_env >/dev/null 2>&1; then
  echo "ERREUR: commun.sh introuvable — mise a jour interrompue." >&2
  echo "  Attendu dans /opt/orion/scripts/commun.sh" >&2
  exit 1
fi
ORION_ETAPE='maj'

ORION_HOME="/opt/orion"
ENV_FILE="$ORION_HOME/backend/.env"
VENV_PY="$ORION_HOME/backend/.venv/bin/python"
MANAGE="$ORION_HOME/backend/manage.py"

MODE='auto'
while [ $# -gt 0 ]; do
  case "$1" in
    --direct)      MODE='direct' ;;
    --django-only) MODE='django' ;;
    -h|--help)     sed -n '2,20p' "$0"; exit 0 ;;
    *)             echo "Option inconnue : $1" >&2; sed -n '11,16p' "$0" >&2; exit 2 ;;
  esac
  shift
done

[ -f "$ENV_FILE" ] || { echo "ERREUR: $ENV_FILE introuvable — appliance non configurée."; exit 1; }

# Le .env etait SOURCE, c'est-a-dire execute : une seule valeur a espaces non
# citee rendait la mise a jour fatale et opaque (« -n: command not found »,
# exit 127, sans nommer ni la cle ni le fichier) sur une appliance par
# ailleurs saine. normaliser_env repare le fichier en place, charger_env le lit
# sans jamais interpreter une valeur.
normaliser_env "$ENV_FILE"
charger_env "$ENV_FILE"

# ─── Avancement lisible SANS la base et SANS l'interface web ────────────────
#
# Le bouton de l'ERP lisait son avancement dans SystemUpdateRun, donc en
# base. C'est exactement ce qu'on ne peut plus consulter quand MySQL est
# tombé — c'est-à-dire au moment où l'on a le plus besoin de savoir où en
# est la mise à jour. Ce fichier-ci est écrit en clair par le script, et se
# lit depuis l'hyperviseur sans rien démarrer :
#
#     qm guest exec <vmid> -- cat /opt/orion/logs/maj-etat.json
#
# Les échecs d'écriture sont ignorés volontairement : ne pas pouvoir noter
# l'état ne doit jamais empêcher la mise à jour elle-même.
FICHIER_ETAT="$ORION_HOME/logs/maj-etat.json"

# Un etat FIGE n'est plus ecrase par le piege de sortie. Sans cela, le piege
# repassait apres « exit 1 » et remplacait « refusee » par « echouee ».
# Constate sur l'appliance le 08/11/2026 : le journal disait « Mise a jour
# NON DEMARREE : rien n'a ete modifie » tandis que maj-etat.json annoncait
# « echouee ». Or la difference est capitale pour qui doit decider d'un
# rollback -- « refusee » signifie que RIEN n'a ete touche, donc qu'il n'y a
# rien a defaire.
ETAT_FIGE=0

noter_etat() {
  mkdir -p "$(dirname "$FICHIER_ETAT")" 2>/dev/null || true
  printf '{"etape": "%s", "mode": "%s", "code": %s, "horodatage": "%s"}\n' \
    "$1" "$MODE" "${2:-null}" "$(date -u +%FT%TZ)" \
    > "$FICHIER_ETAT" 2>/dev/null || true
  chmod 0644 "$FICHIER_ETAT" 2>/dev/null || true
}

# Le code de sortie est relevé par un piège sur EXIT, et non écrit à la fin
# du script : une mise à jour tuée en route (mémoire épuisée, délai systemd
# dépassé) ne serait jamais passée par la dernière ligne, et le fichier
# d'état aurait indiqué « en cours » indéfiniment.
figer_etat() {
  noter_etat "$1" "${2:-null}"
  ETAT_FIGE=1
}

sur_sortie() {
  local code=$?
  if [ "$ETAT_FIGE" -ne 0 ]; then
    return
  fi
  if [ "$code" -eq 0 ]; then
    noter_etat 'terminee' 0
  else
    noter_etat 'echouee' "$code"
  fi
}
trap sur_sortie EXIT

# Un signal doit laisser une trace DISTINCTE, et non passer pour un succes.
#
# Mesure du 08/11/2026 : sur SIGTERM, bash execute bien le piege EXIT, mais
# « $? » y vaut ZERO -- c'est le code de la derniere commande achevee, pas
# celui du signal. Le script notait donc « terminee », code 0, pour une mise
# a jour que systemd venait de tuer a son TimeoutStartSec. C'est exactement
# le mensonge que ce fichier d'etat existe pour empecher, et il etait au
# coeur du mecanisme cense dire la verite quand la base est en panne.
#
# SIGKILL -- le tueur de memoire du noyau -- ne peut par definition pas etre
# intercepte. Dans ce seul cas l'etat reste celui de la derniere etape notee,
# et c'est le journal systemd qui leve le doute. Limite assumee : il n'existe
# aucun moyen de l'eviter depuis le processus tue.
sur_signal() {
  local nom="$1" code="$2"
  echo "  INTERROMPU ($nom) — la mise a jour s'arrete en cours de route." >&2
  figer_etat 'interrompue' "$code"
  exit "$code"
}
trap 'sur_signal TERM 143' TERM
trap 'sur_signal INT 130' INT
trap 'sur_signal HUP 129' HUP

# ─── Contrôle préalable : refuser AVANT de modifier quoi que ce soit ────────
#
# Les deux mises à jour qui ont échoué sur cette appliance l'ont fait sur une
# machine à 85 % de disque et à bout de mémoire. L'une a laissé une migration
# à mi-chemin, dans un état qui bloquait toutes les suivantes. Rien n'avait
# vérifié que la machine pouvait encaisser le travail.
#
# Un refus net AVANT la première modification vaut infiniment mieux qu'un
# échec au milieu d'un `apt upgrade` ou d'un `CREATE TABLE` : il n'y a rien
# à rattraper, et le message dit quoi libérer.
#
# Les seuils bloquants sont bas à dessein : ils marquent le point où la mise
# à jour ÉCHOUERA de toute façon, pas le point où elle devient inconfortable.
# L'inconfort, lui, est signalé sans bloquer — c'est à l'exploitant de juger.
MINI_DISQUE_MO=2048
ALERTE_DISQUE_MO=8192
MINI_MEMOIRE_MO=600
ALERTE_MEMOIRE_MO=1500

verifier_avant_de_commencer() {
  local libre_mo memoire_mo refus=0

  libre_mo="$(df -BM --output=avail / 2>/dev/null | tail -1 | tr -dc '0-9')"
  memoire_mo="$(awk '/^MemAvailable:/ {printf "%d", $2/1024}' /proc/meminfo 2>/dev/null)"
  [ -n "$libre_mo" ]   || libre_mo=0
  [ -n "$memoire_mo" ] || memoire_mo=0

  echo "[0/7] Controle prealable : ${libre_mo} Mo libres sur /, ${memoire_mo} Mo de memoire disponible."

  if [ "$libre_mo" -lt "$MINI_DISQUE_MO" ]; then
    echo "  ECHEC: moins de ${MINI_DISQUE_MO} Mo libres sur /. La mise a jour" >&2
    echo "         echouerait en cours de route. Liberez de la place :" >&2
    echo "         journalctl --vacuum-size=200M ; docker image prune -af" >&2
    refus=1
  elif [ "$libre_mo" -lt "$ALERTE_DISQUE_MO" ]; then
    echo "  ATTENTION: ${libre_mo} Mo libres seulement. apt, pip et trois" >&2
    echo "             builds npm en consomment plusieurs milliers." >&2
  fi

  if [ "$memoire_mo" -lt "$MINI_MEMOIRE_MO" ]; then
    echo "  ECHEC: ${memoire_mo} Mo de memoire disponible. Le tueur de memoire" >&2
    echo "         du noyau interromprait la migration ou un build." >&2
    refus=1
  elif [ "$memoire_mo" -lt "$ALERTE_MEMOIRE_MO" ]; then
    echo "  ATTENTION: ${memoire_mo} Mo de memoire disponible, c'est juste." >&2
  fi

  # Sonde informative, JAMAIS bloquante : « --direct » existe précisément
  # pour tourner quand la base est en panne, et actualiser le code et les
  # frontends garde alors tout son sens. Mais le dire d'avance évite de
  # croire ensuite que la mise à jour a tout fait.
  if sudo -u orion -E "$VENV_PY" "$MANAGE" showmigrations --plan >/dev/null 2>&1; then
    echo "  base joignable, plan de migrations lisible."
  else
    echo "  ATTENTION: base injoignable ou plan de migrations illisible." >&2
    echo "             Le code et les frontends seront actualises ; les" >&2
    echo "             migrations echoueront. Verifiez orion-db-stack." >&2
  fi

  if [ "$refus" -ne 0 ]; then
    echo "  Mise a jour NON DEMARREE : rien n'a ete modifie." >&2
    figer_etat 'refusee' 1
    exit 1
  fi
}

noter_etat 'demarrage'
verifier_avant_de_commencer

echo "======================================"
echo " Mise à jour Orion ERP Appliance"
echo "======================================"

echo "[1/7] Mise à jour Ubuntu..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y

echo "[2/7] Mise à jour images Docker (MySQL/Redis)..."
docker compose -f "$ORION_HOME/docker/docker-compose.yml" pull
docker compose -f "$ORION_HOME/docker/docker-compose.yml" up -d

echo "[3/7] Mise à jour Node.js (paquets globaux) et dépendances Python (venv)..."
npm update -g --silent || true
"$VENV_PY" -m pip install --upgrade pip --quiet
"$VENV_PY" -m pip install --no-cache-dir -r "$ORION_HOME/backend/requirements.txt"

echo "[4/7] Mise à jour applicative Orion ERP (git pull + migrations)..."

# Mise à jour sans aucune dépendance au mécanisme applicatif : seuls git, pip
# et les commandes Django de base sont requis. C'est la voie de survie quand
# l'ERP est en panne — un bug DANS le mécanisme de mise à jour serait sinon
# irrécupérable, son propre correctif ne pouvant arriver que par lui.
# Constaté en production avec « Commande de sauvegarde non configurée », qui
# bloquait toute mise à jour par défaut.
# ─── Relevés de catalogues fabricants ──────────────────────────────────────────
#
# Les CSV de data/catalogues/ arrivent avec le code. Cette étape les importe
# pour que les 8 430 articles de Hager, Legrand et Soprema soient à jour sans
# aucune manipulation.
#
# SANS DANGER PAR CONSTRUCTION, et c'est ce qui autorise un appel
# automatique : « --toutes-entreprises » ne touche QUE les entreprises qui
# portent déjà des sources « Relevé web », c'est-à-dire celles où
# l'administrateur a lancé creer_sources_fabricants volontairement. Une
# installation qui n'en veut pas n'est jamais modifiée, et l'étape ne dit
# rien.
#
# L'import est rejouable : un second passage ne duplique rien, et un prix
# que l'exploitant a CONFIRMÉ -- case « prix indicatif » décochée -- n'est
# jamais écrasé. Ce sont des prix publics, pas des tarifs négociés.
#
# L'échec n'interrompt pas la mise à jour : un catalogue non importé est un
# désagrément, une mise à jour interrompue en est un autre, bien plus grand.
importer_catalogues_fabricants() {
  if [ ! -d "$ORION_HOME/backend/data/catalogues" ]; then
    return 0
  fi
  echo "  relevés de catalogues fabricants..."
  if sudo -u orion -E "$VENV_PY" "$MANAGE" importer_releves_web        --toutes-entreprises --ecrire 2>&1 | sed 's/^/    /'; then
    :
  else
    echo "  ATTENTION: import des relevés de catalogues échoué ; la mise à" >&2
    echo "             jour continue. Relancez à la main :" >&2
    echo "             manage.py importer_releves_web --toutes-entreprises --ecrire" >&2
  fi
}

# CHAQUE etape est verifiee SEPAREMENT, et non laissee a « set -euo pipefail ».
#
# Defaut constate sur l'appliance le 08/11/2026 : appelee a gauche d'un
# « || », cette fonction tourne avec set -e SUSPENDU pour TOUT son corps.
# Un `migrate` en echec n'interrompait donc rien du tout -- collectstatic
# s'executait quand meme, et la ligne « code récupéré, schéma migré »
# s'affichait trois lignes sous un traceback MySQL. Releve textuellement
# dans le journal de l'appliance :
#
#     django.db.utils.OperationalError: (1060, "Duplicate column name
#     'archive_ref'")
#       code récupéré, schéma migré, statiques collectés.
#
# Consequence la plus grave : la fonction renvoyait 0, donc maj-etat.json
# notait « terminee » et l'unite systemd se declarait reussie, sur un ERP
# dont le schema ne correspondait pas au code. C'est ainsi qu'une base a
# moitie migree a survecu a plusieurs mises a jour « reussies ».
# LES SORTIES DE BUILD CASSENT LE PULL DE LA MISE A JOUR SUIVANTE
#
# « static/siecle-store » et « apps/lunea/static/lunea/dist » sont des
# sorties de build, et elles sont pourtant suivies par git : l'appliance
# n'a pas toujours de quoi compiler, on lui livre donc des assets prets.
#
# Mais cette mise a jour RECONSTRUIT les frontends plus bas. Chaque mise a
# jour reussie laissait donc ces fichiers modifies, et le pull de la
# SUIVANTE refusait de s'executer :
#
#   error: Your local changes to the following files would be overwritten
#   by merge: static/siecle-store/index.html
#
# On ne remet a zero QUE ces dossiers — ils sont regeneres quelques etapes
# plus loin. Un « reset --hard » debloquerait aussi le pull, en detruisant
# au passage tout reglage local pose sur la machine.
CHEMINS_GENERES=(
  "static/siecle-store"
  "apps/lunea/static/lunea/dist"
)

restaurer_les_fichiers_generes() {
  local depot="$ORION_HOME/backend" chemin
  for chemin in "${CHEMINS_GENERES[@]}"; do
    [ -e "$depot/$chemin" ] || continue
    # On NE MASQUE PAS l'erreur : si un build a tourne en root, « orion » ne
    # peut plus ecrire ici et git repond « Permission denied ». Avale, ce
    # message laissait le pull echouer juste apres en ne parlant que du
    # fichier, jamais des droits.
    if ! sudo -u orion git -C "$depot" checkout -- "$chemin" 2>&1; then
      echo "  ATTENTION: restauration impossible de $chemin." >&2
      echo "             Cause frequente : un build a tourne en root et les" >&2
      echo "             fichiers n'appartiennent plus a l'utilisateur orion." >&2
      echo "             Verifiez : ls -la $depot/$chemin" >&2
    fi
    # Les bundles non suivis, aux noms haches, s'accumulent a chaque build :
    # un fichier entrant du meme nom ferait echouer le pull a son tour.
    sudo -u orion git -C "$depot" clean -fdq -- "$chemin" 2>&1 || true
  done
}

maj_directe() {
  restaurer_les_fichiers_generes
  if ! sudo -u orion git -C "$ORION_HOME/backend" pull --ff-only; then
    echo "  ERREUR: git pull impossible (arbre modifié, ou branche suivie différente)." >&2
    echo "          Vérifiez : git -C $ORION_HOME/backend status" >&2
    return 1
  fi
  if ! sudo -u orion -E "$VENV_PY" "$MANAGE" migrate --noinput; then
    echo "  ERREUR: migrate a echoue — le code est deploye sur un schema qui ne" >&2
    echo "          lui correspond pas. L'ERP peut repondre en 500." >&2
    echo "          MySQL n'a pas de DDL transactionnelle : une migration" >&2
    echo "          interrompue laisse ses tables et colonnes sans ecrire sa" >&2
    echo "          ligne dans django_migrations, et bute ensuite sur son" >&2
    echo "          propre travail. Le detail ci-dessus nomme l'objet en" >&2
    echo "          cause ; voir apps/core/migrations_rejouables.py." >&2
    return 1
  fi
  if ! sudo -u orion -E "$VENV_PY" "$MANAGE" collectstatic --noinput >/dev/null; then
    echo "  ERREUR: collectstatic a echoue — l'interface s'afficherait sans" >&2
    echo "          styles ni scripts." >&2
    return 1
  fi
  echo "  code récupéré, schéma migré, statiques collectés."
}

maj_applicative() {
  sudo -u orion -E "$VENV_PY" "$MANAGE" run_system_update --no-confirm
}

# Un echec du code ou du schema est RETENU ici, et decide du code de sortie a
# la toute fin. Il n'interrompt pas le script sur place : les etapes qui
# suivent -- scripts d'exploitation, unites systemd, redemarrage des
# services -- sont precisement celles par lesquelles un correctif ARRIVE sur
# la machine. S'arreter net les priverait de leur mise a jour, et la panne se
# reconduirait au lancement suivant.
ECHEC_CRITIQUE=0

case "$MODE" in
  direct)
    echo "  mode --direct : le mécanisme applicatif est volontairement ignoré."
    if ! maj_directe; then
      echo "  ATTENTION: mise à jour directe échouée." >&2
      ECHEC_CRITIQUE=1
    fi
    ;;
  django)
    echo "  mode --django-only : aucun repli."
    if ! maj_applicative; then
      echo "  ATTENTION: run_system_update a échoué." >&2
      ECHEC_CRITIQUE=1
    fi
    ;;
  *)
    if ! maj_applicative; then
      echo "  ATTENTION: run_system_update a échoué — repli sur une mise à jour directe." >&2
      if maj_directe; then
        # Nouvelle tentative avec le code à jour : si l'échec venait du
        # mécanisme lui-même, il est désormais corrigé. Cela restaure la trace
        # SystemUpdateRun et le point de rollback, que le repli ne crée pas.
        echo "  nouvelle tentative du mécanisme normal..."
        maj_applicative \
          || echo "  ATTENTION: run_system_update échoue encore — cause applicative, voir /opt/orion/logs/errors.log." >&2
      else
        # Les deux voies ont echoue : ni le mecanisme applicatif ni le repli
        # direct n'ont pose le code et le schema. Rien n'est a jour.
        ECHEC_CRITIQUE=1
      fi
    fi
    ;;
esac

# Rafraichit /opt/orion/scripts/ depuis le depot.
#
# Ces scripts n'arrivaient QUE par le payload cloud-init, copie une seule
# fois au provisioning (07-backup-cron.sh). Aucune mise a jour ne les
# touchait : un correctif apporte a refresh_allowed_hosts.sh, orion-disk.sh
# ou orion-cloudflare.sh n'atteignait jamais une appliance deja installee,
# alors meme que le code applicatif, lui, se mettait a jour.
#
# Le renommage (mv) est essentiel : bash lit son script au fur et a mesure de
# l'execution. Un cp ecraserait le fichier EN PLACE, et le shell en cours
# reprendrait sa lecture a son ancien decalage dans le nouveau contenu --
# donc au milieu d'une ligne. Un mv cree un nouvel inode ; le processus en
# cours garde l'ancien ouvert et se termine proprement sur la version avec
# laquelle il a demarre.
rafraichir_scripts() {
  local source_scripts="$ORION_HOME/backend/deployment/proxmox-appliance/scripts"
  if [ ! -d "$source_scripts" ]; then
    echo "  scripts absents du depot ($source_scripts) — ignores."
    return 0
  fi

  local sas
  sas="$(mktemp -d)"
  cp "$source_scripts"/*.sh "$sas"/ 2>/dev/null || true
  cp "$source_scripts"/*.py "$sas"/ 2>/dev/null || true
  # commun.sh vit dans provisioning/lib, pas dans scripts/ : sans cette ligne,
  # les scripts rafraichis trouveraient une bibliotheque plus ancienne qu'eux
  # -- ou pas de bibliotheque du tout sur une appliance installee avant son
  # introduction, et refuseraient alors de s'executer.
  cp "$ORION_HOME/backend/deployment/proxmox-appliance/provisioning/lib/commun.sh"      "$sas"/commun.sh 2>/dev/null || true

  local poses=0
  for fichier in "$sas"/*; do
    [ -f "$fichier" ] || continue
    chmod +x "$fichier" || echo "  ATTENTION: $fichier non rendu executable." >&2
    mv -f "$fichier" "$ORION_HOME/scripts/$(basename "$fichier")" \
      || echo "  ATTENTION: $(basename "$fichier") non pose." >&2
    poses=$((poses + 1))
  done
  rm -rf "$sas" || true

  chown -R orion:orion "$ORION_HOME/scripts" 2>/dev/null || true
  echo "  $poses script(s) d'exploitation rafraichis depuis le depot."
  echo "  (update_orion.sh lui-meme prendra effet au prochain lancement)"
}
rafraichir_scripts || echo "  ATTENTION: rafraichissement des scripts echoue." >&2

# Rafraichit aussi les unites systemd, pour la meme raison que les scripts :
# elles n'arrivaient que par le provisioning (03-systemd-units.sh), donc un
# correctif apporte a orion-backend.service n'atteignait jamais une appliance
# deja installee. Constate douloureusement : le prefixe ExecStartPre=- qui
# empeche un script de confort de rendre l'ERP indemarrable n'aurait pas pu
# etre livre par une mise a jour.
#
# Un cp suffit ici, contrairement aux scripts : systemd relit les unites au
# daemon-reload et ne tient pas de descripteur ouvert sur le fichier. Le
# depot est la source de verite, le provisioning les copiant deja telles
# quelles, sans rendu de variables.
rafraichir_unites_systemd() {
  local source_unites="$ORION_HOME/backend/deployment/proxmox-appliance/systemd"
  if [ ! -d "$source_unites" ]; then
    echo "  unites systemd absentes du depot — ignorees."
    return 0
  fi
  cp "$source_unites"/*.service /etc/systemd/system/ 2>/dev/null || true
  cp "$source_unites"/*.timer   /etc/systemd/system/ 2>/dev/null || true

  # Les FRAGMENTS (« drop-ins ») completent des unites que ce depot ne
  # possede pas. cloudflared.service est installe par cloudflared lui-meme :
  # le remplacer serait ecrase a sa prochaine mise a jour. Systemd lit
  # /etc/systemd/system/<unite>.d/*.conf PAR-DESSUS l'unite d'origine, ce qui
  # permet d'ajouter « Restart=always » et une borne de redemarrage a une
  # unite dont on n'est pas proprietaire.
  #
  # C'est ainsi que le tunnel se releve seul, sans gardien pour le
  # surveiller -- le 09/11/2026, l'acces a l'ERP a ete perdu parce que
  # cloudflared etait tombe et que rien ne le relevait.
  if [ -d "$source_unites/dropins" ]; then
    poses=0
    for dossier in "$source_unites"/dropins/*/; do
      [ -d "$dossier" ] || continue
      cible="/etc/systemd/system/$(basename "$dossier")"
      if ! mkdir -p "$cible" 2>/dev/null; then
        echo "  ATTENTION: $cible non cree, fragment ignore." >&2
        continue
      fi
      if cp "$dossier"*.conf "$cible"/ 2>/dev/null; then
        poses=$((poses + 1))
      else
        echo "  ATTENTION: fragments de $(basename "$dossier") non poses." >&2
      fi
    done
    echo "  $poses fragment(s) d'unite pose(s)."
  fi
  systemctl daemon-reload || echo "  ATTENTION: daemon-reload a echoue." >&2
  echo "  unites systemd rafraichies depuis le depot."
}
rafraichir_unites_systemd || echo "  ATTENTION: rafraichissement des unites echoue." >&2

# Les relevés de catalogues, APRÈS le bloc de modes et non dans l'un d'eux :
# le mode par défaut passe par le mécanisme applicatif et ne touche
# maj_directe qu'en cas d'échec. Placée dans maj_directe, cette étape ne se
# serait jamais exécutée en usage normal.
#
# Et APRÈS le rafraîchissement des scripts et des unités, non avant. Cette
# étape interroge des sites de fabricants : elle dure des minutes, dépend du
# réseau, et n'apporte que des prix indicatifs. Placée avant, elle retardait
# la pose de /etc/systemd/system/orion-update.service -- au point que
# `systemctl start orion-update.service` répondait encore « Unit not found »
# alors que la mise à jour tournait depuis plusieurs minutes. L'infrastructure
# d'abord, le confort ensuite.
importer_catalogues_fabricants

# Recompile les catalogues : un .po mis a jour par le git pull resterait
# sans effet tant que son .mo n'est pas regenere.
sudo -u orion -E "$VENV_PY" "$MANAGE" compilemessages \
  || echo "  ATTENTION: compilemessages a echoue, traductions inchangees."

# Rafraichir les aides privilegiees (regles sudo et assistant disque).
#
# POURQUOI CE BLOC EXISTE. Ces fichiers n'etaient installes que par
# provisioning/02-deploy-orion.sh, c'est-a-dire une seule fois, a la
# creation de la machine. Une regle sudo ajoutee ou corrigee plus tard
# n'arrivait donc JAMAIS sur une machine deja installee : le bouton
# correspondant s'affichait dans l'ERP et ne faisait rien, exactement le
# defaut que sudoers/orion-serveur decrit. On les reinstalle a chaque mise
# a jour, apres le git pull qui vient de les apporter.
#
# visudo -c AVANT mise en place, et c'est imperatif : un fichier malforme
# dans /etc/sudoers.d/ casse sudo pour TOUT LE MONDE, y compris pour le
# reparer.
# ─── Les cles de .env apparues APRES l'installation ──────────────────────────
#
# Le provisioning ne tourne qu'une seule fois. Une cle ajoutee au produit
# plus tard n'arrive donc JAMAIS sur une machine deja installee, et son
# absence se manifeste des mois apres, loin de sa cause.
#
# Constate le 09/11/2026 : ORION_NODE_ID manquait sur une appliance
# installee avant son introduction, et le verificateur declarait a juste
# titre un defaut bloquant -- sans lui, la protection anti-divergence de la
# haute disponibilite compare une valeur VIDE au verrou de grappe.
#
# Meme raisonnement que pour les regles sudo, les unites systemd et
# l'assistant disque : ce qui n'est pose qu'une fois doit etre RATTRAPE a
# chaque mise a jour.
#
# La valeur par defaut est celle du provisioning, « orion-primary », et non
# le nom de machine : identique a une installation neuve, donc aucun
# changement de comportement. Une grappe de plusieurs serveurs doit la
# personnaliser, comme le provisioning le fait avec --node-domain.
completer_env() {
  local cle="$1" valeur="$2"
  if [ ! -w "$ENV_FILE" ]; then
    echo "  ATTENTION: $ENV_FILE non inscriptible, $cle non ajoutee." >&2
    return 0
  fi
  if grep -qE "^[[:space:]]*${cle}=" "$ENV_FILE" 2>/dev/null; then
    return 0
  fi
  if printf '%s=%s
' "$cle" "$valeur" >> "$ENV_FILE"; then
    echo "  .env complete : $cle=$valeur (cle absente depuis l'installation)"
  else
    echo "  ATTENTION: $cle n'a pas pu etre ajoutee a $ENV_FILE." >&2
  fi
}

completer_env ORION_NODE_ID orion-primary
completer_env ORION_NODE_PRIORITY 1

echo "[5/7] Rafraîchissement des droits et assistants privilégiés..."
SUDOERS_DIR="$ORION_HOME/backend/deployment/proxmox-appliance/sudoers"
for nom in orion-serveur orion-stockage orion-maj; do
  src="$SUDOERS_DIR/$nom"
  if [ ! -f "$src" ]; then
    echo "  $nom : source absente, ignoré."
    continue
  fi
  tmp="$(mktemp)"
  if ! install -m 0440 -o root -g root "$src" "$tmp"; then
    echo "  ATTENTION: $nom non prepare, conserve en l'etat." >&2
    rm -f "$tmp" || true
    continue
  fi
  if visudo -c -f "$tmp" >/dev/null 2>&1; then
    if install -m 0440 -o root -g root "$tmp" "/etc/sudoers.d/$nom"; then
      echo "  $nom : installé."
    else
      echo "  ATTENTION: $nom non installe dans /etc/sudoers.d/." >&2
    fi
  else
    echo "  ATTENTION: $nom refusé par visudo -c, conservé en l'état." >&2
  fi
  rm -f "$tmp" || true
done

# Mode 0750, groupe orion : executable par le compte de service, jamais
# inscriptible par lui. S'il pouvait reecrire ce fichier, la regle sudo qui
# l'autorise equivaudrait a un acces root complet.
STOCKAGE_SRC="$ORION_HOME/backend/deployment/proxmox-appliance/scripts/orion-stockage"
if [ -f "$STOCKAGE_SRC" ]; then
  if install -o root -g orion -m 0750 "$STOCKAGE_SRC" /usr/local/sbin/orion-stockage; then
    echo "  assistant disque : /usr/local/sbin/orion-stockage installé."
  else
    echo "  ATTENTION: assistant disque non installe ; la preparation" >&2
    echo "             d'un disque restera indisponible dans l'ERP." >&2
  fi
  if ! command -v sgdisk >/dev/null 2>&1 || ! command -v partprobe >/dev/null 2>&1; then
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq gdisk parted >/dev/null 2>&1 \
      || echo "  ATTENTION: gdisk/parted non installés, préparation de disque indisponible." >&2
  fi
else
  echo "  assistant disque : source absente, ignoré."
fi

# ─── LE REDEMARRAGE DU BACKEND, AVANT LES BUILDS NPM ──────────────────────
#
# C'est le point le plus important de ce script, et il etait le dernier.
#
# Django met ses gabarits en cache des que DEBUG est faux : un gabarit
# corrige sur le disque n'est PLUS JAMAIS relu tant que le processus ne
# redemarre pas. Le redemarrage n'est donc pas une finition, c'est l'etape
# qui rend la mise a jour EFFECTIVE.
#
# Or il etait place en dernier, derriere trois builds npm et un « chown »
# non protege. Mesure du 08/11/2026, dans le journal de l'unite :
#
#     chown: cannot access '/opt/orion/siecle': No such file or directory
#     orion-update.service: Main process exited, code=exited, status=1/FAILURE
#
# Sous « set -e », ce chown a tue le script juste avant le redemarrage. Le
# code etait bien sur le disque ; gunicorn servait toujours l'ancien depuis
# sa memoire. QUATRE correctifs successifs n'ont donc jamais ete charges --
# chacun paraissant sans effet, ce qui a envoye le diagnostic dans le mur a
# chaque fois, et fait chercher le defaut dans le code corrige au lieu du
# mecanisme qui ne le livrait pas.
#
# Plus rien de facultatif ne se trouve entre le code et son chargement, et
# un test interdit toute commande non protegee dans cet intervalle.
echo "[6/7] Redémarrage du backend et des tâches de fond..."
if systemctl restart orion-backend.service; then
  echo "  orion-backend redémarré — le nouveau code est désormais servi."
else
  echo "  ERREUR: orion-backend n'a pas redemarre. L'ERP continue de servir" >&2
  echo "          l'ANCIEN code depuis la memoire du processus, et aucun" >&2
  echo "          correctif de cette mise a jour n'est visible." >&2
  ECHEC_CRITIQUE=1
fi
# Celery charge le code applicatif au demarrage : sans redemarrage, les
# taches continueraient de tourner sur l'ancienne version.
systemctl restart orion-celery.service orion-celery-beat.service   || echo "  ATTENTION: Celery n'a pas redemarre ; les taches de fond tournent sur l'ancien code." >&2

# npm doit etre TROUVE, pas suppose.
#
# Mesure du 08/11/2026, dans le journal de l'unite systemd :
#
#     update_orion.sh: line 450: npm: command not found
#
# Lance a la main par « bash -lc », le shell de connexion lit /etc/profile et
# les scripts de nvm : npm est la. Lance par systemd, PATH est le minimum du
# systeme et npm est introuvable. Le meme script reussissait donc a la main
# et echouait en service -- le pire des deux mondes, puisque le mode service
# est precisement celui qui doit marcher quand l'interface web est tombee.
chemin_de_npm() {
  local candidat
  if command -v npm >/dev/null 2>&1; then
    command -v npm
    return 0
  fi
  for candidat in /usr/local/bin/npm /usr/bin/npm /opt/node/bin/npm; do
    if [ -x "$candidat" ]; then echo "$candidat"; return 0; fi
  done
  # nvm : la version la plus recente installee, pour root comme pour orion.
  candidat="$(ls -1d /root/.nvm/versions/node/*/bin/npm                      /home/orion/.nvm/versions/node/*/bin/npm 2>/dev/null               | sort -V | tail -1)"
  if [ -n "$candidat" ] && [ -x "$candidat" ]; then echo "$candidat"; return 0; fi
  return 1
}

NPM_TROUVE="$(chemin_de_npm || true)"
if [ -n "$NPM_TROUVE" ]; then
  PATH="$(dirname "$NPM_TROUVE"):$PATH"
  export PATH
  echo "  npm : $NPM_TROUVE"
else
  echo "  ATTENTION: npm introuvable, meme hors du PATH de systemd. Les" >&2
  echo "             frontends ne seront pas reconstruits ; leurs versions" >&2
  echo "             precedentes restent servies. Le backend, lui, est deja" >&2
  echo "             a jour et redemarre." >&2
fi

echo "[7/7] Reconstruction des frontends SIÈCLE / LUNEA / NÉOSTRUCTURA..."
for store in siecle-store:siecle lunea-store:lunea; do
  SRC_DIR="${store%%:*}"; DEST_NAME="${store##*:}"
  STORE_PATH="$ORION_HOME/backend/frontend/$SRC_DIR"
  if [ -d "$STORE_PATH" ]; then
    (cd "$STORE_PATH" && npm ci --silent && \
      VITE_API_BASE_URL="https://${ORION_LOGIN_DOMAIN:-$ORION_FRONTEND_DOMAIN}/api/v1" npm run build) \
      && rm -rf "$ORION_HOME/$DEST_NAME"/* \
      && cp -r "$STORE_PATH/dist/." "$ORION_HOME/$DEST_NAME/" \
      || echo "  ATTENTION: build $SRC_DIR échoué — version précédente conservée."
  fi
done
# Le chown qui a tue cette mise a jour quatre fois. Les dossiers n'existaient
# pas -- les builds npm ayant echoue, rien ne les avait crees -- et sous
# « set -e » un chown en echec arrete tout le script. Desormais : les
# dossiers sont crees s'il manquent, et l'echec est signale sans interrompre.
for nom_du_frontend in siecle lunea; do
  mkdir -p "$ORION_HOME/$nom_du_frontend" 2>/dev/null     || echo "  ATTENTION: $ORION_HOME/$nom_du_frontend non cree." >&2
  chown -R orion:orion "$ORION_HOME/$nom_du_frontend" 2>/dev/null     || echo "  ATTENTION: proprietaire de $ORION_HOME/$nom_du_frontend inchange." >&2
done

# NÉOSTRUCTURA à part : aucune URL d'API à injecter au build (appels relatifs,
# proxifiés par Nginx), et pas de service applicatif à redémarrer puisque c'est
# Nginx qui sert les fichiers — d'où le chmod, www-data doit pouvoir les lire.
NS_PATH="$ORION_HOME/backend/frontend/neostructura-site"
if [ -d "$NS_PATH" ]; then
  if (cd "$NS_PATH" && npm ci --silent && npm run build); then
    mkdir -p "$ORION_HOME/neostructura"
    rm -rf "$ORION_HOME/neostructura"/*
    cp -r "$NS_PATH/dist/." "$ORION_HOME/neostructura/"
    chown -R orion:orion "$ORION_HOME/neostructura"
    chmod -R a+rX "$ORION_HOME/neostructura"
  else
    echo "  ATTENTION: build NÉOSTRUCTURA échoué — version précédente conservée."
  fi
fi


# Les frontends redemarrent APRES leur build, contrairement au backend : ils
# servent des fichiers produits a l'instant, et les relancer avant les
# laisserait servir l'ancien bundle.
echo "  redémarrage des frontends..."
systemctl restart orion-frontend.service   || echo "  ATTENTION: orion-frontend n'a pas redemarre." >&2
systemctl restart siecle-frontend.service lunea-frontend.service   || echo "  ATTENTION: siecle-frontend / lunea-frontend n'ont pas redemarre." >&2
systemctl reload nginx   || echo "  ATTENTION: nginx n'a pas recharge sa configuration." >&2

sleep 3
systemctl --no-pager status orion-backend.service orion-frontend.service \
  siecle-frontend.service lunea-frontend.service --lines=0 || true

# Verifie ce qu'un navigateur verrait, au lieu d'annoncer un succes sur la
# seule foi des commandes passees. Une mise a jour peut laisser l'ERP en 500
# (statiques non recollectes) ou en 502 (service qui ne redemarre pas) : les
# deux se sont produits, et dans les deux cas le script s'etait declare
# termine.
echo ""
echo "[verification] Etat de l'installation apres mise a jour..."
VERIFICATEUR="$ORION_HOME/scripts/orion-verifier.sh"
VERIFICATION_OK=1
if [ -f "$VERIFICATEUR" ]; then
  bash "$VERIFICATEUR" || VERIFICATION_OK=0
else
  echo "  (orion-verifier.sh absent — rien n'a ete verifie)"
fi

# Le verdict final, en un seul endroit. Il etait auparavant annonce depuis
# trois branches differentes, et l'une d'elles -- celle de la mise a jour
# directe -- disait « terminee » sur une migration en echec.
echo ""
if [ "$ECHEC_CRITIQUE" -ne 0 ]; then
  echo "ECHEC: le code ou le schema n'a PAS ete mis a jour (detail plus haut)." >&2
  echo "       Les scripts d'exploitation, les unites systemd et les services" >&2
  echo "       ont tout de meme ete rafraichis : c'est par eux qu'un correctif" >&2
  echo "       arrive sur la machine, donc un nouveau lancement a une chance" >&2
  echo "       d'aboutir la ou celui-ci a echoue." >&2
  echo "       Etat : cat $FICHIER_ETAT" >&2
  echo "       Journal : journalctl -u orion-update --no-pager" >&2
  exit 1
fi
if [ "$VERIFICATION_OK" -eq 0 ]; then
  echo "ATTENTION: la mise a jour est passee mais la verification signale des" >&2
  echo "defauts (detail ci-dessus). Rollback applicatif si necessaire :" >&2
  echo "  sudo -u orion $VENV_PY $MANAGE rollback_system_update" >&2
  exit 1
fi
if [ -f "$VERIFICATEUR" ]; then
  echo "Mise a jour terminee — installation verifiee."
else
  echo "Mise à jour terminée."
fi
echo "En cas de problème : sudo -u orion $VENV_PY $MANAGE rollback_system_update"
