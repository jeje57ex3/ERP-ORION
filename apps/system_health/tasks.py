"""
apps/system_health/tasks.py — Tâches Celery de collecte des capteurs.
"""
import logging
from celery import shared_task

logger = logging.getLogger('system_health')


@shared_task(name='system_health.collect_all_sensors', bind=True, max_retries=2)
def collect_all_sensors(self):
    """
    Collecte tous les capteurs, calcule le score global, enregistre un snapshot,
    et déclenche les alertes automatiques si nécessaire.
    Planifié toutes les 5 minutes via Celery Beat.
    """
    from . import services
    from .models import HealthSnapshot

    try:
        # 1. Récupérer l'état précédent avant d'écraser les lectures
        last_snapshot = HealthSnapshot.objects.order_by('-collected_at').first()
        prev_criticals = last_snapshot.critical_sensors if last_snapshot else []

        # 2. Collecter tous les capteurs
        services.collect_server_sensors()
        services.collect_app_sensors()
        services.collect_db_sensors()
        services.collect_backup_sensors()
        services.collect_security_sensors()
        services.collect_celery_sensors()

        # 3. Calculer le score global
        health = services.compute_global_health()

        # 4. Enregistrer le snapshot
        services.save_health_snapshot(health)

        # 5. Vérifier et déclencher les alertes automatiques
        services.check_and_alert(prev_criticals, health)

        logger.info(
            'system_health collected: global=%d/100 (%s) — criticals=%s',
            health['score'], health['status'], health.get('critical', [])
        )
        return {
            'score': health['score'],
            'status': health['status'],
            'breakdown': health['breakdown'],
        }

    except Exception as exc:
        logger.exception('collect_all_sensors failed: %s', exc)
        raise self.retry(exc=exc, countdown=60)


@shared_task(name='system_health.purge_old_sensor_readings')
def purge_old_sensor_readings(days=90):
    """Purge les lectures de capteurs et snapshots anciens."""
    from . import services
    deleted_readings = services.purge_old_sensor_readings(days=days)
    deleted_snapshots = services.purge_old_snapshots(days=30)
    return {'deleted_readings': deleted_readings, 'deleted_snapshots': deleted_snapshots}


# ─── Stockage : déplacer des fichiers sans bloquer la page ───────────────────
#
# Pourquoi des tâches de fond. Copier un dossier de médias prend des
# minutes, parfois des heures. Le faire dans la requête HTTP donnerait un
# délai d'attente de gunicorn, et surtout : une copie interrompue au
# mauvais moment laisse des fichiers à moitié écrits. Ici la copie survit
# à la fermeture de l'onglet, et son avancement est lisible en base.
#
# La fréquence d'écriture de l'avancement est bornée (RYTHME_D_ECRITURE) :
# un UPDATE par fichier sur 200 000 fichiers ferait de la base le goulet
# d'étranglement de la copie.

RYTHME_D_ECRITURE = 2.0   # secondes entre deux enregistrements d'avancement


def _executer_l_operation(operation_id, travail):
    """Encadre une opération : états, horodatages, journal, erreurs.

    Tout passe par ici pour qu'aucune tâche ne puisse laisser une
    opération bloquée en « en_cours » après une exception — un état
    d'attente éternel qu'aucune interface ne sait expliquer.
    """
    from django.utils import timezone
    from .models import OperationDeStockage

    operation = OperationDeStockage.objects.filter(pk=operation_id).first()
    if operation is None:
        logger.warning('Opération de stockage %s introuvable.', operation_id)
        return {'ok': False, 'erreur': 'Opération introuvable.'}

    if operation.etat not in ('en_attente',):
        # Deja traitee : Celery peut relivrer un message, et refaire une
        # copie par-dessus une bascule deja faite serait destructeur.
        return {'ok': False, 'erreur': f'Déjà à l\'état {operation.etat}.'}

    operation.etat = 'en_cours'
    operation.debute_le = timezone.now()
    operation.ajouter_au_journal('Démarrage.')
    operation.save(update_fields=['etat', 'debute_le', 'journal'])

    try:
        resultat = travail(operation)
    except Exception as exc:                        # noqa: BLE001
        logger.exception('Opération de stockage %s en échec', operation_id)
        operation.refresh_from_db(fields=['journal'])
        operation.etat = 'echouee'
        operation.message = str(exc)[:300]
        operation.fini_le = timezone.now()
        operation.ajouter_au_journal(f'ÉCHEC : {exc}')
        operation.save(update_fields=['etat', 'message', 'fini_le',
                                      'journal'])
        return {'ok': False, 'erreur': str(exc)}

    operation.fini_le = timezone.now()
    operation.save()
    return {'ok': True, **(resultat or {})}


@shared_task(name='system_health.preparer_un_disque')
def preparer_un_disque(operation_id):
    """Partitionne, formate et monte un disque, via l'assistant root."""
    from . import stockage_privilegie

    def travail(operation):
        operation.ajouter_au_journal(
            f'Préparation de {operation.peripherique}.')
        resultat = stockage_privilegie.preparer_un_disque(
            operation.peripherique,
            operation.volume_cible,
            effacer=True,
            numero_de_serie=operation.message)
        for ligne in resultat.get('journal', []):
            operation.ajouter_au_journal(ligne)
        operation.volume_cible = resultat.get('point_de_montage', '')
        operation.etat = 'terminee'
        operation.message = (f'Disque prêt et monté sur '
                             f'{operation.volume_cible}.')[:300]
        return {'point_de_montage': operation.volume_cible}

    return _executer_l_operation(operation_id, travail)


@shared_task(name='system_health.basculer_une_categorie')
def basculer_une_categorie(operation_id):
    """Fait pointer une catégorie vers un autre disque, sans rien copier."""
    import os

    from . import stockage_actions

    def travail(operation):
        if not os.path.isdir(operation.chemin_cible):
            os.makedirs(operation.chemin_cible, exist_ok=True)
            operation.ajouter_au_journal(
                f'Dossier créé : {operation.chemin_cible}.')

        ancien = stockage_actions.basculer(operation.categorie,
                                           operation.chemin_cible)
        operation.ajouter_au_journal(
            f'{operation.categorie} pointe désormais sur '
            f'{operation.chemin_cible}.')
        if ancien:
            operation.chemin_source = ancien
            operation.ajouter_au_journal(
                f'Ancien dossier conservé sous {ancien} — rien n\'a été '
                f'supprimé.')
        operation.etat = 'terminee'
        operation.message = (
            'Les nouveaux fichiers vont sur le disque choisi. Les anciens '
            'restent où ils sont.')[:300]
        return {'ancien_dossier': ancien}

    return _executer_l_operation(operation_id, travail)


@shared_task(name='system_health.copier_puis_basculer')
def copier_puis_basculer(operation_id):
    """Copie, vérifie, puis bascule — sans jamais supprimer la source.

    S'arrête à l'état « verifiee » : l'ancien emplacement est intact et sa
    suppression demande une action séparée de l'utilisateur. Enchaîner la
    suppression ferait de la moindre erreur une perte de données.
    """
    import os
    import time

    from . import stockage_actions

    def travail(operation):
        source = stockage_actions.cible_actuelle(operation.categorie)
        operation.chemin_source = source
        operation.ajouter_au_journal(f'Source : {source}.')

        nombre, octets = stockage_actions.inventaire(source)
        operation.fichiers_total = nombre
        operation.octets_total = octets
        operation.ajouter_au_journal(
            f'{nombre} fichier(s), {octets / 1e9:.2f} Go à copier.')
        operation.save(update_fields=['chemin_source', 'fichiers_total',
                                      'octets_total', 'journal'])

        stockage_actions.verifier_la_place(operation.volume_cible, octets)
        os.makedirs(operation.chemin_cible, exist_ok=True)

        dernier = [time.monotonic()]

        def avancement(fichiers_faits, octets_faits, _relatif):
            maintenant = time.monotonic()
            if maintenant - dernier[0] < RYTHME_D_ECRITURE:
                return
            dernier[0] = maintenant
            operation.fichiers_traites = fichiers_faits
            operation.octets_traites = octets_faits
            operation.save(update_fields=['fichiers_traites',
                                          'octets_traites'])

        resultat = stockage_actions.copier_avec_verification(
            source, operation.chemin_cible, rappel=avancement)

        operation.fichiers_traites = resultat['fichiers']
        operation.octets_traites = resultat['octets']

        if resultat['erreurs']:
            # Ne PAS basculer : basculer apres une copie incomplete
            # rendrait des fichiers introuvables a l'application.
            for ligne in resultat['erreurs'][:50]:
                operation.ajouter_au_journal(ligne)
            raise stockage_actions.ErreurDeStockage(
                f'{len(resultat["erreurs"])} fichier(s) n\'ont pas été '
                f'copiés correctement. Rien n\'a été basculé, l\'ancien '
                f'emplacement reste en service.')

        operation.ajouter_au_journal(
            f'{resultat["fichiers"]} fichier(s) copiés et relus sans écart.')

        ancien = stockage_actions.basculer(operation.categorie,
                                           operation.chemin_cible)
        operation.ajouter_au_journal(
            f'{operation.categorie} pointe désormais sur '
            f'{operation.chemin_cible}.')
        if ancien:
            operation.chemin_source = ancien
            operation.ajouter_au_journal(
                f'Ancien emplacement écarté sous {ancien}.')

        operation.etat = 'verifiee'
        operation.message = (
            'Copie vérifiée et bascule faite. L\'ancien emplacement est '
            'conservé : sa suppression vous appartient.')[:300]
        return {'ancien_dossier': ancien}

    return _executer_l_operation(operation_id, travail)


@shared_task(name='system_health.supprimer_l_ancien_emplacement')
def supprimer_l_ancien_emplacement(operation_id):
    """Supprime un ancien emplacement, sur demande explicite."""
    from . import stockage_actions

    def travail(operation):
        resultat = stockage_actions.supprimer_source(operation.chemin_source,
                                                      operation.categorie)
        operation.ajouter_au_journal(
            f'{resultat["fichiers"]} fichier(s) supprimés, '
            f'{resultat["octets"] / 1e9:.2f} Go libérés.')
        operation.etat = 'terminee'
        operation.message = (
            f'{resultat["octets"] / 1e9:.2f} Go libérés.')[:300]
        return resultat

    return _executer_l_operation(operation_id, travail)
