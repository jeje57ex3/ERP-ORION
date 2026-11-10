#!/usr/bin/env bash
# ============================================================================
# Orion ERP Appliance — Moteur IA local (Ollama)
#
# Orion répond UNIQUEMENT en local : les devis, les clients, les factures et
# l'état du système ne doivent jamais quitter la machine. Aucune clé d'API,
# aucun appel sortant, aucun tiers dans la boucle. C'est pourquoi le moteur
# est servi ici, et pourquoi il n'écoute que la boucle locale.
#
# Dimensionnement, en Go de RAM À L'INFÉRENCE et non sur le disque — c'est la
# RAM qui décide si le modèle répond ou se fait tuer par le noyau en pleine
# réponse :
#
#   qwen3.5:2b-q4_K_M   1,9 Go disque   ~2,7 Go RAM   tient sur une VM à 4 Go
#   qwen3.5:4b-q4_K_M   3,3 Go disque   ~4,3 Go RAM   défaut, VM à 8 Go
#   qwen3.5:9b-q4_K_M   6,6 Go disque   ~7,7 Go RAM   ne tient pas avec MySQL
#
# Sur 2 à 4 cœurs, comptez quelques secondes par réponse. « orion-ai.sh bench »
# mesure le débit réel de CETTE machine et le qualifie ; aucun réglage de l'ERP
# ne compense un débit insuffisant, seul un modèle plus petit le fait.
#
# Les noms sont exacts et ne se devinent pas : qwen3.5 a abandonné le suffixe
# « -instruct » de qwen2.5 et n'a pas de taille « 3b ». La quantification est
# épinglée parce qu'un tag court est réattribuable — le même nom peut désigner
# un fichier plus lourd après une mise à jour amont.
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
MODELE_DEFAUT="qwen3.5:4b-q4_K_M"
MODELE_PLUS_PETIT="qwen3.5:2b-q4_K_M"
HOTE="127.0.0.1:11434"

# L'en-tete de ce fichier EST le texte d'aide. La plage etait ecrite en dur
# (« sed -n 2,22p »), ce qui obligeait a la recaler a chaque ligne ajoutee
# au-dessus -- sinon la derniere ligne de l'aide disparaissait en silence.
# Elle est desormais deduite : toutes les lignes de commentaire qui suivent le
# shebang, jusqu'a la premiere ligne qui n'en est pas une.
usage() { awk 'NR>1 && /^#/ {print; next} NR>1 {exit}' "$0"; exit "${1:-0}"; }

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

# Fragment JSON « , "think": false » -- ou rien du tout.
#
# Les familles recentes (qwen3.5 et suivantes) reflechissent avant de repondre.
# La reflexion n arrive PAS dans « content » et ses jetons sont pris sur
# num_predict : « test » n afficherait qu une reponse vide, et « bench »
# mesurerait un debit de reflexion. Il faut donc la couper.
#
# Mais l option ne peut pas etre ajoutee par precaution : Ollama REFUSE la
# requete entiere -- HTTP 400, « <modele> does not support thinking » -- quand
# « think » est adresse a un modele sans cette capacite. Elle n est donc
# ajoutee que si le demon la DECLARE, et la capacite est demandee, pas deduite
# du nom.
#
# Sans python3, la capacite n est pas determinee et rien n est envoye : le pire
# cas est alors une mesure plus lente, jamais un refus.
option_think() {
  local modele="$1"
  command -v python3 >/dev/null 2>&1 || return 0
  if curl -fsS --max-time 10 -X POST "http://$HOTE/api/show" \
       -H 'Content-Type: application/json' \
       -d "{\"model\": \"$modele\"}" 2>/dev/null \
     | python3 -c 'import json,sys; sys.exit(0 if "thinking" in (json.load(sys.stdin).get("capabilities") or []) else 1)' 2>/dev/null
  then
    printf ', "think": false'
  fi
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
  # Seuil relevé avec le modèle : qwen3.5:4b-q4_K_M demande ~4300 Mo à
  # l'inférence, là où l'ancien 3B en demandait ~3000. Garder l'ancien seuil
  # aurait laissé passer sans un mot une machine où le noyau tue le processus
  # en pleine réponse — panne intermittente, et sans message qui la désigne.
  if [ "$ram" -lt 4500 ]; then
    echo "ATTENTION: $ram Mo de RAM disponibles seulement." >&2
    echo "           Le modèle demandé — « $modele » — peut ne pas tenir." >&2
    echo "           Reperes a l'inference : 2b-q4_K_M ~2700 Mo," >&2
    echo "           4b-q4_K_M ~4300 Mo, 9b-q4_K_M ~7700 Mo." >&2
    echo "           Le noyau risque de tuer le processus en pleine réponse." >&2
    echo "           Deux issues :" >&2
    echo "             - augmenter la RAM : qm set <vmid> --memory 8192" >&2
    echo "             - ou prendre le modèle plus petit (~2700 Mo) :" >&2
    echo "               orion-ai.sh install $MODELE_PLUS_PETIT" >&2
    echo "               puis le sélectionner dans « Paramètres IA »." >&2
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
# Délai d'inactivité après lequel le modèle est libéré de la mémoire, POUR
# LES SEULES REQUÊTES QUI N'EN IMPOSENT PAS UN. Le commentaire précédent
# affirmait ici que le modèle était libéré au bout de 5 minutes ; c'était
# faux pour l'usage réel de l'ERP.
#
# L'ERP envoie « keep_alive » dans chaque requête /api/chat (réglage
# « Garder le modèle en mémoire », 30 minutes par défaut, modifiable dans
# Paramètres IA), et la valeur de la requête l'emporte sur cette variable.
# Les 5 minutes ne s'appliquent donc qu'à ce qui ne précise rien :
# « orion-ai.sh test » et « orion-ai.sh bench ».
#
# C'est voulu : un diagnostic lancé depuis le serveur ne doit pas retenir
# trois gigaoctets pendant une demi-heure, alors qu'un utilisateur qui pose
# des questions a tout intérêt à ce que le modèle reste chargé.
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

  local think
  think="$(option_think "$modele")"

  local debut fin
  debut="$(date +%s)"
  local reponse
  if ! reponse="$(curl -fsS "http://$HOTE/api/chat" \
      -H 'Content-Type: application/json' \
      --data-binary @- <<EOF
{"model": "$modele", "stream": false$think, "messages": [{"role": "user", "content": "$question"}]}
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
  local modele="${1:-$(modele_configure)}"
  echo "[ia] Mesure sur « $modele »..."
  echo "[ia] Deux passes : la premiere inclut le chargement du modele."

  # Sans cela, sur un modele qui reflechit, les 120 jetons mesures seraient des
  # jetons de REFLEXION : le debit annonce ne serait pas celui des reponses.
  local think
  think="$(option_think "$modele")"

  local passe reponse
  for passe in 1 2; do
    if ! reponse="$(curl -fsS --max-time 300 -X POST "http://$HOTE/api/chat"         -H 'Content-Type: application/json'         -d "{\"model\": \"$modele\", \"stream\": false$think, \"options\": {\"num_predict\": 120}, \"messages\": [{\"role\": \"user\", \"content\": \"Explique en trois phrases a quoi sert un devis.\"}]}" 2>&1)"; then
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
      #
      # Les trois verdicts tenaient chacun dans UNE chaine awk coupee par de
      # vrais retours a la ligne. C'est une erreur de syntaxe -- « awk:
      # unterminated string » -- et sous « set -e » elle interrompait le
      # script juste avant d'afficher le verdict : la seule ligne que la
      # documentation demande de lire. Un print par ligne, donc.
      awk -v d="$debit" -v petit="$MODELE_PLUS_PETIT" 'BEGIN{
        if (d >= 20) {
          print "[ia] Confortable : les reponses arrivent sans attente notable.";
        } else if (d >= 8) {
          print "[ia] Acceptable avec le flux active : les premiers mots";
          print "[ia] arrivent vite, la fin defile. Rien a changer.";
        } else {
          print "[ia] LENT. Aucun reglage ne compensera ce debit. Essayez un";
          print "[ia] modele plus petit : orion-ai.sh pull " petit;
          print "[ia] puis selectionnez-le dans Parametres IA.";
        }
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
