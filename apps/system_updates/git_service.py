import base64
import subprocess
from pathlib import Path

from django.conf import settings


def run_command(command, cwd=None, timeout=300, display_command=None):
    result = subprocess.run(
        command,
        cwd=cwd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return {
        'returncode': result.returncode,
        'stdout': result.stdout.strip(),
        'stderr': result.stderr.strip(),
        'ok': result.returncode == 0,
        'command': display_command if display_command is not None else command,
    }


def _github_token():
    try:
        from apps.system_updates.models import SystemUpdateSettings
        from apps.website_shop_settings.crypto import decrypt_secret
    except Exception:
        return ''
    obj = SystemUpdateSettings.get_solo()
    return decrypt_secret(obj.github_token_encrypted) if obj.github_token_encrypted else ''


def _authenticated_git_command(subcommand):
    """Construit une commande git authentifiée (dépôt privé) sans jamais écrire le
    jeton sur disque (.git/config) ni dans l'URL — un en-tête HTTP temporaire, valable
    uniquement pour cette invocation, via `-c http.extraheader`.
    Retourne (commande réelle à exécuter, commande à journaliser/afficher — sans jeton).
    """
    display = f'git {subcommand}'
    token = _github_token()
    if not token:
        return display, display
    basic = base64.b64encode(f'x-access-token:{token}'.encode()).decode()
    real = f'git -c http.extraheader="AUTHORIZATION: basic {basic}" {subcommand}'
    return real, display


def get_project_root():
    configured = getattr(settings, 'ORION_PROJECT_ROOT', '')
    if configured:
        p = Path(configured)
        if p.exists() and p.is_dir():
            return p
    return Path(settings.BASE_DIR)


def get_current_commit():
    result = run_command('git rev-parse HEAD', cwd=get_project_root())
    return result['stdout'] if result['ok'] else ''


def get_current_branch():
    result = run_command('git rev-parse --abbrev-ref HEAD', cwd=get_project_root())
    return result['stdout'] if result['ok'] else ''


def fetch_remote():
    remote = getattr(settings, 'ORION_GIT_REMOTE', 'origin')
    real, display = _authenticated_git_command(f'fetch {remote}')
    return run_command(real, cwd=get_project_root(), timeout=600, display_command=display)


def get_remote_commit():
    remote = getattr(settings, 'ORION_GIT_REMOTE', 'origin')
    branch = getattr(settings, 'ORION_GIT_BRANCH', 'main')
    result = run_command(f'git rev-parse {remote}/{branch}', cwd=get_project_root())
    return result['stdout'] if result['ok'] else ''


def get_commits_behind_ahead():
    """Combien de commits de retard et d'avance. (None, None) si on ne sait pas.

    NE PAS SAVOIR N'EST PAS ETRE A JOUR, et cette fonction rendait
    pourtant (0, 0) des que la commande echouait -- ce que l'appelant lit
    comme « aucun commit de retard », donc « a jour ».

    Consequence constatee le 09/11/2026 : l'ERP annoncait « le systeme est
    a jour » alors que son ecran servait du code vieux de plusieurs lots.
    Personne ne pouvait le soupconner, puisque la page l'affirmait.

    C'est la meme faute que le script de mise a jour qui annoncait
    « schema migre » trois lignes sous un traceback : une incertitude
    rapportee comme un succes. Elle coute d'autant plus cher ici que la
    page sert precisement a savoir s'il faut agir.
    """
    remote = getattr(settings, 'ORION_GIT_REMOTE', 'origin')
    branch = getattr(settings, 'ORION_GIT_BRANCH', 'main')
    result = run_command(
        f'git rev-list --left-right --count HEAD...{remote}/{branch}',
        cwd=get_project_root(),
    )
    if not result['ok']:
        return None, None
    parts = result['stdout'].split()
    if len(parts) != 2:
        return None, None
    try:
        return int(parts[1]), int(parts[0])  # behind, ahead
    except ValueError:
        return None, None


def get_changelog(max_count=20):
    remote = getattr(settings, 'ORION_GIT_REMOTE', 'origin')
    branch = getattr(settings, 'ORION_GIT_BRANCH', 'main')
    result = run_command(
        f'git log --oneline HEAD..{remote}/{branch} -n {max_count}',
        cwd=get_project_root(),
    )
    return result['stdout'] if result['ok'] else ''


def build_pull_command(remote=None, branch=None):
    """Retourne (commande réelle, commande à journaliser) pour `git pull` — utilisé
    ici et par update_runner.py, pour ne construire la logique d'auth qu'à un seul
    endroit."""
    remote = remote or getattr(settings, 'ORION_GIT_REMOTE', 'origin')
    branch = branch or getattr(settings, 'ORION_GIT_BRANCH', 'main')
    return _authenticated_git_command(f'pull {remote} {branch}')


def pull_latest():
    real, display = build_pull_command()
    return run_command(real, cwd=get_project_root(), timeout=1200, display_command=display)


def hard_reset_to_commit(commit):
    return run_command(f'git reset --hard {commit}', cwd=get_project_root(), timeout=600)


# ─── LES SORTIES DE BUILD, ET POURQUOI ELLES CASSENT LA MISE À JOUR ──────────

# Ces deux dossiers sont des SORTIES DE BUILD, et ils sont pourtant suivis par
# git : l'appliance n'a pas toujours de quoi compiler, on lui livre donc des
# assets déjà construits.
#
# Seulement, la mise à jour RECONSTRUIT les deux frontends juste après avoir
# tiré le code. Chaque mise à jour réussie laisse donc ces fichiers modifiés
# dans la copie de travail — et c'est exactement ce qui fait échouer le
# « git pull » de la SUIVANTE :
#
#     error: Your local changes to the following files would be overwritten
#     by merge: static/siecle-store/index.html
#
# Autrement dit, chaque mise à jour posait la mine sur laquelle la suivante
# sautait. Le défaut ne pouvait pas se voir lors d'une mise à jour isolée :
# il fallait deux mises à jour de suite, dont une touchant la boutique.
CHEMINS_GENERES = (
    'static/siecle-store',
    'apps/lunea/static/lunea/dist',
)


def _est_genere(chemin):
    """Ce chemin est-il une sortie de build connue ?"""
    chemin = chemin.replace('\\', '/').strip()
    return any(chemin == base or chemin.startswith(base + '/')
               for base in CHEMINS_GENERES)


def fichiers_modifies(racine=None):
    """Les fichiers SUIVIS dont le contenu diffère de HEAD."""
    resultat = run_command('git diff --name-only',
                           cwd=racine or get_project_root())
    if not resultat['ok']:
        return []
    return [ligne.strip() for ligne in resultat['stdout'].splitlines()
            if ligne.strip()]


def restaurer_les_fichiers_generes(racine=None):
    """Rend aux sorties de build leur état commité, avant de tirer le code.

    ON NE RESTAURE QUE CE QU'ON SAIT REGÉNÉRER.

    Un « git reset --hard » règlerait le symptôme et détruirait au passage
    tout réglage local posé sur la machine. Ici on ne touche qu'aux chemins
    listés dans CHEMINS_GENERES, et ils sont reconstruits quelques étapes
    plus loin dans la même mise à jour : les écraser ne perd rien.

    Les fichiers modifiés HORS de ces chemins sont laissés intacts et
    RAPPORTÉS. Si le « pull » échoue encore, l'exploitant lit alors le nom
    d'un fichier qui lui appartient, au lieu d'un fichier généré qu'il n'a
    jamais édité et dont le nom ne lui dit rien.

    Rend (restaurés, autres_modifiés, erreurs). Les erreurs ne sont PAS
    levées : la mise à jour continue et le « pull » dira peut-être autre
    chose. Mais elles sont journalisées avant lui, pour qu'on lise la vraie
    cause — « Permission denied » — et non seulement son symptôme.
    """
    racine = racine or get_project_root()
    modifies = fichiers_modifies(racine)

    restaures = [c for c in modifies if _est_genere(c)]
    autres = [c for c in modifies if not _est_genere(c)]

    # On restaure par DOSSIER plutôt que fichier par fichier : la ligne de
    # commande reste courte quel que soit le nombre d'assets, et les fichiers
    # supprimés sous ces dossiers reviennent aussi.
    dossiers = [base for base in CHEMINS_GENERES
                if any(_est_genere(c) and (c == base or c.startswith(base + '/'))
                       for c in restaures)]

    erreurs = []
    for base in dossiers:
        commandes = (
            # « -- » sépare les chemins des révisions : sans lui, un chemin
            # qui ressemble à un nom de branche serait pris pour une révision.
            'git checkout -- %s' % base,
            # Un build laisse aussi des bundles NON SUIVIS, aux noms hachés.
            # Ils s'accumulent, et un fichier entrant portant le même nom
            # ferait échouer le pull à son tour (« untracked working tree
            # files would be overwritten »). Ils sont reconstruits juste après.
            'git clean -fdq -- %s' % base,
        )
        for commande in commandes:
            resultat = run_command(commande, cwd=racine, timeout=600)
            if not resultat['ok']:
                detail = (resultat['stderr'] or resultat['stdout'] or '').strip()
                erreurs.append('%s : %s' % (commande, detail[:800]))

    # ON REVÉRIFIE PLUTÔT QUE DE CROIRE LE CODE DE RETOUR.
    #
    # Sur une machine où un build a tourné en root, les fichiers générés ne
    # sont plus accessibles en écriture à l'utilisateur « orion » qui fait
    # tourner l'ERP. git répond alors « Permission denied » et ne restaure
    # rien — mais la première version de cette fonction ignorait le code de
    # retour, et la mise à jour échouait ensuite sur le « pull », avec un
    # message qui ne parlait que du fichier et jamais de la permission.
    #
    # C'était le même défaut que celui qu'on corrige ici : quelque chose qui
    # échoue sans le dire.
    restants = [c for c in fichiers_modifies(racine) if _est_genere(c)]
    if restants:
        erreurs.append(
            '%d fichier(s) généré(s) encore modifié(s) après restauration '
            '(droits d\'écriture ?) : %s'
            % (len(restants), ', '.join(restants[:5])))

    return restaures, autres, erreurs
