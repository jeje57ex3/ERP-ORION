"""Interface téléphone d'Orion ERP.

Trois besoins, trois pages, servies par le serveur lui-même :

1. **S'adapter au téléphone.** Des pages conçues pour le pouce plutôt qu'une
   mise en page de bureau rétrécie : une colonne, de grandes cibles, aucun
   tableau à faire défiler latéralement.
2. **Atteindre l'interface d'un serveur.** Un lanceur qui connaît les serveurs
   de la grappe et permet d'en ouvrir un.
3. **Prendre des photos pour l'ERP.** L'appareil photo du téléphone, sans
   installer d'application.

Pourquoi le web et non l'application Flutter du dépôt : une page web
fonctionne depuis n'importe quel téléphone sans passer par un magasin
d'applications, et `capture="environment"` ouvre directement l'appareil photo
arrière sur Android comme sur iOS. Les deux voies peuvent coexister.

Cloisonnement : toutes les requêtes sont filtrées sur l'entreprise active.
C'est la règle la plus importante de cet ERP, et un formulaire qui laisserait
choisir le chantier d'une autre entreprise serait une fuite de données.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.mobile_web.forms import PhotoMobileForm
from apps.mobile_web.models import EnvoiPhotoMobile

PHOTOS_MAX = 10
TAILLE_MAX_OCTETS = 12 * 1024 * 1024  # 12 Mo par photo
TYPES_ACCEPTES = ('image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif')


def _entreprise(request):
    return getattr(request, 'current_company', None)


def _chantiers_visibles(request):
    """Chantiers de l'entreprise active, et d'elle seule.

    Sans ce filtre, la liste déroulante exposerait les chantiers des autres
    entreprises — y compris leurs noms de clients. C'est précisément la fuite
    que le cloisonnement multi-entreprises existe pour empêcher.
    """
    entreprise = _entreprise(request)
    if not entreprise:
        return []
    try:
        from apps.btp.models import BTPProject
    except Exception:
        return []
    return list(
        BTPProject.objects
        .filter(company=entreprise)
        .exclude(status__in=('cancelled', 'archived'))
        .order_by('-id')[:200]
    )


@login_required
def accueil(request):
    """Point d'entrée téléphone : les actions, pas le menu complet."""
    return render(request, 'mobile_web/accueil.html', {
        'entreprise': _entreprise(request),
        'page_title': 'Orion mobile',
        'rubrique': 'accueil',
    })


@login_required
def serveurs(request):
    """Serveurs joignables, pour ouvrir l'interface de l'un d'eux.

    La liste vient de la grappe enregistrée : des adresses décidées par
    l'exploitant, pas par le visiteur. Aucune redirection n'est émise par le
    serveur — ce sont de simples liens — ce qui écarte toute redirection
    ouverte.
    """
    noeuds = []
    try:
        from apps.high_availability.models import OrionHANode
        noeuds = list(
            OrionHANode.objects
            .filter(is_enabled=True)
            .exclude(base_url='')
            .order_by('priority')
        )
    except Exception:
        noeuds = []

    return render(request, 'mobile_web/serveurs.html', {
        'noeuds': noeuds,
        'ici': request.get_host(),
        'page_title': 'Serveurs',
        'rubrique': 'serveurs',
    })


def _nom_par_defaut():
    return f"Photo du {timezone.localtime().strftime('%d/%m/%Y a %H:%M')}"


def _verifier_photo(fichier):
    """Refus explicite plutôt qu'échec obscur à l'enregistrement."""
    if fichier.size > TAILLE_MAX_OCTETS:
        mo = fichier.size / (1024 * 1024)
        return f'{fichier.name} fait {mo:.1f} Mo, au-delà de la limite de 12 Mo.'
    # Le type déclaré par le navigateur ne prouve rien, mais il écarte les
    # envois manifestement hors sujet avant d'écrire sur le disque.
    if fichier.content_type and fichier.content_type not in TYPES_ACCEPTES:
        return f'{fichier.name} n\'est pas une image ({fichier.content_type}).'
    return ''


def _appel_de_la_file(request):
    """L'envoi vient-il de la file d'attente plutôt que du formulaire ?

    La file a besoin d'une réponse exploitable par du code — un JSON disant si
    la photo est passée — là où le formulaire attend une page. Un seul point
    d'entrée pour les deux : dupliquer la vue dupliquerait aussi le
    cloisonnement par entreprise et les contrôles de fichier, c'est-à-dire
    exactement ce qu'il ne faut pas voir diverger.
    """
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


@login_required
def photo(request):
    """Prend une ou plusieurs photos et les range dans l'ERP."""
    entreprise = _entreprise(request)
    chantiers = _chantiers_visibles(request)

    if request.method != 'POST':
        return render(request, 'mobile_web/photo.html', {
            'form': PhotoMobileForm(chantiers=chantiers),
            'entreprise': entreprise,
            'photos_max': PHOTOS_MAX,
            'page_title': 'Prendre une photo',
            'rubrique': 'photo',
        })

    depuis_la_file = _appel_de_la_file(request)
    cle = (request.POST.get('cle_envoi') or '').strip()[:64]

    # Un envoi déjà enregistré ne doit pas l'être deux fois. La file ne peut
    # pas savoir si une coupure est survenue avant ou APRÈS l'enregistrement :
    # sans ce contrôle, toute réponse perdue donnerait une photo en double.
    if cle:
        deja = EnvoiPhotoMobile.objects.filter(cle=cle).first()
        if deja is not None:
            if depuis_la_file:
                return JsonResponse({
                    'statut': 'deja_recu',
                    'photos': deja.photos,
                    'message': 'Envoi déjà enregistré.',
                })
            messages.info(request, 'Cet envoi avait déjà été enregistré.')
            return redirect('mobile_web:photo')

    form = PhotoMobileForm(request.POST, chantiers=chantiers)
    fichiers = request.FILES.getlist('photos')[:PHOTOS_MAX]
    erreurs = []

    if not entreprise:
        erreurs.append(
            "Aucune entreprise active : impossible de savoir où ranger la photo."
        )
    elif not fichiers:
        erreurs.append('Aucune photo reçue. Prenez ou choisissez une image.')
    elif not form.is_valid():
        for nom_champ, liste in form.errors.items():
            if not liste:
                continue
            champ = form.fields.get(nom_champ)
            libelle = getattr(champ, 'label', '') or nom_champ
            erreurs.append('%s : %s' % (libelle, liste[0]))
    else:
        erreurs.extend(m for m in (_verifier_photo(f) for f in fichiers) if m)

    if not erreurs:
        enregistrees = _enregistrer(
            request, form.cleaned_data, fichiers, entreprise)
        # Zero enregistrement n'est pas un succes. _enregistrer a deja
        # pose l'erreur ; annoncer « 0 photo enregistree » par-dessus,
        # puis rediriger, faisait croire a une reussite et masquait la
        # cause -- un chantier refuse, par exemple.
        if enregistrees:
            if cle:
                try:
                    EnvoiPhotoMobile.objects.create(
                        cle=cle, company=entreprise,
                        user=request.user if request.user.is_authenticated else None,
                        photos=enregistrees,
                    )
                except IntegrityError:
                    # Deux envois simultanés de la même clé : le premier a
                    # gagné, et c'est sans conséquence — la trace existe.
                    pass
            if depuis_la_file:
                return JsonResponse({'statut': 'enregistre',
                                     'photos': enregistrees})
            messages.success(
                request,
                'Photo enregistrée.' if enregistrees == 1
                else f'{enregistrees} photos enregistrées.',
            )
            return redirect('mobile_web:photo')
        erreurs.append("La photo n'a pas pu être enregistrée.")

    if depuis_la_file:
        # _enregistrer signale ses refus par le cadre de messages de Django,
        # invisible pour un appel de la file : sans cette récupération, le
        # téléphone n'affichait qu'un « La photo n'a pas pu être enregistrée »
        # générique là où le serveur avait dit « Chantier inconnu pour cette
        # entreprise ». Le motif précis est ce qui permet de corriger.
        for message in messages.get_messages(request):
            if message.level_tag in ('error', 'warning')                     and str(message) not in erreurs:
                erreurs.append(str(message))

        # 422 et non 400 : la requête est bien formée, c'est son contenu que le
        # serveur refuse. La file doit distinguer ce refus définitif d'une
        # panne de réseau, qu'elle doit au contraire réessayer.
        return JsonResponse({'statut': 'refuse', 'erreurs': erreurs},
                            status=422)

    for message in erreurs:
        messages.error(request, message)

    return render(request, 'mobile_web/photo.html', {
        'form': form,
        'entreprise': entreprise,
        'photos_max': PHOTOS_MAX,
        'page_title': 'Prendre une photo',
        'rubrique': 'photo',
    })


def _enregistrer(request, donnees, fichiers, entreprise):
    """Range les photos dans les pièces jointes existantes de l'ERP.

    Deux destinations, selon qu'un chantier est désigné. Dans les deux cas le
    modèle est celui que l'ERP affiche déjà : la photo apparaît donc là où on
    la cherche, sans écran supplémentaire à construire.
    """
    libelle = (donnees.get('libelle') or '').strip() or _nom_par_defaut()
    description = (donnees.get('description') or '').strip()
    chantier_id = donnees.get('chantier') or ''
    total = 0

    chantier = None
    if chantier_id:
        # Re-filtré sur l'entreprise active : le champ vient du navigateur, et
        # une valeur forgée ne doit pas atteindre le chantier d'un autre.
        chantier = next(
            (p for p in _chantiers_visibles(request) if str(p.pk) == str(chantier_id)),
            None,
        )
        if chantier is None:
            messages.error(request, 'Chantier inconnu pour cette entreprise.')
            return 0

    for index, fichier in enumerate(fichiers, start=1):
        nom = libelle if len(fichiers) == 1 else f'{libelle} ({index}/{len(fichiers)})'

        if chantier is not None:
            from apps.btp.models import ProjectDocument
            ProjectDocument.objects.create(
                project=chantier,
                doc_type='photo',
                name=nom[:200],
                file=fichier,
                description=description,
                visible_to_client=bool(donnees.get('visible_client')),
                added_by=request.user,
            )
        else:
            from apps.documents.models import Document
            Document.objects.create(
                company=entreprise,
                document_type='photo',
                title=nom[:200],
                description=description,
                file=fichier,
                file_size=fichier.size,
                uploaded_by=request.user,
            )
        total += 1

    return total


# ─── Installation sur le telephone (PWA) ─────────────────────────────────────
# Ce qui transforme les trois pages en application : un manifeste, qui donne
# nom et icone au lanceur et ouvre la page en plein ecran, et un agent de
# service, qui garde la coquille en cache pour un demarrage instantane.
#
# Servis par des VUES et non comme fichiers statiques, pour deux raisons :
# l'agent de service doit etre servi depuis /m/ pour que sa portee couvre ces
# pages -- un fichier place a la racine du domaine prendrait tout l'ERP dans
# sa portee -- et les deux restent ainsi versionnes avec le code qu'ils
# decrivent, sans dependre d'une recollecte des statiques.

from django.http import HttpResponse, JsonResponse
from django.templatetags.static import static as url_statique

# Change A CHAQUE modification de la coquille : un agent de service ne se
# remplace que si son contenu differe. Oublier de l'incrementer laisse les
# telephones sur l'ancienne version, indefiniment.
VERSION_CACHE = 'orion-m-v1'


def manifeste(request):
    """Manifeste d'application. Sans lui, aucun navigateur ne propose
    l'installation."""
    return JsonResponse({
        'name': 'Orion ERP',
        'short_name': 'Orion',
        'description': "Interface téléphone d'Orion ERP : photos de chantier "
                       "et accès à l'ERP.",
        'lang': 'fr',
        'dir': 'ltr',
        # L'application s'ouvre sur l'accueil telephone, mais sa portee
        # couvre TOUT l'ERP : « Interface complete » reste donc en plein
        # ecran, sans la barre d'adresse du navigateur. Une portee limitee a
        # /m/ aurait rouvert ces pages dans le navigateur.
        #
        # A ne pas confondre avec la portee de l'agent de service, qui reste
        # volontairement limitee a /m/ (il est servi depuis /m/sw.js). Les
        # deux sont independantes, et c'est ce qui permet d'avoir le plein
        # ecran partout SANS jamais mettre en cache les pages de l'ERP, dont
        # les donnees changent a chaque instant.
        #
        # Consequence a connaitre : sans barre d'adresse, il n'y a plus de
        # recours par l'URL si une page echoue. La barre d'action basse de
        # l'ERP (<= 768px) et le bouton retour du systeme restent les voies
        # de sortie.
        'start_url': '/m/',
        'scope': '/',
        'display': 'standalone',
        'orientation': 'portrait-primary',
        'background_color': '#14110f',
        'theme_color': '#1C120A',
        'icons': [
            {
                'src': url_statique('mobile_web/icons/orion-192.png'),
                'sizes': '192x192', 'type': 'image/png', 'purpose': 'any',
            },
            {
                'src': url_statique('mobile_web/icons/orion-512.png'),
                'sizes': '512x512', 'type': 'image/png', 'purpose': 'any',
            },
            {
                # « maskable » : Android recadre l'icone selon le lanceur.
                'src': url_statique('mobile_web/icons/orion-maskable-512.png'),
                'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable',
            },
        ],
        'shortcuts': [
            {
                'name': 'Prendre une photo',
                'short_name': 'Photo',
                'url': '/m/photo/',
                'icons': [{
                    'src': url_statique('mobile_web/icons/orion-192.png'),
                    'sizes': '192x192',
                }],
            },
        ],
    }, json_dumps_params={'ensure_ascii': False})


# Agent de service. Volontairement court et lisible : un agent de service
# fautif est quasi impossible a diagnostiquer depuis un telephone, et il
# survit a un rechargement de page.
AGENT_DE_SERVICE = """
const CACHE = '%(version)s';
const COQUILLE = ['/m/', '/m/hors-ligne/'];

self.addEventListener('install', (e) => {
  // On precharge la coquille, et on prend la main sans attendre la fermeture
  // des onglets : sinon une correction n'arrive qu'au prochain demarrage.
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(COQUILLE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((noms) => Promise.all(noms.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const requete = e.request;

  // Seules les lectures sont servies depuis le cache. Un POST mis en cache
  // serait une photo perdue ou envoyee deux fois.
  if (requete.method !== 'GET') { return; }

  const url = new URL(requete.url);
  if (url.origin !== self.location.origin) { return; }

  // Hors de /m/, on ne touche a rien : l'ERP complet doit rester servi par le
  // reseau, ses pages dependant de donnees qui changent a chaque instant.
  const dansPortee = url.pathname.startsWith('/m/');
  const estStatique = url.pathname.startsWith('/static/');
  if (!dansPortee && !estStatique) { return; }

  if (estStatique) {
    // Les statiques portent un nom hache : le cache ne peut pas devenir
    // obsolete, on le prefere donc au reseau.
    e.respondWith(
      caches.match(requete).then((trouve) => trouve || fetch(requete).then((rep) => {
        if (rep.ok) { caches.open(CACHE).then((c) => c.put(requete, rep.clone())); }
        return rep;
      }))
    );
    return;
  }

  // Pages de /m/ : le reseau d'abord, car elles affichent des donnees de
  // l'ERP -- une liste de chantiers servie depuis le cache serait perimee et
  // trompeuse. Le cache ne sert que de filet quand le reseau manque.
  e.respondWith(
    fetch(requete)
      .then((rep) => {
        if (rep.ok) { caches.open(CACHE).then((c) => c.put(requete, rep.clone())); }
        return rep;
      })
      .catch(() => caches.match(requete).then((trouve) => trouve || caches.match('/m/hors-ligne/')))
  );
});
"""


def agent_de_service(request):
    reponse = HttpResponse(
        AGENT_DE_SERVICE % {'version': VERSION_CACHE},
        content_type='application/javascript; charset=utf-8',
    )
    # Jamais mis en cache par le navigateur : c'est ce fichier qui decide de
    # tout le reste, et une version figee empecherait toute correction.
    reponse['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return reponse


def hors_ligne(request):
    """Page servie quand le reseau manque. Sans elle, l'application affiche
    l'erreur brute du navigateur, qui ne dit pas quoi faire."""
    return render(request, 'mobile_web/hors_ligne.html', {
        'page_title': 'Hors ligne',
    })
