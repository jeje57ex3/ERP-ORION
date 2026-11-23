"""La traduction des messages flash, selon la langue de l'interface.

**LE DÉFAUT MESURÉ (23/11/2026).** Les gabarits de l'ERP portent leurs
`{% trans %}` et se traduisent. Les **messages flash**, non : sur 721
appels à `messages.success/error/warning/info`, **5** passaient par
`gettext`. Un utilisateur qui met l'ERP en portugais obtient donc des pages
portugaises et, par-dessus, des bandeaux français — « Accès refusé. »,
« Enregistré. », « Devis supprimé. » Rien ne le signale : un message
s'affiche toujours, simplement pas dans la bonne langue.

Détail de la mesure : 327 appels portent une chaîne littérale (271
distinctes, 10 073 caractères), 315 sont des f-strings qui insèrent une
valeur, 79 passent une variable. **Zéro** des 271 littéraux ne figurait
dans un catalogue.

**POURQUOI PAS SIMPLEMENT ENVELOPPER LES 271 LITTÉRAUX.** Il le faudrait,
et c'est fait pour les plus courants. Mais cela laisse dehors les 315
f-strings : `f'Utilisateur "{nom}" créé.'` n'est pas un littéral, et la
rendre traduisible demande de réécrire chaque appel une par une. Un écran
où un message sur deux reste français se voit, et se voit mal.

D'où un **point de passage unique**, et trois sources dans cet ordre :

1. **Le catalogue gettext.** Instantané, hors ligne, versionné, relisible.
   C'est la bonne place pour une chaîne stable.
2. **Le cache `InterfaceTranslation`.** La table existait déjà pour les
   traductions d'interface par entreprise : on s'en sert plutôt que d'en
   créer une seconde.
3. **Rien.** Le texte français est rendu tel quel.

**LE MOTEUR N'EST JAMAIS APPELÉ PENDANT UN RENDU**, et c'est délibéré. Un
modèle qui met deux secondes par chaîne ferait attendre dix secondes une
page qui porte cinq messages — on désactiverait la traduction dans la
semaine. Les chaînes inconnues sont simplement **notées**, et traduites
plus tard par lots, depuis l'interface.

**LE MOTEUR EST LOCAL, ET SEULEMENT LOCAL.** Un message porte très souvent
un nom de client, un numéro de facture ou un nom de fichier —
`f'Utilisateur "{username}" créé.'`. Les envoyer à un service tiers serait
faire sortir des données clients de l'installation pour un confort
d'affichage. `apps.orion_ai` distingue déjà ses fournisseurs locaux de ses
fournisseurs externes ; on n'emploie que les premiers.
"""

import hashlib
import logging

from django.conf import settings
from django.utils import translation

journal = logging.getLogger('orion')

#: Préfixe des clés de cache, pour ne pas se mêler aux clés d'interface
#: nommées à la main (« sales.invoices » et les siennes).
PREFIXE = 'msg:'

#: Au-delà, on ne traduit pas : ce n'est plus un message mais un texte, et
#: il vient probablement d'une exception ou d'une sortie de commande.
LONGUEUR_MAXIMALE = 400


def _empreinte(texte):
    """Une clé stable et courte pour ce texte.

    `InterfaceTranslation.key` fait 200 caractères et certains messages sont
    plus longs ; et la clé sert d'index. On hache donc, en gardant le texte
    source complet dans `source_text` — sans quoi la table serait
    illisible, et personne ne pourrait relire une traduction.
    """
    condense = hashlib.sha256(texte.encode('utf-8')).hexdigest()[:32]
    return '%s%s' % (PREFIXE, condense)


def _langue_courante(langue=None):
    return (langue or translation.get_language()
            or settings.LANGUAGE_CODE or 'fr')


def traduisible(texte):
    """Ce texte mérite-t-il d'être traduit ?

    Écarte ce qui n'apporterait rien et encombrerait le cache : le vide, ce
    qui n'a aucune lettre (un nombre, un identifiant), et ce qui est trop
    long pour être un message.
    """
    if not texte or not isinstance(texte, str):
        return False
    nu = texte.strip()
    if not nu or len(nu) > LONGUEUR_MAXIMALE:
        return False
    return any(caractere.isalpha() for caractere in nu)


def _du_catalogue(texte):
    """La traduction du catalogue gettext, ou None.

    `gettext` rend la SOURCE quand la chaîne manque : comparer les deux est
    la seule façon de distinguer « traduit à l'identique » de « absent ».
    Les deux donnant le même affichage, on préfère rendre None et laisser le
    cache tenter sa chance.
    """
    traduit = translation.gettext(texte)
    return traduit if traduit != texte else None


def _du_cache(texte, langue):
    """La traduction enregistrée, ou None. N'échoue jamais.

    Appelée pendant l'affichage d'un bandeau : une table absente avant
    migration, ou une base momentanément injoignable, ne doit pas faire
    tomber la page qui voulait dire « Enregistré. »
    """
    try:
        from apps.translations.models import InterfaceTranslation

        ligne = InterfaceTranslation.objects.filter(
            key=_empreinte(texte), language__code=langue, company=None,
        ).only('translated_text').first()
    except Exception:
        return None
    if ligne and ligne.translated_text.strip():
        return ligne.translated_text
    return None


def noter_a_traduire(texte, langue):
    """Enregistre une chaîne inconnue, sans traduction, pour un lot futur.

    **UNE LIGNE VIDE EST UN SIGNAL, pas un déchet.** C'est elle qui
    permettra à l'écran des traductions de dire « 42 messages attendent »,
    et au lot de savoir quoi demander au modèle. Sans elle, il faudrait
    deviner la liste — ou parcourir le code, ce qui ne verrait pas les
    f-strings.

    `get_or_create` et non `create` : le même message passe cent fois par
    jour.
    """
    try:
        from apps.translations.models import InterfaceTranslation, Language

        objet_langue = Language.objects.filter(code=langue).first()
        if objet_langue is None:
            return
        InterfaceTranslation.objects.get_or_create(
            key=_empreinte(texte), language=objet_langue, company=None,
            defaults={'source_text': texte, 'translated_text': '',
                      'module': 'messages', 'is_verified': False},
        )
    except Exception:
        # Noter est un confort : jamais une raison de faire tomber une page.
        pass


def traduire(texte, langue=None, noter=True):
    """Le message dans la langue de l'interface, ou le français tel quel.

    JAMAIS D'EXCEPTION, JAMAIS D'ATTENTE. Cette fonction est appelée pour
    chaque bandeau de chaque page : elle ne lit que le catalogue (en
    mémoire) et une ligne indexée. Le moteur de traduction, lui, tourne par
    lots — voir `apps.translations.lot_de_traduction`.
    """
    langue = _langue_courante(langue)

    # La langue source n'a rien à traduire, et c'est la majorité du trafic.
    if langue == (settings.LANGUAGE_CODE or 'fr'):
        return texte
    if not traduisible(texte):
        return texte

    du_catalogue = _du_catalogue(texte)
    if du_catalogue is not None:
        return du_catalogue

    du_cache = _du_cache(texte, langue)
    if du_cache is not None:
        return du_cache

    if noter:
        # LA GARANTIE EST ICI, et pas seulement dans `noter_a_traduire`.
        #
        # Cette fonction promet de ne jamais lever, et un test l'a prise au
        # mot : elle s'en remettait à ses auxiliaires pour tenir cette
        # promesse. Or une promesse doit être tenue là où elle est faite —
        # `noter_a_traduire` peut être remplacée, décorée, ou se mettre à
        # lever pour une raison que son propre `except` ne couvre pas, et
        # c'est alors l'affichage de la page qui tombe.
        try:
            noter_a_traduire(texte, langue)
        except Exception:
            pass
    return texte
