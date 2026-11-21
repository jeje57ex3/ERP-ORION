"""apps/core/redirections.py — Où l'on accepte de renvoyer l'utilisateur.

LE DÉFAUT : `url_has_allowed_host_and_scheme` N'ÉTAIT APPELÉ NULLE PART

Une quinzaine de vues renvoyaient l'utilisateur vers une adresse prise
dans la requête, sans la vérifier :

    apps/user_security/views.py:138   redirect(request.GET.get("next") …)
    apps/accounts/views.py:86         redirect(request.GET.get('next', …))
    apps/notifications/views.py       redirect(POST['next'] or REFERER)
    apps/dashboard/views.py           redirect(POST.get('next', …))
    apps/ecommerce/store_views.py     redirect(POST.get('next', …))
    apps/core/views.py:410            next ou HTTP_REFERER
    apps/private_saas/views.py:341    POST['next']

`django.shortcuts.redirect` accepte une adresse absolue et la sert
telle quelle. `?next=https://exemple-pirate/` envoie donc l'utilisateur
hors du site, depuis une adresse qui commence par le vrai domaine.

LA PLUS GRAVE EST CELLE DU 2FA, ET C'EST PRÉCISÉMENT PARCE QU'ELLE
MARCHE

    apps/user_security/views.py
        login(request, user)
        mark_2fa_verified(request, user)
        response = redirect(request.GET.get("next") or "core:dashboard")

Elle s'exécute **après** une authentification réussie, code à deux
facteurs compris. L'utilisateur a saisi son mot de passe, sorti son
téléphone, tapé son code — et atterrit sur une page choisie par
l'attaquant. À cet instant précis, il n'a plus aucune raison de se
méfier : tout ce qu'on lui a demandé a fonctionné. Une page qui demande
alors de « confirmer » quoi que ce soit sera remplie.

CE QUE FAIT LA VÉRIFICATION, ET CE QU'ELLE NE FAIT PAS

Elle n'autorise qu'une adresse du même hôte, ou un chemin relatif. Elle
ne tente pas de « nettoyer » une adresse étrangère : une adresse hors du
site est remplacée par la destination de repli, sans discussion. Une
liste d'exceptions se contourne ; un refus ne se contourne pas.

Les hôtes acceptés sont ceux d'`ALLOWED_HOSTS`, plus celui de la requête
en cours — ce dernier parce que l'ERP sert plusieurs domaines (l'ERP,
les vitrines, les boutiques) et qu'un retour vers le domaine d'où l'on
vient est légitime.
"""
from django.conf import settings
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme


def _hotes_admis(request):
    hotes = {h for h in getattr(settings, 'ALLOWED_HOSTS', []) or []
             if h and h not in ('*',)}

    # `ALLOWED_HOSTS = ['*']` ne vaut PAS « n'importe quel hôte » ici.
    #
    # Il dit à Django d'accepter n'importe quel en-tête `Host` en
    # entrée, ce qui est un réglage de déploiement. L'employer pour
    # décider d'une redirection reviendrait à n'en vérifier aucune, et
    # c'est l'état dont on sort.
    hote = request.get_host() if hasattr(request, 'get_host') else None
    if hote:
        hotes.add(hote)
        # `get_host()` porte le port ; une adresse de retour peut ne pas
        # l'avoir, et l'inverse.
        hotes.add(hote.split(':')[0])

    return hotes


def destination_sure(request, candidate, defaut):
    """La destination si elle est interne, sinon `defaut`.

    `candidate` est ce que la requête propose — un `next`, un `Referer`.
    `defaut` est ce vers quoi la vue voulait aller sans lui : un nom de
    route, un chemin, ce que `redirect()` sait traiter.
    """
    if not candidate:
        return defaut

    texte = str(candidate).strip()
    if not texte:
        return defaut

    # DEUX FORMES QUI PASSENT LA VÉRIFICATION DE DJANGO ET QUI SORTENT
    # QUAND MÊME DU SITE.
    #
    # `//exemple-pirate/` est une adresse « protocole-relatif » : le
    # navigateur y voit un hôte, pas un chemin. Et un retour à la ligne
    # ou une tabulation au début sont retirés par les navigateurs avant
    # l'analyse, si bien que `/\nhttps://pirate` devient une adresse
    # absolue. `url_has_allowed_host_and_scheme` traite déjà le premier
    # cas ; on écarte les deux ici, avant même de l'appeler, parce que ce
    # sont des formes qu'aucune destination légitime ne prend.
    if any(c in texte for c in ('\n', '\r', '\t', '\x00')):
        return defaut

    if url_has_allowed_host_and_scheme(
            url=texte,
            allowed_hosts=_hotes_admis(request),
            require_https=request.is_secure()):
        return texte

    return defaut


def rediriger_sans_sortir(request, candidate, defaut):
    """`redirect()` vers `candidate` s'il est interne, sinon vers `defaut`."""
    return redirect(destination_sure(request, candidate, defaut))


def destination_demandee(request, defaut, champ='next'):
    """Ce que la requête demande comme retour, vérifié.

    Cherche `champ` dans le POST, puis dans le GET, puis se rabat sur le
    `Referer` — l'ordre employé par les vues qui faisaient cela à la
    main. Le `Referer` est traité comme tout le reste : c'est un en-tête,
    donc une valeur que le client écrit.
    """
    propose = ''
    if request.method == 'POST':
        propose = request.POST.get(champ) or ''
    if not propose:
        propose = request.GET.get(champ) or ''
    if not propose:
        propose = request.META.get('HTTP_REFERER') or ''

    return destination_sure(request, propose, defaut)
