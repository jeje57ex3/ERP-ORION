# -*- coding: utf-8 -*-
"""Pose en base les traductions du contenu statique des sites publics.

LE DÉFAUT, MESURÉ SUR LE SITE EN SERVICE

Les noms de services et la foire aux questions des vitrines ne viennent pas
de la base : ce sont des listes Python, dans
`apps/websites/electricite_public_views.py` et `btp_public_views.py`. Elles
passent par `translate_static_items`, qui lit `InterfaceTranslation` — donc
la base — et retombe sur le français quand aucune ligne n'existe.

Or rien ne créait ces lignes, sinon `manage.py seed_site_translations`, un
fichier **qui n'était pas suivi par git**. Il n'existait donc pas sur le
serveur. Et c'était une commande en terminal, ce que les règles de ce
projet interdisent pour un réglage d'exploitation.

Conséquence : sur le site en service, les noms de services et la FAQ —
l'essentiel du contenu visible d'une page d'accueil — restaient en français
DANS TOUTES LES LANGUES. Rien ne le signalait, une traduction absente
retombant sur sa source. C'est le troisième défaut de cette famille dans
ce dépôt : un fichier non versionné dont dépend une fonctionnalité qui,
elle, l'est.

CE QU'ELLE N'ÉCRASE JAMAIS

Une traduction déjà présente ET renseignée. Si quelqu'un a corrigé une
formulation depuis l'écran des traductions, c'est sa version qui reste :
cette migration est rejouée sur chaque base, et une migration de contenu
qui écrase est une migration qu'on regrette. En revanche elle REMPLIT une
ligne existante mais vide — `sync_missing_translations` en crée de telles
coquilles, et une coquille vide n'est pas un choix à respecter.
"""
from django.db import migrations

from apps.translations.contenu_des_sites import TRADUCTIONS_DES_SITES


def poser(apps, schema_editor):
    Language = apps.get_model('translations', 'Language')
    Traduction = apps.get_model('translations', 'InterfaceTranslation')

    langues = {langue.code: langue
               for langue in Language.objects.filter(is_active=True)}

    for cle, par_langue in TRADUCTIONS_DES_SITES.items():
        module = cle.split('.')[0]
        for code, texte in par_langue.items():
            langue = langues.get(code)
            if langue is None:
                # La langue n'est pas active sur cette installation : on
                # ne la crée pas ici. C'est la migration
                # `0002_cinq_langues_du_site` qui décide des langues.
                continue

            ligne = Traduction.objects.filter(
                company=None, key=cle, language=langue).first()

            if ligne is None:
                Traduction.objects.create(
                    company=None, key=cle, language=langue,
                    source_text=texte, translated_text=texte,
                    module=module, is_verified=True)
            elif not (ligne.translated_text or '').strip():
                # Coquille vide : on la remplit. Ce n'est pas un choix
                # qu'on écrase, c'est un trou qu'on comble.
                ligne.translated_text = texte
                ligne.source_text = ligne.source_text or texte
                ligne.module = ligne.module or module
                ligne.is_verified = True
                ligne.save(update_fields=['translated_text', 'source_text',
                                          'module', 'is_verified'])


def retirer(apps, schema_editor):
    """Ne retire que les lignes restées identiques à ce que l'on a posé.

    Une formulation corrigée depuis l'écran des traductions n'est pas de
    notre fait et ne doit pas disparaître avec un retour en arrière.
    """
    Language = apps.get_model('translations', 'Language')
    Traduction = apps.get_model('translations', 'InterfaceTranslation')

    langues = {langue.code: langue for langue in Language.objects.all()}
    for cle, par_langue in TRADUCTIONS_DES_SITES.items():
        for code, texte in par_langue.items():
            langue = langues.get(code)
            if langue is None:
                continue
            Traduction.objects.filter(
                company=None, key=cle, language=langue,
                translated_text=texte).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('translations', '0004_detection_auto_sur_les_sites_existants'),
    ]

    operations = [
        migrations.RunPython(poser, retirer),
    ]
