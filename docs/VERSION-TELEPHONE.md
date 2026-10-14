# Version téléphone

Une interface servie par le serveur lui-même, pensée pour le pouce, qui permet
de prendre des photos et de rejoindre l'interface complète ou un autre
serveur. Adresse : **`/m/`**.

Rien à installer, rien à publier sur un magasin d'applications : c'est une
page web, donc elle fonctionne depuis n'importe quel téléphone, Android comme
iPhone.

## Les trois pages

| Page | Adresse | Ce qu'elle fait |
|---|---|---|
| Accueil | `/m/` | les actions, pas le menu complet |
| Photo | `/m/photo/` | ouvre l'appareil photo et range l'image dans l'ERP |
| Serveurs | `/m/serveurs/` | ouvre l'interface d'un autre serveur de la grappe |

Elle est aussi accessible depuis le menu, sous **Version téléphone**.

## Prendre une photo

Deux boutons, et la distinction compte :

- **Ouvrir l'appareil photo** utilise `capture="environment"`, qui ouvre
  directement l'appareil arrière sans passer par la galerie. C'est le geste
  attendu sur un chantier. En revanche cet attribut interdit de choisir une
  image déjà prise.
- **Parcourir la galerie** ouvre la galerie et accepte plusieurs photos à la
  fois.

Un seul champ aurait obligé à choisir entre les deux usages.

### Où va la photo

Dans les pièces jointes que l'ERP connaît déjà — aucun stock parallèle n'a été
créé, pour que la photo apparaisse là où on la cherche :

| Destination choisie | Modèle | Visible dans |
|---|---|---|
| Un chantier | `btp.ProjectDocument`, type « photo » | les documents du chantier |
| Documents généraux | `documents.Document`, type « photo » | les documents de l'entreprise |

La case **Visible par le client** est décochée par défaut : une photo de
chantier ne doit pas devenir visible sans décision.

### Limites

Dix photos par envoi, 12 Mo chacune. Un lot contenant une pièce invalide est
refusé **en entier** : un lot à moitié enregistré laisserait sans moyen de
savoir ce qui est passé.

Le bouton se verrouille pendant l'envoi. Sur un réseau mobile, plusieurs
photos prennent du temps, et un second appui créerait des doublons.

## Cloisonnement

La liste des chantiers ne contient que ceux de l'entreprise active. Une liste
non filtrée exposerait les noms de chantiers et de clients d'autres
entreprises, et un identifiant forgé rangerait la photo chez un tiers. Deux
barrières le refusent : les choix du formulaire, puis une nouvelle
vérification avant écriture.

## Changer de serveur

La page liste les serveurs de la grappe, avec leur rang et leur état. Ouvrir
l'un d'eux demande de s'y connecter — les sessions ne sont pas partagées entre
serveurs.

Un champ libre permet une adresse hors grappe. Elle est mémorisée **dans le
navigateur seulement**, et le lien est construit côté client : l'ERP n'émet
aucune redirection, ce qui écarte toute redirection ouverte. Seuls `http` et
`https` sont ouverts.

## Ce que cette version n'est pas

Ce n'est pas l'application mobile native. Le dépôt contient aussi un projet
Flutter et son arrière-plan (`apps/mobile_app`, `apps/mobile_interface`) :
appareils enregistrés, authentification à deux facteurs, scan de QR,
inventaire, opérations hors ligne, distribution d'APK. Ce travail n'est ni
versionné ni branché, et les deux voies peuvent coexister — la version web
couvre le besoin immédiat sans dépendre d'une chaîne de compilation Android.
