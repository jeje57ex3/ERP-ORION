"""Mise à disposition de l'application PC depuis « Mon dashboard ».

L'installeur pèse environ 180 Mo : il n'est pas versionné et ne voyage pas
avec le code. Il est déposé sur le serveur, et la page le propose — ou dit
clairement qu'il n'y est pas, plutôt qu'offrir un lien mort.

**La propriété qui compte est la traversée de répertoire.** Le nom du fichier
passe dans l'adresse, et le processus tourne en tant qu'utilisateur ayant
accès à la base et aux sauvegardes. Un nom joint au chemin du répertoire —
même « validé » — rouvrirait la porte ; ici le nom reçu est COMPARÉ aux
fichiers réellement présents, ce qui rend la question sans objet.
"""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='PC SA', slug='pc-sa')


@pytest.fixture
def connecte(client, django_user_model, entreprise):
    client.force_login(django_user_model.objects.create_user(
        username='employe', password='motdepasse-test'))
    return client


@pytest.fixture
def depot(tmp_path, settings):
    """Un répertoire de dépôt vide, propre à chaque test."""
    dossier = tmp_path / 'desktop'
    dossier.mkdir()
    settings.ORION_DESKTOP_DIR = str(dossier)
    return dossier


def _installeur(depot, nom='OrionERP-Desktop-Setup.exe', octets=2048):
    chemin = depot / nom
    chemin.write_bytes(b'MZ' + b'\x00' * octets)
    return chemin


# ── L'entrée de menu ────────────────────────────────────────────────────────

def test_l_entree_figure_dans_mon_dashboard():
    """À côté de « Version téléphone », et dans le même module : il est dans
    always_show, donc l'entrée reste visible de tous. Un employé qui veut
    l'application sur son poste n'a pas à passer par un administrateur."""
    from apps.core.context_processors import NAV_MODULES

    groupe = next(m for m in NAV_MODULES if m['id'] == 'dashboard')
    cibles = [e['url_name'] for e in groupe['children']]
    assert 'dashboard:version_pc' in cibles


# ── La page ─────────────────────────────────────────────────────────────────

def test_la_page_liste_les_installeurs_presents(connecte, depot):
    _installeur(depot, 'OrionERP-Desktop-Setup.exe')
    _installeur(depot, 'OrionERP-Desktop-User-Setup.exe')

    corps = connecte.get(reverse('dashboard:version_pc')).content.decode()
    assert 'OrionERP-Desktop-Setup.exe' in corps
    assert 'OrionERP-Desktop-User-Setup.exe' in corps


def test_les_deux_installations_sont_distinguees(connecte, depot):
    """Confondre les deux fait échouer l'installation sur un poste où
    l'employé n'est pas administrateur — cas courant en entreprise."""
    _installeur(depot, 'OrionERP-Desktop-Setup.exe')
    _installeur(depot, 'OrionERP-Desktop-User-Setup.exe')

    corps = connecte.get(reverse('dashboard:version_pc')).content.decode()
    assert 'administrateur' in corps
    assert 'mon compte' in corps.lower()


def test_sans_installeur_la_page_dit_ou_le_deposer(connecte, depot):
    """« Déposez le fichier sur le serveur » sans le chemin exact n'est pas
    une instruction exécutable."""
    corps = connecte.get(reverse('dashboard:version_pc')).content.decode()

    assert 'Aucun installeur' in corps
    assert str(depot) in corps or 'desktop' in corps


def test_le_plus_recent_est_propose_en_premier(connecte, depot):
    """Après un nouveau build, c'est celui-là qu'on veut : laisser l'ordre
    alphabétique décider offrirait l'ancien."""
    import os
    import time

    ancien = _installeur(depot, 'OrionERP-ancien.exe')
    recent = _installeur(depot, 'OrionERP-a-nouveau.exe')
    # Horodatages explicites : deux ecritures de suite peuvent partager la
    # meme seconde, et le test deviendrait dependant de la vitesse du disque.
    os.utime(ancien, (time.time() - 7200, time.time() - 7200))
    os.utime(recent, (time.time(), time.time()))

    from apps.dashboard.version_pc import installeurs_disponibles
    noms = [i['nom'] for i in installeurs_disponibles()]
    assert noms[0] == 'OrionERP-a-nouveau.exe', noms


def test_un_fichier_sans_extension_d_installeur_est_ignore(connecte, depot):
    """Parcourir sans filtre proposerait au téléchargement n'importe quel
    fichier déposé là par erreur — un journal, une sauvegarde."""
    (depot / 'notes.txt').write_text('du texte')
    (depot / 'sauvegarde.sql').write_text('-- dump')
    _installeur(depot, 'OrionERP-Desktop-Setup.exe')

    from apps.dashboard.version_pc import installeurs_disponibles
    noms = [i['nom'] for i in installeurs_disponibles()]
    assert noms == ['OrionERP-Desktop-Setup.exe']


def test_un_repertoire_absent_n_est_pas_une_erreur(connecte, settings,
                                                   tmp_path):
    """Rien de déposé n'est pas une anomalie : la page doit s'afficher."""
    settings.ORION_DESKTOP_DIR = str(tmp_path / 'nexiste-pas')
    reponse = connecte.get(reverse('dashboard:version_pc'))
    assert reponse.status_code == 200
    assert 'Aucun installeur' in reponse.content.decode()


def test_la_page_exige_une_connexion(client, depot, entreprise):
    reponse = client.get(reverse('dashboard:version_pc'))
    assert reponse.status_code == 302
    assert 'version-pc' not in reponse['Location'].split('?')[0]


# ── Le téléchargement ───────────────────────────────────────────────────────

def test_l_installeur_est_servi(connecte, depot):
    _installeur(depot, 'OrionERP-Desktop-Setup.exe', octets=4096)

    reponse = connecte.get(reverse(
        'dashboard:version_pc_telecharger',
        args=['OrionERP-Desktop-Setup.exe']))

    assert reponse.status_code == 200
    assert reponse['Content-Disposition'].startswith('attachment')
    assert 'OrionERP-Desktop-Setup.exe' in reponse['Content-Disposition']
    # Annoncer la taille permet au navigateur d'afficher une progression :
    # sans elle, 180 Mo se telechargent sans qu'on sache ou l'on en est.
    assert int(reponse['Content-Length']) == 4098


def test_le_fichier_est_diffuse_et_non_charge_en_memoire(connecte, depot):
    """Charger 180 Mo en mémoire pour les renvoyer serait déraisonnable."""
    _installeur(depot, 'OrionERP-Desktop-Setup.exe')

    reponse = connecte.get(reverse(
        'dashboard:version_pc_telecharger',
        args=['OrionERP-Desktop-Setup.exe']))
    assert reponse.streaming is True


def test_un_nom_inconnu_renvoie_404(connecte, depot):
    _installeur(depot, 'OrionERP-Desktop-Setup.exe')
    assert connecte.get(reverse(
        'dashboard:version_pc_telecharger',
        args=['autre-chose.exe'])).status_code == 404


def test_le_telechargement_exige_une_connexion(client, depot, entreprise):
    _installeur(depot, 'OrionERP-Desktop-Setup.exe')
    reponse = client.get(reverse(
        'dashboard:version_pc_telecharger',
        args=['OrionERP-Desktop-Setup.exe']))
    assert reponse.status_code == 302


# ── La traversée de répertoire ──────────────────────────────────────────────

@pytest.mark.parametrize('nom', [
    '../../backend/.env',
    '..%2F..%2F.env',
    'OrionERP-Desktop-Setup.exe/../../../etc/passwd',
    '....//....//.env',
])
def test_aucun_nom_ne_permet_de_sortir_du_repertoire(connecte, depot, nom):
    """Le processus a accès à la base et aux sauvegardes : servir un fichier
    arbitraire ne serait pas une fuite mineure.

    La protection ne repose pas sur une normalisation de chemin qu'on
    pourrait écrire de travers, mais sur une COMPARAISON aux fichiers
    réellement présents — ce qui rend la question sans objet.
    """
    from apps.dashboard.version_pc import trouver_installeur

    _installeur(depot, 'OrionERP-Desktop-Setup.exe')
    assert trouver_installeur(nom) is None


def test_un_fichier_voisin_du_repertoire_est_hors_de_portee(connecte, depot,
                                                            tmp_path):
    """Même sans séparateur de chemin : un nom qui désigne un fichier existant
    ailleurs ne doit pas être servi."""
    from apps.dashboard.version_pc import trouver_installeur

    (tmp_path / 'secret.exe').write_bytes(b'MZ')
    assert trouver_installeur('../secret.exe') is None
    assert trouver_installeur('secret.exe') is None


def test_un_nom_vide_ne_sert_rien(depot):
    from apps.dashboard.version_pc import trouver_installeur

    assert trouver_installeur('') is None
    assert trouver_installeur(None) is None


# ── L'emplacement par défaut ────────────────────────────────────────────────

def test_le_depot_par_defaut_est_sur_le_volume_persistant(settings):
    """Sous MEDIA_ROOT : c'est le volume de l'appliance (/opt/orion/uploads),
    donc un emplacement qui survit aux mises à jour et qui est sauvegardé.
    Hors de ce volume, le fichier serait perdu au premier redéploiement."""
    from pathlib import Path

    from apps.dashboard.version_pc import repertoire

    settings.ORION_DESKTOP_DIR = ''
    assert repertoire() == Path(settings.MEDIA_ROOT) / 'desktop'


def test_le_reglage_prime_sur_le_defaut(settings, tmp_path):
    from apps.dashboard.version_pc import repertoire

    settings.ORION_DESKTOP_DIR = str(tmp_path / 'ailleurs')
    assert str(repertoire()).endswith('ailleurs')
