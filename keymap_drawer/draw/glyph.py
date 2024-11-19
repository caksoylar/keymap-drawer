"""
Module containing class and methods to help with fetching
and drawing SVG glyphs.
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache, partial
from pathlib import Path
from random import random
from time import sleep
from typing import Iterable
from urllib.error import HTTPError
from urllib.request import urlopen

from platformdirs import user_cache_dir

from keymap_drawer.config import DrawConfig
from keymap_drawer.keymap import KeymapData, LayoutKey

logger = logging.getLogger(__name__)

FETCH_WORKERS = 8
FETCH_TIMEOUT = 10
N_RETRY = 5
CACHE_GLYPHS_PATH = Path(user_cache_dir("keymap-drawer", False)) / "glyphs"


class GlyphMixin:
    """Mixin that handles SVG glyphs for KeymapDrawer."""

    _glyph_name_re = re.compile(r"\$\$(?P<glyph>.*)\$\$")
    _view_box_dimensions_re = re.compile(
        r'<svg.*viewbox="(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)".*>',
        flags=re.IGNORECASE | re.ASCII | re.DOTALL,
    )
    _scrub_dims_re = re.compile(r' (width|height)=".*?"')

    # initialized in KeymapDrawer
    cfg: DrawConfig
    keymap: KeymapData

    def init_glyphs(self) -> None:
        """Preprocess all glyphs in the keymap to get their name to SVG mapping."""

        def find_key_glyph_names(key: LayoutKey) -> set[str]:
            return {
                glyph
                for field in (key.tap, key.hold, key.shifted, key.left, key.right)
                if (glyph := self._legend_to_name(field))
            }

        # find all named glyphs in the keymap
        names = set()
        for layer in self.keymap.layers.values():
            for key in layer:
                names |= find_key_glyph_names(key)
        for combo in self.keymap.combos:
            names |= find_key_glyph_names(combo.key)

        # get the ones defined in draw_config.glyphs
        self.name_to_svg = {name: glyph for name in names if (glyph := self.cfg.glyphs.get(name))}
        logger.debug("found glyphs %s in draw_config.glyphs", list(self.name_to_svg))
        rest = names - set(self.name_to_svg)

        # try to fetch the rest using draw_config.glyph_urls
        if rest:
            self.name_to_svg |= self._fetch_glyphs(rest)
        if rest := rest - set(self.name_to_svg):
            raise ValueError(
                f'Glyphs "{rest}" are not defined in draw_config.glyphs or fetchable using draw_config.glyph_urls'
            )

        for name, svg in self.name_to_svg.items():
            if not self._view_box_dimensions_re.match(svg):
                raise ValueError(f'Glyph definition for "{name}" does not have the required "viewbox" property')

    def _fetch_glyphs(self, names: Iterable[str]) -> dict[str, str]:
        names = list(names)
        urls = []
        for name in names:
            if ":" in name:  # templated source:ID format
                source, glyph_id = name.split(":", maxsplit=1)
                if templated_url := self.cfg.glyph_urls.get(source):
                    if source == "phosphor":  # special case to handle variants
                        assert "/" in glyph_id, "phosphor glyphs should be in `$$phosphor:<type>/<id>$$` format"
                        ph_type, ph_id = glyph_id.split("/", maxsplit=1)
                        ph_type = ph_type.lower()
                        glyph_id = f"{ph_type}/{ph_id}"
                        if ph_type != "regular":
                            glyph_id += f"-{ph_type}"
                    urls.append(templated_url.format(glyph_id))
            if url := self.cfg.glyph_urls.get(name):  # source only
                urls.append(url)

        with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as p:
            fetch_fn = partial(_fetch_svg_url, use_local_cache=self.cfg.use_local_cache)
            return dict(zip(names, p.map(fetch_fn, names, urls, timeout=N_RETRY * (FETCH_TIMEOUT + 1))))

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
        for name, svg in sorted(self.name_to_svg.items()):
            defs += f'<svg id="{name}">\n'
            defs += self._scrub_dims_re.sub("", svg)
            defs += "\n</svg>\n"
        defs += "</defs>/* end glyphs */\n"
        return defs

    def get_glyph_dimensions(self, name: str, legend_type: str) -> tuple[float, float, float, float]:
        """Given a glyph name, calculate and return its width, height and y-offset for drawing."""
        view_box = self._view_box_dimensions_re.match(self.name_to_svg[name])
        assert view_box is not None
        _, _, w, h = (float(v) for v in view_box.groups())

        # set dimensions and offsets from center
        match legend_type:
            case "tap":
                height = self.cfg.glyph_tap_size
                width = w * height / h
                d_x = 0.5 * width
                d_y = 0.5 * height
            case "hold":
                height = self.cfg.glyph_hold_size
                width = w * height / h
                d_x = 0.5 * width
                d_y = height
            case "shifted":
                height = self.cfg.glyph_shifted_size
                width = w * height / h
                d_x = 0.5 * width
                d_y = 0
            case "left":
                height = self.cfg.glyph_shifted_size
                width = w * height / h
                d_x = 0
                d_y = 0.5 * height
            case "right":
                height = self.cfg.glyph_shifted_size
                width = w * height / h
                d_x = width
                d_y = 0.5 * height
            case _:
                raise ValueError("Unsupported legend_type for glyph")

        return width, height, d_x, d_y


@lru_cache(maxsize=128)
def _fetch_svg_url(name: str, url: str, use_local_cache: bool = False) -> str:
    """Get an SVG glyph definition from url, using the local cache for reading and writing if enabled."""
    cache_path = CACHE_GLYPHS_PATH / f"{name.replace('/', '@')}.svg"
    if use_local_cache and cache_path.is_file():
        logger.debug('found glyph "%s" in local cache', name)
        with open(cache_path, "r", encoding="utf-8") as f:
            return f.read()

    logger.debug('fetching glyph "%s" from %s', name, url)
    try:
        for _ in range(N_RETRY):
            try:
                sleep(0.2 * random())
                with urlopen(url, timeout=FETCH_TIMEOUT) as f:
                    content = f.read().decode("utf-8")
                break
            except TimeoutError:
                logger.warning("request timed out while trying to fetch SVG from %s", url)
        else:
            raise RuntimeError(f"Failed to fetch SVG in {N_RETRY} tries")
        if use_local_cache:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f_out:
                f_out.write(content)
        return content
    except (HTTPError, RuntimeError) as exc:
        raise RuntimeError(f'Could not fetch SVG from URL "{url}"') from exc
