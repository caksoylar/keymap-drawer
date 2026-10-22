"""Tests for keymap_drawer.config defaults and environment overrides.

Only the offline parts are covered: pydantic field defaults, derived values
and KEYMAP_-prefixed environment variables handled by pydantic-settings.
"""

from keymap_drawer.config import Config, DrawConfig, ParseConfig


class TestDrawConfigDefaults:
    def test_key_dimensions(self, draw_config):
        assert draw_config.key_w == 60
        assert draw_config.key_h == 56
        assert (draw_config.key_rx, draw_config.key_ry) == (6, 6)

    def test_derived_dimensions(self, draw_config):
        # split_gap, combo box size and outer pads are derived from key_w/key_h.
        assert draw_config.split_gap == 30
        assert draw_config.combo_w == 28
        assert draw_config.combo_h == 26
        assert draw_config.outer_pad_w == 30
        assert draw_config.outer_pad_h == 56

    def test_padding_and_spacing(self, draw_config):
        assert draw_config.inner_pad_w == 2
        assert draw_config.inner_pad_h == 2
        assert draw_config.line_spacing == 1.2
        assert draw_config.small_pad == 2.0

    def test_drawing_toggles_default_off(self, draw_config):
        assert draw_config.dark_mode is False
        assert draw_config.n_columns == 1
        assert draw_config.separate_combo_diagrams is False
        assert draw_config.draw_key_sides is False
        assert draw_config.footer_text == ""
        assert draw_config.svg_extra_style == ""

    def test_layer_header_and_activator_defaults(self, draw_config):
        assert draw_config.append_colon_to_layer_header is True
        assert draw_config.style_layer_activators is True
        assert draw_config.shrink_wide_legends == 7

    def test_glyph_sizes(self, draw_config):
        assert draw_config.glyph_tap_size == 14
        assert draw_config.glyph_hold_size == 12
        assert draw_config.glyph_shifted_size == 10
        assert draw_config.glyphs == {}

    def test_default_glyph_url_sources(self, draw_config):
        assert set(draw_config.glyph_urls) == {"tabler", "mdi", "mdil", "material", "phosphor", "fa"}
        assert "{}" in draw_config.glyph_urls["tabler"]

    def test_key_side_pars_defaults(self, draw_config):
        pars = draw_config.key_side_pars
        assert (pars.rel_x, pars.rel_y) == (0, 4)
        assert (pars.rel_w, pars.rel_h) == (12, 12)
        assert (pars.rx, pars.ry) == (4, 4)

    def test_svg_style_contains_key_selectors(self, draw_config):
        assert "rect.key" in draw_config.svg_style
        assert "svg.keymap" in draw_config.svg_style
        assert "#3f4750" in draw_config.svg_style_dark

    def test_use_local_cache_default(self, draw_config):
        assert draw_config.use_local_cache is True

    def test_fields_can_be_overridden(self):
        cfg = DrawConfig(key_w=100, n_columns=3, dark_mode=True)
        assert cfg.key_w == 100
        assert cfg.n_columns == 3
        assert cfg.dark_mode is True
        # Derived-looking fields are plain defaults: they do not recompute.
        assert cfg.split_gap == 30


class TestParseConfigDefaults:
    def test_labels(self, parse_config):
        assert parse_config.sticky_label == "sticky"
        assert parse_config.toggle_label == "toggle"
        assert parse_config.tap_toggle_label == "tap-toggle"

    def test_trans_legend(self, parse_config):
        assert parse_config.trans_legend == {"t": "▽", "type": "trans"}

    def test_preprocess_and_skip_defaults(self, parse_config):
        assert parse_config.preprocess is True
        assert parse_config.skip_binding_parsing is False
        assert parse_config.raw_binding_map == {}
        assert parse_config.mark_alternate_layer_activators is False

    def test_prefix_lists(self, parse_config):
        assert parse_config.qmk_remove_keycode_prefix == ["KC_"]
        assert parse_config.zmk_remove_keycode_prefix == []

    def test_qmk_keycode_map_samples(self, parse_config):
        mapping = parse_config.qmk_keycode_map
        assert mapping["MINUS"] == "-"
        assert mapping["EQUAL"] == "="
        assert mapping["SLASH"] == "/"
        assert mapping["XXXXXXX"] == ""
        assert mapping["NO"] == ""

    def test_zmk_keycode_map_samples(self, parse_config):
        mapping = parse_config.zmk_keycode_map
        assert mapping["EXCL"] == "!"
        assert mapping["AT"] == "@"
        assert mapping["GRAVE"] == "`"

    def test_modifier_fn_map_defaults(self, parse_config):
        fn_map = parse_config.modifier_fn_map
        assert fn_map is not None
        assert fn_map.left_ctrl == "Ctl"
        assert fn_map.right_alt == "AltGr"
        assert fn_map.keycode_combiner == "{mods}+{key}"
        assert fn_map.mod_combiner == "{mod_1}+{mod_2}"
        assert fn_map.special_combinations == {
            "left_ctrl+left_alt+left_gui+left_shift": "Hyper",
            "left_ctrl+left_alt+left_shift": "Meh",
        }

    def test_modifier_fn_map_can_be_disabled(self):
        assert ParseConfig(modifier_fn_map=None).modifier_fn_map is None

    def test_zmk_preamble(self, parse_config):
        assert parse_config.zmk_preamble == "#define KEYMAP_DRAWER"
        assert parse_config.zmk_combos == {}
        assert parse_config.zmk_additional_includes == []


class TestConfig:
    def test_nested_configs(self, config):
        assert isinstance(config.draw_config, DrawConfig)
        assert isinstance(config.parse_config, ParseConfig)

    def test_nested_values_can_be_set(self):
        config = Config(draw_config={"key_w": 42}, parse_config={"sticky_label": "STK"})
        assert config.draw_config.key_w == 42
        assert config.parse_config.sticky_label == "STK"


class TestEnvironmentOverrides:
    """pydantic-settings reads KEYMAP_-prefixed environment variables."""

    def test_draw_config_env_override(self, monkeypatch):
        monkeypatch.setenv("KEYMAP_KEY_W", "42")
        assert DrawConfig().key_w == 42.0

    def test_parse_config_env_override(self, monkeypatch):
        monkeypatch.setenv("KEYMAP_STICKY_LABEL", "STK")
        assert ParseConfig().sticky_label == "STK"

    def test_env_does_not_leak_between_instances(self, monkeypatch):
        monkeypatch.setenv("KEYMAP_KEY_W", "42")
        assert DrawConfig().key_w == 42.0
        monkeypatch.delenv("KEYMAP_KEY_W")
        assert DrawConfig().key_w == 60
