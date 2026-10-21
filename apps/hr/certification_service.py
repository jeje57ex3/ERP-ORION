"""
apps/hr/certification_service.py — Les habilitations qu'il faut surveiller

Une seule définition de « à surveiller », partagée par l'écran RH et le
widget du tableau de bord. Deux définitions auraient divergé à la première
correction, et le widget aurait annoncé un nombre que l'écran ne confirme
pas — ce qui apprend à ne plus regarder ni l'un ni l'autre.

Pourquoi cet écran existe : `EmployeeCertification` portait déjà
`is_expired` et `expires_soon`, mais rien ne s'en servait au-delà d'une
couleur de ligne sur la fiche du salarié. Pour un CACES ou une
habilitation électrique, c'est précisément l'inverse du besoin : il faut le
savoir **avant** que quelqu'un arrive sur chantier avec un titre périmé,
pas en ouvrant les fiches une par une.
"""

from datetime import date, timedelta

# Seuils, du plus grave au plus lointain. « imminente » à 30 jours parce
# qu'un renouvellement de CACES demande de réserver une session de
# formation : prévenir la veille ne sert à rien.
JOURS_IMMINENTE = 30
JOURS_PROCHE = 90

LIBELLES_STATUT = {
    'expiree': 'Expirée',
    'imminente': 'Expire sous 30 jours',
    'proche': 'Expire sous 90 jours',
}

ORDRE_STATUT = {'expiree': 0, 'imminente': 1, 'proche': 2}


def statut_echeance(certification, aujourdhui=None):
    """'expiree', 'imminente', 'proche', ou None si rien à signaler.

    None couvre deux cas très différents et c'est voulu : une échéance
    lointaine, et une certification SANS date d'expiration — un diplôme, par
    exemple, qui ne périme pas. Les distinguer ici obligerait chaque
    appelant à traiter un troisième cas pour rien.
    """
    if not certification.expiry_date:
        return None
    reference = aujourdhui or date.today()
    if certification.expiry_date < reference:
        return 'expiree'
    restants = (certification.expiry_date - reference).days
    if restants <= JOURS_IMMINENTE:
        return 'imminente'
    if restants <= JOURS_PROCHE:
        return 'proche'
    return None


def certifications_a_surveiller(company, jours=JOURS_PROCHE,
                                inclure_expirees=True, aujourdhui=None):
    """Les habilitations expirées ou proches de l'être, les plus graves d'abord.

    Deux filtres qui ne vont pas de soi :

    `is_active=True` sur la certification — une habilitation explicitement
    désactivée a été remplacée ou retirée ; la signaler comme expirée
    remettrait du bruit déjà traité.

    `employee__is_active=True` — le CACES périmé d'un salarié parti n'est
    pas un risque, c'est de l'archive. Le laisser remonterait ferait grossir
    la liste jusqu'à ce qu'on cesse de la lire.

    Retourne une liste de dict {certification, statut, libelle, jours_restants}.
    """
    from .models import EmployeeCertification

    reference = aujourdhui or date.today()
    limite = reference + timedelta(days=jours)

    requete = EmployeeCertification.objects.filter(
        employee__company=company,
        employee__is_active=True,
        is_active=True,
        expiry_date__isnull=False,
        expiry_date__lte=limite,
    ).select_related('employee')

    if not inclure_expirees:
        requete = requete.filter(expiry_date__gte=reference)

    lignes = []
    for certification in requete:
        statut = statut_echeance(certification, reference)
        if statut is None:
            continue
        restants = (certification.expiry_date - reference).days
        lignes.append({
            'certification': certification,
            'statut': statut,
            'libelle': LIBELLES_STATUT[statut],
            'jours_restants': restants,
            # Valeur absolue fournie ici, et non calculee dans le gabarit.
            # « {% blocktrans count n=jours_restants|cut:"-" %} » semblait
            # suffire : cut rend une CHAINE, et blocktrans count exige un
            # nombre -- TemplateSyntaxError, donc page 500 des qu'une
            # habilitation est expiree. Defaut commis ici, attrape par un
            # test.
            'jours_absolus': abs(restants),
        })

    # Expirées d'abord, puis par date la plus proche. Trier sur la seule
    # date mettrait les expirées en tête de toute façon, mais l'ordre
    # deviendrait faux dès qu'on filtre les expirées.
    lignes.sort(key=lambda ligne: (ORDRE_STATUT[ligne['statut']],
                                   ligne['certification'].expiry_date))
    return lignes


def compter_par_statut(lignes):
    """Les trois compteurs de l'en-tête, calculés sur la liste déjà lue.

    Sur la liste et non par trois requêtes : les chiffres affichés doivent
    décrire exactement le tableau affiché en dessous, sinon l'en-tête
    annonce « 4 expirées » au-dessus d'un tableau qui en montre 3.
    """
    compteurs = {'expiree': 0, 'imminente': 0, 'proche': 0}
    for ligne in lignes:
        compteurs[ligne['statut']] += 1
    compteurs['total'] = len(lignes)
    return compteurs


def peut_voir_certification(utilisateur, certification, company):
    """Qui a le droit d'ouvrir le scan d'une habilitation.

    Un scan de CACES, d'habilitation électrique ou de diplôme est un
    document personnel. Deux accès, et deux seulement : l'encadrement RH, et
    le salarié concerné.

    À ne pas confondre avec le contrôle d'entreprise, qui est nécessaire
    mais très insuffisant : `private_document_download`, dans le même
    module, ne vérifie que l'entreprise — n'importe quel compte connecté y
    télécharge le document privé de n'importe quel collègue. Ce défaut n'est
    pas reproduit ici.
    """
    if certification.employee.company_id != getattr(company, 'pk', None):
        return False
    if utilisateur.is_superuser:
        return True
    profil = getattr(utilisateur, 'profile', None)
    role = getattr(profil, 'role', '') or ''
    if role in ('admin', 'superadmin', 'hr_manager'):
        return True
    return certification.employee.user_id == utilisateur.pk
