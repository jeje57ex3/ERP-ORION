"""apps/fiscal_pt/schema.py — Vérifier le SAF-T contre le schéma de l'AT.

POURQUOI CE MODULE EXISTE

Les tests figent l'ordre des éléments d'après le schéma, mais ils le
figent d'après une LECTURE du schéma. Ici on lit le schéma lui-même :
`schemas/SAFTPT1.04_01.xsd`, tel que l'AT le publie. Un fichier produit
par l'ERP se compare donc à la source, et non à notre compréhension
d'elle.

C'est le critère d'acceptation réel. Un export remis à l'administration
passe par ce validateur ; mieux vaut découvrir un élément déplacé ici
que dans le courriel de rejet.

POURQUOI PAS `lxml`

`lxml` valide un XSD complètement, et c'est une dépendance compilée de
plus dans un projet qui n'en a pas besoin ailleurs. Le XSD est du XML :
on en extrait le modèle de contenu avec la bibliothèque standard, et on
vérifie ce qui fait rejeter un fichier en pratique — ordre des éléments,
éléments obligatoires absents, éléments inconnus.

CE QUE CE VALIDATEUR NE FAIT PAS

Il ne vérifie pas les types simples : longueurs maximales, motifs,
énumérations, bornes numériques. Il vérifie la STRUCTURE. Un
`TaxRegistrationNumber` de douze chiffres passerait ici et serait refusé
par l'AT — c'est dit franchement plutôt que laissé à supposer.

LA SUBTILITÉ QUI COMMANDE TOUTE LA CONCEPTION

Le schéma définit QUATRE `Line` différents, et quatre `DocumentStatus` :
un par famille de documents (ventes, mouvements de marchandises,
documents de travail, paiements). Celui des mouvements n'a ni `TaxBase`
ni `References` ; celui des paiements n'a même pas `ProductCode`.

Un validateur qui chercherait les définitions PAR NOM prendrait donc la
mauvaise au hasard — et accepterait un fichier faux, ou refuserait un
fichier juste. Le modèle est donc indexé par CHEMIN, et c'est pour cela
qu'il se construit en descendant depuis `AuditFile`.
"""

from pathlib import Path
from xml.etree import ElementTree as ET

XS = '{http://www.w3.org/2001/XMLSchema}'
ESPACE_DE_NOMS = 'urn:OECD:StandardAuditFile-Tax:PT_1.04_01'

#: Le schéma publié par l'AT, versé dans le dépôt pour que la
#: vérification soit reproductible sans accès au réseau.
FICHIER_XSD = Path(__file__).parent / 'schemas' / 'SAFTPT1.04_01.xsd'

#: Profondeur maximale de descente. Le schéma n'est pas récursif, mais une
#: version future qui le deviendrait ferait tourner la construction sans
#: fin — et sans message.
PROFONDEUR_MAXIMALE = 12


class ErreurDeSchema(Exception):
    """Le schéma lui-même n'a pas pu être lu."""


class Anomalie:
    """Un écart entre le fichier et le schéma, dit en clair."""

    def __init__(self, chemin, message):
        self.chemin = chemin
        self.message = message

    def __str__(self):
        return f'{self.chemin} : {self.message}'

    def __repr__(self):
        return f'<Anomalie {self.chemin} : {self.message}>'

    def __eq__(self, autre):
        return (isinstance(autre, Anomalie)
                and (self.chemin, self.message) == (autre.chemin, autre.message))


class Modele:
    """Le modèle de contenu du schéma, indexé par chemin.

    `enfants['AuditFile/Header']` rend la liste ordonnée des noms
    d'éléments que `Header` peut contenir, `obligatoires` ceux dont
    `minOccurs` n'est pas zéro, et `alternatives` les groupes de `choice`
    — dont il faut exactement un membre et non chacun.
    """

    def __init__(self, enfants, obligatoires, alternatives):
        self.enfants = enfants
        self.obligatoires = obligatoires
        self.alternatives = alternatives

    def ordre(self, chemin):
        return self.enfants.get(chemin)

    def exiges(self, chemin):
        return self.obligatoires.get(chemin, ())

    def alternatives_de(self, chemin):
        return self.alternatives.get(chemin, ())


#: Nombre minimal de chemins attendus dans le modèle.
#:
#: UN VALIDATEUR QUI NE CONNAÎT RIEN ACCEPTE TOUT, et c'est le pire des
#: défauts possibles ici : il annoncerait « structure conforme » sur
#: n'importe quel fichier.
#:
#: Mesure : une première version lisait l'attribut `name` des
#: déclarations d'éléments. Or le schéma déclare `Header`, `Customer`,
#: `Invoice` et la plupart des autres comme éléments GLOBAUX, référencés
#: par `ref=` — où `name` est absent. Le modèle connaissait DEUX chemins
#: au lieu de plus de cent, et validait tout sans rien vérifier.
#:
#: Ce plancher transforme ce silence en erreur.
CHEMINS_MINIMAUX = 60


def _types_nommes(racine):
    return {ct.get('name'): ct for ct in racine.findall(f'{XS}complexType')
            if ct.get('name')}


def _elements_globaux(racine):
    """Les déclarations d'éléments de premier niveau, par nom.

    Le schéma s'en sert massivement : un élément imbriqué est le plus
    souvent un `ref=` vers l'une d'elles.
    """
    return {e.get('name'): e for e in racine.findall(f'{XS}element')
            if e.get('name')}


def _nom_de_declaration(declaration):
    """Le nom d'une déclaration, qu'elle soit locale ou un `ref=`."""
    nom = declaration.get('name')
    if nom:
        return nom
    reference = declaration.get('ref')
    return reference.split(':')[-1] if reference else None


def _sequence_de(noeud, types, dans_un_choix=False):
    """Les déclarations d'éléments d'un modèle de contenu, dans l'ordre.

    Rend des couples (déclaration, appartient à un `choice`).

    POURQUOI LE `choice` DOIT ÊTRE SUIVI, ET PAS SEULEMENT APLATI

    Un `choice` entre `DebitAmount` et `CreditAmount` se lit bien comme
    deux positions possibles dans l'ORDRE — l'aplatir suffit pour cela.
    Mais ses branches ne sont pas obligatoires INDIVIDUELLEMENT : une
    ligne de facture porte l'une ou l'autre, jamais les deux.

    Mesure : une première version les comptait chacune obligatoire. Le
    validateur réclamait alors `DebitAmount` sur une facture et
    `TaxAmount` à côté d'un `TaxPercentage` — quatre anomalies annoncées
    sur un fichier parfaitement conforme. Un validateur qui crie à tort
    finit par être ignoré, ce qui est aussi grave qu'un validateur muet.
    """
    rendu = []

    for enfant in noeud:
        tag = enfant.tag.replace(XS, '')
        if tag == 'element':
            rendu.append((enfant, dans_un_choix))
        elif tag == 'choice':
            rendu.extend(_sequence_de(enfant, types, dans_un_choix=True))
        elif tag in ('sequence', 'all'):
            rendu.extend(_sequence_de(enfant, types, dans_un_choix))
        elif tag in ('complexType', 'complexContent', 'extension'):
            rendu.extend(_sequence_de(enfant, types, dans_un_choix))

    return rendu


def _modele_de_contenu(declaration, types):
    """Le modèle de contenu d'une déclaration d'élément.

    Soit un `complexType` en ligne, soit un type nommé référencé par
    l'attribut `type`. Un type simple ne contient pas d'éléments : on rend
    alors une liste vide, et le validateur sait que l'élément est une
    feuille.
    """
    for enfant in declaration:
        if enfant.tag == f'{XS}complexType':
            return _sequence_de(enfant, types)

    nom_de_type = declaration.get('type')
    if nom_de_type:
        # Les types du schéma ne portent pas de préfixe : l'espace de noms
        # par défaut du XSD est celui du SAF-T.
        nom_de_type = nom_de_type.split(':')[-1]
        complexe = types.get(nom_de_type)
        if complexe is not None:
            return _sequence_de(complexe, types)

    return []


def charger(fichier=None):
    """Construit le modèle en descendant depuis `AuditFile`.

    La descente par chemin est ce qui distingue les quatre `Line` du
    schéma. Voir l'en-tête du module : c'est la raison d'être de toute
    cette mécanique.
    """
    chemin_xsd = Path(fichier) if fichier else FICHIER_XSD

    try:
        racine = ET.parse(chemin_xsd).getroot()
    except Exception as exc:
        raise ErreurDeSchema(
            f'Schéma illisible ({chemin_xsd}) : {exc}')

    types = _types_nommes(racine)
    globaux = _elements_globaux(racine)

    depart = globaux.get('AuditFile')
    if depart is None:
        raise ErreurDeSchema(
            'Le schéma ne déclare pas d’élément « AuditFile » : ce n’est '
            'pas un schéma SAF-T (PT).')

    enfants = {}
    obligatoires = {}
    alternatives = {}

    def descendre(declaration, chemin, profondeur):
        if profondeur > PROFONDEUR_MAXIMALE:
            raise ErreurDeSchema(
                f'Descente trop profonde à « {chemin} » : le schéma est-il '
                'devenu récursif ?')

        sous_elements = _modele_de_contenu(declaration, types)
        if not sous_elements:
            return

        enfants[chemin] = [_nom_de_declaration(e)
                           for e, _ in sous_elements]

        # `minOccurs` est lu sur le SITE de la référence, pas sur la
        # déclaration globale : le même élément peut être obligatoire ici
        # et facultatif ailleurs.
        #
        # Les branches d'un `choice` sont ÉCARTÉES des obligatoires : on
        # en exige une, pas chacune. Voir `_sequence_de`.
        obligatoires[chemin] = tuple(
            _nom_de_declaration(e) for e, en_choix in sous_elements
            if e.get('minOccurs') != '0' and not en_choix)

        groupe = tuple(_nom_de_declaration(e)
                       for e, en_choix in sous_elements if en_choix)
        if groupe:
            alternatives[chemin] = (groupe,)

        for sous, _ in sous_elements:
            nom = _nom_de_declaration(sous)
            if not nom:
                continue

            # Un `ref=` n'a pas de modèle de contenu : il faut descendre
            # dans la déclaration GLOBALE qu'il désigne. Sans cette
            # résolution, le modèle s'arrêtait au deuxième niveau.
            cible = sous if sous.get('name') else globaux.get(nom, sous)
            descendre(cible, f'{chemin}/{nom}', profondeur + 1)

    descendre(depart, 'AuditFile', 0)

    if len(enfants) < CHEMINS_MINIMAUX:
        raise ErreurDeSchema(
            f'Le modèle n’a que {len(enfants)} chemin(s), là où le schéma '
            f'1.04_01 en donne plus de {CHEMINS_MINIMAUX}. Un validateur '
            'qui ne connaît presque rien accepte tout : il annoncerait '
            '« structure conforme » sur n’importe quel fichier. Lecture du '
            'schéma à revoir avant de s’y fier.')

    return Modele(enfants, obligatoires, alternatives)


def _nom_local(element):
    return element.tag.split('}')[-1]


def valider(contenu, modele=None):
    """Compare un fichier SAF-T au schéma. Rend la liste des anomalies.

    Une liste vide signifie que la STRUCTURE est conforme — pas que le
    fichier serait accepté : les types simples ne sont pas vérifiés ici.
    Voir l'en-tête du module.
    """
    modele = modele or charger()

    try:
        racine = (ET.fromstring(contenu) if isinstance(contenu, (bytes, str))
                  else contenu)
    except ET.ParseError as exc:
        return [Anomalie('(fichier)', f'XML illisible : {exc}')]

    anomalies = []

    if _nom_local(racine) != 'AuditFile':
        anomalies.append(Anomalie(
            '(racine)',
            f'La racine est « {_nom_local(racine)} » et non « AuditFile ».'))
        return anomalies

    if not racine.tag.startswith('{'):
        anomalies.append(Anomalie(
            'AuditFile',
            'Aucun espace de noms déclaré. L’AT attend '
            f'« {ESPACE_DE_NOMS} » : sans lui le fichier est rejeté avant '
            'toute autre vérification.'))
    elif racine.tag[1:].split('}')[0] != ESPACE_DE_NOMS:
        anomalies.append(Anomalie(
            'AuditFile',
            f'Espace de noms « {racine.tag[1:].split("}")[0]} » au lieu de '
            f'« {ESPACE_DE_NOMS} ».'))

    def verifier(element, chemin):
        attendus = modele.ordre(chemin)

        observes = [_nom_local(e) for e in element]

        if attendus is None:
            # Une feuille du schéma qui porte des enfants : c'est un
            # élément simple qu'on a rempli d'éléments.
            if observes:
                anomalies.append(Anomalie(
                    chemin,
                    f'Le schéma attend une valeur simple ici, et le fichier '
                    f'contient {", ".join(observes)}.'))
            return

        inconnus = [nom for nom in observes if nom not in attendus]
        for nom in inconnus:
            anomalies.append(Anomalie(
                f'{chemin}/{nom}',
                'Élément inconnu du schéma à cet endroit. Attendus : '
                f'{", ".join(attendus)}.'))

        # L'ORDRE : les éléments observés doivent suivre celui du schéma.
        #
        # On compare les POSITIONS plutôt que de reconstruire une
        # sous-séquence : cela permet de nommer l'élément fautif ET celui
        # qu'il précède à tort. Le validateur de l'AT, lui, désigne
        # l'élément suivant — ce qui envoie chercher le défaut au mauvais
        # endroit.
        position = -1
        precedent = None
        for nom in observes:
            if nom in inconnus:
                continue
            rang = attendus.index(nom)
            if rang < position:
                anomalies.append(Anomalie(
                    f'{chemin}/{nom}',
                    f'Placé après « {precedent} », alors que le schéma le '
                    f'veut avant. Ordre attendu : {", ".join(attendus)}.'))
            else:
                position = rang
                precedent = nom

        manquants = [nom for nom in modele.exiges(chemin)
                     if nom not in observes]
        for nom in manquants:
            anomalies.append(Anomalie(
                f'{chemin}/{nom}',
                'Élément obligatoire absent.'))

        # Les groupes d'alternatives : UN membre, pas chacun.
        for groupe in modele.alternatives_de(chemin):
            presents = [nom for nom in groupe if nom in observes]
            if not presents:
                anomalies.append(Anomalie(
                    chemin,
                    'Aucun de ces éléments, alors que le schéma en demande '
                    f'un : {" ou ".join(groupe)}.'))
            elif len(presents) > 1:
                anomalies.append(Anomalie(
                    chemin,
                    f'{" et ".join(presents)} sont tous les deux présents, '
                    'alors que le schéma n’en veut qu’un.'))

        for enfant in element:
            nom = _nom_local(enfant)
            if nom in attendus:
                verifier(enfant, f'{chemin}/{nom}')

    verifier(racine, 'AuditFile')
    return anomalies


def resume(anomalies):
    """Une phrase pour l'écran, et la liste pour le détail."""
    if not anomalies:
        return ('Structure conforme au schéma SAF-T (PT) 1.04_01. '
                'Les types simples — longueurs, motifs, énumérations — ne '
                'sont pas vérifiés ici.')
    nombre = len(anomalies)
    return (f'{nombre} anomalie{"s" if nombre > 1 else ""} de structure. '
            'L’AT rejette le fichier entier pour une seule d’entre elles.')
