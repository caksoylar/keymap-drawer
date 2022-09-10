import sys
import ruamel as yaml

from .draw import KeymapDrawer


def main() -> None:
    with open(sys.argv[1], "rb") as f:
        data = yaml.safe_load(f)
    kd = KeymapDrawer(**data)
    kd.print_board()


if __name__ == "__main__":
    main()
