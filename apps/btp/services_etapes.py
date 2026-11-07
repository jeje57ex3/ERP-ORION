"""apps/btp/services_etapes.py — appliquer un modèle de chantier.

Un modèle de chantier décrit les étapes et, dans chaque étape, les points à
remplir. Ce module fait le passage du modèle au chantier.

Le mot qui gouverne tout le fichier est RECOPIER. Les étapes et les points
sont dupliqués dans le chantier, et non référencés. Trois raisons, dont la
dernière est la vraie :

  1. Retoucher un modèle ne doit pas réécrire un chantier en cours.
  2. Un chantier doit pouvoir diverger — ajouter une étape, en retirer une.
  3. Une question à laquelle on a répondu ne doit pas changer de sens après
     coup. « Nacelle nécessaire ? » répondu « oui » en mars ne peut pas
     devenir « Échafaudage nécessaire ? » parce qu'on a corrigé le modèle en
     juin : la réponse resterait, la question aurait changé.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import (
    ProjectPlanStep,
    ProjectStepItem,
    ProjectTemplate,
    ProjectTemplateItem,
)


def modele_par_defaut(company):
    """Le modèle à proposer quand l'utilisateur n'en choisit pas.

    Retourne None s'il n'y en a aucun — ce n'est pas une anomalie : une
    entreprise qui n'a pas encore écrit de modèle crée des chantiers sans
    étapes, exactement comme avant.
    """
    return ProjectTemplate.objects.filter(
        company=company, is_active=True, is_default=True).first()


def modeles_disponibles(company):
    return ProjectTemplate.objects.filter(company=company, is_active=True)


@transaction.atomic
def appliquer_le_modele(project, template, remplacer=False):
    """Crée les étapes du chantier à partir du modèle. Retourne leur nombre.

    `remplacer=False` et un chantier qui a déjà des étapes : on ne fait
    RIEN et l'on retourne 0. C'est voulu. Appliquer un modèle par-dessus
    des étapes existantes les doublerait, et les réponses déjà saisies se
    retrouveraient noyées dans une seconde copie vide des mêmes questions —
    sans qu'on sache laquelle est la bonne.

    `remplacer=True` supprime les étapes existantes, donc aussi les
    réponses qui y pendent (CASCADE). L'appelant doit avoir fait confirmer.
    """
    if template is None:
        return 0

    existantes = ProjectPlanStep.objects.filter(project=project)
    if existantes.exists():
        if not remplacer:
            return 0
        existantes.delete()

    debut = project.start_date
    cree = 0

    for etape_modele in template.steps.all().order_by('order', 'pk'):
        # La date prévue n'est proposée que si l'on sait d'où compter. Sans
        # date de début de chantier, un décalage en jours ne désigne rien :
        # mieux vaut une étape sans date qu'une date fausse, qu'on prendrait
        # pour un engagement.
        date_prevue = None
        if debut is not None and etape_modele.offset_days is not None:
            date_prevue = debut + timedelta(days=etape_modele.offset_days)

        etape = ProjectPlanStep.objects.create(
            project=project,
            name=etape_modele.name,
            step_type=etape_modele.step_type,
            order=etape_modele.order,
            planned_date=date_prevue,
            status='pending',
            visible_to_client=etape_modele.visible_to_client,
            client_can_validate=etape_modele.client_can_validate,
        )
        cree += 1

        points = ProjectTemplateItem.objects.filter(
            step=etape_modele).order_by('order', 'pk')
        ProjectStepItem.objects.bulk_create([
            ProjectStepItem(
                step=etape,
                label=point.label,
                help_text=point.help_text,
                answer_type=point.answer_type,
                unit=point.unit,
                # list(...) et non la liste elle-même : un JSONField rend
                # l'objet Python tel quel, et partager la liste entre le
                # modèle et ses copies ferait qu'une modification ici se
                # verrait là.
                options=list(point.options or []),
                is_required=point.is_required,
                order=point.order,
            )
            for point in points
        ])

    return cree


def points_manquants(project):
    """Les points obligatoires qui n'ont pas de réponse, étape par étape.

    Retourne une liste de dictionnaires {etape, points}. Sert à AVERTIR et
    jamais à bloquer : un chantier avance souvent avant que tout soit
    renseigné, et refuser d'enregistrer ferait inventer des réponses — ce
    qui est pire qu'une case vide, parce qu'une case vide se voit.
    """
    manquants = []
    etapes = (ProjectPlanStep.objects
              .filter(project=project)
              .prefetch_related('items')
              .order_by('order', 'pk'))

    for etape in etapes:
        vides = [point for point in etape.items.all()
                 if point.is_required and not point.is_answered]
        if vides:
            manquants.append({'etape': etape, 'points': vides})

    return manquants


def compter_les_points_manquants(project):
    """Le nombre total de points obligatoires sans réponse."""
    return sum(len(bloc['points']) for bloc in points_manquants(project))


def avancement_des_points(etape):
    """(remplis, total) pour une étape, pour afficher « 3 / 7 »."""
    points = list(etape.items.all())
    return sum(1 for point in points if point.is_answered), len(points)


def _valeur_de_la_reponse(point):
    """La réponse courante, sous une forme comparable.

    Sert à savoir si l'enregistrement change quelque chose. On lit la
    colonne du TYPE du point et non toutes les colonnes : comparer les six
    rendrait « différent » un point dont on vient simplement de nettoyer
    une colonne inutilisée.
    """
    if point.answer_type == 'yes_no':
        return point.answer_boolean
    if point.answer_type == 'number':
        return point.answer_number
    if point.answer_type == 'date':
        return point.answer_date
    if point.answer_type == 'choice':
        return point.answer_choice
    if point.answer_type == 'photo':
        # Le NOM du fichier : deux FieldFile distincts désignant le même
        # fichier ne sont pas égaux entre eux.
        return point.answer_photo.name or ''
    return point.answer_text


def enregistrer_la_reponse(point, donnees, user=None):
    """Écrit la réponse dans la colonne correspondant à son type.

    Les colonnes scalaires des AUTRES types sont remises à vide. Sans cela,
    une valeur traînerait dans sa colonne d'origine : `is_answered` regarde
    la colonne du type courant, mais une recherche sur l'ancienne colonne
    retrouverait un chantier qui n'a plus cette réponse.

    La photo, elle, n'est PAS effacée par ce nettoyage, et c'est volontaire :
    c'est un fichier, et le supprimer sans que personne l'ait demandé est
    irréversible. Elle ne part que sur la case « effacer » du champ, que
    Django rend par `False` dans cleaned_data.

    `donnees` est le cleaned_data du formulaire dynamique, dont les clés
    sont préfixées par l'identifiant du point.

    **« Rempli le » ne bouge que si la réponse bouge.** Le formulaire poste
    les cinquante points de l'étape à chaque enregistrement, qu'on les ait
    touchés ou non. Horodater sans comparer ferait dire « rempli
    aujourd'hui » à une réponse saisie il y a trois mois, à chaque fois
    qu'on revient corriger un autre point — et la colonne, qui doit dire
    quand l'information a été relevée, ne dirait plus que la date du dernier
    passage sur l'écran.
    """
    cle = f'point_{point.pk}'
    valeur = donnees.get(cle)
    avant = _valeur_de_la_reponse(point)

    point.answer_boolean = None
    point.answer_text = ''
    point.answer_number = None
    point.answer_date = None
    point.answer_choice = ''

    if point.answer_type == 'yes_no':
        # '' = pas de réponse, et c'est distinct de False. Un ChoiceField à
        # trois états ('', 'oui', 'non') est le seul moyen de les séparer :
        # une case à cocher ne sait pas dire « je ne sais pas encore ».
        if valeur in ('true', 'True', True):
            point.answer_boolean = True
        elif valeur in ('false', 'False', False):
            point.answer_boolean = False
    elif point.answer_type == 'number':
        point.answer_number = valeur
    elif point.answer_type == 'date':
        point.answer_date = valeur
    elif point.answer_type == 'choice':
        point.answer_choice = valeur or ''
    elif point.answer_type == 'photo':
        # ClearableFileInput rend TROIS choses, et les confondre coûte cher :
        #   None  → rien n'a été envoyé, on garde la photo en place
        #   False → la case « effacer » a été cochée, on la retire
        #   fichier → une nouvelle photo
        # Un simple `if valeur:` traite False comme None, et la case
        # « effacer » n'efface alors rien — sans message d'erreur, donc sans
        # qu'on comprenne pourquoi.
        if valeur is False:
            point.answer_photo.delete(save=False)
        elif valeur:
            point.answer_photo = valeur
    else:
        point.answer_text = valeur or ''

    commentaire = donnees.get(f'commentaire_{point.pk}')
    if commentaire is not None:
        point.comment = commentaire

    if not point.is_answered:
        # Une réponse retirée emporte sa traçabilité : sinon « rempli le
        # 3 mars par Untel » reste affiché sous une case vide.
        point.filled_by = None
        point.filled_at = None
    elif _valeur_de_la_reponse(point) != avant:
        point.filled_by = user if (user and user.is_authenticated) else None
        point.filled_at = timezone.now()

    point.save()
    return point
