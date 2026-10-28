import time
import logging

from django.conf import settings
from django.db import connection

logger = logging.getLogger('orion.performance')


class PerformanceMiddleware:
    """Mesure le temps de réponse et le nombre de requêtes SQL par requête HTTP.

    Ajoute les en-têtes X-Orion-Response-Time-ms et X-Orion-SQL-Count.
    Enregistre un PerformanceEvent pour les requêtes dépassant ORION_SLOW_REQUEST_MS.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.threshold_ms = getattr(settings, 'ORION_SLOW_REQUEST_MS', 800)

    def __call__(self, request):
        sql_before = len(connection.queries)
        t_start = time.monotonic()

        response = self.get_response(request)

        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        sql_count  = len(connection.queries) - sql_before

        response['X-Orion-Response-Time-ms'] = str(elapsed_ms)
        response['X-Orion-SQL-Count']        = str(sql_count)

        if elapsed_ms >= self.threshold_ms:
            self._log_slow(request, response, elapsed_ms, sql_count)

        return response

    def _log_slow(self, request, response, elapsed_ms, sql_count):
        logger.warning(
            'SLOW %s %s — %dms — %d SQL — status %s',
            request.method,
            request.path,
            elapsed_ms,
            sql_count,
            response.status_code,
        )
        try:
            from apps.performance_monitor.models import PerformanceEvent
            user = getattr(request, 'user', None)
            company = getattr(request, 'current_company', None)
            PerformanceEvent.objects.create(
                path=request.path[:500],
                method=request.method,
                status_code=response.status_code,
                response_ms=elapsed_ms,
                sql_count=sql_count,
                user_id=user.pk if user and user.is_authenticated else None,
                company_id=company.pk if company else None,
                level='slow',
            )
        except Exception:
            pass
