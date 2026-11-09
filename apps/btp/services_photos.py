# -*- coding: utf-8 -*-
"""Toutes les photos d'un chantier, rassemblées depuis leurs trois sources.

POURQUOI PAS UN QUATRIÈME MODÈLE. Les photos d'un chantier existent déjà,
mais dispersées en trois endroits, et chacun est légitime :

  - `ProjectDocument` — la photothèque documentaire du chantier ;
  - `ReservationPhoto` — ce que l'on a photographié pour appuyer une réserve ;
  - `ProjectStepItem.answer_photo` — la réponse à un point de contrôle qui
    demande une photo, « état de l'existant » par exemple.

Un modèle « photo du chantier » de plus obligerait à y recopier les trois
autres, et deux galeries finiraient par ne plus dire la même chose — ce
dépôt a déjà payé ce genre de doublon. On rassemble donc à la LECTURE, et
aucune migration n'est nécessaire.

CE QUI DÉCIDE QU'UN FICHIER EST UNE PHOTO : son extension, pas son
étiquette. Un `ProjectDocument` de type « Photo » peut parfaitement porter
un PDF — il s'afficherait alors comme une image cassée au milieu de la
galerie. Et une vraie photo de chantier est souvent déposée sous un autre
type : « Rapport journalier », « Document client ». Juger l'étiquette
afficherait donc des cassures et raterait des photos ; on juge le fichier.

L'APPELANT FOURNIT L'INSTANCE, jamais un identifiant. `project` est déjà
filtré sur l'entreprise par la vue, et tout ce qui est atteint ici l'est par
une clé étrangère depuis lui : l'isolement entre entreprises est donc acquis
par construction. Accepter un `pk` ici rouvrirait précisément la fuite que
l'audit de ce module a corrigée ailleurs.
"""

import os

from django.urls import reverse

# Ce qu'un navigateur sait afficher dans une balise <img>. Le HEIC des
# iPhone n'en fait pas partie pour tous les navigateurs, mais le refuser
# ferait disparaître des photos prises sur le chantier : mieux vaut une
# vignette que certains ne voient pas qu'une photo qu'on ne sait plus où
# retrouver.
EXTENSIONS_IMAGE = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp',
                    '.heic', '.heif', '.avif')


def est_une_image(nom_de_fichier):
    """Vrai si ce nom de fichier porte une extension d'image."""
    if not nom_de_fichier:
        return False
    extension = os.path.splitext(str(nom_de_fichier))[1].lower()
    return extension in EXTENSIONS_IMAGE


# Les trois origines, et leur libellé d'affichage. La CLÉ voyage dans
# l'URL de service ; le libellé est ce que l'écran montre.
ORIGINES = (
    ('document', 'Document'),
    ('reserve', 'Réserve'),
    ('point', 'Étape'),
)


def _url_de_service(project, origine, pk):
    """L'URL par laquelle la galerie demande une image.

    PAS `fichier.url`, et c'est le correctif du 09/11/2026 : sous /media/,
    `apps/core/media_access.py` applique un REFUS PAR DÉFAUT et ne sert que
    des préfixes nommés. `project_documents/` et `btp/checklists/` n'en font
    pas partie — délibérément, puisqu'on y trouve des devis, des contrats et
    des documents clients. Les vignettes s'affichaient donc cassées, et
    seules celles de réserves fonctionnaient, `reservations/` étant le seul
    des trois préfixes autorisé.

    La tentation est d'ajouter les deux préfixes manquants à la liste
    blanche. Ce serait une fuite : cette liste n'a AUCUNE notion
    d'entreprise, et tout utilisateur connecté de n'importe quelle société
    pourrait alors lire les documents de n'importe quelle autre en devinant
    une URL. C'est exactement ce que l'audit de ce module a corrigé
    ailleurs.

    On passe donc par une vue qui vérifie l'entreprise à chaque lecture.
    """
    from django.urls import reverse

    return reverse('btp:project_photo', args=[project.pk, origine, pk])


def fichier_de_la_photo(project, origine, pk):
    """Le fichier d'une photo de CE chantier, ou None.

    Le `project` est fourni par la vue, déjà filtré sur l'entreprise. Chaque
    recherche ci-dessous repart de lui par une clé étrangère : une photo
    d'un autre chantier, ou d'une autre société, ne peut donc pas être
    servie même si son identifiant est deviné.
    """
    if origine == 'document':
        objet = project.project_documents.filter(pk=pk).first()
        return objet.file if objet and objet.file else None

    if origine == 'reserve':
        from .models import ReservationPhoto
        objet = ReservationPhoto.objects.filter(
            pk=pk, reservation__project=project).first()
        return objet.photo if objet and objet.photo else None

    if origine == 'point':
        from .models import ProjectStepItem
        objet = ProjectStepItem.objects.filter(
            pk=pk, step__project=project).first()
        return objet.answer_photo if objet and objet.answer_photo else None

    return None


def photos_du_chantier(project):
    """Les photos du chantier, les plus récentes d'abord.

    Rend une liste de dictionnaires : `url`, `titre`, `origine`, `detail`,
    `date`, `lien`. `lien` renvoie vers la fiche d'où la photo vient quand
    une telle page existe, et vaut None sinon — l'affichage doit rester
    exact plutôt que de promettre un lien mort.
    """
    photos = []

    # ── 1. Les documents du chantier ────────────────────────────────────
    for document in project.project_documents.all():
        nom_du_fichier = getattr(document.file, 'name', '')
        if not est_une_image(nom_du_fichier):
            continue
        photos.append({
            'url': _url_de_service(project, 'document', document.pk),
            'titre': document.name or os.path.basename(nom_du_fichier),
            'origine': 'Document',
            'detail': document.get_doc_type_display(),
            'date': document.added_at,
            'lien': None,
        })

    # ── 2. Les photos de réserves ───────────────────────────────────────
    for reserve in project.reservations.prefetch_related('photos'):
        for cliche in reserve.photos.all():
            if not cliche.photo:
                continue
            photos.append({
                'url': _url_de_service(project, 'reserve', cliche.pk),
                'titre': cliche.caption or reserve.title,
                'origine': 'Réserve',
                'detail': reserve.title,
                'date': cliche.uploaded_at,
                'lien': reverse('btp:reservations_list'),
            })

    # ── 3. Les points de contrôle dont la réponse EST une photo ─────────
    for etape in project.plan_steps.prefetch_related('items'):
        for point in etape.items.all():
            if not point.answer_photo:
                continue
            photos.append({
                'url': _url_de_service(project, 'point', point.pk),
                'titre': point.label,
                'origine': 'Étape',
                'detail': etape.name,
                'date': point.filled_at,
                'lien': reverse('btp:step_detail', args=[etape.pk]),
            })

    # Les plus récentes d'abord, et celles sans date à la fin.
    #
    # Deux listes plutôt qu'une clé de tri avec une date sentinelle : une
    # sentinelle demande de choisir entre naïf et conscient du fuseau, et se
    # trompe un jour sur deux. `filled_at` est nul tant que le point n'a pas
    # été rempli, et une photo peut y être déposée sans que le reste le soit.
    datees = [p for p in photos if p['date']]
    sans_date = [p for p in photos if not p['date']]
    datees.sort(key=lambda p: p['date'], reverse=True)
    return datees + sans_date


def compter_les_photos(project):
    """Combien de photos, pour le compteur de l'onglet.

    Volontairement séparé de `photos_du_chantier` : la fiche du chantier
    s'affiche à chaque consultation et n'a besoin que du nombre, alors que
    la galerie n'est construite que lorsqu'on ouvre l'onglet. Trois requêtes
    légères plutôt que le parcours complet des trois sources.
    """
    from .models import ProjectStepItem, ReservationPhoto

    # Les documents demandent de regarder les noms de fichiers, puisque
    # c'est l'extension qui tranche : une seule colonne est ramenée.
    noms = project.project_documents.values_list('file', flat=True)
    total = sum(1 for nom in noms if est_une_image(nom))

    total += ReservationPhoto.objects.filter(
        reservation__project=project).count()

    total += ProjectStepItem.objects.filter(
        step__project=project).exclude(answer_photo='').exclude(
        answer_photo__isnull=True).count()

    return total
