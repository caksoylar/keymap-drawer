"""Structural tests for KeymapDrawer SVG output, plus an offline integration
test that loads one of the bundled example keymaps.

These assertions check the shape of the produced SVG string only; no files
are written and no glyphs are fetched from the network.
"""

from io import StringIO
from pathlib import Path

import pytest
import yaml

from keymap_drawer.config import Config
from keymap_drawer.draw import KeymapDrawer
from keymap_drawer.keymap import KeymapData

REPO_ROOT = Path(__file__).resolve().parent.parent


def draw(config=None, **kwargs):
    """Render a board into a string and return it."""
    out = StringIO()
    drawer = KeymapDrawer(config=config or Config(), out=out, **kwargs)
    return drawer, out


def simple_board(config=None, **kwargs):
    kwargs.setdefault("layout", {"ortho_layout": {"rows": 1, "columns": 2}})
    kwargs.setdefault("layers", {"Base": ["A", "B"]})
    drawer, out = draw(config, **kwargs)
    drawer.print_board()
    return out.getvalue()


class TestSvgStructure:
    def test_svg_document_shape(self):
        svg = simple_board()
        assert svg.startswith('<svg width="180" height="168" viewBox="0 0 180 168" class="keymap"')
        assert 'xmlns="http://www.w3.org/2000/svg"' in svg
        assert svg.rstrip().endswith("</svg>")

    def test_style_block_is_included(self):
        assert "<style>" in simple_board()
        assert "rect.key" in simple_board()

    def test_layer_header_and_legends_are_drawn(self):
        svg = simple_board(layers={"Base": ["A", {"t": "B", "h": "Ctrl"}]})
        assert "Base:" in svg
        assert ">A</text>" in svg
        assert ">B</text>" in svg
        assert "Ctrl" in svg

    def test_one_rect_per_key(self):
        svg = simple_board()
        assert svg.count("<rect") == 2

    def test_held_and_ghost_key_types_become_classes(self):
        svg = simple_board(layers={"Base": [{"t": "A", "type": "held"}, {"t": "B", "type": "ghost"}]})
        assert "held" in svg
        assert "ghost" in svg

    def test_footer_text_is_drawn(self):
        config = Config()
        config.draw_config.footer_text = "my footer"
        svg = simple_board(config)
        assert "my footer" in svg
        assert 'class="footer"' in svg

    def test_dark_mode_adds_dark_style(self):
        config = Config()
        config.draw_config.dark_mode = True
        assert "#3f4750" in simple_board(config)

    def test_auto_dark_mode_wraps_style_in_media_query(self):
        config = Config()
        config.draw_config.dark_mode = "auto"
        assert "prefers-color-scheme: dark" in simple_board(config)


class TestDrawingOptions:
    def test_draw_layers_subset(self):
        drawer, out = draw(
            layout={"ortho_layout": {"rows": 1, "columns": 2}},
            layers={"Base": ["A", "B"], "Nav": ["C", "D"]},
        )
        drawer.print_board(draw_layers=["Nav"])
        svg = out.getvalue()
        assert "Nav:" in svg
        assert "Base:" not in svg

    def test_draw_unknown_layer_raises(self):
        drawer, _ = draw(
            layout={"ortho_layout": {"rows": 1, "columns": 2}}, layers={"Base": ["A", "B"]}
        )
        with pytest.raises(AssertionError, match="not in the keymap"):
            drawer.print_board(draw_layers=["Nope"])

    def test_ghost_keys_option_marks_positions(self):
        drawer, out = draw(
            layout={"ortho_layout": {"rows": 1, "columns": 2}}, layers={"Base": ["A", "B"]}
        )
        drawer.print_board(ghost_keys=[0])
        assert "ghost" in out.getvalue()

    def test_ghost_keys_out_of_range_raises(self):
        drawer, _ = draw(
            layout={"ortho_layout": {"rows": 1, "columns": 2}}, layers={"Base": ["A", "B"]}
        )
        with pytest.raises(AssertionError, match="ghost_keys"):
            drawer.print_board(ghost_keys=[5])

    def test_keys_only_skips_combos(self):
        drawer, out = draw(
            layout={"ortho_layout": {"rows": 1, "columns": 2}},
            layers={"Base": ["A", "B"]},
            combos=[{"p": [0, 1], "k": "Esc"}],
        )
        drawer.print_board(keys_only=True)
        svg = out.getvalue()
        assert "Esc" not in svg
        assert ">A</text>" in svg


class TestCombosInSvg:
    def test_combo_is_drawn_on_layer(self):
        svg = simple_board(combos=[{"p": [0, 1], "k": "Esc"}])
        assert "Esc" in svg
        assert "combo" in svg

    def test_separate_combo_diagrams_get_their_own_section(self):
        config = Config()
        config.draw_config.separate_combo_diagrams = True
        svg = simple_board(config, combos=[{"p": [0, 1], "k": "Esc"}])
        assert "Combos" in svg
        assert "Esc" in svg


class TestBundledExample:
    """Load the shipped 4x12 MIT example: fully offline (ortho layout)."""

    def test_example_loads_into_keymap_data(self):
        data = yaml.safe_load((REPO_ROOT / "examples" / "4x12.MIT.yaml").read_text(encoding="utf-8"))
        keymap = KeymapData(config=Config(), **data)
        # 4 rows x 12 columns, with the MIT wide key replacing two 1u keys.
        assert len(keymap.layout) == 47
        assert list(keymap.layers) == ["Qwerty", "Lower", "Raise"]
        assert all(len(layer) == 47 for layer in keymap.layers.values())

    def test_example_draws_to_svg(self):
        data = yaml.safe_load((REPO_ROOT / "examples" / "4x12.MIT.yaml").read_text(encoding="utf-8"))
        out = StringIO()
        drawer = KeymapDrawer(config=Config(), out=out, **data)
        drawer.print_board()
        svg = out.getvalue()
        assert svg.startswith("<svg ")
        assert "Qwerty:" in svg
        assert svg.rstrip().endswith("</svg>")
