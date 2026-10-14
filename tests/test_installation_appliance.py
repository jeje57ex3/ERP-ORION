"""Invariants de la chaîne d'installation de l'appliance Proxmox.

Ces tests ne vérifient pas une API : ils gardent les propriétés dont l'absence
a produit, séparément, cinq pannes de provisioning sans symptôme commun —
502 Bad Gateway, erreur 500 sur toutes les pages, exit 127 muet,
« command not found » sur un script présent, et un assistant IA en 404.

Le point commun de ces cinq pannes : le symptôme apparaissait plusieurs étapes
après sa cause et ne la désignait jamais. D'où deux familles de contrôles ici —
ceux qui empêchent la cause (lecture du .env, droits, ordre des étapes) et
celui qui garantit qu'une panne sera constatée là où elle se produit
(l'étape de vérification).
"""

import os
import re
import shutil
import subprocess

import pytest
from django.conf import settings

RACINE = os.path.join(settings.BASE_DIR, 'deployment', 'proxmox-appliance')
PROVISIONING = os.path.join(RACINE, 'provisioning')
SCRIPTS = os.path.join(RACINE, 'scripts')

ETAPES = [
    '01-system-packages.sh',
    '02-deploy-orion.sh',
    '03-systemd-units.sh',
    '04-nginx-config.sh',
    '05-cloudflared-config.sh',
    '06-ufw-fail2ban.sh',
    '07-backup-cron.sh',
    '08-verification.sh',
]


def lire(*morceaux):
    with open(os.path.join(*morceaux), encoding='utf-8') as fichier:
        return fichier.read()


# ── La bibliothèque commune, exécutée pour de vrai ──────────────────────────

def test_la_suite_bash_de_la_bibliotheque_passe():
    """Délègue à la suite bash : seul bash peut prouver un comportement bash.

    Elle rejoue les pannes réelles — sourçage fatal sur une valeur à espaces,
    clé absente qui tuait un ExecStartPre, sed cassé par un « # » dans une
    valeur.
    """
    bash = shutil.which('bash')
    if not bash:
        pytest.skip('bash indisponible sur cette machine')

    suite = os.path.join(RACINE, 'tests', 'test_commun.sh')
    resultat = subprocess.run(
        [bash, suite], capture_output=True, text=True, timeout=120,
    )
    assert resultat.returncode == 0, resultat.stdout + resultat.stderr
    assert 'TOUT PASSE' in resultat.stdout


# ── Plus aucun .env n'est exécuté ───────────────────────────────────────────

def test_aucun_script_ne_source_le_env():
    """`set -a; . .env` exécute le fichier.

    Une seule valeur à espaces non citée
    (ORION_UPDATE_CELERY_RESTART_COMMAND=sudo -n …) a tué tout le
    provisionnement d'une VM neuve en exit 127, sur un « -n: command not
    found » qui ne nommait ni la clé ni le fichier.
    """
    # Seules les lignes de COMMANDE comptent : ces scripts expliquent en
    # commentaire pourquoi le sourçage a été abandonné, et une recherche
    # naïve matcherait sa propre explication.
    fautifs = []
    for dossier in (PROVISIONING, SCRIPTS):
        for nom in sorted(os.listdir(dossier)):
            if not nom.endswith('.sh'):
                continue
            for numero, ligne in enumerate(lire(dossier, nom).splitlines(), 1):
                nue = ligne.strip()
                if not nue or nue.startswith('#'):
                    continue
                for motif in (r'set -a\s*;', r'(^|;|&&|\|\|)\s*\.\s+"?\$\{?ENV_FILE'):
                    if re.search(motif, nue):
                        fautifs.append('%s:%d  %s' % (nom, numero, nue))
    assert fautifs == [], 'sourçage du .env encore présent : %s' % fautifs


def test_chaque_etape_charge_la_bibliotheque_commune():
    """Sans elle, $HOME n'est pas garanti et le .env redevient exécuté."""
    sans = [
        etape for etape in ETAPES
        if 'lib/commun.sh' not in lire(PROVISIONING, etape)
    ]
    assert sans == [], 'étapes sans commun.sh : %s' % sans


def test_toutes_les_valeurs_du_env_genere_sont_citees():
    """Contrôle statique du bloc qui écrit backend/.env.

    La règle est uniforme — tout est cité, même ce qui n'en a pas besoin —
    parce qu'une exception « seulement là où c'est nécessaire » se perd au
    premier ajout de clé, et que la panne qui s'ensuit ne nomme pas la clé.
    """
    contenu = lire(PROVISIONING, '02-deploy-orion.sh')
    debut = contenu.index('cat > "$ENV_FILE" <<EOF')
    fin = contenu.index('\nEOF\n', debut)
    bloc = contenu[debut:fin]

    nues = []
    for ligne in bloc.split('\n'):
        ligne = ligne.strip()
        if not ligne or ligne.startswith('#') or '=' not in ligne:
            continue
        if ligne.startswith('cat >'):
            continue
        cle, _, valeur = ligne.partition('=')
        if not re.fullmatch(r'[A-Z0-9_]+', cle):
            continue
        if not (valeur.startswith('"') and valeur.endswith('"')):
            nues.append(ligne)
    assert nues == [], 'valeurs non citées dans le .env généré : %s' % nues


def test_le_env_genere_est_valide_a_l_ecriture():
    """Un .env malformé ne se voyait qu'en aval, et jamais sous son vrai nom.

    L'étape 02 le contrôle désormais par les deux lecteurs réels — charger_env
    et python-decouple — à l'instant où elle l'écrit.
    """
    contenu = lire(PROVISIONING, '02-deploy-orion.sh')
    assert 'charger_env "$ENV_FILE"' in contenu
    assert 'decouple' in contenu
    assert 'CLES_MANQUANTES' in contenu


# ── Les quatre causes récurrentes ───────────────────────────────────────────

def test_home_est_garanti_par_la_bibliotheque():
    """« qm guest exec » — seul accès à une appliance sans clé SSH — ne
    définit aucun $HOME. git refuse sa configuration, la CLI Ollama panique
    (« panic: $HOME is not defined »), npm écrit dans /.npm."""
    assert 'export HOME="${HOME:-/root}"' in lire(
        PROVISIONING, 'lib', 'commun.sh')


def test_git_est_autorise_sur_les_depots_d_orion():
    """Le provisioning clone en root puis chown vers orion : sans
    safe.directory, toute commande git lancée par root est refusée pour
    « dubious ownership », y compris les mises à jour depuis l'interface."""
    commun = lire(PROVISIONING, 'lib', 'commun.sh')
    assert 'autoriser_git_systeme' in commun
    assert 'safe.directory' in commun
    assert 'autoriser_git_systeme' in lire(PROVISIONING, '02-deploy-orion.sh')


def test_les_bits_d_execution_sont_poses_avant_toute_etape():
    """git conserve le mode : un script committé en 100644 échoue en
    « command not found » — message qui laisse croire à un script absent.
    Constaté sur orion-mesh.sh, dont tous les boutons renvoyaient cette
    erreur."""
    orchestrateur = lire(PROVISIONING, '00-provisionner.sh')
    assert 'chmod +x' in orchestrateur
    position_chmod = orchestrateur.index('chmod +x')
    position_boucle = orchestrateur.index('for etape in')
    assert position_chmod < position_boucle, (
        'le chmod doit précéder l\'exécution des étapes'
    )


def test_les_scripts_du_depot_sont_executables():
    """Même garde, côté dépôt : le mode est versionné."""
    resultat = subprocess.run(
        ['git', 'ls-files', '-s',
         'deployment/proxmox-appliance/provisioning',
         'deployment/proxmox-appliance/scripts'],
        capture_output=True, text=True, cwd=settings.BASE_DIR,
    )
    if resultat.returncode != 0:
        pytest.skip('git indisponible')

    non_executables = []
    for ligne in resultat.stdout.splitlines():
        mode, _, reste = ligne.partition(' ')
        chemin = reste.split('\t')[-1]
        if chemin.endswith('.sh') and mode != '100755':
            non_executables.append('%s (%s)' % (chemin, mode))
    assert non_executables == [], (
        'scripts non exécutables dans git : %s' % non_executables
    )


# ── L'ordre des étapes est du code, non un commentaire ──────────────────────

def test_l_orchestrateur_execute_07_avant_03():
    """07 installe wait_for_port.sh et refresh_allowed_hosts.sh, exigés par les
    ExecStartPre d'orion-backend et d'orion-frontend que 03 démarre. Dans
    l'autre ordre : 203/EXEC, services morts, nginx 502 — sans que rien ne
    mentionne un script manquant."""
    contenu = lire(PROVISIONING, '00-provisionner.sh')
    debut = contenu.index('ETAPES=(')
    liste = contenu[debut:contenu.index(')', debut)]
    assert liste.index('07-backup-cron') < liste.index('03-systemd-units')


def test_la_verification_est_la_derniere_etape():
    contenu = lire(PROVISIONING, '00-provisionner.sh')
    debut = contenu.index('ETAPES=(')
    liste = [
        l.strip().strip("'")
        for l in contenu[debut:contenu.index(')', debut)].split('\n')
        if l.strip().startswith("'")
    ]
    assert liste[-1] == '08-verification.sh'


def test_une_etape_en_echec_ne_prive_pas_des_suivantes():
    """Un provisioning qui s'arrête à la première anomalie laisse une
    appliance à moitié installée dont plus rien ne dit ce qui manque — et
    surtout, il saute la vérification finale."""
    contenu = lire(PROVISIONING, '00-provisionner.sh')
    assert 'set -uo pipefail' in contenu
    assert 'set -euo pipefail' not in contenu, (
        "l'orchestrateur doit survivre à l'échec d'une étape"
    )
    assert 'on poursuit' in contenu


def test_cloud_init_delegue_tout_a_l_orchestrateur():
    """La liste des étapes vivait dans le gabarit YAML, et son ordre réel
    n'était qu'un commentaire."""
    contenu = lire(RACINE, 'cloud-init', 'user-data.yaml.tmpl')
    debut = contenu.index('runcmd:')
    runcmd = contenu[debut:contenu.index('final_message:')]
    assert '00-provisionner.sh' in runcmd
    for etape in ETAPES:
        assert etape not in runcmd, (
            '%s est encore appelée directement par cloud-init' % etape
        )
    # Hors commentaires : l'en-tête du bloc explique précisément ce qui a été
    # supprimé, et le mentionner ne doit pas faire échouer le test.
    commandes = '\n'.join(
        l for l in runcmd.splitlines() if not l.strip().startswith('#')
    )
    assert 'set -a' not in commandes, 'cloud-init exécute encore les .env'


def test_le_payload_est_controle_a_la_construction():
    """Une image construite sans ces fichiers produit une VM qui démarre,
    exécute une ligne de cloud-init, et ne provisionne rien — en silence."""
    contenu = lire(RACINE, 'lib', '20-build-cloud-init-seed.sh')
    for requis in ('provisioning/00-provisionner.sh',
                   'provisioning/lib/commun.sh',
                   'scripts/orion-verifier.sh'):
        assert requis in contenu


# ── La vérification finale : ce qu'un navigateur constate ───────────────────

def test_le_verificateur_controle_ce_qui_a_reellement_casse():
    """Chaque contrôle correspond à une panne survenue en production, et
    vérifie ce qu'un utilisateur constate — une page qui répond — plutôt que ce
    que le script croit avoir fait."""
    contenu = lire(SCRIPTS, 'orion-verifier.sh')

    # 500 sur toutes les pages : staticfiles.json absent (stockage à manifeste)
    assert 'staticfiles.json' in contenu
    # 502 : services morts faute de leurs ExecStartPre
    assert 'wait_for_port.sh' in contenu
    assert 'refresh_allowed_hosts.sh' in contenu
    # « Table orion_core.core_company doesn't exist » : migrations non passées
    assert 'migrate --check' in contenu
    # exit 127 : valeur à espaces non citée
    assert 'non citée' in contenu or 'non cit' in contenu
    # 404 de l'assistant : daemon debout mais modèle absent
    assert 'api/tags' in contenu
    # « dubious ownership » sur les mises à jour
    assert 'safe.directory' in contenu
    # et enfin le seul contrôle qui aurait attrapé 502 ET 500
    assert 'http://127.0.0.1/' in contenu
    assert 'ha/public-health' in contenu


def test_le_verificateur_distingue_bloquant_et_optionnel():
    """Un composant optionnel absent — pas de tunnel, pas d'IA locale — ne doit
    pas faire échouer la vérification, sinon personne ne la lira."""
    contenu = lire(SCRIPTS, 'orion-verifier.sh')
    assert 'CRITIQUES' in contenu and 'AVERTISSEMENTS' in contenu
    assert 'exit 0' in contenu and 'exit 1' in contenu


def test_l_etape_03_verifie_les_statiques():
    """La cause était un collectstatic sauté deux étapes plus tôt ; elle est
    désormais constatée là où elle se produit."""
    contenu = lire(PROVISIONING, '03-systemd-units.sh')
    assert 'staticfiles.json' in contenu
    assert 'retenir_defaut' in contenu
    assert 'verdict_etape' in contenu


def test_la_mise_a_jour_se_verifie_elle_meme():
    """Une mise à jour peut laisser l'ERP en 500 (statiques non recollectés) ou
    en 502 (service qui ne redémarre pas) : les deux se sont produits, et le
    script s'était déclaré terminé."""
    contenu = lire(SCRIPTS, 'update_orion.sh')
    assert 'orion-verifier.sh' in contenu
    assert 'commun.sh' in contenu


def test_le_message_d_accueil_dit_la_verite():
    """Annoncer « prête » sans l'avoir vérifié envoie l'exploitant chercher la
    panne dans son navigateur, à plusieurs étapes de sa cause."""
    orchestrateur = lire(PROVISIONING, '00-provisionner.sh')
    assert '/etc/motd' in orchestrateur
    assert 'INCOMPLET' in orchestrateur

    gabarit = lire(RACINE, 'cloud-init', 'user-data.yaml.tmpl')
    final = gabarit[gabarit.index('final_message:'):]
    assert 'prête' not in final, (
        'cloud-init ne doit plus affirmer que la machine est prête'
    )


# ── Le .env tel que l'étape 02 l'écrit, lu par Django ───────────────────────

def test_les_deux_lecteurs_du_env_voient_la_meme_chose(tmp_path):
    """Propriété qui compte : charger_env (shell) et python-decouple (Django)
    doivent rendre la même chaîne. Un désaccord ici signifierait qu'un mot de
    passe de base ou une clé Fernet est utilisé déformé — panne silencieuse."""
    from decouple import Config, RepositoryEnv

    fichier = tmp_path / '.env'
    fichier.write_text(
        'SECRET_KEY="abc-def_123"\n'
        'ALLOWED_HOSTS="localhost,127.0.0.1,192.168.1.109"\n'
        'ORION_UPDATE_CELERY_RESTART_COMMAND="sudo -n systemctl restart orion-celery"\n'
        'VIDE=""\n'
        'ORION_SECRET_ENCRYPTION_KEY="abc=="\n',
        encoding='utf-8',
    )

    config = Config(RepositoryEnv(str(fichier)))
    attendu = {
        'SECRET_KEY': 'abc-def_123',
        'ALLOWED_HOSTS': 'localhost,127.0.0.1,192.168.1.109',
        'ORION_UPDATE_CELERY_RESTART_COMMAND':
            'sudo -n systemctl restart orion-celery',
        'VIDE': '',
        'ORION_SECRET_ENCRYPTION_KEY': 'abc==',
    }
    for cle, valeur in attendu.items():
        assert config.get(cle, default='') == valeur, cle

    bash = shutil.which('bash')
    if not bash:
        pytest.skip('bash indisponible')

    commun = os.path.join(PROVISIONING, 'lib', 'commun.sh').replace('\\', '/')
    chemin = str(fichier).replace('\\', '/')
    script = (
        '. "%s"; charger_env "%s"; '
        'printf "%%s\\n" "$SECRET_KEY" "$ALLOWED_HOSTS" '
        '"$ORION_UPDATE_CELERY_RESTART_COMMAND" "$VIDE" '
        '"$ORION_SECRET_ENCRYPTION_KEY"' % (commun, chemin)
    )
    resultat = subprocess.run(
        [bash, '-c', script], capture_output=True, text=True, timeout=60,
    )
    assert resultat.returncode == 0, resultat.stderr
    vu_shell = resultat.stdout.splitlines()
    assert vu_shell == [
        attendu['SECRET_KEY'],
        attendu['ALLOWED_HOSTS'],
        attendu['ORION_UPDATE_CELERY_RESTART_COMMAND'],
        attendu['VIDE'],
        attendu['ORION_SECRET_ENCRYPTION_KEY'],
    ], resultat.stdout
