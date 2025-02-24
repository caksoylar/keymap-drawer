"""
Module containing classes pertaining to the physical layout of a keyboard,
i.e. a sequence of keys each represented by its coordinates, dimensions
and rotation.
"""

import json
import logging
import re
from dataclasses import dataclass
from functools import cache, cached_property, lru_cache
from io import BytesIO
from math import cos, pi, sin, sqrt
from pathlib import Path
from typing import ClassVar, Literal
from urllib.error import HTTPError
from urllib.request import urlopen

import yaml
from platformdirs import user_cache_dir
from pydantic import BaseModel, Field, field_validator, model_validator

from keymap_drawer.config import Config, ParseConfig
from keymap_drawer.dts import DeviceTree

logger = logging.getLogger(__name__)

QMK_LAYOUTS_PATH = Path(__file__).parent.parent / "resources" / "extra_layouts"
ZMK_LAYOUTS_PATH = Path(__file__).parent.parent / "resources" / "zmk_keyboard_layouts.yaml"
QMK_METADATA_URL = "https://keyboards.qmk.fm/v1/keyboards/{keyboard}/info.json"
QMK_DEFAULT_LAYOUTS_URL = "https://raw.githubusercontent.com/qmk/qmk_firmware/master/layouts/default/{layout}/info.json"
ZMK_SHARED_LAYOUTS_URL = (
    "https://raw.githubusercontent.com/zmkfirmware/zmk/refs/heads/main/app/dts/layouts/{layout}.dtsi"
)
CACHE_LAYOUTS_PATH = Path(user_cache_dir("keymap-drawer", False)) / "qmk_layouts"
QMK_MAPPINGS_PATH = Path(__file__).parent.parent / "resources" / "qmk_keyboard_mappings.yaml"


@dataclass(frozen=True, slots=True)
class Point:
    """Simple class representing a 2d point."""

    x: float
    y: float

    def __add__(self, other: "Point") -> "Point":
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Point") -> "Point":
        return Point(self.x - other.x, self.y - other.y)

    def __abs__(self) -> float:
        return sqrt(self.x**2 + self.y**2)

    def __mul__(self, other: int | float) -> "Point":
        return Point(other * self.x, other * self.y)

    def __rmul__(self, other: int | float) -> "Point":
        return self.__mul__(other)

    def copy(self) -> "Point":  # pylint: disable=missing-function-docstring
        return Point(self.x, self.y)


@dataclass(slots=True)
class PhysicalKey:
    """
    Represents a physical key, in terms of its center coordinates, width, height and
    rotation angle.
    """

    pos: Point
    width: float
    height: float
    rotation: float = 0  # CW if positive
    bounding_width: float = 0.0
    bounding_height: float = 0.0
    is_iso_enter: bool = False

    @classmethod
    def from_qmk_spec(
        cls, scale: float, pos: Point, width: float, height: float, rotation: float, rotation_pos: Point
    ) -> "PhysicalKey":
        """
        Create a PhysicalKey from QMK-format key definition. `pos` is the top left corner coordinates,
        `rotation_pos` is the coordinates around which the rectangle is rotated. `scale` maps from `1u` dimensions
        to pixel dimensions.
        During construction of PhysicalKey, uses `rotation_pos` to re-adjust center position.
        """
        center = pos + Point(width / 2, height / 2)
        if rotation:
            center = cls._rotate_point(rotation_pos, center, rotation)

        is_iso_enter = width == 1.25 and height == 2.0

        return cls(scale * center, scale * width, scale * height, rotation, is_iso_enter=is_iso_enter)

    def __post_init__(self) -> None:
        if self.rotation:
            # calculate bounding box dimensions
            rotated_corners = [
                self._rotate_point(Point(0, 0), p, self.rotation)
                for p in (Point(0, 0), Point(0, self.height), Point(self.width, 0), Point(self.width, self.height))
            ]
            self.bounding_width = max(p.x for p in rotated_corners) - min(p.x for p in rotated_corners)
            self.bounding_height = max(p.y for p in rotated_corners) - min(p.y for p in rotated_corners)
        else:
            self.bounding_width = self.width
            self.bounding_height = self.height

    @staticmethod
    def _rotate_point(origin: Point, point: Point, angle: float) -> Point:
        angle *= pi / 180
        delta = point - origin
        rotated = Point(
            delta.x * cos(angle) - delta.y * sin(angle),
            delta.x * sin(angle) + delta.y * cos(angle),
        )
        return origin + rotated

    def __add__(self, other: "Point") -> "PhysicalKey":
        return PhysicalKey(
            pos=self.pos + other,
            width=self.width,
            height=self.height,
            rotation=self.rotation,
            is_iso_enter=self.is_iso_enter,
        )

    def __sub__(self, other: "Point") -> "PhysicalKey":
        return PhysicalKey(
            pos=self.pos - other,
            width=self.width,
            height=self.height,
            rotation=self.rotation,
            is_iso_enter=self.is_iso_enter,
        )

    def __rmul__(self, other: int | float) -> "PhysicalKey":
        return PhysicalKey(
            pos=self.pos * other,
            width=self.width * other,
            height=self.height * other,
            rotation=self.rotation,
            is_iso_enter=self.is_iso_enter,
        )


class PhysicalLayout(BaseModel):
    """Represents the physical layout of keys on the keyboard, as a sequence of keys."""

    keys: list[PhysicalKey]

    def __len__(self) -> int:
        return len(self.keys)

    @cached_property
    def width(self) -> float:
        """Return overall width of layout."""
        return max(k.pos.x + k.bounding_width / 2 for k in self.keys)

    @cached_property
    def height(self) -> float:
        """Return overall height of layout."""
        return max(k.pos.y + k.bounding_height / 2 for k in self.keys)

    @cached_property
    def min_width(self) -> float:
        """Return minimum key width in the layout."""
        return min(k.width for k in self.keys)

    @cached_property
    def min_height(self) -> float:
        """Return minimum key height in the layout."""
        return min(k.height for k in self.keys)

    def __add__(self, other: Point) -> "PhysicalLayout":
        return PhysicalLayout(keys=[k + other for k in self.keys])

    def __rmul__(self, other: int | float) -> "PhysicalLayout":
        return PhysicalLayout(keys=[other * k for k in self.keys])

    def normalize(self) -> "PhysicalLayout":
        """Normalize the layout so that the keys are all in (0, 0) to (width, height) coordinates."""
        min_pt = Point(
            min(k.pos.x - k.bounding_width / 2 for k in self.keys),
            min(k.pos.y - k.bounding_height / 2 for k in self.keys),
        )
        return PhysicalLayout(keys=[k - min_pt for k in self.keys])


class PhysicalLayoutGenerator(BaseModel, arbitrary_types_allowed=True):
    """Top level object to generate physical layouts, given a config and set of possible user-facing specs."""

    config: Config
    qmk_keyboard: str | None = None
    zmk_keyboard: str | None = None
    zmk_shared_layout: str | None = None
    qmk_info_json: Path | BytesIO | None = None
    dts_layout: Path | BytesIO | None = None
    layout_name: str | None = None
    qmk_layout: str | None = None
    ortho_layout: dict | None = None
    cols_thumbs_notation: str | None = None

    @model_validator(mode="after")
    def handle_file_overrides(self):
        """Allow certain spec combinations where one overrides the other."""
        if self.qmk_info_json and self.qmk_keyboard:
            logger.warning("qmk_info_json is overriding qmk_keyboard specification")
            self.qmk_keyboard = None
        if self.dts_layout and self.zmk_keyboard:
            logger.warning("dts_layout is overriding zmk_keyboard specification")
            self.zmk_keyboard = None
        return self

    @model_validator(mode="after")
    def check_specs(self):
        """Check that exactly one layout type is specified."""
        if (
            sum(
                spec is not None
                for spec in (
                    self.qmk_keyboard,
                    self.zmk_keyboard,
                    self.zmk_shared_layout,
                    self.qmk_info_json,
                    self.dts_layout,
                    self.ortho_layout,
                    self.cols_thumbs_notation,
                )
            )
            != 1
        ):
            raise ValueError(
                'Please provide exactly one of "qmk_keyboard", "zmk_keyboard", "zmk_shared_layout", "qmk_info_json", "dts_layout", "ortho_layout" '
                'or "cols_thumbs_notation" specs for physical layout'
            )
        return self

    @model_validator(mode="after")
    def handle_qmk_layout(self):
        """Check and set the layout name to account for deprecated qmk_layout field."""
        if self.qmk_layout is not None:
            logger.warning('"qmk_layout" is deprecated, please use "layout_name" instead')
            assert self.layout_name is None, '"qmk_layout" cannot be used with "layout_name", use the latter'
            self.layout_name = self.qmk_layout
        if self.layout_name is not None and (self.ortho_layout is not None or self.cols_thumbs_notation is not None):
            logger.warning(
                '"layout_name" cannot be used with "ortho_layout" or "cols_thumbs_notation", will be ignored'
            )
        return self

    def generate(self) -> PhysicalLayout:
        """Generate a physical layout given config and layout specs."""
        draw_cfg, parse_cfg = self.config.draw_config, self.config.parse_config

        if self.qmk_keyboard or self.qmk_info_json:
            if self.qmk_keyboard:
                qmk_info = _get_qmk_info(self.qmk_keyboard, draw_cfg.use_local_cache)
            else:  # qmk_info_json
                assert self.qmk_info_json is not None
                with (
                    open(self.qmk_info_json, "rb")
                    if not isinstance(self.qmk_info_json, BytesIO)
                    else self.qmk_info_json
                ) as f:
                    qmk_info = json.load(f)

            layout_name = self.layout_name
            if isinstance(qmk_info, list):
                assert self.layout_name is None, "Cannot use layout_name with a list-format QMK spec"
                layouts = {None: qmk_info}  # shortcut for list-only representation
            else:
                assert "layouts" in qmk_info, "QMK info.json must contain a `layouts` field"
                if aliases := qmk_info.get("layout_aliases"):
                    layout_name = aliases.get(layout_name, layout_name)
                layouts = {name: val["layout"] for name, val in qmk_info["layouts"].items()}

            return QmkLayout(layouts=layouts).generate(layout_name=layout_name, key_size=draw_cfg.key_h)

        if self.zmk_keyboard is not None:
            try:
                return PhysicalLayoutGenerator(
                    config=self.config, **_map_zmk_layout(self.zmk_keyboard, self.layout_name)
                ).generate()
            except ValueError as exc:
                raise ValueError('A physical layout for zmk_keyboard "{self.zmk_keyboard}" could not be found') from exc

        if self.zmk_shared_layout is not None:
            fetched = _get_zmk_shared_layout(self.zmk_shared_layout, draw_cfg.use_local_cache)
            return _parse_dts_layout(fetched, parse_cfg).generate(layout_name=None, key_size=draw_cfg.key_h)

        if self.dts_layout is not None:
            return _parse_dts_layout(self.dts_layout, parse_cfg).generate(
                layout_name=self.layout_name, key_size=draw_cfg.key_h
            )

        if self.ortho_layout is not None:
            return OrthoLayout(**self.ortho_layout).generate(draw_cfg.key_w, draw_cfg.key_h, draw_cfg.split_gap)

        assert self.cols_thumbs_notation is not None
        return CPTLayout(spec=self.cols_thumbs_notation).generate(draw_cfg.key_w, draw_cfg.key_h, draw_cfg.split_gap)


class OrthoLayout(BaseModel):
    """
    Generator for a physical layout representing an ortholinear keyboard, as specified by
    its number of rows, columns, thumb keys and whether it is split or not. If split,
    row/column number represents the size of one half. Thumb keys can only be used if split.
    """

    split: bool = False
    rows: int
    columns: int
    thumbs: int | Literal["MIT", "2x2u"] = 0
    drop_pinky: bool = False
    drop_inner: bool = False

    @model_validator(mode="after")
    def check_thumbs(self):
        """Check that the number of thumb keys is specified correctly."""
        if self.thumbs:
            if isinstance(self.thumbs, int):
                assert self.thumbs <= self.columns, "Number of thumbs should not be greater than columns"
                assert self.split, "Cannot process non-split layout with thumb keys"
            else:
                assert not self.split, "Non-integer thumb specs (MIT/2x2u) can only be used with non-split layout"
                assert self.thumbs in (
                    "MIT",
                    "2x2u",
                ), 'Only "MIT" or "2x2u" supported for "thumbs" for non-splits'
                assert self.columns % 2 == 0, "Cannot use MIT or 2x2u bottom row layout with odd number of columns"
        return self

    @model_validator(mode="after")
    def check_drops(self):
        """Check that drop_pinky or drop_index are only used with split layouts."""
        if self.drop_pinky or self.drop_inner:
            assert self.split, '"drop_*" properties can only be used with split layouts'
        return self

    def generate(self, key_w: float, key_h: float, split_gap: float) -> PhysicalLayout:
        """Generate a list of PhysicalKeys from given ortho specifications."""
        logger.debug("generating OrthoLayout-based physical layout for spec %s", self.model_dump())

        nrows = self.rows
        if not isinstance(self.thumbs, int):
            nrows -= 1
        ncols = self.columns

        keys: list[PhysicalKey] = []

        def create_row(x: float, y: float, ncols: int = ncols) -> list[PhysicalKey]:
            row_keys = []
            for _ in range(ncols):
                row_keys.append(PhysicalKey(pos=Point(x + key_w / 2, y + key_h / 2), width=key_w, height=key_h))
                x += key_w
            return row_keys

        x, y = 0.0, 0.0
        for row in range(nrows):
            row_keys = create_row(x, y)
            if self.split:
                row_keys += create_row(x + ncols * key_w + split_gap, y)

            drop_cols = [0, -1] * self.drop_pinky + [
                len(row_keys) // 2 - 1,
                len(row_keys) // 2,
            ] * self.drop_inner
            for col in reversed(drop_cols):
                if row < nrows - 1:
                    row_keys[col].pos += Point(0, key_h / 2)
                else:
                    row_keys.pop(col)

            keys.extend(row_keys)
            y += key_h

        if not self.thumbs:
            return PhysicalLayout(keys=keys)

        match self.thumbs:
            case int():  # implies split
                keys += create_row((ncols - self.thumbs) * key_w, y, self.thumbs)
                keys += create_row(ncols * key_w + split_gap, y, self.thumbs)
            case "MIT":
                keys += create_row(0.0, y, ncols // 2 - 1)
                keys.append(PhysicalKey(pos=Point((ncols / 2) * key_w, y + key_h / 2), width=2 * key_w, height=key_h))
                keys += create_row((ncols / 2 + 1) * key_w, y, ncols // 2 - 1)
            case "2x2u":
                keys += create_row(0.0, y, ncols // 2 - 2)
                keys.append(
                    PhysicalKey(pos=Point((ncols / 2 - 1) * key_w, y + key_h / 2), width=2 * key_w, height=key_h)
                )
                keys.append(
                    PhysicalKey(pos=Point((ncols / 2 + 1) * key_w, y + key_h / 2), width=2 * key_w, height=key_h)
                )
                keys += create_row((ncols / 2 + 2) * key_w, y, ncols // 2 - 2)
            case _:
                raise ValueError("Unknown thumbs value in ortho layout")

        return PhysicalLayout(keys=keys)


class CPTLayout(BaseModel):
    """
    Generator for a physical layout representing an ortholinear keyboard, as specified by
    its CPT (cols+thumbs) notation. Can do splits and non-splits, but doesn't support special
    thumb notation of OrthoLayout.
    """

    spec: str

    col_pattern: ClassVar[str] = r"\d[v^ud]*"
    alphas_pattern: ClassVar[str] = rf"({col_pattern}){{2,}}"
    thumbs_pattern: ClassVar[str] = r"\d[><lr]*"
    part_pattern: ClassVar[re.Pattern] = re.compile(
        rf"(?P<a_l>{alphas_pattern})(\+(?P<t_l>{thumbs_pattern}))?|"
        rf"((?P<t_r>{thumbs_pattern})\+)?(?P<a_r>{alphas_pattern})"
    )
    split_pattern: ClassVar[str] = r"[ _]+"

    @classmethod
    def _split_spec(cls, spec: str) -> list[str]:
        return [val for val in re.split(cls.split_pattern, spec) if val]

    @field_validator("spec")
    @classmethod
    def spec_validator(cls, val: str) -> str:
        """Split spec string by spaces or underscores then validate each part."""
        assert all(
            cls.part_pattern.match(part) for part in cls._split_spec(val)
        ), "Cols+thumbs `spec` value does not match the expected syntax, please double check"
        return val

    @classmethod
    def _get_part_keys(cls, part_dict: dict[str, str | None], max_rows: int) -> tuple[list[Point], float]:
        part_keys = []
        alpha_spec = part_dict["a_l"] or part_dict["a_r"]
        assert alpha_spec is not None
        col_specs = re.findall(cls.col_pattern, alpha_spec)
        for x, c_spec in enumerate(col_specs):
            n_keys = int(c_spec[0])
            n_shift = c_spec.count("v", 1) + c_spec.count("d", 1) - c_spec.count("^", 1) - c_spec.count("u", 1)
            y_top = (max_rows - n_keys + n_shift) / 2
            part_keys += [Point(x, y_top + i) for i in range(n_keys)]

        t_spec = part_dict["t_l"] or part_dict["t_r"]
        if t_spec:
            n_keys = int(t_spec[0])
            n_shift = t_spec.count(">", 1) + t_spec.count("r", 1) - t_spec.count("<", 1) - t_spec.count("l", 1)
            x_left = (len(col_specs) - n_keys if part_dict["t_l"] is not None else 0) + n_shift / 2
            part_keys += [Point(x_left + i, max_rows) for i in range(n_keys)]

        min_pt = Point(min(p.x for p in part_keys), min(p.y for p in part_keys))

        return [key - min_pt for key in part_keys], max(p.x for p in part_keys) - min_pt.x

    def generate(self, key_w: float, key_h: float, split_gap: float) -> PhysicalLayout:
        """Generate a list of PhysicalKeys from given CPT specification."""
        logger.debug("generating CPT-based physical layout for spec %s", self.spec)

        parts = [match.groupdict() for part in self._split_spec(self.spec) if (match := self.part_pattern.match(part))]
        max_rows = max(int(char) for part in parts for char in (part["a_l"] or part["a_r"]) if char.isdigit())

        x_offsets = [0.0]
        all_keys = []
        for part_ind, part in enumerate(parts):
            part_keys, max_x = self._get_part_keys(part, max_rows)
            all_keys += [(key, part_ind) for key in part_keys]
            x_offsets.append(x_offsets[-1] + max_x + 1)

        sorted_keys = sorted(all_keys, key=lambda item: (int(item[0].y), item[1], int(item[0].x)))
        return PhysicalLayout(
            keys=[
                PhysicalKey(
                    Point((key.x + 0.5 + x_offsets[part_ind]) * key_w + part_ind * split_gap, (key.y + 0.5) * key_h),
                    key_w,
                    key_h,
                )
                for key, part_ind in sorted_keys
            ]
        )


class QmkLayout(BaseModel):
    """Generator for layouts given by QMK's info.json format."""

    class QmkKey(BaseModel, populate_by_name=True):
        """Model representing each key in QMK's layout definition."""

        x: float  # coordinates of top-left corner
        y: float
        w: float = Field(default=1.0, validation_alias="u")
        h: float = 1.0
        r: float = 0  # assume CW rotation around rx, ry (defaults to x, y), after translation to x, y
        rx: float | None = None
        ry: float | None = None

    layouts: dict[str | None, list[QmkKey]]

    def generate(self, layout_name: str | None, key_size: float) -> PhysicalLayout:
        """Generate a sequence of PhysicalKeys from QmkKeys."""
        logger.debug("generating QMK-based physical layout for layout name %s", layout_name)
        assert self.layouts, "QmkLayout.layouts cannot be empty"
        if layout_name is not None:
            assert layout_name in self.layouts, (
                f'Could not find layout "{layout_name}" in available physical layouts, '
                f"available options are: {list(self.layouts)}"
            )
            chosen_layout = self.layouts[layout_name]
        else:
            chosen_layout = next(iter(self.layouts.values()))

        return PhysicalLayout(
            keys=[
                PhysicalKey.from_qmk_spec(
                    scale=key_size,
                    pos=Point(k.x, k.y),
                    width=k.w,
                    height=k.h,
                    rotation=k.r,
                    rotation_pos=Point(k.x if k.rx is None else k.rx, k.y if k.ry is None else k.ry),
                )
                for k in chosen_layout
            ]
        ).normalize()


def _map_zmk_layout(zmk_keyboard: str, layout_name: str | None) -> dict[str, str | None]:
    @cache
    def _get_zmk_layouts() -> dict:
        with open(ZMK_LAYOUTS_PATH, "rb") as f:
            return yaml.safe_load(f)

    keyboard_to_layout_map = _get_zmk_layouts()

    if (keyboard_layouts := keyboard_to_layout_map.get(zmk_keyboard)) is None:
        logger.debug("found no ZMK layout mapping for %s, output same qmk_keyboard value", zmk_keyboard)
        return {"qmk_keyboard": zmk_keyboard, "layout_name": layout_name}

    if layout_name is None:
        out = next(iter(keyboard_layouts.values()))
    else:
        out = keyboard_layouts.get(layout_name, {})
    logger.debug("found ZMK layout mapping for %s, returning look-up value: %s", zmk_keyboard, out)
    return out


def _map_qmk_keyboard(qmk_keyboard: str) -> str:
    @cache
    def get_qmk_mappings() -> dict[str, str]:
        with open(QMK_MAPPINGS_PATH, "rb") as f:
            return yaml.safe_load(f)

    mappings = get_qmk_mappings()
    if to_keyboard := mappings.get(qmk_keyboard):
        return to_keyboard

    for from_prefix, to_keyboard in mappings.items():
        if from_prefix.endswith("/") and qmk_keyboard.startswith(from_prefix):
            return to_keyboard

    return qmk_keyboard


@lru_cache(maxsize=128)
def _get_qmk_info(qmk_keyboard: str, use_local_cache: bool = False) -> dict:
    """
    Get a QMK info.json file from either self-maintained folder of layouts,
    local file cache if enabled, or from QMK keyboards metadata API.
    """
    qmk_keyboard = _map_qmk_keyboard(qmk_keyboard)
    local_path = QMK_LAYOUTS_PATH / f"{qmk_keyboard.replace('/', '@')}.json"
    cache_path = CACHE_LAYOUTS_PATH / f"{qmk_keyboard.replace('/', '@')}.json"

    if local_path.is_file():
        with open(local_path, "rb") as f:
            return json.load(f)

    if use_local_cache and cache_path.is_file():
        logger.debug("found keyboard %s in local cache", qmk_keyboard)
        with open(cache_path, "rb") as f:
            return json.load(f)

    try:
        if qmk_keyboard.startswith("generic/"):
            logger.debug("getting generic layout %s from QMK default layouts", qmk_keyboard)
            with urlopen(QMK_DEFAULT_LAYOUTS_URL.format(layout=qmk_keyboard[len("generic/") :])) as f:
                info = json.load(f)
        else:
            with urlopen(QMK_METADATA_URL.format(keyboard=qmk_keyboard)) as f:
                logger.debug("getting QMK keyboard layout %s from QMK metadata API", qmk_keyboard)
                info = json.load(f)["keyboards"][qmk_keyboard]
        if use_local_cache:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f_out:
                json.dump({"layouts": info["layouts"]}, f_out)
        return info
    except HTTPError as exc:
        raise ValueError(
            f"QMK keyboard '{qmk_keyboard}' not found, please make sure you specify an existing keyboard "
            "(hint: check from https://config.qmk.fm)"
        ) from exc


@lru_cache(maxsize=128)
def _get_zmk_shared_layout(zmk_shared_layout: str, use_local_cache: bool = False) -> bytes:
    cache_path = CACHE_LAYOUTS_PATH / f"zmk.{zmk_shared_layout.replace('/', '@')}.dtsi"
    if use_local_cache and cache_path.is_file():
        logger.debug("found ZMK shared layout %s in local cache", zmk_shared_layout)
        with open(cache_path, "rb") as f:
            return f.read()
    try:
        with urlopen(ZMK_SHARED_LAYOUTS_URL.format(layout=zmk_shared_layout)) as f:
            logger.debug("getting ZMK shared layout %s from Github ZMK repo", zmk_shared_layout)
            layout = f.read()
        if use_local_cache:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "wb") as f_out:
                f_out.write(layout)
        return layout
    except HTTPError as exc:
        raise ValueError(
            f"ZMK shared layout '{zmk_shared_layout}' not found, please make sure you specify an existing layout "
            "(hint: check from https://github.com/zmkfirmware/zmk/tree/main/app/dts/layouts)"
        ) from exc


def _parse_dts_layout(dts_in: Path | BytesIO | bytes, cfg: ParseConfig) -> QmkLayout:  # pylint: disable=too-many-locals
    if isinstance(dts_in, Path):
        with open(dts_in, "r", encoding="utf-8") as f:
            in_str, file_name = f.read(), str(dts_in)
    elif isinstance(dts_in, BytesIO):
        in_str, file_name = dts_in.read().decode("utf-8"), None
    else:  # bytes
        in_str, file_name = dts_in.decode("utf-8"), None

    dts = DeviceTree(
        in_str,
        file_name,
        preprocess=cfg.preprocess,
        preamble=cfg.zmk_preamble,
        additional_includes=cfg.zmk_additional_includes,
    )

    def parse_binding_params(bindings):
        params = {
            k: int(v.lstrip("(").rstrip(")")) / 100 for k, v in zip(("w", "h", "x", "y", "r", "rx", "ry"), bindings)
        }
        if params["r"] == 0:
            del params["rx"], params["ry"]
        return params

    bindings_to_position = {"key_physical_attrs": parse_binding_params}

    defined_layouts: dict[str | None, list[str] | None]
    if nodes := dts.get_compatible_nodes("zmk,physical-layout"):
        defined_layouts = {node.label or node.name: node.get_phandle_array("keys") for node in nodes}
        logger.debug("found these physical layouts in DTS: %s", defined_layouts)
    else:
        raise ValueError('No `compatible = "zmk,physical-layout"` nodes found in DTS layout')

    layouts = {}
    for layout_name, position_bindings in defined_layouts.items():
        assert position_bindings is not None, f'No `keys` property found for layout "{layout_name}"'
        keys = []
        for binding_arr in position_bindings:
            binding = binding_arr.split()
            assert binding[0].lstrip("&") in bindings_to_position, f"Unrecognized position binding {binding[0]}"
            keys.append(bindings_to_position[binding[0].lstrip("&")](binding[1:]))
        layouts[layout_name] = keys
    return QmkLayout(layouts=layouts)
