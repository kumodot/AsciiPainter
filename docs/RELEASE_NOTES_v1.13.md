## ASCII Painter v1.13

First public release since v0.91. It rolls up everything from v0.92 to v1.13 (see `CHANGELOG.md` for the full list).

**Read this first:** this is not real ASCII art, and it does not pretend to be. It is a paint program that uses letters as ink, a toy. All respect to the artists who place every character by hand (Vagon Parovoz is the reason the project exists). For people who want to do it that way inside the app, there is the new **TRU mode**.

- **TRU mode** (`Tab`): no brushes, the mouse only moves a cursor and you type every character. `Alt+1` to `Alt+0` sets the shading level of the cell under the cursor, from darkest to lightest.
- **Palette editor** (double click the palette bar or the tone sphere): pick characters from a table or just type them, add and remove shading levels with `-` and `+`, drag characters to reorder, `RESTORE` / `SAVE` / `SAVE NEW`.
- **Bomb brush** (`K`): a ripple that pushes the ink outward, with a shrinking warning ring during the fuse. Dense areas now fade out gradually along every ray.
- **Voice**: a raw formant speech synthesizer announces brushes, TRU mode, bombs, timelapse and palette saves, with yellow captions at the top of the canvas. `VOICE` checkbox or `V` turns it off.
- **Timelapse row** under the tone sphere: `REC`, progress bar, `GIF`, `CLR`.
- **Smart Brush / Smart Edge**, **Smudge**, **pen pressure** (Windows Ink), **resizable canvas**, **tooltips** and a **palette shortcut bar** (all since v0.92).
- 401 headless checks (`python tests/smoke_test.py`).

Run: `run_asciipaint.bat` (Windows) or `sh run_asciipaint.sh`, or download the Windows build from the release assets.
