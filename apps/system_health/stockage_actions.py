"""Déplacer une catégorie de fichiers vers un autre disque, sans terminal.

`storage_service.py` mesure et rédige des commandes que l'administrateur
exécute lui-même. Ce module-ci les **exécute**.

**Le pivot de la conception : un lien symbolique.** `settings.MEDIA_ROOT` est
lu directement par une vingtaine d'endroits — `apps/backups/services.py`,
`apps/core/media_access.py`, `apps/high_availability/media_sync.py`,
`apps/dashboard/version_pc.py`… Rendre ce réglage dynamique obligerait à
modifier chacun d'eux, et `Path(settings.MEDIA_ROOT)` échouerait sur un
objet paresseux, qui n'est ni `str` ni `os.PathLike`.

Si au contraire le chemin configuré reste **fixe** et devient un lien
symbolique vers le vrai emplacement, déplacer les données revient à copier
puis **repointer le lien**. Le noyau fait le reste : tous les
consommateurs continuent de fonctionner sans être touchés, nginx compris
— il `proxy_pass` vers gunicorn, qui ouvre le chemin canonique — et sans
redémarrage. C'est d'ailleurs déjà ce que fait l'appliance, dont
`backend/media` est un lien vers `$ORION_HOME/uploads`.

**Où est la vérité.** Sur le disque, et nulle part ailleurs : la cible du
lien. Aucun champ en base ne la double. Un disque remonté ailleurs à la
main, une restauration, et une table l'affirmerait encore quand le noyau
ne la suit plus. Ce projet a déjà payé ce genre de doublon deux fois
(`apps/core/menu.py` contre `NAV_MODULES`, le champ `two_factor_enabled`).

**Aucun chemin libre.** L'interface ne demande jamais un chemin à taper :
elle propose les volumes détectés, et le dossier cible est *calculé*
(`<point de montage>/orion/<catégorie>`). Il n'y a donc pas de chaîne à
valider contre une traversée de répertoire, parce qu'il n'y a pas de
chaîne venue du navigateur.

**Les limites, dites franchement.** Les journaux déjà ouverts par gunicorn
et Celery continuent d'écrire dans l'ancien fichier jusqu'au prochain
redémarrage : un descripteur de fichier suit l'inode, pas le chemin. Le
déplacement des journaux ne prend donc tout son effet qu'après relance des
services. Pour les médias et les sauvegardes, l'effet est immédiat, chaque
ouverture repassant par le chemin canonique.
"""

import hashlib
import os
import shutil

from django.conf import settings

# Les catégories déplaçables, et le réglage qui porte leur chemin canonique.
# « statiques » n'y est pas : collectstatic le réécrit à chaque déploiement
# et sa taille est stable, le déplacer n'apporte rien.
REGLAGE_PAR_CATEGORIE = {
    'medias': 'MEDIA_ROOT',
    'sauvegardes': 'BACKUP_DIR',
    'journaux': 'LOG_DIR',
}

# Le sous-dossier sous lequel l'ERP range ses données sur un volume.
# Jamais la racine du volume : un « rm -rf » de l'ancien emplacement
# viserait alors le point de montage lui-même, et un volume peut porter
# autre chose que l'ERP.
DOSSIER_SUR_LE_VOLUME = 'orion'

# Taille des blocs de lecture pendant la copie.
TAILLE_DE_BLOC = 1024 * 1024

# Marge exigée sur le volume cible, en plus de la taille des données.
# Copier jusqu'au dernier octet libre laisse un volume inutilisable.
MARGE_LIBRE_OCTETS = 2 * 1024 ** 3


class ErreurDeStockage(Exception):
    """Refus explicite, porteur d'un message destiné à l'utilisateur."""


# ── Lire l'état réel ────────────────────────────────────────────────────────

def canonique(categorie):
    """Le chemin fixe que l'application utilise pour cette catégorie."""
    reglage = REGLAGE_PAR_CATEGORIE.get(categorie)
    if not reglage:
        raise ErreurDeStockage(
            f'Catégorie inconnue ou non déplaçable : « {categorie} ».')
    valeur = getattr(settings, reglage, None)
    if not valeur:
        raise ErreurDeStockage(
            f'Le réglage {reglage} n\'est pas défini : impossible de savoir '
            f'où se trouvent ces fichiers.')
    return os.path.normpath(str(valeur))


def cible_actuelle(categorie):
    """Où les fichiers sont réellement, lien résolu."""
    chemin = canonique(categorie)
    try:
        return os.path.realpath(chemin)
    except OSError:
        return chemin


def est_deja_un_lien(categorie):
    """Vrai si le chemin canonique est déjà un lien symbolique.

    Détermine si une bascule sera atomique (remplacement d'un lien par un
    autre) ou devra d'abord écarter un vrai dossier.
    """
    return os.path.islink(canonique(categorie))


def chemin_propose(point_de_montage, categorie):
    """Le dossier cible sur un volume donné. Calculé, jamais saisi."""
    if categorie not in REGLAGE_PAR_CATEGORIE:
        raise ErreurDeStockage(f'Catégorie inconnue : « {categorie} ».')
    return os.path.normpath(os.path.join(
        point_de_montage, DOSSIER_SUR_LE_VOLUME, categorie))


def volume_autorise(point_de_montage):
    """Le point de montage doit être un volume réellement détecté.

    L'interface ne propose que cette liste ; cette fonction garantit qu'une
    requête forgée ne peut pas faire écrire ailleurs — dans `/etc`, par
    exemple. On compare à la liste que la page des disques affiche, et non
    à un motif de chemin : un motif aurait fini par autoriser un dossier
    qui n'est pas un volume.
    """
    from .storage_service import volumes

    attendu = os.path.normpath(str(point_de_montage or ''))
    for volume in volumes():
        if os.path.normpath(volume['point_de_montage']) == attendu:
            return volume
    return None


# ── Inventorier avant d'agir ────────────────────────────────────────────────

def inventaire(chemin):
    """Nombre de fichiers et total d'octets sous un dossier.

    Ne suit pas les liens symboliques : un lien qui remonterait vers un
    parent ferait tourner le parcours indéfiniment, et compterait des
    octets qui ne sont pas là.
    """
    nombre, octets = 0, 0
    if not os.path.isdir(chemin):
        return nombre, octets
    for dossier, _sous, fichiers in os.walk(chemin, followlinks=False):
        for nom in fichiers:
            try:
                taille = os.lstat(os.path.join(dossier, nom)).st_size
            except OSError:
                continue
            nombre += 1
            octets += taille
    return nombre, octets


def verifier_la_place(point_de_montage, octets_necessaires):
    """Refuse la copie si le volume cible ne peut pas l'accueillir.

    Mesuré avant de commencer, et avec une marge : une copie qui remplit
    un volume à 100 % laisse un système incapable d'écrire, et c'est pire
    que de n'avoir rien déplacé.
    """
    try:
        statistiques = shutil.disk_usage(point_de_montage)
    except OSError as exc:
        raise ErreurDeStockage(
            f'Impossible de lire l\'espace libre de {point_de_montage} : '
            f'{exc}')

    requis = octets_necessaires + MARGE_LIBRE_OCTETS
    if statistiques.free < requis:
        raise ErreurDeStockage(
            f'Place insuffisante sur {point_de_montage} : '
            f'{statistiques.free / 1e9:.1f} Go libres, il en faut '
            f'{requis / 1e9:.1f} Go (données + 2 Go de marge).')
    return statistiques.free


# ── Copier, et vérifier ce qui a été écrit ─────────────────────────────────

def _empreinte_et_copie(source, destination):
    """Copie un fichier en calculant l'empreinte de ce qui est lu.

    L'empreinte est calculée pendant la lecture, et non par une seconde
    passe : relire la source doublerait les entrées-sorties sans rien
    apprendre de plus sur ce qui a été écrit.
    """
    empreinte = hashlib.sha256()
    with open(source, 'rb') as entree, open(destination, 'wb') as sortie:
        while True:
            bloc = entree.read(TAILLE_DE_BLOC)
            if not bloc:
                break
            empreinte.update(bloc)
            sortie.write(bloc)
        sortie.flush()
        os.fsync(sortie.fileno())
    return empreinte.hexdigest()


def _empreinte(chemin):
    empreinte = hashlib.sha256()
    with open(chemin, 'rb') as fichier:
        while True:
            bloc = fichier.read(TAILLE_DE_BLOC)
            if not bloc:
                break
            empreinte.update(bloc)
    return empreinte.hexdigest()


def copier_avec_verification(source, destination, rappel=None,
                             verifier=True):
    """Copie un arbre et relit chaque fichier écrit pour le contrôler.

    `rappel(fichiers_faits, octets_faits, chemin_relatif)` est appelé au fil
    de l'eau : c'est ce qui alimente la barre de progression.

    Pourquoi relire : l'utilisateur va ensuite décider de supprimer
    l'original. Comparer les tailles ne prouve pas que les octets écrits
    sont les bons — un disque qui commence à défaillir rend des tailles
    justes et des octets faux. La relecture passe le plus souvent par le
    cache du noyau, donc son coût réel est bien moindre que son coût
    théorique.

    Les liens symboliques sont recréés tels quels, et non suivis : les
    suivre dupliquerait des données et pourrait sortir de l'arbre.
    """
    fichiers_faits, octets_faits = 0, 0
    erreurs = []

    for dossier, sous_dossiers, fichiers in os.walk(source,
                                                    followlinks=False):
        relatif = os.path.relpath(dossier, source)
        cible_dossier = (destination if relatif == '.'
                         else os.path.join(destination, relatif))
        os.makedirs(cible_dossier, exist_ok=True)

        # Ne pas descendre dans un lien vers un dossier : on le recree.
        liens_de_dossier = [n for n in sous_dossiers
                            if os.path.islink(os.path.join(dossier, n))]
        for nom in liens_de_dossier:
            sous_dossiers.remove(nom)
            _recreer_le_lien(os.path.join(dossier, nom),
                             os.path.join(cible_dossier, nom), erreurs)

        for nom in fichiers:
            chemin_source = os.path.join(dossier, nom)
            chemin_cible = os.path.join(cible_dossier, nom)

            if os.path.islink(chemin_source):
                _recreer_le_lien(chemin_source, chemin_cible, erreurs)
                continue

            try:
                empreinte_lue = _empreinte_et_copie(chemin_source,
                                                    chemin_cible)
                shutil.copystat(chemin_source, chemin_cible)
                if verifier:
                    if _empreinte(chemin_cible) != empreinte_lue:
                        erreurs.append(
                            f'{os.path.join(relatif, nom)} : les octets '
                            f'écrits ne correspondent pas à ceux lus.')
                        continue
                taille = os.lstat(chemin_cible).st_size
            except OSError as exc:
                erreurs.append(f'{os.path.join(relatif, nom)} : {exc}')
                continue

            fichiers_faits += 1
            octets_faits += taille
            if rappel is not None:
                rappel(fichiers_faits, octets_faits,
                       os.path.join(relatif, nom))

    return {
        'fichiers': fichiers_faits,
        'octets': octets_faits,
        'erreurs': erreurs,
    }


def _recreer_le_lien(source, destination, erreurs):
    try:
        vise = os.readlink(source)
        if os.path.lexists(destination):
            os.remove(destination)
        os.symlink(vise, destination)
    except OSError as exc:
        erreurs.append(f'{destination} : lien non recréé ({exc})')


# ── Basculer le chemin canonique ───────────────────────────────────────────

def basculer(categorie, nouvelle_cible):
    """Fait pointer le chemin canonique vers un nouvel emplacement.

    Trois cas, et un seul est vraiment atomique :

    - le chemin est déjà un lien : `os.replace` d'un lien par un autre est
      atomique, aucune requête ne peut tomber dans un trou ;
    - c'est un vrai dossier (premier déplacement) : il est d'abord écarté
      par un `rename`, lui aussi atomique, puis le lien est posé. Entre les
      deux, le chemin n'existe pas pendant une fraction de milliseconde.
      C'est le seul instant non couvert, et c'est pourquoi cette fonction
      rend le nom du dossier écarté : rien n'est supprimé, tout est
      récupérable ;
    - il n'y a rien : le lien est simplement posé.

    Renvoie le chemin de l'ancien dossier écarté, ou None.
    """
    if not os.path.isdir(nouvelle_cible):
        raise ErreurDeStockage(
            f'La cible {nouvelle_cible} n\'existe pas : rien n\'a été '
            f'basculé.')

    lien = canonique(categorie)
    provisoire = lien + '.nouveau'

    try:
        if os.path.lexists(provisoire):
            os.remove(provisoire)
        os.symlink(nouvelle_cible, provisoire)
    except OSError as exc:
        raise ErreurDeStockage(
            f'Impossible de préparer le lien {provisoire} : {exc}')

    ancien_dossier = None
    try:
        if os.path.islink(lien):
            os.replace(provisoire, lien)
        elif os.path.isdir(lien):
            ancien_dossier = _nom_libre(lien + '.ancien')
            os.rename(lien, ancien_dossier)
            os.replace(provisoire, lien)
        else:
            os.replace(provisoire, lien)
    except OSError as exc:
        # Remettre le dossier en place si le lien n'a pas pu etre pose :
        # sinon l'application se retrouverait sans emplacement du tout.
        if ancien_dossier and not os.path.lexists(lien):
            try:
                os.rename(ancien_dossier, lien)
            except OSError:
                pass
        if os.path.lexists(provisoire):
            try:
                os.remove(provisoire)
            except OSError:
                pass
        raise ErreurDeStockage(
            f'Impossible de basculer {lien} : {exc}')

    return ancien_dossier


def _nom_libre(base):
    """Un nom qui n'est pas déjà pris, pour ne jamais écraser un écarté."""
    if not os.path.lexists(base):
        return base
    for numero in range(2, 100):
        candidat = f'{base}-{numero}'
        if not os.path.lexists(candidat):
            return candidat
    raise ErreurDeStockage(
        f'Trop d\'anciens emplacements conservés à côté de {base} : '
        f'supprimez-en avant de recommencer.')


# ── Supprimer l'ancien emplacement, et seulement sur demande ───────────────

def supprimer_source(chemin, categorie):
    """Supprime un ancien emplacement, après plusieurs refus de principe.

    Cette fonction détruit des données. Elle refuse donc tout ce qui n'est
    pas, sans ambiguïté, un ancien emplacement écarté par `basculer` :

    - le chemin doit exister et être un vrai dossier, pas un lien ;
    - il ne doit pas être l'emplacement actuellement utilisé, ni le chemin
      canonique lui-même ;
    - il doit porter le suffixe « .ancien » que `basculer` pose, ou se
      trouver sous un volume, dans le sous-dossier de l'ERP.

    Sans ces refus, un paramètre mal transmis effacerait les médias en
    service, et aucune sauvegarde n'est garantie à cet instant.
    """
    chemin = os.path.normpath(str(chemin or ''))
    if not chemin or chemin == '.':
        raise ErreurDeStockage('Chemin vide : refusé.')

    # Une racine de systeme de fichiers, quelle que soit la plateforme :
    # son parent est elle-meme. Vrai pour « / », « C:\ » et « \\serveur\part ».
    #
    # Comparer a ('/', '.') ne suffisait PAS, et ce defaut etait de ma main :
    # os.path.normpath('/') rend '\\' sous Windows, qui n'etait dans aucune
    # des deux valeurs. Le refus tenait sous Linux et tombait ailleurs -- et
    # le test ne l'a pas vu, parce qu'un garde-fou situe plus bas refusait a
    # sa place. Il ne s'est montre qu'en neutralisant ce garde-fou : la
    # fonction s'est mise a parcourir le disque entier.
    if os.path.dirname(chemin) == chemin:
        raise ErreurDeStockage(
            f'{chemin} est une racine de système de fichiers. Refusé.')

    # Profondeur minimale. Redondant avec le controle de provenance plus
    # bas, et c'est voulu : sur une fonction qui detruit des donnees, deux
    # refus independants valent mieux qu'un seul bien ecrit. « /mnt » ou
    # « /home » ne doivent jamais arriver jusqu'au parcours.
    morceaux = [m for m in chemin.replace('\\', '/').split('/') if m
                and not m.endswith(':')]
    if len(morceaux) < 2:
        raise ErreurDeStockage(
            f'{chemin} est trop proche de la racine pour être un '
            f'emplacement de l\'ERP. Refusé.')

    if os.path.islink(chemin):
        raise ErreurDeStockage(
            f'{chemin} est un lien symbolique. Supprimer un lien ne '
            f'libère aucune place, et pointe peut-être sur les données en '
            f'service.')

    if not os.path.isdir(chemin):
        raise ErreurDeStockage(f'{chemin} n\'est pas un dossier.')

    en_service = cible_actuelle(categorie)
    if os.path.normpath(chemin) == os.path.normpath(en_service):
        raise ErreurDeStockage(
            f'{chemin} est l\'emplacement actuellement utilisé pour '
            f'« {categorie} ». Refusé.')

    if os.path.normpath(chemin) == canonique(categorie):
        raise ErreurDeStockage(
            f'{chemin} est le chemin canonique de l\'application. Refusé.')

    nom = os.path.basename(chemin)
    sous_un_volume = volume_autorise(_point_de_montage_parent(chemin))
    marque_ancien = '.ancien' in nom
    dans_le_dossier_orion = f'{os.sep}{DOSSIER_SUR_LE_VOLUME}{os.sep}' in (
        chemin + os.sep)

    if not marque_ancien and not (sous_un_volume and dans_le_dossier_orion):
        raise ErreurDeStockage(
            f'{chemin} ne ressemble pas à un ancien emplacement de l\'ERP. '
            f'Par précaution, seuls les dossiers écartés par un '
            f'déplacement, ou situés sous « {DOSSIER_SUR_LE_VOLUME}/ » sur '
            f'un volume, peuvent être supprimés ici.')

    nombre, octets = inventaire(chemin)
    shutil.rmtree(chemin)
    return {'fichiers': nombre, 'octets': octets}


def _point_de_montage_parent(chemin):
    """Le point de montage qui porte ce chemin, par remontée des parents."""
    from .storage_service import volume_du_chemin

    volume = volume_du_chemin(chemin)
    return volume['point_de_montage'] if volume else ''
