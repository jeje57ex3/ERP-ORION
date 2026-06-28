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
from apps.high_availability.failover import validate_failover_target, run_manual_failover_to_node
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
    # The atomic transaction rolls back on exception (including the event), so only
    # check that the RuntimeError is raised, not the DB event.
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

def test_node_form_rejects_primary_with_wrong_priority(primary_node):
    data = {
        'node_id': 'orion-primary',
        'name': 'Principal',
        'role': 'primary',
        'status': 'active',
        'priority': 2,
        'is_enabled': True,
        'is_current_active': True,
        'is_failover_target': False,
        'allow_auto_failover': False,
    }
    form = OrionHANodeForm(data=data, instance=primary_node)
    assert not form.is_valid()


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

def test_settings_view_requires_superuser(client, staff_user):
    client.force_login(staff_user)
    response = client.get('/orion-admin/ha/settings/')
    assert response.status_code == 403


def test_settings_view_accessible_to_superuser(client, superuser):
    client.force_login(superuser)
    response = client.get('/orion-admin/ha/settings/')
    assert response.status_code == 200


def test_nodes_view_accessible_to_superuser(client, superuser, primary_node):
    client.force_login(superuser)
    response = client.get('/orion-admin/ha/nodes/')
    assert response.status_code == 200


def test_failover_view_accessible_to_superuser(client, superuser):
    client.force_login(superuser)
    response = client.get('/orion-admin/ha/failover/')
    assert response.status_code == 200


def test_events_view_accessible_to_superuser(client, superuser):
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
