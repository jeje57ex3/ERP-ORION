"""
tests/test_orion_assistant.py
Tests du module Orion Assistant IA.
"""
import pytest
from apps.core.models import Company
from apps.orion_assistant.models import AssistantConversation, AssistantMessage
from apps.orion_assistant.services import (
    start_conversation, add_message, get_conversation_history,
    get_user_conversations, archive_conversation, build_context_prompt,
    get_assistant_stats,
)


@pytest.fixture
def company(db):
    return Company.objects.create(name='AI SA', slug='ai-sa', status='active', is_active=True)


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(username='ai_user', password='pass')


@pytest.fixture
def conversation(db, company, user):
    return start_conversation(company, user, title='Test conv')


class TestStartConversation:
    def test_creates_conversation(self, db, company, user):
        conv = start_conversation(company, user, title='Q1', context_module='sales')
        assert conv.pk is not None
        assert conv.title == 'Q1'
        assert conv.context_module == 'sales'

    def test_links_to_company_and_user(self, db, company, user):
        conv = start_conversation(company, user)
        assert conv.company == company
        assert conv.user == user


class TestAddMessage:
    def test_adds_user_message(self, db, conversation):
        msg = add_message(conversation, 'user', 'Bonjour Orion')
        assert msg.pk is not None
        assert msg.role == 'user'
        assert msg.content == 'Bonjour Orion'

    def test_adds_assistant_message(self, db, conversation):
        msg = add_message(conversation, 'assistant', 'Bonjour !', tokens_used=10)
        assert msg.tokens_used == 10

    def test_updates_conversation_timestamp(self, db, conversation):
        old_ts = conversation.updated_at
        import time; time.sleep(0.01)
        add_message(conversation, 'user', 'Message')
        conversation.refresh_from_db()
        assert conversation.updated_at >= old_ts


class TestGetConversationHistory:
    def test_returns_messages_in_order(self, db, conversation):
        add_message(conversation, 'user', 'M1')
        add_message(conversation, 'assistant', 'R1')
        add_message(conversation, 'user', 'M2')
        history = list(get_conversation_history(conversation))
        assert len(history) == 3
        assert history[0].content == 'M1'
        assert history[2].content == 'M2'

    def test_respects_limit(self, db, conversation):
        for i in range(10):
            add_message(conversation, 'user', f'M{i}')
        history = list(get_conversation_history(conversation, limit=5))
        assert len(history) == 5


class TestGetUserConversations:
    def test_returns_user_convs(self, db, company, user, conversation):
        result = get_user_conversations(company, user)
        assert conversation in result

    def test_excludes_other_user(self, db, company, user, django_user_model):
        other = django_user_model.objects.create_user(username='other_ai', password='pass')
        start_conversation(company, other, title='Other conv')
        result = get_user_conversations(company, user)
        pks = [c.pk for c in result]
        assert all(AssistantConversation.objects.get(pk=pk).user == user for pk in pks)

    def test_excludes_archived_by_default(self, db, company, user, conversation):
        archive_conversation(conversation)
        result = get_user_conversations(company, user)
        assert conversation not in result

    def test_includes_archived_when_requested(self, db, company, user, conversation):
        archive_conversation(conversation)
        result = get_user_conversations(company, user, include_archived=True)
        assert conversation in result


class TestBuildContextPrompt:
    def test_contains_company_name(self, db, company):
        prompt = build_context_prompt(company)
        assert company.name in prompt

    def test_contains_module_when_given(self, db, company):
        prompt = build_context_prompt(company, context_module='ventes')
        assert 'ventes' in prompt


class TestAssistantStats:
    def test_stats_keys(self, db, company, user, conversation):
        add_message(conversation, 'user', 'Hello')
        stats = get_assistant_stats(company)
        assert 'total_conversations' in stats
        assert 'active_conversations' in stats
        assert 'total_messages' in stats
        assert stats['total_conversations'] >= 1
        assert stats['total_messages'] >= 1
