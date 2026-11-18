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

from . import assinatura, atcud, isencao, qr, taxas

#: Le format que le SAF-T (PT) impose au numéro de document.
#:
#: Le schéma XSD de l'AT valide « InvoiceNo » contre « [^ ]+ [^/^ ]+/[0-9]+ » :
#: un type, une espace, une série sans barre oblique, une barre oblique, un
#: numéro. « FT A/1 » passe ; « FAC-2026-0042 » ne passe pas — ni espace, ni
#: barre oblique. Un export entier serait rejeté pour cette seule raison, et
#: le numéro, lui, a l'air parfaitement normal.
MOTIF_NUMERO_SAFT = re.compile(r'^[^ ]+ [^/ ]+/[0-9]+$')

#: Les types de documents de facturation, tels que l'AT les nomme. Ce sont
#: les valeurs du champ D du code QR et de « InvoiceType » du SAF-T.
TYPES_DE_DOCUMENT = (
    ('FT', 'Fatura'),
    ('FS', 'Fatura simplificada'),
    ('FR', 'Fatura-recibo'),
    ('ND', 'Nota de débito'),
    ('NC', 'Nota de crédito'),
)

#: Les types qui RECTIFIENT un autre document. La constante vit dans
#: `saft`, parce que c'est elle qui decide du sens debit/credit dans le
#: fichier ; on l'importe plutot que de la recopier, deux listes jumelles
#: finissant toujours par diverger.
from .saft import TYPES_AU_DEBIT  # noqa: E402

#: Les états possibles d'un document (champ E du code QR).
ETATS_DE_DOCUMENT = (
    ('N', 'Normal'),
    ('A', 'Annulé'),
    ('F', 'Facturé'),
    ('S', 'Autofacturation'),
    ('R', 'Autre'),
)


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
    if code_de_taux == 'ISE':
        try:
            code_exoneration = isencao.valider(
                contenu.get('code_exoneration'), date_document)
        except isencao.MotifInvalide as exc:
            raise ValidationError(
                f'Ligne « {description[:60]} » : {exc}')
        motif_exoneration = isencao.mencao(code_exoneration)

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
        if self.est_actif and not self.nif:
            raise ValidationError({
                'nif': 'Le NIF est obligatoire pour émettre un document au '
                       'Portugal : il figure dans le code QR et dans le '
                       'SAF-T.'})

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
    type_document = models.CharField('Type de document', max_length=2,
                                     choices=TYPES_DE_DOCUMENT, default='FT')
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
                document_rectifie=None, motif_rectification=''):
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

            # Une note de crédit SANS document rectifié est un avoir dans
            # le vide. Le contrôle est ici, à l'émission, parce qu'à
            # l'export l'avoir est déjà parti chez le client.
            if verrouillee.type_document in TYPES_AU_DEBIT:
                if document_rectifie is None:
                    raise ValidationError(
                        'Une note de crédit doit désigner la facture '
                        'qu’elle rectifie : l’administration rapproche les '
                        'deux, et le SAF-T l’exige.')
                if document_rectifie.company_id != verrouillee.company_id:
                    raise ValidationError(
                        'La facture rectifiée appartient à une autre '
                        'entreprise.')
            elif document_rectifie is not None:
                raise ValidationError(
                    f'Un document de type « {verrouillee.type_document} » ne '
                    'rectifie rien. Employez une série de type « NC ».')

            sequentiel = verrouillee.prochain_numero
            numero = verrouillee.numero_du_document(sequentiel)
            valider_numero_saft(numero)

            precedent = (cls.objects.filter(serie=verrouillee)
                         .order_by('-numero_sequentiel')
                         .values_list('signature', flat=True)
                         .first()) or ''

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
