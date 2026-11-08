# -*- coding: utf-8 -*-
"""La mise à jour ne doit JAMAIS annoncer un succès qu'elle n'a pas obtenu.

CE QUI EST ARRIVÉ SUR L'APPLIANCE le 08/11/2026. Relevé textuellement dans
le journal, dans cet ordre :

    django.db.utils.OperationalError: (1060, "Duplicate column name
    'archive_ref'")
      code récupéré, schéma migré, statiques collectés.

Le script annonçait un schéma migré trois lignes sous le traceback de
`migrate`, et continuait. La cause n'est pas une étourderie d'écriture :
`maj_directe` est appelée à GAUCHE d'un `||`, et bash suspend alors
`set -e` pour TOUT le corps de la fonction. La commande en échec ne
l'interrompait donc pas, et la fonction renvoyait le code de son DERNIER
`echo`, soit 0.

Conséquence la plus grave, et celle qui explique la série de pannes : code
de sortie 0, donc `maj-etat.json` notait « terminee » et l'unité systemd se
déclarait réussie — sur un ERP dont le schéma ne correspondait pas au code.
Une base à moitié migrée a ainsi survécu à plusieurs mises à jour
« réussies », sans que rien ne le signale jamais.

Les tests ci-dessous EXÉCUTENT la fonction en bash, avec `migrate` qui
échoue, plutôt que de relire son texte : c'est le comportement de bash qui
était en cause, pas le texte.
"""

import os
import re
import shutil
import subprocess

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(RACINE, 'deployment', 'proxmox-appliance',
                      'scripts', 'update_orion.sh')

BASH = shutil.which('bash')
besoin_de_bash = pytest.mark.skipif(
    BASH is None, reason='bash absent de cette machine')


@pytest.fixture(scope='module')
def texte():
    with open(SCRIPT, encoding='utf-8') as fichier:
        return fichier.read()


def _extraire_fonction(texte, nom):
    """Isole une fonction bash, de sa déclaration à son `}` en colonne 0."""
    debut = texte.index('%s() {' % nom)
    fin = texte.index('\n}\n', debut) + len('\n}\n')
    return texte[debut:fin]


def _jouer(corps, code_de_migrate, tmp_path):
    """Exécute `maj_directe` en bash, avec un faux `sudo`.

    Aucune commande réelle n'est lancée : `sudo` est remplacé par une
    fonction qui répond ce que le scénario demande. Ce qu'on mesure est
    donc uniquement la façon dont la fonction enchaîne ses étapes.
    """
    harnais = '\n'.join([
        'set -euo pipefail',
        'ORION_HOME=%s' % tmp_path.as_posix(),
        'VENV_PY=python', 'MANAGE=manage.py',
        'FICHIER_ETAT=%s/maj-etat.json' % tmp_path.as_posix(),
        'sudo() {',
        '  case " $* " in',
        '    *" migrate "*) return %d ;;' % code_de_migrate,
        '    *) return 0 ;;',
        '  esac',
        '}',
        corps,
        'if maj_directe; then',
        '  echo "RESULTAT=succes"',
        'else',
        '  echo "RESULTAT=echec"',
        'fi',
    ])
    fichier = tmp_path / 'essai.sh'
    fichier.write_text(harnais, encoding='utf-8')
    acheve = subprocess.run([BASH, str(fichier)], capture_output=True,
                            text=True, encoding='utf-8', errors='replace')
    return (acheve.stdout or '') + (acheve.stderr or '')


# ─── Le défaut lui-même, mesuré en bash ───────────────────────────────────

@besoin_de_bash
def test_une_migration_en_echec_ne_fait_pas_annoncer_un_succes(texte,
                                                               tmp_path):
    """Le cœur du correctif, et le texte exact relevé en production."""
    sortie = _jouer(_extraire_fonction(texte, 'maj_directe'), 1, tmp_path)
    assert 'schéma migré' not in sortie, (
        'la fonction annonce encore un schema migre apres un migrate en '
        'echec :\n%s' % sortie)
    assert 'ERREUR: migrate a echoue' in sortie


@besoin_de_bash
def test_une_migration_en_echec_fait_renvoyer_un_code_non_nul(texte,
                                                              tmp_path):
    """C'est ce code qui devient celui de l'unité systemd.

    À 0, `maj-etat.json` note « terminee » et plus rien ne signale que
    l'ERP tourne sur un schéma qui ne correspond pas à son code.
    """
    sortie = _jouer(_extraire_fonction(texte, 'maj_directe'), 1, tmp_path)
    assert 'RESULTAT=echec' in sortie, sortie


@besoin_de_bash
def test_une_migration_en_echec_n_enchaine_pas_sur_collectstatic(texte,
                                                                 tmp_path):
    """Rien ne doit suivre une migration en échec dans cette fonction."""
    corps = _extraire_fonction(texte, 'maj_directe')
    sortie = _jouer(corps, 1, tmp_path)
    assert 'collectstatic a echoue' not in sortie
    assert 'statiques collectés' not in sortie


@besoin_de_bash
def test_tout_se_passe_bien_le_succes_est_bien_annonce(texte, tmp_path):
    """Le correctif ne doit pas transformer un succès en échec."""
    sortie = _jouer(_extraire_fonction(texte, 'maj_directe'), 0, tmp_path)
    assert 'code récupéré, schéma migré, statiques collectés.' in sortie
    assert 'RESULTAT=succes' in sortie, sortie


@besoin_de_bash
def test_le_script_reste_syntaxiquement_valide():
    acheve = subprocess.run([BASH, '-n', SCRIPT], capture_output=True,
                            text=True, encoding='utf-8', errors='replace')
    assert acheve.returncode == 0, acheve.stderr


# ─── Le verdict final, en un seul endroit ─────────────────────────────────

def test_chaque_etape_de_maj_directe_est_verifiee_separement(texte):
    """Aucune commande nue : `set -e` ne protège pas ici, voir l'en-tête."""
    corps = _extraire_fonction(texte, 'maj_directe')
    nues = [ligne.strip() for ligne in corps.splitlines()
            if re.match(r'^\s+sudo -u orion', ligne)
            and 'if ! ' not in ligne]
    assert nues == [], 'commandes non verifiees dans maj_directe : %s' % nues


def test_un_echec_critique_est_retenu_et_decide_du_code_de_sortie(texte):
    assert 'ECHEC_CRITIQUE=0' in texte, (
        'le drapeau doit etre initialise avant le bloc de modes')
    assert texte.count('ECHEC_CRITIQUE=1') >= 3, (
        'les trois modes (direct, django, defaut) doivent chacun pouvoir '
        'signaler un echec')
    assert 'if [ "$ECHEC_CRITIQUE" -ne 0 ]; then' in texte


def test_le_drapeau_est_initialise_avant_le_bloc_de_modes(texte):
    """Sous `set -u`, un drapeau non initialisé ferait planter la fin."""
    assert texte.index('ECHEC_CRITIQUE=0') < texte.index('case "$MODE" in')
    assert (texte.index('case "$MODE" in')
            < texte.index('if [ "$ECHEC_CRITIQUE" -ne 0 ]; then'))


def test_les_trois_modes_signalent_leur_echec(texte):
    """Le mode par défaut aussi : son repli peut échouer à son tour."""
    debut = texte.index('case "$MODE" in')
    fin = texte.index('\nesac', debut)
    bloc = texte[debut:fin]
    assert bloc.count('ECHEC_CRITIQUE=1') == 3, (
        'un mode ne signale pas son echec :\n%s' % bloc)


def test_le_succes_n_est_annonce_qu_apres_le_controle(texte):
    """Il l'était depuis trois branches, dont une qui mentait."""
    controle = texte.index('if [ "$ECHEC_CRITIQUE" -ne 0 ]; then')
    for annonce in ('Mise a jour terminee — installation verifiee.',
                    'Mise à jour terminée.'):
        assert texte.index(annonce) > controle, (
            'annonce de succes avant le controle : %s' % annonce)


def test_l_echec_critique_laisse_quand_meme_passer_les_correctifs(texte):
    """Ne pas s'arrêter net : scripts et unités sont la voie du correctif.

    Si le script s'interrompait sur l'échec de `migrate`, il ne
    rafraîchirait ni /opt/orion/scripts ni /etc/systemd/system — donc le
    correctif n'arriverait jamais, et le lancement suivant échouerait de
    la même façon. Le drapeau est posé, le travail continue, le verdict
    tombe à la fin.
    """
    pose = texte.index('ECHEC_CRITIQUE=1')
    assert pose < texte.index('rafraichir_scripts ||')
    assert pose < texte.index('rafraichir_unites_systemd ||')


# ─── L'ordre des étapes ───────────────────────────────────────────────────

def test_les_catalogues_viennent_apres_les_unites_systemd(texte):
    """« Unit orion-update.service not found », mise à jour en cours.

    L'import des relevés de catalogues interroge des sites de fabricants :
    il dure des minutes et ne rapporte que des prix indicatifs. Placé
    avant le rafraîchissement des unités, il retardait la pose de
    orion-update.service — constaté sur l'appliance, où `systemctl start`
    répondait encore « Unit not found » plusieurs minutes après le
    lancement. L'infrastructure d'abord.
    """
    appel = re.search(r'^importer_catalogues_fabricants$', texte,
                      re.MULTILINE)
    assert appel, "l'import des catalogues n'est plus appele"
    assert appel.start() > texte.index('rafraichir_unites_systemd ||')
    assert appel.start() > texte.index('rafraichir_scripts ||')


def test_les_catalogues_restent_hors_de_maj_directe(texte):
    """Sinon l'étape ne tournerait jamais en usage normal.

    Le mode par défaut passe par le mécanisme applicatif et ne touche
    `maj_directe` qu'en cas d'échec.
    """
    corps = _extraire_fonction(texte, 'maj_directe')
    assert 'importer_catalogues_fabricants' not in corps


def test_l_echec_des_catalogues_n_est_pas_critique(texte):
    """Un catalogue non importé est un désagrément, pas une panne."""
    corps = _extraire_fonction(texte, 'importer_catalogues_fabricants')
    assert 'ECHEC_CRITIQUE' not in corps


# ─── L'état écrit sur le disque dit la vérité ─────────────────────────────

def _jouer_l_etat(texte, final, tmp_path):
    """Exécute les fonctions d'état en bash et renvoie le JSON écrit.

    Le fichier d'état est la SEULE source lisible quand la base est en
    panne. Ce qu'il contient se vérifie donc en l'écrivant pour de vrai.
    """
    import json

    etat = tmp_path / 'maj-etat.json'
    harnais = '\n'.join([
        'set -euo pipefail',
        'MODE=direct',
        'FICHIER_ETAT=%s' % etat.as_posix(),
        'ETAT_FIGE=0',
        _extraire_fonction(texte, 'noter_etat'),
        _extraire_fonction(texte, 'figer_etat'),
        _extraire_fonction(texte, 'sur_sortie'),
        _extraire_fonction(texte, 'sur_signal'),
        'trap sur_sortie EXIT',
        "trap 'sur_signal TERM 143' TERM",
        final,
    ])
    fichier = tmp_path / 'essai_etat.sh'
    fichier.write_text(harnais, encoding='utf-8')
    subprocess.run([BASH, str(fichier)], capture_output=True, text=True,
                   encoding='utf-8', errors='replace')
    return json.loads(etat.read_text(encoding='utf-8'))


@besoin_de_bash
def test_un_refus_reste_un_refus_et_non_un_echec(texte, tmp_path):
    """Le piège sur EXIT écrasait « refusee » par « echouee ».

    Constaté sur l'appliance le 08/11/2026, les deux sorties se
    contredisant :

        journal  : Mise a jour NON DEMARREE : rien n'a ete modifie.
        maj-etat : {"etape": "echouee", "code": 1}

    La distinction n'est pas cosmétique : « refusee » signifie que RIEN
    n'a été touché, donc qu'il n'y a rien à défaire. C'est l'information
    dont dépend la décision de faire ou non un rollback, et c'est
    précisément celle que le piège détruisait.
    """
    donnees = _jouer_l_etat(texte, "figer_etat 'refusee' 1\nexit 1", tmp_path)
    assert donnees['etape'] == 'refusee', donnees


@besoin_de_bash
def test_un_vrai_echec_est_bien_note_echoue(texte, tmp_path):
    """Le correctif ne doit pas rendre le piège muet."""
    donnees = _jouer_l_etat(texte, "noter_etat 'migrations'\nexit 3",
                            tmp_path)
    assert donnees['etape'] == 'echouee'
    assert donnees['code'] == 3


@besoin_de_bash
def test_une_mise_a_jour_qui_passe_est_notee_terminee(texte, tmp_path):
    donnees = _jouer_l_etat(texte, "noter_etat 'frontends'\nexit 0",
                            tmp_path)
    assert donnees['etape'] == 'terminee'
    assert donnees['code'] == 0


@besoin_de_bash
def test_une_mise_a_jour_tuee_par_systemd_n_est_pas_notee_reussie(texte,
                                                                  tmp_path):
    """LE défaut le plus grave trouvé dans ce mécanisme.

    Mesuré le 08/11/2026 : sur SIGTERM, bash exécute bien le piège EXIT,
    mais `$?` y vaut ZÉRO — c'est le code de la dernière commande achevée,
    pas celui du signal. Le script notait donc « terminee », code 0, pour
    une mise à jour que systemd venait de tuer à son TimeoutStartSec.

    Au cœur du mécanisme censé dire la vérité quand la base est en panne,
    et dans la seule source que l'exploitant peut alors consulter.
    """
    final = chr(10).join(["noter_etat 'migrations'", 'kill -TERM $$'])
    donnees = _jouer_l_etat(texte, final, tmp_path)
    assert donnees['etape'] != 'terminee', (
        'une mise a jour tuee est annoncee reussie : %s' % donnees)
    assert donnees['etape'] == 'interrompue', donnees
    assert donnees['code'] == 143


def test_les_trois_signaux_d_arret_sont_interceptes(texte):
    """TERM vient de systemd, INT d'un Ctrl-C, HUP d'une session coupée."""
    for signal in ('TERM', 'INT', 'HUP'):
        assert "trap 'sur_signal %s " % signal in texte, (
            'signal non intercepte : %s' % signal)


def test_la_limite_de_sigkill_est_documentee(texte):
    """SIGKILL ne peut pas être intercepté, et il faut le dire.

    Le tueur de mémoire du noyau frappe en SIGKILL. Prétendre que l'état
    est toujours fiable serait faux, et c'est le genre de promesse sur
    laquelle on s'appuie au pire moment.
    """
    assert 'SIGKILL' in texte
    assert 'Limite assumee' in texte or 'limite assumee' in texte
