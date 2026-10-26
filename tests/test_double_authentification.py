"""Double authentification : le branchement de `apps.user_security`.

L'application existait sur le disque, complète — modèles, services,
intergiciel, formulaires, API, quatre gabarits et quatre tests — mais
**absente de `LOCAL_APPS` et des URLs**. Du code inerte, et ses tests
n'avaient jamais pu tourner.

Ce fichier ne reteste pas la mécanique TOTP, que `apps/user_security/
tests.py` couvre déjà. Il verrouille le **branchement**, où sont les deux
pièges qui auraient coûté cher :

**Le réglage à False.** Le code de l'application défaut à `True` pour
`ORION_2FA_REQUIRED_FOR_SUPERUSERS`. L'enregistrer tel quel aurait forcé
TOUS les super administrateurs à configurer la 2FA dès la requête suivante,
sur un ERP en service. Un gabarit cassé, une horloge décalée, un téléphone
indisponible — et l'administrateur est verrouillé dehors de son propre
outil par une mise à jour qu'il n'a pas demandée.

**`pyotp` absent des requirements.** Il était importé par le code et
manquait du fichier d'installation, alors que `qrcode` y figurait — ce qui
rendait l'oubli d'autant plus facile à manquer. Sur un serveur installé
depuis `requirements.txt`, l'intergiciel aurait planté à l'import : 500 sur
toutes les pages.

**Et la position de l'intergiciel.** Il lit `request.user` ; placé avant
`AuthenticationMiddleware`, il ne verrait jamais personne — c'est
exactement le défaut qui rendait l'exemption super-admin de la maintenance
inopérante plus tôt dans ce projet.
"""

import os
import re

import pytest
from django.urls import reverse

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── 1. Le réglage qui évite le verrouillage ─────────────────────────────────

def test_la_2fa_n_est_pas_imposee_aux_super_admins():
    """LE piège principal.

    L'application défaut à True. Imposer la 2FA par un déploiement, sur un
    ERP en service, c'est risquer d'enfermer dehors celui qui l'administre.
    Elle reste disponible et s'active compte par compte.
    """
    from django.conf import settings

    assert settings.ORION_2FA_REQUIRED_FOR_SUPERUSERS is False


def test_le_reglage_est_pilotable_par_l_environnement():
    """Pour que l'imposer plus tard ne demande pas de modifier le code."""
    chemin = os.path.join(RACINE, 'erp_btp', 'settings', 'base.py')
    with open(chemin, encoding='utf-8-sig') as flux:
        contenu = flux.read()
    assert "config(\n    'ORION_2FA_REQUIRED_FOR_SUPERUSERS'" in contenu \
        or "config('ORION_2FA_REQUIRED_FOR_SUPERUSERS'" in contenu


def test_un_super_admin_sans_2fa_n_est_pas_redirige(client, django_user_model):
    """La conséquence concrète du réglage, mesurée sur une vraie requête.

    Sans lui, cette requête partirait vers la configuration de la 2FA.
    """
    from apps.accounts.models import UserProfile
    from apps.core.models import Company

    entreprise = Company.objects.create(name='X SA', slug='x-sa')
    patron = django_user_model.objects.create_user(
        'root', password='x', is_superuser=True, is_staff=True)
    profil, _ = UserProfile.objects.get_or_create(user=patron)
    profil.role = 'superadmin'
    profil.save()
    profil.companies.add(entreprise)

    client.force_login(django_user_model.objects.get(pk=patron.pk))
    reponse = client.get(reverse('accounts:profile'))
    assert reponse.status_code == 200


# ── 2. La dépendance qui manquait ───────────────────────────────────────────

def test_pyotp_est_dans_les_requirements():
    """Il était importé par le code et absent du fichier d'installation.

    Sur un serveur installé depuis requirements.txt, l'intergiciel aurait
    planté à l'import — donc 500 sur toutes les pages, pas seulement sur
    celles de la 2FA.
    """
    chemin = os.path.join(RACINE, 'requirements.txt')
    with open(chemin, encoding='utf-8') as flux:
        contenu = flux.read()
    assert re.search(r'^pyotp==', contenu, re.MULTILINE), (
        'pyotp est importé par apps/user_security et doit être épinglé')


def test_les_dependances_de_l_app_sont_toutes_declarees():
    """La règle générale, pour qu'un futur import ne reparte pas sans.

    On relève les modules tiers importés par l'application et on vérifie
    que chacun figure dans requirements.txt.
    """
    dossier = os.path.join(RACINE, 'apps', 'user_security')
    chemin_req = os.path.join(RACINE, 'requirements.txt')
    with open(chemin_req, encoding='utf-8') as flux:
        requirements = flux.read().lower()

    # Modules de la bibliothèque standard et paquets déjà garantis par le
    # socle : inutile de les redéclarer.
    connus = {
        'base64', 'hashlib', 'io', 'secrets', 'string', 'json', 'os', 're',
        'datetime', 'typing', 'functools', 'django', 'rest_framework',
        'apps', 'collections', 'urllib', 'uuid', 'time', 'logging',
    }
    manquants = set()
    for nom in sorted(os.listdir(dossier)):
        if not nom.endswith('.py'):
            continue
        with open(os.path.join(dossier, nom), encoding='utf-8') as flux:
            for ligne in flux:
                trouve = re.match(r'\s*(?:import|from)\s+([a-zA-Z0-9_]+)',
                                  ligne)
                if not trouve:
                    continue
                module = trouve.group(1)
                if module in connus or module.startswith('_'):
                    continue
                if module.lower() not in requirements:
                    manquants.add(f'{module} (importé par {nom})')

    assert not manquants, (
        'modules tiers importés mais absents de requirements.txt :\n  '
        + '\n  '.join(sorted(manquants)))


# ── 3. L'ordre des intergiciels ─────────────────────────────────────────────

def test_l_intergiciel_suit_l_authentification():
    """Il lit request.user, qui n'existe pas avant AuthenticationMiddleware.

    Placé avant, il ne verrait jamais personne et ne ferait rien — défaut
    silencieux, exactement celui qui rendait inopérante l'exemption
    super-admin de la page de maintenance.
    """
    from django.conf import settings

    liste = list(settings.MIDDLEWARE)
    auth = liste.index(
        'django.contrib.auth.middleware.AuthenticationMiddleware')
    deux_facteurs = liste.index(
        'apps.user_security.middleware.RequireTwoFactorMiddleware')
    assert deux_facteurs > auth


def test_l_app_est_enregistree():
    from django.apps import apps

    assert apps.is_installed('apps.user_security')


# ── 4. Les adresses, et la boucle à ne pas créer ────────────────────────────

@pytest.mark.parametrize('nom,chemin', [
    ('user_security:account_security', '/account/security/'),
    ('user_security:two_factor_setup', '/account/security/2fa/setup/'),
    ('user_security:two_factor_verify', '/auth/2fa/verify/'),
    ('user_security:recovery_codes', '/account/security/2fa/recovery-codes/'),
])
def test_les_adresses_sont_a_la_racine(nom, chemin):
    """Montées sous un préfixe, elles sortiraient des exemptions de
    l'intergiciel — et la page de vérification deviendrait elle-même
    soumise à vérification. Une boucle de redirection sans sortie."""
    assert reverse(nom) == chemin


def test_chaque_adresse_de_l_app_est_exemptee_par_l_intergiciel():
    """La propriété qui garantit l'absence de boucle.

    Vérifiée sur les préfixes réels de l'intergiciel, et non supposée :
    un chemin ajouté plus tard hors des exemptions enfermerait
    l'utilisateur.
    """
    from apps.user_security.middleware import EXEMPT_PREFIXES

    for nom in ('user_security:account_security',
                'user_security:two_factor_setup',
                'user_security:two_factor_verify',
                'user_security:recovery_codes'):
        adresse = reverse(nom)
        assert any(adresse.startswith(p) for p in EXEMPT_PREFIXES), (
            f'{adresse} n\'est pas exemptée : l\'utilisateur y serait '
            f'redirigé en boucle')


def test_la_page_de_securite_s_affiche(client, django_user_model):
    from apps.accounts.models import UserProfile
    from apps.core.models import Company

    entreprise = Company.objects.create(name='X SA', slug='x-sa')
    salarie = django_user_model.objects.create_user('jean', password='x')
    profil, _ = UserProfile.objects.get_or_create(user=salarie)
    profil.companies.add(entreprise)

    client.force_login(django_user_model.objects.get(pk=salarie.pk))
    reponse = client.get(reverse('user_security:account_security'))
    assert reponse.status_code == 200


def test_un_anonyme_ne_voit_pas_la_page_de_securite(client):
    reponse = client.get(reverse('user_security:account_security'))
    assert reponse.status_code in (301, 302)


# ── 5. Le champ mort de accounts, remis en accord ───────────────────────────

pytestmark = pytest.mark.django_db


def test_le_champ_du_profil_reflete_l_activation(django_user_model):
    """`accounts.UserProfile.two_factor_enabled` n'est lu nulle part.

    Ce n'est donc pas une case à cocher qui mentirait à l'utilisateur,
    c'est un champ mort. Mais un champ mort nommé « 2FA activé » est un
    piège pour qui le lira : il resterait à False sur un compte réellement
    protégé. La source de vérité est UserTwoFactorSettings ; ce champ en
    devient un reflet.
    """
    import pyotp

    from apps.accounts.models import UserProfile
    from apps.user_security.services import (
        disable_2fa, enable_2fa, start_2fa_setup,
    )

    utilisateur = django_user_model.objects.create_user('marc',
                                                        password='motdepasse')
    UserProfile.objects.get_or_create(user=utilisateur)

    reglages = start_2fa_setup(utilisateur)
    code = pyotp.TOTP(reglages.totp_secret).now()
    actif, codes = enable_2fa(utilisateur, code)
    assert actif is True, 'l\'activation doit réussir avec un code valide'
    assert codes, 'des codes de récupération doivent être rendus'

    utilisateur.refresh_from_db()
    assert utilisateur.profile.two_factor_enabled is True

    assert disable_2fa(utilisateur, 'motdepasse') is True
    utilisateur.refresh_from_db()
    assert utilisateur.profile.two_factor_enabled is False


def test_l_activation_marche_sans_profil(django_user_model):
    """Un User sans UserProfile existe — createsuperuser, profil effacé.

    Refuser d'activer la 2FA pour cette raison serait absurde : le reflet
    sur le profil est un confort, la protection du compte ne l'est pas.
    """
    import pyotp

    from apps.accounts.models import UserProfile
    from apps.user_security.services import enable_2fa, start_2fa_setup

    utilisateur = django_user_model.objects.create_user('nu', password='x')
    UserProfile.objects.filter(user=utilisateur).delete()
    utilisateur.refresh_from_db()

    reglages = start_2fa_setup(utilisateur)
    actif, _codes = enable_2fa(
        utilisateur, pyotp.TOTP(reglages.totp_secret).now())
    assert actif is True


# ── 6. La preuve que le garde-fou mord ──────────────────────────────────────

def test_a_True_le_super_admin_est_bien_detourne(client, django_user_model,
                                                 settings):
    """Sans celui-ci, le test du défaut à False ne prouverait rien.

    Un test qui passe parce que le mécanisme qu'il surveille est inerte est
    décoratif. On force donc le réglage à True et on mesure le détournement
    vers la configuration de la 2FA : c'est la preuve que le False du
    déploiement évite un verrouillage réel, et non théorique.
    """
    from apps.accounts.models import UserProfile
    from apps.core.models import Company

    settings.ORION_2FA_REQUIRED_FOR_SUPERUSERS = True

    entreprise = Company.objects.create(name='Y SA', slug='y-sa')
    patron = django_user_model.objects.create_user(
        'chef', password='x', is_superuser=True, is_staff=True)
    profil, _ = UserProfile.objects.get_or_create(user=patron)
    profil.role = 'superadmin'
    profil.save()
    profil.companies.add(entreprise)

    client.force_login(django_user_model.objects.get(pk=patron.pk))
    reponse = client.get(reverse('accounts:profile'))

    assert reponse.status_code == 302
    assert reponse['Location'] == reverse('user_security:two_factor_setup')


def test_a_True_la_page_de_configuration_reste_joignable(client,
                                                         django_user_model,
                                                         settings):
    """La sortie du piège.

    L'intergiciel détourne vers la configuration ; si cette page était
    elle-même détournée, l'utilisateur tournerait en rond sans jamais
    pouvoir activer la 2FA qu'on lui impose. C'est précisément pourquoi les
    adresses sont montées à la racine, sous les préfixes exemptés.
    """
    from apps.accounts.models import UserProfile
    from apps.core.models import Company

    settings.ORION_2FA_REQUIRED_FOR_SUPERUSERS = True

    entreprise = Company.objects.create(name='Z SA', slug='z-sa')
    patron = django_user_model.objects.create_user(
        'patronne', password='x', is_superuser=True, is_staff=True)
    profil, _ = UserProfile.objects.get_or_create(user=patron)
    profil.role = 'superadmin'
    profil.save()
    profil.companies.add(entreprise)

    client.force_login(django_user_model.objects.get(pk=patron.pk))
    reponse = client.get(reverse('user_security:two_factor_setup'))
    assert reponse.status_code == 200


# ── 7. La porte de sortie ───────────────────────────────────────────────────

def test_la_reinitialisation_remet_le_profil_a_faux(django_user_model):
    """Régression de ma propre main.

    `reset_user_2fa` est le recours de celui qui a perdu son téléphone. Elle
    supprimait les réglages sans toucher au reflet : le profil aurait
    continué d'affirmer « 2FA active » sur un compte qui ne l'avait plus —
    le champ qui mentait de nouveau, ce que le reflet existe pour empêcher.
    """
    import pyotp
    from django.core.management import call_command

    from apps.accounts.models import UserProfile
    from apps.user_security.models import UserTwoFactorSettings
    from apps.user_security.services import enable_2fa, start_2fa_setup

    utilisateur = django_user_model.objects.create_user('perdu', password='x')
    UserProfile.objects.get_or_create(user=utilisateur)
    reglages = start_2fa_setup(utilisateur)
    enable_2fa(utilisateur, pyotp.TOTP(reglages.totp_secret).now())
    utilisateur.refresh_from_db()
    assert utilisateur.profile.two_factor_enabled is True

    call_command('reset_user_2fa', 'perdu')

    utilisateur.refresh_from_db()
    assert utilisateur.profile.two_factor_enabled is False
    assert not UserTwoFactorSettings.objects.filter(user=utilisateur).exists()


def test_la_reinitialisation_signale_un_nom_inconnu():
    """Un script doit pouvoir distinguer « c'est fait » de « nom inconnu »."""
    from django.core.management import call_command
    from django.core.management.base import CommandError

    with pytest.raises(CommandError):
        call_command('reset_user_2fa', 'personne-de-ce-nom')
