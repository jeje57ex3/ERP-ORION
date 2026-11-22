"""Le relais local : « accepté » n'est pas « remis », et le dire change tout.

**La panne qui a motivé ces tests.** Les courriels de l'ERP ne partaient pas.
Cause mesurée : `/orion-admin/courriels/` n'avait jamais été rempli, donc
`BackendMailOrion` retombait sur son repli — le SMTP de Django, pointé par
défaut sur `localhost:25`, où rien n'écoutait. Et
`deployment/quick-install/install.sh` ne fait qu'**afficher** la commande
d'installation du relais local : il ne l'installe jamais.

**Le piège de la correction.** Installer Postfix fait disparaître l'erreur
sans garantir la remise. Postfix accepte le message sur `127.0.0.1:25` et
rend un succès immédiat : il a pris la responsabilité de l'acheminer, il ne
l'a pas acheminé. Si le port 25 **sortant** est bloqué — le cas normal sur
une ligne résidentielle et chez beaucoup d'hébergeurs — le message dort dans
la file et n'arrive jamais.

C'est la pire panne possible, parce qu'elle se présente comme une réussite :
sur la création d'un utilisateur, le code provisoire n'est parti nulle part
et l'écran est vert. Ces tests gardent les deux endroits qui doivent le
dire : le message de la page de test, et le script d'installation.
"""

import os

import pytest

from apps.core.mail import _est_un_relais_local

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(RACINE, 'deployment', 'proxmox-appliance', 'scripts',
                      'setup_mail_relay.sh')


# ═══════════════════════════════════════════════════════════════════════════
#  Reconnaître un relais local
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize('hote', [
    '127.0.0.1', 'localhost', 'LOCALHOST', '::1', '[::1]',
    'localhost.localdomain', '  127.0.0.1  ',
])
def test_ces_hotes_sont_la_machine_elle_meme(hote):
    """`::1` et `localhost` ne commencent pas par « 127 ».

    Une version écrite en `startswith('127.')` les aurait manqués, et le
    message trompeur serait revenu pour une installation IPv6.
    """
    assert _est_un_relais_local(hote) is True


@pytest.mark.parametrize('hote', [
    'smtp-relay.brevo.com', 'in-v3.mailjet.com', 'smtp.gmail.com', '', None,
])
def test_un_serveur_distant_n_est_pas_un_relais_local(hote):
    assert _est_un_relais_local(hote) is False


# ═══════════════════════════════════════════════════════════════════════════
#  Le message de la page de test
# ═══════════════════════════════════════════════════════════════════════════

def _reglages(db, hote, port):
    from apps.core.models import ReglagesMail

    reglages = ReglagesMail.get_global()
    reglages.actif = True
    reglages.hote = hote
    reglages.port = port
    reglages.chiffrement = 'aucun' if port == 25 else 'tls'
    reglages.adresse_expediteur = 'no-reply@orion.test'
    reglages.save()
    return reglages


@pytest.fixture
def envoi_qui_reussit(monkeypatch):
    """Un envoi accepté, sans toucher à un vrai serveur.

    On remplace `connexion_smtp` et non `send_mail` : c'est bien le chemin
    réel de `tester_l_envoi` qu'on veut parcourir, jusqu'au message qu'il
    compose — c'est ce message qui portait le défaut.
    """
    from django.core.mail.backends.locmem import EmailBackend

    from apps.core import mail as module_mail

    monkeypatch.setattr(module_mail, 'connexion_smtp',
                        lambda reglages, fail_silently=False: EmailBackend())


@pytest.mark.django_db
def test_un_relais_local_ne_dit_pas_message_envoye(db, envoi_qui_reussit):
    """LE DÉFAUT CORRIGÉ.

    L'ancien message disait « Message envoyé à … », puis conseillait de
    regarder les indésirables. Il envoyait donc chercher la panne dans la
    boîte du destinataire, alors que rien n'avait quitté le serveur.
    """
    from apps.core.mail import tester_l_envoi

    reussi, message = tester_l_envoi('essai@orion.test',
                                     _reglages(db, '127.0.0.1', 25))

    assert reussi is True
    assert 'ACCEPTÉ' in message
    assert 'file' in message.lower(), message
    assert 'port 25 sortant' in message, message


@pytest.mark.django_db
def test_le_relais_local_renvoie_vers_la_correction(db, envoi_qui_reussit):
    """Nommer la panne sans nommer la sortie laisse l'exploitant sur place.

    La correction est de relayer par un service d'envoi, et le script le
    sait faire : le message doit donc dire où regarder.
    """
    from apps.core.mail import tester_l_envoi

    _, message = tester_l_envoi('essai@orion.test',
                                _reglages(db, '127.0.0.1', 25))
    assert 'RELAYHOST' in message
    assert 'setup_mail_relay' in message


@pytest.mark.django_db
def test_un_serveur_distant_garde_le_message_d_origine(db, envoi_qui_reussit):
    """La nuance ne vaut que pour un relais local.

    Avec un service d'envoi, l'acceptation est bien un engagement de
    remise : étendre l'avertissement à tous les cas le rendrait bruyant,
    donc ignoré.
    """
    from apps.core.mail import tester_l_envoi

    _, message = tester_l_envoi('essai@orion.test',
                                _reglages(db, 'smtp-relay.brevo.com', 587))
    assert 'Message envoyé' in message
    assert 'ACCEPTÉ' not in message


# ═══════════════════════════════════════════════════════════════════════════
#  Le script d'installation
# ═══════════════════════════════════════════════════════════════════════════

def _source():
    with open(SCRIPT, encoding='utf-8') as flux:
        return flux.read()


def test_le_script_existe_et_est_du_bash_valide():
    """Garde la garde : sans cela, un renommage rendrait les suivants verts.

    Ce script n'est appelé par RIEN dans le dépôt — `install.sh` se borne à
    afficher sa ligne de commande. Il n'a donc aucun appelant pour le
    casser bruyamment, et c'est précisément pour cela qu'il a besoin de
    tests.
    """
    assert os.path.isfile(SCRIPT)
    assert _source().startswith('#!/usr/bin/env bash')


def test_le_script_verifie_le_port_25_sortant():
    """CE QUI MANQUAIT, et c'était le plus coûteux.

    Le script annonçait « Terminé » après avoir installé Postfix, sans
    jamais vérifier que la machine peut joindre l'extérieur sur le port 25.
    Sur une ligne résidentielle, il installait donc un relais qui accepte
    tout et ne remet rien — en le présentant comme une réussite.
    """
    source = _source()
    assert 'gmail-smtp-in.l.google.com' in source, (
        'aucun témoin de joignabilité du port 25')
    assert 'LE PORT 25 SORTANT EST BLOQUE' in source
    assert 'NON FONCTIONNEL' in source, (
        'le script peut encore conclure « Terminé » sans remise possible')


def test_le_script_sait_relayer_par_un_service_d_envoi():
    """La seule correction praticable sans IP publique fixe.

    Le relais local garde son intérêt — la file d'attente et les réessais,
    qu'un appel direct depuis Django n'a pas — mais confie la remise à un
    service qui, lui, a le droit de parler sur le port 25.
    """
    source = _source()
    for attendu in ('RELAYHOST', 'RELAY_USER', 'RELAY_PASSWORD',
                    'smtp_sasl_password_maps', 'postmap'):
        assert attendu in source, attendu


def test_la_clef_du_service_n_est_jamais_lisible_par_tous():
    """Entre la création du fichier et un `chmod`, la clef serait exposée.

    `/etc/postfix/sasl_passwd` porte l'identifiant et la clef SMTP en
    clair. Écrit puis corrigé, il est lisible par tout le monde pendant
    l'intervalle — bref, mais suffisant sur une machine partagée.
    """
    source = _source()
    assert 'umask 077' in source
    assert 'chmod 600 /etc/postfix/sasl_passwd' in source


def test_le_mode_relais_exige_le_chiffrement():
    """`may` laisserait repartir la clef en clair si STARTTLS disparaît.

    Un intermédiaire qui supprime l'annonce STARTTLS suffit, et rien ne le
    signalerait. On refuse plutôt d'envoyer.
    """
    assert 'smtp_tls_security_level = encrypt' in _source()


def test_le_script_dit_quoi_remplir_dans_l_erp():
    """Installer le relais ne configure pas l'ERP, et l'écran resterait muet.

    Tant que `/orion-admin/courriels/` n'est pas rempli et activé, la page
    affiche « envoi désactivé » et son bouton de test est inutilisable,
    alors que les courriels partent par le repli. Deux vérités
    contradictoires à l'écran, c'est une de trop.
    """
    source = _source()
    assert '/orion-admin/courriels/' in source
    assert 'Aucun (relais local' in source


def test_le_mode_relais_ne_conseille_pas_un_spf_qui_casse_tout():
    """UNE ERREUR ACTIVE, si on gardait le conseil du mode direct.

    « v=spf1 ip4:<votre IP> -all » autoriserait VOTRE machine et
    interdirait le service d'envoi qui expédie réellement. Tous les
    courriels échoueraient SPF, et le « -all » demande explicitement au
    destinataire de les rejeter — on passerait d'« ils n'arrivent pas » à
    « ils sont rejetés », en croyant corriger.
    """
    source = _source()
    assert 'include:spf.brevo.com' in source
    assert 'celui de VOTRE SERVICE' in source


def test_une_signature_dkim_sans_enregistrement_est_signalee():
    """Elle vaut MOINS que pas de signature : elle est constatée invalide.

    En mode relais, c'est le service d'envoi qui signe. Laisser OpenDKIM
    apposer une seconde signature dont la clef publique n'est pas publiée
    ajoute un signal négatif franc.
    """
    source = _source()
    assert 'SKIP_DKIM' in source
    assert 'vaut MOINS que pas de signature' in source
