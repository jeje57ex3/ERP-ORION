"""Qui a le droit de lire le dossier prive d'un salarie.

Les documents de `EmployeePrivateDocument` sont les plus sensibles de
l'ERP : contrat de travail, bulletin de paie, piece d'identite, RIB, visite
medicale, sanction disciplinaire. Le modele porte deja tout ce qu'il faut
pour les proteger -- un `confidentiality_level` a cinq niveaux et un
`visible_to_employee` -- et AUCUNE vue ne les lisait.

Les six vues de `dossiers-prives/` ne verifiaient que l'entreprise. Dans
une entreprise de vingt salaries, les vingt pouvaient lister les dossiers
de tous, ouvrir le journal de qui avait lu quoi, telecharger le bulletin de
paie du voisin, deposer une piece dans son dossier et supprimer la sienne.
Le controle d'entreprise est necessaire et tres insuffisant : il arrete le
client d'une autre societe, pas le collegue du bureau d'a cote.

Les regles, lues sur les intitules du modele et non inventees :

* `hr_only` (« RH uniquement ») exclut le salarie lui-meme.
* `direction_only` (« Direction uniquement ») exclut aussi les RH.
* `visible_to_employee` est la porte du salarie sur son propre dossier,
  et `my_private_documents` la respectait deja.

Un choix a signaler, parce qu'il t'appartient : le role « manager »
(Responsable) n'a **pas** acces. Donner a tout chef d'equipe la lecture des
bulletins de paie et des sanctions disciplinaires de ses subordonnes est
une decision d'entreprise, pas un detail technique -- et rien dans le
modele ne relie un responsable a une equipe. Pour la lui donner, ajoute
'manager' a ROLES_RH ci-dessous.
"""

# La direction : seule a voir les documents « Direction uniquement ».
# Il n'existe pas de role « direction » dans ROLE_CHOICES ; les deux roles
# ci-dessous en sont l'equivalent le plus proche.
ROLES_DIRECTION = ('admin', 'superadmin')

# L'encadrement RH. Ajoute 'manager' ici pour ouvrir aux responsables.
ROLES_RH = ('hr_manager',)

# Niveaux que le salarie ne voit pas, meme coches « visible par le
# salarie » : une incoherence de saisie ne doit pas ouvrir un document
# marque « RH uniquement ».
NIVEAUX_CACHES_AU_SALARIE = ('hr_only', 'direction_only')

# Niveau que les RH ne voient pas non plus.
NIVEAUX_RESERVES_A_LA_DIRECTION = ('direction_only',)


def role_de(utilisateur):
    """Le role du profil, ou une chaine vide.

    Un User sans UserProfile existe (createsuperuser, profil efface) :
    `getattr` en cascade plutot qu'un acces direct qui leverait.
    """
    profil = getattr(utilisateur, 'profile', None)
    return (getattr(profil, 'role', '') or '')


def est_direction(utilisateur):
    if not utilisateur or not utilisateur.is_authenticated:
        return False
    if utilisateur.is_superuser:
        return True
    return role_de(utilisateur) in ROLES_DIRECTION


def est_encadrement_rh(utilisateur):
    """Direction ou RH : ceux qui gerent les dossiers prives."""
    if est_direction(utilisateur):
        return True
    return role_de(utilisateur) in ROLES_RH


def peut_gerer_les_dossiers(utilisateur):
    """Lister les dossiers, ouvrir celui d'un salarie, deposer, supprimer.

    Deliberement plus strict que la lecture d'un document : un salarie ne
    doit pas pouvoir supprimer la sanction disciplinaire qui le concerne,
    ni deposer une piece dans le dossier d'un autre. Son propre dossier, il
    le consulte par `my_private_documents`.
    """
    return est_encadrement_rh(utilisateur)


def salarie_de(utilisateur, company):
    """La fiche salarie rattachee a ce compte dans cette entreprise.

    None si le compte n'est pas un salarie -- prestataire, expert-comptable
    externe, compte de service. C'est un cas normal, pas une erreur.
    """
    from apps.hr.models import Employee

    if not utilisateur or not utilisateur.is_authenticated:
        return None
    if company is None:
        return None
    return Employee.objects.filter(company=company, user=utilisateur).first()


def peut_voir_document(utilisateur, document, company):
    """Le droit de telecharger CE document.

    Trois acces, et trois seulement : la direction, les RH (sauf
    « Direction uniquement »), et le salarie concerne -- si le document lui
    est declare visible et n'est pas marque « RH uniquement » ou
    « Direction uniquement ».
    """
    if not utilisateur or not utilisateur.is_authenticated:
        return False

    # Le controle d'entreprise reste, en premier : il arrete ce qu'aucune
    # regle de role ne verrait, un document d'une autre societe.
    attendu = getattr(company, 'pk', None)
    if attendu is None or document.company_id != attendu:
        return False

    if est_direction(utilisateur):
        return True

    niveau = document.confidentiality_level or 'confidential'

    if role_de(utilisateur) in ROLES_RH:
        return niveau not in NIVEAUX_RESERVES_A_LA_DIRECTION

    # Le salarie concerne. On compare les identifiants de compte plutot que
    # de chercher sa fiche : un document dont l'employe n'a pas de compte
    # rattache (employee.user is None) ne doit s'ouvrir pour personne par
    # cette branche, et None == None serait vrai.
    titulaire = document.employee.user_id
    if titulaire is None or titulaire != utilisateur.pk:
        return False
    if niveau in NIVEAUX_CACHES_AU_SALARIE:
        return False
    return bool(document.visible_to_employee)


def documents_visibles(utilisateur, queryset):
    """Restreint un lot de documents a ceux que cet utilisateur peut voir.

    Pour les listes. Le filtrage se fait en base -- un `exclude` et non une
    comprehension Python -- pour que les compteurs affiches au-dessus d'un
    tableau portent sur les memes lignes que le tableau.
    """
    if est_direction(utilisateur):
        return queryset
    if role_de(utilisateur) in ROLES_RH:
        return queryset.exclude(
            confidentiality_level__in=NIVEAUX_RESERVES_A_LA_DIRECTION)
    return queryset.none()
