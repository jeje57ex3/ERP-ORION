"""File d'attente des photos prises hors ligne.

Un chantier n'a pas toujours de réseau. Sans file, la photo prise dans un
sous-sol était perdue : le formulaire échouait, et la seule façon de la
renvoyer était de la reprendre — ce qui suppose d'être encore devant le sujet.

La propriété la plus délicate n'est pas la mise en file, c'est l'**absence de
doublon**. La file ne peut pas savoir si une coupure est survenue avant ou
APRÈS l'enregistrement côté serveur : une réponse perdue — le cas banal sur un
chantier — laisse la photo enregistrée et la file persuadée du contraire. Elle
la renverrait alors, et le chantier aurait deux fois la même photo,
précisément dans la situation de réseau instable qui justifie la file.

D'où la clé d'envoi éprouvée ici. Le reste — JSON pour la file, HTML pour le
formulaire, refus définitif distingué d'une panne passagère — existe pour que
le navigateur sache quoi faire de chaque réponse.
"""

import io
import os

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile

pytestmark = pytest.mark.django_db


def _image(nom='photo.jpg', octets=2048, type_mime='image/jpeg'):
    return SimpleUploadedFile(
        nom, b'\xff\xd8\xff' + b'0' * octets, content_type=type_mime)


@pytest.fixture
def entreprise_a(db):
    from apps.core.models import Company
    return Company.objects.create(name='Entreprise A')


@pytest.fixture
def utilisateur(django_user_model):
    return django_user_model.objects.create_user(
        username='ouvrier', email='o@test.fr', password='motdepasse-test',
    )


@pytest.fixture
def connecte(client, utilisateur, entreprise_a, monkeypatch):
    client.force_login(utilisateur)
    from apps.mobile_web import views
    monkeypatch.setattr(views, '_entreprise', lambda requete: entreprise_a)
    return client


def _envoyer(client, cle=None, fichiers=None, depuis_la_file=False, **extra):
    donnees = {'libelle': 'Mur nord'}
    donnees.update(extra)
    if cle is not None:
        donnees['cle_envoi'] = cle
    donnees['photos'] = fichiers if fichiers is not None else [_image()]

    entetes = {}
    if depuis_la_file:
        entetes['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
    return client.post('/m/photo/', donnees, **entetes)


def _nb_documents():
    from apps.documents.models import Document
    return Document.objects.count()


# ── Absence de doublon ───────────────────────────────────────────────────────

def test_une_cle_deja_recue_n_enregistre_pas_une_seconde_fois(connecte):
    """Le cas réel : la photo est passée, la réponse s'est perdue, la file
    renvoie."""
    premier = _envoyer(connecte, cle='cle-abc', depuis_la_file=True)
    assert premier.status_code == 200, premier.content
    assert premier.json()['statut'] == 'enregistre'
    apres_le_premier = _nb_documents()
    assert apres_le_premier == 1

    second = _envoyer(connecte, cle='cle-abc', depuis_la_file=True)
    assert second.status_code == 200
    assert second.json()['statut'] == 'deja_recu'
    assert _nb_documents() == apres_le_premier, 'photo enregistrée deux fois'


def test_la_cle_est_retenue_en_base(connecte):
    from apps.mobile_web.models import EnvoiPhotoMobile

    _envoyer(connecte, cle='cle-xyz', depuis_la_file=True)
    envoi = EnvoiPhotoMobile.objects.get(cle='cle-xyz')
    assert envoi.photos == 1
    assert envoi.company is not None


def test_deux_cles_distinctes_enregistrent_deux_fois(connecte):
    """Le garde-fou ne doit pas confondre deux envois différents."""
    _envoyer(connecte, cle='cle-1', depuis_la_file=True)
    _envoyer(connecte, cle='cle-2', depuis_la_file=True)
    assert _nb_documents() == 2


def test_un_envoi_sans_cle_reste_possible(connecte):
    """Le formulaire normal n'en fournit pas : il ne doit pas être bloqué."""
    reponse = _envoyer(connecte)
    assert reponse.status_code == 302
    assert _nb_documents() == 1


def test_une_cle_deja_recue_depuis_le_formulaire_redirige_sans_doublon(connecte):
    """Même protection hors de la file, par exemple sur un double envoi."""
    _envoyer(connecte, cle='cle-form')
    reponse = _envoyer(connecte, cle='cle-form')
    assert reponse.status_code == 302
    assert _nb_documents() == 1


# ── Réponses exploitables par la file ────────────────────────────────────────

def test_la_file_recoit_du_json_et_non_une_page(connecte):
    reponse = _envoyer(connecte, cle='cle-json', depuis_la_file=True)
    assert reponse['Content-Type'].startswith('application/json')
    assert reponse.json()['photos'] == 1


def test_un_refus_est_annonce_en_422_et_non_en_200(connecte):
    """La file doit distinguer un refus DÉFINITIF d'une panne de réseau : le
    réessayer indéfiniment ne le ferait pas passer, et bloquerait la suite."""
    reponse = _envoyer(connecte, cle='cle-vide', fichiers=[],
                       depuis_la_file=True)
    assert reponse.status_code == 422, reponse.content
    donnees = reponse.json()
    assert donnees['statut'] == 'refuse'
    assert donnees['erreurs'], 'un refus sans motif est inexploitable'


def test_un_chantier_d_une_autre_entreprise_est_refuse(connecte, db):
    """Cloisonnement : un identifiant forgé ne doit pas ranger la photo chez
    un tiers — et la file doit le savoir définitivement."""
    from apps.btp.models import BTPProject
    from apps.core.models import Company
    from apps.crm.models import Customer

    autre = Company.objects.create(name='Entreprise B')
    client_autre = Customer.objects.create(company=autre, name='Client B')
    chantier_autre = BTPProject.objects.create(
        company=autre, code='CH-B', name='Chantier B', customer=client_autre,
    )

    reponse = _envoyer(connecte, cle='cle-fuite', depuis_la_file=True,
                       chantier=str(chantier_autre.pk))
    assert reponse.status_code == 422, reponse.content
    from apps.btp.models import ProjectDocument
    assert ProjectDocument.objects.filter(project=chantier_autre).count() == 0
    # Et le motif doit NOMMER le champ en cause. Le refus vient ici de la
    # validation du formulaire, dont le message brut — « Sélectionnez un choix
    # valide » — ne dit pas de quoi il parle. Sur un téléphone, et plus encore
    # dans la file qui n'affiche qu'une ligne, c'est le nom du champ qui
    # permet de corriger.
    motifs = ' '.join(reponse.json()['erreurs']).lower()
    assert 'chantier' in motifs, reponse.json()


def test_un_envoi_sans_entreprise_active_est_refuse(client, utilisateur,
                                                    monkeypatch):
    client.force_login(utilisateur)
    from apps.mobile_web import views
    monkeypatch.setattr(views, '_entreprise', lambda requete: None)

    reponse = _envoyer(client, cle='cle-sans-entreprise', depuis_la_file=True)
    assert reponse.status_code == 422
    assert 'entreprise' in ' '.join(reponse.json()['erreurs']).lower()


# ── Le code du navigateur ────────────────────────────────────────────────────
# Il n'est pas exécutable ici, mais trois de ses propriétés se vérifient, et
# chacune correspond à une façon de perdre ou de dupliquer une photo.

def _fichier_js():
    chemin = os.path.join(
        settings.BASE_DIR, 'static', 'js', 'orion-file-photos.js')
    with io.open(chemin, encoding='utf-8') as fichier:
        return fichier.read()


def test_la_file_du_navigateur_envoie_une_cle():
    """Sans elle, aucune protection contre les doublons ne peut exister."""
    code = _fichier_js()
    assert "append('cle_envoi'" in code
    assert 'randomUUID' in code


def test_la_file_utilise_indexeddb_et_non_localstorage():
    """localStorage ne stocke que du texte : encoder des images en base64 y
    dépasserait la limite (~5 Mo) dès la deuxième photo."""
    code = _fichier_js()
    assert 'indexedDB' in code
    appels = [
        ligne.strip() for ligne in code.splitlines()
        if 'localStorage.' in ligne and not ligne.strip().startswith(('*', '//', '/*'))
    ]
    assert appels == [], 'appel a localStorage subsistant : %s' % appels


def test_un_refus_definitif_sort_de_la_file():
    """Un envoi refusé par le serveur et réessayé sans fin bloquerait tous les
    suivants."""
    code = _fichier_js()
    assert 'reponse.status === 422' in code
    assert 'retirer' in code


def test_le_jeton_csrf_est_relu_au_moment_du_renvoi():
    """Un jeton capturé au dépôt serait périmé après renouvellement de session,
    et l'envoi échouerait en 403 sans raison visible."""
    code = _fichier_js()
    assert "lireCookie('csrftoken')" in code


def test_la_page_photo_charge_la_file():
    chemin = os.path.join(
        settings.BASE_DIR, 'apps', 'mobile_web', 'templates', 'mobile_web',
        'photo.html')
    with io.open(chemin, encoding='utf-8') as fichier:
        gabarit = fichier.read()
    assert 'orion-file-photos.js' in gabarit
    # L'apostrophe de « l'ERP » fermerait la chaîne JavaScript après rendu :
    # tout le script de la file serait muet.
    assert "'{% trans \"Enregistrer dans l'ERP\" %}'" not in gabarit
    assert 'escapejs' in gabarit
