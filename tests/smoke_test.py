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


for fn in (t_startup_and_palette, t_bbox_and_copy_fit, t_ctrl_shift_c_does_not_crash, t_ctrl_alt_s_slack_copy,
           t_ctrl_s_saves_in_saves_dir, t_import_button_does_not_stick, t_save_load_roundtrip_and_short_lines,
           t_import_image_undo, t_new_canvas_undoable, t_timelapse,
           t_plain_click_does_not_inject_timelapse_frames, t_line_mode_records_timelapse_frame, t_glyph_cache, t_tone_sphere,
           t_brush_is_round_in_pixels, t_sphere_drag, t_sidebar_layout,
           t_smart_edge_engine, t_smart_paint_clears_and_undo, t_smart_save_load_roundtrip, t_smart_modes_and_mouse,
           t_smudge, t_blur_opacity_and_pen, t_help_overlay_fits, t_canvas_resize, t_canvas_resize_speed):
    guarded(fn.__name__, fn)

failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed  ({APP_FILE.name})")
sys.exit(1 if failed else 0)
