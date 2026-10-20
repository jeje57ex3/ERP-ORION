"""Éteindre et redémarrer le serveur depuis Orion ERP.

L'écran existait déjà — confirmation à saisir, `@super_admin_required`,
journal `ServerActionLog`, délai d'une minute pour que la réponse HTTP sorte
avant l'arrêt. **Ce qui manquait était le DROIT de l'exécuter :**
`orion-backend.service` tourne sous `User=orion`, et aucune règle sudoers
n'existait pour ce compte. Les boutons s'affichaient, et `sudo shutdown`
échouait avec « orion is not in the sudoers file ».

**L'invariant que ce fichier protège : la commande que le code lance est
exactement celle que sudoers autorise.** Les deux listes vivent dans deux
fichiers différents — un module Python et un fichier de configuration
système. Si elles divergent, les boutons cessent de fonctionner sans que
rien ne le signale, et on ne s'en aperçoit qu'en voulant redémarrer un
serveur en production.

**Il n'y a pas d'action « allumer », et il ne peut pas y en avoir.** Une
machine éteinte ne sert aucune page web, donc ne peut pas recevoir l'ordre
de démarrer. Les tests vérifient que l'écran le DIT, plutôt que de laisser
chercher un bouton absent.
"""

import re
from pathlib import Path

import pytest

SUDOERS = (Path(__file__).resolve().parent.parent / 'deployment'
           / 'proxmox-appliance' / 'sudoers' / 'orion-serveur')


def _regles_sudoers():
    """Les lignes de commande autorisées, telles que sudoers les déclare."""
    autorisees = set()
    for ligne in SUDOERS.read_text(encoding='utf-8').splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith('#'):
            continue
        # « orion ALL=(root) NOPASSWD: /sbin/shutdown -r +1 »
        _, _, commande = ligne.partition('NOPASSWD:')
        if commande.strip():
            autorisees.add(commande.strip())
    return autorisees


# ═══ LE COUPLAGE CODE ↔ SUDOERS ═════════════════════════════════════════════

def test_le_fichier_sudoers_existe():
    assert SUDOERS.is_file(), SUDOERS


@pytest.mark.parametrize('action', ['reboot', 'shutdown', 'cancel'])
def test_chaque_commande_du_code_est_autorisee_par_sudoers(action):
    """L'invariant central. Si le code change de délai, de chemin ou
    d'option sans que sudoers suive, le bouton échoue en production."""
    from apps.system_updates.server_actions import ligne_de_commande

    argv = ligne_de_commande(action)
    # sudoers compare ce qui suit « sudo » et ses options.
    assert argv[0] == 'sudo'
    assert argv[1] == '-n', 'sudo -n : jamais d’attente de mot de passe'
    commande = ' '.join(argv[2:])

    autorisees = _regles_sudoers()
    assert commande in autorisees, (
        f'« {commande} » n’est pas dans {SUDOERS.name} : '
        f'autorisées = {sorted(autorisees)}')


def test_sudoers_couvre_les_deux_emplacements_de_shutdown():
    """« shutdown » est dans /sbin sur certaines distributions et
    /usr/sbin sur d'autres. N'en couvrir qu'un casserait sur l'autre."""
    autorisees = _regles_sudoers()
    for prefixe in ('/sbin/shutdown', '/usr/sbin/shutdown'):
        for arguments in ('-r +1', '-h +1', '-c'):
            assert f'{prefixe} {arguments}' in autorisees


def test_sudoers_ne_contient_AUCUN_joker():
    """Le point essentiel de la règle. « /sbin/shutdown * » accepte
    beaucoup plus que ce qu'on croit lui accorder : sudo compare la
    commande demandée à ce motif, et un joker en fin de motif laisse
    passer des arguments supplémentaires."""
    for commande in _regles_sudoers():
        assert '*' not in commande, commande
        assert '?' not in commande, commande
        assert 'ALL' not in commande, commande


def test_sudoers_n_autorise_que_shutdown():
    """Aucune autre commande ne doit se glisser dans ce fichier : il est
    installé dans /etc/sudoers.d/ et accorde du root sans mot de passe."""
    for commande in _regles_sudoers():
        assert commande.split()[0].endswith('/shutdown'), commande


def test_sudoers_ne_vise_que_le_compte_de_service():
    texte = SUDOERS.read_text(encoding='utf-8')
    for ligne in texte.splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith('#'):
            continue
        assert ligne.startswith('orion '), ligne


def test_le_fichier_sudoers_dit_de_le_valider_avant_installation():
    """Un fichier malformé dans /etc/sudoers.d/ casse sudo pour tout le
    monde, y compris pour le réparer. L'avertissement doit être dans le
    fichier, là où on le lit avant de l'installer."""
    texte = SUDOERS.read_text(encoding='utf-8')
    assert 'visudo -c' in texte


def test_le_provisionnement_valide_avant_d_installer():
    racine = Path(__file__).resolve().parent.parent
    script = (racine / 'deployment' / 'proxmox-appliance' / 'provisioning'
              / '02-deploy-orion.sh').read_text(encoding='utf-8')

    assert 'orion-serveur' in script
    assert 'visudo -c' in script
    # L'installation ne doit pas etre inconditionnelle.
    assert re.search(r'if\s+visudo\s+-c', script), (
        'visudo -c doit CONDITIONNER l’installation, pas seulement '
        'être appelé')


# ═══ LA CONSTRUCTION DE LA COMMANDE ═════════════════════════════════════════

def test_le_delai_est_d_une_minute_et_non_immediat():
    """`shutdown -h now` couperait gunicorn avant que la réponse HTTP de
    confirmation ne parte : l'administrateur resterait devant une page qui
    ne charge jamais, sans savoir si l'action a été prise en compte."""
    from apps.system_updates.server_actions import DELAI_MINUTES, ARGUMENTS

    assert DELAI_MINUTES >= 1
    assert ARGUMENTS['reboot'] == ('-r', f'+{DELAI_MINUTES}')
    assert ARGUMENTS['shutdown'] == ('-h', f'+{DELAI_MINUTES}')
    assert 'now' not in ' '.join(ARGUMENTS['reboot'])


def test_le_chemin_est_absolu():
    """« sudo shutdown » dépendrait du PATH du processus, que systemd ne
    garantit pas."""
    from apps.system_updates.server_actions import chemin_shutdown

    assert chemin_shutdown().startswith('/')


def test_une_action_inconnue_est_refusee():
    from apps.system_updates.server_actions import (
        ServerActionError, ligne_de_commande,
    )

    with pytest.raises(ServerActionError):
        ligne_de_commande('formater_le_disque')


def test_la_commande_est_une_LISTE_et_non_une_chaine():
    """Pas de shell : une chaîne passée à shell=True ouvrirait la porte à
    l'injection le jour où un argument viendrait d'une requête."""
    from apps.system_updates.server_actions import ligne_de_commande

    argv = ligne_de_commande('reboot')
    assert isinstance(argv, list)
    assert all(isinstance(element, str) for element in argv)


def test_aucun_shell_dans_le_module():
    """Le module precedent passait par run_command(shell=True) avec une
    f-string interpolee.

    Verifie sur l'ARBRE SYNTAXIQUE et non sur le texte : une premiere
    version de ce test cherchait « shell=True » dans la source, et matchait
    sa propre docstring d'explication. Un test qui se valide lui-meme ne
    prouve rien.
    """
    import ast

    from apps.system_updates import server_actions

    arbre = ast.parse(
        Path(server_actions.__file__).read_text(encoding='utf-8'))

    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Call):
            for argument in noeud.keywords:
                if argument.arg == 'shell':
                    assert not (isinstance(argument.value, ast.Constant)
                                and argument.value.value),                         'un appel passe shell=True'
        # run_command vient de git_service et passe shell=True.
        if isinstance(noeud, ast.Name):
            assert noeud.id != 'run_command', 'run_command est revenu'
        if isinstance(noeud, ast.Attribute):
            assert noeud.attr != 'run_command', 'run_command est revenu'


# ═══ LE GARDE-FOU HORS LINUX ════════════════════════════════════════════════

def test_hors_linux_l_action_est_refusee_proprement(monkeypatch):
    """Sur un poste de développement Windows, le message doit dire
    pourquoi — pas lever une erreur de commande introuvable."""
    import platform

    from apps.system_updates import server_actions

    monkeypatch.setattr(platform, 'system', lambda: 'Windows')
    with pytest.raises(server_actions.ServerActionError) as echec:
        server_actions.schedule_reboot()
    assert 'Linux' in str(echec.value)


def test_un_refus_de_sudo_nomme_le_fichier_a_installer(monkeypatch):
    """« sudo: a password is required » n'apprend rien à l'exploitant. Le
    message doit nommer le fichier sudoers manquant — c'est le seul remède,
    et c'était exactement le défaut à corriger."""
    import platform
    import subprocess

    from apps.system_updates import server_actions

    class Resultat:
        returncode = 1
        stdout = ''
        stderr = 'sudo: a password is required'

    monkeypatch.setattr(platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: Resultat())

    with pytest.raises(server_actions.ServerActionError) as echec:
        server_actions.schedule_shutdown()
    assert 'sudoers' in str(echec.value)
    assert 'orion-serveur' in str(echec.value)


def test_un_echec_ordinaire_rapporte_le_detail(monkeypatch):
    import platform
    import subprocess

    from apps.system_updates import server_actions

    class Resultat:
        returncode = 1
        stdout = ''
        stderr = 'shutdown: unrecognized option'

    monkeypatch.setattr(platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: Resultat())

    with pytest.raises(server_actions.ServerActionError) as echec:
        server_actions.schedule_reboot()
    assert 'unrecognized' in str(echec.value)


def test_un_succes_rend_la_commande_lancee(monkeypatch):
    import platform
    import subprocess

    from apps.system_updates import server_actions

    class Resultat:
        returncode = 0
        stdout = 'Shutdown scheduled'
        stderr = ''

    monkeypatch.setattr(platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: Resultat())

    resultat = server_actions.schedule_reboot()
    assert resultat['ok'] is True
    assert '/shutdown -r +1' in resultat['command']


def test_un_depassement_de_delai_est_dit(monkeypatch):
    import platform
    import subprocess

    from apps.system_updates import server_actions

    def tombe(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd='shutdown', timeout=15)

    monkeypatch.setattr(platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(subprocess, 'run', tombe)

    with pytest.raises(server_actions.ServerActionError) as echec:
        server_actions.cancel_scheduled_action()
    assert 'secondes' in str(echec.value)


# ═══ « ALLUMER » : CE QUI N'EST PAS POSSIBLE, ET QUI EST DIT ════════════════

def test_le_module_ne_pretend_pas_savoir_allumer():
    """Aucune fonction de démarrage : une machine éteinte ne sert aucune
    page web, donc ne peut pas recevoir cet ordre."""
    from apps.system_updates import server_actions

    publiques = {nom for nom in dir(server_actions)
                 if not nom.startswith('_')}
    for interdit in ('power_on', 'allumer', 'schedule_boot', 'start_server'):
        assert interdit not in publiques


def test_le_module_explique_pourquoi_allumer_est_impossible():
    """Un lecteur qui cherche la fonction manquante doit trouver la raison
    sur place, et non conclure à un oubli."""
    from apps.system_updates import server_actions

    docstring = (server_actions.__doc__ or '').upper()
    assert 'ALLUMER' in docstring


# ═══ LES ÉCRANS ═════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestEcrans:
    """Les écrans, avec une base : ils sont réservés au super-administrateur."""

    @pytest.fixture
    def entreprise(self, db):
        from apps.core.models import Company
        return Company.objects.create(name='Dupont SA', slug='dupont-sa')

    @pytest.fixture
    def admin(self, client, entreprise, django_user_model):
        user = django_user_model.objects.create_superuser(
            username='patron', password='motdepasse-test',
            email='patron@example.test')
        user.profile.companies.add(entreprise)
        user.profile.current_company = entreprise
        user.profile.save()
        client.force_login(user)
        return client

    @pytest.fixture
    def simple(self, client, entreprise, django_user_model):
        user = django_user_model.objects.create_user(
            username='employe', password='motdepasse-test')
        user.profile.companies.add(entreprise)
        user.profile.current_company = entreprise
        user.profile.save()
        client.force_login(user)
        return client

    def test_un_employe_n_atteint_pas_l_extinction(self, simple):
        from django.urls import reverse

        reponse = simple.get(reverse('system_updates:server_shutdown'))
        assert reponse.status_code in (302, 403), reponse.status_code

    def test_un_visiteur_non_connecte_non_plus(self, client, entreprise):
        from django.urls import reverse

        reponse = client.get(reverse('system_updates:server_shutdown'))
        assert reponse.status_code in (302, 403)

    def test_l_ecran_d_extinction_dit_comment_rallumer(self, admin):
        """L'avertissement « il ne se rallumera pas seul » ne suffit pas :
        il faut dire comment s'y prendre, AVANT de couper. Après, cette
        page n'est plus là pour l'apprendre."""
        from django.urls import reverse

        corps = admin.get(
            reverse('system_updates:server_shutdown')).content.decode()
        assert 'Comment rallumer' in corps
        assert 'qm start' in corps
        assert 'Proxmox' in corps

    def test_l_ecran_de_redemarrage_ne_parle_pas_de_rallumer(self, admin):
        """Un redémarrage revient tout seul : le panneau serait du bruit."""
        from django.urls import reverse

        corps = admin.get(
            reverse('system_updates:server_reboot')).content.decode()
        assert 'Comment rallumer' not in corps

    def test_l_extinction_exige_le_mot_exact(self, admin):
        from django.urls import reverse

        from apps.system_updates.models import ServerActionLog

        reponse = admin.post(reverse('system_updates:server_shutdown'),
                             {'confirm_text': 'oui'})
        assert reponse.status_code == 200
        assert not ServerActionLog.objects.exists()

    def test_le_tableau_de_bord_explique_l_absence_d_allumer(self, admin):
        """Sinon on cherche un bouton qui ne peut pas exister."""
        from django.urls import reverse

        corps = admin.get(
            reverse('system_updates:dashboard')).content.decode()
        assert 'Allumer' in corps
        assert 'ne sert aucune page web' in corps

    def test_un_echec_est_journalise_avec_son_auteur(self, admin,
                                                      monkeypatch):
        """Une action aussi destructrice doit laisser une trace nominative,
        qu'elle aboutisse ou non."""
        import platform

        from django.urls import reverse

        from apps.system_updates.models import ServerActionLog

        # Hors Linux : l'action echoue proprement, et doit etre journalisee.
        monkeypatch.setattr(platform, 'system', lambda: 'Windows')
        admin.post(reverse('system_updates:server_shutdown'),
                   {'confirm_text': 'ETEINDRE'})

        journal = ServerActionLog.objects.get()
        assert journal.action == 'shutdown'
        assert journal.status == 'failed'
        assert journal.executed_by is not None
