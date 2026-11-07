# Changelog

## v0.98

### Added
- **Dynamic canvas size.** `Ctrl+Arrow` adds cells on that side (10 columns / 6 rows per press; left and up shift the drawing so it keeps its place). `Ctrl+Shift+Arrow` removes up to one step from that side, but only cells that are empty; if the edge has ink nothing is removed. Fully undoable (`Ctrl+Z` also restores the old size). The window and the sidebar resize with the canvas, the overlay image is rescaled, and the sidebar shows `CANVAS: WxH`. Limits: 20x12 minimum, 240x160 and 30000 cells maximum (`CANVAS_*` constants).
- **LOAD grows the canvas** when the TXT is bigger than the current one (`AUTO_GROW_ON_LOAD`).

### Changed
- **SHIFT+H help uses a smaller font** (`HELP_FONT_SIZE`) so the whole list, the credits and the new shortcuts fit in the sidebar.

### Notes
- NEW keeps the current canvas size. The timelapse stretches frames recorded before a resize to the shape of the first frame; clear it (`Ctrl+T`) after resizing if you want a clean aspect.

### Tests
- 40 new checks (141 in total): grow/shrink on every side, content and sidebar alignment, undo, limits, exports, LOAD fit, overlay, timelapse, help layout, redraw speed at 200x108.

## v0.97

### Fixed
- **Blur brush ignored the opacity setting.** It now blends with the brush opacity, and it follows the SOFT edge falloff like the paint brush does.

### Added
- **Pen pressure** (Windows Ink, optional): pressure can drive opacity, size or both (`P` cycles OFF / OPACITY / SIZE / BOTH). Mouse behaviour is unchanged, and outside Windows the hook stays off. The sidebar shows `PEN:` with mode and live pressure. Not tested on real tablet hardware yet.

### Tests
- 13 new checks (101 in total): blur opacity, pressure mapping, structure layout, P key.

## v0.96

### Added
- **SMUDGE** (`D`, button in the sidebar): pushes the ink along the drag direction. Ink is conserved and piles up in front of the brush until cells are full; ink that does not fit stays behind and nothing leaves the canvas. Brush radius = size, opacity = strength (`SMUDGE_GAIN`). Smart Edge characters of moved cells are removed.

### Tests
- 10 new checks (88 in total): ink conservation, pushing direction, full areas, canvas edge, drag through the app, key and button.

## v0.95

### Added
- **SMART BRUSH** (`M`, button in the sidebar): paints like the normal brush and gives the borders of the painted shape characters that follow the angle of the edge.
- **SMART EDGE** (`E`, button, or `Ctrl + Left Click` while in SMART BRUSH): changes only the characters of border cells under the brush, tones stay as they are. `Right Click` in SMART EDGE restores the plain tone characters. `Shift` still blurs in SMART BRUSH.
- **Character override layer** in the canvas. It is part of undo, TXT/PNG save and Markdown/HTML copy, and a TXT with edge-set characters loads back with them.
- **`assets/EDGES.txt`:** global edge character set (works with every palette). The matching is done from the shape of each glyph in the current font, so it adapts to any font.
- New sidebar buttons `SMART [M]` and `EDGE [E]`, new lines in the help overlay.

### Notes
- Timelapse and `Ctrl+Shift+C` (copy fit) resample the tones, so they do not show smart characters.

### Tests
- 22 new checks (78 in total).

## v0.94

### Changed
- **Round brush.** Character cells are taller than wide, so a brush of radius r looked like a tall oval. Brush, blur, thick lines and the brush ring now measure distance in screen pixels and are round on screen (`BRUSH_ROUND_IN_PIXELS = True`; set it to False for the old cell-space circle). The ring is a gap-free outline of exactly the cells the brush paints.
- **Click and drag on the tone sphere and on the palette bar** changes the tone while the mouse is held. Dragging outside the sphere clamps to the nearest cell. The click sound plays only on the first press.
- **Smaller sidebar font** (`UI_FONT_SIZE = 13`) for buttons, info lines and GRID. The drawing font and the mode indicators beside the sphere did not change.
- **Compact buttons:** NEW / LOAD / IMPORT / SAVE share one row (24 px high), the sidebar spacing is tighter and there is more free room at the bottom.

### Tests
- 14 new checks (57 in total): brush roundness, ring, drag, sidebar layout.

## v0.93

Tone sphere (gradient picker) fixes.

### Fixed
- **Tangled glyphs in the sphere.** The sphere drew characters at half-cell steps, so neighbours overlapped. It now uses a real character grid with a smaller font (`PICKER_FONT_SIZE = 11`), so every glyph has its own cell.
- **Sphere not centered / cut at the top.** The grid is now centered in the frame and the sphere always fits inside it.
- **Weak dark fall-off.** Shading is now "half lambert" normalised over the visible hemisphere, so the sphere uses the full tonal range, from the lightest highlight to a soft dark edge.
- **Click did not pick the clicked character.** It recomputed the tone from the pixel and then highlighted another cell with a similar tone. A click now picks the exact tone of the clicked cell and the highlight stays on that cell.

### Tests
- `tests/smoke_test.py` has 8 new checks for the sphere (43 in total).

## v0.92

Bug fix and cleanup release. The look and feel of the interface did not change.

### Fixed
- **Copy Fit (`Ctrl+Shift+C`) crashed the app.** It used a variable that did not exist (`is_space`), and the error fallback called the same code again.
- **Saves from the .exe went to a temporary folder.** The app changed its working directory to the PyInstaller bundle, so `Ctrl+S` wrote there. Saves now go to a `saves` folder next to the script or the `.exe`.
- **IMPORT button left the mouse "held".** The dialog swallowed the mouse-up, so the app kept painting by itself afterwards. Every dialog now resets the mouse state.
- **`Ctrl+Alt+S` (copy for Slack) never ran.** `Ctrl+S` and plain `S` caught it first.
- **Timelapse frame limit.** The source declared 20000 and silently used 2000. There is now a single `TIMELAPSE_MAX_FRAMES = 2000`.
- **Timelapse recorded noise.** Plain UI clicks injected pause frames, and key presses added frames even when the canvas did not change. Now only real strokes count, and duplicate frames are skipped.
- **Timelapse export lost your frames on failure.** Frames are now cleared only after a successful export. Cancelling the save dialog really cancels.
- **Line mode** now records its final frame in the timelapse.
- **LOAD .txt:** short lines, missing rows and characters that are not in the palette became the lightest tone. They are now empty (the darkest tone, a space).
- **NEW canvas** erased the whole undo history. NEW, LOAD and IMPORT are now undoable.
- Pillow: removed the deprecated `mode=` argument of `Image.fromarray`.

### Changed
- Much faster drawing: glyphs are rendered once and cached (the canvas needs about 4000 per frame). The picture is pixel-identical to v0.91.
- Timelapse GIF export is faster and uses about 3x less memory (8-bit grey frames, repeated frames rendered once).
- `PAL.txt`, `startup.txt` and the sounds moved to `assets/`. Copies placed next to the script or the `.exe` override them.
- The window shrinks when the screen is too small for it (`AUTO_FIT_WINDOW`).
- The version is shown in the sidebar (bottom left) and the file name carries it (`ASCIIPAINT_v092.py`).
- A crash now writes `crash.log` next to the app.
- New `run_asciipaint.bat` / `.sh`, `build_release.bat`, `build_onefile.bat`. They find the newest `ASCIIPAINT_v*.py` and read its version.

### Added
- `tests/smoke_test.py`, a headless test of the main features.
- `README.md` rewritten, `LICENSE` (MIT), `.gitignore`, this changelog.

## v0.91
- Timelapse recorder with GIF export, IMPORT button, overlay image.

Older versions: see the git history.
