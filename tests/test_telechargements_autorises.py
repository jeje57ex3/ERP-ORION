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

    IL NE CHERCHAIT QUE `.file.url`, et ce projet nomme ses champs en
    français. `VersionApplicationBureau.fichier`,
    `SupplierInvoice.fichier`, `UserProfile.signature`,
    `TicketMessage.attachment`, `ReservationPhoto.photo` : aucun n'était
    regardé. Une garde qui ne connaît qu'un seul nom de champ ne garde que
    les modèles écrits dans la langue de son auteur.

    Les noms surveillés sont donc LUS SUR LES MODÈLES, et pas écrits à la
    main : la liste des préfixes refusés bouge, celle des champs qui les
    emploient aussi, et une énumération recopiée ici se serait périmée au
    premier modèle ajouté. C'est le même raisonnement que
    `prefixes_declares()` dans la commande de vérification.

    Ce que cette version a trouvé, du premier coup : l'aperçu de la
    signature dans le profil, les pièces jointes de tous les tickets de
    support, et les photos de réserves des deux côtés — ERP et portail
    client. Les trois rendaient 404.
    """
    import os
    import re

    from django.apps import apps
    from django.db import models

    from apps.core.media_access import niveau_requis

    noms_surveilles = set()
    for modele in apps.get_models():
        for champ in modele._meta.get_fields():
            if not isinstance(champ, models.FileField):
                continue
            cible = getattr(champ, 'upload_to', '')
            if callable(cible) or not cible:
                continue
            prefixe = str(cible).replace('\\', '/').split('%')[0]
            if niveau_requis(prefixe) == 'interdit':
                noms_surveilles.add(champ.name)

    # Si cet ensemble se vidait, le test passerait sans rien examiner et
    # personne ne s'en apercevrait -- le pire etat possible pour une garde.
    assert noms_surveilles, (
        'aucun champ ne declare de prefixe refuse : soit la politique a '
        'change, soit ce test ne regarde plus rien.')

    motif = re.compile(
        r'\{\{\s*([\w.]+)\.(' + '|'.join(sorted(noms_surveilles))
        + r')\.url\s*\}\}')

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    suspects = []

    for dossier, _sous, fichiers in os.walk(os.path.join(racine, 'templates')):
        for nom in fichiers:
            if not nom.endswith('.html'):
                continue
            chemin = os.path.join(dossier, nom)
            with open(chemin, encoding='utf-8', errors='replace') as fichier:
                contenu = fichier.read()
            relatif = os.path.relpath(chemin, racine).replace('\\', '/')
            for variable, champ in motif.findall(contenu):
                suspects.append(f'{relatif} : {variable}.{champ}.url')

    # Chaque exception est une DECISION, avec sa raison -- meme forme que
    # PREFIXES_INTERDITS dans media_access.py. La cle est le suspect ENTIER
    # et non le seul gabarit : autoriser un fichier en bloc y laisserait
    # passer le prochain lien brut qu'on y ecrira.
    autorises = {
        # training/blocks/ est dans PREFIXES_AUTHENTIFIES : /media/ sert ces
        # fichiers aux comptes connectes, aucune vue dediee n'est
        # necessaire. Le nom « file » est surveille a cause d'AUTRES modeles
        # -- employee_private/, documents/, client_messages/ -- et c'est la
        # limite d'une recherche sur le texte : elle ne sait pas de quel
        # modele vient la variable. Verifie avec niveau_requis('training/').
        'templates/internal_training/page_editor.html : block.file.url',
        'templates/internal_training/page_view.html : block.file.url',
        # CES DEUX-LA NE DESIGNENT AUCUN FICHIER. Ni `hr.Employee` ni
        # `inventory.Product` ne portent de champ `photo` -- verifie sur les
        # modeles. Les deux balises sont sous un `{% if ... .photo %}`
        # toujours faux, donc jamais rendues : branches mortes, et non liens
        # casses. On les nomme ici pour que ce constat soit ecrit quelque
        # part, plutot que refait a chaque echec du test.
        'templates/hr/employee_list.html : emp.photo.url',
        'templates/inventory/product_form_desktop.html : product.photo.url',
    }
    restants = [s for s in suspects if s not in autorises]

    assert not restants, (
        'Des gabarits pointent vers un fichier televerse par son URL /media/ '
        'brute. Si son prefixe figure dans PREFIXES_INTERDITS, le lien '
        'rendra 404 : il lui faut une vue qui controle les droits. Sinon, '
        'ajoutez-le a la liste ci-dessus EN DISANT POURQUOI.\n  '
        + '\n  '.join(restants))


# ── 7. Les quatre liens que la garde élargie a trouvés ────────────────────
#
# Elle ne cherchait que `{{ x.file.url }}`. Ce projet nomme ses champs en
# français, donc elle ne voyait ni `signature`, ni `attachment`, ni
# `photo`, ni `fichier`. Les quatre liens ci-dessous rendaient 404 — ou,
# pour les photos de réserves, servaient le fichier à tout compte connecté
# de n'importe quelle entreprise, ce qui était pire.


def _ticket(entreprise, avec_piece=True, interne=False):
    from apps.support.models import Ticket, TicketMessage

    ticket = Ticket.objects.create(
        company=entreprise, number='TKT-0001', subject='Écran noir')
    return TicketMessage.objects.create(
        ticket=ticket, message='Voici la capture.', is_internal=interne,
        attachment=_televerse('capture.pdf') if avec_piece else None)


def _reserve_avec_photo(chantier, nom='carrelage.png'):
    from apps.btp.models import ProjectReservation, ReservationPhoto

    reserve = ProjectReservation.objects.create(
        project=chantier, title='Carrelage fendu',
        description='Deux carreaux fendus près de la porte.')
    return ReservationPhoto.objects.create(
        reservation=reserve,
        photo=SimpleUploadedFile(nom, b'\x89PNG\r\n\x1a\nfaux',
                                 content_type='image/png'),
        caption='Le carreau fendu')


def _png_signe():
    """Un PNG qui passe le contrôle d'encre : au moins 50 pixels opaques."""
    import base64

    from PIL import Image, ImageDraw

    image = Image.new('RGBA', (900, 300), (0, 0, 0, 0))
    ImageDraw.Draw(image).line((50, 150, 850, 150), fill=(0, 0, 0, 255),
                               width=6)
    tampon = io.BytesIO()
    image.save(tampon, format='PNG')
    return ('data:image/png;base64,'
            + base64.b64encode(tampon.getvalue()).decode('ascii'))


# ── 7.1 La signature du profil ───────────────────────────────────────────

@pytest.mark.django_db
def test_le_proprietaire_voit_sa_signature(client, django_user_model):
    """L'aperçu du profil était cassé : `signatures/` rend 404 par /media/."""
    entreprise = _entreprise('Orion SAS', 'orion-sig')
    utilisateur = _salarie(client, django_user_model, entreprise)
    utilisateur.profile.signature.save(
        'signature-x.png',
        SimpleUploadedFile('s.png', b'\x89PNG\r\n\x1a\nfaux'), save=True)

    reponse = client.get(reverse('accounts:signature_image'))

    assert reponse.status_code == 200
    # Affichée, et non téléchargée : c'est un aperçu dans la page.
    assert reponse['Content-Disposition'].startswith('inline')
    assert reponse['Content-Type'] == 'image/png'


@pytest.mark.django_db
def test_la_signature_servie_est_celle_du_demandeur(client,
                                                    django_user_model):
    """LA BORNE EST L'ABSENCE D'IDENTIFIANT DANS L'ADRESSE.

    Il n'y a pas de numéro à changer pour atteindre la signature d'un
    collègue. Ce test le vérifie par la conséquence : un second compte,
    sans signature, obtient 404 là où le premier obtient son image — la
    même adresse, deux réponses, parce qu'elle ne désigne pas un fichier
    mais un demandeur.
    """
    entreprise = _entreprise('Orion SAS', 'orion-sig2')
    premier = _salarie(client, django_user_model, entreprise, 'avec-sig')
    premier.profile.signature.save(
        'signature-a.png',
        SimpleUploadedFile('a.png', b'\x89PNG\r\n\x1a\nfaux'), save=True)
    assert client.get(reverse('accounts:signature_image')).status_code == 200

    _salarie(client, django_user_model, entreprise, 'sans-sig')
    assert client.get(reverse('accounts:signature_image')).status_code == 404


@pytest.mark.django_db
def test_l_enregistrement_ne_renvoie_plus_une_adresse_media(
        client, django_user_model):
    """Le défaut se voyait JUSTE APRÈS avoir annoncé la réussite.

    `signature_save` renvoyait `profil.signature.url`, et
    `orion-signature.js` posait cette adresse dans l'aperçu. L'écran
    affichait donc « Signature enregistrée » au-dessus d'une image
    cassée — le pire ordre possible, puisqu'on ne doute pas de ce qu'on
    vient de réussir.
    """
    entreprise = _entreprise('Orion SAS', 'orion-sig3')
    _salarie(client, django_user_model, entreprise)

    reponse = client.post(reverse('accounts:signature_save'),
                          {'signature': _png_signe()})

    assert reponse.status_code == 200
    adresse = reponse.json()['url']
    assert adresse == reverse('accounts:signature_image')
    assert not adresse.startswith('/media/')
    # Et l'adresse rendue sert vraiment quelque chose.
    assert client.get(adresse).status_code == 200


@pytest.mark.django_db
def test_un_anonyme_n_obtient_aucune_signature(client):
    reponse = client.get(reverse('accounts:signature_image'))
    assert reponse.status_code in (302, 403)


# ── 7.2 La pièce jointe d'un ticket ──────────────────────────────────────

@pytest.mark.django_db
def test_un_salarie_telecharge_la_piece_jointe_d_un_ticket(
        client, django_user_model):
    entreprise = _entreprise('Orion SAS', 'orion-tkt')
    _salarie(client, django_user_model, entreprise)
    message = _ticket(entreprise)

    reponse = client.get(reverse('support:ticket_attachment',
                                 args=[message.pk]))

    assert reponse.status_code == 200
    # En téléchargement : une pièce jointe de ticket est déposée par un
    # tiers, et un SVG affiché en ligne exécuterait son script.
    assert reponse['Content-Disposition'].startswith('attachment')


@pytest.mark.django_db
def test_la_piece_jointe_d_une_autre_entreprise_est_refusee(
        client, django_user_model):
    """Le bornage de l'écran, reproduit : `ticket__company`.

    Un ticket de support porte volontiers une capture de l'ERP, donc des
    données de l'entreprise. Sans ce filtre, changer le numéro dans
    l'adresse suffisait.
    """
    autre = _entreprise('Concurrent SARL', 'concurrent-tkt')
    message = _ticket(autre)

    mienne = _entreprise('Orion SAS', 'orion-tkt2')
    _salarie(client, django_user_model, mienne)

    reponse = client.get(reverse('support:ticket_attachment',
                                 args=[message.pk]))
    assert reponse.status_code == 404


@pytest.mark.django_db
def test_un_message_sans_piece_jointe_rend_404(client, django_user_model):
    entreprise = _entreprise('Orion SAS', 'orion-tkt3')
    _salarie(client, django_user_model, entreprise)
    message = _ticket(entreprise, avec_piece=False)

    reponse = client.get(reverse('support:ticket_attachment',
                                 args=[message.pk]))
    assert reponse.status_code == 404


# ── 7.3 Les photos de réserves, et la fuite entre entreprises ────────────

@pytest.mark.django_db
def test_un_salarie_voit_la_photo_d_une_reserve(client, django_user_model):
    entreprise = _entreprise('Orion SAS', 'orion-res')
    chantier = _chantier(entreprise, 'jean@exemple.fr')
    _salarie(client, django_user_model, entreprise)
    photo = _reserve_avec_photo(chantier)

    reponse = client.get(reverse('btp:reservation_photo', args=[photo.pk]))

    assert reponse.status_code == 200
    assert reponse['Content-Disposition'].startswith('inline')


@pytest.mark.django_db
def test_la_photo_de_reserve_d_une_autre_entreprise_est_refusee(
        client, django_user_model):
    autre = _entreprise('Concurrent SARL', 'concurrent-res')
    photo = _reserve_avec_photo(_chantier(autre, 'luc@exemple.fr'))

    mienne = _entreprise('Orion SAS', 'orion-res2')
    _salarie(client, django_user_model, mienne)

    assert client.get(reverse('btp:reservation_photo',
                              args=[photo.pk])).status_code == 404


@pytest.mark.django_db
def test_le_client_voit_les_photos_des_reserves_de_son_chantier(
        client, django_user_model):
    entreprise = _entreprise('Orion SAS', 'orion-res3')
    chantier = _chantier(entreprise, 'jean@exemple.fr')
    _compte_portail(client, django_user_model, entreprise, 'jean@exemple.fr')
    photo = _reserve_avec_photo(chantier)

    reponse = client.get(reverse('client_portal:reservation_photo',
                                 args=[chantier.pk, photo.pk]))

    assert reponse.status_code == 200


@pytest.mark.django_db
def test_un_client_ne_voit_pas_les_reserves_d_un_autre_chantier(
        client, django_user_model):
    """Le contrôle passe par le CHANTIER, pas par la photo seule.

    Sinon il suffirait de garder son propre numéro de chantier dans
    l'adresse et de changer celui de la photo.
    """
    entreprise = _entreprise('Orion SAS', 'orion-res4')
    le_mien = _chantier(entreprise, 'jean@exemple.fr', 'Le mien')
    celui_d_un_autre = _chantier(entreprise, 'luc@exemple.fr', 'Autre')
    _compte_portail(client, django_user_model, entreprise, 'jean@exemple.fr')
    photo = _reserve_avec_photo(celui_d_un_autre)

    assert client.get(reverse('client_portal:reservation_photo',
                              args=[le_mien.pk, photo.pk])).status_code == 404


@pytest.mark.django_db
def test_media_ne_sert_plus_les_photos_de_reserves(client, tmp_path,
                                                   settings,
                                                   django_user_model):
    """LA FUITE QUI ÉTAIT OUVERTE, et la raison du déplacement.

    `reservations/` était au niveau « authentifié », qui n'est PAS borné
    par entreprise. Or un client de portail est un compte Django
    authentifié — `_get_portal_account` ne le reconnaît qu'une fois
    `request.user.is_authenticated` vrai. Le client de l'entreprise A
    pouvait donc lire les photos de réserves de l'entreprise B en devinant
    un nom de fichier, et `upload_to='reservations/'` conserve le nom
    d'origine de la photo.

    Ce test tient la propriété dans le sens qui compte : par /media/,
    plus personne — même connecté.
    """
    settings.MEDIA_ROOT = str(tmp_path)
    cible = tmp_path / 'reservations' / 'IMG_1234.jpg'
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_bytes(b'\x89PNG\r\n\x1a\nfaux')

    assert client.get('/media/reservations/IMG_1234.jpg').status_code == 404

    entreprise = _entreprise('Concurrent SARL', 'concurrent-res5')
    _compte_portail(client, django_user_model, entreprise, 'luc@exemple.fr')
    assert client.get('/media/reservations/IMG_1234.jpg').status_code == 404


# ── 7.4 Les gabarits ne portent plus d'adresse /media/ ───────────────────

@pytest.mark.django_db
def test_l_ecran_d_un_ticket_pointe_vers_la_vue(client, django_user_model):
    """Mesuré sur le HTML rendu, et non sur la source du gabarit."""
    entreprise = _entreprise('Orion SAS', 'orion-tkt4')
    _salarie(client, django_user_model, entreprise)
    message = _ticket(entreprise)

    reponse = client.get(reverse('support:ticket_detail',
                                 args=[message.ticket.pk]))
    corps = reponse.content.decode('utf-8')

    assert reverse('support:ticket_attachment', args=[message.pk]) in corps
    assert '/media/tickets/' not in corps
