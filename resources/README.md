# Resource files for `keymap-drawer`

This folder contains resource/"data" files used by `keymap-drawer`. In particular:

- [`zmk_keyboard_layouts.yaml`](zmk_keyboard_layouts.yaml): Contains a mapping of ZMK keyboard names (the part of the filename `<keyboard>.keymap`) to a mapping
  of `physical-layout` to [physical layout specs](../PHYSICAL_LAYOUTS.md). For example:
  ```yaml
  planck:
    layout_grid_transform: {qmk_keyboard: planck/rev6, layout_name: LAYOUT_ortho_4x12}
    layout_mit_transform: {qmk_keyboard: planck/rev6, layout_name: LAYOUT_planck_1x2uC}
    layout_2x2u_transform: {qmk_keyboard: planck/rev6, layout_name: LAYOUT_planck_2x2u}
  ```
  Above maps each of the three physical layouts that are defined in the
  [ZMK `planck` config](https://github.com/zmkfirmware/zmk/blob/main/app/boards/arm/planck/planck_rev6.dts) to a corresponding QMK
  keyboard+layout.

  When `keymap parse` parses a `planck.keymap`, it first searches for a ZMK physical layout (or matrix transform, for backwards compatibility)
  selected under a `chosen` node, e.g.:
  ```dts
  / {
      chosen {
          zmk,physical-layout = &layout_ortho_4x12_2x2u;

          // or, equivalently:
          // zmk,matrix-transform = &layout_2x2u_transform;
      };
      ...
  };
  ```
  Then it outputs the value corresponding to that keyboard/physical layout pair as the physical layout spec: `{zmk_keyboard: planck, layout_name: LAYOUT_ortho_4x12}`.
  If there is no layout selected in the keymap (which is the most frequent scenario), `layout_name` will be omitted.

  `keymap draw` will then look up and replace the physical layout spec with the corresponding entry in this file.
  If there is no `layout_name`, the first entry is assumed to be the default and its value is used.

- [`extra_layouts`](extra_layouts/) folder: This folder contains QMK layout definitions in a pared-down `info.json` format, that either don't
  exist in the QMK keyboards API because they aren't present in the official QMK repo, or they are improved versions of existing
  layouts (such as `corne_rotated`, which contains rotated thumb keys unlike the official QMK layout).

  The file names of files in this folder should match the QMK keyboard name, except that forward slashes are replaced by `@`. The definitions
  in this folder take priority over definitions that would otherwise be fetched from the QMK API.

- [`qmk_keyboard_mappings.yaml`](qmk_keyboard_mappings.yaml): This file contains a set of mappings that map `qmk_keyboard` values to another
  `qmk_keyboard` value. If the key/field ends with a trailing slash, it matches as a prefix. Otherwise it looks for an exact match.

  This is used to prefer certain physical layout definitions over others: For instance all Corne variants are mapped to use
  the `extra_layouts/corne_rotated.json` file instead of the QMK default layout for `crkbd/rev1`.
  This look-up and consequent replacement happens during drawing -- it is transparent to the user and it cannot be prevented.

## Contributing

Contributions are welcome for resource files! Informally, the inclusion criterion for keyboards is whether more than one user can benefit from them.
So contributions for open source keyboards and ones that are generally available to buy are welcome. As a counter-example, if you hand-wired a keyboard
of your own design, it might be better for you to use the [`qmk_info_json`](../PHYSICAL_LAYOUTS.md#qmk-infojson-specification) or
[`dts_layout`](../PHYSICAL_LAYOUTS.md#zmk-devicetree-physical-layout-specification) options to use `keymap-drawer` with your bespoke layout.

For adding new keyboards to `zmk_keyboard_layouts.yaml`, make note of the existing organization and place the new keyboard accordingly. Reference one of the
existing YAML anchors if you are mapping to the same physical layout as others.

Adding new layouts to `extra_layouts/` should be done only after making sure that there isn't a keyboard with the same layout in the official QMK repo that
can be referenced. If adding a new file, please make sure the formatting and contents is consistent with the existing files. Note the remarks for the
expected schema and tips for creating new layouts in the [physical layouts documentation](../PHYSICAL_LAYOUTS.md).
