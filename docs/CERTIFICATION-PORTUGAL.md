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
| **Códigos de Motivo de Isenção** (AT), v4.0 du 18/06/2026 | La table des motifs d'exonération (`TaxExemptionCode`). |
| **Código do IVA, art. 40.º** (rédaction du DL n.º 35/2025, en vigueur le 25/03/2025) | Les trois cas de la facture simplifiée et leurs plafonds. |
| **Código do IVA, art. 29.º n.º 7 et art. 36.º n.º 6** | Les documents rectificatifs — avoir **et note de débit** — et l'obligation de désigner la facture corrigée. |
| **Ofício-Circulado n.º 30141** du 04/01/2013 | Que les montants de l'article 40.º s'entendent **hors TVA**, et que l'acquéreur peut émettre une note de débit. |

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

### 2.5 Les motifs d'exonération — `isencao.py`

La table officielle de l'AT, **version 4.0 du 18 juin 2026**, recopiée
depuis le PDF publié et non d'après un site qui la reproduit : plusieurs
reproductions omettent M35, le plus récent.

Trois pièges que le module ferme :

- **Les codes ne sont pas contigus.** M03, M08, M17, M18, M22 à M24,
  M27 à M29 et M36 à M39 **n'existent pas**. Un code choisi par analogie
  — on voit M07 et M09, on écrit M08 — fait rejeter le fichier entier
  tout en ayant l'air aussi normal que les autres.
- **La « menção » est une mention légale du document**, pas une étiquette
  d'interface. Elle est relue dans la table d'après le code, jamais
  saisie à la main, et figure sur la facture.
- **M35 a une date d'entrée en vigueur** : factures émises à partir du
  1er juillet 2026 seulement. L'employer avant est un refus assuré.

**Ce qui concerne directement le BTP.** Deux codes servent à l'inversion
du redevable sur les travaux, et la liste déroulante les met en tête :

- **M31** — autoliquidation sur les services de construction civile en
  régime d'entreprise ou de sous-traitance, entre assujettis établis au
  Portugal. C'est le cas courant de la sous-traitance de chantier.
- **M35** — chantiers de construction ou de réhabilitation d'immeubles
  destinés à l'habitation propre et permanente de l'acquéreur, ou à la
  location à usage d'habitation (Decreto-Lei n.º 97/2026).

Le motif est exigé **à l'émission**, et non à l'export : à l'export, la
facture est déjà partie chez le client et on ne peut plus que constater
le manque.

### 2.6 La note de crédit — `facturation.py`

**Pourquoi elle est indispensable, et pas optionnelle.** Un document émis
ne se modifie plus : sa signature couvre son contenu, et tous les
suivants de la série signent la sienne. Le message d'erreur du modèle dit
donc « Émettez une note de crédit pour le corriger » — et sans cette
fonction, il désignerait quelque chose d'inexistant. La seule voie légale
de correction serait fermée.

L'avoir :

- **désigne toujours** le document qu'il rectifie, dans
  `Line/References/Reference` du SAF-T. Un avoir orphelin donne un
  fichier valide au schéma dont le contrôle relève l'incohérence ;
- **porte son motif**, dans `DocumentStatus/Reason` et
  `Line/References/Reason` — le schéma l'attend aux deux endroits. C'est
  lui qui distingue un geste commercial d'une erreur de facturation ;
- **reprend les lignes figées** du document d'origine, et non la facture
  de l'ERP, qui a pu changer depuis ;
- **va au débit** là où la facture va au crédit ;
- **ouvre sa propre chaîne**, dans la série NC : une chaîne par série ;
- **ne peut pas être émis deux fois** pour le même montant. Deux avoirs
  complets créditeraient deux fois le client, et pris séparément les deux
  documents sont parfaitement valides — rien dans la chaîne de signatures
  ne le dénoncerait.

L'écran est accessible d'un bouton sur la facture.

### 2.7 Les garanties structurelles — `models.py`

| Garantie | Comment |
|---|---|
| Numérotation sans trou | Compteur en base, verrou `SELECT FOR UPDATE` sur la série, tout dans une transaction. Un échec rend le numéro. |
| Format légal du numéro | `FT A/1`, validé contre le motif du SAF-T `[^ ]+ [^/^ ]+/[0-9]+`. |
| Document immuable | `save()` refuse toute modification d'un enregistrement existant ; `delete()` refuse la suppression. |
| Chaîne continue | La dernière signature de la série est relue **sous le même verrou** que le compteur. |
| Rotation de clé | Chaque document conserve la version de la clé qui l'a signé ; l'historique reste vérifiable. |
| Lignes figées | Le détail est recopié à l'émission, jamais relu depuis la facture vivante. |
| Clé privée chiffrée | Fernet au repos ; un échec de déchiffrement **le dit** au lieu de rendre une chaîne vide. |

### 2.8 Le SAF-T (PT) — `saft.py` et `export.py`

- Version **1.04_01**, `TaxAccountingBasis` = `F` (facturation).
- En-tête, clients, produits, table des taux, documents de vente.
- `Hash` porte la signature, `HashControl` la **version de la clé** —
  pas un contrôle du hachage, en dépit du nom.
- Totaux **recalculés** depuis les documents, jamais repris d'un cumul.
- L'ordre des éléments est écrit sous forme de listes nommées,
  relisibles contre le schéma, et **figé par des tests**.

### 2.9 La vérification contre le schéma de l'AT — `schema.py`

Le schéma publié par l'administration, `SAFTPT1.04_01.xsd`, est **versé
dans le dépôt** (`apps/fiscal_pt/schemas/`, 104 Ko, sha256
`292c0ab4…`). La vérification est donc reproductible sans accès au
réseau.

Deux usages :

1. **Les tests comparent les listes d'ordre au schéma lui-même**, élément
   par élément. Elles sont recopiées à la main dans `saft.py` ; sans
   cette comparaison, un test écrit d'après la même lecture confirmerait
   la même erreur. Les onze listes correspondent exactement.
2. **L'écran d'export vérifie le fichier avant de le remettre.** Un
   élément déplacé découvert ici coûte une minute ; découvert dans le
   courriel de rejet, il coûte une remise — et le message de l'AT désigne
   l'élément *suivant*, ce qui envoie chercher la cause au mauvais
   endroit.

Le fichier reste téléchargeable d'un second clic malgré les anomalies :
un validateur qui empêche de récupérer son propre travail se fait
contourner, et c'est alors plus personne qui vérifie.

**Pourquoi pas `lxml`.** Il valide un XSD complètement, et c'est une
dépendance compilée de plus dans un projet qui n'en a pas besoin
ailleurs. Le XSD est du XML : on en extrait le modèle de contenu avec la
bibliothèque standard.

**Ce qui est vérifié** : la structure — ordre des éléments, éléments
obligatoires absents, éléments inconnus, `choice` dont il faut exactement
un membre — sur 78 chemins, **et les valeurs** sur 387 : motifs,
énumérations, longueurs, bornes numériques.

Les constantes écrites à la main sont confrontées au schéma : les types
de document, les états, la base comptable, les régions fiscales, les
codes de taux, la version annoncée, et le motif du numéro de document.

**Ce que le schéma ne sait pas dire** fait l'objet d'un second contrôle,
`coherence.py`, décrit ci-dessous.

**La subtilité qui commande toute la conception.** Le schéma définit
**quatre** `Line` et quatre `DocumentStatus`, un par famille de
documents. Celui des mouvements de marchandises n'a ni `TaxBase` ni
`References` ; celui des paiements n'a même pas de `ProductCode`. Un
validateur qui chercherait les définitions par *nom* en prendrait une au
hasard, et accepterait un fichier faux ou refuserait un fichier juste. Le
modèle est donc indexé par **chemin**.

#### La cohérence — `coherence.py`

Un XSD décrit une **forme**. Il ne sait pas dire que `GrossTotal` doit
égaler `NetTotal` plus `TaxPayable`, ni qu'un `ProductCode` employé sur
une ligne doit figurer dans le référentiel. Le validateur de l'AT, lui,
vérifie les deux : **un fichier conforme au schéma mais incohérent est
rejeté tout autant**, et le motif du rejet est alors bien plus difficile
à comprendre, parce qu'il parle de cohérence et non de structure.

Deux familles de contrôles :

**L'arithmétique.** `GrossTotal` contre `NetTotal` plus `TaxPayable`,
exactement — les trois nombres sont écrits par nous, un écart signifie
que l'un a été calculé autrement. `NetTotal` contre la somme des lignes,
exactement. `TaxPayable` contre la TVA recalculée depuis les taux, **à
l'arrondi près**. Puis, pour le fichier entier, `NumberOfEntries`,
`TotalCredit` et `TotalDebit`.

La tolérance d'arrondi est d'**un centime par ligne**, et ce n'est pas du
laxisme : la TVA se calcule ligne par ligne, chaque ligne arrondie au
centime, et la somme des arrondis diffère parfois d'un centime de la TVA
calculée sur le total. Refuser cela rendrait le contrôle inutilisable ;
une tolérance plus large laisserait passer une vraie incohérence.

**Le référentiel.** Chaque `ProductCode`, chaque `CustomerID`, chaque
couple (`TaxCode`, `TaxCountryRegion`) doit exister dans `MasterFiles`.
C'est l'oubli le plus fréquent : les documents sont justes, le
référentiel est incomplet, et le fichier est rejeté en entier.

**Et les dates.** Un document hors de la période déclarée, une `Period`
qui n'est pas le mois du document — elle ne casse ni le schéma ni
l'arithmétique, elle range le document dans le mauvais mois et l'écart
n'apparaît qu'au rapprochement des déclarations de TVA —, et un
`SystemEntryDate` antérieur à la date du document, qui est le signe d'une
antidate.

**L'ordre des deux contrôles compte.** La cohérence ne se vérifie que si
la structure tient. Sur un fichier dont les totaux manquent, les
contrôles arithmétiques crieraient à l'incohérence pour chacun — une
avalanche de messages dont aucun ne désigne la cause réelle.

#### Deux trouvailles de cette confrontation

**L'accent circonflexe du motif de numéro.** Le schéma écrit
`[^ ]+ [^/^ ]+/[0-9]+` : la série exclut la barre oblique, l'espace **et
l'accent circonflexe**. Une première copie écrivait `[^/ ]+`, qui
laissait passer une série nommée « A^B » — acceptée par l'ERP, refusée
par le schéma. Un test compare désormais les deux motifs caractère par
caractère.

**Deux documents officiels se contredisent sur M15.** La table des
motifs publie « Regime da margem de lucro – Objetos de coleção e
antiguidades », qui fait **61 caractères**. Le schéma plafonne
`TaxExemptionReason` à **60**. Une entreprise qui facture des objets
d'art sous le régime de la marge produirait donc un fichier rejeté, en
employant le texte publié par l'administration elle-même.

Tronquer au soixantième caractère couperait « antiguidade|s » au milieu
d'un mot. Le module abrège donc explicitement, en remplaçant « e » par
« / » — tous les mots sont conservés. **La mention imprimée sur la
facture reste celle de la table** : c'est elle qui a valeur légale sur le
document ; l'abrègement ne concerne que le champ du fichier. Un test
garde la mesure, et échouera si une version future de l'un ou l'autre
texte lève la contradiction.

**Le NIF est validé à la saisie, clé comprise.** Le schéma n'impose que
les bornes — neuf chiffres de 100000000 à 999999999. Un NIF mal recopié,
deux chiffres intervertis, les respecte parfaitement : le fichier passe,
et le NIF désigne quelqu'un d'autre ou personne. L'erreur n'apparaîtrait
que lorsque l'administration ne retrouverait pas l'entreprise. Le
contrôle modulo 11 l'attrape à la saisie, et il coûte dix lignes.

### 2.9bis Les formes de facture, et ce que chacune exige — `tipos.py`

Le SAF-T accepte les cinq types de documents de facturation — `FT`, `FS`,
`FR`, `ND`, `NC` — avec **exactement les mêmes éléments obligatoires**.
Le schéma ne distingue rien. Trois documents illégaux passent donc le
contrôle du schéma **et** celui de la cohérence arithmétique :

- une **note de débit sans référence** à la facture qu'elle corrige ;
- une **facture-reçu qui n'atteste aucun paiement** ;
- une **facture simplifiée de douze mille euros**.

Les règles qui les interdisent sont dans le Code de l'IVA, pas dans le
XSD. C'est au logiciel de les tenir, et c'est précisément ce qu'une
certification vérifie.

#### Le défaut trouvé en chemin : deux notions pour une seule liste

`TYPES_AU_DEBIT = ('NC',)` servait à **deux** choses : décider du sens
débit/crédit dans le fichier, et décider quels documents doivent
désigner la facture qu'ils rectifient.

Les deux coïncident tant qu'on ne connaît que la note de crédit, qui est
à la fois rectificative et portée au débit. La **note de débit** les
sépare : l'article 29.º n.º 7 du CIVA la nomme *documento retificativo*
au même titre que l'avoir, et l'article 36.º n.º 6 lui impose « a
referência à fatura a que respeitam » — mais elle **augmente** ce que le
client doit, donc son montant va au **crédit** comme celui d'une facture.

Conséquence mesurée : le code **refusait** de rattacher une facture à une
note de débit (« un document de type ND ne rectifie rien »). Chaque note
de débit qu'il aurait pu émettre était donc irrégulière, et rien ne le
signalait — le schéma rend `References` optionnel.

Les deux notions sont désormais deux constantes distinctes, et un test
tombe si quelqu'un les réunifie.

#### Le plafond de la facture simplifiée, et une contradiction

L'article 40.º n.º 1 du CIVA, dans sa rédaction en vigueur depuis le
25 mars 2025, prévoit trois cas :

| Cas | Qui | Plafond |
|---|---|---|
| a) | Détaillants et marchands ambulants, à des non-assujettis | 1 000 € |
| b) | **Toutes les autres livraisons et prestations** | **100 €** |
| c) | Assujettis au régime d'exonération de l'art. 53.º | aucun |

Une entreprise de travaux relève du cas **b)**. Le cas applicable est un
réglage de l'entreprise — il dépend de l'activité, pas du document — et
non un choix offert sur chaque facture, où il finirait par être mis au
plus large.

**La contradiction.** L'article plafonne « o montante da fatura », ce qui
se lit comme le total à payer. L'Ofício-Circulado n.º 30141 du 4 janvier
2013 précise, lui, que « para determinação dos montantes referidos,
considera-se o valor da fatura sem o IVA ».

Les deux lectures ne divergent que dans une bande étroite : total hors
taxe sous le plafond, total à payer au-dessus. Choisir l'une et se taire
reviendrait soit à refuser des factures que l'administration accepte,
soit à en laisser passer qu'un contrôle pourrait reprendre. Le logiciel
**refuse** donc là où les deux lectures s'accordent, et **avertit sans
bloquer** dans la bande de divergence, en citant les deux textes. Le
choix revient à l'entreprise et à son comptable — mais il est fait en
connaissance de cause.

#### L'encaissement de la facture-reçu

Une facture-reçu vaut quittance : le client peut l'opposer comme preuve
de paiement. Elle doit donc porter au moins un `Payment`, et la somme
encaissée doit égaler le total **exactement**.

La tolérance d'un centime admise ailleurs sur la TVA n'a pas lieu d'être
ici : un encaissement n'est pas le résultat d'un arrondi, c'est une somme
qui a réellement changé de main. Un écart en moins atteste un solde payé
qui ne l'est pas ; un écart en plus déclare un encaissement qui n'a pas
eu lieu.

L'écran ne demande d'ailleurs **pas** le montant : c'est le total, et
toute autre valeur serait irrégulière. Demander le montant n'offrirait
que l'occasion de se tromper.

Les **quatorze** moyens de paiement sont relevés un par un dans
l'énumération `PaymentMechanism` du XSD vendu avec le logiciel, et non
dans une documentation qui la reproduit. Un test relit le schéma : si
l'AT en publie une version qui ajoute un code, c'est là qu'on l'apprend.

#### Un troisième défaut de la même famille

`SerieFiscale.type_document` porte des `choices`, que Django ne vérifie
qu'au `full_clean()` d'un formulaire. Une série créée autrement — un
script, un import, la base en direct — pouvait donc porter n'importe
quoi. Les documents s'émettaient et se **signaient** ; c'est l'export qui
les refusait, parce que `InvoiceType` est une énumération du schéma. À ce
moment-là le document est immuable et le **fichier entier** est bloqué,
pour un simple défaut de configuration.

La liste des cinq types vit désormais dans `tipos.py` — un fait légal,
que le code QR, le SAF-T et l'énumération du XSD citent tous les trois —
et `models` l'importe au lieu de la recopier. Le type est vérifié à
l'émission, et un test relit l'énumération du XSD pour confirmer que les
cinq y figurent.

#### Un défaut trouvé en mesurant, et non en relisant

`PaymentDate` n'était d'abord vérifié que **non vide**. Une saisie
malformée — un champ date d'un navigateur qui n'en a pas, une valeur
postée à la main — passait donc, et le composeur du SAF-T écrit
`str(valeur)[:10]` sans rien vérifier. Mesure faite :

```
saft.paiement({'date': 'pas-une-date'})
→ <PaymentDate>pas-une-da</PaymentDate>
```

Le document aurait été **signé et figé** avec cette valeur, et le défaut
ne se serait découvert qu'à l'export, des semaines plus tard, sur un
document que seul un avoir peut reprendre. C'est la forme la plus
coûteuse d'erreur de saisie : celle dont le coût arrive après le point de
non-retour. La date est désormais analysée avant la signature, et quatre
formes illisibles sont sous test — dont `07/03/2026`, le format français,
qui est précisément celui qu'on saisit par réflexe.

#### Où les contrôles ont lieu, et pourquoi deux fois

À l'**émission**, avant la signature : c'est le dernier instant où un
refus coûte encore quelque chose d'annulable. À l'**export** aussi, dans
`coherence.py` : un document importé d'un autre logiciel, ou émis avant
que la règle existe, n'est jamais passé par notre émission. Le fichier
remis est ce que l'AT regarde, donc c'est lui qu'il faut mesurer.

Une nuance que les tests gardent : ce qui est **exigé** d'un rectificatif
n'est pas **interdit** aux autres. Une facture peut légitimement renvoyer
à un bon de livraison. Signaler ce renvoi comme une anomalie apprendrait
à ignorer les messages du contrôle — le seul moyen de rendre un
validateur inutile sans le casser.

### 2.10 Les écrans

`/conformite-portugal/` — tout se pilote à l'écran, sans terminal :

- état de la conformité en cinq points, dans l'ordre où ils se remplissent ;
- création de clé (la précédente est retirée, les documents anciens
  restent vérifiables) ;
- déclaration des séries et saisie du code de validation de l'AT ;
- liste des documents, détail avec code QR, chaîne signée et mention ;
- **vérification des chaînes** d'un bouton : signature de chaque
  document **et** continuité de la chaîne, deux contrôles distincts ;
- export SAF-T de la période ;
- émission d'une **note de débit** depuis une facture signée, avec saisie
  des lignes à facturer en plus.

Les mentions légales (ATCUD, code QR, mention du programme certifié)
figurent aussi **sur la facture elle-même**, et pas seulement dans
l'écran d'administration.

### 2.11 Le branchement

`invoice_send` signe **avant** de changer le statut, dans la même
transaction. Si la signature échoue, la facture reste en brouillon et
rien ne part. L'inverse paraît plus accommodant et serait bien pire : la
facture sortirait sans preuve et rien ne le signalerait.

C'est aussi là que se choisit la **forme légale** — `FT`, `FS` ou `FR`.
Elle est écrite dans le numéro du document, signée avec lui, et ne se
change plus : l'envoi est le dernier instant où le choix est encore
ouvert. Elle n'est surtout pas déduite du montant, ce qui autoriserait
une facture simplifiée sans que personne ne l'ait voulue — irrégulière,
et sans TVA déductible pour le client.

Le menu n'offre que les formes dont une **série active** existe. Proposer
« facture simplifiée » pour la refuser à l'envoi donnerait un écran qui
désigne un problème au mauvais endroit, alors que la seule chose à faire
est de déclarer la série.

---

## 3. Ce qui reste à faire

### 3.1 Dans le logiciel

| Reste | Pourquoi ce n'est pas fait |
|---|---|
| **Communication des séries à l'AT par webservice** | Le service SOAP de l'AT demande un certificat client délivré à l'entreprise. Le code de validation se saisit donc à la main aujourd'hui, ce qui est légal mais manuel. |
| **Documents de mouvement de marchandises** | `MovementOfGoods` du SAF-T n'est pas produit. Obligatoire seulement si l'entreprise transporte des marchandises. |
| **Documents de travail** | `WorkingDocuments` (devis, bons) n'est pas produit. |
| **Reçus autonomes (`RG`)** | La facture-reçu `FR` est émise ; le reçu séparé d'un acompte ne l'est pas. Il relève de la table `Payments` du SAF-T, qui n'est pas produite. |
| **Plusieurs moyens de paiement sur une même facture-reçu** | Le modèle et le SAF-T en acceptent plusieurs — le schéma rend `Payment` répétable — mais l'écran n'en propose qu'un. La limite est dans la saisie, pas dans le fichier. |

### 3.2 Un défaut à corriger dans la facturation française

Indépendant du Portugal, trouvé en chemin, et réel :

`apps/sales/views.py` numérote les factures avec
`Invoice.objects.filter(company=company).count() + 1`. Deux
conséquences mesurables :

- **supprimez une facture et la suivante reprend un numéro déjà
  employé** ;
- deux créations simultanées obtiennent le même numéro.

Le service atomique `apps/core/numbering.py:next_number` existe pourtant
et n'est pas appelé ici — alors que la vue des devis, dans le même
fichier, l'appelle avec un commentaire qui explique précisément pourquoi
`count() + 1` est faux. **Ce point reste ouvert** : le corriger changerait
le format des numéros français (`FAC-0001` → `FAC-2026-0001`), ce qui est
visible par vos clients. Ce n'est pas un problème portugais — les
factures portugaises passent par les séries — mais c'en est un pour la
facturation française.

### 3.3 Un manque comblé en chemin : les lignes de facture

`InvoiceLine` était importé dans `apps/sales/forms.py` et instancié
**nulle part** dans l'application. Le modèle existait, l'écran de détail
affichait `invoice.lines`, et aucun chemin de code n'en créait jamais.

Le défaut ne se voyait pas : l'écran affichait fidèlement une liste vide,
et les totaux des factures restaient à zéro sans qu'aucune erreur
n'apparaisse. Au Portugal il était bloquant — le SAF-T exige au moins
une ligne par document, donc aucune facture conforme n'était possible.

Un éditeur de lignes a donc été ajouté au formulaire de facture :
désignation, référence, quantité, unité, prix, remise, taux et motif
d'exonération. Les totaux se recalculent depuis les lignes à chaque
enregistrement, plutôt que d'être tenus à part — un cumul mis à jour
« au passage » dériverait après la suppression d'une ligne, et au
Portugal ce centime est signé.

Au passage, le client n'était borné à l'entreprise qu'à l'affichage : un
identifiant forgé dans la requête rattachait la facture au client d'une
**autre** entreprise. Le contrôle existait dans la vue des devis, qui
l'appelle « la règle centrale de cet ERP », et manquait ici.

### 3.4 Les démarches auprès de l'AT

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
| `tests/test_fiscal_pt_isencao.py` | La table des motifs, et que les codes absents sont refusés. |
| `tests/test_lignes_de_facture.py` | La saisie des lignes, les totaux, et l'étanchéité entre entreprises. |
| `tests/test_fiscal_pt_avoir.py` | Qu'un avoir désigne sa facture, porte son motif, et ne crédite pas deux fois. |
| `tests/test_fiscal_pt_schema.py` | Que les listes d'ordre sont celles du XSD, que les fichiers produits passent, et que les fichiers cassés sont refusés. |
| `tests/test_fiscal_pt_coherence.py` | Que les totaux s'accordent, que les renvois au référentiel existent, et que chaque incohérence est nommée. |
| `tests/test_fiscal_pt_tipos.py` | Les règles du CIVA propres à chaque type, mesurées hors base : plafond de la facture simplifiée, encaissement de la facture-reçu, référence des rectificatifs, les quatorze moyens de paiement relus dans le XSD. |
| `tests/test_fiscal_pt_formes_de_facture.py` | Que le chemin réel — formulaire, série, signature, gel, export — applique ces règles **avant** que le document devienne immuable, et que le fichier produit porte les quatre formes en restant conforme. |

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
