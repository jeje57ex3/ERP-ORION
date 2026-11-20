# -*- coding: utf-8 -*-
"""Les cinq langues du site existent, sont actives, et sont choisies.

TROIS RAISONS INDÉPENDANTES EMPÊCHAIENT L'ALLEMAND, et chacune suffisait.

1. **La langue n'existait qu'en terminal.** Les lignes de `Language` ne sont
   créées que par `manage.py seed_languages` — vérifié sur tout le dépôt,
   aucun autre endroit n'en crée. Sur une installation où la commande n'a
   jamais tourné, la table est vide, `_get_website_languages` rend une liste
   vide, et le sélecteur de langue **disparaît sans un mot**, le gabarit
   étant gardé par un `{% if website_languages %}`. Une migration, elle,
   passe à chaque mise à jour sans que personne n'ouvre un terminal.

2. **L'allemand était semé inactif.** `seed_languages` le crée avec
   `is_active: False`. Or `set_site_language` ne retient un code que si la
   langue est active, et `get_enabled_language_list()` filtre de même : on
   pouvait cliquer « Deutsch », la vue refusait, et la page revenait en
   français sans rien expliquer.

3. **Il n'était pas dans les cinq langues par défaut d'un site**, qui
   contenaient de l'italien à sa place.

POURQUOI ON NE TOUCHE PAS À L'ITALIEN NI AU NÉERLANDAIS

Les désactiver serait un choix qu'on ne nous a pas demandé, et un site les
emploie peut-être déjà. Cette migration n'ajoute et n'active que ce qui
manque.
"""
from django.db import migrations

#: Les cinq langues demandées pour le site, avec leur drapeau et leur rang
#: d'affichage dans le sélecteur. L'ordre reprend celui de `seed_languages`
#: pour les quatre qui y figuraient déjà, afin que le sélecteur ne change pas
#: d'ordre sous les yeux de l'exploitant.
LANGUES = [
    {'code': 'fr', 'name': 'French', 'native_name': 'Français',
     'flag_icon': '\U0001F1EB\U0001F1F7', 'order': 1},
    {'code': 'en', 'name': 'English', 'native_name': 'English',
     'flag_icon': '\U0001F1EC\U0001F1E7', 'order': 2},
    {'code': 'es', 'name': 'Spanish', 'native_name': 'Español',
     'flag_icon': '\U0001F1EA\U0001F1F8', 'order': 3},
    {'code': 'pt', 'name': 'Portuguese', 'native_name': 'Português',
     'flag_icon': '\U0001F1F5\U0001F1F9', 'order': 5},
    {'code': 'de', 'name': 'German', 'native_name': 'Deutsch',
     'flag_icon': '\U0001F1E9\U0001F1EA', 'order': 6},
]

CODES = [langue['code'] for langue in LANGUES]

#: Le domaine du site dont on nous a demandé les cinq langues.
DOMAINE = 's-peace.com'


def _sites_concernes(Website, WebsiteDomain):
    identifiants = set(
        Website.objects.filter(domain__icontains=DOMAINE)
        .values_list('pk', flat=True))
    identifiants.update(
        WebsiteDomain.objects.filter(domain__icontains=DOMAINE)
        .values_list('website_id', flat=True))
    return identifiants


def installer(apps, schema_editor):
    Language = apps.get_model('translations', 'Language')
    Reglages = apps.get_model('translations', 'WebsiteLanguageSettings')
    Website = apps.get_model('websites', 'Website')
    WebsiteDomain = apps.get_model('websites', 'WebsiteDomain')

    for donnees in LANGUES:
        langue, cree = Language.objects.get_or_create(
            code=donnees['code'],
            defaults={
                'name': donnees['name'],
                'native_name': donnees['native_name'],
                'flag_icon': donnees['flag_icon'],
                'order': donnees['order'],
                'is_active': True,
            })
        if cree:
            continue
        # Elle existait : on l'active si elle ne l'était pas, et on lui pose
        # un drapeau si elle n'en avait pas. On ne retouche ni son nom ni son
        # ordre, que l'exploitant a peut-être ajustés.
        champs = []
        if not langue.is_active:
            langue.is_active = True
            champs.append('is_active')
        if not (langue.flag_icon or '').strip():
            langue.flag_icon = donnees['flag_icon']
            champs.append('flag_icon')
        if champs:
            langue.save(update_fields=champs)

    # Le français reste la langue par défaut du système s'il n'y en a aucune.
    if not Language.objects.filter(is_default=True).exists():
        Language.objects.filter(code='fr').update(is_default=True)

    # Le site nommé reçoit exactement les cinq langues demandées. Les autres
    # sites ne sont pas touchés : leur choix leur appartient, et l'écran des
    # langues permet de le changer.
    cinq = list(Language.objects.filter(code__in=CODES))
    for identifiant in _sites_concernes(Website, WebsiteDomain):
        reglages, _cree = Reglages.objects.get_or_create(website_id=identifiant)
        reglages.enabled_languages.add(*cinq)
        if reglages.default_language_id is None:
            site = Website.objects.filter(pk=identifiant).first()
            prefere = (site.language if site else 'fr') or 'fr'
            if prefere not in CODES:
                prefere = 'fr'
            defaut = Language.objects.filter(code=prefere).first()
            if defaut is not None:
                reglages.default_language = defaut
                reglages.save(update_fields=['default_language'])
        if not reglages.show_language_switcher:
            reglages.show_language_switcher = True
            reglages.save(update_fields=['show_language_switcher'])


def desinstaller(apps, schema_editor):
    """Rend l'allemand inactif, et rien d'autre.

    Les quatre autres langues étaient déjà actives avant cette migration :
    les désactiver en revenant en arrière casserait un site qui marchait.
    L'allemand, lui, était bien inactif — c'est le seul état que cette
    migration a changé et qu'elle peut donc rendre.
    """
    Language = apps.get_model('translations', 'Language')
    Language.objects.filter(code='de').update(is_active=False)


class Migration(migrations.Migration):

    dependencies = [
        ('translations', '0001_initial'),
        # La migration touche `WebsiteLanguageSettings`, qui pointe vers
        # `websites.Website` : la table doit exister quand elle passe.
        ('websites', '0029_zone_intervention_leiria'),
    ]

    operations = [
        migrations.RunPython(installer, desinstaller),
    ]
