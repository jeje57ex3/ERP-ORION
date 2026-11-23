# -*- coding: utf-8 -*-
"""La page des courriels doit dire l'état COURANT, et nommer la vraie cause.

**CE QUI S'EST PASSÉ LE 23/11/2026.** Un exploitant configure IONOS
(`smtp.ionos.fr:465`), le test échoue :

    SMTPSenderRefused: (550, b'Requested action not taken: mailbox
    unavailable\\nSender address is not allowed.', 'no-reply@orion-erp.local')

Il corrige l'adresse d'expédition — `no.reply@s-peace.com` — enregistre, et
relit **le même message, nommant l'ancienne adresse**. Il en conclut, très
logiquement, que l'ERP ignore sa saisie.

Elle était pourtant bien enregistrée. Le défaut était double :

1. **Le diagnostic n'était jamais oublié.** La page affiche
   `dernier_test_le` et `derniere_erreur` tels quels, et `_enregistrer` ne
   les touchait pas. Un verdict rendu sur des réglages qui ont changé depuis
   ne décrit plus rien — et le garder affiché est pire que ne rien
   afficher : il envoie chercher une panne qui vient peut-être d'être
   réparée.

2. **Le repli de l'expéditeur ne peut JAMAIS marcher.**
   `adresse_expediteur` est facultative et retombe sur
   `DEFAULT_FROM_EMAIL`, dont le défaut de `base.py` est
   « no-reply@orion-erp.local ». `.local` est réservé au mDNS : aucun
   fournisseur ne l'acceptera. Et le 550 renvoyé parle de « mailbox
   unavailable », ce qui se lit comme un problème de BOÎTE DESTINATAIRE et
   envoie vérifier le mot de passe, le port, le chiffrement — tout sauf le
   champ resté vide.
"""
import smtplib

import pytest
from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Company, ReglagesMail

pytestmark = pytest.mark.django_db


# ═══════════════════════════════════════════════════════════════════════════
#  Décor
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def entreprise(db):
    from apps.core import middleware
    middleware._setup_complete_cache = None
    societe = Company.objects.create(name='Elysiums', slug='elysiums-mail')
    yield societe
    middleware._setup_complete_cache = None


@pytest.fixture
def exploitant(db, client, entreprise):
    """La page est réservée au superadmin (`user_is_super_admin`)."""
    utilisateur = User.objects.create_superuser(
        username='exploitant-mail', email='ops@elysiums.test',
        password='tourbillon-de-sable-91')
    utilisateur.profile.companies.add(entreprise)
    utilisateur.profile.current_company = entreprise
    utilisateur.profile.save()
    client.force_login(utilisateur)
    return client


@pytest.fixture
def reglages_en_echec(db):
    """Des réglages IONOS portant l'échec du 23/11, comme sur l'appliance."""
    reglages = ReglagesMail.get_global()
    reglages.actif = True
    reglages.hote = 'smtp.ionos.fr'
    reglages.port = 465
    reglages.chiffrement = 'ssl'
    reglages.utilisateur = 'no.reply@s-peace.com'
    reglages.adresse_expediteur = ''
    reglages.dernier_test_le = timezone.now()
    reglages.dernier_test_reussi = False
    reglages.derniere_erreur = (
        "SMTPSenderRefused: (550, b'Sender address is not allowed.', "
        "'no-reply@orion-erp.local')")
    reglages.save()
    return reglages


def _formulaire(reglages, **modifications):
    """Le POST que la page envoie, repris de son gabarit."""
    donnees = {
        'action': 'enregistrer',
        'hote': reglages.hote,
        'port': str(reglages.port),
        'chiffrement': reglages.chiffrement,
        'delai_secondes': str(reglages.delai_secondes),
        'utilisateur': reglages.utilisateur,
        'adresse_expediteur': reglages.adresse_expediteur,
        'mot_de_passe': '',
    }
    if reglages.actif:
        donnees['actif'] = 'on'
    donnees.update(modifications)
    return donnees


# ═══════════════════════════════════════════════════════════════════════════
#  1. Un diagnostic périmé est oublié
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(ALLOWED_HOSTS=['testserver'])
def test_corriger_l_expediteur_efface_le_verdict_precedent(
        exploitant, reglages_en_echec):
    """LE DÉFAUT EXACT QU'ON A RENCONTRÉ.

    L'exploitant corrige l'adresse et relisait le même échec nommant
    l'ancienne. Il doit maintenant voir « aucune tentative depuis la
    dernière modification ».
    """
    exploitant.post(
        reverse('core_mail:reglages'),
        _formulaire(reglages_en_echec,
                    adresse_expediteur='no.reply@s-peace.com'))

    reglages_en_echec.refresh_from_db()
    assert reglages_en_echec.adresse_expediteur == 'no.reply@s-peace.com', (
        'la saisie n’a pas été enregistrée')
    assert reglages_en_echec.derniere_erreur == '', (
        'l’ancien message d’échec est toujours affiché')
    assert reglages_en_echec.dernier_test_le is None
    assert reglages_en_echec.dernier_test_reussi is None


@override_settings(ALLOWED_HOSTS=['testserver'])
def test_la_page_ne_montre_plus_l_ancienne_adresse(exploitant,
                                                   reglages_en_echec):
    """Mesuré sur le HTML rendu, parce que c'est ce que l'exploitant lit."""
    exploitant.post(
        reverse('core_mail:reglages'),
        _formulaire(reglages_en_echec,
                    adresse_expediteur='no.reply@s-peace.com'))

    corps = exploitant.get(reverse('core_mail:reglages')).content.decode()
    assert 'no-reply@orion-erp.local' not in corps
    assert 'no.reply@s-peace.com' in corps


@override_settings(ALLOWED_HOSTS=['testserver'])
def test_un_enregistrement_sans_changement_garde_le_verdict(
        exploitant, reglages_en_echec):
    """L'oubli ne doit pas être systématique.

    Rouvrir la page et enregistrer sans rien toucher ne change pas les
    réglages : le verdict les décrit toujours, et l'effacer ferait perdre
    le seul indice disponible sur une panne réelle.
    """
    exploitant.post(reverse('core_mail:reglages'),
                    _formulaire(reglages_en_echec))

    reglages_en_echec.refresh_from_db()
    assert reglages_en_echec.derniere_erreur != ''
    assert reglages_en_echec.dernier_test_le is not None


@override_settings(ALLOWED_HOSTS=['testserver'])
@pytest.mark.parametrize('champ,valeur', [
    ('hote', 'smtp-relay.brevo.com'),
    ('port', '587'),
    ('chiffrement', 'tls'),
    ('utilisateur', 'autre@s-peace.com'),
    ('adresse_expediteur', 'no.reply@s-peace.com'),
    ('delai_secondes', '30'),
])
def test_chaque_champ_qui_decide_perime_le_verdict(exploitant,
                                                   reglages_en_echec,
                                                   champ, valeur):
    """Tous les champs dont dépend le sort d'un envoi, pas seulement l'un.

    Une version qui n'aurait regardé que `adresse_expediteur` aurait laissé
    le même piège sur le port et le chiffrement — précisément les deux
    qu'on corrige quand on cherche au mauvais endroit.
    """
    exploitant.post(reverse('core_mail:reglages'),
                    _formulaire(reglages_en_echec, **{champ: valeur}))

    reglages_en_echec.refresh_from_db()
    assert reglages_en_echec.derniere_erreur == '', champ


@override_settings(ALLOWED_HOSTS=['testserver'])
def test_decocher_l_envoi_perime_aussi_le_verdict(exploitant,
                                                  reglages_en_echec):
    """`actif` décide s'il part quoi que ce soit : c'est un champ qui décide."""
    donnees = _formulaire(reglages_en_echec)
    donnees.pop('actif')
    exploitant.post(reverse('core_mail:reglages'), donnees)

    reglages_en_echec.refresh_from_db()
    assert reglages_en_echec.actif is False
    assert reglages_en_echec.derniere_erreur == ''


# ═══════════════════════════════════════════════════════════════════════════
#  2. Un expéditeur non routable est refusé AVANT la connexion
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize('adresse', [
    'no-reply@orion-erp.local',
    'no-reply@localhost',
    'orion@machine.localdomain',
    'x@exemple.invalid',
    '',
    'pas-une-adresse',
])
def test_ces_expediteurs_ne_peuvent_jamais_marcher(adresse):
    from apps.core.mail import _expediteur_inutilisable

    motif = _expediteur_inutilisable(adresse, 'smtp.ionos.fr')
    assert motif, adresse
    assert 'Adresse d’expédition' in motif, (
        'le motif ne nomme pas le champ à remplir')


@pytest.mark.parametrize('adresse', [
    'no.reply@s-peace.com',
    'contact@elysiums.fr',
    'devis@sparkling-peace.pt',
])
def test_une_vraie_adresse_passe(adresse):
    from apps.core.mail import _expediteur_inutilisable

    assert _expediteur_inutilisable(adresse, 'smtp.ionos.fr') == ''


def test_un_relais_local_accepte_n_importe_quel_expediteur():
    """Postfix sur 127.0.0.1 accepte tout et réécrit souvent le domaine.

    Refuser ici casserait une installation qui marche — et c'est le genre
    de contrôle trop zélé qu'on finit par désactiver entièrement.
    """
    from apps.core.mail import _expediteur_inutilisable

    assert _expediteur_inutilisable('no-reply@orion-erp.local',
                                    '127.0.0.1') == ''
    assert _expediteur_inutilisable('', 'localhost') == ''


@override_settings(ALLOWED_HOSTS=['testserver'])
def test_le_test_refuse_sans_ouvrir_la_connexion(reglages_en_echec,
                                                 monkeypatch):
    """Mieux vaut un refus qui dit quoi faire qu'un 550 qui dit où.

    On vérifie aussi qu'AUCUNE connexion n'est tentée : attendre le refus
    du serveur fait patienter l'exploitant pour une réponse qu'on connaît
    déjà.
    """
    from apps.core import mail as module_mail
    from apps.core.mail import tester_l_envoi

    appels = []
    monkeypatch.setattr(module_mail, 'connexion_smtp',
                        lambda *a, **k: appels.append(1))

    reussi, motif = tester_l_envoi('essai@s-peace.com',
                                   reglages=reglages_en_echec)

    assert reussi is False
    assert appels == [], 'une connexion SMTP a été ouverte malgré tout'
    assert 'orion-erp.local' in motif


@override_settings(ALLOWED_HOSTS=['testserver'])
def test_l_avertissement_apparait_des_l_enregistrement(exploitant,
                                                       reglages_en_echec):
    """On ne teste pas toujours tout de suite, et un envoi réel peut partir
    avant : le dire à l'enregistrement, pas seulement au test."""
    reponse = exploitant.post(
        reverse('core_mail:reglages'),
        _formulaire(reglages_en_echec, adresse_expediteur=''),
        follow=True)

    corps = reponse.content.decode()
    assert 'n’est pas un domaine routable' in corps


# ═══════════════════════════════════════════════════════════════════════════
#  3. L'erreur du serveur est traduite en cause
# ═══════════════════════════════════════════════════════════════════════════

def test_le_550_de_ionos_nomme_l_expediteur_et_le_remede():
    """« mailbox unavailable » se lit comme un problème de DESTINATAIRE.

    C'est pourtant l'EXPÉDITEUR que le serveur refuse. Sans traduction, on
    cherche la panne du mauvais côté — et c'est exactement ce qui est
    arrivé.
    """
    from apps.core.mail import _motif_lisible

    exc = smtplib.SMTPSenderRefused(
        550, b'Requested action not taken: mailbox unavailable\n'
             b'Sender address is not allowed.',
        'no-reply@orion-erp.local')
    motif = _motif_lisible(exc)

    assert 'refuse d’expédier au nom de' in motif
    assert 'no-reply@orion-erp.local' in motif
    assert 'Adresse d’expédition' in motif


def test_le_texte_brut_du_serveur_est_conserve():
    """Retirer la réponse du serveur remplacerait une erreur illisible par
    une erreur imprécise. Elle reste, précédée de la cause."""
    from apps.core.mail import _motif_lisible

    exc = smtplib.SMTPSenderRefused(550, b'Sender address is not allowed.',
                                    'x@y.local')
    assert 'SMTPSenderRefused' in _motif_lisible(exc)


def test_l_authentification_refusee_parle_de_mot_de_passe_d_application():
    """Chez plusieurs fournisseurs, le mot de passe du courriel ne suffit
    pas — et on cherche longtemps avant d'y penser."""
    from apps.core.mail import _motif_lisible

    exc = smtplib.SMTPAuthenticationError(535, b'Authentication credentials invalid')
    motif = _motif_lisible(exc)
    assert 'mot de passe d’application' in motif


def test_un_delai_depasse_renvoie_vers_le_port_et_le_chiffrement():
    """465 et 587 confondus donnent précisément une attente sans réponse."""
    from apps.core.mail import _motif_lisible

    motif = _motif_lisible(TimeoutError('timed out'))
    assert '587' in motif and '465' in motif


def test_une_erreur_inconnue_reste_lisible_telle_quelle():
    """La traduction ne doit pas avaler ce qu'elle ne reconnaît pas."""
    from apps.core.mail import _motif_lisible

    motif = _motif_lisible(ValueError('quelque chose d’inattendu'))
    assert 'ValueError' in motif
    assert 'inattendu' in motif


def test_les_envois_reels_emploient_la_meme_traduction():
    """Deux formulations pour une même cause feraient croire à deux pannes.

    L'échec d'un envoi réel est lu sur la MÊME page que celui du bouton de
    test.
    """
    import inspect

    from apps.core.mail import BackendMailOrion

    source = inspect.getsource(BackendMailOrion._noter_l_echec)
    assert '_motif_lisible(exc)' in source
