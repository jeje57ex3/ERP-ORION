"""Supprimer une demande de devis guidée.

Supprimer une demande n'est pas supprimer une ligne. Mesure faite, la
cascade emporte quatre choses :

- `btp.GuidedQuotePhoto` — les photos envoyées par le client
- `btp.GuidedQuoteDocument` — les documents qu'il a joints
- `btp.GuidedQuoteEstimate` — le pré-devis, et ses lignes
- `configurator.ConfiguratorSubmission` — sa saisie d'origine

Ce sont des pièces que le client a fournies et qu'il ne renverra pas.

**En revanche le devis et le chantier survivent.** La clé étrangère est
portée par la demande, pas l'inverse : `btp_quote` et `btp_project` sont
des champs *de* `GuidedQuoteRequest`. On perd donc la traçabilité — pourquoi
ce devis a été établi, et sur quelles photos — pas le travail. L'écran le
dit, parce que croire qu'on va détruire un chantier retiendrait d'une
suppression inoffensive, et croire l'inverse serait pire.

D'où l'archivage, proposé avant et à portée égale : le statut `archived`
existait déjà dans le modèle et n'avait **aucun bouton**. Il sort la demande
des listes actives sans rien détruire.
"""

from datetime import date

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.accounts.models import UserProfile
from apps.btp.models import (
    GuidedQuoteDocument,
    GuidedQuoteEstimate,
    GuidedQuotePhoto,
    GuidedQuoteRequest,
)

pytestmark = pytest.mark.django_db


# ── Terrain ─────────────────────────────────────────────────────────────────

@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Dupont SA', slug='dupont-sa')


@pytest.fixture
def autre_entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Martin SA', slug='martin-sa')


def creer_compte(nom, company, role='admin'):
    utilisateur = User.objects.create_user(username=nom, password='x')
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.role = role
    profil.save()
    profil.companies.add(company)
    # Relecture : le signal qui crée le profil le met en cache sur l'objet
    # User avec son rôle d'origine.
    return User.objects.get(pk=utilisateur.pk)


@pytest.fixture
def agent(entreprise):
    return creer_compte('agent', entreprise)


def creer_demande(company, statut='new', reference='DG-001'):
    return GuidedQuoteRequest.objects.create(
        company=company, reference=reference, request_type='travaux',
        status=statut, client_first_name='Paul', client_last_name='Martin',
        client_email='paul.martin@exemple.fr')


def image_minimale():
    """Un GIF d'un pixel : le plus petit fichier image valide.

    Un ImageField valide le contenu, donc des octets quelconques seraient
    refusés — et le test échouerait sur la fixture plutôt que sur ce qu'il
    mesure.
    """
    octets = (b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff'
              b'!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01'
              b'\x00\x00\x02\x02D\x01\x00;')
    return SimpleUploadedFile('photo.gif', octets, content_type='image/gif')


# ── 1. L'archivage, l'opération à préférer ──────────────────────────────────

def test_l_archivage_ne_detruit_rien(client, agent, entreprise):
    """Le statut existait déjà dans le modèle et n'avait aucun bouton."""
    demande = creer_demande(entreprise)
    GuidedQuotePhoto.objects.create(request=demande, photo=image_minimale())

    client.force_login(agent)
    client.post(reverse('btp:guided_quote_archive', args=[demande.pk]))

    demande.refresh_from_db()
    assert demande.status == 'archived'
    assert GuidedQuotePhoto.objects.filter(request=demande).count() == 1


def test_archiver_deux_fois_est_sans_effet(client, agent, entreprise):
    demande = creer_demande(entreprise, statut='archived')
    client.force_login(agent)
    reponse = client.post(reverse('btp:guided_quote_archive',
                                  args=[demande.pk]), follow=True)
    assert 'déjà archivée' in reponse.content.decode()


def test_l_archivage_exige_un_post(client, agent, entreprise):
    """Un GET qui modifie l'état se déclenche au survol d'un lien, à
    l'indexation, ou au passage d'un antivirus qui suit les liens."""
    demande = creer_demande(entreprise)
    client.force_login(agent)
    assert client.get(reverse('btp:guided_quote_archive',
                              args=[demande.pk])).status_code == 405
    demande.refresh_from_db()
    assert demande.status == 'new'


def test_l_archivage_d_une_autre_entreprise_est_introuvable(
        client, agent, autre_entreprise):
    demande = creer_demande(autre_entreprise)
    client.force_login(agent)
    assert client.post(reverse('btp:guided_quote_archive',
                               args=[demande.pk])).status_code == 404
    demande.refresh_from_db()
    assert demande.status == 'new'


# ── 2. La page de confirmation ──────────────────────────────────────────────

def test_la_confirmation_ne_supprime_pas(client, agent, entreprise):
    """GET affiche, POST agit.

    Un GET destructeur se déclenche sans intention : c'est la raison pour
    laquelle la suppression n'est pas un simple lien.
    """
    demande = creer_demande(entreprise)
    client.force_login(agent)
    reponse = client.get(reverse('btp:guided_quote_delete',
                                 args=[demande.pk]))
    assert reponse.status_code == 200
    assert GuidedQuoteRequest.objects.filter(pk=demande.pk).exists()


def test_la_confirmation_dresse_l_inventaire(client, agent, entreprise):
    """Les nombres exacts, pas une mise en garde générique."""
    demande = creer_demande(entreprise)
    GuidedQuotePhoto.objects.create(request=demande, photo=image_minimale())
    GuidedQuotePhoto.objects.create(request=demande, photo=image_minimale())
    GuidedQuoteDocument.objects.create(
        request=demande,
        file=SimpleUploadedFile('plan.pdf', b'%PDF-1.4',
                                content_type='application/pdf'))

    client.force_login(agent)
    reponse = client.get(reverse('btp:guided_quote_delete',
                                 args=[demande.pk]))
    inventaire = reponse.context['inventaire']
    par_label = {ligne['label']: ligne['total']
                 for ligne in inventaire['lignes']}
    assert par_label['btp.GuidedQuotePhoto'] == 2
    assert par_label['btp.GuidedQuoteDocument'] == 1
    assert inventaire['total'] == 3


def test_l_inventaire_ne_compte_pas_la_demande_elle_meme(client, agent,
                                                          entreprise):
    """Elle n'est pas une perte collatérale, c'est l'objet de l'acte.

    La compter annoncerait « 1 élément lié » pour une demande qui ne porte
    rien.
    """
    demande = creer_demande(entreprise)
    client.force_login(agent)
    reponse = client.get(reverse('btp:guided_quote_delete',
                                 args=[demande.pk]))
    labels = [ligne['label'] for ligne in reponse.context['inventaire']['lignes']]
    assert 'btp.GuidedQuoteRequest' not in labels
    assert reponse.context['inventaire']['total'] == 0


def test_la_confirmation_propose_l_archivage(client, agent, entreprise):
    demande = creer_demande(entreprise)
    client.force_login(agent)
    corps = client.get(reverse('btp:guided_quote_delete',
                               args=[demande.pk])).content.decode()
    assert reverse('btp:guided_quote_archive', args=[demande.pk]) in corps
    assert 'Archiver' in corps


def test_la_confirmation_dit_que_le_devis_survit(client, agent, entreprise):
    """Croire qu'on va détruire un chantier retiendrait d'une suppression
    inoffensive ; croire l'inverse serait pire.

    La clé est portée par la demande : le devis et le chantier ne sont pas
    touchés, et l'écran l'écrit.
    """
    from apps.btp.models import BTPQuote
    from apps.crm.models import Customer

    demande = creer_demande(entreprise)
    client_crm = Customer.objects.create(company=entreprise, name='Client A')
    devis = BTPQuote.objects.create(
        company=entreprise, customer=client_crm, number='DV-77')
    demande.btp_quote = devis
    demande.save()

    client.force_login(agent)
    corps = client.get(reverse('btp:guided_quote_delete',
                               args=[demande.pk])).content.decode()
    assert 'DV-77' in corps
    assert 'pas' in corps and 'supprim' in corps


# ── 3. La suppression ───────────────────────────────────────────────────────

def test_la_suppression_emporte_les_pieces_du_client(client, agent,
                                                      entreprise):
    demande = creer_demande(entreprise)
    GuidedQuotePhoto.objects.create(request=demande, photo=image_minimale())
    GuidedQuoteDocument.objects.create(
        request=demande,
        file=SimpleUploadedFile('plan.pdf', b'%PDF-1.4',
                                content_type='application/pdf'))
    GuidedQuoteEstimate.objects.create(request=demande)

    client.force_login(agent)
    reponse = client.post(reverse('btp:guided_quote_delete',
                                  args=[demande.pk]), follow=True)
    assert reponse.status_code == 200
    assert not GuidedQuoteRequest.objects.filter(pk=demande.pk).exists()
    assert GuidedQuotePhoto.objects.count() == 0
    assert GuidedQuoteDocument.objects.count() == 0
    assert GuidedQuoteEstimate.objects.count() == 0


def test_le_devis_et_le_chantier_survivent_a_la_suppression(client, agent,
                                                             entreprise):
    """La propriété que l'écran annonce doit être vraie.

    Un avertissement qui se trompe est pire que pas d'avertissement.
    """
    from apps.btp.models import BTPProject, BTPQuote
    from apps.crm.models import Customer

    client_crm = Customer.objects.create(company=entreprise, name='Client A')
    devis = BTPQuote.objects.create(
        company=entreprise, customer=client_crm, number='DV-77')
    chantier = BTPProject.objects.create(
        company=entreprise, name='Chantier A', customer=client_crm)

    demande = creer_demande(entreprise)
    demande.btp_quote = devis
    demande.btp_project = chantier
    demande.save()

    client.force_login(agent)
    client.post(reverse('btp:guided_quote_delete', args=[demande.pk]))

    assert not GuidedQuoteRequest.objects.filter(pk=demande.pk).exists()
    assert BTPQuote.objects.filter(pk=devis.pk).exists()
    assert BTPProject.objects.filter(pk=chantier.pk).exists()


def test_une_demande_d_une_autre_entreprise_est_introuvable(
        client, agent, autre_entreprise):
    """404 et non 403 : l'existence de la demande ne doit pas se déduire."""
    demande = creer_demande(autre_entreprise)
    client.force_login(agent)
    assert client.get(reverse('btp:guided_quote_delete',
                              args=[demande.pk])).status_code == 404
    assert client.post(reverse('btp:guided_quote_delete',
                               args=[demande.pk])).status_code == 404
    assert GuidedQuoteRequest.objects.filter(pk=demande.pk).exists()


def test_la_suppression_ne_touche_pas_les_autres_demandes(client, agent,
                                                           entreprise):
    cible = creer_demande(entreprise, reference='DG-001')
    voisine = creer_demande(entreprise, reference='DG-002')
    GuidedQuotePhoto.objects.create(request=voisine, photo=image_minimale())

    client.force_login(agent)
    client.post(reverse('btp:guided_quote_delete', args=[cible.pk]))

    assert GuidedQuoteRequest.objects.filter(pk=voisine.pk).exists()
    assert GuidedQuotePhoto.objects.filter(request=voisine).count() == 1


def test_un_anonyme_ne_supprime_rien(client, entreprise):
    demande = creer_demande(entreprise)
    reponse = client.post(reverse('btp:guided_quote_delete',
                                  args=[demande.pk]))
    assert reponse.status_code in (301, 302)
    assert GuidedQuoteRequest.objects.filter(pk=demande.pk).exists()


# ── 4. Les boutons dans les écrans ──────────────────────────────────────────

def test_la_liste_porte_les_deux_boutons(client, agent, entreprise):
    demande = creer_demande(entreprise)
    client.force_login(agent)
    corps = client.get(reverse('btp:guided_quote_list')).content.decode()
    assert reverse('btp:guided_quote_delete', args=[demande.pk]) in corps
    assert reverse('btp:guided_quote_archive', args=[demande.pk]) in corps


def test_la_liste_n_archive_pas_une_demande_deja_archivee(client, agent,
                                                           entreprise):
    """Un bouton qui ne fait rien apprend à se méfier de l'interface."""
    demande = creer_demande(entreprise, statut='archived')
    client.force_login(agent)
    corps = client.get(reverse('btp:guided_quote_list')).content.decode()
    assert reverse('btp:guided_quote_archive', args=[demande.pk]) not in corps
    # La suppression reste proposée.
    assert reverse('btp:guided_quote_delete', args=[demande.pk]) in corps


def test_le_detail_porte_les_deux_boutons(client, agent, entreprise):
    demande = creer_demande(entreprise)
    client.force_login(agent)
    corps = client.get(reverse('btp:guided_quote_detail',
                               args=[demande.pk])).content.decode()
    assert reverse('btp:guided_quote_delete', args=[demande.pk]) in corps
    assert reverse('btp:guided_quote_archive', args=[demande.pk]) in corps
