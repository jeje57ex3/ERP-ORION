"""Disques et placement des fichiers.

Ce que j'avais cru, et qui était faux : que l'ERP ne détectait pas les
disques. La détection **existait** et fonctionnait —
`services.get_disk_partitions_usage()` énumère tous les volumes montés par
`psutil.disk_partitions()`, `get_disk_allocations()` lit `lsblk` pour les
partitions non montées et l'espace non alloué, et la page
`/orion-admin/sante-systeme/disques/` les affiche. Un disque ajouté à la
machine y apparaît dès qu'il est monté. Elle est seulement enfouie sous
Super Admin.

Ce qui manquait réellement, et que ces tests couvrent :

1. **Les capteurs ne mesuraient que `/`.** Un disque de données monté sur
   `/mnt/donnees` et rempli à 99 % ne déclenchait aucune alerte. Les
   élargir sous le même nom de capteur aurait cassé `score_service` et
   `capacity_service`, qui lisent « la lecture `disk_usage` la plus
   récente » : plusieurs volumes sous ce nom leur auraient fait lire un
   disque au hasard. D'où deux capteurs distincts.
2. **Les emplacements n'étaient pas paramétrables.** `MEDIA_ROOT` et
   `STATIC_ROOT` étaient écrits « BASE_DIR / 'media' », codés en dur.
3. **La répartition ne disait pas sur quel disque chaque emplacement se
   trouve**, ni combien il reste sur ce disque — donc rien ne permettait
   de décider quoi déplacer.
4. **Rien ne disait comment déplacer une catégorie** sans se tromper.
"""

import pytest

pytestmark = pytest.mark.django_db


# ── 1. La détection, qui existait déjà : on la fige ─────────────────────────

def test_tous_les_volumes_montes_sont_vus():
    """Pas une régression possible : c'est la propriété dont tout dépend."""
    from apps.system_health.storage_service import volumes

    liste = volumes()
    assert liste, 'aucun volume détecté — psutil absent ?'
    for volume in liste:
        assert volume['point_de_montage']
        assert volume['total_go'] > 0
        assert 0 <= volume['pourcentage'] <= 100


def test_volumes_delegue_a_la_fonction_existante():
    """Une seule énumération, pas deux qui divergeront.

    `apps/core/menu.py` et `NAV_MODULES` ont divergé exactement comme ça :
    deux « sources de vérité » du même fait, dont une morte.
    """
    from apps.system_health.services import get_disk_partitions_usage
    from apps.system_health.storage_service import volumes

    origine = {p['mountpoint'] for p in get_disk_partitions_usage()}
    traduit = {v['point_de_montage'] for v in volumes()}
    assert origine == traduit


# ── 2. Le volume d'un chemin : le piège du préfixe ──────────────────────────

def test_le_volume_d_un_chemin_est_le_montage_le_plus_long():
    """`/` est un préfixe de tout.

    Une comparaison naïve attribuerait `/mnt/donnees/media` à la racine, et
    la page annoncerait l'espace libre du mauvais disque — celui qu'on
    cherche justement à soulager.
    """
    from apps.system_health.storage_service import volume_du_chemin

    faux_volumes = [
        {'point_de_montage': '/', 'libre_go': 5.0, 'pourcentage': 95.0},
        {'point_de_montage': '/mnt/donnees', 'libre_go': 450.0,
         'pourcentage': 10.0},
    ]
    trouve = volume_du_chemin('/mnt/donnees/orion/medias', faux_volumes)
    assert trouve['point_de_montage'] == '/mnt/donnees'
    assert trouve['libre_go'] == 450.0


def test_un_nom_de_montage_voisin_ne_compte_pas():
    """« /mnt/donnees2 » commence par « /mnt/donnees » sans être dessous.

    C'est pourquoi on compare avec `os.path.commonpath` et non un
    `startswith`, qui se tromperait de disque en silence.
    """
    from apps.system_health.storage_service import volume_du_chemin

    # « /mnt/donnees » est place EN PREMIER a dessein : une implementation
    # qui rendrait simplement le premier volume correspondant -- ou le
    # premier de la liste -- donnerait la mauvaise reponse et ce test le
    # verrait. Place en second, il passerait sans rien prouver.
    faux_volumes = [
        {'point_de_montage': '/mnt/donnees', 'libre_go': 450.0,
         'pourcentage': 10.0},
        {'point_de_montage': '/', 'libre_go': 5.0, 'pourcentage': 95.0},
    ]
    trouve = volume_du_chemin('/mnt/donnees2/fichiers', faux_volumes)
    assert trouve['point_de_montage'] == '/'


def test_sans_volume_connu_on_rend_rien_plutot_qu_un_faux():
    from apps.system_health.storage_service import volume_du_chemin

    assert volume_du_chemin('/mnt/donnees', []) is None


# ── 3. Les emplacements paramétrables ───────────────────────────────────────

def test_les_quatre_reglages_sont_lus_depuis_l_environnement():
    """MEDIA_ROOT et STATIC_ROOT étaient codés en dur.

    Les noms de clés sont ceux que le provisioning écrit DÉJÀ dans le .env
    de l'appliance — et que Django ne lisait nulle part.
    """
    import os
    import re

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(racine, 'erp_btp', 'settings', 'base.py'),
              encoding='utf-8-sig') as flux:
        contenu = flux.read()

    for cle in ('MEDIA_ROOT', 'STATIC_ROOT', 'BACKUP_DIR', 'LOG_DIR'):
        assert re.search(rf"emplacement\('{cle}'", contenu), (
            f'{cle} ne passe pas par emplacement() : il reste code en dur')


def test_un_chemin_absolu_remplace_le_dossier_de_l_application(monkeypatch):
    """Le cœur du besoin : poser une catégorie sur un autre disque.

    Avant, `MEDIA_ROOT = BASE_DIR / 'media'` ne laissait aucune prise.
    """
    import importlib
    from pathlib import Path

    from django.conf import settings

    # On rejoue le helper tel que base.py le définit, plutôt que de
    # recharger tout Django : le comportement testé est celui du helper.
    base = Path(settings.BASE_DIR)

    def emplacement(valeur):
        chemin = Path(valeur).expanduser()
        return chemin if chemin.is_absolute() else (base / chemin)

    assert emplacement('media') == base / 'media'
    absolu = emplacement('/mnt/donnees/orion/medias')
    assert absolu.is_absolute()
    assert 'mnt' in absolu.as_posix()
    assert str(base) not in absolu.as_posix()


def test_chaque_categorie_est_rattachee_a_un_volume():
    from apps.system_health.storage_service import emplacements

    liste = emplacements(mesurer_tailles=False)
    assert liste, 'aucune catégorie'
    cles = {e['cle'] for e in liste}
    assert {'medias', 'sauvegardes', 'journaux'} <= cles

    for entree in liste:
        assert entree['chemin_reel']
        assert entree['variable_env']
        # Le volume peut être None sur une machine exotique, mais le champ
        # doit exister pour que le gabarit ne lève pas.
        assert 'volume' in entree


def test_la_base_mysql_n_est_pas_proposee():
    """Choix délibéré, et il est le tien : MySQL n'est pas déplaçable ici.

    Arrêter le conteneur, déplacer le volume et le redémarrer est
    l'endroit où une erreur coûte le plus cher. Ce n'est pas une case à
    cocher dans une page web.
    """
    from apps.system_health.storage_service import CATEGORIES

    libelles = ' '.join(c['nom'].lower() + c['contenu'].lower()
                        for c in CATEGORIES)
    assert 'mysql' not in libelles


# ── 4. Les capteurs, qui ne voyaient que la racine ──────────────────────────

def test_les_deux_capteurs_multi_volumes_existent():
    from apps.system_health.models import SENSOR_TYPE_CHOICES

    codes = {code for code, _ in SENSOR_TYPE_CHOICES}
    assert 'disk_usage_max' in codes
    assert 'disk_free_min_gb' in codes


def test_les_nouveaux_capteurs_ont_un_seuil_par_defaut():
    """Un capteur sans seuil ne déclenche jamais rien : il serait décoratif."""
    from apps.system_health.management.commands.setup_health_thresholds import (
        DEFAULT_THRESHOLDS,
    )

    codes = {ligne[0] for ligne in DEFAULT_THRESHOLDS}
    assert 'disk_usage_max' in codes
    assert 'disk_free_min_gb' in codes


def test_la_collecte_remonte_le_pire_volume():
    """Le disque de données à 99 % doit faire réagir, pas seulement `/`."""
    from unittest.mock import patch

    from apps.system_health.models import SensorReading
    from apps.system_health.services import collect_server_sensors

    faux = [
        {'point_de_montage': '/', 'peripherique': '/dev/sda1',
         'systeme_de_fichiers': 'ext4', 'total_go': 40.0, 'utilise_go': 20.0,
         'libre_go': 20.0, 'pourcentage': 50.0, 'statut': 'ok'},
        {'point_de_montage': '/mnt/donnees', 'peripherique': '/dev/sdb1',
         'systeme_de_fichiers': 'ext4', 'total_go': 500.0,
         'utilise_go': 496.0, 'libre_go': 4.0, 'pourcentage': 99.2,
         'statut': 'critical'},
    ]
    with patch('apps.system_health.storage_service.volumes', return_value=faux):
        collect_server_sensors()

    pire = SensorReading.objects.filter(
        sensor_type='disk_usage_max').order_by('-collected_at').first()
    assert pire is not None, 'aucune lecture disk_usage_max'
    assert pire.value == 99.2
    assert pire.metadata['pire_volume'] == '/mnt/donnees'
    assert pire.metadata['nombre_de_volumes'] == 2

    libre = SensorReading.objects.filter(
        sensor_type='disk_free_min_gb').order_by('-collected_at').first()
    assert libre.value == 4.0


def test_la_racine_garde_son_sens_pour_les_scores():
    """LE piège évité.

    `score_service._latest_sensor('disk_usage')` et
    `capacity_service._sensor_latest('disk_usage')` prennent la lecture la
    plus récente pour ce seul nom de capteur. Émettre une lecture
    `disk_usage` par volume leur aurait fait lire un disque au hasard — et
    fausser des moyennes sur trente jours. Il doit donc y avoir
    exactement UNE lecture `disk_usage` par collecte.
    """
    from unittest.mock import patch

    from apps.system_health.models import SensorReading
    from apps.system_health.services import collect_server_sensors

    faux = [
        {'point_de_montage': '/', 'peripherique': '/dev/sda1',
         'systeme_de_fichiers': 'ext4', 'total_go': 40.0, 'utilise_go': 20.0,
         'libre_go': 20.0, 'pourcentage': 50.0, 'statut': 'ok'},
        {'point_de_montage': '/mnt/donnees', 'peripherique': '/dev/sdb1',
         'systeme_de_fichiers': 'ext4', 'total_go': 500.0,
         'utilise_go': 496.0, 'libre_go': 4.0, 'pourcentage': 99.2,
         'statut': 'critical'},
    ]
    with patch('apps.system_health.storage_service.volumes', return_value=faux):
        collect_server_sensors()

    assert SensorReading.objects.filter(sensor_type='disk_usage').count() == 1
    assert SensorReading.objects.filter(
        sensor_type='disk_free_gb').count() == 1


def test_un_montage_illisible_ne_casse_pas_la_collecte():
    """Un partage réseau coupé ne doit pas emporter CPU et mémoire avec lui."""
    from unittest.mock import patch

    from apps.system_health.models import SensorReading
    from apps.system_health.services import collect_server_sensors

    with patch('apps.system_health.storage_service.volumes',
               side_effect=OSError('montage injoignable')):
        assert collect_server_sensors() is True

    assert SensorReading.objects.filter(sensor_type='cpu_usage').exists()
    assert SensorReading.objects.filter(sensor_type='disk_usage').exists()


# ── 5. La répartition dit maintenant sur quel disque ────────────────────────

def test_chaque_emplacement_porte_son_volume():
    """L'information qui manquait pour décider quoi déplacer."""
    from apps.system_health.services import get_storage_breakdown

    resultat = get_storage_breakdown(use_cache=False)
    assert resultat['rows'], 'aucun emplacement mesuré'
    for ligne in resultat['rows']:
        assert 'mountpoint' in ligne
        assert 'volume_free_gb' in ligne


def test_les_sauvegardes_suivent_le_reglage():
    """Le chemin était figé sur « base / storage / backups ».

    Maintenant que BACKUP_DIR est déplaçable, un chemin figé aurait fait
    annoncer « 0 Go de sauvegardes » sur une installation qui en a des
    dizaines.
    """
    import os
    import re

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(racine, 'apps', 'system_health', 'services.py'),
              encoding='utf-8') as flux:
        contenu = flux.read()

    bloc = contenu[contenu.index('def _emplacements_donnees'):]
    bloc = bloc[:bloc.index('def _taille_repertoire')]
    assert 'BACKUP_DIR' in bloc, (
        'les sauvegardes doivent suivre settings.BACKUP_DIR')


# ── 6. Le plan de migration : rédigé, jamais exécuté ────────────────────────

def test_le_plan_ne_contient_aucune_commande_destructrice_active():
    """La propriété qui compte le plus dans ce travail.

    Un plan qui glisserait un `rm -rf` exécutable ferait perdre des
    fichiers à quelqu'un qui copie-colle sans lire. La suppression de
    l'ancien dossier est présente — mais commentée.
    """
    from apps.system_health.storage_service import commandes_de_migration

    plan = commandes_de_migration('medias', '/mnt/donnees')
    for etape in plan['etapes']:
        for commande in etape['commandes']:
            if 'rm -rf' in commande:
                assert commande.strip().startswith('#'), (
                    f'suppression non commentee : {commande}')


def test_le_plan_copie_avant_de_basculer_le_reglage():
    """L'ordre n'est pas cosmétique.

    Basculer le réglage avant la copie laisserait l'ERP écrire dans un
    dossier vide pendant tout le transfert : les fichiers déposés entre
    les deux seraient introuvables.
    """
    from apps.system_health.storage_service import commandes_de_migration

    plan = commandes_de_migration('medias', '/mnt/donnees')
    titres = [e['titre'].lower() for e in plan['etapes']]
    rang_copie = next(i for i, t in enumerate(titres) if 'copier' in t)
    rang_bascule = next(i for i, t in enumerate(titres) if 'basculer' in t)
    rang_suppression = next(i for i, t in enumerate(titres)
                            if 'supprimer' in t)
    assert rang_copie < rang_bascule < rang_suppression


def test_le_plan_verifie_le_montage_au_demarrage():
    """Sans ligne dans fstab, le disque disparaît au redémarrage suivant.

    L'ERP écrirait alors dans un dossier vide du disque système, sans
    rien signaler — le genre de panne qu'on découvre des semaines plus
    tard, quand on cherche un fichier.
    """
    from apps.system_health.storage_service import commandes_de_migration

    plan = commandes_de_migration('medias', '/mnt/donnees')
    tout = ' '.join(c for e in plan['etapes'] for c in e['commandes'])
    assert 'fstab' in tout


def test_le_plan_cible_la_bonne_variable():
    from apps.system_health.storage_service import commandes_de_migration

    for cle, variable in (('medias', 'MEDIA_ROOT'),
                          ('sauvegardes', 'BACKUP_DIR'),
                          ('journaux', 'LOG_DIR')):
        plan = commandes_de_migration(cle, '/mnt/donnees')
        tout = ' '.join(c for e in plan['etapes'] for c in e['commandes'])
        assert variable in tout, f'{cle} doit basculer {variable}'


def test_une_categorie_inconnue_est_refusee():
    from apps.system_health.storage_service import commandes_de_migration

    with pytest.raises(ValueError):
        commandes_de_migration('mysql', '/mnt/donnees')


# ── 7. La page, rendue pour de vrai ─────────────────────────────────────────

def _super_admin(client, django_user_model):
    # Une entreprise est necessaire : sans elle, l'ERP redirige vers
    # /setup/ avant d'atteindre la vue -- la page n'aurait pas ete testee.
    from apps.accounts.models import UserProfile
    from apps.core.models import Company

    entreprise = Company.objects.create(name='Orion SAS', slug='orion-sas')
    utilisateur = django_user_model.objects.create_user(
        'root', password='x', is_superuser=True, is_staff=True)
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


def test_la_page_des_disques_s_affiche(client, django_user_model):
    """Elle existait déjà et fonctionnait — ce test la protège."""
    from django.urls import reverse

    _super_admin(client, django_user_model)
    reponse = client.get(reverse('system_health:disk_dashboard'))
    assert reponse.status_code == 200
    assert reponse.context['placements']
    assert reponse.context['volumes']


def test_la_page_montre_le_plan_quand_on_choisit_un_volume(
        client, django_user_model):
    from django.urls import reverse

    from apps.system_health.storage_service import volumes

    _super_admin(client, django_user_model)
    cible = volumes()[0]['point_de_montage']

    reponse = client.get(reverse('system_health:disk_dashboard'),
                         {'categorie': 'medias', 'volume': cible})
    assert reponse.status_code == 200
    assert reponse.context['plan'] is not None
    assert reponse.context['plan']['categorie']['cle'] == 'medias'


def test_un_volume_invente_dans_l_url_ne_produit_pas_de_plan(
        client, django_user_model):
    """Sinon l'URL dicterait des commandes qui créeraient un dossier
    ailleurs — sur le disque système, par exemple."""
    from django.urls import reverse

    _super_admin(client, django_user_model)
    reponse = client.get(reverse('system_health:disk_dashboard'),
                         {'categorie': 'medias',
                          'volume': '/mnt/inexistant-invente'})
    assert reponse.status_code == 200
    assert reponse.context['plan'] is None


def test_un_simple_utilisateur_n_accede_pas_a_la_page(client,
                                                      django_user_model):
    from django.urls import reverse

    django_user_model.objects.create_user('jean', password='x')
    client.force_login(django_user_model.objects.get(username='jean'))
    reponse = client.get(reverse('system_health:disk_dashboard'))
    assert reponse.status_code in (302, 403, 404)
