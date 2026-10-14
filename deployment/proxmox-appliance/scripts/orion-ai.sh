#!/usr/bin/env bash
# ============================================================================
# Orion ERP Appliance — Moteur IA local (Ollama)
#
# Orion répond UNIQUEMENT en local : les devis, les clients, les factures et
# l'état du système ne doivent jamais quitter la machine. Aucune clé d'API,
# aucun appel sortant, aucun tiers dans la boucle. C'est pourquoi le moteur
# est servi ici, et pourquoi il n'écoute que la boucle locale.
#
# Dimensionnement : un modèle de 3 milliards de paramètres quantifié tient en
# ~2 Go sur le disque et demande ~3 Go de RAM à l'inférence. Sur une VM à
# 2 cœurs, comptez quelques secondes par réponse. Un modèle de 7 Go et plus
# ne tient pas dans 4 Go de RAM : il serait chargé puis tué par le noyau.
#
# Usage :
#   orion-ai.sh install [MODELE]   Installe Ollama et télécharge le modèle
#   orion-ai.sh status             Service, modèles présents, RAM disponible
#   orion-ai.sh test [QUESTION]    Interroge le moteur et mesure le temps
#   orion-ai.sh bench [MODELE]     Mesure le débit réel et le qualifie
#   orion-ai.sh models             Modèles téléchargés
#   orion-ai.sh pull MODELE        Télécharge un autre modèle
#   orion-ai.sh stop | start       Arrête / démarre le service
# ============================================================================

set -euo pipefail

# La CLI Ollama panique avec « $HOME is not defined » quand la variable
# manque -- et « qm guest exec » n en definit aucune, ce qui est le mode
# d acces normal a cette appliance. Constate en production. La garde vaut
# pour toutes les commandes du script, y compris l installateur officiel.
export HOME="${HOME:-/root}"

ORION_HOME="/opt/orion"
ENV_FILE="$ORION_HOME/backend/.env"
MODELE_DEFAUT="qwen2.5:3b-instruct"
HOTE="127.0.0.1:11434"

# Les lignes 2 a 22 de ce fichier SONT le texte d'aide : ajouter une commande
# ci-dessus demande d'etendre cette plage, sinon la derniere ligne disparait.
usage() { sed -n '2,22p' "$0"; exit "${1:-0}"; }

exiger_root() { [ "$(id -u)" -eq 0 ] || { echo "ERREUR: à lancer en root." >&2; exit 1; }; }

modele_configure() {
  # Le modèle réellement attendu par l'application, et non celui qu'on croit
  # avoir installé : les deux ont divergé une fois de trop dans ce projet.
  local depuis_env=''
  [ -f "$ENV_FILE" ] && depuis_env="$(grep '^ORION_AI_DEFAULT_MODEL=' "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' || true)"
  echo "${depuis_env:-$MODELE_DEFAUT}"
}

ram_libre_mo() {
  awk '/MemAvailable/ {printf "%d", $2/1024}' /proc/meminfo 2>/dev/null || echo 0
}

telecharger_modele() {
  local modele="$1"

  # Par l API du demon et non par la CLI. Deux raisons : « ollama pull »
  # panique sans $HOME, et c est de toute facon le demon qui telecharge et
  # stocke le modele -- passer par son API supprime toute dependance a
  # l environnement de la CLI et a l utilisateur qui la lance.
  #
  # stream:false attend la fin sans rien afficher. C est assume : sous
  # « qm guest exec » la sortie est de toute maniere retenue jusqu a la fin
  # de la commande, une progression ne serait donc pas visible.
  echo "[ia] Telechargement de $modele par l API du demon (plusieurs minutes, sans affichage)..."

  local reponse
  if ! reponse="$(curl -fsS --max-time 3000 -X POST "http://$HOTE/api/pull"       -H 'Content-Type: application/json'       -d "{\"model\": \"$modele\", \"name\": \"$modele\", \"stream\": false}" 2>&1)"; then
    echo "ERREUR: le telechargement de $modele a echoue." >&2
    echo "        $reponse" >&2
    return 1
  fi

  if echo "$reponse" | grep -q '"error"'; then
    echo "ERREUR: le demon a refuse le telechargement :" >&2
    echo "        $reponse" >&2
    return 1
  fi

  # Verifie, pas suppose : un telechargement interrompu laisse le demon debout
  # sans le modele, et l ERP repond alors un 404 sur /api/chat -- message qui
  # ne designe pas la cause.
  if ! curl -fsS "http://$HOTE/api/tags" 2>/dev/null | grep -q "\"$modele\""; then
    echo "ERREUR: $modele n apparait pas dans les modeles installes." >&2
    echo "        Relancez : orion-ai.sh pull $modele" >&2
    return 1
  fi

  echo "[ia] Modele $modele present et verifie."
}

cmd_install() {
  exiger_root
  local modele="${1:-$(modele_configure)}"

  local ram
  ram="$(ram_libre_mo)"
  if [ "$ram" -lt 2500 ]; then
    echo "ATTENTION: $ram Mo de RAM disponibles seulement." >&2
    echo "           Un modèle 3B en demande environ 3000 Mo à l'inférence." >&2
    echo "           Le noyau risque de tuer le processus en pleine réponse." >&2
    echo "           Augmentez la RAM de la VM : qm set <vmid> --memory 8192" >&2
    echo ""
  fi

  if ! command -v ollama >/dev/null 2>&1; then
    echo "[ia] Installation d'Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
  else
    echo "[ia] Ollama déjà installé."
  fi

  # N'écouter QUE la boucle locale. C'est le point le plus important de ce
  # script : un moteur IA joignable depuis le réseau est une porte ouverte sur
  # tout ce qu'on lui soumet, et il n'a aucune authentification. Ollama écoute
  # déjà 127.0.0.1 par défaut, mais un défaut se change — on l'impose.
  mkdir -p /etc/systemd/system/ollama.service.d
  cat > /etc/systemd/system/ollama.service.d/orion.conf <<EOF
[Service]
Environment=OLLAMA_HOST=$HOTE
# Le modèle est libéré de la mémoire après ce délai d'inactivité. Sur une
# petite VM, garder 3 Go résidents en permanence prive l'ERP de sa mémoire,
# alors que le rechargement ne coûte que quelques secondes.
Environment=OLLAMA_KEEP_ALIVE=5m
# Un seul chargement à la fois : deux inférences simultanées sur 2 cœurs ne
# vont pas deux fois plus vite, elles échouent toutes les deux.
Environment=OLLAMA_MAX_LOADED_MODELS=1
Environment=OLLAMA_NUM_PARALLEL=1
EOF

  systemctl daemon-reload
  systemctl enable --now ollama >/dev/null 2>&1 || systemctl restart ollama

  echo "[ia] Attente du service..."
  local pret=0
  for _ in $(seq 1 30); do
    if curl -fsS "http://$HOTE/api/tags" >/dev/null 2>&1; then pret=1; break; fi
    sleep 2
  done
  [ "$pret" -eq 1 ] || { echo "ERREUR: Ollama ne répond pas sur $HOTE." >&2; exit 1; }

  telecharger_modele "$modele" || exit 1

  if command -v ufw >/dev/null 2>&1; then
    # Refus explicite, par principe de défense en profondeur : même si
    # OLLAMA_HOST était un jour desserré, le pare-feu tiendrait.
    ufw deny 11434/tcp >/dev/null 2>&1 || true
    echo "[ia] Pare-feu : port 11434 refusé depuis le réseau."
  fi

  echo "[ia] Terminé. Orion peut répondre, entièrement sur ce serveur."
  cmd_status
}

cmd_status() {
  echo "=== Service ==="
  if systemctl is-active --quiet ollama 2>/dev/null; then
    echo "  ollama : actif"
  else
    echo "  ollama : INACTIF — lancez « install »"
  fi

  echo "  écoute : $HOTE (boucle locale uniquement)"
  echo "  RAM disponible : $(ram_libre_mo) Mo"

  echo ""
  echo "=== Modèle attendu par l'application ==="
  local attendu
  attendu="$(modele_configure)"
  echo "  $attendu"

  echo ""
  echo "=== Modèles présents ==="
  if curl -fsS "http://$HOTE/api/tags" 2>/dev/null | grep -q '"name"'; then
    curl -fsS "http://$HOTE/api/tags" 2>/dev/null \
      | tr ',' '\n' | grep '"name"' | cut -d'"' -f4 | sed 's/^/  /'
    if ! curl -fsS "http://$HOTE/api/tags" 2>/dev/null | grep -q "\"$attendu\""; then
      echo ""
      echo "  ATTENTION: le modèle attendu « $attendu » n'est pas téléchargé." >&2
      echo "             Orion échouera à chaque question." >&2
      echo "             Lancez : orion-ai.sh pull $attendu" >&2
    fi
  else
    echo "  (moteur injoignable)"
  fi
}

cmd_models() { curl -fsS "http://$HOTE/api/tags" | tr ',' '\n' | grep '"name"' | cut -d'"' -f4; }

cmd_pull() {
  exiger_root
  local modele="${1:-}"
  [ -n "$modele" ] || { echo "Usage: pull MODELE" >&2; exit 2; }
  telecharger_modele "$modele" || exit 1
}

cmd_test() {
  local question="${*:-Bonjour, en une phrase : que fais-tu ?}"
  local modele
  modele="$(modele_configure)"

  echo "Modèle  : $modele"
  echo "Question: $question"
  echo ""

  local debut fin
  debut="$(date +%s)"
  local reponse
  if ! reponse="$(curl -fsS "http://$HOTE/api/chat" \
      -H 'Content-Type: application/json' \
      --data-binary @- <<EOF
{"model": "$modele", "stream": false, "messages": [{"role": "user", "content": "$question"}]}
EOF
  )"; then
    echo "ERREUR: le moteur n'a pas répondu. Vérifiez « orion-ai.sh status »." >&2
    exit 1
  fi
  fin="$(date +%s)"

  echo "$reponse" | python3 -c "import json,sys; print(json.load(sys.stdin).get('message',{}).get('content','(vide)'))" 2>/dev/null \
    || echo "$reponse"
  echo ""
  echo "Temps de réponse : $((fin - debut)) s"
}

cmd_bench() {
  # Mesure le debit reel de ce serveur, et le compare a ce qui est confortable.
  #
  # C'est la seule question que les reglages de l'ERP ne peuvent pas trancher :
  # garder le modele en memoire, plafonner la reponse et raccourcir le prompt
  # aident, mais si la machine ne produit que 3 jetons par seconde, aucun
  # reglage ne rendra l'assistant agreable -- il faut un modele plus petit.
  local modele="${1:-$MODELE_DEFAUT}"
  echo "[ia] Mesure sur « $modele »..."
  echo "[ia] Deux passes : la premiere inclut le chargement du modele."

  local passe reponse
  for passe in 1 2; do
    if ! reponse="$(curl -fsS --max-time 300 -X POST "http://$HOTE/api/chat"         -H 'Content-Type: application/json'         -d "{\"model\": \"$modele\", \"stream\": false, \"options\": {\"num_predict\": 120}, \"messages\": [{\"role\": \"user\", \"content\": \"Explique en trois phrases a quoi sert un devis.\"}]}" 2>&1)"; then
      echo "[ia] ERREUR : le moteur n'a pas repondu. Verifiez : orion-ai.sh status" >&2
      return 1
    fi
    if printf '%s' "$reponse" | grep -q '"error"'; then
      echo "[ia] ERREUR : $(printf '%s' "$reponse" | tr ',' '
' | grep '"error"' | cut -d'"' -f4)" >&2
      return 1
    fi

    # Durees en nanosecondes dans la reponse d'Ollama.
    local charge evalue genere jetons
    charge="$(printf '%s' "$reponse" | tr ',' '
' | grep '"load_duration"' | tr -dc '0-9')"
    evalue="$(printf '%s' "$reponse" | tr ',' '
' | grep '"prompt_eval_duration"' | tr -dc '0-9')"
    genere="$(printf '%s' "$reponse" | tr ',' '
' | grep '"eval_duration"' | grep -v prompt | tr -dc '0-9')"
    jetons="$(printf '%s' "$reponse" | tr ',' '
' | grep '"eval_count"' | tr -dc '0-9')"

    printf '[ia] passe %s : chargement %s s, lecture du prompt %s s, generation %s s
'       "$passe"       "$(awk "BEGIN{printf \"%.1f\", ${charge:-0}/1000000000}")"       "$(awk "BEGIN{printf \"%.1f\", ${evalue:-0}/1000000000}")"       "$(awk "BEGIN{printf \"%.1f\", ${genere:-0}/1000000000}")"

    if [ "$passe" = '2' ] && [ -n "${genere:-}" ] && [ -n "${jetons:-}" ]        && [ "${genere:-0}" -gt 0 ]; then
      local debit
      debit="$(awk "BEGIN{printf \"%.1f\", $jetons/($genere/1000000000)}")"
      echo ""
      echo "[ia] Debit : $debit jetons/seconde."
      # Reperes : en dessous de 8 jetons/s, une reponse de 300 jetons demande
      # plus de 35 secondes -- le flux la rend lisible, mais l'attente reste.
      awk -v d="$debit" 'BEGIN{
        if (d >= 20) print "[ia] Confortable : les reponses arrivent sans attente notable.";
        else if (d >= 8) print "[ia] Acceptable avec le flux active : les premiers mots arrivent vite,
[ia] la fin defile. Rien a changer.";
        else print "[ia] LENT. Aucun reglage ne compensera ce debit. Essayez un modele
[ia] plus petit : orion-ai.sh pull qwen2.5:1.5b-instruct
[ia] puis selectionnez-le dans Parametres IA.";
      }'
    fi
  done

  echo ""
  echo "[ia] Si le chargement de la passe 1 depasse 2 s, augmentez"
  echo "[ia] « Garder le modele en memoire » dans Parametres IA : c'est la cause"
  echo "[ia] la plus courante d'une reponse isolee tres lente."
}

cmd_stop()  { exiger_root; systemctl stop ollama;  echo "[ia] Moteur arrêté."; }
cmd_start() { exiger_root; systemctl start ollama; echo "[ia] Moteur démarré."; }

case "${1:-}" in
  install) shift; cmd_install "$@" ;;
  status)  shift; cmd_status "$@" ;;
  models)  shift; cmd_models "$@" ;;
  pull)    shift; cmd_pull "$@" ;;
  test)    shift; cmd_test "$@" ;;
  bench)   shift; cmd_bench "$@" ;;
  stop)    shift; cmd_stop "$@" ;;
  start)   shift; cmd_start "$@" ;;
  -h|--help|'') usage 0 ;;
  *)       echo "Commande inconnue : $1" >&2; usage 2 ;;
esac
