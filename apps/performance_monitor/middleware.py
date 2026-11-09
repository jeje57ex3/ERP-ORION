import logging
import random
import time

from django.conf import settings
from django.db import connection

logger = logging.getLogger('orion.performance')

# Chemins dont la mesure n'apprend rien et noierait l'echantillon.
#
# Une page de l'ERP et un fichier statique ne se comparent pas : WhiteNoise
# rend un CSS en une poignee de millisecondes, et une page en charge
# plusieurs dizaines. Les melanger ferait tomber la latence mediane a
# quelques millisecondes et masquerait completement la lenteur des pages,
# qui est la seule chose qu'on veuille voir ici.
CHEMINS_IGNORES = ('/static/', '/media/', '/favicon.ico', '/ha/health/')


class _CompteurDeRequetesSQL:
    """Compte les requetes SQL d'une requete HTTP, meme hors DEBUG.

    `len(connection.queries)` ne fonctionne QUE si DEBUG est vrai : Django
    ne remplit cette liste que dans ce cas. La version precedente de ce
    middleware s'en servait, et aurait donc affiche « 0 requete SQL » sur
    chaque ligne en production -- une colonne qui ment est pire qu'une
    colonne absente, parce qu'on la croit.

    `connection.execute_wrapper` fonctionne quel que soit DEBUG, pour un
    cout d'un appel de fonction par requete SQL.
    """

    def __init__(self):
        self.nombre = 0

    def __call__(self, execute, sql, params, many, context):
        self.nombre += 1
        return execute(sql, params, many, context)


class PerformanceMiddleware:
    """Mesure la latence du serveur et le nombre de requetes SQL.

    POURQUOI LA PAGE N'AFFICHAIT RIEN.

    Deux raisons, et la premiere suffisait. Ce middleware n'etait declare
    NULLE PART dans `MIDDLEWARE` : l'application figurait bien dans
    `INSTALLED_APPS`, son modele existait, sa vue etait correcte, son
    gabarit aussi -- mais rien ne mesurait quoi que ce soit, donc la table
    restait vide et le tableau de bord muet.

    La seconde : il n'enregistrait QUE les requetes depassant un seuil de
    800 ms. Meme branche, un ERP qui se porte bien n'aurait rien affiche du
    tout, et on en aurait conclu qu'il etait encore casse.

    D'OU L'ECHANTILLONNAGE.

    Une requete sur `ORION_PERF_SAMPLE_RATE` est enregistree telle quelle,
    rapide ou non. C'est ce qui donne une LATENCE -- mediane, 95e centile,
    maximum -- plutot qu'un simple journal des incidents. Les requetes
    lentes, elles, sont toujours enregistrees : une lenteur ne doit jamais
    dependre d'un tirage au sort.

    Enregistrer chaque requete serait plus simple et intenable : une table
    qui grossit de plusieurs dizaines de milliers de lignes par jour finit
    par couter plus cher que ce qu'elle mesure.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.seuil_lent_ms = getattr(settings, 'ORION_SLOW_REQUEST_MS', 800)
        self.taux = max(1, int(getattr(settings, 'ORION_PERF_SAMPLE_RATE', 20)))

    def __call__(self, request):
        compteur = _CompteurDeRequetesSQL()
        depart = time.monotonic()

        with connection.execute_wrapper(compteur):
            response = self.get_response(request)

        duree_ms = int((time.monotonic() - depart) * 1000)

        # Les en-tetes sont poses sur TOUTES les reponses, y compris celles
        # qu'on n'enregistre pas : ils ne coutent rien et permettent de
        # mesurer une page precise depuis le navigateur, sans attendre
        # qu'elle tombe dans l'echantillon.
        response['X-Orion-Response-Time-ms'] = str(duree_ms)
        response['X-Orion-SQL-Count'] = str(compteur.nombre)

        if self._merite_enregistrement(request, duree_ms):
            self._enregistrer(request, response, duree_ms, compteur.nombre)

        return response

    def _merite_enregistrement(self, request, duree_ms):
        chemin = request.path or ''
        if chemin.startswith(CHEMINS_IGNORES):
            return False
        if duree_ms >= self.seuil_lent_ms:
            return True
        return random.randrange(self.taux) == 0

    def _enregistrer(self, request, response, duree_ms, nombre_sql):
        lent = duree_ms >= self.seuil_lent_ms
        if lent:
            logger.warning(
                'LENT %s %s — %dms — %d SQL — statut %s',
                request.method, request.path, duree_ms, nombre_sql,
                response.status_code,
            )
        try:
            from apps.performance_monitor.models import PerformanceEvent

            utilisateur = getattr(request, 'user', None)
            entreprise = getattr(request, 'current_company', None)
            PerformanceEvent.objects.create(
                path=request.path[:500],
                method=request.method,
                status_code=response.status_code,
                response_ms=duree_ms,
                sql_count=nombre_sql,
                user_id=(utilisateur.pk
                         if utilisateur and utilisateur.is_authenticated
                         else None),
                company_id=entreprise.pk if entreprise else None,
                level='slow' if lent else 'info',
            )
        except Exception:                               # noqa: BLE001
            # Base injoignable, table absente avant migration, disque
            # plein. Mesurer la performance ne doit JAMAIS faire echouer la
            # requete qu'on mesure.
            pass
