"""
apps/core/nombres.py — Lire un nombre écrit par un humain

Déplacée ici depuis `apps.btp.catalogue_import`, où elle s'appelait
`_nombre`. Elle sert désormais à deux choses sans rapport — les tarifs
fournisseurs et l'extraction des factures PDF — et une deuxième copie
aurait divergé à la première correction : l'une lirait « 1.234,56 » et
l'autre « 1,23456 », sur des montants qui partent en comptabilité.

`catalogue_import` garde l'alias `_nombre`, pour que ses appels et ses
tests continuent de fonctionner sans être réécrits.
"""

from decimal import Decimal, InvalidOperation


def nombre_francais(valeur):
    """Un montant, quelle que soit la façon dont il est écrit.

    « 1 234,56 », « 1.234,56 », « 1234.56 », « 12,50 € » : tous lus.

    **None quand c'est illisible, jamais zéro.** Un prix illisible devenu
    zéro est un prix : un devis le facturerait, une facture le
    rapprocherait. L'absence doit rester visible comme une absence.
    """
    if valeur is None or valeur == '':
        return None
    if isinstance(valeur, (int, float, Decimal)):
        return Decimal(str(valeur))

    texte = str(valeur)
    garde = ''.join(c for c in texte if c.isdigit() or c in ',.-')
    if not garde or garde in ('-', '.', ','):
        return None

    # Le dernier separateur rencontre est le separateur DECIMAL ; tous les
    # autres sont des separateurs de milliers. C'est ce qui permet de lire
    # « 1.234,56 » et « 1,234.56 » sans se tromper.
    dernier_point = garde.rfind('.')
    derniere_virgule = garde.rfind(',')
    if dernier_point > derniere_virgule:
        garde = garde.replace(',', '')
    elif derniere_virgule > dernier_point:
        garde = garde.replace('.', '').replace(',', '.')

    try:
        return Decimal(garde)
    except InvalidOperation:
        return None
