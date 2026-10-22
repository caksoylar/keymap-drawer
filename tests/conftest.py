"""Shared fixtures for the keymap-drawer test suite.

The repository root is inserted into ``sys.path`` so ``keymap_drawer`` can be
imported without installing the package.
"""

import sys
from io import StringIO
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from keymap_drawer.config import Config, DrawConfig, ParseConfig  # noqa: E402
from keymap_drawer.draw.utils import UtilsMixin  # noqa: E402


@pytest.fixture
def config() -> Config:
    """A default top-level Config."""
    return Config()


@pytest.fixture
def draw_config() -> DrawConfig:
    """A default DrawConfig."""
    return DrawConfig()


@pytest.fixture
def parse_config() -> ParseConfig:
    """A default ParseConfig."""
    return ParseConfig()


class _Utils(UtilsMixin):
    """Concrete stand-in for the draw UtilsMixin, which is normally mixed into KeymapDrawer."""


@pytest.fixture
def utils(draw_config) -> _Utils:
    """A UtilsMixin instance wired up the way KeymapDrawer would wire it."""
    obj = _Utils()
    obj.cfg = draw_config
    obj.layer_names = set()
    obj.out = StringIO()
    obj.name_to_svg = {}
    return obj


class NamedStringIO(StringIO):
    """A StringIO with a ``name`` attribute, mimicking an opened text file."""


@pytest.fixture
def named_buffer():
    """Factory returning a NamedStringIO with the given content and file name."""

    def _make(content: str, name: str = "keymap.json") -> NamedStringIO:
        buf = NamedStringIO(content)
        buf.name = name
        return buf

    return _make
