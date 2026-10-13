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

### 3. Raccorder le serveur dans l'ERP

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

### 4. Les règles du cluster

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

## Limite à connaître : la détection automatique

La bascule **manuelle** est opérationnelle. La bascule **automatique** ne l'est
pas, et c'est délibéré.

À deux serveurs, il n'existe pas de majorité. Si le lien entre eux se coupe
sans qu'aucun ne soit tombé, chacun conclut que l'autre est mort et se
promeut : deux bases divergentes, des écritures des deux côtés, et une fusion
impossible. C'est le *split brain*.

Une détection fiable demande un arbitre extérieur aux deux serveurs. Deux
voies :

| | Troisième serveur témoin | Contrôles de santé Cloudflare |
|---|---|---|
| Rôle | vote, sans servir de trafic | détecte et détourne depuis l'extérieur |
| Coût | une machine de plus | inclus dans le Load Balancer |
| L'ERP gère | tout | la base seulement |

La seconde est recommandée : Cloudflare est déjà devant vos serveurs et reste
debout quand l'un d'eux tombe. Laissez `Confirmation manuelle obligatoire`
activé jusqu'à ce qu'un arbitre soit en place.

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

**Un serveur ne se raccorde pas.** Lancez « Tester la liaison » sur la
page de raccordement : chacun des cinq contrôles nomme sa cause et son
remède.

**Un serveur revenu ne reprend jamais la main.** `ha_check_nodes` donne le
motif exact : rang insuffisant, stabilité trop courte, réplication en retard,
politique sur « jamais », ou divergence détectée.

**« accepte les écritures alors que la main est à … ».** Divergence : la base
du revenant n'est pas en lecture seule. Voir la section ci-dessus — ne
basculez pas avant de l'avoir traitée.
