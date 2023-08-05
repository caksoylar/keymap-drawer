"""
Module that contains the KeymapDrawer class which takes a physical layout,
keymap with layers and optionally combo definitions, then can draw an SVG
representation of the keymap using these two.
"""
from html import escape
from copy import deepcopy
from typing import Sequence, TextIO, Literal

from keymap_drawer.keymap import KeymapData, LayoutKey
from keymap_drawer.physical_layout import Point, PhysicalKey
from keymap_drawer.config import DrawConfig
from keymap_drawer.draw.glyph import GlyphMixin
from keymap_drawer.draw.combo_drawer import ComboDrawerMixin


LegendType = Literal["tap", "hold", "shifted"]


class KeymapDrawer(GlyphMixin, ComboDrawerMixin):
    """Class that draws a keyboard representation in SVG."""

    def __init__(self, config: DrawConfig, out: TextIO, **kwargs) -> None:
        self.cfg = config
        self.keymap = KeymapData(config=config, **kwargs)
        self.init_glyphs()
        assert self.keymap.layout is not None, "A PhysicalLayout must be provided for drawing"
        assert self.keymap.config is not None, "A DrawConfig must be provided for drawing"
        self.layout = self.keymap.layout
        self.out = out

    @staticmethod
    def _to_class_str(classes: Sequence[str]):
        return (' class="' + " ".join(c for c in classes if c) + '"') if classes else ""

    @staticmethod
    def _split_text(text: str) -> list[str]:
        # do not split on double spaces, but do split on single
        return [word.replace("\x00", " ") for word in text.replace("  ", "\x00").split()]

    def _draw_rect(self, p: Point, dims: Point, radii: Point, classes: Sequence[str]) -> None:
        self.out.write(
            f'<rect rx="{round(radii.x)}" ry="{round(radii.y)}"'
            f' x="{round(p.x - dims.x / 2)}" y="{round(p.y - dims.y / 2)}" '
            f'width="{round(dims.x)}" height="{round(dims.y)}"{self._to_class_str(classes)}/>\n'
        )

    def _draw_key(self, p: Point, dims: Point, classes: Sequence[str]) -> None:
        if self.cfg.draw_key_sides:
            # draw side rectangle
            self._draw_rect(
                p,
                dims,
                Point(self.cfg.key_rx, self.cfg.key_ry),
                classes=[*classes, "side"],
            )
            # draw internal rectangle
            self._draw_rect(
                p - Point(self.cfg.key_side_pars.rel_x, self.cfg.key_side_pars.rel_y),
                dims - Point(self.cfg.key_side_pars.rel_w, self.cfg.key_side_pars.rel_h),
                Point(self.cfg.key_side_pars.rx, self.cfg.key_side_pars.ry),
                classes=classes,
            )
        else:
            # default key style
            self._draw_rect(
                p,
                dims,
                Point(self.cfg.key_rx, self.cfg.key_ry),
                classes=classes,
            )

    def _get_scaling(self, width: int) -> str:
        if not self.cfg.shrink_wide_legends or width <= self.cfg.shrink_wide_legends:
            return ""
        return f' style="font-size: {max(60.0, 100 * self.cfg.shrink_wide_legends / width):.0f}%"'

    def _draw_text(self, p: Point, word: str, classes: Sequence[str]) -> None:
        if not word:
            return
        self.out.write(
            f'<text x="{round(p.x)}" y="{round(p.y)}"{self._to_class_str(classes)}{self._get_scaling(len(word))}>'
            f"{escape(word)}</text>\n"
        )

    def _draw_textblock(self, p: Point, words: Sequence[str], classes: Sequence[str], shift: float = 0) -> None:
        self.out.write(
            f'<text x="{round(p.x)}" y="{round(p.y)}"{self._to_class_str(classes)}'
            f"{self._get_scaling(max(len(w) for w in words))}>\n"
        )
        dy_0 = (len(words) - 1) * (self.cfg.line_spacing * (1 + shift) / 2)
        self.out.write(f'<tspan x="{p.x}" dy="-{dy_0}em">{escape(words[0])}</tspan>')
        for word in words[1:]:
            self.out.write(f'<tspan x="{p.x}" dy="{self.cfg.line_spacing}em">{escape(word)}</tspan>')
        self.out.write("</text>\n")

    def _draw_glyph(self, p: Point, name: str, legend_type: LegendType, classes: Sequence[str]) -> None:
        width, height, d_y = self.get_glyph_dimensions(name, legend_type)

        classes = [*classes, "glyph", name]
        self.out.write(
            f'<use href="#{name}" xlink:href="#{name}" x="{round(p.x - (width / 2))}" y="{round(p.y - d_y)}" '
            f'height="{height}" width="{width}"{self._to_class_str(classes)}/>\n'
        )

    def print_layer_header(self, p: Point, header: str) -> None:
        """Print a layer header that precedes the layer visualization."""
        if self.cfg.append_colon_to_layer_header:
            header += ":"
        self.out.write(f'<text x="{p.x}" y="{p.y}" class="label">{escape(header)}</text>\n')

    def print_key(self, p_0: Point, p_key: PhysicalKey, l_key: LayoutKey) -> None:
        """
        Given anchor coordinates p_0, print SVG code for a rectangle with text representing
        the key, which is described by its physical representation (p_key) and what it does in
        the given layer (l_key).
        """
        p, w, h, r = (
            p_0 + p_key.pos,
            p_key.width,
            p_key.height,
            p_key.rotation,
        )
        if r != 0:
            self.out.write(f'<g transform="rotate({r}, {round(p.x)}, {round(p.y)})">\n')
        self._draw_key(
            p, Point(w - 2 * self.cfg.inner_pad_w, h - 2 * self.cfg.inner_pad_h), classes=[l_key.type, "key"]
        )

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
            p + tap_shift,
            tap_words,
            key_type=l_key.type,
            legend_type="tap",
            shift=shift,
        )
        self._draw_legend(
            p + Point(0, h / 2 - self.cfg.inner_pad_h - self.cfg.small_pad),
            [l_key.hold],
            key_type=l_key.type,
            legend_type="hold",
        )
        self._draw_legend(
            p - Point(0, h / 2 - self.cfg.inner_pad_h - self.cfg.small_pad),
            [l_key.shifted],
            key_type=l_key.type,
            legend_type="shifted",
        )

        if r != 0:
            self.out.write("</g>\n")

    def _draw_legend(  # pylint: disable=too-many-arguments
        self, p: Point, words: Sequence[str], key_type: str, legend_type: LegendType, shift: float = 0
    ):
        if not words:
            return

        classes = [key_type, legend_type]

        if len(words) == 1:
            if glyph := self.legend_is_glyph(words[0]):
                self._draw_glyph(p, glyph, legend_type, classes)
                return

            self._draw_text(p, words[0], classes)
            return

        self._draw_textblock(p, words, classes, shift)

    def print_layer(self, p_0: Point, layer_keys: Sequence[LayoutKey], empty_layer: bool = False) -> None:
        """
        Given anchor coordinates p_0, print SVG code for keys for a given layer.
        """
        for p_key, l_key in zip(self.layout.keys, layer_keys):
            self.print_key(p_0, p_key, l_key if not empty_layer else LayoutKey())

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
        offsets_per_layer = self.get_offsets_per_layer(combos_per_layer)

        board_w = self.layout.width + 2 * self.cfg.outer_pad_w
        board_h = (
            len(layers) * self.layout.height
            + (len(layers) + 1) * self.cfg.outer_pad_h
            + sum(top_offset + bot_offset for top_offset, bot_offset in offsets_per_layer.values())
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
            self.out.write(f'<g class="layer-{name}">\n')

            # draw layer name
            self.print_layer_header(p + Point(0, self.cfg.outer_pad_h / 2), name)

            # get offsets added by combo alignments, draw keys and combos
            p += Point(0, self.cfg.outer_pad_h + offsets_per_layer[name][0])
            self.print_layer(p, layer_keys, empty_layer=combos_only)
            self.print_combos_for_layer(p, combos_per_layer[name])
            p += Point(0, self.layout.height + offsets_per_layer[name][1])

            self.out.write("</g>\n")

        self.out.write("</svg>\n")
