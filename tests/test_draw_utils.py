"""Tests for the low-level SVG helpers in keymap_drawer.draw.utils (UtilsMixin)."""

from io import StringIO

from keymap_drawer.config import DrawConfig
from keymap_drawer.physical_layout import Point


class TestStrToId:
    def test_empty_string(self, utils):
        assert utils._str_to_id("") == "o_o"

    def test_spaces_become_dashes(self, utils):
        assert utils._str_to_id("Base Layer") == "Base-Layer"

    def test_leading_non_letters_are_stripped(self, utils):
        assert utils._str_to_id("1Nav") == "Nav"
        assert utils._str_to_id("_foo") == "foo"

    def test_no_letters_at_all(self, utils):
        assert utils._str_to_id("!!!") == "x_x"
        assert utils._str_to_id("9") == "x_x"

    def test_disallowed_characters_are_removed(self, utils):
        assert utils._str_to_id("a b@c#d") == "a-bcd"

    def test_allowed_punctuation_is_kept(self, utils):
        assert utils._str_to_id("a:b.c_d") == "a:b.c_d"


class TestToClassStr:
    def test_no_classes(self, utils):
        assert utils._to_class_str([]) == ""

    def test_empty_class_names_are_filtered(self, utils):
        assert utils._to_class_str(["a", "", "b"]) == ' class="a b"'

    def test_single_class(self, utils):
        assert utils._to_class_str(["key"]) == ' class="key"'


class TestSplitText:
    def test_splits_on_whitespace(self, utils):
        assert utils._split_text("hello world") == ["hello", "world"]

    def test_double_space_is_preserved_within_a_word(self, utils):
        assert utils._split_text("hello  world") == ["hello world"]

    def test_empty_text(self, utils):
        assert utils._split_text("") == []

    def test_truncation_replaces_tail_with_ellipsis(self, utils):
        assert utils._split_text("one two three four", truncate=2) == ["one", "…"]

    def test_zero_truncate_means_no_truncation(self, utils):
        assert utils._split_text("one two three", truncate=0) == ["one", "two", "three"]

    def test_long_word_is_wrapped_on_word_boundaries(self, utils):
        assert utils._split_text("aaaa-bbbb-cccc", truncate=5, line_width=5) == ["aaaa-", "bbbb-", "cccc"]

    def test_unsplittable_long_word_is_left_alone(self, utils):
        assert utils._split_text("abcdefghij klmnop", truncate=3, line_width=5) == ["abcdefghij", "klmnop"]

    def test_glyph_legend_is_never_split(self, utils):
        utils.name_to_svg = {"foo": "<svg viewBox='0 0 1 1'></svg>"}
        assert utils._split_text("$$foo$$ bar baz") == ["$$foo$$ bar baz"]


class TestScalingAndTruncation:
    def test_scaling_empty_below_limit(self, utils):
        assert utils._get_scaling(7) == ""

    def test_scaling_percentage(self, utils):
        # Default shrink_wide_legends is 7: 100 * 7 / 8 = 87.5 -> 88%.
        assert utils._get_scaling(8) == ' style="font-size: 88%"'

    def test_scaling_has_a_floor_of_60_percent(self, utils):
        assert utils._get_scaling(14) == ' style="font-size: 60%"'
        assert utils._get_scaling(100) == ' style="font-size: 60%"'

    def test_scaling_disabled_when_limit_is_zero(self, utils):
        utils.cfg = DrawConfig(shrink_wide_legends=0)
        assert utils._get_scaling(100) == ""

    def test_truncate_word_at_boundary(self, utils):
        # Limit is int(1.7 * 7) = 11 chars.
        assert utils._truncate_word("a" * 11) == "a" * 11
        assert utils._truncate_word("a" * 12) == "a" * 10 + "…"

    def test_truncate_word_disabled_when_limit_is_zero(self, utils):
        utils.cfg = DrawConfig(shrink_wide_legends=0)
        assert utils._truncate_word("a" * 50) == "a" * 50


class TestDrawPrimitives:
    def test_draw_rect_exact_output(self, utils):
        utils._draw_rect(Point(10, 10), Point(60, 56), Point(6, 6), ["key"])
        assert utils.out.getvalue() == (
            '<rect rx="6" ry="6" x="-20" y="-18" width="60" height="56" class="key"/>\n'
        )

    def test_draw_text_escapes_html(self, utils):
        utils._draw_text(Point(5, 5), "A&B", ["key"])
        assert utils.out.getvalue() == '<text x="5" y="5" class="key">A&amp;B</text>\n'

    def test_draw_text_with_empty_word_writes_nothing(self, utils):
        utils._draw_text(Point(5, 5), "", ["key"])
        assert utils.out.getvalue() == ""

    def test_draw_textblock_exact_output(self, utils):
        utils._draw_textblock(Point(0, 0), ["one", "two"], ["key"])
        assert utils.out.getvalue() == (
            '<text x="0" y="0" class="key">\n'
            '<tspan x="0" dy="-0.6em">one</tspan>'
            '<tspan x="0" dy="1.2em">two</tspan>\n'
            "</text>\n"
        )

    def test_draw_key_without_sides_draws_one_rect(self, utils):
        utils._draw_key(Point(56, 52), ["key"])
        assert utils.out.getvalue().count("<rect") == 1

    def test_draw_key_with_sides_draws_two_rects(self, utils):
        utils.cfg = DrawConfig(draw_key_sides=True)
        utils.out = StringIO()
        utils._draw_key(Point(56, 52), ["key"])
        out = utils.out.getvalue()
        assert out.count("<rect") == 2
        assert 'class="key side"' in out

    def test_draw_legend_for_layer_activator_is_linked(self, utils):
        utils.layer_names = {"Nav"}
        utils._draw_legend(Point(0, 0), ["Nav"], ["key"], "tap")
        out = utils.out.getvalue()
        assert '<a href="#Nav">' in out
        assert 'class="key tap layer-activator"' in out
        assert out.endswith("</a>")

    def test_draw_legend_plain(self, utils):
        utils._draw_legend(Point(0, 0), ["A"], ["key"], "tap")
        assert utils.out.getvalue() == '<text x="0" y="0" class="key tap">A</text>\n'

    def test_draw_legend_with_no_words_writes_nothing(self, utils):
        utils._draw_legend(Point(0, 0), [], ["key"], "tap")
        assert utils.out.getvalue() == ""
