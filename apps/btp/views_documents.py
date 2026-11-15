"""apps/btp/views_documents.py — Les documents d'un chantier.

CE QUI MANQUAIT, ET CE QUE CELA PROVOQUAIT

`ProjectDocument` existe depuis longtemps, avec dix-huit types de documents,
une visibilité client, des versions et un marqueur « obligatoire ». Mais
AUCUN écran ne le servait : ni liste, ni dépôt, ni téléchargement. Seul
l'envoi depuis le téléphone y écrivait, et uniquement des photos.

Faute de cet écran, les factures d'un chantier étaient déposées dans le
module Documents général — le seul endroit qui offrait un bouton. Elles s'y
accumulaient, mêlées aux documents de l'entreprise, sans lien avec le
chantier auquel elles appartiennent.

Le modèle était là, le dossier était là ; il manquait la porte.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import BTPProject, ProjectDocument


def _chantier(request, pk):
    """Le chantier demandé, borné à l'entreprise active.

    La borne est ici et non dans la vue : un document de chantier peut
    porter un prix, un nom de client et une signature. Laisser filtrer sur
    l'identifiant seul ouvrirait les pièces d'une entreprise à une autre.
    """
    return get_object_or_404(BTPProject, pk=pk, company=request.current_company)


@login_required
def project_documents(request, project_pk):
    """La liste des documents d'un chantier, et leur dépôt."""
    chantier = _chantier(request, project_pk)

    # « corbeille_le » : ce chantier a deja une corbeille, avec quinze
    # jours de conservation (services_photos). Un document qui y est parti
    # doit disparaitre d'ici, sans quoi il resterait servi par son adresse
    # alors qu'il a disparu de la liste.
    documents = (chantier.project_documents
                 .filter(corbeille_le__isnull=True)
                 .select_related('added_by')
                 .order_by('-added_at'))

    type_demande = (request.GET.get('type') or '').strip()
    if type_demande:
        documents = documents.filter(doc_type=type_demande)

    if request.method == 'POST':
        fichier = request.FILES.get('file')
        nom = (request.POST.get('name') or '').strip()
        doc_type = (request.POST.get('doc_type') or 'other').strip()

        # On refuse EXPLICITEMENT, avec le motif. Un formulaire qui se
        # recharge sans rien dire est lu comme une panne — c'est arrivé
        # plusieurs fois ailleurs dans cet ERP.
        if not fichier:
            messages.error(
                request, 'Choisissez un fichier. Sans '
                         '« enctype="multipart/form-data" » sur le '
                         'formulaire, le navigateur ne l’envoie pas.')
        elif doc_type not in dict(ProjectDocument.DOC_TYPE_CHOICES):
            messages.error(request, 'Type de document inconnu.')
        else:
            ProjectDocument.objects.create(
                project=chantier,
                doc_type=doc_type,
                # Le nom du fichier sert de libellé par défaut : exiger une
                # saisie pour déposer une facture déjà nommée serait une
                # friction sans contrepartie.
                name=(nom or fichier.name)[:200],
                file=fichier,
                description=(request.POST.get('description') or '').strip(),
                visible_to_client=bool(request.POST.get('visible_to_client')),
                added_by=request.user,
            )
            messages.success(request, 'Document ajouté au chantier.')
            return redirect('btp:project_documents', project_pk=chantier.pk)

    return render(request, 'btp/project_documents.html', {
        'page_title': f'Documents — {chantier.name}',
        'project': chantier,
        'documents': documents,
        'type_demande': type_demande,
        'type_choices': ProjectDocument.DOC_TYPE_CHOICES,
        'active_module': 'btp',
    })


@login_required
def project_document_download(request, pk):
    """Sert le fichier, borné à l'entreprise active.

    Le fichier pourrait être servi depuis media/, qui est public sur cette
    installation : son adresse circulerait alors hors de l'ERP. Une facture
    de chantier porte des prix et un nom de client — elle n'a pas à être
    lisible de qui connaît l'URL.
    """
    document = get_object_or_404(
        ProjectDocument, pk=pk, corbeille_le__isnull=True,
        project__company=request.current_company)

    if not document.file:
        raise Http404('Ce document n’a pas de fichier.')

    try:
        flux = document.file.open('rb')
    except (OSError, ValueError):
        # Reference en base, absent du disque. On le dit, plutot que de
        # servir un telechargement de zero octet.
        raise Http404('Le fichier est introuvable sur le serveur.')

    nom = document.file.name.rsplit('/', 1)[-1] or 'document'
    return FileResponse(flux, as_attachment=True, filename=nom)


@login_required
@require_POST
def project_document_delete(request, pk):
    """Met le document a la corbeille du chantier.

    ON N'EFFACE PAS. Le chantier a deja une corbeille, avec quinze jours de
    conservation : un second chemin de suppression, definitif celui-la,
    aurait rendu la corbeille trompeuse — on croirait pouvoir recuperer ce
    qu'on vient de perdre. On emploie donc le mecanisme existant.
    """
    from .services_photos import mettre_a_la_corbeille

    document = get_object_or_404(
        ProjectDocument, pk=pk, corbeille_le__isnull=True,
        project__company=request.current_company)
    chantier = document.project

    libelle = mettre_a_la_corbeille(chantier, 'document', document.pk,
                                    request.user)
    if libelle is None:
        messages.error(request, 'Document introuvable.')
    else:
        messages.success(
            request, f'Document « {libelle} » mis a la corbeille du chantier.')
    return redirect('btp:project_documents', project_pk=chantier.pk)
