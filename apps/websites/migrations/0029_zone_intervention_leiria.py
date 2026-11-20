"""Renseigne la zone d'intervention du site Sparkling Peace.

POURQUOI UNE MIGRATION ET PAS UNE SAISIE DANS L'ÉCRAN

Le champ `service_area` est éditable depuis les réglages du site, et c'est
là qu'il se modifiera ensuite. Mais il vient de naître vide : sans cette
migration, la mention demandée n'apparaîtrait sur le site qu'après que
quelqu'un ait pensé à ouvrir l'écran et à la taper. Une mise à jour qui
livre un champ vide livre une fonctionnalité, pas un résultat.

POURQUOI ON NE PEUT PAS DÉSIGNER LE SITE PAR SON IDENTIFIANT

Les numéros de clé primaire diffèrent d'une installation à l'autre. Le
domaine, lui, est la même chaîne partout : « s-peace.com ». On le cherche
donc à deux endroits, parce que les deux existent — le champ `domain` du
site, rempli à la création, et la table `WebsiteDomain`, qui porte les
domaines branchés ensuite (voir `domaine_vitrine_middleware`).

CE QU'ELLE NE FAIT JAMAIS

Écraser une valeur déjà saisie. Si quelqu'un a écrit sa propre zone
d'intervention avant que cette migration ne passe — ou s'il la corrige
puis que la migration est rejouée sur une autre base — c'est sa valeur qui
reste. Une migration de contenu qui écrase est une migration qu'on
regrette.
"""
from django.db import migrations

#: Le domaine qui désigne le site, à la casse près.
DOMAINE = 's-peace.com'

#: La mention demandée. Le gabarit l'affiche derrière un libellé traduit
#: — « Zone d'intervention : … » — et non enchâssée dans une phrase :
#: une phrase traduite autour d'une valeur qui, elle, ne l'est pas
#: donnerait de l'allemand mêlé de français. La valeur doit donc se
#: lire seule, d'où la majuscule initiale.
ZONE = 'Région de Leiria, Portugal'

#: `country` vaut « France » par défaut sur chaque site créé, ce qui est
#: faux pour une entreprise portugaise. Aucun code ne lit ce champ — vérifié
#: sur tout `apps/websites` — il n'est donc corrigé que pour dire vrai.
PAYS = 'Portugal'


def _sites_concernes(Website, WebsiteDomain):
    """Les identifiants des sites portant ce domaine, d'où qu'il vienne."""
    identifiants = set(
        Website.objects.filter(domain__icontains=DOMAINE)
        .values_list('pk', flat=True))
    identifiants.update(
        WebsiteDomain.objects.filter(domain__icontains=DOMAINE)
        .values_list('website_id', flat=True))
    return identifiants


def renseigner(apps, schema_editor):
    Website = apps.get_model('websites', 'Website')
    WebsiteDomain = apps.get_model('websites', 'WebsiteDomain')

    for identifiant in _sites_concernes(Website, WebsiteDomain):
        site = Website.objects.filter(pk=identifiant).first()
        if site is None:
            continue
        champs = []
        if not (site.service_area or '').strip():
            site.service_area = ZONE
            champs.append('service_area')
        if (site.country or '').strip() in ('', 'France'):
            site.country = PAYS
            champs.append('country')
        if champs:
            site.save(update_fields=champs)


def retirer(apps, schema_editor):
    """Ne retire QUE la valeur que cette migration a posée.

    Si l'exploitant a écrit autre chose entre-temps, on n'y touche pas : une
    annulation ne doit pas effacer un travail qu'elle n'a pas fait.
    """
    Website = apps.get_model('websites', 'Website')
    WebsiteDomain = apps.get_model('websites', 'WebsiteDomain')

    for identifiant in _sites_concernes(Website, WebsiteDomain):
        site = Website.objects.filter(pk=identifiant, service_area=ZONE).first()
        if site is not None:
            site.service_area = ''
            site.save(update_fields=['service_area'])


class Migration(migrations.Migration):

    dependencies = [
        ('websites', '0028_website_service_area'),
    ]

    operations = [
        migrations.RunPython(renseigner, retirer),
    ]
