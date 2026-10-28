"""
Tests unitaires pour apps/orion_ops/services/behavioral_detection.py
"""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone


class TestDetectBruteForce(TestCase):

    def test_no_detection_when_no_sensor(self):
        from apps.orion_ops.services.behavioral_detection import detect_brute_force
        result = detect_brute_force()
        self.assertFalse(result['detected'])

    def test_no_detection_below_threshold(self):
        from apps.system_health.models import SensorReading
        from apps.orion_ops.services.behavioral_detection import detect_brute_force
        SensorReading.objects.create(sensor_type='failed_logins_1h', value=5.0, status='ok')
        result = detect_brute_force()
        self.assertFalse(result['detected'])

    def test_detection_above_15(self):
        from apps.system_health.models import SensorReading
        from apps.orion_ops.services.behavioral_detection import detect_brute_force
        SensorReading.objects.create(sensor_type='failed_logins_1h', value=20.0, status='critical')
        result = detect_brute_force()
        self.assertTrue(result['detected'])
        self.assertEqual(result['severity'], 'high')

    def test_critical_severity_above_30(self):
        from apps.system_health.models import SensorReading
        from apps.orion_ops.services.behavioral_detection import detect_brute_force
        SensorReading.objects.create(sensor_type='failed_logins_1h', value=35.0, status='critical')
        result = detect_brute_force()
        self.assertTrue(result['detected'])
        self.assertEqual(result['severity'], 'critical')

    def test_creates_anomaly_on_detection(self):
        from apps.system_health.models import SensorReading
        from apps.orion_ops.models import DataQualityAnomaly
        from apps.orion_ops.services.behavioral_detection import detect_brute_force
        SensorReading.objects.create(sensor_type='failed_logins_1h', value=20.0, status='critical')
        detect_brute_force()
        self.assertTrue(DataQualityAnomaly.objects.filter(cause__startswith='brute_force_logins').exists())

    def test_dedup_does_not_create_duplicate_in_24h(self):
        from apps.system_health.models import SensorReading
        from apps.orion_ops.models import DataQualityAnomaly
        from apps.orion_ops.services.behavioral_detection import detect_brute_force
        SensorReading.objects.create(sensor_type='failed_logins_1h', value=20.0, status='critical')
        detect_brute_force()
        detect_brute_force()
        self.assertEqual(DataQualityAnomaly.objects.filter(cause__startswith='brute_force_logins').count(), 1)


class TestDetectFailedTaskAccumulation(TestCase):

    def test_no_detection_below_10(self):
        from apps.orion_ops.services.behavioral_detection import detect_failed_task_accumulation
        result = detect_failed_task_accumulation()
        self.assertFalse(result['detected'])

    def test_detection_above_10(self):
        from apps.orion_ops.models import FailedTask
        from apps.orion_ops.services.behavioral_detection import detect_failed_task_accumulation
        for i in range(11):
            FailedTask.objects.create(
                task_id=f'task-{i}', task_name='test.task',
                created_at=timezone.now(), error_type='ValueError',
                error_safe='test error', status='failed',
            )
        result = detect_failed_task_accumulation()
        self.assertTrue(result['detected'])
        self.assertGreaterEqual(result['count'], 10)


class TestRunBehavioralDetection(TestCase):

    def test_returns_all_keys(self):
        from apps.orion_ops.services.behavioral_detection import run_behavioral_detection
        result = run_behavioral_detection()
        self.assertIn('brute_force', result)
        self.assertIn('2fa_spike', result)
        self.assertIn('recovery_code', result)
        self.assertIn('failed_task_backlog', result)

    def test_each_result_has_detected_key(self):
        from apps.orion_ops.services.behavioral_detection import run_behavioral_detection
        result = run_behavioral_detection()
        for name, data in result.items():
            if 'error' not in data:
                self.assertIn('detected', data, f'{name} missing detected key')
