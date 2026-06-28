AI_TOOLS = {}


def register_ai_tool(
    name,
    description,
    is_write_action=False,
    is_dangerous_action=False,
    required_permission=None,
):
    def decorator(func):
        AI_TOOLS[name] = {
            'name': name,
            'description': description,
            'func': func,
            'is_write_action': is_write_action,
            'is_dangerous_action': is_dangerous_action,
            'required_permission': required_permission,
        }
        return func
    return decorator


def get_ai_tool(name):
    return AI_TOOLS.get(name)


def get_available_ai_tools():
    return AI_TOOLS


def list_tools_for_prompt():
    lines = []
    for tool in AI_TOOLS.values():
        prefix = '[ÉCRITURE]' if tool['is_write_action'] else '[LECTURE]'
        if tool['is_dangerous_action']:
            prefix = '[DANGEREUX]'
        lines.append(f'{prefix} {tool["name"]} — {tool["description"]}')
    return '\n'.join(lines)
