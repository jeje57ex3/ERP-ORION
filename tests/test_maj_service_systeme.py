"""La mise à jour ne doit plus dépendre de l'interface web.

CE QUE CE FICHIER PROTÈGE. Le bouton de mise à jour confiait le travail à
`run_system_update`, qui cumule quatre dépendances — toutes constatées en
panne sur l'appliance les 07 et 08/11/2026 :

1. sa PREMIÈRE instruction lit la base (`get_update_settings`) : il ne
   démarre pas si MySQL est tombé, c'est-à-dire précisément quand il faut
   déployer un correctif ;
2. il tourne dans un worker gunicorn : un `orion-backend` tué par manque de
   mémoire emporte la mise à jour en cours de route. La VM étant
   surréservée en mémoire, ce n'est pas une hypothèse ;
3. il tourne sous « orion », qui n'est pas administrateur : il ne peut
   rafraîchir ni apt, ni /etc/sudoers.d/, ni /usr/local/sbin/orion-stockage,
   ni les unités systemd. **L'assistant de préparation des disques est ainsi
   resté absent d'une machine mise à jour plusieurs fois** ;
4. il exige que l'interface web réponde.

La solution confie le travail à `orion-update.service`. Les tests ci-dessous
tiennent les quatre propriétés qui en découlent, et surtout l'invariant
central : **la commande que le code lance est exactement celle que sudoers
autorise.** Les deux listes vivent dans deux fichiers de nature différente ;
si elles divergent, le bouton cesse de fonctionner sans que rien ne le
signale, et on s'en aperçoit en voulant déployer un correctif urgent.
"""

from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
DEPLOIEMENT = RACINE / 'deployment' / 'proxmox-appliance'

SUDOERS = DEPLOIEMENT / 'sudoers' / 'orion-maj'
UNITE = DEPLOIEMENT / 'systemd' / 'orion-update.service'
SCRIPT_MAJ = DEPLOIEMENT / 'scripts' / 'update_orion.sh'
PROVISIONING = DEPLOIEMENT / 'provisioning' / '02-deploy-orion.sh'


def _regles_sudoers():
    """Les lignes de commande autorisées, telles que sudoers les déclare."""
    autorisees = set()
    for ligne in SUDOERS.read_text(encoding='utf-8').splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith('#'):
            continue
        _, _, commande = ligne.partition('NOPASSWD:')
        if commande.strip():
            autorisees.add(commande.strip())
    return autorisees


# ═══ L'invariant central : code ↔ sudoers ═══════════════════════════════════

def test_le_fichier_sudoers_existe():
    assert SUDOERS.is_file(), SUDOERS


def test_la_commande_du_code_est_autorisee_par_sudoers():
    """Si le code change d'unité ou de chemin sans que sudoers suive, le
    bouton échoue en production, et seulement là."""
    from apps.system_updates import service_maj

    autorisees = _regles_sudoers()
    for chemin in service_maj.CHEMINS_SYSTEMCTL:
        attendue = f'{chemin} start {service_maj.UNITE}'
        assert attendue in autorisees, (
            f'« {attendue} » doit figurer dans {SUDOERS.name}')


def test_la_commande_passe_par_sudo_sans_mot_de_passe():
    """`sudo -n` : sans lui, un sudoers mal installé ferait patienter la
    requête jusqu'au délai d'expiration au lieu d'échouer clairement."""
    from apps.system_updates import service_maj

    commande = service_maj.ligne_de_commande()

    assert commande[0] == 'sudo'
    assert commande[1] == '-n'
    assert commande[-2:] == ['start', service_maj.UNITE]


def test_sudoers_n_accorde_aucun_joker():
    """« systemctl * » donnerait à orion le contrôle de tous les services.

    C'est la racine par un autre chemin, et c'est le défaut qu'une règle
    large introduit sans en avoir l'air.
    """
    for regle in _regles_sudoers():
        assert '*' not in regle, f'joker dans sudoers : {regle}'
        assert regle.endswith('start orion-update.service'), (
            f'seul « start » sur cette unité doit être autorisé : {regle}')


def test_sudoers_n_autorise_ni_stop_ni_daemon_reload():
    texte = SUDOERS.read_text(encoding='utf-8')
    actives = [l for l in texte.splitlines()
               if l.strip() and not l.strip().startswith('#')]
    joint = ' '.join(actives)

    for interdit in ('stop', 'restart', 'disable', 'daemon-reload', 'mask'):
        assert f' {interdit} ' not in f' {joint} ', interdit


# ═══ L'unité systemd ════════════════════════════════════════════════════════

def test_l_unite_existe_et_appelle_le_script_root():
    assert UNITE.is_file(), UNITE
    texte = UNITE.read_text(encoding='utf-8')

    assert 'ExecStart=/opt/orion/scripts/update_orion.sh --direct' in texte, (
        '--direct : c est ce qui rend la mise a jour independante de la base')
    assert 'Type=oneshot' in texte


def test_l_unite_n_est_pas_activee_au_demarrage():
    """Décision de Jessy : déclenchement manuel, jamais automatique.

    Une section [Install] la ferait démarrer au boot. Un `git pull` et des
    migrations non surveillés sur un ERP en production, c'est se réveiller
    devant un système cassé sans savoir ce qui a changé.
    """
    # Hors commentaires : l'en-tête du fichier EXPLIQUE pourquoi il n'y a
    # pas de section [Install], et contient donc ce mot. Chercher dans le
    # texte brut échouait sur sa propre justification.
    actives = [l.strip() for l in UNITE.read_text(encoding='utf-8').splitlines()
               if l.strip() and not l.strip().startswith('#')]

    assert '[Install]' not in actives
    assert not any(l.startswith('WantedBy') for l in actives)


def test_l_unite_ne_se_rejoue_pas_en_boucle():
    """Un Restart= sur un disque plein ferait trois fois les mêmes dégâts."""
    lignes = [l.strip() for l in UNITE.read_text(encoding='utf-8').splitlines()]
    assert not any(l.startswith('Restart=') for l in lignes)


def test_l_unite_laisse_le_temps_aux_builds():
    """Un délai trop court tuerait la mise à jour au milieu d'un build npm,
    c'est-à-dire dans l'état le plus pénible à rattraper."""
    texte = UNITE.read_text(encoding='utf-8')

    for ligne in texte.splitlines():
        if ligne.strip().startswith('TimeoutStartSec='):
            secondes = int(ligne.split('=', 1)[1].strip())
            assert secondes >= 3600, (
                f'{secondes} s est trop court pour apt + pip + trois builds')
            return
    pytest.fail('TimeoutStartSec absent : systemd tuerait la mise a jour')


def test_l_unite_journalise():
    """Sans journal, une mise à jour échouée ne laisse aucune trace lisible
    après un redémarrage — et c'est après un redémarrage qu'on cherche."""
    texte = UNITE.read_text(encoding='utf-8')

    assert 'StandardOutput=journal' in texte
    assert 'StandardError=journal' in texte


# ═══ Le contrôle préalable du script ════════════════════════════════════════

def test_le_script_refuse_avant_de_modifier_quoi_que_ce_soit():
    """Les deux pannes sont arrivées sur une machine à 85 % de disque et à
    bout de mémoire, sans que rien ne l'ait vérifié."""
    texte = SCRIPT_MAJ.read_text(encoding='utf-8')

    assert 'verifier_avant_de_commencer' in texte
    assert 'MINI_DISQUE_MO' in texte
    assert 'MINI_MEMOIRE_MO' in texte
    assert 'MemAvailable' in texte


def test_le_controle_prealable_court_avant_la_premiere_etape():
    """Un contrôle posé après `apt upgrade` ne protégerait de rien."""
    texte = SCRIPT_MAJ.read_text(encoding='utf-8')

    appel = texte.index('\nverifier_avant_de_commencer\n')
    premiere_etape = texte.index('[1/6]')

    assert appel < premiere_etape, (
        'le controle doit courir AVANT la premiere modification')


def test_l_etat_est_ecrit_sur_le_disque_et_non_en_base():
    """C'est ce qui le rend lisible quand MySQL est tombé — le défaut exact
    de SystemUpdateRun, qui vit en base."""
    texte = SCRIPT_MAJ.read_text(encoding='utf-8')

    assert 'maj-etat.json' in texte
    assert 'noter_etat' in texte
    assert "trap sur_sortie EXIT" in texte, (
        'sans piege sur EXIT, une mise a jour tuee resterait « en cours »')


def test_le_script_installe_la_regle_sudo_de_la_mise_a_jour():
    """Sinon le bouton ne fonctionnerait que sur une appliance neuve."""
    texte = SCRIPT_MAJ.read_text(encoding='utf-8')

    assert 'orion-maj' in texte, (
        'update_orion.sh doit rafraichir /etc/sudoers.d/orion-maj')


def test_le_provisionnement_installe_la_regle_sudo():
    texte = PROVISIONING.read_text(encoding='utf-8')

    assert 'installer_sudoers orion-maj' in texte


# ═══ Le module Python ═══════════════════════════════════════════════════════

def test_le_module_ne_tente_rien_hors_linux():
    """Sur le poste de développement, l'écran doit rester consultable."""
    from apps.system_updates import service_maj

    if __import__('platform').system() == 'Linux':
        pytest.skip('ce test décrit le comportement hors Linux')

    assert service_maj.est_disponible() is False
    with pytest.raises(service_maj.ServiceDeMiseAJourIndisponible):
        service_maj.declencher()


def test_un_etat_illisible_n_est_pas_une_erreur(monkeypatch):
    """Il n'y a simplement jamais eu de mise à jour par ce chemin."""
    from apps.system_updates import service_maj

    monkeypatch.setattr(service_maj, 'FICHIER_ETAT',
                        Path('/chemin/qui/n/existe/pas.json'))

    etat = service_maj.etat()

    assert etat['derniere_etape'] is None
    assert etat['dernier_code'] is None
    assert etat['unite'] == service_maj.UNITE


def test_un_etat_lisible_est_rapporte(monkeypatch, tmp_path):
    from apps.system_updates import service_maj

    fichier = tmp_path / 'maj-etat.json'
    fichier.write_text(
        '{"etape": "refusee", "mode": "direct", "code": 1, '
        '"horodatage": "2026-11-08T13:00:00Z"}', encoding='utf-8')
    monkeypatch.setattr(service_maj, 'FICHIER_ETAT', fichier)

    etat = service_maj.etat()

    assert etat['derniere_etape'] == 'refusee'
    assert etat['dernier_code'] == 1
    assert etat['dernier_mode'] == 'direct'


def test_un_json_tronque_ne_fait_pas_tomber_la_page(monkeypatch, tmp_path):
    """Le fichier est écrit pendant la mise à jour : il peut être lu à
    l'instant où il est réécrit."""
    from apps.system_updates import service_maj

    fichier = tmp_path / 'maj-etat.json'
    fichier.write_text('{"etape": "demarr', encoding='utf-8')
    monkeypatch.setattr(service_maj, 'FICHIER_ETAT', fichier)

    assert service_maj.etat()['derniere_etape'] is None


def test_un_json_qui_n_est_pas_un_objet_est_ignore(monkeypatch, tmp_path):
    from apps.system_updates import service_maj

    fichier = tmp_path / 'maj-etat.json'
    fichier.write_text('["demarrage"]', encoding='utf-8')
    monkeypatch.setattr(service_maj, 'FICHIER_ETAT', fichier)

    assert service_maj.etat()['derniere_etape'] is None


def test_le_refus_de_sudo_est_dit_en_clair(monkeypatch):
    """« orion is not in the sudoers file » ne dit pas quoi faire."""
    import subprocess

    from apps.system_updates import service_maj

    monkeypatch.setattr(service_maj.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(service_maj.CHEMIN_DE_L_UNITE.__class__, 'is_file',
                        lambda self: True)

    def _refus(*args, **kwargs):
        return subprocess.CompletedProcess(
            args, 1, '', 'sudo: a password is required')

    monkeypatch.setattr(service_maj.subprocess, 'run', _refus)

    with pytest.raises(service_maj.ServiceDeMiseAJourIndisponible) as leve:
        service_maj.declencher()

    assert 'orion-maj' in str(leve.value), (
        'le message doit nommer le fichier a installer')


# ═══ La vue ═════════════════════════════════════════════════════════════════

def _super_admin(client, django_user_model):
    from apps.accounts.models import UserProfile
    from apps.core.models import Company

    entreprise, _ = Company.objects.get_or_create(
        slug='orion-maj-service', defaults={'name': 'Orion MAJ'})
    utilisateur = django_user_model.objects.create_user(
        'patron-maj', password='x', is_superuser=True, is_staff=True)
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.role = 'superadmin'
    profil.save()
    profil.companies.add(entreprise)

    utilisateur = django_user_model.objects.get(pk=utilisateur.pk)
    client.force_login(utilisateur)
    session = client.session
    session['current_company_id'] = entreprise.pk
    session.save()
    return utilisateur


@pytest.mark.django_db
def test_la_vue_refuse_la_methode_get(client, django_user_model):
    """Un déclenchement ne doit pas pouvoir partir d'un lien visité."""
    from django.urls import reverse

    _super_admin(client, django_user_model)

    reponse = client.get(reverse('system_updates:maj_par_le_service'))

    assert reponse.status_code == 405


@pytest.mark.django_db
def test_un_utilisateur_ordinaire_ne_peut_pas_declencher(
        client, django_user_model, monkeypatch):
    from django.urls import reverse

    from apps.system_updates import service_maj

    appels = []
    monkeypatch.setattr(service_maj, 'declencher',
                        lambda: appels.append(1))

    django_user_model.objects.create_user('simple-maj', password='x')
    client.login(username='simple-maj', password='x')

    client.post(reverse('system_updates:maj_par_le_service'))

    assert appels == [], 'seul un super administrateur peut declencher'


@pytest.mark.django_db
def test_la_vue_declenche_et_rend_la_main(client, django_user_model,
                                          monkeypatch):
    """Elle ne doit PAS attendre la fin : une mise à jour dure des minutes,
    la requête expirerait bien avant."""
    from django.urls import reverse

    from apps.system_updates import service_maj

    appels = []
    monkeypatch.setattr(service_maj, 'declencher',
                        lambda: appels.append(1) or True)
    _super_admin(client, django_user_model)

    reponse = client.post(reverse('system_updates:maj_par_le_service'))

    assert appels == [1]
    assert reponse.status_code == 302
    assert reponse['Location'] == reverse('system_updates:dashboard')


@pytest.mark.django_db
def test_un_echec_de_declenchement_est_dit_a_l_ecran(
        client, django_user_model, monkeypatch):
    from django.urls import reverse

    from apps.system_updates import service_maj

    def _echoue():
        raise service_maj.ServiceDeMiseAJourIndisponible('unite absente')

    monkeypatch.setattr(service_maj, 'declencher', _echoue)
    _super_admin(client, django_user_model)

    reponse = client.post(reverse('system_updates:maj_par_le_service'),
                          follow=True)
    contenu = reponse.content.decode()

    assert 'unite absente' in contenu


@pytest.mark.django_db
def test_le_tableau_de_bord_affiche_le_chemin_sans_interface(
        client, django_user_model, monkeypatch):
    """L'écran doit DIRE comment faire sans lui : c'est tout l'objet.

    Vérifié sur le HTML rendu, parce qu'un gabarit qui nomme ses champs un
    par un peut très bien ignorer une variable ajoutée au contexte.

    L'état est simulé : sur un poste de développement l'unité n'existe pas,
    et la carte afficherait son message d'absence. Ce qui est testé ici est
    le cas de l'appliance.
    """
    from django.urls import reverse

    from apps.system_updates import service_maj

    monkeypatch.setattr(service_maj, 'etat', lambda: {
        'disponible': True,
        'unite': 'orion-update.service',
        'etat_systemd': 'inactive',
        'en_cours': False,
        'fichier': '/opt/orion/logs/maj-etat.json',
        'derniere_etape': 'terminee',
        'dernier_code': 0,
        'dernier_horodatage': '2026-11-08T13:00:00Z',
        'dernier_mode': 'direct',
    })
    _super_admin(client, django_user_model)

    reponse = client.get(reverse('system_updates:dashboard'))
    contenu = reponse.content.decode()

    assert reponse.status_code == 200
    assert 'service système' in contenu
    assert 'systemctl start orion-update.service' in contenu
    assert 'journalctl -u orion-update' in contenu
    assert 'maj-etat.json' in contenu
    # Le bouton doit être un POST, pas un lien : un déclencheur ne part pas
    # d'une URL visitée.
    assert "system-updates/service/lancer/" in contenu


@pytest.mark.django_db
def test_sans_l_unite_le_tableau_de_bord_explique_quoi_faire(
        client, django_user_model):
    """Le cas du poste de développement, et d'une appliance pas encore à jour.

    Une carte vide laisserait chercher un bouton absent.
    """
    from django.urls import reverse

    _super_admin(client, django_user_model)

    reponse = client.get(reverse('system_updates:dashboard'))
    contenu = reponse.content.decode()

    assert reponse.status_code == 200
    assert 'update_orion.sh' in contenu
    assert 'Lancer par le service système' not in contenu
