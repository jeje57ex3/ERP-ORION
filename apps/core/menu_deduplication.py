"""
Menu deduplication utilities for Orion ERP navigation.

Ensures that nav modules and nav groups built from multiple app registrations
don't produce duplicate items in the sidebar.
"""

from __future__ import annotations
from typing import Any


def deduplicate_nav_modules(modules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Remove duplicate nav module entries by their `id` field.
    The first occurrence wins; subsequent entries with the same id are discarded.

    Args:
        modules: List of nav module dicts, each expected to have an 'id' key.

    Returns:
        List with duplicates removed, preserving original order.
    """
    seen: set[str] = set()
    result: list[dict[str, Any]] = []

    for module in modules:
        mid = module.get("id")
        if mid is None:
            result.append(module)
            continue
        if mid not in seen:
            seen.add(mid)
            result.append(module)

    return result


def deduplicate_nav_groups(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Deduplicate nav groups by their `label` field, merging their `items` lists.
    Groups with the same label are merged: items from later groups are appended,
    then item-level deduplication is applied within the merged group.

    Args:
        groups: List of nav group dicts with 'label' and 'items' keys.

    Returns:
        List of merged/deduplicated groups.
    """
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for group in groups:
        label = group.get("label", "")
        if label not in merged:
            merged[label] = {**group, "items": list(group.get("items", []))}
            order.append(label)
        else:
            existing_ids = {m.get("id") for m in merged[label]["items"]}
            for item in group.get("items", []):
                if item.get("id") not in existing_ids:
                    merged[label]["items"].append(item)
                    existing_ids.add(item.get("id"))

    return [merged[label] for label in order]


def merge_nav_structures(
    base: list[dict[str, Any]],
    extra: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Merge two nav group lists, deduplicating the result.

    Args:
        base:  Primary nav structure (e.g. from the main app).
        extra: Additional items (e.g. from a plugin or brand module).

    Returns:
        Merged and deduplicated nav structure.
    """
    return deduplicate_nav_groups(base + extra)


def find_duplicate_module_ids(modules: list[dict[str, Any]]) -> list[str]:
    """Return a list of module ids that appear more than once."""
    seen: dict[str, int] = {}
    for m in modules:
        mid = m.get("id")
        if mid:
            seen[mid] = seen.get(mid, 0) + 1
    return [mid for mid, count in seen.items() if count > 1]
