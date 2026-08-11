"""
apps/translations/middleware.py — Middleware langue Orion ERP
Ordre de priorite ERP  : preference utilisateur > langue entreprise > session > navigateur > fr
Ordre de priorite site : prefixe URL > session > navigateur > langue site > fr
"""
from django.utils import translation


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

    def _resolve_language(self, request):
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
