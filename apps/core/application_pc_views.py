"""apps/core/application_pc_views.py — Publier et télécharger l'application PC.

DEUX ÉCRANS, DEUX PUBLICS

Un exploitant dépose l'installeur Windows depuis `/orion-admin/application-pc/`.
Tout utilisateur connecté le télécharge depuis son profil. L'installeur est
produit sur un poste Windows (voir `desktop/orion_desktop_app/installer/`) et
n'a pas sa place dans le dépôt : un binaire de plusieurs dizaines de
méga-octets, qui changerait à chaque version.

POURQUOI LE TÉLÉCHARGEMENT PASSE PAR UNE VUE

Le fichier pourrait être servi directement depuis `media/`. Cette docstring
disait « mais `media/` est public sur cette installation » — ce n'est plus
vrai : `apps/core/media_access.py` refuse désormais par défaut, et
`application-bureau/` y figure parmi les préfixes jamais servis. La raison
de cette vue a changé, et il vaut mieux l'écrire que de laisser un argument
périmé défendre une décision qui tient toujours.

Elle tient pour deux motifs. Le premier est celui d'origine : `login_required`
réserve le téléchargement aux comptes de la maison, ce qui est le minimum pour
un exécutable signé du nom de l'entreprise.

Le second est le décisif, et il n'a rien à voir avec la confidentialité.
Cette vue sert `courante()`, c'est-à-dire la seule version dont `est_publiee`
est vrai. Une adresse directe sous `/media/` désignerait chaque fichier
déposé, y compris celui d'une version retirée parce qu'elle était
défectueuse : le bouton « retirer cette version » cesserait d'avoir un effet,
et on s'en apercevrait en recevant l'appel de quelqu'un qui vient d'installer
la version qu'on croyait écartée.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render

from apps.core.models import VersionApplicationBureau
from apps.orion_ai.permissions import user_is_super_admin


@login_required
def publier_application(request):
    """Dépôt d'une version, réservé au super-administrateur."""
    if not user_is_super_admin(request.user):
        messages.error(
            request, "Seul un super-administrateur peut publier l’application.")
        return redirect('accounts:profile')

    if request.method == 'POST':
        version = (request.POST.get('version') or '').strip()
        fichier = request.FILES.get('fichier')
        url_externe = (request.POST.get('url_externe') or '').strip()
        notes = (request.POST.get('notes') or '').strip()

        # On refuse EXPLICITEMENT, avec le motif. Un formulaire qui se
        # recharge sans rien dire est lu comme une panne — c'est arrivé
        # ailleurs dans cet ERP, plusieurs fois.
        if not version:
            messages.error(request, 'Indiquez le numéro de version.')
        elif not fichier and not url_externe:
            messages.error(
                request, 'Choisissez un fichier d’installation, ou collez le '
                         'lien de téléchargement si le fichier est hébergé '
                         'ailleurs.')
        else:
            VersionApplicationBureau.objects.create(
                version=version, fichier=fichier or None,
                url_externe=url_externe, notes=notes,
                deposee_par=request.user,
            )
            messages.success(
                request, f'Version {version} publiée. Le bouton de '
                         'téléchargement est actif pour tous les utilisateurs.')
            return redirect('core_application_pc:publier')

    return render(request, 'core/application_pc.html', {
        'page_title': 'Application PC',
        'versions': VersionApplicationBureau.objects.all()[:20],
        'courante': VersionApplicationBureau.courante(),
    })


@login_required
def basculer_publication(request, pk):
    """Retire une version du bouton, ou l'y remet."""
    if not user_is_super_admin(request.user):
        messages.error(request, "Action réservée aux super-administrateurs.")
        return redirect('accounts:profile')

    if request.method != 'POST':
        raise Http404

    try:
        version = VersionApplicationBureau.objects.get(pk=pk)
    except VersionApplicationBureau.DoesNotExist:
        raise Http404('Version inconnue.')

    version.est_publiee = not version.est_publiee
    version.save(update_fields=['est_publiee'])
    messages.success(
        request,
        f'Version {version.version} '
        + ('publiée.' if version.est_publiee else 'retirée du téléchargement.'))
    return redirect('core_application_pc:publier')


@login_required
def telecharger_application(request):
    """Sert l'installeur de la version courante.

    404 plutôt qu'une page d'erreur quand rien n'est publié : le bouton ne
    s'affiche que s'il existe une version, et une adresse tapée à la main ne
    doit pas produire un rapport d'incident.
    """
    version = VersionApplicationBureau.courante()
    if version is None:
        raise Http404('Aucune version publiée.')

    # Version hebergee ailleurs : on renvoie vers son adresse. On ne la
    # relaie PAS a travers l'ERP — faire transiter des centaines de Mo par
    # gunicorn occuperait un processus pour chaque telechargement, et le
    # tunnel refuserait de toute facon la reponse au-dela de sa limite.
    if version.url_externe:
        return redirect(version.url_externe)

    if not version.fichier:
        raise Http404('Cette version n’a ni fichier ni lien.')

    try:
        flux = version.fichier.open('rb')
    except (OSError, ValueError):
        # Le fichier est reference en base mais absent du disque. On le dit,
        # plutot que de renvoyer un telechargement de zero octet que
        # l'utilisateur essaierait d'installer.
        raise Http404(
            'Le fichier de cette version est introuvable sur le serveur.')

    nom = version.fichier.name.rsplit('/', 1)[-1] or 'OrionERP-Setup.exe'
    return FileResponse(flux, as_attachment=True, filename=nom)
