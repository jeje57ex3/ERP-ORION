"""Adresses publiques des produits et des catégories.

Sans ce champ, la boutique publique répondait 500 dès qu'un seul produit
ou une seule catégorie existait : les routes sont déclarées en
« <slug:slug> » et les gabarits construisaient leurs liens avec
« p.slug », qui rendait une chaîne vide — `{% url %}` levait
NoReverseMatch, et la page entière avec.

L'ORDRE DES OPÉRATIONS EST ESSENTIEL ICI.

Django a généré AddField puis AlterUniqueTogether. Tel quel, cette
migration échouerait sur toute base contenant déjà des produits : le
champ est ajouté vide pour toutes les lignes, et la contrainte
(company, slug) refuserait la deuxième ligne d'une même entreprise.

Le `RunPython` inséré entre les deux remplit les slugs AVANT la
contrainte. Il traite les collisions de nom — deux produits « Écrou M8 »
dans la même entreprise donnent « ecrou-m8 » et « ecrou-m8-2 » — et il
est réversible : la marche arrière vide simplement la colonne, qui
disparaît ensuite avec le champ.
"""

from django.db import migrations, models
from django.utils.text import slugify


def _remplir(modele, ancien_slug_vide=''):
    """Donne à chaque ligne un slug unique au sein de son entreprise."""
    pris = {}
    for objet in modele.objects.all().order_by('pk').iterator():
        if objet.slug and objet.slug != ancien_slug_vide:
            pris.setdefault(objet.company_id, set()).add(objet.slug)

    a_ecrire = []
    for objet in modele.objects.all().order_by('pk').iterator():
        if objet.slug and objet.slug != ancien_slug_vide:
            continue
        deja = pris.setdefault(objet.company_id, set())
        base = (slugify(objet.name or '') or 'sans-nom')[:214]
        candidat = base
        numero = 2
        while candidat in deja:
            candidat = f'{base}-{numero}'
            numero += 1
        deja.add(candidat)
        objet.slug = candidat
        a_ecrire.append(objet)
        if len(a_ecrire) >= 500:
            modele.objects.bulk_update(a_ecrire, ['slug'])
            a_ecrire = []
    if a_ecrire:
        modele.objects.bulk_update(a_ecrire, ['slug'])


def remplir_les_slugs(apps, schema_editor):
    _remplir(apps.get_model('inventory', 'ProductCategory'))
    _remplir(apps.get_model('inventory', 'Product'))


def vider_les_slugs(apps, schema_editor):
    for nom in ('ProductCategory', 'Product'):
        apps.get_model('inventory', nom).objects.update(slug='')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_maintenanceannonce'),
        ('inventory', '0003_remove_product_inv_prod_co_active_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='slug',
            field=models.SlugField(blank=True, max_length=220, verbose_name='Slug'),
        ),
        migrations.AddField(
            model_name='productcategory',
            name='slug',
            field=models.SlugField(blank=True, max_length=220, verbose_name='Slug'),
        ),
        # ENTRE les deux : voir l'en-tête de ce fichier.
        migrations.RunPython(remplir_les_slugs, vider_les_slugs),
        migrations.AlterUniqueTogether(
            name='product',
            unique_together={('company', 'slug')},
        ),
        migrations.AlterUniqueTogether(
            name='productcategory',
            unique_together={('company', 'slug')},
        ),
    ]
