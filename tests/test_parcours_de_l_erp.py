"""Parcours de l'ERP : chaque page s'affiche, chaque bouton mène quelque part.

Deux balayages, qui trouvent deux familles de défauts différentes.

**1. Les pages.** On visite les ~1050 adresses sans argument du projet avec
un compte super-admin et tous les modules actifs. C'est le seul moyen de
voir qu'un gabarit manque ou qu'une requête est fausse : rien de tout cela
ne se remarque avant que la vue n'ait été rendue une fois.

Ce balayage a trouvé sept pannes en service, toutes dans `apps/ecommerce`
et invisibles jusque-là :
  - quatre `TemplateDoesNotExist` — les vues et leurs routes existaient,
    les gabarits non ;
  - trois `FieldError` sur `WebOrder.created_at`, un champ qui n'existe
    pas : il s'appelle `order_date`.

**2. Les boutons.** Un `{% url 'nom' %}` vers un nom inexistant lève
`NoReverseMatch` **au rendu**, donc un seul bouton faux fait répondre 500 à
toute sa page. On vérifie donc que chaque nom cité par un gabarit existe.

Ce balayage a trouvé quarante noms morts. Dix-sept citaient le nom du
GABARIT de confirmation (« customer_confirm_delete ») au lieu du nom de
l'URL (« customer_delete ») — corrigés. Les autres vivent dans des
gabarits que rien ne rend, et sont documentés ci-dessous plutôt que
recâblés : réparer du code mort donne l'illusion qu'il est maintenu.
"""

import collections
import datetime
import decimal
import os
import re

import pytest
from django.apps import apps as registre
from django.db import models, transaction
from django.urls import NoReverseMatch, get_resolver, reverse
from django.utils import timezone
from django.urls.resolvers import URLPattern, URLResolver

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MOTIF_URL = re.compile(r"""\{%\s*url\s+['"]([a-zA-Z0-9_:.\-]+)['"]""")

# Adresses ecartees du parcours, et pourquoi :
#  - deconnexion : me sortirait de session, et toutes les pages suivantes
#    ne diraient plus rien ;
#  - suppression : un GET sur une vue de suppression mal protegee
#    detruirait le jeu d'essai au milieu du parcours ;
#  - extinction : ces vues appellent sudo.
MOTIFS_ECARTES = (
    'logout', 'deconnexion', 'supprimer', 'delete', 'purge',
    'redemarrer', 'reboot', 'shutdown', 'eteindre',
)

# Les noms d'URL morts qu'on accepte, chacun avec sa raison. Toute NOUVELLE
# reference cassee fait echouer le test : c'est une liste de decisions, pas
# une liste d'exceptions commodes.
NOMS_MORTS_ACCEPTES = {
    # Tout le dossier templates/layouts/ est mort : MESURE, aucun gabarit
    # ne l'etend ni ne l'inclut, aucune vue ne le rend. Le vrai gabarit de
    # base est erp_base.html, etendu par 420 fichiers.
    'core:home',
    'core:profile',
    'orion_admin:dashboard',
    'private_saas:select_active_company',
    'private_saas:clear_active_company',
    # templates/websites/gift_card_*.html et loyalty_*.html ne sont rendus
    # par aucune vue. Attention : templates/commerce/loyalty_list.html,
    # lui, est bien vivant -- deux fichiers de meme nom.
    'websites:gift_card_list',
    'websites:gift_card_detail',
    'websites:gift_card_create',
    'websites:gift_card_cancel',
    'websites:loyalty_list',
    'websites:loyalty_detail',
    'websites:loyalty_add_points',
    # Les quinze noms de apps/ecommerce/views_siecle.py ont quitte cette
    # liste : le back-office SIECLE est desormais branche. Il lui manquait
    # deux modeles, un formset, vingt-cinq champs editoriaux sur
    # StoreProduct et deux sur StoreProductImage -- voir
    # tests/test_back_office_siecle.py. C'est le second test ci-dessous qui
    # a impose de les retirer d'ici, et c'est son role.
}


def _adresses_sans_argument():
    def parcourir(resolver, prefixe=''):
        for p in resolver.url_patterns:
            if isinstance(p, URLPattern):
                yield prefixe + str(p.pattern)
            elif isinstance(p, URLResolver):
                yield from parcourir(p, prefixe + str(p.pattern))

    vues = set()
    for motif in parcourir(get_resolver()):
        if '<' in motif or '(' in motif:
            continue
        if any(mot in motif.lower() for mot in MOTIFS_ECARTES):
            continue
        vues.add('/' + motif.lstrip('/'))
    return sorted(vues)


@pytest.fixture
def super_admin_tous_modules(client, django_user_model):
    """Un compte qui voit tout, et une entreprise dont tout est actif."""
    from apps.accounts.models import UserProfile
    from apps.core.models import Company
    from apps.private_saas.models import ALL_MODULE_CODES, CompanyModule

    entreprise = Company.objects.create(name='Parcours SA', slug='parcours')
    for code in ALL_MODULE_CODES:
        CompanyModule.objects.update_or_create(
            company=entreprise, module_code=code,
            defaults={'is_enabled': True})

    utilisateur = django_user_model.objects.create_user(
        'parcoureur', password='x', is_superuser=True, is_staff=True)
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.role = 'superadmin'
    profil.save()
    profil.companies.add(entreprise)

    client.force_login(django_user_model.objects.get(pk=utilisateur.pk))
    session = client.session
    session['current_company_id'] = entreprise.pk
    session.save()
    return utilisateur


# ── 1. Toutes les pages s'affichent ────────────────────────────────────────

@pytest.mark.django_db
def test_aucune_page_ne_leve_d_erreur(client, super_admin_tous_modules):
    """Le parcours complet. Environ une minute, et il en vaut la peine.

    On n'exige pas 200 partout : un 302 (redirection), un 403 (droit
    refusé) ou un 405 (vue en POST seulement) sont des réponses valides et
    volontaires. Ce qui n'est jamais valide, c'est une exception.
    """
    adresses = _adresses_sans_argument()
    assert len(adresses) > 500, (
        f'Seulement {len(adresses)} adresses trouvees : le parcours ne '
        f'mesurerait plus grand-chose.')

    par_code = collections.Counter()
    echecs = []

    for adresse in adresses:
        try:
            par_code[client.get(adresse).status_code] += 1
        except Exception as exc:                    # noqa: BLE001
            echecs.append(f'{adresse}\n      {type(exc).__name__}: '
                          f'{str(exc)[:160]}')

    assert not echecs, (
        f'{len(echecs)} page(s) levent une exception sur '
        f'{len(adresses)} visitees :\n  ' + '\n  '.join(echecs))

    # Un parcours ou tout redirige ne prouverait rien : si une regression
    # faisait rediriger l'ERP entier (perte de session, intergiciel
    # d'installation), le test ci-dessus passerait sans rien mesurer.
    assert par_code[200] > 800, (
        f'Seulement {par_code[200]} page(s) en 200 : quelque chose '
        f'detourne le parcours. Repartition : {dict(par_code)}')


# ── 1 bis. Les mêmes pages, sur une base PEUPLÉE ──────────────────────────
#
# Le parcours ci-dessus visite une base VIDE, et c'est sa limite : il n'a
# rien vu de la panne de la boutique publique, qui ne se declenche qu'avec
# un produit au catalogue. C'est avec des donnees que les gabarits
# bouclent, donc que les {% url %} s'evaluent et que les attributs se
# resolvent.
#
# Ce second parcours seme une instance de chaque modele rattache a une
# entreprise -- 458 modeles sur 462 -- puis revisite les memes adresses. Il
# a trouve huit pannes que le premier ne pouvait pas voir :
#
#   - trois « |default:<chemin.pointe> » dont l'argument ne resolvait pas.
#     Un argument de filtre n'est PAS silencieux, contrairement a une
#     variable seule : la page entiere tombait ;
#   - « conv.project.client_name », champ inexistant sur BTPProject ;
#   - une photo de reserve sans fichier, dont « .url » levait ValueError ;
#   - un widget de tableau de bord dont le gabarit, nomme en BASE,
#     n'existait pas -- il emportait le tableau de bord entier ;
#   - un « {% include ... ignore missing %} », syntaxe que Django n'accepte
#     pas pour « include » : TemplateSyntaxError des l'analyse.


COMPTEUR = {'n': 0}


def _valeur(champ, entreprise, deja_crees):
    """Une valeur plausible pour un champ requis, selon son type."""
    COMPTEUR['n'] += 1
    n = COMPTEUR['n']

    if champ.choices:
        return champ.choices[0][0]

    if isinstance(champ, models.ForeignKey):
        cible = champ.related_model
        if cible._meta.label == 'core.Company':
            return entreprise
        return deja_crees.get(cible._meta.label)

    if isinstance(champ, (models.SlugField,)):
        return f'essai-{n}'
    if isinstance(champ, models.EmailField):
        return f'essai{n}@exemple.fr'
    if isinstance(champ, models.URLField):
        return 'https://exemple.fr'
    if isinstance(champ, models.GenericIPAddressField):
        return '192.0.2.1'
    if isinstance(champ, models.UUIDField):
        import uuid
        return uuid.uuid4()
    if isinstance(champ, (models.CharField, models.TextField)):
        valeur = f'Essai {n}'
        longueur = getattr(champ, 'max_length', None)
        return valeur[:longueur] if longueur else valeur
    if isinstance(champ, models.BooleanField):
        return champ.name.startswith('is_active')
    if isinstance(champ, models.DecimalField):
        return decimal.Decimal('1')
    if isinstance(champ, (models.IntegerField, models.FloatField)):
        return 1
    if isinstance(champ, models.DateTimeField):
        return timezone.now()
    if isinstance(champ, models.DateField):
        return timezone.now().date()
    if isinstance(champ, models.TimeField):
        return datetime.time(9, 0)
    if isinstance(champ, models.DurationField):
        return datetime.timedelta(hours=1)
    if isinstance(champ, models.JSONField):
        return {} if champ.default is dict else []
    return None


def _semer(entreprise, utilisateur):
    """Cree une instance de chaque modele qu'on peut, en plusieurs passes."""
    deja = {'core.Company': entreprise,
            'auth.User': utilisateur}

    modeles = [m for m in registre.get_models()
               if m._meta.app_label not in ('contenttypes', 'sessions',
                                            'admin', 'auth', 'migrations')
               and not m._meta.abstract and not m._meta.proxy]

    echecs = {}
    progres = True
    while progres:
        progres = False
        for modele in modeles:
            label = modele._meta.label
            if label in deja:
                continue
            valeurs = {}
            manquant = False
            for champ in modele._meta.get_fields():
                if not getattr(champ, 'concrete', False):
                    continue
                if champ.primary_key or champ.auto_created:
                    continue
                if isinstance(champ, (models.FileField, models.ImageField)):
                    continue
                requis = (not getattr(champ, 'blank', True)
                          and not champ.has_default()
                          and not getattr(champ, 'null', False))
                if isinstance(champ, models.ForeignKey) and requis:
                    cible = champ.related_model._meta.label
                    if cible == 'core.Company':
                        valeurs[champ.name] = entreprise
                        continue
                    if cible in ('auth.User',):
                        valeurs[champ.name] = utilisateur
                        continue
                    if cible not in deja or deja[cible] is None:
                        manquant = True
                        break
                    valeurs[champ.name] = deja[cible]
                    continue
                if not requis:
                    # On renseigne quand meme l'entreprise : sans elle, les
                    # listes bornees par entreprise resteraient vides et la
                    # page ne bouclerait sur rien.
                    if (isinstance(champ, models.ForeignKey)
                            and champ.related_model._meta.label
                            == 'core.Company'):
                        valeurs[champ.name] = entreprise
                    continue
                v = _valeur(champ, entreprise, deja)
                if v is None:
                    manquant = True
                    break
                valeurs[champ.name] = v
            if manquant:
                continue
            try:
                with transaction.atomic():
                    deja[label] = modele.objects.create(**valeurs)
                progres = True
            except Exception as exc:                # noqa: BLE001
                echecs[label] = f'{type(exc).__name__}: {str(exc)[:110]}'
    return deja, echecs


@pytest.mark.django_db
def test_aucune_page_ne_leve_d_erreur_sur_donnees_peuplees(
        client, django_user_model):
    """Le parcours qui compte vraiment. Environ deux minutes.

    On n'exige pas 200 partout -- un 302, un 403 ou un 405 sont des
    reponses voulues. Ce qui n'est jamais acceptable, c'est une exception.
    """
    from apps.accounts.models import UserProfile
    from apps.core.models import Company
    from apps.private_saas.models import ALL_MODULE_CODES, CompanyModule

    entreprise = Company.objects.create(name='Peuple SA', slug='peuple-sa',
                                        sector='btp')
    for code in ALL_MODULE_CODES:
        CompanyModule.objects.update_or_create(
            company=entreprise, module_code=code,
            defaults={'is_enabled': True})

    utilisateur = django_user_model.objects.create_user(
        'semeur', password='x', is_superuser=True, is_staff=True,
        email='semeur@exemple.fr')
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.role = 'superadmin'
    profil.save()
    profil.companies.add(entreprise)

    crees, _echecs = _semer(entreprise, utilisateur)
    assert len(crees) > 300, (
        f'Seulement {len(crees)} modele(s) peuple(s) : le parcours ne '
        f'mesurerait plus grand-chose.')

    client.force_login(django_user_model.objects.get(pk=utilisateur.pk))
    session = client.session
    session['current_company_id'] = entreprise.pk
    session.save()

    par_code = collections.Counter()
    echecs = []
    for adresse in _adresses_sans_argument():
        try:
            par_code[client.get(adresse).status_code] += 1
        except Exception as exc:                    # noqa: BLE001
            echecs.append(f'{adresse}\n      {type(exc).__name__}: '
                          f'{str(exc)[:170]}')

    assert not echecs, (
        f'{len(echecs)} page(s) levent une exception AVEC DES DONNEES :\n  '
        + '\n  '.join(echecs))

    assert par_code[200] > 850, (
        f'Seulement {par_code[200]} page(s) en 200 : quelque chose '
        f'detourne le parcours. Repartition : {dict(par_code)}')


# ── 2. Tous les boutons mènent quelque part ───────────────────────────────

def _nom_introuvable(nom):
    """Vrai si ce nom d'URL n'existe pas du tout.

    Django rend DEUX messages differents, et ne reconnaitre que le premier
    etait un angle mort de ce fichier :

      - « 'x' is not a valid view function or pattern name » : l'espace de
        noms existe, le nom non ;
      - « 'y' is not a registered namespace » : l'espace de noms lui-meme
        n'existe pas -- c'est le cas de `orion_admin:dashboard`.

    Un troisieme message, « Reverse for 'x' with no arguments not found »,
    n'est PAS un defaut : le nom existe, la vue attend juste un pk. Le
    distinguer est tout l'objet de cette fonction.
    """
    try:
        reverse(nom)
        return False
    except NoReverseMatch as exc:
        message = str(exc)
        return ('not a valid view function or pattern name' in message
                or 'is not a registered namespace' in message)
    except Exception:
        return False


def _references_des_gabarits():
    refs = {}
    for racine in ('templates', 'apps'):
        for dossier, sous, fichiers in os.walk(os.path.join(RACINE, racine)):
            sous[:] = [s for s in sous
                       if s not in ('__pycache__', 'node_modules')]
            for nom in fichiers:
                if not nom.endswith('.html'):
                    continue
                chemin = os.path.join(dossier, nom)
                with open(chemin, encoding='utf-8', errors='replace') as f:
                    for ref in MOTIF_URL.findall(f.read()):
                        refs.setdefault(ref, set()).add(
                            os.path.relpath(chemin, RACINE))
    return refs


def test_chaque_bouton_mene_a_une_adresse_existante():
    """Un nom d'URL faux fait répondre 500 à toute la page qui le porte.

    Et il ne lève qu'au RENDU : ni `manage.py check`, ni l'import des
    modules, ni un test de modèle ne le voient.
    """
    refs = _references_des_gabarits()
    assert len(refs) > 500, 'Trop peu de references lues : test sans valeur.'

    casses = {ref: sorted(fichiers) for ref, fichiers in refs.items()
              if ref not in NOMS_MORTS_ACCEPTES and _nom_introuvable(ref)}

    details = []
    for ref, fichiers in sorted(casses.items()):
        autres = f' +{len(fichiers) - 1}' if len(fichiers) > 1 else ''
        details.append(f'{ref}  ({os.path.basename(fichiers[0])}{autres})')

    assert not casses, (
        f'{len(casses)} nom(s) d URL cite(s) par un gabarit et inexistant(s). '
        f'Chaque page qui porte ce bouton repondra 500 au rendu. Si le '
        f'gabarit est mort, ajoutez le nom a NOMS_MORTS_ACCEPTES EN DISANT '
        f'POURQUOI.\n  ' + '\n  '.join(details))


def test_la_liste_des_noms_morts_ne_contient_rien_de_vivant():
    """L'inverse : une exception devenue inutile doit disparaître.

    Si quelqu'un crée enfin `ecommerce:article_list`, le laisser dans la
    liste des morts masquerait un vrai bouton — et le test ne surveillerait
    plus rien à son sujet.
    """
    ressuscites = [nom for nom in sorted(NOMS_MORTS_ACCEPTES)
                   if not _nom_introuvable(nom)]

    assert not ressuscites, (
        'Ces noms existent desormais et doivent sortir de '
        'NOMS_MORTS_ACCEPTES :\n  ' + '\n  '.join(ressuscites))


# ── 3. Les champs que les requêtes nomment existent ───────────────────────

def test_weborder_n_a_pas_de_champ_created_at():
    """La régression nommée : sept requêtes utilisaient un champ absent.

    `ecommerce.WebOrder` n'a pas de `created_at` — son horodatage est
    `order_date` (`auto_now_add=True`). Sept requêtes le nommaient, et
    chacune levait `FieldError` : tableau de bord e-commerce, API SIÈCLE,
    API LUNEA, historique de commandes du client.

    Attention au piège qui m'a arrêté en route : `lunea.WebOrder` est un
    AUTRE modèle, et lui a bien un `created_at`. Deux classes de même nom,
    aux champs différents.
    """
    from apps.ecommerce.models import WebOrder as EcomWebOrder
    from apps.lunea.models import WebOrder as LuneaWebOrder

    champs_ecom = {c.name for c in EcomWebOrder._meta.get_fields()
                   if getattr(c, 'concrete', False)}
    assert 'order_date' in champs_ecom
    assert 'created_at' not in champs_ecom

    champs_lunea = {c.name for c in LuneaWebOrder._meta.get_fields()
                    if getattr(c, 'concrete', False)}
    assert 'created_at' in champs_lunea, (
        'lunea.WebOrder a perdu created_at : les widgets du tableau de '
        'bord qui le nomment vont lever.')


def test_aucune_requete_ne_nomme_created_at_sur_le_weborder_ecommerce():
    """Garde de source : le défaut se reproduirait sans bruit.

    Une requête sur un champ absent ne lève qu'à l'EXÉCUTION de la vue.
    Ce test relit les sources, pour que l'erreur se voie sans attendre
    qu'un utilisateur ouvre la page.
    """
    suspects = []
    for fichier in ('apps/ecommerce/views.py', 'apps/ecommerce/store_views.py',
                    'apps/ecommerce/brand_views.py'):
        chemin = os.path.join(RACINE, fichier)
        if not os.path.isfile(chemin):
            continue
        with open(chemin, encoding='utf-8') as f:
            for numero, ligne in enumerate(f, 1):
                if 'WebOrder' in ligne and 'created_at' in ligne:
                    suspects.append(f'{fichier}:{numero}')

    assert not suspects, (
        'ecommerce.WebOrder n a pas de created_at : utilisez order_date.\n  '
        + '\n  '.join(suspects))
