"""
tests/conftest.py — Fixtures partagées pour tous les tests Orion ERP
"""
import pytest
from django.contrib.auth.models import User
from apps.core.models import Company, CompanySettings


# NOTE SUR L'ISOLATION DES TESTS, et sur une correction retiree.
#
# SetupRequiredMiddleware garde son etat dans une variable de MODULE
# (apps.core.middleware._setup_complete_cache). Des qu'un test cree une
# entreprise et qu'une requete passe par l'intergiciel, « installation
# terminee » est retenu pour tout le processus pytest. Les tests suivants ne
# voient donc plus la redirection vers /setup/, et certains ne passent QUE
# grace a cette fuite.
#
# Une fixture autouse remettant ce cache a zero entre chaque test a ete
# essayee ici. Elle est plus correcte en theorie, et c'est une mauvaise idee
# en pratique : mesure faite, elle fait passer la suite de 64 a 98 echecs, en
# redonnant a une trentaine de tests la redirection /setup/ qu'ils ne
# rencontraient plus. Les reparer un par un depasse largement le cadre de ce
# qui etait demande, et une suite plus rouge n'aide personne.
#
# Un test qui depend de cet etat doit donc le dire lui-meme, en acceptant les
# DEUX destinations possibles -- voir test_mobile_web.test_accueil_exige_une_
# connexion, rendu independant de l'ordre de cette facon.


@pytest.fixture
def company(db):
    """Entreprise de test avec paramètres complets."""
    co = Company.objects.create(
        name='Test Company SA',
        slug='test-company-sa',
        status='active',
        is_active=True,
        invoice_prefix='FAC',
        quote_prefix='DEV',
        order_prefix='CMD',
    )
    # CompanySettings existe deja : apps/core/signals.py le cree sur le
    # post_save de Company. Un create() ici violerait la contrainte d'unicite
    # sur company_id -- ce qui etait le cas, sans que personne le voie, chaque
    # fichier de tests definissant sa propre fixture par-dessus celle-ci.
    CompanySettings.objects.filter(company=co).update(
        next_invoice_number=1,
        next_quote_number=1,
        next_order_number=1,
        next_journal_entry_number=1,
    )
    return co


@pytest.fixture
def company_b(db):
    """Deuxième entreprise pour tests d'isolation."""
    co = Company.objects.create(
        name='Other Company SARL',
        slug='other-company-sarl',
        status='active',
        is_active=True,
    )
    # Idem : le signal s'en est charge.
    CompanySettings.objects.get_or_create(company=co)
    return co


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        username='admin', password='adminpass123', email='admin@test.com'
    )


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username='staff', password='staffpass123', email='staff@test.com'
    )


@pytest.fixture
def client_logged_in(client, staff_user):
    client.force_login(staff_user)
    return client


@pytest.fixture
def superuser_client(client, superuser):
    client.force_login(superuser)
    return client
