"""Les quatre boutons de téléchargement rendus à leurs ayants droit.

La politique de `/media/` refuse par défaut, et douze préfixes y sont
explicitement interdits parce qu'un document appartient à quelqu'un :
`project_documents/` à un client et à une entreprise, `client_messages/`
au chantier d'une entreprise, `smart_documents/` à une entreprise.

Quatre gabarits rendaient pourtant `{{ x.file.url }}` vers ces préfixes.
Ces boutons étaient **déjà cassés en production** avant la politique,
puisque Django n'avait aucune route `/media/` ; ils ne fonctionnaient
qu'en développement, où `static()` servait tout sans rien filtrer. Les
remplacer par des vues qui contrôlent les droits est donc à la fois une
réparation et une fermeture.

**Ce que ces tests mesurent avant tout : ce qui est REFUSÉ.** Un bouton
de téléchargement plus permissif que la page qui le porte serait une
fuite d'autant plus discrète qu'aucun écran ne la montrerait. Chaque vue
reproduit donc exactement le bornage de sa page, et chaque bornage est
éprouvé ici par un cas qui doit échouer.

La différence délibérée entre les deux côtés d'une conversation est elle
aussi testée : le client ne doit jamais atteindre les pièces jointes
d'une **note interne**, qu'un salarié écrit à ses collègues à propos de
lui ; le salarié, si.
"""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse


# ── Fixtures ───────────────────────────────────────────────────────────────

def _entreprise(nom, slug):
    from apps.core.models import Company
    return Company.objects.create(name=nom, slug=slug)


def _chantier(entreprise, courriel, nom='Chantier'):
    from apps.btp.models import BTPProject
    from apps.crm.models import Customer

    client = Customer.objects.create(
        company=entreprise, name='Client ' + nom, email=courriel)
    return BTPProject.objects.create(
        company=entreprise, name=nom, customer=client)


def _compte_portail(client_http, django_user_model, entreprise, courriel,
                    identifiant='client-portail'):
    """Un client connecté au portail, avec son compte et sa session."""
    from apps.portals.models import ClientPortalAccount

    utilisateur = django_user_model.objects.create_user(
        identifiant, password='x', email=courriel)
    ClientPortalAccount.objects.create(
        company=entreprise, user=utilisateur, first_name='Jean',
        last_name='Dupont', email=courriel)

    client_http.force_login(django_user_model.objects.get(pk=utilisateur.pk))
    session = client_http.session
    session['current_company_id'] = entreprise.pk
    session.save()
    return utilisateur


def _salarie(client_http, django_user_model, entreprise,
             identifiant='salarie'):
    from apps.accounts.models import UserProfile

    utilisateur = django_user_model.objects.create_user(
        identifiant, password='x')
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.companies.add(entreprise)
    profil.current_company = entreprise
    profil.save()

    client_http.force_login(django_user_model.objects.get(pk=utilisateur.pk))
    session = client_http.session
    session['current_company_id'] = entreprise.pk
    session.save()
    return utilisateur


def _televerse(nom='piece.pdf', contenu=b'%PDF-1.4 contenu'):
    return SimpleUploadedFile(nom, contenu,
                              content_type='application/pdf')


def _document(chantier, visible=True, nom='Plan de masse'):
    from apps.btp.models import ProjectDocument
    return ProjectDocument.objects.create(
        project=chantier, name=nom, file=_televerse(),
        doc_type='other', visible_to_client=visible)


def _conversation(chantier, sujet='Question'):
    from apps.btp.models import ClientConversation
    return ClientConversation.objects.create(project=chantier, subject=sujet)


def _piece_jointe(conversation, interne=False, nom='devis.pdf'):
    from apps.btp.models import ClientMessage, MessageAttachment

    message = ClientMessage.objects.create(
        conversation=conversation, sender_name='Chef', is_from_client=False,
        is_internal=interne, content='Voici le document.')
    return MessageAttachment.objects.create(
        message=message, file=_televerse(nom), name=nom)


# ── 1. Documents de chantier, côté client ─────────────────────────────────

@pytest.mark.django_db
def test_le_client_telecharge_son_document(client, django_user_model):
    """Le chemin qui aboutit : sans lui, tous les refus pourraient venir
    d'une vue qui refuse tout -- une panne, non une sécurité."""
    entreprise = _entreprise('Orion SAS', 'orion-doc')
    chantier = _chantier(entreprise, 'jean@exemple.fr')
    _compte_portail(client, django_user_model, entreprise, 'jean@exemple.fr')
    document = _document(chantier)

    reponse = client.get(reverse(
        'client_portal:project_document_download',
        args=[chantier.pk, document.pk]))

    assert reponse.status_code == 200
    assert b'%PDF' in b''.join(reponse.streaming_content)


@pytest.mark.django_db
def test_un_document_masque_au_client_ne_se_telecharge_pas(
        client, django_user_model):
    """`visible_to_client=False` est le filtre de la page ; il doit valoir ici.

    Sans lui, un document interne au chantier -- un devis fournisseur, une
    note de chiffrage -- serait telechargeable par le client a qui la page
    ne le montre pas.
    """
    entreprise = _entreprise('Orion SAS', 'orion-masque')
    chantier = _chantier(entreprise, 'jean@exemple.fr')
    _compte_portail(client, django_user_model, entreprise, 'jean@exemple.fr')
    document = _document(chantier, visible=False)

    reponse = client.get(reverse(
        'client_portal:project_document_download',
        args=[chantier.pk, document.pk]))

    assert reponse.status_code == 404


@pytest.mark.django_db
def test_un_autre_client_ne_telecharge_pas_le_document(client,
                                                       django_user_model):
    """Le bornage par courriel : deux clients de la même entreprise."""
    entreprise = _entreprise('Orion SAS', 'orion-autre-client')
    chantier = _chantier(entreprise, 'jean@exemple.fr')
    document = _document(chantier)
    # Connecte un AUTRE client de la meme entreprise.
    _compte_portail(client, django_user_model, entreprise,
                    'marie@exemple.fr', identifiant='marie')

    reponse = client.get(reverse(
        'client_portal:project_document_download',
        args=[chantier.pk, document.pk]))

    assert reponse.status_code == 404


@pytest.mark.django_db
def test_un_client_d_une_autre_entreprise_ne_telecharge_pas(
        client, django_user_model):
    """Le bornage multi-entreprises, celui qui compte le plus ici."""
    une = _entreprise('Orion SAS', 'orion-une')
    autre = _entreprise('Concurrent SA', 'orion-autre')
    chantier = _chantier(une, 'jean@exemple.fr')
    document = _document(chantier)
    # Meme courriel, mais rattache a une autre entreprise.
    _compte_portail(client, django_user_model, autre, 'jean@exemple.fr',
                    identifiant='jean-ailleurs')

    reponse = client.get(reverse(
        'client_portal:project_document_download',
        args=[chantier.pk, document.pk]))

    assert reponse.status_code == 404


@pytest.mark.django_db
def test_un_visiteur_anonyme_est_renvoye_a_la_connexion(client):
    entreprise = _entreprise('Orion SAS', 'orion-anon')
    chantier = _chantier(entreprise, 'jean@exemple.fr')
    document = _document(chantier)

    reponse = client.get(reverse(
        'client_portal:project_document_download',
        args=[chantier.pk, document.pk]))

    assert reponse.status_code == 302
    assert 'connexion' in reponse['Location']


# ── 2. Pièces jointes, côté client ───────────────────────────────────────

@pytest.mark.django_db
def test_le_client_telecharge_une_piece_jointe(client, django_user_model):
    entreprise = _entreprise('Orion SAS', 'orion-pj')
    chantier = _chantier(entreprise, 'jean@exemple.fr')
    _compte_portail(client, django_user_model, entreprise, 'jean@exemple.fr')
    conversation = _conversation(chantier)
    piece = _piece_jointe(conversation)

    reponse = client.get(reverse(
        'client_portal:message_attachment_download',
        args=[chantier.pk, conversation.pk, piece.pk]))

    assert reponse.status_code == 200


@pytest.mark.django_db
def test_le_client_n_atteint_pas_les_pieces_d_une_note_interne(
        client, django_user_model):
    """LE refus central de cette série.

    Une note interne est écrite par un salarié POUR ses collègues, à
    propos du client. La page de conversation la masque déjà
    (`messages.filter(is_internal=False)`) ; sans le même filtre sur le
    téléchargement, ses pièces jointes resteraient accessibles au client
    dont elle parle — par une URL qu'il suffit d'incrémenter.
    """
    entreprise = _entreprise('Orion SAS', 'orion-interne')
    chantier = _chantier(entreprise, 'jean@exemple.fr')
    _compte_portail(client, django_user_model, entreprise, 'jean@exemple.fr')
    conversation = _conversation(chantier)
    piece = _piece_jointe(conversation, interne=True,
                          nom='chiffrage-interne.pdf')

    reponse = client.get(reverse(
        'client_portal:message_attachment_download',
        args=[chantier.pk, conversation.pk, piece.pk]))

    assert reponse.status_code == 404


@pytest.mark.django_db
def test_une_piece_d_un_autre_chantier_ne_se_telecharge_pas(
        client, django_user_model):
    """L'identifiant de pièce ne suffit pas : il doit appartenir à la conversation."""
    entreprise = _entreprise('Orion SAS', 'orion-croise')
    mien = _chantier(entreprise, 'jean@exemple.fr', nom='Le mien')
    autre = _chantier(entreprise, 'marie@exemple.fr', nom='Celui de Marie')
    _compte_portail(client, django_user_model, entreprise, 'jean@exemple.fr')
    ma_conversation = _conversation(mien)
    piece_voisine = _piece_jointe(_conversation(autre))

    reponse = client.get(reverse(
        'client_portal:message_attachment_download',
        args=[mien.pk, ma_conversation.pk, piece_voisine.pk]))

    assert reponse.status_code == 404


# ── 3. Pièces jointes, côté ERP ──────────────────────────────────────────

@pytest.mark.django_db
def test_un_salarie_telecharge_une_piece_jointe(client, django_user_model):
    entreprise = _entreprise('Orion SAS', 'orion-erp-pj')
    chantier = _chantier(entreprise, 'jean@exemple.fr')
    _salarie(client, django_user_model, entreprise)
    conversation = _conversation(chantier)
    piece = _piece_jointe(conversation)

    reponse = client.get(reverse(
        'btp:client_message_attachment_download',
        args=[conversation.pk, piece.pk]))

    assert reponse.status_code == 200


@pytest.mark.django_db
def test_un_salarie_atteint_bien_les_notes_internes(client,
                                                    django_user_model):
    """La différence avec le portail est DÉLIBÉRÉE, donc elle se teste.

    Sans ce test, on ne saurait pas distinguer « le côté ERP autorise les
    notes internes » de « le côté ERP a oublié de les exclure ». Les notes
    internes sont écrites pour les salariés : la page les affiche toutes.
    """
    entreprise = _entreprise('Orion SAS', 'orion-erp-interne')
    chantier = _chantier(entreprise, 'jean@exemple.fr')
    _salarie(client, django_user_model, entreprise)
    conversation = _conversation(chantier)
    piece = _piece_jointe(conversation, interne=True)

    reponse = client.get(reverse(
        'btp:client_message_attachment_download',
        args=[conversation.pk, piece.pk]))

    assert reponse.status_code == 200


@pytest.mark.django_db
def test_un_salarie_d_une_autre_entreprise_ne_telecharge_pas(
        client, django_user_model):
    """Le filtre d'entreprise n'est pas un contrôle d'accès entre collègues,
    mais il doit tenir entre entreprises — c'est tout son objet."""
    une = _entreprise('Orion SAS', 'orion-erp-une')
    autre = _entreprise('Concurrent SA', 'orion-erp-autre')
    chantier = _chantier(une, 'jean@exemple.fr')
    conversation = _conversation(chantier)
    piece = _piece_jointe(conversation)
    _salarie(client, django_user_model, autre, identifiant='espion')

    reponse = client.get(reverse(
        'btp:client_message_attachment_download',
        args=[conversation.pk, piece.pk]))

    assert reponse.status_code == 404


# ── 4. Documents intelligents ────────────────────────────────────────────

@pytest.mark.django_db
def test_un_document_intelligent_se_telecharge_dans_son_entreprise(
        client, django_user_model):
    from apps.smart_documents.models import SmartDocument

    entreprise = _entreprise('Orion SAS', 'orion-smart')
    _salarie(client, django_user_model, entreprise)
    document = SmartDocument.objects.create(
        company=entreprise, title='Contrat de sous-traitance',
        file=_televerse('contrat.pdf'))

    reponse = client.get(reverse('smart_documents:download',
                                 args=[document.pk]))

    assert reponse.status_code == 200


@pytest.mark.django_db
def test_un_document_intelligent_d_une_autre_entreprise_est_refuse(
        client, django_user_model):
    from apps.smart_documents.models import SmartDocument

    une = _entreprise('Orion SAS', 'orion-smart-une')
    autre = _entreprise('Concurrent SA', 'orion-smart-autre')
    document = SmartDocument.objects.create(
        company=une, title='Contrat', file=_televerse('contrat.pdf'))
    _salarie(client, django_user_model, autre, identifiant='espion-smart')

    reponse = client.get(reverse('smart_documents:download',
                                 args=[document.pk]))

    assert reponse.status_code == 404


# ── 4 bis. Devis guidé : ce qu'un prospect a déposé chez lui ─────────────

def _demande_guidee(entreprise):
    from apps.btp.models import GuidedQuoteRequest
    return GuidedQuoteRequest.objects.create(
        company=entreprise, request_type='electricite',
        client_first_name='Jean', client_last_name='Dupont',
        client_email='jean@exemple.fr')


@pytest.mark.django_db
def test_une_photo_de_demande_s_affiche_en_ligne(client, django_user_model):
    """Une vignette doit s'afficher, pas se télécharger.

    C'est le seul cas où l'aide sert « inline », et seulement pour un type
    d'image — un SVG repartirait en téléchargement.
    """
    from apps.btp.models import GuidedQuotePhoto

    entreprise = _entreprise('Orion SAS', 'orion-gq-photo')
    _salarie(client, django_user_model, entreprise)
    demande = _demande_guidee(entreprise)
    photo = GuidedQuotePhoto.objects.create(
        request=demande, caption='Tableau électrique',
        photo=SimpleUploadedFile('tableau.png', b'\x89PNG\r\n\x1a\nfaux',
                                 content_type='image/png'))

    reponse = client.get(reverse('btp:guided_quote_photo',
                                 args=[demande.pk, photo.pk]))

    assert reponse.status_code == 200
    assert reponse['Content-Disposition'].startswith('inline')
    assert reponse['Content-Type'] == 'image/png'


@pytest.mark.django_db
def test_un_svg_de_demande_ne_s_affiche_pas_malgre_le_drapeau(
        client, django_user_model):
    """Le drapeau « afficher si image » ne doit pas ouvrir une brèche.

    Un SVG est un document XML qui peut porter un <script> ; il ne figure
    donc pas dans TYPES_AFFICHABLES, et doit repartir en téléchargement
    même sur une vue qui affiche les images en ligne.
    """
    from apps.btp.models import GuidedQuotePhoto

    entreprise = _entreprise('Orion SAS', 'orion-gq-svg')
    _salarie(client, django_user_model, entreprise)
    demande = _demande_guidee(entreprise)
    photo = GuidedQuotePhoto.objects.create(
        request=demande, caption='Piege',
        photo=SimpleUploadedFile(
            'piege.svg',
            b'<svg xmlns="http://www.w3.org/2000/svg">'
            b'<script>alert(1)</script></svg>',
            content_type='image/svg+xml'))

    reponse = client.get(reverse('btp:guided_quote_photo',
                                 args=[demande.pk, photo.pk]))

    assert reponse['Content-Disposition'].startswith('attachment')
    assert reponse['Content-Type'] == 'application/octet-stream'


@pytest.mark.django_db
def test_une_photo_d_une_autre_entreprise_est_refusee(client,
                                                      django_user_model):
    """Ce sont des photos prises chez un particulier, dans son logement."""
    from apps.btp.models import GuidedQuotePhoto

    une = _entreprise('Orion SAS', 'orion-gq-une')
    autre = _entreprise('Concurrent SA', 'orion-gq-autre')
    demande = _demande_guidee(une)
    photo = GuidedQuotePhoto.objects.create(
        request=demande, photo=_televerse('salon.png'))
    _salarie(client, django_user_model, autre, identifiant='espion-gq')

    reponse = client.get(reverse('btp:guided_quote_photo',
                                 args=[demande.pk, photo.pk]))

    assert reponse.status_code == 404


@pytest.mark.django_db
def test_une_piece_de_demande_se_telecharge(client, django_user_model):
    from apps.btp.models import GuidedQuoteDocument

    entreprise = _entreprise('Orion SAS', 'orion-gq-doc')
    _salarie(client, django_user_model, entreprise)
    demande = _demande_guidee(entreprise)
    document = GuidedQuoteDocument.objects.create(
        request=demande, name='Diagnostic', file=_televerse('diag.pdf'))

    reponse = client.get(reverse('btp:guided_quote_document_download',
                                 args=[demande.pk, document.pk]))

    assert reponse.status_code == 200
    assert reponse['Content-Disposition'].startswith('attachment')


@pytest.mark.django_db
def test_une_photo_d_une_autre_demande_est_refusee(client,
                                                   django_user_model):
    """L'identifiant de photo ne suffit pas : il doit appartenir à la demande."""
    from apps.btp.models import GuidedQuotePhoto

    entreprise = _entreprise('Orion SAS', 'orion-gq-croise')
    _salarie(client, django_user_model, entreprise)
    mienne = _demande_guidee(entreprise)
    voisine = _demande_guidee(entreprise)
    photo_voisine = GuidedQuotePhoto.objects.create(
        request=voisine, photo=_televerse('autre.png'))

    reponse = client.get(reverse('btp:guided_quote_photo',
                                 args=[mienne.pk, photo_voisine.pk]))

    assert reponse.status_code == 404


# ── 5. L'aide partagée : toujours en téléchargement ──────────────────────

@pytest.mark.django_db
def test_un_svg_televerse_ne_s_affiche_jamais(client, django_user_model):
    """Le même raisonnement que la politique de /media/.

    Ces fichiers sont déposés par des tiers — un client, un prospect. Un
    SVG affiché depuis l'origine du site exécuterait son script avec les
    droits du LECTEUR, c'est-à-dire ici un salarié connecté à l'ERP. Le
    téléchargement forcé supprime ce risque.
    """
    from apps.smart_documents.models import SmartDocument

    entreprise = _entreprise('Orion SAS', 'orion-svg')
    _salarie(client, django_user_model, entreprise)
    document = SmartDocument.objects.create(
        company=entreprise, title='Schema',
        file=SimpleUploadedFile(
            'piege.svg',
            b'<svg xmlns="http://www.w3.org/2000/svg">'
            b'<script>alert(1)</script></svg>',
            content_type='image/svg+xml'))

    reponse = client.get(reverse('smart_documents:download',
                                 args=[document.pk]))

    assert reponse.status_code == 200
    assert reponse['Content-Disposition'].startswith('attachment')
    assert reponse['Content-Type'] == 'application/octet-stream'
    assert reponse['X-Content-Type-Options'] == 'nosniff'


@pytest.mark.django_db
def test_aucun_cache_ne_garde_un_fichier_reserve(client, django_user_model):
    """Un proxy d'entreprise ne doit pas garder un document d'un client.

    L'aide pose « private, no-store ». `NoCacheMiddleware` le remplace
    ensuite par « no-cache, no-store, must-revalidate » sur toute page
    authentifiée de l'ERP — ces adresses ne sont pas sous /media/, donc
    l'exemption ajoutée pour les médias ne s'y applique pas.

    On éprouve donc la PROPRIÉTÉ et non la chaîne exacte : `no-store`
    interdit toute conservation, par un cache privé comme par un cache
    partagé, ce qui est l'objectif. L'en-tête de l'aide reste utile là où
    l'intergiciel ne passe pas.
    """
    from apps.smart_documents.models import SmartDocument

    entreprise = _entreprise('Orion SAS', 'orion-cache')
    _salarie(client, django_user_model, entreprise)
    document = SmartDocument.objects.create(
        company=entreprise, title='Contrat', file=_televerse())

    reponse = client.get(reverse('smart_documents:download',
                                 args=[document.pk]))

    assert 'no-store' in reponse['Cache-Control']


def test_l_aide_marque_le_fichier_comme_prive():
    """Mesuré sur l'aide elle-même, sans l'intergiciel par-dessus."""
    from apps.core.media_access import servir_fichier_autorise

    class FichierSimule:
        name = 'smart_documents/x.pdf'

        def open(self, _mode='rb'):
            return io.BytesIO(b'%PDF')

    reponse = servir_fichier_autorise(FichierSimule(), 'Contrat')
    assert 'private' in reponse['Cache-Control']
    assert 'no-store' in reponse['Cache-Control']


@pytest.mark.django_db
def test_un_document_d_entreprise_se_telecharge_par_sa_vue(client,
                                                           django_user_model):
    """L'app `documents` : contrats, factures, plans, rapports.

    Trouvée par le garde-fou de source ci-dessous, et non prévue au
    départ : quatre liens bruts vers `documents/`, un préfixe interdit.
    """
    from apps.documents.models import Document

    entreprise = _entreprise('Orion SAS', 'orion-docs-app')
    _salarie(client, django_user_model, entreprise)
    document = Document.objects.create(
        company=entreprise, title='Contrat de maintenance',
        file=_televerse('contrat.pdf'))

    reponse = client.get(reverse('documents:document_download',
                                 args=[document.pk]))

    assert reponse.status_code == 200
    assert reponse['Content-Disposition'].startswith('attachment')


@pytest.mark.django_db
def test_un_document_d_une_autre_entreprise_est_refuse(client,
                                                       django_user_model):
    from apps.documents.models import Document

    une = _entreprise('Orion SAS', 'orion-docs-une')
    autre = _entreprise('Concurrent SA', 'orion-docs-autre')
    document = Document.objects.create(
        company=une, title='Contrat', file=_televerse('contrat.pdf'))
    _salarie(client, django_user_model, autre, identifiant='espion-docs')

    reponse = client.get(reverse('documents:document_download',
                                 args=[document.pk]))

    assert reponse.status_code == 404


def test_l_extension_est_rendue_au_nom_affiche():
    """« Contrat de sous-traitance » n'ouvre aucun logiciel.

    Les noms affichés viennent de champs libres (`name`, `title`) et n'ont
    souvent aucune extension. Sans récupérer celle du fichier stocké, le
    téléchargement produit un fichier que le système ne sait pas ouvrir.
    """
    from apps.core.media_access import servir_fichier_autorise

    class FichierSimule:
        name = 'smart_documents/abc123.pdf'

        def open(self, _mode='rb'):
            return io.BytesIO(b'%PDF-1.4')

    reponse = servir_fichier_autorise(FichierSimule(),
                                      'Contrat de sous-traitance')
    assert 'Contrat de sous-traitance.pdf' in reponse['Content-Disposition']


def test_un_nom_affiche_ne_peut_pas_forger_l_entete():
    """Un guillemet ou un retour à la ligne dans le nom casserait l'en-tête.

    Ces noms sont saisis par des utilisateurs, parfois par le client
    lui-même au téléversement : un retour chariot permettrait d'injecter
    un second en-tête dans la réponse.
    """
    from apps.core.media_access import servir_fichier_autorise

    class FichierSimule:
        name = 'client_messages/x.pdf'

        def open(self, _mode='rb'):
            return io.BytesIO(b'%PDF')

    reponse = servir_fichier_autorise(
        FichierSimule(), 'mechant".pdf\r\nX-Injecte: oui')
    disposition = reponse['Content-Disposition']

    assert '"' not in disposition.replace('filename="', '').rstrip('"')
    assert '\r' not in disposition and '\n' not in disposition
    assert 'X-Injecte' not in reponse


def test_un_fichier_absent_du_disque_rend_404():
    """Et non une erreur 500, qui exposerait le chemin dans une page de debug."""
    from django.http import Http404

    from apps.core.media_access import servir_fichier_autorise

    class FichierAbsent:
        name = 'smart_documents/disparu.pdf'

        def open(self, _mode='rb'):
            raise OSError('No such file or directory')

    with pytest.raises(Http404):
        servir_fichier_autorise(FichierAbsent(), 'Disparu')


# ── 6. Garde de source : plus aucun lien brut vers un préfixe refusé ─────

def test_aucun_gabarit_ne_pointe_plus_vers_un_prefixe_refuse():
    """Le test qui empêche la régression de se réinstaller.

    Un `{{ x.file.url }}` vers un préfixe interdit ne lève aucune erreur à
    l'écriture du gabarit : il produit un bouton qui rend 404, et il faut
    cliquer pour s'en apercevoir.
    """
    import os
    import re

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    suspects = []

    for dossier, _sous, fichiers in os.walk(os.path.join(racine, 'templates')):
        for nom in fichiers:
            if not nom.endswith('.html'):
                continue
            chemin = os.path.join(dossier, nom)
            with open(chemin, encoding='utf-8', errors='replace') as fichier:
                contenu = fichier.read()
            for champ in re.findall(r'\{\{\s*(\w+)\.file\.url\s*\}\}',
                                    contenu):
                suspects.append(
                    f'{os.path.relpath(chemin, racine)} : {champ}.file.url')

    # Chaque exception est une DECISION, avec sa raison -- meme forme que
    # PREFIXES_INTERDITS dans media_access.py. Un gabarit qui n'est pas
    # dans cette liste et qui pointe vers /media/ fait echouer le test, ce
    # qui force a trancher plutot qu'a laisser passer.
    autorises = {
        # training/blocks/ est dans PREFIXES_AUTHENTIFIES : /media/ sert
        # ces fichiers aux comptes connectes, aucune vue dediee n'est
        # necessaire. Verifie avec niveau_requis('training/').
        'templates/internal_training/page_editor.html',
        'templates/internal_training/page_view.html',
    }
    restants = [s for s in suspects
                if s.split(' : ')[0].replace('\\', '/') not in autorises]

    assert not restants, (
        'Des gabarits pointent vers un fichier televerse par son URL /media/ '
        'brute. Si son prefixe figure dans PREFIXES_INTERDITS, le bouton '
        'rendra 404 : il lui faut une vue qui controle les droits. Sinon, '
        'ajoutez-le a la liste ci-dessus EN DISANT POURQUOI.\n  '
        + '\n  '.join(restants))
