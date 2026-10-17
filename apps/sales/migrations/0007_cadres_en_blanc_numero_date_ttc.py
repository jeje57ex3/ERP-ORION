"""Passe en blanc les cadres déjà posés pour le numéro, la date et le total TTC.

Demandé explicitement : ces trois valeurs se posent sur un bandeau sombre du
modèle, où du texte noir est illisible.

La migration ne touche QUE ces trois clés, et seulement les cadres restés à
la couleur par défaut (`#000000`). Un cadre dont la couleur a déjà été
choisie à la main est laissé tel quel : écraser un choix délibéré au nom
d'un réglage global est précisément ce qu'une migration de données ne doit
pas faire.
"""

from django.db import migrations

CLES_EN_BLANC = ('numero_devis', 'date', 'total_ttc')

NOIR = '#000000'
BLANC = '#FFFFFF'


def passer_en_blanc(apps, schema_editor):
    Champ = apps.get_model('sales', 'QuoteTemplateField')
    Champ.objects.filter(cle__in=CLES_EN_BLANC, couleur=NOIR).update(
        couleur=BLANC)


def revenir_au_noir(apps, schema_editor):
    """Retour en arrière.

    On ne peut pas distinguer un blanc posé par cette migration d'un blanc
    choisi ensuite à la main : le retour remet donc en noir tous les cadres
    blancs de ces trois clés. C'est la conséquence à accepter, et elle est
    dite ici plutôt que découverte.
    """
    Champ = apps.get_model('sales', 'QuoteTemplateField')
    Champ.objects.filter(cle__in=CLES_EN_BLANC, couleur=BLANC).update(
        couleur=NOIR)


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0006_quote_cout_fournitures_quote_cout_main_oeuvre_and_more'),
    ]

    operations = [
        migrations.RunPython(passer_en_blanc, revenir_au_noir),
    ]
