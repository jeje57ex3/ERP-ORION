"""L'écran des disques, vérifié sur le HTML RENDU et non sur la logique.

Pourquoi ce fichier existe : `test_stockage_execution.py` couvrait les
refus, le contrat sudo et la validation du script root — mais jamais la
page. Trois défauts s'y cachaient, tous invisibles aux tests existants et
tous rapportés depuis l'écran :

1. **Le sélecteur « Déplacer vers » proposait /boot et /boot/efi.** Sur une
   appliance à un seul disque, `volumes()` rend « / », « /boot » et
   « /boot/efi ». La racine portant déjà les données était grisée, il ne
   restait donc que deux partitions de démarrage de 100 Mo et 880 Mo. Vu de
   l'écran : « l'ERP ne propose rien ». Il proposait, mais rien
   d'utilisable — et y déposer des médias aurait empêché la machine de
   redémarrer.

2. **Une liste de destinations vide n'expliquait rien.** Un disque de 3 To
   marqué « Disponible » plus haut dans la page, et aucun moyen de s'en
   servir plus bas : rien ne disait qu'il fallait d'abord le préparer, ni
   où cliquer.

3. **Une opération coincée condamnait l'écran.** Le verrou « une seule à la
   fois » masquait le bouton de préparation ET tous les sélecteurs, sans
   aucune sortie depuis l'interface. Le seul recours était un UPDATE en
   base — exactement ce que Jessy a demandé à ne jamais avoir à faire.

Les données injectées sont celles RÉELLEMENT mesurées sur sa machine,
recopiées des sorties de `orion-stockage lister` et de `findmnt`.
"""

import pytest

# ── Les disques tels que l'assistant les a réellement rapportés ───────────

DISQUES_REELS = {
    'ok': True,
    'disques': [
        {
            'peripherique': '/dev/sda',
            'taille_octets': 53687091200,
            'modele': 'QEMU HARDDISK',
            'numero_de_serie': 'drive-scsi0',
            'wwn': '',
            'amovible': False,
            'partitions': 4,
            'systemes_de_fichiers': ['ext4', 'vfat', 'ext4'],
            'points_de_montage': ['/', '/boot/efi', '/boot'],
            'contient_des_donnees': True,
            'utilisable': False,
            'raisons': ['porte le système (/)'],
        },
        {
            'peripherique': '/dev/sdb',
            'taille_octets': 3221225472000,
            'modele': 'QEMU HARDDISK',
            'numero_de_serie': 'QM00013',
            'wwn': '',
            'amovible': False,
            'partitions': 0,
            'systemes_de_fichiers': [],
            'points_de_montage': [],
            'contient_des_donnees': False,
            'utilisable': True,
            'raisons': [],
        },
    ],
    'montages_orion': [],
}


def _volume(point, libre_go, total_go, fstype='ext4', peripherique='/dev/sda1'):
    return {
        'point_de_montage': point,
        'peripherique': peripherique,
        'systeme_de_fichiers': fstype,
        'total_go': total_go,
        'utilise_go': round(total_go - libre_go, 2),
        'libre_go': libre_go,
        'pourcentage': round((total_go - libre_go) / total_go * 100, 1),
        'statut': 'ok',
    }


# Exactement ce que `findmnt` a rendu sur la machine de Jessy, overlays
# Docker exclus (ils le sont déjà par _EXCLUDED_FSTYPES).
VOLUMES_UN_SEUL_DISQUE = [
    _volume('/', 7.4, 47.4),
    _volume('/boot', 0.4, 0.88, peripherique='/dev/sda16'),
    _volume('/boot/efi', 0.09, 0.104, fstype='vfat', peripherique='/dev/sda15'),
]

VOLUMES_APRES_PREPARATION = VOLUMES_UN_SEUL_DISQUE + [
    _volume('/mnt/orion-donnees', 2900.0, 2900.0, peripherique='/dev/sdb1'),
]


def _placements(volume_courant):
    """Un seul placement déplaçable, posé sur le volume indiqué.

    `emplacements()` est remplacé plutôt que simulé : il résout des liens
    symboliques et compare des points de montage POSIX, ce qui ne se
    reproduit pas sous Windows. Ce qui est testé ici est l'enrichissement
    fait par la vue, pas la résolution de chemins.
    """
    def _faux(mesurer_tailles=True):
        return [{
            'cle': 'medias',
            'nom': 'Médias et documents',
            'reglage': 'MEDIA_ROOT',
            'variable_env': 'MEDIA_ROOT',
            'contenu': 'Photos, PDF, documents RH privés.',
            'purge': 'Jamais purgé.',
            'deplacable': True,
            'chemin_configure': '/opt/orion/backend/media',
            'chemin_reel': '/opt/orion/uploads',
            'est_un_lien': True,
            'existe': True,
            'taille_octets': None,
            'taille_go': None,
            'taille_complete': True,
            'volume': volume_courant,
        }]
    return _faux


def _super_admin(client, django_user_model):
    from apps.accounts.models import UserProfile
    from apps.core.models import Company

    entreprise, _ = Company.objects.get_or_create(
        slug='orion-affichage-disques', defaults={'name': 'Orion Disques'})
    utilisateur = django_user_model.objects.create_user(
        'patron-disques', password='x', is_superuser=True, is_staff=True)
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


def _assistant_qui_repond(monkeypatch, reponse=None):
    monkeypatch.setattr(
        'apps.system_health.stockage_privilegie.est_disponible',
        lambda: True)
    monkeypatch.setattr(
        'apps.system_health.stockage_privilegie.lister_les_disques',
        lambda: reponse if reponse is not None else DISQUES_REELS)


def _machine(monkeypatch, volumes, volume_courant):
    """Fixe les volumes montés et l'emplacement actuel des médias."""
    monkeypatch.setattr(
        'apps.system_health.storage_service.volumes', lambda: volumes)
    monkeypatch.setattr(
        'apps.system_health.storage_service.emplacements',
        _placements(volume_courant))


def _page(client):
    from django.urls import reverse
    reponse = client.get(reverse('system_health:disk_dashboard'))
    assert reponse.status_code == 200
    return reponse.content.decode()


# ── 1. Le bouton de préparation ───────────────────────────────────────────

@pytest.mark.django_db
def test_le_bouton_preparer_apparait_pour_un_disque_utilisable(
        client, django_user_model, monkeypatch):
    """Le cas de Jessy : assistant installé, /dev/sdb vierge et utilisable."""
    _assistant_qui_repond(monkeypatch)
    _super_admin(client, django_user_model)

    contenu = _page(client)

    assert '/dev/sdb' in contenu, 'le disque n\'est pas listé du tout'
    assert 'Disponible' in contenu, 'le badge « Disponible » manque'
    assert 'Préparer et monter' in contenu, (
        'LE BOUTON MANQUE alors que le disque est utilisable')
    assert 'name="etiquette"' in contenu
    assert 'name="confirmation"' in contenu


@pytest.mark.django_db
def test_aucun_commentaire_de_gabarit_ne_fuit_dans_la_page(
        client, django_user_model, monkeypatch):
    """Le formulaire affichait en clair le commentaire du développeur.

    « {# … #} » étalé sur trois lignes n'est pas un commentaire pour
    Django : son texte est rendu. Il apparaissait entre la phrase
    d'avertissement et le bouton, au milieu du seul formulaire de cette
    page qui efface un disque.

    Le contrôle porte sur le HTML rendu et non sur le fichier : c'est
    `tests/test_gabarits_sains.py` qui garde la syntaxe, mais lui ne
    regardait pas les gabarits des apps — d'où ce test de plus, ici, sur
    l'écran lui-même.
    """
    _assistant_qui_repond(monkeypatch)
    _super_admin(client, django_user_model)

    contenu = _page(client)

    assert 'Préparer et monter' in contenu, 'le formulaire doit être rendu'
    assert '{#' not in contenu
    assert '#}' not in contenu
    assert 'numero de serie AFFICHE' not in contenu
    assert '{% comment %}' not in contenu
    assert '{% endcomment %}' not in contenu


@pytest.mark.django_db
def test_sans_assistant_aucun_disque_n_est_liste(
        client, django_user_model, monkeypatch):
    """L'état d'avant l'installation : bandeau, aucun disque, aucun bouton."""
    monkeypatch.setattr(
        'apps.system_health.stockage_privilegie.est_disponible',
        lambda: False)
    _super_admin(client, django_user_model)

    contenu = _page(client)

    assert 'Préparer et monter' not in contenu
    # Sans apostrophe dans l'assertion : le gabarit échappe « n'est » en
    # « n&#x27;est », donc chercher la forme Python ne trouve jamais rien.
    assert 'pas installé sur ce serveur' in contenu


# ── 2. Les partitions de démarrage ne sont jamais des destinations ────────

def test_les_partitions_de_demarrage_sont_ecartees(monkeypatch):
    """Défaut n°1, à la source : /boot et /boot/efi hors des destinations."""
    from apps.system_health import storage_service

    monkeypatch.setattr(storage_service, 'volumes',
                        lambda: VOLUMES_UN_SEUL_DISQUE)

    points = [v['point_de_montage']
              for v in storage_service.volumes_pour_destination()]

    assert points == ['/'], (
        'seule la racine doit rester : /boot ferait planter le démarrage')


def test_la_racine_reste_une_destination_possible(monkeypatch):
    """Elle n'est pas écartée : on doit pouvoir revenir en arrière."""
    from apps.system_health import storage_service

    monkeypatch.setattr(storage_service, 'volumes',
                        lambda: VOLUMES_APRES_PREPARATION)

    points = [v['point_de_montage']
              for v in storage_service.volumes_pour_destination()]

    assert points == ['/', '/mnt/orion-donnees']


def test_un_sous_dossier_de_boot_est_ecarte_aussi(monkeypatch):
    """Le filtre porte sur le préfixe, pas sur une liste figée de noms."""
    from apps.system_health import storage_service

    monkeypatch.setattr(storage_service, 'volumes', lambda: [
        _volume('/', 7.4, 47.4),
        _volume('/boot/firmware', 0.2, 0.5),
        _volume('/bootstrap-donnees', 500.0, 900.0),
    ])

    points = [v['point_de_montage']
              for v in storage_service.volumes_pour_destination()]

    # /bootstrap-donnees commence par « /boot » en tant que TEXTE mais
    # n'est pas dans /boot : un filtre par startswith() naïf l'aurait
    # écarté, et aurait rendu un vrai disque de données inutilisable.
    assert points == ['/', '/bootstrap-donnees']


@pytest.mark.django_db
def test_le_selecteur_ne_propose_pas_boot(
        client, django_user_model, monkeypatch):
    """Défaut n°1 vu de l'écran, après préparation du disque."""
    _assistant_qui_repond(monkeypatch)
    _machine(monkeypatch, VOLUMES_APRES_PREPARATION,
             VOLUMES_UN_SEUL_DISQUE[0])
    _super_admin(client, django_user_model)

    contenu = _page(client)

    assert 'value="/mnt/orion-donnees"' in contenu, (
        'le disque préparé doit être proposé')
    assert 'value="/boot"' not in contenu
    assert 'value="/boot/efi"' not in contenu
    # Et plus aucune option grisée : ce qui s'affiche est choisissable.
    assert 'disabled' not in contenu.split('name="volume"')[1][:600]


@pytest.mark.django_db
def test_un_deplacement_vers_boot_est_refuse(
        client, django_user_model, monkeypatch):
    """Le contrôle au POST porte sur la même liste que l'écran."""
    from django.urls import reverse

    from apps.system_health.models import OperationDeStockage

    _machine(monkeypatch, VOLUMES_UN_SEUL_DISQUE, VOLUMES_UN_SEUL_DISQUE[0])
    _super_admin(client, django_user_model)

    client.post(reverse('system_health:stockage_deplacer'), {
        'categorie': 'medias', 'volume': '/boot', 'mode': 'basculer'})

    assert OperationDeStockage.objects.count() == 0, (
        'une requête forgée ne doit pas pouvoir remplir /boot')


# ── 3. Une liste vide doit s'expliquer ────────────────────────────────────

@pytest.mark.django_db
def test_sans_destination_la_page_nomme_le_disque_a_preparer(
        client, django_user_model, monkeypatch):
    """Défaut n°2 : « rien » devient « ce disque, pas encore préparé »."""
    _assistant_qui_repond(monkeypatch)
    _machine(monkeypatch, VOLUMES_UN_SEUL_DISQUE, VOLUMES_UN_SEUL_DISQUE[0])
    _super_admin(client, django_user_model)

    contenu = _page(client)

    assert 'Aucun autre volume' in contenu
    assert 'pas encore préparé' in contenu
    assert '/dev/sdb' in contenu
    assert 'href="#ajouter-un-disque"' in contenu
    assert 'id="ajouter-un-disque"' in contenu, (
        'le lien doit mener quelque part')
    # Et surtout : aucun sélecteur trompeur.
    assert 'name="volume"' not in contenu


@pytest.mark.django_db
def test_sans_disque_du_tout_la_page_le_dit_autrement(
        client, django_user_model, monkeypatch):
    """Aucun disque préparable : inutile de proposer d'en préparer un."""
    _assistant_qui_repond(
        monkeypatch, {'ok': True, 'disques': [DISQUES_REELS['disques'][0]],
                      'montages_orion': []})
    _machine(monkeypatch, VOLUMES_UN_SEUL_DISQUE, VOLUMES_UN_SEUL_DISQUE[0])
    _super_admin(client, django_user_model)

    contenu = _page(client)

    assert 'Ajoutez un disque à la machine' in contenu
    assert 'pas encore préparé' not in contenu


# ── 4. Une opération coincée ne doit plus condamner l'écran ───────────────

def _operation_coincee(etat='en_attente'):
    from apps.system_health.models import OperationDeStockage

    return OperationDeStockage.objects.create(
        type_operation='copier_basculer', categorie='medias', etat=etat)


@pytest.mark.django_db
def test_une_operation_en_cours_masque_le_bouton_mais_offre_une_sortie(
        client, django_user_model, monkeypatch):
    """Défaut n°3 : le blocage reste, le cul-de-sac disparaît."""
    _assistant_qui_repond(monkeypatch)
    _machine(monkeypatch, VOLUMES_APRES_PREPARATION,
             VOLUMES_UN_SEUL_DISQUE[0])
    _super_admin(client, django_user_model)
    operation = _operation_coincee()

    contenu = _page(client)

    # Le verrou tient toujours.
    assert 'Préparer et monter' not in contenu
    assert 'name="volume"' not in contenu
    # Mais l'écran nomme ce qui bloque, et permet de le clore.
    assert f'Opération #{operation.pk}' in contenu
    assert 'Abandonner cette opération' in contenu
    assert 'ABANDONNER' in contenu


@pytest.mark.django_db
def test_abandonner_rouvre_l_ecran(client, django_user_model, monkeypatch):
    from django.urls import reverse

    from apps.system_health.models import OperationDeStockage

    _assistant_qui_repond(monkeypatch)
    _machine(monkeypatch, VOLUMES_APRES_PREPARATION,
             VOLUMES_UN_SEUL_DISQUE[0])
    _super_admin(client, django_user_model)
    operation = _operation_coincee()

    client.post(
        reverse('system_health:stockage_abandonner_operation',
                args=[operation.pk]),
        {'confirmation': 'ABANDONNER'})

    operation = OperationDeStockage.objects.get(pk=operation.pk)
    assert operation.etat == 'echouee'
    # Rien n'est supprimé : la trace reste.
    assert OperationDeStockage.objects.count() == 1
    assert 'Abandonnée depuis' in operation.journal

    contenu = _page(client)
    assert 'Préparer et monter' in contenu
    assert 'value="/mnt/orion-donnees"' in contenu


@pytest.mark.django_db
def test_abandonner_sans_la_confirmation_ne_fait_rien(
        client, django_user_model, monkeypatch):
    from django.urls import reverse

    from apps.system_health.models import OperationDeStockage

    _super_admin(client, django_user_model)
    operation = _operation_coincee(etat='en_cours')

    for essai in ('', 'abandonner', 'oui'):
        client.post(
            reverse('system_health:stockage_abandonner_operation',
                    args=[operation.pk]),
            {'confirmation': essai})
        assert OperationDeStockage.objects.get(pk=operation.pk).etat == 'en_cours'


@pytest.mark.django_db
def test_abandonner_une_operation_deja_close_ne_la_touche_pas(
        client, django_user_model, monkeypatch):
    """Une opération terminée ne doit pas pouvoir être repassée en échec."""
    from django.urls import reverse

    from apps.system_health.models import OperationDeStockage

    _super_admin(client, django_user_model)
    operation = _operation_coincee(etat='terminee')

    client.post(
        reverse('system_health:stockage_abandonner_operation',
                args=[operation.pk]),
        {'confirmation': 'ABANDONNER'})

    assert OperationDeStockage.objects.get(pk=operation.pk).etat == 'terminee'


@pytest.mark.django_db
def test_abandonner_refuse_la_methode_get(client, django_user_model):
    from django.urls import reverse

    _super_admin(client, django_user_model)
    operation = _operation_coincee()

    reponse = client.get(
        reverse('system_health:stockage_abandonner_operation',
                args=[operation.pk]))

    assert reponse.status_code == 405


@pytest.mark.django_db
def test_un_utilisateur_ordinaire_ne_peut_pas_abandonner(
        client, django_user_model):
    from django.urls import reverse

    from apps.system_health.models import OperationDeStockage

    django_user_model.objects.create_user('simple-disques', password='x')
    client.login(username='simple-disques', password='x')
    operation = _operation_coincee()

    client.post(
        reverse('system_health:stockage_abandonner_operation',
                args=[operation.pk]),
        {'confirmation': 'ABANDONNER'})

    assert OperationDeStockage.objects.get(pk=operation.pk).etat == 'en_attente'


# ─── Défaut n°4 : un lien habillé en bouton d'action ──────────────────────
#
# Rapporté depuis l'écran, trois fois : « le bouton Préparer un disque ne
# fonctionne pas ». Il avait raison. Le mot « Préparer un disque » ne
# désignait pas le bouton du formulaire -- qui s'appelle « Préparer et
# monter » -- mais un lien d'ancre habillé en `orion-btn btn-outline-primary`,
# donc indiscernable d'un bouton d'action. Cliquer faisait défiler la page
# jusqu'à la section « Ajouter un disque », et RIEN DU TOUT quand cette
# section était déjà à l'écran.
#
# Un contrôle qui ressemble à un bouton promet d'agir. Celui-ci naviguait.


@pytest.mark.django_db
def test_le_lien_vers_le_formulaire_n_est_pas_habille_en_bouton(
        client, django_user_model, monkeypatch):
    """Sinon il promet une action et n'en exécute aucune."""
    import re

    _assistant_qui_repond(monkeypatch)
    _machine(monkeypatch, VOLUMES_UN_SEUL_DISQUE, VOLUMES_UN_SEUL_DISQUE[0])
    _super_admin(client, django_user_model)

    contenu = _page(client)
    balise = re.search('<a href="#ajouter-un-disque"[^>]*>', contenu)
    assert balise, 'le lien de navigation a disparu'

    assert 'orion-btn' not in balise.group(0), (
        'un lien de navigation habille en bouton fait croire a une action : '
        + balise.group(0))


@pytest.mark.django_db
def test_le_lien_annonce_ou_il_mene(client, django_user_model, monkeypatch):
    """« Préparer un disque » décrivait une action, pas une destination."""
    _assistant_qui_repond(monkeypatch)
    _machine(monkeypatch, VOLUMES_UN_SEUL_DISQUE, VOLUMES_UN_SEUL_DISQUE[0])
    _super_admin(client, django_user_model)

    contenu = _page(client)

    assert 'Aller au formulaire de préparation' in contenu
    assert 'plus bas' in contenu


@pytest.mark.django_db
def test_le_clic_produit_un_effet_visible_meme_si_la_cible_est_a_l_ecran(
        client, django_user_model, monkeypatch):
    """Le cœur du défaut : une ancre déjà visible ne fait rien du tout.

    `:target` met la section en évidence sans JavaScript, et retombe au
    clic suivant. Sans cette règle, le lien reste muet sur un grand écran
    où la section est déjà affichée — et c'est exactement la situation
    depuis laquelle le défaut a été rapporté.
    """
    _assistant_qui_repond(monkeypatch)
    _machine(monkeypatch, VOLUMES_UN_SEUL_DISQUE, VOLUMES_UN_SEUL_DISQUE[0])
    _super_admin(client, django_user_model)

    contenu = _page(client)

    assert '#ajouter-un-disque:target' in contenu, (
        'sans effet visible, le lien paraitra casse')


@pytest.mark.django_db
def test_le_formulaire_qui_efface_un_disque_n_apparait_qu_une_fois(
        client, django_user_model, monkeypatch):
    """Deux exemplaires d'une commande destructrice invitent à l'erreur.

    La tentation, en corrigeant le défaut ci-dessus, est de recopier le
    formulaire à l'endroit du lien. Il efface un disque sans retour
    possible : il reste à un seul endroit, et on y conduit.
    """
    _assistant_qui_repond(monkeypatch)
    _machine(monkeypatch, VOLUMES_UN_SEUL_DISQUE, VOLUMES_UN_SEUL_DISQUE[0])
    _super_admin(client, django_user_model)

    contenu = _page(client)

    assert contenu.count('disques/preparer/') == 1, (
        'le formulaire de preparation doit rester unique sur la page')
