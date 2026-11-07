# ASCII Painter - v0.92

import os, math, glob, time, random, webbrowser
import pygame
import numpy as np
from collections import deque
import re

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
#   BUNDLE_DIR : read-only bundled files (PyInstaller _MEIPASS when frozen,
#                the script folder otherwise)
#   USER_DIR   : the user's files (folder of the .exe when frozen, the script
#                folder otherwise). Saves go to USER_DIR/saves, and PAL.txt /
#                startup.txt placed in USER_DIR override the bundled ones.
# (v0.91 did os.chdir(_MEIPASS), so Ctrl+S inside the .exe wrote to a temp folder.)
# ---------------------------------------------------------------------------
IS_FROZEN = bool(getattr(sys, "frozen", False))
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
USER_DIR = Path(sys.executable).resolve().parent if IS_FROZEN else Path(__file__).resolve().parent
ASSETS_DIR = BUNDLE_DIR / "assets"
SAVES_DIR = USER_DIR / "saves"


def find_asset(name):
    """First existing file called `name`: USER_DIR (user override) first, then the bundled assets."""
    for base in (USER_DIR, ASSETS_DIR):
        p = base / name
        if p.is_file():
            return p
    return None


def compute_rows_for_aspect(cols: int, char_w: int, char_h: int, target_aspect: float, fallback_rows: int) -> int:
    """Compute number of rows so that (cols*char_w)/(rows*char_h) ~= target_aspect."""
    if char_w <= 0 or char_h <= 0 or cols <= 0:
        return max(1, int(fallback_rows))
    rows_float = (cols * float(char_w)) / (target_aspect * float(char_h))
    return max(1, int(round(rows_float)))

# ====================== CONFIG ======================
VERSION = "0.92"

# Palette stored LIGHT -> DARK (left to right)
DEFAULT_PALETTE = "$@%#*+=;:,. "

# --- Timelapse config ---
TIMELAPSE_TARGET_COLS = 80
TIMELAPSE_MAX_FRAMES  = 2000   # v0.91 declared 20000 here but a second definition further down silently won with 2000
TL_INTERVAL_MS = 80            # capture rate while the mouse is down (interval mode)
TL_SKIP_DUPLICATE_FRAMES = True  # don't record a frame when the canvas did not change
TL_DEBUG = False  # True to see full tracebacks and crash on export errors

# --- Timelapse progress bar (UI) ---
TL_BAR_HEIGHT = 3
TL_BAR_MARGIN_X = 12
TL_BAR_GAP_FROM_SPHERE = 6

# --- Overlay settings ---
OVERLAY_OPACITY = 0.35  # 0.0 = fully transparent, 1.0 = fully opaque

# --- Timelapse GIF output ---
TIMELAPSE_GIF_FPS = 24         # frames per second (ignored if TIMELAPSE_GIF_FRAME_MS is set)
TIMELAPSE_GIF_FRAME_MS = None  # set e.g. 80 to force ms/frame; None -> derive from FPS
TIMELAPSE_EXPORT_SCALE = 1    # 1.0 sem downscale; 0.5 = metade dos pixels
TIMELAPSE_EXPORT_RESAMPLE = "lanczos"   # "nearest" | "box" | "bilinear" | "bicubic" | "lanczos"
TIMELAPSE_GIF_OPTIMIZE = True   # pode botar False pra debugar “1 frame”

# Capture modes
TL_CAPTURE_STROKE   = 0
TL_CAPTURE_INTERVAL = 1
TL_CAPTURE_BOTH     = 2
# Backward-compat alias for older patches that used "sound" capture
try:
    TL_CAPTURE_SOUND
except NameError:
    TL_CAPTURE_SOUND = 3  # deprecated: treated same as interval trigger

# --- Timelapse GIF downscale (keeps same ASCII cols/rows) ---
TIMELAPSE_EXPORT_METHOD = "font"       # "font" (faster) or "scale" (fallback)

TIMELAPSE_CAPTURE_MODE = TL_CAPTURE_INTERVAL  # or TL_CAPTURE_STROKE / TL_CAPTURE_BOTH

# Dynamic timelapse pause on mouse release
DYNAMIC_TLAPSE = True                 # turn ON/OFF the pause injection
TL_MOUSE_RELEASE_INJECT_FRAMES = 4    # how many extra frames to inject on mouse-up

# Garante que o tom mais escuro (último) é sempre ' ' (espaço)
ENFORCE_DARKEST_IS_SPACE = True

# Cursor
HIDE_CURSOR_OVER_CANVAS = True  # esconde o mouse sobre o canvas; mostra no sidebar/HELP

# Horizontal palette bar display order (UI only):
PALETTE_BAR_DARK_TO_LIGHT = True  # show DARK -> LIGHT for intuitive -= navigation

# Window / Font
WINDOW_SCALE = 1.0
AUTO_FIT_WINDOW = True   # shrink the window (never enlarge) when the screen is too small for it
FONT_NAME, FONT_SIZE = "consolas", 16

# Canvas & Grid Defaults (character cells)
# Grid will always match the canvas text cells (1:1)
GRID_MATCH_CELLS: bool = True

# Target display aspect (width:height) for the rendered canvas area
TARGET_ASPECT: float = 4.0 / 3.0  # classic 4:3 look

# --- Rows override (optional) ---
ROWS_OVERRIDE: int = 48   # 0 = disabled. Put e.g. 64 to force 80x64 cells

# Max columns (width in characters). Height will be computed from font metrics
MAX_COLS: int = 80
# Fallback rows used before font metrics are available
FALLBACK_ROWS: int = 48

# Initial placeholders; real values computed after font init
COLS, ROWS = MAX_COLS, FALLBACK_ROWS

# UI layout
SIDEBAR_W, PICKER_SIZE, PALETTE_BAR_H, UI_MARGIN = 260, 160, 28, 16

SIDEBAR_MIN_HEIGHT = 800
IND_GAP_Y, IND_PAD_X, IND_PAD_Y = 6, 6, 3
UI_EXTRA_VERTICAL = 0
PICKER_Y_OFFSET_LINES = 1  # lift sphere inside its box by 1 text line

HELP_DESC_SHIFT = 145  # pixels, tweak to taste
HELP_BLOCK_XOFFSET = 10  # pixels, indent for HELP

# Brush & history
INITIAL_BRUSH_RADIUS = 1
LIGHTEN_STEP = 0.03
UNDO_LIMIT = 64

##### Audio
# --- Gating / crossfade essenciais ---
SOUND_CHOP_MS         = 32
SOUND_FULL_WINDOW_MS  = 140
SND_MIN_INTERVAL_MS   = 50
SND_CROSSFADE_MS      = 2
SND_OUTPUT_VOLUME     = 1.0
SND_USE_TWO_CHANNELS = True
SND_REQUIRE_RADIUS1   = False
SND_CELL_TRIGGER_ONLY = True
SND_OVERLAP_FADE_MS = 8   # fade-out when reusing the same channel
SND_FADEIN_MS       = 0    # small fade-in on the new tick
SND_DUCKING         = 1 # lower the "other" channel a bit while both overlap

SND_UI_KEYPRESS_ON_ANY_KEYDOWN = True

# Canal base para o brush (0..7). O 2º canal usa (index+1)%8
SOUND_CHANNEL_INDEX   = 0

# Variação de pitch (pool de fatores). Coloque STEPS=1 para desativar.
PITCH_VARIATION_PCT   = 0.1
PITCH_VARIATION_STEPS = 5

# Tocar sample FULL quando soltar o stroke
SND_PLAY_FULL_ON_RELEASE = False

# Colors
WHITE=(255,255,255); BLACK=(0,0,0)
GREY_TEXT=(204,204,204); GREY_DESC=(140,140,140)
GREY=(180,180,180); GREY50=(128,128,128); GREY10=(26,26,26)
GRID_COL=(35,35,35)
HOVER_FILL=(40,40,40); PRESS_FILL=(70,70,70)
CYAN=(90,220,220); RED=(240,80,80)
HL_RGB=(253,253,253)

# Per-cell text luminance (RGB)
TEXT_LUMA     = 0.72          # default grey
HLIGHT_LUMA   = 253/255.0     # almost white for highlight
HL_ERASE_LUMA = TEXT_LUMA

# --- Copy/Export settings ---
COPY_DEFAULT_MODE = "markdown"   # "markdown" | "plain" | "html"
COPY_USE_NBSP = False            # when True, replace spaces by \u00A0 on copy
DEFAULT_COPY_FIT_COLS = 80

# --- Copy/export aspect correction ---
EXPORT_ROW_SCALE = 1.0
SLACK_ROW_SCALE  = 0.74  # tweak to match Slack's line-height
       # default width for Ctrl+Shift+C

# --- Grid settings ---
GRID_MIN = 1
GRID_MAX = 64
DEFAULT_GRID_COLS = 4
DEFAULT_GRID_ROWS = 3

# ====================== UTILS ======================
def clamp01(v: float) -> float:
    return float(max(0.0, min(1.0, v)))

def timestamp():
    return time.strftime("%Y%m%d_%H%M%S")

def open_folder(path):
    try: os.startfile(os.path.abspath(path))
    except Exception: webbrowser.open('file:///' + os.path.abspath(path).replace('\\','/'))

def load_palette_file(path: str):
    if os.path.exists(path):
        s = open(path, "r", encoding="utf-8").read().replace("\r","").replace("\n","")
        if len(s) >= 2:
            return s
    return None

def build_pitch_pool():
    if PITCH_VARIATION_STEPS <= 1 or PITCH_VARIATION_PCT <= 0:
        return [1.0]
    lo = 1.0 - PITCH_VARIATION_PCT
    hi = 1.0 + PITCH_VARIATION_PCT
    return list(np.linspace(lo, hi, PITCH_VARIATION_STEPS))

def luma_to_rgb(l):
    v = int(clamp01(l)*255)
    return (v, v, v)

class GlyphCache:
    """font.render() is slow and the canvas needs ~4000 glyphs per frame: render each (char, color) once."""
    def __init__(self, font, max_items=20000):
        self.font = font
        self.max_items = max_items
        self._cache = {}

    def get(self, ch, rgb):
        key = (ch, rgb)
        surf = self._cache.get(key)
        if surf is None:
            if len(self._cache) >= self.max_items:
                self._cache.clear()
            surf = self.font.render(ch, True, rgb)
            self._cache[key] = surf
        return surf

def ascii_lines_from_buf(buf2d, pal_chars):
    """Convert tone buffer [0..1] to list of strings using palette chars (index = round(v*(n-1)))."""
    n = len(pal_chars) - 1
    idx = np.rint(np.clip(buf2d * n, 0, n)).astype(np.int32)
    return ["".join(pal_chars[i] for i in row) for row in idx]

def resize_tone_buffer_bilinear(src, new_rows, new_cols):
    """Bilinear resize (numpy-only). src: (H,W) -> (new_rows,new_cols)."""
    h, w = src.shape
    if new_rows == h and new_cols == w:
        return src.copy()
    ys = np.linspace(0, h - 1, new_rows)
    xs = np.linspace(0, w - 1, new_cols)
    # interpolate along Y into tmp (new_rows, w)
    y0 = np.floor(ys).astype(int)
    y1 = np.clip(y0 + 1, 0, h - 1)
    wy = (ys - y0)[:, None]
    tmp = (1 - wy) * src[y0, :] + wy * src[y1, :]
    # interpolate along X into out (new_rows, new_cols)
    x0 = np.floor(xs).astype(int)
    x1 = np.clip(x0 + 1, 0, w - 1)
    wx = (xs - x0)[None, :]
    out = (1 - wx) * tmp[:, x0] + wx * tmp[:, x1]
    return out

def copy_to_clipboard(text):
    """Use Tkinter clipboard (works on Windows/macOS/Linux)."""
    try:
        import tkinter as tk
        r = tk.Tk(); r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(text)
        r.update()
        r.destroy()
        return True
    except Exception as e:
        print("Clipboard error:", e)
        return False

def wrap_as_markdown(lines):
    return "```\n" + "\n".join(lines) + "\n```"

def wrap_as_html_pre(lines):
    # Use &nbsp; for spaces to avoid collapse outside <pre> (optional)
    def esc(s):
        s = s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        return s.replace(" ", "&nbsp;")
    return "<pre style=\"font: 12px/1.1 monospace; white-space: pre;\">" + \
           "\n".join(esc(l) for l in lines) + "</pre>"

def maybe_nbsp(lines, enable):
    if not enable: return lines
    return [l.replace(" ", "\u00A0") for l in lines]

# ====================== PALETTE ======================
def ensure_darkest_space(palette_str: str) -> str:
    """Retorna uma paleta com exatamente 1 espaço no final.
    - Remove quaisquer espaços internos (e NBSP).
    - Se ficar só espaço, usa '.' como placeholder claro.
    """
    if not ENFORCE_DARKEST_IS_SPACE:
        return palette_str
    core = (palette_str
            .replace(' ', '')
            .replace('\u00A0', ''))
    if not core:
        core = '.'  # mínimo 1 char visível
    return core + ' '


class PaletteManager:
    """
    Gerencia múltiplas paletas a partir de 'PAL.txt'.
    Formato esperado (UTF-8):
        NN-NOME
        <linha de caracteres da paleta>
        [linha(s) em branco]
    Ex.: 
        01-MINIMAL
        @#*+=. 

        02-PAUL.BURKE.(1997).MINIMAL
        @%#*+=-:. 
    """
    PAL_FILE = "PAL.txt"
    HEADER_RX = re.compile(r'^\s*(\d{2})\s*-\s*(.+?)\s*$')

    def __init__(self):
        # dicionário: { nn(int 1..99): {"name": str, "chars": str} }
        self.map = {}
        self.order = []  # lista ordenada de NN existentes
        self.index = 1   # índice selecionado (01..99), default = 1 (ajustado abaixo)
        self.display_name = "DEFAULT"  # "01-NOME"
        self.string = DEFAULT_PALETTE  # linha de caracteres (LIGHT -> DARK)
        self.chars = list(self.string)
        self.n = len(self.chars)
        self.decile_to_index = [int(round((k/9.0)*(self.n-1))) for k in range(10)]
        self.is_space = np.array([c == ' ' for c in self.chars], dtype=bool)

        self._load_all_from_file()
        # se não houver nenhuma paleta no arquivo, já estamos com DEFAULT
        # se houver, tenta selecionar 01, senão a primeira disponível
        if self.order:
            self.set_index(1 if 1 in self.map else self.order[0])

    # ---------- carregamento ----------
    def _load_all_from_file(self):
        found = find_asset(self.PAL_FILE)
        if found is None:
            # sem PAL.txt: mantém DEFAULT
            return
        path = str(found)
        try:
            # Importante: não usar .strip() na linha da paleta, para manter espaços à direita
            txt = open(path, "r", encoding="utf-8").read().splitlines()
        except Exception:
            return

        i = 0
        pending_nn = None
        pending_name = None
        while i < len(txt):
            line = txt[i].rstrip("\r\n")
            i += 1
            if not line.strip():
                continue  # pula linhas em branco

            m = self.HEADER_RX.match(line)
            if m:
                # cabeçalho encontrado: próxima linha não-vazia é a paleta
                pending_nn = int(m.group(1))
                pending_name = m.group(2).strip()
                # consome até achar a linha da paleta
                while i < len(txt) and not txt[i].strip():
                    i += 1
                if i < len(txt):
                    pal_line = txt[i].rstrip("\r\n")  # mantém espaços!
                    i += 1
                    # registra
                    self.map[pending_nn] = {"name": pending_name, "chars": pal_line}
                    pending_nn = None; pending_name = None
                continue

        # ordena índices válidos
        self.order = sorted(self.map.keys())

    # ---------- reconstruções ----------
    def rebuild_cache_from_string(self, s: str):
        s = ensure_darkest_space(s)  # <<< força espaço como mais escuro
        self.string = s
        self.chars = list(s)
        self.n = len(self.chars)
        self.decile_to_index = [int(round((k/9.0)*max(0, self.n-1))) for k in range(10)]
        self.is_space = np.array([c == ' ' for c in self.chars], dtype=bool)

    # ---------- API pública ----------
    def set_index(self, idx: int):
        """
        Seleciona paleta NN = 1..99.
        - SHIFT+1..0 chama com 1..10 (0->10) no seu loop.
        - Fallback para DEFAULT se NN não existir.
        """
        if idx in self.map:
            entry = self.map[idx]
            # mantém string EXATAMENTE como no arquivo (inclui espaços finais)
            s = entry["chars"]
            # sanity: paleta mínima com 2 caracteres
            if isinstance(s, str) and len(s) >= 2:
                self.index = idx
                self.display_name = f"{idx:02d}-{entry['name']}"
                self.rebuild_cache_from_string(s)
                return
        # fallback DEFAULT
        self.index = 0
        self.display_name = "DEFAULT"
        self.rebuild_cache_from_string(DEFAULT_PALETTE)

    def invert(self):
        self.chars.reverse()
        s = "".join(self.chars)
        s = ensure_darkest_space(s)
        self.rebuild_cache_from_string(s)

    # tom v in [0..1] -> índice 0..n-1 (0 = light, 1 = dark)
    def idx_from_value(self, v: float) -> int:
        return int(round(clamp01(v) * max(0, self.n-1)))

    def char_from_value(self, v: float) -> str:
        return self.chars[self.idx_from_value(v)]

    def value_from_idx(self, i: int) -> float:
        if self.n <= 1: return 0.0
        i = max(0, min(self.n-1, i))
        return i/float(self.n-1)

    def set_from_decile_key(self, digit: int) -> float:
        # mantém comportamento anterior (1..9 e 0=extremo direito)
        idx = self.decile_to_index[9] if digit == 0 else self.decile_to_index[max(0, min(9, digit-1))]
        return self.value_from_idx(idx)


# ====================== CANVAS ======================
class ASCIICanvas:
    """buf: tone [0..1] (0 light, 1 dark). col: per-cell text luminance [0..1]."""
    def __init__(self, rows, cols):
        self.rows, self.cols = rows, cols
        self.buf = np.zeros((rows, cols), dtype=np.float32)               # tones
        self.col = np.full((rows, cols), TEXT_LUMA, dtype=np.float32)     # RGB luma

    def clear(self, tone_val=1.0, luma=TEXT_LUMA):
        # default clear = darkest
        self.buf[:] = tone_val
        self.col[:] = luma

    def _blend_cell(self, x, y, target, a):
        self.buf[y, x] = self.buf[y, x]*(1.0-a) + target*a

    def _blend_luma_cell(self, x, y, target_l, a):
        self.col[y, x] = self.col[y, x]*(1.0-a) + target_l*a

    # ---- tone discs ----
    def paint_disc_blend(self, cx, cy, r, target, a, soft):
        if r <= 1:
            if 0<=cx<self.cols and 0<=cy<self.rows:
                self._blend_cell(cx, cy, target, a)
            return
        R = r - 0.5; R2 = R*R
        x0 = max(0, int(cx-r)); x1 = min(self.cols-1, int(cx+r))
        y0 = max(0, int(cy-r)); y1 = min(self.rows-1, int(cy+r))
        for y in range(y0, y1+1):
            dy = y - cy
            for x in range(x0, x1+1):
                dx = x - cx; d2 = dx*dx + dy*dy
                if d2 <= R2:
                    aa = a
                    if soft:
                        t = clamp01(1.0 - math.sqrt(d2)/max(1e-6, R))
                        aa = a*(t**1.5)
                    self._blend_cell(x, y, target, aa)

    def erase_disc_blend(self, cx, cy, r, a, soft):
        # erase = go to darkest (1.0)
        self.paint_disc_blend(cx, cy, r, 1.0, a, soft)

    def add_disc(self, cx, cy, r, delta, a, soft):
        # delta > 0 => darker; delta < 0 => lighter (since 1=dark)
        if r <= 1:
            if 0<=cx<self.cols and 0<=cy<self.rows:
                self.buf[cy, cx] = clamp01(self.buf[cy, cx] + delta*a)
            return
        R = r - 0.5; R2 = R*R
        x0 = max(0, int(cx-r)); x1 = min(self.cols-1, int(cx+r))
        y0 = max(0, int(cy-r)); y1 = min(self.rows-1, int(cy+r))
        for y in range(y0, y1+1):
            dy = y - cy
            for x in range(x0, x1+1):
                dx = x - cx; d2 = dx*dx + dy*dy
                if d2 <= R2:
                    scale = 1.0
                    if soft:
                        t = clamp01(1.0 - math.sqrt(d2)/max(1e-6, R))
                        scale = t**1.5
                    self.buf[y, x] = clamp01(self.buf[y, x] + delta*a*scale)

    # ---- luma discs (RGB) ----
    def luma_disc_blend(self, cx, cy, r, target_l, a, soft):
        if r <= 1:
            if 0<=cx<self.cols and 0<=cy<self.rows:
                self._blend_luma_cell(cx, cy, target_l, a)
            return
        R = r - 0.5; R2 = R*R
        x0 = max(0, int(cx-r)); x1 = min(self.cols-1, int(cx+r))
        y0 = max(0, int(cy-r)); y1 = min(self.rows-1, int(cy+r))
        for y in range(y0, y1+1):
            dy = y - cy
            for x in range(x0, x1+1):
                dx = x - cx; d2 = dx*dx + dy*dy
                if d2 <= R2:
                    aa = a
                    if soft:
                        t = clamp01(1.0 - math.sqrt(d2)/max(1e-6, R))
                        aa = a*(t**1.5)
                    self._blend_luma_cell(x, y, target_l, aa)

    # ---- blur ----
    def blur_disc(self, cx, cy, radius):
        r = max(1, radius); R2 = (r-0.5)*(r-0.5)
        x0 = max(0, cx-r); x1 = min(self.cols-1, cx+r)
        y0 = max(0, cy-r); y1 = min(self.rows-1, cy+r)
        patch = self.buf[y0:y1+1, x0:x1+1]
        if patch.size == 0: return
        k = np.array([[1,2,1],[2,4,2],[1,2,1]], dtype=np.float32) / 16.0
        padded = np.pad(patch, ((1,1),(1,1)), mode='edge')
        out = (padded[0:-2,0:-2]*k[0,0] + padded[0:-2,1:-1]*k[0,1] + padded[0:-2,2:]*k[0,2] +
               padded[1:-1,0:-2]*k[1,0] + padded[1:-1,1:-1]*k[1,1] + padded[1:-1,2:]*k[1,2] +
               padded[2:,0:-2]*k[2,0] + padded[2:,1:-1]*k[2,1] + padded[2:,2:]*k[2,2])
        hh, ww = out.shape
        yy, xx = np.ogrid[0:hh, 0:ww]
        dy = yy - (cy - y0); dx = xx - (cx - x0)
        mask = (dx*dx + dy*dy) <= R2
        patch[mask] = out[mask]

    # ---- lines ----
    @staticmethod
    def _closest_point_to_segment(px, py, x0, y0, x1, y1):
        vx, vy = (x1 - x0), (y1 - y0)
        len2 = vx*vx + vy*vy
        if len2 <= 1e-6: return x0, y0, 0.0
        t = ((px - x0)*vx + (py - y0)*vy) / len2
        t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
        cx, cy = (x0 + t*vx, y0 + t*vy)
        return cx, cy, t

    def draw_line_basic(self, x0, y0, x1, y1, val, a, radius, soft):
        dx = abs(x1 - x0); sx = 1 if x0 < x1 else -1
        dy = -abs(y1 - y0); sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.paint_disc_blend(x0, y0, max(1, radius), val, a, soft)
            if x0 == x1 and y0 == y1: break
            e2 = 2 * err
            if e2 >= dy: err += dy; x0 += sx
            if e2 <= dx: err += dx; y0 += sy

    def draw_line_aa_thick(self, x0, y0, x1, y1, val, a, radius, soft, reset_luma_to=None):
        r = float(max(1, radius))
        minx = max(0, int(min(x0, x1) - r - 1))
        maxx = min(self.cols-1, int(max(x0, x1) + r + 1))
        miny = max(0, int(min(y0, y1) - r - 1))
        maxy = min(self.rows-1, int(max(y0, y1) + r + 1))
        for y in range(miny, maxy+1):
            for x in range(minx, maxx+1):
                cx, cy, _ = self._closest_point_to_segment(x, y, x0, y0, x1, y1)
                dx, dy = (x - cx), (y - cy)
                d = math.hypot(dx, dy)
                if soft:
                    base = clamp01(1.0 - d/r); cov  = base**1.5
                else:
                    if d <= r - 0.5: cov = 1.0
                    elif d <= r + 0.5: cov = (r + 0.5 - d)
                    else: cov = 0.0
                if cov <= 0.0: continue
                aa = clamp01(a * cov)
                self._blend_cell(x, y, val, aa)
                if reset_luma_to is not None:
                    self._blend_luma_cell(x, y, reset_luma_to, cov)

# ====================== AUDIO ======================

def build_pitch_variants(path, pool_factors):
    try:
        base = pygame.mixer.Sound(path)
        import pygame.sndarray as SA
        arr = SA.array(base); arr = np.array(arr)
        # DEPOIS (downmix por média, mais fiel e com nível melhor)
        if arr.ndim == 2:
            if arr.shape[1] in (1,2):
                mono = arr.mean(axis=1)           # (N,2) -> (N,)
            elif arr.shape[0] in (1,2):
                mono = arr.mean(axis=0)           # (2,N) -> (N,)
            else:
                mono = arr.mean(axis=-1)
        else:
            mono = arr

        mono = np.asarray(mono, dtype=np.int16)
        freq, fmt, ch = pygame.mixer.get_init()
        variants = []
        for r in pool_factors:
            n = max(1, int(len(mono)/r))
            xp = np.linspace(0, len(mono)-1, n)
            y = np.interp(xp, np.arange(len(mono)), mono).astype(np.int16)
            if ch == 2: y = np.stack([y, y], axis=1)
            variants.append(pygame.sndarray.make_sound(np.ascontiguousarray(y)))
        return variants, os.path.basename(path)
    except Exception:
        try:
            snd = pygame.mixer.Sound(path)
            return [snd], os.path.basename(path)
        except Exception:
            return None, "wav not present"

def add_tail_fade(sound: pygame.mixer.Sound, tail_fade_ms: int) -> pygame.mixer.Sound:
    """Aplica um fade no final do sample SEM cortar duração."""
    import pygame.sndarray as SA
    try:
        arr = SA.array(sound)
        arr = np.array(arr, dtype=np.int16, copy=True)
        freq, fmt, ch = pygame.mixer.get_init()
        n_tail = max(1, int((tail_fade_ms/1000.0) * freq))
        n_tail = min(n_tail, arr.shape[0])
        if n_tail > 0:
            out = arr.astype(np.float32)
            if out.ndim == 2:
                fade = np.linspace(1.0, 0.0, n_tail, dtype=np.float32)[:, None]
            else:
                fade = np.linspace(1.0, 0.0, n_tail, dtype=np.float32)
            out[-n_tail:] *= fade
            out = np.clip(out, -32768, 32767).astype(np.int16)
            return pygame.sndarray.make_sound(np.ascontiguousarray(out))
        return sound
    except Exception:
        return sound

def make_chopped_copy(sound: pygame.mixer.Sound, chop_ms: int, tail_fade_ms: int) -> pygame.mixer.Sound:
    """Copia encurtada do sample com fade no final (para toques rápidos)."""
    import pygame.sndarray as SA
    try:
        arr = SA.array(sound)
        arr = np.array(arr, dtype=np.int16, copy=True)
        freq, fmt, ch = pygame.mixer.get_init()
        n_chop = max(1, int((chop_ms/1000.0) * freq))
        n = min(arr.shape[0], n_chop)
        out = arr[:n].astype(np.float32)
        n_tail = max(1, int((tail_fade_ms/1000.0) * freq))
        n_tail = min(n_tail, out.shape[0])
        if n_tail > 0:
            if out.ndim == 2:
                fade = np.linspace(1.0, 0.0, n_tail, dtype=np.float32)[:, None]
            else:
                fade = np.linspace(1.0, 0.0, n_tail, dtype=np.float32)
            out[-n_tail:] *= fade
        out = np.clip(out, -32768, 32767).astype(np.int16)
        return pygame.sndarray.make_sound(np.ascontiguousarray(out))
    except Exception:
        return sound

def normalize_sound(snd: pygame.mixer.Sound, target_peak=0.98) -> pygame.mixer.Sound:
    import pygame.sndarray as SA
    try:
        arr = SA.array(snd)
        arr = np.array(arr, dtype=np.int16, copy=True)
        peak = np.max(np.abs(arr))
        if peak <= 0:
            return snd
        scale = float(target_peak * 32767.0) / float(peak)
        out = np.clip(arr.astype(np.float32) * scale, -32768, 32767).astype(np.int16)
        return pygame.sndarray.make_sound(np.ascontiguousarray(out))
    except Exception:
        return snd


def list_keypress_wavs():
    """
    Procura apenas arquivos 'keypress_XX.wav' (XX = 2 dígitos).
    Retorna lista ordenada pelo número (01, 02, 03...).
    """
    cand = []
    for d in (USER_DIR / "sounds", ASSETS_DIR / "sounds", USER_DIR, ASSETS_DIR):
        cand += glob.glob(str(d / "keypress_*.wav"))
    seen, uniq = set(), []
    for p in cand:                      # same file name in several folders: first one wins
        b = os.path.basename(p).lower()
        if b not in seen:
            seen.add(b)
            uniq.append(p)
    cand = uniq
    rx = re.compile(r'^keypress_(\d{2})\.wav$', re.IGNORECASE)
    out = []
    for p in cand:
        fname = os.path.basename(p)
        m = rx.match(fname)
        if m:
            out.append(p)
    # ordena pelo sufixo numérico
    out.sort(key=lambda p: int(re.search(r'(\d{2})', os.path.basename(p)).group(1)))
    return out

def build_pitch_variants_multi(paths, pool_factors):
    """Carrega todos os wavs e concatena as variantes de pitch."""
    all_vars = []
    for p in paths:
        vars_p, _ = build_pitch_variants(p, pool_factors)
        if vars_p:
            all_vars.extend(vars_p)
    return all_vars


# (timelapse config lives in the CONFIG block at the top of the file)

# ==== [Timelapse] Recorder ====================================================
class TimelapseRecorder:
    """
    Records small ASCII snapshots at the end of each stroke (low-cost).
    Each frame stores only ASCII chars (no per-cell luma) to keep memory tiny.
    Export later to an animated GIF via Pillow.
    """
    def __init__(self, target_cols=TIMELAPSE_TARGET_COLS, max_frames=TIMELAPSE_MAX_FRAMES):
        self.enabled = False
        self.target_cols = max(10, int(target_cols))
        self.target_rows = None
        self.max_frames = max_frames
        self.frames = []
        self.pal_string = None
        self.last_tone = None      # tone buffer of the last captured frame (duplicate detection)

    def reset(self):
        self.frames.clear()
        self.target_rows = None
        self.pal_string = None
        self.last_tone = None

    def _downsample_to_ascii_lines(self, buf2d, pal_chars):
        src_h, src_w = buf2d.shape
        if self.target_rows is None:
            self.target_rows = max(2, int(round(src_h * (self.target_cols / max(1, src_w)))))
        small = resize_tone_buffer_bilinear(buf2d, self.target_rows, self.target_cols)
        return ascii_lines_from_buf(small, pal_chars)

    def capture(self, canvas, palette, force=False):
        if not self.enabled:
            return
        if len(self.frames) >= self.max_frames:
            return
        if (TL_SKIP_DUPLICATE_FRAMES and not force and self.last_tone is not None
                and np.array_equal(self.last_tone, canvas.buf)):
            return                 # canvas did not change since the last frame
        self.last_tone = canvas.buf.copy()
        if self.pal_string is None:
            self.pal_string = "".join(palette.chars)
        lines = self._downsample_to_ascii_lines(canvas.buf, list(self.pal_string))
        self.frames.append(lines)

    def export_gif(self, out_path, font, char_w, char_h):
        """
        Export frames captured by the timelapse recorder as an animated GIF.
        Displays a centered 'WAIT... EXPORTING' message before processing.
        """
        if not self.frames:
            print("[TL] No frames to export.")
            return False

        # Try to get owner App (for drawing the message)
        owner = getattr(self, "app", None)

        # --- Draw static message BEFORE export ---
        if owner is not None:
            try:
                surf = owner.surface
                surf.fill(BLACK)
                msg1 = owner.font.render("WAIT...", True, CYAN)
                msg2 = owner.font.render("EXPORTING", True, CYAN)
                y_center = surf.get_height() // 2
                x_center = surf.get_width() // 2
                surf.blit(msg1, (x_center - msg1.get_width() // 2, y_center - msg1.get_height()))
                surf.blit(msg2, (x_center - msg2.get_width() // 2, y_center + 10))
                owner.screen.blit(surf, (0, 0))
                pygame.display.flip()
                pygame.time.wait(300)  # small delay to ensure it shows before processing starts
            except Exception as e:
                print("[TL] Could not display export message:", e)
        else:
            # Fallback to clear screen if no owner
            try:
                screen = pygame.display.get_surface()
                if screen:
                    screen.fill((0, 0, 0))
                    font_tmp = pygame.font.SysFont("consolas", 22)
                    text = font_tmp.render("WAIT... EXPORTING", True, (90, 220, 220))
                    screen.blit(text, ((screen.get_width() - text.get_width()) // 2,
                                    (screen.get_height() - text.get_height()) // 2))
                    pygame.display.flip()
                    pygame.time.wait(300)
            except Exception:
                pass

        try:
            from PIL import Image
        except Exception as e:
            print("[TL] Pillow not installed, cannot export GIF. Error:", e)
            return False

        exported_ok = False
        try:
            # --- derive frame duration ---
            frame_ms = globals().get("TIMELAPSE_GIF_FRAME_MS", None)
            if frame_ms is None:
                fps = int(globals().get("TIMELAPSE_GIF_FPS", 12))
                fps = max(1, fps)
                frame_ms = max(10, int(round(1000 / fps)))

            surf_w = self.target_cols * char_w
            surf_h = self.target_rows * char_h
            scale = float(globals().get("TIMELAPSE_EXPORT_SCALE", 1.0))
            scale = 1.0 if scale <= 0 else min(scale, 1.0)

            images = []
            glyphs = GlyphCache(font)
            text_rgb = luma_to_rgb(TEXT_LUMA)
            frame_cache = {}   # identical frames (pauses, repeats) are rendered only once

            try:
                Res = Image.Resampling
            except AttributeError:
                Res = Image
            RESMAP = {
                "nearest": getattr(Res, "NEAREST"),
                "box": getattr(Res, "BOX", getattr(Res, "BILINEAR")),
                "bilinear": getattr(Res, "BILINEAR"),
                "bicubic": getattr(Res, "BICUBIC"),
                "lanczos": getattr(Res, "LANCZOS", getattr(Res, "BICUBIC")),
            }
            res_name = str(globals().get("TIMELAPSE_EXPORT_RESAMPLE", "box")).lower()
            resample = RESMAP.get(res_name, RESMAP["box"])

            for lines in self.frames:
                key = tuple(lines)
                im = frame_cache.get(key)
                if im is None:
                    surf = pygame.Surface((surf_w, surf_h))
                    surf.fill(BLACK)
                    for r, line in enumerate(lines):
                        for c, ch in enumerate(line):
                            if ch != " ":
                                surf.blit(glyphs.get(ch, text_rgb), (c * char_w, r * char_h))
                    arr = np.transpose(pygame.surfarray.array3d(surf), (1, 0, 2))
                    # frames are grey on black: 8-bit grey is lossless and uses 1/3 of the memory of RGB
                    im = Image.fromarray(np.ascontiguousarray(arr)).convert("L")
                    if scale < 1.0:
                        target = (max(1, int(im.width * scale)), max(1, int(im.height * scale)))
                        im = im.resize(target, resample=resample)
                    frame_cache[key] = im
                images.append(im)

            optimize = bool(globals().get("TIMELAPSE_GIF_OPTIMIZE", True))

            images[0].save(
                out_path,
                save_all=True,
                append_images=images[1:] if len(images) > 1 else [],
                duration=frame_ms,
                loop=0,
                optimize=optimize,
                disposal=2,
            )

            print(
                f"[TL] GIF saved: {out_path} "
                f"(frames={len(images)}, px={images[0].size[0]}x{images[0].size[1]}, frame_ms={frame_ms}, optimize={optimize})"
            )
            exported_ok = True
            return True

        except Exception as e:
            print(f"[TL] GIF export failed ({type(e).__name__}): {e}")
            if globals().get("TL_DEBUG", False):
                raise
            return False

        finally:
            if exported_ok:
                self.frames.clear()
                self.last_tone = None
                self.target_rows = None
                print("[TL] Frames cleared after export.")
            else:
                print("[TL] Export did not finish: frames were kept.")

            # refresh the screen after export
            if owner is not None:
                try:
                    owner.redraw_canvas_ascii(owner.surface, *pygame.mouse.get_pos(), pygame.time.get_ticks())
                    owner.present_surface()
                    pygame.display.flip()
                except Exception:
                    pass


    def inject_repeat_last(self, n: int) -> int:
        """Repeat the last recorded frame N times (capped by max_frames)."""
        if not self.enabled or n <= 0:
            return 0
        if not self.frames:
            return 0
        room = max(0, self.max_frames - len(self.frames))
        if room <= 0:
            return 0
        k = min(n, room)
        last = self.frames[-1]
        # Make shallow copies to avoid any accidental aliasing
        for _ in range(k):
            self.frames.append(list(last))
        return k

# ==== [/Timelapse] ============================================================



# ====================== APP ======================
class App:
    def __init__(self):
        # Mixer robusto (buffer maior para evitar pops)
        try:
            pygame.mixer.pre_init(frequency=22050, size=-16, channels=1, buffer=1024, allowedchanges=0)
        except Exception:
            pass

        pygame.init()
        pygame.display.set_caption(f"ASCII Painter || v{VERSION} || @msouza3d - 2025")

        # --------- ÁUDIO ---------
        self.sound_enabled = True
        self.wav_variants, self.wav_name = None, "wav not present"
        self.brush_channel = None
        self.last_tick_ms = 0

        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=1024, allowedchanges=0)
            pygame.mixer.set_num_channels(8)

            pool = build_pitch_pool()

            # >>> usa SOMENTE os arquivos keypress_XX.wav <<<
            wavs = list_keypress_wavs()
            if wavs:
                # nome exibido na UI
                self.wav_name = (os.path.basename(wavs[0]) if len(wavs) == 1 else "Multi-waves")

                # variantes de pitch somando todos os arquivos
                self.wav_variants = build_pitch_variants_multi(wavs, pool)

                if not self.wav_variants:
                    self.sound_enabled = False
                else:
                    # normaliza pico e monta pools FULL/CHOP (se tiver estes helpers no projeto)
                    try:
                        self.wav_variants = [normalize_sound(s, 0.98) for s in self.wav_variants]
                    except Exception:
                        pass

                    TAIL_FULL_MS = 10
                    TAIL_CHOP_MS = 10
                    try:
                        self.wav_variants_full = [add_tail_fade(s, TAIL_FULL_MS) for s in self.wav_variants]
                        self.wav_variants_chop = [make_chopped_copy(s, SOUND_CHOP_MS, TAIL_CHOP_MS) for s in self.wav_variants]
                    except Exception:
                        # fallback se não tiver os helpers: usa a lista crua
                        self.wav_variants_full = list(self.wav_variants)
                        self.wav_variants_chop = list(self.wav_variants)

                    # canais para ping-pong/crossfade
                    self.brush_channel  = pygame.mixer.Channel(SOUND_CHANNEL_INDEX)
                    self.brush_channel2 = pygame.mixer.Channel((SOUND_CHANNEL_INDEX + 1) % 8)
                    self.active_brush_ch = 0
                    try:
                        self.brush_channel.set_volume(SND_OUTPUT_VOLUME)
                        self.brush_channel2.set_volume(SND_OUTPUT_VOLUME)
                    except Exception:
                        pass
            else:
                self.sound_enabled = False
        except Exception:
            self.sound_enabled = False

        # Gate de célula/tempo (som do brush)
        self.snd_last_cell = None
        self.snd_last_ts   = 0

        self.processing_active = False
        self.processing_ticks = 0

        self.overlay_image = None
        self.overlay_visible = False

        # Fonts & surfaces
        self.font = pygame.font.SysFont(FONT_NAME, FONT_SIZE)
        self.font_small = pygame.font.SysFont(FONT_NAME, max(10, FONT_SIZE-2))
        self.char_w, self.char_h = self.font.size("M")
        self.glyphs = GlyphCache(self.font)
        # Compute rows to target ~4:3 aspect with fixed MAX_COLS using actual font metrics
        global COLS, ROWS, WINDOW_SCALE
        ROWS = compute_rows_for_aspect(MAX_COLS, self.char_w, self.char_h, TARGET_ASPECT, FALLBACK_ROWS)
        COLS = MAX_COLS

        # If ROWS_OVERRIDE > 0, use it instead of aspect-derived rows
        if ROWS_OVERRIDE > 0:
            ROWS = int(ROWS_OVERRIDE)
            COLS = int(COLS)  # keep 80

        self.canvas_px_w, self.canvas_px_h = self.char_w*COLS, self.char_h*ROWS
        # Use a taller surface so the sidebar + HELP fit; center canvas vertically
        self.surface_h = max(self.canvas_px_h, SIDEBAR_MIN_HEIGHT) + UI_EXTRA_VERTICAL
        self.surface_w = self.canvas_px_w + SIDEBAR_W
        if AUTO_FIT_WINDOW:
            try:
                di = pygame.display.Info()
                if di.current_h and di.current_h > 0:
                    avail_h = di.current_h - 100     # title bar + taskbar margin
                    avail_w = di.current_w - 20
                    fit = min(1.0, avail_h / float(self.surface_h), avail_w / float(self.surface_w))
                    if fit < 1.0:
                        WINDOW_SCALE = max(0.5, fit)
            except Exception:
                pass
        self.win_w = int(self.surface_w * WINDOW_SCALE)
        self.win_h = int(self.surface_h * WINDOW_SCALE)
        self.screen  = pygame.display.set_mode((self.win_w, self.win_h))
        self.surface = pygame.Surface((self.surface_w, self.surface_h))
        self.canvas_offset_y = (self.surface_h - self.canvas_px_h) // 2


        self.canvas = ASCIICanvas(ROWS, COLS)
        # Start with darkest background by default
        self.canvas.clear(1.0, TEXT_LUMA)

        self.pal = PaletteManager()

        # T.LAPSE FLAGS
        self.tl = None
        self.tl_last_interval_ms = 0
        self.tl_exporting = False       # show "EXPORTING T.LAPSE..." while True
        self.tl_full_prompted = False   # avoid spamming the Y/N prompt when full   
        self._ensure_timelapse()
        self.tl_flash_until_ms = 0
        self.tl_last_sound_capture_ms = 0  # new: for rate-limiting sound-based capture
        self.action_label_rect = None

        # UI rects
        self.sidebar_rect = pygame.Rect(self.canvas_px_w, 0, SIDEBAR_W, self.surface.get_height())
        self.picker_rect  = pygame.Rect(self.canvas_px_w+UI_MARGIN, UI_MARGIN, PICKER_SIZE, PICKER_SIZE)
        self.palette_rect = pygame.Rect(self.canvas_px_w+UI_MARGIN, self.picker_rect.bottom+UI_MARGIN,
                                        SIDEBAR_W-2*UI_MARGIN, PALETTE_BAR_H)

        # Indicators
        self.ind_labels = ["HLIGHT","SOFT","PAINT","BLUR","LINE","LINEAA"]
        self.ind_rects = []

        # Buttons (paired)
        self.btn_w = (SIDEBAR_W - 3*UI_MARGIN)//2
        self.btn_h = 32
        row1_y = self.palette_rect.bottom + UI_MARGIN
        row2_y = row1_y + self.btn_h + UI_MARGIN
        left_x  = self.canvas_px_w + UI_MARGIN
        right_x = self.canvas_px_w + 2*UI_MARGIN + self.btn_w
        self.new_btn    = pygame.Rect(left_x,  row1_y, self.btn_w, self.btn_h)
        self.load_btn   = pygame.Rect(right_x, row1_y, self.btn_w, self.btn_h)
        self.import_btn = pygame.Rect(left_x,  row2_y, self.btn_w, self.btn_h)
        self.save_btn   = pygame.Rect(right_x, row2_y, self.btn_w, self.btn_h)
        self.hovered_btn = None; self.pressed_btn = None

        # Grid UI elements (below SAVE row)
        grid_top = row2_y + self.btn_h + UI_MARGIN
        checkbox_size = 18
        self.grid_checkbox_rect = pygame.Rect(self.canvas_px_w+UI_MARGIN, grid_top, checkbox_size, checkbox_size)
        self.grid_label_rect = pygame.Rect(self.grid_checkbox_rect.right+8, grid_top, 80, checkbox_size)

        y2 = grid_top + checkbox_size + 8
        btn_w_small, btn_h_small = 22, 22
        # Cols controls
        self.grid_cols_minus = pygame.Rect(self.canvas_px_w+UI_MARGIN, y2, btn_w_small, btn_h_small)
        self.grid_cols_plus  = pygame.Rect(self.grid_cols_minus.right+60, y2, btn_w_small, btn_h_small)
        self.grid_cols_val_rect = pygame.Rect(self.grid_cols_minus.right+8, y2, 50, btn_h_small)
        # Rows controls (next line)
        y3 = y2 + btn_h_small + 6
        self.grid_rows_minus = pygame.Rect(self.canvas_px_w+UI_MARGIN, y3, btn_w_small, btn_h_small)
        self.grid_rows_plus  = pygame.Rect(self.grid_rows_minus.right+60, y3, btn_w_small, btn_h_small)
        self.grid_rows_val_rect = pygame.Rect(self.grid_rows_minus.right+8, y3, 50, btn_h_small)

        # State
        self.current_value = 0.2       # start somewhat light to paint on dark bg
        self.brush_radius  = INITIAL_BRUSH_RADIUS
        self.brush_alpha   = 1.0
        self.soft_edge = False
        self.line_aa   = True

        # Modes: 'paint' | 'blur' | 'line' | 'hlight'
        self.mode = "paint"
        self.prev_mode = "paint"
        self.shift_blur = False
        self.shift_from_hlight = False
        self.pt1 = None

        # Grid state
        self.grid_enabled = True
        self.grid_cols = COLS
        self.grid_rows = ROWS

        # Help / links
        self.show_help = False
        self.help_click_zones = []
        self.cursor_support = False
        self.cursor_hidden = False
        try:
            self.cursor_arrow = pygame.cursors.Cursor(pygame.SYSTEM_CURSOR_ARROW)
            self.cursor_hand  = pygame.cursors.Cursor(pygame.SYSTEM_CURSOR_HAND)
            pygame.mouse.set_cursor(self.cursor_arrow)
            self.cursor_support = True
        except Exception:
            self.cursor_support = False

        # Undo & mouse
        self.undo_stack = deque(maxlen=UNDO_LIMIT)
        self.left_down=False; self.right_down=False; self.mid_down=False
        self.stroke_started=False

        self.clock = pygame.time.Clock(); self.running = True
        self.hover_cell = None

        # Picker caches
        self.picker_cells=[]; self.picker_sel_rect=None
        # For horizontal palette bar we store a mapping idx->rect
        self.palette_items=[]   # list of (rect, idx)
        self.palette_rect_map={}
        self.palette_sel_rect=None
        self.try_autoload_startup()

    def load_overlay_image(self):
        """Load an image from file and prepare it as a semi-transparent overlay."""
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk(); root.withdraw()
            path = filedialog.askopenfilename(
                title="Select Overlay Image",
                filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.bmp;*.webp")]
            )
            root.destroy()
            if not path:
                print("[OVERLAY] No image selected.")
                return
            img = pygame.image.load(path).convert_alpha()
            img = pygame.transform.smoothscale(img, (self.canvas_px_w, self.canvas_px_h))
            alpha_val = int(clamp01(OVERLAY_OPACITY) * 255)
            img.set_alpha(alpha_val)
            self.overlay_image = img
            self.overlay_visible = True
            print(f"[OVERLAY] Loaded: {path}")
        except Exception as e:
            print("Overlay load error:", e)


    def draw_overlay_if_needed(self, surf):
        """Draw the overlay image on top of the canvas if enabled."""
        if self.overlay_image and self.overlay_visible:
            oy = getattr(self, 'canvas_offset_y', 0)
            surf.blit(self.overlay_image, (0, oy))


    def draw_tl_progress_bar(self, surf):
        """
        Draw a single-line progress bar for timelapse:
        - placed below the tone sphere and above the palette bar
        - white baseline; red fill proportional to frames/max_frames
        """
        # We need anchors: the tone sphere rect and sidebar geometry
        if not hasattr(self, "picker_rect"):
            return

        # Compute bar rect: align to palette bar width if available, otherwise to sidebar width
        x = self.canvas_px_w + TL_BAR_MARGIN_X
        w = SIDEBAR_W - 2 * TL_BAR_MARGIN_X
        y = self.picker_rect.bottom + TL_BAR_GAP_FROM_SPHERE
        h = max(1, int(globals().get("TL_BAR_HEIGHT", 3)))

        # If your code already has a palette bar rect, reuse its x/w for perfect alignment
        pal_rect = getattr(self, "palbar_rect", None) or getattr(self, "palette_bar_rect", None)
        if pal_rect:
            x, w = pal_rect.x, pal_rect.w

        bar_rect = pygame.Rect(x, y, w, h)

        # Draw white baseline
        pygame.draw.rect(surf, WHITE, bar_rect, 0, border_radius=h//2)

        # Compute fill based on tl frames / max_frames
        self._ensure_timelapse()
        tl = getattr(self, "tl", None)
        if not tl:
            return

        max_frames = int(getattr(tl, "max_frames", globals().get("TIMELAPSE_MAX_FRAMES", 2000)))
        cur_frames = int(len(tl.frames))
        if max_frames <= 0 or cur_frames <= 0:
            return

        ratio = min(1.0, cur_frames / float(max_frames))
        fill_w = max(1, int(round(w * ratio)))

        fill_rect = pygame.Rect(x, y, fill_w, h)
        pygame.draw.rect(surf, RED, fill_rect, 0, border_radius=h//2)



    def _ensure_timelapse(self):
        """Make sure self.tl exists (lazy init)."""
        if getattr(self, "tl", None) is None:
            self.tl = TimelapseRecorder(TIMELAPSE_TARGET_COLS, TIMELAPSE_MAX_FRAMES)

    def draw_tlapse_indicator_below(self, surf, anchor_rect):
        if not anchor_rect:
            return
        self._ensure_timelapse()
        tl = getattr(self, "tl", None)
        if not tl:
            return

        # pick label and visibility
        if self.tl_exporting:
            label_text = "EXPORTING T.LAPSE..."
            always_on = True
            color = RED
        elif tl.enabled:
            label_text = "T.LAPSE ON"
            always_on = False
            color = RED
        else:
            return  # off -> nothing

        ticks = pygame.time.get_ticks()
        blink_on = ((ticks // 400) % 2) == 0
        if always_on or ticks < getattr(self, "tl_flash_until_ms", 0):
            blink_on = True
        if not blink_on:
            return

        label_surf = self.font_small.render(label_text, True, color)
        # align left to match your action label (you disse que preferiu left)
        x = anchor_rect.left
        y = anchor_rect.bottom + 4
        surf.blit(label_surf, (x, y))



    # ---------- helpers ----------
    def tl_poll_interval(self):
        """Capture frames at a fixed rate while mouse is down (interval mode)."""
        self._ensure_timelapse()
        tl = getattr(self, "tl", None)
        if not (tl and tl.enabled):
            return
        mode = globals().get("TIMELAPSE_CAPTURE_MODE", 0)
        if mode not in (TL_CAPTURE_INTERVAL, TL_CAPTURE_BOTH):
            return
        if not getattr(self, "stroke_started", False):
            return

        now = pygame.time.get_ticks()
        gap = globals().get("TL_INTERVAL_MS", 80)
        last = getattr(self, "tl_last_interval_ms", 0)
        if (now - last) >= gap:
            tl.capture(self.canvas, self.pal)
            self.tl_last_interval_ms = now
            self.tl_flash_until_ms = now + 300  # flash curtinho para micro-capturas
            self.tl_prompt_export_if_full() 

    def tl_export_via_dialog(self) -> bool:
        """Ask where to save and export GIF. Returns True on success."""
        self._ensure_timelapse()
        tl = getattr(self, "tl", None)
        if not (tl and tl.frames):
            print("[TL] Nothing to export.")
            return False

        # choose filename
        out_path = None
        dialog_ok = False
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk(); root.withdraw()
            SAVES_DIR.mkdir(parents=True, exist_ok=True)
            out_path = filedialog.asksaveasfilename(
                title="Export Timelapse GIF",
                defaultextension=".gif",
                filetypes=[("GIF", "*.gif")],
                initialdir=str(SAVES_DIR),
                initialfile=f"timelapse_{timestamp()}.gif"
            )
            root.destroy()
            dialog_ok = True
        except Exception as e:
            print("Save dialog error:", e)

        if dialog_ok and not out_path:
            print("[TL] Export cancelled.")
            return False
        if not out_path:       # no dialog available: save into the saves folder
            SAVES_DIR.mkdir(parents=True, exist_ok=True)
            out_path = str(SAVES_DIR / f"timelapse_{timestamp()}.gif")

        # export with UI state
        prev_enabled = tl.enabled
        self.tl_exporting = True
        try:
            # pause recording during export to avoid race
            tl.enabled = False
            ok = tl.export_gif(out_path, self.font, self.char_w, self.char_h)
        finally:
            self.tl_exporting = False
            tl.enabled = prev_enabled

        if ok:
            try: open_folder(os.path.dirname(out_path) or ".")
            except Exception: pass
        return ok


    def tl_prompt_export_if_full(self):
        """
        If tl.frames reached tl.max_frames, prompt Y/N to export and then clear cache.
        Guarded by self.tl_full_prompted to avoid repeated prompts.
        """
        self._ensure_timelapse()
        tl = getattr(self, "tl", None)
        if not (tl and tl.enabled):
            return
        if self.tl_full_prompted:
            return

        max_frames = int(getattr(tl, "max_frames", 0))
        if max_frames <= 0:
            return
        if len(tl.frames) < max_frames:
            return

        # We've just hit the limit
        self.tl_full_prompted = True
        user_yes = False
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk(); root.withdraw()
            user_yes = messagebox.askyesno(
                "Timelapse full",
                "Timelapse frame limit reached.\nDo you want to export the GIF now?"
            )
            root.destroy()
        except Exception as e:
            print("Prompt error:", e)

        if user_yes:
            if self.tl_export_via_dialog():
                # clear cache after successful export
                tl.reset()
                # optional: keep recording ON to start fresh
                tl.enabled = True
                print("[TL] Cache cleared after export.")
        else:
            print("[TL] Limit reached. Recording paused until you clear or export.")
            tl.enabled = False  # pause to avoid silent misses

        # allow prompting again later (when user re-enables or after reset)
        self.tl_full_prompted = False


    def tl_maybe_capture(self, reason: str):
        """Capture a timelapse frame based on the global capture mode and reason."""
        self._ensure_timelapse()
        tl = getattr(self, "tl", None)
        if not (tl and tl.enabled):
            return

        mode = globals().get("TIMELAPSE_CAPTURE_MODE", 0)
        now = pygame.time.get_ticks()

        if reason == "sound":
            # Accept legacy TL_CAPTURE_SOUND and also map 'sound' to interval-style captures.
            legacy_sound = globals().get("TL_CAPTURE_SOUND", None)
            if (mode not in (legacy_sound, globals().get("TL_CAPTURE_INTERVAL"), globals().get("TL_CAPTURE_BOTH"))):
                return
            gap = globals().get("TL_INTERVAL_MS", 80)  # reuse same throttle as interval mode
            last = getattr(self, "tl_last_interval_ms", 0)
            if gap and (now - last) < gap:
                return
            tl.capture(self.canvas, self.pal)
            self.tl_last_interval_ms = now
            self.tl_flash_until_ms = now + 300
            return

        if reason == "stroke":
            if mode not in (globals().get("TL_CAPTURE_STROKE"), globals().get("TL_CAPTURE_BOTH")):
                return
            tl.capture(self.canvas, self.pal)
            self.tl_flash_until_ms = now + 900


    def sample_tone_from_canvas(self, cell):
        """Lê o tom da célula e aplica em current_value."""
        if not cell: 
            return
        x, y = cell
        if 0 <= x < self.canvas.cols and 0 <= y < self.canvas.rows:
            v = float(self.canvas.buf[y, x])
            self.current_value = clamp01(v)

    def push_undo(self): self.undo_stack.append((self.canvas.buf.copy(), self.canvas.col.copy()))
    def begin_stroke_if_needed(self):
        if not self.stroke_started:
            self.push_undo(); self.stroke_started=True
            # allow immediate first interval capture
            if globals().get("TIMELAPSE_CAPTURE_MODE", 0) in (TL_CAPTURE_INTERVAL, TL_CAPTURE_BOTH):
                self.tl_last_interval_ms = pygame.time.get_ticks() - globals().get("TL_INTERVAL_MS", 80)

    def current_action_string(self):
        # 1) ALT = Color picker (mostra enquanto ALT estiver pressionado)
        mods = pygame.key.get_mods()
        alt  = bool(mods & pygame.KMOD_ALT)
        if alt and (self.hover_cell is not None):
            return "COLOR PICKER"

        # 2) Linha tem prioridade
        if self.mode == "line":
            return "LINE"

        # 3) HLIGHT (com borracha no RMB)
        if self.mode == "hlight":
            if self.right_down:
                return "ERASE HLIGHT"
            return "HLIGHT"

        # 4) Blur temporário com SHIFT ou modo BLUR
        blur_now = (self.mode == "blur") or (self.mode == "paint" and self.shift_blur)
        if blur_now:
            return "BLUR"

        # 5) Botões do mouse
        if self.left_down:
            return "PAINT"
        if self.right_down:
            return "ERASE"
        if self.mid_down:
            ctrl = bool(mods & pygame.KMOD_CTRL)
            return "DARKEN" if ctrl else "LIGHTEN"

        # 6) Idle -> mostra modo base
        return "PAINT"


    def _release_mouse_state(self):
        """Call after a blocking tkinter dialog: the dialog swallows the mouse-up, so the
        buttons would stay 'held' and the app would keep painting on its own."""
        self.left_down = self.right_down = self.mid_down = False
        self.pressed_btn = None
        self.snd_last_cell = None
        self.stroke_started = False

    def end_stroke(self):
        was_stroke = self.stroke_started
        self.stroke_started = False
        self._ensure_timelapse()
        tl = getattr(self, "tl", None)
        if not was_stroke:
            return      # a plain click (button, picker...) is not a stroke: no frames, no pause injection
        if not (tl and tl.enabled):
            # even if TL is off, reset interval timer for safety
            self.tl_last_interval_ms = 0
            return

        # 1) Record the final state of the stroke (skipped when nothing changed since the last frame)
        n_before = len(tl.frames)
        tl.capture(self.canvas, self.pal)
        did_capture = len(tl.frames) > n_before

        # 2) Dynamic pause injection (optional)
        if globals().get("DYNAMIC_TLAPSE", False):
            n = int(globals().get("TL_MOUSE_RELEASE_INJECT_FRAMES", 0))
            if n > 0:
                tl.inject_repeat_last(n)

        self.tl_prompt_export_if_full() 

        # 3) Visual feedback flash (longer on stroke end)
        now = pygame.time.get_ticks()
        self.tl_flash_until_ms = now + (900 if did_capture else 600)

        # 4) Reset interval timer so next stroke can start fresh
        self.tl_last_interval_ms = 0


    def _update_cursor_visibility(self, mx, my):
        """Esconde o cursor somente sobre o canvas (se habilitado)."""
        if not HIDE_CURSOR_OVER_CANVAS:
            if self.cursor_hidden:
                try: pygame.mouse.set_visible(True)
                except Exception: pass
                self.cursor_hidden = False
            return

        oy = getattr(self, 'canvas_offset_y', 0)
        in_canvas = (0 <= mx < self.canvas_px_w) and (oy <= my < oy + self.canvas_px_h)
        # Durante HELP, mantemos o cursor visível (links clicáveis)
        want_hidden = in_canvas and (not self.show_help)

        if want_hidden and not self.cursor_hidden:
            try: pygame.mouse.set_visible(False)
            except Exception: pass
            self.cursor_hidden = True
        elif (not want_hidden) and self.cursor_hidden:
            try: pygame.mouse.set_visible(True)
            except Exception: pass
            self.cursor_hidden = False


    def undo(self):
        if self.undo_stack:
            buf,col=self.undo_stack.pop()
            self.canvas.buf[:,:]=buf; self.canvas.col[:,:]=col
    def mouse_to_cell(self,mx,my):
        oy = getattr(self, 'canvas_offset_y', 0)
        if (mx < 0) or (mx >= self.canvas_px_w) or (my < oy) or (my >= oy + self.canvas_px_h):
            return None
        return int(mx // self.char_w), int((my - oy) // self.char_h)
    def present_surface(self):
        if WINDOW_SCALE!=1.0:
            self.screen.blit(pygame.transform.smoothscale(self.surface,(self.win_w,self.win_h)),(0,0))
        else:
            self.screen.blit(self.surface,(0,0))
        pygame.display.flip()

    # ---------- IO ----------
    def try_autoload_startup(self, names=("startup.txt", "STARTUP.TXT")) -> bool:
        """If a startup ASCII project exists next to the app, load it on launch."""
        for fname in names:
            found = find_asset(fname)
            path = str(found) if found else None
            if path and os.path.isfile(path):
                try:
                    self.load_txt_into_canvas(path)
                    self.undo_stack.clear()  # fresh start (no undo before startup)
                    print(f"[STARTUP] Loaded: {path}")
                    return True
                except Exception as e:
                    print(f"[STARTUP] Failed to load {path}: {e}")
                    return False
        # Optional: be quiet if you prefer no console noise
        print("[STARTUP] No startup.txt found.")
        return False


    def build_ascii_lines(self):
        n=self.pal.n-1; lines=[]
        for r in range(ROWS):
            row=(self.canvas.buf[r,:]*n).round().clip(0,n).astype(np.int32)
            lines.append("".join(self.pal.chars[i] for i in row))
        return lines
    def save_txt(self,path):
        with open(path,"w",encoding="utf-8") as f:
            f.write("\n".join(self.build_ascii_lines()))
    def save_png(self,path):
        temp=pygame.Surface((self.canvas_px_w,self.canvas_px_h)); temp.fill(BLACK)
        n=self.pal.n-1
        for r in range(ROWS):
            row=(self.canvas.buf[r,:]*n).round().clip(0,n).astype(np.int32)
            for c in range(COLS):
                ch=self.pal.chars[row[c]]
                if ch==' ': continue
                col=luma_to_rgb(self.canvas.col[r,c])
                temp.blit(self.glyphs.get(ch,col),(c*self.char_w,r*self.char_h))
        pygame.image.save(temp,path)
    def quick_save(self):
        SAVES_DIR.mkdir(parents=True, exist_ok=True)
        base=str(SAVES_DIR / f"ascii_{timestamp()}")
        self.save_txt(base+".txt"); self.save_png(base+".png"); open_folder(str(SAVES_DIR))
    def load_txt_into_canvas(self,path):
        if not os.path.exists(path): return
        with open(path,"r",encoding="utf-8") as f:
            lines=f.read().splitlines()
        char_to_idx={ch:i for i,ch in enumerate(self.pal.chars)}
        dark_idx=self.pal.n-1                        # last palette char = space = darkest tone
        dark_val=self.pal.value_from_idx(dark_idx)
        self.push_undo()
        self.canvas.buf[:,:]=dark_val                # whatever the file does not cover stays empty
        rows=min(ROWS,len(lines))
        for r in range(rows):
            line=lines[r].replace("\u00a0"," "); cols=min(COLS,len(line))
            for c in range(cols):
                idx=char_to_idx.get(line[c],dark_idx)    # char not in the palette -> empty
                self.canvas.buf[r,c]=self.pal.value_from_idx(idx)
        self.canvas.col[:,:]=TEXT_LUMA
    def import_image_to_canvas(self,path):
        try:
            img=pygame.image.load(path).convert()
            small=pygame.transform.smoothscale(img,(COLS,ROWS))
            arr=pygame.surfarray.pixels3d(small)
            # y in [0..1]: 0=black(dark), 1=white(light) -> tone = 1 - y
            y=(0.2126*arr[:,:,0]+0.7152*arr[:,:,1]+0.0722*arr[:,:,2])/255.0
            self.push_undo()
            self.canvas.buf[:,:]=np.clip((1.0 - y).T,0.0,1.0); del arr
            self.canvas.col[:,:]=TEXT_LUMA
        except Exception as e: print("Import error:",e)

    # ---------- COPY / EXPORT ----------
    def compute_content_bbox(self):
        """Return bbox (r0,r1,c0,c1) inclusive-exclusive of non-space chars. If none, return full canvas."""
        n = self.pal.n - 1
        idx = np.rint(np.clip(self.canvas.buf * n, 0, n)).astype(np.int32)
        # map to "is not space"
        mask = ~self.pal.is_space[idx]
        if not mask.any():
            return (0, self.canvas.rows, 0, self.canvas.cols)
        rows = np.where(mask.any(axis=1))[0]
        cols = np.where(mask.any(axis=0))[0]
        r0, r1 = int(rows[0]), int(rows[-1])+1
        c0, c1 = int(cols[0]), int(cols[-1])+1
        return (r0, r1, c0, c1)

    def expand_bbox_to_grid(self, r0, r1, c0, c1):
        """Snap bbox to nearest grid cell boundaries (if grid enabled)."""
        if not self.grid_enabled: return (r0, r1, c0, c1)
        gc = max(GRID_MIN, min(GRID_MAX, self.grid_cols))
        gr = max(GRID_MIN, min(GRID_MAX, self.grid_rows))
        # compute grid boundaries
        gx = [int(math.floor(i * self.canvas.cols / gc)) for i in range(gc+1)]
        gy = [int(math.floor(i * self.canvas.rows / gr)) for i in range(gr+1)]
        # snap
        c0s = max(0, max([x for x in gx if x <= c0] or [0]))
        c1s = min(self.canvas.cols, min([x for x in gx if x >= c1] or [self.canvas.cols]))
        r0s = max(0, max([y for y in gy if y <= r0] or [0]))
        r1s = min(self.canvas.rows, min([y for y in gy if y >= r1] or [self.canvas.rows]))
        # ensure non-empty
        if c1s <= c0s: c0s, c1s = c0, c1
        if r1s <= r0s: r0s, r1s = r0, r1
        return (r0s, r1s, c0s, c1s)

    def copy_current_as(self, mode="markdown"):
        """Copy current canvas as text (markdown/plain/html)."""
        lines = ascii_lines_from_buf(self.canvas.buf, self.pal.chars)
        lines = maybe_nbsp(lines, COPY_USE_NBSP and mode != "markdown")  # md preserves spaces
        if mode == "markdown":
            txt = wrap_as_markdown(lines)
        elif mode == "html":
            txt = wrap_as_html_pre(lines)
        else:
            txt = "\n".join(lines)
        ok = copy_to_clipboard(txt)
        if ok: print("[COPY] ok:", mode)
        else:  print("[COPY] failed:", mode)

    def copy_fit_cols(self, target_cols=DEFAULT_COPY_FIT_COLS, target_rows=None, mode="markdown", row_scale: float = EXPORT_ROW_SCALE):
        """Resample canvas to fit width after cropping to bbox, or grid-aligned bbox if grid is enabled."""
        if target_cols < 4: target_cols = 4
        r0, r1, c0, c1 = self.compute_content_bbox()
        r0, r1, c0, c1 = self.expand_bbox_to_grid(r0, r1, c0, c1)
        src = self.canvas.buf[r0:r1, c0:c1]
        if src.size == 0:
            src = self.canvas.buf  # fallback
        src_h, src_w = src.shape
        if target_rows is None:
            base_rows = src_h * (target_cols / max(1, src_w))
            target_rows = max(2, int(round(base_rows * row_scale)))
        buf_small = resize_tone_buffer_bilinear(src, target_rows, target_cols)
        lines = ascii_lines_from_buf(buf_small, self.pal.chars)
        lines = maybe_nbsp(lines, COPY_USE_NBSP and mode != "markdown")
        if mode == "markdown": txt = wrap_as_markdown(lines)
        elif mode == "html":   txt = wrap_as_html_pre(lines)
        else:                  txt = "\n".join(lines)
        ok = copy_to_clipboard(txt)
        if ok:
            print(f"[COPY FIT] crop=({c0}:{c1}, {r0}:{r1}) -> {target_cols}x{target_rows} -> {mode}")
        else:
            print("[COPY FIT] failed")

    # ---------- AUDIO ----------
    def play_brush_tick(self):
        self.tl_maybe_capture("sound")
        self.tl_prompt_export_if_full() 
        if not (self.sound_enabled and self.wav_variants and self.brush_channel): return
        now=pygame.time.get_ticks()
        maxtime=0 if (now-self.last_tick_ms>SOUND_FULL_WINDOW_MS) else SOUND_CHOP_MS
        snd=random.choice(self.wav_variants)
        try: self.brush_channel.play(snd, maxtime=maxtime); self.last_tick_ms=now
        except Exception: pass

    def play_ui_click(self):
        self.tl_maybe_capture("sound")
        self.tl_prompt_export_if_full() 
        self.play_brush_tick()

    def _play_full_once_release(self):
        self.tl_maybe_capture("sound")
        self.tl_prompt_export_if_full() 
        ## """Toca um sample FULL (sem maxtime) ao encerrar o stroke, se habilitado."""
        if not SND_PLAY_FULL_ON_RELEASE: 
            return
        if not (self.sound_enabled and self.wav_variants):
            return
        try:
            snd = random.choice(self.wav_variants)  # FULL
            # escolhe um canal livre; se ambos ocupados, usa ping-pong atual
            chA = getattr(self, "brush_channel", None)
            chB = getattr(self, "brush_channel2", None)
            ch = None
            if chA and (not chA.get_busy()): ch = chA
            elif chB and (not chB.get_busy()): ch = chB
            else:
                # usa o canal "da vez" sem crossfade; é um tail “de encerramento”
                if getattr(self, "active_brush_ch", 0) == 0:
                    ch = chA or chB
                else:
                    ch = chB or chA
            if ch:
                    ch.set_volume(SND_OUTPUT_VOLUME)
                    ch.play(snd, loops=0, maxtime=0, fade_ms=0)
        except Exception:
            pass


    def _pick_channels_for_alternate(self):
        """Return (curr, other) where curr is the channel we will play now and
        other is the opposite one. Toggle self.active_brush_ch."""
        if not SND_USE_TWO_CHANNELS or self.brush_channel2 is None:
            return (self.brush_channel, self.brush_channel)
        if self.active_brush_ch == 0:
            curr, other = self.brush_channel, self.brush_channel2
            self.active_brush_ch = 1
        else:
            curr, other = self.brush_channel2, self.brush_channel
            self.active_brush_ch = 0
        return (curr, other)

    def _brush_channels(self):
        """Return (prev, next) channels and toggle active."""
        if not SND_USE_TWO_CHANNELS or self.brush_channel2 is None:
            return (self.brush_channel, self.brush_channel)
        # ping-pong
        if self.active_brush_ch == 0:
            prev, nxt = self.brush_channel2, self.brush_channel
            self.active_brush_ch = 1
        else:
            prev, nxt = self.brush_channel, self.brush_channel2
            self.active_brush_ch = 0
        return (prev, nxt)


    def play_brush_cell_trigger(self, cell):
        """Play short brush tick, gated by cell change + min interval."""
        if not (self.sound_enabled and self.wav_variants and self.brush_channel):
            return

        # Som só com raio 1 (se quiser, desative via SND_REQUIRE_RADIUS1=False)
        if SND_REQUIRE_RADIUS1 and getattr(self, "brush_radius", 1) != 1:
            return

        # Accepsts LMB, RMB, MMB
        if not (self.left_down or self.right_down or self.mid_down):
            return

        now = pygame.time.get_ticks()
        if SND_CELL_TRIGGER_ONLY and cell == self.snd_last_cell:
            return
        if now - self.snd_last_ts < SND_MIN_INTERVAL_MS:
            return

        # compute gap since last sound
        gap = now - self.snd_last_ts
        self.snd_last_cell = cell
        self.snd_last_ts   = now

        # full sound if gap > SOUND_FULL_WINDOW_MS, else chop it
        maxtime = 0 if gap > SOUND_FULL_WINDOW_MS else SOUND_CHOP_MS
        fadein  = SND_FADEIN_MS if maxtime else 0  # fade-in só faz sentido no chop

        # Here is where it actually plays
        try:
            # sempre toca o sample "full" (sem maxtime) e alterna os canais
            snd = random.choice(self.wav_variants)
            curr_ch, other_ch = self._pick_channels_for_alternate()

            # se o canal atual ainda está tocando, faz um fade-out curto nele
            try:
                if curr_ch.get_busy():
                    curr_ch.fadeout(SND_OVERLAP_FADE_MS)
            except Exception:
                pass

            # ducking no outro canal enquanto sobrepõe
            try:
                if other_ch.get_busy():
                    other_ch.set_volume(SND_OUTPUT_VOLUME * SND_DUCKING)
            except Exception:
                pass

            # toca o novo tick com fade-in curto (sem maxtime => deixa tocar até o fim)
            curr_ch.set_volume(SND_OUTPUT_VOLUME)
            curr_ch.play(snd, maxtime=0, fade_ms=SND_FADEIN_MS)

        except Exception:
            pass



    # ---------- UI ----------
    def draw_button(self,surf,rect,label,hovered=False,pressed=False,enabled=True):
        fill=GREY10
        if hovered: fill=HOVER_FILL
        if pressed: fill=PRESS_FILL
        pygame.draw.rect(surf,fill,rect,0,border_radius=5)
        pygame.draw.rect(surf,WHITE if enabled else GREY,rect,2,border_radius=5)
        color=WHITE if enabled else GREY
        t=self.font.render(label,True,color)
        surf.blit(t,(rect.x+(rect.w-t.get_width())//2, rect.y+(rect.h-t.get_height())//2))

    def _indicator_box_size(self):
        ts=self.font_small.render("LINEAA",True,WHITE)
        return ts.get_width()+2*IND_PAD_X, ts.get_height()+2*IND_PAD_Y

    def draw_mode_stack(self,surf):
        blur_effective=(self.mode=="blur") or (self.mode=="paint" and self.shift_blur)
        states={"HLIGHT":(self.mode=="hlight"),
                "SOFT":self.soft_edge,
                "PAINT":(self.mode=="paint" and not self.shift_blur),
                "BLUR":blur_effective,
                "LINE":(self.mode=="line"),
                "LINEAA":self.line_aa}
        w_box,h_box=self._indicator_box_size(); self.ind_rects.clear()
        right_edge=self.canvas_px_w+SIDEBAR_W-UI_MARGIN; y=self.picker_rect.top
        for label in self.ind_labels:
            if states[label]:
                if label=="BLUR": tcol=RED
                elif label=="LINE": tcol=CYAN
                elif label=="HLIGHT": tcol=HL_RGB
                else: tcol=WHITE
            else: tcol=GREY50
            ts=self.font_small.render(label,True,tcol)
            x=right_edge-w_box; rect=pygame.Rect(x,y,w_box,h_box)
            pygame.draw.rect(surf,GREY10,rect,0,border_radius=4)
            border_col = RED if (label=="BLUR" and states[label]) else \
                         CYAN if (label=="LINE" and states[label]) else \
                         (WHITE if states[label] else GREY50)
            pygame.draw.rect(surf,border_col,rect,1,border_radius=4)
            surf.blit(ts,(rect.x+(rect.w-ts.get_width())//2, rect.y+(rect.h-ts.get_height())//2))
            self.ind_rects.append(rect); y+=h_box+IND_GAP_Y

    def draw_grid_panel(self, surf):
        # Checkbox only (G toggles as well). Grid cells always match canvas.
        pygame.draw.rect(surf, WHITE, self.grid_checkbox_rect, 1)
        if self.grid_enabled:
            inner = self.grid_checkbox_rect.inflate(-6, -6)
            pygame.draw.rect(surf, WHITE, inner, 0)
        label = self.font.render('GRID (cells)', True, WHITE if self.grid_enabled else GREY)
        surf.blit(label, (self.grid_label_rect.x, self.grid_label_rect.y))

        # --- coords indicator (cell under cursor) ---
        # show 1-based indices; fallback to '-' when outside
        if getattr(self, "hover_cell", None):
            cx, cy = self.hover_cell
            txt = f"x: {cx+1:>3}   y: {cy+1:>3}"
        else:
            txt = "x:  -     y:  -"

        # pick a small or regular font
        f_coords = getattr(self, "font_small", self.font)
        coord_surf = f_coords.render(txt, True, GREY)
        surf.blit(coord_surf, (self.grid_label_rect.x, self.grid_label_rect.bottom + 6))

        # --- action (always-on, in blue) ---
        action_txt = self.current_action_string()
        act_surf = self.font_small.render(action_txt, True, CYAN)
        ax = self.canvas_px_w + UI_MARGIN
        ay = self.grid_label_rect.bottom + 6 + self.font_small.get_height() + 5  # abaixo das coords
        act_rect = act_surf.get_rect(topleft=(ax, ay))
        surf.blit(act_surf, act_rect.topleft)

        self.action_label_rect = act_rect
        self.draw_tlapse_indicator_below(surf, act_rect)

    def draw_grid_overlay(self, surf):
        if not self.grid_enabled:
            return
        # Draw a subtle per-cell grid aligned to character cells
        if GRID_MATCH_CELLS:
            gc, gr = self.canvas.cols, self.canvas.rows
            oy = getattr(self, 'canvas_offset_y', 0)
            # vertical lines (skip outer border to keep it subtle)
            for i in range(1, gc):
                x = i * self.char_w
                pygame.draw.aaline(surf, GRID_COL, (x, oy), (x, oy + self.canvas_px_h))
            # horizontal lines
            for j in range(1, gr):
                y = oy + j * self.char_h
                pygame.draw.aaline(surf, GRID_COL, (0, y), (self.canvas_px_w, y))
        else:
            # Legacy evenly-spaced grid based on user-set cols/rows
            gc = max(GRID_MIN, min(GRID_MAX, self.grid_cols))
            gr = max(GRID_MIN, min(GRID_MAX, self.grid_rows))
            oy = getattr(self, 'canvas_offset_y', 0)
            for i in range(1, gc):
                x = int(i * self.canvas_px_w / gc)
                pygame.draw.line(surf, GRID_COL, (x, oy), (x, oy + self.canvas_px_h), 1)
            for j in range(1, gr):
                y = oy + int(j * self.canvas_px_h / gr)
                pygame.draw.line(surf, GRID_COL, (0, y), (self.canvas_px_w, y), 1)

    def draw_spherical_picker(self,surf):
        pygame.draw.rect(surf,WHITE,self.picker_rect,1)
        cx=self.picker_rect.centerx
        cy=self.picker_rect.centery - PICKER_Y_OFFSET_LINES * self.char_h
        R=(self.picker_rect.width - 4)//2
        # Light vector (upper-left)
        Lx, Ly, Lz = -0.58, -0.58, 0.58
        step_x=max(1,self.char_w//2); step_y=self.char_h
        self.picker_cells.clear()
        for y in range(self.picker_rect.top+2, self.picker_rect.bottom-2, step_y):
            for x in range(self.picker_rect.left+2, self.picker_rect.right-2, step_x):
                nx=(x-cx)/R; ny=(y-cy)/R
                d2=nx*nx+ny*ny
                if d2<=1.0:
                    nz=math.sqrt(max(0.0,1.0-d2))
                    diffuse=max(0.0, float(nx*Lx + ny*Ly + nz*Lz))  # 0..1
                    # Brighter => lighter tone (low value)
                    t_disp = clamp01(1.0 - diffuse)    # 0 light .. 1 dark
                    ch=self.pal.char_from_value(t_disp)
                    surf.blit(self.glyphs.get(ch,GREY_TEXT),(x,y))
                    self.picker_cells.append((pygame.Rect(x,y,self.char_w,self.char_h), t_disp))
        # selection rect nearest to current tone
        if self.picker_cells:
            self.picker_sel_rect = min(self.picker_cells, key=lambda p: abs(p[1]-self.current_value))[0]
        if self.picker_sel_rect:
            pygame.draw.rect(surf, CYAN, self.picker_sel_rect, 2)


    # ---- horizontal palette bar (DISPLAY ONLY order can be reversed) ----
    def draw_palette_bar(self,surf):
        pygame.draw.rect(surf,WHITE,self.palette_rect,1)
        n=self.pal.n
        inner_w=self.palette_rect.width-4
        left=self.palette_rect.left+2
        center_y=self.palette_rect.centery
        slot=inner_w/max(1,n)
        self.palette_items.clear(); self.palette_rect_map.clear()
        # Decide display order: UI index -> underlying glyph index
        if PALETTE_BAR_DARK_TO_LIGHT:
            order_indices = list(range(n-1, -1, -1))   # display dark->light
        else:
            order_indices = list(range(0, n))          # display light->dark
        # Draw in display order, but remember underlying idx
        for ui_i, idx in enumerate(order_indices):
            ch=self.pal.chars[idx]
            cx=left+(ui_i+0.5)*slot
            x=int(cx - self.char_w/2); y=int(center_y - self.char_h/2)
            rect=pygame.Rect(x,y,self.char_w,self.char_h)
            self.palette_items.append((rect, idx))
            self.palette_rect_map[idx]=rect
            surf.blit(self.glyphs.get(ch,GREY_TEXT),(x,y))
        # Selection rectangle for current underlying idx
        idx=self.pal.idx_from_value(self.current_value)
        sel_rect=self.palette_rect_map.get(idx,None)
        if sel_rect:
            self.palette_sel_rect=sel_rect
            pygame.draw.rect(surf,CYAN,self.palette_sel_rect,2)

    def draw_tool_info(self,surf):
        ch=self.pal.char_from_value(self.current_value)
        infos=[
            f"PAL: {self.pal.display_name}",
            f"TONE: {self.current_value:.2f}",
            f"CHAR: '{ch}'",
            f"RADIUS: {self.brush_radius}",
            f"OPACITY: {self.brush_alpha:.2f}",
            f"SOUND: {'ON' if (self.sound_enabled and self.wav_variants) else 'OFF'}",
            f"SND FILE: {self.wav_name}",
            f"COPY: {COPY_DEFAULT_MODE.upper()}",
            f"NBSP: {'ON' if COPY_USE_NBSP else 'OFF'}",
        ]
        
        # --- Processing indicator (centered version) ---
        if self.processing_active:
            if (self.processing_ticks // 30) % 2 == 0:
                msg = self.font.render("PROCESSING...", True, CYAN)
                x = (self.surface.get_width() - msg.get_width()) // 2
                y = (self.surface.get_height() - msg.get_height()) // 2
                surf.blit(msg, (x, y))

        y=self.grid_rows_val_rect.bottom+UI_MARGIN
        for s in infos:
            surf.blit(self.font.render(s,True,GREY),(self.canvas_px_w+UI_MARGIN,y))
            y+=self.char_h+2
        # Bottom-right help hint
        hint = self.font_small.render("SHIFT+H for HELP", True, GREY_TEXT)
        hx = self.canvas_px_w + SIDEBAR_W - UI_MARGIN - hint.get_width()
        hy = self.surface.get_height() - UI_MARGIN - hint.get_height()
        surf.blit(hint, (hx, hy))
        ver = self.font_small.render(f"v{VERSION}", True, GREY_TEXT)
        surf.blit(ver, (self.canvas_px_w + UI_MARGIN, hy))

    # ---- help ----
    def draw_help_overlay(self,surf,mx,my,ticks):
        if not self.show_help: return
        self.help_click_zones.clear()
        panel=pygame.Surface((SIDEBAR_W, self.surface.get_height())); panel.fill(BLACK)
        surf.blit(panel,(self.canvas_px_w,0))
        items=[
            ("LEFT CLK","PAINT"),
            ("RIGHT CLK","ERASE"),
            ("MID CLK","LIGHTEN"),
            ("ALT","COLOR PICKER"),
            ("CTRL+MID","DARKEN"),
            ("H","HIGHLIGHT MODE"),
            ("SHFT","BLUR BRUSH"),
            ("SHFT+H","HELP"),
            ("ESC","EXIT HELP"),
            ("T","T.LAPSE ON/OFF"),
            ("CTRL+T","WIPE T.LAPSE"),
            ("CTRL+E","EXPORT T.LAPSE"),
            ("CTRL+Q","QUIT"),
            ("CTRL+S","SAVE TXT+PNG"),
            ("CTRL+C","COPY (MARKDOWN)"),
            ## ("CTRL+SHFT+C","COPY (BBOX)"),
            ("CTRL+ALT+C","COPY(HTML)"),
            ## ("CTRL+SHFT+N","NBSP ON/OFF"),
            ("O","OVERLAY SHOW/HIDE"),
            ("SHIFT+O","LOAD OVERLAY IMAGE"),
            ("X","LIGHT/DARK"),
            ("I","INVERT PALETTE"),
            ("S","SOFTEDGE ON/OFF"),
            ("SHFT+S","SOUND ON/OFF"),
            ("SHFT+1<->0","PALETTE"),
            ("1<->0","TONE"),
            ("- | =","TONE UP|DOWN"),
            ("CTRL+WHEEL","TONE"),
            ("[", "RADIUS DEC"),
            ("]", "RADIUS INC"),
            ("SHFT+WHEEL","OPACITY"),
            ("B","BLUR MODE"),
            ("L","LINE MODE"),
            ("A","LINE AA ON/OFF"),
            ("G","GRID ON/OFF"),
        ]
        x_cmd=self.canvas_px_w+UI_MARGIN - HELP_BLOCK_XOFFSET
        x_desc=x_cmd+HELP_DESC_SHIFT-3*self.char_w
        y=UI_MARGIN
        title=self.font.render("SHORTCUTS",True,WHITE)
        surf.blit(title,(x_cmd,y)); y+=self.char_h+4
        for cmd,desc in items:
            tcmd=self.font.render(cmd,True,WHITE)
            tdesc=self.font.render(desc,True,GREY_DESC)
            surf.blit(tcmd,(x_cmd,y)); surf.blit(tdesc,(x_desc,y))
            y+=self.char_h+2
        # credits + links
        cx=self.canvas_px_w+SIDEBAR_W//2
        insp1="Inspired by the Art of"
        link_vagon="@vagonparovoz"
        t1=self.font.render(insp1,True,GREY_TEXT)
        t_vagon=self.font.render(link_vagon,True,CYAN)
        link_me="@msouza3d"; t_me=self.font.render(link_me,True,CYAN)
        tag_suffix=f" - 2025 - V{VERSION}"; t_suffix=self.font.render(tag_suffix,True,GREY_TEXT)
        k1="BUY ME A COFFEE :"; k2="https://ko-fi.com/msouza3d"
        tk1=self.font.render(k1,True,GREY_TEXT); tk2=self.font.render(k2,True,CYAN)
        tag_y=self.surface.get_height()-UI_MARGIN - t_me.get_height()
        total_tag_w=t_me.get_width()+t_suffix.get_width(); tag_x=cx-total_tag_w//2
        insp_y_top=(tag_y - 6 - t_vagon.get_height() - 2*self.char_h
                    - tk1.get_height() - tk2.get_height() - 4 - t1.get_height())
        surf.blit(t1,(cx - t1.get_width()//2, insp_y_top))
        r_vagon=pygame.Rect(cx - t_vagon.get_width()//2, insp_y_top + t1.get_height() + 4,
                            t_vagon.get_width(), t_vagon.get_height())
        surf.blit(t_vagon,r_vagon.topleft)
        mid_y=tag_y - 6 - t_vagon.get_height()
        surf.blit(tk1,(cx - tk1.get_width()//2, mid_y - tk1.get_height() - self.char_h))
        r_k2=pygame.Rect(cx - tk2.get_width()//2, mid_y - tk2.get_height(), tk2.get_width(), tk2.get_height())
        surf.blit(tk2,r_k2.topleft)
        r_me=pygame.Rect(tag_x, tag_y, t_me.get_width(), t_me.get_height())
        surf.blit(t_me,r_me.topleft); surf.blit(t_suffix,(tag_x + t_me.get_width(), tag_y))
        if self.cursor_support:
            over=any(r.collidepoint(mx,my) for r in (r_k2,r_vagon,r_me))
            try: pygame.mouse.set_cursor(self.cursor_hand if over else self.cursor_arrow)
            except Exception: pass
        self.help_click_zones=[(r_k2,"https://ko-fi.com/msouza3d"),
                               (r_vagon,"https://www.instagram.com/vagonparovoz/"),
                               (r_me,"https://www.instagram.com/msouza3d/")]

    # ---- ghost ring ----
    def _nearest_non_empty_char(self):
        idx=self.pal.idx_from_value(self.current_value)
        for off in [1,-1,2,-2,3,-3]:
            j=idx+off
            if 0<=j<self.pal.n and self.pal.chars[j] != ' ':
                return self.pal.chars[j]
        return '.'

    def draw_brush_ring(self,surf,ring_col,ticks):
        if not self.hover_cell: return
        base_y = getattr(self, 'canvas_offset_y', 0)
        cx,cy=self.hover_cell; r=max(1,self.brush_radius)
        selected=self.pal.char_from_value(self.current_value)
        blink_alt=(selected==' ')
        if blink_alt:
            show=(ticks//300)%2==0
            glyph_char=self._nearest_non_empty_char() if show else None
        else:
            glyph_char=selected if selected!=' ' else '·'
        if glyph_char:
            glyph=self.font.render(glyph_char,True,ring_col)
        if r==1:
            if glyph_char: surf.blit(glyph,(cx*self.char_w, base_y + cy*self.char_h))
            return
        rmin2=(r-1.0)*(r-1.0); rmax2=float(r)*float(r)
        x0=max(0,cx-r); x1=min(COLS-1,cx+r)
        y0=max(0,cy-r); y1=min(ROWS-1,cy+r)
        for y in range(y0,y1+1):
            dy2=(y-cy)*(y-cy)
            for x in range(x0,x1+1):
                d2=(x-cx)*(x-cx)+dy2
                if (rmin2<=d2<=rmax2) and glyph_char:
                    surf.blit(glyph,(x*self.char_w, base_y + y*self.char_h))

    # ---- full redraw ----
    def redraw_canvas_ascii(self,surf,mx,my,ticks):
        surf.fill(BLACK)

        # (opcional) calcula uma vez
        base_y = getattr(self, 'canvas_offset_y', 0)

        # 1) Draw GRID Before Characters
        if self.grid_enabled:
            self.draw_grid_overlay(surf)   # <- precisa alinhar usando base_y internamente

        # 2) Draw Characters Over it
        n=self.pal.n-1
        idx_all=(self.canvas.buf*n).round().clip(0,n).astype(np.int32)
        lum_all=(np.clip(self.canvas.col,0.0,1.0).astype(np.float64)*255).astype(np.int32)
        chars=self.pal.chars; get_glyph=self.glyphs.get
        cw=self.char_w; chh=self.char_h
        for r in range(ROWS):
            idx_row=idx_all[r].tolist(); lum_row=lum_all[r].tolist()
            y=base_y + r*chh
            for c in range(COLS):
                ch=chars[idx_row[c]]
                if ch==' ': continue            # nothing to draw on the black background
                v=lum_row[c]
                surf.blit(get_glyph(ch,(v,v,v)),(c*cw, y))

        # --- Overlay image (drawn after ASCII canvas but before UI) ---
        self.draw_overlay_if_needed(surf)


        # overlays / UI
        # self.draw_grid_overlay(surf)                 # grid over canvas
        self.draw_spherical_picker(surf)
        self.draw_tl_progress_bar(surf)
        self.draw_mode_stack(surf)
        self.draw_palette_bar(surf)
        self.draw_grid_panel(surf)

        # buttons
        self.draw_button(surf,self.new_btn,"NEW",
                         hovered=(self.hovered_btn=="NEW"),pressed=(self.pressed_btn=="NEW"))
        self.draw_button(surf,self.load_btn,"LOAD",
                         hovered=(self.hovered_btn=="LOAD"),pressed=(self.pressed_btn=="LOAD"))
        self.draw_button(surf,self.import_btn,"IMPORT",
                         hovered=(self.hovered_btn=="IMPORT"),pressed=(self.pressed_btn=="IMPORT"))
        self.draw_button(surf,self.save_btn,"SAVE",
                         hovered=(self.hovered_btn=="SAVE"),pressed=(self.pressed_btn=="SAVE"))

        self.draw_tool_info(surf)

        # ring
        if self.hover_cell:
            ring_col = RED if (self.mode=="blur" or (self.mode=="paint" and self.shift_blur)) \
                       else (HL_RGB if self.mode=="hlight" else WHITE)
            self.draw_brush_ring(surf, ring_col, ticks)
        self.draw_help_overlay(surf, mx, my, ticks)

    def draw_preview_line(self,surf,mx,my):
        if self.mode!="line" or self.pt1 is None: return
        base_y = getattr(self, 'canvas_offset_y', 0)
        x1=self.pt1[0]*self.char_w; y1=base_y + self.pt1[1]*self.char_h
        pygame.draw.circle(surf,CYAN,(x1,y1),6,1)
        pygame.draw.line(surf,CYAN,(x1,y1),(mx,my),1)

    # ---- picker math ----
    def _sphere_value_from_point(self,mx,my):
        """Return tone [0..1]. Inside sphere: tone = 1 - diffuse (bright->light).
           Outside (inside frame): 1.0 (darkest)."""
        cx=self.picker_rect.centerx
        cy=self.picker_rect.centery - PICKER_Y_OFFSET_LINES * self.char_h
        R=(self.picker_rect.width - 4)//2
        nx=(mx-cx)/R; ny=(my-cy)/R
        d2=nx*nx+ny*ny
        if d2<=1.0:
            Lx,Ly,Lz=-0.58,-0.58,0.58
            nz=math.sqrt(max(0.0,1.0-d2))
            diffuse=max(0.0, float(nx*Lx + ny*Ly + nz*Lz))
            return clamp01(1.0 - diffuse)
        else:
            return 1.0

    def handle_picker_click(self, mx, my):
        # palette bar
        if self.palette_rect.collidepoint(mx, my):
            if self.palette_items:
                # pick nearest rect by x, then map to underlying idx
                rect, idx = min(self.palette_items, key=lambda it: abs(it[0].centerx - mx))
                self.current_value = self.pal.value_from_idx(idx)
                self.play_ui_click()  # <- som de clique
                return True
            # fallback: compute index from position
            n = self.pal.n
            inner_w = self.palette_rect.width - 4
            left = self.palette_rect.left + 2
            rel = (mx - left) / max(1, inner_w)
            ui_idx = int(rel * n)
            ui_idx = max(0, min(n - 1, ui_idx))
            idx = (n - 1 - ui_idx) if PALETTE_BAR_DARK_TO_LIGHT else ui_idx
            self.current_value = self.pal.value_from_idx(idx)
            self.play_ui_click()  # <- som de clique
            return True

        # sphere
        if self.picker_rect.collidepoint(mx, my):
            self.current_value = self._sphere_value_from_point(mx, my)
            if self.picker_cells:
                self.picker_sel_rect = min(
                    self.picker_cells,
                    key=lambda p: abs(p[0].centerx - mx) + abs(p[0].centery - my)
                )[0]
            self.play_ui_click()  # <- som de clique
            return True

        return False


    def handle_mode_stack_click(self, mx, my):
        """Torna HLIGHT, SOFT, PAINT, BLUR, LINE, LINEAA clicáveis."""
        if not self.ind_rects: 
            return False
        for rect, label in zip(self.ind_rects, self.ind_labels):
            if rect.collidepoint(mx, my):
                self.play_ui_click()
                if label == "HLIGHT":
                    # mesmo comportamento do atalho H
                    if self.mode == "hlight":
                        if self.prev_mode and self.prev_mode != "hlight":
                            self.mode = self.prev_mode
                        else:
                            self.mode = "paint"
                    else:
                        if self.mode != "hlight":
                            self.prev_mode = self.mode
                        self.mode = "hlight"

                elif label == "SOFT":
                    # mesmo do atalho S (sem shift)
                    self.soft_edge = not self.soft_edge

                elif label == "PAINT":
                    self.prev_mode = self.mode if self.mode != "hlight" else self.prev_mode
                    self.mode = "paint"; self.pt1 = None

                elif label == "BLUR":
                    # mesmo do atalho B
                    if self.mode == "blur":
                        self.mode = "paint"
                    else:
                        self.prev_mode = self.mode if self.mode != "hlight" else self.prev_mode
                        self.mode = "blur"; self.pt1 = None

                elif label == "LINE":
                    # mesmo do atalho L
                    if self.mode == "line":
                        self.mode, self.pt1 = ("paint", None)
                    else:
                        if self.mode != "hlight":
                            self.prev_mode = self.mode
                        self.mode, self.pt1 = ("line", None)

                elif label == "LINEAA":
                    # mesmo do atalho A
                    self.line_aa = not self.line_aa

                return True
        return False


    # ---------- painting ----------
    def paint_under_mouse(self,mx,my):
        cell=self.mouse_to_cell(mx,my); self.hover_cell=cell
        if not cell: return
        ctrl=bool(pygame.key.get_mods() & pygame.KMOD_CTRL)
        x,y=cell

        if self.mode=="line": return

        # Highlight mode: left applies almost-white luma; right erases to default grey
        if self.mode=="hlight":
            if self.left_down:
                self.begin_stroke_if_needed()
                self.canvas.luma_disc_blend(x,y,self.brush_radius,HLIGHT_LUMA,1.0,self.soft_edge)
                ## if self.brush_radius==1: self.play_brush_tick()
            elif self.right_down:
                self.begin_stroke_if_needed()
                self.canvas.luma_disc_blend(x,y,self.brush_radius,HL_ERASE_LUMA,1.0,self.soft_edge)
                ##if self.brush_radius==1: self.play_brush_tick()
            return

        blur_now=(self.mode=="blur") or (self.mode=="paint" and self.shift_blur)

        if self.left_down:
            self.begin_stroke_if_needed()
            if blur_now:
                self.canvas.blur_disc(x,y,self.brush_radius)
                ##if self.brush_radius==1: self.play_brush_tick()
            else:
                self.canvas.paint_disc_blend(x,y,self.brush_radius,self.current_value,self.brush_alpha,self.soft_edge)
                # reset luma to default grey regardless of opacity
                self.canvas.luma_disc_blend(x,y,self.brush_radius,TEXT_LUMA,1.0,self.soft_edge)
                ##if self.brush_radius==1: self.play_brush_tick()

        elif self.right_down:
            self.begin_stroke_if_needed()
            self.canvas.erase_disc_blend(x,y,self.brush_radius,self.brush_alpha,self.soft_edge)
            ##if self.brush_radius==1: self.play_brush_tick()

        elif self.mid_down:
            self.begin_stroke_if_needed()
            # MID = lighten (towards 0), CTRL+MID = darken (towards 1)
            delta = (-LIGHTEN_STEP) if not ctrl else (+LIGHTEN_STEP)
            self.canvas.add_disc(x,y,self.brush_radius, delta, self.brush_alpha, self.soft_edge)
            ##if self.brush_radius==1: self.play_brush_tick()

    # ---------- modal prompt ----------
    def ask_modal_yesno(self,text):
        h=110
        panel=pygame.Surface((SIDEBAR_W,h)); panel.fill(BLACK)
        y0 = self.surface.get_height() - h
        self.redraw_canvas_ascii(self.surface,*pygame.mouse.get_pos(), pygame.time.get_ticks())
        self.surface.blit(panel,(self.canvas_px_w,y0))
        title=self.font.render(text,True,WHITE)
        self.surface.blit(title,(self.canvas_px_w+UI_MARGIN, y0+UI_MARGIN))
        sub=self.font.render("(Y / N)",True,GREY_TEXT)
        self.surface.blit(sub,(self.canvas_px_w+UI_MARGIN, y0+UI_MARGIN+self.char_h+6))
        self.present_surface()
        while True:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT: return False
                if ev.type == pygame.KEYDOWN:
                    if ev.key in (pygame.K_y, pygame.K_RETURN): return True
                    if ev.key in (pygame.K_n, pygame.K_ESCAPE): return False
            pygame.time.delay(10)

    # ---------- main loop ----------
    def run(self):
        global COPY_USE_NBSP
        while self.running:
            self.clock.tick(60)
            mx, my = pygame.mouse.get_pos()
            mx = int(mx / WINDOW_SCALE); my = int(my / WINDOW_SCALE)
            ticks = pygame.time.get_ticks()

            # Track button hover
            self.hovered_btn = None
            if   self.new_btn.collidepoint(mx, my):    self.hovered_btn = "NEW"
            elif self.load_btn.collidepoint(mx, my):   self.hovered_btn = "LOAD"
            elif self.import_btn.collidepoint(mx, my): self.hovered_btn = "IMPORT"
            elif self.save_btn.collidepoint(mx, my):   self.hovered_btn = "SAVE"

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False

                elif ev.type == pygame.KEYDOWN:
                    mods = pygame.key.get_mods()
                    ctrl = bool(mods & pygame.KMOD_CTRL)
                    shift = bool(mods & pygame.KMOD_SHIFT)
                    self._ensure_timelapse()


                    if SND_UI_KEYPRESS_ON_ANY_KEYDOWN:
                        try: self.play_ui_click()
                        except Exception: pass

                    # --- Timelapse controls (agora independentes) ---
                    if (ev.key == pygame.K_t) and (not ctrl) and (not shift):
                        self.tl.enabled = not self.tl.enabled
                        print("[TL] Recording:", "ON" if self.tl.enabled else "OFF")

                    elif ctrl and (ev.key == pygame.K_t):
                        self.tl.reset()
                        self.tl_last_interval_ms = 0
                        self.tl_full_prompted = False
                        print("[TL] Frames cleared.")

                    elif ctrl and (ev.key == pygame.K_e):
                        self.tl_export_via_dialog()
                        self._release_mouse_state()

                    # SHIFT+O = load overlay image
                    if (pygame.key.get_mods() & pygame.KMOD_SHIFT) and ev.key == pygame.K_o:
                        self.load_overlay_image()
                        self._release_mouse_state()

                    # O = toggle overlay visibility
                    elif ev.key == pygame.K_o and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                        if self.overlay_image:
                            self.overlay_visible = not self.overlay_visible
                            print(f"[OVERLAY] Visible: {self.overlay_visible}")


                    # SHIFT+H (Help)
                    if shift and ev.key == pygame.K_h:
                        self.show_help = not self.show_help
                        continue

                    # SHIFT down (start smooth). If we were in HLIGHT, temporarily switch to PAINT+SMOOTH
                    if ev.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                        if self.mode == "hlight":
                            self.mode = "paint"
                            self.shift_from_hlight = True
                            self.shift_blur = True
                        elif self.mode == "paint":
                            self.shift_blur = True

                    if ctrl and ev.key == pygame.K_q:
                        if self.ask_modal_yesno("SAVE BEFORE EXIT?"): self.quick_save()
                        self.running = False

                    # N -> NEW (mesmo comportamento do botão)
                    elif (not ctrl) and (not shift) and ev.key == pygame.K_n:
                        self.play_ui_click()
                        if self.ask_modal_yesno("NEW CANVAS"):
                            darkest_val = self.pal.value_from_idx(self.pal.n - 1)  # right-most (stored) = darkest
                            self.push_undo()
                            self.canvas.clear(darkest_val, TEXT_LUMA)

                    # H toggle HLIGHT (not shift)
                    elif (not shift) and ev.key == pygame.K_h:
                        if self.mode == "hlight":
                            if self.prev_mode and self.prev_mode != "hlight":
                                self.mode = self.prev_mode
                            else:
                                self.mode = "paint"
                        else:
                            if self.mode != "hlight":
                                self.prev_mode = self.mode
                            self.mode = "hlight"

                    elif ev.key == pygame.K_ESCAPE:
                        if self.show_help:
                            self.show_help = False
                        elif self.mode == "line":
                            self.mode = self.prev_mode if (self.prev_mode and self.prev_mode != "hlight") else "paint"
                            self.pt1 = None
                        elif self.mode == "hlight":
                            self.mode = self.prev_mode if (self.prev_mode and self.prev_mode != "hlight") else "paint"

                    elif ctrl and (not (mods & pygame.KMOD_ALT)) and ev.key == pygame.K_s:
                        self.quick_save()

                    elif ctrl and ev.key == pygame.K_z:
                        self.undo()

                    elif (not shift) and (not ctrl) and ev.key == pygame.K_s:
                        self.soft_edge = not self.soft_edge

                    elif shift and ev.key == pygame.K_s:
                        self.sound_enabled = not self.sound_enabled

                    elif ev.key == pygame.K_i:
                        self.pal.invert()

                    elif ev.key == pygame.K_x:
                        # toggle between extreme light (0.0) and extreme dark (1.0)
                        self.current_value = (1.0 if self.current_value < 0.5 else 0.0)
                        self.picker_sel_rect = None

                    elif ev.key == pygame.K_a:
                        self.line_aa = not self.line_aa

                    elif ev.key == pygame.K_b:
                        if self.mode == "blur": self.mode = "paint"
                        else: self.mode, self.pt1 = "blur", None

                    elif ev.key == pygame.K_l:
                        if self.mode == "line":
                            self.mode, self.pt1 = "paint", None
                        else:
                            if self.mode != "hlight":
                                self.prev_mode = self.mode
                            self.mode, self.pt1 = "line", None

                    elif ev.key == pygame.K_g:
                        self.grid_enabled = not self.grid_enabled

                    elif ev.key == pygame.K_LEFTBRACKET:
                        self.brush_radius = max(1, self.brush_radius - 1)

                    elif ev.key == pygame.K_RIGHTBRACKET:
                        self.brush_radius = min(64, self.brush_radius + 1)

                    # '-' = darker (towards 1), '=' = lighter (towards 0)
                    elif ev.key == pygame.K_MINUS:
                        idx = self.pal.idx_from_value(self.current_value)
                        idx = min(self.pal.n-1, idx+1)     # one step to darker
                        self.current_value = self.pal.value_from_idx(idx)
                    elif ev.key == pygame.K_EQUALS:
                        idx = self.pal.idx_from_value(self.current_value)
                        idx = max(0, idx-1)               # one step to lighter
                        self.current_value = self.pal.value_from_idx(idx)

                    # --- Copy / Export ---
                    elif ctrl and (not shift) and (not (mods & pygame.KMOD_ALT)) and ev.key == pygame.K_c:
                        # CTRL+C -> copy current as Markdown (default)
                        self.copy_current_as(COPY_DEFAULT_MODE)

                    elif ctrl and shift and ev.key == pygame.K_c:
                        # CTRL+SHIFT+C -> ask target columns, crop to bbox (or grid-aligned bbox), resample, copy
                        cols = None
                        try:
                            import tkinter as tk
                            from tkinter import simpledialog
                            root = tk.Tk(); root.withdraw()
                            cols = simpledialog.askinteger("Copy Fit (BBox/Grid)", "Target columns:", minvalue=10, maxvalue=400, initialvalue=DEFAULT_COPY_FIT_COLS)
                            root.destroy()
                        except Exception as e:
                            print("CopyFit dialog error:", e)
                            cols = DEFAULT_COPY_FIT_COLS      # dialog unavailable: use the default width
                        self._release_mouse_state()
                        if cols:
                            try:
                                self.copy_fit_cols(cols, None, COPY_DEFAULT_MODE)
                            except Exception as e:
                                print("[COPY FIT] error:", e)

                    elif ctrl and (mods & pygame.KMOD_ALT) and ev.key == pygame.K_c:
                        # CTRL+ALT+C -> copy current as HTML <pre>
                        self.copy_current_as("html")
                    elif ctrl and (mods & pygame.KMOD_ALT) and ev.key == pygame.K_s:
                        # CTRL+ALT+S -> Copy for Slack (Markdown) with row aspect correction
                        self.copy_fit_cols(DEFAULT_COPY_FIT_COLS, None, COPY_DEFAULT_MODE, row_scale=SLACK_ROW_SCALE)
                        print('[COPY] Slack aspect correction applied')


                    elif ctrl and shift and ev.key == pygame.K_n:
                        # CTRL+SHIFT+N -> toggle NBSP replacement
                        COPY_USE_NBSP = not COPY_USE_NBSP
                        print("NBSP:", "ON" if COPY_USE_NBSP else "OFF")

                    # SHIFT+1..0 = palette files
                    elif shift and ev.key in (pygame.K_1,pygame.K_2,pygame.K_3,pygame.K_4,pygame.K_5,
                                              pygame.K_6,pygame.K_7,pygame.K_8,pygame.K_9,pygame.K_0):
                        self.picker_sel_rect = None
                        self.pal.set_index(10 if ev.key == pygame.K_0 else (ev.key - pygame.K_0))

                    # 1..0 = tone deciles (0 key -> RIGHT end = darkest)
                    elif (not shift) and ev.key in (pygame.K_1,pygame.K_2,pygame.K_3,pygame.K_4,pygame.K_5,
                                                    pygame.K_6,pygame.K_7,pygame.K_8,pygame.K_9,pygame.K_0):
                        digit = 0 if ev.key == pygame.K_0 else (ev.key - pygame.K_0)
                        self.current_value = self.pal.set_from_decile_key(digit)

                elif ev.type == pygame.KEYUP:
                    if ev.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                        self.shift_blur = False
                        if self.shift_from_hlight:
                            self.mode = "hlight"
                            self.shift_from_hlight = False

                elif ev.type == pygame.MOUSEWHEEL:
                    mods = pygame.key.get_mods()
                    ctrl = bool(mods & pygame.KMOD_CTRL)
                    shift = bool(mods & pygame.KMOD_SHIFT)
                    if shift:
                        self.brush_alpha = clamp01(self.brush_alpha + (0.05 if ev.y > 0 else -0.05))
                    elif ctrl:
                        idx = self.pal.idx_from_value(self.current_value)
                        idx = min(self.pal.n-1, max(0, idx + (1 if ev.y > 0 else -1)))
                        self.current_value = self.pal.value_from_idx(idx)
                    else:
                        self.brush_radius = max(1, min(64, self.brush_radius + (1 if ev.y > 0 else -1)))

                elif ev.type == pygame.MOUSEBUTTONDOWN:
                    mods = pygame.key.get_mods()
                    alt  = bool(mods & pygame.KMOD_ALT)

                    # ... (já tem botões, help, pickers etc.)

                    # ALT-pick no canvas (não inicia pintura)
                    if alt and (ev.button == 1) and (0 <= mx < self.canvas_px_w):
                        cell = self.mouse_to_cell(mx, my)
                        if cell:
                            self.sample_tone_from_canvas(cell)
                            self.play_ui_click()   # som de keypress no pick também
                        continue

                    # Buttons hover/press feedback
                    if ev.button == 1:
                        if self.hovered_btn:
                            self.pressed_btn = self.hovered_btn
                            self.play_ui_click()
                        # Help links
                        if self.show_help:
                            for r, url in self.help_click_zones:
                                if r.collidepoint(mx, my):
                                    self.play_ui_click()  # <- som de clique
                                    try:
                                        webbrowser.open(url)
                                    except Exception:
                                        pass
                                    break


                    # Click on pickers/bars first
                    if self.handle_picker_click(mx, my):
                        continue

                    # Click nos indicadores (HLIGHT, SOFT, PAINT, BLUR, LINE, LINEAA)
                    if ev.button == 1:
                        if self.handle_mode_stack_click(mx, my):
                            continue

                    # Grid UI clicks
                    if ev.button == 1:
                        if self.grid_checkbox_rect.collidepoint(mx,my) or self.grid_label_rect.collidepoint(mx,my):
                            self.grid_enabled = not self.grid_enabled; self.play_ui_click()
                        elif not GRID_MATCH_CELLS:
                            if self.grid_cols_minus.collidepoint(mx,my):
                                self.grid_cols = max(GRID_MIN, self.grid_cols-1); self.play_ui_click()
                            elif self.grid_cols_plus.collidepoint(mx,my):
                                self.grid_cols = min(GRID_MAX, self.grid_cols+1); self.play_ui_click()
                            elif self.grid_rows_minus.collidepoint(mx,my):
                                self.grid_rows = max(GRID_MIN, self.grid_rows-1); self.play_ui_click()
                            elif self.grid_rows_plus.collidepoint(mx,my):
                                self.grid_rows = min(GRID_MAX, self.grid_rows+1); self.play_ui_click()
                        else:
                            # Grid matches cells; ignore +/- and reflect actual canvas size
                            self.grid_cols, self.grid_rows = self.canvas.cols, self.canvas.rows
                   # Map mouse buttons
                    if ev.button in (3, 8):  # ERASE: right mouse
                        self.right_down = True
                        self.snd_last_cell = None
                        cell = self.mouse_to_cell(mx, my)   # célula do clique (não use hover_cell aqui)
                        if cell:
                            self.play_brush_cell_trigger(cell)

                    elif ev.button == 1:
                        # Buttons actions
                        if self.new_btn.collidepoint(mx, my):
                            if self.ask_modal_yesno("NEW CANVAS"):
                                darkest_val = self.pal.value_from_idx(self.pal.n - 1)  # right-most (stored) = darkest
                                self.push_undo()
                                self.canvas.clear(darkest_val, TEXT_LUMA)
                            continue
                        if self.load_btn.collidepoint(mx, my):
                            try:
                                import tkinter as tk
                                from tkinter import filedialog
                                root = tk.Tk(); root.withdraw()
                                path = filedialog.askopenfilename(
                                    title="LOAD ASCII .TXT",
                                    initialdir=str(SAVES_DIR if SAVES_DIR.is_dir() else USER_DIR),
                                    filetypes=[("Text files","*.txt")])
                                root.destroy()
                                if path: self.load_txt_into_canvas(path)
                            except Exception as e:
                                print("Load dialog error:", e)
                            self._release_mouse_state()
                            continue
                        if self.save_btn.collidepoint(mx, my):
                            try:
                                import tkinter as tk
                                from tkinter import filedialog
                                import os
                                root = tk.Tk(); root.withdraw()

                                SAVES_DIR.mkdir(parents=True, exist_ok=True)
                                base_suggestion = f"ascii_{timestamp()}"
                                path = filedialog.asksaveasfilename(
                                    title="SAVE ASCII (TXT + PNG)",
                                    defaultextension=".txt",
                                    initialdir=str(SAVES_DIR),
                                    initialfile=base_suggestion + ".txt",  # <- nome sugerido
                                    filetypes=[("Text file", "*.txt"), ("All files", "*.*")]
                                )
                                root.destroy()

                                if path:
                                    base, _ = os.path.splitext(path)
                                    self.save_txt(base + ".txt")
                                    self.save_png(base + ".png")
                                    self.play_ui_click()
                            except Exception as e:
                                print("Save dialog error:", e)
                            self._release_mouse_state()
                            continue

                        # --- IMPORT button ---
                        if self.import_btn.collidepoint(mx, my):
                            try:
                                import tkinter as tk
                                from tkinter import filedialog
                                root = tk.Tk(); root.withdraw()
                                path = filedialog.askopenfilename(
                                    title="Select Image to Import",
                                    filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.bmp;*.webp")]
                                )
                                root.destroy()
                                if path:
                                    print(f"[IMPORT] Loading image: {path}")
                                    self.import_image_to_canvas(path)
                                    print("[IMPORT] Image imported successfully.")
                                else:
                                    print("[IMPORT] Cancelled by user.")
                            except Exception as e:
                                print("[IMPORT] Error:", e)
                            self._release_mouse_state()
                            continue


                        # Canvas click
                        if self.mode == "line":
                            cell = self.mouse_to_cell(mx, my)
                            if cell:
                                # toca um tick para cada ponto marcado na linha
                                self.play_ui_click()

                                if self.pt1 is None:
                                    self.pt1 = cell
                                else:
                                    x0,y0 = self.pt1; x1,y1 = cell
                                    self.push_undo()
                                    self.stroke_started = True   # end_stroke() on mouse-up records the timelapse frame
                                    if self.line_aa:
                                        self.canvas.draw_line_aa_thick(
                                            x0,y0,x1,y1,self.current_value,self.brush_alpha,self.brush_radius,self.soft_edge,reset_luma_to=TEXT_LUMA)
                                    else:
                                        self.canvas.draw_line_basic(
                                            x0,y0,x1,y1,self.current_value,self.brush_alpha,self.brush_radius,self.soft_edge)
                                        # ensure luma reset on basic too
                                        self.canvas.luma_disc_blend(
                                            x1,y1,self.brush_radius,TEXT_LUMA,1.0,self.soft_edge)
                                    self.pt1 = (x1,y1)

                        else:
                            # STROKE START (LMB)
                            self.snd_last_cell = None
                            self.left_down = True
                            cell = self.mouse_to_cell(mx, my)
                            if cell:
                                self.play_brush_cell_trigger(cell)

                    elif ev.button == 2:
                        self.mid_down = True
                    self.snd_last_cell = None       # reset sound cell to allow immediate sound 

                elif ev.type == pygame.MOUSEBUTTONUP:
                    if ev.button == 1:
                        self.left_down = False
                        self.snd_last_cell = None
                    elif ev.button in (3, 8):
                        self.right_down = False
                    elif ev.button == 2:
                        self.mid_down = False
                    self.pressed_btn = None
                    if not (self.left_down or self.right_down or self.mid_down):
                        self.end_stroke()

                elif ev.type == pygame.MOUSEMOTION:
                    self.hover_cell = self.mouse_to_cell(mx, my)
                    if (self.left_down or self.right_down or self.mid_down) and self.hover_cell and (self.hover_cell != self.snd_last_cell):
                        self.play_brush_cell_trigger(self.hover_cell)
                    if self.show_help and self.cursor_support:
                        over = any(r.collidepoint(mx, my) for r,_ in self.help_click_zones)
                        try: pygame.mouse.set_cursor(self.cursor_hand if over else self.cursor_arrow)
                        except Exception: pass

            # Continuous paint
            if (self.left_down or self.right_down or self.mid_down) and (self.mode != "line"):
                self.paint_under_mouse(mx, my)

            # Timelapse (interval mode) — capture while mouse is down
            self.tl_poll_interval()

            self._update_cursor_visibility(mx, my)
            
            if self.processing_active:
                self.processing_ticks += 1

            # Draw
            self.redraw_canvas_ascii(self.surface, mx, my, ticks)
            if self.mode == "line" and self.pt1 is not None:
                self.draw_preview_line(self.surface, mx, my)
            self.present_surface()
        try: pygame.mouse.set_visible(True)
        except Exception: pass

        pygame.quit()

if __name__ == "__main__":
    try:
        App().run()
    except Exception:
        # the windowed .exe has no console: leave the traceback next to it
        import traceback
        try:
            (USER_DIR / "crash.log").write_text(traceback.format_exc(), encoding="utf-8")
        except Exception:
            pass
        raise 