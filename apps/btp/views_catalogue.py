"""Sources de catalogue web : configurer, essayer à blanc, importer.

**L'essai à blanc n'est pas un confort, c'est la seule façon de vérifier
une correspondance de colonnes sans risque.** Une colonne mal nommée
produit quelques centaines d'articles au mauvais nom, ou des prix d'achat
à zéro, dans un catalogue qui sert ensuite à chiffrer des devis. L'essai
lit, compare et compte tout, et n'écrit rien.

Tout est borné à `request.current_company`, y compris en passant par la
relation (`source__company`) : un identifiant forgé dans l'URL ne doit pas
atteindre la source d'une autre société.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .catalogue_import import CatalogueError, articles_disparus, executer
from .forms_catalogue import CatalogueSourceForm
from .models import CatalogueSource


@login_required
def catalogue_source_list(request):
    company = request.current_company
    sources = (CatalogueSource.objects.filter(company=company)
               .select_related('supplier')
               .prefetch_related('imports'))
    return render(request, 'btp/catalogue_source_list.html', {
        'page_title': 'Catalogues web à importer',
        'sources': sources,
        'active_subnav': 'materials',
    })


@login_required
def catalogue_source_create(request):
    company = request.current_company
    form = CatalogueSourceForm(request.POST or None, company=company)
    if request.method == 'POST' and form.is_valid():
        source = form.save(commit=False)
        source.company = company
        source.created_by = request.user
        source.save()
        messages.success(
            request,
            f'Source « {source.name} » enregistrée. Faites un essai à blanc '
            'avant le premier import.')
        return redirect('btp:catalogue_source_detail', pk=source.pk)
    return render(request, 'btp/catalogue_source_form.html', {
        'page_title': 'Nouveau catalogue web',
        'form': form,
        'action': 'create',
        'active_subnav': 'materials',
    })


@login_required
def catalogue_source_edit(request, pk):
    company = request.current_company
    source = get_object_or_404(CatalogueSource, pk=pk, company=company)
    form = CatalogueSourceForm(request.POST or None, instance=source,
                               company=company)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Source « {source.name} » mise à jour.')
        return redirect('btp:catalogue_source_detail', pk=source.pk)
    return render(request, 'btp/catalogue_source_form.html', {
        'page_title': source.name,
        'form': form,
        'source': source,
        'action': 'edit',
        'active_subnav': 'materials',
    })


@login_required
def catalogue_source_detail(request, pk):
    company = request.current_company
    source = get_object_or_404(CatalogueSource, pk=pk, company=company)
    return render(request, 'btp/catalogue_source_detail.html', {
        'page_title': source.name,
        'source': source,
        'imports': source.imports.select_related('lance_par')[:30],
        'articles': source.articles.order_by('name')[:50],
        'nombre_articles': source.articles.count(),
        'active_subnav': 'materials',
    })


@login_required
@require_POST
def catalogue_source_delete(request, pk):
    """Supprime la source, jamais ses articles.

    `Material.catalogue_source` est en SET_NULL : les articles importés
    restent, simplement sans origine. Les effacer viderait un catalogue qui
    sert peut-être déjà à des devis envoyés.
    """
    company = request.current_company
    source = get_object_or_404(CatalogueSource, pk=pk, company=company)
    nom = source.name
    nombre = source.articles.count()
    source.delete()
    messages.success(
        request,
        f'Source « {nom} » supprimée. Les {nombre} article(s) importés sont '
        'conservés dans le catalogue.')
    return redirect('btp:catalogue_source_list')


@login_required
@require_POST
def catalogue_source_run(request, pk):
    """Importe maintenant. `?blanc=1` pour un essai qui n'écrit rien."""
    company = request.current_company
    source = get_object_or_404(CatalogueSource, pk=pk, company=company)
    a_blanc = request.POST.get('a_blanc') == '1'

    journal = executer(source, a_blanc=a_blanc, utilisateur=request.user)

    if journal.statut == 'echec':
        messages.error(
            request,
            f'Import impossible : {journal.message or "cause inconnue"}')
    else:
        prefixe = 'Essai à blanc — ' if a_blanc else ''
        detail = (f'{journal.lignes_lues} ligne(s) lue(s) : '
                  f'{journal.crees} à créer, {journal.mis_a_jour} à modifier, '
                  f'{journal.inchanges} inchangé(s)'
                  if a_blanc else
                  f'{journal.lignes_lues} ligne(s) lue(s) : '
                  f'{journal.crees} créé(s), {journal.mis_a_jour} modifié(s), '
                  f'{journal.inchanges} inchangé(s)')
        if journal.ignores:
            detail += f', {journal.ignores} ignorée(s)'
        (messages.warning if journal.ignores else messages.success)(
            request, prefixe + detail + '.')

    return redirect('btp:catalogue_source_detail', pk=source.pk)


# Taille d'un tarif de fabricant : celui de Schneider depasse les cent
# mille references, soit une vingtaine de megaoctets en Excel. La borne est
# haute pour cette raison, et pas par negligence.
TAILLE_MAX_TARIF = 60 * 1024 * 1024


@login_required
@require_POST
def catalogue_source_upload(request, pk):
    """Importe un fichier DEPOSE, sans rien telecharger.

    La seule voie possible pour les tarifs des fabricants. Schneider,
    Legrand, Hager, Soprema : leurs tarifs se telechargent a la main
    depuis un portail protege par identifiants, et n'ont aucune adresse
    publique que l'ERP pourrait atteindre.

    Meme chemin de lecture et d'import que la voie URL -- executer()
    accepte les octets -- donc le meme fichier donne le meme resultat
    qu'il arrive par le reseau ou par le navigateur.
    """
    company = request.current_company
    source = get_object_or_404(CatalogueSource, pk=pk, company=company)
    a_blanc = request.POST.get('a_blanc') == '1'

    fichier = request.FILES.get('fichier')
    if fichier is None:
        messages.error(request, 'Aucun fichier reçu.')
        return redirect('btp:catalogue_source_detail', pk=source.pk)

    if fichier.size > TAILLE_MAX_TARIF:
        messages.error(request, (
            f'Fichier trop volumineux : {fichier.size // 1024 // 1024} Mo, '
            f'contre {TAILLE_MAX_TARIF // 1024 // 1024} Mo au maximum. '
            f'Pour un tarif de cette taille, passez par la commande '
            f'« importer_fichier_catalogue » sur le serveur : elle lit le '
            f'fichier sur le disque et ne le fait pas transiter par le '
            f'navigateur.'))
        return redirect('btp:catalogue_source_detail', pk=source.pk)

    journal = executer(source, a_blanc=a_blanc, utilisateur=request.user,
                       octets=fichier.read())

    if journal.statut == 'echec':
        messages.error(
            request,
            f'Import impossible : {journal.message or "cause inconnue"}')
    else:
        prefixe = 'Essai à blanc — ' if a_blanc else ''
        verbes = (('à créer', 'à modifier') if a_blanc
                  else ('créé(s)', 'modifié(s)'))
        detail = (f'{fichier.name} : {journal.lignes_lues} ligne(s) lue(s), '
                  f'{journal.crees} {verbes[0]}, '
                  f'{journal.mis_a_jour} {verbes[1]}, '
                  f'{journal.inchanges} inchangé(s)')
        if journal.ignores:
            detail += f', {journal.ignores} ignorée(s)'
        (messages.warning if journal.ignores else messages.success)(
            request, prefixe + detail + '.')

    return redirect('btp:catalogue_source_detail', pk=source.pk)


@login_required
@require_POST
def catalogue_source_disparus(request, pk):
    """Nomme les articles que le fournisseur ne publie plus.

    Action séparée et explicite, parce qu'elle retélécharge le fichier :
    la déclencher à chaque affichage de la fiche ralentirait l'écran et
    solliciterait le serveur du fournisseur pour rien.

    Rien n'est désactivé ni supprimé : un article peut figurer dans un
    devis déjà envoyé. On le dit, l'exploitant décide.
    """
    company = request.current_company
    source = get_object_or_404(CatalogueSource, pk=pk, company=company)

    try:
        disparus = articles_disparus(source)
    except CatalogueError as exc:
        messages.error(request, f'Vérification impossible : {exc}')
        return redirect('btp:catalogue_source_detail', pk=source.pk)

    if not disparus:
        messages.success(
            request,
            'Tous les articles de cette source figurent encore dans le '
            'fichier publié.')
    else:
        noms = ', '.join(a.name for a in disparus[:10])
        reste = f' et {len(disparus) - 10} autre(s)' if len(disparus) > 10 else ''
        messages.warning(
            request,
            f'{len(disparus)} article(s) ne figurent plus dans le fichier '
            f'publié : {noms}{reste}. Ils sont conservés — à vous de les '
            'désactiver si besoin.')

    return redirect('btp:catalogue_source_detail', pk=source.pk)
