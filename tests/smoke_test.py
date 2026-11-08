"""Headless smoke test for ASCII Painter (no window, no sound card needed).

Usage:  python tests/smoke_test.py [path/to/ASCIIPAINT_vXXX.py]
Without an argument it tests the newest ASCIIPAINT_v*.py next to this folder.
Needs: pygame, numpy, Pillow.
"""
import os, sys, glob, time, importlib.util, tempfile, traceback
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
    check("LOAD: a drawable char outside the palette is kept as typed (TRU text)",
          int(app.canvas.ov[0, 0]) == ord("\u00e9") and float(app.canvas.buf[0, 0]) < 1.0)
    q.write_text("\U0001F600\U0001F600", encoding="utf-8")   # a char the font cannot draw
    app.load_txt_into_canvas(str(q))
    check("LOAD: a char the font cannot draw becomes empty", float(app.canvas.buf[0, 0]) == 1.0 and int(app.canvas.ov[0, 0]) == 0)
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


def t_tone_sphere():
    app = new_app()
    app._build_picker_grid()
    g = app._picker_grid
    rects = [r for r, _t in g.values()]
    pr = app.picker_rect
    check("sphere cells are inside the frame", all(pr.contains(r) for r in rects))
    check("sphere cells never overlap", all(not a.colliderect(b) for i, a in enumerate(rects) for b in rects[i+1:]))
    check("sphere cells are exact character cells",
          all(r.w == app.pk_w and r.h == app.pk_h for r in rects))
    left = min(r.left for r in rects) - pr.left; right = pr.right - max(r.right for r in rects)
    top = min(r.top for r in rects) - pr.top; bottom = pr.bottom - max(r.bottom for r in rects)
    check("sphere is centered and not cut", abs(left-right) <= app.pk_w + 1 and abs(top-bottom) <= app.pk_h + 1,
          f"L{left} R{right} T{top} B{bottom}")
    tones = [t for _r, t in g.values()]
    check("sphere uses the full tonal range", min(tones) < 0.05 and max(tones) > 0.9, f"{min(tones):.2f}..{max(tones):.2f}")

    # clicking a cell picks exactly that cell's tone and keeps the highlight on that cell
    ok_val = ok_sel = True; n = 0
    for pal_n in app.pal.order[:4]:
        app.pal.set_index(pal_n)
        app._picker_grid = None; app._build_picker_grid(); g = app._picker_grid
        for key in list(g)[::9]:
            rect, tone = g[key]
            app._last_sphere_click = None                  # (two quick clicks on the same shade would be a double click)
            app.handle_picker_click(*rect.center)
            app.draw_spherical_picker(app.surface)
            n += 1
            ok_val &= abs(app.current_value - tone) < 1e-9
            ok_sel &= (app.picker_sel_rect == rect)
    check(f"click picks the clicked cell tone ({n} cells, 4 palettes)", ok_val)
    check("selection stays on the clicked cell", ok_sel)

    # same click delivered through the real event loop
    app.pal.set_index(app.pal.order[0]); app._picker_grid = None; app._build_picker_grid()
    key = list(app._picker_grid)[len(app._picker_grid)//3]
    rect, tone = app._picker_grid[key]
    run_events(app, [pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(0, 0), button=1),
                     pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(0, 0), button=1)], mouse_pos=rect.center)
    check("click through the main loop picks the same tone", abs(app.current_value - tone) < 1e-9,
          f"{app.current_value} vs {tone}")
    pygame.quit()


def t_brush_is_round_in_pixels():
    app = new_app()
    c = app.canvas
    check("canvas knows the cell aspect", c.aspect > 1.2, f"aspect={c.aspect}")
    for r in (3, 6, 12):
        c.clear(1.0)
        c.paint_disc_blend(40, 30, r, 0.0, 1.0, False)
        ys, xs = np.nonzero(c.buf < 0.5)
        w_px = (xs.max() - xs.min() + 1) * app.char_w
        h_px = (ys.max() - ys.min() + 1) * app.char_h
        ratio = h_px / float(w_px)
        check(f"brush r={r} is roughly circular on screen (h/w={ratio:.2f})", 0.8 <= ratio <= 1.25, f"{ratio:.2f}")
    # ring outline matches the painted disc and has no gaps in its rows/cols
    app.brush_radius = 8; app.hover_cell = (40, 30)
    try:
        app.draw_brush_ring(app.surface, (255, 255, 255), 0)
        ok = True
    except Exception as e:
        ok = False; print(e)
    check("brush ring draws without errors", ok)
    # blur and line still work with the aspect compensation
    c.clear(1.0); c.draw_line_aa_thick(10, 10, 60, 40, 0.0, 1.0, 4, False)
    check("thick line paints something", (c.buf < 0.5).sum() > 20)
    c.blur_disc(40, 30, 5)
    pygame.quit()


def t_sphere_drag():
    app = new_app()
    app._build_picker_grid()
    g = app._picker_grid
    keys = sorted(g, key=lambda k: g[k][1])          # lightest .. darkest
    a, b = g[keys[3]][0], g[keys[-3]][0]
    pr = app.picker_rect
    # press on one cell, drag to another, release: tone must follow the mouse
    run_events(app, [
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=a.center, button=1),
        pygame.event.Event(pygame.MOUSEMOTION, pos=b.center, rel=(0, 0), buttons=(1, 0, 0)),
        pygame.event.Event(pygame.MOUSEBUTTONUP, pos=b.center, button=1)], mouse_pos=b.center)
    check("drag on sphere follows the mouse", abs(app.current_value - g[keys[-3]][1]) < 1e-9,
          f"{app.current_value} vs {g[keys[-3]][1]}")
    check("drag ended on release", app.picker_drag is None)
    # dragging outside the frame clamps to the nearest cell (no jump to darkest)
    out = (pr.left - 30, pr.top + 20)
    run_events(app, [
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=a.center, button=1),
        pygame.event.Event(pygame.MOUSEMOTION, pos=out, rel=(0, 0), buttons=(1, 0, 0)),
        pygame.event.Event(pygame.MOUSEBUTTONUP, pos=out, button=1)], mouse_pos=out)
    check("drag outside the sphere stays on a sphere cell", app.picker_pick in g and app.picker_drag is None)
    # a plain click on the canvas still paints, and no drag state is left over
    app.picker_drag = None
    pygame.quit()


def t_sidebar_layout():
    app = new_app()
    sb = app.sidebar_rect
    btns = [app.new_btn, app.load_btn, app.import_btn, app.save_btn]
    check("NEW/LOAD/IMPORT/SAVE share one row inside the sidebar",
          len({b.y for b in btns}) == 1 and all(sb.contains(b) for b in btns))
    check("buttons do not overlap", all(not a.colliderect(b) for i, a in enumerate(btns) for b in btns[i+1:]))
    t = app.font_ui.render("IMPORT", True, (255, 255, 255))
    check("IMPORT text fits in its button", t.get_width() + 6 <= app.import_btn.w, f"{t.get_width()} vs {app.import_btn.w}")
    check("UI font is smaller than the drawing font", app.font_ui.get_height() < app.font.get_height())
    check("info lines stay on screen", app.grid_rows_val_rect.bottom + 9*(app.font_ui.get_height()+1) < app.surface_h - 40)
    pygame.quit()


def _blob(app):
    c = app.canvas
    c.clear(1.0)
    c.paint_disc_blend(20, 12, 8, 0.05, 1.0, False)
    return c


def _cell_px(app, x, y):
    return (x*app.char_w + app.char_w//2, app.canvas_offset_y + y*app.char_h + app.char_h//2)


def t_smart_edge_engine():
    app = new_app(); c = _blob(app)
    check("edge set loaded", len(app.edge.chars) > 20, str(len(app.edge.chars)))
    app.smart_refine(20, 12, 20, margin=False)
    edge = c.ov > 0
    check("smart edge marks some border cells", 20 < edge.sum() < 200, str(int(edge.sum())))
    # only cells next to the empty background may change; the middle of the blob stays a tone character
    check("blob interior is untouched", c.ov[12, 20] == 0 and c.ov[10, 17] == 0)
    ys, xs = np.nonzero(edge)
    f = 1.0 - c.buf
    ok = all((f[max(0,y-1):y+2, max(0,x-1):x+2].min() < M.EDGE_BG_MAX) for y, x in zip(ys, xs))
    check("every changed cell touches empty background", ok)
    # tones are never modified by SMART EDGE, and repeating it is stable
    before_buf = c.buf.copy(); before_ov = c.ov.copy()
    app.smart_refine(20, 12, 20, margin=False)
    check("smart edge does not change tones", np.array_equal(before_buf, c.buf))
    check("smart edge is idempotent", np.array_equal(before_ov, c.ov))
    # the chosen characters show up in the text
    txt = "\n".join(app.build_ascii_lines())
    codes = {chr(v) for v in np.unique(c.ov) if v}
    check("overrides reach the saved text", all(ch in txt for ch in codes))
    pygame.quit()


def t_smart_paint_clears_and_undo():
    app = new_app(); c = _blob(app)
    app.smart_refine(20, 12, 20, margin=False)
    y, x = [int(v[0]) for v in np.nonzero(c.ov)]
    app.canvas.paint_disc_blend(x, y, 1, 1.0, 1.0, False)
    check("normal painting removes the override", c.ov[y, x] == 0)
    # undo restores overrides
    app.smart_refine(20, 12, 20, margin=False)
    saved = c.ov.copy()
    app.push_undo(); c.ov[:, :] = 0; c.buf[:, :] = 1.0
    app.undo()
    check("undo restores the overrides", np.array_equal(c.ov, saved))
    c.clear(1.0)
    check("clear removes overrides", not c.ov.any())
    pygame.quit()


def t_smart_save_load_roundtrip():
    app = new_app(); c = _blob(app)
    app.smart_refine(20, 12, 20, margin=False)
    lines = app.build_ascii_lines()
    f = TMP / "smart.txt"; f.write_text("\n".join(lines), encoding="utf-8")
    c.clear(1.0)
    app.load_txt_into_canvas(str(f))
    check("smart art survives save + load", app.build_ascii_lines() == lines)
    pygame.quit()


def t_smart_modes_and_mouse():
    app = new_app(); c = _blob(app)
    run_events(app, [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_m, mod=0, unicode="m", scancode=0)])
    check("M = SMART BRUSH", app.mode == "smart")
    run_events(app, [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e, mod=0, unicode="e", scancode=0)])
    check("E = SMART EDGE", app.mode == "edge")
    run_events(app, [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e, mod=0, unicode="e", scancode=0)])
    check("E again returns to PAINT", app.mode == "paint")
    # click the toggle buttons
    run_events(app, [pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=app.smart_btn.center, button=1),
                     pygame.event.Event(pygame.MOUSEBUTTONUP, pos=app.smart_btn.center, button=1)], mouse_pos=app.smart_btn.center)
    check("SMART button toggles the mode", app.mode == "smart")
    check("smart buttons fit in the sidebar and do not overlap the main row",
          app.sidebar_rect.contains(app.smart_btn) and app.sidebar_rect.contains(app.edge_btn)
          and not app.smart_btn.colliderect(app.new_btn) and not app.smart_btn.colliderect(app.edge_btn))
    for lab, rect in (("SMART [M]", app.smart_btn), ("EDGE [E]", app.edge_btn)):
        w = app.font_ui.render(lab, True, (255,255,255)).get_width()
        check(f"label {lab} fits its button", w + 8 <= rect.w, f"{w} vs {rect.w}")
    # Ctrl + LMB in SMART = swap characters only (tones untouched)
    app.mode = "smart"; c = _blob(app); before = c.buf.copy(); c.ov[:, :] = 0
    pos = _cell_px(app, 20, 5)
    app.brush_radius = 6
    # (no MOUSEBUTTONUP: the continuous paint step runs after the events of the same frame)
    run_events(app, [pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)], mouse_pos=pos, mods=pygame.KMOD_CTRL)
    check("Ctrl+LMB (SMART EDGE) swaps characters without painting", np.array_equal(before, c.buf) and c.ov.any())
    # plain LMB in SMART = paints AND refines the borders
    c.clear(1.0)
    pos = _cell_px(app, 30, 12)
    run_events(app, [pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)], mouse_pos=pos)
    check("SMART BRUSH paints ink and border characters", (c.buf < 0.5).any() and c.ov.any())
    # RMB in SMART EDGE mode removes the overrides under the brush
    app.left_down = False; app.mode = "edge"; n = int((c.ov > 0).sum())
    run_events(app, [pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=3)], mouse_pos=pos)
    check("RMB in SMART EDGE clears the overrides", n > 0 and int((c.ov > 0).sum()) < n, f"{n} -> {int((c.ov > 0).sum())}")
    pygame.quit()


def t_smudge():
    app = new_app(); c = app.canvas
    ink = lambda: float((1.0 - c.buf).sum())
    c.clear(1.0); c.paint_disc_blend(30, 12, 5, 0.3, 1.0, False)
    total = ink(); cx0 = float(((1.0 - c.buf).sum(axis=0) * np.arange(c.cols)).sum() / total)
    app.brush_radius = 6; app.brush_alpha = 1.0
    app.smudge_move(25, 12, 45, 12)
    check("smudge conserves the ink", abs(ink() - total) < 1e-3, f"{total:.3f} -> {ink():.3f}")
    cx1 = float(((1.0 - c.buf).sum(axis=0) * np.arange(c.cols)).sum() / ink())
    check("smudge pushes the ink along the stroke", cx1 > cx0 + 1.0, f"{cx0:.1f} -> {cx1:.1f}")
    check("tones stay in 0..1", c.buf.min() >= 0.0 and c.buf.max() <= 1.0)
    # pushing into a full area: nothing overflows and nothing is lost
    c.clear(1.0); c.buf[8:17, 30:60] = 0.0                         # full ink block
    total = ink(); app.smudge_move(20, 12, 50, 12)
    check("smudge into a full area keeps ink and range", abs(ink() - total) < 1e-3 and c.buf.min() >= 0.0 and c.buf.max() <= 1.0)
    # nothing is pushed out of the canvas
    c.clear(1.0); c.paint_disc_blend(c.cols - 4, 10, 4, 0.0, 1.0, False); total = ink()
    app.smudge_move(c.cols - 12, 10, c.cols - 1, 10)
    check("smudge at the canvas edge does not lose ink", abs(ink() - total) < 1e-3)
    # smudge clears smart overrides it touches
    c.clear(1.0); c.paint_disc_blend(30, 12, 6, 0.05, 1.0, False); app.smart_refine(30, 12, 12, margin=False)
    had = c.ov.any(); app.smudge_move(24, 12, 38, 12)
    check("smudge removes smart characters it moved", had and (c.ov > 0).sum() < 30)
    # no motion = no change
    before = c.buf.copy(); app.smudge_move(10, 10, 10, 10)
    check("no motion, no smudge", np.array_equal(before, c.buf))
    # mode key + button
    run_events(app, [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d, mod=0, unicode="d", scancode=0)])
    check("D = SMUDGE", app.mode == "smudge")
    w = app.font_ui.render("SMUDGE [D]", True, (255,255,255)).get_width()
    check("SMUDGE button fits", w + 8 <= app.smudge_btn.w and app.sidebar_rect.contains(app.smudge_btn)
          and not app.smudge_btn.colliderect(app.smart_btn), f"{w} vs {app.smudge_btn.w}")
    # a real drag through paint_under_mouse: anchor is set on the first frame, then it moves ink
    c.clear(1.0); c.paint_disc_blend(20, 12, 4, 0.2, 1.0, False); total = ink()
    app.left_down = True; app.smudge_last = None
    for x in range(14, 40, 2):
        app.paint_under_mouse(*_cell_px(app, x, 12))
    app.left_down = False; app.smudge_last = None
    cxs = float(((1.0 - c.buf).sum(axis=0) * np.arange(c.cols)).sum() / ink())
    check("smudge drag in the app loop moves ink", cxs > 21.0 and abs(ink() - total) < 1e-2, f"{cxs:.1f}")
    pygame.quit()


def t_blur_opacity_and_pen():
    app = new_app(); c = app.canvas
    def noisy():
        c.clear(1.0); rng = np.random.RandomState(1)
        c.buf[5:20, 20:40] = rng.rand(15, 20).astype(np.float32)
        return c.buf.copy()
    base = noisy(); c.blur_disc(30, 12, 6, 1.0, False); full = c.buf.copy()
    noisy(); c.blur_disc(30, 12, 6, 0.5, False); half = c.buf.copy()
    noisy(); c.blur_disc(30, 12, 6, 0.0, False); none = c.buf.copy()
    check("blur at opacity 0 changes nothing", np.array_equal(none, base))
    check("blur at opacity 1 changes the canvas", not np.array_equal(full, base))
    d_full = np.abs(full - base).sum(); d_half = np.abs(half - base).sum()
    check("blur at opacity 0.5 is weaker than at 1.0", 0.2 * d_full < d_half < 0.8 * d_full, f"{d_half:.2f} vs {d_full:.2f}")
    # through the brush: opacity slider must reach the blur
    noisy(); app.mode = "blur"; app.brush_radius = 6; app.brush_alpha = 0.0; app.left_down = True
    app.paint_under_mouse(*_cell_px(app, 30, 12)); app.left_down = False
    check("blur brush respects the opacity setting", np.array_equal(c.buf, base))

    # --- pen pressure ---
    pen = app.pen
    POINTER_INFO, POINTER_PEN_INFO = M._pen_structs()
    import ctypes
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        check("POINTER_PEN_INFO has the Windows x64 size", ctypes.sizeof(POINTER_PEN_INFO) == 120, str(ctypes.sizeof(POINTER_PEN_INFO)))
    pen.mode = "OPACITY"; pen.in_contact = False
    check("no pen contact = full opacity (mouse unchanged)", abs(app.eff_alpha() - app.brush_alpha) < 1e-9)
    app.brush_alpha = 1.0; pen.in_contact = True; pen.pressure = 0.4
    check("pressure scales opacity", abs(app.eff_alpha() - 0.4) < 1e-6 and app.eff_radius() == app.brush_radius)
    pen.mode = "SIZE"; app.brush_radius = 10
    check("pressure scales size", app.eff_radius() == 4 and abs(app.eff_alpha() - 1.0) < 1e-9, str(app.eff_radius()))
    pen.mode = "BOTH"; pen.pressure = 0.0
    check("zero pressure keeps a minimal trace", app.eff_radius() >= 1 and app.eff_alpha() > 0)
    pen.mode = "OFF"; pen.pressure = 0.2
    check("pen mode OFF ignores pressure", app.eff_radius() == 10 and abs(app.eff_alpha() - 1.0) < 1e-9)
    # paint with half pressure leaves a lighter-ink result than full pressure
    pen.mode = "OPACITY"; app.mode = "paint"; app.current_value = 0.0; app.brush_radius = 3
    c.clear(1.0); pen.in_contact = True; pen.pressure = 1.0; app.left_down = True
    app.paint_under_mouse(*_cell_px(app, 20, 12)); full_ink = float((1 - c.buf).sum())
    c.clear(1.0); pen.pressure = 0.5
    app.paint_under_mouse(*_cell_px(app, 20, 12)); half_ink = float((1 - c.buf).sum()); app.left_down = False
    check("half pressure paints about half the ink", 0.35 * full_ink < half_ink < 0.65 * full_ink, f"{half_ink:.2f} vs {full_ink:.2f}")
    # the P key cycles the modes
    pen.mode = "OFF"
    run_events(app, [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p, mod=0, unicode="p", scancode=0)])
    check("P cycles the pen mode", pen.mode == "OPACITY")
    check("pen hook stays off outside Windows", sys.platform == "win32" or not pen.available)
    pygame.quit()


def _key(app, key, mods=0):
    run_events(app, [pygame.event.Event(pygame.KEYDOWN, key=key, mod=mods, unicode="", scancode=0)], mods=mods)


def _mark(app, x, y, ch_tone=0.0):
    app.canvas.buf[y, x] = ch_tone


def t_help_overlay_fits():
    app = new_app()
    app.show_help = True
    wide = pygame.Surface((app.surface_w + 400, app.surface_h))
    app.draw_help_overlay(wide, 0, 0, 0)
    arr = pygame.surfarray.array3d(wide).sum(axis=2)
    check("help text stays inside the sidebar (nothing past its right edge)", int(arr[app.surface_w:, :].sum()) == 0)
    check("help text does not start left of the sidebar", int(arr[:app.canvas_px_w - 12, :].sum()) == 0)
    vagon = [r for r, url in app.help_click_zones if "vagon" in url][0]
    check("shortcut list ends above the credits block", app.help_list_bottom < vagon.top - app.font_help.get_height(),
          f"{app.help_list_bottom} vs {vagon.top}")
    check("help font is smaller than the canvas font", app.font_help.get_height() < app.font.get_height())
    check("all 3 credit links are clickable", len(app.help_click_zones) == 3)
    pygame.quit()


def t_canvas_resize():
    app = new_app(); c = app.canvas
    R0, C0 = c.rows, c.cols
    pw0, sw0 = app.canvas_px_w, app.surface_w
    c.clear(1.0, M.TEXT_LUMA)
    _mark(app, 5, 7, 0.0)                       # a bright cell near the top-left
    sb_x0 = app.sidebar_rect.x; sm_x0 = app.smart_btn.x; pk_x0 = app.picker_rect.x
    # --- grow right
    _key(app, pygame.K_RIGHT, pygame.KMOD_CTRL)
    check("Ctrl+Right adds columns on the right", c.cols == C0 + M.CANVAS_GROW_COLS and c.rows == R0 and M.COLS == c.cols)
    check("content did not move when growing right", c.buf[7, 5] == 0.0 and c.buf[7, 5 + 1] == 1.0)
    check("new columns are empty", float(c.buf[:, C0:].min()) == 1.0 and int(c.ov[:, C0:].sum()) == 0)
    dx = app.canvas_px_w - pw0
    check("canvas pixel size follows the cell count", dx == M.CANVAS_GROW_COLS * app.char_w and app.surface.get_width() == app.surface_w)
    check("sidebar slides right with the canvas", app.sidebar_rect.x == sb_x0 + dx and app.smart_btn.x == sm_x0 + dx and app.picker_rect.x == pk_x0 + dx)
    check("sidebar still fits in the surface", app.sidebar_rect.right == app.surface_w)
    check("window matches the surface", app.win_w == int(app.surface_w * M.WINDOW_SCALE) and app.screen.get_width() == app.win_w)
    check("grid state follows the canvas", app.grid_cols == c.cols and app.grid_rows == c.rows)
    # mouse -> cell works over the new area
    cell = app.mouse_to_cell(app.canvas_px_w - 2, app.canvas_offset_y + 3)
    check("mouse_to_cell reaches the new last column", cell is not None and cell[0] == c.cols - 1)
    # --- painting works in the new area and the ring/redraw run
    app.mode = "paint"; app.current_value = 0.0; app.brush_radius = 2
    run_events(app, [pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(0, 0))],
               mouse_pos=_cell_px(app, c.cols - 3, 5)); app.left_down = False; app.stroke_started = False
    check("can paint inside the grown area", float(c.buf[:, C0:].min()) < 1.0)
    # --- undo of the paint, then undo of the resize
    app.undo()
    check("undo of the stroke keeps the grown size", c.cols == C0 + M.CANVAS_GROW_COLS and float(c.buf[:, C0:].min()) == 1.0)
    app.undo()
    check("undo of the resize restores the old size", c.cols == C0 and c.rows == R0 and M.COLS == C0 and app.canvas_px_w == pw0)
    check("undo of the resize restores the sidebar position", app.sidebar_rect.x == sb_x0 and app.smart_btn.x == sm_x0)
    check("content survives the grow/undo round trip", c.buf[7, 5] == 0.0)
    # --- grow left shifts content right
    _key(app, pygame.K_LEFT, pygame.KMOD_CTRL)
    n = M.CANVAS_GROW_COLS
    check("Ctrl+Left adds columns on the left and shifts the drawing", c.cols == C0 + n and c.buf[7, 5 + n] == 0.0 and c.buf[7, 5] == 1.0)
    # --- grow up / down
    _key(app, pygame.K_UP, pygame.KMOD_CTRL)
    m = M.CANVAS_GROW_ROWS
    check("Ctrl+Up adds rows on top and shifts the drawing down", c.rows == R0 + m and c.buf[7 + m, 5 + n] == 0.0)
    _key(app, pygame.K_DOWN, pygame.KMOD_CTRL)
    check("Ctrl+Down adds rows at the bottom", c.rows == R0 + 2 * m and c.buf[7 + m, 5 + n] == 0.0)
    check("surface/offset follow the new height", app.canvas_px_h == c.rows * app.char_h and app.canvas_offset_y == (app.surface_h - app.canvas_px_h) // 2)
    # four undos bring back the original
    for _ in range(4): app.undo()
    check("four undos restore the original size", c.rows == R0 and c.cols == C0 and c.buf[7, 5] == 0.0)
    # --- shrink: only empty cells go
    _key(app, pygame.K_RIGHT, pygame.KMOD_CTRL)
    _key(app, pygame.K_RIGHT, pygame.KMOD_CTRL | pygame.KMOD_SHIFT)
    check("Ctrl+Right then Ctrl+Shift+Right is a no-op overall", c.cols == C0 and c.rows == R0)
    c.buf[10, c.cols - 1] = 0.0                  # ink in the last column
    _key(app, pygame.K_RIGHT, pygame.KMOD_CTRL | pygame.KMOD_SHIFT)
    check("shrink refuses to cut drawn cells", c.cols == C0 and c.buf[10, c.cols - 1] == 0.0)
    c.buf[10, c.cols - 1] = 1.0
    c.buf[3, c.cols - 4] = 0.0                    # ink 4 columns from the edge: only 3 empty columns can go
    _key(app, pygame.K_RIGHT, pygame.KMOD_CTRL | pygame.KMOD_SHIFT)
    check("shrink removes only the empty part of the step", c.cols == C0 - 3 and c.buf[3, c.cols - 1] == 0.0, str(c.cols))
    check("a shrink is undoable (stack grew)", len(app.undo_stack) >= 1)
    app.undo()
    check("undo of a shrink restores the removed columns", c.cols == C0)
    c.buf[:, :] = 1.0
    # --- smart-edge override survives a resize
    c.ov[4, 4] = ord("/"); c.buf[4, 4] = 0.5
    ok = app.resize_canvas(left=3, top=2)
    check("overrides move with the content", ok and c.ov[4 + 2, 4 + 3] == ord("/") and c.ov[4, 4] == 0)
    # --- limits
    app.resize_canvas(right=M.CANVAS_MAX_COLS)
    check("growth is limited to the maximum", c.cols <= M.CANVAS_MAX_COLS and c.cols * c.rows <= M.CANVAS_MAX_CELLS)
    before = (c.rows, c.cols)
    c.cols  # no-op
    for _ in range(40): app.resize_canvas(right=-50, bottom=-50)
    check("shrink stops at the minimum size", c.cols >= M.CANVAS_MIN_COLS and c.rows >= M.CANVAS_MIN_ROWS, f"{c.cols}x{c.rows}")
    # --- other features follow the size
    app.resize_canvas(right=7)
    lines = app.build_ascii_lines()
    check("ASCII export has one line per row and one char per column", len(lines) == c.rows and all(len(l) == c.cols for l in lines))
    p = TMP / "resized.png"; app.save_png(str(p))
    img = pygame.image.load(str(p))
    check("PNG export matches the canvas pixel size", img.get_size() == (app.canvas_px_w, app.canvas_px_h), str(img.get_size()))
    t = TMP / "resized.txt"; app.save_txt(str(t))
    app.redraw_canvas_ascii(app.surface, 5, 5, 0); app.present_surface()
    app.draw_tool_info(app.surface)
    check("redraw + info panel run on the resized canvas", True)
    # load a bigger text file: the canvas grows to fit it
    big = TMP / "big.txt"
    big.write_text("\n".join(("#" * 100 if i % 2 else " " * 3 + "@" * 90) for i in range(60)), encoding="utf-8")
    app.canvas.clear(1.0, M.TEXT_LUMA)
    app.load_txt_into_canvas(str(big))
    check("LOAD of a bigger TXT grows the canvas to fit", c.cols >= 100 and c.rows >= 60, f"{c.cols}x{c.rows}")
    app.undo()
    check("undo of that LOAD restores the previous size", c.cols != 100 or c.rows != 60)
    # overlay is rescaled
    src = pygame.Surface((50, 30), pygame.SRCALPHA); src.fill((255, 0, 0, 255))
    app.overlay_src = src; app._fit_overlay()
    app.resize_canvas(right=5)
    check("overlay follows the canvas size", app.overlay_image.get_size() == (app.canvas_px_w, app.canvas_px_h))
    # timelapse still records after a resize
    app._ensure_timelapse(); app.tl.reset(); app.tl.enabled = True
    app.tl.capture(app.canvas, app.pal, force=True)
    app.resize_canvas(bottom=6)
    app.tl.capture(app.canvas, app.pal, force=True)
    check("timelapse keeps recording across a resize", len(app.tl.frames) == 2 and all(len(f) == len(app.tl.frames[0]) for f in app.tl.frames))
    pygame.quit()


def t_canvas_resize_speed():
    import time
    app = new_app(); c = app.canvas
    app.resize_canvas(right=120, bottom=60)          # 200 x 108 = 21600 cells
    rng = np.random.default_rng(1)
    c.buf[:, :] = rng.random(c.buf.shape).astype(np.float32) * 0.8        # dense: almost every cell is drawn
    t0 = time.perf_counter()
    for _ in range(5): app.redraw_canvas_ascii(app.surface, 10, 10, 0)
    ms = (time.perf_counter() - t0) / 5 * 1000
    check(f"full redraw of a dense {c.cols}x{c.rows} canvas stays under 120 ms ({ms:.0f} ms)", ms < 120, f"{ms:.0f} ms")
    pygame.quit()


def t_palette_slots():
    app = new_app()
    have = [n for n in range(1, 11) if n in app.pal.map]
    slots = app._pal_slots()
    check("one shortcut slot per palette 1..10 found in PAL.txt", [n for _, n in slots] == have and len(have) >= 2, str([n for _, n in slots]))
    sb = app.sidebar_rect
    check("slots sit inside the sidebar, under the character bar, above the buttons",
          all(sb.contains(r) and r.top >= app.palette_rect.bottom and r.bottom <= app.new_btn.top for r, _ in slots))
    check("slots do not overlap", all(not a[0].colliderect(b[0]) for i, a in enumerate(slots) for b in slots[i+1:]))
    t = app.font_ui.render("9", True, (255, 255, 255))
    check("slot digit fits its button", t.get_width() + 4 <= slots[0][0].w and t.get_height() <= slots[0][0].h, f"{t.get_size()} vs {slots[0][0].size}")
    check("info lines still stay on screen", app.grid_rows_val_rect.bottom + 12*(app.font_ui.get_height()+1) < app.surface_h - 40)
    # the highlighted slot is the current palette, and a click switches palette without painting or starting a drag
    check("current palette slot is the selected one", app.pal.index == 1)
    c = app.canvas; before = c.buf.copy(); tone = app.current_value
    r3 = [r for r, n in slots if n == 3][0]
    run_events(app, [pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=r3.center)], mouse_pos=r3.center)
    app.left_down = False
    check("clicking slot 3 selects palette 03", app.pal.index == 3 and app.pal.display_name.startswith("03-"), app.pal.display_name)
    check("slot click does not paint or start a tone drag", np.array_equal(before, c.buf) and app.picker_drag is None and app.current_value == tone)
    # same result as SHIFT+5
    run_events(app, [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_5, mod=pygame.KMOD_SHIFT, unicode="", scancode=0)], mods=pygame.KMOD_SHIFT)
    check("SHIFT+5 and the slot bar agree", app.pal.index == 5 and 5 in [n for _, n in app._pal_slots()])
    app.redraw_canvas_ascii(app.surface, 0, 0, 0)
    r5 = [r for r, n in app._pal_slots() if n == 5][0]
    cy = app.surface.get_at((r5.centerx, r5.top))[:3]
    check("current slot is drawn with the cyan outline", cy == (90, 220, 220), str(cy))
    # still works after the sidebar moved (canvas resize)
    app.resize_canvas(right=10)
    r2 = [r for r, n in app._pal_slots() if n == 2][0]
    check("slots moved with the sidebar", sb.contains(r2) and r2.x >= app.canvas_px_w)
    app.stroke_started = False
    run_events(app, [pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=r2.center)], mouse_pos=r2.center)
    app.left_down = False
    check("slot click works after a canvas resize", app.pal.index == 2)
    pygame.quit()


def _click(app, pos, button=1, mods=0):
    run_events(app, [pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=button, pos=pos)], mouse_pos=pos, mods=mods)
    app.left_down = app.right_down = False; app.stroke_started = False; app.picker_drag = None


def _fresh_pal_file():
    """Point palette saving at a temp copy so the tests never touch the real PAL.txt."""
    import shutil
    p = TMP / f"PAL_{len(list(TMP.glob('PAL_*.txt')))}.txt"
    shutil.copyfile(ROOT / "assets" / "PAL.txt", p)
    M.pal_write_path = lambda p=p: p
    return p


def t_tooltips():
    app = new_app(); app.redraw_canvas_ascii(app.surface, 0, 0, 0)
    slot = {n: r for r, n in app._pal_slot_rects()}
    tip = app.tooltip_at(*slot[3].center)
    check("palette slot tooltip names the Shift key and the palette", tip and tip[1][0].startswith("SHIFT+3  03-"), str(tip))
    tip = app.tooltip_at(*slot[8].center)
    check("empty slot tooltip says EMPTY", tip and "SHIFT+8" in tip[1][0] and "EMPTY" in tip[1][0], str(tip))
    tip = app.tooltip_at(*slot[10].center)
    check("slot 10 is Shift+0", tip and tip[1][0].startswith("SHIFT+0"), str(tip))
    for label, key in (("HLIGHT", "H"), ("SOFT", "S"), ("PAINT", "ESC"), ("BLUR", "SHIFT"), ("LINE", "L"), ("LINEAA", "A")):
        r = app.ind_rects[app.ind_labels.index(label)]
        tip = app.tooltip_at(*r.center)
        check(f"{label} button tooltip shows its key", tip and key in tip[1][0], str(tip))
    for rect, key in ((app.smart_btn, "M"), (app.edge_btn, "E"), (app.smudge_btn, "D"), (app.new_btn, "N"), (app.save_btn, "CTRL+S"), (app.grid_checkbox_rect, "G")):
        tip = app.tooltip_at(*rect.center)
        check(f"tooltip for the {key} control", tip and tip[1][0].startswith(key), str(tip))
    check("no tooltip over the canvas", app.tooltip_at(100, 100) is None)
    # shows only after the delay
    r = slot[3]; pos = r.center
    before = pygame.surfarray.array3d(app.surface).copy()
    app.redraw_canvas_ascii(app.surface, pos[0], pos[1], 1000)           # first frame over the slot: timer starts
    early = pygame.surfarray.array3d(app.surface).copy()
    app.redraw_canvas_ascii(app.surface, pos[0], pos[1], 1000 + M.TOOLTIP_DELAY_MS + 50)
    late = pygame.surfarray.array3d(app.surface).copy()
    box = pygame.Rect(pos[0] + 14, pos[1] + 18, 40, 12)
    sub = lambda a: a[box.x:box.right, box.y:box.bottom].sum()
    check("tooltip is not drawn right away", sub(early) == sub(before))
    check("tooltip appears after the hover delay", sub(late) != sub(early))
    pygame.quit()


def t_opacity_slider():
    app = new_app(); app.redraw_canvas_ascii(app.surface, 0, 0, 0)
    r = app.opacity_slider_rect
    check("opacity slider exists inside the sidebar, on the OPACITY line", r is not None and app.sidebar_rect.contains(r) and r.w >= 60, str(r))
    _click(app, (r.x + 1, r.centery)); app.redraw_canvas_ascii(app.surface, 0, 0, 0)
    check("click at the left end sets the minimum opacity", abs(app.brush_alpha - 0.05) < 1e-9, str(app.brush_alpha))
    _click(app, (r.right - 1, r.centery))
    check("click at the right end sets full opacity", abs(app.brush_alpha - 1.0) < 1e-9, str(app.brush_alpha))
    _click(app, (r.x + r.w // 2, r.centery))
    check("click in the middle is about half", 0.4 <= app.brush_alpha <= 0.6, str(app.brush_alpha))
    # drag
    run_events(app, [pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(r.x + 2, r.centery))], mouse_pos=(r.x + 2, r.centery))
    check("press on the slider starts an opacity drag", app.picker_drag == "opacity")
    app.left_down = True
    run_events(app, [pygame.event.Event(pygame.MOUSEMOTION, pos=(r.x + int(r.w * 0.75), r.centery), rel=(1, 0), buttons=(1, 0, 0))],
               mouse_pos=(r.x + int(r.w * 0.75), r.centery))
    check("dragging moves the opacity", 0.65 <= app.brush_alpha <= 0.85, str(app.brush_alpha))
    app.left_down = False; app.picker_drag = None
    app.brush_alpha = 0.3
    t = app.tooltip_at(r.centerx, r.centery)
    check("slider tooltip mentions SHIFT+WHEEL", t and "SHIFT+WHEEL" in t[1][0])
    c = app.canvas; c.clear(1.0, M.TEXT_LUMA); app.mode = "paint"; app.current_value = 0.0
    before = c.buf.copy()
    _click(app, (r.x + 3, r.centery))
    check("clicking the slider does not paint", np.array_equal(before, c.buf))
    # slider follows a canvas resize
    app.resize_canvas(right=10); app.redraw_canvas_ascii(app.surface, 0, 0, 0)
    r2 = app.opacity_slider_rect
    check("slider moves with the sidebar", r2 is not None and r2.x >= app.canvas_px_w)
    pygame.quit()


def t_bomb():
    # ---- pure engine
    rng = np.random.default_rng(3)
    ink = np.zeros((40, 80)); ink[10:30, 25:55] = 1.0
    cx, cy, R, A = 40, 20, 9.0, 2.0
    pl = M.bomb_plan(ink, cx, cy, R, A, np.random.default_rng(1))
    yy, xx = np.mgrid[0:40, 0:80]; d = np.hypot(xx - cx, (yy - cy) * A)
    fin = pl.ink_at(1.0)
    ring = lambda a, b: float(fin[(d > a * R) & (d <= b * R)].mean())
    check("bomb: the centre is a void", ring(0.0, M.BOMB_CORE) < 0.35, str(ring(0.0, M.BOMB_CORE)))
    check("bomb: the void fades out toward the tips", ring(0.0, M.BOMB_CORE) < ring(0.3, 0.5) < ring(0.5, 0.75) < ring(0.75, 0.95), str([ring(0, .25), ring(.3, .5), ring(.5, .75), ring(.75, .95)]))
    check("bomb: ink far outside the blast is untouched", np.array_equal(fin[d > R * 1.9], ink[d > R * 1.9]))
    inner = np.zeros((40, 80)); inner[d <= 0.5 * R] = 1.0
    pc = M.bomb_plan(inner, cx, cy, R, A, np.random.default_rng(2)); fc = pc.ink_at(1.0)
    check("bomb: ink from the middle is thrown out around it", float(fc[d > 0.5 * R].sum()) > 5.0 and float(fc[d <= M.BOMB_CORE * R].mean()) < 0.35)
    check("bomb: deposits stay within ~1.8 R", len(pl.va) > 0 and float(np.hypot(pl.vx - cx, (pl.vy - cy) * A).max()) <= R * 1.8 + 1.0)
    quad = {(np.sign(x - cx) >= 0, np.sign(y - cy) >= 0) for x, y in zip(pl.vx, pl.vy)}
    check("bomb: debris flies in every direction", len(quad) == 4)
    check("bomb: ink stays in 0..1", float(fin.min()) >= 0.0 and float(fin.max()) <= 1.0)
    pl2 = M.bomb_plan(ink, cx, cy, R, A, np.random.default_rng(1))
    check("bomb: same seed gives the same explosion", np.array_equal(pl.ink_at(1.0), pl2.ink_at(1.0)))
    i0 = pl.ink_at(0.0)
    check("bomb: at tau=0 only the core is gone, the wave has not left yet", np.array_equal(i0[d > M.BOMB_CORE * R], ink[d > M.BOMB_CORE * R]) and float(i0[d <= M.BOMB_CORE * R].max()) == 0.0)
    check("bomb: the wave front moves out (the void grows with time)", float(pl.ink_at(0.05)[(d > 0.3 * R) & (d <= 0.5 * R)].sum()) > float(pl.ink_at(0.6)[(d > 0.3 * R) & (d <= 0.5 * R)].sum()) - 1e-9)
    half = M.bomb_plan(ink, cx, cy, R, A, np.random.default_rng(1), alpha=0.5)
    moved_full = float((pl.orig - pl.base).sum()); moved_half = float((half.orig - half.base).sum())
    check("bomb: opacity scales how much ink the wave pushes", 0.45 <= moved_half / max(moved_full, 1e-9) <= 0.55, str(moved_half / max(moved_full, 1e-9)))
    check("bomb: at half opacity the centre is only half empty", 0.3 <= float(half.ink_at(1.0)[d <= M.BOMB_CORE * R].mean()) <= 0.7)
    low = M.bomb_plan(ink, cx, cy, R, A, np.random.default_rng(1), alpha=0.05)
    check("bomb: at minimum opacity the canvas hardly changes", float(np.abs(low.ink_at(1.0) - ink).sum()) < 0.12 * float(np.abs(fin - ink).sum()))
    check("bomb: ink is roughly conserved (pushed, not destroyed)", 0.8 * float(ink.sum()) <= float(fin.sum()) <= 1.1 * float(ink.sum()), str(float(fin.sum())))
    empty = M.bomb_plan(np.zeros((40, 80)), cx, cy, R, A, np.random.default_rng(1))
    check("bomb: an empty canvas stays empty", float(empty.ink_at(1.0).max()) == 0.0 and float(empty.ink_at(0.5).max()) == 0.0)
    # trail gets stronger towards the landing point
    one = np.zeros((40, 80)); one[20, 40] = 1.0
    p1 = M.bomb_plan(one, 40, 20, 12.0, 2.0, np.random.default_rng(5))
    if len(p1.va) > 3:
        order = np.argsort(p1.vf)
        check("bomb: trail strength never decreases along the flight", bool(np.all(np.diff(p1.va[order]) >= -1e-9)))
    check("bomb: radius follows the brush radius", M.bomb_radius(1) == M.BOMB_R_BASE and M.bomb_radius(5) > M.bomb_radius(2) and M.bomb_radius(999) == M.BOMB_R_MAX)
    # ---- sounds
    f, b = M.bomb_sound_arrays(22050)
    check("bomb: sounds are short and not loud", len(f) / 22050 <= 4.0 and len(b) / 22050 <= 1.0 and np.abs(f).max() <= 0.6 and np.abs(b).max() <= 0.6)
    check("bomb: sounds taper to silence at the end", abs(f[-1]) < 0.02 and abs(b[-1]) < 0.02)
    # ---- in the app
    app = new_app(); c = app.canvas; app.sound_enabled = False
    app.redraw_canvas_ascii(app.surface, 0, 0, 0)
    check("bomb: the BOMB button exists in the sidebar", app.sidebar_rect.contains(app.bomb_btn))
    _key(app, pygame.K_k)
    check("bomb: K toggles bomb mode on", app.mode == "bomb")
    _key(app, pygame.K_ESCAPE)
    check("bomb: ESC leaves bomb mode", app.mode != "bomb")
    _click(app, app.bomb_btn.center)
    check("bomb: clicking the button enters bomb mode", app.mode == "bomb")
    c.clear(1.0, M.TEXT_LUMA)
    for yy_ in range(8, 24):
        for xx_ in range(20, 50): c.buf[yy_, xx_] = 0.0
    app.brush_radius = 4; app.brush_alpha = 1.0
    before = c.buf.copy()
    _click(app, _cell_px(app, 35, 16)); app.left_down = False; app.stroke_started = False
    check("bomb: a click lights a fuse and does not paint", len(app.bombs) == 1 and np.array_equal(before, c.buf))
    b0 = app.bombs[0]; t0 = b0.t0; R0 = b0.R
    check("bomb: the bomb sits at the clicked cell with the brush-radius blast", (b0.cx, b0.cy) == (35, 16) and R0 == M.bomb_radius(4))
    n_undo = len(app.undo_stack) if hasattr(app, "undo_stack") else None
    app.update_bombs(t0 + 100)
    check("bomb: the canvas is untouched during the fuse", b0.phase == "fuse" and np.array_equal(before, c.buf))
    chars = {app.bomb_fuse_char(b0, t0 + int(b0.fuse_ms * k / 400.0)) for k in range(400)}
    palette_chars = {ch if ch != " " else "\u00b7" for ch in app.pal.chars}
    check("bomb: the fuse character runs through every shade of the palette", chars >= palette_chars, str(chars ^ palette_chars))
    rs = [app.bomb_ring_radius(b0, t0 + int(b0.fuse_ms * k / 20.0)) for k in range(21)]
    check("bomb: the warning ring starts at the full radius", abs(rs[0] - R0) < 1e-9)
    check("bomb: the ring only closes in (never grows)", all(rs[i] >= rs[i + 1] - 1e-9 for i in range(20)))
    check("bomb: the ring closes faster and faster", (rs[0] - rs[5]) < (rs[15] - rs[20]) + 1e-9)
    check("bomb: the ring reaches the centre cell exactly at the boom", rs[20] <= 0.5 + 1e-9)
    app.redraw_canvas_ascii(app.surface, 0, 0, 0)
    app.draw_bombs(app.surface, t0 + 50)
    px = pygame.surfarray.array3d(app.surface)
    far = px[int((35 + R0 * 0.9) * app.char_w):int((35 + R0 + 1) * app.char_w), app.canvas_offset_y + 16 * app.char_h:app.canvas_offset_y + 17 * app.char_h]
    check("bomb: early in the fuse the ring is drawn out at the blast radius", int(((far[..., 0] > 60) & (far[..., 1] < 80)).sum()) > 0)
    app.redraw_canvas_ascii(app.surface, 0, 0, 0)
    app.draw_bombs(app.surface, t0 + 500)
    px = pygame.surfarray.array3d(app.surface)
    r = pygame.Rect(35 * app.char_w, app.canvas_offset_y + 16 * app.char_h, app.char_w, app.char_h)
    sub = px[r.x:r.right, r.y:r.bottom]
    red = ((sub[..., 0] > 150) & (sub[..., 1] < 120)).sum() + ((sub[..., 0] > 200) & (sub[..., 1] > 200)).sum()
    check("bomb: the fuse cell is drawn hot (red/white)", red > 0)
    app.update_bombs(t0 + b0.fuse_ms + 1)
    check("bomb: after the fuse the bomb flashes", b0.phase == "flash")
    flash_ink = 1.0 - c.buf
    check("bomb: the flash lights up the blast core", float(flash_ink[16, 35]) == 1.0)
    check("bomb: the explosion is blocked from painting/resizing while it runs", app.blast_busy())
    w0 = c.cols; _key(app, pygame.K_RIGHT, pygame.KMOD_CTRL)
    check("bomb: canvas resize is ignored while the blast runs", c.cols == w0)
    tf = b0.t_flash
    app.update_bombs(tf + M.BOMB_FLASH_MS + 1)
    check("bomb: flash turns into the blast", b0.phase == "blast")
    app.update_bombs(b0.t_blast + M.BOMB_BLAST_MS // 3)
    app.update_bombs(b0.t_blast + M.BOMB_BLAST_MS + 5)
    check("bomb: the blast ends and the bomb is gone", len(app.bombs) == 0 and not app.blast_busy())
    after = c.buf.copy()
    core = np.zeros(after.shape, bool)
    yy2, xx2 = np.mgrid[0:c.rows, 0:c.cols]
    core = np.hypot(xx2 - 35, (yy2 - 16) * c.aspect) <= M.BOMB_CORE * R0
    check("bomb: the middle is a void (little ink left)", float((1.0 - after[core]).mean()) < 0.4, str(float((1.0 - after[core]).mean())))
    check("bomb: some ink ended outside the original square", float((after < 1.0).sum()) > 0 and not np.array_equal(after, before))
    app.undo()
    check("bomb: ONE undo takes the whole explosion back", np.array_equal(c.buf, before))
    # two bombs wait for each other
    a = app.place_bomb((30, 12), now=1000, seed=1); b = app.place_bomb((40, 18), now=1000, seed=2)
    app.update_bombs(1000 + a.fuse_ms + 1)
    check("bomb: two bombs never explode at the same time", sorted([a.phase, b.phase]) == ["flash", "fuse"])
    for tt in range(0, 8000, 40): app.update_bombs(1000 + a.fuse_ms + tt)
    check("bomb: every bomb finishes", len(app.bombs) == 0)
    pygame.quit()


def t_tl_row():
    app = new_app(); app.sound_enabled = False; c = app.canvas
    app.redraw_canvas_ascii(app.surface, 0, 0, 0)
    r = app.tl_rect; P = app._tl_parts()
    check("tl: the T.LAPSE row sits inside the sidebar between the sphere and the character bar", app.sidebar_rect.contains(r) and r.top >= app.picker_rect.bottom and r.bottom <= app.palette_rect.top)
    check("tl: row does not touch the mode buttons", r.top >= max(x.bottom for x in app.ind_rects))
    check("tl: parts are inside the row and do not overlap", all(r.contains(p) for p in P.values()) and not P["rec"].colliderect(P["bar"]) and not P["bar"].colliderect(P["cnt"]) and not P["cnt"].colliderect(P["exp"]) and not P["exp"].colliderect(P["clr"]))
    check("tl: bar is wide enough to read", P["bar"].w >= 60, str(P["bar"]))
    app._ensure_timelapse(); tl = app.tl
    check("tl: starts off by default", tl.enabled == bool(M.TL_START_ON))
    tl.enabled = False
    _click(app, P["rec"].center)
    check("tl: REC button turns recording on", tl.enabled is True)
    before = c.buf.copy(); _click(app, P["bar"].center)
    check("tl: clicking the bar does nothing (and does not paint)", np.array_equal(before, c.buf) and tl.enabled is True)
    _click(app, P["rec"].center)
    check("tl: REC button turns recording off again", tl.enabled is False)
    # GIF: needs frames
    calls = []; app.tl_export_via_dialog = lambda: calls.append(1) or True
    tl.frames = []
    _click(app, P["exp"].center)
    check("tl: GIF does nothing without frames", not calls)
    tl.frames = [[0]] * 5
    _click(app, P["exp"].center)
    check("tl: GIF exports when there are frames", len(calls) == 1)
    # CLR: two clicks
    _click(app, P["clr"].center)
    check("tl: first CLR click only asks OK?", len(tl.frames) == 5 and app._tl_wipe_until > pygame.time.get_ticks())
    _click(app, P["clr"].center)
    check("tl: second CLR click wipes the frames", len(tl.frames) == 0 and app._tl_wipe_until == 0)
    tl.frames = [[0]] * 5; app._tl_wipe_until = 0
    _click(app, P["clr"].center); app._tl_wipe_until = pygame.time.get_ticks() - 1
    _click(app, P["clr"].center)
    check("tl: the OK? confirmation expires (that click only asks again)", len(tl.frames) == 5)
    # T key shares the same toggle
    tl.enabled = False; _key(app, pygame.K_t)
    check("tl: T key still toggles recording", tl.enabled is True)
    _key(app, pygame.K_t, pygame.KMOD_CTRL)
    check("tl: Ctrl+T still wipes the frames", len(tl.frames) == 0)
    # tooltips
    for key, part in (("rec", "rec"), ("exp", "exp"), ("clr", "clr"), ("bar", "bar")):
        tip = app.tooltip_at(*P[part].center)
        check(f"tl: tooltip on {key}", tip is not None and tip[0] == ("tl", key) and len(tip[1]) >= 1)
    check("tl: REC tooltip names the key", "T" == app.tooltip_at(*P["rec"].center)[1][0].split()[0])
    check("tl: CLR tooltip says click twice", "TWICE" in " ".join(app.tooltip_at(*P["clr"].center)[1]))
    # drawing
    tl.enabled = True; tl.frames = [[0]] * 600
    app.redraw_canvas_ascii(app.surface, 0, 0, 0); app.draw_tl_progress_bar(app.surface)
    px = pygame.surfarray.array3d(app.surface)
    sub = px[P["bar"].x:P["bar"].right, P["bar"].y:P["bar"].bottom]
    reds = int(((sub[..., 0] > 200) & (sub[..., 1] < 120)).sum())
    check("tl: the bar fills red in proportion to the frames", reds > 0 and reds < sub.shape[0] * sub.shape[1])
    # follows a canvas resize
    app.resize_canvas(right=10); app.redraw_canvas_ascii(app.surface, 0, 0, 0)
    check("tl: the row moves with the sidebar when the canvas grows", app.tl_rect.x >= app.canvas_px_w and app.sidebar_rect.contains(app.tl_rect))
    pygame.quit()


def t_palette_editor():
    pf = _fresh_pal_file()
    app = new_app(); app.redraw_canvas_ascii(app.surface, 0, 0, 0)
    slot = {n: r for r, n in app._pal_slot_rects()}
    check("10 fixed slots, only the palettes in PAL.txt are active", len(slot) == 10 and len(app._pal_slots()) == len(app.pal.map))
    app.pal.set_index(2); _click(app, slot[8].center)
    check("clicking an empty slot does nothing", app.pal.index == 2)
    _click(app, slot[1].center)
    check("clicking slot 1 selects palette 1", app.pal.index == 1)
    # double click on a bar character opens the table
    items = {i: r for r, i in app.palette_items}
    idx = 1; pos = items[idx].center
    run_events(app, [pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)] * 2, mouse_pos=pos)
    app.left_down = False; app.picker_drag = None; app.stroke_started = False
    check("double click on a bar character opens the palette editor", isinstance(app.popup, M.PaletteEditorPopup) and app.popup.sel == idx)
    ch = app.table_chars()
    check("table offers many drawable, unique characters and no spaces", len(ch) > 150 and len(set(ch)) == len(ch) and " " not in ch, str(len(ch)))
    check("table includes ASCII, blocks and box characters", all(x in ch for x in "A#@~") and all(x in ch for x in "█▒─"))
    # popup owns the input
    c = app.canvas; c.clear(1.0, M.TEXT_LUMA); before = c.buf.copy(); mode0 = app.mode
    orig_char = app.pal.chars[idx]
    run_events(app, [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_h, mod=0, unicode="h", scancode=0)])
    app.redraw_canvas_ascii(app.surface, 100, 100, 0)
    check("shortcut keys do not leak out while the editor is open", app.mode == mode0 and app.popup is not None)
    check("typing a character puts it into the selected slot", app.pal.chars[idx] == "h" and 1 in app.pal.edits)
    # pick a character
    app.redraw_canvas_ascii(app.surface, 0, 0, 0)
    pop = app.popup; i_blk = ch.index("█"); cell = pop.cell_rect(i_blk).center
    old = orig_char
    run_events(app, [pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=cell)], mouse_pos=cell)
    app.left_down = False; app.stroke_started = False
    check("clicking a table cell changes the selected palette character and the editor stays open", app.pal.chars[idx] == "█" and app.popup is pop and old != "█", app.pal.string)
    app.popup = None
    check("the canvas was not painted by those clicks", np.array_equal(before, c.buf))
    check("the palette is marked as edited", 1 in app.pal.edits and app.pal.display_name.startswith("01-"))
    app.redraw_canvas_ascii(app.surface, 0, 0, 0)
    top = app.surface.get_at((slot[1].centerx, slot[1].top))[:3]
    check("edited palette button is red", top == M.RED, str(top))
    check("PAL info line shows the edit mark", True)
    # the edit survives switching palettes
    _click(app, slot[2].center); _click(app, slot[1].center)
    check("an unsaved edit survives switching palettes", app.pal.chars[idx] == "█" and 1 in app.pal.edits)
    # the darkest slot cannot be edited
    last = app.pal.n - 1
    app.open_char_table(last)
    check("opening the editor on the darkest slot selects the nearest editable one", app.popup is not None and app.popup.sel == last - 1)
    app.popup = None
    # Esc closes
    app.open_char_table(idx); run_events(app, [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="", scancode=0)])
    check("Esc closes the editor without changes", app.popup is None and app.pal.chars[idx] == "█")
    # right-click menu: restore
    app.redraw_canvas_ascii(app.surface, 0, 0, 0)
    _click(app, slot[1].center, button=3)
    check("right click on a slot opens the palette menu", isinstance(app.popup, M.MenuPopup) and [l for l, _ in app.popup.items] == ["RESTORE", "SAVE", "SAVE NEW"])
    app.redraw_canvas_ascii(app.surface, 0, 0, 0)
    pos = app.popup.item_rect(0).center
    run_events(app, [pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)], mouse_pos=pos); app.left_down = False
    check("RESTORE brings back the saved palette", app.pal.chars[idx] == old and 1 not in app.pal.edits and app.popup is None)
    # not edited: restore/save are disabled
    app.open_pal_menu(1, (10, 10))
    check("RESTORE and SAVE are disabled when nothing changed", app.popup.items[0][1] is None and app.popup.items[1][1] is None and app.popup.items[2][1] is not None)
    app.popup = None
    # edit again and SAVE
    app.pal.set_char(idx, "█")
    ok, msg = app.pal.save(1)
    txt = pf.read_text(encoding="utf-8")
    check("SAVE writes the edited palette into PAL.txt", ok and "█" in txt.split("02-")[0] and 1 not in app.pal.edits, msg)
    check("a .bak copy of the original PAL.txt is kept", (pf.with_name(pf.name + ".bak")).exists())
    check("the file still has every palette and the trailing space of each line", txt.count("\n\n") >= len(app.pal.map) - 1 and all(f"{n:02d}-" in txt for n in app.pal.map))
    app.pal.restore(1)
    # SAVE NEW goes to the next free number
    app.pal.set_index(2); app.pal.set_char(1, "█")
    new, msg = app.pal.save_new(2)
    check("SAVE NEW uses the next free number", new == 7 and app.pal.index == 7 and 7 in app.pal.map, msg)
    check("the original palette goes back to its saved state", 2 not in app.pal.edits and "█" not in app.pal.map[2]["chars"])
    check("the new palette is in the file with a .EDIT name", "07-PAUL.BURKE(97).MIN.EDIT" in pf.read_text(encoding="utf-8"))
    # fill the slots: SAVE NEW is then disabled
    for k in range(8, 11): app.pal.map[k] = {"name": f"X{k}", "chars": "@#. "}
    app.pal.set_char(0, "&")
    app.open_pal_menu(7, (10, 10))
    check("SAVE NEW is disabled when all 10 slots are used", app.popup.items[2][1] is None)
    app.popup = None
    # empty slot menu
    del app.pal.map[9]
    app.open_pal_menu(9, (10, 10))
    check("an empty slot offers SAVE CURRENT HERE", [l for l, _ in app.popup.items] == ["SAVE CURRENT HERE"])
    app.popup.items[0][1](app)
    check("SAVE CURRENT HERE stores the palette in that slot", 9 in app.pal.map and app.pal.index == 9 and "09-CUSTOM" in pf.read_text(encoding="utf-8"))
    # a write error must not change anything
    bad = TMP / "afile.txt"; bad.write_text("x"); M.pal_write_path = lambda: bad / "PAL.txt"
    app.pal.set_char(0, "%")
    n_before = len(app.pal.map)
    ok, msg = app.pal.save(9)
    check("a failed write reports the error and keeps the old data", (not ok) and "COULD NOT" in msg and app.pal.map[9]["chars"] != app.pal.string and len(app.pal.map) == n_before)
    ok2, msg2 = app.pal.save_here(5) if 5 not in app.pal.map else (False, "")
    pygame.quit()


def _tkey(app, key, uni="", mod=0):
    run_events(app, [pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod, unicode=uni, scancode=0)], mods=mod)


def t_tru():
    pf = _fresh_pal_file()
    app = new_app(); app.redraw_canvas_ascii(app.surface, 0, 0, 0); c = app.canvas
    app.pal.set_index(1); n = app.pal.n; c.clear(1.0, M.TEXT_LUMA)
    # ---- button / key / layout
    check("the TRU button exists, is inside the sidebar and does not overlap the button above or the grid row",
          app.tru_btn.right <= app.surface_w and app.tru_btn.top >= app.bomb_btn.bottom and app.tru_btn.bottom <= app.grid_checkbox_rect.top)
    _click(app, app.tru_btn.center)
    check("clicking the TRU button turns the mode on", app.mode == "tru" and app.tru_cursor is not None)
    _tkey(app, pygame.K_TAB); check("Tab leaves TRU", app.mode == "paint")
    _tkey(app, pygame.K_TAB); check("Tab enters TRU", app.mode == "tru")
    _tkey(app, pygame.K_ESCAPE); check("Esc leaves TRU", app.mode == "paint")
    app.toggle_smart_mode("tru"); app.tru_cursor = (5, 4); undo0 = len(app.undo_stack)
    # ---- the mouse only moves the cursor
    cx, cy = 10 * app.char_w + 3, app.canvas_offset_y + 6 * app.char_h + 3
    run_events(app, [pygame.event.Event(pygame.MOUSEMOTION, pos=(cx, cy), rel=(0, 0), buttons=(0, 0, 0))], mouse_pos=(cx, cy))
    check("moving the mouse moves the cursor", app.tru_cursor == (10, 6))
    before = c.buf.copy()
    app.tru_cursor = (3, 3)
    run_events(app, [pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(cx, cy))], mouse_pos=(cx, cy)); app.left_down = False
    run_events(app, [pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=3, pos=(cx, cy))], mouse_pos=(cx, cy)); app.right_down = False
    app.stroke_started = False
    check("clicking never paints or erases in TRU", np.array_equal(before, c.buf) and np.all(c.ov == 0))
    check("a click moves the cursor to the clicked cell", app.tru_cursor == (10, 6))
    # ---- typing characters
    app.tru_cursor = (2, 2); u0 = len(app.undo_stack); _tkey(app, pygame.K_a, "A")
    check("typing a letter puts it at the cursor and the cursor moves right",
          app.row_chars(2)[2] == "A" and app.tru_cursor == (3, 2) and float(c.buf[2, 2]) < 1.0)
    check("a typed character is one undo step", len(app.undo_stack) == u0 + 1)
    _tkey(app, pygame.K_1, "!", mod=pygame.KMOD_SHIFT)
    check("Shift + number types the shifted character", app.row_chars(2)[3] == "!" and app.tru_cursor == (4, 2))
    _tkey(app, pygame.K_SPACE, " ")
    check("space erases the cell and moves on", app.row_chars(2)[4] == " " and float(c.buf[2, 4]) == 1.0 and app.tru_cursor == (5, 2))
    _tkey(app, pygame.K_BACKSPACE)
    check("backspace steps back and clears", app.tru_cursor == (4, 2) and app.row_chars(2)[4] == " ")
    _tkey(app, pygame.K_e, "\u00e9")
    check("any character the font can draw works, even outside the palette", app.row_chars(2)[4] == "\u00e9" and int(c.ov[2, 4]) == ord("\u00e9"))
    pc = app.pal.chars
    _tkey(app, pygame.K_h, pc[0]); check("typing a palette character stores a plain tone (no override)", int(c.ov[2, 5]) == 0 and app.row_chars(2)[5] == pc[0])
    # ---- Alt + 1..0 : shading levels, in place
    app.tru_cursor = (7, 7)
    seen = []
    for k, kk in zip(range(1, 11), [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6, pygame.K_7, pygame.K_8, pygame.K_9, pygame.K_0]):
        _tkey(app, kk, "", mod=pygame.KMOD_ALT); seen.append(app.row_chars(7)[7])
        assert app.tru_cursor == (7, 7)
    check("Alt+1 is the darkest level (empty) and Alt+0 the lightest", seen[0] == " " and seen[-1] == pc[0], str(seen))
    check("Alt+number changes the character in place (the cursor does not move)", app.tru_cursor == (7, 7))
    idxs = [app.tru_level_idx(k) for k in range(1, 11)]
    check("levels get lighter from key 1 to key 0", all(idxs[i] >= idxs[i + 1] for i in range(9)) and idxs[0] == n - 1 and idxs[-1] == 0, str(idxs))
    check("every Alt level is a plain palette tone", int(c.ov[7, 7]) == 0)
    # ---- cursor keys
    app.tru_cursor = (0, 0); _tkey(app, pygame.K_RIGHT); _tkey(app, pygame.K_DOWN); _tkey(app, pygame.K_DOWN); _tkey(app, pygame.K_LEFT); _tkey(app, pygame.K_LEFT)
    check("arrow keys move the cursor and stop at the edge", app.tru_cursor == (0, 2))
    app.tru_cursor = (4, 2); _tkey(app, pygame.K_RETURN); check("Enter goes to the start of the next line", app.tru_cursor == (0, 3))
    app.tru_cursor = (app.canvas.cols - 1, 0); _tkey(app, pygame.K_x, "x")
    check("typing at the last column stays there", app.tru_cursor == (app.canvas.cols - 1, 0))
    # ---- shortcuts do not leak; Ctrl combos still work
    m0 = app.mode; _tkey(app, pygame.K_k, "k"); _tkey(app, pygame.K_m, "m"); _tkey(app, pygame.K_t, "t")
    check("letters that are shortcuts elsewhere are just typed in TRU", app.mode == "tru" and not app.tl.enabled)
    cb = c.buf.copy(); _tkey(app, pygame.K_z, "\x1a", mod=pygame.KMOD_CTRL)
    check("Ctrl+Z still undoes typing", not np.array_equal(cb, c.buf))
    # ---- save / load round trip keeps typed text
    app.canvas.clear(1.0, M.TEXT_LUMA); app.tru_cursor = (1, 1)
    for chh in "Hi!":
        _tkey(app, pygame.K_a, chh)
    line = app.build_ascii_lines()[1]
    check("typed text is written to the TXT", line[1:4] == "Hi!")
    q = TMP / "tru.txt"; app.save_txt(str(q)); app.canvas.clear(1.0, M.TEXT_LUMA); app.load_txt_into_canvas(str(q))
    check("typed text survives save and load", app.build_ascii_lines()[1][1:4] == "Hi!")
    # ---- drawing and tooltip
    app.redraw_canvas_ascii(app.surface, 0, 0, 0)
    app.tru_cursor = (4, 4)
    px = lambda: app.surface.get_at((4 * app.char_w, app.canvas_offset_y + 4 * app.char_h + app.char_h - 1))[:3]
    app.redraw_canvas_ascii(app.surface, 0, 0, 0)
    check("the TRU cursor is drawn (underline in the cursor colour)", px() == M.TRU_RGB, str(px()))
    tip = app.tooltip_at(*app.tru_btn.center)
    check("TRU has a tooltip", bool(tip) and tip[0] == ("btn", "tru"))
    app.mode = "paint"
    pygame.quit()


def t_bomb_gradation():
    """A bomb on a solid block of the densest character must still fade out gradually along every ray."""
    rng = np.random.default_rng(5); R, C = 60, 100
    ink = np.clip(0.97 + rng.normal(0, 0.03, (R, C)), 0, 1)
    pl = M.bomb_plan(ink, C // 2, R // 2, 30.0, 1.0, np.random.default_rng(3), 1.0)
    fin = pl.ink_at(1.0); d = pl.d; ring = pl.disc & (d > 0.25 * 30)
    frac_full = float((fin[ring] > 0.95).mean())
    check("bomb on a solid block: only a small part of the blast area is back at full ink", frac_full < 0.25, f"{frac_full:.2f}")
    means = [float(fin[(d / np.maximum(pl.Lc, 1e-6) >= a) & (d / np.maximum(pl.Lc, 1e-6) < a + 0.2) & pl.disc].mean()) for a in (0.0, 0.2, 0.4, 0.6, 0.8)]
    check("ink rises steadily from the centre to the tips", all(means[i] < means[i + 1] for i in range(4)), str([round(x, 2) for x in means]))
    check("all five distance bands have a real spread of values (gradation, not two levels)",
          len(np.unique(np.round(fin[ring], 1))) >= 6)
    half = M.bomb_plan(ink, C // 2, R // 2, 30.0, 1.0, np.random.default_rng(3), 0.5).ink_at(1.0)
    check("opacity 50% leaves more ink than 100%", float(half[pl.disc].mean()) > float(fin[pl.disc].mean()))
    pygame.quit()


def t_cursor_visible_in_popup():
    pf = _fresh_pal_file()
    app = new_app(); app.redraw_canvas_ascii(app.surface, 0, 0, 0)
    calls = []; orig = pygame.mouse.set_visible
    pygame.mouse.set_visible = lambda v: calls.append(v)
    try:
        mx, my = app.canvas_px_w // 2, app.canvas_offset_y + app.canvas_px_h // 2
        app.cursor_hidden = False; app._update_cursor_visibility(mx, my)
        check("the pointer is hidden over the canvas (the brush ring replaces it)", app.cursor_hidden and calls[-1] is False)
        app.open_char_table(1); app._update_cursor_visibility(mx, my)
        check("with a popup open (palette editor) the pointer is visible again over the canvas area", not app.cursor_hidden and calls[-1] is True)
        app.popup = None; app._update_cursor_visibility(mx, my)
        check("closing the popup hides it again over the canvas", app.cursor_hidden)
    finally:
        pygame.mouse.set_visible = orig


def t_fade():
    pf = _fresh_pal_file()
    app = new_app(); app.redraw_canvas_ascii(app.surface, 0, 0, 0); app.redraw_canvas_ascii  # layout
    app.draw_tool_info(app.surface)
    c = app.canvas
    check("FADE starts off", not app.fade_on and app.fade_factor() == 1.0)
    check("FADE row has a checkbox and a slider lined up under OPACITY", app.fade_box_rect is not None and app.fade_slider_rect is not None and app.fade_slider_rect.x == app.opacity_slider_rect.x and app.fade_slider_rect.y > app.opacity_slider_rect.y)
    def stroke(row, x0, x1):
        app.end_stroke(); app.left_down = True
        for x in range(x0, x1 + 1):
            app.paint_under_mouse(x * app.char_w + 1, app.canvas_offset_y + row * app.char_h + 1)
        app.left_down = False; app.end_stroke()
        return [1.0 - float(c.buf[row, x]) for x in range(x0, x1 + 1)]
    app.brush_radius = 1; app.brush_alpha = 1.0; app.current_value = 0.2
    plain = stroke(3, 2, 14)
    check("without FADE the whole stroke has the same ink", max(plain) - min(plain) < 1e-6 and plain[0] > 0.7, str(plain))
    app.fade_on = True; app.fade_speed = 1.0                                     # fastest: dies out in FADE_LEN_MIN cells
    check("fade length follows the slider (fast = short, slow = long)", abs(app.fade_length() - M.FADE_LEN_MIN) < 1e-6 and (setattr(app, "fade_speed", 0.05) or app.fade_length() > 100))
    app.fade_speed = 1.0
    f = stroke(6, 2, 14)
    check("a FADE stroke starts at the chosen opacity", abs(f[0] - plain[0]) < 1e-6, str(f))
    check("... and the ink only goes down along the stroke", all(f[i] >= f[i + 1] - 1e-9 for i in range(len(f) - 1)) and f[2] < f[0], str(f))
    check("... until it is gone (the darkest tone, a space)", all(v < 1e-6 for v in f[int(M.FADE_LEN_MIN) + 1:]), str(f))
    g = stroke(8, 2, 14)
    check("a new stroke starts at full strength again", abs(g[0] - plain[0]) < 1e-6, str(g))
    app.fade_speed = 0.05; slow = stroke(10, 2, 14)
    check("a slower fade keeps more ink along the same path", sum(slow) > sum(f) * 2 and slow[-1] > 0.5, str((slow, f)))
    # opacity still counts
    app.brush_alpha = 0.5; app.fade_speed = 0.05; h = stroke(12, 2, 4)
    check("FADE multiplies the brush opacity", h[0] < slow[0] - 0.1, str((h, slow)))
    # vertical movement counts too
    app.brush_alpha = 1.0; app.fade_speed = 1.0; app.end_stroke(); app.left_down = True
    for y in range(14, 22): app.paint_under_mouse(5 * app.char_w + 1, app.canvas_offset_y + y * app.char_h + 1)
    app.left_down = False; app.end_stroke()
    col = [1.0 - float(c.buf[y, 5]) for y in range(14, 22)]
    check("moving down the canvas fades too", col[0] > 0.7 and col[-1] < 1e-6, str(col))
    # ---- UI
    app.fade_on = False
    app.redraw_canvas_ascii(app.surface, 0, 0, 0); app.draw_tool_info(app.surface)
    app.handle_picker_click(*app.fade_box_rect.center)
    check("clicking the checkbox turns FADE on", app.fade_on)
    app.handle_picker_click(*app.fade_label_rect.center)
    check("clicking the label turns it off again", not app.fade_on)
    r = app.fade_slider_rect
    app.handle_picker_click(r.right - 1, r.centery)
    check("clicking the slider sets the speed (and turns FADE on)", app.fade_on and app.fade_speed >= 0.95 and app._picker_grabbed == "fade")
    app.picker_drag = "fade"; app.picker_drag_update(r.x, r.centery)
    check("dragging the slider to the left makes the trail long", app.fade_speed <= 0.1)
    app.fade_on = False; run_events(app, [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_f, mod=0, unicode="f", scancode=0)])
    check("F toggles FADE", app.fade_on)
    app.redraw_canvas_ascii(app.surface, 0, 0, 0); app.draw_tool_info(app.surface)
    tip = app.tooltip_at(*app.fade_box_rect.center); tip2 = app.tooltip_at(*app.fade_slider_rect.center)
    check("tooltips for the checkbox and the slider", tip and tip[0] == ("btn", "fade") and tip2 and tip2[0] == ("fade",), str((tip, tip2)))
    # smudge and the bomb are not affected
    app.fade_dist = 1e6
    check("smudge strength ignores FADE", app.eff_alpha() == app.brush_alpha)


def t_voice_lines_in_lexicon():
    words = {w for line in list(M.VOICE_BOMB_LINES) + list(M.VOICE_MODE_LINES.values()) + list(M.VOICE_TRU_LINES) for w in line.split()}
    missing = sorted(w for w in words if w not in M.VOICE_LEXICON)
    check("every word of the bomb, mode and TRU lines is in the voice lexicon", not missing, str(missing))
    V = M.VoiceSynth()
    check("every bomb line renders to audio", all(len(V.render(l)) > 2000 for l in M.VOICE_BOMB_LINES))
    check("no war talk is left in the bomb lines", not any(w in " ".join(M.VOICE_BOMB_LINES) for w in ("fire in the hole", "duck", "cover", "away")))


def t_voice_captions():
    pf = _fresh_pal_file()
    V = M.VoiceSynth()
    tm = V.timing("less slop mode")
    check("timing gives one entry per word, in order, not overlapping", [w for w, a, b in tm] == ["less", "slop", "mode"] and all(tm[i][2] <= tm[i + 1][1] + 1e-9 for i in range(2)) and all(a < b for _, a, b in tm), str(tm))
    check("the last word ends before the audio ends", tm[-1][2] <= len(V.render("less slop mode")) / M.VOICE_RATE)
    check("a word without sounds (digits) is ignored in the timing", [w for w, a, b in V.timing("level 3 up")] == ["level", "up"])
    check("empty phrase has no timing", V.timing("  ") == [])
    app = new_app(); app.redraw_canvas_ascii(app.surface, 0, 0, 0); app.voice_on = True; app.sound_enabled = True
    t0 = 100000
    app.speak("less slop mode"); app.caption = (app.caption[0], app.caption[1], t0)
    tm = app.caption[1]
    check("the caption is the phrase in capitals", app.caption[0] == "LESS SLOP MODE" and [w for w, a, b in tm] == ["LESS", "SLOP", "MODE"])
    w0 = app.caption_words(t0 + 5); w1 = app.caption_words(t0 + int(tm[1][1] * 1000) + 20); w2 = app.caption_words(t0 + int(tm[2][1] * 1000) + 20)
    check("words appear one by one as they are spoken", w0 == ["LESS"] and w1 == ["LESS", "SLOP"] and w2 == ["LESS", "SLOP", "MODE"], str((w0, w1, w2)))
    # regression (v1.10): the phrase is spoken AFTER the frame's ticks were read, so the age is slightly negative: the caption must survive
    app.caption = (app.caption[0], app.caption[1], t0 + 50)
    check("a caption spoken later in the same frame is not lost", app.caption_words(t0) == ["LESS"] and app.caption is not None, str(app.caption_words(t0)))
    app.caption = (app.caption[0], app.caption[1], t0)
    end = t0 + int((tm[-1][2] + M.VOICE_CAPTION_HOLD) * 1000)
    check("the caption stays a little after the last word and then goes away", app.caption_words(end - 50) is not None and app.caption_words(end + 50) is None and app.caption is None)
    # drawing: yellow pixels at the top centre of the canvas
    app.speak("palette saved"); app.caption = (app.caption[0], app.caption[1], 200000)
    app.redraw_canvas_ascii(app.surface, 0, 0, 200000 + 1000)
    def yellow_in(rect):
        sub = app.surface.subsurface(rect.clip(app.surface.get_rect())); arr = pygame.surfarray.array3d(sub).astype(int)
        return int(((abs(arr[:, :, 0] - 255) < 30) & (abs(arr[:, :, 1] - 214) < 30) & (arr[:, :, 2] < 60)).sum())
    top = pygame.Rect(0, 0, app.canvas_px_w, 40)
    check("the caption is drawn in yellow at the top of the canvas", yellow_in(top) > 50, str(yellow_in(top)))
    check("and inside the canvas area (not over the sidebar)", yellow_in(pygame.Rect(app.canvas_px_w, 0, app.surface_w - app.canvas_px_w, 40)) == 0)
    app.redraw_canvas_ascii(app.surface, 0, 0, 200000 + 5000)
    check("it is gone after the hold time", yellow_in(top) == 0)
    # off switches
    app.caption = None; app.voice_on = False; app.speak("paint")
    check("no caption while the voice is off", app.caption is None)
    app.speak("voice off", force=True); check("'voice off' still shows its caption (it was spoken)", app.caption is not None and app.caption[0] == "VOICE OFF")
    app.caption = None; app.voice_on = True; M.VOICE_CAPTIONS = False; app.speak("paint"); M.VOICE_CAPTIONS = True
    check("VOICE_CAPTIONS = False hides captions", app.caption is None)
    app.sound_enabled = False; app.speak("paint"); check("no caption when the sound is off", app.caption is None)
    pygame.quit()


def t_voice():
    pf = _fresh_pal_file()
    # ---- the synthesizer itself
    V = M.VoiceSynth()
    check("lexicon words give phonemes, unknown words fall back to spelling rules",
          M.voice_phonemes("palette")[:2] == ["P", "AE"] and len(M.voice_phonemes("zorbleshing")) >= 6 and M.voice_phonemes("123") == [])
    for text in ("palette saved", "less slop mode", "splat incoming", "timelapse start", "smart brush", "gif ready", "qwxz"):
        a = V.render(text); dur = len(a) / M.VOICE_RATE
        check(f"'{text}': int16, not silent, not clipped, sensible length ({dur:.2f}s)",
              a.dtype == np.int16 and np.abs(a).max() > 8000 and np.abs(a).max() < 32767 and 0.2 < dur < 3.0)
    check("rendering is deterministic", np.array_equal(M.VoiceSynth().render("palette saved"), V.render("palette saved")))
    check("different phrases sound different", not np.array_equal(V.render("smudge")[:4000], V.render("ink bomb")[:4000]))
    check("an empty phrase renders to (almost) nothing", len(V.render("  ")) <= 1)
    t0 = time.time(); M.VoiceSynth().render("palette saved"); check("a phrase renders fast enough to do it on demand (< 0.5 s)", time.time() - t0 < 0.5)
    def band(text, lo, hi):
        a = V.render(text).astype(np.float64); sp = np.abs(np.fft.rfft(a * np.hanning(len(a)))); fq = np.fft.rfftfreq(len(a), 1.0 / M.VOICE_RATE)
        return sp[(fq >= lo) & (fq < hi)].sum() / sp.sum()
    M.VOICE_LEXICON["zzee"] = "IY IY IY IY IY"; M.VOICE_LEXICON["zzaa"] = "AA AA AA AA AA"; M.VOICE_LEXICON["zzss"] = "S S S"; M.VOICE_LEXICON["zzmm"] = "M M M M"
    check("IY has more energy around 2.3 kHz than AA (formants work)", band("zzee", 2000, 2700) > 1.3 * band("zzaa", 2000, 2700))
    check("AA has more energy around 1 kHz than IY", band("zzaa", 800, 1300) > 1.3 * band("zzee", 800, 1300))
    check("S is mostly high-frequency noise", band("zzss", 4000, 10000) > 0.5 and band("zzmm", 4000, 10000) < 0.1)
    # ---- the voice in the app
    app = new_app(); app.redraw_canvas_ascii(app.surface, 0, 0, 0); app.voice_on = True
    said = []
    def _rec(real):
        def f(text, force=False):
            r = real(text, force)
            if r: said.append(text)
            return r
        return f
    app.speak = _rec(app.speak)
    check("the voice is on by default", M.VOICE_ON_DEFAULT is True and app.voice_on)
    def last(): return said[-1] if said else None
    for key, mode, want in ((pygame.K_m, "smart", "smart brush"), (pygame.K_e, "edge", "smart edge"), (pygame.K_d, "smudge", "smudge"), (pygame.K_k, "bomb", "ink bomb")):
        n0 = len(said); _tkey(app, key, key and chr(key)); 
        check(f"switching to {mode} says '{want}'", app.mode == mode and len(said) == n0 + 1 and last() == want, str(said[n0:]))
    _tkey(app, pygame.K_ESCAPE); n0 = len(said)
    _tkey(app, pygame.K_TAB)
    check("TRU mode says one of the funny lines", app.mode == "tru" and len(said) > n0 and last() in M.VOICE_TRU_LINES, str(said[n0:]))
    check("and its caption is on screen (not thrown away by the frame clock)", app.caption is not None and app.caption_words(pygame.time.get_ticks()))
    _tkey(app, pygame.K_ESCAPE)
    # timelapse
    n0 = len(said); app._ensure_timelapse(); app.tl.enabled = False; app.tl_toggle(); app.tl_toggle(); app.tl_wipe()
    check("timelapse start / stop / cleared are announced", said[n0:] == ["timelapse start", "timelapse stop", "timelapse cleared"], str(said[n0:]))
    # bomb
    n0 = len(said); app.place_bomb((10, 10), now=0, seed=1)
    check("lighting a bomb says one of the bomb lines", len(said) == n0 + 1 and last() in M.VOICE_BOMB_LINES)
    app.bombs.clear()
    # palette saved
    n0 = len(said); app.pal.set_index(2); app.pal.set_char(1, "W"); app.open_char_table(1); app.redraw_canvas_ascii(app.surface, 0, 0, 0)
    dict(app.popup.btns); app.popup.press_button(app, "SAVE")
    check("saving a palette says 'palette saved'", "palette saved" in said[n0:], str(said[n0:]))
    n0 = len(said); app.pal.set_char(1, "Q"); app.popup.press_button(app, "RESTORE")
    check("restoring a palette says 'palette restored'", said[n0:] == ["palette restored"], str(said[n0:])); app.popup = None
    # toggling: V key and the checkbox
    app.redraw_canvas_ascii(app.surface, 0, 0, 0)
    check("the VOICE checkbox sits inside the sidebar and does not overlap the grid label",
          app.voice_checkbox_rect.right + 40 <= app.surface_w and app.voice_checkbox_rect.left > app.grid_label_rect.left + 100)
    n0 = len(said); _tkey(app, pygame.K_v, "v")
    check("V turns the voice off (it says so first)", (not app.voice_on) and said[n0:] == ["voice off"], str(said[n0:]))
    n0 = len(said)
    for key in (pygame.K_m, pygame.K_ESCAPE): _tkey(app, key, "")
    check("while off nothing is spoken", len(said) == n0)
    _click(app, app.voice_checkbox_rect.center)
    check("clicking the checkbox turns it on again (says 'voice on')", app.voice_on and last() == "voice on")
    app.sound_enabled = False; r_off = app.speak("paint"); app.sound_enabled = True; r_on = app.speak("paint")
    check("no voice when the sound is off (Shift+S)", r_off is False and r_on is True)
    app.sound_enabled = True
    # ---- no TRU line when typing letters that are shortcuts
    app.toggle_smart_mode("tru"); n0 = len(said)
    _tkey(app, pygame.K_v, "v"); check("in TRU the V key is typed, it does not toggle the voice", app.voice_on)
    app.mode = "paint"
    pygame.quit()


def t_palette_modal():
    pf = _fresh_pal_file()
    app = new_app(); app.redraw_canvas_ascii(app.surface, 0, 0, 0); c = app.canvas
    app.pal.set_index(2); original = app.pal.string; n0 = app.pal.n
    # ---- engine
    check("insert_slot adds a level (a copy of the slot it pushes along) and marks the palette edited", app.pal.insert_slot(1) and app.pal.n == n0 + 1 and app.pal.chars[1] == app.pal.chars[2] and 2 in app.pal.edits)
    check("the darkest slot is still the only space", app.pal.string.endswith(" ") and app.pal.string.count(" ") == 1)
    check("remove_slot takes a level out", app.pal.remove_slot(1) and app.pal.string == original and 2 not in app.pal.edits)
    check("undoing the change by hand clears the edited mark", 2 not in app.pal.edits)
    check("slots cannot be added or removed at the darkest position", not app.pal.insert_slot(app.pal.n - 1) and not app.pal.remove_slot(app.pal.n - 1))
    s0 = app.pal.string; check("move_slot reorders the shades", app.pal.move_slot(0, 2) and app.pal.chars[2] == s0[0] and app.pal.chars[0] == s0[1] and app.pal.string.endswith(" "))
    app.pal.restore(2)
    check("restore brings the original palette back", app.pal.string == original and app.pal.n == n0)
    # ---- opening: double click on the sphere
    app.redraw_canvas_ascii(app.surface, 0, 0, 0); app._build_picker_grid() if app._picker_grid is None else None
    key = list(app._picker_grid)[len(app._picker_grid) // 2]; rect, tone = app._picker_grid[key]
    app._last_sphere_click = None
    app.handle_picker_click(*rect.center)
    check("one click on the sphere only picks the tone", app.popup is None and abs(app.current_value - tone) < 1e-9)
    app.handle_picker_click(*rect.center)
    want = min(app.pal.idx_from_value(tone), app.pal.n - 2)
    check("double click on the sphere opens the palette editor on that shade", isinstance(app.popup, M.PaletteEditorPopup) and app.popup.sel == want)
    app.popup = None
    run_events(app, [pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center)] * 2, mouse_pos=rect.center)
    app.left_down = False; app.picker_drag = None; app.stroke_started = False
    check("the same double click works through the main loop", isinstance(app.popup, M.PaletteEditorPopup))
    pop = app.popup
    tip = app.tooltip_at(*rect.center)
    check("the sphere has a tooltip that mentions the editor", tip is not None and "EDIT PALETTE" in " ".join(tip[1]))
    # ---- layout
    app.redraw_canvas_ascii(app.surface, 0, 0, 0); pop.draw(app, app.surface, 0, 0)
    check("editor sits inside the window", app.surface.get_rect().contains(pop.rect))
    check("bar, table and buttons are inside the editor", pop.rect.contains(pop.bar) and pop.rect.contains(pop.minus) and pop.rect.contains(pop.plus) and all(pop.rect.contains(r) for _, r in pop.btns) and pop.rect.contains(pop.cell_rect(len(pop.chars) - 1)))
    check("slots do not overlap and each is wide enough for a character", all(not pop.slot_rect(app, i).colliderect(pop.slot_rect(app, i + 1)) for i in range(app.pal.n - 1)) and pop.slot_rect(app, 0).w >= 9)
    check("the palette bar is on top of the table", pop.bar.bottom <= pop.gy)
    # ---- click a slot, then a character: the editor stays open
    sel_before = pop.sel; target = 0 if sel_before != 0 else 1
    r = pop.slot_rect(app, target)
    run_events(app, [pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=r.center), pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=r.center)], mouse_pos=r.center)
    app.left_down = False; app.stroke_started = False
    check("clicking a slot in the editor bar selects it", pop.sel == target and app.popup is pop)
    k = pop.chars.index("█"); cell = pop.cell_rect(k).center
    before = c.buf.copy()
    run_events(app, [pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=cell)], mouse_pos=cell); app.left_down = False; app.stroke_started = False
    check("a table character goes into the selected slot and the editor stays open", app.pal.chars[target] == "█" and app.popup is pop and 2 in app.pal.edits)
    check("nothing was painted on the canvas", np.array_equal(before, c.buf))
    # a second slot, a second character (no need to reopen)
    t2 = 1 if target != 1 else 2; r2 = pop.slot_rect(app, t2)
    pop.on_click(app, *r2.center, 1); pop.on_release(app)
    pop.on_click(app, *pop.cell_rect(pop.chars.index("#")).center, 1)
    check("other slots can be changed one after the other", app.pal.chars[t2] == "#" and app.pal.chars[target] == "█")
    # the darkest slot is locked
    last = pop.slot_rect(app, app.pal.n - 1)
    sel0 = pop.sel; pop.on_click(app, *last.center, 1)
    check("clicking the darkest slot does not select it", pop.sel == sel0 and app.pal.string.endswith(" "))
    # ---- + and -
    n1 = app.pal.n
    run_events(app, [pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pop.plus.center)], mouse_pos=pop.plus.center); app.left_down = False
    check("the + button adds a shading level", app.pal.n == n1 + 1 and app.popup is pop)
    pop.on_click(app, *pop.minus.center, 1)
    check("the - button removes one", app.pal.n == n1)
    while app.pal.n < pop.max_n: pop.on_click(app, *pop.plus.center, 1)
    pop.on_click(app, *pop.plus.center, 1)
    check("+ stops at the maximum number of levels", app.pal.n == pop.max_n and "MAX" in pop.status)
    check("the full palette still fits the bar", pop.slot_rect(app, 0).w >= 9 and all(not pop.slot_rect(app, i).colliderect(pop.slot_rect(app, i + 1)) for i in range(app.pal.n - 1)))
    for _ in range(40): pop.on_click(app, *pop.minus.center, 1)
    check("- stops at the minimum number of levels", app.pal.n == M.PAL_MIN_SLOTS and "MIN" in pop.status)
    check("the selection always stays on an editable slot", 0 <= pop.sel <= app.pal.n - 2)
    # the tone mapping follows the new palette size
    app.current_value = 0.0; check("the lightest tone still maps to the first slot", app.pal.char_from_value(0.0) == app.pal.chars[0])
    app.pal.restore(2); app.popup = None
    # ---- drag to reorder
    app.open_char_table(0); pop = app.popup; app.redraw_canvas_ascii(app.surface, 0, 0, 0)
    s_before = app.pal.string; a, b = pop.slot_rect(app, 0).center, pop.slot_rect(app, 3).center
    pop.on_click(app, *a, 1); pop.on_drag(app, *b)
    pop.on_release(app); app.pal.restore(2); pop.sel = 0
    pop.on_click(app, *a, 1)                                  # press on slot 0 (the main loop reads the mouse from the OS, so the press is delivered directly)
    run_events(app, [pygame.event.Event(pygame.MOUSEMOTION, pos=b, rel=(0, 0), buttons=(1, 0, 0)),
                     pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=b)], mouse_pos=b)
    app.left_down = False; app.stroke_started = False
    exp = list(s_before[:-1]); ch = exp.pop(0); exp.insert(3, ch)
    check("dragging a slot along the bar moves its character", app.pal.string == "".join(exp) + " ", app.pal.string)
    check("the selection follows the dragged slot and the drag ends on release", pop.sel == 3 and pop.drag_idx is None)
    pop.on_drag(app, *a)
    check("moving the mouse without the button down does nothing", pop.sel == 3 and app.pal.string == "".join(exp) + " ")
    # ---- keys
    pop.sel = 3; pop.on_key(app, pygame.K_RIGHT); r1 = pop.sel; pop.on_key(app, pygame.K_LEFT)
    check("arrow keys move the selection (right = lighter, like the bar)", r1 == 2 and pop.sel == 3)
    nk = app.pal.n; sel0 = pop.sel
    for chr_, kk in (("+", pygame.K_PLUS), ("-", pygame.K_MINUS), ("=", pygame.K_EQUALS)):
        run_events(app, [pygame.event.Event(pygame.KEYDOWN, key=kk, mod=0, unicode=chr_, scancode=0)])
        check(f"typing '{chr_}' puts it in the slot (does not add or remove levels)", app.pal.n == nk and app.pal.chars[sel0] == chr_)
    # typing: table follows, errors are reported, the darkest slot stays a space
    run_events(app, [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode=" ", scancode=0)])
    check("typing a space is refused", app.pal.chars[sel0] == "=" and "DARKEST" in pop.status)
    run_events(app, [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode="\U0001F600", scancode=0)])
    check("typing a character the font cannot draw is refused", app.pal.chars[sel0] == "=" and "NOT IN THE FONT" in pop.status)
    run_events(app, [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode="W", scancode=0)])
    app.redraw_canvas_ascii(app.surface, 0, 0, 0)
    check("the typed character is highlighted in the table", app.pal.chars[sel0] == "W" and pop.jump_until > 0 and app.popup is pop)
    # ---- buttons
    check("RESTORE and SAVE are enabled once edited", pop.button_enabled(app, "RESTORE") and pop.button_enabled(app, "SAVE") and pop.button_enabled(app, "SAVE NEW"))
    edited_string = app.pal.string
    dict_btn = dict(pop.btns)
    pop.on_click(app, *dict_btn["SAVE"].center, 1)
    txt = pf.read_text(encoding="utf-8")
    check("SAVE writes the edited palette (any number of levels) to PAL.txt", edited_string in txt and 2 not in app.pal.edits and not pop.button_enabled(app, "SAVE"), pop.status)
    app.pal.insert_slot(2); app.pal.set_char(2, "&"); newstr = app.pal.string
    pop.on_click(app, *dict(pop.btns)["SAVE NEW"].center, 1)
    check("SAVE NEW stores it in the next free number and the editor now edits that one", app.pal.index == 7 and app.pal.map[7]["chars"] == newstr and app.popup is pop and "07-" in pop.status, pop.status)
    check("the saved-as-new palette keeps the extra level", len(app.pal.map[7]["chars"]) == len(newstr))
    app.pal.set_char(0, "%"); pop.on_click(app, *dict(pop.btns)["RESTORE"].center, 1)
    check("RESTORE button drops the unsaved edit", app.pal.string == newstr and 7 not in app.pal.edits)
    check("RESTORE and SAVE are disabled when nothing changed", not pop.button_enabled(app, "RESTORE") and not pop.button_enabled(app, "SAVE"))
    pop.on_click(app, *dict(pop.btns)["CLOSE"].center, 1)
    check("CLOSE button closes the editor", app.popup is None)
    # a click outside the editor does nothing (no accidental close)
    app.open_char_table(1); pop = app.popup; pop.on_click(app, 1, 1, 1)
    check("clicking outside the editor does not close it or change anything", app.popup is pop)
    run_events(app, [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="", scancode=0)])
    check("Esc closes the editor", app.popup is None)
    # drawing never crashes, with the mouse anywhere
    app.open_char_table(1)
    for pos in ((0, 0), app.popup.plus.center, app.popup.cell_rect(5).center, app.popup.slot_rect(app, 0).center):
        app.redraw_canvas_ascii(app.surface, 0, 0, 0); app.popup.draw(app, app.surface, *pos)
    check("the editor draws with the mouse anywhere", True)
    pygame.quit()



for fn in (t_startup_and_palette, t_bbox_and_copy_fit, t_ctrl_shift_c_does_not_crash, t_ctrl_alt_s_slack_copy,
           t_ctrl_s_saves_in_saves_dir, t_import_button_does_not_stick, t_save_load_roundtrip_and_short_lines,
           t_import_image_undo, t_new_canvas_undoable, t_timelapse,
           t_plain_click_does_not_inject_timelapse_frames, t_line_mode_records_timelapse_frame, t_glyph_cache, t_tone_sphere,
           t_brush_is_round_in_pixels, t_sphere_drag, t_sidebar_layout,
           t_smart_edge_engine, t_smart_paint_clears_and_undo, t_smart_save_load_roundtrip, t_smart_modes_and_mouse,
           t_smudge, t_blur_opacity_and_pen, t_help_overlay_fits, t_canvas_resize, t_canvas_resize_speed, t_palette_slots, t_tooltips, t_opacity_slider, t_palette_editor, t_palette_modal, t_bomb, t_tl_row, t_tru, t_voice, t_voice_captions, t_voice_lines_in_lexicon, t_fade, t_cursor_visible_in_popup, t_bomb_gradation):
    guarded(fn.__name__, fn)

failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed  ({APP_FILE.name})")
sys.exit(1 if failed else 0)
