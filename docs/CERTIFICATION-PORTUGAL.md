# Certification du logiciel de facturation au Portugal

Ce document dit trois choses : ce que la loi portugaise exige, ce que
l'ERP fait aujourd'hui, et ce qui reste à faire avant de pouvoir déposer
une demande de certification auprès de l'**Autoridade Tributária e
Aduaneira** (AT).

Il est écrit pour être relu contre les textes. Chaque exigence porte sa
référence.

---

## 1. Les textes qui s'appliquent

| Texte | Ce qu'il impose |
|---|---|
| **Portaria n.º 363/2010** | Les règles de certification des programmes de facturation. |
| **Despacho n.º 8632/2014** | Les paramètres exacts de la signature : RSA, 1024 bits, SHA-1, PKCS#1 v1.5, base 64, 172 caractères. |
| **Portaria n.º 302/2016** | Le format SAF-T (PT), version 1.04_01. |
| **Portaria n.º 195/2020** | L'ATCUD et le code QR. |
| **Especificações Técnicas Código QR** (AT) | Le contenu champ par champ du code QR. |

Deux remarques qui surprennent et qui sont pourtant la règle :

- **RSA-1024 et SHA-1 sont obligatoires.** Ils sont aujourd'hui
  considérés comme faibles. Une signature plus solide serait **refusée**
  à la certification. Le code les fixe explicitement et refuse une clé
  de 2048 bits, avec un commentaire pour qu'un relecteur ne « corrige »
  pas ce qui est une obligation légale.
- **Le numéro de certificat vaut `0`** tant que l'AT n'en a pas attribué
  un. C'est la valeur correcte, et non une erreur à corriger. Y inscrire
  un numéro d'emprunt serait une fausse déclaration.

---

## 2. Ce qui est en place

Le module `apps/fiscal_pt`. Il est **inactif par défaut** : une
installation qui ne facture pas au Portugal ne voit aucune différence.

### 2.1 La signature chaînée — `assinatura.py`

- Chaîne signée `InvoiceDate;SystemEntryDate;InvoiceNo;GrossTotal;HashPrécédent`,
  vérifiée contre l'exemple officiel du Despacho
  (`2010-05-18;2010-05-18T11:22:19;FAC 001/14;3.12;`).
- RSA-1024, SHA-1, PKCS#1 v1.5, base 64, **172 caractères** contrôlés.
- Les quatre caractères imprimés (positions 1, 11, 21, 31) et la mention
  `…-Processado por programa certificado n.º NNNN/AT`.
- La mention des documents **non signés** (les reçus), que le Despacho
  traite à part et qu'on oublie facilement.

### 2.2 L'ATCUD — `atcud.py`

- Composition `<code de validation>-<numéro séquentiel>`.
- **Refus d'inventer le code de validation.** Il vient de l'AT. Un code
  fabriqué localement produirait des documents d'apparence correcte et
  juridiquement nuls, sur des mois de facturation.
- Série non communiquée → ATCUD `0-n`, la marque explicite prévue par la
  Portaria.

### 2.3 Le code QR — `qr.py`

- Champs A à S dans l'ordre du tableau officiel, séparateur `*`.
- Vérifié **au caractère près** contre les deux exemples publiés par
  l'AT (figures 5 et 6 de la spécification).
- Les trois espaces fiscaux prennent `I`, `J`, `K` selon leur **ordre
  d'apparition** et non selon la région — c'est l'erreur la plus
  fréquente.
- Un champ optionnel vide est **omis**, pas écrit vide.

### 2.4 Les paliers de TVA — `taxas.py`

Un taux ne vaut rien sans sa région : 22 % est le taux **normal** à
Madère et n'existe pas sur le continent. La table couvre les trois
régions, et un taux étranger (20 %, par exemple) **arrête l'émission**
au lieu d'être rangé dans le palier voisin.

### 2.5 Les garanties structurelles — `models.py`

| Garantie | Comment |
|---|---|
| Numérotation sans trou | Compteur en base, verrou `SELECT FOR UPDATE` sur la série, tout dans une transaction. Un échec rend le numéro. |
| Format légal du numéro | `FT A/1`, validé contre le motif du SAF-T `[^ ]+ [^/^ ]+/[0-9]+`. |
| Document immuable | `save()` refuse toute modification d'un enregistrement existant ; `delete()` refuse la suppression. |
| Chaîne continue | La dernière signature de la série est relue **sous le même verrou** que le compteur. |
| Rotation de clé | Chaque document conserve la version de la clé qui l'a signé ; l'historique reste vérifiable. |
| Lignes figées | Le détail est recopié à l'émission, jamais relu depuis la facture vivante. |
| Clé privée chiffrée | Fernet au repos ; un échec de déchiffrement **le dit** au lieu de rendre une chaîne vide. |

### 2.6 Le SAF-T (PT) — `saft.py` et `export.py`

- Version **1.04_01**, `TaxAccountingBasis` = `F` (facturation).
- En-tête, clients, produits, table des taux, documents de vente.
- `Hash` porte la signature, `HashControl` la **version de la clé** —
  pas un contrôle du hachage, en dépit du nom.
- Totaux **recalculés** depuis les documents, jamais repris d'un cumul.
- L'ordre des éléments est écrit sous forme de listes nommées,
  relisibles contre le schéma, et **figé par des tests**.

### 2.7 Les écrans

`/conformite-portugal/` — tout se pilote à l'écran, sans terminal :

- état de la conformité en cinq points, dans l'ordre où ils se remplissent ;
- création de clé (la précédente est retirée, les documents anciens
  restent vérifiables) ;
- déclaration des séries et saisie du code de validation de l'AT ;
- liste des documents, détail avec code QR, chaîne signée et mention ;
- **vérification des chaînes** d'un bouton : signature de chaque
  document **et** continuité de la chaîne, deux contrôles distincts ;
- export SAF-T de la période.

Les mentions légales (ATCUD, code QR, mention du programme certifié)
figurent aussi **sur la facture elle-même**, et pas seulement dans
l'écran d'administration.

### 2.8 Le branchement

`invoice_send` signe **avant** de changer le statut, dans la même
transaction. Si la signature échoue, la facture reste en brouillon et
rien ne part. L'inverse paraît plus accommodant et serait bien pire : la
facture sortirait sans preuve et rien ne le signalerait.

---

## 3. Ce qui reste à faire

### 3.1 Dans le logiciel

| Reste | Pourquoi ce n'est pas fait |
|---|---|
| **Communication des séries à l'AT par webservice** | Le service SOAP de l'AT demande un certificat client délivré à l'entreprise. Le code de validation se saisit donc à la main aujourd'hui, ce qui est légal mais manuel. |
| **Notes de crédit (NC) et autres types** | La mécanique les accepte (`TYPES_DE_DOCUMENT`, débit/crédit au SAF-T), mais aucun écran ne les émet encore depuis l'ERP. |
| **Documents de mouvement de marchandises** | `MovementOfGoods` du SAF-T n'est pas produit. Obligatoire seulement si l'entreprise transporte des marchandises. |
| **Documents de travail** | `WorkingDocuments` (devis, bons) n'est pas produit. |
| **Reçus (FR / RG)** | La mention « sans signature » existe, l'émission non. |
| **Motifs d'exonération** | Le SAF-T les exige dès qu'une ligne est à 0 % ; il faut un champ par ligne dans l'ERP pour les saisir (`M01`…`M99`). Aujourd'hui l'export **refuse** une ligne exonérée sans motif, ce qui est préférable à un fichier rejeté, mais bloque la facturation exonérée. |
| **Validation contre le XSD officiel** | Les tests figent l'ordre et les champs d'après le schéma, mais aucune validation automatique contre le fichier `.xsd` de l'AT n'est branchée. |

### 3.2 Un défaut à corriger dans la facturation française

Indépendant du Portugal, trouvé en chemin, et réel :

`apps/sales/views.py` numérote les factures avec
`Invoice.objects.filter(company=company).count() + 1`. Deux
conséquences mesurables :

- **supprimez une facture et la suivante reprend un numéro déjà
  employé** ;
- deux créations simultanées obtiennent le même numéro.

Le service atomique `apps/core/numbering.py:next_number` existe pourtant
et n'est pas appelé ici. Ce n'est pas un problème portugais — les
factures portugaises passent par les séries — mais c'en est un pour la
facturation française.

### 3.3 Les démarches auprès de l'AT

Le code ne suffit pas. La certification est une **demande
administrative** :

1. L'éditeur doit avoir un **NIF portugais** et être enregistré auprès
   de l'AT.
2. Déposer le formulaire de demande de certification, en décrivant le
   programme et en joignant une **déclaration de conformité** aux
   exigences de la Portaria 363/2010.
3. Fournir un **jeu de documents d'essai** et le SAF-T correspondant,
   que l'AT revérifie — signatures recalculées, codes QR relus.
4. Remettre la **clé publique** employée pour les signatures.
5. L'AT attribue un **numéro de certificat**, à saisir dans
   Conformité Portugal → Paramètres. Il apparaît alors sur chaque
   document et dans l'en-tête du SAF-T.

Le point 3 est celui que le travail décrit ici prépare : les signatures,
les ATCUD, les codes QR et le SAF-T sont produits selon les textes, et
les tests les comparent aux exemples publiés par l'administration.

---

## 4. Les tests

| Fichier | Ce qu'il prouve |
|---|---|
| `tests/test_fiscal_pt.py` | Les calculs, contre les exemples officiels de l'AT. |
| `tests/test_fiscal_pt_saft.py` | L'ordre des éléments du SAF-T, bloc par bloc. |
| `tests/test_fiscal_pt_models.py` | Numérotation sans trou, immuabilité, chaînage, rotation de clé. |
| `tests/test_fiscal_pt_vues.py` | Que chaque geste se fait réellement à l'écran. |
| `tests/test_fiscal_pt_facturation.py` | Qu'une facture ne peut pas partir sans sa signature. |

Deux limites, dites franchement :

- Les tests ne prouvent **pas** qu'une signature produite ici serait
  acceptée par l'AT : cela dépend de la clé privée que l'AT enregistre
  pour l'éditeur, et qu'on ne possède pas. Ils prouvent que le
  **mécanisme** est conforme — format, longueur, chaînage, ordre des
  champs.
- Le champ `G` des deux exemples de code QR est repris de l'extraction du
  PDF officiel, qui ne permet pas de trancher son espacement interne. Les
  tests le passent en entrée et l'attendent en sortie à l'identique : ils
  ne dépendent donc pas de cette lecture.
