"""
Module that contains the KeymapDrawer class which takes a physical layout,
keymap with layers and optionally combo definitions, then can draw an SVG
representation of the keymap using these two.
"""

from copy import deepcopy
from html import escape
from io import StringIO
from typing import Mapping, Sequence, TextIO

from keymap_drawer.config import DrawConfig
from keymap_drawer.draw.combo import ComboDrawerMixin
from keymap_drawer.draw.utils import UtilsMixin
from keymap_drawer.keymap import ComboSpec, KeymapData, LayoutKey
from keymap_drawer.physical_layout import PhysicalKey, PhysicalLayout, Point


class KeymapDrawer(ComboDrawerMixin, UtilsMixin):
    """Class that draws a keyboard representation in SVG."""

    def __init__(self, config: DrawConfig, out: TextIO, **kwargs) -> None:
        self.cfg = config
        self.keymap = KeymapData(config=config, **kwargs)
        self.init_glyphs()
        assert self.keymap.layout is not None, "A PhysicalLayout must be provided for drawing"
        assert self.keymap.config is not None, "A DrawConfig must be provided for drawing"
        self.layout = self.keymap.layout
        self.output_stream = out
        self.out = StringIO()

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

    def print_layers(  # pylint: disable=too-many-arguments,too-many-locals
        self,
        p: Point,
        layout: PhysicalLayout,
        layers: Mapping[str, Sequence[LayoutKey]],
        combos_per_layer: Mapping[str, Sequence[ComboSpec]],
        n_cols: int = 1,
        draw_header: bool = True,
        pad_divisor: int = 1,
    ) -> Point:
        """
        Print SVG code for keys for all layers (including combos on them) starting at coordinate p,
        into n_cols columns and return the bottom right coordinate.
        """
        outer_pad_w = self.cfg.outer_pad_w // pad_divisor
        p += Point(self.cfg.outer_pad_w - outer_pad_w, 0)
        original_x = p.x
        col_width = layout.width + 2 * outer_pad_w
        max_height = 0.0
        for ind, (name, layer_keys) in enumerate(layers.items()):
            outer_pad_h = self.cfg.outer_pad_h // pad_divisor if ind > n_cols - 1 else self.cfg.outer_pad_h

            # per-layer class group
            self.out.write(
                f'<g transform="translate({round(p.x + outer_pad_w)}, {round(p.y)})" class="layer-{escape(name)}">\n'
            )

            # draw layer name
            if draw_header:
                self.print_layer_header(Point(0, outer_pad_h / 2), name)

            # back up main buffer, create and start writing to a temp output buffer
            with StringIO() as temp_buffer:
                writer = self.out
                self.out = temp_buffer

                # draw keys to temp buffer
                for key_ind, (p_key, l_key) in enumerate(zip(layout.keys, layer_keys)):
                    self.print_key(p_key, l_key, key_ind)

                # draw combos to temp buffer and calculate top/bottom y coordinates
                min_y, max_y = self.print_combos_for_layer(combos_per_layer.get(name, []))
                top_y = 0.0 if min_y is None else min(0.0, min_y)
                bottom_y = layout.height if max_y is None else max(layout.height, max_y)

                # shift by the top y coordinate, then dump the temp buffer
                writer.write(f'<g transform="translate(0, {round(outer_pad_h - top_y)})">\n')
                writer.write(temp_buffer.getvalue())
                writer.write("</g>\n")
                writer.write("</g>\n")
            self.out = writer

            max_height = max(max_height, bottom_y - top_y)

            if ind % n_cols == n_cols - 1 or ind == len(layers) - 1:
                p = Point(original_x, p.y + outer_pad_h + max_height)
                max_height = 0.0
            else:
                p += Point(col_width, 0)

        return Point(original_x + col_width * n_cols, p.y)

    def print_board(
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

        if combos_only:
            if not self.cfg.separate_combo_diagrams:
                layers = {name: [LayoutKey() for _ in range(len(self.layout))] for name, layer in layers.items()}
            else:
                layers = {}

        if ghost_keys:
            for key_position in ghost_keys:
                assert (
                    0 <= key_position < len(self.layout)
                ), "Some key positions for `ghost_keys` are negative or too large for the layout"
                for layer in layers.values():
                    layer[key_position].type = "ghost"

        if keys_only or self.cfg.separate_combo_diagrams:
            combos_per_layer: dict[str, list[ComboSpec]] = {}
        else:
            combos_per_layer = self.keymap.get_combos_per_layer(layers)

        # write to internal output stream self.out
        p = self.print_layers(Point(0, 0), self.layout, layers, combos_per_layer, self.cfg.n_columns)

        if self.cfg.separate_combo_diagrams:
            self.print_layer_header(Point(self.cfg.outer_pad_w, p.y + self.cfg.outer_pad_h / 2), "Combos")
            layout, layers = self.create_combo_diagrams(self.cfg.combo_diagrams_scale, ghost_keys)
            p = self.print_layers(
                Point(0, p.y),
                layout,
                layers,
                combos_per_layer,
                self.cfg.n_columns * self.cfg.combo_diagrams_scale,
                draw_header=False,
                pad_divisor=self.cfg.combo_diagrams_scale,
            )

        # write to final output stream self.output_stream
        board_w, board_h = round(p.x), round(p.y + self.cfg.outer_pad_h)
        self.output_stream.write(
            f'<svg width="{board_w}" height="{board_h}" viewBox="0 0 {board_w} {board_h}" class="keymap" '
            'xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">\n'
        )
        self.output_stream.write(self.get_glyph_defs())
        extra_style = f"\n{self.cfg.svg_extra_style}" if self.cfg.svg_extra_style else ""
        self.output_stream.write(f"<style>{self.cfg.svg_style}{extra_style}</style>\n")
        self.output_stream.write(self.out.getvalue())
        self.output_stream.write("</svg>\n")
