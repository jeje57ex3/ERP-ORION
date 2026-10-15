"""Suppression des conversations avec Orion.

Une conversation avec l'assistant porte des devis, des noms de clients, des
montants. « Supprimer » doit donc vouloir dire supprimer : le modèle offrait
un statut « supprimée » que rien ne posait jamais, et la liste l'excluait
déjà — un demi-mécanisme qui aurait gardé le contenu indéfiniment en base,
invisible mais intact.

Trois propriétés comptent ici, et aucune n'est cosmétique :

  1. **la propriété** — personne ne supprime la conversation d'un autre, ni
     celle d'une autre entreprise. C'est la règle centrale de cet ERP, et elle
     a déjà été enfreinte dans ce dépôt ;
  2. **la méthode** — en GET, une suppression est déclenchée par tout ce qui
     parcourt les pages : préchargement du navigateur, antivirus, indexeur.
     L'historique disparaîtrait sans que personne ait cliqué ;
  3. **la trace** — le geste est journalisé, le contenu ne l'est pas.
     Conserver ce qui a été dit dans une conversation supprimée viderait la
     suppression de son sens.
"""

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Suppression SA', slug='suppression-sa')


@pytest.fixture
def autre_entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Autre SA', slug='autre-sa')


@pytest.fixture
def utilisateur(django_user_model):
    return django_user_model.objects.create_user(
        username='proprietaire', email='p@test.fr', password='motdepasse-test')


@pytest.fixture
def collegue(django_user_model):
    return django_user_model.objects.create_user(
        username='collegue', email='c@test.fr', password='motdepasse-test')


def _conversation(entreprise, utilisateur, titre='Devis Dupont', messages=2):
    from apps.orion_ai.models import OrionAIConversation, OrionAIMessage

    conversation = OrionAIConversation.objects.create(
        company=entreprise, user=utilisateur, title=titre)
    for index in range(messages):
        OrionAIMessage.objects.create(
            conversation=conversation,
            role='user' if index % 2 == 0 else 'assistant',
            content='Montant du devis : 12 400 €',
        )
    return conversation


@pytest.fixture
def connecte(client, utilisateur, entreprise, monkeypatch):
    """Session authentifiée, avec l'entreprise active forcée.

    L'entreprise active est posée par un intergiciel ; on la force pour
    éprouver les vues sans dépendre de son mécanisme de résolution.
    """
    client.force_login(utilisateur)
    from apps.orion_ai import api, services, views
    for module in (services, views, api):
        monkeypatch.setattr(module, 'get_request_company',
                            lambda requete: entreprise)
    return client


# ── La suppression supprime vraiment ────────────────────────────────────────

def test_la_conversation_et_ses_messages_disparaissent(connecte, entreprise,
                                                       utilisateur):
    from apps.orion_ai.models import OrionAIConversation, OrionAIMessage

    conversation = _conversation(entreprise, utilisateur, messages=3)
    assert OrionAIMessage.objects.count() == 3

    reponse = connecte.post(
        f'/erp/assistant/conversations/{conversation.id}/supprimer/')

    assert reponse.status_code == 302
    assert not OrionAIConversation.objects.filter(id=conversation.id).exists()
    # Les messages partent en cascade : les laisser orphelins garderait le
    # contenu que l'on vient d'effacer.
    assert OrionAIMessage.objects.count() == 0


def test_ce_n_est_pas_un_simple_changement_de_statut(connecte, entreprise,
                                                     utilisateur):
    """Le modèle porte un statut « supprimée » que rien ne posait jamais.

    S'en servir aurait gardé devis, clients et montants indéfiniment en base,
    invisibles mais intacts — ce qui n'est pas une suppression.
    """
    from apps.orion_ai.models import OrionAIConversation

    conversation = _conversation(entreprise, utilisateur)
    connecte.post(f'/erp/assistant/conversations/{conversation.id}/supprimer/')

    assert OrionAIConversation.objects.count() == 0
    # Et surtout : aucune ligne ne subsiste avec le statut « supprimée », ce
    # qui serait le signe d'une suppression de façade.
    assert not OrionAIConversation.objects.filter(status='deleted').exists()


def test_les_actions_proposees_en_attente_sont_annoncees(connecte, entreprise,
                                                         utilisateur):
    """Supprimer la conversation qui a proposé une action l'abandonne.

    C'est légitime, mais doit être dit : une action « créer la facture »
    abandonnée en silence laisserait croire qu'elle reste en attente.
    """
    from apps.orion_ai.models import OrionAIProposedAction

    conversation = _conversation(entreprise, utilisateur)
    OrionAIProposedAction.objects.create(
        conversation=conversation,
        title='Créer la facture',
        action_code='create_invoice',
        status='pending',
    )

    reponse = connecte.post(
        f'/erp/assistant/conversations/{conversation.id}/supprimer/',
        follow=True)

    texte = ' '.join(str(m) for m in reponse.context['messages'])
    assert 'abandonn' in texte.lower(), texte
    assert OrionAIProposedAction.objects.count() == 0


# ── La propriété ────────────────────────────────────────────────────────────

def test_on_ne_supprime_pas_la_conversation_d_un_collegue(client, entreprise,
                                                          utilisateur,
                                                          collegue,
                                                          monkeypatch):
    """Filtrer la seule entreprise laisserait un collègue supprimer
    l'historique d'un autre en devinant un identifiant."""
    from apps.orion_ai import api, services, views
    from apps.orion_ai.models import OrionAIConversation

    conversation = _conversation(entreprise, utilisateur)

    client.force_login(collegue)
    for module in (services, views, api):
        monkeypatch.setattr(module, 'get_request_company',
                            lambda requete: entreprise)

    reponse = client.post(
        f'/erp/assistant/conversations/{conversation.id}/supprimer/')

    assert reponse.status_code == 302
    assert OrionAIConversation.objects.filter(id=conversation.id).exists()


def test_on_ne_supprime_pas_la_conversation_d_une_autre_entreprise(
        client, entreprise, autre_entreprise, utilisateur, monkeypatch):
    """Filtrer le seul utilisateur laisserait passer un identifiant venu
    d'une autre entreprise."""
    from apps.orion_ai import api, services, views
    from apps.orion_ai.models import OrionAIConversation

    chez_eux = _conversation(autre_entreprise, utilisateur)

    client.force_login(utilisateur)
    for module in (services, views, api):
        monkeypatch.setattr(module, 'get_request_company',
                            lambda requete: entreprise)

    client.post(f'/erp/assistant/conversations/{chez_eux.id}/supprimer/')
    assert OrionAIConversation.objects.filter(id=chez_eux.id).exists()


def test_le_refus_ne_revele_pas_l_existence_de_la_conversation(
        client, entreprise, utilisateur, collegue, monkeypatch):
    """Distinguer « inexistante » de « pas à vous » renseignerait sur
    l'historique des autres."""
    from apps.orion_ai import api, services, views

    conversation = _conversation(entreprise, utilisateur)

    client.force_login(collegue)
    for module in (services, views, api):
        monkeypatch.setattr(module, 'get_request_company',
                            lambda requete: entreprise)

    existante = client.post(
        f'/erp/assistant/conversations/{conversation.id}/supprimer/',
        follow=True)
    inexistante = client.post(
        '/erp/assistant/conversations/999999/supprimer/', follow=True)

    def messages_de(reponse):
        return ' '.join(str(m) for m in reponse.context['messages'])

    assert messages_de(existante) == messages_de(inexistante)


# ── La méthode ──────────────────────────────────────────────────────────────

def test_une_visite_en_get_ne_supprime_rien(connecte, entreprise, utilisateur):
    """En GET, une suppression est déclenchée par tout ce qui parcourt les
    pages : préchargement du navigateur, antivirus, indexeur."""
    from apps.orion_ai.models import OrionAIConversation

    conversation = _conversation(entreprise, utilisateur)
    reponse = connecte.get(
        f'/erp/assistant/conversations/{conversation.id}/supprimer/')

    assert reponse.status_code == 405
    assert OrionAIConversation.objects.filter(id=conversation.id).exists()


def test_un_anonyme_ne_supprime_rien(client, entreprise, utilisateur):
    from apps.orion_ai.models import OrionAIConversation

    conversation = _conversation(entreprise, utilisateur)
    reponse = client.post(
        f'/erp/assistant/conversations/{conversation.id}/supprimer/')

    assert reponse.status_code in (302, 403)
    assert OrionAIConversation.objects.filter(id=conversation.id).exists()


# ── La trace ────────────────────────────────────────────────────────────────

def test_le_geste_est_journalise_sans_le_contenu(connecte, entreprise,
                                                 utilisateur):
    from apps.orion_ai.models import OrionAIAuditLog

    conversation = _conversation(entreprise, utilisateur,
                                 titre='Devis Dupont', messages=2)
    connecte.post(f'/erp/assistant/conversations/{conversation.id}/supprimer/')

    trace = OrionAIAuditLog.objects.filter(
        event_type='conversation_deleted').first()
    assert trace is not None
    assert trace.payload['messages'] == 2
    # Le titre suffit a retrouver de quoi il s'agissait ; le contenu des
    # messages, lui, ne doit pas survivre a leur suppression.
    assert 'Devis Dupont' in trace.description
    assert '12 400' not in str(trace.payload)


# ── Effacer tout l'historique ───────────────────────────────────────────────

def test_tout_effacer_ne_touche_que_ses_propres_conversations(
        connecte, entreprise, autre_entreprise, utilisateur, collegue):
    from apps.orion_ai.models import OrionAIConversation

    a_moi = _conversation(entreprise, utilisateur, titre='A moi')
    du_collegue = _conversation(entreprise, collegue, titre='Au collegue')
    ailleurs = _conversation(autre_entreprise, utilisateur, titre='Ailleurs')

    reponse = connecte.post('/erp/assistant/conversations/tout-supprimer/')

    assert reponse.status_code == 302
    assert not OrionAIConversation.objects.filter(id=a_moi.id).exists()
    # « Effacer mon historique » n'est pas « effacer celui de tout le monde ».
    assert OrionAIConversation.objects.filter(id=du_collegue.id).exists()
    assert OrionAIConversation.objects.filter(id=ailleurs.id).exists()


def test_tout_effacer_sur_un_historique_vide_le_dit(connecte):
    reponse = connecte.post('/erp/assistant/conversations/tout-supprimer/',
                            follow=True)
    texte = ' '.join(str(m) for m in reponse.context['messages'])
    assert 'Aucune conversation' in texte


def test_tout_effacer_exige_un_post(connecte, entreprise, utilisateur):
    from apps.orion_ai.models import OrionAIConversation

    _conversation(entreprise, utilisateur)
    reponse = connecte.get('/erp/assistant/conversations/tout-supprimer/')
    assert reponse.status_code == 405
    assert OrionAIConversation.objects.count() == 1


# ── L'API ───────────────────────────────────────────────────────────────────

def test_l_api_supprime_aussi(connecte, entreprise, utilisateur):
    from apps.orion_ai.models import OrionAIConversation

    conversation = _conversation(entreprise, utilisateur)
    reponse = connecte.delete(
        f'/api/v1/orion-ai/conversations/{conversation.id}/')

    assert reponse.status_code == 200, reponse.content
    assert reponse.json()['supprimee'] is True
    assert not OrionAIConversation.objects.filter(id=conversation.id).exists()


def test_l_api_refuse_la_conversation_d_un_autre(client, entreprise,
                                                 utilisateur, collegue,
                                                 monkeypatch):
    from apps.orion_ai import api, services, views
    from apps.orion_ai.models import OrionAIConversation

    conversation = _conversation(entreprise, utilisateur)

    client.force_login(collegue)
    for module in (services, views, api):
        monkeypatch.setattr(module, 'get_request_company',
                            lambda requete: entreprise)

    reponse = client.delete(
        f'/api/v1/orion-ai/conversations/{conversation.id}/')
    assert reponse.status_code == 404
    assert OrionAIConversation.objects.filter(id=conversation.id).exists()


def test_l_api_lit_toujours_une_conversation(connecte, entreprise,
                                             utilisateur):
    """L'ajout de DELETE ne doit pas avoir évincé GET."""
    conversation = _conversation(entreprise, utilisateur)
    reponse = connecte.get(
        f'/api/v1/orion-ai/conversations/{conversation.id}/')
    assert reponse.status_code == 200


# ── L'interface ─────────────────────────────────────────────────────────────

def test_la_liste_propose_la_suppression(connecte, entreprise, utilisateur):
    _conversation(entreprise, utilisateur)
    corps = connecte.get('/erp/assistant/conversations/').content.decode()

    assert 'supprimer/' in corps
    # En POST, avec jeton : un lien GET serait suivi par un préchargement.
    assert 'csrfmiddlewaretoken' in corps
    assert 'confirm(' in corps


def test_la_page_de_detail_propose_la_suppression(connecte, entreprise,
                                                  utilisateur):
    conversation = _conversation(entreprise, utilisateur)
    corps = connecte.get(
        f'/erp/assistant/conversations/{conversation.id}/').content.decode()
    assert f'/conversations/{conversation.id}/supprimer/' in corps
