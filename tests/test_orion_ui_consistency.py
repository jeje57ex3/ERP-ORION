"""
Tests de cohérence du système UI Orion Internal.

Vérifie :
  1. Les fichiers CSS orion-internal existent
  2. Les templates internes utilisent les bonnes classes
  3. Les sites publics ne chargent pas le thème interne
  4. Le registre de widgets ne produit pas de doublons
  5. La déduplication de menus fonctionne
"""

import pytest
from pathlib import Path


# ── Fixtures ─────────────────────────────────────────────────────────────

ORION_CSS_DIR = Path("static/orion/css")

EXPECTED_CSS_FILES = [
    "orion-internal.css",
    "orion-core-theme.css",
    "orion-internal-layout.css",
    "orion-internal-navigation.css",
    "orion-internal-components.css",
    "orion-internal-forms.css",
    "orion-internal-tables.css",
    "orion-internal-badges.css",
    "orion-internal-widgets.css",
    "orion-internal-utilities.css",
    "orion-internal-overrides.css",
]

INTERNAL_TEMPLATE_DIRS = [
    Path("templates/orion_admin"),
    Path("templates/private_saas"),
    Path("templates/high_availability"),
    Path("templates/orion_ai"),
    Path("templates/continuous_improvement"),
    Path("templates/lunea_beauty_profile"),
    Path("templates/siecle_creations"),
    Path("templates/website_shop_settings"),
]

PUBLIC_DIRS = [
    Path("templates/store"),
    Path("templates/public"),
    Path("templates/siecle"),
    Path("templates/lunea"),
]


# ── 1. CSS files ──────────────────────────────────────────────────────────

class TestOrionCSSFilesExist:
    @pytest.mark.parametrize("filename", EXPECTED_CSS_FILES)
    def test_css_file_exists(self, filename):
        path = ORION_CSS_DIR / filename
        assert path.exists(), f"CSS file missing: {path}"

    def test_entry_point_imports_all(self):
        entry = ORION_CSS_DIR / "orion-internal.css"
        assert entry.exists()
        content = entry.read_text(encoding="utf-8")
        for filename in EXPECTED_CSS_FILES:
            if filename == "orion-internal.css":
                continue
            assert filename in content, f"orion-internal.css does not import {filename}"

    def test_core_theme_defines_gold_variable(self):
        css = (ORION_CSS_DIR / "orion-core-theme.css").read_text(encoding="utf-8")
        assert "--orion-gold" in css

    def test_core_theme_defines_bg_variable(self):
        css = (ORION_CSS_DIR / "orion-core-theme.css").read_text(encoding="utf-8")
        assert "--orion-bg" in css


# ── 2. Layout templates ───────────────────────────────────────────────────

class TestOrionLayoutTemplates:
    def test_orion_internal_html_exists(self):
        assert Path("templates/layouts/orion_internal.html").exists()

    def test_orion_internal_sidebar_exists(self):
        assert Path("templates/layouts/_orion_internal_sidebar.html").exists()

    def test_messages_partial_exists(self):
        assert Path("templates/layouts/_messages.html").exists()

    def test_orion_admin_layout_exists(self):
        assert Path("templates/layouts/orion_admin.html").exists()

    def test_private_suite_layout_exists(self):
        assert Path("templates/layouts/private_suite.html").exists()

    def test_enterprise_layout_exists(self):
        assert Path("templates/layouts/enterprise.html").exists()

    def test_orion_internal_is_standalone(self):
        """orion_internal.html must NOT extend base.html (it's a standalone layout)."""
        content = Path("templates/layouts/orion_internal.html").read_text(encoding="utf-8")
        assert '{% extends' not in content, (
            "orion_internal.html must be a standalone layout, not extending another template"
        )

    def test_orion_internal_loads_internal_css(self):
        content = Path("templates/layouts/orion_internal.html").read_text(encoding="utf-8")
        assert "orion/css/orion-internal.css" in content

    def test_orion_internal_includes_bootstrap_cdn(self):
        content = Path("templates/layouts/orion_internal.html").read_text(encoding="utf-8")
        assert "bootstrap@5" in content or "bootstrap.min.css" in content

    def test_child_layouts_extend_orion_internal(self):
        for name in ["orion_admin.html", "private_suite.html", "enterprise.html"]:
            path = Path("templates/layouts") / name
            content = path.read_text(encoding="utf-8")
            assert 'layouts/orion_internal.html' in content, (
                f"{name} must extend layouts/orion_internal.html"
            )


# ── 3. Public sites: no internal theme leak ───────────────────────────────

class TestNoInternalThemeOnPublicSites:
    FORBIDDEN_PATTERNS = [
        "orion-internal.css",
        "orion-erp.css",
        "orion-app-shell",
        "orion-sidebar",
        "erp-shell",
    ]

    def _get_public_html_files(self):
        files = []
        for d in PUBLIC_DIRS:
            if d.exists():
                files.extend(d.rglob("*.html"))
        return files

    @pytest.mark.parametrize("pattern", FORBIDDEN_PATTERNS)
    def test_pattern_not_in_public_templates(self, pattern):
        violations = []
        for path in self._get_public_html_files():
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if pattern in text:
                violations.append(str(path))

        assert not violations, (
            f"Pattern {pattern!r} found in public templates:\n"
            + "\n".join(f"  {v}" for v in violations)
        )


# ── 4. Dashboard widget registry ─────────────────────────────────────────

class TestDashboardWidgetRegistry:
    def test_register_raises_on_duplicate_code(self):
        from apps.dashboard_widgets.registry import (
            register_dashboard_widget,
            unregister_widget,
            DASHBOARD_WIDGETS,
        )
        import copy

        # Use a unique test code to avoid polluting the real registry
        test_code = "__test_duplicate_code__"
        original_state = copy.copy(DASHBOARD_WIDGETS)

        try:
            @register_dashboard_widget(code=test_code, title="Test Widget")
            def dummy_widget_1(**kw):
                return {}

            with pytest.raises(ValueError, match=test_code):
                @register_dashboard_widget(code=test_code, title="Another Widget")
                def dummy_widget_2(**kw):
                    return {}
        finally:
            unregister_widget(test_code)

    def test_list_widget_codes_returns_list(self):
        from apps.dashboard_widgets.registry import list_widget_codes
        codes = list_widget_codes()
        assert isinstance(codes, list)

    def test_deduplicate_widgets_returns_list(self):
        from apps.dashboard_widgets.services import deduplicate_widgets
        result = deduplicate_widgets()
        assert isinstance(result, list)

    def test_get_widgets_by_module_returns_dict(self):
        from apps.dashboard_widgets.services import get_widgets_by_module
        result = get_widgets_by_module()
        assert isinstance(result, dict)


# ── 5. Menu deduplication ─────────────────────────────────────────────────

class TestMenuDeduplication:
    def test_deduplicate_nav_modules_removes_duplicates(self):
        from apps.core.menu_deduplication import deduplicate_nav_modules
        modules = [
            {"id": "dashboard", "label": "Dashboard"},
            {"id": "reports", "label": "Reports"},
            {"id": "dashboard", "label": "Dashboard (dup)"},
        ]
        result = deduplicate_nav_modules(modules)
        ids = [m["id"] for m in result]
        assert ids.count("dashboard") == 1
        assert len(result) == 2

    def test_deduplicate_preserves_order(self):
        from apps.core.menu_deduplication import deduplicate_nav_modules
        modules = [
            {"id": "a"},
            {"id": "b"},
            {"id": "c"},
            {"id": "a"},
        ]
        result = deduplicate_nav_modules(modules)
        assert [m["id"] for m in result] == ["a", "b", "c"]

    def test_deduplicate_nav_groups_merges_same_label(self):
        from apps.core.menu_deduplication import deduplicate_nav_groups
        groups = [
            {"label": "ERP", "items": [{"id": "module1"}]},
            {"label": "ERP", "items": [{"id": "module2"}]},
        ]
        result = deduplicate_nav_groups(groups)
        assert len(result) == 1
        assert len(result[0]["items"]) == 2

    def test_merge_nav_structures(self):
        from apps.core.menu_deduplication import merge_nav_structures
        base = [{"label": "Base", "items": [{"id": "x"}]}]
        extra = [{"label": "Base", "items": [{"id": "y"}]}, {"label": "Extra", "items": []}]
        result = merge_nav_structures(base, extra)
        labels = [g["label"] for g in result]
        assert "Base" in labels
        assert "Extra" in labels
        assert labels.count("Base") == 1

    def test_find_duplicate_module_ids(self):
        from apps.core.menu_deduplication import find_duplicate_module_ids
        modules = [
            {"id": "x"},
            {"id": "y"},
            {"id": "x"},
            {"id": "z"},
            {"id": "y"},
        ]
        dupes = find_duplicate_module_ids(modules)
        assert set(dupes) == {"x", "y"}


# ── 6. Orion Internal CSS: no Bootstrap blue ─────────────────────────────

class TestOrionCSSNoBlueLeak:
    """Ensure the Orion Internal CSS doesn't hardcode Bootstrap blue (#0d6efd)."""

    FORBIDDEN_HEX = ["#0d6efd", "#007bff"]

    @pytest.mark.parametrize("filename", EXPECTED_CSS_FILES)
    def test_no_bootstrap_blue_in_css(self, filename):
        path = ORION_CSS_DIR / filename
        if not path.exists():
            pytest.skip(f"{filename} not found")
        content = path.read_text(encoding="utf-8")
        for hex_val in self.FORBIDDEN_HEX:
            assert hex_val not in content, (
                f"Bootstrap blue {hex_val!r} found in {filename}"
            )
