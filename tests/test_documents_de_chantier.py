"""« Les factures des chantiers apparaissent dans l'onglet Documents ; je veux
qu'elles aillent dans les documents du chantier. »

POURQUOI ELLES FINISSAIENT LÀ

`ProjectDocument` existe depuis longtemps, avec dix-huit types de documents,
une visibilité client, des versions et un marqueur « obligatoire ». Mais
AUCUN écran ne le servait : ni liste, ni dépôt, ni téléchargement, ni même
une route. Seul l'envoi de photos depuis le téléphone y écrivait.

Le module Documents général était donc le seul endroit offrant un bouton.
Les factures d'un chantier s'y accumulaient, mêlées aux pièces de
l'entreprise, sans lien avec le chantier auquel elles appartiennent.

Le modèle était là, le dossier était là ; il manquait la porte.

CE QU'ON NE FAIT PAS

On n'ajoute PAS un lien « chantier » au modèle Document. Il ferait doublon
avec ProjectDocument, qui porte déjà bien davantage — et deux modèles pour
la même chose finissent toujours par diverger. On route vers celui qui
existe.
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse


@pytest.fixture
def chantier(db, client, django_user_model):
    from apps.accounts.models import UserProfile
    from apps.btp.models import BTPProject
    from apps.core.models import Company
    from apps.crm.models import Customer
    from apps.private_saas.models import ALL_MODULE_CODES, CompanyModule

    entreprise = Company.objects.create(name='Martin SA', slug='martin-sa')
    for code in ALL_MODULE_CODES:
        CompanyModule.objects.update_or_create(
            company=entreprise, module_code=code, defaults={'is_enabled': True})

    personne = django_user_model.objects.create_user(
        'chef', password='x', is_superuser=True, is_staff=True)
    profil, _ = UserProfile.objects.get_or_create(user=personne)
    profil.role = 'superadmin'
    profil.save()
    profil.companies.add(entreprise)
    client.force_login(django_user_model.objects.get(pk=personne.pk))
    session = client.session
    session['current_company_id'] = entreprise.pk
    session.save()

    acheteur = Customer.objects.create(company=entreprise, name='Client')
    projet = BTPProject.objects.create(
        company=entreprise, name='Rénovation Metz', customer=acheteur)

    return {'client': client, 'entreprise': entreprise, 'projet': projet,
            'utilisateur': personne}


def _facture(nom='facture.pdf'):
    return SimpleUploadedFile(nom, b'%PDF-1.4 fausse facture',
                              content_type='application/pdf')


# ── 1. L'écran qui manquait ──────────────────────────────────────────────────

@pytest.mark.django_db
def test_le_chantier_a_desormais_un_ecran_de_documents(chantier):
    reponse = chantier['client'].get(
        reverse('btp:project_documents',
                kwargs={'project_pk': chantier['projet'].pk}))

    assert reponse.status_code == 200


@pytest.mark.django_db
def test_une_facture_se_depose_sur_le_chantier(chantier):
    """LA DEMANDE, dans sa forme la plus directe."""
    from apps.btp.models import ProjectDocument

    reponse = chantier['client'].post(
        reverse('btp:project_documents',
                kwargs={'project_pk': chantier['projet'].pk}),
        {'file': _facture(), 'doc_type': 'invoice',
         'name': 'Facture Leroy Merlin', 'description': ''})

    assert reponse.status_code == 302
    document = ProjectDocument.objects.get(project=chantier['projet'])
    assert document.doc_type == 'invoice'
    assert document.name == 'Facture Leroy Merlin'


@pytest.mark.django_db
def test_un_depot_sans_fichier_le_dit(chantier):
    """Un formulaire qui se recharge sans rien dire est lu comme une panne.
    Ce defaut s'est deja produit trois fois dans cet ERP."""
    reponse = chantier['client'].post(
        reverse('btp:project_documents',
                kwargs={'project_pk': chantier['projet'].pk}),
        {'doc_type': 'invoice', 'name': 'Sans fichier'})

    assert reponse.status_code == 200
    messages = [str(m) for m in reponse.context['messages']]
    assert any('fichier' in m.lower() for m in messages), messages


@pytest.mark.django_db
def test_le_nom_du_fichier_sert_de_libelle_par_defaut(chantier):
    """Exiger une saisie pour deposer une facture deja nommee serait une
    friction sans contrepartie."""
    from apps.btp.models import ProjectDocument

    chantier['client'].post(
        reverse('btp:project_documents',
                kwargs={'project_pk': chantier['projet'].pk}),
        {'file': _facture('FA-2026-0042.pdf'), 'doc_type': 'invoice',
         'name': ''})

    assert ProjectDocument.objects.get(
        project=chantier['projet']).name == 'FA-2026-0042.pdf'


@pytest.mark.django_db
def test_le_telechargement_est_borne_a_l_entreprise(chantier, django_user_model):
    """Une facture de chantier porte des prix et un nom de client : elle
    n'a pas a etre lisible depuis une autre entreprise."""
    from apps.accounts.models import UserProfile
    from apps.btp.models import ProjectDocument
    from apps.core.models import Company

    document = ProjectDocument.objects.create(
        project=chantier['projet'], doc_type='invoice', name='Facture',
        file=_facture(), added_by=chantier['utilisateur'])

    autre = Company.objects.create(name='Autre SA', slug='autre-sa')
    espion = django_user_model.objects.create_user(
        'espion', password='x', is_staff=True)
    profil, _ = UserProfile.objects.get_or_create(user=espion)
    profil.companies.add(autre)
    profil.save()

    client = chantier['client']
    client.force_login(django_user_model.objects.get(pk=espion.pk))
    session = client.session
    session['current_company_id'] = autre.pk
    session.save()

    reponse = client.get(
        reverse('btp:project_document_download', kwargs={'pk': document.pk}))

    assert reponse.status_code == 404


# ── 2. Le rattachement depuis le module Documents ────────────────────────────

@pytest.mark.django_db
def test_le_formulaire_general_propose_un_chantier(chantier):
    contenu = chantier['client'].get(
        reverse('documents:document_create')).content.decode()

    assert 'name="chantier"' in contenu
    assert 'Rénovation Metz' in contenu


@pytest.mark.django_db
def test_un_document_avec_chantier_part_au_chantier(chantier):
    """LE CŒUR DE LA DEMANDE : il ne doit PAS rester dans la liste
    generale."""
    from apps.btp.models import ProjectDocument
    from apps.documents.models import Document

    reponse = chantier['client'].post(reverse('documents:document_create'), {
        'title': 'Facture Point P', 'document_type': 'invoice',
        'description': '', 'version': '1.0', 'tags': '',
        'chantier': chantier['projet'].pk, 'file': _facture(),
    })

    assert reponse.status_code == 302
    assert ProjectDocument.objects.filter(
        project=chantier['projet'], name='Facture Point P').exists()
    assert not Document.objects.filter(title='Facture Point P').exists(), (
        'le document est reste dans la liste generale — c’est le defaut '
        'rapporte')


@pytest.mark.django_db
def test_le_type_facture_est_conserve_a_la_traversee(chantier):
    """Les deux listes de types ne se recouvrent pas tout a fait. « Facture »
    y figure des deux cotes et doit survivre au passage."""
    from apps.btp.models import ProjectDocument

    chantier['client'].post(reverse('documents:document_create'), {
        'title': 'Facture', 'document_type': 'invoice', 'description': '',
        'version': '1.0', 'tags': '', 'chantier': chantier['projet'].pk,
        'file': _facture(),
    })

    assert ProjectDocument.objects.get(
        project=chantier['projet']).doc_type == 'invoice'


@pytest.mark.django_db
def test_un_type_sans_equivalent_ne_fait_pas_echouer_le_depot(chantier):
    """« Rapport » n'existe pas tel quel cote chantier. Mieux vaut un type
    approximatif qu'un enregistrement refuse pour un libelle absent."""
    from apps.btp.models import ProjectDocument

    reponse = chantier['client'].post(reverse('documents:document_create'), {
        'title': 'Rapport de visite', 'document_type': 'report',
        'description': '', 'version': '1.0', 'tags': '',
        'chantier': chantier['projet'].pk, 'file': _facture('r.pdf'),
    })

    assert reponse.status_code == 302
    assert ProjectDocument.objects.filter(project=chantier['projet']).exists()


@pytest.mark.django_db
def test_sans_chantier_le_document_reste_dans_l_entreprise(chantier):
    """On ne detourne QUE ce qui designe un chantier : la plupart des
    documents d'une entreprise n'en relevent pas."""
    from apps.btp.models import ProjectDocument
    from apps.documents.models import Document

    chantier['client'].post(reverse('documents:document_create'), {
        'title': 'Statuts de la société', 'document_type': 'contract',
        'description': '', 'version': '1.0', 'tags': '', 'chantier': '',
        'file': _facture('statuts.pdf'),
    })

    assert Document.objects.filter(title='Statuts de la société').exists()
    assert not ProjectDocument.objects.filter(
        project=chantier['projet']).exists()


@pytest.mark.django_db
def test_un_chantier_d_une_autre_entreprise_n_est_pas_proposable(chantier):
    """Le champ vient du navigateur : une valeur forgee ne doit pas
    atteindre le chantier d'une autre entreprise."""
    from apps.btp.models import BTPProject, ProjectDocument
    from apps.core.models import Company
    from apps.crm.models import Customer

    autre = Company.objects.create(name='Autre SA', slug='autre-sa')
    ailleurs = BTPProject.objects.create(
        company=autre, name='Chantier voisin',
        customer=Customer.objects.create(company=autre, name='Client voisin'))

    reponse = chantier['client'].post(reverse('documents:document_create'), {
        'title': 'Facture volée', 'document_type': 'invoice',
        'description': '', 'version': '1.0', 'tags': '',
        'chantier': ailleurs.pk, 'file': _facture(),
    })

    assert reponse.status_code == 200, 'le formulaire aurait du refuser'
    assert not ProjectDocument.objects.filter(project=ailleurs).exists()
