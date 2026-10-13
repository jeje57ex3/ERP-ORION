"""
tests/test_high_availability.py — Module Haute Disponibilité Orion ERP
"""
import pytest
from django.utils import timezone
from django.test import RequestFactory

from apps.high_availability.models import (
    OrionHANode,
    OrionHASettings,
    OrionHAClusterLock,
    OrionHAFailoverEvent,
)
from apps.high_availability import services
from apps.high_availability.failover import (
    FailoverTrafficError,
    _hote_du_noeud,
    run_manual_failover_to_node,
    validate_failover_target,
)
from apps.high_availability.automatic import check_and_run_automatic_failover
from apps.high_availability.forms import OrionHASettingsForm, OrionHANodeForm

pytestmark = pytest.mark.django_db


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def primary_node(db):
    return OrionHANode.objects.create(
        node_id='orion-primary',
        name='Orion Principal',
        role='primary',
        priority=1,
        status='active',
        is_current_active=True,
        is_failover_target=False,
        is_enabled=True,
    )


@pytest.fixture
def secondary_1(db):
    return OrionHANode.objects.create(
        node_id='orion-secondary-1',
        name='Orion Secondaire 1',
        role='secondary',
        priority=2,
        status='healthy',
        is_current_active=False,
        is_failover_target=True,
        is_enabled=True,
    )


@pytest.fixture
def secondary_2(db):
    return OrionHANode.objects.create(
        node_id='orion-secondary-2',
        name='Orion Secondaire 2',
        role='secondary',
        priority=3,
        status='healthy',
        is_current_active=False,
        is_failover_target=True,
        is_enabled=True,
    )


@pytest.fixture
def ha_settings(db):
    return OrionHASettings.get_solo()


@pytest.fixture
def cluster_lock(db):
    return OrionHAClusterLock.get_lock()


# ── OrionHANode — modèle ──────────────────────────────────────────────────────

def test_node_str(primary_node):
    assert 'orion-primary' in str(primary_node)
    assert 'Orion Principal' in str(primary_node)


def test_node_heartbeat_age_none_when_no_heartbeat(primary_node):
    assert primary_node.heartbeat_age_seconds is None


def test_node_is_stale_when_no_heartbeat(primary_node):
    assert primary_node.is_stale is True


def test_node_is_not_stale_with_fresh_heartbeat(primary_node):
    primary_node.last_heartbeat_at = timezone.now()
    primary_node.save()
    assert primary_node.is_stale is False


def test_node_is_stale_with_old_heartbeat(primary_node):
    from datetime import timedelta
    primary_node.last_heartbeat_at = timezone.now() - timedelta(seconds=200)
    primary_node.save()
    assert primary_node.is_stale is True


def test_secondary_can_be_failover_target(secondary_1):
    assert secondary_1.can_be_failover_target is True


def test_primary_cannot_be_failover_target(primary_node):
    assert primary_node.can_be_failover_target is False


def test_disabled_node_cannot_be_failover_target(secondary_1):
    secondary_1.is_enabled = False
    secondary_1.save()
    assert secondary_1.can_be_failover_target is False


def test_down_node_cannot_be_failover_target(secondary_1):
    secondary_1.status = 'down'
    secondary_1.save()
    assert secondary_1.can_be_failover_target is False


# ── OrionHASettings — singleton ───────────────────────────────────────────────

def test_ha_settings_singleton(db):
    s1 = OrionHASettings.get_solo()
    s2 = OrionHASettings.get_solo()
    assert s1.pk == s2.pk == 1


def test_ha_settings_defaults(ha_settings):
    assert ha_settings.failover_enabled is True
    assert ha_settings.automatic_failover_enabled is False
    assert ha_settings.require_manual_confirmation is True
    assert ha_settings.split_brain_protection_enabled is True
    assert ha_settings.failover_after_seconds == 120
    assert ha_settings.max_allowed_replication_lag_seconds == 10


# ── OrionHAClusterLock — singleton ───────────────────────────────────────────

def test_cluster_lock_singleton(db):
    l1 = OrionHAClusterLock.get_lock()
    l2 = OrionHAClusterLock.get_lock()
    assert l1.pk == l2.pk == 1


def test_cluster_lock_default_node(cluster_lock):
    assert cluster_lock.active_node_id == 'orion-primary'


# ── Services — seed ───────────────────────────────────────────────────────────

def test_seed_creates_three_nodes(db, settings):
    settings.ORION_PRIMARY_URL = 'http://primary.test'
    settings.ORION_SECONDARY_1_URL = 'http://secondary1.test'
    settings.ORION_SECONDARY_2_URL = 'http://secondary2.test'
    services.seed_default_ha_nodes()
    assert OrionHANode.objects.count() == 3


def test_seed_primary_is_active(db, settings):
    settings.ORION_PRIMARY_URL = ''
    settings.ORION_SECONDARY_1_URL = ''
    settings.ORION_SECONDARY_2_URL = ''
    services.seed_default_ha_nodes()
    primary = OrionHANode.objects.get(node_id='orion-primary')
    assert primary.is_current_active is True
    assert primary.role == 'primary'
    assert primary.priority == 1


def test_seed_sets_preferred_secondary(db, settings):
    settings.ORION_PRIMARY_URL = ''
    settings.ORION_SECONDARY_1_URL = ''
    settings.ORION_SECONDARY_2_URL = ''
    services.seed_default_ha_nodes()
    ha = OrionHASettings.get_solo()
    assert ha.preferred_secondary_node is not None
    assert ha.preferred_secondary_node.node_id == 'orion-secondary-1'


def test_seed_is_idempotent(db, settings):
    settings.ORION_PRIMARY_URL = ''
    settings.ORION_SECONDARY_1_URL = ''
    settings.ORION_SECONDARY_2_URL = ''
    services.seed_default_ha_nodes()
    services.seed_default_ha_nodes()
    assert OrionHANode.objects.count() == 3


# ── Services — get_active_node ───────────────────────────────────────────────

def test_get_active_node_returns_primary(primary_node, secondary_1):
    active = services.get_active_node()
    assert active.node_id == 'orion-primary'


def test_get_active_node_none_when_no_active(db):
    OrionHANode.objects.create(
        node_id='orion-primary', name='P', role='primary',
        priority=1, is_current_active=False, is_enabled=True,
    )
    assert services.get_active_node() is None


# ── Services — count_healthy_secondaries ─────────────────────────────────────

def test_count_healthy_secondaries(primary_node, secondary_1, secondary_2):
    assert services.count_healthy_secondaries() == 2


def test_count_healthy_excludes_down(primary_node, secondary_1, secondary_2):
    secondary_2.status = 'down'
    secondary_2.save()
    assert services.count_healthy_secondaries() == 1


def test_count_healthy_excludes_disabled(primary_node, secondary_1, secondary_2):
    secondary_1.is_enabled = False
    secondary_1.save()
    secondary_2.is_enabled = False
    secondary_2.save()
    assert services.count_healthy_secondaries() == 0


# ── Services — select_best_failover_target ───────────────────────────────────

def test_select_best_returns_preferred(primary_node, secondary_1, secondary_2, ha_settings):
    ha_settings.preferred_secondary_node = secondary_1
    ha_settings.save()
    target = services.select_best_failover_target()
    assert target.node_id == 'orion-secondary-1'


def test_select_best_skips_preferred_if_down(primary_node, secondary_1, secondary_2, ha_settings):
    ha_settings.preferred_secondary_node = secondary_1
    ha_settings.save()
    secondary_1.status = 'down'
    secondary_1.save()
    target = services.select_best_failover_target()
    assert target.node_id == 'orion-secondary-2'


def test_select_best_skips_high_lag(primary_node, secondary_1, secondary_2, ha_settings):
    ha_settings.preferred_secondary_node = secondary_1
    ha_settings.max_allowed_replication_lag_seconds = 10
    ha_settings.save()
    secondary_1.replication_lag_seconds = 60
    secondary_1.save()
    target = services.select_best_failover_target()
    assert target.node_id == 'orion-secondary-2'


def test_select_best_returns_none_when_all_down(primary_node, secondary_1, secondary_2):
    secondary_1.status = 'down'
    secondary_1.save()
    secondary_2.status = 'down'
    secondary_2.save()
    assert services.select_best_failover_target() is None


# ── Services — set_active_node ────────────────────────────────────────────────

def test_set_active_node_switches_lock(primary_node, secondary_1, cluster_lock):
    services.set_active_node(secondary_1, lock_token='tok123')
    secondary_1.refresh_from_db()
    primary_node.refresh_from_db()
    lock = OrionHAClusterLock.get_lock()
    assert secondary_1.is_current_active is True
    assert primary_node.is_current_active is False
    assert lock.active_node_id == 'orion-secondary-1'
    assert lock.lock_token == 'tok123'


# ── Failover — validate_failover_target ──────────────────────────────────────

def test_validate_target_raises_when_failover_disabled(secondary_1, ha_settings):
    ha_settings.failover_enabled = False
    ha_settings.save()
    with pytest.raises(RuntimeError, match='désactivé'):
        validate_failover_target(secondary_1)


def test_validate_target_raises_when_not_secondary(primary_node, ha_settings):
    with pytest.raises(RuntimeError, match='secondaire'):
        validate_failover_target(primary_node)


def test_validate_target_raises_when_not_failover_target(secondary_1, ha_settings):
    secondary_1.is_failover_target = False
    secondary_1.save()
    with pytest.raises(RuntimeError, match='autorisé'):
        validate_failover_target(secondary_1)


def test_validate_target_raises_when_lag_too_high(secondary_1, ha_settings):
    ha_settings.max_allowed_replication_lag_seconds = 5
    ha_settings.save()
    secondary_1.replication_lag_seconds = 30
    secondary_1.save()
    with pytest.raises(RuntimeError, match='retard'):
        validate_failover_target(secondary_1)


def test_validate_target_passes_for_healthy_secondary(secondary_1, ha_settings):
    assert validate_failover_target(secondary_1) is True


# ── Failover — run_manual_failover_to_node ───────────────────────────────────

def test_run_failover_creates_event(primary_node, secondary_1, ha_settings, superuser):
    event = run_manual_failover_to_node(
        target_node=secondary_1,
        started_by=superuser,
        reason='Test bascule',
    )
    assert event.status == 'success'
    assert event.to_node == secondary_1
    assert event.from_node == primary_node
    assert event.started_by == superuser


def test_run_failover_switches_active_node(primary_node, secondary_1, ha_settings):
    run_manual_failover_to_node(target_node=secondary_1, reason='Test')
    secondary_1.refresh_from_db()
    assert secondary_1.is_current_active is True


def test_run_failover_fails_on_disabled_target(primary_node, secondary_1, ha_settings):
    secondary_1.is_enabled = False
    secondary_1.save()
    # L'evenement d'echec est desormais enregistre : la bascule n'est plus
    # englobee dans une transaction atomique qui le perdait au rollback.
    with pytest.raises(RuntimeError):
        run_manual_failover_to_node(target_node=secondary_1, reason='Test')


# ── Automatic failover ────────────────────────────────────────────────────────

def test_automatic_failover_skipped_when_disabled(primary_node, ha_settings):
    ha_settings.failover_enabled = False
    ha_settings.save()
    result = check_and_run_automatic_failover()
    assert result['skipped'] is True


def test_automatic_failover_skipped_when_auto_disabled(primary_node, ha_settings):
    ha_settings.automatic_failover_enabled = False
    ha_settings.save()
    result = check_and_run_automatic_failover()
    assert result['skipped'] is True


def test_automatic_failover_skipped_when_manual_confirmation(primary_node, ha_settings):
    ha_settings.automatic_failover_enabled = True
    ha_settings.require_manual_confirmation = True
    ha_settings.save()
    result = check_and_run_automatic_failover()
    assert result['skipped'] is True


def test_automatic_failover_skipped_when_active_healthy(primary_node, ha_settings):
    ha_settings.automatic_failover_enabled = True
    ha_settings.require_manual_confirmation = False
    ha_settings.save()
    primary_node.last_heartbeat_at = timezone.now()
    primary_node.status = 'active'
    primary_node.save()
    result = check_and_run_automatic_failover()
    assert result['skipped'] is True


# ── Forms — OrionHASettingsForm ───────────────────────────────────────────────

def test_settings_form_valid(ha_settings):
    data = {
        'failover_enabled': True,
        'automatic_failover_enabled': False,
        'require_manual_confirmation': True,
        'failover_after_seconds': 120,
        'max_allowed_replication_lag_seconds': 10,
        'minimum_healthy_secondaries': 1,
        'allow_failover_to_secondary_2': True,
        'failback_policy': 'manual',
        'failback_min_stable_seconds': 300,
        'media_sync_enabled': True,
        'database_replication_check_enabled': True,
        'cloudflare_failover_enabled': False,
        'cloudflare_record_name': 'erp',
        'notify_admins': True,
        'split_brain_protection_enabled': True,
        'maintenance_mode_enabled': False,
    }
    form = OrionHASettingsForm(data=data, instance=ha_settings)
    assert form.is_valid(), form.errors


def test_settings_form_rejects_auto_with_manual_confirmation(ha_settings):
    data = {
        'failover_enabled': True,
        'automatic_failover_enabled': True,
        'require_manual_confirmation': True,
        'failover_after_seconds': 120,
        'max_allowed_replication_lag_seconds': 10,
        'minimum_healthy_secondaries': 1,
        'allow_failover_to_secondary_2': True,
        'failback_policy': 'manual',
        'failback_min_stable_seconds': 300,
        'media_sync_enabled': True,
        'database_replication_check_enabled': True,
        'cloudflare_failover_enabled': False,
        'cloudflare_record_name': 'erp',
        'notify_admins': True,
        'split_brain_protection_enabled': True,
        'maintenance_mode_enabled': False,
    }
    form = OrionHASettingsForm(data=data, instance=ha_settings)
    assert not form.is_valid()
    assert 'automatique' in str(form.errors).lower() or '__all__' in form.errors


def test_settings_form_rejects_failover_under_60s(ha_settings):
    data = {
        'failover_enabled': True,
        'automatic_failover_enabled': False,
        'require_manual_confirmation': True,
        'failover_after_seconds': 30,
        'max_allowed_replication_lag_seconds': 10,
        'minimum_healthy_secondaries': 1,
        'allow_failover_to_secondary_2': True,
        'failback_policy': 'manual',
        'failback_min_stable_seconds': 300,
        'media_sync_enabled': True,
        'database_replication_check_enabled': True,
        'cloudflare_failover_enabled': False,
        'cloudflare_record_name': 'erp',
        'notify_admins': True,
        'split_brain_protection_enabled': True,
        'maintenance_mode_enabled': False,
    }
    form = OrionHASettingsForm(data=data, instance=ha_settings)
    assert not form.is_valid()


# ── Forms — OrionHANodeForm ───────────────────────────────────────────────────

def test_node_form_rejects_active_node_without_primary_role(primary_node):
    """Le rang n'est plus lie au role, mais l'actif doit porter le role principal."""
    data = {
        'node_id': 'orion-primary',
        'name': 'Principal',
        'role': 'secondary',
        'status': 'active',
        'priority': 1,
        'is_enabled': True,
        'is_current_active': True,
        'is_failover_target': False,
        'allow_auto_failover': False,
    }
    form = OrionHANodeForm(data=data, instance=primary_node)
    assert not form.is_valid()


def test_node_form_accepts_demoted_primary_keeping_its_rank(primary_node):
    """Cas normal apres une bascule : rang 1 conserve, role secondaire.

    Les deux anciennes regles de couplage le rejetaient, rendant inediteable
    tout serveur ayant connu une bascule.
    """
    data = {
        'node_id': 'orion-primary',
        'name': 'Principal',
        'role': 'secondary',
        'status': 'passive',
        'priority': 1,
        'is_enabled': True,
        'is_current_active': False,
        'is_failover_target': True,
        'allow_auto_failover': True,
    }
    form = OrionHANodeForm(data=data, instance=primary_node)
    assert form.is_valid(), form.errors


def test_node_form_rejects_duplicate_active(primary_node, secondary_1):
    data = {
        'node_id': 'orion-secondary-1',
        'name': 'Secondaire 1',
        'role': 'secondary',
        'status': 'healthy',
        'priority': 2,
        'is_enabled': True,
        'is_current_active': True,
        'is_failover_target': True,
        'allow_auto_failover': True,
    }
    form = OrionHANodeForm(data=data, instance=secondary_1)
    assert not form.is_valid()


# ── Views — permissions ───────────────────────────────────────────────────────

def test_settings_view_requires_superuser(client, staff_user, entreprise):
    """super_admin_required redirige, il ne renvoie pas 403.

    Le test affirmait un 403 que le decorateur n'a jamais produit : il
    redirige vers le tableau de bord avec un message, par choix
    d'ergonomie. On eprouve donc la propriete de securite -- la page
    n'est pas servie -- plutot qu'un code de statut imaginaire.
    """
    client.force_login(staff_user)
    response = client.get('/orion-admin/ha/settings/')
    assert response.status_code == 302
    assert '/orion-admin/ha/' not in response.url


def test_settings_view_accessible_to_superuser(client, superuser, entreprise):
    client.force_login(superuser)
    response = client.get('/orion-admin/ha/settings/')
    assert response.status_code == 200


def test_nodes_view_accessible_to_superuser(client, superuser, primary_node, entreprise):
    client.force_login(superuser)
    response = client.get('/orion-admin/ha/nodes/')
    assert response.status_code == 200


def test_failover_view_accessible_to_superuser(client, superuser, entreprise):
    client.force_login(superuser)
    response = client.get('/orion-admin/ha/failover/')
    assert response.status_code == 200


def test_events_view_accessible_to_superuser(client, superuser, entreprise):
    client.force_login(superuser)
    response = client.get('/orion-admin/ha/events/')
    assert response.status_code == 200


# ── Health endpoint ───────────────────────────────────────────────────────────

def test_health_view_forbidden_without_secret(client, settings):
    settings.ORION_HA_SECRET = 'mysecret'
    response = client.get('/ha/health/')
    assert response.status_code == 403


def test_health_view_ok_with_secret(client, settings):
    settings.ORION_HA_SECRET = 'mysecret'
    response = client.get('/ha/health/', HTTP_X_ORION_HA_SECRET='mysecret')
    assert response.status_code == 200
    data = response.json()
    assert 'status' in data
    assert 'node_id' in data


def test_public_health_view_no_auth(client):
    response = client.get('/ha/public-health/')
    assert response.status_code == 200
    data = response.json()
    assert 'status' in data
    assert 'role' in data


# ── Bascule : redirection du trafic par indirection DNS ──────────────────────
# Tous les domaines publics pointent par CNAME vers un seul nom d'indirection
# (actif.exemple.fr), lui-même pointé vers le sous-domaine du serveur actif.
# La bascule ne doit modifier QUE cet enregistrement.

class _FauxCloudflare:
    """Client Cloudflare en double, pour éprouver la bascule sans réseau."""

    def __init__(self, enregistrements=None, zone_nom='exemple.fr'):
        self.zone_nom = zone_nom
        self.patchs = []
        self.enregistrements = enregistrements if enregistrements is not None else [
            {'id': 'rec-actif', 'type': 'CNAME', 'name': 'actif.exemple.fr',
             'content': 'serveur1.exemple.fr', 'proxied': True},
        ]

    def get_zone(self, zone_id):
        return {'id': zone_id, 'name': self.zone_nom}

    def list_zones(self, name=None):
        return [{'id': 'zone-1', 'name': name}] if name == self.zone_nom else []

    def list_dns_records(self, zone_id, name=None, record_type=None):
        return [r for r in self.enregistrements if name is None or r['name'] == name]

    def patch_dns_record(self, zone_id, record_id, **payload):
        self.patchs.append((zone_id, record_id, payload))
        for r in self.enregistrements:
            if r['id'] == record_id:
                r.update(payload)
                return r
        return None


@pytest.fixture
def faux_cloudflare(monkeypatch):
    """Substitue le client Cloudflare, importé paresseusement par failover.py."""
    faux = _FauxCloudflare()
    monkeypatch.setattr(
        'apps.domain_diagnostics.cloudflare.CloudflareClient',
        lambda *a, **k: faux,
    )
    return faux


@pytest.fixture
def ha_cloudflare(ha_settings):
    ha_settings.cloudflare_failover_enabled = True
    ha_settings.cloudflare_zone_id = 'zone-1'
    ha_settings.cloudflare_record_name = 'actif'
    ha_settings.save()
    return ha_settings


@pytest.fixture
def secondary_avec_sous_domaine(secondary_1):
    secondary_1.base_url = 'https://serveur2.exemple.fr'
    secondary_1.save()
    return secondary_1


# ── _hote_du_noeud ───────────────────────────────────────────────────────────

@pytest.mark.parametrize('valeur,attendu', [
    ('https://serveur2.exemple.fr', 'serveur2.exemple.fr'),
    ('https://serveur2.exemple.fr/', 'serveur2.exemple.fr'),
    ('http://Serveur2.Exemple.FR:9000/ha/', 'serveur2.exemple.fr'),
    ('serveur2.exemple.fr', 'serveur2.exemple.fr'),
    ('', ''),
])
def test_hote_du_noeud_extrait_le_sous_domaine(valeur, attendu, secondary_1):
    secondary_1.base_url = valeur
    assert _hote_du_noeud(secondary_1) == attendu


# ── Repointage de l'indirection ──────────────────────────────────────────────

def test_bascule_repointe_l_indirection_vers_le_noeud_cible(
    primary_node, secondary_avec_sous_domaine, ha_cloudflare, faux_cloudflare,
):
    event = run_manual_failover_to_node(target_node=secondary_avec_sous_domaine)

    assert faux_cloudflare.patchs == [
        ('zone-1', 'rec-actif', {'content': 'serveur2.exemple.fr'}),
    ]
    dns = event.result_payload['dns']
    assert dns['changed'] is True
    assert dns['previous'] == 'serveur1.exemple.fr'
    assert dns['content'] == 'serveur2.exemple.fr'


def test_bascule_ne_modifie_pas_les_domaines_publics(
    primary_node, secondary_avec_sous_domaine, ha_cloudflare, monkeypatch,
):
    """Le gain du modèle d'indirection : un seul appel, quel que soit le parc."""
    faux = _FauxCloudflare(enregistrements=[
        {'id': 'rec-actif', 'type': 'CNAME', 'name': 'actif.exemple.fr',
         'content': 'serveur1.exemple.fr'},
        {'id': 'rec-erp', 'type': 'CNAME', 'name': 'erp.exemple.fr',
         'content': 'actif.exemple.fr'},
        {'id': 'rec-siecle', 'type': 'CNAME', 'name': 'siecle.exemple.fr',
         'content': 'actif.exemple.fr'},
        {'id': 'rec-client', 'type': 'CNAME', 'name': 'client-x.exemple.fr',
         'content': 'actif.exemple.fr'},
    ])
    monkeypatch.setattr(
        'apps.domain_diagnostics.cloudflare.CloudflareClient', lambda *a, **k: faux,
    )
    run_manual_failover_to_node(target_node=secondary_avec_sous_domaine)

    assert [p[1] for p in faux.patchs] == ['rec-actif']
    for rec in faux.enregistrements:
        if rec['id'] != 'rec-actif':
            assert rec['content'] == 'actif.exemple.fr'


def test_bascule_est_idempotente_si_deja_pointe(
    primary_node, secondary_avec_sous_domaine, ha_cloudflare, monkeypatch,
):
    faux = _FauxCloudflare(enregistrements=[
        {'id': 'rec-actif', 'type': 'CNAME', 'name': 'actif.exemple.fr',
         'content': 'serveur2.exemple.fr'},
    ])
    monkeypatch.setattr(
        'apps.domain_diagnostics.cloudflare.CloudflareClient', lambda *a, **k: faux,
    )
    event = run_manual_failover_to_node(target_node=secondary_avec_sous_domaine)

    assert faux.patchs == []
    assert event.result_payload['dns']['changed'] is False


def test_nom_complet_accepte_un_fqdn_sans_identifiant_de_zone(
    primary_node, secondary_avec_sous_domaine, ha_settings, faux_cloudflare,
):
    ha_settings.cloudflare_failover_enabled = True
    ha_settings.cloudflare_zone_id = ''
    ha_settings.cloudflare_record_name = 'actif.exemple.fr'
    ha_settings.save()

    run_manual_failover_to_node(target_node=secondary_avec_sous_domaine)
    assert faux_cloudflare.patchs[0][0] == 'zone-1'


def test_enregistrement_a_recoit_l_ip_publique(
    primary_node, secondary_1, ha_cloudflare, monkeypatch,
):
    """Sans tunnel devant, l'indirection est un A : un nom d'hôte n'y a pas sa place."""
    secondary_1.base_url = 'https://serveur2.exemple.fr'
    secondary_1.public_ip = '203.0.113.7'
    secondary_1.save()
    faux = _FauxCloudflare(enregistrements=[
        {'id': 'rec-actif', 'type': 'A', 'name': 'actif.exemple.fr',
         'content': '203.0.113.1'},
    ])
    monkeypatch.setattr(
        'apps.domain_diagnostics.cloudflare.CloudflareClient', lambda *a, **k: faux,
    )
    run_manual_failover_to_node(target_node=secondary_1)
    assert faux.patchs == [('zone-1', 'rec-actif', {'content': '203.0.113.7'})]


def test_cloudflare_desactive_laisse_la_bascule_passer(
    primary_node, secondary_1, ha_settings,
):
    event = run_manual_failover_to_node(target_node=secondary_1)
    assert event.status == 'success'
    assert event.result_payload['dns']['skipped'] is True


# ── Échecs de redirection : la bascule doit être refusée ─────────────────────

def test_bascule_refusee_si_noeud_sans_sous_domaine(
    primary_node, secondary_1, ha_cloudflare, faux_cloudflare,
):
    with pytest.raises(FailoverTrafficError, match="URL de base"):
        run_manual_failover_to_node(target_node=secondary_1)


def test_bascule_refuse_un_cname_sur_lui_meme(
    primary_node, secondary_1, ha_cloudflare, faux_cloudflare,
):
    secondary_1.base_url = 'https://actif.exemple.fr'
    secondary_1.save()
    with pytest.raises(FailoverTrafficError, match='lui-même'):
        run_manual_failover_to_node(target_node=secondary_1)


def test_bascule_refusee_si_enregistrement_absent(
    primary_node, secondary_avec_sous_domaine, ha_cloudflare, monkeypatch,
):
    faux = _FauxCloudflare(enregistrements=[])
    monkeypatch.setattr(
        'apps.domain_diagnostics.cloudflare.CloudflareClient', lambda *a, **k: faux,
    )
    with pytest.raises(FailoverTrafficError, match='Aucun enregistrement'):
        run_manual_failover_to_node(target_node=secondary_avec_sous_domaine)


def test_noeud_actif_inchange_quand_la_redirection_echoue(
    primary_node, secondary_1, ha_cloudflare, faux_cloudflare,
):
    """Propriété de sûreté : mieux vaut refuser que déclarer actif un nœud
    que personne ne joint. Les domaines pointent encore vers l'ancien."""
    with pytest.raises(FailoverTrafficError):
        run_manual_failover_to_node(target_node=secondary_1)

    primary_node.refresh_from_db()
    secondary_1.refresh_from_db()
    assert primary_node.is_current_active is True
    assert secondary_1.is_current_active is False


def test_echec_de_redirection_est_journalise(
    primary_node, secondary_1, ha_cloudflare, faux_cloudflare,
):
    """Possible seulement depuis que la trace est écrite hors transaction
    englobante : l'ancienne version la perdait au rollback."""
    with pytest.raises(FailoverTrafficError):
        run_manual_failover_to_node(target_node=secondary_1, reason='Test trace')

    event = OrionHAFailoverEvent.objects.latest('started_at')
    assert event.status == 'failed'
    assert event.to_node == secondary_1
    assert event.from_node == primary_node
    assert 'URL de base' in event.error_message
    assert event.steps == [
        'Validation du serveur cible',
        'Promotion base de données',
        'Redirection du trafic (DNS Cloudflare)',
    ]


def test_type_evenement_est_personnalisable(primary_node, secondary_1, ha_settings):
    """La bascule automatique doit pouvoir se distinguer d'une bascule manuelle."""
    event = run_manual_failover_to_node(
        target_node=secondary_1, event_type='automatic_failover',
    )
    assert event.event_type == 'automatic_failover'


# ── Préséance et retour de main ──────────────────────────────────────────────
# Le rang de préséance (priority) est indépendant du rôle courant : le rôle se
# déplace à chaque bascule, le rang est une décision d'exploitation.

from datetime import timedelta

from apps.high_availability.takeover import (
    evaluate_returning_node,
    precedence_order,
    preferred_primary,
    run_failback_to_node,
)


def _rendre_revenant(node, stable_depuis=3600, read_only=True):
    """Place un serveur dans l'état d'un revenant en bon état et stable."""
    node.status = 'healthy'
    node.healthy_since = timezone.now() - timedelta(seconds=stable_depuis)
    node.last_health_payload = {'read_only': read_only}
    node.save()
    return node


# ── Rétrogradation : sans elle, aucun retour n'est possible ──────────────────

def test_bascule_retrograde_l_ancien_principal(primary_node, secondary_1, ha_settings):
    run_manual_failover_to_node(target_node=secondary_1)

    primary_node.refresh_from_db()
    assert primary_node.role == 'secondary'
    assert primary_node.is_current_active is False
    assert primary_node.status == 'passive'
    # Il a déjà porté la main : rien ne justifie de l'écarter pour la suite.
    assert primary_node.is_failover_target is True


def test_le_rang_de_preseance_survit_a_la_bascule(primary_node, secondary_1, ha_settings):
    run_manual_failover_to_node(target_node=secondary_1)

    primary_node.refresh_from_db()
    secondary_1.refresh_from_db()
    assert primary_node.priority == 1
    assert secondary_1.priority == 2
    assert preferred_primary().node_id == 'orion-primary'


def test_un_serveur_hors_ligne_reste_hors_ligne_apres_bascule(
    primary_node, secondary_1, ha_settings,
):
    """Le repasser en « passif » laisserait croire qu'il est disponible."""
    primary_node.status = 'down'
    primary_node.save()
    run_manual_failover_to_node(target_node=secondary_1)

    primary_node.refresh_from_db()
    assert primary_node.status == 'down'


def test_ancien_principal_redevient_cible_eligible(primary_node, secondary_1, ha_settings):
    run_manual_failover_to_node(target_node=secondary_1)
    primary_node.refresh_from_db()
    _rendre_revenant(primary_node)

    assert primary_node.can_be_failover_target is True
    assert validate_failover_target(primary_node) is True


# ── Ordre de préséance ───────────────────────────────────────────────────────

def test_preseance_classee_par_rang(primary_node, secondary_1, secondary_2, ha_settings):
    ordre = [ligne['node'].node_id for ligne in precedence_order()]
    assert ordre == ['orion-primary', 'orion-secondary-1', 'orion-secondary-2']


def test_preseance_explique_pourquoi_un_serveur_est_ecarte(
    primary_node, secondary_1, secondary_2, ha_settings,
):
    secondary_1.is_failover_target = False
    secondary_1.save()
    secondary_2.status = 'down'
    secondary_2.save()

    par_id = {l['node'].node_id: l for l in precedence_order()}
    assert par_id['orion-primary']['is_active'] is True
    assert par_id['orion-primary']['eligible'] is False
    assert 'actif' in par_id['orion-primary']['reason'].lower()
    assert par_id['orion-secondary-1']['eligible'] is False
    assert 'recevoir la main' in par_id['orion-secondary-1']['reason']
    assert par_id['orion-secondary-2']['eligible'] is False
    assert 'Hors ligne' in par_id['orion-secondary-2']['reason']


def test_preseance_signale_le_retard_de_replication(
    primary_node, secondary_1, ha_settings,
):
    ha_settings.max_allowed_replication_lag_seconds = 10
    ha_settings.save()
    secondary_1.replication_lag_seconds = 45
    secondary_1.save()

    ligne = [l for l in precedence_order() if l['node'].pk == secondary_1.pk][0]
    assert ligne['eligible'] is False
    assert '45' in ligne['reason']


def test_promotion_automatique_interdite_ecarte_le_serveur(
    primary_node, secondary_1, secondary_2, ha_settings,
):
    """Ce drapeau existait sans être lu : le décocher ne protégeait de rien."""
    secondary_1.allow_auto_failover = False
    secondary_1.save()

    assert services.select_best_failover_target().node_id == 'orion-secondary-1'
    assert services.select_best_failover_target(automatic=True).node_id == 'orion-secondary-2'


# ── healthy_since : la stabilité, pas la fraîcheur du battement ──────────────

def test_healthy_since_pose_au_premier_bon_etat(secondary_1):
    assert secondary_1.healthy_since is None
    services.update_node_from_health(secondary_1, {'status': 'healthy'})
    assert secondary_1.healthy_since is not None


def test_healthy_since_non_ecrase_aux_bilans_suivants(secondary_1):
    services.update_node_from_health(secondary_1, {'status': 'healthy'})
    premier = secondary_1.healthy_since
    services.update_node_from_health(secondary_1, {'status': 'healthy'})
    assert secondary_1.healthy_since == premier


def test_healthy_since_remis_a_zero_quand_le_serveur_tombe(secondary_1):
    services.update_node_from_health(secondary_1, {'status': 'healthy'})
    assert secondary_1.healthy_since is not None
    services.update_node_from_health(secondary_1, {'status': 'down'})
    assert secondary_1.healthy_since is None


# ── Politique de retour ──────────────────────────────────────────────────────

def test_retour_jamais_laisse_la_main_au_promu(primary_node, secondary_1, ha_settings):
    ha_settings.failback_policy = 'never'
    ha_settings.save()
    run_manual_failover_to_node(target_node=secondary_1)
    primary_node.refresh_from_db()
    _rendre_revenant(primary_node)

    decision = evaluate_returning_node(primary_node)
    assert decision['failback'] is False
    assert decision['proposed'] is False
    assert 'jamais' in decision['reason']


def test_retour_manuel_propose_sans_agir(primary_node, secondary_1, ha_settings):
    ha_settings.failback_policy = 'manual'
    ha_settings.save()
    run_manual_failover_to_node(target_node=secondary_1)
    primary_node.refresh_from_db()
    _rendre_revenant(primary_node)

    decision = evaluate_returning_node(primary_node)
    assert decision['proposed'] is True
    assert decision['failback'] is False
    secondary_1.refresh_from_db()
    assert secondary_1.is_current_active is True


def test_retour_automatique_rend_la_main(primary_node, secondary_1, ha_settings):
    ha_settings.failback_policy = 'automatic'
    ha_settings.save()
    run_manual_failover_to_node(target_node=secondary_1)
    primary_node.refresh_from_db()
    _rendre_revenant(primary_node)

    decision = evaluate_returning_node(primary_node)
    assert decision['failback'] is True

    primary_node.refresh_from_db()
    secondary_1.refresh_from_db()
    assert primary_node.is_current_active is True
    assert primary_node.role == 'primary'
    assert secondary_1.is_current_active is False
    assert secondary_1.role == 'secondary'


def test_retour_refuse_a_un_serveur_moins_bien_classe(
    primary_node, secondary_1, secondary_2, ha_settings,
):
    ha_settings.failback_policy = 'automatic'
    ha_settings.save()
    run_manual_failover_to_node(target_node=secondary_1)
    secondary_2.refresh_from_db()
    _rendre_revenant(secondary_2)

    decision = evaluate_returning_node(secondary_2)
    assert decision['failback'] is False
    assert 'moins bien classé' in decision['reason']


def test_retour_refuse_a_un_serveur_qui_oscille(primary_node, secondary_1, ha_settings):
    ha_settings.failback_policy = 'automatic'
    ha_settings.failback_min_stable_seconds = 600
    ha_settings.save()
    run_manual_failover_to_node(target_node=secondary_1)
    primary_node.refresh_from_db()
    _rendre_revenant(primary_node, stable_depuis=30)

    decision = evaluate_returning_node(primary_node)
    assert decision['failback'] is False
    assert 'stable depuis 30' in decision['reason']


def test_retour_refuse_si_la_replication_est_en_retard(
    primary_node, secondary_1, ha_settings,
):
    ha_settings.failback_policy = 'automatic'
    ha_settings.max_allowed_replication_lag_seconds = 10
    ha_settings.save()
    run_manual_failover_to_node(target_node=secondary_1)
    primary_node.refresh_from_db()
    _rendre_revenant(primary_node)
    primary_node.replication_lag_seconds = 120
    primary_node.save()

    decision = evaluate_returning_node(primary_node)
    assert decision['failback'] is False
    assert '120' in decision['reason']


def test_revenant_inscriptible_est_signale_comme_divergence(
    primary_node, secondary_1, ha_settings,
):
    """Deux bases acceptant des écritures ne se fusionnent pas : on alerte,
    on ne bascule jamais."""
    ha_settings.failback_policy = 'automatic'
    ha_settings.save()
    run_manual_failover_to_node(target_node=secondary_1)
    primary_node.refresh_from_db()
    _rendre_revenant(primary_node, read_only=False)

    decision = evaluate_returning_node(primary_node)
    assert decision['split_brain_suspected'] is True
    assert decision['failback'] is False
    assert 'lecture seule' in decision['reason']

    secondary_1.refresh_from_db()
    assert secondary_1.is_current_active is True


def test_etat_inconnu_n_est_pas_tenu_pour_inscriptible(secondary_1):
    """« read_only » absent du bilan ne doit pas valoir « inscriptible »."""
    secondary_1.last_health_payload = {}
    assert secondary_1.claims_to_be_writable is False


def test_retour_trace_comme_un_retour_et_non_une_bascule(
    primary_node, secondary_1, ha_settings,
):
    run_manual_failover_to_node(target_node=secondary_1)
    primary_node.refresh_from_db()
    _rendre_revenant(primary_node)

    event = run_failback_to_node(target_node=primary_node)
    assert event.event_type == 'manual_failback'
    assert event.status == 'success'
    assert event.to_node == primary_node


# ── Raccordement d'un serveur et diagnostic de liaison ──────────────────────
# Six causes très différentes donnent le même symptôme — « le serveur ne
# répond pas ». Le diagnostic doit les distinguer, et surtout proposer le bon
# remède : c'est toute sa raison d'être.

import requests

from apps.high_availability.connection import (
    chemin_ignore,
    diagnose_node_connection,
    normaliser_base_url,
    prochain_rang_libre,
)


class _FausseReponse:
    def __init__(self, status_code=200, donnees=None, texte=''):
        self.status_code = status_code
        self._donnees = donnees
        self._texte = texte

    def json(self):
        if self._donnees is None:
            raise ValueError('pas du JSON')
        return self._donnees


def _etape(resultat, nom):
    for etape in resultat['steps']:
        if etape['name'] == nom:
            return etape
    return None


SANTE_PUBLIQUE = {'status': 'healthy', 'node_id': 'orion-secondary-9', 'role': 'secondary'}
SANTE_PRIVEE = {
    'status': 'healthy', 'node_id': 'orion-secondary-9', 'role': 'secondary',
    'database': 'ok', 'database_role': 'replica', 'read_only': True,
    'replication_lag_seconds': 2,
}


@pytest.fixture
def dns_resolvable(monkeypatch):
    monkeypatch.setattr(
        'apps.high_availability.connection.socket.getaddrinfo',
        lambda *a, **k: [('AF_INET', None, None, '', ('203.0.113.9', 0))],
    )


@pytest.fixture
def secret_pose(settings):
    settings.ORION_HA_SECRET = 'secret-partage-de-test'
    return settings


def _brancher_http(monkeypatch, par_chemin):
    """Remplace requests.get par une table chemin -> réponse (ou exception)."""
    appels = []

    def faux_get(url, **kwargs):
        appels.append((url, kwargs))
        for fragment, reponse in par_chemin.items():
            if fragment in url:
                if isinstance(reponse, Exception):
                    raise reponse
                return reponse
        raise AssertionError(f'URL non prévue par le test : {url}')

    monkeypatch.setattr('apps.high_availability.connection.requests.get', faux_get)
    return appels


# ── normaliser_base_url ──────────────────────────────────────────────────────

@pytest.mark.parametrize('brut,url,hote', [
    ('serveur2.exemple.fr', 'https://serveur2.exemple.fr', 'serveur2.exemple.fr'),
    ('https://serveur2.exemple.fr/', 'https://serveur2.exemple.fr', 'serveur2.exemple.fr'),
    ('http://Serveur2.Exemple.FR:9000', 'http://Serveur2.Exemple.FR:9000', 'serveur2.exemple.fr'),
    # URL d'une page de l'ERP, collee depuis la barre d'adresse : le chemin
    # doit etre ecarte, sinon la sonde interroge
    # .../orion-admin/ha/nodes/2/ha/public-health/ et renvoie un 404 que le
    # diagnostic imputait a tort a la version du serveur distant.
    ('https://login.exemple.fr/orion-admin/ha/nodes/2',
     'https://login.exemple.fr', 'login.exemple.fr'),
    ('https://login.exemple.fr/orion-admin/ha/nodes/2/?x=1',
     'https://login.exemple.fr', 'login.exemple.fr'),
    ('', '', ''),
])
def test_normaliser_base_url(brut, url, hote):
    assert normaliser_base_url(brut) == (url, hote)


@pytest.mark.parametrize('brut,attendu', [
    ('serveur2.exemple.fr', ''),
    ('https://serveur2.exemple.fr', ''),
    ('https://serveur2.exemple.fr/', ''),
    ('https://login.exemple.fr/orion-admin/ha/nodes/2', '/orion-admin/ha/nodes/2'),
    ('https://login.exemple.fr/a/b/?x=1', '/a/b?x=1'),
])
def test_chemin_ignore(brut, attendu):
    assert chemin_ignore(brut) == attendu


def test_url_de_page_sonde_la_bonne_adresse_et_le_signale(
    db, monkeypatch, dns_resolvable, secret_pose,
):
    """Le chemin colle est ecarte, la sonde atteint la bonne URL, et
    l'exploitant est averti au lieu d'etre envoye sur une fausse piste."""
    appels = _brancher_http(monkeypatch, {
        '/ha/public-health/': _FausseReponse(200, SANTE_PUBLIQUE),
        '/ha/health/': _FausseReponse(200, SANTE_PRIVEE),
    })
    resultat = diagnose_node_connection(
        'https://login.exemple.fr/orion-admin/ha/nodes/2'
    )

    assert appels[0][0] == 'https://login.exemple.fr/ha/public-health/'
    assert resultat['identity_ok'] is True
    etape = _etape(resultat, 'Adresse du serveur')
    assert etape['ok'] is True
    assert '/orion-admin/ha/nodes/2' in etape['remedy']
    assert 'pas celle d' in etape['remedy']


def test_adresse_vide_est_refusee_sans_appel_reseau(db):
    resultat = diagnose_node_connection('')
    assert resultat['ok'] is False
    assert resultat['identity_ok'] is False
    assert _etape(resultat, 'Adresse du serveur')['ok'] is False


# ── Liaison complète ─────────────────────────────────────────────────────────

def test_liaison_complete_releve_l_identifiant(
    db, monkeypatch, dns_resolvable, secret_pose,
):
    """L'identifiant vient du serveur, jamais d'une saisie : c'est lui que
    compare la protection en écriture."""
    _brancher_http(monkeypatch, {
        '/ha/public-health/': _FausseReponse(200, SANTE_PUBLIQUE),
        '/ha/health/': _FausseReponse(200, SANTE_PRIVEE),
    })
    resultat = diagnose_node_connection('serveur2.exemple.fr')

    assert resultat['ok'] is True
    assert resultat['identity_ok'] is True
    assert resultat['node_id'] == 'orion-secondary-9'
    assert resultat['payload']['replication_lag_seconds'] == 2
    assert all(e['ok'] for e in resultat['steps'])


def test_le_secret_local_est_envoye_en_entete(
    db, monkeypatch, dns_resolvable, secret_pose,
):
    appels = _brancher_http(monkeypatch, {
        '/ha/public-health/': _FausseReponse(200, SANTE_PUBLIQUE),
        '/ha/health/': _FausseReponse(200, SANTE_PRIVEE),
    })
    diagnose_node_connection('serveur2.exemple.fr')

    prive = [a for a in appels if '/ha/health/' in a[0]][0]
    assert prive[1]['headers']['X-Orion-HA-Secret'] == 'secret-partage-de-test'


# ── Les six causes, distinguées ──────────────────────────────────────────────

def test_nom_qui_ne_resout_pas(db, monkeypatch):
    import socket as vrai_socket
    monkeypatch.setattr(
        'apps.high_availability.connection.socket.getaddrinfo',
        lambda *a, **k: (_ for _ in ()).throw(vrai_socket.gaierror('introuvable')),
    )
    resultat = diagnose_node_connection('serveur-inexistant.exemple.fr')
    etape = _etape(resultat, 'Résolution DNS')
    assert etape['ok'] is False
    assert 'orthographe' in etape['remedy']


def test_connexion_refusee_pointe_vers_un_service_arrete(db, monkeypatch, dns_resolvable):
    _brancher_http(monkeypatch, {
        '/ha/public-health/': requests.exceptions.ConnectionError('refused'),
    })
    etape = _etape(diagnose_node_connection('serveur2.exemple.fr'), 'Joignabilité')
    assert etape['ok'] is False
    assert 'orion-backend' in etape['remedy']


def test_delai_depasse_pointe_vers_un_pare_feu(db, monkeypatch, dns_resolvable):
    _brancher_http(monkeypatch, {
        '/ha/public-health/': requests.exceptions.ConnectTimeout('timeout'),
    })
    etape = _etape(diagnose_node_connection('serveur2.exemple.fr'), 'Joignabilité')
    assert etape['ok'] is False
    assert 'pare-feu' in etape['remedy']


def test_certificat_invalide_est_nomme(db, monkeypatch, dns_resolvable):
    _brancher_http(monkeypatch, {
        '/ha/public-health/': requests.exceptions.SSLError('bad cert'),
    })
    etape = _etape(diagnose_node_connection('serveur2.exemple.fr'), 'Joignabilité')
    assert etape['ok'] is False
    assert 'Certificat' in etape['detail']


def test_400_renvoie_vers_allowed_hosts(db, monkeypatch, dns_resolvable):
    """Le piège documenté : le serveur rejette son propre nom de domaine."""
    _brancher_http(monkeypatch, {
        '/ha/public-health/': _FausseReponse(400),
    })
    etape = _etape(diagnose_node_connection('serveur2.exemple.fr'), 'Joignabilité')
    assert etape['ok'] is False
    assert 'ORION_NODE_DOMAIN' in etape['remedy']
    assert 'ALLOWED_HOSTS' in etape['remedy']


def test_404_signale_que_ce_n_est_pas_un_orion(db, monkeypatch, dns_resolvable):
    _brancher_http(monkeypatch, {'/ha/public-health/': _FausseReponse(404)})
    etape = _etape(diagnose_node_connection('serveur2.exemple.fr'), 'Joignabilité')
    assert etape['ok'] is False
    assert 'mettez-le à jour' in etape['remedy']


def test_502_distingue_le_proxy_de_l_application(db, monkeypatch, dns_resolvable):
    _brancher_http(monkeypatch, {'/ha/public-health/': _FausseReponse(502)})
    etape = _etape(diagnose_node_connection('serveur2.exemple.fr'), 'Joignabilité')
    assert etape['ok'] is False
    assert 'Nginx est debout' in etape['remedy']


def test_530_renvoie_au_connecteur_cloudflare(db, monkeypatch, dns_resolvable):
    _brancher_http(monkeypatch, {'/ha/public-health/': _FausseReponse(530)})
    etape = _etape(diagnose_node_connection('serveur2.exemple.fr'), 'Joignabilité')
    assert etape['ok'] is False
    assert 'cloudflared' in etape['remedy']


def test_reponse_non_json_signale_un_autre_service(db, monkeypatch, dns_resolvable):
    _brancher_http(monkeypatch, {
        '/ha/public-health/': _FausseReponse(200, donnees=None, texte='<html>'),
    })
    etape = _etape(diagnose_node_connection('serveur2.exemple.fr'), 'Joignabilité')
    assert etape['ok'] is False
    assert 'JSON' in etape['detail']


# ── Secret partagé ───────────────────────────────────────────────────────────

def test_secret_different_est_nomme_precisement(
    db, monkeypatch, dns_resolvable, secret_pose,
):
    _brancher_http(monkeypatch, {
        '/ha/public-health/': _FausseReponse(200, SANTE_PUBLIQUE),
        '/ha/health/': _FausseReponse(403),
    })
    resultat = diagnose_node_connection('serveur2.exemple.fr')
    etape = _etape(resultat, 'Secret partagé')
    assert etape['ok'] is False
    assert 'ORION_HA_SECRET' in etape['remedy']
    # L'identité reste exploitable : le raccordement demeure possible.
    assert resultat['identity_ok'] is True
    assert resultat['ok'] is False


def test_secret_local_absent_est_signale_cote_local(
    db, monkeypatch, dns_resolvable, settings,
):
    settings.ORION_HA_SECRET = 'CHANGE_ME'
    _brancher_http(monkeypatch, {
        '/ha/public-health/': _FausseReponse(200, SANTE_PUBLIQUE),
    })
    etape = _etape(diagnose_node_connection('serveur2.exemple.fr'), 'Secret partagé')
    assert etape['ok'] is False
    assert 'MÊME valeur' in etape['remedy']


# ── Identité ─────────────────────────────────────────────────────────────────

def test_identifiant_deja_pris_est_refuse(
    db, monkeypatch, dns_resolvable, secret_pose, secondary_1,
):
    """Deux serveurs de même identifiant : la protection en écriture ne
    saurait plus lequel a la main."""
    _brancher_http(monkeypatch, {
        '/ha/public-health/': _FausseReponse(200, {**SANTE_PUBLIQUE, 'node_id': secondary_1.node_id}),
        '/ha/health/': _FausseReponse(200, SANTE_PRIVEE),
    })
    resultat = diagnose_node_connection('serveur2.exemple.fr')
    etape = _etape(resultat, 'Identité du serveur')
    assert etape['ok'] is False
    assert resultat['identity_ok'] is False
    assert secondary_1.name in etape['detail']


def test_tester_un_serveur_deja_enregistre_ne_signale_pas_son_propre_id(
    db, monkeypatch, dns_resolvable, secret_pose, secondary_1,
):
    secondary_1.base_url = 'https://serveur2.exemple.fr'
    secondary_1.save()
    _brancher_http(monkeypatch, {
        '/ha/public-health/': _FausseReponse(200, {**SANTE_PUBLIQUE, 'node_id': secondary_1.node_id}),
        '/ha/health/': _FausseReponse(200, SANTE_PRIVEE),
    })
    resultat = diagnose_node_connection(secondary_1.base_url, node=secondary_1)
    assert resultat['identity_ok'] is True


def test_serveur_sans_identifiant_renvoie_vers_orion_node_id(
    db, monkeypatch, dns_resolvable, secret_pose,
):
    _brancher_http(monkeypatch, {
        '/ha/public-health/': _FausseReponse(200, {'status': 'healthy', 'role': 'secondary'}),
        '/ha/health/': _FausseReponse(200, SANTE_PRIVEE),
    })
    etape = _etape(diagnose_node_connection('serveur2.exemple.fr'), 'Identité du serveur')
    assert etape['ok'] is False
    assert 'ORION_NODE_ID' in etape['remedy']


# ── État de la base ──────────────────────────────────────────────────────────

def test_secondaire_inscriptible_est_signale(
    db, monkeypatch, dns_resolvable, secret_pose,
):
    _brancher_http(monkeypatch, {
        '/ha/public-health/': _FausseReponse(200, SANTE_PUBLIQUE),
        '/ha/health/': _FausseReponse(200, {**SANTE_PRIVEE, 'read_only': False}),
    })
    resultat = diagnose_node_connection('serveur2.exemple.fr')
    etape = _etape(resultat, 'Base de données')
    assert etape['ok'] is False
    assert 'diverger' in etape['remedy']
    # Grave, mais la fiche du serveur reste enregistrable.
    assert resultat['identity_ok'] is True


def test_base_injoignable_est_signalee(db, monkeypatch, dns_resolvable, secret_pose):
    _brancher_http(monkeypatch, {
        '/ha/public-health/': _FausseReponse(200, SANTE_PUBLIQUE),
        '/ha/health/': _FausseReponse(200, {**SANTE_PRIVEE, 'database': 'error'}),
    })
    etape = _etape(diagnose_node_connection('serveur2.exemple.fr'), 'Base de données')
    assert etape['ok'] is False
    assert 'MySQL' in etape['remedy']


# ── prochain_rang_libre ──────────────────────────────────────────────────────

def test_prochain_rang_sur_cluster_vide(db):
    assert prochain_rang_libre() == 1


def test_prochain_rang_suit_le_dernier(primary_node, secondary_1, secondary_2):
    assert prochain_rang_libre() == 4


# ── Vues de raccordement ─────────────────────────────────────────────────────

@pytest.fixture
def entreprise(db):
    """Une Company doit exister, sinon SetupRequiredMiddleware renvoie toute
    requête vers /setup/ — cause des 302 qui rendaient les tests de vues HA
    inopérants : ils affirmaient un 200 et recevaient une redirection."""
    from apps.core.models import Company
    return Company.objects.create(name='Entreprise de test')


def test_page_de_raccordement_accessible(client, superuser, entreprise):
    client.force_login(superuser)
    reponse = client.get('/orion-admin/ha/nodes/connecter/')
    assert reponse.status_code == 200
    assert 'Raccorder' in reponse.content.decode()


def test_page_des_serveurs_propose_le_raccordement(
    client, superuser, entreprise, primary_node,
):
    client.force_login(superuser)
    corps = client.get('/orion-admin/ha/nodes/').content.decode()
    assert '/orion-admin/ha/nodes/connecter/' in corps


def test_test_de_liaison_ne_cree_aucun_serveur(
    client, superuser, entreprise, monkeypatch, dns_resolvable, secret_pose,
):
    _brancher_http(monkeypatch, {
        '/ha/public-health/': _FausseReponse(200, SANTE_PUBLIQUE),
        '/ha/health/': _FausseReponse(200, SANTE_PRIVEE),
    })
    client.force_login(superuser)
    reponse = client.post('/orion-admin/ha/nodes/connecter/', {
        'action': 'test',
        'base_url': 'serveur2.exemple.fr',
        'name': 'Serveur 2',
        'priority': 2,
    })
    assert reponse.status_code == 200
    assert OrionHANode.objects.count() == 0
    assert 'orion-secondary-9' in reponse.content.decode()


def test_raccordement_cree_le_serveur_avec_l_identifiant_distant(
    client, superuser, entreprise, monkeypatch, dns_resolvable, secret_pose,
):
    _brancher_http(monkeypatch, {
        '/ha/public-health/': _FausseReponse(200, SANTE_PUBLIQUE),
        '/ha/health/': _FausseReponse(200, SANTE_PRIVEE),
    })
    client.force_login(superuser)
    reponse = client.post('/orion-admin/ha/nodes/connecter/', {
        'action': 'connect',
        'base_url': 'serveur2.exemple.fr',
        'name': 'Serveur 2',
        'priority': 2,
        'is_failover_target': 'on',
        'allow_auto_failover': 'on',
    })
    assert reponse.status_code == 302

    node = OrionHANode.objects.get()
    assert node.node_id == 'orion-secondary-9'
    assert node.name == 'Serveur 2'
    assert node.base_url == 'https://serveur2.exemple.fr'
    assert node.role == 'secondary'
    assert node.priority == 2
    assert node.is_current_active is False
    assert node.is_failover_target is True
    # Le bilan de santé obtenu pendant le test est repris : pas de serveur
    # tout neuf affiché « inconnu » alors qu'on vient de le joindre.
    assert node.replication_lag_seconds == 2
    assert node.healthy_since is not None


def test_raccordement_refuse_si_l_identite_est_douteuse(
    client, superuser, entreprise, monkeypatch, dns_resolvable, secret_pose,
):
    _brancher_http(monkeypatch, {
        '/ha/public-health/': _FausseReponse(400),
    })
    client.force_login(superuser)
    reponse = client.post('/orion-admin/ha/nodes/connecter/', {
        'action': 'connect',
        'base_url': 'serveur2.exemple.fr',
        'name': 'Serveur 2',
        'priority': 2,
    })
    assert reponse.status_code == 200
    assert OrionHANode.objects.count() == 0
    assert 'ORION_NODE_DOMAIN' in reponse.content.decode()


def test_test_depuis_la_fiche_d_un_serveur(
    client, superuser, entreprise, secondary_1, monkeypatch, dns_resolvable, secret_pose,
):
    secondary_1.base_url = 'https://serveur2.exemple.fr'
    secondary_1.save()
    _brancher_http(monkeypatch, {
        '/ha/public-health/': _FausseReponse(200, {**SANTE_PUBLIQUE, 'node_id': secondary_1.node_id}),
        '/ha/health/': _FausseReponse(200, SANTE_PRIVEE),
    })
    client.force_login(superuser)
    reponse = client.post(f'/orion-admin/ha/nodes/{secondary_1.pk}/', {'action': 'test'})

    assert reponse.status_code == 200
    assert 'Secret partagé' in reponse.content.decode()
    # Un test ne modifie rien.
    secondary_1.refresh_from_db()
    assert secondary_1.base_url == 'https://serveur2.exemple.fr'


# ── Grappe par convention de nommage ────────────────────────────────────────
# « serveur2.exemple.fr » EST le serveur de rang 2 : adresse et rang se
# déduisent l'un de l'autre et ne peuvent plus se contredire.

from apps.high_availability.cluster import (
    adresse_de_ce_serveur,
    adresse_du_rang,
    explorer_grappe,
    hote_du_rang,
    raccorder_grappe,
    verifier_reciprocite,
)


@pytest.fixture
def grappe(ha_settings):
    ha_settings.cluster_base_domain = 'exemple.fr'
    ha_settings.node_name_pattern = 'serveur{n}'
    ha_settings.cluster_max_nodes = 3
    ha_settings.cluster_use_https = True
    ha_settings.save()
    return ha_settings


# ── Déduction des adresses ───────────────────────────────────────────────────

def test_hote_deduit_du_rang(grappe):
    assert hote_du_rang(grappe, 1) == 'serveur1.exemple.fr'
    assert hote_du_rang(grappe, 2) == 'serveur2.exemple.fr'
    assert adresse_du_rang(grappe, 2) == 'https://serveur2.exemple.fr'


def test_schema_http_pour_une_grappe_locale(grappe):
    grappe.cluster_use_https = False
    grappe.save()
    assert adresse_du_rang(grappe, 2) == 'http://serveur2.exemple.fr'


def test_motif_personnalise(grappe):
    grappe.node_name_pattern = 'orion-n{n}'
    grappe.save()
    assert hote_du_rang(grappe, 3) == 'orion-n3.exemple.fr'


def test_aucune_adresse_sans_domaine(ha_settings):
    assert hote_du_rang(ha_settings, 1) == ''
    assert adresse_du_rang(ha_settings, 1) == ''


def test_motif_sans_marqueur_ne_produit_rien(grappe):
    """Sans {n}, tous les rangs donneraient le même hôte."""
    grappe.node_name_pattern = 'serveur'
    grappe.save()
    assert hote_du_rang(grappe, 2) == ''


def test_adresse_de_ce_serveur_suit_son_rang(grappe, settings):
    settings.ORION_NODE_PRIORITY = 2
    assert adresse_de_ce_serveur(grappe) == 'https://serveur2.exemple.fr'


# ── Validation réciproque ────────────────────────────────────────────────────

def _brancher_post(monkeypatch, reponse):
    appels = []

    def faux_post(url, **kwargs):
        appels.append((url, kwargs))
        if isinstance(reponse, Exception):
            raise reponse
        return reponse

    monkeypatch.setattr('apps.high_availability.cluster.requests.post', faux_post)
    return appels


def test_reciprocite_validee(db, monkeypatch, secret_pose):
    appels = _brancher_post(monkeypatch, _FausseReponse(200, {
        'source_reachable': True, 'secret_match': True,
        'source_node_id': 'serveur1', 'detail': 'Liaison vérifiée dans les deux sens.',
    }))
    r = verifier_reciprocite('https://serveur2.exemple.fr', 'https://serveur1.exemple.fr')

    assert r['ok'] is True
    assert r['source_node_id'] == 'serveur1'
    assert appels[0][0] == 'https://serveur2.exemple.fr/ha/join-check/'
    assert appels[0][1]['data']['source_url'] == 'https://serveur1.exemple.fr'


def test_liaison_a_sens_unique_est_refusee(db, monkeypatch, secret_pose):
    """Le défaut que rien ne détectait : A joint B, mais B ne joint pas A."""
    _brancher_post(monkeypatch, _FausseReponse(200, {
        'source_reachable': False, 'secret_match': False, 'source_node_id': '',
        'detail': 'Serveur source injoignable depuis ici : timeout',
    }))
    r = verifier_reciprocite('https://serveur2.exemple.fr', 'https://serveur1.exemple.fr')
    assert r['ok'] is False
    assert 'injoignable' in r['detail']


def test_secret_different_vu_depuis_le_candidat(db, monkeypatch, secret_pose):
    _brancher_post(monkeypatch, _FausseReponse(200, {
        'source_reachable': True, 'secret_match': False, 'source_node_id': '',
        'detail': 'Le serveur source refuse notre secret',
    }))
    r = verifier_reciprocite('https://serveur2.exemple.fr', 'https://serveur1.exemple.fr')
    assert r['ok'] is False
    assert 'secret' in r['detail'].lower()


def test_candidat_trop_ancien_est_distingue(db, monkeypatch, secret_pose):
    """404 sur le point de validation : version antérieure, pas panne de liaison."""
    _brancher_post(monkeypatch, _FausseReponse(404))
    r = verifier_reciprocite('https://serveur2.exemple.fr', 'https://serveur1.exemple.fr')
    assert r['ok'] is False
    assert r['supported'] is False
    assert 'antérieure' in r['detail']


def test_reciprocite_impossible_sans_adresse_source(db, secret_pose):
    r = verifier_reciprocite('https://serveur2.exemple.fr', '')
    assert r['ok'] is False
    assert 'convention' in r['detail']


def test_reciprocite_impossible_sans_secret_local(db, settings):
    settings.ORION_HA_SECRET = 'CHANGE_ME'
    r = verifier_reciprocite('https://serveur2.exemple.fr', 'https://serveur1.exemple.fr')
    assert r['ok'] is False
    assert 'secret' in r['detail'].lower()


# ── Exploration de la grappe ─────────────────────────────────────────────────

def _grappe_branchee(monkeypatch, presents, secret_pose=True):
    """Branche le réseau pour que seuls les rangs de `presents` répondent.

    `presents` associe un rang à son node_id.
    """
    par_hote = {f'serveur{r}.exemple.fr': nid for r, nid in presents.items()}

    def faux_get(url, **kwargs):
        for hote, nid in par_hote.items():
            if hote in url:
                if '/ha/public-health/' in url:
                    return _FausseReponse(200, {
                        'status': 'healthy', 'node_id': nid, 'role': 'secondary',
                    })
                return _FausseReponse(200, {
                    'status': 'healthy', 'node_id': nid, 'role': 'secondary',
                    'database': 'ok', 'database_role': 'replica',
                    'read_only': True, 'replication_lag_seconds': 1,
                })
        raise requests.exceptions.ConnectionError('refused')

    def faux_post(url, **kwargs):
        return _FausseReponse(200, {
            'source_reachable': True, 'secret_match': True,
            'source_node_id': 'serveur1', 'detail': 'ok',
        })

    monkeypatch.setattr('apps.high_availability.connection.requests.get', faux_get)
    monkeypatch.setattr('apps.high_availability.cluster.requests.post', faux_post)
    monkeypatch.setattr(
        'apps.high_availability.connection.socket.getaddrinfo',
        lambda *a, **k: [('AF_INET', None, None, '', ('203.0.113.1', 0))],
    )


def test_exploration_ne_signale_pas_les_rangs_vides(
    db, monkeypatch, grappe, secret_pose,
):
    """Un rang non pourvu est normal, pas un défaut à corriger."""
    _grappe_branchee(monkeypatch, {2: 'serveur2'})
    res = explorer_grappe(grappe)

    par_rang = {l['rang']: l for l in res['rangs']}
    assert par_rang[1]['present'] is False
    assert par_rang[2]['present'] is True
    assert par_rang[3]['present'] is False
    assert OrionHANode.objects.count() == 0  # l'exploration ne modifie rien


def test_exploration_reconnait_ce_serveur(
    db, monkeypatch, grappe, secret_pose, settings,
):
    settings.ORION_NODE_ID = 'serveur1'
    settings.ORION_NODE_PRIORITY = 1
    _grappe_branchee(monkeypatch, {1: 'serveur1', 2: 'serveur2'})
    res = explorer_grappe(grappe)

    par_rang = {l['rang']: l for l in res['rangs']}
    assert par_rang[1]['est_ce_serveur'] is True
    # Se valider soi-même en réciprocité n'aurait aucun sens.
    assert par_rang[1]['reciprocite'] is None
    assert par_rang[1]['raccordable'] is True
    assert par_rang[2]['est_ce_serveur'] is False
    assert par_rang[2]['reciprocite']['ok'] is True


# ── Raccordement ─────────────────────────────────────────────────────────────

def test_raccordement_pose_rang_et_adresse_depuis_la_convention(
    db, monkeypatch, grappe, secret_pose, settings,
):
    settings.ORION_NODE_ID = 'serveur1'
    settings.ORION_NODE_PRIORITY = 1
    _grappe_branchee(monkeypatch, {1: 'serveur1', 2: 'serveur2', 3: 'serveur3'})

    res = raccorder_grappe(explorer_grappe(grappe), grappe)
    assert len(res['poses']) == 3

    n2 = OrionHANode.objects.get(node_id='serveur2')
    assert n2.priority == 2
    assert n2.base_url == 'https://serveur2.exemple.fr'
    assert n2.role == 'secondary'
    assert n2.is_failover_target is True

    n1 = OrionHANode.objects.get(node_id='serveur1')
    assert n1.priority == 1
    assert n1.role == 'primary'
    # Aucun actif n'existait : le serveur courant prend la main.
    assert n1.is_current_active is True


def test_raccordement_ne_deplace_pas_la_main(
    db, monkeypatch, grappe, secret_pose, settings, primary_node,
):
    """Une exploration ne doit jamais basculer le cluster."""
    settings.ORION_NODE_ID = 'serveur2'
    settings.ORION_NODE_PRIORITY = 2
    _grappe_branchee(monkeypatch, {2: 'serveur2'})

    raccorder_grappe(explorer_grappe(grappe), grappe)

    primary_node.refresh_from_db()
    assert primary_node.is_current_active is True
    assert OrionHANode.objects.get(node_id='serveur2').is_current_active is False


def test_raccordement_est_idempotent(db, monkeypatch, grappe, secret_pose, settings):
    settings.ORION_NODE_ID = 'serveur1'
    _grappe_branchee(monkeypatch, {1: 'serveur1', 2: 'serveur2'})

    raccorder_grappe(explorer_grappe(grappe), grappe)
    raccorder_grappe(explorer_grappe(grappe), grappe)
    assert OrionHANode.objects.count() == 2


def test_raccordement_conserve_le_nom_choisi(db, monkeypatch, grappe, secret_pose, settings):
    """Une nouvelle exploration ne doit pas effacer le nom donné par l'exploitant."""
    settings.ORION_NODE_ID = 'serveur1'
    _grappe_branchee(monkeypatch, {2: 'serveur2'})
    raccorder_grappe(explorer_grappe(grappe), grappe)

    node = OrionHANode.objects.get(node_id='serveur2')
    node.name = 'Secours Lille'
    node.save()

    raccorder_grappe(explorer_grappe(grappe), grappe)
    node.refresh_from_db()
    assert node.name == 'Secours Lille'
    assert node.base_url == 'https://serveur2.exemple.fr'


def test_raccordement_ecarte_une_liaison_a_sens_unique(
    db, monkeypatch, grappe, secret_pose, settings,
):
    settings.ORION_NODE_ID = 'serveur1'
    _grappe_branchee(monkeypatch, {2: 'serveur2'})
    monkeypatch.setattr(
        'apps.high_availability.cluster.requests.post',
        lambda url, **k: _FausseReponse(200, {
            'source_reachable': False, 'secret_match': False,
            'source_node_id': '', 'detail': 'Serveur source injoignable depuis ici',
        }),
    )
    res = raccorder_grappe(explorer_grappe(grappe), grappe)

    assert res['poses'] == []
    assert len(res['ignores']) == 1
    assert OrionHANode.objects.count() == 0


# ── Point d'entrée /ha/join-check/ ───────────────────────────────────────────

def test_join_check_exige_le_secret(client, db, secret_pose):
    reponse = client.post('/ha/join-check/', {'source_url': 'https://serveur1.exemple.fr'})
    assert reponse.status_code == 403


def test_join_check_refuse_les_requetes_get(client, db, secret_pose):
    reponse = client.get('/ha/join-check/', HTTP_X_ORION_HA_SECRET='secret-partage-de-test')
    assert reponse.status_code == 405


def test_join_check_refuse_une_adresse_illisible(client, db, secret_pose):
    reponse = client.post(
        '/ha/join-check/', {'source_url': 'pas-une-url://'},
        HTTP_X_ORION_HA_SECRET='secret-partage-de-test',
    )
    assert reponse.status_code == 400


def test_join_check_sonde_le_source_et_rapporte(client, db, monkeypatch, secret_pose):
    appels = []

    def faux_get(url, **kwargs):
        appels.append((url, kwargs))
        return _FausseReponse(200, {'node_id': 'serveur1', 'status': 'healthy'})

    monkeypatch.setattr('apps.high_availability.health.requests.get', faux_get)
    reponse = client.post(
        '/ha/join-check/', {'source_url': 'https://serveur1.exemple.fr/un/chemin'},
        HTTP_X_ORION_HA_SECRET='secret-partage-de-test',
    )

    assert reponse.status_code == 200
    donnees = reponse.json()
    assert donnees['source_reachable'] is True
    assert donnees['secret_match'] is True
    assert donnees['source_node_id'] == 'serveur1'
    # Seul /ha/health/ est construit sur l'hote fourni : le chemin est ecarte.
    assert appels[0][0] == 'https://serveur1.exemple.fr/ha/health/'
    assert appels[0][1]['headers']['X-Orion-HA-Secret'] == 'secret-partage-de-test'


def test_join_check_signale_un_secret_different(client, db, monkeypatch, secret_pose):
    monkeypatch.setattr(
        'apps.high_availability.health.requests.get',
        lambda url, **k: _FausseReponse(403),
    )
    reponse = client.post(
        '/ha/join-check/', {'source_url': 'https://serveur1.exemple.fr'},
        HTTP_X_ORION_HA_SECRET='secret-partage-de-test',
    )
    donnees = reponse.json()
    assert donnees['source_reachable'] is True
    assert donnees['secret_match'] is False
    assert 'ORION_HA_SECRET' in donnees['detail']


def test_join_check_signale_un_source_injoignable(client, db, monkeypatch, secret_pose):
    monkeypatch.setattr(
        'apps.high_availability.health.requests.get',
        lambda url, **k: (_ for _ in ()).throw(
            requests.exceptions.ConnectionError('refused')
        ),
    )
    reponse = client.post(
        '/ha/join-check/', {'source_url': 'https://serveur1.exemple.fr'},
        HTTP_X_ORION_HA_SECRET='secret-partage-de-test',
    )
    donnees = reponse.json()
    assert donnees['source_reachable'] is False
    assert 'injoignable' in donnees['detail']


# ── Vue de la grappe ─────────────────────────────────────────────────────────

def test_page_grappe_accessible(client, superuser, entreprise):
    client.force_login(superuser)
    reponse = client.get('/orion-admin/ha/grappe/')
    assert reponse.status_code == 200
    assert 'Relier les serveurs' in reponse.content.decode()


def test_page_grappe_refuse_la_recherche_sans_domaine(
    client, superuser, entreprise, ha_settings,
):
    client.force_login(superuser)
    reponse = client.post('/orion-admin/ha/grappe/', {'action': 'scan'}, follow=True)
    assert 'domaine de la grappe' in reponse.content.decode()


def test_page_grappe_enregistre_la_convention(client, superuser, entreprise, ha_settings):
    client.force_login(superuser)
    reponse = client.post('/orion-admin/ha/grappe/', {
        'action': 'save',
        'cluster_base_domain': 'exemple.fr',
        'node_name_pattern': 'serveur{n}',
        'cluster_max_nodes': 4,
        'cluster_use_https': 'on',
    })
    assert reponse.status_code == 302
    ha_settings.refresh_from_db()
    assert ha_settings.cluster_base_domain == 'exemple.fr'
    assert ha_settings.cluster_max_nodes == 4


def test_convention_refuse_un_motif_sans_marqueur(client, superuser, entreprise, ha_settings):
    client.force_login(superuser)
    reponse = client.post('/orion-admin/ha/grappe/', {
        'action': 'save',
        'cluster_base_domain': 'exemple.fr',
        'node_name_pattern': 'serveur',
        'cluster_max_nodes': 4,
    })
    assert reponse.status_code == 200
    assert '{n}' in reponse.content.decode()
    ha_settings.refresh_from_db()
    assert ha_settings.cluster_base_domain == ''


def test_convention_refuse_un_domaine_avec_schema(client, superuser, entreprise, ha_settings):
    client.force_login(superuser)
    reponse = client.post('/orion-admin/ha/grappe/', {
        'action': 'save',
        'cluster_base_domain': 'https://exemple.fr',
        'node_name_pattern': 'serveur{n}',
        'cluster_max_nodes': 4,
    })
    assert reponse.status_code == 200
    ha_settings.refresh_from_db()
    assert ha_settings.cluster_base_domain == ''


# ── Réseau privé entre sites ────────────────────────────────────────────────
# L'adresse privée se déduit du rang, comme le nom d'hôte : rang 2 donne
# 10.10.0.2. Les trois identités ne peuvent donc plus se contredire.

from apps.high_availability.mesh import (
    MeshConfigError,
    adresse_overlay,
    config_locale,
    entrees_hosts,
    pairs_attendus,
    reseau,
)
from apps.high_availability.media_sync import (
    cibles_de_synchronisation,
    construire_commande,
    synchroniser,
)
from apps.high_availability.replication import (
    appliquer_etat,
    parse_replica_status,
)
from apps.high_availability.models import OrionHAReplicationStatus


@pytest.fixture
def mesh(grappe):
    grappe.mesh_subnet = '10.10.0.0/24'
    grappe.mesh_port = 51820
    grappe.save()
    return grappe


def test_adresse_deduite_du_rang(mesh):
    assert adresse_overlay(mesh, 1) == '10.10.0.1'
    assert adresse_overlay(mesh, 2) == '10.10.0.2'
    assert adresse_overlay(mesh, 12) == '10.10.0.12'


def test_adresse_suit_un_autre_sous_reseau(mesh):
    mesh.mesh_subnet = '172.31.9.0/24'
    mesh.save()
    assert adresse_overlay(mesh, 3) == '172.31.9.3'


def test_rang_zero_refuse(mesh):
    """Le rang 0 donnerait l'adresse du réseau lui-même."""
    with pytest.raises(MeshConfigError, match='Rang invalide'):
        adresse_overlay(mesh, 0)


def test_rang_hors_du_sous_reseau_refuse(mesh):
    mesh.mesh_subnet = '10.10.0.0/30'  # 2 hôtes utilisables
    mesh.save()
    assert adresse_overlay(mesh, 2) == '10.10.0.2'
    with pytest.raises(MeshConfigError, match='ne tient pas'):
        adresse_overlay(mesh, 9)


def test_sous_reseau_illisible_est_nomme(mesh):
    mesh.mesh_subnet = 'pas-un-reseau'
    mesh.save()
    with pytest.raises(MeshConfigError, match='illisible'):
        reseau(mesh)


def test_sous_reseau_absent_est_nomme(mesh):
    mesh.mesh_subnet = ''
    mesh.save()
    with pytest.raises(MeshConfigError, match='Aucun sous-réseau'):
        reseau(mesh)


def test_entrees_hosts_deduites_des_noeuds(mesh, primary_node, secondary_1):
    entrees = dict((h, a) for a, h in entrees_hosts(mesh))
    assert entrees['serveur1.exemple.fr'] == '10.10.0.1'
    assert entrees['serveur2.exemple.fr'] == '10.10.0.2'


def test_entrees_hosts_sans_noeud_explore_les_rangs(mesh):
    """Avant tout raccordement, on prépare la résolution des rangs possibles."""
    mesh.cluster_max_nodes = 2
    mesh.save()
    assert len(entrees_hosts(mesh)) == 2


def test_config_locale_suit_le_rang_de_ce_serveur(mesh, settings):
    settings.ORION_NODE_PRIORITY = 2
    cfg = config_locale(mesh)
    assert cfg['ORION_MESH_ADDRESS'] == '10.10.0.2'
    assert cfg['ORION_MESH_PREFIX'] == '24'
    assert cfg['ORION_MESH_SUBNET'] == '10.10.0.0/24'
    assert cfg['ORION_MESH_PORT'] == '51820'
    assert cfg['ORION_MESH_RANK'] == '2'
    assert cfg['ORION_MESH_HOST'] == 'serveur2.exemple.fr'


def test_pairs_attendus_excluent_ce_serveur(mesh, settings, primary_node, secondary_1):
    settings.ORION_NODE_PRIORITY = 1
    pairs = pairs_attendus(mesh)
    assert [p['rang'] for p in pairs] == [2]
    assert pairs[0]['adresse'] == '10.10.0.2'


def test_pairs_attendus_excluent_un_serveur_desactive(
    mesh, settings, primary_node, secondary_1, secondary_2,
):
    settings.ORION_NODE_PRIORITY = 1
    secondary_2.is_enabled = False
    secondary_2.save()
    assert [p['rang'] for p in pairs_attendus(mesh)] == [2]


# ── Analyse de SHOW REPLICA STATUS ──────────────────────────────────────────
# MySQL 8.0.22 a renommé la commande ET ses colonnes ; MariaDB ne connaît que
# les anciens noms. Les deux familles doivent être comprises.

def test_serveur_autonome_n_est_pas_une_erreur():
    etat = parse_replica_status({})
    assert etat['is_replica'] is False
    assert etat['status'] == 'standalone'
    assert etat['lag_seconds'] is None


def test_colonnes_mysql_8():
    etat = parse_replica_status({
        'Replica_IO_Running': 'Yes',
        'Replica_SQL_Running': 'Yes',
        'Seconds_Behind_Source': 3,
        'Source_Log_File': 'bin.000007',
        'Read_Source_Log_Pos': 1543,
        'Source_Host': '10.10.0.1',
    })
    assert etat['is_replica'] is True
    assert etat['status'] == 'ok'
    assert etat['io_running'] is True
    assert etat['sql_running'] is True
    assert etat['lag_seconds'] == 3
    assert etat['log_file'] == 'bin.000007'
    assert etat['log_position'] == '1543'
    assert etat['source_host'] == '10.10.0.1'


def test_colonnes_mariadb():
    etat = parse_replica_status({
        'Slave_IO_Running': 'Yes',
        'Slave_SQL_Running': 'Yes',
        'Seconds_Behind_Master': 0,
        'Master_Log_File': 'bin.000002',
        'Read_Master_Log_Pos': 99,
        'Master_Host': '10.10.0.1',
    })
    assert etat['status'] == 'ok'
    assert etat['lag_seconds'] == 0
    assert etat['log_file'] == 'bin.000002'
    assert etat['source_host'] == '10.10.0.1'


def test_retard_nul_distingue_de_retard_inconnu():
    """NULL veut dire « réplication arrêtée », pas « aucun retard ».

    Les confondre ferait passer une réplication morte pour parfaite — le genre
    de faux positif qui ne se découvre qu'au moment de la bascule.
    """
    a_jour = parse_replica_status({
        'Replica_IO_Running': 'Yes', 'Replica_SQL_Running': 'Yes',
        'Seconds_Behind_Source': 0,
    })
    arretee = parse_replica_status({
        'Replica_IO_Running': 'Yes', 'Replica_SQL_Running': 'Yes',
        'Seconds_Behind_Source': None,
    })
    assert a_jour['lag_seconds'] == 0
    assert a_jour['status'] == 'ok'
    assert arretee['lag_seconds'] is None
    assert arretee['status'] == 'warning'


def test_fil_arrete_est_une_erreur():
    etat = parse_replica_status({
        'Replica_IO_Running': 'Yes',
        'Replica_SQL_Running': 'No',
        'Seconds_Behind_Source': 0,
    })
    assert etat['status'] == 'error'
    assert etat['sql_running'] is False


def test_erreur_rapportee_est_remontee():
    etat = parse_replica_status({
        'Replica_IO_Running': 'Yes', 'Replica_SQL_Running': 'Yes',
        'Seconds_Behind_Source': 0,
        'Last_SQL_Error': "Duplicate entry '7' for key 'PRIMARY'",
    })
    assert etat['status'] == 'error'
    assert any('Duplicate entry' in e for e in etat['errors'])


@pytest.mark.parametrize('brut,attendu', [
    ('Yes', True), ('yes', True), ('YES', True), (1, True), (True, True),
    ('No', False), ('', False), (None, False), (0, False),
])
def test_lecture_des_booleens_du_serveur(brut, attendu):
    etat = parse_replica_status({
        'Replica_IO_Running': brut, 'Replica_SQL_Running': 'Yes',
        'Seconds_Behind_Source': 0,
    })
    assert etat['io_running'] is attendu


# ── Consignation de l'état de réplication ───────────────────────────────────

def test_etat_consigne_pour_un_noeud(secondary_1):
    """La page Réplication affichait un tableau que rien ne remplissait."""
    assert OrionHAReplicationStatus.objects.count() == 0

    appliquer_etat(secondary_1, parse_replica_status({
        'Replica_IO_Running': 'Yes', 'Replica_SQL_Running': 'Yes',
        'Seconds_Behind_Source': 4,
        'Source_Log_File': 'bin.000003', 'Read_Source_Log_Pos': 77,
    }))

    objet = OrionHAReplicationStatus.objects.get(node=secondary_1)
    assert objet.database_status == 'ok'
    assert objet.io_thread_running is True
    assert objet.sql_thread_running is True
    assert objet.seconds_behind_primary == 4
    assert objet.primary_log_file == 'bin.000003'
    assert objet.primary_log_position == '77'
    assert objet.payload['releve_a']


def test_consignation_est_idempotente(secondary_1):
    etat = parse_replica_status({'Replica_IO_Running': 'Yes', 'Replica_SQL_Running': 'Yes'})
    appliquer_etat(secondary_1, etat)
    appliquer_etat(secondary_1, etat)
    assert OrionHAReplicationStatus.objects.filter(node=secondary_1).count() == 1


def test_bilan_de_sante_alimente_la_replication(secondary_1):
    """Le chemin complet : un nœud distant rapporte, on consigne."""
    services.update_node_from_health(secondary_1, {
        'status': 'healthy',
        'replication': parse_replica_status({
            'Slave_IO_Running': 'Yes', 'Slave_SQL_Running': 'Yes',
            'Seconds_Behind_Master': 12,
        }),
    })
    objet = OrionHAReplicationStatus.objects.get(node=secondary_1)
    assert objet.seconds_behind_primary == 12
    assert objet.database_status == 'ok'


# ── Synchronisation des médias ──────────────────────────────────────────────

def test_commande_rsync_ne_supprime_jamais():
    """Décision de conception : pas de --delete.

    Un fichier absent de la source peut provenir d'une bascule précédente, où
    l'autre serveur a reçu des téléversements. Supprimer serait irréversible.
    """
    commande = construire_commande(
        '10.10.0.2', source_dir='/opt/orion/uploads', dest_dir='/opt/orion/uploads',
    )
    assert '--delete' not in commande
    assert '-a' in commande
    assert '--partial' in commande


def test_commande_rsync_pousse_le_contenu_du_repertoire():
    """La barre finale sur la source compte : sans elle, rsync imbriquerait
    le répertoire dans la destination."""
    commande = construire_commande(
        '10.10.0.2', source_dir='/opt/orion/uploads', dest_dir='/opt/orion/uploads',
    )
    assert '/opt/orion/uploads/' in commande
    assert 'orion@10.10.0.2:/opt/orion/uploads/' in commande


def test_commande_rsync_porte_la_cle_ssh():
    commande = construire_commande(
        '10.10.0.2', source_dir='/m', dest_dir='/m', cle_ssh='/etc/orion/id_sync', port=2222,
    )
    transport = commande[commande.index('-e') + 1]
    assert '-p 2222' in transport
    assert '/etc/orion/id_sync' in transport
    assert 'BatchMode=yes' in transport


def test_pas_de_cible_sans_serveur_actif(db, mesh):
    cibles, motif = cibles_de_synchronisation(mesh)
    assert cibles == []
    assert 'Aucun serveur actif' in motif


def test_un_serveur_passif_ne_pousse_rien(mesh, settings, primary_node, secondary_1):
    """Pousser depuis un passif écraserait du récent par de l'ancien."""
    settings.ORION_NODE_ID = 'orion-secondary-1'
    cibles, motif = cibles_de_synchronisation(mesh)
    assert cibles == []
    assert "n'est pas l'actif" in motif


def test_le_serveur_actif_pousse_vers_les_autres(mesh, settings, primary_node, secondary_1):
    settings.ORION_NODE_ID = 'orion-primary'
    cibles, motif = cibles_de_synchronisation(mesh)
    assert motif == ''
    assert [c['node'].node_id for c in cibles] == ['orion-secondary-1']
    assert cibles[0]['adresse'] == '10.10.0.2'


def test_synchronisation_desactivee_ne_fait_rien(mesh, settings, primary_node, secondary_1):
    settings.ORION_NODE_ID = 'orion-primary'
    mesh.media_sync_enabled = False
    mesh.save()
    res = synchroniser(mesh)
    assert res['skipped'] is True
    assert 'désactivée' in res['reason']


def test_mode_constat_ne_copie_rien(mesh, settings, primary_node, secondary_1, monkeypatch):
    settings.ORION_NODE_ID = 'orion-primary'
    settings.MEDIA_ROOT = '/opt/orion/uploads'

    appels = []
    monkeypatch.setattr(
        'apps.high_availability.media_sync.subprocess.run',
        lambda *a, **k: appels.append(a) or None,
    )
    res = synchroniser(mesh, executer=False)

    assert appels == []
    assert res['resultats'][0]['ok'] is None
    assert 'rsync' in res['resultats'][0]['commande'][0]


def test_statut_consigne_sur_le_noeud_destination(
    mesh, settings, primary_node, secondary_1, monkeypatch,
):
    """C'est le contenu de la DESTINATION qui est à jour ou non."""
    settings.ORION_NODE_ID = 'orion-primary'
    settings.MEDIA_ROOT = '/opt/orion/uploads'

    class _Proc:
        returncode = 0
        stdout = 'sent 12 bytes'
        stderr = ''

    monkeypatch.setattr(
        'apps.high_availability.media_sync.subprocess.run', lambda *a, **k: _Proc(),
    )
    synchroniser(mesh)

    secondary_1.refresh_from_db()
    assert secondary_1.media_sync_status == 'ok'
    assert secondary_1.media_last_sync_at is not None


def test_echec_de_rsync_est_consigne(mesh, settings, primary_node, secondary_1, monkeypatch):
    settings.ORION_NODE_ID = 'orion-primary'
    settings.MEDIA_ROOT = '/opt/orion/uploads'

    class _Proc:
        returncode = 23
        stdout = ''
        stderr = 'rsync: connection unexpectedly closed'

    monkeypatch.setattr(
        'apps.high_availability.media_sync.subprocess.run', lambda *a, **k: _Proc(),
    )
    res = synchroniser(mesh)

    secondary_1.refresh_from_db()
    assert secondary_1.media_sync_status == 'error'
    assert secondary_1.media_last_sync_at is None
    assert res['resultats'][0]['ok'] is False
    assert 'connection unexpectedly closed' in res['resultats'][0]['detail']


def test_rsync_absent_est_dit_clairement(mesh, settings, primary_node, secondary_1, monkeypatch):
    settings.ORION_NODE_ID = 'orion-primary'
    settings.MEDIA_ROOT = '/opt/orion/uploads'
    monkeypatch.setattr(
        'apps.high_availability.media_sync.subprocess.run',
        lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError()),
    )
    res = synchroniser(mesh)
    assert "rsync n'est pas installé" in res['resultats'][0]['detail']


# ── Commandes d'exploitation ─────────────────────────────────────────────────
# Eprouvees ici plutot que sur la base de developpement : celle-ci peut etre
# en retard de migrations, et l'echec serait alors imputable a elle et non au
# code qu'on veut verifier.

from io import StringIO

from django.core.management import call_command


def test_commande_mesh_config_affiche_les_cles(mesh, settings):
    settings.ORION_NODE_PRIORITY = 2
    sortie = StringIO()
    call_command('ha_mesh_config', stdout=sortie)
    texte = sortie.getvalue()

    assert 'ORION_MESH_ADDRESS=10.10.0.2' in texte
    assert 'ORION_MESH_PREFIX=24' in texte
    assert 'ORION_MESH_PORT=51820' in texte
    assert 'ORION_MESH_HOST=serveur2.exemple.fr' in texte
    # Sourcable par un shell : une cle par ligne, aucun espace autour du =.
    for ligne in texte.strip().splitlines():
        assert ligne.count('=') >= 1
        assert ' = ' not in ligne


def test_commande_mesh_config_hosts(mesh, primary_node, secondary_1):
    sortie = StringIO()
    call_command('ha_mesh_config', '--hosts', stdout=sortie)
    lignes = sortie.getvalue().strip().splitlines()
    assert '10.10.0.1 serveur1.exemple.fr' in lignes
    assert '10.10.0.2 serveur2.exemple.fr' in lignes


def test_commande_mesh_config_refuse_un_sous_reseau_invalide(mesh):
    from django.core.management.base import CommandError
    mesh.mesh_subnet = 'pas-un-reseau'
    mesh.save()
    with pytest.raises(CommandError, match='illisible'):
        call_command('ha_mesh_config', stdout=StringIO())


def test_commande_replication_status_sans_consigner(db, secondary_1):
    sortie = StringIO()
    call_command('ha_replication_status', '--no-save', stdout=sortie)
    # SQLite n'a pas de replication : l'etat autonome est le bon resultat.
    assert 'autonome' in sortie.getvalue()
    assert OrionHAReplicationStatus.objects.count() == 0


def test_commande_replication_status_consigne_le_noeud_courant(
    db, secondary_1, settings,
):
    settings.ORION_NODE_ID = secondary_1.node_id
    sortie = StringIO()
    call_command('ha_replication_status', stdout=sortie)
    assert OrionHAReplicationStatus.objects.filter(node=secondary_1).exists()
    assert 'Consigné' in sortie.getvalue()


def test_commande_replication_status_sans_noeud_correspondant(db, settings):
    """Un serveur pas encore raccorde ne doit pas faire echouer la commande."""
    settings.ORION_NODE_ID = 'serveur-inconnu'
    sortie = StringIO()
    call_command('ha_replication_status', stdout=sortie)
    assert 'Non consigné' in sortie.getvalue()
    assert OrionHAReplicationStatus.objects.count() == 0


def test_commande_sync_media_constat(mesh, settings, primary_node, secondary_1):
    settings.ORION_NODE_ID = 'orion-primary'
    settings.MEDIA_ROOT = '/opt/orion/uploads'
    sortie = StringIO()
    call_command('ha_sync_media', '--constat', stdout=sortie)
    texte = sortie.getvalue()
    assert 'orion-secondary-1' in texte
    assert 'rsync' in texte
    assert '--delete' not in texte


def test_commande_sync_media_explique_son_refus(mesh, settings, primary_node, secondary_1):
    settings.ORION_NODE_ID = 'orion-secondary-1'
    sortie = StringIO()
    call_command('ha_sync_media', stdout=sortie)
    assert "n'est pas l'actif" in sortie.getvalue()
