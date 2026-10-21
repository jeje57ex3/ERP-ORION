"""Détecter des articles dans un PDF ou sur une page, puis les choisir.

Deux étapes, et la séparation est le cœur du dispositif : **la première
PROPOSE, la seconde n'enregistre que ce qui a été coché.** Une extraction
qui se trompe se voit dans le tableau, et on ne coche rien. C'est ce qui
rend l'exercice acceptable là où une synchronisation automatique depuis des
pages web installerait des erreurs que personne ne surveille.

Les candidats voyagent entre les deux étapes par des champs cachés, et non
en relançant la détection. Relancer coûterait un second téléchargement, et
surtout la page pourrait avoir changé entre-temps : ce qui est enregistré
ne serait plus ce qui a été relu et coché.

Ces champs cachés viennent donc du navigateur, donc de l'utilisateur. Ils
sont revalidés et tronqués côté serveur à l'enregistrement — pas parce
qu'on se méfie de l'exploitant, mais parce qu'un champ de formulaire n'est
jamais une source de confiance, et que la longueur des colonnes de la base
ne se négocie pas.
"""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .catalogue_detection import CANDIDATS_MAX, detecter_dans_pdf, \
    detecter_depuis_url
from .catalogue_import import CatalogueError
from .forms_catalogue import DetectionForm
from .models import Material


@login_required
def catalogue_detection(request):
    company = request.current_company
    form = DetectionForm(request.POST or None, request.FILES or None)
    candidats = []
    compte_rendu = ''

    if request.method == 'POST' and form.is_valid():
        try:
            if form.cleaned_data.get('fichier'):
                fichier = form.cleaned_data['fichier']
                candidats, compte_rendu = detecter_dans_pdf(fichier.read())
            else:
                candidats, compte_rendu = detecter_depuis_url(
                    form.cleaned_data['url'])
        except CatalogueError as exc:
            messages.error(request, f'Détection impossible : {exc}')
            compte_rendu = ''

        if candidats:
            # Ce qui est DEJA au catalogue est signale plutot que masque :
            # retrouver un article absent de la liste sans savoir pourquoi
            # fait douter de la detection elle-meme.
            deja = _references_connues(company, candidats)
            for candidat in candidats:
                candidat['deja'] = _est_connu(candidat, deja)

    return render(request, 'btp/catalogue_detection.html', {
        'page_title': 'Détecter des matériaux et fournitures',
        'form': form,
        'candidats': candidats,
        'compte_rendu': compte_rendu,
        'natures': Material.KIND_CHOICES,
        'active_subnav': 'catalogues',
    })


def _references_connues(company, candidats):
    """Les références et noms déjà présents, en une seule requête.

    Une requête par candidat ferait cinq cents requêtes sur un tarif de
    cinq cents lignes.
    """
    references = {(c.get('reference') or '').lower()
                  for c in candidats if c.get('reference')}
    noms = {(c.get('nom') or '').lower() for c in candidats}

    connus = {'references': set(), 'noms': set()}
    for reference, nom in Material.objects.filter(
            company=company).values_list('reference', 'name'):
        if reference and reference.lower() in references:
            connus['references'].add(reference.lower())
        if nom and nom.lower() in noms:
            connus['noms'].add(nom.lower())
    return connus


def _est_connu(candidat, connus):
    reference = (candidat.get('reference') or '').lower()
    if reference:
        return reference in connus['references']
    return (candidat.get('nom') or '').lower() in connus['noms']


@login_required
@require_POST
def catalogue_detection_import(request):
    """Enregistre les candidats cochés, et eux seuls."""
    company = request.current_company

    nature = request.POST.get('nature')
    natures_connues = {valeur for valeur, _ in Material.KIND_CHOICES}
    if nature not in natures_connues:
        messages.error(request, 'Nature inconnue.')
        return redirect('btp:catalogue_detection')

    # Le prix releve est un REPERE : l'exploitant dit s'il s'agit d'un prix
    # d'achat ou de vente, car une page fabricant publie un tarif public,
    # plus proche d'un prix de vente que d'un cout d'achat negocie.
    cible = request.POST.get('cible_prix')
    if cible not in ('achat', 'vente'):
        cible = 'achat'

    retenus = request.POST.getlist('retenu')[:CANDIDATS_MAX]
    if not retenus:
        messages.warning(request, 'Aucun article coché : rien n’a été ajouté.')
        return redirect('btp:catalogue_detection')

    crees = 0
    ignores = 0
    a_creer = []
    for index in retenus:
        nom = (request.POST.get(f'nom_{index}') or '').strip()[:300]
        if not nom:
            ignores += 1
            continue

        reference = (request.POST.get(f'reference_{index}') or '').strip()[:30]
        unite = (request.POST.get(f'unite_{index}') or '').strip()[:20] or 'u'
        prix = _prix_poste(request.POST.get(f'prix_{index}'))

        # Le doublon est ignore, pas fusionne : ecraser un prix ferme par un
        # prix de repere serait exactement l'inverse de ce qu'on cherche.
        if _existe_deja(company, reference, nom):
            ignores += 1
            continue

        article = Material(
            company=company, kind=nature, name=nom, reference=reference,
            unit=unite, prix_indicatif=True,
        )
        if cible == 'vente':
            article.sale_price = prix
        else:
            article.purchase_price = prix
        a_creer.append(article)
        crees += 1

    if a_creer:
        Material.objects.bulk_create(a_creer)

    message = (f'{crees} article(s) ajouté(s) au catalogue, en prix '
               f'{"de vente" if cible == "vente" else "d’achat"} indicatif.')
    if ignores:
        message += (f' {ignores} ignoré(s) : déjà au catalogue, ou sans '
                    'désignation.')
    (messages.warning if ignores else messages.success)(request, message)
    return redirect(f'{_url_catalogue()}?indicatif=1')


def _prix_poste(brut):
    """Le prix d'un champ caché, ou zéro.

    Revalidé ici : la valeur a fait un aller-retour par le navigateur, et
    la colonne n'accepte ni None ni du texte.
    """
    from .catalogue_import import _nombre

    valeur = _nombre(brut)
    if valeur is None or valeur < 0:
        return Decimal('0')
    return valeur


def _existe_deja(company, reference, nom):
    if reference:
        return Material.objects.filter(
            company=company, reference__iexact=reference).exists()
    return Material.objects.filter(company=company, name__iexact=nom).exists()


def _url_catalogue():
    from django.urls import reverse
    return reverse('btp:material_list')
