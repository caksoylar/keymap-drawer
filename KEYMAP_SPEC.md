# Keymap YAML specification

This page documents the YAML-format keymap representation that is output by `keymap parse` and used by `keymap draw`.

At the root, three key values are expected, which are detailed in respective sections. A typical keymap will have the following structure:

```yaml
layout:     # physical layout specs
  ...
layers:     # mapping of layer name to contents
  layer_1:  # list of (lists of) key specs
    - [Q, W, ...]
    ...
  layer_2:
    ...
combos:     # optional, list of combo specs
  - ...
```

## `layout`

## `layers`

## `combos`
