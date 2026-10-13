"""Raccordement d'un serveur au cluster Orion, et diagnostic de la liaison.

Raccorder un serveur demandait jusqu'ici de lancer `manage.py ha_seed`, qui
crée trois nœuds figés depuis des variables d'environnement, puis d'éditer
chacun à la main — sans aucun moyen d'ajouter un quatrième serveur, ni de
vérifier que la liaison fonctionne avant de s'y fier.

Le diagnostic ci-dessous existe parce que six causes très différentes
produisent le même symptôme — « le serveur ne répond pas » — et que les
distinguer à l'œil coûte des heures : nom de domaine qui ne résout pas,
service arrêté, domaine absent d'ALLOWED_HOSTS (400), secret partagé
différent (403), connecteur Cloudflare absent (530), ou proxy debout devant
une application tombée (502).

Il relève aussi le `node_id` **depuis le serveur lui-même**. C'est essentiel :
`HAActiveNodeWriteProtectionMiddleware` compare `settings.ORION_NODE_ID` au
verrou de cluster. Un identifiant saisi à la main qui diffère de celui du
serveur distant donne un nœud qui refuse toutes les écritures sans que rien
n'explique pourquoi.
"""

import socket
from urllib.parse import urlsplit

import requests
from django.conf import settings

from apps.high_availability.models import OrionHANode

DELAI_SECONDES = 6


def normaliser_base_url(brut):
    """Retourne (origine, hôte). Le chemin est volontairement écarté.

    L'adresse d'un nœud est une ORIGINE, pas une page : elle sert de préfixe à
    « /ha/health/ ». Coller l'URL d'une page de l'ERP — réflexe naturel de qui
    copie sa barre d'adresse — produisait sinon une sonde absurde du genre
    « …/orion-admin/ha/nodes/2/ha/public-health/ », un 404, et un message
    accusant le serveur distant d'être antérieur au module de haute
    disponibilité au lieu de désigner la saisie. Constaté en production.

    Un déploiement sous sous-chemin n'existe pas : les URL de l'ERP sont
    montées à la racine. Écarter le chemin est donc toujours correct, et
    `chemin_ignore()` permet de le signaler plutôt que de le faire en silence.
    """
    valeur = (brut or '').strip()
    if not valeur:
        return '', ''
    if '://' not in valeur:
        valeur = f'https://{valeur}'
    decoupe = urlsplit(valeur)
    hote = (decoupe.hostname or '').strip('.').lower()
    if not hote:
        return '', ''
    return f'{decoupe.scheme}://{decoupe.netloc}', hote


def chemin_ignore(brut):
    """Partie de l'adresse saisie qui a été écartée, vide s'il n'y en a pas."""
    valeur = (brut or '').strip()
    if not valeur:
        return ''
    if '://' not in valeur:
        valeur = f'https://{valeur}'
    decoupe = urlsplit(valeur)
    reste = decoupe.path.rstrip('/')
    if decoupe.query:
        reste = f'{reste}?{decoupe.query}'
    return reste


def _etape(nom, ok, detail, remede=''):
    return {'name': nom, 'ok': ok, 'detail': detail, 'remedy': remede}


def _diagnostic_reseau(exc, hote):
    """Traduit une exception requests en cause probable et en remède.

    Sans cette traduction, l'interface affichait la représentation brute de
    l'exception — illisible, et identique pour des causes qui n'ont rien à
    voir entre elles.
    """
    if isinstance(exc, requests.exceptions.SSLError):
        return (
            'Certificat TLS refusé.',
            f'Le certificat de {hote} est invalide ou expiré. En interne, '
            'utilisez http:// plutôt que https://.',
        )
    if isinstance(exc, requests.exceptions.ConnectTimeout):
        return (
            f'Aucune réponse de {hote} dans le délai imparti.',
            'Un pare-feu filtre probablement la connexion : rien ne répond, '
            'et rien ne refuse non plus.',
        )
    if isinstance(exc, requests.exceptions.ReadTimeout):
        return (
            'Connexion établie, mais le serveur ne répond pas.',
            "L'application est probablement bloquée ou saturée. Vérifiez "
            'orion-backend sur ce serveur.',
        )
    if isinstance(exc, requests.exceptions.ConnectionError):
        return (
            f'Connexion refusée par {hote}.',
            'Le nom résout bien, mais rien n\'écoute sur ce port : Nginx ou '
            'orion-backend est arrêté sur ce serveur.',
        )
    return (f'Échec réseau : {exc}', '')


def _interpreter_code(code, url):
    """Cause probable d'un code HTTP inattendu sur un point de santé."""
    if code == 400:
        return (
            "Le serveur rejette son propre nom de domaine (400).",
            'Son domaine manque à ALLOWED_HOSTS. Renseignez ORION_NODE_DOMAIN '
            'dans son .env et redémarrez orion-backend.',
        )
    if code in (401, 403):
        return (
            'Accès refusé au point de santé public (403).',
            'Une protection en amont (Cloudflare Access, règle WAF) bloque '
            'la requête avant Orion.',
        )
    if code == 404:
        return (
            "Le serveur répond, mais n'expose pas le point de santé Orion.",
            f"Soit {url} ne pointe pas vers un Orion ERP, soit sa version est "
            'antérieure au module de haute disponibilité : mettez-le à jour.',
        )
    if code in (502, 503, 504):
        return (
            f'Le proxy répond, pas l\'application ({code}).',
            'Nginx est debout mais orion-backend est arrêté ou en échec sur '
            'ce serveur.',
        )
    if code == 530:
        return (
            'Cloudflare ne trouve aucun connecteur (530).',
            'Le tunnel de ce serveur est arrêté : démarrez cloudflared.',
        )
    return (f'Réponse inattendue : HTTP {code}.', '')


def diagnose_node_connection(base_url, node=None):
    """Éprouve la liaison avec un serveur Orion, étape par étape.

    Retourne un dictionnaire avec `steps` (la liste des contrôles), `payload`
    (le bilan de santé distant si obtenu), `node_id` (relevé sur le serveur)
    et `ok` (tous les contrôles bloquants sont passés).

    `node` sert à exclure le nœud courant du contrôle d'unicité : sans lui,
    tester un serveur déjà enregistré signalerait son propre identifiant
    comme déjà pris.
    """
    etapes = []
    payload = None
    node_id = ''
    identite_ok = False

    url, hote = normaliser_base_url(base_url)
    if not hote:
        etapes.append(_etape(
            'Adresse du serveur', False,
            'Adresse vide ou illisible.',
            'Indiquez le sous-domaine du serveur, par exemple '
            'serveur2.exemple.fr.',
        ))
        return {'steps': etapes, 'payload': None, 'node_id': '', 'ok': False,
                'identity_ok': False, 'url': url}

    # Signalé, pas corrigé en silence : l'exploitant doit savoir que le champ
    # attend une origine, sinon il recollera la même URL de page la fois
    # suivante.
    ecarte = chemin_ignore(base_url)
    if ecarte:
        etapes.append(_etape(
            'Adresse du serveur', True,
            f'{url} (hôte : {hote})',
            f'Le chemin « {ecarte} » a été ignoré : ce champ attend l\'adresse '
            "d'un serveur, pas celle d'une page. Corrigez-le pour éviter toute "
            'ambiguïté.',
        ))
    else:
        etapes.append(_etape('Adresse du serveur', True, f'{url} (hôte : {hote})'))

    # ── Résolution du nom ────────────────────────────────────────────────────
    try:
        socket.getaddrinfo(hote, None)
        etapes.append(_etape('Résolution DNS', True, f'{hote} résout correctement.'))
    except socket.gaierror as exc:
        etapes.append(_etape(
            'Résolution DNS', False,
            f'{hote} ne résout pas ({exc.strerror or exc}).',
            "Vérifiez l'orthographe du nom, ou créez l'enregistrement DNS "
            'correspondant.',
        ))
        return {'steps': etapes, 'payload': None, 'node_id': '', 'ok': False,
                'identity_ok': False, 'url': url}

    # ── Point de santé public : prouve qu'un Orion répond ───────────────────
    try:
        reponse = requests.get(f'{url}/ha/public-health/', timeout=DELAI_SECONDES)
    except requests.RequestException as exc:
        detail, remede = _diagnostic_reseau(exc, hote)
        etapes.append(_etape('Joignabilité', False, detail, remede))
        return {'steps': etapes, 'payload': None, 'node_id': '', 'ok': False,
                'identity_ok': False, 'url': url}

    if reponse.status_code != 200:
        detail, remede = _interpreter_code(reponse.status_code, url)
        etapes.append(_etape('Joignabilité', False, detail, remede))
        return {'steps': etapes, 'payload': None, 'node_id': '', 'ok': False,
                'identity_ok': False, 'url': url}

    try:
        public = reponse.json()
    except ValueError:
        etapes.append(_etape(
            'Joignabilité', False,
            'Le serveur répond, mais pas en JSON.',
            f'{url} sert probablement autre chose qu\'un Orion ERP — une page '
            'de maintenance ou un portail captif, par exemple.',
        ))
        return {'steps': etapes, 'payload': None, 'node_id': '', 'ok': False,
                'identity_ok': False, 'url': url}

    node_id = (public.get('node_id') or '').strip()
    etapes.append(_etape(
        'Joignabilité', True,
        f"Orion répond — identifiant « {node_id or 'inconnu'} », rôle déclaré "
        f"« {public.get('role', '?')} ».",
    ))

    # ── Secret partagé ───────────────────────────────────────────────────────
    secret_local = getattr(settings, 'ORION_HA_SECRET', '')
    if not secret_local or secret_local == 'CHANGE_ME':
        etapes.append(_etape(
            'Secret partagé', False,
            "Ce serveur-ci n'a pas de secret de haute disponibilité.",
            'Renseignez ORION_HA_SECRET dans son .env, avec la MÊME valeur sur '
            'tous les serveurs, puis redémarrez orion-backend.',
        ))
    else:
        try:
            prive = requests.get(
                f'{url}/ha/health/',
                headers={'X-Orion-HA-Secret': secret_local},
                timeout=DELAI_SECONDES,
            )
        except requests.RequestException as exc:
            detail, remede = _diagnostic_reseau(exc, hote)
            etapes.append(_etape('Secret partagé', False, detail, remede))
            prive = None

        if prive is not None:
            if prive.status_code == 200:
                try:
                    payload = prive.json()
                except ValueError:
                    payload = None
                etapes.append(_etape(
                    'Secret partagé', True,
                    'Les deux serveurs partagent le même secret.',
                ))
            elif prive.status_code == 403:
                etapes.append(_etape(
                    'Secret partagé', False,
                    'Le serveur distant refuse notre secret (403).',
                    'ORION_HA_SECRET diffère entre les deux serveurs, ou vaut '
                    'encore CHANGE_ME sur le distant. Posez la même valeur des '
                    'deux côtés et redémarrez orion-backend.',
                ))
            else:
                detail, remede = _interpreter_code(prive.status_code, url)
                etapes.append(_etape('Secret partagé', False, detail, remede))

    # ── Identité : unicité de l'identifiant relevé ──────────────────────────
    if not node_id:
        etapes.append(_etape(
            'Identité du serveur', False,
            "Le serveur ne communique pas d'identifiant.",
            'Renseignez ORION_NODE_ID dans son .env puis redémarrez '
            'orion-backend.',
        ))
    else:
        doublon = OrionHANode.objects.filter(node_id=node_id)
        if node is not None and node.pk:
            doublon = doublon.exclude(pk=node.pk)
        existant = doublon.first()
        if existant:
            etapes.append(_etape(
                'Identité du serveur', False,
                f"L'identifiant « {node_id} » est déjà pris par "
                f'« {existant.name} ».',
                'Deux serveurs ne peuvent pas partager un identifiant : la '
                'protection en écriture ne saurait plus lequel a la main. '
                'Donnez à ce serveur un ORION_NODE_ID distinct.',
            ))
        else:
            identite_ok = True
            etapes.append(_etape(
                'Identité du serveur', True,
                f'Identifiant « {node_id} », relevé sur le serveur lui-même.',
            ))

    # ── État de la base, informatif mais décisif pour la bascule ────────────
    if payload:
        lecture_seule = payload.get('read_only')
        retard = payload.get('replication_lag_seconds')
        role_bdd = payload.get('database_role', 'inconnu')

        if payload.get('database') != 'ok':
            etapes.append(_etape(
                'Base de données', False,
                'Le serveur ne joint pas sa propre base.',
                'Vérifiez MySQL sur ce serveur : il ne pourra jamais prendre '
                'la main dans cet état.',
            ))
        elif lecture_seule is False:
            etapes.append(_etape(
                'Base de données', False,
                f'Base inscriptible (rôle « {role_bdd} »).',
                'Un serveur secondaire doit être en lecture seule. Deux bases '
                'inscriptibles finissent par diverger et ne se fusionnent '
                'pas. Passez-la en réplica avant de la raccorder.',
            ))
        else:
            detail = f'Base joignable, rôle « {role_bdd} »'
            detail += f', retard de réplication {retard} s.' if retard is not None else ', retard inconnu.'
            etapes.append(_etape('Base de données', True, detail))

    return {
        'steps': etapes,
        'payload': payload,
        'node_id': node_id,
        'ok': all(e['ok'] for e in etapes),
        'identity_ok': identite_ok,
        'url': url,
    }


def prochain_rang_libre():
    """Rang de préséance suivant, pour pré-remplir le formulaire."""
    dernier = OrionHANode.objects.order_by('-priority').first()
    return (dernier.priority + 1) if dernier else 1
