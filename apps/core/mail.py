"""apps/core/mail.py — L'envoi des courriels, réglable depuis l'interface.

POURQUOI UN BACKEND À NOUS

Django lit EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER et EMAIL_HOST_PASSWORD
dans les settings, c'est-à-dire dans `/opt/orion/backend/.env`, une seule
fois au démarrage de gunicorn. Changer de serveur SMTP demandait donc un
accès SSH, une édition de fichier et un redémarrage de service.

Ce backend lit les réglages EN BASE (core.ReglagesMail) à chaque envoi, ce
qui les rend modifiables depuis /orion-admin/courriels/ sans terminal et
sans redémarrage. Quand aucun réglage n'est actif, il délègue au backend de
repli, de sorte que le comportement d'avant est conservé par défaut.

TROIS PRÉCAUTIONS QUI ONT CHACUNE LEUR RAISON

1. `open()` et `close()` délèguent vraiment. apps/system_observability
   diagnostique le courriel en faisant `get_connection()`, `conn.open()`,
   `conn.close()`. Un `open()` vide — l'implémentation par défaut de
   BaseEmailBackend — aurait rendu ce contrôle toujours vert, donc menteur.

2. Le délégué est toujours construit avec `fail_silently=False`, et c'est
   CE module qui avale l'erreur si l'appelant l'a demandé. Sinon l'échec
   était absorbé à l'intérieur de Django et n'atteignait aucun journal :
   quatre appels du dépôt passent `fail_silently=True`, dont l'invitation
   au portail client et la réinitialisation de mot de passe des boutiques.
   « Les mails ne fonctionnent pas » sans le moindre message vient de là.

3. Le motif de l'échec est écrit sur la ligne de réglages, pour qu'il
   survive à la requête qui l'a rencontré. Un envoi déclenché par une tâche
   de fond échoue loin de tout écran ; sans cette trace, personne ne saura
   jamais pourquoi.
"""
import logging

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.utils.module_loading import import_string

journal = logging.getLogger('orion')

BACKEND_SMTP = 'django.core.mail.backends.smtp.EmailBackend'


def reglages_utilisables():
    """Les réglages en base s'ils permettent de tenter un envoi, sinon None."""
    from apps.core.models import ReglagesMail

    reglages = ReglagesMail.courants()
    if reglages is not None and reglages.utilisable:
        return reglages
    return None


def cle_de_chiffrement_presente():
    """Peut-on chiffrer un mot de passe sur cette installation ?

    ORION_SECRET_ENCRYPTION_KEY est generee au provisioning de l'appliance,
    mais vaut '' par defaut : sur un poste de developpement ou une
    installation faite a la main, `get_fernet()` leve une RuntimeError. La
    page doit alors le DIRE -- « mot de passe non enregistre » sans motif
    enverrait chercher une faute de frappe la ou il manque une cle.
    """
    return bool(getattr(settings, 'ORION_SECRET_ENCRYPTION_KEY', ''))


def chemin_du_repli():
    """Le backend utilisé quand aucun réglage n'est actif en base.

    Par défaut le SMTP de Django, qui lit le .env comme avant. La clé
    EMAIL_BACKEND du .env gouverne cette valeur : elle y était documentée
    depuis toujours et rien ne la lisait — production.py écrasait le backend
    en dur. Un opérateur qui y pose le backend « console » obtient enfin ce
    qu'il a demandé.
    """
    return getattr(settings, 'ORION_MAIL_BACKEND_DE_REPLI', BACKEND_SMTP)


def connexion_smtp(reglages, fail_silently=False):
    """Un backend SMTP Django construit sur les réglages en base."""
    from django.core.mail.backends.smtp import EmailBackend

    return EmailBackend(
        host=reglages.hote,
        port=reglages.port,
        username=reglages.utilisateur or None,
        password=reglages.mot_de_passe or None,
        use_tls=reglages.use_tls,
        use_ssl=reglages.use_ssl,
        timeout=reglages.delai_secondes or None,
        fail_silently=fail_silently,
    )


class BackendMailOrion(BaseEmailBackend):
    """Envoie par les réglages de l'interface, ou par le repli."""

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self._kwargs = kwargs
        self._delegue = None
        self._reglages = None

    # ── Choix du délégué ────────────────────────────────────────────────────

    def _construire_le_delegue(self):
        """Toujours `fail_silently=False` : c'est nous qui décidons d'avaler.

        Si on transmettait fail_silently au délégué, Django absorberait
        l'exception à l'intérieur de son propre send_messages et nous ne
        verrions jamais passer l'erreur — donc rien à journaliser et rien à
        montrer dans l'interface.
        """
        self._reglages = reglages_utilisables()
        if self._reglages is not None:
            return connexion_smtp(self._reglages, fail_silently=False)

        classe = import_string(chemin_du_repli())
        return classe(fail_silently=False, **self._kwargs)

    def _obtenir_le_delegue(self):
        if self._delegue is None:
            self._delegue = self._construire_le_delegue()
        return self._delegue

    # ── Cycle de vie : délégué, pour que le diagnostic reste honnête ────────

    def open(self):
        return self._obtenir_le_delegue().open()

    def close(self):
        if self._delegue is None:
            return None
        try:
            return self._delegue.close()
        finally:
            self._delegue = None

    # ── Envoi ───────────────────────────────────────────────────────────────

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        messages = list(email_messages)
        delegue = self._obtenir_le_delegue()
        self._appliquer_l_expediteur(messages)

        try:
            envoyes = delegue.send_messages(messages)
        except Exception as exc:
            self._noter_l_echec(exc, len(messages))
            if self.fail_silently:
                return 0
            raise

        return envoyes or 0

    def _appliquer_l_expediteur(self, messages):
        """Remplace l'adresse d'expédition SEULEMENT quand elle est le défaut.

        Les boutiques composent déjà leur expéditeur par marque
        (« no-reply@siecle.fr »). Écraser cela mettrait toutes les marques
        sous une seule adresse. On ne touche donc qu'aux messages qui n'ont
        rien choisi : adresse vide, ou égale à DEFAULT_FROM_EMAIL.
        """
        reglages = self._reglages
        if reglages is None or not reglages.adresse_expediteur:
            return

        defaut = getattr(settings, 'DEFAULT_FROM_EMAIL', '')
        for message in messages:
            actuelle = getattr(message, 'from_email', '') or ''
            if not actuelle or actuelle == defaut:
                message.from_email = reglages.adresse_expediteur

    def _noter_l_echec(self, exc, nombre):
        """Journalise, puis garde le motif là où l'interface le montrera."""
        journal.warning(
            'Envoi de %s courriel(s) en echec : %s: %s',
            nombre, type(exc).__name__, exc,
        )
        noter_le_resultat(False, f'{type(exc).__name__}: {exc}')


def noter_le_resultat(reussi, message=''):
    """Écrit le dernier diagnostic sur la ligne de réglages.

    Avale ses erreurs : un échec d'écriture ici ne doit pas remplacer
    l'erreur d'envoi qu'on essaie justement de rendre visible, ni faire
    tomber une page. Le cas réel est la table absente entre le déploiement
    du code et l'application de la migration.
    """
    from django.utils import timezone
    from apps.core.models import ReglagesMail

    try:
        reglages = ReglagesMail.courants()
        if reglages is None:
            return
        ReglagesMail.objects.filter(pk=reglages.pk).update(
            dernier_test_le=timezone.now(),
            dernier_test_reussi=bool(reussi),
            derniere_erreur=(message or '')[:2000],
        )
    except Exception:
        pass


# ── Le bouton « envoyer un test » ───────────────────────────────────────────

def tester_l_envoi(destinataire, reglages=None):
    """Tente un vrai envoi et rend (reussi, message lisible).

    On n'attrape pas l'erreur pour la cacher : on la rend, mot pour mot, à
    la page. Un « échec de connexion SMTP » sans le texte du serveur est
    inutilisable — c'est toute la différence entre « ça ne marche pas » et
    « authentification refusée », « nom de serveur introuvable » ou
    « certificat expiré ».
    """
    from django.core.mail import EmailMessage
    from apps.core.models import ReglagesMail

    if reglages is None:
        reglages = ReglagesMail.get_global()

    if not destinataire:
        return False, 'Indiquez une adresse de destination pour le test.'

    if not reglages.hote:
        return False, ('Aucun serveur SMTP renseigné. Remplissez le serveur '
                       'et le port avant de tester.')

    if reglages.mot_de_passe_illisible:
        return False, (
            'Le mot de passe enregistré est illisible : la clé de chiffrement '
            'de cette installation a changé depuis son enregistrement '
            '(restauration de base avec un .env régénéré). Saisissez-le à '
            'nouveau.'
        )

    expediteur = (reglages.adresse_expediteur
                  or getattr(settings, 'DEFAULT_FROM_EMAIL', '')
                  or 'no-reply@localhost')

    # Le test court-circuite volontairement `actif` et le backend configuré :
    # on veut pouvoir essayer des reglages AVANT de les mettre en service, et
    # sans que le mode de repli (console, memoire) ne fasse passer le test
    # pour reussi alors que rien n'est parti.
    connexion = connexion_smtp(reglages, fail_silently=False)

    message = EmailMessage(
        subject='Orion ERP — test d’envoi',
        body=(
            'Ce message confirme que votre ERP sait envoyer des courriels.\n\n'
            f'Serveur : {reglages.hote}:{reglages.port}\n'
            f'Chiffrement : {reglages.get_chiffrement_display()}\n'
            f'Expéditeur : {expediteur}\n'
        ),
        from_email=expediteur,
        to=[destinataire],
        connection=connexion,
    )

    try:
        envoyes = message.send(fail_silently=False)
    except Exception as exc:
        motif = f'{type(exc).__name__}: {exc}'
        journal.warning('Test d_envoi en echec : %s', motif)
        noter_le_resultat(False, motif)
        return False, motif

    if not envoyes:
        motif = ('Le serveur a accepté la connexion mais n’a accepté aucun '
                 'destinataire.')
        noter_le_resultat(False, motif)
        return False, motif

    noter_le_resultat(True, '')
    return True, (
        f'Message envoyé à {destinataire} via {reglages.hote}:{reglages.port}. '
        'S’il n’arrive pas, regardez les indésirables : la remise dépend '
        'ensuite de vos enregistrements SPF, DKIM et DMARC.'
    )
