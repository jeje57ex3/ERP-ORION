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
from datetime import timedelta

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


def _url_de_suppression(project, origine, pk):
    """L'URL du bouton qui retire cette photo du chantier."""
    from django.urls import reverse

    return reverse('btp:project_photo_delete',
                   args=[project.pk, origine, pk])


def fichier_de_la_photo(project, origine, pk,
                        inclure_la_corbeille=False):
    """Le fichier d'une photo de CE chantier, ou None.

    Le `project` est fourni par la vue, déjà filtré sur l'entreprise. Chaque
    recherche ci-dessous repart de lui par une clé étrangère : une photo
    d'un autre chantier, ou d'une autre société, ne peut donc pas être
    servie même si son identifiant est deviné.
    """
    objet = _objet_de_la_photo(project, origine, pk, inclure_la_corbeille)
    if objet is None:
        return None
    fichier = _fichier_porte_par(origine, objet)
    return fichier if fichier else None


def _objet_de_la_photo(project, origine, pk, inclure_la_corbeille=False):
    """L'objet qui porte la photo, cherché DEPUIS le chantier.

    `inclure_la_corbeille` n'est vrai que pour l'écran de corbeille et la
    restauration : partout ailleurs, une photo mise à la corbeille doit
    être introuvable, sans quoi elle resterait servie par son URL alors
    qu'elle a disparu de la galerie.
    """
    if origine == 'document':
        recherche = project.project_documents.filter(pk=pk)
        if not inclure_la_corbeille:
            recherche = recherche.filter(corbeille_le__isnull=True)
        return recherche.first()

    if origine == 'reserve':
        from .models import ReservationPhoto
        recherche = ReservationPhoto.objects.filter(
            pk=pk, reservation__project=project)
        if not inclure_la_corbeille:
            recherche = recherche.filter(corbeille_le__isnull=True)
        return recherche.first()

    if origine == 'point':
        from .models import ProjectStepItem
        recherche = ProjectStepItem.objects.filter(
            pk=pk, step__project=project).exclude(answer_photo='')
        if not inclure_la_corbeille:
            recherche = recherche.filter(photo_corbeille_le__isnull=True)
        return recherche.first()

    return None


def _fichier_porte_par(origine, objet):
    return {
        'document': getattr(objet, 'file', None),
        'reserve': getattr(objet, 'photo', None),
        'point': getattr(objet, 'answer_photo', None),
    }.get(origine)


# ─── La corbeille ──────────────────────────────────────────────────────────
#
# Une photo retirée d'un chantier n'est pas détruite : elle est datée et
# reste récupérable DEUX SEMAINES. Une photo de chantier peut servir de
# preuve en cas de litige, et un clic de trop ne doit pas la faire
# disparaître à jamais.
#
# Rien n'est déplacé ni recopié : l'objet reste à sa place, seule une date
# le marque. Copier le fichier ailleurs doublerait l'occupation disque
# pendant quinze jours, et une restauration consisterait à le recopier en
# sens inverse — deux fois plus d'occasions de le perdre.
DUREE_DE_CONSERVATION_JOURS = 14

# Le champ qui porte la date, par origine. Le point de contrôle a le sien
# parce que la photo n'y est qu'une des réponses possibles : c'est la PHOTO
# qu'on met à la corbeille, pas la question.
CHAMP_DE_CORBEILLE = {
    'document': 'corbeille_le',
    'reserve': 'corbeille_le',
    'point': 'photo_corbeille_le',
}
CHAMP_D_AUTEUR = {
    'document': 'corbeille_par',
    'reserve': 'corbeille_par',
    'point': 'photo_corbeille_par',
}


def mettre_a_la_corbeille(project, origine, pk, utilisateur=None):
    """Retire la photo de la galerie. Rend un libellé, ou None si introuvable.

    CE QUI N'EST PAS SUPPRIMÉ, et c'est le point délicat :

    * **réserve** — seule la photo part. Le titre, la description et le
      statut de la réserve sont le dossier ; une réserve sans son image
      reste une malfaçon à traiter, et l'effacer avec la photo la ferait
      disparaître du suivi.
    * **point de contrôle** — la question reste, et redevient « non
      renseignée » donc comptée par l'avertisseur de l'onglet Étapes.
      Supprimer le point ferait disparaître du contrôle une case qu'il
      faut encore remplir, sans que personne ne sache qu'elle manque.
    """
    from django.utils import timezone

    objet = _objet_de_la_photo(project, origine, pk)
    if objet is None:
        return None

    libelle = _libelle_de(origine, objet)
    setattr(objet, CHAMP_DE_CORBEILLE[origine], timezone.now())
    if utilisateur is not None and utilisateur.is_authenticated:
        setattr(objet, CHAMP_D_AUTEUR[origine], utilisateur)
    objet.save(update_fields=[CHAMP_DE_CORBEILLE[origine],
                              CHAMP_D_AUTEUR[origine]])
    return libelle


def restaurer_la_photo(project, origine, pk):
    """Remet la photo dans la galerie. Rend un libellé, ou None."""
    objet = _objet_de_la_photo(project, origine, pk,
                               inclure_la_corbeille=True)
    if objet is None or getattr(objet, CHAMP_DE_CORBEILLE[origine]) is None:
        return None

    libelle = _libelle_de(origine, objet)
    setattr(objet, CHAMP_DE_CORBEILLE[origine], None)
    setattr(objet, CHAMP_D_AUTEUR[origine], None)
    objet.save(update_fields=[CHAMP_DE_CORBEILLE[origine],
                              CHAMP_D_AUTEUR[origine]])
    return libelle


def _libelle_de(origine, objet):
    if origine == 'document':
        return objet.name or os.path.basename(
            getattr(objet.file, 'name', '') or '')
    if origine == 'reserve':
        return objet.caption or objet.reservation.title
    return objet.label


def purger_la_corbeille(maintenant=None):
    """Détruit définitivement ce qui dort dans la corbeille depuis 14 jours.

    Rend un décompte par origine. Ne lève jamais sur un fichier : la ligne
    doit partir même si le fichier manque déjà — une sauvegarde restaurée
    sans les médias laisse exactement cet état.

    APPELÉE DE DEUX ENDROITS, ET C'EST DÉLIBÉRÉ.

    Une tâche périodique, et aussi l'ouverture de l'écran de corbeille. La
    promesse faite à l'utilisateur — « supprimée définitivement au bout de
    deux semaines » — ne doit pas dépendre d'un planificateur que personne
    n'a configuré. Ce dépôt a déjà livré trois choses que rien n'activait :
    le middleware de performance, les règles sudo et l'assistant disque.
    Une purge qui ne tourne jamais garderait les fichiers indéfiniment, et
    l'écran afficherait « 0 jour restant » sans que rien ne se passe.
    """
    from django.utils import timezone

    from .models import ProjectDocument, ProjectStepItem, ReservationPhoto

    maintenant = maintenant or timezone.now()
    limite = maintenant - timedelta(days=DUREE_DE_CONSERVATION_JOURS)
    comptes = {'documents': 0, 'reserves': 0, 'points': 0}

    for document in ProjectDocument.objects.filter(
            corbeille_le__isnull=False, corbeille_le__lt=limite):
        fichier = document.file
        document.delete()
        _oublier_le_fichier(fichier)
        comptes['documents'] += 1

    for cliche in ReservationPhoto.objects.filter(
            corbeille_le__isnull=False, corbeille_le__lt=limite):
        fichier = cliche.photo
        cliche.delete()
        _oublier_le_fichier(fichier)
        comptes['reserves'] += 1

    # Le point de contrôle SURVIT : seule sa photo part, et la question
    # reste « non renseignée ». La date de corbeille est remise à None,
    # sans quoi le point resterait marqué comme ayant eu une photo retirée
    # alors qu'il n'y en a plus du tout.
    for point in ProjectStepItem.objects.filter(
            photo_corbeille_le__isnull=False, photo_corbeille_le__lt=limite):
        fichier = point.answer_photo
        point.answer_photo = None
        point.photo_corbeille_le = None
        point.photo_corbeille_par = None
        point.save(update_fields=['answer_photo', 'photo_corbeille_le',
                                  'photo_corbeille_par'])
        _oublier_le_fichier(fichier)
        comptes['points'] += 1

    return comptes


def _oublier_le_fichier(fichier):
    """Retire le fichier du stockage, sans jamais lever.

    La ligne est déjà partie quand on arrive ici : si le fichier a disparu
    du disque, si les droits manquent, ou si le stockage est distant et
    injoignable, la suppression reste un succès du point de vue de
    l'utilisateur. Lever ici rendrait une erreur 500 sur une purge qui a
    bel et bien eu lieu.
    """
    if not fichier:
        return
    try:
        fichier.delete(save=False)
    except Exception:                                   # noqa: BLE001
        pass


def photos_du_chantier(project, corbeille=False):
    """Les photos du chantier, les plus récentes d'abord.

    Avec `corbeille=True`, rend au contraire celles qui attendent leur
    suppression définitive, avec le nombre de jours restants.

    La MÊME fonction sert les deux écrans, et c'est voulu : deux parcours
    séparés des trois sources finiraient par diverger, et une photo
    pourrait alors manquer aux deux endroits à la fois.
    """
    photos = []

    # ── 1. Les documents du chantier ────────────────────────────────────
    documents = project.project_documents.filter(
        corbeille_le__isnull=not corbeille)
    for document in documents:
        nom_du_fichier = getattr(document.file, 'name', '')
        if not est_une_image(nom_du_fichier):
            continue
        photos.append(_decrire(
            project, 'document', document.pk,
            titre=document.name or os.path.basename(nom_du_fichier),
            origine='Document',
            detail=document.get_doc_type_display(),
            date=document.added_at,
            lien=None,
            corbeille_le=document.corbeille_le,
            corbeille=corbeille))

    # ── 2. Les photos de réserves ───────────────────────────────────────
    for reserve in project.reservations.prefetch_related('photos'):
        for cliche in reserve.photos.all():
            if not cliche.photo:
                continue
            if (cliche.corbeille_le is None) == corbeille:
                continue
            photos.append(_decrire(
                project, 'reserve', cliche.pk,
                titre=cliche.caption or reserve.title,
                origine='Réserve',
                detail=reserve.title,
                date=cliche.uploaded_at,
                lien=reverse('btp:reservations_list'),
                corbeille_le=cliche.corbeille_le,
                corbeille=corbeille))

    # ── 3. Les points de contrôle dont la réponse EST une photo ─────────
    for etape in project.plan_steps.prefetch_related('items'):
        for point in etape.items.all():
            if not point.answer_photo:
                continue
            if (point.photo_corbeille_le is None) == corbeille:
                continue
            photos.append(_decrire(
                project, 'point', point.pk,
                titre=point.label,
                origine='Étape',
                detail=etape.name,
                date=point.filled_at,
                lien=reverse('btp:step_detail', args=[etape.pk]),
                corbeille_le=point.photo_corbeille_le,
                corbeille=corbeille))

    # Les plus récentes d'abord, et celles sans date à la fin.
    #
    # Deux listes plutôt qu'une clé de tri avec une date sentinelle : une
    # sentinelle demande de choisir entre naïf et conscient du fuseau, et se
    # trompe un jour sur deux.
    datees = [p for p in photos if p['date']]
    sans_date = [p for p in photos if not p['date']]
    datees.sort(key=lambda p: p['date'], reverse=True)
    return datees + sans_date


def _decrire(project, cle, pk, titre, origine, detail, date, lien,
             corbeille_le, corbeille):
    """Une entrée de galerie, pour l'un ou l'autre des deux écrans."""
    photo = {
        'url': _url_de_service(project, cle, pk),
        'titre': titre,
        'origine': origine,
        'detail': detail,
        'date': date,
        'lien': lien,
    }
    if corbeille:
        photo['restauration'] = reverse(
            'btp:project_photo_restore', args=[project.pk, cle, pk])
        photo['corbeille_le'] = corbeille_le
        photo['jours_restants'] = jours_restants(corbeille_le)
    else:
        photo['suppression'] = _url_de_suppression(project, cle, pk)
    return photo


def jours_restants(corbeille_le):
    """Combien de jours avant la suppression définitive. 0 si c'est passé."""
    from django.utils import timezone

    if corbeille_le is None:
        return None
    limite = corbeille_le + timedelta(days=DUREE_DE_CONSERVATION_JOURS)
    restant = limite - timezone.now()
    return max(0, restant.days + (1 if restant.seconds else 0))


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
    noms = project.project_documents.filter(
        corbeille_le__isnull=True).values_list('file', flat=True)
    total = sum(1 for nom in noms if est_une_image(nom))

    total += ReservationPhoto.objects.filter(
        reservation__project=project,
        corbeille_le__isnull=True).count()

    total += ProjectStepItem.objects.filter(
        step__project=project,
        photo_corbeille_le__isnull=True).exclude(
        answer_photo='').exclude(answer_photo__isnull=True).count()

    return total
