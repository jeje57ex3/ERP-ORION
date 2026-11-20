"""apps/fiscal_pt/models.py — Clés, séries et documents signés.

CE QUE CETTE COUCHE AJOUTE

Les modules `assinatura`, `atcud`, `qr` et `taxas` calculent. Ici on
CONSERVE, et la conservation est elle-même une obligation : le Despacho
8632/2014 exige que la signature soit stockée avec la version de la clé
qui l'a produite, et la Portaria 195/2020 que chaque série soit déclarée
à l'AT avant son premier document.

TROIS GARANTIES, ET ELLES SONT STRUCTURELLES

1. UNE SÉRIE NUMÉROTE SANS TROU. Le compteur vit en base et s'incrémente
   sous verrou, dans la même transaction que le document. Un document qui
   échoue à s'enregistrer rend son numéro ; deux émissions simultanées
   n'obtiennent jamais le même.

2. UN DOCUMENT ÉMIS NE CHANGE PLUS. `save()` refuse toute modification
   d'un enregistrement existant. Ce n'est pas une convention : c'est la
   seule façon de garantir que la chaîne de signatures reste vérifiable,
   puisque modifier un document invalide tous les suivants.

3. LA CHAÎNE EST CONTINUE. Chaque document signe la signature du
   précédent de SA série. On relit donc la dernière signature en base,
   sous le même verrou que le compteur — sans quoi deux documents
   pourraient se référer au même prédécesseur.
"""

import re
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from . import assinatura, atcud, isencao, qr, taxas, tipos

#: Le format que le SAF-T (PT) impose au numéro de document.
#:
#: Recopié EXACTEMENT du schéma de l'AT, où `InvoiceNo` porte le motif
#: « [^ ]+ [^/^ ]+/[0-9]+ » : un type, une espace, une série sans barre
#: oblique ni accent circonflexe, une barre oblique, un numéro. « FT A/1 »
#: passe ; « FAC-2026-0042 » ne passe pas — ni espace, ni barre oblique.
#: Un export entier serait rejeté pour cette seule raison, et le numéro,
#: lui, a l'air parfaitement normal.
#:
#: L'ACCENT CIRCONFLEXE EXCLU N'EST PAS UN DÉTAIL DE COPIE. Une première
#: version écrivait « [^/ ]+ », qui laissait passer une série nommée
#: « A^B » : le numéro était accepté ici et refusé par le schéma. Un test
#: compare désormais ce motif à celui du XSD, caractère par caractère.
MOTIF_NUMERO_SAFT = re.compile(r'[^ ]+ [^/^ ]+/[0-9]+')

#: Les bornes du NIF portugais, telles que le schéma les fixe sur
#: `TaxRegistrationNumber` : un entier de 100000000 à 999999999, donc
#: neuf chiffres dont le premier n'est pas zéro.
NIF_MINIMUM = 100000000
NIF_MAXIMUM = 999999999


def valider_nif(valeur, obligatoire=True):
    """Le NIF portugais : neuf chiffres, et le chiffre de contrôle juste.

    POURQUOI LE CHIFFRE DE CONTRÔLE EST VÉRIFIÉ ICI

    Le schéma de l'AT n'impose que les bornes : neuf chiffres. Un NIF mal
    recopié — deux chiffres intervertis — les respecte parfaitement, passe
    la validation du fichier, et désigne quelqu'un d'autre ou personne.

    L'erreur ne se découvre alors ni à la saisie, ni à la remise du
    SAF-T : elle apparaît quand l'administration ne retrouve pas
    l'entreprise, des mois après. Le contrôle modulo 11 l'attrape
    immédiatement, et il coûte dix lignes.
    """
    texte = str(valeur or '').strip().replace(' ', '')

    if not texte:
        if obligatoire:
            raise ValidationError(
                'Le NIF est absent. Il figure dans le code QR et dans '
                'l’en-tête du SAF-T.')
        return ''

    if not texte.isdigit() or len(texte) != 9:
        raise ValidationError(
            f'« {texte} » n’est pas un NIF portugais : le schéma de l’AT en '
            'exige neuf chiffres, sans préfixe de pays ni séparateur.')

    if not (NIF_MINIMUM <= int(texte) <= NIF_MAXIMUM):
        raise ValidationError(
            f'« {texte} » est hors des bornes du schéma '
            f'({NIF_MINIMUM} à {NIF_MAXIMUM}).')

    # Modulo 11 sur les huit premiers chiffres, pondérés de 9 à 2.
    somme = sum(int(chiffre) * poids
                for chiffre, poids in zip(texte[:8], range(9, 1, -1)))
    reste = somme % 11
    attendu = 0 if reste in (0, 1) else 11 - reste

    if int(texte[8]) != attendu:
        raise ValidationError(
            f'« {texte} » a un chiffre de contrôle incorrect : {attendu} '
            f'était attendu en dernière position. Deux chiffres intervertis '
            'suffisent, et l’erreur ne se verrait ni à la saisie ni à la '
            'remise du fichier — seulement quand l’administration ne '
            'retrouverait pas l’entreprise.')

    return texte

#: Les types de documents de facturation, tels que l'AT les nomme. Ce sont
#: les valeurs du champ D du code QR et de « InvoiceType » du SAF-T.
#:
#: La liste vit dans `tipos` — c'est un fait legal, que le code QR, le
#: SAF-T et l'enumeration du XSD citent tous les trois — et on l'importe
#: plutot que de la recopier : deux listes jumelles finissent toujours
#: par diverger, et celle-ci borne ce que l'export acceptera.
TYPES_DE_DOCUMENT = tipos.TYPES_DE_DOCUMENT

#: Le sens debit/credit dans le fichier. La constante vit dans `saft`,
#: parce que c'est elle qui en decide ; on l'importe plutot que de la
#: recopier, deux listes jumelles finissant toujours par diverger.
#:
#: Elle ne dit QUE le sens. Les types qui doivent designer la facture
#: qu'ils rectifient sont dans `tipos.TYPES_RECTIFICATIFS`, et ce n'est
#: pas la meme liste : la note de debit rectifie une facture et porte son
#: montant au credit.
from .saft import TYPES_AU_DEBIT  # noqa: E402,F401

#: Les états possibles d'un document de facturation (champ E du code QR).
#:
#: La liste vit dans `tipos`, comme celle des types : c'est une
#: énumération du schéma, et les reçus en ont une AUTRE, plus courte.
#: Deux listes jumelles tenues à deux endroits finissent par diverger, et
#: celle-ci borne ce que l'export acceptera.
#:
#: Au passage, « R » y était libellé « Autre ». Le schéma le documente
#: autrement : « R para Documento de resumo doutros documentos criados
#: noutras aplicacoes ». Un libellé d'écran qui désinforme sur un état
#: fiscal n'est pas un détail de rédaction.
ETATS_DE_DOCUMENT = tipos.ETATS_DE_FACTURATION

#: Les états d'un reçu — deux, et non cinq. Voir `tipos.ETATS_DE_RECU`.
ETATS_DE_RECU = tipos.ETATS_DE_RECU


def valider_numero_saft(valeur):
    """Refuse à la saisie un numéro que le SAF-T rejetterait."""
    if not MOTIF_NUMERO_SAFT.fullmatch(str(valeur or '')):
        raise ValidationError(
            f'« {valeur} » n’est pas un numéro de document valide au '
            'Portugal. Le SAF-T (PT) exige la forme « TYPE SÉRIE/NUMÉRO », '
            'par exemple « FT A/1 ».')


def ligne_figee(contenu, region=taxas.CONTINENT, date_document=None):
    """Normalise une ligne de facture en la forme que le SAF-T attend.

    On exige le minimum indispensable et on complète le reste : une
    description et une base suffisent à émettre, mais le code produit,
    l'unité et la quantité sont obligatoires dans le SAF-T. Les déduire
    ici, à l'émission, vaut mieux que de les inventer à l'export — à ce
    moment-là la facture d'origine a pu changer, et on ne saurait plus ce
    qui avait réellement été facturé.

    UNE LIGNE SANS TVA DOIT PORTER SON MOTIF, et il est exigé ICI plutôt
    qu'à l'export. À l'export, la facture est déjà partie chez le client :
    on ne peut plus que constater le manque. À l'émission, on peut encore
    demander le motif à celui qui facture.
    """
    description = str(contenu.get('description') or '').strip()
    if not description:
        raise ValidationError(
            'Une ligne sans description ne peut pas être facturée : le '
            'SAF-T exige « ProductDescription » sur chaque ligne.')

    base = Decimal(str(contenu.get('base', 0) or 0))
    taux = Decimal(str(contenu.get('taux', 0) or 0))
    tva = contenu.get('tva')
    tva = (Decimal(str(tva)) if tva is not None
           else (base * taux / Decimal('100')).quantize(Decimal('0.01')))
    quantite = Decimal(str(contenu.get('quantite', 1) or 1))
    prix = contenu.get('prix_unitaire')
    prix = (Decimal(str(prix)) if prix is not None
            else (base / quantite if quantite else Decimal('0')))

    code_de_taux = taxas.code_saft(taux, region)

    # Le motif n'est PAS recopié de la saisie : il est relu dans la table
    # officielle d'après le code. Une mention tapée à la main serait
    # fautive une fois sur dix, et c'est une mention légale du document.
    code_exoneration = ''
    motif_exoneration = ''
    mention_facture = ''
    if code_de_taux == 'ISE':
        try:
            code_exoneration = isencao.valider(
                contenu.get('code_exoneration'), date_document)
        except isencao.MotifInvalide as exc:
            raise ValidationError(
                f'Ligne « {description[:60]} » : {exc}')

        # DEUX MENTIONS, ET CE N'EST PAS UNE REDONDANCE.
        #
        # Celle de la facture a valeur légale sur le document imprimé.
        # Celle du SAF-T entre dans un champ borné à 60 caractères, que la
        # mention officielle de M15 dépasse d'un caractère. Les confondre
        # ferait soit rejeter le fichier, soit amputer la facture.
        mention_facture = isencao.mencao(code_exoneration)
        motif_exoneration = isencao.mencao_saft(code_exoneration)

    return {
        'description': description[:200],
        'code_produit': str(contenu.get('code_produit')
                            or _code_produit(description)),
        'quantite': quantite,
        'unite': str(contenu.get('unite') or 'UN'),
        'prix_unitaire': prix,
        'base': base,
        'taux': taux,
        'tva': tva,
        'code_de_taux': code_de_taux,
        'motif_exoneration': motif_exoneration,
        'mention_facture': mention_facture,
        'code_exoneration': code_exoneration,
    }


def _code_produit(description):
    """Un code produit déduit de la description, à défaut de référence.

    Le SAF-T exige un « ProductCode » sur chaque ligne, et chaque code
    employé doit figurer dans le référentiel. Un code vide ferait rejeter
    le fichier ; un code déduit, stable pour une même description, permet
    de construire un référentiel cohérent.
    """
    import hashlib

    empreinte = hashlib.sha1(description.encode('utf-8')).hexdigest()[:8]
    return f'SRV{empreinte.upper()}'


def _pour_json(figee):
    """Les montants en TEXTE, jamais en `float`.

    Un `float` perd des centimes sur de gros totaux, et la signature porte
    sur le total : un écart d'un centime entre la ligne stockée et le
    total signé rendrait le SAF-T incohérent avec sa propre preuve.
    """
    return {cle: (str(valeur) if isinstance(valeur, Decimal) else valeur)
            for cle, valeur in figee.items()}


def _paiement_pour_json(paiement):
    """Un encaissement figé : trois clés, et rien d'autre.

    On ne recopie PAS le dictionnaire reçu tel quel. Un appelant qui y
    aurait glissé un objet de règlement entier ferait grossir le JSON de
    tout ce que la comptabilité sait du paiement — données qui n'ont rien
    à faire dans un document immuable, et qui changeraient de forme au
    premier refactoring du module de trésorerie.
    """
    date = paiement.get('date')
    return {
        'mecanisme': paiement.get('mecanisme') or '',
        'montant': str(paiement.get('montant') or 0),
        'date': date.isoformat() if hasattr(date, 'isoformat') else str(date),
    }


def _affectation_pour_json(affectation):
    """Une affectation de reçu figée : cinq clés, et rien d'autre.

    Le montant en TEXTE pour la même raison que les lignes de facture : un
    `float` perd des centimes, et c'est le total qui est signé.

    Le sens est figé LUI AUSSI, et non recalculé à l'export depuis le type
    du document réglé. Ce type se relit dans une autre table, qui a pu
    changer — et un reçu doit dire ce qu'il a attesté le jour où il a été
    remis, pas ce qu'on en déduirait aujourd'hui.
    """
    date = affectation.get('date')
    return {
        'document': str(affectation.get('document') or ''),
        'date': date.isoformat() if hasattr(date, 'isoformat') else str(date),
        'montant': str(affectation.get('montant') or 0),
        'au_debit': bool(affectation.get('au_debit')),
        'description': str(affectation.get('description') or ''),
    }


def _attribuer_le_numero(verrouillee, modele):
    """Le numéro suivant de la série, et la signature à chaîner.

    LES DEUX LECTURES QUI NE DOIVENT PAS SE SÉPARER

    Le compteur et la dernière signature de la série se lisent sous LE
    MÊME verrou, que l'appelant a pris avec `select_for_update` sur la
    série. Les séparer ouvre deux failles concrètes : deux documents
    simultanés qui reçoivent le même numéro, et deux documents qui signent
    le même prédécesseur.

    LA FONCTION EST PARTAGÉE, ET C'EST LE POINT

    Les documents de facturation et les reçus se numérotent dans deux
    tables différentes, avec la même discipline. L'écrire deux fois la
    ferait diverger un jour — et ce serait la seule divergence à la fois
    invisible et irréparable : une chaîne rompue ne se répare pas, elle se
    constate au contrôle. `modele` dit seulement dans quelle table lire la
    chaîne ; une série n'appartient jamais qu'à l'une des deux.
    """
    sequentiel = verrouillee.prochain_numero
    numero = verrouillee.numero_du_document(sequentiel)
    valider_numero_saft(numero)

    precedent = (modele.objects.filter(serie=verrouillee)
                 .order_by('-numero_sequentiel')
                 .values_list('signature', flat=True)
                 .first()) or ''

    return sequentiel, numero, precedent


class ParametresFiscauxPT(models.Model):
    """Ce qu'il faut savoir de l'entreprise pour émettre au Portugal.

    POURQUOI UN MODÈLE PLUTÔT QU'UN RÉGLAGE DE FICHIER

    Le numéro de certificat est attribué par l'AT en cours de vie du
    logiciel, et le NIF diffère d'une entreprise à l'autre dans la même
    installation. Les mettre dans `settings.py` demanderait un accès au
    serveur à chaque changement ; ils se saisissent donc à l'écran, comme
    tout le reste.

    `numero_de_certificat` vaut « 0 » tant que l'AT n'a rien attribué.
    C'est la valeur que le SAF-T prévoit pour un logiciel non certifié :
    y inscrire un numéro d'emprunt serait une fausse déclaration, et le
    champ est contrôlé.
    """

    company = models.OneToOneField('core.Company', on_delete=models.CASCADE,
                                   related_name='parametres_fiscaux_pt',
                                   verbose_name='Entreprise')
    est_actif = models.BooleanField(
        'Conformité portugaise active', default=False,
        help_text='Tant que cette case est décochée, rien ne change dans la '
                  'facturation existante.')
    nif = models.CharField(
        'NIF de l’entreprise', max_length=20, blank=True,
        help_text='Neuf chiffres, sans préfixe de pays.')
    numero_de_certificat = models.CharField(
        'N° de certificat AT', max_length=4, default='0',
        help_text='Attribué par l’AT. Laissez « 0 » tant que le logiciel '
                  'n’est pas certifié.')
    region_par_defaut = models.CharField('Région par défaut', max_length=10,
                                         choices=taxas.REGIONS,
                                         default=taxas.CONTINENT)
    #: Le cas de l'article 40.º n.º 1 dont relève l'entreprise, qui fixe
    #: le plafond d'une facture simplifiée. Il dépend de l'ACTIVITÉ et non
    #: du document : un détaillant peut simplifier jusqu'à mille euros,
    #: une entreprise de travaux jusqu'à cent. Le réglage est donc ici,
    #: une fois, et non à choisir sur chaque facture — où il finirait par
    #: être mis au plus large.
    regime_simplifiee = models.CharField(
        'Régime de facture simplifiée', max_length=1,
        choices=tipos.REGIMES_SIMPLIFIEE,
        default=tipos.REGIME_SIMPLIFIEE_PAR_DEFAUT,
        help_text='Fixe le plafond au-delà duquel une facture simplifiée '
                  'n’est plus régulière. Une entreprise de travaux relève '
                  'du cas b).')
    nom_editeur = models.CharField('Éditeur du logiciel', max_length=120,
                                   default='Orion')
    nif_editeur = models.CharField('NIF de l’éditeur', max_length=20,
                                   blank=True)
    version_produit = models.CharField('Version du logiciel', max_length=30,
                                       default='1.0')

    class Meta:
        verbose_name = 'Paramètres fiscaux (PT)'
        verbose_name_plural = 'Paramètres fiscaux (PT)'

    def __str__(self):
        return f'Conformité PT — {self.company}'

    def clean(self):
        if self.numero_de_certificat:
            try:
                assinatura.valider_numero_de_certificat(
                    self.numero_de_certificat)
            except assinatura.ErreurDeSignature as exc:
                raise ValidationError({'numero_de_certificat': str(exc)})
        # Le NIF est valide des qu'il est saisi, actif ou non : une
        # faute laissee dans un champ inactif ressortirait le jour de
        # l'activation, c'est-a-dire le jour ou l'on a le moins envie de
        # chercher.
        if self.nif:
            try:
                self.nif = valider_nif(self.nif)
            except ValidationError as exc:
                raise ValidationError({'nif': exc.messages})
        elif self.est_actif:
            raise ValidationError({
                'nif': 'Le NIF est obligatoire pour émettre un document au '
                       'Portugal : il figure dans le code QR et dans le '
                       'SAF-T.'})

        if self.nif_editeur:
            try:
                self.nif_editeur = valider_nif(self.nif_editeur)
            except ValidationError as exc:
                raise ValidationError({'nif_editeur': exc.messages})

    @classmethod
    def de(cls, company):
        """Les paramètres de l'entreprise, créés au besoin."""
        parametres, _ = cls.objects.get_or_create(company=company)
        return parametres


class CleDeSignature(models.Model):
    """Une paire de clés RSA-1024, et la version qui l'identifie.

    POURQUOI UNE VERSION

    Le Despacho exige que chaque document conserve la version de la clé
    qui l'a signé. Une entreprise qui change de clé — parce que la
    précédente a fuité, par exemple — doit pouvoir continuer à prouver les
    documents signés avec l'ancienne. Sans numéro de version, une
    rotation de clé rendrait invérifiable tout l'historique.

    La clé privée est chiffrée au repos avec la clé Fernet de
    l'installation. Ce n'est pas exigé par le texte, qui est muet là-dessus,
    mais une clé de signature en clair dans une sauvegarde de base
    permettrait de fabriquer des factures au nom de l'entreprise.
    """

    company = models.ForeignKey('core.Company', on_delete=models.CASCADE,
                                related_name='cles_de_signature',
                                verbose_name='Entreprise')
    version = models.PositiveIntegerField('Version', default=1)
    pem_privee_chiffree = models.TextField('Clé privée (chiffrée)', blank=True)
    pem_publique = models.TextField('Clé publique', blank=True)
    est_active = models.BooleanField('Active', default=True)
    cree_le = models.DateTimeField('Créée le', auto_now_add=True)
    commentaire = models.CharField('Commentaire', max_length=300, blank=True)

    class Meta:
        verbose_name = 'Clé de signature (PT)'
        verbose_name_plural = 'Clés de signature (PT)'
        ordering = ['company', '-version']
        constraints = [
            models.UniqueConstraint(fields=['company', 'version'],
                                    name='fiscal_pt_cle_version_unique'),
        ]

    def __str__(self):
        return f'Clé v{self.version} — {self.company}'

    # ── Création ────────────────────────────────────────────────────────

    @classmethod
    def creer(cls, company, commentaire=''):
        """Fabrique une paire de clés conforme et la range chiffrée.

        La version suit la précédente. On désactive les clés antérieures :
        une seule clé signe à un instant donné, sinon deux documents
        voisins porteraient des versions différentes sans raison.
        """
        from apps.website_shop_settings.crypto import encrypt_secret

        privee, publique = assinatura.generer_une_cle()
        chiffree = encrypt_secret(privee)

        # Vérification immédiate : un chiffrement qui échouerait en silence
        # donnerait une clé irrécupérable, et on ne le découvrirait qu'à la
        # première facture.
        if not chiffree:
            raise ValidationError(
                'Le chiffrement de la clé privée a échoué. Vérifiez '
                'ORION_SECRET_ENCRYPTION_KEY avant d’émettre un document.')

        with transaction.atomic():
            derniere = (cls.objects.filter(company=company)
                        .order_by('-version').values_list('version', flat=True)
                        .first())
            cls.objects.filter(company=company, est_active=True).update(
                est_active=False)
            return cls.objects.create(
                company=company,
                version=(derniere or 0) + 1,
                pem_privee_chiffree=chiffree,
                pem_publique=publique,
                est_active=True,
                commentaire=commentaire,
            )

    @classmethod
    def active_de(cls, company):
        """La clé qui signe aujourd'hui, ou une erreur explicite."""
        cle = cls.objects.filter(company=company, est_active=True).first()
        if cle is None:
            raise ValidationError(
                'Aucune clé de signature active pour cette entreprise. '
                'Créez-la depuis Paramètres → Conformité Portugal avant '
                'd’émettre un document.')
        return cle

    # ── Lecture ─────────────────────────────────────────────────────────

    def privee(self):
        """La clé privée en clair, ou une erreur.

        On ne rend JAMAIS une chaîne vide en cas d'échec de déchiffrement :
        `signer()` lèverait alors une erreur de clé illisible, loin de la
        cause réelle, et on chercherait le défaut dans la cryptographie au
        lieu de la configuration.
        """
        from apps.website_shop_settings.crypto import get_fernet

        if not self.pem_privee_chiffree:
            raise ValidationError(
                f'La clé v{self.version} n’a pas de partie privée '
                'enregistrée : elle ne peut pas signer.')
        try:
            return get_fernet().decrypt(
                self.pem_privee_chiffree.encode()).decode()
        except Exception as exc:
            raise ValidationError(
                f'La clé privée v{self.version} est illisible ({exc}). '
                'ORION_SECRET_ENCRYPTION_KEY a-t-elle changé depuis sa '
                'création ? Les documents déjà signés restent valides, '
                'mais aucun nouveau ne peut l’être avec cette clé.')


class SerieFiscale(models.Model):
    """Une série de documents, déclarée à l'AT, et son compteur.

    CE QUE LA SÉRIE PORTE

    Le code de validation rendu par l'AT lors de la communication de la
    série, sans lequel l'ATCUD ne peut pas être composé. On le laisse
    vide tant que la série n'est pas communiquée, et l'ATCUD porte alors
    « 0 » — la marque explicite d'une série non déclarée, prévue par la
    Portaria, plutôt qu'un code fabriqué pour faire bonne figure.
    """

    company = models.ForeignKey('core.Company', on_delete=models.CASCADE,
                                related_name='series_fiscales',
                                verbose_name='Entreprise')
    #: Les documents de facturation ET les reçus. Une série de reçus se
    #: déclare à l'AT, porte son code de validation et son compteur comme
    #: les autres : c'est la même table, et le type dit seulement dans
    #: quelle table du SAF-T les documents iront.
    type_document = models.CharField('Type de document', max_length=2,
                                     choices=tipos.TYPES_DE_SERIE,
                                     default='FT')
    nom = models.CharField('Série', max_length=20, default='A',
                           help_text='Sans espace ni barre oblique. Ex. « A », « 2026 ».')
    code_de_validation = models.CharField(
        'Code de validation AT', max_length=60, blank=True,
        help_text='Rendu par l’AT à la communication de la série. '
                  'Laissez vide si la série n’est pas encore communiquée.')
    prochain_numero = models.PositiveIntegerField('Prochain numéro', default=1)
    cle = models.ForeignKey(CleDeSignature, on_delete=models.PROTECT,
                            related_name='series', null=True, blank=True,
                            verbose_name='Clé de signature')
    region = models.CharField('Région fiscale', max_length=10,
                              choices=taxas.REGIONS, default=taxas.CONTINENT)
    est_active = models.BooleanField('Active', default=True)
    cree_le = models.DateTimeField('Créée le', auto_now_add=True)

    class Meta:
        verbose_name = 'Série fiscale (PT)'
        verbose_name_plural = 'Séries fiscales (PT)'
        ordering = ['company', 'type_document', 'nom']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'type_document', 'nom'],
                name='fiscal_pt_serie_unique'),
        ]

    def __str__(self):
        return f'{self.type_document} {self.nom}'

    def clean(self):
        if ' ' in self.nom or '/' in self.nom:
            raise ValidationError({
                'nom': 'Le nom de série ne peut contenir ni espace ni barre '
                       'oblique : ces deux caractères séparent les parties du '
                       'numéro de document et le SAF-T rejetterait l’export.'})
        if self.code_de_validation:
            try:
                atcud.valider_code_de_validation(self.code_de_validation)
            except atcud.ErreurATCUD as exc:
                raise ValidationError({'code_de_validation': str(exc)})

    @property
    def est_communiquee(self):
        return bool(self.code_de_validation)

    def numero_du_document(self, sequentiel):
        """« FT A/35 » — la forme exigée par le SAF-T."""
        return f'{self.type_document} {self.nom}/{sequentiel}'


class DocumentFiscal(models.Model):
    """Un document émis, signé, et désormais immuable.

    POURQUOI « IMMUABLE » EST ICI UN MOT TECHNIQUE

    Chaque document signe la signature du précédent de sa série. Modifier
    un document ancien ne casse pas seulement sa propre preuve : elle rend
    invérifiables tous ceux qui l'ont suivi. `save()` refuse donc les
    modifications, et ce refus est la garantie elle-même, pas une
    précaution de confort.

    Corriger un document émis se fait par une note de crédit, comme la loi
    le prévoit — jamais par une mise à jour.
    """

    company = models.ForeignKey('core.Company', on_delete=models.PROTECT,
                                related_name='documents_fiscaux',
                                verbose_name='Entreprise')
    serie = models.ForeignKey(SerieFiscale, on_delete=models.PROTECT,
                              related_name='documents', verbose_name='Série')

    numero_sequentiel = models.PositiveIntegerField('Numéro dans la série')
    numero = models.CharField('Numéro du document', max_length=60)

    date_document = models.DateField('Date du document')
    horodatage = models.DateTimeField('Enregistré le')

    nif_acquereur = models.CharField('NIF de l’acquéreur', max_length=30,
                                     blank=True)
    pays_acquereur = models.CharField('Pays', max_length=12, default='PT')
    etat = models.CharField('État', max_length=1, choices=ETATS_DE_DOCUMENT,
                            default='N')

    total_base = models.DecimalField('Total hors taxe', max_digits=14,
                                     decimal_places=2, default=0)
    total_taxes = models.DecimalField('Total des taxes', max_digits=14,
                                      decimal_places=2, default=0)
    total = models.DecimalField('Total du document', max_digits=14,
                                decimal_places=2, default=0)

    message_signe = models.TextField('Chaîne signée')
    signature = models.CharField('Signature', max_length=200)
    signature_precedente = models.CharField('Signature précédente',
                                            max_length=200, blank=True)
    version_cle = models.PositiveIntegerField('Version de la clé')

    atcud = models.CharField('ATCUD', max_length=70)
    contenu_qr = models.TextField('Contenu du code QR')

    #: Le détail des lignes, FIGÉ au moment de l'émission.
    #:
    #: POURQUOI ON LE RECOPIE PLUTÔT QUE DE LE RELIRE
    #:
    #: Le SAF-T exige le détail ligne par ligne. Le lire depuis la facture
    #: d'origine au moment de l'export paraît économe, et ouvre une
    #: divergence silencieuse : modifier la facture changerait le SAF-T
    #: alors que la signature, elle, resterait celle du contenu d'origine.
    #: Le fichier remis à l'administration ne correspondrait plus à la
    #: preuve qui l'accompagne, et rien ne le signalerait.
    lignes = models.JSONField('Lignes figées', default=list, blank=True)

    #: Les encaissements attestés par le document, FIGÉS eux aussi.
    #:
    #: Une facture-reçu vaut quittance : le client peut l'opposer comme
    #: preuve de paiement. Relire l'encaissement depuis la comptabilité au
    #: moment de l'export ouvrirait la même divergence que pour les lignes
    #: — un règlement annulé plus tard ferait disparaître du fichier le
    #: paiement que le document atteste, et que sa signature couvre.
    #:
    #: Chaque entrée porte « mecanisme », « montant » et « date ».
    paiements = models.JSONField('Paiements figés', default=list, blank=True)

    #: Le document que celui-ci rectifie, pour une note de crédit.
    #:
    #: `PROTECT` et non `CASCADE` : supprimer la facture d'origine
    #: laisserait l'avoir orphelin, et le SAF-T exige qu'il la désigne. De
    #: toute façon `delete()` refuse déjà la suppression — la contrainte
    #: est là pour le cas où quelqu'un passerait par la base.
    document_rectifie = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='rectifications', verbose_name='Document rectifié')
    motif_rectification = models.CharField('Motif de la rectification',
                                           max_length=200, blank=True)

    # Le document d'origine dans l'ERP, sans dépendre d'un modèle précis :
    # une facture de vente aujourd'hui, un ticket de caisse demain.
    source_app = models.CharField('Application source', max_length=50,
                                  blank=True)
    source_modele = models.CharField('Modèle source', max_length=50, blank=True)
    source_id = models.PositiveIntegerField('Identifiant source', null=True,
                                            blank=True)

    cree_le = models.DateTimeField('Créé le', auto_now_add=True)

    class Meta:
        verbose_name = 'Document fiscal (PT)'
        verbose_name_plural = 'Documents fiscaux (PT)'
        ordering = ['-date_document', '-numero_sequentiel']
        constraints = [
            models.UniqueConstraint(fields=['company', 'numero'],
                                    name='fiscal_pt_numero_unique'),
            models.UniqueConstraint(fields=['serie', 'numero_sequentiel'],
                                    name='fiscal_pt_sequence_unique'),
        ]
        indexes = [
            models.Index(fields=['company', 'date_document']),
            models.Index(fields=['source_app', 'source_modele', 'source_id']),
        ]

    def __str__(self):
        return self.numero

    # ── L'immuabilité ───────────────────────────────────────────────────

    def save(self, *args, **kwargs):
        """Autorise la création, refuse la modification.

        Le contrôle porte sur l'existence en BASE, pas sur `self.pk` : un
        objet rechargé puis modifié a bien un pk, et c'est exactement le
        cas qu'il faut arrêter.
        """
        if self.pk and DocumentFiscal.objects.filter(pk=self.pk).exists():
            raise ValidationError(
                f'Le document {self.numero} est déjà émis et ne peut plus '
                'être modifié : sa signature couvre son contenu, et tous '
                'les documents suivants de la série signent la sienne. '
                'Émettez une note de crédit pour le corriger.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            f'Le document {self.numero} ne peut pas être supprimé : la '
            'chaîne de signatures de la série serait rompue, et '
            'l’administration le constaterait au premier contrôle.')

    # ── L'émission ──────────────────────────────────────────────────────

    @classmethod
    def emettre(cls, *, serie, date_document, lignes, nif_emetteur,
                nif_acquereur='', pays_acquereur='PT', etat='N',
                source=None, horodatage=None, numero_de_certificat='0',
                document_rectifie=None, motif_rectification='',
                paiements=None,
                regime_simplifiee=tipos.REGIME_SIMPLIFIEE_PAR_DEFAUT):
        """Numérote, signe et enregistre un document — tout ou rien.

        `lignes` est un itérable de dictionnaires. Les clés attendues sont
        celles que `ligne_figee()` produit : description, code_produit,
        quantite, unite, prix_unitaire, base, taux, tva. Les montants sont
        des `Decimal` ; ils sont convertis en texte pour le stockage JSON,
        car un `float` perdrait des centimes sur de gros totaux et la
        signature porte sur le total.

        POURQUOI UNE SEULE TRANSACTION, ET UN SEUL VERROU

        Trois choses doivent s'accorder : le numéro attribué, la signature
        du document précédent, et l'enregistrement. Les séparer ouvre deux
        failles concrètes — deux documents simultanés qui reçoivent le même
        numéro, et deux documents qui signent le même prédécesseur. Le
        verrou porte donc sur la SÉRIE, et il est pris avant la lecture du
        compteur comme de la dernière signature.
        """
        horodatage = horodatage or timezone.now()

        with transaction.atomic():
            # `select_for_update` sur la série : tout le reste en découle.
            verrouillee = (SerieFiscale.objects
                           .select_for_update()
                           .get(pk=serie.pk))

            cle = verrouillee.cle or CleDeSignature.active_de(
                verrouillee.company)

            # L'ISOLEMENT, qui ne se délègue pas.
            #
            # `tipos` ne connaît pas Django : il vérifie les règles du
            # CIVA sur des montants et des chaînes. L'appartenance du
            # document rectifié à la même entreprise, elle, ne se mesure
            # qu'ici — et une facture d'une autre société rectifiée par
            # erreur donnerait un avoir parfaitement signé qui crédite le
            # client de quelqu'un d'autre.
            if document_rectifie is not None:
                if document_rectifie.company_id != verrouillee.company_id:
                    raise ValidationError(
                        'La facture rectifiée appartient à une autre '
                        'entreprise.')

            sequentiel, numero, precedent = _attribuer_le_numero(
                verrouillee, cls)

            figees = [ligne_figee(contenu, verrouillee.region, date_document)
                      for contenu in lignes]
            if not figees:
                raise ValidationError(
                    'Un document sans ligne ne peut pas être émis : le '
                    'SAF-T en exige au moins une, et le fichier entier '
                    'serait rejeté à la remise.')

            bloc = taxas.ventiler(
                ((f['taux'], f['base'], f['tva']) for f in figees),
                verrouillee.region)
            base = sum((bloc.get(f'base_{p}', 0)
                        for p in ('isenta', 'reduzida', 'intermedia',
                                  'normal')), start=0)
            taxes = sum((bloc.get(f'iva_{p}', 0)
                         for p in ('reduzida', 'intermedia', 'normal')),
                        start=0)
            total = base + taxes

            # LES RÈGLES PROPRES AU TYPE, juste avant la signature.
            #
            # Le contrôle est ici et non à l'export : à l'export le
            # document est déjà parti chez le client, immuable, et une
            # facture simplifiée hors plafond ne se reprend plus qu'à
            # coups d'avoir. Les montants sont connus depuis deux lignes :
            # c'est le premier instant où le plafond et la somme
            # encaissée PEUVENT être vérifiés, et le dernier où le refus
            # coûte encore quelque chose d'annulable.
            try:
                avertissements = tipos.verifier(
                    verrouillee.type_document, base, total,
                    document_rectifie=document_rectifie,
                    paiements=paiements,
                    regime=regime_simplifiee,
                    etat=etat,
                )
            except tipos.RegleDeType as exc:
                raise ValidationError(str(exc))

            message = assinatura.composer_le_message(
                date_document, horodatage, numero, total, precedent)
            signature = assinatura.signer(message, cle.privee())

            code_atcud = atcud.composer(
                verrouillee.code_de_validation or atcud.SANS_CODE, sequentiel)

            contenu = qr.composer(
                nif_emetteur=nif_emetteur,
                nif_acquereur=nif_acquereur or None,
                pays_acquereur=pays_acquereur,
                type_document=verrouillee.type_document,
                etat_document=etat,
                date_document=date_document,
                numero_document=numero,
                atcud=code_atcud,
                espaces_fiscaux=[bloc],
                total_impostos=taxes,
                total_documento=total,
                caracteres_hash=assinatura.caracteres_imprimes(signature),
                numero_certificat=numero_de_certificat,
            )

            document = cls(
                company=verrouillee.company,
                serie=verrouillee,
                numero_sequentiel=sequentiel,
                numero=numero,
                date_document=date_document,
                horodatage=horodatage,
                nif_acquereur=nif_acquereur or '',
                pays_acquereur=pays_acquereur,
                etat=etat,
                total_base=base,
                total_taxes=taxes,
                total=total,
                message_signe=message,
                signature=signature,
                signature_precedente=precedent,
                version_cle=cle.version,
                atcud=code_atcud,
                contenu_qr=contenu,
                lignes=[_pour_json(f) for f in figees],
                paiements=[_paiement_pour_json(p) for p in (paiements or [])],
                document_rectifie=document_rectifie,
                motif_rectification=motif_rectification[:200],
            )

            if source is not None:
                document.source_app = source._meta.app_label
                document.source_modele = source._meta.model_name
                document.source_id = source.pk

            document.save()

            # Le compteur n'avance QUE si tout ce qui précède a réussi. Un
            # échec plus haut annule la transaction, et le numéro reste
            # disponible : une série sans trou, sans avoir à les combler.
            verrouillee.prochain_numero = sequentiel + 1
            verrouillee.save(update_fields=['prochain_numero'])

            # Les avertissements voyagent sur l'INSTANCE, pas en base.
            #
            # Ils portent sur la décision prise à l'émission — « ce total
            # dépasse le plafond selon la lettre du texte » — et non sur
            # le document, qui est désormais immuable. Les enregistrer
            # donnerait à relire plus tard un conseil dont le contexte
            # aurait disparu ; les perdre silencieusement priverait
            # l'écran du seul instant où ils servent à quelque chose.
            document.avertissements = avertissements

            return document

    # ── La relecture ────────────────────────────────────────────────────

    def verifier(self):
        """Revérifie la signature avec la clé qui l'a produite.

        Rend True ou False. C'est l'opération que fait l'administration ;
        on doit pouvoir la faire soi-même, et souvent.
        """
        cle = CleDeSignature.objects.filter(
            company=self.company, version=self.version_cle).first()
        if cle is None or not cle.pem_publique:
            return False
        return assinatura.verifier(self.message_signe, self.signature,
                                   cle.pem_publique)

    def mention_legale(self, numero_de_certificat):
        """La ligne à imprimer au pied du document."""
        return assinatura.mention_legale(self.signature, numero_de_certificat)


class RecuFiscal(models.Model):
    """Un reçu émis — la table 4.4 du SAF-T, et non la 4.1.

    POURQUOI UN MODÈLE À PART, ET NON UN TYPE DE PLUS SUR `DocumentFiscal`

    Un reçu n'a pas de lignes de produit. Ses lignes AFFECTENT une somme à
    un document déjà émis : le schéma définit quatre `Line` différents, et
    celui des reçus n'a même pas de `ProductCode`. Loger les deux formes
    dans le même champ JSON donnerait un contenu dont la forme dépend du
    type, et l'export irait chercher une clé absente un jour sur deux.

    Le reçu part d'ailleurs dans une AUTRE table du fichier. Les mélanger
    dans la même requête, c'est accepter qu'un oubli de filtre range un
    reçu parmi les factures — où il serait parfaitement valide au schéma,
    et faux.

    CE QUE LA LOI EXIGE, ET CE QU'ELLE N'EXIGE PAS

    Le Despacho 8632/2014 (1.1) exclut expressément les reçus de
    l'obligation de signature : « devem assinar quaisquer documentos
    emitidos com eficácia externa, COM EXCEÇÃO DOS RECIBOS ». Le schéma
    dit la même chose à sa manière — la table 4.4 n'a ni `Hash` ni
    `HashControl`.

    Le reçu est signé TOUT DE MÊME, et c'est un choix qu'il faut défendre.
    Les spécifications du code QR rendent le champ Q obligatoire — « 4
    carateres do Hash », « preencher de acordo com a Portaria n.º
    363/2010 » — et ne prévoient aucune exception pour les reçus ; elles
    nomment au contraire la table 4.4 à propos du champ I1. Il faut donc
    quatre caractères de signature, et la seule façon honnête d'en avoir
    est d'en produire une. Signer n'est pas interdit : le texte dispense,
    il ne défend pas. La signature ne sort jamais dans le fichier,
    puisque la table ne la porte pas ; elle sert au code QR et à la
    chaîne.

    Le point reste contesté — une réponse de l'AT rapportée sur un forum
    professionnel conseille de remplir le champ par « 0 ». Ce n'est pas
    une source officielle, et « 0 » n'a pas quatre caractères.

    LES DEUX MENTIONS IMPRIMÉES, ET ELLES SONT DEUX

    Le Despacho les sépare : 2.2.3 impose « Emitido por programa
    certificado n.º NNNN/AT » aux documents non signés, « nomeadamente os
    recibos » — et non « Processado por », qui est la mention des
    documents signés (2.2.2). Le point 1.2 ajoute « Este documento não
    serve de fatura » à tout document des tables 4.2, 4.3 et 4.4
    présentable au client. Un reçu porte donc les deux.
    """

    company = models.ForeignKey('core.Company', on_delete=models.PROTECT,
                                related_name='recus_fiscaux',
                                verbose_name='Entreprise')
    serie = models.ForeignKey(SerieFiscale, on_delete=models.PROTECT,
                              related_name='recus', verbose_name='Série')

    numero_sequentiel = models.PositiveIntegerField('Numéro dans la série')
    numero = models.CharField('Numéro du reçu', max_length=60)

    date_document = models.DateField('Date du reçu')
    horodatage = models.DateTimeField('Enregistré le')

    nif_acquereur = models.CharField('NIF de l’acquéreur', max_length=30,
                                     blank=True)
    pays_acquereur = models.CharField('Pays', max_length=12, default='PT')
    etat = models.CharField('État', max_length=1, choices=ETATS_DE_RECU,
                            default='N')

    #: `NetTotal`, `TaxPayable` et `GrossTotal` de la table 4.4.
    #:
    #: Un reçu « RG » n'indique pas de taux : les trois valent donc le
    #: montant reçu, zéro, et le montant reçu. Les porter quand même
    #: plutôt que de les recalculer à l'export garde le fichier d'accord
    #: avec ce que le document a attesté.
    total_base = models.DecimalField('Total hors taxe', max_digits=14,
                                     decimal_places=2, default=0)
    total_taxes = models.DecimalField('Total des taxes', max_digits=14,
                                      decimal_places=2, default=0)
    total = models.DecimalField('Total du reçu', max_digits=14,
                                decimal_places=2, default=0)

    #: Le sens du mouvement : l'argent entre (crédit) ou sort (débit).
    #:
    #: Il est porté par le reçu ET par chaque affectation, parce que les
    #: sommes de contrôle de la table 4.4 se tiennent par ligne tandis que
    #: le document, lui, n'a qu'un total. `tipos` refuse un reçu qui
    #: mêlerait les deux sens, ce qui rend les deux toujours d'accord.
    au_debit = models.BooleanField('Porté au débit', default=False)

    message_signe = models.TextField('Chaîne signée')
    signature = models.CharField('Signature', max_length=200)
    signature_precedente = models.CharField('Signature précédente',
                                            max_length=200, blank=True)
    version_cle = models.PositiveIntegerField('Version de la clé')

    atcud = models.CharField('ATCUD', max_length=70)
    contenu_qr = models.TextField('Contenu du code QR')

    #: Ce que le reçu solde, FIGÉ : numéro du document, sa date, le montant
    #: affecté, le sens, et une description libre.
    #:
    #: Le numéro est recopié en TEXTE et non tenu par une clé étrangère.
    #: Un reçu peut solder un document émis par un autre logiciel, ou
    #: repris d'un bloc manuel — le SAF-T n'attend qu'un numéro dans
    #: « OriginatingON ». Une clé étrangère interdirait ces cas, et un
    #: numéro relu plus tard depuis le document lié pourrait diverger de
    #: ce que le reçu a réellement attesté.
    affectations = models.JSONField('Affectations figées', default=list,
                                    blank=True)

    #: Comment la somme a été reçue : mécanisme, montant, date.
    paiements = models.JSONField('Encaissements figés', default=list,
                                 blank=True)

    source_app = models.CharField('Application source', max_length=50,
                                  blank=True)
    source_modele = models.CharField('Modèle source', max_length=50,
                                     blank=True)
    source_id = models.PositiveIntegerField('Identifiant source', null=True,
                                            blank=True)

    cree_le = models.DateTimeField('Créé le', auto_now_add=True)

    class Meta:
        verbose_name = 'Reçu (PT)'
        verbose_name_plural = 'Reçus (PT)'
        ordering = ['-date_document', '-numero_sequentiel']
        constraints = [
            models.UniqueConstraint(fields=['company', 'numero'],
                                    name='fiscal_pt_recu_numero_unique'),
            models.UniqueConstraint(fields=['serie', 'numero_sequentiel'],
                                    name='fiscal_pt_recu_sequence_unique'),
        ]
        indexes = [
            models.Index(fields=['company', 'date_document']),
            models.Index(fields=['source_app', 'source_modele', 'source_id']),
        ]

    def __str__(self):
        return self.numero

    # ── L'immuabilité ───────────────────────────────────────────────────

    def save(self, *args, **kwargs):
        if self.pk and RecuFiscal.objects.filter(pk=self.pk).exists():
            raise ValidationError(
                f'Le reçu {self.numero} est déjà émis et ne peut plus être '
                'modifié : les reçus suivants de la série chaînent sa '
                'signature. Un encaissement attesté par erreur se reprend '
                'par un reçu de sens inverse, pas par une correction.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            f'Le reçu {self.numero} ne peut pas être supprimé : la série '
            'perdrait un numéro, et l’administration vérifie précisément '
            'qu’aucun ne manque.')

    # ── L'émission ──────────────────────────────────────────────────────

    @classmethod
    def emettre(cls, *, serie, date_document, affectations, nif_emetteur,
                nif_acquereur='', pays_acquereur='PT', etat='N',
                paiements=None, source=None, horodatage=None,
                numero_de_certificat='0'):
        """Numérote, signe et enregistre un reçu — tout ou rien.

        `affectations` est un itérable de dictionnaires portant
        « document » (le numéro du document réglé), « date » (la sienne),
        « montant », et facultativement « type_du_document » — qui décide
        du sens — et « description ».

        LA DESCRIPTION EST CELLE DE CHAQUE AFFECTATION, et non du reçu.
        Le schéma offre les deux ; celle de la ligne dit ce que l'argent
        règle (« acompte de 30 % »), ce qui est l'information utile quand
        un reçu en solde plusieurs. Un champ au niveau du reçu
        dupliquerait la même phrase sans jamais la préciser.

        LE TOTAL N'EST PAS UN PARAMÈTRE, et c'est le même raisonnement que
        pour la facture-reçu : il est la somme des affectations, calculée
        ici. Le recevoir de l'appelant ferait entrer dans une quittance un
        cumul tenu ailleurs, qui dérive d'un centime après la moindre
        correction.
        """
        horodatage = horodatage or timezone.now()

        with transaction.atomic():
            verrouillee = (SerieFiscale.objects
                           .select_for_update()
                           .get(pk=serie.pk))

            cle = verrouillee.cle or CleDeSignature.active_de(
                verrouillee.company)

            try:
                figees, total, au_debit, avertissements = (
                    tipos.verifier_un_recu(
                        verrouillee.type_document, affectations, paiements,
                        etat=etat))
            except tipos.RegleDeType as exc:
                raise ValidationError(str(exc))

            sequentiel, numero, precedent = _attribuer_le_numero(
                verrouillee, cls)

            message = assinatura.composer_le_message(
                date_document, horodatage, numero, total, precedent)
            signature = assinatura.signer(message, cle.privee())

            code_atcud = atcud.composer(
                verrouillee.code_de_validation or atcud.SANS_CODE, sequentiel)

            # L'ESPACE FISCAL D'UN REÇU VAUT « 0 », ET C'EST LA RÈGLE.
            #
            # Spécifications du code QR, champ I1 : « no caso de documento
            # sem indicação da taxa de IVA, que deva constar na tabela
            # 4.2, 4.3 ou 4.4 do SAF-T(PT), preencher com "0" ». La table
            # 4.4 est celle des reçus. Y mettre « PT » comme sur une
            # facture déclarerait un espace fiscal pour un document qui
            # n'indique aucun taux.
            contenu = qr.composer(
                nif_emetteur=nif_emetteur,
                nif_acquereur=nif_acquereur or None,
                pays_acquereur=pays_acquereur,
                type_document=verrouillee.type_document,
                etat_document=etat,
                date_document=date_document,
                numero_document=numero,
                atcud=code_atcud,
                espaces_fiscaux=[{'regiao': '0'}],
                total_impostos=0,
                total_documento=total,
                caracteres_hash=assinatura.caracteres_imprimes(signature),
                numero_certificat=numero_de_certificat,
            )

            recu = cls(
                company=verrouillee.company,
                serie=verrouillee,
                numero_sequentiel=sequentiel,
                numero=numero,
                date_document=date_document,
                horodatage=horodatage,
                nif_acquereur=nif_acquereur or '',
                pays_acquereur=pays_acquereur,
                etat=etat,
                total_base=total,
                total_taxes=Decimal('0'),
                total=total,
                au_debit=au_debit,
                message_signe=message,
                signature=signature,
                signature_precedente=precedent,
                version_cle=cle.version,
                atcud=code_atcud,
                contenu_qr=contenu,
                affectations=[_affectation_pour_json(a) for a in figees],
                paiements=[_paiement_pour_json(p) for p in (paiements or [])],
            )

            if source is not None:
                recu.source_app = source._meta.app_label
                recu.source_modele = source._meta.model_name
                recu.source_id = source.pk

            recu.save()

            verrouillee.prochain_numero = sequentiel + 1
            verrouillee.save(update_fields=['prochain_numero'])

            recu.avertissements = avertissements
            return recu

    # ── La relecture ────────────────────────────────────────────────────

    def verifier(self):
        """Revérifie la signature avec la clé qui l'a produite."""
        cle = CleDeSignature.objects.filter(
            company=self.company, version=self.version_cle).first()
        if cle is None or not cle.pem_publique:
            return False
        return assinatura.verifier(self.message_signe, self.signature,
                                   cle.pem_publique)

    def mentions_legales(self, numero_de_certificat):
        """Les DEUX lignes à imprimer au pied d'un reçu.

        « Emitido por » et non « Processado por » — le Despacho sépare les
        deux mentions, et celle des documents signés ne convient pas à un
        reçu même lorsqu'on l'a signé : c'est la nature du document qui
        décide, pas ce que le logiciel a choisi de faire en plus.
        """
        return [
            assinatura.mention_sans_signature(numero_de_certificat),
            assinatura.MENTION_NON_FATURA,
        ]


# ── Les mouvements de marchandises et les documents de travail ───────────────
#
# DEUX MODÈLES DE PLUS, ET LA MÊME RAISON QUE POUR LE REÇU.
#
# Un mouvement et un document de travail ne sont pas des types de plus sur
# `DocumentFiscal` : ils vont dans d'autres tables du SAF-T, avec d'autres
# éléments, d'autres états et d'autres règles. Les faire tenir dans le même
# modèle obligerait à laisser vides la moitié des colonnes selon le type —
# et c'est ainsi qu'un champ obligatoire finit par manquer sans que rien ne
# le dise.
#
# CE QU'ILS PARTAGENT AVEC LA FACTURE, EN REVANCHE : ils sont SIGNÉS. Le
# schéma leur donne `Hash` et `HashControl`, contrairement au reçu. La
# chaîne, le verrou de série et l'attribution du numéro sont donc les mêmes,
# par `_attribuer_le_numero`.

ETATS_DE_MOUVEMENT = tipos.ETATS_DE_MOUVEMENT
ETATS_DE_TRAVAIL = tipos.ETATS_DE_TRAVAIL


def _lignes_pour_json(lignes):
    """Les lignes, réduites à ce que le SAF-T en demande.

    Un `Decimal` et une `date` ne se sérialisent pas en JSON : on les
    convertit ici, à l'écriture, plutôt que de confier la conversion à
    l'appelant — qui l'oublierait une fois sur deux, et dont l'oubli ne se
    verrait qu'à l'export.
    """
    propres = []
    for ligne in lignes:
        propre = {
            'designation': str(ligne.get('designation') or '').strip(),
            'reference': str(ligne.get('reference') or '').strip(),
            'quantite': str(ligne.get('quantite') or 0),
            'unite': str(ligne.get('unite') or 'UN'),
            'prix_unitaire': str(ligne.get('prix_unitaire') or 0),
            'montant': str(ligne.get('montant') or 0),
        }
        if ligne.get('taux') is not None:
            propre['taux'] = str(ligne['taux'])
            propre['code_de_taux'] = str(ligne.get('code_de_taux') or 'NOR')
        if ligne.get('motif_exoneration'):
            propre['motif_exoneration'] = str(ligne['motif_exoneration'])
            propre['code_exoneration'] = str(ligne.get('code_exoneration')
                                             or '')
        if ligne.get('date_tva'):
            propre['date_tva'] = ligne['date_tva'].isoformat()
        description = ligne.get('description')
        if description:
            propre['description'] = str(description)
        propres.append(propre)
    return propres


def _valider_les_lignes(lignes, contexte):
    """Au moins une ligne, et chacune complète. Rend (liste, total).

    LE SCHÉMA EXIGE `Line+` DANS LES DEUX TABLES. Un document sans ligne
    s'émettrait, se signerait, et ferait échouer l'export du fichier
    ENTIER — sur un document que plus rien ne modifie. C'est le défaut
    qu'`InvoiceLine` avait déjà posé une fois, et il se referme ici avant
    la signature.
    """
    lignes = list(lignes or [])
    if not lignes:
        raise ValidationError(
            f'{contexte} : au moins une ligne est exigée. Le schéma de l’AT '
            'écrit « Line+ », et un document sans ligne ferait refuser le '
            'fichier entier après avoir été signé.')

    total = Decimal('0')
    for rang, ligne in enumerate(lignes, start=1):
        for champ in ('designation', 'quantite', 'prix_unitaire'):
            if ligne.get(champ) in (None, ''):
                raise ValidationError(
                    f'{contexte}, ligne {rang} : « {champ} » est exigé.')
        try:
            quantite = Decimal(str(ligne['quantite']))
            prix = Decimal(str(ligne['prix_unitaire']))
        except (ArithmeticError, TypeError, ValueError):
            raise ValidationError(
                f'{contexte}, ligne {rang} : quantité ou prix illisible.')
        if quantite <= 0:
            raise ValidationError(
                f'{contexte}, ligne {rang} : la quantité doit être '
                'strictement positive. Le Despacho 8632/2014, point 2.2.6, '
                'interdit les valeurs négatives sur un document émis.')
        montant = ligne.get('montant')
        montant = (Decimal(str(montant)) if montant not in (None, '')
                   else (quantite * prix))
        ligne['montant'] = montant
        total += montant
    return lignes, total


class MouvementFiscal(models.Model):
    """Un mouvement de marchandises — la table 4.2 du SAF-T.

    GUIA DE TRANSPORTE, GUIA DE REMESSA ET LES TROIS AUTRES. Le type décide
    de la nature légale du document ; le schéma les compose à l'identique,
    et aucun de ses deux `xs:assert` ne les distingue.

    DEUX CONTRAINTES PROPRES À CETTE TABLE, qu'aucune autre ne porte.

    1. `CustomerID` et `SupplierID` sont dans un `xs:choice` OBLIGATOIRE :
       exactement l'un des deux. Un mouvement vers un client porte le
       client ; une réception depuis un fournisseur porte le fournisseur.
       Les deux, ou aucun, et le fichier est refusé.

    2. `MovementStartTime` est obligatoire. On ne transporte pas sans dire
       quand le transport commence — et la loi portugaise veut ce document
       ÉMIS AVANT le départ, ce qui est une règle d'usage que le logiciel
       ne peut pas vérifier mais que l'écran rappelle.

    COMME LA FACTURE, ET CONTRAIREMENT AU REÇU : il est SIGNÉ. Le schéma
    lui donne `Hash` et `HashControl`.
    """

    company = models.ForeignKey('core.Company', on_delete=models.PROTECT,
                               related_name='mouvements_fiscaux_pt')
    serie = models.ForeignKey(SerieFiscale, on_delete=models.PROTECT,
                              related_name='mouvements')
    numero_sequentiel = models.PositiveIntegerField('Numéro dans la série')
    numero = models.CharField('Numéro légal', max_length=60)

    date_document = models.DateField('Date du document')
    horodatage = models.DateTimeField('Horodatage d’émission')

    type_mouvement = models.CharField('Type de mouvement', max_length=2,
                                      choices=tipos.TYPES_DE_MOUVEMENT)
    etat = models.CharField('État', max_length=1, default='N',
                            choices=ETATS_DE_MOUVEMENT)

    #: L'un des deux, jamais les deux : le schéma les met dans un choix.
    identifiant_client = models.CharField('Client', max_length=30, blank=True)
    identifiant_fournisseur = models.CharField('Fournisseur', max_length=30,
                                               blank=True)

    debut_transport = models.DateTimeField('Début du transport')
    fin_transport = models.DateTimeField('Fin du transport', null=True,
                                         blank=True)
    commentaire = models.CharField('Commentaire', max_length=200, blank=True)

    #: `ShipFrom` et `ShipTo` du schéma : le trajet.
    origine_envoi = models.JSONField('Point de départ', default=dict,
                                     blank=True)
    destination = models.JSONField('Point de livraison', default=dict,
                                   blank=True)

    lignes = models.JSONField('Lignes', default=list)
    total_base = models.DecimalField('Total hors taxes', max_digits=14,
                                     decimal_places=2, default=0)
    total_taxes = models.DecimalField('Total des taxes', max_digits=14,
                                      decimal_places=2, default=0)
    total = models.DecimalField('Total', max_digits=14, decimal_places=2,
                                default=0)

    message_signe = models.TextField('Message signé', blank=True)
    signature = models.TextField('Signature', blank=True)
    signature_precedente = models.TextField('Signature précédente',
                                            blank=True)
    version_cle = models.PositiveSmallIntegerField('Version de la clé',
                                                   default=1)
    atcud = models.CharField('ATCUD', max_length=70, blank=True)
    contenu_qr = models.TextField('Contenu du code QR', blank=True)

    source_app = models.CharField('Application source', max_length=50,
                                  blank=True)
    source_modele = models.CharField('Modèle source', max_length=50,
                                     blank=True)
    source_id = models.PositiveIntegerField('Identifiant source', null=True,
                                            blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Mouvement de marchandises (PT)'
        verbose_name_plural = 'Mouvements de marchandises (PT)'
        ordering = ['-date_document', '-numero_sequentiel']
        constraints = [
            models.UniqueConstraint(
                fields=['serie', 'numero'],
                name='fiscal_pt_mouvement_numero_unique'),
            models.UniqueConstraint(
                fields=['serie', 'numero_sequentiel'],
                name='fiscal_pt_mouvement_sequence_unique'),
        ]

    def __str__(self):
        return self.numero

    def save(self, *args, **kwargs):
        """Refuse toute modification, comme une facture.

        Un document signé ne se corrige pas : la signature porte sur son
        contenu, et le modifier romprait la chaîne de tous les suivants.
        """
        if self.pk is not None:
            raise ValidationError(
                'Un mouvement émis ne se modifie pas : sa signature porte '
                'sur son contenu, et la chaîne de la série en dépend. '
                'Émettez un mouvement de retour, ou annulez celui-ci.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            'Un mouvement émis ne se supprime pas : la série ne doit sauter '
            'aucun numéro. Annulez-le — il reste alors dans le fichier, en '
            'état « A », et ses quantités ne comptent plus.')

    @classmethod
    def emettre(cls, *, serie, date_document, lignes, nif_emetteur,
                debut_transport, identifiant_client='',
                identifiant_fournisseur='', nif_acquereur='',
                pays_acquereur='PT', etat='N', fin_transport=None,
                origine_envoi=None, destination=None, commentaire='',
                source=None, horodatage=None, numero_de_certificat='0'):
        """Numérote, signe et enregistre un mouvement — tout ou rien.

        LE CHOIX CLIENT/FOURNISSEUR EST VÉRIFIÉ ICI, avant la signature.
        Le schéma les met dans un `xs:choice` obligatoire ; notre
        validateur accepte les deux cas, et l'AT refuse. Le contrôle doit
        donc être posé avant que le document ne soit figé.
        """
        from django.core.exceptions import ValidationError as Invalide

        horodatage = horodatage or timezone.now()

        if bool(identifiant_client) == bool(identifiant_fournisseur):
            raise Invalide(
                'Un mouvement désigne un client OU un fournisseur, et '
                'exactement un des deux : le schéma les place dans un choix '
                'obligatoire. '
                + ('Aucun des deux n’est renseigné.'
                   if not identifiant_client
                   else 'Les deux sont renseignés.'))

        # UNE HEURE DE TRANSPORT SANS FUSEAU EST REFUSÉE, et ce n'est pas
        # du zèle. `MovementStartTime` part dans le SAF-T et compte
        # légalement : la loi veut le document émis AVANT le départ. Une
        # heure naïve serait interprétée en silence — Django l'enregistre
        # en avertissant seulement — et l'heure déclarée pourrait se
        # décaler d'une ou deux heures selon le réglage du serveur. Sur un
        # document signé, personne ne le rattrape.
        #
        # C'est le même défaut que les sauvegardes planifiées, dont
        # l'heure était interprétée en UTC alors que l'écran annonçait
        # l'heure locale. Ici, on refuse plutôt que de deviner.
        for nom, valeur in (('debut_transport', debut_transport),
                            ('fin_transport', fin_transport)):
            if valeur is not None and timezone.is_naive(valeur):
                raise Invalide(
                    f'« {nom} » est donné sans fuseau horaire. L’heure de '
                    'transport part dans le SAF-T et compte légalement : '
                    'interprétée au hasard du réglage du serveur, elle se '
                    'décalerait d’une à deux heures sur un document déjà '
                    'signé. Employez `django.utils.timezone`.')

        with transaction.atomic():
            verrouillee = (SerieFiscale.objects
                           .select_for_update()
                           .get(pk=serie.pk))

            cle = verrouillee.cle or CleDeSignature.active_de(
                verrouillee.company)

            try:
                tipos.valider_le_type_de_mouvement(verrouillee.type_document)
                tipos.valider_l_etat(etat, verrouillee.type_document)
            except tipos.RegleDeType as exc:
                raise Invalide(str(exc))

            lignes, total = _valider_les_lignes(
                lignes, f'Mouvement {verrouillee.type_document}')

            sequentiel, numero, precedent = _attribuer_le_numero(
                verrouillee, cls)

            message = assinatura.composer_le_message(
                date_document, horodatage, numero, total, precedent)
            signature = assinatura.signer(message, cle.privee())

            code_atcud = atcud.composer(
                verrouillee.code_de_validation or atcud.SANS_CODE, sequentiel)

            # L'ESPACE FISCAL EST CELUI DU DOCUMENT, ET NON « 0 ».
            #
            # Les spécifications du code QR réservent « I1:0 » au document
            # « sem indicação da taxa de IVA, que deva constar na tabela
            # 4.2, 4.3 ou 4.4 ». La condition est l'ABSENCE de taux, pas
            # l'appartenance à ces tables : un reçu n'indique aucun taux et
            # reçoit « 0 », un mouvement porte un bloc `Tax` par ligne et
            # reçoit donc son espace fiscal. Recopier la règle du reçu
            # ici déclarerait l'inverse de ce que le fichier contient.
            contenu = qr.composer(
                nif_emetteur=nif_emetteur,
                nif_acquereur=nif_acquereur or None,
                pays_acquereur=pays_acquereur,
                type_document=verrouillee.type_document,
                etat_document=etat,
                date_document=date_document,
                numero_document=numero,
                atcud=code_atcud,
                espaces_fiscaux=[{'regiao': pays_acquereur or 'PT',
                                  'base': 0, 'total': 0}],
                total_impostos=0,
                total_documento=total,
                caracteres_hash=assinatura.caracteres_imprimes(signature),
                numero_certificat=numero_de_certificat,
            )

            mouvement = cls(
                company=verrouillee.company,
                serie=verrouillee,
                numero_sequentiel=sequentiel,
                numero=numero,
                date_document=date_document,
                horodatage=horodatage,
                type_mouvement=verrouillee.type_document,
                etat=etat,
                identifiant_client=identifiant_client,
                identifiant_fournisseur=identifiant_fournisseur,
                debut_transport=debut_transport,
                fin_transport=fin_transport,
                commentaire=commentaire,
                origine_envoi=origine_envoi or {},
                destination=destination or {},
                lignes=_lignes_pour_json(lignes),
                total_base=total,
                total_taxes=Decimal('0'),
                total=total,
                message_signe=message,
                signature=signature,
                signature_precedente=precedent,
                version_cle=cle.version,
                atcud=code_atcud,
                contenu_qr=contenu,
                source_app=getattr(source, '_meta', None)
                and source._meta.app_label or '',
                source_modele=getattr(source, '_meta', None)
                and source._meta.model_name or '',
                source_id=getattr(source, 'pk', None),
            )
            mouvement.save()

            verrouillee.prochain_numero = sequentiel + 1
            verrouillee.save(update_fields=['prochain_numero'])

        return mouvement

    def mentions_legales(self, numero_de_certificat):
        """Les deux mentions qu'un mouvement imprimé doit porter.

        Il est SIGNÉ, donc « Processado » et non « Emitido » — Despacho
        8632/2014, point 2.2.2. Et il relève de la table 4.2, donc le
        point 1.2 lui impose « Este documento não serve de fatura ».
        """
        return [assinatura.mention_legale(self.signature,
                                          numero_de_certificat),
                assinatura.MENTION_NON_FATURA]


class DocumentDeTravailFiscal(models.Model):
    """Un document de travail — la table 4.3 du SAF-T.

    DEVIS, FICHE DE CHANTIER, BON DE COMMANDE. Le type décide de la nature
    (`OR` pour un orçamento, `FO` pour une folha de obra, `NE` pour une
    nota de encomenda), et le schéma les compose à l'identique.

    POURQUOI UN DEVIS DOIT Y FIGURER. Un devis remis au client est un
    document à efficacité externe : la Portaria le veut dans la table 4.3,
    et le Despacho 8632/2014 lui impose au point 1.2 la mention « Este
    documento não serve de fatura » — c'est exactement le cas qu'il
    nomme. Sans cette table, un devis imprimé sur papier à en-tête
    ressemble à une facture et n'en est pas une.

    TROIS ÉTATS SEULEMENT : « N », « A », « F ». Ni « S » ni « R », que la
    table des factures accepte. Un devis facturé passe en « F ».

    IL EST SIGNÉ, comme la facture et le mouvement.
    """

    company = models.ForeignKey('core.Company', on_delete=models.PROTECT,
                               related_name='documents_de_travail_pt')
    serie = models.ForeignKey(SerieFiscale, on_delete=models.PROTECT,
                              related_name='documents_de_travail')
    numero_sequentiel = models.PositiveIntegerField('Numéro dans la série')
    numero = models.CharField('Numéro légal', max_length=60)

    date_document = models.DateField('Date du document')
    horodatage = models.DateTimeField('Horodatage d’émission')

    type_travail = models.CharField('Type', max_length=2,
                                    choices=tipos.TYPES_DE_TRAVAIL)
    etat = models.CharField('État', max_length=1, default='N',
                            choices=ETATS_DE_TRAVAIL)

    identifiant_client = models.CharField('Client', max_length=30)
    nif_acquereur = models.CharField('NIF de l’acquéreur', max_length=20,
                                     blank=True)
    pays_acquereur = models.CharField('Pays de l’acquéreur', max_length=12,
                                      default='PT')

    lignes = models.JSONField('Lignes', default=list)
    total_base = models.DecimalField('Total hors taxes', max_digits=14,
                                     decimal_places=2, default=0)
    total_taxes = models.DecimalField('Total des taxes', max_digits=14,
                                      decimal_places=2, default=0)
    total = models.DecimalField('Total', max_digits=14, decimal_places=2,
                                default=0)

    message_signe = models.TextField('Message signé', blank=True)
    signature = models.TextField('Signature', blank=True)
    signature_precedente = models.TextField('Signature précédente',
                                            blank=True)
    version_cle = models.PositiveSmallIntegerField('Version de la clé',
                                                   default=1)
    atcud = models.CharField('ATCUD', max_length=70, blank=True)
    contenu_qr = models.TextField('Contenu du code QR', blank=True)

    source_app = models.CharField('Application source', max_length=50,
                                  blank=True)
    source_modele = models.CharField('Modèle source', max_length=50,
                                     blank=True)
    source_id = models.PositiveIntegerField('Identifiant source', null=True,
                                            blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Document de travail (PT)'
        verbose_name_plural = 'Documents de travail (PT)'
        ordering = ['-date_document', '-numero_sequentiel']
        constraints = [
            models.UniqueConstraint(
                fields=['serie', 'numero'],
                name='fiscal_pt_travail_numero_unique'),
            models.UniqueConstraint(
                fields=['serie', 'numero_sequentiel'],
                name='fiscal_pt_travail_sequence_unique'),
        ]

    def __str__(self):
        return self.numero

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError(
                'Un document de travail émis ne se modifie pas : sa '
                'signature porte sur son contenu, et la chaîne de la série '
                'en dépend. Émettez-en un nouveau.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            'Un document de travail émis ne se supprime pas : la série ne '
            'doit sauter aucun numéro. Annulez-le — il reste alors dans le '
            'fichier, en état « A », et ses montants ne comptent plus.')

    @classmethod
    def emettre(cls, *, serie, date_document, lignes, nif_emetteur,
                identifiant_client, nif_acquereur='', pays_acquereur='PT',
                etat='N', source=None, horodatage=None,
                numero_de_certificat='0'):
        """Numérote, signe et enregistre un document de travail.

        `date_tva` de chaque ligne alimente `TaxPointDate`, que le schéma
        rend OBLIGATOIRE dans cette table et qui n'existe pas dans celle
        des mouvements. À défaut, la date du document est employée : une
        date absente ferait refuser le fichier entier, et la date du
        document est la réponse juste dans la quasi-totalité des cas.
        """
        from django.core.exceptions import ValidationError as Invalide

        horodatage = horodatage or timezone.now()

        with transaction.atomic():
            verrouillee = (SerieFiscale.objects
                           .select_for_update()
                           .get(pk=serie.pk))

            cle = verrouillee.cle or CleDeSignature.active_de(
                verrouillee.company)

            try:
                tipos.valider_le_type_de_travail(verrouillee.type_document)
                tipos.valider_l_etat(etat, verrouillee.type_document)
            except tipos.RegleDeType as exc:
                raise Invalide(str(exc))

            lignes, total = _valider_les_lignes(
                lignes, f'Document de travail {verrouillee.type_document}')

            for ligne in lignes:
                ligne.setdefault('date_tva', date_document)

            sequentiel, numero, precedent = _attribuer_le_numero(
                verrouillee, cls)

            message = assinatura.composer_le_message(
                date_document, horodatage, numero, total, precedent)
            signature = assinatura.signer(message, cle.privee())

            code_atcud = atcud.composer(
                verrouillee.code_de_validation or atcud.SANS_CODE, sequentiel)

            # L'espace fiscal du document, et non « 0 » : ses lignes
            # portent un bloc `Tax`, donc il INDIQUE un taux. Voir la
            # note de `MouvementFiscal.emettre`.
            contenu = qr.composer(
                nif_emetteur=nif_emetteur,
                nif_acquereur=nif_acquereur or None,
                pays_acquereur=pays_acquereur,
                type_document=verrouillee.type_document,
                etat_document=etat,
                date_document=date_document,
                numero_document=numero,
                atcud=code_atcud,
                espaces_fiscaux=[{'regiao': pays_acquereur or 'PT',
                                  'base': 0, 'total': 0}],
                total_impostos=0,
                total_documento=total,
                caracteres_hash=assinatura.caracteres_imprimes(signature),
                numero_certificat=numero_de_certificat,
            )

            document = cls(
                company=verrouillee.company,
                serie=verrouillee,
                numero_sequentiel=sequentiel,
                numero=numero,
                date_document=date_document,
                horodatage=horodatage,
                type_travail=verrouillee.type_document,
                etat=etat,
                identifiant_client=identifiant_client,
                nif_acquereur=nif_acquereur,
                pays_acquereur=pays_acquereur,
                lignes=_lignes_pour_json(lignes),
                total_base=total,
                total_taxes=Decimal('0'),
                total=total,
                message_signe=message,
                signature=signature,
                signature_precedente=precedent,
                version_cle=cle.version,
                atcud=code_atcud,
                contenu_qr=contenu,
                source_app=getattr(source, '_meta', None)
                and source._meta.app_label or '',
                source_modele=getattr(source, '_meta', None)
                and source._meta.model_name or '',
                source_id=getattr(source, 'pk', None),
            )
            document.save()

            verrouillee.prochain_numero = sequentiel + 1
            verrouillee.save(update_fields=['prochain_numero'])

        return document

    def mentions_legales(self, numero_de_certificat):
        """Les deux mentions. Il est signé, donc « Processado ».

        Et le point 1.2 du Despacho lui impose la seconde en nommant la
        table 4.3 : un devis qui ne la porte pas peut être présenté comme
        une facture.
        """
        return [assinatura.mention_legale(self.signature,
                                          numero_de_certificat),
                assinatura.MENTION_NON_FATURA]
