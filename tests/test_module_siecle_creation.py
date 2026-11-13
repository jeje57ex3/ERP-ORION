"""« Créer un module pour rattacher SIÈCLE Création. »

CE QUI MANQUAIT

L'entrée de menu « SIÈCLE Création » existait dans NAV_MODULES depuis le
début, avec l'identifiant « siecle_creations ». Mais AUCUN code module ne la
gouvernait : elle était absente d'ALL_MODULE_CODES, de MODULE_LABELS et de
MODULE_NAV_IDS.

Conséquence : `filter_nav_modules` ne trouvait jamais de module activé qui
la couvre, donc elle était invisible à tout utilisateur non super-admin — et
aucune case de l'interface ne pouvait rien y changer.

POURQUOI LE DÉFAUT A SURVÉCU SI LONGTEMPS

Parce qu'un super-admin reçoit la liste de navigation ENTIÈRE, sans
filtrage. Celui qui installe et vérifie l'ERP est précisément celui qui ne
peut pas voir le problème. Ces tests regardent donc avec les yeux d'un
SALARIÉ, pas d'un administrateur.
"""
import pytest
from django.urls import reverse


@pytest.fixture
def entreprise_et_salarie(db, client, django_user_model):
    from apps.accounts.models import UserProfile
    from apps.core.models import Company
    from apps.private_saas.models import ALL_MODULE_CODES, CompanyModule

    entreprise = Company.objects.create(name='Siècle SA', slug='siecle-sa')
    # Toutes les lignes existent ; seul « siecle_creations » sera bascule.
    for code in ALL_MODULE_CODES:
        CompanyModule.objects.update_or_create(
            company=entreprise, module_code=code,
            defaults={'is_enabled': True})

    def connecter(super_admin=False):
        utilisateur = django_user_model.objects.create_user(
            'salarie' if not super_admin else 'patron',
            password='x', is_superuser=super_admin, is_staff=True)
        profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
        profil.role = 'superadmin' if super_admin else 'admin'
        profil.save()
        profil.companies.add(entreprise)
        client.force_login(django_user_model.objects.get(pk=utilisateur.pk))
        session = client.session
        session['current_company_id'] = entreprise.pk
        session.save()
        return utilisateur

    def basculer(actif):
        CompanyModule.objects.update_or_create(
            company=entreprise, module_code='siecle_creations',
            defaults={'is_enabled': actif})

    return {'client': client, 'connecter': connecter,
            'basculer': basculer, 'entreprise': entreprise}


# ── 1. Le registre ───────────────────────────────────────────────────────────

def test_le_module_existe_dans_les_trois_structures():
    """Les trois doivent s'accorder : un code sans libellé n'est pas
    affichable dans l'interface, et un code sans identifiant de navigation
    n'allume aucun menu."""
    from apps.private_saas.models import (ALL_MODULE_CODES, MODULE_LABELS,
                                          MODULE_NAV_IDS)

    assert 'siecle_creations' in ALL_MODULE_CODES
    assert MODULE_LABELS['siecle_creations'] == 'SIÈCLE Création'
    assert MODULE_NAV_IDS['siecle_creations'] == ['siecle_creations']


@pytest.mark.django_db
def test_le_module_est_propose_dans_le_formulaire_de_l_interface(
        entreprise_et_salarie):
    """LE BUT DE LA DEMANDE : pouvoir le cocher sans ligne de commande.

    Le formulaire boucle sur ALL_MODULE_CODES ; si le code n'y figure pas,
    aucune case n'apparaît et le module reste inactivable à jamais.
    """
    from apps.private_saas.forms import CompanyModuleForm

    champs = CompanyModuleForm(entreprise_et_salarie['entreprise']).fields

    assert 'module_siecle_creations' in champs
    assert champs['module_siecle_creations'].label == 'SIÈCLE Création'


# ── 2. Ce que voit un salarié ────────────────────────────────────────────────

def _ids_du_menu(reponse):
    return [m['id'] for m in reponse.context['nav_modules']]


@pytest.mark.django_db
def test_module_actif_le_salarie_voit_le_menu(entreprise_et_salarie):
    entreprise_et_salarie['basculer'](True)
    entreprise_et_salarie['connecter'](super_admin=False)

    reponse = entreprise_et_salarie['client'].get(reverse('core:dashboard'))

    assert 'siecle_creations' in _ids_du_menu(reponse)


@pytest.mark.django_db
def test_module_inactif_le_menu_disparait(entreprise_et_salarie):
    """L'autre moitié du contrat : une case décochée doit AVOIR un effet."""
    entreprise_et_salarie['basculer'](False)
    entreprise_et_salarie['connecter'](super_admin=False)

    reponse = entreprise_et_salarie['client'].get(reverse('core:dashboard'))

    assert 'siecle_creations' not in _ids_du_menu(reponse)


# ── 3. L'adresse, pas seulement le menu ──────────────────────────────────────

@pytest.mark.django_db
def test_module_inactif_l_adresse_est_fermee(entreprise_et_salarie):
    """CE QU'UN MENU ESCAMOTABLE NE FAIT PAS.

    Cacher une entrée de navigation laisse l'adresse ouverte : il suffit de
    la taper. Sans garde sur les vues, ce ne serait pas un module.
    """
    entreprise_et_salarie['basculer'](False)
    entreprise_et_salarie['connecter'](super_admin=False)

    reponse = entreprise_et_salarie['client'].get(
        reverse('siecle_creations:dashboard'))

    assert reponse.status_code == 302
    assert 'siecle' not in reponse['Location']


@pytest.mark.django_db
def test_module_actif_l_adresse_repond(entreprise_et_salarie):
    entreprise_et_salarie['basculer'](True)
    entreprise_et_salarie['connecter'](super_admin=False)

    reponse = entreprise_et_salarie['client'].get(
        reverse('siecle_creations:dashboard'))

    assert reponse.status_code == 200


@pytest.mark.django_db
def test_le_super_admin_garde_son_acces_module_coupe(entreprise_et_salarie):
    """Poser la garde ne doit retirer l'accès à personne qui l'avait à ce
    titre : le décorateur laisse passer les super-admins."""
    entreprise_et_salarie['basculer'](False)
    entreprise_et_salarie['connecter'](super_admin=True)

    reponse = entreprise_et_salarie['client'].get(
        reverse('siecle_creations:dashboard'))

    assert reponse.status_code == 200
