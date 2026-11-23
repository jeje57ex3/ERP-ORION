"""Traduire par lots les messages inconnus, avec le modèle LOCAL.

**POURQUOI PAR LOTS ET NON À L'AFFICHAGE.** Un modèle qui met une seconde
par chaîne ferait attendre cinq secondes une page qui porte cinq bandeaux.
On aurait désactivé la traduction dans la semaine. `messages_auto.traduire`
ne lit donc que le catalogue et le cache — tous deux instantanés — et NOTE
les chaînes qu'il ne connaît pas. Ce module les reprend plus tard.

**LE MOTEUR EST LOCAL, EN DUR, ET CE N'EST PAS UN RÉGLAGE.** Un message
flash porte très souvent un nom de client, un numéro de facture ou un nom de
fichier : « Utilisateur "Durand" créé. », « Facture FAC-2026-0184
envoyée. ». Les faire sortir de l'installation pour un confort d'affichage
serait un mauvais échange.

`get_ai_provider` sait déjà refuser un fournisseur externe quand le verrou
local est posé, mais ce verrou est un RÉGLAGE — et un réglage se change par
inadvertance. On passe donc `local_only=True` explicitement à chaque appel :
même si quelqu'un lève le verrou global pour l'assistant, la traduction des
messages reste locale.

**CE QUE LE MODÈLE REND EST VÉRIFIÉ.** Un modèle local bavarde : il ajoute
« Voici la traduction : », explique son choix, ou rend trois variantes. Une
réponse non conforme est REFUSÉE et la chaîne reste en attente — mieux vaut
un bandeau français qu'un bandeau portant « Sure! Here's the translation ».
"""

import logging

from django.conf import settings

journal = logging.getLogger('orion')

#: Par clic. Au-delà, la requête HTTP de l'écran risque d'expirer avant la
#: fin du lot, et l'exploitant ne saurait pas ce qui a été fait.
PAR_LOT = 25

#: Un message traduit plus de trois fois plus long que sa source est une
#: explication, pas une traduction.
FACTEUR_DE_LONGUEUR = 3

NOMS_DES_LANGUES = dict(settings.LANGUAGES)

CONSIGNE = (
    'Tu traduis des messages d’interface d’un logiciel de gestion, du '
    'français vers %(langue)s.\n'
    'Règles absolues :\n'
    '- Rends UNIQUEMENT la traduction, sans guillemets, sans commentaire, '
    'sans préfixe.\n'
    '- Garde la ponctuation finale et la casse initiale.\n'
    '- Ne traduis PAS ce qui est entre guillemets, ni les codes, '
    'références, noms propres et nombres : recopie-les à l’identique.\n'
    '- Reste aussi court que la source : c’est un bandeau, pas une phrase '
    'd’explication.'
)


def chaines_en_attente(langue=None, limite=None):
    """Les lignes notées sans traduction, les plus anciennes d'abord.

    Les plus anciennes d'abord parce qu'elles ont été vues en premier,
    donc probablement plus souvent.
    """
    from apps.translations.models import InterfaceTranslation

    qs = InterfaceTranslation.objects.filter(
        module='messages', translated_text='', company=None,
    ).select_related('language').order_by('created_at')
    if langue:
        qs = qs.filter(language__code=langue)
    if limite:
        qs = qs[:limite]
    return qs


def compter(langue=None):
    """(en attente, traduits) pour cette langue, ou toutes."""
    from apps.translations.models import InterfaceTranslation

    qs = InterfaceTranslation.objects.filter(module='messages', company=None)
    if langue:
        qs = qs.filter(language__code=langue)
    total = qs.count()
    attente = qs.filter(translated_text='').count()
    return attente, total - attente


def _reponse_acceptable(source, proposition):
    """La proposition du modèle est-elle une traduction, ou un bavardage ?

    Rend (acceptée, motif). Le motif sert au journal : refuser en silence
    laisserait croire que le modèle ne répond pas, alors qu'il répond mal.
    """
    if not proposition:
        return False, 'réponse vide'
    nu = proposition.strip().strip('"').strip('«»').strip()
    if not nu:
        return False, 'réponse vide après nettoyage'
    if '\n' in nu:
        return False, 'réponse sur plusieurs lignes'
    if len(nu) > max(40, len(source) * FACTEUR_DE_LONGUEUR):
        return False, 'réponse %d fois plus longue que la source' % (
            len(nu) // max(len(source), 1))
    if nu == source:
        return False, 'identique à la source'
    return True, nu


def traduire_une_chaine(source, langue, fournisseur=None, modele=None):
    """Demande une traduction au modèle local. Rend (texte, motif d'échec).

    Les erreurs sont RENDUES et non levées : ce lot tourne sur des dizaines
    de chaînes, et une seule qui échoue ne doit pas annuler les autres.
    """
    from apps.orion_ai.providers import AIProviderError, get_ai_provider

    nom_langue = NOMS_DES_LANGUES.get(langue, langue)
    try:
        # `local_only=True` EN DUR : voir la docstring du module.
        fournisseur = fournisseur or get_ai_provider('local', local_only=True)
    except AIProviderError as exc:
        return None, str(exc)

    modele = modele or getattr(settings, 'LOCAL_AI_MODEL', 'qwen2.5:7b')

    try:
        reponse = fournisseur.generate(
            messages=[
                {'role': 'system', 'content': CONSIGNE % {'langue': nom_langue}},
                {'role': 'user', 'content': source},
            ],
            model=modele,
            temperature=0.0,          # une traduction n'a pas à varier
            max_output_tokens=120,    # un bandeau : au-dela, c'est du bavardage
            keep_alive_minutes=10,    # le lot enchaine : inutile de recharger
        )
    except Exception as exc:
        return None, '%s: %s' % (type(exc).__name__, exc)

    proposition = ''
    if isinstance(reponse, dict):
        proposition = (reponse.get('content') or reponse.get('text') or '')
    elif isinstance(reponse, str):
        proposition = reponse

    accepte, resultat = _reponse_acceptable(source, proposition)
    if not accepte:
        return None, resultat
    return resultat, ''


def traduire_un_lot(langue=None, limite=None):
    """Traduit les chaînes en attente. Rend un compte rendu lisible.

    LE FOURNISSEUR EST CONSTRUIT UNE FOIS pour tout le lot : le reconstruire
    par chaîne rouvrirait une connexion à chaque fois, et `keep_alive` ne
    servirait à rien.
    """
    from apps.orion_ai.providers import AIProviderError, get_ai_provider

    limite = limite or PAR_LOT
    lignes = list(chaines_en_attente(langue, limite))
    if not lignes:
        return {'traduits': 0, 'echecs': 0, 'restants': 0, 'motifs': [],
                'message': 'Aucun message en attente.'}

    try:
        fournisseur = get_ai_provider('local', local_only=True)
    except AIProviderError as exc:
        return {'traduits': 0, 'echecs': len(lignes),
                'restants': compter(langue)[0], 'motifs': [str(exc)],
                'message': 'Le moteur local n’est pas disponible.'}

    traduits, motifs = 0, []
    for ligne in lignes:
        texte, motif = traduire_une_chaine(
            ligne.source_text, ligne.language.code, fournisseur=fournisseur)
        if texte:
            ligne.translated_text = texte
            # `is_verified` reste FAUX : c'est une machine qui a traduit, et
            # l'exploitant doit pouvoir distinguer ce qu'il a relu de ce
            # qu'il n'a pas relu.
            ligne.is_verified = False
            ligne.save(update_fields=['translated_text', 'is_verified',
                                      'updated_at'])
            traduits += 1
        else:
            motifs.append('« %s » : %s' % (ligne.source_text[:50], motif))
            journal.info('Traduction refusee (%s) : %s',
                         ligne.language.code, motif)

    attente, _faits = compter(langue)
    return {
        'traduits': traduits,
        'echecs': len(lignes) - traduits,
        'restants': attente,
        'motifs': motifs[:5],
        'message': '%d message(s) traduit(s), %d refusé(s), %d en attente.'
                   % (traduits, len(lignes) - traduits, attente),
    }
