from django.conf import settings
from django.http import HttpResponseForbidden


class HAActiveNodeWriteProtectionMiddleware:
    """Refuse les écritures sur un nœud non actif (protection split-brain)."""

    SAFE_PATHS = [
        '/ha/health/',
        '/ha/public-health/',
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

        return self.get_response(request)
