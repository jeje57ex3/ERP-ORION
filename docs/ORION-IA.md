# Orion — l'IA locale d'Orion ERP

Orion guide les utilisateurs dans l'interface, répond aux questions
techniques, et pilote les fonctionnalités IA du logiciel. Elle tourne
**entièrement sur votre serveur** : aucune donnée ne part ailleurs.

## Ce que « local » garantit ici

Ce n'est pas un réglage par défaut mais une **interdiction**. Les devis, les
clients, les factures et l'état du système ne doivent jamais quitter la
machine, et un réglage se change par inadvertance — l'appel externe serait
alors fait sans que personne le remarque, et les données déjà parties.

Le refus est donc placé à l'endroit par lequel tout appel passe : choisir un
fournisseur externe est **refusé** tant que *Traitement local uniquement* est
coché, dans **Super Admin → IA — Paramètres**. Décocher cette case est
possible, mais demande de le faire sciemment, et la page dit ce que cela
implique.

## Installer le moteur

Orion s'appuie sur un modèle servi par Ollama, sur le serveur lui-même.

```bash
/opt/orion/scripts/orion-ai.sh install
```

Le script installe Ollama, télécharge le modèle, **n'ouvre l'écoute que sur la
boucle locale** et refuse le port au pare-feu. Ce point est le plus important :
un moteur IA joignable depuis le réseau est une porte ouverte sur tout ce
qu'on lui soumet, et il n'a aucune authentification.

```bash
/opt/orion/scripts/orion-ai.sh status          # service, modèles, RAM
/opt/orion/scripts/orion-ai.sh test            # une question, et le temps de réponse
```

`status` compare les modèles présents à celui que l'application attend
réellement, lu dans le `.env`. Les deux ont divergé une fois de trop dans ce
projet : un modèle installé mais non attendu fait échouer chaque question,
sans que rien ne le dise.

### Dimensionnement

| | Disque | RAM à l'inférence | Sur 2 cœurs |
|---|---|---|---|
| Modèle 3B quantifié (défaut) | ~2 Go | ~3 Go | quelques secondes |
| Modèle 7B | ~5 Go | ~6 Go | ne tient pas dans 4 Go |

Le script avertit si la RAM disponible est insuffisante. Au-delà de la
capacité, le noyau tue le processus **en pleine réponse** : mieux vaut le
savoir avant.

Le modèle est libéré de la mémoire après cinq minutes d'inactivité. Sur une
petite VM, garder 3 Go résidents en permanence prive l'ERP de sa mémoire,
alors que le rechargement ne coûte que quelques secondes.

## Pourquoi Orion n'invente pas de page

Un petit modèle local produit volontiers un nom de page plausible. Et un guide
qui envoie chercher une page inexistante est **pire qu'un guide muet** :
l'utilisateur cherche, ne trouve rien, et conclut que le logiciel est en
défaut.

Avant chaque réponse, Orion cherche donc les faits dans l'installation
elle-même et les lui fournit comme seule source autorisée :

| Source | Origine |
|---|---|
| Pages et menus | `NAV_MODULES`, celui que l'interface affiche réellement |
| Adresses | le résolveur d'URL, par `reverse()` |
| Documentation | les fichiers de `docs/`, versionnés avec le code |

Les adresses existent donc **par construction**, et une page renommée ou
supprimée disparaît d'elle-même des réponses sans qu'il faille y penser.
C'est la seule façon de tenir cette promesse sur un dépôt qui compte
1854 routes nommées.

Cette recherche est déterministe et faite **avant** l'appel au modèle, plutôt
que laissée à son initiative : un petit modèle oublie de se servir de ses
outils, ou invente leurs arguments. Le modèle ne sert qu'à formuler.

Quand rien ne correspond, le contexte est vide et Orion répond qu'elle ne sait
pas — ce qui est la bonne réponse.

## L'appeler depuis n'importe quelle page

Une icone en forme d'etoiles figure dans la barre du haut, a cote du
selecteur de langue. Elle n'apparait que si Orion peut reellement
repondre : fonctionnalite activee sur le serveur, activee pour
l'entreprise, et droit accorde a l'utilisateur. Un bouton qui menerait a
« assistant desactive » serait une promesse non tenue a chaque page.

Elle transmet **la page d'ou vous l'appelez**. « Comment je fais ca ? »
n'a de sens que rapporte a l'ecran ouvert, et sans cette information
Orion demanderait des precisions que l'interface connaissait deja. Le nom
de route est traduit en libelle de menu, le seul qui ait du sens pour vous
comme pour le modele.

## Ce qu'Orion ne propose pas

**Les pages que vous ne pouvez pas ouvrir.** Le menu etant filtre par
utilisateur et par entreprise, Orion applique le meme filtre : elle ne vous
enverra pas vers une page Super Admin si vous n'y avez pas droit. Un
guidage qui mene a un refus d'acces est pire qu'un silence.

**Les modules absents du menu.** Un module atteignable seulement en tapant
son adresse est invisible pour elle. C'est voulu : le guidage porte sur ce
que l'on peut cliquer.

## Ce qu'Orion sait faire

Douze outils sont enregistrés, classés par risque et soumis aux permissions de
l'utilisateur. Les outils de **lecture** peuvent s'exécuter directement ; ceux
d'**écriture** sont proposés comme action à confirmer ; les actions
**dangereuses** sont bloquées tant que `allow_dangerous_actions` est
désactivé.

| Guidage | Lecture métier | Écriture |
|---|---|---|
| `trouver_page` | `get_erp_summary` | `create_order_note` |
| `lister_modules_interface` | `get_shop_status` | `update_shop_maintenance` |
| `chercher_documentation` | `get_recent_orders` | |
| | `get_system_health_summary` | |
| | `get_crm_stats` | |
| | `get_inventory_alerts` | |
| | `get_stripe_config_status` | |

Les trois outils de guidage ne lisent que la navigation et la documentation :
aucune donnée métier, donc aucun risque et aucune confirmation à demander.

## Activer Orion

`ORION_AI_ENABLED` vaut **False** par défaut. Dans le `.env` du serveur :

```
ORION_AI_ENABLED=True
```

puis redémarrez `orion-backend`. Le reste se règle dans **Super Admin →
IA — Paramètres** : nom, modèle, outils autorisés, journalisation, rédaction
des secrets.

## Supprimer une conversation

Depuis **Conversations**, chaque ligne porte un bouton de suppression ; la page
d'une conversation en porte un aussi. Un bouton **Effacer l'historique**
supprime toutes vos conversations d'un coup.

La suppression est **définitive**. Elle efface la conversation, ses messages,
les appels d'outils et les actions proposées qui en découlaient. Ce n'est pas
un simple masquage : une conversation avec Orion porte des devis, des noms de
clients et des montants, et les garder indéfiniment en base — invisibles mais
intacts — ne serait pas une suppression.

Ce qui en reste : une ligne dans le **journal d'audit IA**, indiquant qui a
supprimé quoi et quand, avec le titre et le nombre de messages. Le contenu des
messages, lui, ne survit pas — le conserver viderait la suppression de son
sens.

| Règle | Pourquoi |
|---|---|
| Vous ne supprimez que **vos** conversations | Dans votre entreprise, et les vôtres seules : « effacer mon historique » n'est pas « effacer celui de tout le monde » |
| Une confirmation est demandée | L'action ne peut pas être annulée |
| Jamais par simple visite d'adresse | Un lien de suppression en GET est déclenché par un préchargement de navigateur, un antivirus ou un indexeur — l'historique disparaîtrait sans que personne ait cliqué |

Si des **actions proposées** étaient en attente dans la conversation, la
supprimer les abandonne. Leur nombre est annoncé dans la confirmation puis
dans le message de résultat, plutôt que de les voir disparaître en silence.

Par l'API, pour un client externe :

```
DELETE /api/v1/orion-ai/conversations/<id>/
```

Les mêmes règles s'appliquent : la vérification de propriété et la trace
d'audit vivent dans le service, pas dans l'écran — sans quoi l'une des deux
voies finirait par oublier un garde-fou.

## Temps de réponse

Sur un petit modèle en CPU — le cas de l'appliance — le temps d'une réponse se
décompose en trois parts. Chacune a son remède, et « c'est lent » ne dit pas
laquelle est en cause :

| Part | Ce qui la fait grossir | Le réglage |
|---|---|---|
| Chargement du modèle | une période calme : Ollama le décharge | **Garder le modèle en mémoire** |
| Lecture du prompt | la longueur de la conversation | **Historique transmis** |
| Génération | la longueur de la réponse | **Longueur maximale de la réponse** |

Les trois durées sont **mesurées à chaque échange** et affichées sous la
réponse, par exemple :

```
4,2 s — lecture 0,8 s, 23 jetons/s
```

Le réglage se fait donc sur des chiffres. Les trois réglages sont dans
`Paramètres IA`.

### La réponse apparaît au fur et à mesure

Elle s'écrit mot à mot plutôt que d'apparaître d'un bloc à la fin. Le temps
total est le même : ce qui change est l'attente **avant de voir quelque
chose** — une à deux secondes au lieu de vingt ou trente. Pendant ces trente
secondes de silence, rien ne distinguait un assistant qui réfléchit d'un
assistant en panne.

Si un intermédiaire réseau empêche le flux de passer, l'interface retombe
automatiquement sur la réponse d'un bloc : l'assistant reste utilisable.

### Un gaspillage corrigé

La question était envoyée **deux fois** au modèle à chaque échange : une fois
dans l'historique (elle y est enregistrée avant la construction du prompt) et
une fois en fin de liste. Des jetons de prompt payés pour rien à chaque
message, et un modèle qui voyait la demande répétée.

### Mesurer la machine, pas seulement les réglages

Aucun réglage ne compense un débit insuffisant. Pour le connaître :

```bash
qm guest exec <vmid> -- /bin/bash /opt/orion/scripts/orion-ai.sh bench
```

Deux passes — la première inclut le chargement — puis un verdict :

| Débit mesuré | Ce que cela donne |
|---|---|
| 20 jetons/s et plus | confortable, aucune attente notable |
| 8 à 20 jetons/s | acceptable : les premiers mots arrivent vite, la fin défile |
| moins de 8 jetons/s | trop lent. Prenez un modèle plus petit |

Pour un modèle plus petit :

```bash
qm guest exec <vmid> -- /bin/bash /opt/orion/scripts/orion-ai.sh pull qwen2.5:1.5b-instruct
```

puis sélectionnez-le dans `Paramètres IA`. Un modèle de 1,5 milliard de
paramètres répond environ deux fois plus vite qu'un 3 milliards, au prix de
réponses un peu plus sommaires — acceptable pour guider dans une interface,
puisque les faits viennent de l'ERP et non du modèle (voir « Pourquoi Orion
n'invente pas de page »).

## Diagnostic

**« Le moteur local ne répond pas ».** Ollama est arrêté ou absent :
`orion-ai.sh status`, puis `orion-ai.sh install`.

**Orion échoue à chaque question alors que le service tourne.** Le modèle
attendu n'est pas téléchargé. `orion-ai.sh status` le signale et donne la
commande.

**« Le fournisseur … est externe ».** Le verrou local est posé, ce qui est le
réglage voulu. Choisissez le fournisseur local plutôt que de lever le verrou.

**Orion dit ne pas savoir où se trouve une page.** Soit la page n'est pas dans
le menu — c'est le cas de modules atteignables seulement par leur adresse —
soit les mots employés ne correspondent à aucun libellé. Les deux sont des
réponses honnêtes : elle préfère se taire qu'inventer.

**Les réponses sont lentes.** Sur 2 cœurs, quelques secondes sont normales. Au
premier appel après cinq minutes d'inactivité, ajoutez le temps de
rechargement du modèle.
