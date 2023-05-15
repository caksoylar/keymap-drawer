"""
Module containing class and methods to help with fetching
and drawing SVG glyphs.
"""
import re
from functools import lru_cache
from urllib.request import urlopen
from urllib.error import HTTPError

from .keymap import KeymapData, LayoutKey
from .config import DrawConfig


class GlyphHandler:
    """Class that handles SVG glyphs."""

    _glyph_name_re = re.compile(r"\$\$(?P<glyph>.*)\$\$")
    _view_box_dimensions_re = re.compile(
        r'<svg.*viewbox="(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)".*>',
        flags=re.IGNORECASE | re.ASCII,
    )
    _scrub_dims_re = re.compile(r' (width|height)=".*?"')

    def __init__(self, config: DrawConfig, keymap: KeymapData) -> None:
        self.cfg = config
        self.name_to_svg = self._get_all_glyphs(keymap)

    def _get_all_glyphs(self, keymap: KeymapData) -> dict[str, str]:
        def find_key_glyph_names(key: LayoutKey) -> set[str]:
            return {glyph for field in (key.tap, key.hold, key.shifted) if (glyph := self._legend_to_name(field))}

        # find all named glyphs in the keymap
        names = set()
        for layer in keymap.layers.values():
            for key in layer:
                names |= find_key_glyph_names(key)
        for combo in keymap.combos:
            names |= find_key_glyph_names(combo.key)

        svgs = {}
        for name in names:
            if not (svg := self.cfg.glyphs.get(name)) and not (svg := self._fetch_glyph(name)):
                raise ValueError(
                    f'Glyph "{name}" not defined in draw_config.glyphs or fetchable using draw_config.glyph_urls'
                )
            if not self._view_box_dimensions_re.match(svg):
                raise ValueError(f'Glyph definition for "{name}" does not have the required "viewbox" property')
            svgs[name] = svg
        return svgs

    def _fetch_glyph(self, name: str) -> str | None:
        if ":" in name:  # templated source:ID format
            source, glyph_id = name.split(":", maxsplit=1)
            if templated_url := self.cfg.glyph_urls.get(source):
                return _fetch_svg_url(templated_url.format(glyph_id))
            return None
        if url := self.cfg.glyph_urls.get(name):  # source only
            return _fetch_svg_url(url)
        return None

    @classmethod
    def _legend_to_name(cls, legend: str) -> str | None:
        if m := cls._glyph_name_re.search(legend):
            return m.group("glyph")
        return None

    def legend_is_glyph(self, legend: str) -> str | None:
        """Return glyph name if a given legend refers to a glyph and None otherwise."""
        if (name := self._legend_to_name(legend)) and name in self.name_to_svg:
            return name
        return None

    def get_glyph_defs(self) -> str:
        """Return an SVG defs block with all glyph SVG definitions to be referred to later on."""
        if not self.name_to_svg:
            return ""

        defs = "<defs>/* start glyphs */\n"
        for name, svg in self.name_to_svg.items():
            defs += f'<svg id="{name}">\n'
            defs += self._scrub_dims_re.sub("", svg)
            defs += "\n</svg>\n"
        defs += "</defs>/* end glyphs */\n"
        return defs

    def get_glyph_dimensions(self, name: str, legend_type: str) -> tuple[float, float, float]:
        """Given a glyph name, calculate and return its width, height and y-offset for drawing."""
        view_box = self._view_box_dimensions_re.match(self.name_to_svg[name])
        assert view_box is not None

        # set height and y-offset from center
        match legend_type:
            case "tap":
                height = self.cfg.glyph_tap_size
                d_y = 0.5 * height
            case "hold":
                height = self.cfg.glyph_hold_size
                d_y = height
            case "shifted":
                height = self.cfg.glyph_shifted_size
                d_y = 0
            case _:
                raise ValueError("Unsupported legend_type for glyph")

        x, y, w, h = (float(v) for v in view_box.groups())

        # calculate width to preserve aspect ratio
        width = (w - x) * (height / (h - y))

        return width, height, d_y


@lru_cache(maxsize=128)
def _fetch_svg_url(url: str) -> str:
    try:
        with urlopen(url) as f:
            return f.read().decode("utf-8")
    except HTTPError as exc:
        raise ValueError(f'Could not fetch SVG from URL "{url}"') from exc
