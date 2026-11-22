# Audit de sécurité — l'authentification et ce qui l'entoure

*21 novembre 2026. Second audit du logiciel.*

Le premier audit a couvert le cloisonnement entre entreprises, les
téléversements publics, l'évasion de `</style>` et le XSS stocké.
Celui-ci regarde ailleurs : **d'où vient l'adresse du client, où l'on
accepte de renvoyer l'utilisateur, et combien de mots de passe on le
laisse essayer.**

Sept défauts, tous corrigés, et quatre points qui attendent votre
décision parce que les corriger a des conséquences que je ne peux pas
prendre à votre place.

---

## 1. L'adresse du client était celle qu'il choisissait

**C'est le défaut central de cet audit, et il en annulait plusieurs
autres.**

Six endroits extrayaient l'adresse IP du client, chacun à sa façon, et
tous les six prenaient le **premier** élément de `X-Forwarded-For` :

    apps/core/utils.py          apps/core/audit_service.py
    apps/core/middleware.py     apps/accounts/signals.py
    apps/accounts/views.py      apps/websites/public_views.py

### Pourquoi le premier élément est le mauvais

`X-Forwarded-For` est une liste qui se lit **par la droite**. Les deux
composants qui la remplissent chez vous y **ajoutent** la vraie adresse
à droite de ce que le client a déjà mis :

| Chemin | Qui écrit le dernier élément |
|---|---|
| Par Cloudflare | Cloudflare, qui ajoute la vraie adresse |
| Par nginx (LAN) | nginx, avec `$proxy_add_x_forwarded_for` |

Un client qui envoie `X-Forwarded-For: 9.9.9.9` fait donc arriver
`9.9.9.9, <sa vraie adresse>`. Prendre le premier élément rendait
`9.9.9.9` — **la valeur que l'attaquant avait écrite**.

### Ce que ça cassait

**Toutes les limitations de débit du dépôt.** Le configurateur en pose
huit, les formulaires publics deux. Chacune met cette adresse dans une
clef de cache : changer un en-tête à chaque requête donne une clef neuve
à chaque fois, donc la limite de dix envois par heure était illimitée.
Le code était écrit, testé, et sans aucun effet.

**Le journal d'audit.** Il enregistrait une adresse choisie par
l'attaquant. C'est pire qu'une colonne vide : une colonne vide se lit
comme inconnue, celle-là se lit comme une preuve.

### Ce qui a été fait

Un seul module, `apps/core/client_ip.py`, auquel les six délèguent. Il
lit le **dernier** élément — écrit par un composant qu'on contrôle dans
les deux chemins — et **valide** la valeur avec `ipaddress` avant de la
rendre, parce qu'elle part dans une clef de cache et dans une colonne de
la base.

`CF-Connecting-IP` n'est **plus lu du tout**, alors qu'il était consulté
en premier. Cloudflare le pose bien, en écrasant toute valeur du client
— mais rien, du côté de Django, ne distingue celui de Cloudflare de
celui qu'un client a émis. `X-Forwarded-For` porte la même information
à un endroit vérifiable.

> **Vérifié plutôt que supposé.** J'ai d'abord écrit que la correction
> avait une seconde moitié dans nginx. C'était faux : le fichier
> `05-cloudflared-config.tmpl.yml` route le domaine de l'ERP vers
> `http://127.0.0.1:9000`, donc vers gunicorn **directement** — nginx
> n'est dans le chemin que pour l'accès LAN. Aucune modification de
> nginx n'est nécessaire.

---

## 2. Aucune redirection n'était vérifiée

`url_has_allowed_host_and_scheme` — la fonction de Django prévue
exactement pour cela — n'était appelée **nulle part** dans le dépôt.
Quinze vues renvoyaient l'utilisateur vers une adresse prise dans la
requête : un `next`, ou un en-tête `Referer`.

`django.shortcuts.redirect` sert telle quelle une adresse absolue. Donc
`?next=https://exemple-pirate/` envoyait l'utilisateur hors du site,
depuis un lien qui commence par votre vrai domaine.

### La plus grave est celle du 2FA, et c'est parce qu'elle marche

```python
# apps/user_security/views.py
login(request, user)
mark_2fa_verified(request, user)
response = redirect(request.GET.get("next") or "core:dashboard")
```

Elle s'exécute **après** une authentification réussie, code à deux
facteurs compris. L'utilisateur a saisi son mot de passe, sorti son
téléphone, tapé son code — et atterrit sur une page choisie par
l'attaquant. À cet instant précis, il n'a plus aucune raison de se
méfier : tout ce qu'on lui a demandé a fonctionné. Une page qui demande
alors de « confirmer » quoi que ce soit sera remplie.

### Deux vues croyaient se protéger

`apps/core/views.py` et `apps/websites/public_views.py` vérifiaient
`next_url.startswith('/')`. Or `//exemple-pirate/` commence par une
barre oblique, et le navigateur y lit un **hôte**, pas un chemin : c'est
une adresse « protocole-relatif ». Le contrôle laissait passer
exactement ce qu'il cherchait à bloquer.

### Ce qui a été fait

`apps/core/redirections.py`, et les quinze vues y passent. Une
destination hors du site est **remplacée** par le repli, sans tentative
de nettoyage : une liste d'exceptions se contourne, un refus ne se
contourne pas. Les retours à la ligne sont écartés aussi — les
navigateurs les retirent avant d'analyser l'adresse, si bien que
`/\nhttps://pirate` devient absolu.

---

## 3. L'écran de connexion acceptait un nombre illimité d'essais

`UserProfile` porte deux colonnes depuis sa toute première migration :

```python
failed_login_attempts = models.PositiveIntegerField(default=0)
locked_until          = models.DateTimeField(null=True, blank=True)
```

**Aucune des deux n'était lue ni écrite nulle part.** Quelqu'un avait
prévu la protection, créé la place pour elle, et elle n'a jamais été
branchée.

Pour un ERP joignable par un domaine public, c'est la porte la plus
simple : pas de faille à trouver, pas de contournement à inventer —
seulement du temps et une liste de mots de passe.

### Deux compteurs, parce qu'un seul se contourne

| Compteur | Ce qu'il arrête |
|---|---|
| **par compte** (en base) | celui qui s'acharne sur **un** identifiant depuis cent adresses |
| **par adresse** (en cache) | celui qui essaie **un** mot de passe courant sur cent identifiants — le balayage, qui ne déclenche jamais le compteur par compte puisqu'il ne retente jamais le même |

Tenir l'un sans l'autre laisse passer exactement l'attaque que l'autre
arrête.

### Trois choix à expliquer

**Le verrou de compte est en base, le compteur d'adresse en cache.**
Redis redémarre à chaque mise à jour, et un verrou qui s'ouvre au
redémarrage est un verrou dont l'attaquant choisit la durée.

**Le verrou est temporaire.** Une minute, puis cinq, puis quinze,
jusqu'à une heure. Un verrou définitif transformerait la protection en
déni de service contre l'utilisateur légitime : il suffirait d'échouer
cinq fois sur votre compte pour vous mettre dehors jusqu'à intervention.

**Le refus ne dit pas si le compte existe.** Le contrôle a lieu avant
toute authentification, donc pour un identifiant qui peut ne
correspondre à rien. Deux textes différents donneraient la liste des
comptes à qui prendrait la peine de comparer.

**Et le contrôle est posé avant `form.is_valid()`** — c'est lui qui
appelle `authenticate()`, donc qui hache le mot de passe proposé. Le
placer après reviendrait à offrir à l'attaquant exactement le coût qu'on
cherche à lui imposer.

Un verrou se lève depuis l'interface (`deverrouiller`) : un verrou qu'on
ne peut lever qu'en base est un verrou qui finit par être levé en
désactivant la protection.

---

## 4. La production démarrait avec la clef du dépôt

`base.py` donne à `SECRET_KEY` une valeur de repli, publiée dans ce
dépôt. `production.py` en héritait **sans la vérifier**.

Un `.env` sans `SECRET_KEY` — oubli, fichier écrasé par une
réinstallation, variable mal nommée — faisait démarrer la production avec
cette valeur. Tout ce que la clef signe devenait alors forgeable par
quiconque a lu ce dépôt :

- les **cookies de session** — se connecter en tant que n'importe qui,
  sans mot de passe ;
- les jetons CSRF ;
- les liens de réinitialisation de mot de passe ;
- les messages signés de `django.core.signing`.

**Et rien ne le disait.** `manage.py check --deploy` émet un
avertissement (`security.W009`) que personne ne lit au démarrage d'un
service systemd : le site fonctionne, les pages s'affichent.

### Ce qui a été fait, et la précaution qui va avec

`production.py` **refuse de démarrer** si la clef est absente, laissée à
la valeur du dépôt, ou plus courte que 50 caractères. Un service qui ne
démarre pas se voit dans la minute ; une clef par défaut ne se voit
jamais.

Mais cela transforme une faiblesse silencieuse en **panne au
redémarrage**. `run_post_update_health_checks` ne protège pas de cela :
il s'exécute **après** les trois redémarrages, donc il constaterait la
panne au lieu de l'éviter.

Un contrôle de configuration a donc été ajouté **en tête de la mise à
jour** — avant la sauvegarde, avant le `git pull`, avant tout. S'il
échoue, la mise à jour s'arrête, l'ERP continue de tourner sur l'ancien
code, et le journal que l'interface affiche porte la phrase qui dit quoi
corriger.

> **À vérifier avant de livrer cette mise à jour :** que
> `/opt/orion/backend/.env` porte bien une `SECRET_KEY` d'au moins 50
> caractères. Le contrôle préalable vous le dira sans rien casser, mais
> autant le savoir avant.

### Une correction de ma première version du contrôle

Écrit tel quel, il levait au simple **import** de `production.py` — ce
que deux tests font légitimement, pour vérifier que la production
n'emploie pas un cache par processus. Un contrôle qui empêche de
vérifier la configuration n'est pas un durcissement, c'est une gêne.

Il ne porte donc que sur le module **réellement actif**, désigné par
`DJANGO_SETTINGS_MODULE` : c'est le processus qui **sert** les requêtes
qu'il faut protéger, pas celui qui lit le fichier. Les quatre unités
systemd posent cette variable, et `manage.py --settings=X` l'écrit aussi
— vérifié dans le code de Django (`core/management/base.py:92`) plutôt
que supposé, sans quoi la restriction aurait laissé un trou.

---

## 5. Les jetons d'authentification partaient sans `Secure`

`siecle_token` et `neo_client_token` portent un jeton d'authentification
pendant **trente jours**, avec `httponly` et `samesite='Lax'` — mais sans
`secure`. Le navigateur les joignait donc aussi à une requête en HTTP
simple. Un seul lien en `http://` vers le domaine, et le jeton part en
clair.

`set_trusted_device_cookie`, dans `apps/user_security`, posait déjà
`secure=not settings.DEBUG` : **la convention existait dans le dépôt**, et
ces deux-là ne l'avaient pas.

---

## 6. L'API client contournait les validateurs de mot de passe

`AUTH_PASSWORD_VALIDATORS` en déclare quatre : longueur minimale, mots de
passe courants, tout-numérique, ressemblance avec le nom.

**`User.objects.create_user()` ne les appelle pas.** Ils ne s'appliquent
qu'à travers un formulaire ou un appel explicite à `validate_password`.

L'API de l'espace client posait donc sa propre règle :

```python
if len(password) < 6:
    return JsonResponse({'error': 'Mot de passe trop court …'}, status=400)
```

Six caractères acceptent « 123456 », qui figure en tête de toutes les
listes de mots de passe. Les comptes clients avaient une politique plus
faible que celle que le projet s'est donnée, sans que rien ne le dise.

---

## 7. Ni la connexion ni l'inscription de l'espace client n'étaient limitées

Essais de mots de passe illimités sur deux endpoints JSON — celui de
SIÈCLE et celui du portail client. Et l'inscription répond « un compte
existe déjà avec cet email » : de quoi dresser la liste des clients d'une
boutique à la vitesse du réseau.

Le message est **conservé** — le cacher rendrait l'écran d'inscription
incompréhensible pour qui a déjà un compte — et c'est le **débit** qui est
borné, puisque c'est lui qui transforme une réponse légitime en moyen
d'énumérer.

---

## 8. Lever un verrou demandait un terminal

La limitation ajoutée au point 3 verrouille un compte temporairement.
C'est suffisant pour rendre l'attaque sans intérêt, et c'est long pour
quelqu'un qui doit émettre une facture maintenant.

**Si la seule façon de lever un verrou est une requête en base, alors la
façon qui sera employée le jour où ça presse est la désactivation de la
protection** — et c'est le genre de réglage qu'on ne remet jamais. Ce
n'est donc pas un point de confort : c'est la condition pour que la
protection survive à son premier dérangement.

L'écran de l'utilisateur (`/accounts/users/<pk>/`) affiche désormais
l'état du verrou — nombre d'échecs, heure de réouverture — et porte un
bouton qui le lève, en POST, avec une trace au journal d'audit. L'état
est **affiché** et pas seulement levable : un administrateur qui ne voit
pas pourquoi un collègue n'entre plus cherchera ailleurs, et conclura à
une panne.

---

## Un point fermé par précaution, qui n'était pas une faille

`apps/core/company_database_service.py` interpole un identifiant dans
quatre requêtes :

```python
cursor.execute(f"DROP DATABASE IF EXISTS `{db_name}`;")
```

**Vérifié avant de l'appeler une faille :** `db_name` vient de
`generate_company_database_name`, qui part d'un `SlugField` rempli par
`slugify()` — lettres, chiffres, tirets et soulignés seulement. Aucun
`fields = '__all__'` dans le dépôt, et aucun formulaire ni vue n'écrit
`database_name`. **Ce n'est donc pas injectable aujourd'hui.**

Mais `database_name` est un `CharField` libre, rien ne garantit son
contenu au point d'usage, et ce point d'usage détruit une base entière.
Un identifiant SQL ne se paramètre pas — `%s` ne s'applique pas à un nom
de base — donc la seule protection est une liste blanche, posée là où
l'interpolation a lieu. Les accents graves qui entourent l'identifiant
ne protègent de rien : un accent grave dans la valeur ferme la citation.

---

## Ce qui attend votre décision

Ces quatre points ont des conséquences que je ne prends pas à votre
place.

### La 2FA n'est obligatoire pour personne

`ORION_2FA_REQUIRED_FOR_SUPERUSERS` vaut `False` par défaut, et le
commentaire du code explique pourquoi : un défaut à `True` l'imposerait
d'un coup à tous les super-administrateurs, dont ceux qui ne l'ont pas
configurée — « une mine qui n'explose qu'en production ».

Le raisonnement est juste. Mais aujourd'hui, **le seul obstacle entre un
mot de passe deviné et votre ERP est la limitation ajoutée ci-dessus.**
Je peux l'activer pour les super-administrateurs quand vous aurez
enrôlé les comptes concernés.

### La durée de session

`SESSION_COOKIE_AGE = 7 jours` en production, avec
`SESSION_SAVE_EVERY_REQUEST = True` : la session se prolonge de sept
jours à chaque visite. C'est donc un délai d'**inactivité** de sept
jours, ce qui est long pour un ERP consulté depuis un poste de chantier
ou un ordinateur partagé. Le réduire à un ou deux jours obligerait à se
reconnecter plus souvent — c'est un arbitrage de confort, pas une
correction, et il vous revient.

### Les jetons de l'espace client sont stockés en clair

`SiecleCustomerToken.key` et son équivalent du portail gardent le jeton
tel quel en base. Une lecture de la base donne donc l'accès au compte de
chaque client. C'est le procédé de Django REST Framework, donc courant —
mais le hacher coûterait peu. À faire si vous le souhaitez ; cela
invalide les jetons existants, donc déconnecte tous les clients une fois.

### `ALLOWED_HOSTS` peut valoir `*`

Il laisse Django accepter n'importe quel en-tête `Host`, ce qui ouvre
l'empoisonnement de cache et les liens de réinitialisation pointant vers
un domaine choisi par l'attaquant. Je ne refuse pas le démarrage —
l'appliance se visite par son adresse IP avant qu'un domaine ne pointe
dessus, et ce réglage est alors le seul praticable — mais le contrôle
préalable de la mise à jour l'écrit désormais dans le journal, pour que
ce ne soit pas un oubli silencieux.

---

## Ce que l'audit a cherché et n'a pas trouvé

Dit pour que vous sachiez ce qui a été regardé, et pas seulement ce qui
a été corrigé.

| Classe | Résultat |
|---|---|
| Injection SQL | Aucune. Treize `cursor.execute` examinés : tous des requêtes fixes ou des identifiants dérivés d'un `SlugField` (voir ci-dessus). |
| `pickle`, `eval`, `exec`, `yaml.load` | Aucun usage sur une donnée de requête. Le moteur de formules du configurateur est un évaluateur borné, pas un `eval`. |
| `shell=True` dans un `subprocess` | Aucun. Les commandes sont passées en liste d'arguments. |
| Traversée de chemin | Les deux `FileResponse(open(…))` partent d'un `FileField` stocké, bornés par entreprise et par client. |
| SSRF | Les requêtes sortantes visent des adresses de configuration (Cloudflare, Proxmox, nœuds du cluster), pas des adresses fournies par un visiteur. |
| Affectation en masse | Aucun `fields = '__all__'`. |
| En-têtes de sécurité | `HSTS`, `X-Frame-Options: DENY`, `nosniff`, `SSL redirect`, `Referrer-Policy` : tous posés en production. |
| `csrf_exempt` | Dix-sept endpoints, tous des API publiques authentifiées par jeton, avec `SameSite=Lax` sur les cookies — pas de mutation accessible en `GET`. |

---

## Les tests

`tests/test_securite_audit_2.py` — quarante mesures. La moitié passe par
le HTML rendu ou par un POST réel, parce que vérifier qu'une fonction
accepte quelque chose ne prouve rien sur ce qu'un attaquant peut faire :
c'est l'erreur qui a laissé ces défauts en place.

Un test existant a dû être corrigé :
`test_register_creates_user_and_token` s'inscrivait avec
« password123 », que le validateur des mots de passe courants refuse
désormais. Il attestait la politique faible — celle de six caractères
que l'API s'était donnée.

Trois d'entre eux sont des **gardes contre la réapparition** : le premier
échoue si un fichier reprend `X-Forwarded-For[0]`, le deuxième si une
vue redirige sans vérifier, le troisième si un `set_cookie` d'API
repart sans `secure`. Les défauts de cet audit n'étaient pas dans un
fichier mais dans six, quinze et trois — écrits chaque fois sur le même
réflexe.
