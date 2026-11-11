# Interroger l'hyperviseur Proxmox depuis l'ERP

Écrit pour qui exploite l'appliance Orion sur Proxmox.

**Page :** `/orion-admin/sante-systeme/proxmox/` — menu Super Admin →
Hyperviseur Proxmox.

## Ce que ça répond

L'écran des disques voit ce que le système d'exploitation voit, et rien de ce
que l'hyperviseur sait. Deux questions restaient sans réponse :

**« Ai-je bien branché un disque sur la VM ? »** Un disque correctement ajouté
mais que le noyau n'a pas vu ressemble *exactement* à un disque jamais ajouté.
Les deux donnaient « aucun disque détecté », et l'action à mener est pourtant
opposée :

| Ce que dit Proxmox | Ce que voit le système | Ce qu'il faut faire |
|---|---|---|
| 1 disque | 1 disque | ajouter un disque **dans Proxmox** |
| 2 disques | 1 disque | **redémarrer la VM** — le disque est déjà là |
| 2 disques | 2 disques | le préparer depuis l'écran des disques |

**« Quelle taille puis-je allouer ? »** La place libre est sur les pools de
stockage de l'hôte, invisibles depuis l'intérieur de la machine.

## Lecture seule, par construction

Le client n'émet **que** des requêtes GET. Il n'y a aucune méthode d'écriture
à désactiver : il n'en existe pas, et un garde-fou refuse tout autre verbe.
Deux tests gardent cette propriété.

Ce n'est pas une étape provisoire. Un jeton d'hyperviseur logé dans la machine
virtuelle qu'il gouverne renverse la confiance : la machine la moins
privilégiée se met à commander celle qui l'héberge — et l'hyperviseur porte
aussi vos autres VM. Tant que le client ne sait que lire, le pire d'une
compromission de l'ERP est la divulgation d'un inventaire, pas la destruction
d'un disque ni l'arrêt d'une machine voisine.

## Mise en route

### 1. Créer le jeton dans Proxmox

1. *Datacenter → Permissions → API Tokens → Add*
2. Choisissez un utilisateur et un nom de jeton.
3. **Copiez le secret immédiatement** : Proxmox ne le réaffiche jamais.
4. *Datacenter → Permissions → Add → API Token Permission* : rôle
   **`PVEAuditor`** sur le chemin `/`.

Le rôle en lecture seule est une **consigne**, pas une contrainte technique :
rien dans l'ERP ne peut l'imposer. Donnez-lui le minimum.

### 2. Renseigner la page

| Champ | Valeur |
|---|---|
| Adresse de l'hôte | l'IP du serveur Proxmox **telle que la VM peut la joindre**, sans `https://` ni port |
| Port | `8006` |
| Nom du nœud | en haut de l'arborescence dans l'interface Proxmox, souvent `pve` |
| Numéro de machine | le VMID de l'appliance (`100` par défaut) — **vérifiez-le**, un mauvais numéro décrirait une autre machine |
| Type | VM (`qm`) ou conteneur (`pct`) — en cas de doute, le test corrige |
| Identifiant du jeton | `utilisateur@pam!nom-du-jeton` — le `!` est obligatoire |
| Secret | collé une fois ; jamais réaffiché |

Puis **Enregistrer et tester**. Le test fonctionne même si « Interroger
l'hyperviseur » est décoché : vérifiez d'abord, activez ensuite.

## Les trois échecs courants

**« Certificat TLS refusé ».** Proxmox s'installe avec un certificat
auto-signé. Décochez « Vérifier le certificat » **si et seulement si** vous
joignez l'hôte sur un réseau que vous maîtrisez : sans vérification, rien ne
distingue l'hôte d'une machine qui se ferait passer pour lui. La page vous
avertit à chaque enregistrement dans ce cas.

**« Proxmox refuse le jeton » (401/403).** Trois causes, dans l'ordre de
fréquence : l'identifiant ne contient pas le `!` (c'est un identifiant
d'utilisateur, pas de jeton) ; le secret a été mal collé ; le jeton n'a aucune
permission sur le nœud.

**« Adresse inconnue de l'hôte » (404).** Le nom du nœud, le numéro de machine
ou son type sont faux. Le bouton de test essaie les deux types et corrige le
réglage quand l'autre répond.

## Le secret

Chiffré en base avec `ORION_SECRET_ENCRYPTION_KEY`, générée au
provisionnement. Il voyage dans un en-tête HTTP, jamais dans une URL — une
adresse se retrouve dans les journaux d'accès et les traces. Il est en outre
retiré de tout message d'erreur affiché.

**Un champ vide conserve le secret enregistré.** Sans cette règle, corriger un
numéro de port couperait l'accès à l'hyperviseur sans raison apparente.
L'effacement passe par une case à cocher.

Si vous restaurez une base sur une installation dont le `.env` a été
régénéré, la page affiche « secret illisible » plutôt qu'un champ vide : la clé
de chiffrement a changé, il faut ressaisir le secret.

## Fraîcheur

L'inventaire est gardé **une minute**, les échecs aussi. Sans cela, l'écran des
disques appellerait l'hôte à chaque affichage et attendrait dix secondes quand
il ne répond pas. Le bouton de test appelle toujours en direct, et enregistrer
les réglages vide le cache.

## Ce que l'ERP ne fait pas

**Il n'ajoute pas de disque.** Créer et rattacher un disque est une écriture
sur l'hyperviseur. L'ajout se fait dans Proxmox :

```
qm set 100 --scsi1 local-lvm:500        # 500 Go, à adapter
```

ou *VM 100 → Hardware → Add → Hard Disk*. L'écran des disques prend ensuite le
relais pour partitionner, formater et monter — voir `/orion-admin/sante-systeme/disques/`.
