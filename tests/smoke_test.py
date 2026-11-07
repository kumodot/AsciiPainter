"""Headless smoke test for ASCII Painter (no window, no sound card needed).

Usage:  python tests/smoke_test.py [path/to/ASCIIPAINT_vXXX.py]
Without an argument it tests the newest ASCIIPAINT_v*.py next to this folder.
Needs: pygame, numpy, Pillow.
"""
import os, sys, glob, importlib.util, tempfile, traceback
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np
import pygame

ROOT = Path(__file__).resolve().parent.parent
if len(sys.argv) > 1:
    APP_FILE = Path(sys.argv[1]).resolve()
else:
    APP_FILE = sorted(ROOT.glob("ASCIIPAINT_v*.py"))[-1]

spec = importlib.util.spec_from_file_location("asciipaint_under_test", APP_FILE)
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

TMP = Path(tempfile.mkdtemp(prefix="asciipaint_test_"))
results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond)))
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{extra}]" if extra and not cond else ""))


def new_app():
    # fresh App each time (run() calls pygame.quit() at the end)
    if hasattr(M, "SAVES_DIR"):
        M.SAVES_DIR = TMP / "saves"
    M.open_folder = lambda *_a, **_k: None
    return M.App()


def run_events(app, events, mouse_pos=(0, 0), mods=0):
    """Feed events to the real main loop, then QUIT. `mouse_pos` is in canvas/surface coordinates
    (the window may be scaled down by AUTO_FIT_WINDOW, so convert like a real mouse would report)."""
    sc = M.WINDOW_SCALE
    raw = (int(round(mouse_pos[0] * sc)), int(round(mouse_pos[1] * sc)))
    real_get_pos, real_get_mods, real_quit = pygame.mouse.get_pos, pygame.key.get_mods, pygame.quit
    pygame.mouse.get_pos = lambda: raw
    pygame.key.get_mods = lambda: mods
    pygame.quit = lambda: None            # keep pygame alive so the same App can run again
    app.running = True
    try:
        for e in events:
            pygame.event.post(e)
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        app.run()
    finally:
        pygame.mouse.get_pos, pygame.key.get_mods, pygame.quit = real_get_pos, real_get_mods, real_quit


def guarded(name, fn):
    try:
        fn()
    except Exception:
        check(name + " (raised an exception)", False, traceback.format_exc().strip().splitlines()[-1])
        traceback.print_exc()


# ---------------------------------------------------------------- tests
def t_startup_and_palette():
    app = new_app()
    check("version string set", isinstance(M.VERSION, str) and M.VERSION)
    check("canvas size 80 cols", app.canvas.cols == 80 and app.canvas.rows > 0)
    check("PAL.txt found (palettes loaded)", len(app.pal.order) >= 1, f"order={app.pal.order}")
    check("darkest tone is a space", app.pal.chars[-1] == " ")
    check("startup.txt loaded (canvas not empty)", float(app.canvas.buf.min()) < 1.0)
    pygame.quit()


def t_bbox_and_copy_fit():
    app = new_app()
    got = {}
    M.copy_to_clipboard = lambda txt: got.setdefault("txt", txt) or True
    bbox = app.compute_content_bbox()               # v0.91: NameError (is_space)
    check("compute_content_bbox works", len(bbox) == 4 and bbox[1] > bbox[0] and bbox[3] > bbox[2], str(bbox))
    app.copy_fit_cols(40, None, "markdown")
    check("copy_fit_cols copies a markdown block", got.get("txt", "").startswith("```"))
    pygame.quit()


def t_ctrl_shift_c_does_not_crash():
    app = new_app()
    got = {}
    M.copy_to_clipboard = lambda txt: got.setdefault("txt", txt) or True
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_c, mod=0, unicode="")
    run_events(app, [ev], mods=pygame.KMOD_CTRL | pygame.KMOD_SHIFT)   # v0.91: crashed the app
    check("Ctrl+Shift+C survives (dialog unavailable or not)", True)
    check("Ctrl+Shift+C copied something", "txt" in got)


def t_ctrl_alt_s_slack_copy():
    app = new_app()
    calls = []
    app.copy_fit_cols = lambda *a, **k: calls.append(k.get("row_scale"))
    saved = []
    app.quick_save = lambda: saved.append(1)
    soft_before = app.soft_edge
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s, mod=0, unicode="")
    run_events(app, [ev], mods=pygame.KMOD_CTRL | pygame.KMOD_ALT)
    check("Ctrl+Alt+S runs the Slack copy", calls == [M.SLACK_ROW_SCALE], str(calls))
    check("Ctrl+Alt+S does not quick-save", not saved)
    check("Ctrl+Alt+S does not toggle soft edge", app.soft_edge == soft_before)


def t_ctrl_s_saves_in_saves_dir():
    app = new_app()
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s, mod=0, unicode="")
    run_events(app, [ev], mods=pygame.KMOD_CTRL)
    files = list((TMP / "saves").glob("ascii_*.txt")) + list((TMP / "saves").glob("ascii_*.png"))
    exts = sorted(f.suffix for f in files)
    check("Ctrl+S writes .txt and .png into saves/", exts == [".png", ".txt"], str(exts))


def t_import_button_does_not_stick():
    app = new_app()
    center = app.import_btn.center
    down = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=center)
    run_events(app, [down], mouse_pos=center)       # v0.91: left_down stayed True after the dialog
    check("IMPORT click leaves no mouse button 'held'", not (app.left_down or app.right_down or app.mid_down))


def t_save_load_roundtrip_and_short_lines():
    app = new_app()
    app.canvas.clear(1.0, M.TEXT_LUMA)
    app.canvas.paint_disc_blend(10, 10, 1, 0.3, 1.0, False)
    p = TMP / "rt.txt"
    app.save_txt(str(p))
    before = app.build_ascii_lines()
    app.canvas.clear(1.0, M.TEXT_LUMA)
    app.load_txt_into_canvas(str(p))
    check("save/load round trip keeps the text", app.build_ascii_lines() == before)

    # editors often trim trailing spaces and empty last lines
    q = TMP / "short.txt"
    q.write_text("@@@@\n##\n", encoding="utf-8")
    app.load_txt_into_canvas(str(q))
    check("LOAD: missing columns are empty (darkest), not the lightest tone",
          float(app.canvas.buf[0, 10]) == 1.0 and float(app.canvas.buf[1, 40]) == 1.0 and float(app.canvas.buf[30, 5]) == 1.0)
    q.write_text("\u00e9\u00e9", encoding="utf-8")   # chars that are not in the palette
    app.load_txt_into_canvas(str(q))
    check("LOAD: unknown char becomes empty", float(app.canvas.buf[0, 0]) == 1.0)
    n = len(app.undo_stack)
    app.undo()
    check("LOAD can be undone", len(app.undo_stack) == n - 1)
    pygame.quit()


def t_import_image_undo():
    from PIL import Image
    app = new_app()
    img = TMP / "grad.png"
    arr = np.tile(np.linspace(0, 255, 64, dtype=np.uint8), (48, 1))
    Image.fromarray(arr).save(img)
    before = app.canvas.buf.copy()
    app.import_image_to_canvas(str(img))
    check("IMPORT changes the canvas", not np.allclose(app.canvas.buf, before))
    app.undo()
    check("IMPORT can be undone", np.allclose(app.canvas.buf, before))
    pygame.quit()


def t_new_canvas_undoable():
    app = new_app()
    app.canvas.paint_disc_blend(5, 5, 1, 0.1, 1.0, False)
    before = app.canvas.buf.copy()
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_n, mod=0, unicode="n")
    app.ask_modal_yesno = lambda *_a, **_k: True
    run_events(app, [ev], mods=0)
    check("N (new canvas) cleared the canvas", float(app.canvas.buf.min()) == 1.0)
    app2 = app  # state is still readable after pygame.quit()
    check("NEW pushed an undo step", len(app2.undo_stack) >= 1 and np.allclose(app2.undo_stack[-1][0], before))


def t_timelapse():
    app = new_app()
    tl = app.tl
    tl.enabled = True
    app.canvas.clear(1.0, M.TEXT_LUMA)
    tl.capture(app.canvas, app.pal)
    tl.capture(app.canvas, app.pal)                 # unchanged canvas -> skipped
    check("timelapse skips duplicate frames", len(tl.frames) == 1, f"frames={len(tl.frames)}")
    for i in range(6):
        app.canvas.paint_disc_blend(5 + i * 3, 8, 2, 0.2, 1.0, False)
        tl.capture(app.canvas, app.pal)
    tl.inject_repeat_last(4)
    n_frames = len(tl.frames)
    check("timelapse recorded frames", n_frames == 1 + 6 + 4, f"frames={n_frames}")
    check("timelapse limit is a single value", M.TIMELAPSE_MAX_FRAMES == tl.max_frames == 2000)

    bad = "/nonexistent_dir_xyz/out.gif"
    ok_bad = tl.export_gif(bad, app.font, app.char_w, app.char_h)
    check("failed export returns False", ok_bad is False)
    check("failed export keeps the frames", len(tl.frames) == n_frames, f"frames={len(tl.frames)}")

    gif = TMP / "tl.gif"
    ok = tl.export_gif(str(gif), app.font, app.char_w, app.char_h)
    check("export_gif succeeds", ok is True and gif.exists() and gif.stat().st_size > 0)
    from PIL import Image
    with Image.open(gif) as im:
        check("GIF has several frames", getattr(im, "n_frames", 1) >= 7, f"n_frames={getattr(im, 'n_frames', 1)}")
    check("successful export clears frames", len(tl.frames) == 0)
    pygame.quit()


def t_plain_click_does_not_inject_timelapse_frames():
    app = new_app()
    app.tl.enabled = True
    app.canvas.clear(1.0, M.TEXT_LUMA)
    app.tl.capture(app.canvas, app.pal)
    n = len(app.tl.frames)
    # click on the GRID checkbox (UI), release: not a stroke
    pos = app.grid_checkbox_rect.center
    down = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)
    up = pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=pos)
    run_events(app, [down, up], mouse_pos=pos)
    check("UI click adds no timelapse frames", len(app.tl.frames) == n, f"{n} -> {len(app.tl.frames)}")


def t_line_mode_records_timelapse_frame():
    app = new_app()
    app.canvas.clear(1.0, M.TEXT_LUMA)
    app.undo_stack.clear()
    app.tl.enabled = True
    app.tl.capture(app.canvas, app.pal)             # blank first frame
    n0 = len(app.tl.frames)
    app.mode = "line"
    cw, ch, oy = app.char_w, app.char_h, app.canvas_offset_y
    p1 = (int(10.5 * cw), int(oy + 10.5 * ch))
    p2 = (int(40.5 * cw), int(oy + 20.5 * ch))
    for p in (p1, p2):
        run_events(app, [pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=p),
                         pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=p)], mouse_pos=p)
    drawn = int((app.canvas.buf < 1.0).sum())
    check("line mode: the line was drawn", drawn > 20, f"cells={drawn}")
    check("line mode: the final state + pause frames are recorded",
          len(app.tl.frames) == n0 + 1 + M.TL_MOUSE_RELEASE_INJECT_FRAMES, f"{n0} -> {len(app.tl.frames)}")
    pygame.quit()


def t_glyph_cache():
    app = new_app()
    a = app.glyphs.get("#", (180, 180, 180))
    b = app.glyphs.get("#", (180, 180, 180))
    check("glyph cache returns the same surface", a is b)
    # a few redraws must work and be reasonably fast
    import time
    t0 = time.time()
    for _ in range(20):
        app.redraw_canvas_ascii(app.surface, 0, 0, 0)
    dt = (time.time() - t0) / 20
    check("canvas redraw is fast (<40 ms/frame headless)", dt < 0.040, f"{dt*1000:.1f} ms")
    print(f"      redraw: {dt*1000:.1f} ms/frame")
    pygame.quit()


for fn in (t_startup_and_palette, t_bbox_and_copy_fit, t_ctrl_shift_c_does_not_crash, t_ctrl_alt_s_slack_copy,
           t_ctrl_s_saves_in_saves_dir, t_import_button_does_not_stick, t_save_load_roundtrip_and_short_lines,
           t_import_image_undo, t_new_canvas_undoable, t_timelapse,
           t_plain_click_does_not_inject_timelapse_frames, t_line_mode_records_timelapse_frame, t_glyph_cache):
    guarded(fn.__name__, fn)

failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed  ({APP_FILE.name})")
sys.exit(1 if failed else 0)
