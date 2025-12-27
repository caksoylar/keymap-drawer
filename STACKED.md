# Stacked Layer Diagrams

The `keymap stack-layers` command combines multiple keyboard layers into a single diagram with corner legends. This creates compact reference diagrams showing up to 5 layers at once.

![Stacked layers example](site/stacked.svg)

## Usage

```sh
keymap stack-layers --center Base --tl Fun --tr Sys --bl Num --br Nav keymap.yaml > stacked.yaml
keymap draw stacked.yaml > stacked.svg
```

### Options

| Option | Description |
|--------|-------------|
| `--center` | Layer name for center position (required) |
| `--tl` | Layer name for top-left corner |
| `--tr` | Layer name for top-right corner |
| `--bl` | Layer name for bottom-left corner |
| `--br` | Layer name for bottom-right corner |
| `--hidden-corner-legends` | Values to hide in corners (e.g., modifier symbols) |
| `--list-layers` | List available layer names and exit |
| `-o, --output` | Output file (default: stdout) |

### Pipeline Example

Stack and draw in a single pipeline:

```sh
keymap -c config.yaml stack-layers --center colemak_dh --tl fun --tr sys --bl num --br nav keymap.yaml | \
  keymap -c config.yaml draw -k "ferris/sweep" - -o stacked.svg
```

**Important:** Pass `-c config.yaml` to both commands:
- `stack-layers` uses `stack_config.hidden_corner_legends` for filtering
- `draw` uses `draw_config.svg_extra_style` for styling

## Configuration

### stack_config

Add to your config YAML:

```yaml
stack_config:
  hidden_corner_legends:
    - ⇧
    - ⌃
    - ⌥
    - ⌘
    - sticky
    - $$mdi:pause$$  # glyphs use full syntax
```

| Field | Type | Description |
|-------|------|-------------|
| `hidden_corner_legends` | `list[str]` | Values to hide in corner positions |
| `hidden_held_legends` | `list[str]` | Hold legend values to hide |
| `hidden_shifted_legends` | `list[str]` | Shifted legend values to hide |

## CSS Styling

Corner legends use CSS classes `tl`, `tr`, `bl`, `br` for styling. Add to `draw_config.svg_extra_style`:

### Text Legends

```css
/* Corner legend text colors, sizing, and alignment */
/* text-anchor controls horizontal alignment, dominant-baseline controls vertical */
text.tl { fill: #F93827; font-size: 8px; text-anchor: start; dominant-baseline: hanging; }
text.tr { fill: #2563EB; font-size: 8px; text-anchor: end; dominant-baseline: hanging; }
text.bl { fill: #16A34A; font-size: 8px; text-anchor: start; dominant-baseline: auto; }
text.br { fill: #FF9D23; font-size: 8px; text-anchor: end; dominant-baseline: auto; }
```

### Glyph Legends

Glyphs are `<use>` elements, not text. Style them separately:

```css
/* Corner glyph colors */
use.tl { fill: #F93827; }
use.tr { fill: #2563EB; }
use.bl { fill: #16A34A; }
use.br { fill: #FF9D23; }
```

### Layer Activator Keys

Style keys that activate layers with colored backgrounds:

```css
/* Layer activator key backgrounds */
.held-tl rect, .layer-tl rect { fill: #F93827; }
.held-tr rect, .layer-tr rect { fill: #2563EB; }
.held-bl rect, .layer-bl rect { fill: #16A34A; }
.held-br rect, .layer-br rect { fill: #FF9D23; }

/* White text on colored backgrounds */
.held-tl text, .layer-tl text { fill: white; }
.held-tr text, .layer-tr text { fill: white; }
.held-bl text, .layer-bl text { fill: white; }
.held-br text, .layer-br text { fill: white; }
```

To use these, set `type: layer-tl` (or `layer-tr`, etc.) on layer activator keys in your keymap:

```yaml
raw_binding_map:
  "&mo FUN": { t: Fun, type: layer-tl }
  "&mo NAV": { t: Nav, type: layer-br }
```

## Corner Positioning

Corner legend positioning is controlled by these `draw_config` settings:

```yaml
draw_config:
  inner_pad_w: 2.0  # padding from key edge (horizontal)
  inner_pad_h: 2.0  # padding from key edge (vertical)
  small_pad: 4.0    # additional corner padding
```

The corner position is calculated as:
```
corner_x = key_width/2 - inner_pad_w - small_pad
corner_y = key_height/2 - inner_pad_h - small_pad
```

## Complete Example Config

```yaml
draw_config:
  small_pad: 4.0
  svg_extra_style: |
    /* Layer activator key colors */
    .held-tl rect, .layer-tl rect { fill: #F93827; }
    .held-tr rect, .layer-tr rect { fill: #2563EB; }
    .held-bl rect, .layer-bl rect { fill: #16A34A; }
    .held-br rect, .layer-br rect { fill: #FF9D23; }

    .held-tl text, .layer-tl text { fill: white; }
    .held-tr text, .layer-tr text { fill: white; }
    .held-bl text, .layer-bl text { fill: white; }
    .held-br text, .layer-br text { fill: white; }

    /* Corner legend text */
    text.tl { fill: #F93827; font-size: 8px; text-anchor: start; dominant-baseline: hanging; }
    text.tr { fill: #2563EB; font-size: 8px; text-anchor: end; dominant-baseline: hanging; }
    text.bl { fill: #16A34A; font-size: 8px; text-anchor: start; dominant-baseline: auto; }
    text.br { fill: #FF9D23; font-size: 8px; text-anchor: end; dominant-baseline: auto; }

    /* Corner glyphs */
    use.tl { fill: #F93827; }
    use.tr { fill: #2563EB; }
    use.bl { fill: #16A34A; }
    use.br { fill: #FF9D23; }

stack_config:
  hidden_corner_legends:
    - ⇧
    - ⌃
    - ⌥
    - ⌘
    - Nav
    - Spc
    - sticky
```

See [`examples/stacked/`](examples/stacked/) for a complete working example.
