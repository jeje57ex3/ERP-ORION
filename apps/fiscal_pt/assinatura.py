"""apps/fiscal_pt/assinatura.py — La signature des documents, au Portugal.

CE QUE LA LOI EXIGE, ET D'OÙ CELA VIENT

Portaria n.º 363/2010 (article 6) et Despacho n.º 8632/2014. Chaque
document de facturation porte une signature RSA, calculée sur quatre
champs du document ET sur la signature du document précédent de la même
série. Les documents d'une série forment donc une CHAÎNE : modifier ou
supprimer un document brise toutes les signatures suivantes, et c'est
précisément ce que l'administration vérifie.

LES PARAMÈTRES NE SONT PAS NÉGOCIABLES

Le Despacho 8632/2014 les fixe un par un :

    Algorithme ............. RSA
    Taille de clé .......... 1024 bits
    Empreinte .............. SHA-1
    Remplissage ............ PKCS#1 v1.5
    Encodage ............... Base-64
    Longueur du résultat ... 172 caractères, sans saut de ligne

SHA-1 et RSA-1024 sont aujourd'hui considérés comme faibles. Ce n'est pas
un oubli de notre part : ce sont les valeurs imposées par le texte, et une
signature calculée autrement serait refusée à la certification. On les
écrit donc explicitement, avec ce commentaire, pour qu'un relecteur ne
« corrige » pas ce qui est en réalité une obligation légale.

CE QUI EST SIGNÉ

    InvoiceDate;SystemEntryDate;InvoiceNo;GrossTotal;HashPrécédent

Séparateur « ; », sans guillemets, sans saut de ligne. Pour le premier
document d'une série, le dernier champ est VIDE — la chaîne se termine
alors par un « ; ». L'exemple officiel du Despacho :

    2010-05-18;2010-05-18T11:22:19;FAC 001/14;3.12;
"""

import base64
import re
from datetime import date, datetime
from decimal import Decimal

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

#: Taille de clé imposée par le Despacho 8632/2014, point 6.2.
TAILLE_DE_CLE = 1024

#: Longueur de la signature encodée. 1024 bits = 128 octets, dont
#: l'encodage base64 donne exactement 172 caractères. Le texte l'exige
#: explicitement : « deve ser garantido que as assinaturas contêm
#: 172 bytes, sem quaisquer carateres separadores de linhas ».
LONGUEUR_SIGNATURE = 172

#: Les positions des caractères imprimés sur le document (Despacho 2.2.2).
#: Elles sont données en base 1 dans le texte ; on les garde telles quelles
#: pour que la comparaison avec le texte reste immédiate.
POSITIONS_IMPRIMEES = (1, 11, 21, 31)


class ErreurDeSignature(Exception):
    """Ce qui a empêché la signature, dit dans des termes exploitables."""


def generer_une_cle():
    """Crée une paire de clés conforme, et rend ses deux moitiés en PEM.

    L'exposant 65537 est celui d'OpenSSL par défaut, et donc celui de la
    commande donnée en exemple par le Despacho
    (« openssl genrsa -out ChavePrivada.pem 1024 »).
    """
    privee = rsa.generate_private_key(public_exponent=65537,
                                      key_size=TAILLE_DE_CLE)

    pem_privee = privee.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode('ascii')

    pem_publique = privee.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode('ascii')

    return pem_privee, pem_publique


def _montant(valeur):
    """Un montant au format exigé : point décimal, deux décimales.

    Le Despacho ne laisse pas le choix du format, et une virgule décimale
    produirait une signature que l'administration ne pourrait pas
    revérifier — l'erreur ne se verrait qu'au contrôle, des mois plus tard.
    """
    if valeur is None:
        raise ErreurDeSignature('Le total du document est absent.')
    return f'{Decimal(str(valeur)):.2f}'


def _date(valeur):
    """La date du document, au format AAAA-MM-JJ."""
    if isinstance(valeur, datetime):
        valeur = valeur.date()
    if isinstance(valeur, date):
        return valeur.isoformat()
    return str(valeur)[:10]


def _horodatage(valeur):
    """L'instant d'enregistrement, au format AAAA-MM-JJTHH:MM:SS.

    Sans fuseau et sans fraction de seconde : l'exemple officiel écrit
    « 2010-05-18T11:22:19 », et un suffixe « +00:00 » changerait la chaîne
    signée.
    """
    if isinstance(valeur, datetime):
        return valeur.replace(microsecond=0, tzinfo=None).isoformat()
    return str(valeur)[:19]


def composer_le_message(date_document, horodatage, numero, total,
                        hash_precedent=''):
    """La chaîne exacte à signer.

    Elle est construite ici et nulle part ailleurs : c'est la pièce que
    l'administration recalcule pour vérifier une facture, et deux endroits
    qui la composeraient finiraient par diverger.
    """
    # On contrôle les valeurs BRUTES, avant toute normalisation.
    #
    # L'ordre compte, et c'est subtil : un `.strip()` appliqué d'abord
    # effacerait le saut de ligne que l'on cherche, et le contrôle ne
    # verrait plus rien. On signerait alors « FT 1/1 » pendant que la base
    # et le SAF-T conserveraient « FT 1/1\n ». L'administration recalcule
    # la signature à partir de la valeur EXPORTÉE : elle ne retomberait
    # pas sur la nôtre, et l'écart n'apparaîtrait qu'au contrôle, sur des
    # mois de facturation déjà remise aux clients.
    for valeur, nom in ((numero, 'numéro du document'),
                        (hash_precedent, 'signature précédente')):
        texte = '' if valeur is None else str(valeur)
        if '\n' in texte or '\r' in texte:
            raise ErreurDeSignature(
                f'Le {nom} contient un saut de ligne, ce que le Despacho '
                '8632/2014 interdit explicitement. Corrigez la valeur '
                'enregistrée : la supprimer ici signerait un document '
                'différent de celui qui sera exporté en SAF-T.')

    champs = [
        _date(date_document),
        _horodatage(horodatage),
        str(numero).strip(),
        _montant(total),
        (hash_precedent or '').strip(),
    ]

    # Les quatre premiers champs sont obligatoires ; le cinquième est vide
    # pour le premier document d'une série, et c'est normal.
    for champ, nom in zip(champs, ('date du document', 'horodatage',
                                   'numéro du document', 'total')):
        if not champ:
            raise ErreurDeSignature(
                f'Le champ « {nom} » de la signature est vide.')

    return ';'.join(champs)


def signer(message, pem_cle_privee):
    """Signe le message et rend les 172 caractères de base 64.

    PKCS#1 v1.5 et SHA-1 sont imposés par le Despacho 8632/2014 — voir
    l'en-tête de ce module avant de vouloir les moderniser.
    """
    try:
        cle = serialization.load_pem_private_key(
            pem_cle_privee.encode('ascii') if isinstance(pem_cle_privee, str)
            else pem_cle_privee,
            password=None,
        )
    except Exception as exc:
        raise ErreurDeSignature(f'Clé privée illisible : {exc}')

    if cle.key_size != TAILLE_DE_CLE:
        raise ErreurDeSignature(
            f'La clé fait {cle.key_size} bits ; le Despacho 8632/2014 en '
            f'exige {TAILLE_DE_CLE}. Une signature plus solide serait '
            'refusée à la certification.')

    binaire = cle.sign(message.encode('utf-8'),
                       padding.PKCS1v15(),
                       hashes.SHA1())

    signature = base64.b64encode(binaire).decode('ascii')

    # On VÉRIFIE la longueur plutôt que de la supposer : une clé mal
    # dimensionnée produirait une signature que l'AT rejetterait, et rien
    # d'autre ne le signalerait avant le contrôle.
    if len(signature) != LONGUEUR_SIGNATURE:
        raise ErreurDeSignature(
            f'La signature fait {len(signature)} caractères au lieu de '
            f'{LONGUEUR_SIGNATURE}.')

    return signature


def verifier(message, signature, pem_cle_publique):
    """Revérifie une signature. Rend True ou False, jamais d'exception.

    C'est ce que fait l'administration lors d'un contrôle, et c'est donc
    ce qu'on doit pouvoir faire soi-même : une chaîne cassée se découvre
    bien mieux chez soi que devant un inspecteur.
    """
    try:
        cle = serialization.load_pem_public_key(
            pem_cle_publique.encode('ascii')
            if isinstance(pem_cle_publique, str) else pem_cle_publique)
        cle.verify(base64.b64decode(signature),
                   message.encode('utf-8'),
                   padding.PKCS1v15(),
                   hashes.SHA1())
        return True
    except Exception:
        return False


def caracteres_imprimes(signature):
    """Les quatre caractères à imprimer sur le document.

    Positions 1, 11, 21 et 31 de la signature (Despacho 2.2.2). Le texte
    les numérote à partir de 1 ; la conversion se fait ici, une seule fois.
    """
    if len(signature) < max(POSITIONS_IMPRIMEES):
        raise ErreurDeSignature('Signature trop courte pour être imprimée.')
    return ''.join(signature[position - 1] for position in POSITIONS_IMPRIMEES)


def mention_legale(signature, numero_de_certificat):
    """La mention obligatoire au pied du document.

    Exemple donné par le Despacho :
        « AxAx-Processado por programa certificado n.º 0000/AT »
    """
    return (f'{caracteres_imprimes(signature)}-Processado por programa '
            f'certificado n.º {numero_de_certificat}/AT')


def mention_sans_signature(numero_de_certificat):
    """La mention des documents NON signés — les reçus, notamment.

    Le Despacho (2.2.3) les traite à part : ils ne portent pas de
    signature, mais doivent tout de même annoncer le programme certifié.
    Les omettre est un manquement aussi réel que de les mal signer.
    """
    return ('Processado por programa certificado n.º '
            f'{numero_de_certificat}/AT')


def valider_numero_de_certificat(valeur):
    """Le numéro attribué par l'AT : quatre chiffres au plus.

    On le valide à la saisie plutôt qu'à l'impression : un numéro fautif
    découvert sur une facture déjà remise au client ne se rattrape pas.
    """
    texte = str(valeur or '').strip()
    if not re.fullmatch(r'\d{1,4}', texte):
        raise ErreurDeSignature(
            f'Numéro de certificat invalide : « {texte} ». L’AT attribue '
            'un nombre d’au plus quatre chiffres.')
    return texte
