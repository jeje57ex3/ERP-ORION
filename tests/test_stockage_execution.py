"""Allocation, déplacement et ajout de disques — exécutés, plus seulement guidés.

`storage_service.py` mesurait et rédigeait des commandes ; l'administrateur
les tapait. Ce module-ci exécute. Le changement de nature est important :
du code qui **formate** un disque et **supprime** des fichiers ne se teste
pas comme du code qui affiche un tableau.

Ce fichier verrouille donc trois choses, dans cet ordre d'importance :

**1. Les refus.** La majorité des tests ci-dessous vérifient que quelque
chose n'arrive PAS : qu'un volume inventé dans une requête ne fait pas
écrire dans `/etc`, qu'un chemin en service ne peut pas être supprimé,
qu'une confirmation absente arrête tout. Sur une fonctionnalité
destructrice, les refus sont la fonctionnalité.

**2. Le contrat avec sudo.** Les commandes passées à `sudo` doivent être
exactement celles que le fichier sudoers autorise. S'ils divergent, les
boutons cessent de fonctionner sans que rien ne le signale — c'est
pourquoi `apps/system_updates/server_actions.py` a déjà un test de ce
genre pour `DELAI_MINUTES`, et pourquoi celui-ci existe aussi.

**3. La validation du script root.** Elle est chargée depuis le fichier et
exercée directement. C'est la seule validation qui compte vraiment : le
code Django tourne sous le compte « orion », donc sous le compte même
qu'on cherche à contenir. Un contrôle écrit côté Django protège d'une
erreur d'interface, pas d'un attaquant qui aurait déjà la main sur
l'application.
"""

import importlib.machinery
import importlib.util
import os
import re

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHEMIN_DU_SCRIPT_ROOT = os.path.join(
    RACINE, 'deployment', 'proxmox-appliance', 'scripts', 'orion-stockage')
CHEMIN_DU_SUDOERS = os.path.join(
    RACINE, 'deployment', 'proxmox-appliance', 'sudoers', 'orion-stockage')


def _charger_le_script_root():
    """Charge l'assistant root comme module, pour tester ses refus.

    Le fichier n'a pas d'extension `.py` — c'est un exécutable installé
    dans /usr/local/sbin — donc `spec_from_file_location` ne suffit pas :
    il faut nommer le chargeur de source explicitement.

    Aucune de ses fonctions privilégiées n'est appelée ici ; seules les
    fonctions de validation le sont, et elles ne touchent à rien.
    """
    chargeur = importlib.machinery.SourceFileLoader(
        'orion_stockage_sous_test', CHEMIN_DU_SCRIPT_ROOT)
    specification = importlib.util.spec_from_loader(chargeur.name, chargeur)
    module = importlib.util.module_from_spec(specification)
    chargeur.exec_module(module)
    return module


def _liens_possibles(tmp_path):
    """Vrai si ce système autorise la création de liens symboliques.

    Sous Windows, elle demande des droits particuliers. Les tests qui en
    dépendent sont sautés plutôt que de rendre un échec qui ne dit rien
    sur le code.
    """
    try:
        cible = tmp_path / 'cible-de-test'
        cible.mkdir()
        lien = tmp_path / 'lien-de-test'
        os.symlink(str(cible), str(lien))
        os.remove(str(lien))
        return True
    except (OSError, NotImplementedError, AttributeError):
        return False


# ── 1. Les chemins sont calculés, jamais reçus ─────────────────────────────

def test_le_chemin_cible_est_calcule_et_non_saisi():
    """Aucune chaîne venue du navigateur ne devient un chemin.

    C'est la décision de conception qui dispense de valider une traversée
    de répertoire : il n'y a rien à valider, puisque l'interface ne
    transmet qu'un choix de volume, comparé ensuite à la liste réelle.
    """
    from apps.system_health import stockage_actions

    attendu = os.path.normpath(os.path.join('/mnt/donnees', 'orion', 'medias'))
    assert stockage_actions.chemin_propose('/mnt/donnees', 'medias') == attendu


def test_une_categorie_inconnue_est_refusee():
    from apps.system_health import stockage_actions

    with pytest.raises(stockage_actions.ErreurDeStockage):
        stockage_actions.chemin_propose('/mnt/donnees', 'base_de_donnees')

    with pytest.raises(stockage_actions.ErreurDeStockage):
        stockage_actions.canonique('n-importe-quoi')


def test_les_statiques_ne_sont_pas_deplacables():
    """Décision assumée : collectstatic les réécrit à chaque déploiement."""
    from apps.system_health import stockage_actions

    assert 'statiques' not in stockage_actions.REGLAGE_PAR_CATEGORIE
    assert set(stockage_actions.REGLAGE_PAR_CATEGORIE) == {
        'medias', 'sauvegardes', 'journaux'}


def test_un_volume_inconnu_n_est_pas_autorise(monkeypatch):
    """LE refus qui empêche d'écrire ailleurs que sur un vrai volume.

    On compare à la liste des volumes réellement montés, et non à un motif
    de chemin : un motif aurait fini par accepter un dossier qui n'est pas
    un volume du tout.
    """
    from apps.system_health import stockage_actions

    monkeypatch.setattr(
        'apps.system_health.storage_service.volumes',
        lambda: [{'point_de_montage': '/mnt/donnees', 'libre_go': 100}])

    assert stockage_actions.volume_autorise('/mnt/donnees') is not None
    assert stockage_actions.volume_autorise('/etc') is None
    assert stockage_actions.volume_autorise('/mnt/donnees/../../etc') is None
    assert stockage_actions.volume_autorise('') is None


def test_un_volume_voisin_ne_passe_pas_pour_un_autre(monkeypatch):
    """« /mnt/donnees2 » commence par « /mnt/donnees » — et n'est pas lui.

    Le même piège que `volume_du_chemin` a déjà eu : une comparaison par
    préfixe de chaîne au lieu d'une comparaison de chemins.
    """
    from apps.system_health import stockage_actions

    monkeypatch.setattr(
        'apps.system_health.storage_service.volumes',
        lambda: [{'point_de_montage': '/mnt/donnees2', 'libre_go': 100}])

    assert stockage_actions.volume_autorise('/mnt/donnees') is None
    assert stockage_actions.volume_autorise('/mnt/donnees2') is not None


# ── 2. Mesurer avant d'agir ────────────────────────────────────────────────

def test_l_inventaire_compte_fichiers_et_octets(tmp_path):
    from apps.system_health import stockage_actions

    (tmp_path / 'a.txt').write_bytes(b'x' * 10)
    (tmp_path / 'sous').mkdir()
    (tmp_path / 'sous' / 'b.txt').write_bytes(b'y' * 25)

    nombre, octets = stockage_actions.inventaire(str(tmp_path))
    assert nombre == 2
    assert octets == 35


def test_l_inventaire_d_un_dossier_absent_rend_zero():
    from apps.system_health import stockage_actions

    assert stockage_actions.inventaire('/dossier/qui/n/existe/pas') == (0, 0)


def test_la_copie_est_refusee_si_la_place_manque(monkeypatch, tmp_path):
    """Remplir un volume à 100 % laisse un système incapable d'écrire.

    C'est pire que de n'avoir rien déplacé, et ça se mesure avant de
    commencer — pas au millionième fichier.
    """
    import collections

    from apps.system_health import stockage_actions

    Usage = collections.namedtuple('Usage', 'total used free')
    monkeypatch.setattr('shutil.disk_usage',
                        lambda _chemin: Usage(100, 99, 1024))

    with pytest.raises(stockage_actions.ErreurDeStockage, match='insuffisante'):
        stockage_actions.verifier_la_place(str(tmp_path), 10 * 1024 ** 3)


def test_la_marge_est_exigee_en_plus_des_donnees(monkeypatch, tmp_path):
    """Juste assez de place pour les données ne suffit pas : il faut la marge."""
    import collections

    from apps.system_health import stockage_actions

    Usage = collections.namedtuple('Usage', 'total used free')
    donnees = 5 * 1024 ** 3

    monkeypatch.setattr('shutil.disk_usage',
                        lambda _c: Usage(0, 0, donnees + 1024))
    with pytest.raises(stockage_actions.ErreurDeStockage):
        stockage_actions.verifier_la_place(str(tmp_path), donnees)

    monkeypatch.setattr(
        'shutil.disk_usage',
        lambda _c: Usage(0, 0, donnees + stockage_actions.MARGE_LIBRE_OCTETS + 1))
    assert stockage_actions.verifier_la_place(str(tmp_path), donnees) > 0


# ── 3. Copier, et relire ce qui a été écrit ────────────────────────────────

def test_la_copie_reproduit_l_arbre_et_le_contenu(tmp_path):
    from apps.system_health import stockage_actions

    source = tmp_path / 'source'
    (source / 'sous').mkdir(parents=True)
    (source / 'a.bin').write_bytes(b'AAAA')
    (source / 'sous' / 'b.bin').write_bytes(b'BBBBBB')
    cible = tmp_path / 'cible'

    resultat = stockage_actions.copier_avec_verification(
        str(source), str(cible))

    assert resultat['erreurs'] == []
    assert resultat['fichiers'] == 2
    assert resultat['octets'] == 10
    assert (cible / 'a.bin').read_bytes() == b'AAAA'
    assert (cible / 'sous' / 'b.bin').read_bytes() == b'BBBBBB'


def test_la_copie_rend_l_avancement_au_fil_de_l_eau(tmp_path):
    """La barre de progression ne peut pas être alimentée après coup."""
    from apps.system_health import stockage_actions

    source = tmp_path / 'source'
    source.mkdir()
    for index in range(5):
        (source / f'{index}.bin').write_bytes(b'z' * 100)

    vus = []
    stockage_actions.copier_avec_verification(
        str(source), str(tmp_path / 'cible'),
        rappel=lambda f, o, _r: vus.append((f, o)))

    assert len(vus) == 5
    assert vus[-1] == (5, 500)
    # Strictement croissant : un compteur qui recule rendrait la barre
    # de progression absurde.
    assert [f for f, _ in vus] == sorted(f for f, _ in vus)


def test_la_relecture_attrape_un_octet_faux(tmp_path, monkeypatch):
    """Comparer les tailles ne prouve rien ; la relecture, si.

    L'utilisateur va décider de supprimer l'original sur la foi de cette
    vérification. Un disque qui commence à défaillir rend des tailles
    justes et des octets faux — on simule exactement ce cas.
    """
    from apps.system_health import stockage_actions

    source = tmp_path / 'source'
    source.mkdir()
    (source / 'a.bin').write_bytes(b'bonnes donnees')

    # L'empreinte relue ne correspondra jamais : comme si le disque avait
    # ecrit autre chose que ce qu'on lui a donne.
    monkeypatch.setattr(stockage_actions, '_empreinte',
                        lambda _chemin: 'empreinte-qui-ne-correspond-pas')

    resultat = stockage_actions.copier_avec_verification(
        str(source), str(tmp_path / 'cible'))

    assert resultat['fichiers'] == 0
    assert len(resultat['erreurs']) == 1
    assert 'ne correspondent pas' in resultat['erreurs'][0]


def test_sans_verification_la_copie_ne_relit_pas(tmp_path, monkeypatch):
    """Le drapeau existe ; sans lui, le test précédent ne prouverait rien."""
    from apps.system_health import stockage_actions

    source = tmp_path / 'source'
    source.mkdir()
    (source / 'a.bin').write_bytes(b'donnees')

    monkeypatch.setattr(stockage_actions, '_empreinte',
                        lambda _c: 'jamais-appelee-normalement')

    resultat = stockage_actions.copier_avec_verification(
        str(source), str(tmp_path / 'cible'), verifier=False)

    assert resultat['erreurs'] == []
    assert resultat['fichiers'] == 1


# ── 4. Basculer le lien ────────────────────────────────────────────────────

def test_la_bascule_remplace_un_vrai_dossier_sans_rien_perdre(
        tmp_path, settings, monkeypatch):
    """Premier déplacement : le dossier est écarté, pas supprimé.

    C'est le point le plus délicat de la bascule — remplacer un dossier
    par un lien n'est pas atomique. La fonction rend donc le nom du
    dossier écarté, et rien n'est détruit.
    """
    from apps.system_health import stockage_actions

    if not _liens_possibles(tmp_path):
        pytest.skip('Liens symboliques indisponibles sur ce système.')

    canonique = tmp_path / 'media'
    canonique.mkdir()
    (canonique / 'temoin.txt').write_bytes(b'je dois survivre')
    nouvelle = tmp_path / 'ailleurs' / 'medias'
    nouvelle.mkdir(parents=True)

    settings.MEDIA_ROOT = str(canonique)

    ancien = stockage_actions.basculer('medias', str(nouvelle))

    assert ancien is not None
    assert os.path.islink(str(canonique))
    assert os.path.realpath(str(canonique)) == os.path.realpath(str(nouvelle))
    assert os.path.isfile(os.path.join(ancien, 'temoin.txt'))


def test_la_bascule_d_un_lien_vers_un_autre_ne_laisse_rien(
        tmp_path, settings):
    """Deuxième déplacement : remplacement atomique, aucun dossier écarté."""
    from apps.system_health import stockage_actions

    if not _liens_possibles(tmp_path):
        pytest.skip('Liens symboliques indisponibles sur ce système.')

    premier = tmp_path / 'un'
    second = tmp_path / 'deux'
    premier.mkdir()
    second.mkdir()
    canonique = tmp_path / 'media'
    os.symlink(str(premier), str(canonique))

    settings.MEDIA_ROOT = str(canonique)

    ancien = stockage_actions.basculer('medias', str(second))

    assert ancien is None
    assert os.path.realpath(str(canonique)) == os.path.realpath(str(second))


def test_la_bascule_vers_une_cible_absente_est_refusee(tmp_path, settings):
    from apps.system_health import stockage_actions

    canonique = tmp_path / 'media'
    canonique.mkdir()
    settings.MEDIA_ROOT = str(canonique)

    with pytest.raises(stockage_actions.ErreurDeStockage, match='existe pas'):
        stockage_actions.basculer('medias', str(tmp_path / 'nulle-part'))


def test_un_ancien_dossier_n_ecrase_jamais_le_precedent(tmp_path):
    from apps.system_health import stockage_actions

    base = tmp_path / 'media.ancien'
    base.mkdir()
    libre = stockage_actions._nom_libre(str(base))
    assert libre != str(base)
    assert not os.path.lexists(libre)


# ── 4 bis. L'ordre des opérations de bascule, appels système simulés ──────
#
# Les trois tests ci-dessus sont sautés sous Windows, qui refuse la création
# de liens symboliques sans privilège (WinError 1314). Or `basculer` est la
# fonction la plus délicate du module : laisser ce trou sur un poste de
# développement reviendrait à ne la vérifier qu'en production.
#
# On simule donc les appels système et on mesure leur ORDRE, qui est tout
# l'enjeu : écarter le dossier AVANT de poser le lien, et le remettre si la
# pose échoue. Ce ne sont pas les liens qu'on teste ici, c'est la décision.


def _simuler_le_systeme(monkeypatch, lien_existant, dossier_existant,
                        echouer_sur_replace=False):
    """Remplace les appels de fichiers par un journal d'intentions."""
    journal = []

    monkeypatch.setattr(os.path, 'isdir',
                        lambda c: c.endswith('nouvelle-cible')
                        or (dossier_existant and c.endswith('media')))
    monkeypatch.setattr(os.path, 'islink',
                        lambda c: lien_existant and c.endswith('media'))
    monkeypatch.setattr(os.path, 'lexists', lambda c: False)
    monkeypatch.setattr(os, 'symlink',
                        lambda cible, nom: journal.append(('symlink', nom)))
    monkeypatch.setattr(os, 'rename',
                        lambda a, b: journal.append(('rename', a, b)))

    def replace(a, b):
        journal.append(('replace', a, b))
        if echouer_sur_replace:
            raise OSError('disque en lecture seule')

    monkeypatch.setattr(os, 'replace', replace)
    monkeypatch.setattr(os, 'remove',
                        lambda c: journal.append(('remove', c)))
    return journal


def test_la_bascule_ecarte_le_dossier_avant_de_poser_le_lien(
        monkeypatch, settings, tmp_path):
    """L'ordre qui évite de perdre les données du premier déplacement."""
    from apps.system_health import stockage_actions

    settings.MEDIA_ROOT = str(tmp_path / 'media')
    journal = _simuler_le_systeme(monkeypatch, lien_existant=False,
                                  dossier_existant=True)

    ancien = stockage_actions.basculer('medias',
                                       str(tmp_path / 'nouvelle-cible'))

    etapes = [entree[0] for entree in journal]
    assert etapes == ['symlink', 'rename', 'replace'], (
        'Le lien doit etre prepare, le dossier ecarte, PUIS le lien pose.')
    assert ancien is not None and '.ancien' in ancien


def test_la_bascule_d_un_lien_existant_ne_renomme_rien(
        monkeypatch, settings, tmp_path):
    """Remplacer un lien par un autre est atomique : aucun écart nécessaire."""
    from apps.system_health import stockage_actions

    settings.MEDIA_ROOT = str(tmp_path / 'media')
    journal = _simuler_le_systeme(monkeypatch, lien_existant=True,
                                  dossier_existant=False)

    ancien = stockage_actions.basculer('medias',
                                       str(tmp_path / 'nouvelle-cible'))

    assert [e[0] for e in journal] == ['symlink', 'replace']
    assert ancien is None


def test_la_bascule_remet_le_dossier_si_la_pose_echoue(
        monkeypatch, settings, tmp_path):
    """LE test du retour arrière.

    Si le lien ne peut pas être posé après que le dossier a été écarté,
    l'application se retrouverait sans emplacement du tout — ni dossier,
    ni lien. La fonction doit remettre le dossier en place avant de
    signaler l'échec.
    """
    from apps.system_health import stockage_actions

    settings.MEDIA_ROOT = str(tmp_path / 'media')
    journal = _simuler_le_systeme(monkeypatch, lien_existant=False,
                                  dossier_existant=True,
                                  echouer_sur_replace=True)

    with pytest.raises(stockage_actions.ErreurDeStockage):
        stockage_actions.basculer('medias', str(tmp_path / 'nouvelle-cible'))

    renommages = [e for e in journal if e[0] == 'rename']
    assert len(renommages) == 2, (
        'Le dossier ecarte doit etre remis en place apres un echec.')
    # Le second renommage est l'inverse du premier.
    assert renommages[1][1] == renommages[0][2]
    assert renommages[1][2] == renommages[0][1]


# ── 5. Supprimer : la fonction qui doit refuser le plus ───────────────────

def _preparer_suppression(tmp_path, settings, monkeypatch):
    from apps.system_health import stockage_actions

    canonique = tmp_path / 'media'
    en_service = tmp_path / 'en-service'
    canonique.mkdir()
    en_service.mkdir()
    settings.MEDIA_ROOT = str(canonique)
    monkeypatch.setattr(stockage_actions, 'cible_actuelle',
                        lambda _cat: str(en_service))
    monkeypatch.setattr(
        'apps.system_health.storage_service.volumes',
        lambda: [{'point_de_montage': str(tmp_path), 'libre_go': 10}])
    return canonique, en_service


def test_la_suppression_refuse_l_emplacement_en_service(
        tmp_path, settings, monkeypatch):
    """Le refus le plus important du module.

    Un paramètre mal transmis effacerait les médias en service, et aucune
    sauvegarde n'est garantie à cet instant précis.
    """
    from apps.system_health import stockage_actions

    _canonique, en_service = _preparer_suppression(tmp_path, settings,
                                                   monkeypatch)

    with pytest.raises(stockage_actions.ErreurDeStockage,
                       match='actuellement utilisé'):
        stockage_actions.supprimer_source(str(en_service), 'medias')
    assert en_service.is_dir()


def test_la_suppression_refuse_le_chemin_canonique(
        tmp_path, settings, monkeypatch):
    from apps.system_health import stockage_actions

    canonique, _ = _preparer_suppression(tmp_path, settings, monkeypatch)

    with pytest.raises(stockage_actions.ErreurDeStockage):
        stockage_actions.supprimer_source(str(canonique), 'medias')
    assert canonique.is_dir()


def test_la_suppression_refuse_la_racine(tmp_path, settings, monkeypatch):
    """Le refus doit venir du contrôle de racine, pas d'un garde-fou plus bas.

    La première version comparait le chemin normalisé à `('/', '.')`. Or
    `os.path.normpath('/')` rend `'\\'` sous Windows : le refus tenait sous
    Linux et tombait ailleurs. Le test passait quand même, parce que le
    contrôle de provenance refusait à sa place — jusqu'à ce qu'une
    neutralisation de ce dernier fasse parcourir le disque entier à la
    fonction.

    D'où la vérification du MESSAGE : sans elle, ce test ne dirait pas
    lequel des deux refus a joué, et pourrait de nouveau passer pour la
    mauvaise raison.
    """
    from apps.system_health import stockage_actions

    _preparer_suppression(tmp_path, settings, monkeypatch)

    for chemin in ('/', os.sep, 'C:' + os.sep):
        with pytest.raises(stockage_actions.ErreurDeStockage,
                           match='racine'):
            stockage_actions.supprimer_source(chemin, 'medias')

    for chemin in ('', '.'):
        with pytest.raises(stockage_actions.ErreurDeStockage, match='vide'):
            stockage_actions.supprimer_source(chemin, 'medias')


def test_la_suppression_refuse_un_chemin_trop_proche_de_la_racine(
        tmp_path, settings, monkeypatch):
    """Deux refus indépendants valent mieux qu'un seul bien écrit.

    « /mnt » et « /home » ne doivent jamais atteindre le parcours de
    fichiers, même si le contrôle de provenance venait à être affaibli.
    """
    from apps.system_health import stockage_actions

    _preparer_suppression(tmp_path, settings, monkeypatch)

    for chemin in ('/mnt', '/home', '/var'):
        with pytest.raises(stockage_actions.ErreurDeStockage,
                           match='trop proche'):
            stockage_actions.supprimer_source(chemin, 'medias')


def test_la_suppression_refuse_un_lien(tmp_path, settings, monkeypatch):
    """Supprimer un lien ne libère rien, et peut viser les données en service."""
    from apps.system_health import stockage_actions

    if not _liens_possibles(tmp_path):
        pytest.skip('Liens symboliques indisponibles sur ce système.')

    _canonique, en_service = _preparer_suppression(tmp_path, settings,
                                                   monkeypatch)
    lien = tmp_path / 'un-lien'
    os.symlink(str(en_service), str(lien))

    with pytest.raises(stockage_actions.ErreurDeStockage,
                       match='lien symbolique'):
        stockage_actions.supprimer_source(str(lien), 'medias')
    assert en_service.is_dir()


def test_la_suppression_refuse_un_dossier_quelconque(
        tmp_path, settings, monkeypatch):
    """Ni écarté par une bascule, ni sous « orion/ » : refusé par principe."""
    from apps.system_health import stockage_actions

    _preparer_suppression(tmp_path, settings, monkeypatch)
    etranger = tmp_path / 'documents-personnels'
    etranger.mkdir()
    (etranger / 'important.txt').write_bytes(b'x')

    with pytest.raises(stockage_actions.ErreurDeStockage,
                       match='ne ressemble pas'):
        stockage_actions.supprimer_source(str(etranger), 'medias')
    assert (etranger / 'important.txt').is_file()


def test_la_suppression_accepte_un_dossier_ecarte(
        tmp_path, settings, monkeypatch):
    """Et elle doit bien finir par accepter quelque chose.

    Sans ce test, tous les refus ci-dessus pourraient venir d'une fonction
    qui refuse tout — ce qui ne serait pas une sécurité mais une panne.
    """
    from apps.system_health import stockage_actions

    _preparer_suppression(tmp_path, settings, monkeypatch)
    ecarte = tmp_path / 'media.ancien'
    ecarte.mkdir()
    (ecarte / 'vieux.txt').write_bytes(b'abcde')

    resultat = stockage_actions.supprimer_source(str(ecarte), 'medias')

    assert resultat == {'fichiers': 1, 'octets': 5}
    assert not ecarte.exists()


# ── 6. Le contrat avec sudo ────────────────────────────────────────────────

def test_chaque_commande_est_autorisee_par_sudoers():
    """Le test de divergence : même motif que DELAI_MINUTES.

    Si le module et le fichier sudoers ne disent plus la même chose, les
    boutons échouent avec « orion is not in the sudoers file » — l'écran
    existe, et rien ne se passe.
    """
    from apps.system_health import stockage_privilegie

    with open(CHEMIN_DU_SUDOERS, encoding='utf-8') as fichier:
        contenu = fichier.read()

    for commande in stockage_privilegie.COMMANDES_AUTORISEES:
        attendu = (f'orion ALL=(root) NOPASSWD: '
                   f'{stockage_privilegie.CHEMIN_DU_SCRIPT} {commande}')
        assert attendu in contenu, (
            f'sudoers n autorise pas « {commande} » : la commande echouera.')


def test_sudoers_ne_contient_aucun_joker():
    """Un joker accorde beaucoup plus qu'on ne croit lui accorder.

    C'est la doctrine écrite dans sudoers/orion-serveur, et la raison pour
    laquelle les paramètres de cet assistant voyagent sur l'entrée
    standard plutôt qu'en arguments.
    """
    lignes = [l.strip() for l in open(CHEMIN_DU_SUDOERS, encoding='utf-8')
              if l.strip() and not l.strip().startswith('#')]

    assert lignes, 'Aucune règle lue : le test ne mesurerait rien.'
    for ligne in lignes:
        assert '*' not in ligne, f'Joker dans une règle sudo : {ligne}'
        assert 'ALL=(root) NOPASSWD:' in ligne


def test_aucune_regle_sudo_n_est_orpheline():
    """L'inverse du premier test : sudoers n'autorise rien de plus.

    Une règle laissée en place après le retrait d'une commande resterait
    un droit root accordé sans raison.
    """
    from apps.system_health import stockage_privilegie

    lignes = [l.strip() for l in open(CHEMIN_DU_SUDOERS, encoding='utf-8')
              if l.strip().startswith('orion ')]
    autorisees = {
        l.rsplit(' ', 1)[-1] for l in lignes
        if stockage_privilegie.CHEMIN_DU_SCRIPT in l}

    assert autorisees == set(stockage_privilegie.COMMANDES_AUTORISEES)


def test_la_ligne_de_commande_est_absolue_et_sans_mot_de_passe():
    from apps.system_health import stockage_privilegie

    ligne = stockage_privilegie.ligne_de_commande('lister')
    assert ligne[:2] == ['sudo', '-n']
    assert ligne[2].startswith('/')
    assert ligne[2] == stockage_privilegie.CHEMIN_DU_SCRIPT


def test_une_commande_non_autorisee_est_impossible_a_former():
    from apps.system_health import stockage_privilegie

    with pytest.raises(ValueError):
        stockage_privilegie.ligne_de_commande('rm')


def test_le_provisionnement_installe_le_script_sans_droit_d_ecriture():
    """Si « orion » pouvait réécrire le script, sudo vaudrait root complet.

    Le mode 0750 avec le groupe orion donne l'exécution sans l'écriture.
    C'est l'hypothèse sur laquelle repose toute la sûreté du dispositif.
    """
    chemin = os.path.join(RACINE, 'deployment', 'proxmox-appliance',
                          'provisioning', '02-deploy-orion.sh')
    with open(chemin, encoding='utf-8') as fichier:
        contenu = fichier.read()

    assert '/usr/local/sbin/orion-stockage' in contenu
    assert re.search(r'install\s+-o\s+root\s+-g\s+orion\s+-m\s+0750',
                     contenu), (
        'Le script doit etre installe root:orion en 0750 : executable par '
        'orion, jamais inscriptible.')
    assert 'installer_sudoers orion-stockage' in contenu


def test_la_mise_a_jour_reinstalle_les_aides_privilegiees():
    """Sinon la fonctionnalité n'arrive jamais sur une machine déjà installée.

    Trou constaté : règles sudo et assistant disque n'étaient posés que par
    `provisioning/02-deploy-orion.sh`, c'est-à-dire **une seule fois**, à
    la création de la machine. Sur une VM existante, une mise à jour
    apportait le code et pas les droits : la carte « Ajouter un disque »
    s'affichait et restait inactive — soit exactement la demande non
    satisfaite, puisqu'il aurait fallu les installer au clavier.

    Le même trou valait depuis toujours pour `orion-serveur` et les boutons
    d'extinction.
    """
    chemin = os.path.join(RACINE, 'deployment', 'proxmox-appliance',
                          'scripts', 'update_orion.sh')
    with open(chemin, encoding='utf-8') as fichier:
        contenu = fichier.read()

    assert 'orion-stockage' in contenu, (
        'La mise a jour doit reinstaller l assistant disque.')
    assert '/etc/sudoers.d/' in contenu, (
        'La mise a jour doit reinstaller les regles sudo.')
    assert 'visudo -c' in contenu, (
        'Un fichier sudoers malforme casse sudo pour tout le monde : il '
        'doit etre valide AVANT mise en place.')
    assert re.search(r'install\s+-o\s+root\s+-g\s+orion\s+-m\s+0750',
                     contenu), (
        'L assistant doit rester non inscriptible par le compte orion.')


# ── 7. Les refus du script root, exercés directement ──────────────────────

def test_le_script_root_refuse_une_partition():
    """« preparer /dev/sda1 » doit être refusé : ce n'est pas un disque."""
    script = _charger_le_script_root()

    with pytest.raises(script.Refus, match='Périphérique refusé'):
        script._valider_la_demande({'peripherique': '/dev/sda1',
                                    'etiquette': 'donnees'})


def test_le_script_root_refuse_un_chemin_detourne(monkeypatch):
    """Le MOTIF doit refuser à lui seul, sans l'aide du test d'existence.

    Sans la simulation ci-dessous, ce test passait sous Windows pour la
    mauvaise raison : `/etc/shadow` n'y existe pas, donc c'était le
    contrôle d'existence qui refusait. Sur le serveur Linux visé, ce
    fichier existe — et le motif serait alors le seul rempart. On force
    donc l'existence pour n'éprouver que lui.
    """
    script = _charger_le_script_root()
    monkeypatch.setattr(script.os.path, 'exists', lambda _c: True)

    for mauvais in ('/dev/../etc/passwd', '/etc/shadow', 'sdb',
                    '/dev/sdb; rm -rf /', '/dev/mapper/vg-root',
                    '/dev/sda1', '/dev/sdb1', '', '/dev/',
                    '/dev/sdb\n/dev/sdc'):
        with pytest.raises(script.Refus, match='Périphérique refusé'):
            script._valider_la_demande({'peripherique': mauvais,
                                        'etiquette': 'donnees'})


def test_le_script_root_refuse_une_etiquette_dangereuse():
    """L'étiquette devient un point de montage : elle est donc contrainte."""
    script = _charger_le_script_root()

    for mauvaise in ('../../etc', 'Donnees', 'avec espace', 'a' * 25,
                     '', 'don/nees', 'don;nees'):
        with pytest.raises(script.Refus, match='Étiquette refusée'):
            script._valider_la_demande({'peripherique': '/dev/sdb',
                                        'etiquette': mauvaise})


def test_le_script_root_accepte_les_formes_legitimes(monkeypatch):
    """Sinon les refus ci-dessus pourraient venir d'une fonction qui refuse tout."""
    script = _charger_le_script_root()
    monkeypatch.setattr(script.os.path, 'exists', lambda _c: True)

    for bon in ('/dev/sdb', '/dev/vdc', '/dev/nvme0n1', '/dev/sdaa'):
        peripherique, etiquette = script._valider_la_demande(
            {'peripherique': bon, 'etiquette': 'donnees-2'})
        assert peripherique == bon
        assert etiquette == 'donnees-2'


def test_le_script_root_juge_inutilisable_un_disque_systeme():
    """La racine ne doit jamais apparaître comme un disque disponible."""
    script = _charger_le_script_root()

    disque = {
        'name': '/dev/sda', 'type': 'disk', 'size': 100,
        'children': [
            {'name': '/dev/sda1', 'type': 'part', 'size': 100,
             'fstype': 'ext4', 'mountpoint': '/'},
        ],
    }
    etat = script._evaluer(disque)

    assert etat['utilisable'] is False
    assert any('système' in raison for raison in etat['raisons'])


def test_le_script_root_juge_inutilisable_un_disque_monte():
    script = _charger_le_script_root()

    disque = {
        'name': '/dev/sdb', 'type': 'disk', 'size': 100,
        'children': [
            {'name': '/dev/sdb1', 'type': 'part', 'size': 100,
             'fstype': 'ext4', 'mountpoint': '/mnt/autre'},
        ],
    }
    etat = script._evaluer(disque)

    assert etat['utilisable'] is False
    assert any('montée' in raison for raison in etat['raisons'])


def test_le_script_root_voit_un_disque_vierge_comme_utilisable():
    script = _charger_le_script_root()

    etat = script._evaluer({'name': '/dev/sdc', 'type': 'disk',
                            'size': 500, 'serial': 'ABC123'})

    assert etat['utilisable'] is True
    assert etat['raisons'] == []
    assert etat['contient_des_donnees'] is False
    assert etat['numero_de_serie'] == 'ABC123'


def test_le_script_root_signale_un_disque_qui_contient_des_donnees():
    """Ce drapeau commande l'exigence de confirmation et de numéro de série."""
    script = _charger_le_script_root()

    etat = script._evaluer({
        'name': '/dev/sdc', 'type': 'disk', 'size': 500, 'serial': 'X1',
        'children': [{'name': '/dev/sdc1', 'type': 'part', 'size': 500,
                      'fstype': 'ntfs', 'mountpoint': None}],
    })

    assert etat['utilisable'] is True
    assert etat['contient_des_donnees'] is True
    assert etat['systemes_de_fichiers'] == ['ntfs']


def test_le_point_de_montage_du_script_est_contraint():
    """Démonter ne doit viser que ce que l'assistant a lui-même monté."""
    script = _charger_le_script_root()

    for mauvais in ('/', '/mnt', '/mnt/autre', '/home', '../mnt/orion-x'):
        with pytest.raises(script.Refus):
            script.commande_demonter({'point_de_montage': mauvais})


def test_le_script_root_n_utilise_jamais_de_shell():
    """Aucun `shell=True`, et pas de chaîne passée à un interpréteur.

    Le script reçoit des données venues de l'application web ; un seul
    `shell=True` suffirait à transformer une étiquette en commande.
    """
    with open(CHEMIN_DU_SCRIPT_ROOT, encoding='utf-8') as fichier:
        contenu = fichier.read()

    assert 'shell=True' not in contenu
    assert 'os.system' not in contenu
    assert 'subprocess.call(' not in contenu or 'shell' not in contenu


def test_le_script_root_inscrit_fstab_avec_nofail():
    """Sans « nofail », un disque absent au démarrage bloque la machine.

    Et il faut alors une console physique pour s'en sortir, ce qui est
    exactement ce que cette fonctionnalité promet d'éviter.
    """
    with open(CHEMIN_DU_SCRIPT_ROOT, encoding='utf-8') as fichier:
        contenu = fichier.read()

    assert 'nofail' in contenu
    assert 'UUID=' in contenu, (
        'fstab doit referencer la partition par UUID : un nom /dev/sdX '
        'peut changer d un demarrage a l autre.')


# ── 8. Les vues : refuser avant d'agir ────────────────────────────────────

def _super_admin(client, django_user_model):
    from apps.accounts.models import UserProfile
    from apps.core.models import Company

    entreprise, _ = Company.objects.get_or_create(
        slug='orion-stockage', defaults={'name': 'Orion Stockage'})
    utilisateur = django_user_model.objects.create_user(
        'patron-stockage', password='x', is_superuser=True, is_staff=True)
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.role = 'superadmin'
    profil.save()
    profil.companies.add(entreprise)

    utilisateur = django_user_model.objects.get(pk=utilisateur.pk)
    client.force_login(utilisateur)
    session = client.session
    session['current_company_id'] = entreprise.pk
    session.save()
    return utilisateur


@pytest.mark.django_db
def test_la_page_des_disques_affiche_les_nouvelles_cartes(client,
                                                          django_user_model):
    from django.urls import reverse

    _super_admin(client, django_user_model)
    reponse = client.get(reverse('system_health:disk_dashboard'))

    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert 'Ajouter un disque' in contenu
    assert 'Copier puis basculer' in contenu


@pytest.mark.django_db
def test_le_deplacement_refuse_un_volume_forge(client, django_user_model):
    """Le refus qui empêche une requête forgée d'écrire sur le disque système."""
    from django.urls import reverse

    from apps.system_health.models import OperationDeStockage

    _super_admin(client, django_user_model)
    reponse = client.post(reverse('system_health:stockage_deplacer'), {
        'categorie': 'medias', 'volume': '/etc', 'mode': 'basculer'})

    assert reponse.status_code == 302
    assert not OperationDeStockage.objects.exists()


@pytest.mark.django_db
def test_le_deplacement_refuse_un_mode_inconnu(client, django_user_model):
    from django.urls import reverse

    from apps.system_health.models import OperationDeStockage

    _super_admin(client, django_user_model)
    client.post(reverse('system_health:stockage_deplacer'), {
        'categorie': 'medias', 'volume': '/', 'mode': 'tout_supprimer'})

    assert not OperationDeStockage.objects.exists()


@pytest.mark.django_db
def test_le_deplacement_refuse_une_categorie_non_deplacable(
        client, django_user_model):
    from django.urls import reverse

    from apps.system_health.models import OperationDeStockage

    _super_admin(client, django_user_model)
    client.post(reverse('system_health:stockage_deplacer'), {
        'categorie': 'statiques', 'volume': '/', 'mode': 'basculer'})

    assert not OperationDeStockage.objects.exists()


@pytest.mark.django_db
def test_la_preparation_refuse_une_confirmation_incorrecte(
        client, django_user_model):
    """Formater efface tout : recopier le nom du disque est obligatoire."""
    from django.urls import reverse

    from apps.system_health.models import OperationDeStockage

    _super_admin(client, django_user_model)
    client.post(reverse('system_health:stockage_preparer_disque'), {
        'peripherique': '/dev/sdb', 'etiquette': 'donnees',
        'confirmation': '/dev/sdc'})

    assert not OperationDeStockage.objects.exists()


@pytest.mark.django_db
def test_la_liberation_refuse_une_operation_non_verifiee(client,
                                                         django_user_model):
    """Avant la vérification, l'ancien emplacement est peut-être l'unique copie."""
    from django.urls import reverse

    from apps.system_health.models import OperationDeStockage

    _super_admin(client, django_user_model)
    operation = OperationDeStockage.objects.create(
        type_operation='copier_basculer', categorie='medias',
        etat='en_cours', chemin_source='/mnt/x/orion/medias.ancien')

    client.post(reverse('system_health:stockage_liberer_la_source',
                        args=[operation.pk]), {'confirmation': 'SUPPRIMER'})

    operation.refresh_from_db()
    assert operation.etat == 'en_cours'


@pytest.mark.django_db
def test_la_liberation_refuse_sans_le_mot_de_confirmation(client,
                                                          django_user_model):
    from django.urls import reverse

    from apps.system_health.models import OperationDeStockage

    _super_admin(client, django_user_model)
    operation = OperationDeStockage.objects.create(
        type_operation='copier_basculer', categorie='medias',
        etat='verifiee', chemin_source='/mnt/x/orion/medias.ancien')

    client.post(reverse('system_health:stockage_liberer_la_source',
                        args=[operation.pk]), {'confirmation': 'oui'})

    operation.refresh_from_db()
    assert operation.etat == 'verifiee'


@pytest.mark.django_db
def test_une_seule_operation_a_la_fois(client, django_user_model,
                                       monkeypatch):
    """Deux copies concurrentes rempliraient le disque sans qu'aucune n'aboutisse."""
    from django.urls import reverse

    from apps.system_health.models import OperationDeStockage

    _super_admin(client, django_user_model)
    monkeypatch.setattr(
        'apps.system_health.storage_service.volumes',
        lambda: [{'point_de_montage': '/mnt/donnees', 'libre_go': 100}])

    OperationDeStockage.objects.create(
        type_operation='copier_basculer', categorie='medias', etat='en_cours')

    client.post(reverse('system_health:stockage_deplacer'), {
        'categorie': 'sauvegardes', 'volume': '/mnt/donnees',
        'mode': 'basculer'})

    assert OperationDeStockage.objects.count() == 1


@pytest.mark.django_db
def test_les_actions_refusent_la_methode_get(client, django_user_model):
    """Un GET est rejouable par un simple rafraîchissement de page."""
    from django.urls import reverse

    _super_admin(client, django_user_model)

    for nom in ('system_health:stockage_deplacer',
                'system_health:stockage_preparer_disque'):
        assert client.get(reverse(nom)).status_code == 405


@pytest.mark.django_db
def test_un_utilisateur_ordinaire_ne_peut_rien_declencher(client,
                                                          django_user_model):
    from django.urls import reverse

    from apps.accounts.models import UserProfile
    from apps.core.models import Company
    from apps.system_health.models import OperationDeStockage

    entreprise, _ = Company.objects.get_or_create(
        slug='ordinaire-stockage', defaults={'name': 'Ordinaire'})
    utilisateur = django_user_model.objects.create_user('simple', password='x')
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.companies.add(entreprise)
    client.force_login(django_user_model.objects.get(pk=utilisateur.pk))

    reponse = client.post(reverse('system_health:stockage_deplacer'), {
        'categorie': 'medias', 'volume': '/', 'mode': 'basculer'})

    assert reponse.status_code in (302, 403)
    assert not OperationDeStockage.objects.exists()


class _ConnexionSimulee:
    """Un courtier joignable, sans courtier.

    Les tests ne peuvent pas joindre Redis, et ne doivent pas essayer :
    c'est exactement la tentative qui a bloqué la suite pendant plus de
    quatre minutes avant que la mise en file ne soit bornée.
    """

    def __init__(self):
        self.appels = []

    def __enter__(self):
        return self

    def __exit__(self, *_erreur):
        return False

    def ensure_connection(self, **parametres):
        self.appels.append(parametres)
        return self


def _simuler_le_courtier(monkeypatch, connexion=None):
    from erp_btp.celery import app

    connexion = connexion or _ConnexionSimulee()
    monkeypatch.setattr(app, 'connection_for_write',
                        lambda *_a, **_k: connexion)
    return connexion


@pytest.mark.django_db
def test_un_deplacement_valide_cree_l_operation(client, django_user_model,
                                                monkeypatch):
    """Le chemin qui aboutit.

    Sans ce test, tous les refus ci-dessus pourraient venir d'une vue qui
    refuse tout — ce qui ne serait pas une sécurité mais une panne.
    """
    from django.urls import reverse

    from apps.system_health import tasks
    from apps.system_health.models import OperationDeStockage

    _super_admin(client, django_user_model)
    monkeypatch.setattr(
        'apps.system_health.storage_service.volumes',
        lambda: [{'point_de_montage': '/mnt/donnees', 'libre_go': 500}])
    _simuler_le_courtier(monkeypatch)
    envoyees = []
    monkeypatch.setattr(tasks.basculer_une_categorie, 'apply_async',
                        lambda *a, **k: envoyees.append((a, k)))

    client.post(reverse('system_health:stockage_deplacer'), {
        'categorie': 'medias', 'volume': '/mnt/donnees', 'mode': 'basculer'})

    operation = OperationDeStockage.objects.get()
    assert operation.type_operation == 'basculer'
    assert operation.categorie == 'medias'
    assert operation.volume_cible == '/mnt/donnees'
    assert operation.chemin_cible.replace('\\', '/').endswith('orion/medias')
    assert operation.etat == 'en_attente'
    assert len(envoyees) == 1


@pytest.mark.django_db
def test_la_mise_en_file_est_bornee(client, django_user_model, monkeypatch):
    """LE test du défaut mesuré à 64 secondes.

    Un `.delay()` lancé alors que Redis est arrêté met 64 s à rendre la
    main. Le délai ne vient pas de la connexion mais des réessais
    d'acquisition (`broker_connection_max_retries`, défaut 100), que
    `retry=False` ne gouverne pas, et que les délais de socket des settings
    ne bornent pas non plus.

    Ce test échoue donc si quelqu'un retire `max_retries=0` : la page
    recommencerait à se figer une minute entière sans rien dire.
    """
    from django.urls import reverse

    from apps.system_health import tasks, views

    _super_admin(client, django_user_model)
    monkeypatch.setattr(
        'apps.system_health.storage_service.volumes',
        lambda: [{'point_de_montage': '/mnt/donnees', 'libre_go': 500}])
    connexion = _simuler_le_courtier(monkeypatch)
    recus = {}
    monkeypatch.setattr(tasks.basculer_une_categorie, 'apply_async',
                        lambda *a, **k: recus.update(k))

    client.post(reverse('system_health:stockage_deplacer'), {
        'categorie': 'medias', 'volume': '/mnt/donnees', 'mode': 'basculer'})

    assert connexion.appels, (
        'La connexion doit etre acquise explicitement, sinon la tentative '
        'n est pas bornee.')
    assert connexion.appels[0]['max_retries'] == 0
    assert 0 < connexion.appels[0]['timeout'] <= 10
    assert recus.get('retry') is False


@pytest.mark.django_db
def test_un_courtier_injoignable_ne_laisse_pas_l_operation_en_attente(
        client, django_user_model, monkeypatch):
    """Une opération « en attente » que rien ne fera avancer est pire qu'un échec.

    Elle se présente comme un travail en route, et bloque en plus le
    verrou « une seule opération à la fois ».
    """
    from django.urls import reverse

    from apps.system_health.models import OperationDeStockage

    _super_admin(client, django_user_model)
    monkeypatch.setattr(
        'apps.system_health.storage_service.volumes',
        lambda: [{'point_de_montage': '/mnt/donnees', 'libre_go': 500}])

    class CourtierAbsent(_ConnexionSimulee):
        def ensure_connection(self, **_parametres):
            raise OSError('Connection refused')

    _simuler_le_courtier(monkeypatch, CourtierAbsent())

    reponse = client.post(reverse('system_health:stockage_deplacer'), {
        'categorie': 'medias', 'volume': '/mnt/donnees', 'mode': 'basculer'})

    assert reponse.status_code == 302
    operation = OperationDeStockage.objects.get()
    assert operation.etat == 'echouee'
    assert 'injoignable' in operation.message
    assert operation.fini_le is not None
    assert 'Redis' in operation.journal


# ── 9. Les tâches : jamais d'opération bloquée ────────────────────────────

@pytest.mark.django_db
def test_une_exception_marque_l_operation_en_echec():
    """Aucune tâche ne doit laisser une opération éternellement « en cours ».

    Un état d'attente que rien ne fait avancer est pire qu'un échec :
    l'interface le présente comme un travail en route, et le verrou
    « une seule opération à la fois » bloque alors tout le reste.
    """
    from apps.system_health.models import OperationDeStockage
    from apps.system_health.tasks import _executer_l_operation

    operation = OperationDeStockage.objects.create(
        type_operation='basculer', categorie='medias')

    def travail(_operation):
        raise RuntimeError('disque arraché')

    resultat = _executer_l_operation(operation.pk, travail)

    operation.refresh_from_db()
    assert resultat['ok'] is False
    assert operation.etat == 'echouee'
    assert 'disque arraché' in operation.message
    assert operation.fini_le is not None


@pytest.mark.django_db
def test_un_message_relivre_ne_refait_pas_le_travail():
    """Celery peut relivrer un message ; refaire une bascule serait destructeur."""
    from apps.system_health.models import OperationDeStockage
    from apps.system_health.tasks import _executer_l_operation

    operation = OperationDeStockage.objects.create(
        type_operation='basculer', categorie='medias', etat='terminee')

    appels = []
    resultat = _executer_l_operation(operation.pk,
                                     lambda _op: appels.append(1))

    assert appels == []
    assert resultat['ok'] is False


@pytest.mark.django_db
def test_une_operation_introuvable_ne_fait_pas_planter_la_tache():
    from apps.system_health.tasks import _executer_l_operation

    resultat = _executer_l_operation(999999, lambda _op: None)
    assert resultat['ok'] is False


@pytest.mark.django_db
def test_la_progression_est_mesuree_en_octets():
    """En fichiers, la barre afficherait 90 % dès la première vignette."""
    from apps.system_health.models import OperationDeStockage

    operation = OperationDeStockage(
        type_operation='copier_basculer', categorie='medias',
        fichiers_total=10, fichiers_traites=9,
        octets_total=1000, octets_traites=100)

    assert operation.progression == 10


@pytest.mark.django_db
def test_le_journal_est_borne():
    """Un échec sur 200 000 fichiers ne doit pas rendre la page illisible."""
    from apps.system_health.models import OperationDeStockage

    operation = OperationDeStockage.objects.create(
        type_operation='copier_basculer', categorie='medias')
    for index in range(3000):
        operation.ajouter_au_journal(f'fichier {index} en erreur ' + 'x' * 40)

    assert len(operation.journal) < 61000
    assert 'début tronqué' in operation.journal
