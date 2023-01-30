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
        self.out = out

    def _draw_rect(self, p: Point, w: float, h: float, cls: str | None = None) -> None:
        class_str = f' class="{cls}"' if cls is not None else ""
        self.out.write(
            f'<rect rx="{self.cfg.key_rx}" ry="{self.cfg.key_ry}" x="{p.x - w / 2}" y="{p.y - h / 2}" '
            f'width="{w}" height="{h}"{class_str}/>\n'
        )

    def _draw_text(self, p: Point, text: str, cls: str | None = None) -> None:
        if not (words := text.split()):
            return
        class_str = f' class="{cls}"' if cls is not None else ""
        if len(words) == 1:
            self.out.write(f'<text x="{p.x}" y="{p.y}"{class_str}>{escape(words[0])}</text>\n')
            return
        self.out.write(f'<text x="{p.x}" y="{p.y}"{class_str}>\n')
        self.out.write(f'<tspan x="{p.x}" dy="-{(len(words) - 1) * 0.6}em">{escape(words[0])}</tspan>')
        for word in words[1:]:
            self.out.write(f'<tspan x="{p.x}" dy="1.2em">{escape(word)}</tspan>')
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
            self.out.write(f'<g transform="rotate({r}, {p.x}, {p.y})">\n')
        self._draw_rect(p, w - 2 * self.cfg.inner_pad_w, h - 2 * self.cfg.inner_pad_h, l_key.type)
        self._draw_text(p, l_key.tap)
        self._draw_text(p + Point(0, h / 2 - self.cfg.line_spacing / 2), l_key.hold, cls="small")
        if r != 0:
            self.out.write("</g>\n")

    def print_combo(self, p_0: Point, combo_spec: ComboSpec) -> None:
        """
        Given anchor coordinates p_0, print SVG code for a rectangle with text representing
        a combo specification, which contains the key positions that trigger it and what it does
        when triggered. The position of the rectangle depends on the alignment specified,
        along with whether dendrons are drawn going to each key position from the combo.
        """
        p_keys = [self.keymap.layout.keys[p] for p in combo_spec.key_positions]
        n_keys = len(p_keys)

        # find center of combo box
        p_mid = Point(p_0.x, p_0.y)
        match combo_spec.align:
            case "mid":
                p_mid.x += sum(k.pos.x for k in p_keys) / n_keys
                p_mid.y += sum(k.pos.y for k in p_keys) / n_keys
            case "top":
                p_mid.x += sum(k.pos.x for k in p_keys) / n_keys
                p_mid.y += min(k.pos.y - k.height / 2 for k in p_keys) - self.cfg.inner_pad_h / 2
                p_mid.y -= combo_spec.offset * self.keymap.layout.min_height
            case "bottom":
                p_mid.x += sum(k.pos.x for k in p_keys) / n_keys
                p_mid.y += max(k.pos.y + k.height / 2 for k in p_keys) + self.cfg.inner_pad_h / 2
                p_mid.y += combo_spec.offset * self.keymap.layout.min_height
            case "left":
                p_mid.x += min(k.pos.x - k.width / 2 for k in p_keys) - self.cfg.inner_pad_w / 2
                p_mid.y += sum(k.pos.y for k in p_keys) / n_keys
                p_mid.x -= combo_spec.offset * self.keymap.layout.min_width
            case "right":
                p_mid.x += max(k.pos.x + k.width / 2 for k in p_keys) + self.cfg.inner_pad_w / 2
                p_mid.y += sum(k.pos.y for k in p_keys) / n_keys
                p_mid.x += combo_spec.offset * self.keymap.layout.min_width

        # draw dendrons going from box to combo keys
        if combo_spec.dendron is not False:
            match combo_spec.align:
                case "top" | "bottom":
                    for k in p_keys:
                        offset = k.height / 5 if abs(p_0.x + k.pos.x - p_mid.x) < self.cfg.combo_w / 2 else k.height / 3
                        self._draw_arc_dendron(p_mid, p_0 + k.pos, True, offset)
                case "left" | "right":
                    for k in p_keys:
                        offset = k.width / 5 if abs(p_0.y + k.pos.y - p_mid.y) < self.cfg.combo_h / 2 else k.width / 3
                        self._draw_arc_dendron(p_mid, p_0 + k.pos, False, offset)
                case "mid":
                    for k in p_keys:
                        if combo_spec.dendron is True or abs(p_0 + k.pos - p_mid) >= k.width - 1:
                            self._draw_line_dendron(p_mid, p_0 + k.pos, k.width / 3)

        # draw combo box with text
        self._draw_rect(p_mid, self.cfg.combo_w, self.cfg.combo_h, "combo")
        self._draw_text(p_mid, combo_spec.key.tap, cls="small")
        self._draw_text(
            p_mid + Point(0, self.cfg.combo_h / 2 - self.cfg.line_spacing / 5), combo_spec.key.hold, cls="smaller"
        )

    def print_layer(self, p_0: Point, layer_keys: Sequence[LayoutKey], combos: Sequence[ComboSpec]) -> None:
        """
        Given anchor coordinates p_0, print SVG code for keys and combos for a given layer.
        """
        for p_key, l_key in zip(self.keymap.layout.keys, layer_keys):
            self.print_key(p_0, p_key, l_key)
        for combo_spec in combos:
            self.print_combo(p_0, combo_spec)

    def print_board(self) -> None:
        """Print SVG code representing the keymap."""
        combos_per_layer = self.keymap.get_combos_per_layer()
        offsets_per_layer = {
            name: (
                max((c.offset * self.keymap.layout.min_height for c in combos if c.align == "top"), default=0.0),
                max((c.offset * self.keymap.layout.min_height for c in combos if c.align == "bottom"), default=0.0),
            )
            for name, combos in combos_per_layer.items()
        }

        board_w = self.keymap.layout.width + 2 * self.cfg.outer_pad_w
        board_h = (
            len(self.keymap.layers) * self.keymap.layout.height + (len(self.keymap.layers) + 1) * self.cfg.outer_pad_h
            + sum(top_offset + bot_offset for top_offset, bot_offset in offsets_per_layer.values())
        )
        self.out.write(
            f'<svg width="{board_w}" height="{board_h}" viewBox="0 0 {board_w} {board_h}" '
            'xmlns="http://www.w3.org/2000/svg">\n'
        )
        self.out.write(f"<style>{self.cfg.svg_style}</style>\n")

        p = Point(self.cfg.outer_pad_w, 0.0)
        for name, layer_keys in self.keymap.layers.items():
            # draw layer name
            self._draw_text(p + Point(0, self.cfg.outer_pad_h / 2), f"{name}:", cls="label")

            # get combos on layer and offsets added by their alignments
            combos = combos_per_layer[name]
            combo_offset_top, combo_offset_bot = offsets_per_layer[name]

            # draw keys and combos
            p.y += self.cfg.outer_pad_h + combo_offset_top
            self.print_layer(p, layer_keys, combos)
            p.y += self.keymap.layout.height + combo_offset_bot

        self.out.write("</svg>\n")
