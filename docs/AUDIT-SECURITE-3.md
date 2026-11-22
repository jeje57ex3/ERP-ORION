# Troisième audit de sécurité — 21 novembre 2026

Les deux premiers audits ont porté sur le code applicatif : l'adresse du
client, les redirections, les mots de passe, les jetons, les secrets de
production. Celui-ci regarde ce qu'ils avaient laissé de côté :
**l'exécution de commandes, la désérialisation, l'extraction d'archives, le
chemin réel des fichiers téléversés, et le contrôle d'accès lui-même.**

Trois défauts corrigés. Ils ont le même squelette, et c'est le fait
marquant de cet audit :

> **Un contrôle juste, écrit, documenté — et contourné par le chemin réel
> des octets.**

Les deux premiers audits butaient sur « du code juste que rien n'appelle ».
Celui-ci trouve la variante : du code juste que **quelque chose contourne**.
C'est plus difficile à voir, parce que le contrôle est là, qu'il est bon, et
qu'un test qui l'appelle directement passe.

---

## 1. Les bulletins de paie étaient téléchargeables sans compte

**Gravité : élevée. Corrigé.**

`apps/core/media_access.py` applique sous `/media/` un **refus par défaut**.
C'est un module soigné : trois niveaux d'accès, une liste de préfixes
interdits avec le motif de chaque refus, un `attachment` forcé sur tout ce
qui n'est pas une image ou un PDF, `X-Content-Type-Options: nosniff`, le
support des requêtes `Range`, et une note expliquant que les en-têtes
doivent être posés *après* la construction de `FileResponse` sous peine
d'être réécrits. Il tient explicitement hors de `/media/` :

| Préfixe | Contenu |
|---|---|
| `employee_private/` | Contrats, bulletins de paie, pièces d'identité, RIB, visites médicales, sanctions |
| `employee_certifications/` | Scans d'habilitations et de diplômes |
| `bank_statements/` | Relevés bancaires |
| `supplier_invoices/` | Factures fournisseurs — vos prix d'achat |
| `expense_receipts/` | Justificatifs de notes de frais |
| `btp/checklists/`, `reservations/` | Photos prises chez des clients |
| `signatures/` | Images de signature |

**Et deux gabarits nginx sur trois ne lui envoyaient jamais la requête.**

```nginx
# deployment/quick-install/nginx.conf.tmpl
location /media/ { alias /opt/orion/backend/media/; }

# deployment/appliance/templates/nginx/orion.conf
location /media/ { alias /var/www/media/; access_log off; }
```

Nginx servait ces fichiers depuis le disque. Aucun contrôle, aucun compte
demandé — et dans le second cas, `access_log off`, donc **pas même une
trace de la lecture**. Ce bloc-là est sous `server_name _`, c'est-à-dire
celui qui répond à n'importe quel `Host` : le serveur par défaut de
l'appliance.

Ce qui rend ce défaut instructif, c'est que la docstring de
`media_access.py` **affirmait le contraire** : « en production, nginx relaie
`/media/` vers gunicorn », en citant le gabarit proxmox. C'était vrai de ce
gabarit-là — le seul des trois à relayer. La note décrivait donc la
configuration qui marchait, et l'auteur de la politique n'avait aucune
raison de soupçonner les deux autres.

**Correction.** Les deux blocs relaient désormais vers Django, avec les
mêmes en-têtes que le bloc `/` (dont `$proxy_add_x_forwarded_for`, qui
*ajoute* la vraie adresse à droite — ce dont dépend `apps/core/client_ip.py`
depuis le deuxième audit). Le cache de 7 jours est retiré avec l'alias : la
vue décide elle-même `public` ou `private` selon le préfixe, et un en-tête
posé dans nginx aurait laissé un fichier interne dans le cache partagé d'un
proxy. La docstring porte la correction.

**Garde.** `tests/test_securite_audit_3.py` lit tous les fichiers de
`deployment/` qui déclarent un bloc nginx, découpe chaque
`location /media/ { ... }` en comptant les accolades, et refuse `alias`
comme `root` — puis exige un `proxy_pass`, parce que l'inverse du défaut est
une panne déjà vécue sur l'appliance : aucune route pour `/media/`, donc
aucune photo de produit ni aucun logo. Un troisième test échoue si plus
aucun gabarit n'est trouvé, sans quoi renommer `deployment/` rendrait les
deux autres verts en n'examinant rien.

---

## 2. Aucun plafond de taille sur les téléversements — et deux réglages qui le laissaient croire

**Gravité : moyenne. Corrigé.**

`erp_btp/settings/base.py` portait :

```python
# ─── Upload fichiers ───
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 Mo
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
```

Sous ce titre et avec cette valeur, cela se lit comme « les fichiers sont
limités à 20 Mo ». **Aucune des deux lignes n'est un plafond.**

* `FILE_UPLOAD_MAX_MEMORY_SIZE` est le seuil au-delà duquel un fichier passe
  de la mémoire à un fichier temporaire sur disque. Il décide *où* le
  fichier atterrit, jamais s'il est accepté.
* `DATA_UPLOAD_MAX_MEMORY_SIZE` borne le corps d'une requête, mais **les
  parties « fichier » n'y sont pas comptées**. Vérifié dans
  `django/http/multipartparser.py` : la comptabilité d'octets
  (`num_bytes_read`) et sa vérification sont toutes deux à l'intérieur de
  `if item_type == FIELD:` ; la branche `elif item_type == FILE:` ne
  contrôle que `DATA_UPLOAD_MAX_NUMBER_FILES`, c'est-à-dire un *nombre* de
  fichiers.

Et **aucun des 65 `FileField`/`ImageField` du projet ne porte de
`validators`** (mesuré : 65 champs, 0 occurrence de `validators`). Il
n'existait donc nulle part de limite de taille.

Un réglage qui rassure sans protéger est pire qu'un réglage absent : on ne
cherche pas ce qu'on croit avoir.

**Correction.** `apps/core/upload_guard.py` pose un gestionnaire de
téléversement, et non un validateur de champ — un validateur s'exécute quand
le fichier est *déjà* écrit sur le disque, et il faudrait l'ajouter à 65
champs, donc l'oublier sur le 66ᵉ. Deux barrières :

1. `Content-Length` annoncé trop gros → refus **sans lire un octet**. C'est
   l'essentiel de la protection.
2. Recomptage des blocs reçus, pour le cas où l'en-tête aurait menti.

Il lève `RequestDataTooBig` (un 400 journalisé) et non `StopUpload`, que
`MultiPartParser` rattrape : la vue verrait alors un champ fichier *vide* et
répondrait « ce champ est obligatoire », ce qui n'apprend rien à qui vient
d'envoyer 300 Mo.

**Quatre chemins sont exemptés**, tous réservés au superadmin : l'import
d'une sauvegarde portable (une base complète plus les médias), les deux
centres de sauvegarde, et le dépôt de l'installeur Windows. C'est un
arbitrage délibéré — un plafond qui casse une restauration serait désactivé
à la première panne, et c'est ainsi qu'une protection disparaît pour de bon.

Le plafond vaut `ORION_TAILLE_MAX_TELEVERSEMENT` (défaut 20 Mo, la valeur
qu'on croyait déjà appliquée ; `0` le désactive). Un réglage illisible
retombe sur le défaut plutôt que de désactiver la protection.

---

## 3. N'importe quel compte connecté pouvait se donner tous les droits

**Gravité : élevée. Corrigé pour la partie exploitable ; le fond demande votre arbitrage.**

### Ce qui était ouvert

Les treize vues de `apps/access_control/` — celles qui créent les rôles,
accordent les permissions, attribuent les accès et posent les dérogations —
n'étaient gardées que par `@login_required`. Aucun contrôle de rôle, aucun
`is_staff`, rien.

`role_permissions` porte une branche `action_type='full_access'` qui, d'un
seul POST, accorde **toutes les actions sur tous les modules**. Enchaîné :

1. `role_create` → créer un rôle dans son entreprise
2. `role_permissions` avec `action_type=full_access` → tout lui accorder
3. `user_access_create` → se l'attribuer

Trois requêtes, depuis n'importe quel compte connecté.

`role_duplicate` allait de plus chercher le rôle par sa **seule clé
primaire** et copiait sa matrice de permissions complète : en changeant le
numéro dans l'URL, un compte de l'entreprise A lisait le nom, le code, la
description et tous les droits d'un rôle de l'entreprise B. C'est le défaut
corrigé le mois dernier sur `role_permissions` juste au-dessus — la ligne
`company = _company(request)` était présente dans les deux vues, et n'était
employée que par l'une.

### Correction

`administration_requise` dans `apps/access_control/decorators.py` réserve
les treize vues aux administrateurs de l'entreprise courante et au
superadmin. La règle est reprise **telle quelle** de
`apps/website_shop_settings/permissions.py`, qui posait déjà la même
question : inventer une seconde règle garantit qu'un jour les deux
divergeront et que personne ne saura laquelle s'applique.

Elle compare le **code** du rôle (`role__code__in=('admin', 'owner')`).
Filtrer `role__in=('admin', 'owner')` fait lever à Django « Field 'id'
expected a number but got 'admin' » — une erreur 500 pour tout
non-superadmin, donc un écran inutilisable par ceux à qui il est destiné. Le
défaut a déjà été commis une fois dans ce dépôt ; il est écrit dans le code
pour ne pas l'être deux fois.

`role_duplicate` est borné à l'entreprise courante, les rôles **système**
(`company=None`) restant dupliquables puisqu'ils servent de modèles à toutes
les entreprises. Écrit avec un `Q`, et non `company__in=[company, None]` :
cette seconde forme produit `company_id IN (5, NULL)`, et SQL ne fait jamais
correspondre `NULL` par `IN` — les rôles système, précisément ceux que le
bornage entend autoriser, auraient tous rendu 404. Le piège a été pris une
fois pendant cet audit, et un test le garde.

### Ce qui reste, et pourquoi je ne l'ai pas fait

**Le système de rôles de l'ERP n'est appliqué nulle part.** Mesuré :

| Outil | Appelants dans le projet |
|---|---|
| `module_required` | **0** |
| `view_required` | **0** |
| `action_required` | **0** |
| `ModuleAccessRequiredMixin` | **0** |
| `ViewAccessRequiredMixin` | **0** |
| `ActionAccessRequiredMixin` | **0** |

Et aucun middleware du projet ne contrôle les permissions : la pile en
compte vingt-trois, aucun ne vient de `access_control`.

Les rôles, permissions, modules, actions et dérogations que l'écran
`/access_control/` permet de configurer **ne gouvernent l'accès à aucune
page**. Les écrans de l'ERP sont gardés par `@login_required`, parfois
`is_staff` ou `is_superuser`, et le reste est décoratif. C'est le motif des
trois audits à son échelle maximale : un système de permissions entier,
correct, et que rien n'appelle.

**Le brancher n'est pas une correction, c'est un chantier**, et il vous
revient : il faut décider module par module qui a le droit de quoi, et toute
erreur enferme dehors quelqu'un qui travaille. Le faire au détour d'un audit
serait le pire des deux mondes — un ERP où plus personne ne peut travailler,
et une protection qu'on désactiverait dans l'heure.

Ce qui est fait : la porte par laquelle on se donnait tous les droits est
fermée, le constat est écrit dans `decorators.py` là où quelqu'un ira
chercher ces outils, et un test échoue au premier usage réel du RBAC — parce
qu'alors cette note deviendrait fausse, et un commentaire qui décrit un état
révolu est pire qu'aucun commentaire.

---

## Vérifié et trouvé sain

Ces classes ont été examinées et n'ont rien donné. Elles figurent ici pour
qu'on ne les refasse pas, et pour dire ce qui a été *mesuré* plutôt que
supposé.

| Classe | Ce qui a été vérifié | Conclusion |
|---|---|---|
| **Zip slip** (`backups/services.py:450`) | Lu `ZipFile._extract_member` dans la bibliothèque installée : `splitroot` retire le lecteur et la racine, et `invalid_path_parts` élimine `..` | Pas exploitable. `zipfile` n'écrit pas non plus de liens symboliques |
| **`shell=True`** (`system_updates/git_service.py:12`) | Toutes les valeurs interpolées viennent de `settings.ORION_GIT_*` et `ORION_UPDATE_RESTART_COMMAND`, donc de `.env`, et `hard_reset_to_commit` reçoit un commit écrit par le programme | Pas atteignable depuis le web. À resserrer un jour par principe, pas en urgence |
| **Désérialisation** | Aucun `pickle.load`, `yaml.load`, `marshal` ni `eval` sur une entrée. `configurator/services/formulas.py` dit explicitement ne pas faire d'`eval` | Sain |
| **Écrans destructeurs** | `system_updates` : les treize vues en `@super_admin_required`, qui vérifie `is_superuser`. `backups` : restauration, téléchargement, export et import en `is_superuser` | Correctement gardés |
| **SSRF** | 30 appels sortants revus. Hôtes fixes (API Cloudflare, Proxmox) ou URL configurées par un admin — nœuds de cluster, fournisseur d'IA, domaine d'un site | Pas d'URL fournie par un utilisateur non privilégié |
| **IDOR inter-entreprises** | Analyse syntaxique : 238 modèles portent un champ `company`, 298 appels à `get_object_or_404` les visent, **17** sans contrainte `company`. Les 17 relus un par un : 4 bornés par `user=request.user`, 6 par `website=`/`domain=`/`fiscal_year=`, 3 sur `BackupJob` (sauvegardes d'instance, vues superadmin), 1 branche superadmin délibérée dans `website_shop_settings`, 1 sur `SystemError` (diagnostic d'instance), **1 vrai défaut** — `role_duplicate`, corrigé ci-dessus | Une seule fuite, fermée |
| **XSS par fichier téléversé** | `servir_media` force `attachment` hors des types affichables, pose `nosniff`, et les en-têtes sont posés après la construction de `FileResponse` — un SVG ne s'exécute pas | Fermé par la couche de service, pas besoin d'une liste d'extensions |

---

## Décisions en attente

Les quatre du deuxième audit restent ouvertes (voir `AUDIT-SECURITE-2.md`) :
2FA obligatoire pour les superadmins, durée de session, hachage des jetons
de l'espace client, `ALLOWED_HOSTS` à `*`. S'y ajoute :

**5. Brancher le contrôle d'accès par rôle.** Décrit ci-dessus. C'est le
seul point de cet audit que je n'ai pas tranché, et le seul qui change ce
que vos utilisateurs peuvent faire. Si vous le voulez, la façon la moins
risquée est de commencer par **journaliser** sans refuser : poser les
décorateurs en mode « constat » pendant quelques semaines pour voir qui
serait refusé, puis basculer module par module. Un refus qui surprend se
désactive ; un refus qu'on a vu venir se corrige.

## Avant de livrer

Inchangé depuis le deuxième audit, et toujours à vérifier :
`/opt/orion/backend/.env` doit porter une `SECRET_KEY` de 50 caractères ou
plus, sans quoi `production.py` refuse de démarrer. Le contrôle en tête de
la mise à jour l'intercepte avant le `git pull`, donc l'ERP resterait sur
l'ancien code sans casser.

**S'ajoute pour cette livraison, et c'est le point important :** la mise à
jour ne réécrit pas la configuration nginx de la VM. Les deux corrections de
`location /media/` sont dans les **gabarits** du dépôt ; sur la machine, le
fichier installé sous `/etc/nginx/sites-enabled/` doit être corrigé à part.
Tant qu'il ne l'est pas, `/media/` reste servi depuis le disque pour qui
atteint nginx — c'est-à-dire par le réseau local, puisque le tunnel vise
gunicorn directement pour le domaine de l'ERP.

**Je n'ai pas pu vérifier lequel des gabarits est installé** : aucun accès
à l'hyperviseur depuis le poste de développement. Le chemin
`/opt/orion/backend/media/` du gabarit `quick-install` correspond à
l'arborescence de production connue (`/opt/orion/backend/.env`), ce qui en
fait le candidat probable — mais c'est une déduction, pas une mesure.

**Vous n'avez pas à le vérifier à la main.** `check_media_derriere_django()`
a été ajouté aux contrôles préalables de la mise à jour : il lit
`/etc/nginx/sites-enabled` et `/etc/nginx/conf.d`, découpe chaque
`location /media/` en comptant les accolades, et nomme le fichier fautif
dans l'écran de mise à jour. Il **n'arrête pas** la mise à jour — le défaut
lui est antérieur et elle ne l'aggrave pas ; bloquer laisserait l'ERP sur du
code plus ancien sans rien fermer. Il le dit, à chaque mise à jour, jusqu'à
ce que ce soit corrigé.

L'absence de Nginx n'est pas traitée comme un défaut : sur un poste de
développement il n'y a pas de `/etc/nginx`, et confondre « absent » et
« fautif » ferait crier le contrôle là où il n'a rien à dire — une alerte
permanente ne se lit plus.

Reste, pour la correction elle-même, une intervention sur le fichier de
`/etc/nginx` : remplacer le bloc par le `proxy_pass` du gabarit corrigé,
`nginx -t`, puis recharger. C'est le seul point de cet audit qui ne se pilote
pas depuis l'interface, et c'est assumé : écrire dans `/etc/nginx` depuis
l'ERP lui donnerait le droit de se couper lui-même du réseau.
