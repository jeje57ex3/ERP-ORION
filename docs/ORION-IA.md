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
