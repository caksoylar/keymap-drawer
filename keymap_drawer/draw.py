"""
Module that contains the KeymapDrawer class which takes a physical layout,
keymap with layers and optionally combo definitions, then can draw an SVG
representation of the keymap using these two.
"""
from math import copysign
from html import escape
from typing import Sequence, TextIO

from .keymap import KeymapData, ComboSpec, LayoutKey
from .physical_layout import Point, PhysicalKey
from .config import DrawConfig


class KeymapDrawer:
    """Class that draws a keyboard representation in SVG."""

    def __init__(self, config: DrawConfig, out: TextIO, **kwargs) -> None:
        self.cfg = config
        self.keymap = KeymapData(config=config, **kwargs)
        assert self.keymap.layout is not None, "A PhysicalLayout must be provided for drawing"
        assert self.keymap.config is not None, "A DrawConfig must be provided for drawing"
        self.layout = self.keymap.layout
        self.out = out

    @staticmethod
    def _split_text(text: str) -> list[str]:
        # do not split on double spaces, but do split on single
        return [word.replace("\x00", " ") for word in text.replace("  ", "\x00").split()]

    def _draw_rect(self, p: Point, w: float, h: float, cls: Sequence[str]) -> None:
        class_str = (' class="' + " ".join(c for c in cls if c) + '"') if cls else ""
        self.out.write(
            f'<rect rx="{self.cfg.key_rx}" ry="{self.cfg.key_ry}" x="{p.x - w / 2}" y="{p.y - h / 2}" '
            f'width="{w}" height="{h}"{class_str}/>\n'
        )

    def _draw_text(self, p: Point, words: Sequence[str], cls: Sequence[str], shift: float = 0) -> None:
        if not words or not words[0]:
            return

        class_str = (' class="' + " ".join(c for c in cls if c) + '"') if cls else ""
        if len(words) == 1:
            self.out.write(f'<text x="{p.x}" y="{p.y}"{class_str}>{escape(words[0])}</text>\n')
            return
        self.out.write(f'<text x="{p.x}" y="{p.y}"{class_str}>\n')
        dy_0 = (len(words) - 1) * (self.cfg.line_spacing * (1 + shift) / 2)
        self.out.write(f'<tspan x="{p.x}" dy="-{dy_0}em">{escape(words[0])}</tspan>')
        for word in words[1:]:
            self.out.write(f'<tspan x="{p.x}" dy="{self.cfg.line_spacing}em">{escape(word)}</tspan>')
        self.out.write("</text>\n")

    def _draw_arc_dendron(self, p_1: Point, p_2: Point, x_first: bool, shorten: float) -> None:
        start = f"M{p_1.x},{p_1.y}"
        arc_x = copysign(self.cfg.arc_radius, p_2.x - p_1.x)
        arc_y = copysign(self.cfg.arc_radius, p_2.y - p_1.y)
        clockwise = (p_2.x > p_1.x) ^ (p_2.y > p_1.y)
        if x_first:
            line_1 = f"h{self.cfg.arc_scale * (p_2.x - p_1.x) - arc_x}"
            line_2 = f"v{p_2.y - p_1.y - arc_y - copysign(shorten, p_2.y - p_1.y)}"
            clockwise = not clockwise
        else:
            line_1 = f"v{self.cfg.arc_scale * (p_2.y - p_1.y) - arc_y}"
            line_2 = f"h{p_2.x - p_1.x - arc_x - copysign(shorten, p_2.x - p_1.x)}"
        arc = f"a{self.cfg.arc_radius},{self.cfg.arc_radius} 0 0 {int(clockwise)} {arc_x},{arc_y}"
        self.out.write(f'<path d="{start} {line_1} {arc} {line_2}"/>\n')

    def _draw_line_dendron(self, p_1: Point, p_2: Point, shorten: float) -> None:
        start = f"M{p_1.x},{p_1.y}"
        diff = p_2 - p_1
        if shorten and shorten < (magn := abs(diff)):
            diff = Point((1 - shorten / magn) * diff.x, (1 - shorten / magn) * diff.y)
        line = f"l{diff.x},{diff.y}"
        self.out.write(f'<path d="{start} {line}"/>\n')

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
            assert p_key.rotation_pos is not None
            r_pos = p_0 + p_key.rotation_pos
            self.out.write(f'<g transform="rotate({r}, {r_pos.x}, {r_pos.y})">\n')
        self._draw_rect(p, w - 2 * self.cfg.inner_pad_w, h - 2 * self.cfg.inner_pad_h, cls=[l_key.type])

        tap_words = self._split_text(l_key.tap)

        # auto-adjust vertical alignment up/down if there are two lines and either hold/shifted is present
        tap_p = Point(p.x, p.y)
        shift = 0
        if len(tap_words) == 2:
            if l_key.shifted and not l_key.hold:  # shift down
                shift = -1
            elif l_key.hold and not l_key.shifted:  # shift up
                shift = 1
        self._draw_text(tap_p, tap_words, cls=[l_key.type, "tap"], shift=shift)

        self._draw_text(
            p + Point(0, h / 2 - self.cfg.inner_pad_h - self.cfg.small_pad), [l_key.hold], cls=[l_key.type, "hold"]
        )
        self._draw_text(
            p - Point(0, h / 2 - self.cfg.inner_pad_h - self.cfg.small_pad),
            [l_key.shifted],
            cls=[l_key.type, "shifted"],
        )
        if r != 0:
            self.out.write("</g>\n")

    def print_combo(self, p_0: Point, combo: ComboSpec) -> None:
        """
        Given anchor coordinates p_0, print SVG code for a rectangle with text representing
        a combo specification, which contains the key positions that trigger it and what it does
        when triggered. The position of the rectangle depends on the alignment specified,
        along with whether dendrons are drawn going to each key position from the combo.
        """
        p_keys = [self.layout.keys[p] for p in combo.key_positions]

        # find center of combo box
        p = p_0.copy()
        p_mid = (1 / len(p_keys)) * sum((k.pos for k in p_keys), start=Point(0, 0))
        match combo.align:
            case "mid":
                p += p_mid
            case "top":
                p += Point(
                    p_mid.x,
                    min(k.pos.y - k.height / 2 for k in p_keys)
                    - self.cfg.inner_pad_h / 2
                    - combo.offset * self.layout.min_height,
                )
            case "bottom":
                p += Point(
                    p_mid.x,
                    max(k.pos.y + k.height / 2 for k in p_keys)
                    + self.cfg.inner_pad_h / 2
                    + combo.offset * self.layout.min_height,
                )
            case "left":
                p += Point(
                    min(k.pos.x - k.width / 2 for k in p_keys)
                    - self.cfg.inner_pad_w / 2
                    - combo.offset * self.layout.min_width,
                    p_mid.y,
                )
            case "right":
                p += Point(
                    max(k.pos.x + k.width / 2 for k in p_keys)
                    + self.cfg.inner_pad_w / 2
                    + combo.offset * self.layout.min_width,
                    p_mid.y,
                )

        # draw dendrons going from box to combo keys
        if combo.dendron is not False:
            match combo.align:
                case "top" | "bottom":
                    for k in p_keys:
                        offset = k.height / 5 if abs(p_0.x + k.pos.x - p.x) < self.cfg.combo_w / 2 else k.height / 3
                        self._draw_arc_dendron(p, p_0 + k.pos, True, offset)
                case "left" | "right":
                    for k in p_keys:
                        offset = k.width / 5 if abs(p_0.y + k.pos.y - p.y) < self.cfg.combo_h / 2 else k.width / 3
                        self._draw_arc_dendron(p, p_0 + k.pos, False, offset)
                case "mid":
                    for k in p_keys:
                        if combo.dendron is True or abs(p_0 + k.pos - p) >= k.width - 1:
                            self._draw_line_dendron(p, p_0 + k.pos, k.width / 3)

        # draw combo box with text
        self._draw_rect(p, self.cfg.combo_w, self.cfg.combo_h, cls=[combo.type])
        self._draw_text(p, self._split_text(combo.key.tap), cls=[combo.type])
        self._draw_text(
            p + Point(0, self.cfg.combo_h / 2 - self.cfg.small_pad), [combo.key.hold], cls=[combo.type, "hold"]
        )
        self._draw_text(
            p - Point(0, self.cfg.combo_h / 2 - self.cfg.small_pad),
            [combo.key.shifted],
            cls=[combo.type, "shifted"],
        )

    def print_layer(
        self, p_0: Point, layer_keys: Sequence[LayoutKey], combos: Sequence[ComboSpec], empty_layer: bool = False
    ) -> None:
        """
        Given anchor coordinates p_0, print SVG code for keys and combos for a given layer.
        """
        for p_key, l_key in zip(self.layout.keys, layer_keys):
            self.print_key(p_0, p_key, l_key if not empty_layer else LayoutKey())
        for combo_spec in combos:
            self.print_combo(p_0, combo_spec)

    def print_board(
        self, draw_layers: Sequence[str] | None = None, keys_only: bool = False, combos_only: bool = False
    ) -> None:
        """Print SVG code representing the keymap."""
        layers = self.keymap.layers
        if draw_layers:
            assert all(l in layers for l in draw_layers), "Some layer names selected for drawing are not in the keymap"
            layers = {name: layer for name, layer in layers.items() if name in draw_layers}

        if not keys_only:
            combos_per_layer = self.keymap.get_combos_per_layer(layers)
        else:
            combos_per_layer = {layer_name: [] for layer_name in layers}
        offsets_per_layer = {
            name: (
                max((c.offset * self.layout.min_height for c in combos if c.align == "top"), default=0.0),
                max((c.offset * self.layout.min_height for c in combos if c.align == "bottom"), default=0.0),
            )
            for name, combos in combos_per_layer.items()
        }

        board_w = self.layout.width + 2 * self.cfg.outer_pad_w
        board_h = (
            len(layers) * self.layout.height
            + (len(layers) + 1) * self.cfg.outer_pad_h
            + sum(top_offset + bot_offset for top_offset, bot_offset in offsets_per_layer.values())
        )
        self.out.write(
            f'<svg width="{board_w}" height="{board_h}" viewBox="0 0 {board_w} {board_h}" '
            'xmlns="http://www.w3.org/2000/svg">\n'
        )
        self.out.write(f"<style>{self.cfg.svg_style}</style>\n")

        p = Point(self.cfg.outer_pad_w, 0.0)
        for name, layer_keys in layers.items():
            # per-layer class group
            self.out.write(f'<g class="layer-{name}">\n')

            # draw layer name
            layer_header = name
            if self.cfg.append_colon_to_layer_header:
                layer_header += ":"
            self._draw_text(p + Point(0, self.cfg.outer_pad_h / 2), [layer_header], cls=["label"])

            # get offsets added by combo alignments
            combo_offset_top, combo_offset_bot = offsets_per_layer[name]

            # draw keys and combos
            p += Point(0, self.cfg.outer_pad_h + combo_offset_top)
            self.print_layer(p, layer_keys, combos_per_layer[name], empty_layer=combos_only)
            p += Point(0, self.layout.height + combo_offset_bot)

            self.out.write("</g>\n")

        self.out.write("</svg>\n")
