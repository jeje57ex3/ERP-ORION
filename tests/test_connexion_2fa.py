"""La connexion d'un compte protégé par 2FA — le maillon qui manquait.

Défaut de ma main, constaté en production. Symptôme rapporté : « le mot de
passe fonctionne mais pas de redirection », et un seul compte touché, le
super-administrateur. Tous les autres entraient normalement.

La cause tenait en une ligne absente. `two_factor_verify_view` attend un
utilisateur à **demi** authentifié, désigné par `orion_2fa_pending_user_id`
dans la session ; c'est elle qui appelle `login()` une fois le code validé.
Or `login_view` appelait `login()` immédiatement, et personne, dans tout le
projet, n'écrivait jamais cette clef — elle n'était que lue en trois
endroits et effacée en deux. L'intergiciel voyait donc une session
complète, 2FA activée, non vérifiée, sans clef d'attente : sa seule issue
était `logout()` puis retour à la connexion.

Le mot de passe était accepté et l'écran de connexion revenait, sans un
mot, à chaque tentative — indiscernable d'un mot de passe refusé, et
définitif. Le compte le mieux protégé était le seul inaccessible.

Ce défaut est invisible à l'unité : chaque fichier était correct, et la
pièce manquait **entre** eux. Les tests de ce fichier tiennent donc le
protocole des deux côtés — la clef est posée, et le code valide achève la
connexion — plus deux gardes de source contre sa disparition.
"""

import os
import re

import pytest
from django.urls import reverse

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MOT_DE_PASSE = 'Mot2passe!'


def _compte_protege(django_user_model, nom='protege'):
    """Un compte réel avec la 2FA activée, et son secret TOTP."""
    import pyotp
    from apps.accounts.models import UserProfile
    from apps.core.models import Company
    from apps.user_security.services import enable_2fa, start_2fa_setup

    entreprise, _ = Company.objects.get_or_create(
        slug='proteges', defaults={'name': 'Proteges SA'})
    utilisateur = django_user_model.objects.create_user(
        nom, password=MOT_DE_PASSE, is_superuser=True, is_staff=True)
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.role = 'superadmin'
    profil.save()
    profil.companies.add(entreprise)

    reglages = start_2fa_setup(utilisateur)
    enable_2fa(utilisateur, pyotp.TOTP(reglages.totp_secret).now())
    return utilisateur, reglages.totp_secret


def _se_connecte(client, utilisateur, suffixe=''):
    return client.post(
        reverse('accounts:login') + suffixe,
        {'username': utilisateur.username, 'password': MOT_DE_PASSE})


# ── 1. La panne elle-même ───────────────────────────────────────────────────

@pytest.mark.django_db
def test_un_compte_2fa_n_est_pas_renvoye_a_la_connexion(client,
                                                        django_user_model):
    """LE test de la panne : le mot de passe passe, et on n'est pas rejeté.

    Avant le correctif, cette réponse pointait sur `accounts:login` après un
    `logout()` — la boucle silencieuse qui a verrouillé le compte.
    """
    utilisateur, _ = _compte_protege(django_user_model)

    reponse = _se_connecte(client, utilisateur)

    assert reponse.status_code == 302
    assert reponse['Location'] != reverse('accounts:login')
    assert reponse['Location'] == reverse('user_security:two_factor_verify')


@pytest.mark.django_db
def test_la_connexion_pose_la_clef_d_attente(client, django_user_model):
    """La ligne qui manquait, mesurée directement dans la session."""
    from apps.user_security.services import TWO_FACTOR_PENDING_USER_KEY

    utilisateur, _ = _compte_protege(django_user_model)

    _se_connecte(client, utilisateur)

    assert client.session.get(TWO_FACTOR_PENDING_USER_KEY) == utilisateur.pk


@pytest.mark.django_db
def test_le_mot_de_passe_seul_n_authentifie_pas(client, django_user_model):
    """Le mot de passe ne suffit pas : c'est tout l'objet de la 2FA.

    Si `login()` était appelé avant la vérification, le second facteur ne
    protégerait plus rien — la session serait déjà ouverte.
    """
    utilisateur, _ = _compte_protege(django_user_model)

    _se_connecte(client, utilisateur)

    assert '_auth_user_id' not in client.session


@pytest.mark.django_db
def test_la_chaine_complete_ne_retombe_pas_sur_le_formulaire(
        client, django_user_model):
    """La panne telle qu'elle se voyait, suivie de bout en bout.

    Avec le défaut, la chaîne était : POST sur la connexion → 302 vers
    `/dashboard/` (le mot de passe EST accepté) → l'intergiciel déconnecte
    sur `/dashboard/` → 302 vers `/accounts/login/` → le formulaire. Deux
    redirections, et retour au point de départ sans un mot.

    C'est pourquoi le symptôme se décrivait « le mot de passe fonctionne
    mais pas de redirection » : la redirection avait bien lieu, et la page
    d'arrivée renvoyait aussitôt à l'expéditeur.
    """
    utilisateur, _ = _compte_protege(django_user_model)

    reponse = _se_connecte(client, utilisateur)
    reponse = client.get(reponse['Location'])

    assert reponse.status_code == 200, (
        'La page de verification doit repondre, non rediriger ailleurs.')
    assert '_auth_user_id' not in client.session


# ── 2. Le protocole complet ─────────────────────────────────────────────────

@pytest.mark.django_db
def test_le_code_valide_acheve_la_connexion(client, django_user_model):
    """De bout en bout : mot de passe, puis code, puis session ouverte.

    L'assertion du milieu n'est pas redondante avec le test précédent :
    sans elle, ce test passait AUSSI avec le défaut, parce que le mot de
    passe ouvrait déjà la session et que la vue de vérification se
    contentait de rediriger un utilisateur déjà connecté. Il mesurait donc
    une connexion que la 2FA n'avait jamais gardée.
    """
    import pyotp

    utilisateur, secret = _compte_protege(django_user_model)

    _se_connecte(client, utilisateur)
    assert '_auth_user_id' not in client.session, (
        'La session ne doit pas etre ouverte avant la verification.')

    reponse = client.post(reverse('user_security:two_factor_verify'),
                          {'code': pyotp.TOTP(secret).now()})

    assert reponse.status_code == 302
    assert client.session.get('_auth_user_id') == str(utilisateur.pk)


@pytest.mark.django_db
def test_un_code_invalide_ne_connecte_pas(client, django_user_model):
    """Sans celui-ci, le test précédent pourrait passer sur n'importe quoi."""
    utilisateur, _ = _compte_protege(django_user_model)

    _se_connecte(client, utilisateur)
    client.post(reverse('user_security:two_factor_verify'), {'code': '000000'})

    assert '_auth_user_id' not in client.session


@pytest.mark.django_db
def test_la_page_de_verification_est_joignable(client, django_user_model):
    """Si elle était détournée, le détour mènerait nulle part.

    Elle est servie à un visiteur encore anonyme : son adresse doit tomber
    sous un préfixe exempté de l'intergiciel.
    """
    utilisateur, _ = _compte_protege(django_user_model)

    _se_connecte(client, utilisateur)
    reponse = client.get(reverse('user_security:two_factor_verify'))

    assert reponse.status_code == 200


# ── 3. Ce qui ne doit surtout pas changer ───────────────────────────────────

@pytest.mark.django_db
def test_la_connexion_sans_2fa_reste_directe(client, django_user_model):
    """Non-régression du chemin que tous les autres comptes empruntent.

    Eux entraient déjà normalement, et c'est ce qui a permis d'isoler la
    cause : le défaut ne touchait que les comptes avec la 2FA activée.
    """
    from apps.accounts.models import UserProfile
    from apps.core.models import Company

    entreprise, _ = Company.objects.get_or_create(
        slug='ordinaire', defaults={'name': 'Ordinaire SA'})
    utilisateur = django_user_model.objects.create_user(
        'simple', password=MOT_DE_PASSE)
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.companies.add(entreprise)

    reponse = _se_connecte(client, utilisateur)

    assert reponse.status_code == 302
    assert reponse['Location'] != reverse('user_security:two_factor_verify')
    assert client.session.get('_auth_user_id') == str(utilisateur.pk)


@pytest.mark.django_db
def test_la_destination_demandee_survit_a_la_verification(client,
                                                          django_user_model):
    """Le « next » ne doit pas être perdu par le détour sur la 2FA."""
    utilisateur, _ = _compte_protege(django_user_model)

    reponse = _se_connecte(client, utilisateur, suffixe='?next=/erp/devis/')

    assert 'next=' in reponse['Location']
    assert 'devis' in reponse['Location']


@pytest.mark.django_db
def test_le_journal_n_affirme_pas_une_connexion_non_validee(client,
                                                            django_user_model):
    """Le journal d'audit doit dater la connexion du code, pas du mot de passe.

    J'avais d'abord ajouté une écriture explicite dans la vue de
    vérification, en croyant que mon correctif faisait disparaître ces
    connexions du journal. C'était faux, et le test l'a montré en comptant
    deux entrées : un récepteur du signal `user_logged_in` journalise déjà
    la connexion, et `login()` émet ce signal où qu'il soit appelé. Mon
    ajout était un doublon ; il est retiré.

    Ce qui reste à vérifier est plus intéressant que ce que je voulais
    prouver : avec le défaut, le journal inscrivait la connexion dès le mot
    de passe accepté — donc il affirmait une connexion que la 2FA refusait
    ensuite, et dont l'utilisateur ne voyait jamais la fin. Le journal
    mentait. Désormais l'entrée tombe avec le second facteur.
    """
    import pyotp
    from apps.core.models import AuditLog

    utilisateur, secret = _compte_protege(django_user_model)

    _se_connecte(client, utilisateur)
    assert not AuditLog.objects.filter(
        user=utilisateur, action='login').exists(), (
        'Le journal ne doit pas inscrire une connexion que la 2FA garde '
        'encore.')

    client.post(reverse('user_security:two_factor_verify'),
                {'code': pyotp.TOTP(secret).now()})

    assert AuditLog.objects.filter(
        user=utilisateur, action='login').count() == 1


# ── 4. Gardes de source contre la disparition du maillon ───────────────────

def test_quelqu_un_ecrit_la_clef_d_attente():
    """La clef doit être POSÉE, pas seulement lue.

    C'est le test qui aurait attrapé la panne. Il échoue si l'unique
    écriture de la clef disparaît à nouveau — un défaut qu'aucun test
    unitaire de fichier ne peut voir, puisque chaque fichier était correct.
    """
    chemin = os.path.join(RACINE, 'apps', 'accounts', 'views.py')
    with open(chemin, encoding='utf-8') as fichier:
        contenu = fichier.read()

    assert re.search(r'session\[\s*TWO_FACTOR_PENDING_USER_KEY\s*\]\s*=',
                     contenu), (
        'Plus personne ne pose orion_2fa_pending_user_id a la connexion : '
        'les comptes avec 2FA seront deconnectes en boucle.')


def test_le_defaut_du_reglage_absent_est_faux():
    """La mine latente, à côté de la panne.

    `getattr(settings, ..., True)` rendait le réglage actif dès que
    l'attribut disparaissait de settings, et imposait alors la 2FA à tous
    les super-administrateurs d'un coup. Ce genre de défaut n'explose qu'en
    production, là où personne ne relit la ligne.
    """
    chemin = os.path.join(RACINE, 'apps', 'user_security', 'services.py')
    with open(chemin, encoding='utf-8') as fichier:
        contenu = fichier.read()

    assert 'ORION_2FA_REQUIRED_FOR_SUPERUSERS", True' not in contenu
    assert 'ORION_2FA_REQUIRED_FOR_SUPERUSERS", False' in contenu


def test_la_deconnexion_forcee_dit_pourquoi():
    """Le silence était la moitié du problème.

    Un `logout()` muet rend la panne indiscernable d'un mot de passe
    refusé : c'est ce qui a fait chercher le mot de passe pendant que le
    défaut était ailleurs. La branche subsiste pour les sessions ouvertes
    avant le correctif ; elle doit désormais s'expliquer.
    """
    chemin = os.path.join(RACINE, 'apps', 'user_security', 'middleware.py')
    with open(chemin, encoding='utf-8') as fichier:
        contenu = fichier.read()

    assert 'messages' in contenu, (
        'La deconnexion forcee doit prevenir l utilisateur.')
    position_logout = contenu.index('logout(request)')
    assert 'messages.warning' in contenu[position_logout:], (
        'Le message doit accompagner la deconnexion forcee.')
