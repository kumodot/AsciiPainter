# Changelog

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
