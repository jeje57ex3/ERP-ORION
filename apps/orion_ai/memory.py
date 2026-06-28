from apps.orion_ai.models import OrionAIMemory


def get_memory_context(*, company=None, user=None, brand_key=''):
    memories = OrionAIMemory.objects.filter(is_active=True)

    relevant = list(memories.filter(scope='global', company=None, user=None))

    if company:
        relevant.extend(memories.filter(scope='company', company=company))

    if user:
        relevant.extend(memories.filter(scope='user', user=user))

    if brand_key:
        relevant.extend(memories.filter(scope='brand', company=company, brand_key=brand_key))

    lines = []
    for memory in relevant:
        if memory.is_sensitive:
            continue
        lines.append(f'- {memory.key}: {memory.value}')

    if not lines:
        return ''

    return 'Mémoire Orion utile :\n' + '\n'.join(lines)


def set_memory(*, company=None, user=None, brand_key='', scope='company', key='', value='', created_by=None):
    memory, _ = OrionAIMemory.objects.update_or_create(
        company=company,
        user=user if scope == 'user' else None,
        brand_key=brand_key if scope == 'brand' else '',
        scope=scope,
        key=key,
        defaults={
            'value': value,
            'created_by': created_by,
            'is_active': True,
        },
    )
    return memory


def delete_memory(*, company=None, user=None, scope='company', key=''):
    OrionAIMemory.objects.filter(
        company=company,
        user=user if scope == 'user' else None,
        scope=scope,
        key=key,
    ).update(is_active=False)
