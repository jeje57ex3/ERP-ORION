"""
Tests unitaires pour apps/orion_ops/services/score_service.py

On vérifie la logique de calcul en mockant les lectures de capteurs
et en créant des objets en DB de test.
"""
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone


class TestComputeDataQualityScore(TestCase):

    def test_unavailable_when_no_checks_ever_run(self):
        from apps.orion_ops.services.score_service import compute_data_quality_score
        result = compute_data_quality_score()
        self.assertIsNone(result['score'])
        self.assertEqual(result['status'], 'unavailable')

    def test_perfect_score_when_all_resolved(self):
        from apps.orion_ops.models import DataQualityAnomaly
        from apps.orion_ops.services.score_service import compute_data_quality_score
        DataQualityAnomaly.objects.create(
            anomaly_type='negative_stock', severity='low',
            count=1, module='inventory', status='resolved',
        )
        result = compute_data_quality_score()
        self.assertEqual(result['score'], 100)
        self.assertEqual(result['status'], 'ok')

    def test_cap_at_40_when_critical_open(self):
        from apps.orion_ops.models import DataQualityAnomaly
        from apps.orion_ops.services.score_service import compute_data_quality_score
        DataQualityAnomaly.objects.create(
            anomaly_type='negative_stock', severity='critical',
            count=5, module='inventory', status='open',
        )
        result = compute_data_quality_score()
        self.assertIsNotNone(result['score'])
        self.assertLessEqual(result['score'], 40)
        self.assertEqual(result['status'], 'critical')

    def test_deductions_for_high_anomalies(self):
        from apps.orion_ops.models import DataQualityAnomaly
        from apps.orion_ops.services.score_service import compute_data_quality_score
        # 2 anomalies high = -20
        for _ in range(2):
            DataQualityAnomaly.objects.create(
                anomaly_type='duplicate_customer', severity='high',
                count=1, module='crm', status='open',
            )
        result = compute_data_quality_score()
        self.assertEqual(result['score'], 80)
        self.assertEqual(result['status'], 'ok')


class TestComputeCapacityScore(TestCase):

    @patch('apps.orion_ops.services.score_service._latest_sensor')
    def test_critical_disk_caps_score(self, mock_sensor):
        # disk_usage=97% (> 95% → cap=20)
        def side(sensor_type, **kwargs):
            mapping = {'disk_usage': 97.0, 'memory_usage': 60.0, 'cpu_usage': 40.0}
            return mapping.get(sensor_type)
        mock_sensor.side_effect = side
        from apps.orion_ops.services.score_service import compute_capacity_score
        result = compute_capacity_score()
        self.assertLessEqual(result['score'], 20)
        self.assertEqual(result['status'], 'critical')

    @patch('apps.orion_ops.services.score_service._latest_sensor')
    def test_healthy_resources_high_score(self, mock_sensor):
        def side(sensor_type, **kwargs):
            return {'disk_usage': 40.0, 'memory_usage': 50.0, 'cpu_usage': 30.0}.get(sensor_type)
        mock_sensor.side_effect = side
        from apps.orion_ops.services.score_service import compute_capacity_score
        result = compute_capacity_score()
        self.assertGreaterEqual(result['score'], 70)


class TestComputeResilienceScore(TestCase):

    @patch('apps.orion_ops.services.score_service._latest_sensor')
    def test_cap_50_without_restore_test(self, mock_sensor):
        mock_sensor.return_value = 1.0  # beat + broker ok
        from apps.orion_ops.services.score_service import compute_resilience_score
        result = compute_resilience_score()
        self.assertLessEqual(result['score'], 50)
        self.assertTrue(result.get('cap_applied'))

    @patch('apps.orion_ops.services.score_service._latest_sensor')
    def test_celery_beat_down_loses_20pts(self, mock_sensor):
        def side(sensor_type, **kwargs):
            if sensor_type == 'celery_beat_ok':
                return 0.0
            if sensor_type == 'celery_broker_ok':
                return 1.0
            return None
        mock_sensor.side_effect = side
        from apps.orion_ops.services.score_service import compute_resilience_score
        result = compute_resilience_score()
        # beat: 0/20, broker: 15/15, rest: partial
        self.assertIsNotNone(result['score'])
        detail = result['points_detail']
        self.assertEqual(detail['celery_beat']['earned'], 0)
        self.assertEqual(detail['broker']['earned'], 15)


class TestComputeIntegrationsScore(TestCase):

    def test_unavailable_when_no_data_and_unknown_components(self):
        from apps.orion_ops.services.score_service import compute_integrations_score
        # ServiceComponent n'existent pas, aucune métrique → unavailable
        result = compute_integrations_score()
        self.assertIsNone(result['score'])
        self.assertEqual(result['status'], 'unavailable')

    def test_good_response_time_gives_20pts(self):
        from apps.orion_ops.models import BusinessMetricReading
        # Créer une métrique sync_errors_1h = 0 pour avoir "has_any_data"
        BusinessMetricReading.objects.create(metric_type='sync_errors_1h', value=0.0, status='ok')
        with patch('apps.orion_ops.services.score_service._latest_sensor') as mock_s:
            mock_s.return_value = 150.0  # 150 ms → 20 pts
            from apps.orion_ops.services.score_service import compute_integrations_score
            result = compute_integrations_score()
        self.assertEqual(result['points_detail']['response_time']['earned'], 20)


class TestScoreDomainCoverage(TestCase):
    """Vérifie que tous les domaines DOMAINS sont dans _SCORE_COMPUTERS."""

    def test_all_domains_have_computers(self):
        from apps.orion_ops.models import HealthScoreRecord
        from apps.orion_ops.services.score_service import _SCORE_COMPUTERS
        domain_keys = {d[0] for d in HealthScoreRecord.DOMAINS}
        computer_keys = set(_SCORE_COMPUTERS.keys())
        self.assertEqual(domain_keys, computer_keys,
                         f'Domaines sans computer: {domain_keys - computer_keys}')
