# -*- coding: utf-8 -*-
"""Deux contrôles finaux faisaient échouer des mises à jour réussies.

RELEVÉ SUR L'APPLIANCE le 09/11/2026. La mise à jour avait tout fait :
code récupéré, schéma à jour, 1307 fichiers statiques collectés, nginx en
302, backend en 302, sonde de santé en 200. Et elle s'est terminée en
échec, sur deux « défauts bloquants » du vérificateur.

1. **« git refuse de lire /opt/orion/backend »** — le contrôle vérifiait
   que ROOT peut lire le dépôt. Le provisioning clone en root puis donne le
   dossier à `orion`, si bien que git refuse à root pour « dubious
   ownership ». Mais **rien ne lit ce dépôt en root** :
   `update_orion.sh` tire avec « sudo -u orion git pull », et
   `run_system_update` tourne sous orion. Le contrôle testait donc une
   chose dont rien ne dépend, la déclarait bloquante, et proposait en
   remède un `safe.directory '*'` qui désactive globalement une protection
   de git.

2. **« clé ORION_NODE_ID vide ou absente »** — celui-là avait raison. La
   clé est arrivée dans le produit APRÈS l'installation de cette machine,
   et le provisioning ne tourne qu'une fois : elle n'y est donc jamais
   arrivée. Sans elle, la protection anti-divergence de la haute
   disponibilité compare une valeur vide au verrou de grappe.

La leçon est la même que pour les règles sudo, les unités systemd et
l'assistant disque : **ce qui n'est posé qu'une fois au provisioning doit
être rattrapé à chaque mise à jour**, sinon une machine déjà installée ne
le reçoit jamais.
"""

import os
import shutil
import subprocess

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_MAJ = os.path.join(RACINE, 'deployment', 'proxmox-appliance',
                          'scripts', 'update_orion.sh')
VERIFICATEUR = os.path.join(RACINE, 'deployment', 'proxmox-appliance',
                            'scripts', 'orion-verifier.sh')

BASH = shutil.which('bash')
besoin_de_bash = pytest.mark.skipif(
    BASH is None, reason='bash absent de cette machine')


def _lire(chemin):
    with open(chemin, encoding='utf-8') as fichier:
        return fichier.read()


def _extraire_fonction(texte, nom):
    debut = texte.index('%s() {' % nom)
    fin = texte.index(chr(10) + '}' + chr(10), debut) + 3
    return texte[debut:fin]


# ─── Le rattrapage des clés de .env ───────────────────────────────────────

def test_la_mise_a_jour_rattrape_les_cles_manquantes():
    """Le provisioning ne tourne qu'une fois ; la mise à jour, à chaque fois."""
    texte = _lire(SCRIPT_MAJ)

    assert 'completer_env()' in texte
    assert 'completer_env ORION_NODE_ID' in texte, (
        "la cle qui a fait echouer la mise a jour n-est pas rattrapee")


def test_la_valeur_par_defaut_est_celle_du_provisioning():
    """Une machine mise à jour et une machine neuve doivent se ressembler.

    Toute autre valeur ferait diverger les deux, et le jour où l'on
    comparerait leurs comportements personne ne comprendrait pourquoi.
    """
    provisioning = _lire(os.path.join(
        RACINE, 'deployment', 'proxmox-appliance', 'provisioning',
        '02-deploy-orion.sh'))
    maj = _lire(SCRIPT_MAJ)

    assert 'orion-primary' in provisioning
    assert 'completer_env ORION_NODE_ID orion-primary' in maj


@besoin_de_bash
def test_completer_env_n_ecrit_qu_une_fois(tmp_path):
    """Appelée deux fois, elle ne doit pas écrire deux lignes.

    Elle tourne à CHAQUE mise à jour : sans cette garantie, le .env
    accumulerait une ligne par passage, et la dernière gagnerait
    silencieusement.
    """
    env = tmp_path / '.env'
    env.write_text('SECRET_KEY=abc\n', encoding='utf-8')

    harnais = chr(10).join([
        'set -euo pipefail',
        'ENV_FILE=%s' % env.as_posix(),
        _extraire_fonction(_lire(SCRIPT_MAJ), 'completer_env'),
        'completer_env ORION_NODE_ID orion-primary',
        'completer_env ORION_NODE_ID orion-primary',
        'completer_env ORION_NODE_ID orion-primary',
    ])
    essai = tmp_path / 'essai.sh'
    essai.write_text(harnais, encoding='utf-8')
    subprocess.run([BASH, str(essai)], capture_output=True, text=True,
                   encoding='utf-8', errors='replace')

    contenu = env.read_text(encoding='utf-8')
    assert contenu.count('ORION_NODE_ID=') == 1, contenu
    assert 'SECRET_KEY=abc' in contenu, 'le fichier existant a ete abime'


@besoin_de_bash
def test_completer_env_ne_touche_pas_une_cle_deja_presente(tmp_path):
    """Une valeur choisie par l'exploitant ne doit jamais être écrasée.

    Sur une grappe, chaque serveur porte un identifiant DISTINCT : le
    remplacer par la valeur par défaut remettrait tous les nœuds au même
    nom, c'est-à-dire exactement le défaut que cette clé corrige.
    """
    env = tmp_path / '.env'
    env.write_text('ORION_NODE_ID=serveur2\n', encoding='utf-8')

    harnais = chr(10).join([
        'set -euo pipefail',
        'ENV_FILE=%s' % env.as_posix(),
        _extraire_fonction(_lire(SCRIPT_MAJ), 'completer_env'),
        'completer_env ORION_NODE_ID orion-primary',
    ])
    essai = tmp_path / 'essai.sh'
    essai.write_text(harnais, encoding='utf-8')
    subprocess.run([BASH, str(essai)], capture_output=True, text=True,
                   encoding='utf-8', errors='replace')

    assert env.read_text(encoding='utf-8').strip() == 'ORION_NODE_ID=serveur2'


@besoin_de_bash
def test_un_env_non_inscriptible_n_interrompt_pas_la_mise_a_jour(tmp_path):
    """Compléter le .env est un confort, pas une condition."""
    harnais = chr(10).join([
        'set -euo pipefail',
        'ENV_FILE=%s/inexistant/.env' % tmp_path.as_posix(),
        _extraire_fonction(_lire(SCRIPT_MAJ), 'completer_env'),
        'completer_env ORION_NODE_ID orion-primary',
        'echo SUITE',
    ])
    essai = tmp_path / 'essai.sh'
    essai.write_text(harnais, encoding='utf-8')
    acheve = subprocess.run([BASH, str(essai)], capture_output=True,
                            text=True, encoding='utf-8', errors='replace')

    assert 'SUITE' in (acheve.stdout or ''), (acheve.stdout, acheve.stderr)


# ─── Le contrôle du dépôt teste enfin la bonne chose ──────────────────────

def test_le_depot_est_lu_par_le_compte_qui_s_en_sert():
    """`orion`, et non root : c'est lui qui tire les mises à jour."""
    texte = _lire(VERIFICATEUR)

    assert 'runuser -u orion -- git -C' in texte, (
        'le controle lit encore le depot en root, et echouera sur une '
        'installation saine')


def test_le_verificateur_ne_propose_plus_de_desactiver_une_garde_de_git():
    """« safe.directory '*' » désactive globalement une protection de git.

    Le proposer en remède d'un contrôle qui n'avait pas lieu d'être
    revenait à faire désarmer une sécurité pour taire une fausse alerte.
    """
    # Sur les lignes EFFECTIVES seulement : le commentaire qui explique
    # pourquoi ce remède a été abandonné contient forcément son nom. Une
    # première version de ce test échouait dessus — c'est le même piège
    # qu'un test écrit la veille, qui cherchait « [Install] » dans le texte
    # brut d'une unité systemd et tombait sur le commentaire expliquant son
    # absence.
    effectives = [ligne for ligne in _lire(VERIFICATEUR).splitlines()
                  if ligne.strip() and not ligne.strip().startswith('#')]
    code = chr(10).join(effectives)

    assert "safe.directory '*'" not in code
    assert '--add safe.directory' not in code


def test_le_remede_propose_est_celui_qui_repare_vraiment():
    texte = _lire(VERIFICATEUR)

    assert 'chown -R orion:orion' in texte, (
        'si orion ne peut pas lire le depot, c-est le proprietaire qu-il '
        'faut corriger')


def test_le_verificateur_reste_syntaxiquement_valide():
    if BASH is None:
        pytest.skip('bash absent')
    acheve = subprocess.run([BASH, '-n', VERIFICATEUR], capture_output=True,
                            text=True, encoding='utf-8', errors='replace')
    assert acheve.returncode == 0, acheve.stderr
