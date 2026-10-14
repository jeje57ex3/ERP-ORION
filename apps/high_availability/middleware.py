from django.conf import settings
from django.http import HttpResponseForbidden


class HAActiveNodeWriteProtectionMiddleware:
    """Refuse les écritures sur un nœud non actif (protection split-brain)."""

    SAFE_PATHS = [
        '/ha/health/',
        '/ha/public-health/',
        # La validation reciproque est un POST, et le candidat est par
        # definition un noeud NON actif : sans cette exemption il se
        # verrait refuser sa propre adhesion a la grappe.
        '/ha/join-check/',
        # Le vote d'election est un POST qui ECRIT (une voix par epoque,
        # persistee avant d'etre annoncee), et il est adresse a des noeuds
        # NON actifs par definition -- c'est tout l'objet d'une election.
        # Sans cette exemption, aucun serveur ne pourrait voter, chaque
        # candidat resterait sans majorite, et la bascule automatique serait
        # inerte tout en paraissant active.
        '/ha/vote/',
        '/orion-admin/ha/',
        '/admin/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, 'ORION_HA_ENABLED', False):
            return self.get_response(request)

        if request.method not in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return self.get_response(request)

        if any(request.path.startswith(p) for p in self.SAFE_PATHS):
            return self.get_response(request)

        from apps.high_availability.models import OrionHASettings, OrionHAClusterLock

        settings_obj = OrionHASettings.get_solo()
        if not settings_obj.split_brain_protection_enabled:
            return self.get_response(request)

        lock = OrionHAClusterLock.get_lock()
        current_node_id = getattr(settings, 'ORION_NODE_ID', 'orion-primary')
        if lock.active_node_id != current_node_id:
            return HttpResponseForbidden(
                "Ce serveur Orion n'est pas le nœud actif. Écriture refusée."
            )

        # Etre le noeud actif ne suffit pas : encore faut-il voir une majorite
        # de la grappe. Un serveur actif isole par une coupure reseau continue
        # sinon d'accepter des ecritures, pendant que la majorite en elit
        # legitimement un autre -- deux serveurs ecrivent alors, et c'est la
        # divergence par un autre chemin que celui que l'election ferme.
        # Pose et leve par election.verifier_quorum_local, au balayage de
        # sante.
        if settings_obj.quorum_perdu:
            return HttpResponseForbidden(
                "Ce serveur Orion ne voit plus une majorité de la grappe : "
                "écriture refusée pour éviter deux serveurs actifs. Elle "
                "reprendra automatiquement au retour de la majorité."
            )

        return self.get_response(request)
