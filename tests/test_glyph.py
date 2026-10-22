"""Tests for the glyph handling in keymap_drawer.draw.glyph (GlyphMixin)."""

import pytest

from keymap_drawer.config import DrawConfig
from keymap_drawer.draw.glyph import GlyphMixin
from keymap_drawer.keymap import KeymapData

SVG = '<svg viewBox="0 0 24 24"><path d="M0 0"/></svg>'


class _Glyphs(GlyphMixin):
    """Concrete stand-in for the GlyphMixin."""


@pytest.fixture
def glyphs():
    obj = _Glyphs()
    obj.cfg = DrawConfig()
    obj.name_to_svg = {"foo": SVG}
    return obj


class TestLegendToName:
    def test_simple_glyph_reference(self):
        assert GlyphMixin._legend_to_name("$$foo$$") == "foo"

    def test_glyph_reference_inside_text(self):
        assert GlyphMixin._legend_to_name("x $$a:b$$ y") == "a:b"

    def test_plain_text_has_no_glyph(self):
        assert GlyphMixin._legend_to_name("plain") is None


class TestLegendIsGlyph:
    def test_known_glyph(self, glyphs):
        assert glyphs.legend_is_glyph("$$foo$$") == "foo"

    def test_unknown_glyph(self, glyphs):
        assert glyphs.legend_is_glyph("$$bar$$") is None

    def test_plain_text(self, glyphs):
        assert glyphs.legend_is_glyph("plain") is None


class TestGlyphDimensions:
    """Width/height/offsets derive from the viewBox aspect and per-type sizes."""

    def test_tap(self, glyphs):
        assert glyphs.get_glyph_dimensions("foo", "tap") == (14.0, 14, 7.0, 7.0)

    def test_hold(self, glyphs):
        assert glyphs.get_glyph_dimensions("foo", "hold") == (12.0, 12, 6.0, 12)

    def test_shifted(self, glyphs):
        assert glyphs.get_glyph_dimensions("foo", "shifted") == (10.0, 10, 5.0, 0)

    def test_left(self, glyphs):
        assert glyphs.get_glyph_dimensions("foo", "left") == (10.0, 10, 0, 5.0)

    def test_right(self, glyphs):
        assert glyphs.get_glyph_dimensions("foo", "right") == (10.0, 10, 10.0, 5.0)

    def test_corners(self, glyphs):
        assert glyphs.get_glyph_dimensions("foo", "tl") == (10.0, 10, 0, 0)
        assert glyphs.get_glyph_dimensions("foo", "br") == (10.0, 10, 10.0, 10)

    def test_non_square_viewbox_scales_width(self, glyphs):
        glyphs.name_to_svg = {"wide": '<svg viewBox="0 0 48 24"></svg>'}
        width, height, _, _ = glyphs.get_glyph_dimensions("wide", "tap")
        assert (width, height) == (28.0, 14)

    def test_unsupported_legend_type_raises(self, glyphs):
        with pytest.raises(ValueError, match="Unsupported legend_type"):
            glyphs.get_glyph_dimensions("foo", "bogus")


class TestGlyphDefs:
    def test_no_glyphs_gives_empty_string(self):
        obj = _Glyphs()
        obj.name_to_svg = {}
        assert obj.get_glyph_defs() == ""

    def test_defs_wrap_glyphs_and_scrub_dimensions(self):
        obj = _Glyphs()
        obj.name_to_svg = {"foo": '<svg width="24" height="24" viewBox="0 0 24 24">x</svg>'}
        defs = obj.get_glyph_defs()
        assert defs.startswith("<defs>/* start glyphs */")
        assert defs.endswith("</defs>/* end glyphs */\n")
        assert '<svg id="foo">' in defs
        assert 'width="24"' not in defs
        assert 'height="24"' not in defs


class TestInitGlyphs:
    def make(self, cfg, layers):
        obj = _Glyphs()
        obj.cfg = cfg
        obj.keymap = KeymapData(layers=layers, layout=None, config=None)
        return obj

    def test_glyphs_from_config_are_collected(self):
        obj = self.make(DrawConfig(glyphs={"foo": SVG}), {"L": ["$$foo$$", "A"]})
        obj.init_glyphs()
        assert obj.name_to_svg == {"foo": SVG}

    def test_glyphs_in_combo_keys_are_collected(self):
        obj = _Glyphs()
        obj.cfg = DrawConfig(glyphs={"foo": SVG})
        obj.keymap = KeymapData(
            layers={"L": ["A", "B"]},
            combos=[{"p": [0, 1], "k": "$$foo$$"}],
            layout=None,
            config=None,
        )
        obj.init_glyphs()
        assert obj.name_to_svg == {"foo": SVG}

    def test_no_glyph_legends_means_no_glyphs(self):
        obj = self.make(DrawConfig(), {"L": ["A"]})
        obj.init_glyphs()
        assert obj.name_to_svg == {}

    def test_glyph_without_viewbox_is_rejected(self):
        obj = self.make(DrawConfig(glyphs={"foo": "<svg>no viewbox</svg>"}), {"L": ["$$foo$$"]})
        with pytest.raises(ValueError, match='does not have the required "viewbox" property'):
            obj.init_glyphs()

    def test_undefined_and_unfetchable_glyph_is_rejected(self):
        # glyph_urls emptied so no network fetching is attempted.
        obj = self.make(DrawConfig(glyphs={}, glyph_urls={}), {"L": ["$$nope$$"]})
        with pytest.raises(ValueError, match="are not defined in draw_config.glyphs"):
            obj.init_glyphs()
