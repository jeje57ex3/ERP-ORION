"""Défauts de gabarit qui ne se voient qu'en production.

Deux familles, et la même raison d'être ici : aucun test fonctionnel ne les
attrape, parce que la page répond 200 et que seul son contenu est faux.

**`{# … #}` ne vaut que sur UNE ligne.** Django découpe ses jetons avec

    tag_re = re.compile(r"({%.*?%}|{{.*?}}|{#.*?#})")

sans `re.DOTALL`. Le point ne franchit donc pas une fin de ligne : un `{#`
fermé deux lignes plus bas n'est pas reconnu comme un commentaire. Son texte
part dans la page, et s'il contient un tag, ce tag est exécuté. Mesure
faite : dix-neuf commentaires de ce genre dans ce dépôt, dont un dans
`erp_base.html` qui affichait « PREVENIR, pas bloquer… » à tous les
utilisateurs dès qu'une maintenance était annoncée, et un dans
`timesheet_list.html` qui portait un `{% url %}` et renvoyait une erreur 500
sur la liste des pointages.

**`{% static %}` doit désigner un fichier qui existe.** En production le
stockage est `CompressedManifestStaticFilesStorage` : un chemin absent du
manifeste lève `ValueError` au rendu, et la page entière répond 500. Or
`settings/testing.py` et `settings/local.py` remplacent tous deux ce
stockage par `StaticFilesStorage`, qui se contente de concaténer l'URL.
Cette classe d'erreur est donc **invisible dans toute la suite de tests** —
c'est exactement le genre de défaut qui n'apparaît que sur la VM.
"""

import os
import re

RACINE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOSSIER_GABARITS = os.path.join(RACINE, 'templates')

MOTIF_COMMENTAIRE = re.compile(r'\{#(.*?)#\}', re.DOTALL)
MOTIF_STATIC = re.compile(r"""\{%\s*static\s+['"]([^'"]+)['"]""")


def _gabarits():
    for dossier, _sous, fichiers in os.walk(DOSSIER_GABARITS):
        for fichier in fichiers:
            if fichier.endswith('.html'):
                yield os.path.join(dossier, fichier)


def _lire(chemin):
    with open(chemin, encoding='utf-8', errors='replace') as flux:
        return flux.read()


def test_aucun_commentaire_etale_sur_plusieurs_lignes():
    """Un {# #} multi-lignes n'est pas un commentaire : son texte s'affiche.

    Pour un commentaire sur plusieurs lignes, il faut
    {% comment %} … {% endcomment %}.
    """
    coupables = []
    for chemin in _gabarits():
        source = _lire(chemin)
        for trouve in MOTIF_COMMENTAIRE.finditer(source):
            if '\n' in trouve.group(1):
                ligne = source[:trouve.start()].count('\n') + 1
                relatif = os.path.relpath(chemin, RACINE)
                debut = trouve.group(1).strip().splitlines()[0][:60]
                coupables.append(f'{relatif}:{ligne} — « {debut}… »')

    assert not coupables, (
        'Commentaires {# #} étalés sur plusieurs lignes — leur texte sera '
        'rendu dans la page. Utilisez {% comment %} … {% endcomment %} :\n  '
        + '\n  '.join(coupables))


def test_chaque_static_designe_un_fichier_existant():
    """Sinon : ValueError au rendu, et 500 sur la page entière en production.

    Le manifeste est construit par collectstatic depuis les dossiers
    statiques ; un chemin qui n'y figure pas n'est pas une URL cassée mais
    une exception.
    """
    dossiers = [os.path.join(RACINE, 'static')]
    for nom in ('staticfiles', 'static_root'):
        chemin = os.path.join(RACINE, nom)
        if os.path.isdir(chemin):
            dossiers.append(chemin)

    manquants = []
    vus = set()
    for chemin in _gabarits():
        for reference in MOTIF_STATIC.findall(_lire(chemin)):
            if reference in vus:
                continue
            vus.add(reference)
            if not any(os.path.isfile(os.path.join(dossier, reference))
                       for dossier in dossiers):
                manquants.append(
                    f'{reference} (cité par {os.path.relpath(chemin, RACINE)})')

    assert not manquants, (
        'Fichiers statiques cités mais introuvables — en production, '
        'CompressedManifestStaticFilesStorage lève ValueError et la page '
        'répond 500 :\n  ' + '\n  '.join(manquants))


def test_le_bandeau_de_maintenance_ne_laisse_pas_fuir_son_commentaire(
        client, django_user_model, db):
    """Régression mesurée, et sur la page de tout le monde.

    Le commentaire d'`erp_base.html` s'affichait littéralement dès qu'une
    annonce de maintenance était active — c'est-à-dire précisément pendant
    un redémarrage ou une mise à jour, au moment où la page doit être
    rassurante et lisible.
    """
    from apps.accounts.models import UserProfile
    from apps.core.maintenance import annoncer
    from apps.core.models import Company
    from django.urls import reverse

    entreprise = Company.objects.create(name='X SA', slug='x-sa')
    utilisateur = django_user_model.objects.create_user(
        'patron', password='x', is_superuser=True, is_staff=True)
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.role = 'superadmin'
    profil.save()
    profil.companies.add(entreprise)

    client.force_login(django_user_model.objects.get(pk=utilisateur.pk))
    assert annoncer('redemarrage', duree_minutes=5) is not None

    corps = client.get(reverse('accounts:profile')).content.decode()
    assert 'Redémarrage' in corps, 'le bandeau devrait être affiché'
    assert 'PREVENIR, pas bloquer' not in corps
    assert 'MaintenanceModeMiddleware' not in corps
