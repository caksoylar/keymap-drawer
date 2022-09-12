"""
Script that takes a yaml containing physical keyboard layout and
keymap descriptions, then prints an SVG representing the keymap.
"""
import sys
from ruamel import yaml

from .draw import KeymapDrawer


def main() -> None:
    """Parse the configuration and print SVG using KeymapDrawer."""
    with open(sys.argv[1], "rb") as f:
        data = yaml.safe_load(f)
    drawer = KeymapDrawer(**data)
    drawer.print_board()


if __name__ == "__main__":
    main()
