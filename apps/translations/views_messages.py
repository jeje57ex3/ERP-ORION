"""L'écran de traduction des messages, pilotable sans terminal.

Les chaînes inconnues sont notées pendant l'affichage, puis traduites par
lots. Il faut donc un endroit d'où déclencher ces lots, voir ce qui attend,
et relire ce que la machine a produit — sans quoi il resterait une commande
à taper, ce que les règles de ce projet écartent pour toute fonction
d'exploitation.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.system_updates.permissions import super_admin_required
from apps.translations import lot_de_traduction


def _etat_par_langue():
    """Ce qui attend et ce qui est fait, langue par langue.

    Les langues sans aucune ligne sont ÉCARTÉES : afficher sept lignes à
    zéro ferait croire à un réglage à faire, alors qu'il n'y a simplement
    rien à traduire — personne n'a encore visité l'ERP dans ces langues.
    """
    from django.conf import settings

    etat = []
    for code, nom in settings.LANGUAGES:
        if code == (settings.LANGUAGE_CODE or 'fr'):
            continue
        attente, faits = lot_de_traduction.compter(code)
        if attente or faits:
            etat.append({'code': code, 'nom': nom,
                         'attente': attente, 'faits': faits})
    return etat


@login_required
@super_admin_required
def messages_traduits(request):
    """L'état des traductions de messages, et le bouton de lot."""
    return render(request, 'translations/messages_auto.html', {
        'page_title': 'Traduction des messages',
        'etat': _etat_par_langue(),
        'en_attente': lot_de_traduction.chaines_en_attente(limite=40),
        'par_lot': lot_de_traduction.PAR_LOT,
    })


@login_required
@super_admin_required
@require_POST
def traduire_un_lot(request):
    """Lance un lot sur le moteur LOCAL.

    EN POST, parce qu'un GET qui appelle un modèle de langage partirait au
    survol d'un lien, à l'indexation ou au passage d'un antivirus — et
    chaque passage coûterait du temps de calcul.

    LE RÉSULTAT EST RAPPORTÉ TEL QU'IL S'EST PASSÉ, y compris les refus.
    Un lot qui annonce « 25 traduits » alors que le modèle a rendu vingt-
    cinq bavardages serait pire qu'un échec franc : on découvrirait les
    dégâts dans l'interface, un bandeau à la fois.
    """
    langue = (request.POST.get('langue') or '').strip() or None
    rapport = lot_de_traduction.traduire_un_lot(langue=langue)

    if rapport['traduits']:
        messages.success(request, rapport['message'])
    else:
        messages.warning(request, rapport['message'])

    for motif in rapport['motifs']:
        messages.info(request, 'Refusé — %s' % motif)

    return redirect('translations_messages:etat')
