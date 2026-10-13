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

### 3. Dans l'ERP

**Super Admin → Haute disponibilité → Paramètres** :

| Réglage | Valeur |
|---|---|
| Déplacer les domaines à la bascule | activé |
| Nom de l'enregistrement d'indirection | `actif` (ou `actif.exemple.fr`) |
| Identifiant de zone Cloudflare | facultatif si le nom ci-dessus est complet |
| Identifiant de l'enregistrement | facultatif, retrouvé par son nom |

Puis, pour chaque serveur dans **Serveurs**, renseignez l'**URL de base** avec
son sous-domaine : `https://serveur2.exemple.fr`. C'est cette valeur que la
bascule écrit dans l'enregistrement d'indirection — sans elle, elle est
refusée.

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
