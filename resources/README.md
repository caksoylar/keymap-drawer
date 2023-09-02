# Resource files for `keymap-drawer`

This folder contains resource/"data" files used by `keymap-drawer`. In particular:

- [`zmk_keyboard_layouts.yaml`](zmk_keyboard_layouts.yaml): Contains a mapping of ZMK keyboard names (the part of the filename `<keyboard>.keymap`) to a mapping
  of `matrix_transform` to [physical layout specs](../KEYMAP_SPEC.md#layout). For example:
  ```yaml
  planck:
    layout_grid_transform: {qmk_keyboard: planck/rev6, qmk_layout: LAYOUT_ortho_4x12}
    layout_mit_transform: {qmk_keyboard: planck/rev6, qmk_layout: LAYOUT_planck_1x2uC}
    layout_2x2u_transform: {qmk_keyboard: planck/rev6, qmk_layout: LAYOUT_planck_2x2u}
  ```
  Above maps each of the three matrix transforms that are defined in the
  [ZMK `planck` config](https://github.com/zmkfirmware/zmk/blob/main/app/boards/arm/planck/planck_rev6.dts) to a corresponding QMK
  keyboard+layout. When `keymap-drawer` parses a `planck.keymap`, it first searches for a matrix transform selected under a `chosen` node, e.g.:
  ```dts
  / {
      chosen {
          zmk,matrix_transform = &layout_2x2u_transform;
      };
      ...
  };
  ```
  Then it outputs the value corresponding to that keyboard/matrix transform pair as the physical layout spec. If no matrix transform is
  selected in the keymap, which is the most frequent scenario, the first transform is assumed to be the default and its value is used.

- [`qmk_layouts`](qmk_layouts/) folder: This folder contains QMK layout definitions in a pared-down `info.json` format, that either don't
  exist in the QMK keyboards API because they aren't present in the official QMK repo, or they are improved versions of existing
  layouts (such as `corne_rotated`, which contains rotated thumb keys unlike the official QMK layout).

  The file names of files in this folder should match the QMK keyboard name, except that forward slashes are replaced by `@`. The definitions
  in this folder take priority over definitions that would otherwise be fetched from the QMK API.

## Contributing

Contributions are welcome for resource files! Informally, the inclusion criterion for keyboards is whether more than one user can benefit from them.
So contributions for open source keyboards and ones that are generally available to buy are welcome. As a counter-example, if you hand-wired a keyboard
of your own design, it might be better for you to use the [`qmk_info_json` option](../KEYMAP_SPEC.md#layout) to use `keymap-drawer` with your bespoke layout.

For adding new keyboards to `zmk_keyboard_layouts.yaml`, make note of the existing organization and place the new keyboard accordingly. Reference one of the
existing YAML anchors if you are mapping to the same physical layout as others.

Adding new layouts to `qmk_layouts/` should be done only after making sure that there isn't a keyboard with the same layout in the official QMK repo that
can be referenced. If adding a new file, please make sure the formatting and contents is consistent with the existing files. Note the remarks for the
expected schema and tips for creating new layouts in the keymap spec's [layout section](../KEYMAP_SPEC.md#layout).
