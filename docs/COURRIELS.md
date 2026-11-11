# Les courriels d'Orion ERP

Où les régler, comment savoir pourquoi ils n'arrivent pas, et pourquoi un
envoi réussi ne garantit pas une remise.

## Où ça se règle

**`/orion-admin/courriels/`** — menu Super Admin → Courriels.

Le serveur SMTP, le port, le chiffrement, l'identifiant, le mot de passe et
l'adresse d'expédition sont stockés en base de données. Aucun accès SSH,
aucun redémarrage de service. Le mot de passe est chiffré avec la clé
`ORION_SECRET_ENCRYPTION_KEY` générée au provisionnement.

Les variables `EMAIL_*` du fichier `.env` subsistent comme **repli**, employé
tant que la case « Envoyer réellement les courriels » n'est pas cochée.

## Mettre en route

Deux chemins. Le premier est plus simple et arrive à destination ; le second
ne dépend de personne.

### Chemin 1 — un service d'envoi tiers (recommandé)

Brevo, Mailgun, Amazon SES, OVH, Scaleway : tous donnent un hôte, un port, un
identifiant et un mot de passe. Les enregistrements d'authentification à
poser dans votre DNS sont fournis par le service, et la question du DNS
inverse (voir plus bas) est déjà réglée de leur côté.

1. Créez le compte, relevez les quatre valeurs SMTP.
2. Reportez-les sur `/orion-admin/courriels/`.
3. Cliquez **Enregistrer et envoyer un test**. L'erreur du serveur, s'il y en
   a une, s'affiche mot pour mot.
4. Une fois le test réussi, cochez « Envoyer réellement les courriels ».
5. Ajoutez les enregistrements SPF et DKIM que le service indique.

### Chemin 2 — le relais auto-hébergé

Le dépôt fournit `deployment/proxmox-appliance/scripts/setup_mail_relay.sh`,
qui installe Postfix et OpenDKIM en mode « envoi seul » : l'écoute se limite
à `127.0.0.1:25`, donc le relais ne peut pas devenir ouvert.

```
pct exec 100 -- env DOMAIN=votre-domaine.fr \
  MAIL_HOSTNAME=mail.votre-domaine.fr \
  /bin/bash /opt/orion/backend/deployment/proxmox-appliance/scripts/setup_mail_relay.sh
```

Le script affiche ensuite les enregistrements SPF, DKIM et DMARC exacts à
ajouter. Puis, sur `/orion-admin/courriels/` : hôte `127.0.0.1`, port `25`,
chiffrement « Aucun », pas d'identifiant.

**Le prérequis qui bloque le plus souvent** est le PTR, ci-dessous.

## Pourquoi un courriel part sans arriver

Un test réussi prouve seulement que votre serveur a **accepté** le message.
La remise dépend ensuite de quatre choses, toutes dans le DNS :

| | Ce que c'est | Qui le pose |
|---|---|---|
| **SPF** | Autorise votre serveur à écrire au nom du domaine | Vous, dans votre DNS |
| **DKIM** | Signature cryptographique du message | Le relais ou le service le génère ; vous publiez la clé |
| **DMARC** | Ce que le destinataire doit faire si SPF ou DKIM échoue | Vous |
| **PTR** | L'IP d'envoi se résout vers le nom du serveur de mail | **L'hébergeur de la machine** |

Le PTR, ou DNS inverse, est celui sur lequel l'auto-hébergement échoue. Il ne
se configure pas sur le serveur : il se demande à qui possède l'adresse IP.
Une ligne résidentielle ne l'obtient généralement pas, et Gmail comme Outlook
rejettent ou classent en indésirable un expéditeur sans PTR cohérent. C'est la
raison principale de préférer le chemin 1.

À noter pour l'appliance : l'enregistrement A du nom de mail doit être en
**DNS-only**, pas proxifié par Cloudflare — le proxy Cloudflare ne relaie pas
le SMTP.

## Diagnostiquer

**La page elle-même** garde le résultat de la dernière tentative, réussie ou
non, avec le message du serveur. Ce motif survit à la requête : un envoi
déclenché par une tâche de fond échoue loin de tout écran, et la trace reste
lisible ici.

**Le contrôle de santé** (`apps/system_observability`) ouvre une vraie
connexion SMTP et remonte l'erreur. Il signale aussi — et c'est nouveau — le
cas où l'ERP n'envoie **rien** : un backend « console » ou « mémoire » était
auparavant déclaré en bon état, avec la mention « pas de SMTP à vérifier ».

**Les journaux.** Quatre endroits du code envoient avec `fail_silently=True`,
pour qu'un courriel manqué ne fasse pas échouer l'opération qui le déclenche —
une invitation au portail client ne doit pas annuler l'inscription. L'échec
est désormais journalisé quand même, sous le logger `orion`. Avant, Django
l'absorbait dans son propre backend et il n'en sortait rien : c'est l'origine
de « les mails ne fonctionnent pas » sans aucune indication.

## Qui envoie quoi

| Endroit | Message |
|---|---|
| `apps/portals/services/signup_service.py` | Inscription au portail client |
| `apps/ecommerce/auth_views.py` | Réinitialisation de mot de passe des boutiques |
| `apps/ecommerce/order_emails.py` | Confirmation de commande |
| `apps/smart_automations/services.py` | Automatisations |
| `apps/launch/views.py` | Avertissement aux administrateurs |

Les boutiques composent leur propre expéditeur par marque
(`no-reply@siecle.fr`, `no-reply@lunea.fr`). L'adresse d'expédition de la page
ne les remplace pas : elle ne s'applique qu'aux messages qui n'ont rien
choisi. Un seul serveur d'envoi avec plusieurs adresses d'expéditeur est le
montage habituel.

## Ce qui n'est pas fait

- **Un SMTP par entreprise.** Les réglages sont uniques pour l'appliance. Le
  serveur est commun à toutes les sociétés hébergées, et seule l'adresse
  d'expédition varie. Un serveur par entreprise serait une extension.
- **Le relais installable depuis l'interface.** `setup_mail_relay.sh` demande
  les droits root et des enregistrements DNS que vous devez créer de toute
  façon.
- **Une file d'attente avec réessais.** Un courriel manqué est journalisé,
  pas rejoué.
