"""
apps/translations/middleware.py — Middleware langue Orion ERP
Ordre de priorite ERP  : preference utilisateur > langue entreprise > session > navigateur > fr
Ordre de priorite site : prefixe URL > session > navigateur > langue site > fr

LES SITES PUBLICS ONT LEURS PROPRES REGLES, ET ELLES DORMAIENT.

`apps/websites/services/language_resolver.py` porte la resolution par
SITE : elle ne retient qu'une langue activee pour ce site-la, et ne
consulte le navigateur que si l'exploitant a coche « choisir la langue du
visiteur automatiquement ». Ce module n'etait importe que par des tests --
aucune vue, aucun middleware ne l'appelait. Ce qui tournait etait la
resolution globale ci-dessous, qui consulte le navigateur pour tout le
monde et valide contre les langues de toute l'installation, sans savoir
quel site est servi.

Consequence : le reglage par site etait decoratif, et une langue non
proposee par un site pouvait quand meme s'activer dessus.
"""
import re

from django.utils import translation

#: Les adresses publiques des sites vitrines sont toutes montees sous
#: « /sites/<slug>/ » -- voir `erp_btp/urls.py`. Le middleware de domaine
#: reecrit deja le chemin d'un domaine personnalise vers cette forme, donc
#: ce motif reconnait les deux acces : « s-peace.com/ » et
#: « /sites/electricite-etancheite/ ».
#:
#: On lit le slug dans le CHEMIN et non `request.website`, que pose
#: `WebsiteResolverMiddleware` : celui-ci tourne APRES ce middleware, et il
#: ne resout que par host -- un acces direct a « /sites/<slug>/ » ne lui
#: donne rien.
MOTIF_SITE_PUBLIC = re.compile(r'^/sites/(?P<slug>[-\w]+)/')


class OrionLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        lang = self._resolve_language(request)
        if lang:
            translation.activate(lang)
            request.LANGUAGE_CODE = lang

        response = self.get_response(request)

        if hasattr(request, 'LANGUAGE_CODE'):
            response.setdefault('Content-Language', request.LANGUAGE_CODE)
        return response

    def _site_public(self, request):
        """Le site vitrine vise par cette requete, ou None.

        Le resultat est garde sur la requete : ce middleware l'interroge
        une fois, et une requete d'ERP n'interroge rien du tout -- le
        motif ne correspond pas.
        """
        if hasattr(request, '_orion_site_public'):
            return request._orion_site_public

        site = None
        trouve = MOTIF_SITE_PUBLIC.match(request.path_info or '')
        if trouve:
            try:
                from apps.websites.models import Website

                site = Website.objects.filter(
                    slug=trouve.group('slug'), is_active=True).first()
            except Exception:
                # Base injoignable, table absente avant migration : la
                # langue n'est pas une raison de faire tomber une page.
                site = None

        request._orion_site_public = site
        return site

    def _resolve_language(self, request):
        # 0. UN SITE PUBLIC DECIDE LUI-MEME. Ses regles sont plus etroites
        #    que celles de l'ERP : seules ses langues activees comptent, et
        #    le navigateur n'est consulte que s'il l'a demande. Elles
        #    passent donc AVANT -- un visiteur de vitrine n'a pas de
        #    preference d'utilisateur d'ERP, et s'il en a une (un salarie
        #    qui regarde le site public), c'est le site qui doit l'emporter
        #    chez lui.
        site = self._site_public(request)
        if site is not None:
            from apps.websites.services.language_resolver import (
                get_website_language_from_request,
            )

            lang = get_website_language_from_request(request, site)
            if lang and self._is_valid(lang):
                return lang

        # 1. Preference utilisateur connecte
        if request.user.is_authenticated:
            lang = self._user_language(request)
            if lang:
                return lang

        # 2. Langue en session (set_language ou selecteur)
        lang = request.session.get('_language')
        if lang and self._is_valid(lang):
            return lang

        # 3. Accept-Language navigateur
        accept = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        if accept:
            for part in accept.split(','):
                code = part.strip().split(';')[0].split('-')[0].lower()
                if self._is_valid(code):
                    return code

        return None

    def _user_language(self, request):
        try:
            from apps.translations.models import UserLanguagePreference
            company = getattr(request, 'current_company', None)
            qs = UserLanguagePreference.objects.select_related('language').filter(user=request.user)
            if company:
                pref = qs.filter(company=company).first()
                if pref and pref.language.is_active:
                    return pref.language.code
            pref = qs.filter(company=None).first()
            if pref and pref.language.is_active:
                return pref.language.code
        except Exception:
            pass
        return None

    @staticmethod
    def _is_valid(code):
        from django.conf import settings as s
        valid = {c for c, _ in s.LANGUAGES}
        return code in valid
