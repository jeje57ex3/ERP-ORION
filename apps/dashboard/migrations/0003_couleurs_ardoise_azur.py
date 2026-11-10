# -*- coding: utf-8 -*-
"""Les couleurs du tableau de bord suivent la palette ardoise et azur.

Deux choses, et la seconde compte plus que la premiere.

LA VALEUR PAR DEFAUT. `color` naissait a `#C6A15B`, l'or de marque. Tout
widget cree apres la bascule serait donc ne dore sur une interface froide.

LES LIGNES DEJA EN BASE. C'est le vrai sujet. Changer un `default` ne
touche AUCUNE ligne existante : le tableau de bord de production serait
reste entierement dore, et l'or ne figure plus dans le selecteur de
couleurs (`apps/dashboard/forms.py`) -- la couleur se serait donc affichee
sans etre proposee, et aurait disparu a la premiere modification du
widget, sans que personne ne comprenne pourquoi.

Seules les lignes portant EXACTEMENT l'ancienne valeur sont converties.
Une couleur choisie a la main parmi les autres (vert, bleu, violet...) est
laissee telle quelle : elle disait quelque chose.

La marche arriere est ecrite et fonctionne, mais elle repeindra en or
toute ligne devenue azur depuis -- y compris celles choisies deliberement.
C'est inherent a une conversion de valeurs : rien n'enregistre
l'intention.
"""
from django.db import migrations, models

OR_DE_MARQUE = '#C6A15B'
AZUR = '#00A5C4'
BRUN_ORION = '#3A2A1A'
ARDOISE = '#212D44'

CORRESPONDANCES = ((OR_DE_MARQUE, AZUR), (BRUN_ORION, ARDOISE))

MODELES = ('DashboardWidget', 'DashboardShortcut')


def vers_le_froid(apps, schema_editor):
    for nom in MODELES:
        modele = apps.get_model('dashboard', nom)
        for avant, apres in CORRESPONDANCES:
            modele.objects.filter(color=avant).update(color=apres)


def retour_au_chaud(apps, schema_editor):
    for nom in MODELES:
        modele = apps.get_model('dashboard', nom)
        for avant, apres in CORRESPONDANCES:
            modele.objects.filter(color=apres).update(color=avant)


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0002_alter_dashboardwidget_widget_type_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dashboardshortcut',
            name='color',
            field=models.CharField(default='#00A5C4', max_length=7,
                                   verbose_name='Couleur'),
        ),
        migrations.AlterField(
            model_name='dashboardwidget',
            name='color',
            field=models.CharField(default='#00A5C4', max_length=7,
                                   verbose_name='Couleur'),
        ),
        migrations.RunPython(vers_le_froid, retour_au_chaud),
    ]
