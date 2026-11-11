"""Deux autres écrans où un champ requis n'était rendu nulle part.

LA SUITE DE L'ENQUÊTE

Après la panne du planning — « j'appuie sur Ajouter et rien ne se passe » —
un balayage du dépôt a signalé huit formulaires dont un champ requis
n'apparaissait dans aucun gabarit de leur application. Vérification faite un
par un : SIX ÉTAIENT DES FAUX POSITIFS de l'heuristique.

  * crm.ActivityForm : importé dans les vues et jamais instancié. Du code
    mort ne peut pas avoir ce défaut ;
  * websites.ContactForm et QuoteRequestForm : rendus par
    templates/websites/public/, un sous-dossier que le balayage ne
    parcourait pas ;
  * continuous_improvement.PDCAActionForm : le gabarit boucle
    « {% for field in action_form %} », donc rend tout ;
  * internal_training.TrainingPageBlockForm : « block_type » voyage dans un
    champ caché posé par le gabarit ;
  * websites.WebsiteAdminForm : jamais rendu par une page.

DEUX ÉTAIENT RÉELS, et c'est le même mécanisme que sur le planning : une
valeur par défaut au niveau du modèle SANS `blank=True`. Django en fait un
champ de formulaire obligatoire — le défaut fournit l'initiale, il ne rend
rien facultatif.
"""
import pytest


# ── 1. Le tableau de bord : le thème manquait ────────────────────────────────

def test_le_theme_du_tableau_de_bord_est_requis():
    """Le piège, encore : `default` ne vaut pas `blank=True`."""
    from apps.dashboard.forms import DashboardLayoutForm

    form = DashboardLayoutForm()
    assert form.fields['theme'].required is True


def test_le_gabarit_du_tableau_de_bord_rend_le_theme():
    from pathlib import Path

    texte = Path(
        'apps/dashboard/templates/dashboard/customize.html'
    ).read_text(encoding='utf-8')
    assert 'layout_form.theme' in texte


@pytest.mark.django_db
def test_la_disposition_est_valide_avec_ce_que_le_gabarit_envoie(
        django_user_model):
    """Le gabarit envoie « layout_type » par une radio posée à la main,
    « theme » et « name » par les widgets du formulaire."""
    from apps.dashboard.forms import DashboardLayoutForm

    form = DashboardLayoutForm({
        'layout_type': 'two_columns',
        'theme': 'orion_luxury',
        'name': 'Mon tableau de bord',
    })
    assert form.is_valid(), form.errors.as_json()


@pytest.mark.django_db
def test_sans_theme_l_erreur_porte_bien_sur_ce_champ():
    """La preuve du mécanisme : c'est bien ce champ qui bloquait."""
    from apps.dashboard.forms import DashboardLayoutForm

    form = DashboardLayoutForm({
        'layout_type': 'two_columns',
        'name': 'Mon tableau de bord',
    })
    assert form.is_valid() is False
    assert 'theme' in form.errors


def test_la_vue_ne_redirige_plus_en_silence_sur_un_refus():
    """LE DÉFAUT QUI A RENDU L'AUTRE INDIAGNOSTICABLE.

    La vue redirigeait vers la même page que le formulaire soit accepté ou
    refusé, sans message dans le second cas. La page se rechargeait, l'air
    de rien, et la disposition n'était jamais enregistrée.
    """
    from pathlib import Path

    source = Path('apps/dashboard/views.py').read_text(encoding='utf-8')
    bloc = source[source.index("if action == 'save_layout':"):]
    bloc = bloc[:bloc.index('return redirect')]
    assert 'else:' in bloc, 'un refus reste silencieux'
    assert 'messages.error' in bloc


# ── 2. La caisse : un statut qu'on ne devrait pas saisir ─────────────────────

def test_le_formulaire_d_ouverture_ne_demande_plus_le_statut():
    """Une session qu'on ouvre est ouverte par définition.

    `status` portait « default='open' » sans `blank=True`, donc restait
    REQUIS, et le gabarit ne le rendait nulle part : ouvrir une caisse
    échouait à chaque fois, en réaffichant la même page sans message.

    Le retirer vaut mieux que l'ajouter au gabarit : demander son statut à
    une session qu'on ouvre n'a pas de sens, et son fond de caisse de
    clôture n'existe pas encore.
    """
    from apps.commerce.forms import POSSessionForm

    champs = set(POSSessionForm().fields)
    assert 'status' not in champs
    assert 'closing_cash' not in champs
    assert champs == {'store', 'opening_cash'}


@pytest.mark.django_db
def test_une_session_de_caisse_s_ouvre_vraiment():
    """De bout en bout : le formulaire accepte, et le modèle pose « open »."""
    from apps.commerce.forms import POSSessionForm
    from apps.commerce.models import Store
    from apps.core.models import Company

    entreprise = Company.objects.create(name='Volt SARL', slug='volt-sarl')
    magasin = Store.objects.create(
        company=entreprise, name='Boutique', is_active=True)

    form = POSSessionForm(
        {'store': str(magasin.pk), 'opening_cash': '100.00'},
        company=entreprise)
    assert form.is_valid(), form.errors.as_json()

    session = form.save(commit=False)
    session.company = entreprise
    session.save()

    assert session.status == 'open', (
        'le modèle doit poser le statut, puisque le formulaire ne le '
        'demande plus')


@pytest.mark.django_db
def test_la_cloture_pose_toujours_le_statut_elle_meme():
    """La contrepartie du retrait : la clôture ne passe pas par ce
    formulaire, elle écrit `status` et `closing_cash` directement. Si elle
    changeait d'avis, ce test tomberait."""
    from pathlib import Path

    source = Path('apps/commerce/views.py').read_text(encoding='utf-8')
    bloc = source[source.index('def pos_session_close'):]
    bloc = bloc[:bloc.index('\n@')] if '\n@' in bloc else bloc
    assert "session.status = 'closed'" in bloc
    assert 'closing_cash' in bloc
    assert 'POSSessionForm' not in bloc


# ── 3. Les six faux positifs, nommés pour ne pas les rechercher deux fois ───

def test_activity_form_du_crm_est_du_code_mort():
    """Importé dans les vues, jamais instancié : il ne peut pas avoir ce
    défaut. Le laisser en l'état plutôt que de l'habiller d'un gabarit qui
    n'existe pas."""
    from pathlib import Path

    source = Path('apps/crm/views.py').read_text(encoding='utf-8')
    assert 'ActivityForm' in source, 'import attendu'
    assert 'ActivityForm(' not in source, (
        'ActivityForm est désormais instancié : il lui faut un gabarit qui '
        'rende ses quatre champs requis — activity_type, subject, date, '
        'duration_minutes')


def test_les_formulaires_publics_des_sites_rendent_leurs_champs_requis():
    """Faux positifs d'un balayage non récursif : ils vivent dans
    templates/websites/public/."""
    from pathlib import Path

    contact = Path('templates/websites/public/contact.html').read_text(
        encoding='utf-8')
    assert 'form.email' in contact and 'form.message' in contact

    devis = Path('templates/websites/public/quote_request.html').read_text(
        encoding='utf-8')
    assert 'form.email' in devis
