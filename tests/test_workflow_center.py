"""
tests/test_workflow_center.py
Tests du module Workflow Center.
"""
import pytest
from apps.core.models import Company
from apps.workflow_center.models import WorkflowTemplate, WorkflowInstance, WorkflowAction
from apps.workflow_center.services import (
    start_workflow, approve_step, reject_step,
    get_pending_instances, get_workflow_stats,
)


@pytest.fixture
def company(db):
    return Company.objects.create(name='Workflow SA', slug='workflow-sa', status='active', is_active=True)


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(username='wf_user', password='pass')


@pytest.fixture
def template(db, company):
    return WorkflowTemplate.objects.create(
        company=company,
        name='Validation devis',
        code='quote_approval',
        object_type='quote',
        steps=[{'name': 'Responsable'}, {'name': 'Direction'}],
        is_active=True,
    )


@pytest.fixture
def instance(db, company, template, user):
    return WorkflowInstance.objects.create(
        company=company, template=template,
        object_type='quote', object_id='99',
        status='pending', created_by=user,
    )


class TestStartWorkflow:
    def test_creates_instance(self, db, company, template, user):
        inst = start_workflow(company, 'quote', 1, 'quote_approval', created_by=user)
        assert inst is not None
        assert inst.status == 'pending'
        assert inst.object_id == '1'

    def test_returns_none_if_no_template(self, db, company):
        result = start_workflow(company, 'quote', 1, 'nonexistent_code')
        assert result is None

    def test_returns_none_if_template_inactive(self, db, company, template):
        template.is_active = False
        template.save()
        result = start_workflow(company, 'quote', 1, 'quote_approval')
        assert result is None


class TestApproveStep:
    def test_advance_step(self, db, instance, user):
        action = approve_step(instance, user, comment='OK')
        instance.refresh_from_db()
        assert action.action == 'approve'
        assert instance.current_step_index == 1
        assert instance.status == 'in_progress'

    def test_final_approval(self, db, instance, user):
        instance.current_step_index = 1
        instance.save()
        approve_step(instance, user)
        instance.refresh_from_db()
        assert instance.status == 'approved'
        assert instance.completed_at is not None

    def test_action_stored(self, db, instance, user):
        approve_step(instance, user, comment='Validated')
        action = instance.actions.first()
        assert action.comment == 'Validated'
        assert action.user == user


class TestRejectStep:
    def test_reject_sets_status(self, db, instance, user):
        reject_step(instance, user, comment='Non conforme')
        instance.refresh_from_db()
        assert instance.status == 'rejected'
        assert instance.completed_at is not None

    def test_action_stored(self, db, instance, user):
        reject_step(instance, user)
        action = instance.actions.first()
        assert action.action == 'reject'


class TestGetPendingInstances:
    def test_returns_pending(self, db, company, instance):
        qs = get_pending_instances(company)
        assert instance in qs

    def test_excludes_approved(self, db, company, instance, user):
        instance.current_step_index = 1
        instance.save()
        approve_step(instance, user)
        qs = get_pending_instances(company)
        assert instance not in qs


class TestWorkflowStats:
    def test_stats_structure(self, db, company, instance):
        stats = get_workflow_stats(company)
        assert 'pending' in stats
        assert 'approved' in stats
        assert stats['pending'] >= 1
