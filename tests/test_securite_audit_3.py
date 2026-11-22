"""Troisième audit de sécurité — ce que les deux premiers n'avaient pas regardé.

Les trois défauts mesurés ici ont le même squelette, et c'est pour cela
qu'ils se suivent : **un contrôle juste, écrit, testé, et contourné par le
chemin réel des octets.**

1. `apps/core/media_access.py` applique un refus par défaut sous `/media/`
   et tient les bulletins de paie hors de ce préfixe. Deux gabarits nginx
   sur trois portaient `location /media/ { alias ... }` : Nginx servait
   les fichiers depuis le disque et la requête n'atteignait jamais cette
   politique.

2. `settings/base.py` annonçait 20 Mo sous le titre « Upload fichiers ».
   Ni `FILE_UPLOAD_MAX_MEMORY_SIZE` (un seuil mémoire/disque) ni
   `DATA_UPLOAD_MAX_MEMORY_SIZE` (qui ne compte pas les parties fichier)
   ne plafonne un téléversement.

3. `apps/access_control/` configure des rôles et des permissions que
   **rien dans le projet n'applique** — zéro appelant pour les trois
   décorateurs et les trois mixins — et ses propres écrans, qui accordent
   ces permissions, n'étaient gardés que par `@login_required`.

D'où la forme de ces tests : ils lisent les gabarits de déploiement, ils
envoient de vrais fichiers par le client HTTP, et ils appellent les vues
avec de vrais comptes. Vérifier qu'une fonction existe aurait validé les
trois défauts.
"""

import io
import os
import re

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, RequestDataTooBig
from django.test import RequestFactory, override_settings
from django.urls import reverse

from apps.core.models import Company

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPLOIEMENT = os.path.join(RACINE, 'deployment')


# ═══════════════════════════════════════════════════════════════════════════
#  1. /media/ ne doit JAMAIS être servi depuis le disque par Nginx
# ═══════════════════════════════════════════════════════════════════════════

def _gabarits_nginx():
    """Tous les fichiers de déploiement qui déclarent un bloc Nginx.

    On cherche par CONTENU (« location ») et non par extension : les
    gabarits du dépôt s'appellent `.conf`, `.conf.tmpl` et `.tmpl.yml`, et
    une garde qui ne connaîtrait qu'une extension manquerait le prochain.
    """
    trouves = []
    for racine, _, fichiers in os.walk(DEPLOIEMENT):
        for nom in fichiers:
            chemin = os.path.join(racine, nom)
            try:
                with open(chemin, encoding='utf-8', errors='replace') as flux:
                    contenu = flux.read()
            except OSError:
                continue
            if 'location ' in contenu and 'server' in contenu:
                trouves.append((chemin, contenu))
    return trouves


def _blocs_media(contenu):
    """Le corps de chaque `location /media/ { ... }` du fichier."""
    blocs = []
    for trouve in re.finditer(r'location\s+/media/\s*\{', contenu):
        debut = trouve.end()
        profondeur = 1
        i = debut
        while i < len(contenu) and profondeur:
            if contenu[i] == '{':
                profondeur += 1
            elif contenu[i] == '}':
                profondeur -= 1
            i += 1
        blocs.append(contenu[debut:i - 1])
    return blocs


def test_il_y_a_bien_des_gabarits_nginx_a_verifier():
    """La garde doit échouer si elle ne trouve plus rien à garder.

    Sans ce test, renommer le dossier `deployment/` rendrait les deux
    suivants verts en n'examinant aucun fichier — une garde qui ne garde
    plus rien et qui l'annonce comme un succès.
    """
    gabarits = _gabarits_nginx()
    assert gabarits, 'aucun gabarit Nginx trouvé sous deployment/'
    avec_media = [c for c, contenu in gabarits if _blocs_media(contenu)]
    assert avec_media, 'aucun bloc « location /media/ » trouvé'


def test_aucun_gabarit_nginx_ne_sert_media_depuis_le_disque():
    """`alias` ou `root` sous /media/ contourne tout le contrôle d'accès.

    `apps/core/media_access.py` tient `employee_private/` (contrats,
    bulletins de paie, pièces d'identité), `bank_statements/`,
    `supplier_invoices/` et `expense_receipts/` hors de `/media/`. Servi
    par Nginx depuis le disque, aucun de ces refus ne s'applique : une URL
    devinée suffit, sans compte.
    """
    fautifs = []
    for chemin, contenu in _gabarits_nginx():
        for bloc in _blocs_media(contenu):
            for directive in ('alias', 'root'):
                if re.search(r'^\s*%s\s' % directive, bloc, re.MULTILINE):
                    fautifs.append('%s : « %s » sous location /media/'
                                   % (os.path.relpath(chemin, RACINE),
                                      directive))
    assert not fautifs, (
        'Ces blocs servent /media/ depuis le disque et contournent '
        'apps/core/media_access.py :\n  ' + '\n  '.join(fautifs))


def test_la_configuration_en_place_est_controlee_avant_chaque_maj():
    """Corriger les gabarits ne corrige pas une machine déjà installée.

    Une mise à jour ne réécrit pas `/etc/nginx`. Le fichier fautif reste
    donc en place, et personne ne pense à relire une configuration qu'on
    n'a pas touchée depuis l'installation. D'où un contrôle qui lit celle
    qui est réellement là — et qui parle dans l'écran de mise à jour, parce
    qu'une alerte qui n'apparaît que dans un terminal n'apparaît pas.
    """
    from apps.system_updates.health_checks import run_pre_update_config_checks

    resultat = run_pre_update_config_checks()
    intitules = [str(c.get('message', '')) for c in resultat['checks']]
    assert any('/media/' in m for m in intitules), (
        'le contrôle de /media/ n’est pas dans les contrôles préalables : '
        + ' | '.join(intitules))


def test_l_absence_de_nginx_n_est_pas_un_defaut():
    """Sur un poste de développement, il n'y a pas de /etc/nginx.

    Confondre « absent » et « fautif » ferait crier ce contrôle sur toutes
    les machines où il n'a rien à dire — et une alerte permanente ne se lit
    plus. C'est le même défaut que l'écran qui annonçait « le système est à
    jour » quand il ne savait pas.
    """
    from apps.domain_diagnostics.nginx_checks import \
        media_servi_depuis_le_disque

    assert media_servi_depuis_le_disque() == [] or all(
        'fichier' in item for item in media_servi_depuis_le_disque())

    from apps.system_updates.health_checks import check_media_derriere_django
    assert check_media_derriere_django()['ok'] is True


def test_le_controle_reconnait_un_alias_dans_une_vraie_configuration(tmp_path,
                                                                     monkeypatch):
    """Mesuré sur un fichier écrit pour l'occasion, et non sur une chaîne.

    Le découpage compte les accolades : un `root` posé au niveau du
    `server` ne doit pas compter, et un `alias` commenté non plus. Une
    version de ce contrôle qui aurait cherché « alias » dans tout le
    fichier aurait crié sur les blocs /static/ — légitimes, eux.
    """
    from apps.domain_diagnostics import nginx_checks

    dossier = tmp_path / 'sites-enabled'
    dossier.mkdir()
    (dossier / 'orion.conf').write_text(
        'server {\n'
        '    root /var/www/html;\n'               # hors bloc : ne compte pas
        '    location /static/ {\n'
        '        alias /opt/orion/staticfiles/;\n'  # legitime : pas /media/
        '    }\n'
        '    location /media/ {\n'
        '        # alias /ancien/chemin/;\n'        # commente : ne compte pas
        '        alias /opt/orion/backend/media/;\n'
        '    }\n'
        '}\n', encoding='utf-8')

    monkeypatch.setattr(nginx_checks, 'NGINX_DIRS', [str(dossier)])
    fautifs = nginx_checks.media_servi_depuis_le_disque()

    assert len(fautifs) == 1, fautifs
    assert fautifs[0]['directive'] == 'alias'


def test_un_bloc_media_qui_relaie_ne_declenche_rien(tmp_path, monkeypatch):
    """Et le contrôle corrigé doit se taire : sinon on le désactivera."""
    from apps.domain_diagnostics import nginx_checks

    dossier = tmp_path / 'sites-enabled'
    dossier.mkdir()
    (dossier / 'orion.conf').write_text(
        'server {\n'
        '    location /media/ {\n'
        '        proxy_pass http://127.0.0.1:9000;\n'
        '    }\n'
        '}\n', encoding='utf-8')

    monkeypatch.setattr(nginx_checks, 'NGINX_DIRS', [str(dossier)])
    assert nginx_checks.media_servi_depuis_le_disque() == []


def test_chaque_bloc_media_relaie_vers_django():
    """Et il doit relayer : ne rien déclarer du tout rend 404 sur les médias.

    L'inverse du défaut est une panne déjà vécue sur l'appliance — aucune
    route pour `/media/`, donc aucune photo de produit ni aucun logo. Le
    bloc doit exister ET relayer.
    """
    for chemin, contenu in _gabarits_nginx():
        for bloc in _blocs_media(contenu):
            assert 'proxy_pass' in bloc, (
                '%s : un bloc location /media/ ne relaie vers rien'
                % os.path.relpath(chemin, RACINE))


# ═══════════════════════════════════════════════════════════════════════════
#  2. Le plafond de téléversement
# ═══════════════════════════════════════════════════════════════════════════

def test_django_ne_plafonne_pas_les_fichiers_de_lui_meme():
    """La preuve du défaut, lue dans la source de Django.

    La comptabilité d'octets de `DATA_UPLOAD_MAX_MEMORY_SIZE` est à
    l'intérieur de `if item_type == FIELD:` ; la branche `FILE` ne compte
    qu'un nombre de fichiers. Si une version future de Django déplaçait
    cette comptabilité, ce test échouerait — et ce serait la bonne
    nouvelle qui justifie de relire `apps/core/upload_guard.py`.
    """
    from django.http import multipartparser
    source = open(multipartparser.__file__, encoding='utf-8').read()

    debut_fichier = source.index('elif item_type == FILE:')
    comptages = [t.start() for t in
                 re.finditer(r'DATA_UPLOAD_MAX_MEMORY_SIZE', source)]
    assert comptages, 'réglage introuvable dans le parseur'
    apres = [p for p in comptages if p > debut_fichier]
    assert not apres, (
        'Django compte désormais les octets des parties fichier : relire '
        'apps/core/upload_guard.py, il fait peut-être double emploi.')


def _handler(chemin='/une/vue/'):
    from apps.core.upload_guard import PlafondDeTaille
    requete = RequestFactory().post(chemin)
    return PlafondDeTaille(requete)


@override_settings(ORION_TAILLE_MAX_TELEVERSEMENT=1000)
def test_un_corps_annonce_trop_gros_est_refuse_sans_etre_lu():
    """La vraie protection : refuser avant d'écrire un seul octet."""
    handler = _handler()
    with pytest.raises(RequestDataTooBig):
        handler.handle_raw_input(None, {}, 50_000, b'frontiere')


@override_settings(ORION_TAILLE_MAX_TELEVERSEMENT=1000)
def test_un_corps_annonce_sous_le_plafond_passe():
    handler = _handler()
    assert handler.handle_raw_input(None, {}, 900, b'frontiere') is None


@override_settings(ORION_TAILLE_MAX_TELEVERSEMENT=1000)
def test_un_en_tete_menteur_est_rattrape_pendant_la_lecture():
    """Content-Length vient du client : il ne suffit pas de le croire."""
    handler = _handler()
    handler.handle_raw_input(None, {}, 10, b'frontiere')   # annonce 10 octets
    handler.new_file('f', 'gros.bin', 'application/octet-stream', None)
    with pytest.raises(RequestDataTooBig):
        for _ in range(20):
            handler.receive_data_chunk(b'x' * 100, 0)      # en envoie 2000


@override_settings(ORION_TAILLE_MAX_TELEVERSEMENT=1000)
def test_les_blocs_sont_rendus_tels_quels_sous_le_plafond():
    """Rendre None priverait les gestionnaires suivants des données.

    Le fichier arriverait alors VIDE au lieu d'être refusé — une panne
    silencieuse là où on voulait un refus bruyant.
    """
    handler = _handler()
    handler.handle_raw_input(None, {}, 500, b'frontiere')
    handler.new_file('f', 'petit.bin', 'application/octet-stream', None)
    assert handler.receive_data_chunk(b'abc', 0) == b'abc'


@override_settings(ORION_TAILLE_MAX_TELEVERSEMENT=1000)
def test_le_compteur_repart_a_zero_pour_chaque_fichier():
    """Deux pièces jointes acceptables ne font pas un refus.

    C'est `Content-Length` qui borne le total ; ce compteur-ci borne un
    fichier. Les confondre refuserait un formulaire de trois photos
    parfaitement légitimes.
    """
    handler = _handler()
    handler.handle_raw_input(None, {}, 1000, b'frontiere')
    for nom in ('a.bin', 'b.bin', 'c.bin'):
        handler.new_file('f', nom, 'application/octet-stream', None)
        for _ in range(9):
            handler.receive_data_chunk(b'x' * 100, 0)      # 900 octets


@override_settings(ORION_TAILLE_MAX_TELEVERSEMENT=1000)
def test_l_import_de_sauvegarde_n_est_pas_plafonne():
    """Une restauration porte une base entière : la plafonner la casserait.

    Et un plafond qui casse une restauration finit désactivé — c'est ainsi
    qu'une protection disparaît pour de bon. Ces chemins sont réservés au
    superadmin.
    """
    from apps.core.upload_guard import plafond_pour
    for chemin in ('/sauvegardes/importer/', '/backups/x/', '/admin/core/',
                   '/orion-admin/application-pc/versions/'):
        requete = RequestFactory().post(chemin)
        assert plafond_pour(requete) == 0, chemin


@override_settings(ORION_TAILLE_MAX_TELEVERSEMENT=1000)
def test_une_vue_ordinaire_est_plafonnee():
    from apps.core.upload_guard import plafond_pour
    requete = RequestFactory().post('/hr/employes/12/documents/')
    assert plafond_pour(requete) == 1000


@override_settings(ORION_TAILLE_MAX_TELEVERSEMENT='pas un nombre')
def test_un_reglage_illisible_ne_desactive_pas_la_protection():
    """Le sens du défaut décide de ce qui arrive quand on se trompe."""
    from apps.core.upload_guard import PLAFOND_PAR_DEFAUT, plafond_configure
    assert plafond_configure() == PLAFOND_PAR_DEFAUT


def test_le_plafond_est_le_premier_gestionnaire():
    """Posé après TemporaryFileUploadHandler, il refuserait trop tard.

    Les gestionnaires reçoivent les blocs dans l'ordre : celui qui écrit
    sur le disque aurait déjà écrit.
    """
    from django.conf import settings
    assert settings.FILE_UPLOAD_HANDLERS[0] == \
        'apps.core.upload_guard.PlafondDeTaille'


def test_les_deux_reglages_trompeurs_portent_leur_avertissement():
    """Ils restent utiles, mais ne doivent plus se lire comme un plafond.

    Le défaut n'était pas leur valeur : c'était leur titre. Quelqu'un
    lisant « Upload fichiers / 20 Mo » ne cherche pas s'il existe une
    limite — il croit l'avoir trouvée.
    """
    chemin = os.path.join(RACINE, 'erp_btp', 'settings', 'base.py')
    contenu = open(chemin, encoding='utf-8').read()
    # Découpé depuis le TITRE de la section plutôt que sur un nombre de
    # caractères en arrière : une version de ce test comptait 1500 octets
    # avant la première ligne et attrapait le bloc des courriels.
    debut = contenu.index('─── Upload fichiers')
    fin = contenu.index('FILE_UPLOAD_HANDLERS')
    bloc = contenu[debut:fin]
    assert 'NE PLAFONNENT AUCUN TELEVERSEMENT' in bloc
    assert 'upload_guard' in bloc
    assert 'ORION_TAILLE_MAX_TELEVERSEMENT' in bloc


# ═══════════════════════════════════════════════════════════════════════════
#  3. Le contrôle d'accès ne doit pas être reconfigurable par n'importe qui
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def entreprise(db):
    """`SetupRequiredMiddleware` redirige tout vers /setup/ sans entreprise.

    Dix tests du deuxième audit rendaient 302 pour cette seule raison, et
    un 302 vers /setup/ se lit comme un refus d'accès alors que c'en est
    l'inverse : la page n'a même pas été atteinte.
    """
    from apps.core import middleware
    middleware._setup_complete_cache = None
    societe = Company.objects.create(name='Audit 3', slug='audit-3')
    yield societe
    middleware._setup_complete_cache = None


@pytest.fixture
def salarie(db):
    return User.objects.create_user(
        username='salarie-audit3', email='s@audit3.test',
        password='tourbillon-de-sable-91')


@pytest.fixture
def exploitant(db):
    return User.objects.create_superuser(
        username='exploitant-audit3', email='e@audit3.test',
        password='tourbillon-de-sable-91')


ECRANS_SENSIBLES = (
    'access_control:role_list',
    'access_control:role_create',
    'access_control:user_access_list',
    'access_control:user_access_create',
    'access_control:override_list',
    'access_control:override_create',
    'access_control:access_log',
    'access_control:dashboard',
    'access_control:module_list',
)


@pytest.mark.django_db
@pytest.mark.parametrize('nom', ECRANS_SENSIBLES)
def test_un_salarie_ordinaire_ne_peut_pas_ouvrir_les_ecrans_de_droits(
        client, entreprise, salarie, nom):
    """Mesuré par un vrai GET, et non en lisant les décorateurs.

    Ces écrans créent les rôles, accordent les permissions et attribuent
    les accès. Ils n'étaient gardés que par `@login_required` : tout
    compte connecté pouvait créer un rôle, lui donner « accès complet »
    d'un clic, et se l'attribuer.
    """
    client.force_login(salarie)
    reponse = client.get(reverse(nom))
    assert reponse.status_code in (403, 302), (
        '%s est ouvert à un salarié ordinaire (statut %s)'
        % (nom, reponse.status_code))
    if reponse.status_code == 302:
        assert '/setup/' not in reponse['Location'], (
            'redirection vers /setup/ : la vue n’a pas été atteinte, ce '
            'test ne mesure donc rien')


@pytest.mark.django_db
def test_un_salarie_ne_peut_pas_creer_un_role_par_un_post(
        client, entreprise, salarie):
    """Le POST compte plus que le GET : c'est lui qui écrit.

    Une garde posée sur le seul affichage laisserait l'écriture ouverte —
    c'est exactement ce qui s'était produit sur les réglages de boutique,
    où la LECTURE des secrets était protégée et l'ÉCRITURE non.
    """
    from apps.access_control.models import Role
    client.force_login(salarie)
    avant = Role.objects.count()
    client.post(reverse('access_control:role_create'),
                {'name': 'Tout pouvoir', 'code': 'tout_pouvoir'})
    assert Role.objects.count() == avant, 'un rôle a été créé'


@pytest.mark.django_db
def test_l_exploitant_garde_l_acces(client, entreprise, exploitant):
    """Une garde qui enferme dehors celui qui doit administrer est inutile.

    Elle serait retirée au premier appel, et c'est ainsi qu'une protection
    disparaît. Le superadmin passe, comme dans
    `shop_settings_access_required`.
    """
    client.force_login(exploitant)
    reponse = client.get(reverse('access_control:role_list'))
    assert reponse.status_code == 200, reponse.status_code


@pytest.mark.django_db
def test_un_administrateur_de_l_entreprise_garde_l_acces(
        rf, entreprise, salarie):
    """La règle reconnaît le rôle « admin » par son CODE.

    Filtrer `role__in=('admin', 'owner')` faisait lever à Django « Field
    'id' expected a number but got 'admin' » — une erreur 500 pour tout
    non-superadmin. Le défaut a déjà été commis une fois dans ce dépôt.
    """
    from apps.access_control.decorators import \
        est_administrateur_de_l_entreprise
    from apps.access_control.models import Role, UserCompanyAccess

    role = Role.objects.create(company=entreprise, name='Admin', code='admin')
    UserCompanyAccess.objects.create(
        user=salarie, company=entreprise, role=role, is_active=True)

    requete = rf.get('/')
    requete.user = salarie
    requete.current_company = entreprise
    assert est_administrateur_de_l_entreprise(requete) is True


@pytest.mark.django_db
def test_un_acces_desactive_ne_vaut_pas_administration(rf, entreprise, salarie):
    """`is_active=False` est la trace d'un accès RETIRÉ.

    L'ignorer rendrait le retrait sans effet — et personne ne le verrait,
    puisque l'écran afficherait bien l'accès comme inactif.
    """
    from apps.access_control.decorators import \
        est_administrateur_de_l_entreprise
    from apps.access_control.models import Role, UserCompanyAccess

    role = Role.objects.create(company=entreprise, name='Admin', code='admin')
    UserCompanyAccess.objects.create(
        user=salarie, company=entreprise, role=role, is_active=False)

    requete = rf.get('/')
    requete.user = salarie
    requete.current_company = entreprise
    assert est_administrateur_de_l_entreprise(requete) is False


@pytest.mark.django_db
def test_administrer_une_entreprise_n_en_administre_pas_une_autre(
        rf, entreprise, salarie):
    """Le rôle est rattaché à UNE entreprise, et la garde doit le lire.

    Sans cela, l'administrateur de l'entreprise A reconfigurerait les
    droits de l'entreprise B en changeant d'entreprise courante.
    """
    from apps.access_control.decorators import \
        est_administrateur_de_l_entreprise
    from apps.access_control.models import Role, UserCompanyAccess

    autre = Company.objects.create(name='Autre', slug='autre-audit-3')
    role = Role.objects.create(company=entreprise, name='Admin', code='admin')
    UserCompanyAccess.objects.create(
        user=salarie, company=entreprise, role=role, is_active=True)

    requete = rf.get('/')
    requete.user = salarie
    requete.current_company = autre
    assert est_administrateur_de_l_entreprise(requete) is False


@pytest.mark.django_db
def test_on_ne_duplique_pas_le_role_d_une_autre_entreprise(
        rf, entreprise, exploitant):
    """La duplication copiait la MATRICE DE PERMISSIONS COMPLÈTE.

    Un compte de l'entreprise A lisait donc, en changeant le numéro dans
    l'URL, la manière dont l'entreprise B organise ses accès. On mesure
    avec le superadmin, à qui la garde d'administration ne s'applique
    pas : c'est bien le BORNAGE qu'on vérifie ici, et non le décorateur.
    """
    from django.http import Http404

    from apps.access_control.models import Role
    from apps.access_control.views import role_duplicate

    autre = Company.objects.create(name='Voisine', slug='voisine-audit-3')
    role_voisin = Role.objects.create(
        company=autre, name='Direction', code='direction')

    requete = rf.post('/')
    requete.user = exploitant
    requete.current_company = entreprise
    requete._messages = _messages_muets()

    avant = Role.objects.count()
    with pytest.raises(Http404):
        role_duplicate(requete, pk=role_voisin.pk)
    assert Role.objects.count() == avant


@pytest.mark.django_db
def test_un_role_systeme_reste_duplicable(rf, entreprise, exploitant):
    """Le piège de la correction : `company__in=[company, None]`.

    Cette forme produit `company_id IN (5, NULL)`, et SQL ne fait jamais
    correspondre NULL par `IN`. Les rôles système — ceux que le bornage
    entend justement autoriser, puisqu'ils servent de modèles à toutes les
    entreprises — auraient tous rendu 404. Écrit avec un `Q`.
    """
    from apps.access_control.models import Role
    from apps.access_control.views import role_duplicate

    modele = Role.objects.create(
        company=None, name='Modèle commun', code='modele_commun',
        is_system_role=True)

    requete = rf.post('/')
    requete.user = exploitant
    requete.current_company = entreprise
    requete._messages = _messages_muets()

    avant = Role.objects.filter(company=entreprise).count()
    role_duplicate(requete, pk=modele.pk)
    assert Role.objects.filter(company=entreprise).count() == avant + 1


def _messages_muets():
    """Un stock de messages pour appeler une vue hors du cycle middleware."""
    from django.contrib.messages.storage.base import BaseStorage

    class Muet(BaseStorage):
        def _get(self, *args, **kwargs):
            return [], True

        def _store(self, messages, response, *args, **kwargs):
            return []

    return Muet(RequestFactory().post('/'))


# ═══════════════════════════════════════════════════════════════════════════
#  Gardes de régression
# ═══════════════════════════════════════════════════════════════════════════

def test_aucune_vue_du_controle_d_acces_ne_reste_sans_garde():
    """Mesuré sur la SOURCE : un ajout futur doit échouer ici.

    Les trois audits butent sur la même chose — un contrôle existe et
    quelque chose ne le traverse pas. Une quatorzième vue ajoutée demain
    sans garde recréerait le défaut exactement.
    """
    import ast

    chemin = os.path.join(RACINE, 'apps', 'access_control', 'views.py')
    arbre = ast.parse(open(chemin, encoding='utf-8').read())

    sans_garde = []
    for noeud in arbre.body:
        if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if noeud.name.startswith('_'):
            continue
        noms = {getattr(d, 'id', None) or getattr(d, 'attr', None)
                for d in noeud.decorator_list}
        if 'administration_requise' not in noms:
            sans_garde.append(noeud.name)

    assert not sans_garde, (
        'Ces vues du contrôle d’accès n’exigent pas d’être administrateur : '
        + ', '.join(sans_garde))


def test_le_fichier_des_decorateurs_dit_que_le_rbac_n_est_pas_branche():
    """Le constat doit rester lisible là où on ira chercher ces outils.

    `module_required`, `view_required`, `action_required` et les trois
    mixins n'ont aucun appelant : les rôles configurés dans l'ERP ne
    gouvernent l'accès à aucune page. Quelqu'un qui ouvre ce fichier pour
    s'en servir doit l'apprendre là, et non le supposer branché.
    """
    chemin = os.path.join(RACINE, 'apps', 'access_control', 'decorators.py')
    contenu = open(chemin, encoding='utf-8').read()
    assert 'zéro appelant' in contenu


def test_le_rbac_est_toujours_sans_appelant_ou_la_note_doit_changer():
    """Si quelqu'un branche enfin le RBAC, cette note devient fausse.

    Un commentaire qui décrit un état révolu est pire qu'aucun commentaire :
    il fait tenir pour vrai ce qui ne l'est plus. Ce test échoue au premier
    usage réel — et c'est alors la note qu'il faut corriger, pas lui.
    """
    import ast

    appels = 0
    for racine, _, fichiers in os.walk(os.path.join(RACINE, 'apps')):
        if 'migrations' in racine:
            continue
        for nom in fichiers:
            if not nom.endswith('.py'):
                continue
            chemin = os.path.join(racine, nom)
            if os.path.basename(chemin) in ('decorators.py', 'mixins.py') \
                    and 'access_control' in racine:
                continue
            try:
                arbre = ast.parse(open(chemin, encoding='utf-8').read())
            except (SyntaxError, UnicodeDecodeError):
                continue
            for noeud in ast.walk(arbre):
                if isinstance(noeud, ast.Name) and noeud.id in (
                        'module_required', 'view_required', 'action_required',
                        'ModuleAccessRequiredMixin', 'ViewAccessRequiredMixin',
                        'ActionAccessRequiredMixin'):
                    appels += 1

    assert appels == 0, (
        'Le RBAC a %d appelant(s) : la note de decorators.py et '
        'docs/AUDIT-SECURITE-3.md doivent être mises à jour.' % appels)
