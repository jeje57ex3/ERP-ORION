"""apps/core/client_ip.py — L'adresse du client, et à qui on la demande.

POURQUOI CE MODULE EXISTE

Six endroits du dépôt extrayaient l'adresse IP du client, chacun à sa
façon, et tous les six prenaient le **premier** élément de
`X-Forwarded-For` :

    apps/core/utils.py          apps/core/audit_service.py
    apps/core/middleware.py     apps/accounts/signals.py
    apps/accounts/views.py      apps/websites/public_views.py

Or cet en-tête est une liste qu'on lit **par la droite**, et le premier
élément est celui que le client a écrit lui-même.

LA TOPOLOGIE RÉELLE, VÉRIFIÉE PLUTÔT QUE SUPPOSÉE

    05-cloudflared-config.tmpl.yml :
        hostname: <domaine de l'ERP>
        service:  http://127.0.0.1:9000     ← gunicorn, directement

    orion-backend.service :
        gunicorn --bind 127.0.0.1:9000

Le tunnel Cloudflare attaque donc **gunicorn directement** : nginx n'est
pas dans le chemin de l'ERP. Il n'y est que pour l'accès LAN, où il
proxifie vers ce même port.

Dans les deux chemins, `REMOTE_ADDR` vaut 127.0.0.1 — c'est le tunnel ou
nginx. La vraie adresse est donc forcément dans un en-tête, et la
question est seulement : **lequel, et écrit par qui.**

    Chemin par Cloudflare
        `X-Forwarded-For` = <ce que le client a envoyé>, <vraie adresse>
        Cloudflare AJOUTE la vraie adresse à droite de ce que le client
        a mis. Le dernier élément est donc écrit par Cloudflare.

    Chemin par nginx (LAN)
        `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`
        nginx AJOUTE l'adresse du pair à droite. Le dernier élément est
        donc écrit par nginx.

**Le dernier élément est écrit par un composant qu'on contrôle, dans les
deux chemins. Le premier est écrit par le client, dans les deux
chemins.** C'est tout le défaut, et toute la correction.

CE QUE ÇA CASSAIT, CONCRÈTEMENT

1. **Les limitations de débit n'en étaient pas.** Le configurateur en
   pose huit, les formulaires publics deux, toutes dans une clef de
   cache qui contient cette adresse. Un client qui envoie
   `X-Forwarded-For: 9.9.9.9` puis `9.9.9.8`, etc., obtient une clef
   neuve à chaque requête : la limite de dix envois par heure devient
   illimitée. Le code était écrit, testé, et sans effet.

2. **Le journal d'audit attribuait les actions à une adresse choisie par
   l'attaquant.** C'est pire qu'une colonne vide : une colonne vide se
   lit comme inconnue, alors que celle-là se lit comme une preuve.

CE QU'ON NE LIT PLUS DU TOUT : `CF-Connecting-IP`

`apps/core/utils.get_client_ip` le lisait **en premier**. Cloudflare le
pose bien, en écrasant toute valeur du client — mais rien, du côté de
Django, ne distingue celui de Cloudflare de celui qu'un client a émis.
Comme `X-Forwarded-For` porte déjà la même information à un endroit
vérifiable, on ne garde que celui-là. Un en-tête de moins à qui se
fier est un en-tête de moins à surveiller.

TOUTE VALEUR EST VALIDÉE AVANT D'ÊTRE RENDUE

Elle part dans une clef de cache et dans une colonne de la base. Un
en-tête qui porterait 4 000 caractères, un chemin, ou une virgule, n'est
pas une adresse : on le jette au lieu de le propager.
"""
import ipaddress

from django.conf import settings

#: Rendue quand aucune source ne donne d'adresse exploitable. On ne rend
#: jamais une chaîne vide : elle se glisserait dans une clef de cache et
#: confondrait en un seul tous les clients sans adresse.
ADRESSE_INCONNUE = '0.0.0.0'

#: Combien de composants de confiance AJOUTENT leur adresse à droite de
#: `X-Forwarded-For`. Un seul dans les deux chemins de cette installation :
#: Cloudflare par le tunnel, nginx par le LAN. On lit donc le dernier
#: élément.
#:
#: À porter à 2 si un jour nginx se place DERRIÈRE le tunnel pour l'ERP
#: — les deux ajouteraient alors, et le dernier élément serait 127.0.0.1.
PROFONDEUR_DE_PROXY_PAR_DEFAUT = 1

#: En-têtes posés par nginx avec `proxy_set_header`, qui REMPLACE la
#: valeur du client. Lus seulement en secours, pour l'accès LAN : par le
#: tunnel ils sont absents, puisque nginx n'est pas dans le chemin.
#:
#: `CF-Connecting-IP` n'y est pas, volontairement : voir l'en-tête du
#: module.
ENTETES_REMPLACES_PAR_NGINX = ('HTTP_X_REAL_IP',)


def _profondeur_de_proxy():
    valeur = getattr(settings, 'ORION_PROFONDEUR_DE_PROXY',
                     PROFONDEUR_DE_PROXY_PAR_DEFAUT)
    try:
        return max(1, int(valeur))
    except (TypeError, ValueError):
        return PROFONDEUR_DE_PROXY_PAR_DEFAUT


def _entetes_de_secours():
    return tuple(getattr(settings, 'ORION_ENTETES_D_IP',
                         ENTETES_REMPLACES_PAR_NGINX))


def adresse_valide(valeur):
    """L'adresse si c'en est une, sinon `None`.

    `ipaddress` accepte IPv4 comme IPv6 et refuse tout le reste. On borne
    d'abord la longueur : une adresse IPv6 pleine tient en 45 caractères,
    et analyser huit kilo-octets d'en-tête à chaque requête est un
    travail offert à qui l'envoie.
    """
    if not valeur:
        return None

    texte = str(valeur).strip()
    if not texte or len(texte) > 64:
        return None

    # Une adresse IPv6 peut arriver entre crochets, parfois avec son port.
    if texte.startswith('[') and ']' in texte:
        texte = texte[1:texte.index(']')]

    try:
        return str(ipaddress.ip_address(texte))
    except ValueError:
        return None


def ip_du_client(request):
    """L'adresse du client, prise de la seule place qu'il n'écrit pas.

    Rend toujours une chaîne : une adresse valide, ou `'0.0.0.0'`.
    """
    meta = getattr(request, 'META', None) or {}

    # `X-Forwarded-For`, LU PAR LA DROITE.
    #
    # Les éléments de gauche viennent du client et valent ce qu'il a
    # voulu. Celui qu'ajoute le composant de confiance — Cloudflare par
    # le tunnel, nginx par le LAN — est le dernier.
    chaine = meta.get('HTTP_X_FORWARDED_FOR')
    if chaine:
        maillons = [m.strip() for m in str(chaine).split(',') if m.strip()]
        if maillons:
            profondeur = min(_profondeur_de_proxy(), len(maillons))
            adresse = adresse_valide(maillons[-profondeur])
            if adresse:
                return adresse

    for entete in _entetes_de_secours():
        adresse = adresse_valide(meta.get(entete))
        if adresse:
            return adresse

    return adresse_valide(meta.get('REMOTE_ADDR')) or ADRESSE_INCONNUE


def cle_de_limitation(request, prefixe):
    """Une clef de cache pour limiter le débit, bornée et sans surprise.

    L'adresse part dans une clef de cache ; `ip_du_client` n'en rend
    qu'une validée, donc le risque d'y glisser un en-tête de huit
    kilo-octets est déjà écarté. On nomme le motif ici pour qu'un futur
    appelant n'ait pas à composer la clef lui-même — et ne réintroduise
    pas une adresse brute en le faisant.
    """
    return f'{prefixe}:{ip_du_client(request)}'
