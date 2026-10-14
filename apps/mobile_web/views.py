"""Interface téléphone d'Orion ERP.

Trois besoins, trois pages, servies par le serveur lui-même :

1. **S'adapter au téléphone.** Des pages conçues pour le pouce plutôt qu'une
   mise en page de bureau rétrécie : une colonne, de grandes cibles, aucun
   tableau à faire défiler latéralement.
2. **Atteindre l'interface d'un serveur.** Un lanceur qui connaît les serveurs
   de la grappe et permet d'en ouvrir un.
3. **Prendre des photos pour l'ERP.** L'appareil photo du téléphone, sans
   installer d'application.

Pourquoi le web et non l'application Flutter du dépôt : une page web
fonctionne depuis n'importe quel téléphone sans passer par un magasin
d'applications, et `capture="environment"` ouvre directement l'appareil photo
arrière sur Android comme sur iOS. Les deux voies peuvent coexister.

Cloisonnement : toutes les requêtes sont filtrées sur l'entreprise active.
C'est la règle la plus importante de cet ERP, et un formulaire qui laisserait
choisir le chantier d'une autre entreprise serait une fuite de données.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.mobile_web.forms import PhotoMobileForm

PHOTOS_MAX = 10
TAILLE_MAX_OCTETS = 12 * 1024 * 1024  # 12 Mo par photo
TYPES_ACCEPTES = ('image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif')


def _entreprise(request):
    return getattr(request, 'current_company', None)


def _chantiers_visibles(request):
    """Chantiers de l'entreprise active, et d'elle seule.

    Sans ce filtre, la liste déroulante exposerait les chantiers des autres
    entreprises — y compris leurs noms de clients. C'est précisément la fuite
    que le cloisonnement multi-entreprises existe pour empêcher.
    """
    entreprise = _entreprise(request)
    if not entreprise:
        return []
    try:
        from apps.btp.models import BTPProject
    except Exception:
        return []
    return list(
        BTPProject.objects
        .filter(company=entreprise)
        .exclude(status__in=('cancelled', 'archived'))
        .order_by('-id')[:200]
    )


@login_required
def accueil(request):
    """Point d'entrée téléphone : les actions, pas le menu complet."""
    return render(request, 'mobile_web/accueil.html', {
        'entreprise': _entreprise(request),
        'page_title': 'Orion mobile',
        'rubrique': 'accueil',
    })


@login_required
def serveurs(request):
    """Serveurs joignables, pour ouvrir l'interface de l'un d'eux.

    La liste vient de la grappe enregistrée : des adresses décidées par
    l'exploitant, pas par le visiteur. Aucune redirection n'est émise par le
    serveur — ce sont de simples liens — ce qui écarte toute redirection
    ouverte.
    """
    noeuds = []
    try:
        from apps.high_availability.models import OrionHANode
        noeuds = list(
            OrionHANode.objects
            .filter(is_enabled=True)
            .exclude(base_url='')
            .order_by('priority')
        )
    except Exception:
        noeuds = []

    return render(request, 'mobile_web/serveurs.html', {
        'noeuds': noeuds,
        'ici': request.get_host(),
        'page_title': 'Serveurs',
        'rubrique': 'serveurs',
    })


def _nom_par_defaut():
    return f"Photo du {timezone.localtime().strftime('%d/%m/%Y a %H:%M')}"


def _verifier_photo(fichier):
    """Refus explicite plutôt qu'échec obscur à l'enregistrement."""
    if fichier.size > TAILLE_MAX_OCTETS:
        mo = fichier.size / (1024 * 1024)
        return f'{fichier.name} fait {mo:.1f} Mo, au-delà de la limite de 12 Mo.'
    # Le type déclaré par le navigateur ne prouve rien, mais il écarte les
    # envois manifestement hors sujet avant d'écrire sur le disque.
    if fichier.content_type and fichier.content_type not in TYPES_ACCEPTES:
        return f'{fichier.name} n\'est pas une image ({fichier.content_type}).'
    return ''


@login_required
def photo(request):
    """Prend une ou plusieurs photos et les range dans l'ERP."""
    entreprise = _entreprise(request)
    chantiers = _chantiers_visibles(request)

    if request.method != 'POST':
        return render(request, 'mobile_web/photo.html', {
            'form': PhotoMobileForm(chantiers=chantiers),
            'entreprise': entreprise,
            'photos_max': PHOTOS_MAX,
            'page_title': 'Prendre une photo',
            'rubrique': 'photo',
        })

    form = PhotoMobileForm(request.POST, chantiers=chantiers)
    fichiers = request.FILES.getlist('photos')[:PHOTOS_MAX]

    if not entreprise:
        messages.error(
            request,
            "Aucune entreprise active : impossible de savoir où ranger la photo.",
        )
    elif not fichiers:
        messages.error(request, 'Aucune photo reçue. Prenez ou choisissez une image.')
    elif form.is_valid():
        refus = [m for m in (_verifier_photo(f) for f in fichiers) if m]
        if refus:
            for message in refus:
                messages.error(request, message)
        else:
            enregistrees = _enregistrer(request, form.cleaned_data, fichiers, entreprise)
            # Zero enregistrement n'est pas un succes. _enregistrer a deja
            # pose l'erreur ; annoncer « 0 photo enregistree » par-dessus,
            # puis rediriger, faisait croire a une reussite et masquait la
            # cause -- un chantier refuse, par exemple.
            if enregistrees:
                messages.success(
                    request,
                    'Photo enregistrée.' if enregistrees == 1
                    else f'{enregistrees} photos enregistrées.',
                )
                return redirect('mobile_web:photo')

    return render(request, 'mobile_web/photo.html', {
        'form': form,
        'entreprise': entreprise,
        'photos_max': PHOTOS_MAX,
        'page_title': 'Prendre une photo',
        'rubrique': 'photo',
    })


def _enregistrer(request, donnees, fichiers, entreprise):
    """Range les photos dans les pièces jointes existantes de l'ERP.

    Deux destinations, selon qu'un chantier est désigné. Dans les deux cas le
    modèle est celui que l'ERP affiche déjà : la photo apparaît donc là où on
    la cherche, sans écran supplémentaire à construire.
    """
    libelle = (donnees.get('libelle') or '').strip() or _nom_par_defaut()
    description = (donnees.get('description') or '').strip()
    chantier_id = donnees.get('chantier') or ''
    total = 0

    chantier = None
    if chantier_id:
        # Re-filtré sur l'entreprise active : le champ vient du navigateur, et
        # une valeur forgée ne doit pas atteindre le chantier d'un autre.
        chantier = next(
            (p for p in _chantiers_visibles(request) if str(p.pk) == str(chantier_id)),
            None,
        )
        if chantier is None:
            messages.error(request, 'Chantier inconnu pour cette entreprise.')
            return 0

    for index, fichier in enumerate(fichiers, start=1):
        nom = libelle if len(fichiers) == 1 else f'{libelle} ({index}/{len(fichiers)})'

        if chantier is not None:
            from apps.btp.models import ProjectDocument
            ProjectDocument.objects.create(
                project=chantier,
                doc_type='photo',
                name=nom[:200],
                file=fichier,
                description=description,
                visible_to_client=bool(donnees.get('visible_client')),
                added_by=request.user,
            )
        else:
            from apps.documents.models import Document
            Document.objects.create(
                company=entreprise,
                document_type='photo',
                title=nom[:200],
                description=description,
                file=fichier,
                file_size=fichier.size,
                uploaded_by=request.user,
            )
        total += 1

    return total
