"""
Bug B regression test – Selection: selected audio item text must be readable.

We parse the stylesheet and verify that every QListWidget item state defines
explicit, sufficiently contrasting foreground and background colors.
Contrast is measured as a simple luminance ratio (WCAG AA minimum = 4.5:1
for normal text).

This is an offscreen Qt test – no real window is required to be visible.
"""

import re
import sys
import unittest

from PySide6.QtWidgets import QApplication

_app = None


def _get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


def _parse_hex(color_str: str):
    """Return (r, g, b) from a #rrggbb or #rgb string, or None."""
    color_str = color_str.strip()
    if color_str.startswith("#"):
        h = color_str[1:]
        if len(h) == 6:
            return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        if len(h) == 3:
            return tuple(int(c*2, 16) for c in h)
    return None


def _relative_luminance(r, g, b):
    """WCAG 2.1 relative luminance."""
    def f(c):
        c /= 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _contrast_ratio(col1, col2):
    l1 = _relative_luminance(*col1)
    l2 = _relative_luminance(*col2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# States we expect to have explicit colors defined.
REQUIRED_STATES = [
    "QListWidget::item",
    "QListWidget::item:selected",
    "QListWidget::item:selected:active",
    "QListWidget::item:selected:!active",
    "QListWidget::item:focus",
    "QListWidget::item:hover",
    "QListWidget::item:disabled",
]


class TestSelectionContrast(unittest.TestCase):

    def setUp(self):
        _get_app()
        from src.ui.main_window import STYLE
        self.style = STYLE

    def _extract_block(self, selector: str) -> str:
        """Return the CSS block body for a given selector."""
        # Strip comments
        cleaned = re.sub(r'/\*.*?\*/', '', self.style, flags=re.DOTALL)
        pattern = re.escape(selector) + r'\s*\{([^}]*)\}'
        m = re.search(pattern, cleaned)
        return m.group(1) if m else ""

    def _get_color(self, block: str, prop: str):
        """Extract the color value for a CSS property from a block."""
        m = re.search(rf'{re.escape(prop)}\s*:\s*([^;]+);', block)
        if not m:
            return None
        return _parse_hex(m.group(1).strip())

    def test_all_required_states_defined(self):
        """Every required item state must have explicit color and background-color."""
        missing = []
        for state in REQUIRED_STATES:
            block = self._extract_block(state)
            if not block:
                missing.append(f"{state}: block not found")
                continue
            if not self._get_color(block, "color"):
                missing.append(f"{state}: missing 'color'")
            if not self._get_color(block, "background"):
                missing.append(f"{state}: missing 'background'")
        self.assertEqual(missing, [], "\n".join(missing))

    def test_selected_state_contrast_ratio(self):
        """Selected item (active) must meet WCAG AA contrast ≥ 4.5:1."""
        block = self._extract_block("QListWidget::item:selected:active")
        if not block:
            block = self._extract_block("QListWidget::item:selected")
        fg = self._get_color(block, "color")
        bg = self._get_color(block, "background")
        self.assertIsNotNone(fg, "No foreground color found for selected:active state")
        self.assertIsNotNone(bg, "No background color found for selected:active state")
        ratio = _contrast_ratio(fg, bg)
        self.assertGreaterEqual(
            ratio, 4.5,
            f"Selected:active contrast ratio {ratio:.2f}:1 is below WCAG AA minimum 4.5:1 "
            f"(fg={fg}, bg={bg})"
        )

    def test_selected_inactive_contrast_ratio(self):
        """Selected item (inactive / unfocused) must also be readable (≥ 4.5:1)."""
        block = self._extract_block("QListWidget::item:selected:!active")
        fg = self._get_color(block, "color")
        bg = self._get_color(block, "background")
        self.assertIsNotNone(fg, "No foreground color for selected:!active")
        self.assertIsNotNone(bg, "No background color for selected:!active")
        ratio = _contrast_ratio(fg, bg)
        self.assertGreaterEqual(
            ratio, 4.5,
            f"Selected:!active contrast ratio {ratio:.2f}:1 < 4.5:1 (fg={fg}, bg={bg})"
        )

    def test_hover_state_contrast_ratio(self):
        """Hovered (unselected) item must be readable (≥ 4.5:1)."""
        block = self._extract_block("QListWidget::item:hover")
        fg = self._get_color(block, "color")
        bg = self._get_color(block, "background")
        self.assertIsNotNone(fg, "No foreground color for :hover")
        self.assertIsNotNone(bg, "No background color for :hover")
        ratio = _contrast_ratio(fg, bg)
        self.assertGreaterEqual(
            ratio, 4.5,
            f"Hover contrast ratio {ratio:.2f}:1 < 4.5:1 (fg={fg}, bg={bg})"
        )


    def test_focus_state_contrast_ratio(self):
        """Focused item must meet WCAG AA contrast ≥ 4.5:1."""
        block = self._extract_block("QListWidget::item:focus")
        fg = self._get_color(block, "color")
        bg = self._get_color(block, "background")
        self.assertIsNotNone(fg, "No foreground color for :focus")
        self.assertIsNotNone(bg, "No background color for :focus")
        ratio = _contrast_ratio(fg, bg)
        self.assertGreaterEqual(
            ratio, 4.5,
            f"Focus contrast ratio {ratio:.2f}:1 < 4.5:1 (fg={fg}, bg={bg})"
        )

    def test_disabled_state_contrast_ratio(self):
        """Disabled item must maintain legible contrast (≥ 3.0:1 for disabled text)."""
        block = self._extract_block("QListWidget::item:disabled")
        fg = self._get_color(block, "color")
        bg = self._get_color(block, "background")
        self.assertIsNotNone(fg, "No foreground color for :disabled")
        self.assertIsNotNone(bg, "No background color for :disabled")
        ratio = _contrast_ratio(fg, bg)
        self.assertGreaterEqual(
            ratio, 3.0,
            f"Disabled contrast ratio {ratio:.2f}:1 < 3.0:1 (fg={fg}, bg={bg})"
        )


if __name__ == "__main__":
    unittest.main()
