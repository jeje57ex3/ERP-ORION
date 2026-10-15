# Modèles de devis

Votre devis vierge, en PDF, sert de modèle. Orion n'y redessine rien : il
écrit par-dessus les seules valeurs qui changent d'un devis à l'autre.

C'est délibérément l'inverse d'un générateur de PDF. Redessiner la mise en page
supposerait de reproduire votre charte dans du code, de la maintenir à chaque
changement de papier à en-tête, et d'expliquer pourquoi le rendu diffère de
l'original. La superposition laisse le document tel que vous l'avez voulu, au
pixel près.

## En trois étapes

**1. Déposez votre devis vierge.** `Devis ▸ Modèles de devis ▸ Nouveau modèle`.
Un PDF, mis en page comme vous l'entendez — en-tête, logo, conditions
générales, mentions légales. Le fichier est vérifié à l'envoi : une extension
`.pdf` sur un fichier qui n'en est pas un est refusée tout de suite, et non à
la première génération de devis.

**2. Placez les cadres.** Bouton **Cadres**. Votre PDF s'affiche tel qu'il
est. À gauche, la liste des valeurs : cliquez « Nom du client », un cadre
apparaît, glissez-le à sa place, étirez-le par le coin bas-droit.

| Geste | Effet |
|---|---|
| Glisser le cadre | le déplacer |
| Coin bas-droit | le redimensionner |
| Flèches | déplacer d'un point |
| Maj + flèches | dix points |
| Suppr | retirer le cadre |

Un panneau à droite règle la taille du texte, le gras, l'alignement et les
textes avant/après. **Enregistrez une fois** : chaque devis sortira rempli.

> Les coordonnées d'un PDF se comptent en points depuis le coin **bas**
> gauche, alors que l'écran mesure depuis le haut. Les deux axes verticaux
> sont inversés, et c'est exactement ce que l'éditeur fait pour vous — une
> erreur de sens imprimerait en bas ce que vous avez posé en haut, et ne se
> verrait qu'au premier devis envoyé.

La **grille de calage** reste disponible : elle imprime un quadrillage coté
sur votre modèle, utile pour relire un placement ou régler au point près dans
le tableau de coordonnées. Vous n'en avez pas besoin pour placer.

**3. Vérifiez.** Bouton **Aperçu** : votre modèle rempli de valeurs d'exemple.
On règle un modèle avant d'avoir un devis — prévisualiser avec de vraies
données supposerait d'en créer un pour rien. L'aperçu sert à contrôler le
placement, pas les montants.

## Les valeurs disponibles

| Valeur | D'où elle vient |
|---|---|
| Numéro du devis | attribué automatiquement, numérotation atomique |
| Date, Date de validité | du devis |
| Numéro de client | code du client |
| Nom du client | raison sociale |
| Nom et prénom du contact | contact de la fiche client |
| Adresse, Email, Téléphone | fiche client |
| Objet | du devis |
| Total HT, Total TVA, Total TTC | calculés depuis les lignes |
| Délai de paiement | du devis |
| Commercial | commercial affecté, ou créateur |

Chaque valeur accepte un **texte avant** et un **texte après** — « N° »,
« € », « jours » — une **taille**, le **gras**, et un **alignement** (à
gauche, à droite, centré). L'alignement à droite compte pour les montants :
aligné à gauche, un total déborde de sa colonne.

Un champ dont la valeur est vide **n'imprime rien**, pas même son texte avant :
« Client : » suivi du vide ferait croire à une donnée perdue.

## Si le texte dépasse du cadre

Il est **réduit** pour y tenir, plutôt que de déborder sur ce qui se trouve à
côté — une colonne voisine, sur un devis. La réduction s'arrête à 5 points :
en dessous, le texte serait illisible, et un débordement visible vaut mieux
qu'une ligne qu'on ne peut pas lire. Si cela arrive, agrandissez le cadre.

## Les montants

Format français : `12 400,00`. Le séparateur de milliers est une espace
insécable, pour que le montant ne soit jamais coupé en fin de ligne.

> Vérifié, et c'est pourquoi ce n'est pas l'espace *fine* que la typographie
> française préférerait : les polices standard du PDF utilisent l'encodage
> WinAnsi, qui ne contient pas ce caractère. Le générateur y substitue un
> carré noir, et votre client recevrait « 12■400,00 ».

## Créer un devis

Deux chemins, selon ce dont vous partez :

| Chemin | Quand |
|---|---|
| `Devis ▸ Nouveau devis depuis un modèle` | vous choisissez le modèle et le client ; numéro, date et objet sont posés |
| `Devis ▸ un devis ▸ PDF` | le devis existe déjà ; le bouton le rend sur son modèle |

Le modèle par défaut est utilisé quand aucun n'est précisé. Un seul modèle peut
l'être à la fois : « le » modèle par défaut dépendrait sinon de l'ordre de tri,
donc du hasard.

## Ce que le modèle ne fait pas

**Il ne porte pas les lignes du devis.** Il porte la mise en page et
l'emplacement des valeurs. Les lignes restent à saisir, ou viennent du
configurateur public, ou d'un devis guidé BTP.

Placer les lignes automatiquement est possible, mais demande autre chose qu'un
emplacement : un point de départ, une hauteur de ligne, un nombre maximal avant
de passer à la page suivante, et une décision sur ce qu'il advient d'un devis
de quarante lignes sur un modèle d'une page. Dites-le si vous en avez besoin.

## Si quelque chose ne sort pas

| Symptôme | Cause |
|---|---|
| Le PDF sort vierge, sans aucune valeur | aucun cadre placé — la liste des modèles le signale |
| Une valeur sort au mauvais endroit | le cadre a été posé ailleurs : rouvrez **Cadres**, l'aperçu montre le résultat réel |
| « Ce PDF n'est pas lisible » | le fichier est corrompu ou n'est pas un PDF ; redéposez-le |
| Le texte est plus petit que prévu | il ne tenait pas dans le cadre et a été réduit ; agrandissez le cadre |
| Une valeur manque | son champ est placé sur une page que le modèle n'a pas ; la génération le dit en nommant la page |
| « Aucun modèle de devis actif » | aucun modèle, ou tous décochés `Actif` |
| Un carré noir à la place d'un caractère | un texte avant/après contient un caractère hors WinAnsi (un tiret cadratin, une espace fine) |
