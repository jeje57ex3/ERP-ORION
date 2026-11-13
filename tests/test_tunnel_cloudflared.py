"""« Enlève la commande de démarrage, mets plutôt un bouton. »

CE QUE CE LOT REMPLACE

Le tunnel se lançait à la main depuis l'hôte Proxmox :

    qm guest exec 100 -- cloudflared tunnel run <uuid>

Cet appel ne pouvait pas tenir. « qm guest exec » ATTEND la fin de la
commande, alors que « cloudflared tunnel run » ne se termine jamais :
l'appel bloque, dépasse son délai, et le tunnel meurt avec lui. Un
processus lancé ainsi ne survit d'ailleurs ni au redémarrage ni au
plantage.

L'appliance installe pourtant déjà « cloudflared.service ». On le pilote
désormais depuis l'écran Cloudflare.

LE TEST QUI COMPTE LE PLUS

`test_sudoers_autorise_exactement_les_commandes_du_code`. Les boutons
passent par `sudo -n` sur des lignes de commande EXACTES ; si le code et le
fichier sudoers divergent d'un seul caractère, les boutons échouent — sur
l'appliance, en production, et pas ici. Ce test fait diverger les deux
fichiers au moment où on les modifie, pas six mois plus tard.
"""
from pathlib import Path

import pytest

from apps.websites.cloudflared_service import (ACTIONS, CHEMINS_SYSTEMCTL,
                                               SERVICE, CloudflaredError,
                                               etat, ligne_de_commande)


SUDOERS = Path('deployment/proxmox-appliance/sudoers/orion-cloudflared')


# ── 1. L'accord entre le code et sudoers ─────────────────────────────────────

def test_le_fichier_sudoers_existe():
    assert SUDOERS.exists(), (
        'sans ce fichier, les boutons echouent avec « orion is not in the '
        'sudoers file » : l’ecran existe, les boutons s’affichent, et rien '
        'ne se passe')


def test_sudoers_autorise_exactement_les_commandes_du_code():
    """LA GARANTIE CENTRALE.

    Chaque action doit être autorisée pour LES DEUX emplacements possibles
    de systemctl : /usr/bin sur certaines distributions, /bin sur d'autres.
    """
    lignes = {l.strip() for l in SUDOERS.read_text(encoding='utf-8').splitlines()
              if l.strip() and not l.startswith('#')}

    manquantes = []
    for action, (verbe, _) in ACTIONS.items():
        for chemin in CHEMINS_SYSTEMCTL:
            attendue = f'orion ALL=(root) NOPASSWD: {chemin} {verbe} {SERVICE}'
            if attendue not in lignes:
                manquantes.append(attendue)

    assert not manquantes, (
        'commande(s) employee(s) par le code et non autorisee(s) par '
        f'sudoers : {manquantes}')


def test_sudoers_n_autorise_rien_de_plus_que_le_code():
    """L'autre sens, et il est tout aussi important : une ligne laissée dans
    sudoers après avoir disparu du code est une permission accordée pour
    rien."""
    lignes = {l.strip() for l in SUDOERS.read_text(encoding='utf-8').splitlines()
              if l.strip() and not l.startswith('#')}

    attendues = {
        f'orion ALL=(root) NOPASSWD: {chemin} {verbe} {SERVICE}'
        for verbe, _ in ACTIONS.values()
        for chemin in CHEMINS_SYSTEMCTL
    }
    assert lignes == attendues, f'en trop : {sorted(lignes - attendues)}'


def test_aucun_joker_dans_sudoers():
    """Un joker transforme une permission étroite en permission large : sudo
    compare la commande à ce motif, et « systemctl * cloudflared »
    accepterait bien plus qu'on ne croit lui accorder."""
    for ligne in SUDOERS.read_text(encoding='utf-8').splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith('#'):
            assert '*' not in ligne, f'joker dans sudoers : {ligne}'


# ── 2. La ligne de commande ──────────────────────────────────────────────────

def test_la_commande_est_une_liste_sans_interpolation():
    """Pas de `shell=True`, pas de chaîne construite : le nom du service est
    une constante, jamais une donnée de requête."""
    argv = ligne_de_commande('demarrer')

    assert argv[0] == 'sudo'
    assert argv[1] == '-n', "sans « -n », un sudoers mal installe ferait " \
                            "patienter la requete au lieu d'echouer vite"
    assert argv[-2:] == ['start', SERVICE]
    assert argv[2].startswith('/'), 'le chemin doit etre absolu'


def test_une_action_inconnue_est_refusee():
    """Le nom d'action vient de l'URL. S'il n'est pas filtré, il arrive
    jusqu'à la ligne de commande."""
    with pytest.raises(CloudflaredError):
        ligne_de_commande('rm-rf')
    with pytest.raises(CloudflaredError):
        ligne_de_commande('start; rm -rf /')


@pytest.mark.parametrize('action', sorted(ACTIONS))
def test_chaque_action_produit_une_commande(action):
    argv = ligne_de_commande(action)
    assert argv[-1] == SERVICE
    assert len(argv) == 5


# ── 3. La lecture d'état ─────────────────────────────────────────────────────

def test_lire_l_etat_ne_leve_jamais():
    """Un écran de diagnostic qui tombe parce que le diagnostic a échoué ne
    sert à rien. Sur ce poste Windows, `etat()` doit rendre un verdict, pas
    une exception."""
    resultat = etat()

    assert isinstance(resultat, dict)
    for cle in ('disponible', 'actif', 'au_demarrage', 'installe'):
        assert cle in resultat


def test_hors_linux_l_etat_le_dit_au_lieu_de_pretendre_que_tout_va_bien():
    resultat = etat()
    import platform
    if platform.system() != 'Linux':
        assert resultat['disponible'] is False
        assert resultat['actif'] is False


# ── 4. L'écran ───────────────────────────────────────────────────────────────

@pytest.fixture
def connecte(db, client, django_user_model):
    from apps.accounts.models import UserProfile
    from apps.core.models import Company
    from apps.private_saas.models import ALL_MODULE_CODES, CompanyModule

    entreprise = Company.objects.create(name='Orion SARL', slug='orion-sarl')
    for code in ALL_MODULE_CODES:
        CompanyModule.objects.update_or_create(
            company=entreprise, module_code=code, defaults={'is_enabled': True})

    def connecter(super_admin=True):
        utilisateur = django_user_model.objects.create_user(
            'patron' if super_admin else 'salarie', password='x',
            is_superuser=super_admin, is_staff=True)
        profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
        profil.role = 'superadmin' if super_admin else 'admin'
        profil.save()
        profil.companies.add(entreprise)
        client.force_login(django_user_model.objects.get(pk=utilisateur.pk))
        session = client.session
        session['current_company_id'] = entreprise.pk
        session.save()
        return utilisateur

    return {'client': client, 'connecter': connecter}


@pytest.mark.django_db
def test_un_salarie_ne_peut_pas_piloter_le_tunnel(connecte):
    """Couper le tunnel coupe l'acces de TOUTE l'installation depuis
    l'exterieur. Ce n'est pas un reglage de site."""
    from django.urls import reverse

    connecte['connecter'](super_admin=False)

    reponse = connecte['client'].post(
        reverse('websites:cloudflared_action', args=['arreter']))

    assert reponse.status_code == 302


@pytest.mark.django_db
def test_l_action_n_est_pas_accessible_en_GET(connecte):
    """Une adresse qui coupe le tunnel ne doit pas pouvoir etre declenchee
    par une simple visite — ni par le prechargement d'un navigateur."""
    from django.urls import reverse

    connecte['connecter'](super_admin=True)

    reponse = connecte['client'].get(
        reverse('websites:cloudflared_action', args=['arreter']))

    assert reponse.status_code == 405


# ── 5. L'installation du fichier de droits ───────────────────────────────────

def test_chaque_fichier_sudoers_est_installe_par_la_mise_a_jour():
    """UN FICHIER DE DROITS QUE RIEN N'INSTALLE NE SERT A RIEN.

    Le fichier peut etre parfait et versionne : s'il n'est pas copie dans
    /etc/sudoers.d/, les boutons echouent quand meme. Ce test relie les
    deux, pour qu'ajouter un fichier sans l'installer devienne impossible
    sans s'en apercevoir.
    """
    dossier = Path('deployment/proxmox-appliance/sudoers')
    maj = Path('deployment/proxmox-appliance/scripts/update_orion.sh')
    deploie = Path('deployment/proxmox-appliance/provisioning/02-deploy-orion.sh')

    texte_maj = maj.read_text(encoding='utf-8')
    texte_deploie = deploie.read_text(encoding='utf-8')

    oublies = []
    for fichier in sorted(dossier.iterdir()):
        if not fichier.is_file():
            continue
        if fichier.name not in texte_maj:
            oublies.append(f'{fichier.name} absent de update_orion.sh')
        if fichier.name not in texte_deploie:
            oublies.append(f'{fichier.name} absent de 02-deploy-orion.sh')

    assert not oublies, oublies


# ── 6. Plus de commande a taper ──────────────────────────────────────────────

ECRANS_TUNNEL = (
    Path('templates/websites/tunnel/tunnel_detail.html'),
    Path('templates/websites/cloudflare/cloudflare_dashboard.html'),
)


def test_aucun_ecran_ne_propose_une_commande_a_taper():
    """« Je ne veux pas de commande, seulement des boutons. »

    L'ecran du tunnel affichait un encadre « Demarrage » dont tout le
    contenu etait la ligne a recopier dans un terminal. Ce n'etait pas un
    pilotage : c'etait un pense-bete qui obligeait a sortir de l'ERP.

    Le test interdit la phrase d'invitation, pas le mot « tunnel run » : une
    MENTION explicative au fil d'une phrase reste legitime (le mode
    « --token-file » doit pouvoir etre explique). Ce qui est proscrit, c'est
    de PRESENTER une commande comme la facon de demarrer.
    """
    fautifs = []
    for gabarit in ECRANS_TUNNEL:
        texte = gabarit.read_text(encoding='utf-8')
        for interdit in ('Commande pour lancer', 'Commande de lancement'):
            if interdit in texte:
                fautifs.append(f'{gabarit.name} : « {interdit} »')
    assert not fautifs, fautifs


def test_l_ecran_du_tunnel_propose_les_boutons():
    """L'autre moitie : avoir retire la commande ne suffit pas, il faut que
    les boutons soient la."""
    texte = ECRANS_TUNNEL[0].read_text(encoding='utf-8')

    assert "'websites:cloudflared_action'" in texte, 'aucun bouton d’action'
    assert 'cloudflared_actions' in texte, 'la liste des actions n’est pas parcourue'
    assert 'csrf_token' in texte, 'une action qui change l’etat exige un jeton CSRF'
