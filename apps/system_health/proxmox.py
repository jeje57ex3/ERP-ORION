"""apps/system_health/proxmox.py — Interroger l'hyperviseur, sans l'écrire.

CE QUE CE MODULE RÉPARE

L'écran des disques voit ce que le système d'exploitation voit, et rien de
ce que l'hyperviseur sait. Deux questions restaient donc sans réponse :

  * « ai-je bien branché un disque sur la VM ? » Un disque correctement
    ajouté mais que le noyau n'a pas vu — ajout à chaud non transmis —
    ressemble exactement à un disque jamais ajouté. C'est l'origine de
    « le disque n'est toujours pas ajouté sur la VM » ;
  * « quelle taille puis-je allouer ? » La place libre est sur les pools de
    stockage de l'hôte, invisibles depuis l'intérieur.

LECTURE SEULE, PAR CONSTRUCTION

Ce client n'expose QUE des GET. Il n'y a pas de méthode d'écriture à
désactiver : il n'en existe aucune, et `_appeler` refuse tout verbe autre
que GET. Le jeton stocké dans l'ERP ne peut donc rien modifier sur
l'hyperviseur depuis ici, même s'il en a le droit côté Proxmox.

Ce n'est pas une étape provisoire, c'est le cœur du compromis. Un jeton
d'hyperviseur logé dans la machine virtuelle qu'il gouverne renverse la
confiance : la machine la moins privilégiée se met à commander celle qui
l'héberge. Tant que le client ne sait que lire, le pire d'une compromission
de l'ERP est la divulgation d'un inventaire, pas la destruction d'un disque
ou l'arrêt d'une autre VM.

LE SECRET NE DOIT JAMAIS APPARAÎTRE

Il voyage dans un en-tête, jamais dans une URL — une adresse se retrouve
dans les journaux d'accès, les traces et les messages d'erreur. Et
`_motif_lisible` retire le secret de tout texte rendu à l'interface, par
précaution : une bibliothèque tierce peut très bien recopier un en-tête
dans son exception.
"""
import logging

import requests
from django.utils import timezone

journal = logging.getLogger('system_health')

# Les préfixes de clés de configuration Proxmox qui désignent un volume.
#
# `unused` en fait partie : un volume détaché reste rattaché à la machine et
# occupe de la place, donc il doit se voir.
#
# `efidisk` et `tpmstate` aussi, et c'était un oubli : ils ne commençaient par
# aucun préfixe de cette liste, donc ils n'étaient jamais collectés -- ce qui
# rendait CLES_SYSTEME ci-dessous entièrement MORT. Un test l'a révélé. Or ces
# volumes occupent de la place réelle sur le pool de stockage : les cacher
# ferait mentir l'inventaire sur l'endroit où est passé l'espace.
PREFIXES_DE_DISQUE = ('scsi', 'virtio', 'sata', 'ide', 'unused',
                      'efidisk', 'tpmstate')

# Ceux qui ne sont pas des disques de DONNÉES. Ils sont rendus, mais marqués :
# le micrologiciel et le module de plateforme sécurisée ne se présentent pas
# au système invité comme des périphériques bloc ordinaires, donc les compter
# dans la comparaison inventerait un écart qui n'existe pas.
#
# Test par préfixe et non par nom exact : « efidisk1 » est improbable, mais un
# nom non reconnu serait compté comme un disque de données, c'est-à-dire la
# mauvaise erreur.
PREFIXES_SYSTEME = ('efidisk', 'tpmstate')


class ProxmoxIndisponible(Exception):
    """L'hôte n'a pas répondu, ou les réglages sont incomplets."""


class ProxmoxRefuse(Exception):
    """L'hôte a répondu, et il refuse — jeton, droits, nœud inconnu."""


def _motif_lisible(exc, secret):
    """Le texte d'une exception, débarrassé du secret."""
    motif = f'{type(exc).__name__}: {exc}'
    if secret:
        motif = motif.replace(secret, '«secret retiré»')
    return motif


class ClientProxmox:
    """Un client en lecture seule pour l'API Proxmox."""

    def __init__(self, reglages):
        self.reglages = reglages

    # ── L'appel, et la seule méthode HTTP autorisée ─────────────────────────

    def _appeler(self, chemin, methode='GET'):
        if methode != 'GET':
            # Garde-fou explicite plutôt qu'implicite : si quelqu'un ajoute
            # un jour une écriture, il tombera ici et devra justifier le
            # changement de compromis décrit en tête de ce module.
            raise ProxmoxRefuse(
                'Ce client est en lecture seule. Écrire sur l’hyperviseur '
                'depuis l’ERP est un choix qui se décide, pas un paramètre.')

        reglages = self.reglages
        if not reglages.utilisable:
            raise ProxmoxIndisponible(
                'Réglages Proxmox incomplets : adresse, nœud, identifiant de '
                'jeton et secret sont nécessaires.')
        if reglages.secret_illisible:
            raise ProxmoxIndisponible(
                'Le secret du jeton est illisible : la clé de chiffrement de '
                'cette installation a changé depuis son enregistrement. '
                'Saisissez-le à nouveau.')

        secret = reglages.jeton_secret
        url = reglages.base_url + chemin
        entetes = {
            'Authorization': f'PVEAPIToken={reglages.jeton_id}={secret}',
            'Accept': 'application/json',
        }

        try:
            reponse = requests.get(
                url, headers=entetes,
                verify=bool(reglages.verifier_le_certificat),
                timeout=reglages.delai_secondes or 10,
            )
        except requests.exceptions.SSLError as exc:
            raise ProxmoxIndisponible(
                'Certificat TLS refusé. Proxmox s’installe avec un '
                'certificat auto-signé : décochez « Vérifier le certificat » '
                'si vous joignez l’hôte sur un réseau que vous maîtrisez. '
                f'Détail : {_motif_lisible(exc, secret)}') from None
        except requests.exceptions.RequestException as exc:
            raise ProxmoxIndisponible(
                f'L’hôte {reglages.hote}:{reglages.port} ne répond pas. '
                f'Détail : {_motif_lisible(exc, secret)}') from None

        if reponse.status_code in (401, 403):
            raise ProxmoxRefuse(
                f'Proxmox refuse le jeton (HTTP {reponse.status_code}). '
                f'Vérifiez l’identifiant « {reglages.jeton_id} », son secret, '
                f'et que le jeton a bien un droit de lecture sur ce nœud.')
        if reponse.status_code == 404:
            raise ProxmoxRefuse(
                f'Adresse inconnue de l’hôte : {chemin}. Le nom du nœud '
                f'(« {reglages.noeud} »), le numéro de machine '
                f'({reglages.vmid}) ou son type sont probablement faux.')
        if reponse.status_code >= 400:
            raise ProxmoxRefuse(
                f'Proxmox a répondu HTTP {reponse.status_code} sur {chemin}.')

        try:
            charge = reponse.json()
        except ValueError:
            raise ProxmoxIndisponible(
                'Réponse illisible de l’hôte : ce n’est pas du JSON. '
                'L’adresse pointe peut-être ailleurs que sur l’API '
                'Proxmox.') from None

        return (charge or {}).get('data')

    # ── Les lectures ────────────────────────────────────────────────────────

    def version(self):
        """La version de l'hôte. Le plus petit appel qui prouve que tout va."""
        return self._appeler('/version') or {}

    def config_de_la_machine(self, type_de_machine=None):
        """La configuration de la machine : c'est là que sont les disques."""
        type_reel = type_de_machine or self.reglages.type_de_machine
        chemin = (f'/nodes/{self.reglages.noeud}/{type_reel}/'
                  f'{self.reglages.vmid}/config')
        return self._appeler(chemin) or {}

    def stockages_du_noeud(self):
        """Les pools de stockage de l'hôte, avec leur place libre."""
        chemin = f'/nodes/{self.reglages.noeud}/storage'
        return self._appeler(chemin) or []

    # ── Mise en forme ───────────────────────────────────────────────────────

    def disques_declares(self, config=None):
        """Les disques que Proxmox dit rattachés à cette machine.

        Rend une liste de dicts : clé, volume, taille, détaché, système.
        La taille n'est pas toujours présente dans la configuration (un
        disque LXC ou un passage de périphérique n'en portent pas) : on rend
        alors None plutôt que zéro, parce que « inconnue » et « vide » ne
        sont pas la même chose.
        """
        if config is None:
            config = self.config_de_la_machine()

        disques = []
        for cle, valeur in sorted((config or {}).items()):
            if not cle.startswith(PREFIXES_DE_DISQUE):
                continue
            texte = str(valeur)
            # Un support optique monté sur une clé « ide2 » n'est pas un
            # disque : « cdrom » ou « none » dans les options le disent.
            if 'media=cdrom' in texte or texte.startswith('none'):
                continue

            disques.append({
                'cle': cle,
                'volume': texte.split(',')[0],
                'taille_octets': _taille_en_octets(texte),
                'detache': cle.startswith('unused'),
                'systeme': cle.startswith(PREFIXES_SYSTEME),
                'brut': texte,
            })
        return disques

    def stockages_utilisables(self):
        """Les pools où un disque de VM peut être créé, avec la place libre.

        On ne garde que ceux dont le contenu accepte des images de disque :
        proposer un pool de sauvegardes pour y créer un disque mènerait à
        une erreur que l'exploitant ne pourrait pas interpréter.
        """
        utilisables = []
        for pool in self.stockages_du_noeud() or []:
            if not isinstance(pool, dict):
                continue
            contenu = str(pool.get('content') or '')
            if 'images' not in contenu and 'rootdir' not in contenu:
                continue
            if not pool.get('enabled', 1):
                continue
            utilisables.append({
                'nom': pool.get('storage'),
                'type': pool.get('type'),
                'total_octets': pool.get('total'),
                'libre_octets': pool.get('avail'),
                'contenu': contenu,
            })
        return sorted(utilisables,
                      key=lambda p: -(p['libre_octets'] or 0))


def _taille_en_octets(valeur):
    """Extrait « size=500G » d'une ligne de configuration Proxmox.

    Proxmox écrit la taille avec un suffixe K, M, G ou T, parfois sans
    suffixe (octets). Rend None quand la clé est absente : une taille
    inconnue ne doit pas s'afficher comme zéro.
    """
    import re

    trouve = re.search(r'(?:^|,)size=(\d+(?:\.\d+)?)([KMGT]?)', str(valeur))
    if not trouve:
        return None
    nombre = float(trouve.group(1))
    facteurs = {'': 1, 'K': 1024, 'M': 1024 ** 2,
                'G': 1024 ** 3, 'T': 1024 ** 4}
    return int(nombre * facteurs[trouve.group(2)])


# ── Les deux fonctions que l'interface appelle ───────────────────────────────

def noter_le_resultat(reglages, reussi, message=''):
    """Garde le dernier diagnostic là où la page le montrera."""
    from .models import ReglagesProxmox

    try:
        ReglagesProxmox.objects.filter(pk=reglages.pk).update(
            dernier_appel_le=timezone.now(),
            dernier_appel_reussi=bool(reussi),
            derniere_erreur=(message or '')[:2000],
        )
    except Exception:
        pass


def tester(reglages):
    """Essaie de joindre l'hôte et de lire la machine. Rend (ok, message).

    ESSAIE LES DEUX TYPES DE MACHINE. Un conteneur et une VM n'ont pas la
    même adresse d'API, et se tromper rend un 404 qui ressemble à « nœud
    inconnu ». Si le type configuré échoue en 404 et que l'autre répond, on
    le dit — et on corrige le réglage, puisqu'on vient d'en avoir la preuve.
    """
    if not reglages.hote:
        return False, 'Renseignez l’adresse de l’hôte Proxmox.'
    if not reglages.noeud:
        return False, 'Renseignez le nom du nœud.'
    if not reglages.jeton_id or not reglages.secret_enregistre:
        return False, 'Renseignez l’identifiant du jeton et son secret.'
    if reglages.secret_illisible:
        return False, ('Le secret du jeton est illisible : la clé de '
                       'chiffrement de cette installation a changé depuis '
                       'son enregistrement. Saisissez-le à nouveau.')

    client = ClientProxmox(reglages)

    try:
        version = client.version()
    except (ProxmoxIndisponible, ProxmoxRefuse) as exc:
        noter_le_resultat(reglages, False, str(exc))
        return False, str(exc)

    autres = [t for t, _ in reglages.TYPE_CHOICES
              if t != reglages.type_de_machine]
    essais = [reglages.type_de_machine] + autres
    config, type_retenu, dernier_motif = None, None, ''

    for type_essaye in essais:
        try:
            config = client.config_de_la_machine(type_essaye)
            type_retenu = type_essaye
            break
        except ProxmoxRefuse as exc:
            dernier_motif = str(exc)
            continue
        except ProxmoxIndisponible as exc:
            noter_le_resultat(reglages, False, str(exc))
            return False, str(exc)

    if config is None:
        noter_le_resultat(reglages, False, dernier_motif)
        return False, dernier_motif

    corrige = ''
    if type_retenu != reglages.type_de_machine:
        reglages.type_de_machine = type_retenu
        reglages.save(update_fields=['type_de_machine'])
        corrige = (f' Le type a été corrigé en « {type_retenu} » : c’est '
                   f'celui qui répond.')

    disques = client.disques_declares(config)
    noter_le_resultat(reglages, True, '')
    return True, (
        f'Hôte joint (Proxmox {version.get("version", "?")}). '
        f'La machine {reglages.vmid} s’appelle '
        f'« {config.get("name") or config.get("hostname") or "?"} » et '
        f'déclare {len(disques)} disque(s).{corrige}'
    )


CLE_DE_CACHE = 'system_health:inventaire_proxmox'
DUREE_DU_CACHE = 60
"""Une minute.

L'écran des disques appellerait l'hyperviseur à CHAQUE affichage, et une
page qui attend dix secondes parce que l'hôte ne répond pas est une page
cassée. Une minute suffit : l'inventaire matériel d'une machine ne change
pas plus vite que cela, et le bouton de test, lui, appelle toujours en
direct.

Ce cache ne sert vraiment que depuis que CACHES pointe sur Redis : avec un
cache par processus, chacun des trois workers gunicorn interrogeait l'hôte
pour son compte.
"""


def inventaire(reglages=None, use_cache=True):
    """Ce que l'écran des disques affiche. Ne lève jamais.

    Rend toujours un dict : la page doit rester consultable quand
    l'hyperviseur ne répond pas, et dire pourquoi plutôt que planter.
    """
    from django.core.cache import cache

    from .models import ReglagesProxmox

    if reglages is None:
        reglages = ReglagesProxmox.courants()

    vide = {'configure': False, 'joignable': False, 'erreur': '',
            'disques': [], 'stockages': [], 'nom_de_la_machine': ''}

    if reglages is None or not reglages.actif:
        return vide
    if not reglages.utilisable:
        return dict(vide, configure=True, erreur=(
            'Réglages Proxmox incomplets : adresse, nœud, identifiant de '
            'jeton et secret sont nécessaires.'))

    if use_cache:
        try:
            en_cache = cache.get(CLE_DE_CACHE)
        except Exception:
            en_cache = None
        if en_cache is not None:
            return en_cache

    client = ClientProxmox(reglages)
    try:
        config = client.config_de_la_machine()
        disques = client.disques_declares(config)
        stockages = client.stockages_utilisables()
    except (ProxmoxIndisponible, ProxmoxRefuse) as exc:
        journal.warning('Interrogation Proxmox en echec : %s', exc)
        noter_le_resultat(reglages, False, str(exc))
        # Un échec est mis en cache AUSSI, et c'est voulu : sans cela, un
        # hôte injoignable ferait attendre dix secondes à chaque
        # rafraîchissement de la page. Une minute de « ne répond pas » vaut
        # mieux qu'une page qui rame.
        resultat = dict(vide, configure=True, erreur=str(exc))
        _mettre_en_cache(resultat)
        return resultat

    noter_le_resultat(reglages, True, '')
    resultat = {
        'configure': True,
        'joignable': True,
        'erreur': '',
        'disques': disques,
        'stockages': stockages,
        'nom_de_la_machine': config.get('name') or config.get('hostname') or '',
        'vmid': reglages.vmid,
        'noeud': reglages.noeud,
    }
    _mettre_en_cache(resultat)
    return resultat


def _mettre_en_cache(resultat):
    from django.core.cache import cache
    try:
        cache.set(CLE_DE_CACHE, resultat, DUREE_DU_CACHE)
    except Exception:
        pass


def oublier_l_inventaire():
    """Vide le cache. Appelé après un enregistrement des réglages.

    Sans cela, corriger une adresse fausse laisserait l'ancienne erreur
    affichée pendant une minute, et l'exploitant conclurait que sa
    correction n'a rien changé.
    """
    from django.core.cache import cache
    try:
        cache.delete(CLE_DE_CACHE)
    except Exception:
        pass


def comparer_avec_le_systeme(inventaire_proxmox, disques_vus):
    """Le cœur du diagnostic : l'hôte en déclare combien, le système en voit
    combien ?

    C'est cette comparaison qui distingue les deux situations que l'écran
    confondait :

      * Proxmox n'en déclare qu'un → aucun disque n'a été ajouté. L'action
        est sur l'hyperviseur ;
      * Proxmox en déclare deux, le système en voit un → le disque EST
        ajouté, mais l'ajout à chaud n'a pas été transmis au noyau. Un
        redémarrage de la VM suffit, et c'est une action tout autre.

    `disques_vus` est la liste rendue par stockage_privilegie.lister_les_
    disques(). Quand l'assistant n'est pas installé, on ne sait pas ce que
    le système voit : on rend alors « inconnu » plutôt que de conclure.
    """
    if not inventaire_proxmox.get('joignable'):
        return {'comparable': False, 'motif': 'hyperviseur non interrogé'}

    declares = [d for d in inventaire_proxmox.get('disques', [])
                if not d['systeme'] and not d['detache']]

    if disques_vus is None:
        return {
            'comparable': False,
            'motif': 'le système invité n’a pas pu être inventorié',
            'nombre_declare': len(declares),
        }

    nombre_declare = len(declares)
    nombre_vu = len(disques_vus)

    if nombre_vu < nombre_declare:
        return {
            'comparable': True,
            'coherent': False,
            'nombre_declare': nombre_declare,
            'nombre_vu': nombre_vu,
            'diagnostic': (
                f'Proxmox déclare {nombre_declare} disque(s) sur cette '
                f'machine, le système n’en voit que {nombre_vu}. Le disque '
                f'est bien ajouté : c’est l’ajout à chaud qui n’a pas été '
                f'transmis au noyau. Un redémarrage de la VM le fera '
                f'apparaître.'),
        }

    return {
        'comparable': True,
        'coherent': True,
        'nombre_declare': nombre_declare,
        'nombre_vu': nombre_vu,
        'diagnostic': (
            f'Proxmox déclare {nombre_declare} disque(s), le système en voit '
            f'{nombre_vu} : les deux concordent.'),
    }
