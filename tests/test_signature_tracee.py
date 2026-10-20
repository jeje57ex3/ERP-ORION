"""Signature tracée dans un cadre, plutôt qu'un fichier à téléverser.

**Le contrôle qui porte tout ce fichier est le refus d'une signature
VIDE.** Une toile sur laquelle rien n'a été tracé produit un PNG
parfaitement valide, entièrement transparent. Enregistré, il ferait dire à
l'écran « signature enregistrée » alors que les devis sortiraient sans rien
à l'emplacement prévu — un défaut qui ne se découvre qu'à l'impression,
chez le client. Le refus est donc côté SERVEUR, pas seulement dans le
navigateur qu'on peut contourner.

Le fond reste transparent : posée sur un modèle de devis, une signature à
fond blanc masquerait l'en-tête ou le filet qui se trouve dessous. Un test
le vérifie sur les octets enregistrés.
"""

import base64
import io

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ── Terrain ─────────────────────────────────────────────────────────────────

def _png(trace=True, taille=(900, 300), un_point=False, mode='RGBA'):
    from PIL import Image, ImageDraw

    image = Image.new(mode, taille,
                      (0, 0, 0, 0) if mode == 'RGBA' else (255, 255, 255))
    dessin = ImageDraw.Draw(image)
    if trace:
        dessin.line([(100, 200), (300, 100), (500, 220), (700, 120)],
                    fill=(17, 17, 17, 255) if mode == 'RGBA' else (17, 17, 17),
                    width=5)
    if un_point:
        dessin.point((10, 10), fill=(17, 17, 17, 255) if mode == 'RGBA'
                     else (17, 17, 17))
    tampon = io.BytesIO()
    image.save(tampon, 'PNG')
    return tampon.getvalue()


def _jpeg():
    from PIL import Image

    image = Image.new('RGB', (400, 150), (255, 255, 255))
    tampon = io.BytesIO()
    image.save(tampon, 'JPEG')
    return tampon.getvalue()


def _url(octets):
    from apps.accounts.signature import PREFIXE
    return PREFIXE + base64.b64encode(octets).decode()


@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Dupont SA', slug='dupont-sa')


@pytest.fixture
def depot(tmp_path, settings):
    """Un MEDIA_ROOT propre à chaque test : on inspecte les fichiers écrits."""
    settings.MEDIA_ROOT = str(tmp_path)
    return tmp_path


@pytest.fixture
def connecte(client, entreprise, django_user_model, depot):
    user = django_user_model.objects.create_user(
        username='patron', password='motdepasse-test',
        first_name='Jean', last_name='Dupont')
    user.profile.companies.add(entreprise)
    user.profile.current_company = entreprise
    user.profile.save()
    client.force_login(user)
    client.user = user
    return client


# ═══ LE DÉCODAGE ════════════════════════════════════════════════════════════

def test_un_trace_est_accepte():
    from apps.accounts.signature import decoder_signature

    octets = decoder_signature(_url(_png()))
    assert octets.startswith(b'\x89PNG')


def test_une_toile_VIDE_est_refusee():
    """Le contrôle central. Un PNG entièrement transparent est valide pour
    un décodeur d'image : seul un comptage de l'encre le distingue d'une
    signature."""
    from apps.accounts.signature import SignatureInvalide, decoder_signature

    with pytest.raises(SignatureInvalide) as echec:
        decoder_signature(_url(_png(trace=False)))
    # Le message doit dire le remede, pas seulement constater.
    assert 'tracez' in str(echec.value).lower()


def test_un_point_pose_par_accident_ne_fait_pas_une_signature():
    from apps.accounts.signature import SignatureInvalide, decoder_signature

    with pytest.raises(SignatureInvalide):
        decoder_signature(_url(_png(trace=False, un_point=True)))


def test_ce_qui_n_est_pas_une_image_est_refuse():
    from apps.accounts.signature import SignatureInvalide, decoder_signature

    with pytest.raises(SignatureInvalide):
        decoder_signature(_url(b'ceci n-est pas une image'))


def test_un_jpeg_deguise_en_png_est_refuse():
    """Le préfixe annoncé ne prouve rien. Et un JPEG n'a pas de couche
    alpha : son fond serait blanc, donc masquant sur le modèle."""
    from apps.accounts.signature import SignatureInvalide, decoder_signature

    with pytest.raises(SignatureInvalide) as echec:
        decoder_signature(_url(_jpeg()))
    assert 'PNG' in str(echec.value)


def test_sans_le_prefixe_attendu_c_est_refuse():
    from apps.accounts.signature import SignatureInvalide, decoder_signature

    with pytest.raises(SignatureInvalide):
        decoder_signature(base64.b64encode(_png()).decode())


@pytest.mark.parametrize('valeur', ['', None, 0, [], {}])
def test_une_charge_absurde_est_refusee(valeur):
    from apps.accounts.signature import SignatureInvalide, decoder_signature

    with pytest.raises(SignatureInvalide):
        decoder_signature(valeur)


def test_une_image_aux_dimensions_inattendues_est_refusee():
    from apps.accounts.signature import SignatureInvalide, decoder_signature

    with pytest.raises(SignatureInvalide) as echec:
        decoder_signature(_url(_png(taille=(3000, 1200))))
    assert 'dimensions' in str(echec.value)


def test_une_charge_enorme_est_refusee_AVANT_le_decodage():
    """Borner après avoir décodé ferait décoder 100 Mo pour les refuser."""
    from apps.accounts.signature import (
        OCTETS_MAX, PREFIXE, SignatureInvalide, decoder_signature,
    )

    enorme = PREFIXE + 'A' * (OCTETS_MAX * 4 // 3 + 100)
    with pytest.raises(SignatureInvalide) as echec:
        decoder_signature(enorme)
    assert 'volumineuse' in str(echec.value)


def test_le_base64_invalide_est_refuse():
    from apps.accounts.signature import (
        PREFIXE, SignatureInvalide, decoder_signature,
    )

    with pytest.raises(SignatureInvalide):
        decoder_signature(PREFIXE + '!!!pas du base64!!!')


def test_la_transparence_est_conservee():
    """Un fond blanc masquerait l'en-tête du modèle de devis."""
    from PIL import Image

    from apps.accounts.signature import decoder_signature

    octets = decoder_signature(_url(_png()))
    image = Image.open(io.BytesIO(octets))
    assert image.mode in ('RGBA', 'LA', 'P')
    alpha = image.convert('RGBA').getchannel('A')
    # Au moins un pixel totalement transparent : le fond n'a pas ete peint.
    assert alpha.getextrema()[0] == 0


# ═══ L'ENREGISTREMENT ═══════════════════════════════════════════════════════

def test_la_signature_tracee_s_enregistre(connecte):
    reponse = connecte.post(reverse('accounts:signature_save'),
                            {'signature': _url(_png())})

    assert reponse.status_code == 200, reponse.content
    connecte.user.profile.refresh_from_db()
    assert connecte.user.profile.signature


def test_la_reponse_donne_l_adresse_de_l_image(connecte):
    reponse = connecte.post(reverse('accounts:signature_save'),
                            {'signature': _url(_png())})

    donnees = reponse.json()
    assert donnees['url'].endswith('.png')
    assert 'message' in donnees


def test_un_cadre_vide_est_refuse_par_le_SERVEUR(connecte):
    """Le navigateur le refuse déjà, mais c'est contournable : c'est le
    serveur qui décide."""
    reponse = connecte.post(reverse('accounts:signature_save'),
                            {'signature': _url(_png(trace=False))})

    assert reponse.status_code == 400
    assert 'tracez' in reponse.json()['erreur'].lower()
    connecte.user.profile.refresh_from_db()
    assert not connecte.user.profile.signature


def test_le_refus_nomme_la_cause(connecte):
    """« Erreur » ne dirait pas si le cadre est vide ou le fichier
    illisible : les deux n'ont pas le même remède."""
    vide = connecte.post(reverse('accounts:signature_save'),
                         {'signature': _url(_png(trace=False))})
    pas_une_image = connecte.post(reverse('accounts:signature_save'),
                                  {'signature': _url(b'xxxx')})

    assert vide.json()['erreur'] != pas_une_image.json()['erreur']


def test_l_enregistrement_refuse_un_GET(connecte):
    reponse = connecte.get(reverse('accounts:signature_save'))
    assert reponse.status_code == 405


def test_l_enregistrement_exige_une_connexion(client, entreprise, depot):
    reponse = client.post(reverse('accounts:signature_save'),
                          {'signature': _url(_png())})
    assert reponse.status_code == 302


def test_reenregistrer_ne_laisse_pas_s_accumuler_les_fichiers(connecte,
                                                              depot):
    """Sans suppression de l'ancien, le stockage renomme le nouveau
    (« signature-3_a8f2.png ») et les fichiers s'empilent — un par
    réenregistrement, indéfiniment."""
    for _ in range(3):
        connecte.post(reverse('accounts:signature_save'),
                      {'signature': _url(_png())})

    dossier = depot / 'signatures'
    assert len(list(dossier.iterdir())) == 1, list(dossier.iterdir())


def test_reenregistrer_remplace_bien_le_trace(connecte, depot):
    from PIL import Image, ImageDraw

    connecte.post(reverse('accounts:signature_save'),
                  {'signature': _url(_png())})
    connecte.user.profile.refresh_from_db()
    # Lire PUIS refermer : une poignee laissee ouverte fait echouer
    # os.remove sous Windows, et le test accuserait la vue a tort.
    premier = connecte.user.profile.signature.read()
    connecte.user.profile.signature.close()

    # Un second trace, nettement different.
    image = Image.new('RGBA', (900, 300), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle([(50, 50), (850, 250)],
                                    outline=(17, 17, 17, 255), width=12)
    tampon = io.BytesIO()
    image.save(tampon, 'PNG')

    connecte.post(reverse('accounts:signature_save'),
                  {'signature': _url(tampon.getvalue())})
    connecte.user.profile.refresh_from_db()
    assert connecte.user.profile.signature.read() != premier


# ═══ LE RETRAIT ═════════════════════════════════════════════════════════════

def test_le_retrait_efface_le_fichier_du_disque(connecte, depot):
    """Une signature manuscrite est une donnée personnelle : la laisser
    traîner après un retrait explicite serait difficile à justifier."""
    connecte.post(reverse('accounts:signature_save'),
                  {'signature': _url(_png())})
    dossier = depot / 'signatures'
    assert list(dossier.iterdir())

    connecte.post(reverse('accounts:signature_delete'))

    connecte.user.profile.refresh_from_db()
    assert not connecte.user.profile.signature
    assert not list(dossier.iterdir())


def test_le_retrait_refuse_un_GET(connecte):
    reponse = connecte.get(reverse('accounts:signature_delete'))
    assert reponse.status_code == 405


def test_retirer_sans_signature_ne_casse_rien(connecte):
    reponse = connecte.post(reverse('accounts:signature_delete'))
    assert reponse.status_code == 302


# ═══ L'ÉCRAN ════════════════════════════════════════════════════════════════

def test_le_profil_montre_le_cadre_et_plus_le_televersement(connecte):
    corps = connecte.get(reverse('accounts:profile')).content.decode()

    assert 'toile-signature' in corps
    assert 'orion-signature.js' in corps
    # Le champ fichier a bien disparu.
    assert 'name="signature"' not in corps


def test_la_signature_n_est_plus_dans_le_formulaire_de_profil():
    """Deux chemins d'écriture pour le même champ, dont un sans le contrôle
    du cadre vide, finiraient par laisser passer une signature invisible."""
    from apps.accounts.forms import UserProfileForm

    assert 'signature' not in UserProfileForm.base_fields


def test_la_toile_est_plus_grande_que_son_affichage(connecte):
    """Dessiner à la taille CSS donnerait une image de ~300 px de large,
    floue à l'impression."""
    corps = connecte.get(reverse('accounts:profile')).content.decode()

    assert 'width="900"' in corps
    assert 'height="300"' in corps


def test_la_toile_neutralise_le_defilement_tactile(connecte):
    """Sans touch-action:none, le doigt fait défiler la page au lieu de
    tracer — l'écran est inutilisable sur téléphone."""
    corps = connecte.get(reverse('accounts:profile')).content.decode()
    assert 'touch-action:none' in corps


def test_l_apercu_est_cache_quand_il_n_y_a_pas_de_signature(connecte):
    corps = connecte.get(reverse('accounts:profile')).content.decode()
    assert 'hidden' in corps

    connecte.post(reverse('accounts:signature_save'),
                  {'signature': _url(_png())})
    corps = connecte.get(reverse('accounts:profile')).content.decode()
    assert 'signatures/signature-' in corps


# ═══ JUSQUE SUR LE DEVIS ════════════════════════════════════════════════════

def test_la_signature_tracee_arrive_sur_le_devis(connecte, entreprise, depot):
    """Le bout en bout : tracée au profil, apposée sur le PDF."""
    from apps.crm.models import Customer
    from apps.sales.models import Quote, QuoteTemplate, QuoteTemplateField
    from apps.sales.quote_pdf import remplir_modele
    from django.core.files.base import ContentFile
    from pypdf import PdfReader
    from reportlab.pdfgen import canvas

    connecte.post(reverse('accounts:signature_save'),
                  {'signature': _url(_png())})
    # Le profil de l'objet en memoire a ete lu AVANT l'enregistrement : sans
    # ce rafraichissement, images_du_devis lirait une copie en cache
    # depourvue de signature, et le test echouerait pour une raison qui
    # n'existe pas en production.
    connecte.user.profile.refresh_from_db()

    client_crm = Customer.objects.create(company=entreprise, name='Client')
    devis = Quote.objects.create(company=entreprise, number='DEV-1',
                                 customer=client_crm,
                                 salesperson=connecte.user)

    tampon = io.BytesIO()
    feuille = canvas.Canvas(tampon, pagesize=(595, 842))
    feuille.drawString(40, 800, 'ENTREPRISE')
    feuille.showPage()
    feuille.save()
    modele = QuoteTemplate.objects.create(company=entreprise, name='M')
    modele.pdf.save('m.pdf', ContentFile(tampon.getvalue()), save=True)
    QuoteTemplateField.objects.create(
        template=modele, cle='signature', page=1, x=380, y=90,
        largeur=150, hauteur=50)

    pdf = remplir_modele(devis, modele)
    flux = PdfReader(pdf).pages[0].get_contents().get_data().decode('latin-1')
    assert ' Do' in flux, 'la signature n-a pas ete dessinee'
