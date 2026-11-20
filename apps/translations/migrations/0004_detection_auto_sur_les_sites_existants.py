# -*- coding: utf-8 -*-
"""Conserve la détection automatique de langue là où elle existait déjà.

CE QUI SE PASSAIT AVANT, ET POURQUOI CETTE MIGRATION EST UNE CONSERVATION
ET NON UN AJOUT.

`OrionLanguageMiddleware` consultait l'en-tête `Accept-Language` du
navigateur pour TOUTES les requêtes, sans condition et sans savoir quel
site était servi. La détection automatique était donc en place partout, à
l'insu de tout le monde — y compris de l'exploitant, dont le réglage
« choisir la langue du visiteur automatiquement » n'était lu par rien :
`apps/websites/services/language_resolver.py`, qui seul le lit, dormait.

Ce réglage est maintenant branché. Son défaut passe à vrai pour les
nouvelles lignes, et cette migration l'active sur celles qui existent — car
le laisser à faux aurait RETIRÉ la détection à tous les sites qui en
bénéficiaient. Une correction qui enlève une fonctionnalité en passant
n'est pas une correction.

L'exploitant peut le couper depuis l'écran des langues du site. C'est le
sens du réglage : il décide, au lieu de subir un comportement qu'aucun
écran ne montrait.
"""
from django.db import migrations


def activer(apps, schema_editor):
    Reglages = apps.get_model('translations', 'WebsiteLanguageSettings')
    Reglages.objects.filter(auto_redirect_by_browser=False).update(
        auto_redirect_by_browser=True)


def desactiver(apps, schema_editor):
    """Ne fait rien, volontairement.

    On ne peut pas distinguer une ligne que cette migration a passée à vrai
    d'une ligne que l'exploitant a cochée lui-même : aucune des deux ne
    porte de marque. Tout remettre à faux effacerait donc un choix. Le
    retour en arrière laisse les valeurs en place, et l'écran des langues
    permet de les changer une par une.
    """


class Migration(migrations.Migration):

    dependencies = [
        ('translations',
         '0003_alter_websitelanguagesettings_auto_redirect_by_browser'),
    ]

    operations = [
        migrations.RunPython(activer, desactiver),
    ]
