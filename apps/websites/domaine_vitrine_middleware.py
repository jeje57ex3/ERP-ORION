"""apps/websites/domaine_vitrine_middleware.py — Servir un site à la racine de son domaine.

LE CHAÎNON QUI MANQUAIT

Un site vitrine vit sous « /sites/<slug>/… ». Brancher un domaine dessus
demandait donc quatre choses, et seules trois existaient :

  1. un enregistrement WebsiteDomain  — l'écran des domaines le crée ;
  2. un CNAME chez Cloudflare         — le « Sync DNS » du tunnel le pose ;
  3. une règle d'ingress vers Django  — l'écran du tunnel la publie ;
  4. **quelque chose qui serve la vitrine quand on demande « / »**.

Faute du quatrième, « https://s-peace.com/ » arrivait sur la racine de
l'ERP — l'écran de connexion — et non sur le site. Les trois premières
étapes pouvaient être parfaites, le résultat restait faux. C'est ce module.

COMMENT, ET POURQUOI AINSI

On RÉÉCRIT le chemin plutôt que de rediriger. Une redirection afficherait
« /sites/electricite-etancheite/etancheite/ » dans la barre d'adresse du
visiteur : le domaine qu'on vient de brancher disparaîtrait à la première
page. La réécriture garde l'adresse publique et laisse le routeur Django
travailler normalement.

Le lien domaine → site est LU EN BASE, jamais écrit en dur : brancher un
second domaine ne demandera pas de toucher au code, seulement de remplir
l'écran des domaines.

CE QU'ON NE TOUCHE PAS

Les chemins techniques (statiques, médias, API, administration) passent
sans réécriture : servir un fichier CSS depuis la vitrine n'aurait pas de
sens, et couper l'accès à l'ERP depuis un domaine mal réglé serait pire que
le défaut qu'on corrige.
"""

from django.utils.deprecation import MiddlewareMixin

from .middleware import _is_internal_host

# Les préfixes qui ne doivent JAMAIS être réécrits. L'ERP doit rester
# joignable même depuis un domaine de site mal configuré — sans quoi une
# erreur de réglage se répare... depuis l'écran devenu inaccessible.
CHEMINS_RESERVES = (
    '/static/', '/media/', '/api/', '/admin/', '/orion-admin/',
    '/accounts/', '/sites/', '/i18n/', '/__debug__/', '/health',
)


def _prefixe_public(site):
    """Le chemin sous lequel ce site est servi.

    LE TYPE D'ABORD, LE SLUG ENSUITE — ET C'EST UNE CORRECTION.

    La premiere version ne connaissait qu'un seul cas, la vitrine
    « etancheite », reconnue a son slug. Tout le reste tombait sur les vues
    publiques generiques. Un site de type « electricite » — « SPARKLING
    PEACE – Electricite », par exemple — etait donc servi par le mauvais
    dessin, sans que rien ne le signale : la page s'affichait, simplement
    ce n'etait pas la bonne.

    On s'aligne desormais sur « home_redirect » (erp_btp/urls.py), qui
    route deja par site_type a la racine. Deux endroits qui decident du
    meme routage avec des regles differentes finissent toujours par se
    contredire ; ici, le symptome aurait ete une page d'accueil correcte et
    des pages internes fausses.

    « public_slug » et non « slug » : un site sans slug retombe sur celui
    de son entreprise, et c'est ce que les adresses publiques emploient.
    """
    from .vitrine_etancheite import SLUG as SLUG_ETANCHEITE

    slug = site.public_slug

    # La vitrine etancheite a ses propres adresses, reconnues au slug : elle
    # n'a pas de site_type dedie.
    if site.slug == SLUG_ETANCHEITE:
        return f'/sites/{slug}/etancheite/'

    if site.site_type == 'electricite':
        return f'/sites/{slug}/electricite/'

    if site.site_type == 'btp':
        return f'/sites/{slug}/btp/'

    return f'/sites/{slug}/'


class VitrineParDomaineMiddleware(MiddlewareMixin):
    """Réécrit « / » vers la vitrine du site attaché à ce nom d'hôte."""

    def process_request(self, request):
        chemin = request.path_info

        if any(chemin.startswith(prefixe) for prefixe in CHEMINS_RESERVES):
            return None

        host = request.get_host()
        if _is_internal_host(host):
            return None

        # « request.website » est pose par WebsiteResolverMiddleware, qui
        # tourne avant celui-ci. On s'en sert plutot que de refaire la
        # requete : deux lectures de la meme ligne a chaque appel seraient
        # deux fois le cout pour le meme resultat.
        site = getattr(request, 'website', None)
        if site is None:
            return None

        prefixe = _prefixe_public(site)

        # Deja sous le bon prefixe : ne rien faire. Sans ce garde, une page
        # interne du site rejouerait la reecriture a chaque requete et
        # empilerait les prefixes.
        if chemin.startswith(prefixe):
            return None

        request.path_info = prefixe.rstrip('/') + chemin
        # « path » sert a l'affichage et aux comparaisons ailleurs dans
        # Django : le laisser diverger de path_info donnerait des
        # comportements qui dependent de la fonction consultee.
        request.path = request.path_info
        return None


class HotesDesSitesMiddleware(MiddlewareMixin):
    """Autorise les noms d'hôte que l'exploitant a connectés à un site.

    LE CINQUIÈME CHAÎNON

    `ALLOWED_HOSTS` est figé au provisionnement de l'appliance, à partir des
    domaines connus ce jour-là. Un domaine branché ensuite depuis l'écran
    des domaines n'y figure pas : Django répond **400 DisallowedHost** avant
    même d'atteindre la moindre vue, et le message ne parle ni du site ni du
    domaine.

    Le corriger demandait d'éditer le `.env` en SSH puis de redémarrer
    gunicorn. Une fonction d'administration qui exige un terminal n'est pas
    administrable.

    CE QUI EST AUTORISÉ, ET CE QUI NE L'EST PAS

    On n'ouvre PAS `ALLOWED_HOSTS`. On y ajoute uniquement les noms qui
    portent, en base, un WebsiteDomain **actif ou vérifié** — c'est-à-dire
    des domaines que quelqu'un a délibérément connectés depuis l'interface.
    Un nom inconnu reste refusé, exactement comme avant : la protection
    contre l'empoisonnement de l'en-tête Host demeure.

    POURQUOI UN CACHE, ET PAS SEULEMENT POUR LA VITESSE

    Sans lui, chaque requête portant un hôte inconnu déclencherait une
    lecture en base. Il suffirait d'envoyer des noms au hasard pour faire
    travailler la base à volonté. Les réponses NÉGATIVES sont donc mises en
    cache elles aussi — c'est le cas qu'un attaquant provoque, pas le cas
    nominal.
    """

    DUREE_CACHE = 300          # 5 minutes : un domaine fraîchement branché
                               # devient joignable sans redémarrage.
    DUREE_CACHE_REFUS = 60

    def process_request(self, request):
        from django.conf import settings
        from django.core.cache import cache

        # On lit l'en-tête BRUT : « request.get_host() » validerait déjà
        # contre ALLOWED_HOSTS et lèverait avant qu'on ait pu décider.
        brut = request.META.get('HTTP_HOST') or request.META.get('SERVER_NAME') or ''
        hote = brut.split(':')[0].strip().rstrip('.').lower()

        if not hote or hote in settings.ALLOWED_HOSTS:
            return None

        cle = f'hote-de-site:{hote}'
        connu = cache.get(cle)

        if connu is None:
            from .models import WebsiteDomain
            from django.db.models import Q

            try:
                connu = WebsiteDomain.objects.filter(
                    Q(status='active') | Q(dns_verified=True),
                    domain=hote, website__is_active=True,
                ).exists()
            except Exception:
                # Base indisponible : on ne prend pas le risque d'autoriser
                # un hôte sur une erreur. Le refus reste le défaut.
                return None

            cache.set(cle, connu,
                      self.DUREE_CACHE if connu else self.DUREE_CACHE_REFUS)

        if connu and hote not in settings.ALLOWED_HOSTS:
            # La liste est propre au processus : chaque worker gunicorn
            # l'apprend de son côté, ce qui est sans conséquence puisque la
            # source de vérité reste la base.
            settings.ALLOWED_HOSTS.append(hote)

        return None
