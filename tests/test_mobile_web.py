"""Interface téléphone : accès, prise de photo, choix du serveur.

La propriété la plus importante éprouvée ici est le **cloisonnement par
entreprise**. Une liste de chantiers non filtrée exposerait les noms de
chantiers et de clients d'autres entreprises, et un identifiant forgé
rangerait une photo chez un tiers. C'est la règle centrale de cet ERP, et
elle a déjà été enfreinte dans ce dépôt.
"""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

pytestmark = pytest.mark.django_db


def _image(nom='photo.jpg', octets=2048, type_mime='image/jpeg'):
    """Un fichier plausible : le contenu n'est pas décodé, seule la taille
    et le type déclaré sont contrôlés."""
    return SimpleUploadedFile(nom, b'\xff\xd8\xff' + b'0' * octets, content_type=type_mime)


@pytest.fixture
def entreprise_a(db):
    from apps.core.models import Company
    return Company.objects.create(name='Entreprise A')


@pytest.fixture
def entreprise_b(db):
    from apps.core.models import Company
    return Company.objects.create(name='Entreprise B')


@pytest.fixture
def utilisateur(django_user_model):
    return django_user_model.objects.create_user(
        username='ouvrier', email='o@test.fr', password='motdepasse-test',
    )


@pytest.fixture
def chantier_a(entreprise_a):
    from apps.btp.models import BTPProject
    from apps.crm.models import Customer

    client = Customer.objects.create(company=entreprise_a, name='Client A')
    return BTPProject.objects.create(
        company=entreprise_a, code='CH-A', name='Chantier A', customer=client,
    )


@pytest.fixture
def chantier_b(entreprise_b):
    from apps.btp.models import BTPProject
    from apps.crm.models import Customer

    client = Customer.objects.create(company=entreprise_b, name='Client B')
    return BTPProject.objects.create(
        company=entreprise_b, code='CH-B', name='Chantier B', customer=client,
    )


@pytest.fixture
def connecte(client, utilisateur, entreprise_a, monkeypatch):
    """Session authentifiée, avec l'entreprise A pour entreprise active.

    L'entreprise active est posée par un intergiciel ; on la force ici pour
    éprouver les vues sans dépendre de son mécanisme de résolution.
    """
    client.force_login(utilisateur)

    from apps.mobile_web import views
    monkeypatch.setattr(views, '_entreprise', lambda requete: entreprise_a)
    return client


# ── Accès ────────────────────────────────────────────────────────────────────

def test_accueil_exige_une_connexion(client):
    reponse = client.get('/m/')
    assert reponse.status_code == 302
    assert '/m/' not in reponse.url


@pytest.mark.parametrize('adresse', ['/m/', '/m/photo/', '/m/serveurs/'])
def test_les_trois_pages_repondent(connecte, adresse):
    assert connecte.get(adresse).status_code == 200


def test_la_page_est_pensee_pour_le_telephone(connecte):
    """Sans viewport la page s'affiche en largeur de bureau, et un champ sous
    16px fait zoomer iOS a la mise au point."""
    corps = connecte.get('/m/').content.decode()
    assert 'width=device-width' in corps
    assert 'viewport-fit=cover' in corps
    assert 'font: 16px' in corps


def test_l_appareil_photo_s_ouvre_directement(connecte):
    """capture=environment ouvre l'appareil arriere sans passer par la
    galerie : c'est le geste attendu sur un chantier."""
    corps = connecte.get('/m/photo/').content.decode()
    assert 'capture="environment"' in corps
    assert 'accept="image/*"' in corps
    # La seconde entree, elle, doit permettre la galerie et le multiple.
    assert 'multiple' in corps


# ── Cloisonnement : la propriété centrale ───────────────────────────────────

def test_seuls_les_chantiers_de_l_entreprise_active_sont_proposes(
    connecte, chantier_a, chantier_b,
):
    """Une liste non filtrée exposerait les chantiers — et les clients —
    d'autres entreprises."""
    corps = connecte.get('/m/photo/').content.decode()
    assert 'Chantier A' in corps
    assert 'Chantier B' not in corps
    assert 'CH-B' not in corps


def test_un_chantier_forge_est_refuse(connecte, chantier_a, chantier_b):
    """Le champ vient du navigateur : une valeur forgée ne doit pas ranger la
    photo chez une autre entreprise."""
    from apps.btp.models import ProjectDocument

    reponse = connecte.post('/m/photo/', {
        'chantier': str(chantier_b.pk),
        'libelle': 'Tentative',
        'photos': _image(),
    })
    assert reponse.status_code == 200
    assert ProjectDocument.objects.filter(project=chantier_b).count() == 0

    # Deux barrieres, et la premiere suffit : les choix du champ sont
    # construits depuis l'entreprise active, donc le formulaire rejette la
    # valeur forgee avant meme la vue. La re-verification dans _enregistrer
    # reste en place comme seconde barriere, au cas ou ces choix viendraient
    # un jour d'ailleurs.
    assert reponse.context['form'].errors.get('chantier')


# ── Enregistrement des photos ───────────────────────────────────────────────

def test_photo_rangee_dans_le_chantier_choisi(connecte, chantier_a):
    """Dans le modèle que l'ERP affiche déjà : la photo apparaît là où on la
    cherche, sans écran supplémentaire."""
    from apps.btp.models import ProjectDocument

    reponse = connecte.post('/m/photo/', {
        'chantier': str(chantier_a.pk),
        'libelle': 'Fissure mur nord',
        'description': 'Vue rapprochee',
        'photos': _image(),
    })
    assert reponse.status_code == 302

    doc = ProjectDocument.objects.get(project=chantier_a)
    assert doc.doc_type == 'photo'
    assert doc.name == 'Fissure mur nord'
    assert doc.description == 'Vue rapprochee'
    assert doc.visible_to_client is False


def test_sans_chantier_la_photo_va_aux_documents_generaux(connecte, entreprise_a):
    from apps.documents.models import Document

    reponse = connecte.post('/m/photo/', {
        'chantier': '',
        'libelle': 'Vue generale',
        'photos': _image(),
    })
    assert reponse.status_code == 302

    doc = Document.objects.get(company=entreprise_a)
    assert doc.document_type == 'photo'
    assert doc.title == 'Vue generale'
    assert doc.file_size > 0


def test_visibilite_client_desactivee_par_defaut(connecte, chantier_a):
    """Une photo de chantier ne doit pas devenir visible sans décision."""
    from apps.btp.models import ProjectDocument

    connecte.post('/m/photo/', {
        'chantier': str(chantier_a.pk), 'photos': _image(),
    })
    assert ProjectDocument.objects.get(project=chantier_a).visible_to_client is False


def test_visibilite_client_activable(connecte, chantier_a):
    from apps.btp.models import ProjectDocument

    connecte.post('/m/photo/', {
        'chantier': str(chantier_a.pk), 'visible_client': 'on', 'photos': _image(),
    })
    assert ProjectDocument.objects.get(project=chantier_a).visible_to_client is True


def test_plusieurs_photos_sont_numerotees(connecte, chantier_a):
    from apps.btp.models import ProjectDocument

    connecte.post('/m/photo/', {
        'chantier': str(chantier_a.pk),
        'libelle': 'Facade',
        'photos': [_image('a.jpg'), _image('b.jpg'), _image('c.jpg')],
    })
    noms = sorted(ProjectDocument.objects.values_list('name', flat=True))
    assert noms == ['Facade (1/3)', 'Facade (2/3)', 'Facade (3/3)']


def test_sans_libelle_la_date_sert_de_nom(connecte, chantier_a):
    from apps.btp.models import ProjectDocument

    connecte.post('/m/photo/', {'chantier': str(chantier_a.pk), 'photos': _image()})
    assert ProjectDocument.objects.get().name.startswith('Photo du ')


def test_envoi_sans_photo_est_refuse(connecte, chantier_a):
    from apps.btp.models import ProjectDocument

    reponse = connecte.post('/m/photo/', {'chantier': str(chantier_a.pk), 'libelle': 'Vide'})
    assert reponse.status_code == 200
    assert ProjectDocument.objects.count() == 0
    assert 'Aucune photo' in reponse.content.decode()


def test_photo_trop_lourde_est_refusee(connecte, chantier_a):
    """Refus explicite plutôt qu'échec obscur à l'écriture."""
    from apps.btp.models import ProjectDocument

    enorme = SimpleUploadedFile(
        'enorme.jpg', b'0' * (13 * 1024 * 1024), content_type='image/jpeg',
    )
    reponse = connecte.post('/m/photo/', {
        'chantier': str(chantier_a.pk), 'photos': enorme,
    })
    assert reponse.status_code == 200
    assert ProjectDocument.objects.count() == 0
    assert '12 Mo' in reponse.content.decode()


def test_fichier_qui_n_est_pas_une_image_est_refuse(connecte, chantier_a):
    from apps.btp.models import ProjectDocument

    reponse = connecte.post('/m/photo/', {
        'chantier': str(chantier_a.pk),
        'photos': SimpleUploadedFile('note.pdf', b'%PDF-1.4', content_type='application/pdf'),
    })
    assert reponse.status_code == 200
    assert ProjectDocument.objects.count() == 0
    # Portion sans apostrophe : Django echappe les apostrophes des messages
    # en &#x27;, qu'aucune recherche litterale ne retrouve.
    assert 'pas une image' in reponse.content.decode()


def test_un_lot_est_refuse_en_entier_si_une_photo_est_invalide(connecte, chantier_a):
    """Tout ou rien : un lot a moitié enregistré laisse l'utilisateur sans
    moyen de savoir ce qui est passé."""
    from apps.btp.models import ProjectDocument

    connecte.post('/m/photo/', {
        'chantier': str(chantier_a.pk),
        'photos': [
            _image('bonne.jpg'),
            SimpleUploadedFile('mauvaise.txt', b'texte', content_type='text/plain'),
        ],
    })
    assert ProjectDocument.objects.count() == 0


def test_le_nombre_de_photos_est_borne(connecte, chantier_a):
    from apps.btp.models import ProjectDocument
    from apps.mobile_web.views import PHOTOS_MAX

    connecte.post('/m/photo/', {
        'chantier': str(chantier_a.pk),
        'photos': [_image(f'p{i}.jpg') for i in range(PHOTOS_MAX + 4)],
    })
    assert ProjectDocument.objects.count() == PHOTOS_MAX


def test_sans_entreprise_active_rien_n_est_enregistre(client, utilisateur, monkeypatch):
    from apps.documents.models import Document
    from apps.mobile_web import views

    client.force_login(utilisateur)
    monkeypatch.setattr(views, '_entreprise', lambda requete: None)

    reponse = client.post('/m/photo/', {'photos': _image()})
    assert reponse.status_code == 200
    assert Document.objects.count() == 0
    assert 'Aucune entreprise active' in reponse.content.decode()


# ── Choix du serveur ────────────────────────────────────────────────────────

def test_la_page_serveurs_liste_la_grappe(connecte):
    from apps.high_availability.models import OrionHANode

    OrionHANode.objects.create(
        node_id='serveur1', name='Serveur principal', priority=1,
        base_url='https://serveur1.exemple.fr', is_enabled=True,
        is_current_active=True,
    )
    OrionHANode.objects.create(
        node_id='serveur2', name='Serveur secours', priority=2,
        base_url='https://serveur2.exemple.fr', is_enabled=True,
    )

    corps = connecte.get('/m/serveurs/').content.decode()
    assert 'Serveur principal' in corps
    assert 'https://serveur2.exemple.fr' in corps


def test_un_serveur_sans_adresse_n_est_pas_propose(connecte):
    """Un lien vide mènerait nulle part sans rien expliquer."""
    from apps.high_availability.models import OrionHANode

    OrionHANode.objects.create(
        node_id='sans-adresse', name='Serveur muet', priority=3,
        base_url='', is_enabled=True,
    )
    assert 'Serveur muet' not in connecte.get('/m/serveurs/').content.decode()


def test_un_serveur_desactive_n_est_pas_propose(connecte):
    from apps.high_availability.models import OrionHANode

    OrionHANode.objects.create(
        node_id='hors-service', name='Serveur retire', priority=4,
        base_url='https://x.exemple.fr', is_enabled=False,
    )
    assert 'Serveur retire' not in connecte.get('/m/serveurs/').content.decode()


def test_aucune_redirection_n_est_emise_par_le_serveur(connecte):
    """L'adresse libre est gardée dans le navigateur et le lien construit côté
    client : l'ERP ne peut donc pas servir de redirection ouverte."""
    corps = connecte.get('/m/serveurs/').content.decode()
    assert 'localStorage' in corps
    # Seuls http et https sont ouverts : une adresse javascript: ne doit pas
    # pouvoir être déclenchée depuis ce bouton.
    assert "url.protocol !== 'http:'" in corps


# ── Decouvrabilite dans le menu ─────────────────────────────────────────────

def test_l_entree_de_menu_est_visible_des_non_administrateurs(db):
    """Placee d'abord dans le module Super Admin, l'entree restait invisible
    pour les chefs de chantier -- ceux qui ont justement besoin de la page
    photo."""
    from apps.core.context_processors import NAV_MODULES
    from apps.private_saas.permissions import filter_nav_modules

    class Simple:
        is_superuser = False

    def hote(modules):
        for module in modules:
            for entree in module.get('children') or []:
                if entree.get('url_name') == 'mobile_web:accueil':
                    return module['id']
        return None

    assert hote(NAV_MODULES) == 'dashboard'
    assert hote(filter_nav_modules(NAV_MODULES, None, user=Simple())) == 'dashboard'


def test_le_module_hote_est_toujours_affiche():
    """« dashboard » figure dans always_show : l'entree ne depend donc d'aucun
    module active pour l'entreprise."""
    from apps.private_saas.permissions import filter_nav_modules
    import inspect

    source = inspect.getsource(filter_nav_modules)
    assert "'dashboard'" in source
    assert 'always_show' in source


# ── Installation sur le telephone ───────────────────────────────────────────
# Ce qui transforme trois pages en application : un manifeste et un agent de
# service. Les erreurs y sont invisibles depuis un telephone, d'ou ces
# verifications.

import json


def test_le_manifeste_est_servi(client):
    """Sans manifeste, aucun navigateur ne propose l'installation."""
    reponse = client.get('/m/manifest.webmanifest')
    assert reponse.status_code == 200

    data = json.loads(reponse.content)
    assert data['name']
    assert data['display'] == 'standalone'
    assert data['start_url'] == '/m/'


def test_la_portee_du_manifeste_se_limite_a_la_version_telephone(client):
    """Une portee sur « / » piegerait l'utilisateur en plein ecran dans tout
    l'ERP, sans barre de navigateur pour en sortir."""
    data = json.loads(client.get('/m/manifest.webmanifest').content)
    assert data['scope'] == '/m/'


def test_le_manifeste_declare_les_deux_tailles_exigees(client):
    """192 et 512 : sans elles, l'installation est refusee."""
    data = json.loads(client.get('/m/manifest.webmanifest').content)
    tailles = {icone['sizes'] for icone in data['icons']}
    assert '192x192' in tailles
    assert '512x512' in tailles


def test_le_manifeste_declare_une_icone_recadrable(client):
    """Android recadre l'icone selon le lanceur ; sans « maskable » elle est
    posee dans un carre blanc."""
    data = json.loads(client.get('/m/manifest.webmanifest').content)
    assert any(i.get('purpose') == 'maskable' for i in data['icons'])


def test_les_icones_existent_reellement(client):
    """Un manifeste qui pointe vers une icone absente fait echouer
    l'installation sans rien expliquer."""
    from pathlib import Path

    from django.conf import settings

    for nom in ('orion-192.png', 'orion-512.png', 'orion-maskable-512.png'):
        chemin = Path(settings.BASE_DIR) / 'static' / 'mobile_web' / 'icons' / nom
        assert chemin.is_file(), f'icone absente : {nom}'
        assert chemin.stat().st_size > 500


def test_l_agent_de_service_est_servi_en_javascript(client):
    reponse = client.get('/m/sw.js')
    assert reponse.status_code == 200
    assert 'javascript' in reponse['Content-Type']


def test_l_agent_de_service_n_est_jamais_mis_en_cache(client):
    """C'est ce fichier qui decide de tout le reste : une version figee dans
    le navigateur empecherait toute correction."""
    reponse = client.get('/m/sw.js')
    assert 'no-store' in reponse['Cache-Control']


def test_l_agent_de_service_ne_met_pas_les_envois_en_cache(client):
    """Un POST mis en cache serait une photo perdue, ou envoyee deux fois."""
    code = client.get('/m/sw.js').content.decode()
    assert "requete.method !== 'GET'" in code


def test_l_agent_de_service_laisse_l_erp_complet_au_reseau(client):
    """Les pages de l'ERP dependent de donnees qui changent : les servir
    depuis un cache afficherait des chiffres perimes."""
    code = client.get('/m/sw.js').content.decode()
    assert "startsWith('/m/')" in code
    assert 'if (!dansPortee && !estStatique) { return; }' in code


def test_l_agent_de_service_prefere_le_reseau_pour_les_pages(client):
    """Reseau d'abord, cache en filet : une liste de chantiers servie depuis
    le cache serait perimee et trompeuse."""
    code = client.get('/m/sw.js').content.decode()
    # Le fetch precede le recours au cache dans la branche des pages.
    assert code.index('fetch(requete)') < code.index("caches.match('/m/hors-ligne/')")


def test_la_page_hors_ligne_repond(client):
    reponse = client.get('/m/hors-ligne/')
    assert reponse.status_code == 200
    assert 'Hors ligne' in reponse.content.decode()


def test_la_page_hors_ligne_ne_promet_pas_de_garder_les_photos(client):
    """Promettre une file d'attente hors ligne qui n'existe pas ferait perdre
    des photos en silence."""
    corps = client.get('/m/hors-ligne/').content.decode()
    assert 'pas conserv' in corps


def test_ios_recoit_ce_qu_il_exige(connecte):
    """iOS ne lit le manifeste que partiellement : sans apple-touch-icon
    l'icone est une capture floue de la page."""
    corps = connecte.get('/m/').content.decode()
    assert 'rel="apple-touch-icon"' in corps
    assert 'apple-mobile-web-app-capable' in corps
    assert 'rel="manifest"' in corps


def test_l_agent_de_service_est_enregistre_depuis_la_page(connecte):
    corps = connecte.get('/m/').content.decode()
    assert 'serviceWorker' in corps
    assert '/m/sw.js' in corps
