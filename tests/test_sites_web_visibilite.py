"""« Le site SIÈCLE n'apparaît pas dans l'ERP. »

CE QUI SE PASSAIT

« website_list » filtrait sur l'entreprise active SANS AUCUNE DÉROGATION.
Un site rattaché à une autre entreprise était donc introuvable, y compris
pour un super-admin — et l'écran affirmait alors :

    « Aucun site web n'a encore été créé »

Cette phrase est le vrai défaut. Elle ne dit pas « rien ici », elle dit
« rien nulle part », et elle envoie créer un second site au lieu d'aller
chercher où était le premier.

CE QUE CE TEST PROTÈGE SURTOUT

Élargir une liste multi-entreprises est exactement le geste qui a déjà fait
fuiter des données ailleurs dans cet ERP. La moitié de ce fichier ne vérifie
donc pas que le super-admin voit plus, mais qu'un utilisateur ORDINAIRE ne
voit rien de plus — même en forgeant « ?toutes=1 » à la main.
"""
import pytest
from django.urls import reverse


@pytest.fixture
def deux_entreprises(db, client, django_user_model):
    """Deux entreprises ; le site SIÈCLE appartient à la SECONDE."""
    from apps.accounts.models import UserProfile
    from apps.core.models import Company
    from apps.private_saas.models import ALL_MODULE_CODES, CompanyModule
    from apps.websites.models import Website

    active = Company.objects.create(name='Orion SARL', slug='orion-sarl')
    ailleurs = Company.objects.create(name='Siècle SA', slug='siecle-sa')

    for entreprise in (active, ailleurs):
        for code in ALL_MODULE_CODES:
            CompanyModule.objects.update_or_create(
                company=entreprise, module_code=code,
                defaults={'is_enabled': True})

    site_siecle = Website.objects.create(
        company=ailleurs, name='SIÈCLE', slug='siecle',
        site_type='ecommerce', is_active=True)
    site_local = Website.objects.create(
        company=active, name='Vitrine Orion', slug='vitrine-orion',
        site_type='showcase', is_active=True)

    def connecter(nom, super_admin):
        utilisateur = django_user_model.objects.create_user(
            nom, password='x', is_superuser=super_admin, is_staff=True)
        profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
        profil.role = 'superadmin' if super_admin else 'admin'
        profil.save()
        profil.companies.add(active)
        client.force_login(django_user_model.objects.get(pk=utilisateur.pk))
        session = client.session
        session['current_company_id'] = active.pk
        session.save()
        return utilisateur

    return {
        'client': client, 'connecter': connecter,
        'active': active, 'ailleurs': ailleurs,
        'siecle': site_siecle, 'local': site_local,
    }


def _noms(reponse):
    return [s.name for s in reponse.context['websites']]


# ── 1. La cloison, d'abord ───────────────────────────────────────────────────

@pytest.mark.django_db
def test_un_utilisateur_ordinaire_ne_voit_jamais_l_autre_entreprise(deux_entreprises):
    """LA GARANTIE LA PLUS IMPORTANTE DE CE FICHIER."""
    deux_entreprises['connecter']('employe', super_admin=False)

    reponse = deux_entreprises['client'].get(reverse('websites:website_list'))

    assert reponse.status_code == 200
    assert _noms(reponse) == ['Vitrine Orion']
    assert 'SIÈCLE' not in _noms(reponse)


@pytest.mark.django_db
def test_un_utilisateur_ordinaire_ne_peut_pas_forger_l_elargissement(deux_entreprises):
    """« ?toutes=1 » se tape dans la barre d'adresse. Si le paramètre
    suffisait, la cloison ne tiendrait qu'à l'absence de curiosité."""
    deux_entreprises['connecter']('employe', super_admin=False)

    reponse = deux_entreprises['client'].get(
        reverse('websites:website_list') + '?toutes=1')

    assert _noms(reponse) == ['Vitrine Orion']
    assert reponse.context['toutes_entreprises'] is False
    assert reponse.context['nb_sites_ailleurs'] == 0, (
        "l'existence d'un site ailleurs ne doit pas non plus etre revelee")


# ── 2. Ce que le super-admin gagne ───────────────────────────────────────────

@pytest.mark.django_db
def test_par_defaut_le_super_admin_reste_sur_son_entreprise(deux_entreprises):
    """On n'élargit pas tout seul : une liste qui change de portée selon
    qui regarde est une liste dont on ne sait plus ce qu'elle montre."""
    deux_entreprises['connecter']('patron', super_admin=True)

    reponse = deux_entreprises['client'].get(reverse('websites:website_list'))

    assert _noms(reponse) == ['Vitrine Orion']
    assert reponse.context['toutes_entreprises'] is False


@pytest.mark.django_db
def test_le_super_admin_est_averti_que_des_sites_vivent_ailleurs(deux_entreprises):
    """LE CŒUR DU SIGNALEMENT : l'absence doit se distinguer de l'inexistence."""
    deux_entreprises['connecter']('patron', super_admin=True)

    reponse = deux_entreprises['client'].get(reverse('websites:website_list'))

    assert reponse.context['nb_sites_ailleurs'] == 1
    contenu = reponse.content.decode()
    assert 'SIÈCLE' in contenu, 'le nom du site manquant doit etre cite'
    assert 'Siècle SA' in contenu, "l'entreprise qui le detient doit etre citee"
    assert 'toutes=1' in contenu, 'il faut un moyen d’aller le voir'


@pytest.mark.django_db
def test_le_super_admin_qui_demande_tout_voit_tout(deux_entreprises):
    deux_entreprises['connecter']('patron', super_admin=True)

    reponse = deux_entreprises['client'].get(
        reverse('websites:website_list') + '?toutes=1')

    assert sorted(_noms(reponse)) == ['SIÈCLE', 'Vitrine Orion']
    assert reponse.context['toutes_entreprises'] is True


# ── 3. La phrase qui mentait ─────────────────────────────────────────────────

@pytest.mark.django_db
def test_l_etat_vide_n_affirme_plus_qu_aucun_site_n_existe(deux_entreprises):
    """Le défaut rapporté, dans sa forme la plus nuisible.

    Entreprise active sans aucun site, alors qu'il en existe un ailleurs :
    l'écran disait « Aucun site web n'a encore été créé ».
    """
    deux_entreprises['local'].delete()
    deux_entreprises['connecter']('patron', super_admin=True)

    contenu = deux_entreprises['client'].get(
        reverse('websites:website_list')).content.decode()

    assert "Aucun site web n&#x27;a encore" not in contenu \
        and "Aucun site web n'a encore" not in contenu, (
            'la liste affirme encore qu’aucun site n’existe')
    assert 'Aucun site pour cette entreprise' in contenu


@pytest.mark.django_db
def test_sans_site_nulle_part_le_message_d_origine_demeure(deux_entreprises):
    """On ne remplace le message que lorsqu'il serait faux. Une installation
    neuve doit toujours lire « aucun site n'a encore été créé »."""
    from apps.websites.models import Website
    Website.objects.all().delete()
    deux_entreprises['connecter']('patron', super_admin=True)

    contenu = deux_entreprises['client'].get(
        reverse('websites:website_list')).content.decode()

    assert 'Aucun site web n' in contenu
    assert 'Aucun site pour cette entreprise' not in contenu


# ── 4. Les compteurs suivent la portée ───────────────────────────────────────

@pytest.mark.django_db
def test_les_compteurs_suivent_la_portee_affichee(deux_entreprises):
    """Un compteur calculé sur une autre portée que la liste qu'il surmonte
    est un chiffre qui contredit ce qu'on voit juste en dessous."""
    deux_entreprises['connecter']('patron', super_admin=True)
    client = deux_entreprises['client']

    restreint = client.get(reverse('websites:website_list'))
    elargi = client.get(reverse('websites:website_list') + '?toutes=1')

    assert restreint.context['ecommerce_count'] == 0
    assert elargi.context['ecommerce_count'] == 1
