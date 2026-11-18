"""apps/fiscal_pt/views.py — L'écran de conformité portugaise.

TOUT SE PILOTE ICI, ET C'EST VOLONTAIRE

Créer une clé de signature, déclarer une série, saisir le code de
validation rendu par l'AT, vérifier la chaîne, produire le SAF-T : rien
de cela ne demande un accès au serveur. Une obligation fiscale qui
exigerait une ligne de commande serait une obligation qu'on n'honore pas
le jour où il le faut.
"""

import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from . import export, qr, schema
from .forms import ParametresForm, PeriodeForm, SerieForm
from .models import (CleDeSignature, DocumentFiscal, ParametresFiscauxPT,
                     SerieFiscale)


def _company(request):
    return request.current_company


@login_required
def index(request):
    """L'état de la conformité, en un écran.

    L'ordre des points suit celui dans lequel ils doivent être remplis :
    le NIF, puis la clé, puis les séries, puis la communication à l'AT.
    Une liste non ordonnée laisserait l'utilisateur deviner par quoi
    commencer, et la réponse n'est pas évidente.
    """
    company = _company(request)
    parametres = ParametresFiscauxPT.de(company)
    cle = CleDeSignature.objects.filter(company=company,
                                        est_active=True).first()
    series = SerieFiscale.objects.filter(company=company).order_by(
        'type_document', 'nom')
    documents = DocumentFiscal.objects.filter(company=company)

    non_communiquees = [s for s in series if not s.est_communiquee]

    etapes = [
        {
            'titre': 'NIF de l’entreprise',
            'fait': bool(parametres.nif),
            'detail': parametres.nif or 'Absent — il figure dans le code QR '
                                        'et dans l’en-tête du SAF-T.',
            'lien': 'fiscal_pt:parametres',
        },
        {
            'titre': 'Clé de signature RSA-1024',
            'fait': cle is not None,
            'detail': (f'Version {cle.version}, créée le '
                       f'{cle.cree_le:%d/%m/%Y}' if cle else
                       'Aucune clé active : aucun document ne peut être signé.'),
            'lien': 'fiscal_pt:cles',
        },
        {
            'titre': 'Séries de documents',
            'fait': series.exists(),
            'detail': (f'{series.count()} série(s) déclarée(s)'
                       if series else
                       'Aucune série : il en faut au moins une par type de '
                       'document émis.'),
            'lien': 'fiscal_pt:series',
        },
        {
            'titre': 'Codes de validation de l’AT',
            'fait': bool(series) and not non_communiquees,
            'detail': (
                'Toutes les séries sont communiquées'
                if series and not non_communiquees else
                f'{len(non_communiquees)} série(s) sans code de validation : '
                'leurs documents portent un ATCUD « 0 ».'),
            'lien': 'fiscal_pt:series',
        },
        {
            'titre': 'Numéro de certificat AT',
            'fait': parametres.numero_de_certificat not in ('', '0'),
            'detail': (
                f'N° {parametres.numero_de_certificat}'
                if parametres.numero_de_certificat not in ('', '0') else
                'Pas encore attribué. « 0 » est la valeur correcte tant que '
                'le logiciel n’est pas certifié — ce n’est pas une erreur à '
                'corriger ici, mais une démarche à mener auprès de l’AT.'),
            'lien': 'fiscal_pt:parametres',
        },
    ]

    return render(request, 'fiscal_pt/index.html', {
        'page_title': 'Conformite Portugal',
        'page_subtitle': 'Signature des documents, ATCUD, code QR et SAF-T',
        'parametres': parametres,
        'cle': cle,
        'series': series,
        'etapes': etapes,
        'prets': sum(1 for e in etapes if e['fait']),
        'total_etapes': len(etapes),
        'nombre_documents': documents.count(),
        'dernier': documents.order_by('-cree_le').first(),
    })


@login_required
def parametres(request):
    company = _company(request)
    objet = ParametresFiscauxPT.de(company)

    if request.method == 'POST':
        form = ParametresForm(request.POST, instance=objet)
        if form.is_valid():
            form.save()
            messages.success(request, 'Paramètres de conformité enregistrés.')
            return redirect('fiscal_pt:index')
    else:
        form = ParametresForm(instance=objet)

    return render(request, 'fiscal_pt/parametres.html', {
        'page_title': 'Parametres de conformite',
        'form': form,
    })


# ── Les clés ─────────────────────────────────────────────────────────────────

@login_required
def cles(request):
    company = _company(request)
    return render(request, 'fiscal_pt/cles.html', {
        'page_title': 'Cles de signature',
        'page_subtitle': 'RSA-1024 et SHA-1, imposes par le Despacho 8632/2014',
        'cles': CleDeSignature.objects.filter(company=company).order_by(
            '-version'),
    })


@login_required
def cle_creer(request):
    """Fabrique une paire de clés conforme.

    Créer une clé DÉSACTIVE la précédente, et les documents déjà signés
    restent vérifiables avec elle — c'est tout l'intérêt du numéro de
    version. On le dit à l'écran, parce qu'une rotation de clé faite sans
    le savoir ressemble à une perte d'historique.
    """
    if request.method != 'POST':
        return redirect('fiscal_pt:cles')

    company = _company(request)
    try:
        cle = CleDeSignature.creer(
            company, commentaire=request.POST.get('commentaire', '')[:300])
    except Exception as exc:
        messages.error(request, f'Création impossible : {exc}')
        return redirect('fiscal_pt:cles')

    messages.success(
        request,
        f'Clé v{cle.version} créée. Les documents signés avec les versions '
        'précédentes restent vérifiables.')
    return redirect('fiscal_pt:cles')


# ── Les séries ───────────────────────────────────────────────────────────────

@login_required
def series(request):
    company = _company(request)
    return render(request, 'fiscal_pt/series.html', {
        'page_title': 'Series fiscales',
        'page_subtitle': 'Une serie par type de document, communiquee a AT',
        'series': SerieFiscale.objects.filter(company=company).order_by(
            'type_document', 'nom'),
    })


@login_required
def serie_creer(request):
    company = _company(request)

    if request.method == 'POST':
        form = SerieForm(company, request.POST)
        if form.is_valid():
            serie = form.save()
            messages.success(request, f'Série {serie} créée.')
            return redirect('fiscal_pt:series')
    else:
        form = SerieForm(company)

    return render(request, 'fiscal_pt/serie_form.html', {
        'page_title': 'Nouvelle serie',
        'form': form, 'titre': 'Nouvelle série'})


@login_required
def serie_modifier(request, pk):
    company = _company(request)
    serie = get_object_or_404(SerieFiscale, pk=pk, company=company)

    if request.method == 'POST':
        form = SerieForm(company, request.POST, instance=serie)
        if form.is_valid():
            form.save()
            messages.success(request, f'Série {serie} enregistrée.')
            return redirect('fiscal_pt:series')
    else:
        form = SerieForm(company, instance=serie)

    return render(request, 'fiscal_pt/serie_form.html', {
        'page_title': f'Serie {serie}',
        'form': form, 'serie': serie, 'titre': f'Série {serie}'})


# ── Les documents ────────────────────────────────────────────────────────────

@login_required
def documents(request):
    company = _company(request)
    liste = (DocumentFiscal.objects.filter(company=company)
             .select_related('serie')
             .order_by('-date_document', '-numero_sequentiel')[:200])
    return render(request, 'fiscal_pt/documents.html', {
        'page_title': 'Documents fiscaux',
        'page_subtitle': 'Signes, chaines et immuables',
        'documents': liste,
    })


@login_required
def document_detail(request, pk):
    company = _company(request)
    document = get_object_or_404(DocumentFiscal.objects.select_related('serie'),
                                 pk=pk, company=company)
    parametres = ParametresFiscauxPT.de(company)

    return render(request, 'fiscal_pt/document_detail.html', {
        'page_title': document.numero,
        'page_subtitle': 'Document signe, non modifiable',
        'document': document,
        'verifie': document.verifier(),
        'mention': document.mention_legale(
            parametres.numero_de_certificat or '0'),
    })


@login_required
def document_qr(request, pk):
    """L'image du code QR, en PNG."""
    company = _company(request)
    document = get_object_or_404(DocumentFiscal, pk=pk, company=company)

    try:
        image = qr.image(document.contenu_qr)
    except qr.ErreurQR as exc:
        raise Http404(str(exc))

    tampon = io.BytesIO()
    image.save(tampon, format='PNG')
    tampon.seek(0)
    return FileResponse(tampon, content_type='image/png',
                        filename=f'qr-{document.numero_sequentiel}.png')


@login_required
def verifier_les_chaines(request):
    """Revérifie toutes les signatures, série par série.

    C'est l'opération que fait l'administration au contrôle. La proposer
    d'un bouton change ce qu'elle coûte : une chaîne cassée se découvre
    bien mieux chez soi que devant un inspecteur.
    """
    company = _company(request)
    rapport = []

    for serie in SerieFiscale.objects.filter(company=company).order_by(
            'type_document', 'nom'):
        liste = list(DocumentFiscal.objects.filter(serie=serie)
                     .order_by('numero_sequentiel'))

        ruptures = []
        attendu = ''
        for document in liste:
            if not document.verifier():
                ruptures.append(
                    f'{document.numero} : signature invalide')
            elif document.signature_precedente != attendu:
                # Un maillon qui ne désigne pas son prédécesseur : la
                # signature est bonne, mais la CHAÎNE est rompue. Les deux
                # contrôles sont distincts, et seul le second repère un
                # document retiré du milieu de la série.
                ruptures.append(
                    f'{document.numero} : ne suit pas le document précédent')
            attendu = document.signature

        trous = [n for n in range(1, len(liste) + 1)
                 if n not in {d.numero_sequentiel for d in liste}]

        rapport.append({
            'serie': serie,
            'nombre': len(liste),
            'ruptures': ruptures,
            'trous': trous,
            'intacte': not ruptures and not trous,
        })

    return render(request, 'fiscal_pt/verification.html', {
        'page_title': 'Verification des chaines',
        'page_subtitle': 'Signatures et continuite, serie par serie',
        'rapport': rapport,
        'tout_intact': all(ligne['intacte'] for ligne in rapport) and bool(rapport),
    })


# ── Le SAF-T ─────────────────────────────────────────────────────────────────

@login_required
def export_saft(request):
    company = _company(request)
    form = PeriodeForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        debut = form.cleaned_data['debut']
        fin = form.cleaned_data['fin']
        try:
            contenu = export.composer(company, debut, fin)
        except Exception as exc:
            messages.error(request, f'Export impossible : {exc}')
            return render(request, 'fiscal_pt/export.html', {
                'page_title': 'Export SAF-T (PT)', 'form': form})

        # Le fichier est compare au schema de l'AT AVANT d'etre remis.
        #
        # Decouvrir un element deplace ici coute une minute ; le decouvrir
        # dans le courriel de rejet coute une remise, et le message de
        # l'AT designe l'element SUIVANT, ce qui envoie chercher la cause
        # au mauvais endroit.
        #
        # On ne BLOQUE pas : le fichier reste telechargeable d'un second
        # clic. Un validateur qui empeche de recuperer son propre travail
        # se fait contourner, et c'est alors plus personne qui verifie.
        anomalies = []
        try:
            anomalies = schema.valider(contenu)
        except schema.ErreurDeSchema as exc:
            messages.warning(
                request,
                f'Verification impossible, fichier produit tel quel : {exc}')

        if anomalies and not request.POST.get('ignorer_les_anomalies'):
            return render(request, 'fiscal_pt/export.html', {
                'page_title': 'Export SAF-T (PT)',
                'page_subtitle': 'Version 1.04_01, facturation',
                'form': form,
                'anomalies': anomalies,
                'resume': schema.resume(anomalies),
                'debut': debut.isoformat(),
                'fin': fin.isoformat(),
            })

        reponse = HttpResponse(contenu, content_type='application/xml')
        nom = export.nom_de_fichier(company, debut, fin)
        reponse['Content-Disposition'] = f'attachment; filename="{nom}"'
        if not anomalies:
            reponse['X-Orion-Schema'] = 'conforme-1.04_01'
        return reponse

    return render(request, 'fiscal_pt/export.html', {
        'page_title': 'Export SAF-T (PT)',
        'page_subtitle': 'Version 1.04_01, facturation',
        'form': form,
    })


@login_required
def note_de_credit(request, pk):
    """Emet l'avoir qui rectifie une facture signee.

    POURQUOI CET ECRAN EXISTE

    Un document emis ne se modifie plus : sa signature couvre son contenu,
    et tous les suivants de la serie signent la sienne. La seule voie
    legale de correction est l'avoir -- et le message d'erreur du modele
    le dit deja. Sans cet ecran, il designerait une fonction inexistante.
    """
    from apps.sales.models import Invoice

    from .facturation import ConformiteInactive, emettre_une_note_de_credit

    company = _company(request)
    facture = get_object_or_404(Invoice, pk=pk, company=company)
    origine = facturation_document(facture)

    if request.method == 'POST':
        motif = (request.POST.get('motif') or '').strip()
        try:
            avoir = emettre_une_note_de_credit(facture, motif)
        except ConformiteInactive:
            messages.error(
                request,
                'La conformite portugaise n\'est pas activee : il n\'y a pas '
                'de document signe a rectifier.')
            return redirect('sales:invoice_detail', pk=facture.pk)
        except Exception as exc:
            messages.error(request, f'Avoir non emis : {exc}')
            return render(request, 'fiscal_pt/note_de_credit.html', {
                'page_title': f'Avoir sur {facture.number}',
                'facture': facture, 'origine': origine, 'motif': motif})

        messages.success(
            request,
            f'Note de credit {avoir.numero} emise (ATCUD {avoir.atcud}).')
        return redirect('fiscal_pt:document_detail', pk=avoir.pk)

    return render(request, 'fiscal_pt/note_de_credit.html', {
        'page_title': f'Avoir sur {facture.number}',
        'page_subtitle': 'La seule voie legale de correction d\'un document emis',
        'facture': facture,
        'origine': origine,
    })


def facturation_document(invoice):
    """Le document fiscal d'une facture, importe tardivement.

    `facturation` importe `models`, qui importe `saft` : l'importer en
    tete de ce module creerait une boucle a l'initialisation de Django.
    """
    from .facturation import document_pour
    return document_pour(invoice)
