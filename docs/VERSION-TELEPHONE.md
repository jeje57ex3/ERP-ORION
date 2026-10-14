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

## L'installer comme une application

La version téléphone est une **application installable**. Une fois posée
sur l'écran d'accueil, elle a son icône, s'ouvre en plein écran sans barre
de navigateur, et démarre instantanément — la coquille est gardée sur le
téléphone.

**Android** : un bouton *Installer sur l'écran d'accueil* apparaît sur
l'accueil quand le navigateur le permet. Sinon, menu ⋮ puis *Ajouter à
l'écran d'accueil*.

**iPhone** : Safari n'offre pas de bouton ; le geste est manuel — bouton
Partager, puis *Sur l'écran d'accueil*. C'est une limite d'iOS, pas un
oubli.

Un raccourci **Photo** est proposé par appui long sur l'icône, sur Android.

### Plein écran partout, barre d'adresse comprise

L'application couvre **tout l'ERP** : *Interface complète* s'affiche en
plein écran, sans la barre d'adresse du navigateur. Elle s'ouvre toujours
sur l'accueil téléphone.

Deux portées distinctes rendent cela possible sans contrepartie :

| Portée | Étendue | Ce qu'elle décide |
|---|---|---|
| Manifeste | tout le site | le plein écran |
| Agent de service | `/m/` seulement | ce qui est gardé en cache |

Les pages de l'ERP restent donc **toujours servies par le réseau** : leurs
chiffres changent à chaque instant, et les servir depuis un cache
afficherait des données périmées sans le dire.

À savoir : sans barre d'adresse, il n'y a plus de recours par l'URL si une
page échoue. La barre d'action basse de l'ERP et le bouton retour du
téléphone restent les voies de sortie.

**Après cette mise à jour, désinstallez puis réinstallez l'application.** Un
changement de portée du manifeste n'est pas toujours repris par une
application déjà posée sur l'écran d'accueil.

### Ce qui fonctionne sans réseau

La coquille de l'application s'ouvre, et une page explique la situation.
Mais **les photos ne sont pas conservées hors ligne** : prenez-les avec
l'appareil photo du téléphone, puis envoyez-les depuis l'application quand
le réseau revient.

Je ne l'ai pas fait à moitié volontairement : une file d'attente hors ligne
mal faite perd des photos **en silence**, ce qui est pire que de ne pas en
avoir. C'est l'étape suivante naturelle, et elle mérite d'être faite
correctement.

### L'installation exige HTTPS

Les navigateurs refusent d'installer une application servie en HTTP nu. Sur
un domaine Cloudflare la condition est remplie ; en accès par adresse IP
locale, la page reste utilisable mais ne s'installe pas.

### Un seul bouton de menu

Sur téléphone, le bouton de menu du haut est masqué : la barre d'action
basse de l'ERP porte déjà le sien, et les deux ouvraient le même tiroir.
Au-delà de 768 px il réapparaît, étant alors le seul contrôle et servant à
replier la barre latérale.

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

## L'ancienne application native a été retirée

Le dépôt contenait un projet Flutter et son arrière-plan Django
(`apps/mobile_app`, `apps/mobile_interface`), jamais versionnés ni
branchés : 2,3 Go dont 2,1 Go d'artefacts de compilation. Ils ont été
retirés.

Les **sources** ont été archivées au préalable, car rien n'était suivi par
git et la suppression aurait été définitive :

```
Downloads/orion-ancienne-app-mobile-<date>.tar.gz
```

35 fichiers Dart et 51 fichiers Python y figurent, artefacts exclus.
