# Haute disponibilité — plusieurs serveurs, un seul domaine

Comment faire suivre tous vos domaines quand le serveur actif change, sans
toucher aux domaines eux-mêmes.

## Le principe : un nom d'indirection

Chaque serveur reçoit un sous-domaine qui lui est propre et ne bouge jamais.
Un nom supplémentaire — l'**indirection** — désigne celui qui est actif. Tous
les domaines publics pointent vers cette indirection, jamais vers un serveur.

```
erp.exemple.fr     ─┐
siecle.exemple.fr  ─┤                              serveur1.exemple.fr
lunea.exemple.fr   ─┼─ CNAME ─→ actif.exemple.fr ─→
ns.exemple.fr      ─┤                   ↑           serveur2.exemple.fr
+ domaines clients ─┘        seul enregistrement
                             modifié à la bascule
```

La bascule ne modifie qu'un enregistrement. C'est ce qui la rend fiable : si
chaque domaine pointait directement vers un serveur, il faudrait autant
d'appels à l'API Cloudflare que de domaines, sans possibilité de transaction —
et un échec au milieu de la série laisserait une partie du trafic sur le
serveur mort, l'autre sur le vivant.

Le sous-domaine par serveur sert de cible **stable** : contrairement à une
adresse IP publique, il ne change pas quand le bail DHCP de la machine est
renouvelé.

## Mise en place

### 1. Dans Cloudflare

Créez, une fois pour toutes :

| Enregistrement | Type | Contenu | Proxy |
|---|---|---|---|
| `serveur1` | CNAME ou A | le tunnel ou l'IP du serveur 1 | activé |
| `serveur2` | CNAME ou A | le tunnel ou l'IP du serveur 2 | activé |
| `actif` | CNAME | `serveur1.exemple.fr` | activé |

Puis faites pointer **chaque domaine public** vers `actif.exemple.fr` en CNAME,
proxy activé.

L'enregistrement `actif` doit exister avant la première bascule : l'ERP le
déplace, il ne le crée pas. S'il est absent, la bascule est refusée avec un
message explicite plutôt que de laisser le trafic dans le vide.

### 2. Sur chaque serveur

Le sous-domaine propre à la machine va dans son `backend/.env` :

```
ORION_NODE_DOMAIN=serveur1.exemple.fr
```

Il est posé automatiquement au déploiement avec `--node-domain` :

```bash
./deploy.sh --node-domain serveur1.exemple.fr   # (+ vos autres options)
```

C'est **indispensable**, et pas seulement pour la forme : les autres serveurs
interrogent `/ha/health/` sur ce nom. Absent d'`ALLOWED_HOSTS`, Django rejette
chaque battement de cœur en **400 DisallowedHost**, tous les serveurs se
croient mutuellement hors ligne, et la surveillance affiche l'inverse de la
réalité. `refresh_allowed_hosts.sh` s'en occupe à chaque démarrage de service.

Les domaines de service (`ORION_LOGIN_DOMAIN`, `SIECLE_STORE_DOMAIN`…) doivent
porter les **mêmes valeurs sur tous les serveurs** : après une bascule, c'est
le serveur 2 qui répond pour `erp.exemple.fr`, et il doit l'accepter.

### 3. Relier les serveurs par convention de nommage

**Super Admin → Nœuds HA → Relier les serveurs.** La voie la plus courte :
nommez vos serveurs par rang, et l'ERP les trouve seul.

```
rang 1  →  serveur1.exemple.fr   (serveur principal)
rang 2  →  serveur2.exemple.fr
rang 3  →  serveur3.exemple.fr
```

Un seul réglage à saisir — le **domaine de la grappe** (`exemple.fr`) — et le
motif de nommage, `serveur{n}` par défaut. Le rang n'est plus une donnée
séparée : `serveur2.exemple.fr` **est** le serveur de rang 2. Adresse et rang
ne peuvent donc plus se contredire, ce qui était possible en les saisissant
séparément.

**Chercher les serveurs** explore les rangs 1 à N sans rien modifier. Un rang
non pourvu n'est pas signalé comme un défaut : la grappe n'a pas besoin d'être
complète.

Décochez **Joindre les serveurs en HTTPS** pour une grappe de test en réseau
local, sans certificat.

#### La validation croisée

Chaque candidat est validé **dans les deux sens** avant d'entrer dans la
grappe. Le serveur source le sonde, puis lui demande de sonder le source en
retour (`/ha/join-check/`, protégé par le secret partagé).

Sans cette réciprocité, l'enregistrement ne prouve qu'un sens de la liaison —
et le cas asymétrique est aussi courant que redoutable : le principal joint le
secondaire, l'enregistre, l'affiche « sain », mais le secondaire ne peut pas
joindre le principal. Règle de pare-feu unilatérale, tunnel sortant seul, DNS
interne partiel, routage NAT. Rien ne le signale — jusqu'à la bascule, où le
nouveau serveur actif se découvre incapable de surveiller l'ancien.

Un serveur dont la liaison ne fonctionne que dans un sens est donc **écarté**,
avec le motif exact. Un serveur d'une version antérieure, qui n'expose pas ce
point, est distingué d'une panne de liaison et vous invite à le mettre à jour.

**Raccorder les serveurs validés** refait la recherche avant d'enregistrer, puis
pose pour chacun son adresse et son rang issus de la convention. L'opération
est rejouable sans danger : elle remet les adresses et les rangs en accord avec
le nommage, conserve les noms que vous avez choisis, et ne déplace **jamais**
la main — le serveur courant ne devient actif que si aucun ne l'est.

### 4. Raccorder un serveur à la main

**Super Admin → Nœuds HA → Raccorder un serveur**. Trois champs suffisent :
l'adresse du serveur (son sous-domaine), un nom d'affichage, et son rang de
préséance.

L'**identifiant du nœud n'est pas à saisir** : il est relevé sur le serveur
lui-même. C'est important, pas seulement commode. La protection en écriture
compare `ORION_NODE_ID` du serveur au verrou de cluster ; un identifiant saisi
à la main qui en diffère donne un serveur qui refuse toutes les écritures sans
que rien n'explique pourquoi.

Le bouton **Tester la liaison** ne modifie rien et passe cinq contrôles :

| Contrôle | Ce qu'il attrape |
|---|---|
| Résolution DNS | nom mal orthographié, enregistrement absent |
| Joignabilité | service arrêté, pare-feu, 400 ALLOWED_HOSTS, 502, 530, certificat |
| Secret partagé | `ORION_HA_SECRET` différent d'un serveur à l'autre |
| Identité | identifiant absent, ou déjà pris par un autre serveur |
| État de la base | base injoignable, ou secondaire encore inscriptible |

Chaque échec affiche la cause probable **et le remède**. C'est tout l'intérêt
du test : six causes très différentes produisent sinon le même « le serveur ne
répond pas », et les distinguer à la main coûte des heures.

**Raccorder ce serveur** refait le test avant d'enregistrer — un résultat
affiché depuis plusieurs minutes ne prouve plus rien. Seul l'échec du contrôle
d'identité bloque l'enregistrement ; les autres défauts sont enregistrés comme
avertissements, à traiter avant de compter sur ce serveur.

La même épreuve est disponible depuis la fiche de chaque serveur déjà
raccordé, par le bouton **Tester la liaison**.

### 5. Les règles du cluster

**Super Admin → Haute disponibilité → Paramètres** :

| Réglage | Valeur |
|---|---|
| Déplacer les domaines à la bascule | activé |
| Nom de l'enregistrement d'indirection | `actif` (ou `actif.exemple.fr`) |
| Identifiant de zone Cloudflare | facultatif si le nom ci-dessus est complet |
| Identifiant de l'enregistrement | facultatif, retrouvé par son nom |

L'URL de base de chaque serveur est posée par le raccordement. C'est
elle que la bascule écrit dans l'enregistrement d'indirection : un
serveur sans adresse voit toute bascule vers lui refusée.

Le compte Cloudflare utilisé est celui connecté dans **Sites web → Cloudflare**,
ou `ORION_CLOUDFLARE_API_TOKEN` dans le `.env`. Le jeton doit pouvoir modifier
le DNS de la zone.

## Ce que fait une bascule

Dans cet ordre, et l'ordre compte :

1. **Validation de la cible** — rôle, autorisation, état, retard de réplication.
2. **Promotion de la base** — arrêt de la réplication, levée de la lecture
   seule, puis **vérification** que la base est bien inscriptible.
3. **Redirection du trafic** — l'enregistrement d'indirection est repointé.
4. **Marquage du serveur actif** — verrou de cluster et rôles.
5. **Journalisation** — trace d'audit consultable dans **Événements**.

Deux points méritent d'être connus :

**La promotion précède toute écriture.** La base du serveur cible est en
lecture seule tant qu'elle n'est pas promue : aucune écriture ne peut donc la
précéder, trace d'audit comprise. C'est pourquoi celle-ci est écrite en
dernier.

**Si le trafic ne peut pas suivre, la bascule est refusée** et le serveur actif
reste celui d'avant — là où les domaines pointent encore. Mieux vaut une
bascule refusée, avec un message clair, qu'un serveur déclaré actif que
personne ne joint.

## Qui prend le dessus : le rang de préséance

Chaque serveur porte un **rang** (`priority`) : 1 reprend la main en priorité,
2 est le secours, 3 le dernier recours. Quand le serveur actif tombe, c'est le
mieux classé parmi les serveurs disponibles qui prend le dessus.

Le rang est **indépendant du rôle courant**. Le rôle se déplace à chaque
bascule ; le rang est une décision d'exploitation qui ne bouge pas. C'est ce
qui permet à un ancien principal rétrogradé de rester désigné pour reprendre
la main — sans quoi le rang n'aurait plus aucun sens après la première
bascule.

Trois réglages par serveur affinent la règle, dans **Serveurs** :

| Réglage | Effet quand il est décoché |
|---|---|
| Activé | le serveur est ignoré de bout en bout |
| Peut recevoir la main | il ne sera jamais promu, même seul survivant |
| Promotion automatique autorisée | seul un administrateur peut le promouvoir |

Le **secondaire préféré** des paramètres passe devant le rang, à condition
d'être disponible. Pour voir l'ordre effectif et, surtout, **pourquoi** un
serveur est écarté :

```bash
python manage.py ha_check_nodes
```

Elle affiche le bilan de chaque serveur, puis l'ordre de préséance avec le
motif d'exclusion de chacun. `--no-failback` permet de constater sans rien
changer.

## Quand un serveur revient

Un serveur qui redevient joignable ne reprend pas la main de lui-même. Ce qui
se passe est décidé par **Au retour d'un serveur**, dans les paramètres :

| Politique | Comportement |
|---|---|
| **Manuel** (défaut) | signale qu'un serveur mieux classé est prêt, et attend |
| **Jamais** | le serveur promu garde la main indéfiniment |
| **Automatique** | le mieux classé reprend la main, sous conditions |

En automatique, la main n'est rendue que si **toutes** ces conditions sont
réunies. Chacune correspond à un incident réel qu'elle évite :

1. **Le revenant est strictement mieux classé** que le serveur actif. À rang
   égal, rien ne bouge : deux serveurs de même rang se reprendraient la main
   en boucle.
2. **Il est stable depuis assez longtemps** (*Stabilité exigée*, 5 min par
   défaut). Un serveur qui oscille entre marche et panne satisferait sinon le
   contrôle à chacun de ses passages en bon état. Le compteur repart de zéro à
   chaque chute.
3. **Sa réplication est à jour**, dans la limite du retard toléré.
4. **Sa base est en lecture seule.** Voir ci-dessous.

### La divergence, et pourquoi elle arrête tout

Si un serveur revient en **acceptant encore les écritures** alors que la main
est passée à un autre, l'opération est refusée et signalée comme divergence.
C'est le cas le plus dangereux : deux bases qui acceptent des écritures ne se
fusionnent pas. Il n'existe pas de réparation automatique, seulement un choix
à faire sur les données à perdre.

Repassez la base du revenant en lecture seule et refaites-en un réplica avant
toute autre opération.

L'information vient du bilan de santé, qui lit l'état réel de MySQL
(`@@global.read_only`, `SHOW REPLICA STATUS`). Un état **inconnu** n'est jamais
tenu pour « inscriptible ».

### Déclencher l'évaluation

La règle de retour s'applique à chaque balayage de santé : le bouton
**Vérifier les serveurs** de l'interface, ou la commande `ha_check_nodes`.
C'est le seul moment où l'on constate qu'un serveur tombé répond de nouveau.
Pour une surveillance continue, planifiez la commande — toutes les minutes est
raisonnable.

Pour rendre la main à la demande, utilisez la page **Bascule** en désignant le
serveur revenu. L'opération est tracée comme un *retour*, distinct d'une
bascule subie, dans **Événements**.

## Plusieurs sites : le chemin privé

Tout ce qui précède suppose que les serveurs se joignent. En production ils ne
partagent aucun réseau local, et les relier par leurs adresses publiques
imposerait d'ouvrir des ports à chaque site, de dépendre d'IP qui changent, et
de faire voyager la réplication MySQL en clair sur Internet — ce dernier point
à lui seul l'interdit.

Un seul chemin privé porte donc tout : battements de cœur, validation
d'adhésion, réplication, fichiers.

```
PUBLIC — Cloudflare Tunnel            → les utilisateurs
  erp / siecle / lunea  →  actif.exemple.fr  →  tunnel du serveur actif

PRIVÉ — WireGuard                     → les serveurs entre eux
  serveur1.exemple.fr  →  10.10.0.1
  serveur2.exemple.fr  →  10.10.0.2
```

L'adresse privée se déduit du rang, comme le nom : **rang 2 donne 10.10.0.2**.
Un seul chiffre à retenir par serveur, et les trois identités ne peuvent plus
se contredire.

### Monter le réseau privé

**Super Admin → Réseau privé.** La page affiche l’identité privée de ce
serveur — rang, nom, adresse déduite — sa clé publique à copier, et l’état
de chaque liaison. Trois boutons suffisent : **Initialiser**, **Poser les
noms privés**, **Activer**.

Le tableau des liaisons distingue trois états, et la distinction compte :

| État | Ce que cela veut dire |
|---|---|
| Non déclaré | la clé de ce serveur n’a jamais été saisie ici |
| Sans réponse | déclaré, mais aucune poignée de main : pare-feu, endpoint, ou absence de déclaration réciproque |
| Établie | la liaison fonctionne réellement |

« Déclaré » et « fonctionne » se ressemblent de loin et n’ont ni la même
cause ni le même remède. Les confondre fait croire à une liaison là où il
n’y a qu’une déclaration.

L’échange de clés reste manuel, et le restera : aucune des deux clés
n’existe avant que les deux machines soient installées, et aucune ne peut
être devinée par l’une pour l’autre. La page rend cet échange lisible, elle
ne le supprime pas. Déclarez la clé obtenue **des deux côtés** : chacun doit
connaître l’autre.

#### En ligne de commande

Les mêmes opérations, pour qui préfère le shell ou doit intervenir avant que
l’interface soit joignable. Sur **chaque** serveur :

```bash
/opt/orion/scripts/orion-mesh.sh init
```

Il installe WireGuard, pose l'adresse déduite du rang, ouvre le port UDP au
pare-feu, et affiche la **clé publique à communiquer aux autres**.

Puis, sur chaque serveur, déclarez les autres — en indiquant leur rang, leur
clé, et l'adresse publique par laquelle les joindre :

```bash
/opt/orion/scripts/orion-mesh.sh add-peer 2 "CLE_DU_SERVEUR_2" serveur2-public.exemple.fr:51820
/opt/orion/scripts/orion-mesh.sh hosts
/opt/orion/scripts/orion-mesh.sh up
/opt/orion/scripts/orion-mesh.sh status
```

`hosts` pose la résolution privée des noms. `status` affiche les liaisons, les
pairs attendus d'après la grappe, et teste la joignabilité de chacun.

L'échange de clés est manuel et le restera : aucune des deux clés n'existe
avant que les deux machines soient installées.

### Mettre en place la réplication

Sans elle, la haute disponibilité est **décorative** : une bascule promouvrait
une base dépourvue des données de l'autre site.

Sur le serveur **source** (rang 1) :

```bash
/opt/orion/scripts/orion-replication.sh expose
/opt/orion/scripts/orion-replication.sh grant 2
```

`expose` ajoute l'écoute de MySQL sur la seule adresse privée — jamais sur
`0.0.0.0` — sans retirer `127.0.0.1`, par lequel l'ERP accède à sa base.
`grant` crée le compte de réplication, restreint à l'adresse privée du
réplica, et affiche la commande à lancer en face.

Sur le **réplica** :

```bash
/opt/orion/scripts/orion-replication.sh follow 1 'MOT_DE_PASSE_AFFICHE'
/opt/orion/scripts/orion-replication.sh status
```

Le mot de passe n'est affiché qu'une fois et stocké nulle part : relancez
`grant` si vous le perdez, il sera simplement remplacé.

La page **Réplication** se remplit ensuite à chaque vérification des serveurs.
Elle affichait jusqu'ici un tableau que rien n'alimentait.

### Synchroniser les fichiers

La base se réplique, les fichiers non. Une facture dont le PDF manque est une
donnée incomplète.

Sur chaque serveur, une fois :

```bash
/opt/orion/scripts/orion-mesh.sh media-key
```

puis déclarez la clé obtenue sur **l'autre** serveur :

```bash
/opt/orion/scripts/orion-mesh.sh trust 1 "CLE_DU_SERVEUR_1"
```

La clé est liée à l'adresse privée de son pair : même divulguée, elle ne sert
à rien depuis ailleurs.

Vérifiez sans rien copier, puis planifiez sur le serveur actif :

```bash
sudo -u orion /opt/orion/backend/.venv/bin/python /opt/orion/backend/manage.py ha_sync_media --constat
```

La copie part **toujours du serveur actif** vers les autres : lui seul reçoit
des téléversements. Lancée sur un passif, la commande refuse et le dit —
copier dans l'autre sens écraserait des fichiers récents par des anciens.

Elle ne supprime jamais rien côté destination. Un fichier absent de la source
peut provenir d'une bascule précédente, où l'autre serveur a reçu des
téléversements ; la place gagnée ne vaudrait pas ce qu'on risquerait de
perdre.

## La bascule automatique : élection par majorité

La bascule **manuelle** est opérationnelle depuis le début. La bascule
**automatique** l'est désormais aussi, mais seulement à partir de **trois
serveurs** — et cette condition n'est pas une limite d'implémentation, c'est
le fond du problème.

### Pourquoi une majorité est nécessaire

Un serveur qui ne joint plus le principal ne peut pas savoir lequel des deux
cas suivants il observe :

- le principal est réellement tombé ;
- le réseau s'est coupé, et c'est lui-même qui est isolé.

Les deux lui apparaissent exactement de la même façon. S'il se promeut sur
cette seule vue, alors lors d'une coupure réseau **chaque** serveur isolé tient
le même raisonnement au même moment : deux serveurs actifs, deux bases
acceptant des écritures, des devis et des factures différents portant les mêmes
numéros. Aucune réconciliation automatique n'existe pour cela ; la réparation
se fait à la main, ligne par ligne.

La règle qui l'empêche : **un candidat ne prend la main que s'il obtient la
voix d'une majorité stricte des serveurs déclarés, et chaque serveur n'accorde
qu'une voix par élection.** Deux majorités d'un même ensemble ont forcément un
serveur en commun, et celui-ci n'a voté qu'une fois : deux candidats ne peuvent
donc pas gagner la même élection. La divergence devient structurellement
impossible, au lieu d'être simplement improbable.

| Serveurs déclarés | Voix nécessaires | Bascule automatique |
|---|---|---|
| 2 | 2 | impossible — le serveur tombé devrait voter |
| 3 | 2 | oui, si un second serveur répond |
| 4 | 3 | oui, si deux autres répondent |
| 5 | 3 | oui, si deux autres répondent |

Le dénominateur est le nombre de serveurs **déclarés**, jamais le nombre de
serveurs joignables : calculer la majorité sur ce qu'un serveur voit lui
permettrait de former à lui seul « la majorité » de son propre isolement.

En revanche, un serveur **désactivé** ne compte pas : il est retiré de la
grappe par votre décision, le balayage de santé ne l'interroge plus, et il ne
peut plus recevoir la main. C'est ce qui permet de réduire une grappe sans
l'immobiliser.

> **Pour retirer un serveur, décochez `Serveur actif dans la grappe` au lieu
> de le laisser éteint.** Un serveur simplement éteint reste déclaré, et
> continue donc d'être compté dans la majorité : une grappe de trois serveurs
> dont deux sont éteints exigerait encore deux voix, et le survivant se
> clôturerait lui-même.

### À deux serveurs

La bascule automatique est refusée, avec ce motif écrit dans le journal des
événements plutôt qu'un silence. Deux voies pour l'obtenir :

| | Troisième serveur témoin | Contrôles de santé Cloudflare |
|---|---|---|
| Rôle | vote, sans servir de trafic | détecte et détourne depuis l'extérieur |
| Coût | une machine de plus | inclus dans le Load Balancer |
| L'ERP gère | tout | la base seulement |

Un témoin suffit : il n'a pas besoin de servir du trafic, seulement de
répondre au vote. C'est la voie la plus simple si vous disposez d'une petite
machine ailleurs.

### L'autre moitié du problème : le chef isolé

Exiger une majorité pour **promouvoir** interdit à une minorité d'élire un
nouveau chef. Cela ne suffit pas, et il faut le savoir : le serveur **déjà
actif** qui se retrouve du mauvais côté d'une coupure continue, lui, de se
croire actif et d'accepter des écritures — tandis que la majorité, de l'autre
côté, en élit légitimement un autre. Deux serveurs écrivent alors, par un
chemin que l'élection seule ne ferme pas.

D'où la **clôture** : à chaque balayage de santé, le serveur actif vérifie
qu'il voit encore une majorité de la grappe. S'il ne la voit plus, il refuse
les écritures jusqu'à la retrouver, avec ce message :

> Ce serveur Orion ne voit plus une majorité de la grappe : écriture refusée
> pour éviter deux serveurs actifs. Elle reprendra automatiquement au retour de
> la majorité.

La lecture reste possible, et la reprise est automatique — aucune intervention
n'est nécessaire quand le réseau revient.

Perdre l'écriture sur le serveur isolé est le prix de cette garantie, et c'est
le bon prix : une indisponibilité s'attend, s'explique et se répare en
rétablissant le réseau. Une divergence, elle, se répare à la main, ligne par
ligne, en choisissant quelle facture garder.

La clôture ne s'applique pas à **deux** serveurs : le remède y serait pire que
le mal, puisqu'une simple coupure du lien rendrait inutilisable le seul serveur
qui fonctionne. À deux serveurs, la protection repose sur la confirmation
manuelle.

### Activation

Trois réglages, dans cet ordre :

1. `Bascule activée` — déjà vrai par défaut ;
2. décocher `Confirmation manuelle obligatoire` ;
3. cocher `Bascule automatique activée`.

Et sur chaque serveur secondaire, `Promotion automatique autorisée` : un
serveur dont la case est décochée ne sera jamais promu sans intervention
humaine, même s'il est le mieux classé.

Tant que `Confirmation manuelle obligatoire` reste cochée, rien ne se déclenche
tout seul — c'est la valeur par défaut, et elle convient à une installation à
deux serveurs.

### Lire un refus

Chaque élection perdue est journalisée avec le détail des voix : qui a voté
pour, qui a refusé et pourquoi, l'époque, et le nombre de voix requises. Une
bascule qui ne se produit pas sans que rien ne dise pourquoi serait aussi
gênante qu'une bascule à tort : on ne saurait pas si le mécanisme a jugé, ou
s'il dort.

Les refus les plus fréquents :

| Motif | Ce qu'il faut faire |
|---|---|
| « impossible avec 2 serveur(s) » | ajouter un témoin, ou basculer à la main |
| « pas de majorité » | les autres serveurs ne répondent pas : vérifier le réseau privé |
| « le serveur principal reste joignable » | un seul serveur le croit tombé — c'est lui qui est isolé |
| « aucun serveur éligible » | `Promotion automatique autorisée` décochée partout, ou retard de réplication trop élevé |

## Diagnostic

**La bascule dit « n'a pas d'URL de base ».** Le serveur cible n'a pas de
sous-domaine renseigné dans **Serveurs**.

**« Aucun enregistrement CNAME ou A nommé … ».** L'indirection n'existe pas
encore dans la zone. Créez-la, pointée vers le serveur actuellement actif.

**« le CNAME pointerait sur lui-même ».** L'URL de base d'un serveur vaut le
nom d'indirection. Donnez à chaque serveur son propre sous-domaine.

**« restée en lecture seule après la promotion ».** L'utilisateur MySQL n'a pas
le privilège `SUPER`. Rien n'a basculé : l'état est intact.

**Tous les serveurs apparaissent hors ligne.** `ORION_NODE_DOMAIN` manque dans
le `.env`, ou le sous-domaine n'est pas dans `ALLOWED_HOSTS`. Vérifiez les logs
pour un 400 DisallowedHost sur `/ha/health/`.

**Une bascule « réussie » mais les domaines ne suivent pas.** Vérifiez que
« Déplacer les domaines à la bascule » est activé : désactivé, l'étape est
sautée et la trace d'audit l'indique (`"skipped": true`).

**« Liaison incomplète » sur la page Relier les serveurs.** Le candidat ne
joint pas ce serveur-ci, alors que l’inverse fonctionne. Vérifiez les règles
de pare-feu dans CE sens, et que l’adresse de ce serveur dans la convention
(affichée en haut du tableau) est bien celle par laquelle les autres peuvent
le joindre.

**Un pair WireGuard reste injoignable.** `orion-mesh.sh status` teste
chaque adresse privee. Verifiez le port UDP au pare-feu des DEUX cotes, et
que l'`Endpoint` declare est joignable depuis l'autre site. Derriere un NAT,
au moins un des deux doit avoir un endpoint atteignable.

**La replication ne demarre pas.** `orion-replication.sh follow` teste
d'abord la joignabilite du port 3306 prive et le dit explicitement.
Si elle echoue : le reseau prive est-il actif, et `expose` a-t-il ete lance
sur la source ?

**Retard de replication « inconnu ».** La replication est arretee, pas a
jour. C'est une panne, pas une absence de retard : `orion-replication.sh
status` donne les fils arretes et la derniere erreur.

**La synchronisation des medias echoue en silence.** La cle SSH du compte
orion manque, ou n'est pas declaree en face : `orion-mesh.sh media-key`
puis `trust` sur l’autre serveur. `--constat` montre la commande exacte.

**Un serveur ne se raccorde pas.** Lancez « Tester la liaison » sur la
page de raccordement : chacun des cinq contrôles nomme sa cause et son
remède.

**Un serveur revenu ne reprend jamais la main.** `ha_check_nodes` donne le
motif exact : rang insuffisant, stabilité trop courte, réplication en retard,
politique sur « jamais », ou divergence détectée.

**« accepte les écritures alors que la main est à … ».** Divergence : la base
du revenant n'est pas en lecture seule. Voir la section ci-dessus — ne
basculez pas avant de l'avoir traitée.
