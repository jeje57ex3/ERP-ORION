"""Deuxième audit de sécurité : l'authentification et ce qui l'entoure.

LE PREMIER AUDIT A COUVERT le cloisonnement entre entreprises, les
téléversements publics, l'évasion de `</style>` et le XSS stocké. Celui-ci
regarde ailleurs : d'où vient l'adresse du client, où l'on accepte de
renvoyer l'utilisateur, et combien de mots de passe on le laisse essayer.

LES QUATRE DÉFAUTS MESURÉS ICI

1. L'ADRESSE DU CLIENT ÉTAIT CELLE QU'IL CHOISISSAIT. Six endroits
   prenaient le premier élément de `X-Forwarded-For` — celui que le
   client écrit. Toutes les limitations de débit du dépôt reposaient sur
   cette valeur, donc aucune ne limitait quoi que ce soit ; et le journal
   d'audit enregistrait une adresse choisie par l'attaquant, ce qui est
   pire qu'une colonne vide.

2. AUCUNE REDIRECTION N'ÉTAIT VÉRIFIÉE.
   `url_has_allowed_host_and_scheme` n'était appelé nulle part. La pire
   est celle qui suit la validation du code à deux facteurs : elle
   s'exécute à l'instant où l'utilisateur a le moins de raisons de se
   méfier, puisque tout ce qu'on lui a demandé a fonctionné.

3. L'ÉCRAN DE CONNEXION ACCEPTAIT UN NOMBRE ILLIMITÉ D'ESSAIS.
   `UserProfile.failed_login_attempts` et `locked_until` existaient
   depuis la première migration et n'étaient lus nulle part : la
   protection était prévue, sa place creusée, et jamais branchée.

4. LES JETONS D'AUTHENTIFICATION PARTAIENT SANS `Secure`, et l'API
   client contournait les validateurs de mot de passe du projet avec sa
   propre règle de six caractères — qui accepte « 123456 ».
"""
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from apps.core.client_ip import adresse_valide, ip_du_client
from apps.core.redirections import destination_sure


# ═══ 1. L'ADRESSE DU CLIENT ════════════════════════════════════════════════

def _requete(**entetes):
    fabrique = RequestFactory()
    requete = fabrique.get('/')
    requete.META.update(entetes)
    return requete


def test_l_adresse_forgee_par_le_client_n_est_plus_retenue():
    """LE DÉFAUT CENTRAL DE CET AUDIT.

    nginx compose l'en-tête avec `$proxy_add_x_forwarded_for`, et
    Cloudflare l'étend de la même façon : tous deux AJOUTENT la vraie
    adresse à DROITE de ce que le client a envoyé. Prendre le premier
    élément — ce que faisaient les six extracteurs — rend donc la valeur
    que l'attaquant a écrite.
    """
    requete = _requete(
        HTTP_X_FORWARDED_FOR='9.9.9.9, 203.0.113.7',
        REMOTE_ADDR='127.0.0.1')

    assert ip_du_client(requete) == '203.0.113.7'


def test_une_longue_chaine_forgee_ne_change_rien():
    """Allonger la liste ne déplace pas la vraie adresse : elle reste la
    dernière, puisque c'est le composant de confiance qui l'ajoute."""
    requete = _requete(
        HTTP_X_FORWARDED_FOR='1.1.1.1, 2.2.2.2, 3.3.3.3, 203.0.113.7',
        REMOTE_ADDR='127.0.0.1')

    assert ip_du_client(requete) == '203.0.113.7'


def test_sans_en_tete_on_prend_le_pair():
    requete = _requete(REMOTE_ADDR='203.0.113.9')
    assert ip_du_client(requete) == '203.0.113.9'


def test_l_en_tete_de_nginx_sert_de_secours():
    """`X-Real-IP` est posé par nginx avec `proxy_set_header`, qui
    REMPLACE la valeur du client — c'est l'accès LAN, où nginx est dans
    le chemin."""
    requete = _requete(HTTP_X_REAL_IP='192.168.1.42',
                       REMOTE_ADDR='127.0.0.1')
    assert ip_du_client(requete) == '192.168.1.42'


def test_cf_connecting_ip_n_est_plus_cru():
    """IL ÉTAIT LU EN PREMIER, et c'était le pire des trois.

    Cloudflare le pose bien, en écrasant toute valeur du client — mais
    rien, du côté de Django, ne distingue celui de Cloudflare de celui
    qu'un client a émis. Comme `X-Forwarded-For` porte la même
    information à un endroit vérifiable, on ne garde que celui-là.
    """
    requete = _requete(HTTP_CF_CONNECTING_IP='9.9.9.9',
                       HTTP_X_FORWARDED_FOR='8.8.8.8, 203.0.113.7',
                       REMOTE_ADDR='127.0.0.1')

    assert ip_du_client(requete) == '203.0.113.7'


@pytest.mark.parametrize('valeur', [
    '',
    '   ',
    'pas-une-adresse',
    '../../etc/passwd',
    'a' * 500,
    '127.0.0.1 ; DROP TABLE',
    '999.999.999.999',
])
def test_une_valeur_qui_n_est_pas_une_adresse_est_jetee(valeur):
    """ELLE PART DANS UNE CLEF DE CACHE ET DANS UNE COLONNE DE LA BASE.

    Un en-tête de cinq cents caractères, un chemin, un point-virgule :
    rien de cela n'est une adresse, et le propager serait laisser le
    client écrire dans nos clefs de cache.
    """
    assert adresse_valide(valeur) is None


def test_une_adresse_ipv6_est_acceptee_avec_ou_sans_crochets():
    assert adresse_valide('2001:db8::1') == '2001:db8::1'
    assert adresse_valide('[2001:db8::1]') == '2001:db8::1'


def test_aucune_source_ne_donne_jamais_la_chaine_vide():
    """Une chaîne vide se glisserait dans une clef de cache et
    confondrait en un seul tous les clients sans adresse.

    `RequestFactory` pose `REMOTE_ADDR='127.0.0.1'` de lui-même : on le
    retire pour mesurer le cas sans aucune source, qui est celui d'une
    requête fabriquee a la main ou d'un serveur mal configure.
    """
    assert ip_du_client(_requete(REMOTE_ADDR='')) == '0.0.0.0'
    assert ip_du_client(_requete(REMOTE_ADDR=None)) == '0.0.0.0'
    assert ip_du_client(_requete(REMOTE_ADDR='pas-une-adresse')) == '0.0.0.0'


def test_les_six_extracteurs_delguent_au_meme_endroit():
    """LA GARDE CONTRE LA RÉAPPARITION.

    Le défaut n'était pas dans un fichier mais dans six, écrits sur le
    même réflexe. Ce test échoue si l'un d'eux reprend `split(',')[0]`.
    """
    import os
    import re

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fichiers = [
        'apps/core/utils.py', 'apps/core/middleware.py',
        'apps/core/audit_service.py', 'apps/accounts/signals.py',
        'apps/accounts/views.py', 'apps/websites/public_views.py',
    ]
    motif = re.compile(
        r"HTTP_X_FORWARDED_FOR'\)[\s\S]{0,200}?split\(','\)\[0\]")

    fautifs = []
    for relatif in fichiers:
        with open(os.path.join(racine, relatif), encoding='utf-8') as flux:
            if motif.search(flux.read()):
                fautifs.append(relatif)

    assert not fautifs, (
        'ces fichiers reprennent le premier élément de X-Forwarded-For, '
        'qui est écrit par le client : %s' % fautifs)


# ═══ 2. LES REDIRECTIONS ═══════════════════════════════════════════════════

@pytest.mark.parametrize('cible', [
    'https://exemple-pirate.test/',
    'http://exemple-pirate.test/connexion',
    '//exemple-pirate.test/',
    'https://exemple-pirate.test@login.elysiums.fr/',
    '/\\exemple-pirate.test',
    'javascript:alert(1)',
])
def test_une_destination_hors_du_site_est_remplacee(cible):
    """`redirect()` SERT TELLE QUELLE UNE ADRESSE ABSOLUE.

    `//exemple-pirate/` mérite une mention : il commence par une barre
    oblique, et deux vues le laissaient passer avec un
    `next_url.startswith('/')`. Le navigateur y lit un HÔTE, pas un
    chemin — le contrôle laissait donc passer exactement ce qu'il
    cherchait à bloquer.
    """
    requete = RequestFactory().get('/')
    assert destination_sure(requete, cible, 'core:dashboard') \
        == 'core:dashboard'


@pytest.mark.parametrize('cible', [
    '/dashboard/',
    '/erp/ventes/factures/12/',
    '/dashboard/?onglet=2',
])
def test_une_destination_interne_passe(cible):
    """Une correction qui casse ce qu'elle protège n'en est pas une : le
    retour légitime après connexion doit continuer de fonctionner."""
    requete = RequestFactory().get('/')
    assert destination_sure(requete, cible, 'core:dashboard') == cible


def test_un_retour_a_la_ligne_dans_la_destination_est_refuse():
    """Les navigateurs retirent les retours à la ligne AVANT d'analyser
    l'adresse : `/\\nhttps://pirate` devient donc absolu."""
    requete = RequestFactory().get('/')
    for cible in ('/\nhttps://exemple-pirate.test',
                  '/\rhttps://exemple-pirate.test',
                  '/\thttps://exemple-pirate.test'):
        assert destination_sure(requete, cible, '/') == '/'


def test_une_destination_vide_rend_le_repli():
    requete = RequestFactory().get('/')
    for vide in (None, '', '   '):
        assert destination_sure(requete, vide, 'core:dashboard') \
            == 'core:dashboard'


def test_plus_aucune_vue_ne_redirige_sans_verifier():
    """LA GARDE QUI SURVIVRA À CET AUDIT.

    Quinze vues renvoyaient l'utilisateur vers une adresse prise dans la
    requête. Ce test échoue si un `redirect()` reprend directement un
    `next` ou un `Referer`.
    """
    import os
    import re

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    apps = os.path.join(racine, 'apps')

    motif = re.compile(
        r'redirect\(\s*request\.(GET|POST)\.get|'
        r"redirect\(\s*request\.META\.get\('HTTP_REFERER'")

    fautifs = []
    for courant, _sous, fichiers in os.walk(apps):
        for nom in sorted(fichiers):
            if not nom.endswith('.py') or nom == 'redirections.py':
                continue
            chemin = os.path.join(courant, nom)
            with open(chemin, encoding='utf-8', errors='replace') as flux:
                if motif.search(flux.read()):
                    fautifs.append(os.path.relpath(chemin, racine))

    assert not fautifs, (
        'ces vues redirigent vers une adresse non vérifiée : %s. '
        'Employez apps.core.redirections.destination_sure.' % fautifs)


# ═══ 3. LA LIMITATION DES TENTATIVES DE CONNEXION ══════════════════════════

@pytest.fixture
def cache_vide():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def entreprise(db):
    """Sans entreprise, `FirstRunMiddleware` renvoie TOUT vers `/setup/`.

    Les requetes des tests n'atteignaient donc pas les vues, et les dix
    echecs disaient seulement cela : un 302 au lieu du refus attendu.
    """
    from apps.core.models import Company

    return Company.objects.create(name='Orion Audit', slug='orion-audit-2')


@pytest.fixture
def salarie(db):
    from apps.accounts.models import UserProfile

    utilisateur = User.objects.create_user(
        username='pedro', password='un-mot-de-passe-solide-42')
    UserProfile.objects.get_or_create(user=utilisateur)
    return utilisateur


@pytest.mark.django_db
def test_cinq_echecs_verrouillent_le_compte(client, salarie, entreprise,
                                            cache_vide):
    """L'ÉCRAN ACCEPTAIT UN NOMBRE ILLIMITÉ D'ESSAIS.

    Pour un ERP joignable par un domaine public, c'est la porte la plus
    simple : pas de faille à trouver, seulement du temps et une liste de
    mots de passe.
    """
    from apps.accounts.models import UserProfile

    adresse = reverse('accounts:login')
    for _ in range(5):
        client.post(adresse, {'username': 'pedro', 'password': 'faux'})

    profil = UserProfile.objects.get(user=salarie)
    assert profil.failed_login_attempts >= 5
    assert profil.locked_until is not None
    assert profil.locked_until > timezone.now()


@pytest.mark.django_db
def test_le_bon_mot_de_passe_est_refuse_pendant_le_verrou(client, salarie,
                                                          entreprise,
                                                          cache_vide):
    """LA MESURE QUI COMPTE. Un compteur qui s'incrémente sans rien
    bloquer n'est pas une protection, c'est une statistique."""
    from apps.accounts.models import UserProfile

    adresse = reverse('accounts:login')
    for _ in range(5):
        client.post(adresse, {'username': 'pedro', 'password': 'faux'})

    reponse = client.post(adresse, {'username': 'pedro',
                                    'password': 'un-mot-de-passe-solide-42'},
                          follow=True)

    assert not reponse.context['user'].is_authenticated
    assert any('tentatives' in str(m) for m in reponse.context['messages'])
    assert UserProfile.objects.get(user=salarie).locked_until is not None


@pytest.mark.django_db
def test_le_verrou_expire_de_lui_meme(client, salarie, entreprise,
                                      cache_vide):
    """LE VERROU EST TEMPORAIRE, ET C'EST UN CHOIX.

    Un verrou définitif transforme la protection en déni de service
    contre l'utilisateur légitime : il suffirait d'échouer cinq fois sur
    le compte du patron pour le mettre dehors jusqu'à ce qu'un
    administrateur intervienne.
    """
    from apps.accounts.models import UserProfile

    adresse = reverse('accounts:login')
    for _ in range(5):
        client.post(adresse, {'username': 'pedro', 'password': 'faux'})

    UserProfile.objects.filter(user=salarie).update(
        locked_until=timezone.now() - timedelta(seconds=1))

    reponse = client.post(adresse, {'username': 'pedro',
                                    'password': 'un-mot-de-passe-solide-42'},
                          follow=True)

    assert reponse.context['user'].is_authenticated


@pytest.mark.django_db
def test_une_connexion_reussie_remet_les_compteurs_a_zero(client, salarie,
                                                          entreprise,
                                                          cache_vide):
    from apps.accounts.models import UserProfile

    adresse = reverse('accounts:login')
    for _ in range(3):
        client.post(adresse, {'username': 'pedro', 'password': 'faux'})
    assert UserProfile.objects.get(user=salarie).failed_login_attempts == 3

    client.post(adresse, {'username': 'pedro',
                          'password': 'un-mot-de-passe-solide-42'})

    profil = UserProfile.objects.get(user=salarie)
    assert profil.failed_login_attempts == 0
    assert profil.locked_until is None


@pytest.mark.django_db
def test_un_identifiant_inconnu_ne_cree_aucune_ligne(client, entreprise,
                                                     cache_vide):
    """La table ne doit pas grossir au rythme de l'attaque.

    Seul le compteur par adresse retient un identifiant inventé — et
    c'est lui qui arrête le balayage, qui ne cible aucun compte existant.
    """
    from apps.accounts.models import UserProfile

    avant = UserProfile.objects.count()
    for _ in range(6):
        client.post(reverse('accounts:login'),
                    {'username': 'inexistant-xyz', 'password': 'faux'})

    assert UserProfile.objects.count() == avant


@pytest.mark.django_db
def test_le_balayage_depuis_une_adresse_est_arrete(client, entreprise,
                                                   cache_vide):
    """LE DEUXIÈME COMPTEUR, ET POURQUOI IL EN FAUT DEUX.

    Essayer UN mot de passe courant sur cent identifiants ne déclenche
    jamais le compteur par compte, puisque aucun n'est retenté. Seul le
    compteur par adresse voit l'attaque.
    """
    from apps.accounts import anti_force_brute

    adresse = reverse('accounts:login')
    for rang in range(anti_force_brute.ECHECS_PAR_ADRESSE + 1):
        client.post(adresse, {'username': f'cible{rang}',
                              'password': 'Azerty123'})

    reponse = client.post(adresse, {'username': 'cible999',
                                    'password': 'Azerty123'}, follow=True)
    assert any('tentatives' in str(m) for m in reponse.context['messages'])


@pytest.mark.django_db
def test_le_refus_ne_dit_pas_si_le_compte_existe(client, salarie,
                                                 cache_vide):
    """Deux textes différents donneraient la liste des comptes à qui
    prendrait la peine de comparer."""
    from apps.accounts import anti_force_brute

    requete = RequestFactory().post('/')
    requete.META['REMOTE_ADDR'] = '203.0.113.7'

    for _ in range(anti_force_brute.ECHECS_PAR_COMPTE):
        anti_force_brute.enregistrer_un_echec(requete, 'pedro')

    _, message_connu = anti_force_brute.est_verrouille(requete, 'pedro')

    cache.clear()
    requete2 = RequestFactory().post('/')
    requete2.META['REMOTE_ADDR'] = '203.0.113.8'
    for _ in range(anti_force_brute.ECHECS_PAR_ADRESSE):
        anti_force_brute.enregistrer_un_echec(requete2, 'inexistant-xyz')
    _, message_inconnu = anti_force_brute.est_verrouille(requete2,
                                                         'inexistant-xyz')

    # Les deux refus emploient la même formule.
    assert 'tentatives de connexion' in message_connu
    assert 'tentatives de connexion' in message_inconnu


@pytest.mark.django_db
def test_le_verrou_se_leve_depuis_l_interface(salarie, cache_vide):
    """Un verrou qu'on ne peut lever qu'en base est un verrou qui finit
    par être levé en désactivant la protection."""
    from apps.accounts import anti_force_brute
    from apps.accounts.models import UserProfile

    profil = UserProfile.objects.get(user=salarie)
    UserProfile.objects.filter(pk=profil.pk).update(
        failed_login_attempts=9,
        locked_until=timezone.now() + timedelta(hours=1))

    anti_force_brute.deverrouiller(profil)

    profil.refresh_from_db()
    assert profil.failed_login_attempts == 0
    assert profil.locked_until is None


# ═══ 4. LES JETONS ET LES MOTS DE PASSE DE L'ESPACE CLIENT ═════════════════

def test_les_jetons_ne_partent_plus_sans_secure():
    """TRENTE JOURS D'AUTHENTIFICATION SUR UNE REQUÊTE EN CLAIR.

    `siecle_token` et `neo_client_token` portaient `httponly` et
    `samesite`, mais pas `secure` : le navigateur les joignait aussi à
    une requête en HTTP simple. `set_trusted_device_cookie`, dans
    `apps/user_security`, posait déjà `secure=not settings.DEBUG` — la
    convention existait, ces deux-là ne l'avaient pas.
    """
    import os
    import re

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    for relatif in ('apps/ecommerce/api/customer_api.py',
                    'apps/portals/client_api.py'):
        with open(os.path.join(racine, relatif), encoding='utf-8') as flux:
            source = flux.read()

        for appel in re.findall(r'set_cookie\([^)]*\)', source,
                                re.DOTALL):
            assert 'secure=' in appel, (
                '%s : un cookie part sans `secure` — %s'
                % (relatif, appel[:90]))


@pytest.mark.django_db
def test_l_api_client_applique_les_validateurs_du_projet(client, entreprise,
                                                         cache_vide):
    """`create_user()` NE LES APPELLE PAS.

    `AUTH_PASSWORD_VALIDATORS` en déclare quatre, et ils ne s'appliquent
    qu'à travers un formulaire ou un appel explicite. L'API posait sa
    propre règle — six caractères — qui accepte « 123456 », lequel figure
    en tête de toutes les listes de mots de passe.
    """
    import json

    reponse = client.post(
        '/api/v1/siecle/auth/register/',
        data=json.dumps({'email': 'client@exemple.test',
                         'password': '123456'}),
        content_type='application/json')

    assert reponse.status_code == 400
    assert not User.objects.filter(email='client@exemple.test').exists()


@pytest.mark.django_db
def test_un_mot_de_passe_solide_est_accepte(client, entreprise,
                                            cache_vide):
    """La contrepartie : la politique ne doit pas fermer l'inscription."""
    import json

    reponse = client.post(
        '/api/v1/siecle/auth/register/',
        data=json.dumps({'email': 'client2@exemple.test',
                         'password': 'tourbillon-de-sable-91'}),
        content_type='application/json')

    assert reponse.status_code == 201, reponse.content
    assert User.objects.filter(email='client2@exemple.test').exists()


@pytest.mark.django_db
def test_les_essais_de_connexion_de_l_api_sont_bornes(client, entreprise,
                                                      cache_vide):
    """Essais illimités sur un endpoint JSON : une liste de mots de passe
    s'essayait aussi vite que le réseau le permet."""
    import json

    from apps.ecommerce.api.customer_api import ESSAIS_PAR_HEURE

    corps = json.dumps({'email': 'client@exemple.test',
                        'password': 'faux'})
    derniere = None
    for _ in range(ESSAIS_PAR_HEURE + 2):
        derniere = client.post('/api/v1/siecle/auth/login/', data=corps,
                               content_type='application/json')

    assert derniere.status_code == 429, derniere.status_code


@pytest.mark.django_db
def test_les_inscriptions_sont_bornees(client, entreprise, cache_vide):
    """L'inscription répond « un compte existe déjà avec cet email » :
    nécessaire pour l'utilisateur, et suffisant pour énumérer les clients
    d'une boutique. C'est le débit qu'on borne, pas le message."""
    import json

    from apps.ecommerce.api.customer_api import INSCRIPTIONS_PAR_HEURE

    derniere = None
    for rang in range(INSCRIPTIONS_PAR_HEURE + 2):
        derniere = client.post(
            '/api/v1/siecle/auth/register/',
            data=json.dumps({'email': f'c{rang}@exemple.test',
                             'password': 'tourbillon-de-sable-91'}),
            content_type='application/json')

    assert derniere.status_code == 429, derniere.status_code


# ═══ 5. LEVER UN VERROU SANS TERMINAL ══════════════════════════════════════
#
# Si la seule façon de lever un verrou est une requête en base, alors la
# façon qui sera employée le jour où ça presse est la désactivation de la
# protection. Et c'est le genre de réglage qu'on ne remet jamais.


@pytest.fixture
def administrateur(db, entreprise):
    from apps.accounts.models import UserProfile

    utilisateur = User.objects.create_user(
        username='ana', password='un-mot-de-passe-solide-42',
        is_staff=True, is_superuser=True)
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.companies.add(entreprise)
    profil.current_company = entreprise
    profil.save()
    return utilisateur


@pytest.mark.django_db
def test_l_ecran_montre_le_verrou(client, administrateur, salarie,
                                  entreprise, cache_vide):
    """L'ÉTAT EST AFFICHÉ, ET PAS SEULEMENT LEVABLE.

    Un administrateur qui ne voit pas pourquoi un collègue n'entre plus
    cherchera ailleurs, et conclura à une panne.
    """
    from apps.accounts.models import UserProfile

    UserProfile.objects.filter(user=salarie).update(
        failed_login_attempts=5,
        locked_until=timezone.now() + timedelta(minutes=10))

    client.force_login(administrateur)
    html = client.get(
        reverse('accounts:user_detail', args=[salarie.pk])
    ).content.decode('utf-8')

    assert 'Connexion verrouill' in html
    assert reverse('accounts:user_unlock', args=[salarie.pk]) in html


@pytest.mark.django_db
def test_l_ecran_leve_le_verrou_en_POST(client, administrateur, salarie,
                                        entreprise, cache_vide):
    from apps.accounts.models import UserProfile

    UserProfile.objects.filter(user=salarie).update(
        failed_login_attempts=7,
        locked_until=timezone.now() + timedelta(hours=1))

    client.force_login(administrateur)
    client.post(reverse('accounts:user_unlock', args=[salarie.pk]))

    profil = UserProfile.objects.get(user=salarie)
    assert profil.locked_until is None
    assert profil.failed_login_attempts == 0


@pytest.mark.django_db
def test_un_GET_ne_leve_aucun_verrou(client, administrateur, salarie,
                                     entreprise, cache_vide):
    """Un GET qui leverait un verrou de sécurité partirait au survol d'un
    lien ou au passage d'un antivirus."""
    from apps.accounts.models import UserProfile

    UserProfile.objects.filter(user=salarie).update(
        failed_login_attempts=7,
        locked_until=timezone.now() + timedelta(hours=1))

    client.force_login(administrateur)
    reponse = client.get(reverse('accounts:user_unlock', args=[salarie.pk]))

    assert reponse.status_code == 405
    assert UserProfile.objects.get(user=salarie).locked_until is not None


@pytest.mark.django_db
def test_le_verrou_leve_est_journalise(client, administrateur, salarie,
                                       entreprise, cache_vide):
    """Lever un verrou de sécurité est une action qui doit laisser une
    trace : c'est la seule qui rouvre un compte que le système a fermé."""
    from apps.accounts.models import UserProfile
    from apps.core.models import AuditLog

    UserProfile.objects.filter(user=salarie).update(
        locked_until=timezone.now() + timedelta(hours=1))

    client.force_login(administrateur)
    client.post(reverse('accounts:user_unlock', args=[salarie.pk]))

    assert AuditLog.objects.filter(
        user=administrateur, description__contains='Verrou').exists()
