"""« Chaque utilisateur doit pouvoir changer son mot de passe, et il n'y a
pas de bouton pour télécharger l'application PC. »

CE QUI MANQUAIT

Aucune route ne permettait de changer son propre mot de passe. Seul un
administrateur pouvait le réinitialiser pour quelqu'un d'autre, ce qui
oblige à le lui transmettre — donc à le faire passer par un canal que
personne ne maîtrise. `PasswordChangeForm` était d'ailleurs déjà importé
dans `apps/accounts/forms.py`, sans être employé nulle part.

LE PIÈGE QUE CE FICHIER SURVEILLE

La session porte une empreinte du mot de passe. Dès qu'il change,
l'empreinte ne correspond plus et Django ferme la session à la requête
SUIVANTE. Sans `update_session_auth_hash`, l'utilisateur serait renvoyé à
l'écran de connexion juste après avoir réussi son changement — et le
lirait comme un échec.

C'est pourquoi le test ne se contente pas de vérifier le mot de passe en
base : il refait une requête ensuite, et exige que la session tienne.
"""
import pytest
from django.urls import reverse


@pytest.fixture
def utilisateur(db, client, django_user_model):
    from apps.accounts.models import UserProfile
    from apps.core.models import Company

    entreprise = Company.objects.create(name='Martin SA', slug='martin-sa')
    personne = django_user_model.objects.create_user(
        'jean', password='MotDePasseInitial1', is_staff=True)
    profil, _ = UserProfile.objects.get_or_create(user=personne)
    profil.companies.add(entreprise)
    client.force_login(django_user_model.objects.get(pk=personne.pk))
    session = client.session
    session['current_company_id'] = entreprise.pk
    session.save()
    return {'client': client, 'personne': personne, 'entreprise': entreprise}


# ── 1. Le mot de passe ───────────────────────────────────────────────────────

@pytest.mark.django_db
def test_l_ecran_existe(utilisateur):
    reponse = utilisateur['client'].get(reverse('accounts:changer_mot_de_passe'))
    assert reponse.status_code == 200


@pytest.mark.django_db
def test_le_mot_de_passe_change_vraiment(utilisateur):
    from django.contrib.auth import authenticate

    reponse = utilisateur['client'].post(
        reverse('accounts:changer_mot_de_passe'), {
            'old_password': 'MotDePasseInitial1',
            'new_password1': 'NouveauSecret2026!',
            'new_password2': 'NouveauSecret2026!',
        })

    assert reponse.status_code == 302
    assert authenticate(username='jean', password='NouveauSecret2026!') is not None
    assert authenticate(username='jean', password='MotDePasseInitial1') is None


@pytest.mark.django_db
def test_l_utilisateur_reste_connecte_apres_le_changement(utilisateur):
    """LE PIÈGE CENTRAL.

    Sans `update_session_auth_hash`, la requête SUIVANTE renverrait vers
    l'écran de connexion. Le changement aurait pourtant réussi — et
    passerait pour un échec.
    """
    utilisateur['client'].post(reverse('accounts:changer_mot_de_passe'), {
        'old_password': 'MotDePasseInitial1',
        'new_password1': 'NouveauSecret2026!',
        'new_password2': 'NouveauSecret2026!',
    })

    suite = utilisateur['client'].get(reverse('accounts:profile'))

    assert suite.status_code == 200, 'la session a saute apres le changement'
    assert suite.context['user'].is_authenticated


@pytest.mark.django_db
def test_l_ancien_mot_de_passe_est_exige(utilisateur):
    """Sans cette exigence, un poste laissé déverrouillé suffirait à
    s'approprier un compte."""
    from django.contrib.auth import authenticate

    reponse = utilisateur['client'].post(
        reverse('accounts:changer_mot_de_passe'), {
            'old_password': 'je-ne-le-connais-pas',
            'new_password1': 'NouveauSecret2026!',
            'new_password2': 'NouveauSecret2026!',
        })

    assert reponse.status_code == 200, 'le refus doit reafficher le formulaire'
    assert 'old_password' in reponse.context['form'].errors
    assert authenticate(username='jean', password='MotDePasseInitial1') is not None


@pytest.mark.django_db
def test_le_refus_est_affiche_et_non_silencieux(utilisateur):
    """Deux saisies differentes : l'ecran doit DIRE pourquoi. Un formulaire
    qui se recharge sans message est lu comme une panne."""
    reponse = utilisateur['client'].post(
        reverse('accounts:changer_mot_de_passe'), {
            'old_password': 'MotDePasseInitial1',
            'new_password1': 'NouveauSecret2026!',
            'new_password2': 'PasLeMeme2026!',
        })

    assert reponse.context['form'].errors
    assert 'new_password2' in reponse.content.decode()


@pytest.mark.django_db
def test_un_visiteur_non_connecte_est_refoule(client):
    reponse = client.get(reverse('accounts:changer_mot_de_passe'))
    assert reponse.status_code == 302
    assert 'login' in reponse['Location']


@pytest.mark.django_db
def test_le_profil_porte_le_lien(utilisateur):
    contenu = utilisateur['client'].get(
        reverse('accounts:profile')).content.decode()
    assert reverse('accounts:changer_mot_de_passe') in contenu


# ── 2. L'application PC ──────────────────────────────────────────────────────

def _deposer(version='1.4.2', publiee=True):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.core.models import VersionApplicationBureau
    return VersionApplicationBureau.objects.create(
        version=version, est_publiee=publiee,
        fichier=SimpleUploadedFile('OrionERP-Setup.exe', b'MZ\x90\x00faux'),
    )


@pytest.mark.django_db
def test_sans_version_publiee_aucun_bouton(utilisateur):
    """Un bouton qui pointe vers le vide est pire que pas de bouton.

    Le bouton vit sur le TABLEAU DE BORD : la fiche de profil n'est pas
    l'endroit ou l'on va chercher une application a installer.
    """
    contenu = utilisateur['client'].get(
        reverse('core:dashboard')).content.decode()

    assert reverse('core_application_pc:telecharger') not in contenu


@pytest.mark.django_db
def test_une_version_publiee_fait_apparaitre_le_bouton(utilisateur):
    _deposer(version='1.4.2')

    contenu = utilisateur['client'].get(
        reverse('core:dashboard')).content.decode()

    assert reverse('core_application_pc:telecharger') in contenu
    assert '1.4.2' in contenu
    assert 'Version PC' in contenu


@pytest.mark.django_db
def test_le_profil_ne_porte_plus_l_application(utilisateur):
    """Le bouton a DEMENAGE : le laisser aux deux endroits donnerait deux
    chemins a maintenir pour la meme action."""
    _deposer()

    contenu = utilisateur['client'].get(
        reverse('accounts:profile')).content.decode()

    assert reverse('core_application_pc:telecharger') not in contenu


@pytest.mark.django_db
def test_le_telechargement_sert_bien_le_fichier(utilisateur):
    _deposer()

    reponse = utilisateur['client'].get(
        reverse('core_application_pc:telecharger'))

    assert reponse.status_code == 200
    assert 'attachment' in reponse['Content-Disposition']
    # FileResponse diffuse : il n'a pas d'attribut « content ».
    assert b''.join(reponse.streaming_content).startswith(b'MZ')


@pytest.mark.django_db
def test_une_version_retiree_n_est_plus_servie(utilisateur):
    _deposer(publiee=False)

    reponse = utilisateur['client'].get(
        reverse('core_application_pc:telecharger'))

    assert reponse.status_code == 404


@pytest.mark.django_db
def test_le_telechargement_exige_une_connexion(client):
    """media/ est public sur cette installation : servir l'installeur par
    une vue est ce qui le reserve aux comptes de la maison."""
    _deposer()

    reponse = client.get(reverse('core_application_pc:telecharger'))

    assert reponse.status_code == 302
    assert 'login' in reponse['Location']


@pytest.mark.django_db
def test_un_utilisateur_ordinaire_ne_peut_pas_publier(utilisateur):
    reponse = utilisateur['client'].get(reverse('core_application_pc:publier'))

    assert reponse.status_code == 302, 'la publication doit etre reservee'


@pytest.mark.django_db
def test_une_taille_reste_lisible_meme_si_le_fichier_a_disparu(db):
    """Un fichier reference en base mais absent du disque (restauration
    partielle) ne doit pas faire tomber la page qui affiche sa taille."""
    from apps.core.models import VersionApplicationBureau

    version = VersionApplicationBureau.objects.create(
        version='9.9.9', fichier='application-bureau/inexistant.exe')

    assert version.taille_lisible == ''


def test_le_formulaire_de_depot_envoie_bien_les_fichiers():
    """Sans « enctype », le navigateur n'envoie PAS le fichier : le champ
    s'afficherait, l'installeur serait choisi, l'enregistrement
    reussirait -- et rien n'aurait ete depose."""
    from pathlib import Path

    gabarit = Path('templates/core/application_pc.html').read_text(encoding='utf-8')

    assert 'enctype="multipart/form-data"' in gabarit
