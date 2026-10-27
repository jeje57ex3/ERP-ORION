"""Tout fichier statique référencé par un gabarit doit être livré.

Défaut de ma main, livré en production. Le commit qui a branché l'éditeur
visuel versionnait ses deux gabarits et **aucun** de leurs cinq fichiers
statiques : `static/site_builder/` n'avait jamais été ajouté à git. Les
fichiers existaient sur ma machine, et nulle part ailleurs.

Pourquoi aucun test ne l'a vu : tous les tests tournaient sur ma machine,
où les cinq fichiers sont bien présents. Vérifier leur **existence** aurait
donc passé partout et échoué seulement sur le serveur. Ce qui distingue
mon disque d'un déploiement neuf n'est pas l'existence du fichier, c'est
son **suivi par git** — et c'est donc cela qu'il faut mesurer.

Pourquoi cela casse une page entière plutôt qu'une image : en production,
`STATICFILES_STORAGE` est le stockage à manifeste de WhiteNoise. Une entrée
absente du manifeste ne dégrade pas l'affichage, elle lève une exception au
rendu — la page répond 500, et non « sans style ».

Le test ne considère que les gabarits suivis par git : un gabarit non
versionné n'est pas déployé, et sa référence ne casse rien. C'est ce qui
distingue le défaut livré des modules encore sur l'établi.
"""

import os
import re
import subprocess

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MOTIF_STATIC = re.compile(r"\{%\s*static\s+['\"]([^'\"]+)['\"]")


def _fichiers_suivis():
    """Les chemins connus de git, ou None si git est indisponible."""
    try:
        acheve = subprocess.run(
            ['git', 'ls-files'], cwd=RACINE,
            capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if acheve.returncode != 0:
        return None
    return set(acheve.stdout.splitlines())


def _dossiers_statiques_des_apps():
    dossier_apps = os.path.join(RACINE, 'apps')
    if not os.path.isdir(dossier_apps):
        return []
    return [
        f'apps/{nom}/static'
        for nom in sorted(os.listdir(dossier_apps))
        if os.path.isdir(os.path.join(dossier_apps, nom, 'static'))
    ]


def test_aucune_reference_statique_n_est_absente_du_depot():
    """Le test qui aurait attrapé la panne de l'éditeur visuel.

    Pour chaque `{% static %}` littéral d'un gabarit versionné, le fichier
    visé doit être versionné lui aussi. « Présent sur mon disque » ne
    compte pas : c'est précisément l'illusion qui a laissé partir des
    gabarits sans leurs fichiers.
    """
    suivis = _fichiers_suivis()
    if suivis is None:
        pytest.skip('git indisponible : ce test mesure le contenu du depot.')

    bases_statiques = ['static'] + _dossiers_statiques_des_apps()
    problemes = []

    for chemin in sorted(suivis):
        if not chemin.endswith('.html'):
            continue
        absolu = os.path.join(RACINE, chemin)
        try:
            with open(absolu, encoding='utf-8') as fichier:
                contenu = fichier.read()
        except OSError:
            continue

        for reference in MOTIF_STATIC.findall(contenu):
            # « {% static logo_url %} » et les chemins composés d'une
            # variable ne designent pas un fichier connu a l'avance.
            if '{{' in reference or '{%' in reference:
                continue

            candidats = [f'{base}/{reference}' for base in bases_statiques]
            if any(candidat in suivis for candidat in candidats):
                continue

            sur_le_disque = any(
                os.path.isfile(os.path.join(RACINE, candidat))
                for candidat in candidats)
            etat = ('present sur le disque mais ABSENT du depot'
                    if sur_le_disque else 'introuvable')
            problemes.append(f'  {reference}  [{etat}]\n      <- {chemin}')

    assert not problemes, (
        'Des gabarits versionnes referencent des fichiers statiques qui ne '
        'seront pas deployes. En production, le stockage a manifeste leve '
        'une exception au rendu : ces pages repondront 500.\n'
        + '\n'.join(problemes))


def test_les_fichiers_de_l_editeur_visuel_sont_versionnes():
    """La régression nommée, pour que l'échec soit lisible sans enquête."""
    suivis = _fichiers_suivis()
    if suivis is None:
        pytest.skip('git indisponible : ce test mesure le contenu du depot.')

    attendus = [
        'static/site_builder/css/builder.css',
        'static/site_builder/css/public_builder.css',
        'static/site_builder/js/builder.js',
        'static/site_builder/js/drag_drop.js',
        'static/site_builder/js/module_settings.js',
    ]
    absents = [chemin for chemin in attendus if chemin not in suivis]

    assert not absents, (
        'Les gabarits de l editeur visuel sont versionnes sans ces '
        'fichiers : ' + ', '.join(absents))
