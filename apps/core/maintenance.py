from pathlib import Path

from django.conf import settings


def _get_maintenance_file():
    return Path(settings.BASE_DIR) / 'maintenance.lock'


def enable_maintenance_mode():
    _get_maintenance_file().write_text('maintenance', encoding='utf-8')


def disable_maintenance_mode():
    """Leve le verrou ET clot l'annonce en cours.

    Les deux ensemble, et a cet endroit precis : sinon un bandeau rouge
    survit au retour du service, fait douter de l'etat reel du serveur, et
    l'on apprend a l'ignorer. Il y a plusieurs appelants (mise a jour,
    restauration) ; les corriger un par un, c'est en oublier un.

    L'activation, elle, reste asymetrique : seul l'appelant connait le
    MOTIF, donc c'est lui qui annonce.
    """
    path = _get_maintenance_file()
    if path.exists():
        path.unlink()
    clore_annonces()


def is_maintenance_mode_enabled():
    return _get_maintenance_file().exists()


def annoncer(motif, duree_minutes=15, message='', utilisateur=None,
             dans_minutes=0):
    """Crée l'annonce qui s'affichera aux utilisateurs. Rend l'annonce ou None.

    Appelée depuis les actions réelles — mise à jour, redémarrage — pour que
    la page de maintenance dise CE QUI se passe, et non « maintenance
    programmée » quoi qu'il arrive.

    Ne lève jamais : une annonce est un confort, un redémarrage est une
    nécessité. Si la table n'existe pas encore, ou si la base ne répond
    plus, l'action doit se faire quand même — les utilisateurs verront la
    page générique plutôt que rien du tout.
    """
    from django.utils import timezone

    try:
        from apps.core.models import MaintenanceAnnonce

        # Une seule annonce a la fois : deux bandeaux simultanes diraient
        # deux choses differentes du meme evenement.
        MaintenanceAnnonce.objects.filter(active=True).update(active=False)

        return MaintenanceAnnonce.objects.create(
            motif=motif,
            message=message or '',
            debut_prevu=timezone.now() + timezone.timedelta(
                minutes=max(0, dans_minutes)),
            duree_minutes=duree_minutes,
            cree_par=utilisateur,
        )
    except Exception:
        return None


def clore_annonces():
    """Désactive les annonces en cours. Ne lève jamais.

    Appelée à la fin d'une mise à jour : un bandeau rouge qui reste après
    le retour du service fait douter de l'état réel du serveur, et on
    apprend à l'ignorer.
    """
    try:
        from apps.core.models import MaintenanceAnnonce
        MaintenanceAnnonce.objects.filter(active=True).update(active=False)
    except Exception:
        pass
