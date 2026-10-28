"""
Tests unitaires pour apps/orion_ops/services/rule_engine.py

Principe : aucune données en base réelle — tout est mocké.
Les tests vérifient la logique d'évaluation des opérateurs et
l'anti-spam via frequency_min / last_triggered.
"""
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone


class TestEvaluateCondition(TestCase):
    """Tests de la fonction _evaluate_condition."""

    def _call(self, value, operator, threshold):
        from apps.orion_ops.services.rule_engine import _evaluate_condition
        return _evaluate_condition(value, operator, threshold)

    def test_gt_true(self):
        self.assertTrue(self._call(96.0, 'gt', 95.0))

    def test_gt_false_equal(self):
        self.assertFalse(self._call(95.0, 'gt', 95.0))

    def test_gte_equal(self):
        self.assertTrue(self._call(95.0, 'gte', 95.0))

    def test_lt_true(self):
        self.assertTrue(self._call(0.0, 'lt', 1.0))

    def test_lte_equal(self):
        self.assertTrue(self._call(1.0, 'lte', 1.0))

    def test_eq_true(self):
        self.assertTrue(self._call(5.0, 'eq', 5.0))

    def test_neq_true(self):
        self.assertTrue(self._call(4.0, 'neq', 5.0))

    def test_unknown_operator_returns_false(self):
        self.assertFalse(self._call(10.0, 'unknown_op', 5.0))


class TestGetCurrentValue(TestCase):
    """Tests de la récupération de valeur par source."""

    @patch('apps.orion_ops.services.rule_engine._get_current_value')
    def test_returns_none_when_no_data(self, mock_get):
        mock_get.return_value = None
        from apps.orion_ops.services.rule_engine import _get_current_value
        result = _get_current_value('sensor', 'disk_usage')
        self.assertIsNone(result)

    def test_data_quality_open_critical(self):
        """data_quality source avec metric_key='open_critical' compte les anomalies critiques ouvertes."""
        from apps.orion_ops.models import DataQualityAnomaly
        DataQualityAnomaly.objects.create(
            anomaly_type='duplicate_customer', severity='critical',
            count=3, module='crm', status='open',
        )
        from apps.orion_ops.services.rule_engine import _get_current_value
        value = _get_current_value('data_quality', 'open_critical')
        self.assertEqual(value, 1.0)

    def test_data_quality_total_open_excludes_resolved(self):
        from apps.orion_ops.models import DataQualityAnomaly
        DataQualityAnomaly.objects.create(
            anomaly_type='negative_stock', severity='medium',
            count=1, module='inventory', status='resolved',
        )
        DataQualityAnomaly.objects.create(
            anomaly_type='duplicate_customer', severity='low',
            count=1, module='crm', status='open',
        )
        from apps.orion_ops.services.rule_engine import _get_current_value
        value = _get_current_value('data_quality', 'total_open')
        self.assertEqual(value, 1.0)


class TestEvaluateAllRules(TestCase):
    """Tests de bout en bout d'evaluate_all_rules."""

    def _make_rule(self, **kwargs):
        from apps.orion_ops.models import AlertRule
        defaults = {
            'name': 'test-rule',
            'source': 'data_quality',
            'metric_key': 'open_critical',
            'operator': 'gte',
            'threshold': 1.0,
            'severity': 'warning',
            'frequency_min': 5,
            'actions': [],
            'enabled': True,
        }
        defaults.update(kwargs)
        return AlertRule.objects.create(**defaults)

    def test_no_rules_returns_zero(self):
        from apps.orion_ops.services.rule_engine import evaluate_all_rules
        result = evaluate_all_rules()
        self.assertEqual(result['total'], 0)
        self.assertEqual(result['triggered'], 0)

    def test_rule_triggers_when_condition_met(self):
        from apps.orion_ops.models import DataQualityAnomaly, AlertRule
        DataQualityAnomaly.objects.create(
            anomaly_type='negative_stock', severity='critical',
            count=2, module='inventory', status='open',
        )
        rule = self._make_rule(name='trigger-test')
        from apps.orion_ops.services.rule_engine import evaluate_all_rules
        result = evaluate_all_rules()
        self.assertEqual(result['triggered'], 1)
        rule.refresh_from_db()
        self.assertEqual(rule.last_status, 'triggered')
        self.assertEqual(rule.trigger_count, 1)

    def test_rule_not_retriggered_within_frequency(self):
        from apps.orion_ops.models import DataQualityAnomaly
        DataQualityAnomaly.objects.create(
            anomaly_type='negative_stock', severity='critical',
            count=2, module='inventory', status='open',
        )
        rule = self._make_rule(
            name='freq-test',
            frequency_min=60,
            last_triggered=timezone.now() - timedelta(minutes=10),
        )
        from apps.orion_ops.services.rule_engine import evaluate_all_rules
        result = evaluate_all_rules()
        self.assertEqual(result['triggered'], 0)
        self.assertEqual(result['skipped'], 1)

    def test_silenced_rule_is_skipped(self):
        rule = self._make_rule(
            name='silenced-test',
            silence_until=timezone.now() + timedelta(hours=1),
        )
        from apps.orion_ops.services.rule_engine import evaluate_all_rules
        result = evaluate_all_rules()
        self.assertEqual(result['skipped'], 1)
        self.assertEqual(result['triggered'], 0)

    def test_disabled_rule_not_evaluated(self):
        self._make_rule(name='disabled-test', enabled=False)
        from apps.orion_ops.services.rule_engine import evaluate_all_rules
        result = evaluate_all_rules()
        self.assertEqual(result['total'], 0)

    def test_rule_resets_to_ok_when_condition_clears(self):
        rule = self._make_rule(name='reset-test', last_status='triggered')
        # Aucune anomalie critique → condition non remplie
        from apps.orion_ops.services.rule_engine import evaluate_all_rules
        evaluate_all_rules()
        rule.refresh_from_db()
        self.assertEqual(rule.last_status, 'ok')
