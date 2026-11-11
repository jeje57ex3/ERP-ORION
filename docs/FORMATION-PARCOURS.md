# Parcours de formation : étapes, quiz, validation terrain

Écrit pour qui monte une formation dans Orion ERP et pour qui valide les
compétences sur le terrain.

## Les trois étapes, et ce que chacune prouve

| Étape | Ce qu'elle prouve | Qui décide |
|---|---|---|
| **1. Les chapitres** | la personne a **lu** | le logiciel (progression des pages) |
| **2. Le quiz** | elle a **retenu** | le logiciel (note minimale) |
| **3. Le terrain** | elle sait **faire** | un responsable, sur place |

Aucune des deux premières ne démontre la troisième. Un quiz réussi à 100 %
ne dit rien de ce qui se passe sur un chantier ; c'est le constat d'un
responsable présent qui le dit. C'est la troisième qui a une valeur en cas de
contrôle, et c'est la seule que le logiciel ne peut pas décider seul.

## Monter un parcours

### 1. La formation et ses chapitres

Rien ne change : `Formations → Nouvelle`, puis chapitres et pages.

**Nouveau : « Imposer l'ordre des chapitres ».** Décoché par défaut. Coché, un
chapitre reste fermé jusqu'à ce que le précédent soit entièrement lu.

À cocher pour un parcours d'habilitation. À laisser décoché pour un support de
référence qu'on consulte par morceaux — imposer un ordre pour « comment saisir
un avoir » n'a aucun sens.

Un chapitre **sans page publiée** ne verrouille rien : un chapitre en cours de
rédaction bloquerait sinon tout le parcours, et seul l'auteur du support
pourrait débloquer la situation.

### 2. Les compétences visées

`Réglages → Administration → Compétences`.

Une compétence est un savoir-faire **constatable**, écrit de façon observable :
« sait consigner une installation avant intervention », pas « connaît la
sécurité ».

Elle est **séparée de la formation**, et c'est le point : le support sera
refait, renommé, remplacé, tandis que l'exigence reste la même. Plusieurs
formations peuvent viser la même compétence.

**Validité (mois)** : 0 = sans expiration. Au-delà, la validation devra être
renouvelée. Une habilitation acquise en 2019 ne dit plus rien de 2026.

Rattachez ensuite les compétences à la formation (champ « Compétences
visées »).

### 3. Le quiz

`Réglages → Administration → Quiz` → un quiz par formation.

- **Note minimale** : pourcentage de bonnes réponses exigé.
- **Tentatives max** : 0 = illimité. Un quiz qu'on repasse indéfiniment finit
  par être réussi par élimination.
- **Mélanger les questions** : contre la mémorisation de l'ordre.
- **Montrer les corrections** : à décocher si le quiz sert de contrôle et non
  d'apprentissage.

Les questions se créent depuis la page du quiz ; **les choix se saisissent en
ouvrant chaque question** (l'admin Django n'imbrique pas deux niveaux).

Trois types : une seule bonne réponse, plusieurs, vrai/faux. Pour « plusieurs »,
il faut **toutes les bonnes et aucune mauvaise** — une réponse partielle est
fausse.

⚠️ Une question **sans bonne réponse déclarée** est comptée fausse pour tout le
monde. La liste des questions affiche « ⚠ aucune » dans ce cas : c'est une
erreur de saisie, et la compter juste offrirait des points gratuits en la
masquant.

## Suivre un parcours (apprenant)

`Formations → une formation → Mon parcours`.

La page montre les trois étapes, ce qui est ouvert et ce qui ne l'est pas, avec
la raison. Le quiz s'ouvre quand toutes les pages ont été lues ; la validation
terrain quand le quiz est réussi.

**Abandonner un quiz ne consomme pas une tentative** : elle reste ouverte et se
reprend. Seule la remise est comptée.

`Formations → Mes compétences` liste ce qui est acquis, ce qui attend un
constat, et ce qui a **expiré** — affiché à part, parce qu'une habilitation
expirée n'est pas une habilitation.

## Valider sur le terrain (responsable)

`Formations → Validations terrain`.

Chaque demande porte le nom de la personne, la compétence et sa description
observable. Vous saisissez la **date du constat** (celle où vous l'avez vue à
l'œuvre, pas celle de la saisie), le **lieu ou chantier**, un commentaire, et
une pièce jointe facultative. Trois issues : **Validée**, **À revoir**,
**Refusée**.

**Un apprenant ne peut pas valider sa propre compétence.** La règle est
appliquée dans le service, pas seulement dans l'écran : une autre vue, une API
ou un import passeraient par le même contrôle. Vos propres demandes
n'apparaissent donc pas dans cette liste.

## Ce qui est figé, et pourquoi

Deux valeurs sont enregistrées au moment du fait et ne bougent plus :

- **la note minimale** du quiz, au moment de la tentative. L'abaisser plus tard
  ne transforme pas rétroactivement un échec en réussite ;
- **l'échéance** de la validation, calculée depuis la validité de la compétence
  au moment du constat. Rallonger la validité ne prolonge pas une habilitation
  déjà délivrée.

Une formation notée **terminée le reste**, même si le support s'allonge
ensuite. Retirer une réussite acquise parce qu'un chapitre a été ajouté après
coup serait injuste et incompréhensible.

## Ce qui n'est pas fait

- **Un constructeur de quiz dédié.** La saisie passe par l'admin Django, qui
  est une interface et non un terminal. Un écran sur mesure serait plus
  agréable ; il n'est pas nécessaire pour que la fonction serve.
- **Les quiz intermédiaires par chapitre.** Un seul quiz par formation, « à la
  fin ». Des quiz de chapitre seraient une autre fonctionnalité.
- **Le rappel automatique avant expiration.** Les compétences expirées sont
  visibles sur « Mes compétences » ; aucun courriel n'est envoyé. Le planifier
  est possible maintenant que le planificateur a un horaire (voir
  `apps/system_health/migrations/0007_planifier_les_taches.py`).
- **Le débordement des tentatives.** Quand elles sont épuisées, l'écran dit
  qu'un responsable doit débloquer la personne — mais le bouton de déblocage
  n'existe pas encore ; il faut passer par l'admin.
