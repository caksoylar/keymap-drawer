"""
Module that contains the KeymapDrawer class which takes a physical layout,
keymap with layers and optionally combo definitions, then can draw an SVG
representation of the keymap using these two.
"""

from html import escape
from copy import deepcopy
from typing import Sequence, TextIO

from keymap_drawer.keymap import KeymapData, LayoutKey
from keymap_drawer.physical_layout import Point, PhysicalKey
from keymap_drawer.config import DrawConfig
from keymap_drawer.draw.utils import UtilsMixin
from keymap_drawer.draw.combo import ComboDrawerMixin


class KeymapDrawer(ComboDrawerMixin, UtilsMixin):
    """Class that draws a keyboard representation in SVG."""

    def __init__(self, config: DrawConfig, out: TextIO, **kwargs) -> None:
        self.cfg = config
        self.keymap = KeymapData(config=config, **kwargs)
        self.init_glyphs()
        assert self.keymap.layout is not None, "A PhysicalLayout must be provided for drawing"
        assert self.keymap.config is not None, "A DrawConfig must be provided for drawing"
        self.layout = self.keymap.layout
        self.out = out

    def print_layer_header(self, p: Point, header: str) -> None:
        """Print a layer header that precedes the layer visualization."""
        if self.cfg.append_colon_to_layer_header:
            header += ":"
        self.out.write(f'<text x="{round(p.x)}" y="{round(p.y)}" class="label">{escape(header)}</text>\n')

    def print_key(self, p_key: PhysicalKey, l_key: LayoutKey, key_ind: int) -> None:
        """
        Print SVG code for a rectangle with text representing the key, which is described by its physical
        representation (p_key) and what it does in the given layer (l_key).
        """
        p, w, h, r = (
            p_key.pos,
            p_key.width,
            p_key.height,
            p_key.rotation,
        )
        rotate_str = f" rotate({r})" if r != 0 else ""
        transform_attr = f' transform="translate({round(p.x)}, {round(p.y)}){rotate_str}"'
        class_str = self._to_class_str(["key", l_key.type, f"keypos-{key_ind}"])
        self.out.write(f"<g{transform_attr}{class_str}>\n")

        self._draw_key(Point(w - 2 * self.cfg.inner_pad_w, h - 2 * self.cfg.inner_pad_h), classes=["key", l_key.type])

        tap_words = self._split_text(l_key.tap)

        # auto-adjust vertical alignment up/down if there are two lines and either hold/shifted is present
        shift = 0
        if len(tap_words) == 2:
            if l_key.shifted and not l_key.hold:  # shift down
                shift = -1
            elif l_key.hold and not l_key.shifted:  # shift up
                shift = 1

        # auto-shift middle legend if key sides are drawn
        tap_shift = Point(self.cfg.legend_rel_x, self.cfg.legend_rel_y)
        if self.cfg.draw_key_sides:
            tap_shift -= Point(self.cfg.key_side_pars.rel_x, self.cfg.key_side_pars.rel_y)

        self._draw_legend(
            tap_shift,
            tap_words,
            classes=["key", l_key.type],
            legend_type="tap",
            shift=shift,
        )
        self._draw_legend(
            Point(0, h / 2 - self.cfg.inner_pad_h - self.cfg.small_pad),
            [l_key.hold],
            classes=["key", l_key.type],
            legend_type="hold",
        )
        self._draw_legend(
            Point(0, -h / 2 + self.cfg.inner_pad_h + self.cfg.small_pad),
            [l_key.shifted],
            classes=["key", l_key.type],
            legend_type="shifted",
        )

        self.out.write("</g>\n")

    def print_layer(self, layer_keys: Sequence[LayoutKey], empty_layer: bool = False) -> None:
        """
        Print SVG code for keys for a given layer.
        """
        for key_ind, (p_key, l_key) in enumerate(zip(self.layout.keys, layer_keys)):
            self.print_key(p_key, l_key if not empty_layer else LayoutKey(), key_ind)

    def print_board(  # pylint: disable=too-many-locals
        self,
        draw_layers: Sequence[str] | None = None,
        keys_only: bool = False,
        combos_only: bool = False,
        ghost_keys: Sequence[int] | None = None,
    ) -> None:
        """Print SVG code representing the keymap."""
        layers = deepcopy(self.keymap.layers)
        if draw_layers:
            assert all(l in layers for l in draw_layers), "Some layer names selected for drawing are not in the keymap"
            layers = {name: layer for name, layer in layers.items() if name in draw_layers}

        if ghost_keys:
            for key_position in ghost_keys:
                assert (
                    0 <= key_position < len(self.layout)
                ), "Some key positions for `ghost_keys` are negative or too large for the layout"
                for layer in layers.values():
                    layer[key_position].type = "ghost"

        if not keys_only:
            combos_per_layer = self.keymap.get_combos_per_layer(layers)
        else:
            combos_per_layer = {layer_name: [] for layer_name in layers}

        board_w = round(self.layout.width + 2 * self.cfg.outer_pad_w)
        board_h = round(
            len(layers) * self.layout.height
            + (len(layers) + 1) * self.cfg.outer_pad_h
            + sum(sum(self.get_combo_offsets(combos)) for combos in combos_per_layer.values())
        )
        self.out.write(
            f'<svg width="{board_w}" height="{board_h}" viewBox="0 0 {board_w} {board_h}" class="keymap" '
            'xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">\n'
        )

        self.out.write(self.get_glyph_defs())

        self.out.write(f"<style>{self.cfg.svg_style}</style>\n")

        p = Point(self.cfg.outer_pad_w, 0.0)
        for name, layer_keys in layers.items():
            # per-layer class group
            self.out.write(f'<g transform="translate({round(p.x)}, {round(p.y)})" class="layer-{name}">\n')

            # draw layer name
            self.print_layer_header(Point(0, self.cfg.outer_pad_h / 2), name)

            # get offsets added by combo alignments, draw keys and combos
            top_offset, bot_offset = self.get_combo_offsets(combos_per_layer[name])
            self.out.write(f'<g transform="translate(0, {round(self.cfg.outer_pad_h + top_offset)})">\n')
            self.print_layer(layer_keys, empty_layer=combos_only)
            self.print_combos_for_layer(combos_per_layer[name])
            self.out.write("</g>\n")
            self.out.write("</g>\n")

            p += Point(0, self.cfg.outer_pad_h + top_offset + self.layout.height + bot_offset)

        self.out.write("</svg>\n")
