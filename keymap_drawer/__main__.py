import sys
from ruamel import yaml

from .draw import KeymapDrawer


def main() -> None:
    with open(sys.argv[1], "rb") as f:
        data = yaml.safe_load(f)
    drawer = KeymapDrawer(**data)
    drawer.print_board()


if __name__ == "__main__":
    main()
