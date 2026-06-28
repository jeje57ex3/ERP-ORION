"""
tests/test_smart_automations.py
Tests du module Automatisations intelligentes.
"""
import pytest
from apps.core.models import Company
from apps.smart_automations.models import AutomationRule, AutomationRun
from apps.smart_automations.services import execute_rule, trigger_event, get_rule_stats


@pytest.fixture
def company(db):
    return Company.objects.create(name='Auto SA', slug='auto-sa', status='active', is_active=True)


@pytest.fixture
def rule(db, company):
    return AutomationRule.objects.create(
        company=company,
        name='Test rule',
        trigger_type='manual',
        conditions=[],
        actions=[{'type': 'create_alert', 'payload': {'title': 'Auto alert', 'priority': 'normal'}}],
        is_active=True,
    )


class TestExecuteRule:
    def test_creates_run(self, db, company, rule):
        run = execute_rule(rule)
        assert run.pk is not None
        assert run.status in ('success', 'skipped', 'failed')

    def test_success_status(self, db, company, rule):
        run = execute_rule(rule)
        assert run.status == 'success'

    def test_increments_run_count(self, db, company, rule):
        execute_rule(rule)
        rule.refresh_from_db()
        assert rule.run_count == 1

    def test_condition_not_met_skips(self, db, company):
        rule = AutomationRule.objects.create(
            company=company, name='Cond rule', trigger_type='manual',
            conditions=[{'field': 'status', 'operator': 'eq', 'value': 'paid'}],
            actions=[], is_active=True,
        )
        run = execute_rule(rule, trigger_payload={'status': 'pending'})
        assert run.status == 'skipped'

    def test_condition_met_runs(self, db, company):
        rule = AutomationRule.objects.create(
            company=company, name='Cond rule 2', trigger_type='manual',
            conditions=[{'field': 'status', 'operator': 'eq', 'value': 'paid'}],
            actions=[], is_active=True,
        )
        run = execute_rule(rule, trigger_payload={'status': 'paid'})
        assert run.status == 'success'


class TestTriggerEvent:
    def test_runs_matching_rules(self, db, company, rule):
        rule.trigger_type = 'new_order'
        rule.save()
        runs = trigger_event('new_order', company, {'order_id': 1})
        assert len(runs) == 1

    def test_ignores_inactive_rules(self, db, company, rule):
        rule.trigger_type = 'new_order'
        rule.is_active = False
        rule.save()
        runs = trigger_event('new_order', company)
        assert len(runs) == 0

    def test_company_isolation(self, db, company, rule):
        other = Company.objects.create(name='Other', slug='auto-other', status='active', is_active=True)
        rule.trigger_type = 'new_order'
        rule.save()
        runs = trigger_event('new_order', other)
        assert len(runs) == 0


class TestRuleStats:
    def test_stats(self, db, company, rule):
        execute_rule(rule)
        stats = get_rule_stats(company)
        assert stats['total'] == 1
        assert stats['active'] == 1
        assert stats['total_runs'] == 1
