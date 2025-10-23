# ASCII Painter v0.90

A lightweight ASCII art painting tool for drawing with monospaced characters on a grid.

**Author:** Marcelo Souza (@msouza3d)  
**Inspired by:** the work of [Vagon Parovoz](https://www.instagram.com/vagonparovoz/) and classic ANSI/ASCII art editors

---

## Overview

ASCII Painter is a standalone, keyboard-driven ASCII art editor built with **Python + Pygame + NumPy**.  
It lets you paint tones, lines, and highlights using a customizable palette of characters (light → dark),  
export directly to text or PNG, and even play subtle audio feedback while you draw.

---

## How to Run

### Windows
Double-click:
```
run_windows.bat
```

### macOS / Linux
Run from terminal:
```
sh run_mac_linux.sh
```

---

## Files

- **ASCIIPAINT.py** → main source code  
- **PAL.txt** → palette definitions (light → dark, optional)  
- **keypress_XX.wav** → optional keypress audio feedback files  
- **startup.txt** → optional auto-load ASCII project at launch  

---

## Features

### 🎨 Drawing System
- Paint with ASCII characters mapped from tone values (0.0 light → 1.0 dark).  
- Adjustable brush radius, opacity, and tone intensity.  
- Smooth and soft edge brushes with optional blur blending.  
- Multiple modes: **Paint**, **Blur**, **Highlight**, and **Line** (with or without AA).  
- Gaussian blur for smoothing and blending ASCII textures.  
- Reversible palette system: `I` to invert (light ↔ dark).  

### 🧱 Canvas & Grid
- Square cell canvas with correct aspect ratio for monospaced rendering.  
- Grid overlay perfectly aligned with character cells (1:1).  
- “Grid = Cells” mode ensures per-character snapping for exports.  
- `Ctrl+Shift+C` automatically snaps the exported bounding box to grid divisions when grid is ON.

### 💡 Overlay Image System (NEW in v0.90)
- `SHIFT+O` → Load an overlay image (`.png`, `.jpg`, `.bmp`, `.webp`).  
- `O` → Show/Hide overlay (toggle visibility).  
- Adjustable transparency via constant `OVERLAY_OPACITY` (default `0.35`).  
- Overlay sits visually **above the ASCII canvas but below the UI**, allowing reference tracing.  
- Ideal for sketching over photos or imported references.

### 🔊 Audio Feedback
- Subtle keypress sounds for strokes and UI actions (`keypress_01.wav`, `keypress_02.wav`, …).  
- Dual-channel playback with short overlap fades for smooth, non-blocking sound.  
- Adjustable pitch variation (`PITCH_VARIATION_PCT`, `PITCH_VARIATION_STEPS`).  
- Automatic gating to prevent sound overlap during fast strokes.  
- Optional “play full sample on release” for brush-up feedback.

### 🧰 Copy, Export & Import
- `Ctrl+S` → Save both `.TXT` (ASCII) and `.PNG` (rendered).  
- `Ctrl+C` → Copy to clipboard as Markdown code block.  
- `Ctrl+Alt+C` → Copy as HTML `<pre>` block (with non-collapsing spaces).  
- `Ctrl+Shift+C` → “Copy Fit” mode — crops by content or grid, then resamples.  
- `Ctrl+Shift+N` → Toggle non-breaking spaces (`NBSP`) for web export.  
- Optional `startup.txt` auto-loads a previous project on launch.  
- Image import (via **IMPORT** button) converts brightness to tone values.

### 🪶 Highlight Mode
- `H` → Toggle highlight mode.  
- Left click = add white highlight (persistent).  
- Right click = erase highlight (restore base luma).  
- `Shift` temporarily switches from Highlight to Paint+Smooth for blending.

### 🧩 Line Drawing
- `L` → Toggle line mode (with live preview).  
- `A` → Toggle anti-aliasing (AA).  
- Lines respect brush radius and soft-edge setting.  
- Supports both thick AA and basic pixel-style lines.

### 🪄 User Interface
- Sidebar shows palette picker, spherical tone picker, indicators, and grid controls.  
- Mode indicators: HLIGHT / SOFT / PAINT / BLUR / LINE / LINEAA.  
- Clickable buttons for NEW, LOAD, IMPORT, SAVE.  
- Grid panel displays live cursor coordinates (x, y).  
- Mouse-over ghost ring shows brush size and active tone character.  
- Context-sensitive tool info and help hint (`SHIFT+H for HELP`).  

---

## Shortcuts

### Drawing
- **Left Click** → Paint / Blur / Highlight  
- **Right Click** → Erase / Erase Highlight  
- **Middle Click** → Lighten  
- **Ctrl + Middle Click** → Darken  

### Modes
- **B** → Blur mode  
- **L** → Line mode (toggle)  
- **A** → Toggle line Anti-Alias  
- **H** → Highlight mode  
- **Shift (hold)** → Temporary Smooth / Blur  

### Tone & Brush
- **-** → Darker tone  
- **=** → Lighter tone  
- **1..0** → Tone deciles  
- **[ / ]** → Brush radius  
- **Ctrl + Scroll Wheel** → Change tone  
- **Shift + Scroll Wheel** → Opacity  
- **X** → Toggle darkest / lightest tone  

### Grid & Export
- **G** → Toggle grid overlay  
- **Ctrl+S** → Save TXT + PNG  
- **Ctrl+C** → Copy as Markdown  
- **Ctrl+Alt+C** → Copy as HTML `<pre>`  
- **Ctrl+Shift+C** → Copy Fit (Bounding Box / Grid)  
- **Ctrl+Shift+N** → Toggle NBSP spaces  

### Overlay
- **O** → Show / Hide overlay  
- **Shift+O** → Load new overlay image  

### UI & Control
- **Shift+H** → Show/Hide Help overlay  
- **Ctrl+Q** → Quit (with save prompt)  

---

## Configuration Constants

Key variables you can tweak in the source:
```python
OVERLAY_OPACITY = 0.35   # Overlay transparency (0.0 - 1.0)
TEXT_LUMA = 0.72         # Default character brightness
INITIAL_BRUSH_RADIUS = 1 # Starting brush radius
UNDO_LIMIT = 64          # Max undo history steps
TARGET_ASPECT = 4.0 / 3.0
MAX_COLS = 80
ROWS_OVERRIDE = 48
```

---

## Credits

Created by **Marcelo Souza (@msouza3d)**  
Inspired by the work of [Vagon Parovoz](https://www.instagram.com/vagonparovoz/)  
and the ASCII/ANSI art community.

Special thanks to everyone experimenting with digital ASCII art in modern creative tools.

---

## License

This project is released under the **MIT License**.  
Feel free to modify, remix, and share — credit appreciated.
