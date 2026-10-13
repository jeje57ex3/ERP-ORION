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
    ('', '', ''),
])
def test_normaliser_base_url(brut, url, hote):
    assert normaliser_base_url(brut) == (url, hote)


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
