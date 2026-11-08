# ASCII Painter - v0.97

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


def pal_write_path():
    """Where palette edits are saved: the PAL.txt in use, or a PAL.txt next to the .exe when the one in use is bundled."""
    p = find_asset("PAL.txt")
    if p is not None and not (IS_FROZEN and BUNDLE_DIR in p.parents): return p
    return USER_DIR / "PAL.txt"


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
VERSION = "1.13"

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
TL_ROW_H = 16                # height of the T.LAPSE row under the tone sphere (REC / bar / count / GIF / CLR)
TL_ROW_GAP = 6
TL_START_ON = False          # True = start every session already recording
TL_WIPE_ARM_MS = 2000        # the CLR button needs a second click within this time

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
# --- Pen pressure (Windows Ink, optional) ---
PEN_MODES = ("OFF", "OPACITY", "SIZE", "BOTH")
PEN_DEFAULT_MODE = "OPACITY"   # what pressure controls; the P key cycles it
PEN_CURVE = 1.0                # pressure ** PEN_CURVE (above 1 = needs a harder press, below 1 = softer)
PEN_MIN_SCALE = 0.05           # lightest pressure still leaves a trace

# --- Smudge ---
FADE_LEN_MAX = 160.0     # FADE: stroke length (in cells) over which the ink dies out, with the slider all the way to the slow side
FADE_LEN_MIN = 4.0       # ... and with the slider all the way to the fast side
SMUDGE_GAIN = 0.8        # fraction of the ink under the brush that moves 1 cell per step at opacity 1.0
SMUDGE_RGB  = (255, 170, 60)

# --- Smart Brush / Smart Edge ---
EDGES_FILE      = "EDGES.txt"   # characters used for borders (global, works with every palette)
DEFAULT_EDGE_CHARS = "_-\u00af.,:;'\"`^\u00a8\u00aa\u00ba\u00ac|/\\()[]<>~!?iIl1jJL7rdbpqocunhkyZ4S$"
EDGE_INK_MIN    = 0.10   # a cell with ink (1 - tone) above this belongs to the drawing
EDGE_BG_MAX     = 0.20   # a neighbour with ink below this counts as empty background
EDGE_UP_THRESH  = 0.62   # silhouette threshold when the cell grid is upsampled (higher = thinner border glyphs)
EDGE_MASS_W     = 0.6    # weight of "same amount of ink" against "same shape" when matching glyphs
UI_FONT_SIZE = 13             # sidebar text (buttons, info lines, GRID): smaller than the drawing font
BRUSH_ROUND_IN_PIXELS = True   # compensate the tall character cells: a brush of radius r is a real circle on screen
PICKER_FONT_SIZE = 11     # font of the tone sphere: smaller than the main font = a more defined sphere
PICKER_LIGHT = (-0.58, -0.58, 0.58)   # light direction of the sphere (upper-left, towards the viewer)

HELP_DESC_SHIFT = 145  # pixels, tweak to taste
HELP_BLOCK_XOFFSET = 10  # pixels, indent for HELP
HELP_FONT_SIZE = 12      # SHIFT+H list font (smaller than the canvas font so the list fits the sidebar)
HELP_LINE_GAP = 1        # extra pixels between help lines
HELP_COL_GAP = 10        # pixels between the command column and the description column

# Dynamic canvas size (Ctrl+Arrows grow, Ctrl+Shift+Arrows shrink empty edges)
CANVAS_GROW_COLS = 10        # cells added per Ctrl+Left/Right press
CANVAS_GROW_ROWS = 6         # cells added per Ctrl+Up/Down press
CANVAS_MIN_COLS, CANVAS_MIN_ROWS = 20, 12
CANVAS_MAX_COLS, CANVAS_MAX_ROWS = 240, 160
CANVAS_MAX_CELLS = 30000     # redraw cost grows with the cell count
AUTO_GROW_ON_LOAD = True     # LOAD of a TXT bigger than the canvas grows the canvas (up to the limits)
RESIZE_MIN_WINDOW_SCALE = 0.3  # lowest window scale AUTO_FIT_WINDOW may use for big canvases
FLASH_MS = 1800

# Palette shortcut bar (under the character bar): one small button per palette 1..10 found in PAL.txt
PAL_SLOT_H = 18
PAL_SLOT_GAP = 3
PAL_SLOT_BAR_GAP = 4
# --- BOMB brush (K): click = fuse, then everything around the bomb is thrown outward leaving trails ---
BOMB_FUSE_MS = 1500          # fuse time (if you provide sounds/bomb_fuse.wav its length is used instead)
BOMB_FUSE_LOOPS = 2          # how many times the centre character runs through all shades during the fuse
BOMB_FLASH_MS = 90           # white flash at the moment of the explosion
BOMB_BLAST_MS = 1000         # time the debris takes to fly out
BOMB_R_BASE = 4.0            # blast radius (in cells) at brush radius 1 ...
BOMB_R_PER_BRUSH = 1.5       # ... plus this much per extra brush radius step
BOMB_R_MAX = 60
BOMB_CORE = 0.25             # fraction of the radius that flashes white and is always blown completely empty
BOMB_REACH_MIN = 0.55        # every direction gets its own reach between these fractions of the radius ...
BOMB_REACH_MAX = 1.15        # ... (can go a little past the radius)
BOMB_RAYS = 18               # number of rays; each has its own reach and pushes its neighbours with a smooth fall-off
BOMB_RAY_SPREAD = 0.65       # angular influence of a ray, as a fraction of the angle between rays (higher = softer blend)
BOMB_KEEP_POW = 1.3          # how the empty core fades out toward the tips (higher = bigger empty area)
BOMB_FADE_POW = 1.0          # ceiling of ink along a ray: (distance / reach) ** this. Lower = darker (more ink) sooner, higher = the void fades out more slowly
BOMB_TRAIL_GAIN = 0.45       # strength of the trails relative to the ink that flies (many trails cross in dense areas)
BOMB_TRAIL_MIN = 0.12        # trail strength at the start of a flight (1.0 = full strength at the landing point)
BOMB_TRAIL_POW = 1.6         # how fast the trail gets stronger towards the landing point
BOMB_WAVE = 0.45             # the shock wave leaves the centre and reaches the tips at this fraction of the blast time
BOMB_RING = 0.45             # strength of the bright ring that rides on the wave front (0 = off)
BOMB_JITTER = 0.06           # random angle (radians) added to each piece of debris
BOMB_SOUND_VOL = 0.6         # procedural sounds; put sounds/bomb_fuse.wav and sounds/bomb_explosion.wav to override
BOMB_RGB = (255, 90, 60)
BOMB_RING_POW = 1.6          # the warning ring shrinks from the full blast radius to the centre; higher = closes later and faster
TOOLTIP_DELAY_MS = 400       # hover time before a quick-help box appears
DOUBLE_CLICK_MS = 450        # double click on a character of the palette bar opens the character table
VOICE_MODE_LINES = {"paint": "paint", "blur": "blur", "line": "line", "hlight": "highlight", "smart": "smart brush",
                    "edge": "smart edge", "smudge": "smudge", "bomb": "ink bomb"}
VOICE_TRU_LINES = ("true mode", "less slop mode", "organic mode", "hand made mode", "artisanal mode", "no cheating mode")
VOICE_BOMB_LINES = ("splat incoming", "messy business", "big splash", "here comes the mess", "letters everywhere", "scatter the letters")
TRU_ADVANCE = True        # TRU mode: the cursor steps right after a typed character
TRU_BLINK_MS = 450
TRU_RGB = (255, 200, 90)
PAL_MIN_SLOTS = 3             # a palette keeps at least 2 shades plus the darkest (space)
PAL_MAX_SLOTS = 24            # more than this would not fit in the palette bar
TABLE_COLS = 20              # columns of the floating character table
# characters offered by the table (only those the font can draw are shown)
TABLE_SETS = ("!\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"
              "░▒▓█▀▄▌▐■□▪▫▬▲►▼◄◊○●◘◙◦"
              "°±²³µ¶·¸¹º¼½¾×÷¤¦§¨©«¬®¯¡¿¢£¥"
              "∙√∞≈≠≤≥∑∏∫∂∆"
              "─│┌┐└┘├┤┬┴┼═║╔╗╚╝╠╣╦╩╬"
              "←↑→↓↔↕"
              "♠♣♥♦♪♫☺☻☼♀♂†‡•…‰")
IND_TIPS = {"HLIGHT": "H  HIGHLIGHT MODE", "SOFT": "S  SOFT EDGE ON/OFF", "PAINT": "ESC  BACK TO PAINT",
            "BLUR": "HOLD SHIFT or B  BLUR BRUSH", "LINE": "L  LINE MODE", "LINEAA": "A  LINE ANTIALIAS ON/OFF"}

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
        self.edits = {}  # {nn: edited string} unsaved edits; kept when you switch palettes
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
            s = self.edits.get(idx, entry["chars"])
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

    # ---------- editing and saving (v1.00) ----------
    def _commit(self, core):
        """Apply a new list of shade characters (the darkest space is added at the end) and track the edit."""
        self.rebuild_cache_from_string("".join(core))
        nn = self.index
        if nn in self.map:
            if self.string == ensure_darkest_space(self.map[nn]["chars"]): self.edits.pop(nn, None)
            else: self.edits[nn] = self.string

    def set_char(self, i, ch):
        """Replace the character at palette position i (the darkest slot stays a space). Tracks the edit."""
        if not (0 <= i < self.n - 1) or ch in (" ", "\u00a0"): return False
        s = list(self.string); s[i] = ch
        self._commit(s)
        return True

    def insert_slot(self, i, max_n=PAL_MAX_SLOTS):
        """Add a shade slot at position i (0 = lightest). It starts as a copy of the slot that is pushed along."""
        if self.n >= max_n or not (0 <= i < self.n - 1): return False
        s = list(self.string[:-1]); s.insert(i, s[i])
        self._commit(s); return True

    def remove_slot(self, i):
        """Remove the shade at position i (never the darkest space, never below PAL_MIN_SLOTS)."""
        if self.n <= PAL_MIN_SLOTS or not (0 <= i < self.n - 1): return False
        s = list(self.string[:-1]); del s[i]
        self._commit(s); return True

    def move_slot(self, i, j):
        """Move the shade at position i to position j (both among the editable slots)."""
        if i == j or not (0 <= i < self.n - 1) or not (0 <= j < self.n - 1): return False
        s = list(self.string[:-1]); ch = s.pop(i); s.insert(j, ch)
        self._commit(s); return True

    def restore(self, nn):
        self.edits.pop(nn, None)
        if self.index == nn: self.set_index(nn)

    def _write_file(self):
        path = pal_write_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        bak = path.with_name(path.name + ".bak")
        if path.exists() and not bak.exists():          # keep the very first version as a safety copy
            import shutil
            shutil.copyfile(path, bak)
        text = "\n".join(f"{nn:02d}-{self.map[nn]['name']}\n{self.map[nn]['chars']}\n" for nn in sorted(self.map))
        tmp = path.with_name(path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as f: f.write(text)
        os.replace(tmp, path)

    def save(self, nn):
        """Write the edited version of palette nn over itself in PAL.txt. Returns (ok, message)."""
        if nn not in self.edits: return False, "NOTHING TO SAVE"
        old = self.map[nn]["chars"]
        self.map[nn]["chars"] = self.edits[nn]
        try: self._write_file()
        except Exception as e:
            self.map[nn]["chars"] = old
            return False, "COULD NOT WRITE PAL.TXT"
        self.edits.pop(nn); self.order = sorted(self.map)
        return True, f"SAVED {nn:02d}-{self.map[nn]['name']}"

    def save_new(self, nn):
        """Save the (edited) palette nn into the lowest free number 1..10. Returns (new number or None, message)."""
        free = [k for k in range(1, 11) if k not in self.map]
        if not free: return None, "NO FREE SLOT (1-10)"
        new = free[0]; name = self.map[nn]["name"]
        if not name.endswith(".EDIT"): name += ".EDIT"
        self.map[new] = {"name": name, "chars": ensure_darkest_space(self.edits.get(nn, self.map[nn]["chars"]))}
        try: self._write_file()
        except Exception:
            del self.map[new]
            return None, "COULD NOT WRITE PAL.TXT"
        self.edits.pop(nn, None); self.order = sorted(self.map)
        self.set_index(new)
        return new, f"SAVED AS {new:02d}-{name}"

    def save_here(self, nn):
        """Save the palette currently in use into the empty slot nn."""
        if nn in self.map: return False, "SLOT NOT EMPTY"
        self.map[nn] = {"name": "CUSTOM", "chars": ensure_darkest_space(self.string)}
        try: self._write_file()
        except Exception:
            del self.map[nn]
            return False, "COULD NOT WRITE PAL.TXT"
        self.order = sorted(self.map); self.set_index(nn)
        return True, f"SAVED AS {nn:02d}-CUSTOM"

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


# ====================== PEN PRESSURE ======================
def _pen_structs():
    """ctypes layouts of the Windows POINTER_INFO / POINTER_PEN_INFO structures (fixed-size fields, so the
    layout is the same on any platform and can be checked by the tests)."""
    import ctypes
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_int32), ("y", ctypes.c_int32)]
    class POINTER_INFO(ctypes.Structure):
        _fields_ = [("pointerType", ctypes.c_uint32), ("pointerId", ctypes.c_uint32), ("frameId", ctypes.c_uint32),
                    ("pointerFlags", ctypes.c_uint32), ("sourceDevice", ctypes.c_void_p), ("hwndTarget", ctypes.c_void_p),
                    ("ptPixelLocation", POINT), ("ptHimetricLocation", POINT),
                    ("ptPixelLocationRaw", POINT), ("ptHimetricLocationRaw", POINT),
                    ("dwTime", ctypes.c_uint32), ("historyCount", ctypes.c_uint32), ("InputData", ctypes.c_int32),
                    ("dwKeyStates", ctypes.c_uint32), ("PerformanceCount", ctypes.c_uint64), ("ButtonChangeType", ctypes.c_int32)]
    class POINTER_PEN_INFO(ctypes.Structure):
        _fields_ = [("pointerInfo", POINTER_INFO), ("penFlags", ctypes.c_uint32), ("penMask", ctypes.c_uint32),
                    ("pressure", ctypes.c_uint32), ("rotation", ctypes.c_uint32),
                    ("tiltX", ctypes.c_int32), ("tiltY", ctypes.c_int32)]
    return POINTER_INFO, POINTER_PEN_INFO


class PenPressure:
    """Optional pen pressure through Windows Ink (WM_POINTER messages). Windows only; anywhere else, or if
    anything fails, it stays unavailable and the app behaves exactly like with a mouse.
    `scale()` returns 1.0 whenever no pen is touching the tablet."""
    WM_POINTERUPDATE, WM_POINTERDOWN, WM_POINTERUP = 0x0245, 0x0246, 0x0247
    PT_PEN, FLAG_INCONTACT, MASK_PRESSURE = 3, 0x4, 0x1

    def __init__(self):
        self.available = False     # hook installed
        self.seen = False          # a pen has been used at least once
        self.pressure = 1.0        # 0..1 of the last pen sample
        self.in_contact = False
        self.mode = PEN_DEFAULT_MODE
        self._old = None; self._cb = None; self._hwnd = None

    def scale(self):
        if self.mode == "OFF" or not self.in_contact: return 1.0
        return max(PEN_MIN_SCALE, min(1.0, self.pressure) ** PEN_CURVE)

    def cycle_mode(self):
        self.mode = PEN_MODES[(PEN_MODES.index(self.mode) + 1) % len(PEN_MODES)]

    def attach(self):
        if sys.platform != "win32": return False
        try:
            import ctypes
            from ctypes import wintypes
            hwnd = pygame.display.get_wm_info()["window"]
            if self.available and self._hwnd == hwnd: return True      # already hooked on this window
            POINTER_INFO, POINTER_PEN_INFO = _pen_structs()
            user32 = ctypes.windll.user32
            LRESULT = ctypes.c_ssize_t
            WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
            setp = getattr(user32, "SetWindowLongPtrW", None) or user32.SetWindowLongW
            setp.restype = ctypes.c_void_p; setp.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
            call = user32.CallWindowProcW
            call.restype = LRESULT; call.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            user32.GetPointerType.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
            user32.GetPointerPenInfo.argtypes = [ctypes.c_uint32, ctypes.POINTER(POINTER_PEN_INFO)]
            me = self
            def proc(h, msg, wp, lp):
                try:
                    if msg in (me.WM_POINTERUPDATE, me.WM_POINTERDOWN, me.WM_POINTERUP):
                        pid = wp & 0xFFFF
                        ptype = ctypes.c_uint32()
                        if user32.GetPointerType(pid, ctypes.byref(ptype)) and ptype.value == me.PT_PEN:
                            info = POINTER_PEN_INFO()
                            if user32.GetPointerPenInfo(pid, ctypes.byref(info)):
                                contact = bool(info.pointerInfo.pointerFlags & me.FLAG_INCONTACT) and msg != me.WM_POINTERUP
                                if info.penMask & me.MASK_PRESSURE:
                                    me.pressure = min(1.0, info.pressure/1024.0)
                                else:
                                    me.pressure = 1.0 if contact else 0.0
                                me.in_contact = contact; me.seen = True
                        else:
                            me.in_contact = False
                except Exception:
                    pass
                return call(me._old, h, msg, wp, lp)
            self._cb = WNDPROC(proc)                       # keep a reference or it gets garbage collected
            GWLP_WNDPROC = -4
            self._old = setp(hwnd, GWLP_WNDPROC, ctypes.cast(self._cb, ctypes.c_void_p))
            self.available = bool(self._old); self._hwnd = hwnd
        except Exception as e:
            print("[PEN] pressure not available:", e)
            self.available = False
        return self.available


# ====================== SMART EDGE ENGINE ======================
def load_edge_chars():
    """EDGES.txt: lines starting with # are comments, everything else is the list of border characters."""
    p = find_asset(EDGES_FILE)
    try:
        if p and os.path.isfile(str(p)):
            txt = "".join(l for l in open(str(p), encoding="utf-8").read().splitlines() if not l.lstrip().startswith("#"))
            txt = "".join(ch for ch in txt if not ch.isspace())
            if txt: return txt
    except Exception as e:
        print("[EDGES] could not read", p, e)
    return DEFAULT_EDGE_CHARS


def _blur2(a):
    """Two passes of a [1 2 1] blur over the last two axes (a is N,H,W)."""
    p = np.pad(a, ((0,0),(1,1),(1,1)), mode="edge")
    h = (p[:,:,:-2] + 2*p[:,:,1:-1] + p[:,:,2:]) * 0.25
    a = (h[:,:-2,:] + 2*h[:,1:-1,:] + h[:,2:,:]) * 0.25
    p = np.pad(a, ((0,0),(1,1),(1,1)), mode="edge")
    h = (p[:,:,:-2] + 2*p[:,:,1:-1] + p[:,:,2:]) * 0.25
    return (h[:,:-2,:] + 2*h[:,1:-1,:] + h[:,2:,:]) * 0.25


class EdgeEngine:
    """Picks border characters by SHAPE. The tone grid is treated as a low-res picture: every border cell
    is upsampled to pixels using its 3x3 neighbourhood, and the glyph of the edge set whose blurred ink
    pattern matches that local silhouette best is chosen (works with any font)."""
    def __init__(self, font, cw, ch, chars):
        self.cw, self.ch = cw, ch
        pats, ink, keep = [], [], []
        for c in dict.fromkeys(chars):
            if c.isspace(): continue
            try:
                surf = font.render(c, True, (255,255,255), (0,0,0))
                a = pygame.surfarray.array3d(surf)[:,:,0].T.astype(np.float32) / 255.0
            except Exception:
                continue
            out = np.zeros((ch, cw), np.float32)
            h = min(ch, a.shape[0]); w = min(cw, a.shape[1]); out[:h,:w] = a[:h,:w]
            if out.sum() <= 0: continue
            keep.append(c); pats.append(out); ink.append(float(out.mean()))
        self.chars = keep
        self.codes = np.array([ord(c) for c in keep], dtype=np.int32)
        G = np.stack(pats) if pats else np.zeros((0, ch, cw), np.float32)
        Gb = _blur2(G) if len(G) else G
        Gn = Gb / np.maximum(Gb.reshape(len(G), -1).max(axis=1), 1e-6)[:,None,None] if len(G) else Gb
        self.Gn = Gn.reshape(len(G), -1).astype(np.float32)
        self.Gn_sq = (self.Gn**2).sum(axis=1)
        self.ink = np.array(ink, dtype=np.float32)
        dense = [self.ink[i] for i, c in enumerate(keep) if c in "$@#8&MW"]
        self.K = 1.0 / max(0.05, float(np.median(dense)) if dense else 0.3)    # ink of a fully covered cell
        # tone of an edge glyph when a .txt is loaded (so it still counts as drawing)
        self.tone_of = {c: 1.0 - float(np.clip(self.ink[i]*self.K, 0.4, 1.0)) for i, c in enumerate(keep)}
        # pixel -> neighbour sampling for the bilinear upsample of one cell
        py, px = np.mgrid[0:ch, 0:cw]
        ux = (px + 0.5)/cw - 0.5; uy = (py + 0.5)/ch - 0.5
        self.ox = np.where(ux >= 0, 1, -1).astype(np.int32); self.oy = np.where(uy >= 0, 1, -1).astype(np.int32)
        self.tx = np.abs(ux).astype(np.float32); self.ty = np.abs(uy).astype(np.float32)

    def codes_for(self, buf, ys, xs):
        """ys,xs: arrays of cell coordinates. Returns int32 codes (0 = keep the normal tone character)."""
        res = np.zeros(len(ys), dtype=np.int32)
        if len(ys) == 0 or len(self.chars) == 0: return res
        f = 1.0 - buf.astype(np.float32)
        fp = np.pad(f, 2, mode="edge")                 # canvas border is not an edge
        Y = ys + 2; X = xs + 2
        c = fp[Y, X]
        nmin = np.full(len(ys), 9.0, dtype=np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy or dx: nmin = np.minimum(nmin, fp[Y+dy, X+dx])
        sel = np.nonzero((c > EDGE_INK_MIN) & (nmin < EDGE_BG_MAX))[0]
        if len(sel) == 0: return res
        Ys = Y[sel][:,None,None]; Xs = X[sel][:,None,None]
        oy = self.oy[None]; ox = self.ox[None]; tx = self.tx[None]; ty = self.ty[None]
        T = ((1-tx)*(1-ty)*fp[Ys, Xs] + tx*(1-ty)*fp[Ys, Xs+ox] +
             (1-tx)*ty*fp[Ys+oy, Xs] + tx*ty*fp[Ys+oy, Xs+ox])
        T = np.clip((T - EDGE_UP_THRESH)/0.3 + 0.5, 0.0, 1.0)         # soft threshold -> silhouette
        cov = T.reshape(len(sel), -1).mean(axis=1)
        ok = (cov > 0.03) & (cov < 0.93)                              # full cells keep their tone char
        if not ok.any(): return res
        sel = sel[ok]; T = T[ok]; cov = cov[ok]
        Tb = _blur2(T).reshape(len(sel), -1)
        Tn = Tb / np.maximum(Tb.max(axis=1), 1e-6)[:,None]
        P = Tn.shape[1]
        err = (self.Gn_sq[None,:] + (Tn**2).sum(axis=1)[:,None] - 2.0*(Tn @ self.Gn.T)) / P
        err = err + EDGE_MASS_W*np.abs(self.K*self.ink[None,:] - cov[:,None])
        res[sel] = self.codes[np.argmin(err, axis=1)]
        return res


# ====================== CANVAS ======================
class ASCIICanvas:
    """buf: tone [0..1] (0 light, 1 dark). col: per-cell text luminance [0..1]."""
    def __init__(self, rows, cols):
        self.rows, self.cols = rows, cols
        self.aspect = 1.0        # cell height / cell width, set by App (see BRUSH_ROUND_IN_PIXELS)
        self.buf = np.zeros((rows, cols), dtype=np.float32)               # tones
        self.col = np.full((rows, cols), TEXT_LUMA, dtype=np.float32)     # RGB luma
        self.ov  = np.zeros((rows, cols), dtype=np.int32)                 # forced character (code point), 0 = none (use tone)

    def clear(self, tone_val=1.0, luma=TEXT_LUMA):
        # default clear = darkest
        self.buf[:] = tone_val
        self.col[:] = luma
        self.ov[:] = 0

    def _blend_cell(self, x, y, target, a):
        self.buf[y, x] = self.buf[y, x]*(1.0-a) + target*a
        self.ov[y, x] = 0

    def disc_cells(self, cx, cy, r):
        """Cells under a brush disc (same shape the brush paints). Returns (ys, xs)."""
        if r <= 1:
            if 0 <= cx < self.cols and 0 <= cy < self.rows:
                return np.array([cy]), np.array([cx])
            return np.array([], dtype=int), np.array([], dtype=int)
        R = r - 0.5
        ry = int(r/self.aspect) + 1
        y0 = max(0, cy-ry); y1 = min(self.rows-1, cy+ry); x0 = max(0, cx-r); x1 = min(self.cols-1, cx+r)
        if y1 < y0 or x1 < x0:
            return np.array([], dtype=int), np.array([], dtype=int)
        yy, xx = np.mgrid[y0:y1+1, x0:x1+1]
        m = (xx-cx)**2 + ((yy-cy)*self.aspect)**2 <= R*R
        return yy[m], xx[m]

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
        ry = r/self.aspect + 1
        y0 = max(0, int(cy-ry)); y1 = min(self.rows-1, int(cy+ry))
        for y in range(y0, y1+1):
            dy = (y - cy)*self.aspect
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
                self.buf[cy, cx] = clamp01(self.buf[cy, cx] + delta*a); self.ov[cy, cx] = 0
            return
        R = r - 0.5; R2 = R*R
        x0 = max(0, int(cx-r)); x1 = min(self.cols-1, int(cx+r))
        ry = r/self.aspect + 1
        y0 = max(0, int(cy-ry)); y1 = min(self.rows-1, int(cy+ry))
        for y in range(y0, y1+1):
            dy = (y - cy)*self.aspect
            for x in range(x0, x1+1):
                dx = x - cx; d2 = dx*dx + dy*dy
                if d2 <= R2:
                    scale = 1.0
                    if soft:
                        t = clamp01(1.0 - math.sqrt(d2)/max(1e-6, R))
                        scale = t**1.5
                    self.buf[y, x] = clamp01(self.buf[y, x] + delta*a*scale); self.ov[y, x] = 0

    # ---- smudge: pushes ink (1 - tone) along a direction, conserving it ----
    def smudge_step(self, cx, cy, r, dx, dy, strength):
        """Moves part of the ink under the brush disc by one step (dx,dy in cells, each -1..1).
        Ink is conserved: it piles up in front of the brush until a cell is full (tone 0); what does not fit
        stays where it was, and nothing is pushed out of the canvas."""
        if dx == 0 and dy == 0: return
        ys, xs = self.disc_cells(cx, cy, r)
        if len(ys) == 0: return
        R = max(0.5, r - 0.5)
        d = np.sqrt((xs - cx)**2 + ((ys - cy)*self.aspect)**2)
        w = np.clip(1.0 - d/(R + 0.5), 0.0, 1.0)
        w = w*w*(3.0 - 2.0*w)                                    # smooth falloff to the rim
        ink = 1.0 - self.buf
        move = ink[ys, xs]*w*float(strength)
        ty = ys + dy; tx = xs + dx
        ok = (ty >= 0) & (ty < self.rows) & (tx >= 0) & (tx < self.cols)
        move = np.where(ok, move, 0.0).astype(np.float32)
        tyc = np.clip(ty, 0, self.rows-1); txc = np.clip(tx, 0, self.cols-1)
        room = np.maximum(1.0 - ink[tyc, txc], 0.0)               # a cell that is already full takes nothing
        dep = np.minimum(move, room)                              # what does not fit simply stays where it was
        new = ink.copy()
        new[ys, xs] -= dep
        np.add.at(new, (tyc, txc), dep)
        new = np.clip(new, 0.0, 1.0)
        for yy, xx in ((ys, xs), (tyc[ok], txc[ok])):
            self.buf[yy, xx] = 1.0 - new[yy, xx]
            self.ov[yy, xx] = 0

    # ---- luma discs (RGB) ----
    def luma_disc_blend(self, cx, cy, r, target_l, a, soft):
        if r <= 1:
            if 0<=cx<self.cols and 0<=cy<self.rows:
                self._blend_luma_cell(cx, cy, target_l, a)
            return
        R = r - 0.5; R2 = R*R
        x0 = max(0, int(cx-r)); x1 = min(self.cols-1, int(cx+r))
        ry = r/self.aspect + 1
        y0 = max(0, int(cy-ry)); y1 = min(self.rows-1, int(cy+ry))
        for y in range(y0, y1+1):
            dy = (y - cy)*self.aspect
            for x in range(x0, x1+1):
                dx = x - cx; d2 = dx*dx + dy*dy
                if d2 <= R2:
                    aa = a
                    if soft:
                        t = clamp01(1.0 - math.sqrt(d2)/max(1e-6, R))
                        aa = a*(t**1.5)
                    self._blend_luma_cell(x, y, target_l, aa)

    # ---- blur ----
    def blur_disc(self, cx, cy, radius, alpha=1.0, soft=False):
        r = max(1, radius); R2 = (r-0.5)*(r-0.5)
        x0 = max(0, cx-r); x1 = min(self.cols-1, cx+r)
        ry = int(math.ceil(r/self.aspect))
        y0 = max(0, cy-ry); y1 = min(self.rows-1, cy+ry)
        patch = self.buf[y0:y1+1, x0:x1+1]
        if patch.size == 0: return
        k = np.array([[1,2,1],[2,4,2],[1,2,1]], dtype=np.float32) / 16.0
        padded = np.pad(patch, ((1,1),(1,1)), mode='edge')
        out = (padded[0:-2,0:-2]*k[0,0] + padded[0:-2,1:-1]*k[0,1] + padded[0:-2,2:]*k[0,2] +
               padded[1:-1,0:-2]*k[1,0] + padded[1:-1,1:-1]*k[1,1] + padded[1:-1,2:]*k[1,2] +
               padded[2:,0:-2]*k[2,0] + padded[2:,1:-1]*k[2,1] + padded[2:,2:]*k[2,2])
        hh, ww = out.shape
        yy, xx = np.ogrid[0:hh, 0:ww]
        dy = (yy - (cy - y0))*self.aspect; dx = xx - (cx - x0)
        d2 = dx*dx + dy*dy
        mask = d2 <= R2
        wgt = np.full(out.shape, float(alpha), dtype=np.float32)           # brush opacity
        if soft:                                                           # same falloff as the paint brush
            t = np.clip(1.0 - np.sqrt(d2)/max(1e-6, math.sqrt(R2)), 0.0, 1.0)
            wgt = wgt*(t**1.5).astype(np.float32)
        patch[mask] = patch[mask]*(1.0 - wgt[mask]) + out[mask]*wgt[mask]
        self.ov[y0:y1+1, x0:x1+1][mask] = 0

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
        A = self.aspect
        miny = max(0, int(min(y0, y1) - r/A - 1))
        maxy = min(self.rows-1, int(max(y0, y1) + r/A + 1))
        for y in range(miny, maxy+1):
            for x in range(minx, maxx+1):
                cx, cy, _ = self._closest_point_to_segment(x, y*A, x0, y0*A, x1, y1*A)
                dx, dy = (x - cx), (y*A - cy)
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



# ====================== BOMB ENGINE ======================
class BombPlan:
    """Everything the explosion needs, computed once: the crater, and for every piece of ink in the crater a
    straight flight path with a trail that gets stronger towards the landing cell."""
    def ink_at(self, tau):
        """Ink (0..1) of the whole canvas at blast time tau (0..1). The wave front leaves the centre like a ripple;
        a cell is emptied when the front reaches it, and its ink starts flying from that moment."""
        out = np.where(tau >= self.tr, self.base, self.orig)
        released = tau >= self.tr
        if self.P:
            g = np.clip((tau - self.trp) / np.maximum(1.0 - self.trp, 1e-6), 0.0, 1.0)      # flight progress of every piece
            vt = self.trp[self.vi] + self.vf * (1.0 - self.trp[self.vi])                      # moment each trail cell appears
            m = vt <= tau + 1e-9
            np.add.at(out, (self.vy[m], self.vx[m]), self.va[m])
            fl = (g > 0.0) & (g < 1.0)                                                         # pieces still flying
            if fl.any():
                t = g[fl] * self.L[fl]
                hx = np.rint(self.sx[fl] + self.ux[fl] * t).astype(int); hy = np.rint(self.sy[fl] + self.uy[fl] * t / self.aspect).astype(int)
                ok = (hx >= 0) & (hx < out.shape[1]) & (hy >= 0) & (hy < out.shape[0])
                np.maximum.at(out, (hy[ok], hx[ok]), self.a[fl][ok])
        if BOMB_RING > 0 and 0.0 < tau < BOMB_WAVE:                                           # the bright ring on the front
            front = tau / BOMB_WAVE * self.Lc
            ring = (np.abs(self.d - front) <= 0.8) & self.disc
            out = np.where(ring, np.maximum(out, BOMB_RING * (1.0 - tau / BOMB_WAVE) + out * 0.0), out)
        out = np.clip(out, 0.0, 1.0)
        # a ceiling that rises smoothly from the centre to the tip of every ray: dense areas keep a long gradation
        # instead of piling the trails back up to the densest character
        out = np.where(released & self.disc, np.minimum(out, self.ceil), out)
        return out

    def flash_ink(self):
        out = self.orig.copy(); out[self.core] = 1.0
        return out


def bomb_plan(ink, cx, cy, R, aspect, rng, alpha=1.0):
    """ink = 1 - tone of the canvas. R is in cell widths (the blast is round in pixels, like the brush).
    Like a radial smudge: every direction has its own reach. Ink is pushed outward along that direction, the cells it
    leaves keep less ink the closer they are to the centre (a void that fades toward the tips), and the pushed ink
    leaves a trail that gets stronger toward the point where it lands."""
    rows, cols = ink.shape
    yy, xx = np.mgrid[0:rows, 0:cols]
    dx = (xx - cx).astype(np.float64); dy = (yy - cy) * aspect
    d = np.hypot(dx, dy)
    th = np.arctan2(dy, dx)
    # a few rays (jittered around the circle), each with its own reach; a cell takes the reach of the rays around it,
    # weighted by how close its direction is to each ray (gradual influence to the sides)
    n = BOMB_RAYS
    ra = (np.arange(n) + rng.uniform(-0.35, 0.35, n)) * (2 * np.pi / n) + rng.uniform(0, 2 * np.pi)
    rr = R * rng.uniform(BOMB_REACH_MIN, BOMB_REACH_MAX, n)
    rr = np.where(rng.random(n) < 0.12, rr * 1.2, rr)                 # a few long spikes
    sig = BOMB_RAY_SPREAD * (2 * np.pi / n)
    dang = (th[..., None] - ra[None, None, :] + np.pi) % (2 * np.pi) - np.pi
    w = np.exp(-(dang / sig) ** 2)
    Lc = (w * rr).sum(-1) / np.maximum(w.sum(-1), 1e-9)               # reach of every cell's direction
    pl = BombPlan(); pl.aspect = aspect
    pl.orig = ink.astype(np.float64).copy()
    pl.core = d <= BOMB_CORE * R
    pl.disc = d <= Lc                                                 # cells the blast touches
    keep = np.where(pl.disc, np.clip((d / np.maximum(Lc, 1e-6)) ** BOMB_KEEP_POW, 0.0, 1.0), 1.0)
    keep[pl.core] = 0.0
    moved = pl.orig * (1.0 - keep) * alpha                           # opacity = how much of the ink the wave pushes
    pl.base = pl.orig - moved
    ceil = np.clip(d / np.maximum(Lc, 1e-6), 0.0, 1.0) ** BOMB_FADE_POW
    pl.ceil = np.maximum(1.0 - alpha * (1.0 - ceil), 0.0)                # opacity relaxes the ceiling (alpha 0 = no ceiling)
    pl.d = d; pl.Lc = Lc
    pl.tr = np.clip(BOMB_WAVE * d / np.maximum(Lc, 1e-6), 0.0, BOMB_WAVE)
    pl.tr[pl.core] = 0.0
    pl.tr[~pl.disc] = 0.0
    sy, sx = np.nonzero(moved > 0.02)
    pl.P = P = len(sy)
    if P == 0: return pl
    a = moved[sy, sx]
    pl.trp = pl.tr[sy, sx]
    dsrc = d[sy, sx]; Ls = Lc[sy, sx]
    ang = np.where(dsrc < 0.3, rng.uniform(0, 2*np.pi, P), th[sy, sx]) + rng.normal(0.0, BOMB_JITTER, P)
    ux, uy = np.cos(ang), np.sin(ang)
    land = dsrc + np.maximum(Ls - dsrc, 0.0) * rng.uniform(0.6, 1.0, P)   # lands near the tip of its direction
    land = np.where(rng.random(P) < 0.10, land * 1.25, land)              # a few shards fly further
    L = np.maximum(land - dsrc, 1.0)
    S = max(3, int(np.ceil(L.max() / 0.5)) + 1)
    f = np.linspace(0.0, 1.0, S)[None, :]
    t = f * L[:, None]
    cxs = np.rint(sx[:, None] + ux[:, None] * t).astype(int)
    cys = np.rint(sy[:, None] + uy[:, None] * t / aspect).astype(int)
    inb = (cxs >= 0) & (cxs < cols) & (cys >= 0) & (cys < rows)
    valid = inb & (t >= np.minimum(1.0, 0.5 * L)[:, None])
    same = (cxs[:, :-1] == cxs[:, 1:]) & (cys[:, :-1] == cys[:, 1:])
    valid[:, :-1] &= ~same                                                       # one deposit per cell: the strongest
    amp = BOMB_TRAIL_GAIN * a[:, None] * (BOMB_TRAIL_MIN + (1.0 - BOMB_TRAIL_MIN) * f ** BOMB_TRAIL_POW)
    pl.vy, pl.vx, pl.va = cys[valid], cxs[valid], amp[valid]
    pl.vf = np.broadcast_to(f, (P, S))[valid]
    pl.vi = np.broadcast_to(np.arange(P)[:, None], (P, S))[valid]
    pl.sx, pl.sy, pl.ux, pl.uy, pl.L, pl.a = sx.astype(np.float64), sy.astype(np.float64), ux, uy, L, a
    return pl


def bomb_radius(brush_radius):
    return min(float(BOMB_R_MAX), BOMB_R_BASE + BOMB_R_PER_BRUSH * (max(1, brush_radius) - 1))


class Bomb:
    def __init__(self, cx, cy, R, t0, alpha, fuse_ms, seed=None):
        self.cx, self.cy, self.R, self.t0, self.alpha, self.fuse_ms = cx, cy, R, t0, alpha, fuse_ms
        self.phase = "fuse"; self.plan = None; self.t_flash = 0; self.t_blast = 0
        self.rng = np.random.default_rng(seed); self.fuse_snd = None

    def fuse_progress(self, now):
        return max(0.0, min(1.0, (now - self.t0) / float(self.fuse_ms)))


def bomb_sound_arrays(freq, fuse_ms=BOMB_FUSE_MS, vol=BOMB_SOUND_VOL):
    """Procedural sounds as float arrays in -1..1: (fuse, explosion). Short and not loud."""
    rng = np.random.default_rng(7)
    # fuse: hiss + crackle with a thin tone that falls in pitch (a bomb coming down)
    n = int(freq * fuse_ms / 1000.0); t = np.arange(n) / float(freq); T = max(t[-1], 1e-6)
    hiss = np.diff(np.convolve(rng.standard_normal(n), np.ones(3) / 3.0, mode="same"), prepend=0.0)
    imp = (rng.random(n) < 0.002) * rng.standard_normal(n) * 6.0
    crack = np.convolve(imp, np.exp(-np.arange(int(freq * 0.004)) / (freq * 0.0008)), mode="same")
    tone = np.sin(2*np.pi*np.cumsum(1900.0 - 1300.0 * (t / T)) / freq) * 0.18
    fuse = (0.35 * hiss + 0.5 * crack + tone) * np.minimum(1.0, t / 0.03) * np.minimum(1.0, (T - t) / 0.06)
    fuse = fuse / max(np.abs(fuse).max(), 1e-9) * 0.5 * vol
    # explosion: low-passed noise burst + a falling thump + a tiny click
    n = int(freq * 0.75); t = np.arange(n) / float(freq); T = t[-1]
    low = np.convolve(rng.standard_normal(n), np.ones(18) / 18.0, mode="same") * np.exp(-t / 0.16)
    thump = np.sin(2*np.pi*np.cumsum(38.0 + 95.0 * np.exp(-t * 9.0)) / freq) * np.exp(-t * 4.5)
    click = rng.standard_normal(n) * np.exp(-t / 0.006) * 0.6
    boom = (0.9 * low + thump + click) * np.minimum(1.0, t / 0.002) * np.minimum(1.0, (T - t) / 0.12)
    boom = boom / max(np.abs(boom).max(), 1e-9) * vol
    return fuse, boom


# ====================== VOICE (a very raw formant speech synthesizer) ======================
# Text -> phonemes (a tiny lexicon + crude spelling rules) -> a source/filter synthesizer in the spirit of the
# old SAM voices. Everything is computed with NumPy, nothing is recorded. Mono, VOICE_RATE Hz.
VOICE_ON_DEFAULT = True
VOICE_RATE = 22050
VOICE_VOL = 0.8
VOICE_PITCH = 104.0            # Hz at the start of a phrase (monotone robot, falls a little)
VOICE_SPEED = 1.0              # 1.0 = normal, 0.8 = faster
VOICE_CRUSH = 56               # amplitude steps per side (gritty low bit depth); 0 = off
VOICE_CHANNEL = 6
VOICE_CAPTIONS = True          # show what the voice says, word by word, in yellow at the top of the canvas
VOICE_CAPTION_HOLD = 0.9       # seconds the whole phrase stays after the last word
VOICE_CAPTION_RGB = (255, 214, 0)
VOICE_FRAME = 110              # samples per control frame (5 ms)

_VOW = {
    "IY": (130, (270, 2290, 3010)), "IH": (100, (390, 1990, 2550)), "EH": (110, (530, 1840, 2480)),
    "AE": (125, (660, 1720, 2410)), "AA": (130, (730, 1090, 2440)), "AO": (130, (570, 840, 2410)),
    "UH": (100, (440, 1020, 2240)), "UW": (130, (300, 870, 2240)), "AH": (100, (640, 1190, 2390)),
    "ER": (130, (490, 1350, 1690)),
}
_DIPH = {"EY": ("EH", "IY", 170), "AY": ("AA", "IY", 190), "OW": ("AO", "UW", 170),
         "AW": ("AA", "UW", 190), "OY": ("AO", "IY", 190)}
_LIQ = {"L": (70, (360, 1300, 2800)), "R": (75, (420, 1250, 1650)), "W": (65, (290, 620, 2200)), "Y": (60, (270, 2200, 3000))}
_NAS = {"M": (80, (270, 1100, 2200)), "N": (75, (270, 1500, 2500)), "NG": (85, (270, 1900, 2500))}
# fricatives: duration, (noise low Hz, high Hz), noise amp, voiced
_FRIC = {"S": (105, (4500, 9500), 0.9, False), "Z": (90, (4500, 9500), 0.7, True),
         "SH": (110, (2200, 6000), 1.0, False), "ZH": (95, (2200, 6000), 0.8, True),
         "F": (90, (1500, 9000), 0.35, False), "V": (75, (1500, 9000), 0.3, True),
         "TH": (90, (1800, 9000), 0.25, False), "DH": (55, (1800, 9000), 0.2, True)}
# stops: closure ms, burst band, voiced
_STOP = {"P": (50, (500, 3000), False), "B": (45, (500, 3000), True), "T": (50, (3000, 9000), False),
         "D": (45, (3000, 9000), True), "K": (55, (1200, 4500), False), "G": (50, (1200, 4500), True)}
_AFF = {"CH": (45, (2200, 6000), False), "JH": (40, (2200, 6000), True)}

VOICE_LEXICON = {
    "palette": "P AE L IH T", "saved": "S EY V D", "restored": "R IY S T AO R D", "paint": "P EY N T",
    "blur": "B L ER", "line": "L AY N", "highlight": "HH AY L AY T", "smart": "S M AA R T",
    "brush": "B R AH SH", "edge": "EH JH", "smudge": "S M AH JH", "bomb": "B AA M", "true": "T R UW",
    "mode": "M OW D", "less": "L EH S", "non": "N AA N", "slop": "S L AA P", "organic": "AO R G AE N IH K",
    "hand": "HH AE N D", "made": "M EY D", "artisanal": "AA R T IH Z AH N L", "no": "N OW",
    "cheating": "CH IY T IH NG", "fire": "F AY ER", "in": "IH N", "the": "DH AH", "hole": "HH OW L",
    "away": "AH W EY", "duck": "D AH K", "and": "AE N D", "cover": "K AH V ER",
    "timelapse": "T AY M L AE P S", "start": "S T AA R T", "stop": "S T AA P", "cleared": "K L IY R D",
    "gif": "JH IH F", "ready": "R EH D IY", "voice": "V OY S", "on": "AA N", "off": "AO F",
    "canvas": "K AE N V AH S", "boom": "B UW M", "sam": "S AE M", "pixel": "P IH K S AH L",
    "letter": "L EH T ER",
    "ink": "IH NG K", "splat": "S P L AE T", "incoming": "IH N K AH M IH NG", "messy": "M EH S IY", "business": "B IH Z N AH S",
    "big": "B IH G", "splash": "S P L AE SH", "here": "HH IY R", "comes": "K AH M Z", "mess": "M EH S",
    "letters": "L EH T ER Z", "everywhere": "EH V R IY W EH R", "scatter": "S K AE T ER", "by": "B AY", "pure": "P Y UH R", "tru": "T R UW", "ascii": "AE S K IY",
}

_LTS_DIGRAPH = [("sh", "SH"), ("ch", "CH"), ("th", "TH"), ("ph", "F"), ("ck", "K"), ("ng", "NG"), ("qu", "K W"),
                ("oo", "UW"), ("ee", "IY"), ("ea", "IY"), ("ai", "EY"), ("ay", "EY"), ("oa", "OW"), ("ou", "AW"),
                ("ow", "OW"), ("oi", "OY"), ("oy", "OY"), ("au", "AO"), ("aw", "AO")]
_LTS_LETTER = {"a": "AE", "b": "B", "c": "K", "d": "D", "e": "EH", "f": "F", "g": "G", "h": "HH", "i": "IH",
               "j": "JH", "k": "K", "l": "L", "m": "M", "n": "N", "o": "AA", "p": "P", "q": "K", "r": "R",
               "s": "S", "t": "T", "u": "AH", "v": "V", "w": "W", "x": "K S", "y": "IY", "z": "Z"}


def voice_phonemes(word):
    """Phonemes of one word: the lexicon first, crude spelling rules for anything else."""
    w = "".join(ch for ch in word.lower() if ch.isalpha())
    if not w: return []
    if w in VOICE_LEXICON: return VOICE_LEXICON[w].split()
    out = []; i = 0
    if len(w) > 3 and w.endswith("e") and w[-2] not in "aeiouy":      # silent final e
        w = w[:-1]
    while i < len(w):
        for dg, ph in _LTS_DIGRAPH:
            if w.startswith(dg, i): out += ph.split(); i += len(dg); break
        else:
            out += _LTS_LETTER[w[i]].split(); i += 1
    return out


def _fmt_envelope(freqs, F, bw=(110.0, 150.0, 220.0)):
    """Spectral shape of a vocal tract with three formants (product of three resonance peaks) and a -6 dB/oct tilt."""
    h = np.ones_like(freqs)
    for Fi, Bi in zip(F, bw):
        h = h / np.sqrt(1.0 + ((freqs**2 - Fi**2) / (freqs * Bi + 1e-9))**2)
    return h * (1.0 / (1.0 + freqs / 1400.0))


class VoiceSynth:
    """phrase -> int16 samples. Deterministic for a given text (own random generator)."""
    def __init__(self, rate=VOICE_RATE):
        self.rate = rate; self._cache = {}; self._timing = {}

    # ---- phoneme string -> control tracks and noise events
    def _plan(self, phones):
        fr = VOICE_FRAME; sp = VOICE_SPEED
        F1 = []; F2 = []; F3 = []; AV = []; PW = []; noise = []     # per frame tracks; noise = (start_frame, n_frames, kind, spec, amp)
        def push(n, f, av, pw=1.0):
            for _ in range(max(1, n)): F1.append(f[0]); F2.append(f[1]); F3.append(f[2]); AV.append(av); PW.append(pw)
        def nfr(ms): return max(1, int(round(ms * sp * self.rate / 1000.0 / fr)))
        last = (500, 1500, 2500)
        bounds = []; wstart = 0
        for i, p in enumerate(phones):
            if p == "_":                                   # word gap
                bounds.append((wstart, len(F1))); push(nfr(45), last, 0.0); wstart = len(F1); continue
            nxt = None
            for q in phones[i + 1:]:
                if q in _VOW or q in _DIPH or q in _LIQ: nxt = _VOW[q][1] if q in _VOW else (_VOW[_DIPH[q][0]][1] if q in _DIPH else _LIQ[q][1]); break
            nxt = nxt or last
            if p in _VOW:
                d, f = _VOW[p]; push(nfr(d), f, 1.0); last = f
            elif p in _DIPH:
                a, b, d = _DIPH[p]; n = nfr(d); fa, fb = _VOW[a][1], _VOW[b][1]
                for k in range(n):
                    t = k / max(1, n - 1); t = t * t * (3 - 2 * t)
                    push(1, tuple(fa[j] + (fb[j] - fa[j]) * t for j in range(3)), 1.0)
                last = fb
            elif p in _LIQ:
                d, f = _LIQ[p]; push(nfr(d), f, 0.8); last = f
            elif p in _NAS:
                d, f = _NAS[p]; push(nfr(d), f, 0.45, 0.6); last = f
            elif p in _FRIC:
                d, band, amp, voiced = _FRIC[p]; n = nfr(d)
                start = len(F1); push(n, nxt, 0.28 if voiced else 0.0)
                noise.append((start, n, "band", band, amp))
            elif p in _STOP:
                clo, band, voiced = _STOP[p]; push(nfr(clo), last, 0.25 if voiced else 0.0)
                bs = len(F1); push(nfr(12), nxt, 0.0); noise.append((bs, nfr(12), "band", band, 0.9))
                if not voiced:
                    asp = len(F1); push(nfr(28), nxt, 0.0); noise.append((asp, nfr(28), "form", nxt, 0.45))
            elif p in _AFF:
                clo, band, voiced = _AFF[p]; push(nfr(clo), last, 0.2 if voiced else 0.0)
                bs = len(F1); push(nfr(75), nxt, 0.25 if voiced else 0.0); noise.append((bs, nfr(75), "band", band, 0.85))
            elif p == "HH":
                s = len(F1); push(nfr(65), nxt, 0.0); noise.append((s, nfr(65), "form", nxt, 0.55))
        bounds.append((wstart, len(F1)))
        self._bounds = bounds
        return [np.array(x, dtype=np.float64) for x in (F1, F2, F3, AV, PW)], noise

    def timing(self, text):
        """[(word, start s, end s)] of a phrase as the synthesizer says it."""
        text = text.strip().lower(); self.render(text)
        return self._timing.get(text, [])

    def _smooth(self, a, w):
        if w <= 1 or len(a) < 2: return a
        k = np.ones(w) / w; pad = np.concatenate([np.full(w, a[0]), a, np.full(w, a[-1])])
        return np.convolve(pad, k, mode="same")[w:-w]

    def render(self, text):
        text = text.strip().lower()
        if text in self._cache: return self._cache[text]
        phones = []
        for wi, word in enumerate(w for w in text.split() if voice_phonemes(w)):
            if wi: phones.append("_")
            phones += voice_phonemes(word)
        if not phones:
            self._cache[text] = np.zeros(1, dtype=np.int16); self._timing[text] = []; return self._cache[text]
        (F1, F2, F3, AV, PW), noise = self._plan(phones)
        words = [w for w in text.split() if voice_phonemes(w)]
        self._timing[text] = [(w, a * VOICE_FRAME / self.rate, b * VOICE_FRAME / self.rate) for w, (a, b) in zip(words, self._bounds)]
        nF = len(F1); fr = VOICE_FRAME; N = nF * fr; rate = self.rate
        rng = np.random.default_rng(sum((i + 1) * ord(c) for i, c in enumerate(text)))
        # coarticulation: glide the formants and the voicing between phonemes
        F1, F2, F3 = (self._smooth(x, 5) for x in (F1, F2, F3)); AVs = self._smooth(AV, 3); PWs = self._smooth(PW, 3)
        # pitch: falls through the phrase, a little lift at every word start
        t = np.arange(N) / rate; dur = N / rate
        f0 = VOICE_PITCH * (1.0 - 0.18 * (t / max(dur, 1e-3)))
        # per-sample control (linear interpolation between frames)
        xs = (np.arange(N) + 0.5) / fr - 0.5; xi = np.arange(nF)
        s_F = [np.interp(xs, xi, x) for x in (F1, F2, F3)]; s_av = np.interp(xs, xi, AVs); s_pw = np.interp(xs, xi, PWs)
        phase = np.cumsum(f0 / rate)
        # voiced source: harmonics shaped by the formant envelope of each frame
        K = int(min(48, (rate * 0.45) / (VOICE_PITCH * 0.85)))
        voiced = np.zeros(N)
        ks = np.arange(1, K + 1)
        # harmonic amplitudes per frame (frames x K), interpolated to samples
        fc = (np.arange(nF) + 0.5) * fr; f0c = np.interp(fc, np.arange(N), f0)
        amps = np.zeros((nF, K))
        for j in range(nF):
            fk = ks * f0c[j]
            amps[j] = _fmt_envelope(fk, (F1[j], F2[j], F3[j])) * (fk < rate * 0.45)
        amps = amps / max(amps.max(), 1e-9)
        for k in range(K):
            a = np.interp(xs, xi, amps[:, k])
            voiced += a * np.sin(2 * np.pi * (k + 1) * phase)
        voiced *= s_av * (0.6 + 0.4 * s_pw)
        # noise events: fricatives, bursts and aspiration, filtered in the frequency domain
        nz = np.zeros(N)
        for (sf, nfm, kind, spec, amp) in noise:
            a0 = sf * fr; n = nfm * fr
            if a0 + n > N: n = N - a0
            if n <= 8: continue
            w = rng.standard_normal(n); W = np.fft.rfft(w); fq = np.fft.rfftfreq(n, 1.0 / rate)
            if kind == "band":
                lo, hi = spec; mask = 1.0 / (1.0 + (lo / np.maximum(fq, 1.0))**4) / (1.0 + (fq / hi)**4)
            else:
                mask = _fmt_envelope(np.maximum(fq, 20.0), spec, bw=(160.0, 220.0, 320.0)) * 6.0
            seg = np.fft.irfft(W * mask, n)
            seg = seg / max(np.abs(seg).max(), 1e-9)
            env = np.minimum(1.0, np.arange(n) / max(1.0, n * 0.25)) * np.minimum(1.0, (n - np.arange(n)) / max(1.0, n * 0.35))
            if kind == "band" and n < 12 * fr: env = env * np.exp(-np.arange(n) / (n * 0.7))        # bursts die quickly
            nz[a0:a0 + n] += seg * env * amp
        sig = voiced / max(np.abs(voiced).max(), 1e-9) * 0.62 + nz * 0.45
        fade = int(rate * 0.004); sig[:fade] *= np.linspace(0, 1, fade); sig[-fade:] *= np.linspace(1, 0, fade)
        sig = np.concatenate([sig, np.zeros(int(rate * 0.03))])
        if VOICE_CRUSH: sig = np.round(sig * VOICE_CRUSH) / VOICE_CRUSH
        peak = max(np.abs(sig).max(), 1e-9)
        out = (sig / peak * 0.9 * VOICE_VOL * 32767).astype(np.int16)
        self._cache[text] = out
        return out


# ====================== POPUPS ======================
class Popup:
    """Floating panel drawn over everything. While one is open it owns the mouse and the keyboard."""
    def draw(self, app, surf, mx, my): pass
    def on_click(self, app, mx, my, button): app.popup = None
    def on_key(self, app, key):
        if key == pygame.K_ESCAPE: app.popup = None
    def on_text(self, app, ch): pass


class PaletteEditorPopup(Popup):
    """Editor of the current palette: its bar on top (click a slot to select it, drag to reorder, - and + at the
    corners to remove / add shading levels), a table of characters to put into the selected slot, and the
    RESTORE / SAVE / SAVE NEW buttons. Every change is applied to the palette at once (live)."""
    BUTTONS = ("RESTORE", "SAVE", "SAVE NEW", "CLOSE")

    def __init__(self, app, idx):
        self.chars = app.table_chars()
        self.cw = app.char_w + 8; self.chh = app.char_h + 4; self.cols = TABLE_COLS
        self.rows = -(-len(self.chars) // self.cols); self.pad = 10
        self.fh = app.font_ui.get_height() + 8
        self.btn_w = 22; self.barh = app.char_h + 10; self.bh = app.font_ui.get_height() + 6
        self.sel = max(0, min(idx, app.pal.n - 2)); self.status = ""; self.drag_idx = None; self.moved = False; self.jump_until = 0
        w = self.cols * self.cw + 2 * self.pad
        h = self.fh + self.barh + self.fh + self.rows * self.chh + 8 + self.bh + self.pad + 2
        x = (app.canvas_px_w - w) // 2; y = app.canvas_offset_y + (app.canvas_px_h - h) // 2
        x = max(4, min(x, app.surface_w - w - 4)); y = max(4, min(y, app.surface_h - h - 4))
        self.rect = pygame.Rect(x, y, w, h)
        by = y + self.fh
        self.minus = pygame.Rect(x + self.pad, by, self.btn_w, self.barh)
        self.plus = pygame.Rect(self.rect.right - self.pad - self.btn_w, by, self.btn_w, self.barh)
        self.bar = pygame.Rect(self.minus.right + 4, by, self.plus.x - 4 - (self.minus.right + 4), self.barh)
        self.gx = x + self.pad; self.gy = by + self.barh + self.fh
        self.foot_y = self.gy + self.rows * self.chh + 6
        fw = [app.font_ui.size(t)[0] + 16 for t in self.BUTTONS]
        self.btns = []; bx = x + self.pad
        for t, wd in zip(self.BUTTONS, fw):
            self.btns.append((t, pygame.Rect(bx, self.foot_y, wd, self.bh))); bx += wd + 6

    @property
    def max_n(self): return max(PAL_MIN_SLOTS, min(PAL_MAX_SLOTS, self.bar.w // 9))

    # ---- geometry
    def slot_rect(self, app, idx):
        """Rect of palette position idx in the bar (same display order as the main bar)."""
        n = app.pal.n; ui = (n - 1 - idx) if PALETTE_BAR_DARK_TO_LIGHT else idx
        a = self.bar.x + ui * self.bar.w // n; b = self.bar.x + (ui + 1) * self.bar.w // n
        return pygame.Rect(a, self.bar.y, max(1, b - a), self.bar.h)

    def slot_at(self, app, mx, my):
        n = app.pal.n
        if not self.bar.collidepoint(mx, my): return None
        ui = min(n - 1, max(0, (mx - self.bar.x) * n // self.bar.w))
        return (n - 1 - ui) if PALETTE_BAR_DARK_TO_LIGHT else ui

    def cell_rect(self, i):
        r, c = divmod(i, self.cols)
        return pygame.Rect(self.gx + c * self.cw, self.gy + r * self.chh, self.cw, self.chh)

    def index_at(self, mx, my):
        c = (mx - self.gx) // self.cw; r = (my - self.gy) // self.chh
        if 0 <= c < self.cols and 0 <= r < self.rows:
            i = r * self.cols + c
            if i < len(self.chars): return i
        return None

    def button_enabled(self, app, name):
        nn = app.pal.index; known = nn in app.pal.map; edited = nn in app.pal.edits
        if name == "CLOSE": return True
        if name in ("RESTORE", "SAVE"): return known and edited
        if name == "SAVE NEW": return known and any(k not in app.pal.map for k in range(1, 11))
        return False

    # ---- actions
    def say(self, app, msg): self.status = msg; app.flash(msg)

    def add_slot(self, app):
        if app.pal.insert_slot(self.sel, self.max_n): app.play_ui_click(); self.status = ""
        else: self.say(app, "MAX SLOTS" if app.pal.n >= self.max_n else "CANNOT ADD HERE")

    def remove_slot(self, app):
        if app.pal.remove_slot(self.sel):
            app.play_ui_click(); self.status = ""; self.sel = min(self.sel, app.pal.n - 2)
        else: self.say(app, "MIN SLOTS")

    def press_button(self, app, name):
        nn = app.pal.index
        if name == "CLOSE": app.popup = None; return
        if not self.button_enabled(app, name): return
        if name == "RESTORE": app.pal.restore(nn); self.sel = min(self.sel, app.pal.n - 2); self.say(app, f"RESTORED {nn:02d}"); app.speak("palette restored")
        elif name == "SAVE": ok, msg = app.pal.save(nn); self.say(app, msg); ok and app.speak("palette saved")
        elif name == "SAVE NEW": ok, msg = app.pal.save_new(nn); self.say(app, msg); ok and app.speak("palette saved")
        app.play_ui_click()

    # ---- input
    def on_click(self, app, mx, my, button):
        if button != 1 or not self.rect.collidepoint(mx, my): return
        if self.minus.collidepoint(mx, my): self.remove_slot(app); return
        if self.plus.collidepoint(mx, my): self.add_slot(app); return
        i = self.slot_at(app, mx, my)
        if i is not None:
            if i >= app.pal.n - 1: self.say(app, "THE DARKEST SLOT STAYS EMPTY")
            else: self.sel = i; self.drag_idx = i; self.moved = False; app.play_ui_click()
            return
        for name, r in self.btns:
            if r.collidepoint(mx, my): self.press_button(app, name); return
        k = self.index_at(mx, my)
        if k is not None and app.pal.set_char(self.sel, self.chars[k]):
            app.play_ui_click(); self.status = ""

    def on_drag(self, app, mx, my):
        """Dragging a slot along the bar moves its character."""
        if self.drag_idx is None: return
        j = self.slot_at(app, mx, my)
        if j is None or j >= app.pal.n - 1 or j == self.drag_idx: return
        if app.pal.move_slot(self.drag_idx, j): self.drag_idx = self.sel = j; self.moved = True

    def on_release(self, app): self.drag_idx = None

    def on_key(self, app, key):
        if key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER): app.popup = None
        elif key == pygame.K_LEFT:  self.sel = min(app.pal.n - 2, self.sel + 1) if PALETTE_BAR_DARK_TO_LIGHT else max(0, self.sel - 1)
        elif key == pygame.K_RIGHT: self.sel = max(0, self.sel - 1) if PALETTE_BAR_DARK_TO_LIGHT else min(app.pal.n - 2, self.sel + 1)

    def on_text(self, app, ch):
        """Typing a character puts it into the selected slot and the table jumps to it (the +/- buttons add/remove slots)."""
        if len(ch) != 1 or not ch.isprintable(): return
        if ch.isspace(): self.say(app, "ONLY THE DARKEST SLOT IS A SPACE"); return
        if ch not in self.chars: self.say(app, f"'{ch}' IS NOT IN THE FONT"); return
        if self.sel >= app.pal.n - 1: return
        app.pal.set_char(self.sel, ch)
        self.jump_until = pygame.time.get_ticks() + 450; self.status = ""
        app.play_ui_click()

    # ---- drawing
    def _small_btn(self, app, surf, r, label, enabled, hov):
        pygame.draw.rect(surf, HOVER_FILL if (hov and enabled) else GREY10, r, 0, border_radius=3)
        col = (WHITE if hov else GREY_TEXT) if enabled else GREY50
        pygame.draw.rect(surf, col, r, 1, border_radius=3)
        t = app.font_ui.render(label, True, col)
        surf.blit(t, (r.x + (r.w - t.get_width()) // 2, r.y + (r.h - t.get_height()) // 2))

    def draw(self, app, surf, mx, my):
        pal = app.pal; n = pal.n; f = app.font_ui
        if self.sel > n - 2: self.sel = max(0, n - 2)
        pygame.draw.rect(surf, BLACK, self.rect); pygame.draw.rect(surf, CYAN, self.rect, 1)
        edited = pal.index in pal.edits
        surf.blit(f.render(f"EDIT {pal.display_name}" + (" *" if edited else ""), True, RED if edited else CYAN), (self.rect.x + self.pad, self.rect.y + 5))
        # the palette bar
        self._small_btn(app, surf, self.minus, "-", n > PAL_MIN_SLOTS, self.minus.collidepoint(mx, my))
        self._small_btn(app, surf, self.plus, "+", n < self.max_n, self.plus.collidepoint(mx, my))
        pygame.draw.rect(surf, GREY50, self.bar, 1)
        hov_slot = self.slot_at(app, mx, my)
        for idx in range(n):
            r = self.slot_rect(app, idx); last = idx == n - 1
            if idx == self.sel: pygame.draw.rect(surf, (0, 60, 70), r.inflate(-2, -2)); pygame.draw.rect(surf, CYAN, r.inflate(-2, -2), 2)
            elif idx == hov_slot and not last: pygame.draw.rect(surf, HOVER_FILL, r.inflate(-2, -2))
            if last: pygame.draw.line(surf, GREY50, (r.x + 3, r.centery), (r.right - 4, r.centery), 1)   # the darkest slot: locked
            else:
                g = app.glyphs.get(pal.chars[idx], WHITE if idx == self.sel else GREY_TEXT)
                surf.blit(g, (r.centerx - g.get_width() // 2, r.centery - g.get_height() // 2))
        # info row
        cur = pal.chars[self.sel] if self.sel < n - 1 else " "
        left = f"SLOT {n - 1 - self.sel} OF {n - 1}:  '{cur}'   {n} LEVELS"
        surf.blit(f.render(left, True, GREY_TEXT), (self.rect.x + self.pad, self.bar.bottom + 5))
        hov = self.index_at(mx, my)
        right = self.status or ("TYPE A CHARACTER OR DRAG A SLOT" if hov is None else f"'{self.chars[hov]}'  U+{ord(self.chars[hov]):04X}")
        rt = f.render(right, True, WHITE if self.status else GREY)
        surf.blit(rt, (self.rect.right - self.pad - rt.get_width(), self.bar.bottom + 5))
        # the table
        for i, ch in enumerate(self.chars):
            r = self.cell_rect(i)
            if i == hov: pygame.draw.rect(surf, HOVER_FILL, r); pygame.draw.rect(surf, WHITE, r, 1)
            elif ch == cur:
                if pygame.time.get_ticks() < self.jump_until: pygame.draw.rect(surf, (0, 60, 70), r)
                pygame.draw.rect(surf, CYAN, r, 2 if pygame.time.get_ticks() < self.jump_until else 1)
            surf.blit(app.glyphs.get(ch, WHITE if (i == hov or ch == cur) else GREY_TEXT), (r.x + 4, r.y + 2))
        # buttons
        for name, r in self.btns:
            self._small_btn(app, surf, r, name, self.button_enabled(app, name), r.collidepoint(mx, my))


class MenuPopup(Popup):
    """Small list of actions. items = [(label, function(app) or None when disabled)]."""
    def __init__(self, app, title, items, pos):
        self.title = title; self.items = items
        self.lh = app.font_ui.get_height() + 6
        w = max(app.font_ui.size(t)[0] for t in [title] + [l for l, _ in items]) + 24
        h = self.lh * (len(items) + 1) + 8
        x = max(2, min(pos[0], app.surface_w - w - 2)); y = max(2, min(pos[1], app.surface_h - h - 2))
        self.rect = pygame.Rect(x, y, w, h)

    def item_rect(self, i):
        return pygame.Rect(self.rect.x + 4, self.rect.y + 4 + self.lh * (i + 1), self.rect.w - 8, self.lh)

    def draw(self, app, surf, mx, my):
        pygame.draw.rect(surf, BLACK, self.rect); pygame.draw.rect(surf, CYAN, self.rect, 1)
        surf.blit(app.font_ui.render(self.title, True, CYAN), (self.rect.x + 10, self.rect.y + 7))
        for i, (label, fn) in enumerate(self.items):
            r = self.item_rect(i)
            hov = fn is not None and r.collidepoint(mx, my)
            if hov: pygame.draw.rect(surf, HOVER_FILL, r)
            col = (WHITE if hov else GREY_TEXT) if fn is not None else GREY50
            surf.blit(app.font_ui.render(label, True, col), (r.x + 6, r.y + 3))

    def on_click(self, app, mx, my, button):
        fn = None
        if button == 1:
            for i, (label, f) in enumerate(self.items):
                if self.item_rect(i).collidepoint(mx, my): fn = f
        app.popup = None
        if fn is not None: fn(app)


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

        self.popup = None                    # floating character table / palette menu
        self.bombs = []                      # bombs in flight (fuse, flash or blast)
        self._bomb_snds = None
        self._tip_key = None; self._tip_since = 0
        self._last_sphere_click = None       # (ticks, palette char index) for double click on the tone sphere
        self._last_bar_click = None          # (ticks, palette char index) for double-click detection
        self.opacity_slider_rect = None
        self._table_chars = None
        self.overlay_image = None
        self.overlay_src = None      # original overlay image (rescaled when the canvas is resized)
        self.overlay_visible = False

        # Fonts & surfaces
        self.font = pygame.font.SysFont(FONT_NAME, FONT_SIZE)
        self.font_small = pygame.font.SysFont(FONT_NAME, max(10, FONT_SIZE-2))
        self.font_ui = pygame.font.SysFont(FONT_NAME, UI_FONT_SIZE)
        self.font_tl = pygame.font.SysFont(FONT_NAME, 11)          # tiny font for the T.LAPSE row
        self.font_help = pygame.font.SysFont(FONT_NAME, HELP_FONT_SIZE)
        self.char_w, self.char_h = self.font.size("M")
        self.glyphs = GlyphCache(self.font)
        self.edge = EdgeEngine(self.font, self.char_w, self.char_h, load_edge_chars())
        self.font_picker = pygame.font.SysFont(FONT_NAME, PICKER_FONT_SIZE)
        self.pk_w, self.pk_h = self.font_picker.size("M")      # character cell of the tone sphere
        self.glyphs_picker = GlyphCache(self.font_picker)
        # Compute rows to target ~4:3 aspect with fixed MAX_COLS using actual font metrics
        global COLS, ROWS, WINDOW_SCALE
        self.base_scale = WINDOW_SCALE          # configured scale, before auto-fit
        self.flash_msg = ""; self.flash_until = 0
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
        self.pen = PenPressure()
        self.pen.attach()
        self.surface = pygame.Surface((self.surface_w, self.surface_h))
        self.canvas_offset_y = (self.surface_h - self.canvas_px_h) // 2


        self.canvas = ASCIICanvas(ROWS, COLS)
        self.canvas.aspect = (self.char_h/float(self.char_w)) if BRUSH_ROUND_IN_PIXELS else 1.0
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
        _hb = self._indicator_box_size()[1]
        _stack_bottom = self.picker_rect.top + 6*_hb + 5*IND_GAP_Y                 # bottom of the HLIGHT..LINEAA stack
        self.tl_rect = pygame.Rect(self.canvas_px_w+UI_MARGIN, max(self.picker_rect.bottom, _stack_bottom)+TL_ROW_GAP,
                                   SIDEBAR_W-2*UI_MARGIN, TL_ROW_H)            # T.LAPSE row (parts computed per draw)
        self._tl_wipe_until = 0
        self.palette_rect = pygame.Rect(self.canvas_px_w+UI_MARGIN, self.tl_rect.bottom+TL_ROW_GAP,
                                        SIDEBAR_W-2*UI_MARGIN, PALETTE_BAR_H)

        # Palette shortcut bar (slots are computed from this rect, so it moves with the sidebar)
        self.palslot_rect = pygame.Rect(self.canvas_px_w+UI_MARGIN, self.palette_rect.bottom+PAL_SLOT_BAR_GAP,
                                        SIDEBAR_W-2*UI_MARGIN, PAL_SLOT_H)

        # Indicators
        self.ind_labels = ["HLIGHT","SOFT","PAINT","BLUR","LINE","LINEAA"]
        self.ind_rects = []

        # Buttons: one compact row NEW LOAD IMPORT SAVE
        BTN_GAP = 4
        self.btn_h = 24
        self.btn_w = (SIDEBAR_W - 2*UI_MARGIN - 3*BTN_GAP)//4
        row1_y = self.palslot_rect.bottom + UI_MARGIN//2
        left_x = self.canvas_px_w + UI_MARGIN
        step = self.btn_w + BTN_GAP
        self.new_btn    = pygame.Rect(left_x,          row1_y, self.btn_w, self.btn_h)
        self.load_btn   = pygame.Rect(left_x + step,   row1_y, self.btn_w, self.btn_h)
        self.import_btn = pygame.Rect(left_x + 2*step, row1_y, self.btn_w, self.btn_h)
        self.save_btn   = pygame.Rect(left_x + 3*step, row1_y, self.btn_w, self.btn_h)
        self.hovered_btn = None; self.pressed_btn = None

        # Smart tools row (toggle buttons)
        row2_y = row1_y + self.btn_h + BTN_GAP
        half_w = (SIDEBAR_W - 2*UI_MARGIN - BTN_GAP)//2
        self.smart_btn = pygame.Rect(left_x, row2_y, half_w, self.btn_h)
        self.edge_btn  = pygame.Rect(left_x + half_w + BTN_GAP, row2_y, half_w, self.btn_h)

        row3_y = row2_y + self.btn_h + BTN_GAP
        self.smudge_btn = pygame.Rect(left_x, row3_y, half_w, self.btn_h)
        self.bomb_btn = pygame.Rect(left_x + half_w + BTN_GAP, row3_y, half_w, self.btn_h)

        row4_y = row3_y + self.btn_h + BTN_GAP
        self.tru_btn = pygame.Rect(left_x, row4_y, SIDEBAR_W - 2*UI_MARGIN, self.btn_h)

        # Grid UI elements (below the button rows)
        grid_top = row4_y + self.btn_h + UI_MARGIN//2
        checkbox_size = 16
        self.grid_checkbox_rect = pygame.Rect(self.canvas_px_w+UI_MARGIN, grid_top, checkbox_size, checkbox_size)
        self.grid_label_rect = pygame.Rect(self.grid_checkbox_rect.right+8, grid_top, 80, checkbox_size)
        self.voice_checkbox_rect = pygame.Rect(self.canvas_px_w + UI_MARGIN + 142, grid_top, checkbox_size, checkbox_size)
        self.voice_label_rect = pygame.Rect(self.voice_checkbox_rect.right + 6, grid_top, 60, checkbox_size)

        y2 = grid_top + checkbox_size + 4
        btn_w_small, btn_h_small = 22, 20
        # Cols controls
        self.grid_cols_minus = pygame.Rect(self.canvas_px_w+UI_MARGIN, y2, btn_w_small, btn_h_small)
        self.grid_cols_plus  = pygame.Rect(self.grid_cols_minus.right+60, y2, btn_w_small, btn_h_small)
        self.grid_cols_val_rect = pygame.Rect(self.grid_cols_minus.right+8, y2, 50, btn_h_small)
        # Rows controls (next line)
        y3 = y2 + btn_h_small + 4
        self.grid_rows_minus = pygame.Rect(self.canvas_px_w+UI_MARGIN, y3, btn_w_small, btn_h_small)
        self.grid_rows_plus  = pygame.Rect(self.grid_rows_minus.right+60, y3, btn_w_small, btn_h_small)
        self.grid_rows_val_rect = pygame.Rect(self.grid_rows_minus.right+8, y3, 50, btn_h_small)

        # State
        self.current_value = 0.2       # start somewhat light to paint on dark bg
        self.brush_radius  = INITIAL_BRUSH_RADIUS
        self.brush_alpha   = 1.0
        self.fade_on = False; self.fade_speed = 0.5            # FADE: the stroke starts at the chosen opacity and dies out along its path
        self.fade_dist = 0.0; self.fade_last = None            # distance travelled by the current stroke (in cells), last cell seen
        self.fade_box_rect = self.fade_label_rect = self.fade_slider_rect = None; self._op_slider_geom = None
        self.soft_edge = False
        self.line_aa   = True

        # Modes: 'paint' | 'blur' | 'line' | 'hlight'
        self.mode = "paint"
        self.tru_cursor = None          # (col,row) of the TRU typing cursor
        self.voice_on = VOICE_ON_DEFAULT; self.voice = VoiceSynth(); self._voice_snd = {}; self.last_spoken = ""
        self._voice_rng = random.Random(); self._voice_mode = "paint"; self.caption = None
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
        self.smudge_last=None        # last cell of the current smudge stroke
        self.picker_drag=None        # "sphere" / "bar" while LMB is held on the tone picker
        self.picker_pick=None        # (col,row) of the sphere cell that is selected
        self._picker_grid=None       # {(col,row): (rect, tone)}, built once
        self._picker_center=(0, 0)
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
            self.overlay_src = img
            self.overlay_image = None
            self._fit_overlay()
            self.overlay_visible = True
            print(f"[OVERLAY] Loaded: {path}")
        except Exception as e:
            print("Overlay load error:", e)


    def _fit_overlay(self):
        """Scale the overlay source image to the current canvas size."""
        if self.overlay_src is None: return
        img = pygame.transform.smoothscale(self.overlay_src, (self.canvas_px_w, self.canvas_px_h))
        img.set_alpha(int(clamp01(OVERLAY_OPACITY) * 255))
        self.overlay_image = img

    def draw_overlay_if_needed(self, surf):
        """Draw the overlay image on top of the canvas if enabled."""
        if self.overlay_image and self.overlay_visible:
            oy = getattr(self, 'canvas_offset_y', 0)
            surf.blit(self.overlay_image, (0, oy))


    def _tl_parts(self):
        """Rects of the T.LAPSE row: REC button, frame bar, frame count, GIF and CLR buttons."""
        r = self.tl_rect; f = self.font_tl
        clr = pygame.Rect(r.right - 34, r.y, 34, r.h)
        exp = pygame.Rect(clr.x - 4 - 34, r.y, 34, r.h)
        cw = f.size("0000")[0] + 4
        cnt = pygame.Rect(exp.x - 4 - cw, r.y, cw, r.h)
        rec = pygame.Rect(r.x, r.y, 46, r.h)
        bx = rec.right + 4
        bar = pygame.Rect(bx, r.y + (r.h - 6) // 2, max(10, cnt.x - 4 - bx), 6)
        return {"rec": rec, "bar": bar, "cnt": cnt, "exp": exp, "clr": clr}

    def _tl_btn(self, surf, rect, label, color, active=False, dot=None):
        pygame.draw.rect(surf, GREY10, rect, 0, border_radius=3)
        pygame.draw.rect(surf, color, rect, 2 if active else 1, border_radius=3)
        t = self.font_tl.render(label, True, color)
        tx = rect.x + (rect.w - t.get_width()) // 2 + (4 if dot is not None else 0)
        surf.blit(t, (tx, rect.y + (rect.h - t.get_height()) // 2))
        if dot is not None:                                   # small record dot: filled when shown, ring when off
            c = (rect.x + 7, rect.centery)
            if dot: pygame.draw.circle(surf, color, c, 3)
            else: pygame.draw.circle(surf, color, c, 3, 1)

    def draw_tl_progress_bar(self, surf):
        """T.LAPSE row under the tone sphere:  [o REC] [=====-----] 0600 [GIF] [CLR]  (tiny, ASCII-style)."""
        self._ensure_timelapse(); tl = self.tl
        P = self._tl_parts(); ticks = pygame.time.get_ticks()
        n = len(tl.frames); mx_ = max(1, int(getattr(tl, "max_frames", TIMELAPSE_MAX_FRAMES)))
        busy = self.tl_exporting; on = bool(tl.enabled)
        sx, sy = pygame.mouse.get_pos(); sx, sy = int(sx / WINDOW_SCALE), int(sy / WINDOW_SCALE)
        hot = lambda k: P[k].collidepoint(sx, sy)
        # REC
        rc = RED if on else (WHITE if hot("rec") else GREY50)
        self._tl_btn(surf, P["rec"], "REC", rc, active=on, dot=bool(on and (ticks // 500) % 2 == 0))
        # bar + count
        b = P["bar"]
        pygame.draw.rect(surf, GREY50 if not on else WHITE, b, 1, border_radius=3)
        if n > 0:
            fw = max(2, int(round((b.w - 2) * min(1.0, n / float(mx_)))))
            pygame.draw.rect(surf, RED if on else (150, 60, 60), pygame.Rect(b.x + 1, b.y + 1, fw, b.h - 2), 0, border_radius=2)
        c = P["cnt"]; full = n >= 0.9 * mx_
        ct = self.font_tl.render(f"{n:04d}" if not busy else "EXP", True, RED if (full or busy) else (GREY_TEXT if n else GREY50))
        surf.blit(ct, (c.right - ct.get_width(), c.y + (c.h - ct.get_height()) // 2))
        # GIF / CLR
        can = n > 0 and not busy
        self._tl_btn(surf, P["exp"], "GIF", (WHITE if hot("exp") else GREY_TEXT) if can else GREY50)
        armed = ticks < self._tl_wipe_until
        self._tl_btn(surf, P["clr"], "OK?" if armed else "CLR", RED if armed else ((WHITE if hot("clr") else GREY_TEXT) if can else GREY50), active=armed)

    def tl_toggle(self):
        self._ensure_timelapse(); self.tl.enabled = not self.tl.enabled
        print("[TL] Recording:", "ON" if self.tl.enabled else "OFF")
        self.speak("timelapse start" if self.tl.enabled else "timelapse stop")

    def tl_wipe(self):
        self._ensure_timelapse(); self.tl.reset()
        self.tl_last_interval_ms = 0; self.tl_full_prompted = False; self._tl_wipe_until = 0
        print("[TL] Frames cleared.")
        self.speak("timelapse cleared")

    def tl_row_click(self, mx, my, button=1):
        """Click on the T.LAPSE row. Always swallows the click (it must never paint)."""
        if button != 1: return True
        P = self._tl_parts(); self._ensure_timelapse(); n = len(self.tl.frames)
        if P["rec"].collidepoint(mx, my):
            self.play_ui_click(); self.tl_toggle()
        elif P["exp"].collidepoint(mx, my):
            if n > 0 and not self.tl_exporting:
                self.play_ui_click(); self.tl_export_via_dialog(); self._release_mouse_state()
        elif P["clr"].collidepoint(mx, my):
            if n > 0:
                self.play_ui_click(); now = pygame.time.get_ticks()
                if now < self._tl_wipe_until: self.tl_wipe()                 # second click: do it
                else: self._tl_wipe_until = now + TL_WIPE_ARM_MS            # first click: ask OK?
        return True

    def _ensure_timelapse(self):
        """Make sure self.tl exists (lazy init)."""
        if getattr(self, "tl", None) is None:
            self.tl = TimelapseRecorder(TIMELAPSE_TARGET_COLS, TIMELAPSE_MAX_FRAMES)
            self.tl.enabled = bool(TL_START_ON)

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
            self.speak("gif ready")
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

    def push_undo(self): self.undo_stack.append((self.canvas.buf.copy(), self.canvas.col.copy(), self.canvas.ov.copy()))
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
        blur_now = self.blur_active()
        if blur_now:
            return "BLUR"

        # 4b) Smart Brush / Smart Edge
        if self.mode == "edge" or (self.mode == "smart" and bool(mods & pygame.KMOD_CTRL)):
            return "SMART EDGE"
        if self.mode == "smart":
            return "SMART BRUSH"
        if self.mode == "smudge":
            return "SMUDGE"
        if self.mode == "bomb":
            return "BOMB"

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
        self.picker_drag = None
        self.smudge_last = None
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
        # Durante HELP e dentro de popups (editor de paleta, menus) o cursor fica visível: ali não há anel de pincel
        want_hidden = in_canvas and (not self.show_help) and (not self.popup)

        if want_hidden and not self.cursor_hidden:
            try: pygame.mouse.set_visible(False)
            except Exception: pass
            self.cursor_hidden = True
        elif (not want_hidden) and self.cursor_hidden:
            try: pygame.mouse.set_visible(True)
            except Exception: pass
            self.cursor_hidden = False


    def undo(self):
        if self.blast_busy(): return
        if self.undo_stack:
            buf,col,ov=self.undo_stack.pop()
            if buf.shape != self.canvas.buf.shape:       # the undone step changed the canvas size
                self._apply_canvas_arrays(buf, col, ov)
            else:
                self.canvas.buf[:,:]=buf; self.canvas.col[:,:]=col; self.canvas.ov[:,:]=ov

    # ---------- dynamic canvas size ----------
    def flash(self, msg, ms=FLASH_MS):
        self.flash_msg = msg; self.flash_until = pygame.time.get_ticks() + ms
        print("[MSG]", msg)

    def _fit_window(self, floor):
        """Pick WINDOW_SCALE so the whole surface fits the desktop (never above the configured scale)."""
        global WINDOW_SCALE
        scale = self.base_scale
        if AUTO_FIT_WINDOW:
            try:
                dw, dh = pygame.display.get_desktop_sizes()[0]
                if dw > 0 and dh > 0:
                    fit = min(1.0, (dh - 100) / float(self.surface_h), (dw - 20) / float(self.surface_w))
                    if fit < 1.0: scale = max(floor, fit)
            except Exception:
                pass
        WINDOW_SCALE = scale
        self.win_w = int(self.surface_w * scale); self.win_h = int(self.surface_h * scale)

    def _empty_mask(self, buf=None, ov=None):
        """True where the cell shows nothing (blank character, no Smart Edge override)."""
        buf = self.canvas.buf if buf is None else buf
        ov = self.canvas.ov if ov is None else ov
        n = self.pal.n - 1
        return ((buf * n).round().clip(0, n).astype(np.int32) == n) & (ov == 0)

    def _apply_canvas_arrays(self, buf, col, ov):
        """Install new canvas arrays (any size) and rebuild everything that depends on the canvas size:
        globals, window, surface, sidebar rects, overlay, picker caches."""
        global COLS, ROWS
        c = self.canvas
        c.rows, c.cols = buf.shape
        c.buf, c.col, c.ov = buf, col, ov
        COLS, ROWS = c.cols, c.rows
        old_w = self.canvas_px_w
        self.canvas_px_w, self.canvas_px_h = self.char_w * COLS, self.char_h * ROWS
        dx = self.canvas_px_w - old_w
        self.surface_h = max(self.canvas_px_h, SIDEBAR_MIN_HEIGHT) + UI_EXTRA_VERTICAL
        self.surface_w = self.canvas_px_w + SIDEBAR_W
        self.canvas_offset_y = (self.surface_h - self.canvas_px_h) // 2
        # the sidebar lives to the right of the canvas: slide every sidebar rect by the width change
        seen = set()
        for v in list(vars(self).values()):
            if isinstance(v, pygame.Rect) and id(v) not in seen:
                seen.add(id(v))
                if v.x >= old_w: v.x += dx
        self.sidebar_rect.height = self.surface_h
        self.picker_cells = []; self.picker_sel_rect = None; self._picker_grid = None
        self.palette_items.clear(); self.palette_rect_map.clear(); self.palette_sel_rect = None
        self.ind_rects.clear(); self.help_click_zones.clear()
        self.grid_cols, self.grid_rows = COLS, ROWS
        self.pt1 = None; self.hover_cell = None; self.smudge_last = None
        # window + drawing surface
        self.surface = pygame.Surface((self.surface_w, self.surface_h))
        self._fit_window(RESIZE_MIN_WINDOW_SCALE)
        self.screen = pygame.display.set_mode((self.win_w, self.win_h))
        if sys.platform == "win32":          # keep the (re-sized) window centred on the desktop
            try:
                import ctypes
                u32 = ctypes.windll.user32
                hwnd = pygame.display.get_wm_info()["window"]
                x = max(0, (u32.GetSystemMetrics(0) - self.win_w) // 2); y = max(0, (u32.GetSystemMetrics(1) - self.win_h) // 2 - 20)
                u32.SetWindowPos(hwnd, 0, x, y, 0, 0, 0x0001 | 0x0004)       # SWP_NOSIZE | SWP_NOZORDER
            except Exception:
                pass
        try: self.pen.attach()           # no-op unless the window handle changed
        except Exception: pass
        self._fit_overlay()
        tl = getattr(self, "tl", None)
        if tl is not None and not tl.frames: tl.target_rows = None      # first frame decides the T.LAPSE shape

    def resize_canvas(self, left=0, top=0, right=0, bottom=0):
        """Grow (+) or shrink (-) each side by that many cells. Content keeps its place; new cells are empty.
        Shrinking only removes cells that are empty. Undoable. Returns True when the size changed."""
        c = self.canvas
        # shrinking: how much of each requested strip is really empty (counted from the outer edge)?
        empty = self._empty_mask()
        def free(strip_axis, from_start):
            lines = empty.all(axis=strip_axis)              # axis=0 -> per column, axis=1 -> per row
            if not from_start: lines = lines[::-1]
            k = 0
            for v in lines:
                if not v: break
                k += 1
            return k
        asked = {"left": left, "top": top, "right": right, "bottom": bottom}
        refused = False
        for side, axis, start in (("left", 0, True), ("right", 0, False), ("top", 1, True), ("bottom", 1, False)):
            if asked[side] < 0:
                want = -asked[side]; got = min(want, free(axis, start))
                if got < want: refused = refused or got == 0
                asked[side] = -got
        left, top, right, bottom = asked["left"], asked["top"], asked["right"], asked["bottom"]
        new_cols = c.cols + left + right; new_rows = c.rows + top + bottom
        # keep inside the limits (trim the request instead of refusing when partly possible)
        if new_cols < CANVAS_MIN_COLS:
            need = CANVAS_MIN_COLS - new_cols
            if right < 0: right += min(need, -right); need = CANVAS_MIN_COLS - (c.cols + left + right)
            if left < 0 and need > 0: left += min(need, -left)
            new_cols = c.cols + left + right
        if new_rows < CANVAS_MIN_ROWS:
            need = CANVAS_MIN_ROWS - new_rows
            if bottom < 0: bottom += min(need, -bottom); need = CANVAS_MIN_ROWS - (c.rows + top + bottom)
            if top < 0 and need > 0: top += min(need, -top)
            new_rows = c.rows + top + bottom
        grow = (left > 0 or right > 0 or top > 0 or bottom > 0)
        if grow and (new_cols > CANVAS_MAX_COLS or new_rows > CANVAS_MAX_ROWS or new_cols * new_rows > CANVAS_MAX_CELLS):
            self.flash(f"CANVAS LIMIT: {CANVAS_MAX_COLS}x{CANVAS_MAX_ROWS} MAX ({CANVAS_MAX_CELLS} CELLS)")
            return False
        if new_cols == c.cols and new_rows == c.rows:
            self.flash("EDGE NOT EMPTY: NOTHING REMOVED" if refused else "CANVAS AT MINIMUM SIZE")
            return False
        old_cols, old_rows = c.cols, c.rows
        self.push_undo()                                   # snapshot (with the old shape) for Ctrl+Z
        dark = self.pal.value_from_idx(self.pal.n - 1)
        nb = np.full((new_rows, new_cols), dark, dtype=np.float32)
        nc = np.full((new_rows, new_cols), TEXT_LUMA, dtype=np.float32)
        no = np.zeros((new_rows, new_cols), dtype=np.int32)
        sx0 = max(0, -left); sx1 = min(old_cols, new_cols - left)
        sy0 = max(0, -top);  sy1 = min(old_rows, new_rows - top)
        if sx1 > sx0 and sy1 > sy0:
            for dst, src in ((nb, c.buf), (nc, c.col), (no, c.ov)):
                dst[sy0 + top:sy1 + top, sx0 + left:sx1 + left] = src[sy0:sy1, sx0:sx1]
        self._apply_canvas_arrays(nb, nc, no)
        self.flash(f"CANVAS {new_cols}x{new_rows}")
        return True

    def canvas_resize_key(self, key, shrink):
        """Ctrl+Arrow grows that side, Ctrl+Shift+Arrow removes up to one step of EMPTY cells from that side."""
        if self.stroke_started or self.left_down or self.right_down or self.mid_down or self.bombs: return
        dc, dr = CANVAS_GROW_COLS, CANVAS_GROW_ROWS
        if shrink: dc, dr = -dc, -dr
        if   key == pygame.K_LEFT:  self.resize_canvas(left=dc)
        elif key == pygame.K_RIGHT: self.resize_canvas(right=dc)
        elif key == pygame.K_UP:    self.resize_canvas(top=dr)
        elif key == pygame.K_DOWN:  self.resize_canvas(bottom=dr)
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


    def row_chars(self, r):
        """Characters of canvas row r: tone characters, with Smart Edge overrides on top."""
        n=self.pal.n-1
        idx=(self.canvas.buf[r,:]*n).round().clip(0,n).astype(np.int32).tolist()
        ov=self.canvas.ov[r,:].tolist(); chars=self.pal.chars
        return [chr(o) if o else chars[i] for i,o in zip(idx,ov)]
    def build_ascii_lines(self):
        return ["".join(self.row_chars(r)) for r in range(ROWS)]
    def save_txt(self,path):
        with open(path,"w",encoding="utf-8") as f:
            f.write("\n".join(self.build_ascii_lines()))
    def save_png(self,path):
        temp=pygame.Surface((self.canvas_px_w,self.canvas_px_h)); temp.fill(BLACK)
        for r in range(ROWS):
            row=self.row_chars(r)
            for c in range(COLS):
                ch=row[c]
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
        if AUTO_GROW_ON_LOAD:
            need_r=min(CANVAS_MAX_ROWS,len(lines)); need_c=min(CANVAS_MAX_COLS,max([len(l.rstrip()) for l in lines] or [0]))
            new_r=max(self.canvas.rows,need_r); new_c=max(self.canvas.cols,need_c)
            if new_r*new_c>CANVAS_MAX_CELLS:
                new_r,new_c=self.canvas.rows,self.canvas.cols
            if (new_r,new_c)!=(self.canvas.rows,self.canvas.cols):
                self._apply_canvas_arrays(np.full((new_r,new_c),dark_val,dtype=np.float32),
                                          np.full((new_r,new_c),TEXT_LUMA,dtype=np.float32),
                                          np.zeros((new_r,new_c),dtype=np.int32))
                self.flash(f"CANVAS {new_c}x{new_r} (FITS FILE)")
        self.canvas.buf[:,:]=dark_val                # whatever the file does not cover stays empty
        self.canvas.ov[:,:]=0
        rows=min(ROWS,len(lines))
        for r in range(rows):
            line=lines[r].replace("\u00a0"," "); cols=min(COLS,len(line))
            for c in range(cols):
                ch=line[c]
                idx=char_to_idx.get(ch)
                if idx is not None:
                    self.canvas.buf[r,c]=self.pal.value_from_idx(idx)
                elif ch in self.edge.tone_of:            # an edge-set character: keep it as a Smart Edge override
                    self.canvas.buf[r,c]=self.edge.tone_of[ch]; self.canvas.ov[r,c]=ord(ch)
                elif ch.isprintable() and not ch.isspace() and self.char_tone(ch) is not None:
                    self.canvas.buf[r,c]=self.char_tone(ch); self.canvas.ov[r,c]=ord(ch)    # any other drawable character (TRU mode text) stays as typed
                else:
                    self.canvas.buf[r,c]=dark_val        # not drawable by the font -> empty
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
            self.canvas.ov[:,:]=0
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
        lines = self.build_ascii_lines()
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
        t=self.font_ui.render(label,True,color)
        surf.blit(t,(rect.x+(rect.w-t.get_width())//2, rect.y+(rect.h-t.get_height())//2))

    def draw_toggle_button(self,surf,rect,label,active,color=CYAN):
        pygame.draw.rect(surf,GREY10,rect,0,border_radius=5)
        pygame.draw.rect(surf,color if active else GREY50,rect,2 if active else 1,border_radius=5)
        t=self.font_ui.render(label,True,color if active else GREY50)
        surf.blit(t,(rect.x+(rect.w-t.get_width())//2, rect.y+(rect.h-t.get_height())//2))

    def _indicator_box_size(self):
        ts=self.font_small.render("LINEAA",True,WHITE)
        return ts.get_width()+2*IND_PAD_X, ts.get_height()+2*IND_PAD_Y

    def draw_mode_stack(self,surf):
        blur_effective=(self.mode=="blur") or (self.mode in ("paint","smart") and self.shift_blur)
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
        label = self.font_ui.render('GRID (cells)', True, WHITE if self.grid_enabled else GREY)
        surf.blit(label, (self.grid_label_rect.x, self.grid_label_rect.y))
        pygame.draw.rect(surf, WHITE, self.voice_checkbox_rect, 1)
        if self.voice_on: pygame.draw.rect(surf, WHITE, self.voice_checkbox_rect.inflate(-6, -6), 0)
        vl = self.font_ui.render('VOICE', True, WHITE if self.voice_on else GREY)
        surf.blit(vl, (self.voice_label_rect.x, self.voice_label_rect.y))

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

    def _build_picker_grid(self):
        """Character grid of the tone sphere, built once.
        Every cell is a real character cell of the picker font (cells never overlap), the grid is centered
        in the frame and the sphere always fits inside it. The tone of a cell is the shading at the
        CENTER of the cell, and that same value is what a click on the cell picks."""
        inner = self.picker_rect.inflate(-4, -4)
        cw, chh = self.pk_w, self.pk_h
        cols = max(1, inner.w // cw)
        rows = max(1, inner.h // chh)
        gx = inner.left + (inner.w - cols*cw)//2
        gy = inner.top + (inner.h - rows*chh)//2
        cx = gx + cols*cw/2.0
        cy = gy + rows*chh/2.0
        R = min(cols*cw, rows*chh)/2.0
        Lx, Ly, Lz = PICKER_LIGHT
        lmag = math.sqrt(Lx*Lx + Ly*Ly + Lz*Lz)
        # "half lambert": the shadow side keeps a gradient instead of being clipped to black.
        # lo/hi = value at the darkest visible limb / at the highlight, so the sphere uses the FULL tonal range.
        lo = 0.5 - 0.5*math.hypot(Lx, Ly)/lmag
        hi = 1.0
        cells = {}
        for r in range(rows):
            for c in range(cols):
                px = gx + (c + 0.5)*cw
                py = gy + (r + 0.5)*chh
                nx = (px - cx)/R
                ny = (py - cy)/R
                d2 = nx*nx + ny*ny
                if d2 > 1.0:
                    continue
                nz = math.sqrt(max(0.0, 1.0 - d2))
                ndl = (nx*Lx + ny*Ly + nz*Lz)/lmag              # -1..1
                lit = (0.5 + 0.5*ndl - lo)/(hi - lo)             # 0..1 over the visible hemisphere
                tone = clamp01(1.0 - lit)                        # 0 light .. 1 dark
                cells[(c, r)] = (pygame.Rect(gx + c*cw, gy + r*chh, cw, chh), tone)
        self._picker_grid = cells
        self._picker_center = (cx, cy)

    def draw_spherical_picker(self,surf):
        pygame.draw.rect(surf,WHITE,self.picker_rect,1)
        if self._picker_grid is None:
            self._build_picker_grid()
        grid = self._picker_grid
        self.picker_cells = []
        for key, (rect, tone) in grid.items():
            ch = self.pal.char_from_value(tone)
            if ch != ' ':
                surf.blit(self.glyphs_picker.get(ch, GREY_TEXT), rect.topleft)
            self.picker_cells.append((rect, tone, key))

        # Selection: keep the clicked cell while it still shows the current tone. Otherwise take the cell
        # with the nearest tone that is closest to where the selection was (it moves smoothly, it does
        # not jump to the first cell of that tone).
        cur = self.pal.idx_from_value(self.current_value)
        sel = None
        if self.picker_pick in grid:
            if self.pal.idx_from_value(grid[self.picker_pick][1]) == cur:
                sel = self.picker_pick
        if sel is None:
            if self.picker_sel_rect is not None:
                ax, ay = self.picker_sel_rect.center
            else:
                ax, ay = self._picker_center
            def score(item):
                _key, (rect, tone) = item
                return (abs(self.pal.idx_from_value(tone) - cur),
                        (rect.centerx - ax)**2 + (rect.centery - ay)**2)
            sel = min(grid.items(), key=score)[0]
            self.picker_pick = sel
        self.picker_sel_rect = grid[sel][0]
        pygame.draw.rect(surf, CYAN, self.picker_sel_rect, 1)

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

    def _pal_slot_rects(self):
        """All 10 slots [(rect, nn)] at fixed positions (nn 1..10, same numbers as SHIFT+1..0)."""
        r = self.palslot_rect; w = (r.w - 9*PAL_SLOT_GAP)//10
        return [(pygame.Rect(r.x + i*(w + PAL_SLOT_GAP), r.y, w, r.h), i + 1) for i in range(10)]

    def _pal_slots(self):
        """Slots of the palettes that exist in PAL.txt."""
        return [(r, nn) for r, nn in self._pal_slot_rects() if nn in self.pal.map]

    def draw_pal_slots(self, surf, mx=-1, my=-1):
        for rect, nn in self._pal_slot_rects():
            exists = nn in self.pal.map
            cur = exists and self.pal.index == nn
            edited = exists and nn in self.pal.edits
            hov = exists and rect.collidepoint(mx, my)
            pygame.draw.rect(surf, HOVER_FILL if hov else GREY10, rect, 0, border_radius=3)
            if not exists:
                bcol = tcol = (60, 60, 60)
            else:
                tcol = RED if edited else (CYAN if cur else (WHITE if hov else GREY_TEXT))
                bcol = RED if edited else (CYAN if cur else (WHITE if hov else GREY50))
            pygame.draw.rect(surf, bcol, rect, 2 if (cur or edited) else 1, border_radius=3)
            t = self.font_ui.render(str(nn % 10), True, tcol)
            surf.blit(t, (rect.x + (rect.w - t.get_width())//2, rect.y + (rect.h - t.get_height())//2))

    # ---------- bomb ----------
    def _bomb_sounds(self):
        """(fuse Sound, explosion Sound, fuse ms) - your own files if present, otherwise generated."""
        if self._bomb_snds is None:
            fuse = boom = None; fuse_ms = BOMB_FUSE_MS
            try:
                init = pygame.mixer.get_init()
                if init:
                    freq, _fmt, ch = init
                    def load(name):
                        p = find_asset(name)
                        return pygame.mixer.Sound(str(p)) if p else None
                    fuse, boom = load("sounds/bomb_fuse.wav"), load("sounds/bomb_explosion.wav")
                    gf, gb = bomb_sound_arrays(freq)
                    def mk(a):
                        a = (np.clip(a, -1, 1) * 32767).astype(np.int16)
                        return pygame.sndarray.make_sound(np.ascontiguousarray(a if ch == 1 else np.column_stack([a] * ch)))
                    if fuse is None: fuse = mk(gf)
                    else: fuse_ms = int(max(600, min(4000, fuse.get_length() * 1000)))
                    if boom is None: boom = mk(gb)
            except Exception as e:
                print("[BOMB] sound not available:", e); fuse = boom = None
            self._bomb_snds = (fuse, boom, fuse_ms)
        return self._bomb_snds

    def blast_busy(self):
        return any(b.phase in ("flash", "blast") for b in self.bombs)

    def place_bomb(self, cell, now=None, seed=None):
        """Light a bomb at this cell. The blast radius follows the brush radius."""
        now = pygame.time.get_ticks() if now is None else now
        fuse, boom, fuse_ms = self._bomb_sounds()
        b = Bomb(cell[0], cell[1], bomb_radius(self.brush_radius), now, self.brush_alpha, fuse_ms, seed)
        self.bombs.append(b)
        self.speak(self._voice_rng.choice(VOICE_BOMB_LINES))
        if fuse is not None and self.sound_enabled:
            try: fuse.play(); b.fuse_snd = fuse
            except Exception: pass
        return b

    def _set_ink(self, ink):
        self.canvas.buf[:, :] = (1.0 - ink).astype(np.float32)

    def update_bombs(self, now):
        """Advance every bomb: fuse -> flash -> blast -> done. The canvas changes only in flash/blast."""
        for b in list(self.bombs):
            if b.phase == "fuse":
                if now - b.t0 >= b.fuse_ms and not self.blast_busy():
                    ink = 1.0 - self.canvas.buf.astype(np.float64)
                    b.plan = bomb_plan(ink, b.cx, b.cy, b.R, self.canvas.aspect, b.rng, b.alpha)
                    self.push_undo()                                   # one Ctrl+Z takes the whole explosion back
                    self.canvas.ov[b.plan.disc] = 0
                    self._set_ink(b.plan.flash_ink())
                    b.phase = "flash"; b.t_flash = now
                    try:
                        if b.fuse_snd: b.fuse_snd.stop()
                        boom = self._bomb_sounds()[1]
                        if boom is not None and self.sound_enabled: boom.play()
                    except Exception: pass
            elif b.phase == "flash":
                if now - b.t_flash >= BOMB_FLASH_MS:
                    self._set_ink(b.plan.ink_at(0.0)); b.phase = "blast"; b.t_blast = now
            elif b.phase == "blast":
                p = (now - b.t_blast) / float(BOMB_BLAST_MS)
                if p >= 1.0:
                    self._set_ink(b.plan.ink_at(1.0)); self.bombs.remove(b)
                    self._ensure_timelapse()
                    try: self.tl.capture(self.canvas, self.pal, force=True)
                    except Exception: pass
                else:
                    self._set_ink(b.plan.ink_at(1.0 - (1.0 - p) ** 2))       # ease out: fast at first, then slows down

    def bomb_fuse_char(self, b, now):
        """Character shown at the bomb during the fuse: runs through all the shades BOMB_FUSE_LOOPS times."""
        p = b.fuse_progress(now); n = self.pal.n
        ch = self.pal.chars[int(p * BOMB_FUSE_LOOPS * n) % n]
        return ch if ch != " " else "\u00b7"

    def _draw_disc_outline(self, surf, cx, cy, R, color, glyph):
        A = self.canvas.aspect; base_y = self.canvas_offset_y; g = self.glyphs.get(glyph, color)
        inside = lambda x, y: (x - cx) ** 2 + ((y - cy) * A) ** 2 <= R * R
        ry = int(math.ceil(R / A)) + 1; rx = int(R) + 1
        for y in range(max(0, cy - ry), min(self.canvas.rows - 1, cy + ry) + 1):
            for x in range(max(0, cx - rx), min(self.canvas.cols - 1, cx + rx) + 1):
                if inside(x, y) and not (inside(x-1, y) and inside(x+1, y) and inside(x, y-1) and inside(x, y+1)):
                    surf.blit(g, (x * self.char_w, base_y + y * self.char_h))

    def bomb_ring_radius(self, b, now):
        """Radius of the warning ring during the fuse: the full blast radius at the start, closing in faster and
        faster (like a falling bomb) and reaching the centre cell exactly when the fuse ends, with the boom."""
        p = b.fuse_progress(now)
        return max(0.5, b.R * (1.0 - p ** BOMB_RING_POW))

    def draw_bombs(self, surf, ticks):
        """Fuse overlay: the centre character cycles through the shades and blinks red/white faster and faster,
        while a ring shows the blast radius and shrinks onto the bomb."""
        for b in self.bombs:
            if b.phase != "fuse": continue
            p = b.fuse_progress(ticks)
            period = max(50, int(240 - 190 * p))
            hot = (ticks // period) % 2 == 0
            col = RED if hot else WHITE
            k = 0.35 + 0.65 * p                                     # the ring gets brighter as it closes
            ring_col = (int(110 + 145 * k), int(35 + 55 * k), int(30 + 30 * k)) if hot else (int(70 + 60 * k), int(25 + 20 * k), int(20 + 15 * k))
            self._draw_disc_outline(surf, b.cx, b.cy, self.bomb_ring_radius(b, ticks), ring_col, "\u00b7")
            r = pygame.Rect(b.cx * self.char_w, self.canvas_offset_y + b.cy * self.char_h, self.char_w, self.char_h)
            pygame.draw.rect(surf, BLACK, r)
            surf.blit(self.glyphs.get(self.bomb_fuse_char(b, ticks), col), r.topleft)
            if hot: pygame.draw.rect(surf, RED, r.inflate(2, 2), 1)

    # ---------- palette editing ----------
    def table_chars(self):
        """Characters offered by the table: only the ones the current font can draw, plus every palette character."""
        if self._table_chars is None:
            out = []; seen = set()
            extra = "".join(e["chars"] for e in self.pal.map.values())
            for ch in TABLE_SETS + extra:
                if ch in seen or ch.isspace(): continue
                m = self.font.metrics(ch)
                if m and m[0] is not None:
                    seen.add(ch); out.append(ch)
            self._table_chars = out
        return self._table_chars

    def open_char_table(self, idx):
        """Open the palette editor with palette position idx selected (the darkest slot is locked, so it picks the one next to it)."""
        self.popup = PaletteEditorPopup(self, idx)

    def open_pal_menu(self, nn, pos):
        if nn in self.pal.map:
            edited = nn in self.pal.edits
            free = any(k not in self.pal.map for k in range(1, 11))
            def do_restore(app): app.pal.restore(nn); app.flash(f"RESTORED {nn:02d}"); app.speak("palette restored")
            def do_save(app): ok, msg = app.pal.save(nn); app.flash(msg); ok and app.speak("palette saved")
            def do_new(app): ok, msg = app.pal.save_new(nn); app.flash(msg); ok and app.speak("palette saved")
            items = [("RESTORE", do_restore if edited else None), ("SAVE", do_save if edited else None),
                     ("SAVE NEW", do_new if free else None)]
            title = f"{nn:02d}-{self.pal.map[nn]['name']}" + (" *" if edited else "")
        else:
            def do_here(app): ok, msg = app.pal.save_here(nn); app.flash(msg); ok and app.speak("palette saved")
            items = [("SAVE CURRENT HERE", do_here)]
            title = f"{nn:02d}-(EMPTY)"
        self.popup = MenuPopup(self, title, items, pos)

    # ---------- quick help ----------
    def tooltip_at(self, mx, my):
        """(key, [lines]) for the control under the mouse, or None."""
        for r, nn in self._pal_slot_rects():
            if r.collidepoint(mx, my):
                if nn in self.pal.map:
                    name = f"{nn:02d}-{self.pal.map[nn]['name']}" + (" (EDITED)" if nn in self.pal.edits else "")
                    return ("slot", nn), [f"SHIFT+{nn % 10}  {name}", "RIGHT CLICK: PALETTE MENU"]
                return ("slot", nn), [f"SHIFT+{nn % 10}  (EMPTY)", "RIGHT CLICK: SAVE CURRENT HERE"]
        for rect, label in zip(self.ind_rects, self.ind_labels):
            if rect.collidepoint(mx, my): return ("ind", label), [IND_TIPS[label]]
        if self.tl_rect.collidepoint(mx, my):
            P = self._tl_parts(); self._ensure_timelapse(); n = len(self.tl.frames); m = int(getattr(self.tl, "max_frames", TIMELAPSE_MAX_FRAMES))
            if P["rec"].collidepoint(mx, my): return ("tl", "rec"), ["T  T.LAPSE REC ON/OFF", f"{n} / {m} FRAMES"]
            if P["exp"].collidepoint(mx, my): return ("tl", "exp"), ["CTRL+E  EXPORT GIF"] + ([] if n else ["NO FRAMES YET"])
            if P["clr"].collidepoint(mx, my): return ("tl", "clr"), ["CTRL+T  WIPE ALL FRAMES", "CLICK TWICE TO CONFIRM"]
            return ("tl", "bar"), [f"T.LAPSE  {n} / {m} FRAMES"]
        for rect, key, lines in ((self.new_btn, "new", ["N  NEW CANVAS"]), (self.load_btn, "load", ["LOAD A TXT FILE"]),
                                 (self.import_btn, "import", ["IMPORT AN IMAGE"]), (self.save_btn, "save", ["CTRL+S  SAVE TXT + PNG"]),
                                 (self.smart_btn, "smart", ["M  SMART BRUSH"]),
                                 (self.edge_btn, "edge", ["E  SMART EDGE", "CTRL+LMB while in SMART"]),
                                 (self.smudge_btn, "smudge", ["D  SMUDGE"]),
                                 (self.bomb_btn, "bomb", ["K  BOMB", "CLICK: LIGHT THE FUSE", "BRUSH RADIUS = BLAST RADIUS"]),
                                 (self.tru_btn, "tru", ["TAB  TRU MODE: NO BRUSHES", "MOUSE MOVES THE CURSOR", "TYPE EACH CHARACTER YOURSELF"]),
                                 (self.grid_checkbox_rect, "grid", ["G  GRID ON/OFF"]),
                                 (self.palette_rect, "bar", ["CLICK: PICK TONE", "DOUBLE CLICK: EDIT PALETTE"]),
                                 (self.picker_rect, "sphere", ["CLICK / DRAG: PICK TONE", "DOUBLE CLICK: EDIT PALETTE"])):
            if rect.collidepoint(mx, my): return ("btn", key), lines
        sl = self.opacity_slider_rect
        if sl is not None and sl.collidepoint(mx, my): return ("opacity",), ["CLICK / DRAG  or  SHIFT+WHEEL"]
        for r in (self.fade_box_rect, self.fade_label_rect):
            if r is not None and r.collidepoint(mx, my): return ("btn", "fade"), ["F  FADE ON/OFF", "THE STROKE DIES OUT AS YOU DRAW"]
        fs = self.fade_slider_rect
        if fs is not None and fs.collidepoint(mx, my): return ("fade",), ["CLICK / DRAG: FADE SPEED", "LEFT = LONG TRAIL", "RIGHT = SHORT TRAIL"]
        return None

    def _draw_tooltip(self, surf, mx, my, ticks):
        tip = self.tooltip_at(mx, my) if not (self.left_down or self.right_down or self.mid_down) else None
        key = tip[0] if tip else None
        if key != self._tip_key: self._tip_key = key; self._tip_since = ticks
        if not tip or ticks - self._tip_since < TOOLTIP_DELAY_MS: return
        lines = tip[1]; f = self.font_ui; lh = f.get_height() + 2
        w = max(f.size(l)[0] for l in lines) + 12; h = lh * len(lines) + 8
        x = max(2, min(mx + 14, self.surface_w - w - 2)); y = max(2, min(my + 18, self.surface_h - h - 2))
        r = pygame.Rect(x, y, w, h)
        pygame.draw.rect(surf, BLACK, r); pygame.draw.rect(surf, GREY, r, 1)
        for i, l in enumerate(lines):
            surf.blit(f.render(l, True, WHITE if i == 0 else GREY_TEXT), (x + 6, y + 4 + i * lh))

    def draw_tool_info(self,surf):
        ch=self.pal.char_from_value(self.current_value)
        infos=[
            f"PAL: {self.pal.display_name}" + (" *" if self.pal.index in self.pal.edits else ""),
            f"TONE: {self.current_value:.2f}",
            f"CHAR: '{ch}'",
            f"CANVAS: {COLS}x{ROWS}",
            f"RADIUS: {self.brush_radius}",
            f"OPACITY: {self.brush_alpha:.2f}",
            "FADE",
            f"SOUND: {'ON' if (self.sound_enabled and self.wav_variants) else 'OFF'}",
            f"SND FILE: {self.wav_name}",
            f"COPY: {COPY_DEFAULT_MODE.upper()}",
            f"NBSP: {'ON' if COPY_USE_NBSP else 'OFF'}",
        ]
        if self.pen.available:        # only shown when the pen hook is installed (Windows)
            infos.append(f"PEN: {self.pen.mode}" + (f" {self.pen.pressure:.2f}" if self.pen.in_contact else ("" if self.pen.seen else " (no pen yet)")))
        
        # --- Processing indicator (centered version) ---
        if self.processing_active:
            if (self.processing_ticks // 30) % 2 == 0:
                msg = self.font.render("PROCESSING...", True, CYAN)
                x = (self.surface.get_width() - msg.get_width()) // 2
                y = (self.surface.get_height() - msg.get_height()) // 2
                surf.blit(msg, (x, y))

        y=self.grid_rows_val_rect.bottom+UI_MARGIN//2
        self.opacity_slider_rect = None; self.fade_slider_rect = self.fade_box_rect = self.fade_label_rect = None
        for s in infos:
            if s == "FADE":
                self._draw_fade_row(surf, y); y += self.font_ui.get_height() + 1; continue
            t = self.font_ui.render(s,True,GREY)
            surf.blit(t,(self.canvas_px_w+UI_MARGIN,y))
            if s.startswith("OPACITY:"):
                # minimal ASCII slider: ------|-------
                cw = self.font_ui.size("-")[0]
                x0 = self.canvas_px_w + UI_MARGIN + t.get_width() + 8
                n = max(6, min(20, (self.canvas_px_w + SIDEBAR_W - UI_MARGIN - x0)//cw))
                k = int(round(clamp01(self.brush_alpha) * (n - 1)))
                left = self.font_ui.render("-"*k, True, GREY50); knob = self.font_ui.render("|", True, CYAN)
                right = self.font_ui.render("-"*(n-1-k), True, GREY50)
                surf.blit(left, (x0, y)); surf.blit(knob, (x0 + k*cw, y)); surf.blit(right, (x0 + (k+1)*cw, y))
                self.opacity_slider_rect = pygame.Rect(x0, y - 1, n*cw, self.font_ui.get_height() + 2)
                self._op_slider_geom = (x0, n)
            y+=self.font_ui.get_height()+1
        # Bottom-right help hint
        hint = self.font_small.render("SHIFT+H for HELP", True, GREY_TEXT)
        hx = self.canvas_px_w + SIDEBAR_W - UI_MARGIN - hint.get_width()
        hy = self.surface.get_height() - UI_MARGIN - hint.get_height()
        surf.blit(hint, (hx, hy))
        ver = self.font_small.render(f"v{VERSION}", True, GREY_TEXT)
        surf.blit(ver, (self.canvas_px_w + UI_MARGIN, hy))

    def _draw_fade_row(self, surf, y):
        """[x] FADE ------|-------   (same ASCII slider as OPACITY, lined up under it)."""
        f = self.font_ui; on = self.fade_on; fh = f.get_height()
        bs = max(6, fh - 4); x = self.canvas_px_w + UI_MARGIN
        box = pygame.Rect(x, y + 2, bs, bs)
        pygame.draw.rect(surf, WHITE if on else GREY, box, 1)
        if on: pygame.draw.rect(surf, WHITE, box.inflate(-4, -4), 0)
        lab = f.render("FADE", True, WHITE if on else GREY); surf.blit(lab, (box.right + 6, y))
        self.fade_box_rect = box; self.fade_label_rect = pygame.Rect(x, y, box.w + 6 + lab.get_width(), fh)
        if self._op_slider_geom is None: return
        x0, n = self._op_slider_geom; cw = f.size("-")[0]
        k = int(round(clamp01(self.fade_speed) * (n - 1)))
        left = f.render("-" * k, True, GREY50); knob = f.render("|", True, CYAN if on else GREY); right = f.render("-" * (n - 1 - k), True, GREY50)
        surf.blit(left, (x0, y)); surf.blit(knob, (x0 + k * cw, y)); surf.blit(right, (x0 + (k + 1) * cw, y))
        self.fade_slider_rect = pygame.Rect(x0, y - 1, n * cw, fh + 2)

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
            ("SHFT+1<->0","PALETTE (OR BAR)"),
            ("2xCLK TONE","EDIT PALETTE"),
            ("TAB","TRU: TYPE IT"),
            ("V","VOICE ON/OFF"),
            ("ALT+1<->0","TRU: LEVEL"),
            ("RCLK PAL BTN","RESTORE / SAVE"),
            ("1<->0","TONE"),
            ("- | =","TONE UP|DOWN"),
            ("CTRL+WHEEL","TONE"),
            ("[", "RADIUS DEC"),
            ("]", "RADIUS INC"),
            ("SHFT+WHEEL","OPACITY"),
            ("F","FADE ON/OFF"),
            ("B","BLUR MODE"),
            ("M","SMART BRUSH"),
            ("E","SMART EDGE"),
            ("CTRL+LMB","SMART EDGE (SMART)"),
            ("D","SMUDGE (OPAC=FORCE)"),
            ("K","BOMB (RADIUS=BLAST)"),
            ("P","PEN PRESSURE MODE"),
            ("L","LINE MODE"),
            ("A","LINE AA ON/OFF"),
            ("G","GRID ON/OFF"),
            ("CTRL+ARROWS","GROW CANVAS"),
            ("CTRL+SHFT+ARR","SHRINK (EMPTY)"),
        ]
        x_cmd=self.canvas_px_w+UI_MARGIN - HELP_BLOCK_XOFFSET
        fh=self.font_help; lh=fh.get_height()+HELP_LINE_GAP
        x_desc=x_cmd+max(fh.size(c)[0] for c,_ in items)+HELP_COL_GAP
        y=UI_MARGIN
        title=fh.render("SHORTCUTS",True,WHITE)
        surf.blit(title,(x_cmd,y)); y+=lh+4
        for cmd,desc in items:
            tcmd=fh.render(cmd,True,WHITE)
            tdesc=fh.render(desc,True,GREY_DESC)
            surf.blit(tcmd,(x_cmd,y)); surf.blit(tdesc,(x_desc,y))
            y+=lh
        list_bottom=y
        # credits + links
        cx=self.canvas_px_w+SIDEBAR_W//2
        insp1="Inspired by the Art of"
        link_vagon="@vagonparovoz"
        t1=fh.render(insp1,True,GREY_TEXT)
        t_vagon=fh.render(link_vagon,True,CYAN)
        link_me="@msouza3d"; t_me=fh.render(link_me,True,CYAN)
        tag_suffix=f" - 2025 - V{VERSION}"; t_suffix=fh.render(tag_suffix,True,GREY_TEXT)
        k1="BUY ME A COFFEE :"; k2="https://ko-fi.com/msouza3d"
        tk1=fh.render(k1,True,GREY_TEXT); tk2=fh.render(k2,True,CYAN)
        tag_y=self.surface.get_height()-UI_MARGIN - t_me.get_height()
        total_tag_w=t_me.get_width()+t_suffix.get_width(); tag_x=cx-total_tag_w//2
        insp_y_top=(tag_y - 6 - t_vagon.get_height() - 2*lh
                    - tk1.get_height() - tk2.get_height() - 4 - t1.get_height())
        surf.blit(t1,(cx - t1.get_width()//2, insp_y_top))
        r_vagon=pygame.Rect(cx - t_vagon.get_width()//2, insp_y_top + t1.get_height() + 4,
                            t_vagon.get_width(), t_vagon.get_height())
        surf.blit(t_vagon,r_vagon.topleft)
        mid_y=tag_y - 6 - t_vagon.get_height()
        surf.blit(tk1,(cx - tk1.get_width()//2, mid_y - tk1.get_height() - lh))
        r_k2=pygame.Rect(cx - tk2.get_width()//2, mid_y - tk2.get_height(), tk2.get_width(), tk2.get_height())
        surf.blit(tk2,r_k2.topleft)
        r_me=pygame.Rect(tag_x, tag_y, t_me.get_width(), t_me.get_height())
        surf.blit(t_me,r_me.topleft); surf.blit(t_suffix,(tag_x + t_me.get_width(), tag_y))
        if self.cursor_support:
            over=any(r.collidepoint(mx,my) for r in (r_k2,r_vagon,r_me))
            try: pygame.mouse.set_cursor(self.cursor_hand if over else self.cursor_arrow)
            except Exception: pass
        self.help_list_bottom=list_bottom
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
        A=self.canvas.aspect
        r2=(r-0.5)*(r-0.5)     # same disc the brush paints
        def inside(x,y):
            dx=x-cx; dy=(y-cy)*A
            return dx*dx+dy*dy<=r2
        # outline of the brush disc: inside cells that touch the outside (1 cell thick, no gaps)
        ry=int(math.ceil(r/A))
        for y in range(max(0,cy-ry),min(ROWS-1,cy+ry)+1):
            for x in range(max(0,cx-r),min(COLS-1,cx+r)+1):
                if glyph_char and inside(x,y) and not (inside(x-1,y) and inside(x+1,y) and inside(x,y-1) and inside(x,y+1)):
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
        ov_all=self.canvas.ov
        for r in range(ROWS):
            idx_row=idx_all[r].tolist(); lum_row=lum_all[r].tolist(); ov_row=ov_all[r].tolist()
            y=base_y + r*chh
            for c in range(COLS):
                o=ov_row[c]
                ch=chr(o) if o else chars[idx_row[c]]
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
        self.draw_pal_slots(surf, mx, my)
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

        self.draw_toggle_button(surf, self.smart_btn, "SMART [M]", self.mode=="smart")
        self.draw_toggle_button(surf, self.edge_btn,  "EDGE [E]", self.mode=="edge")
        self.draw_toggle_button(surf, self.smudge_btn, "SMUDGE [D]", self.mode=="smudge", SMUDGE_RGB)
        self.draw_toggle_button(surf, self.bomb_btn, "BOMB [K]", self.mode=="bomb", BOMB_RGB)
        self.draw_toggle_button(surf, self.tru_btn, "TRU: TYPE IT [TAB]", self.mode=="tru", TRU_RGB)

        self.draw_tool_info(surf)

        self.draw_bombs(surf, ticks)

        # ring
        if self.mode == "tru":
            self.draw_tru_cursor(surf, ticks)
        elif self.hover_cell and self.mode == "bomb":
            hx, hy = self.hover_cell
            self._draw_disc_outline(surf, hx, hy, bomb_radius(self.brush_radius), BOMB_RGB, "\u00b7")
            surf.blit(self.glyphs.get("*", BOMB_RGB), (hx * self.char_w, self.canvas_offset_y + hy * self.char_h))
        elif self.hover_cell:
            edge_now = (self.mode=="edge") or (self.mode=="smart" and bool(pygame.key.get_mods() & pygame.KMOD_CTRL))
            ring_col = RED if self.blur_active() else (HL_RGB if self.mode=="hlight" else (CYAN if edge_now else (SMUDGE_RGB if self.mode=="smudge" else WHITE)))
            self.draw_brush_ring(surf, ring_col, ticks)
        self.draw_help_overlay(surf, mx, my, ticks)
        if self.popup: self.popup.draw(self, surf, mx, my)
        elif not self.show_help: self._draw_tooltip(surf, mx, my, ticks)
        self.draw_caption(surf, ticks)
        if self.flash_msg and ticks < self.flash_until:
            t=self.font.render(self.flash_msg,True,CYAN)
            r=pygame.Rect(0,0,t.get_width()+16,t.get_height()+8)
            r.midbottom=(self.canvas_px_w//2, base_y+self.canvas_px_h-self.char_h)
            pygame.draw.rect(surf,BLACK,r); pygame.draw.rect(surf,CYAN,r,1)
            surf.blit(t,(r.x+8,r.y+4))

    def draw_preview_line(self,surf,mx,my):
        if self.mode!="line" or self.pt1 is None: return
        base_y = getattr(self, 'canvas_offset_y', 0)
        x1=self.pt1[0]*self.char_w; y1=base_y + self.pt1[1]*self.char_h
        pygame.draw.circle(surf,CYAN,(x1,y1),6,1)
        pygame.draw.line(surf,CYAN,(x1,y1),(mx,my),1)

    # ---- picker math ----
    def _picker_cell_at(self, mx, my):
        """(col,row) of the sphere cell under the point, or None."""
        if self._picker_grid is None:
            self._build_picker_grid()
        for key, (rect, _tone) in self._picker_grid.items():
            if rect.collidepoint(mx, my):
                return key
        return None

    def set_opacity_from_mouse(self, mx):
        r = self.opacity_slider_rect
        if r is None: return
        frac = (mx - r.x) / float(max(1, r.w - 1))
        self.brush_alpha = max(0.05, min(1.0, round(frac * 20) / 20.0))

    def picker_drag_update(self, mx, my):
        """LMB held on the sphere / palette bar: follow the mouse. Outside the sphere it clamps to the
        nearest cell instead of jumping to the darkest tone. No click sound while dragging."""
        if self.picker_drag == "sphere":
            if self._picker_grid is None:
                self._build_picker_grid()
            key = min(self._picker_grid, key=lambda k: (self._picker_grid[k][0].centerx - mx)**2 +
                                                       (self._picker_grid[k][0].centery - my)**2)
            self.current_value = self._picker_grid[key][1]
            self.picker_pick = key
            self.picker_sel_rect = self._picker_grid[key][0]
        elif self.picker_drag == "opacity":
            self.set_opacity_from_mouse(mx)
        elif self.picker_drag == "fade":
            self.set_fade_from_mouse(mx)
        elif self.picker_drag == "bar" and self.palette_items:
            rect, idx = min(self.palette_items, key=lambda it: abs(it[0].centerx - mx))
            self.current_value = self.pal.value_from_idx(idx)

    def handle_picker_click(self, mx, my, button=1):
        # T.LAPSE row (REC / GIF / CLR)
        if self.tl_rect.collidepoint(mx, my):
            self._picker_grabbed = None
            return self.tl_row_click(mx, my, button)
        # opacity slider
        if self.opacity_slider_rect is not None and self.opacity_slider_rect.collidepoint(mx, my) and button == 1:
            self.set_opacity_from_mouse(mx); self.play_ui_click(); self._picker_grabbed = "opacity"
            return True
        # fade checkbox / slider
        if button == 1:
            for r in (self.fade_box_rect, self.fade_label_rect):
                if r is not None and r.collidepoint(mx, my):
                    self._picker_grabbed = None; self.toggle_fade(); return True
            if self.fade_slider_rect is not None and self.fade_slider_rect.collidepoint(mx, my):
                self.set_fade_from_mouse(mx); self.play_ui_click(); self._picker_grabbed = "fade"
                return True
        # palette shortcut bar (same as SHIFT+1..0); right click opens the palette menu (empty slots too)
        for rect, nn in self._pal_slot_rects():
            if rect.collidepoint(mx, my):
                self._picker_grabbed = None
                if button == 3:
                    self.open_pal_menu(nn, (rect.x, rect.bottom + 2)); return True
                if nn not in self.pal.map: return True          # empty slot: nothing to select
                self.picker_sel_rect = None
                self.pal.set_index(nn)
                self.play_ui_click()
                self._picker_grabbed = None          # a click here must not start a tone drag
                return True
        # palette bar
        if self.palette_rect.collidepoint(mx, my):
            if self.palette_items:
                # pick nearest rect by x, then map to underlying idx
                rect, idx = min(self.palette_items, key=lambda it: abs(it[0].centerx - mx))
                self.current_value = self.pal.value_from_idx(idx)
                self.play_ui_click()  # <- som de clique
                now = pygame.time.get_ticks()
                if button == 1 and self._last_bar_click and self._last_bar_click[1] == idx and now - self._last_bar_click[0] <= DOUBLE_CLICK_MS:
                    self._last_bar_click = None
                    self.open_char_table(idx)                    # double click: character table
                    return True
                self._last_bar_click = (now, idx)
                self._picker_grabbed = "bar"
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
            key = self._picker_cell_at(mx, my)
            if key is not None:
                # exactly the tone of the glyph you clicked, and the selection stays on that cell
                self.current_value = self._picker_grid[key][1]
                self.picker_pick = key
                self.picker_sel_rect = self._picker_grid[key][0]
            else:
                # inside the frame but outside the sphere = darkest tone
                self.current_value = 1.0
                self.picker_pick = None
                self.picker_sel_rect = pygame.Rect(mx, my, 1, 1)   # anchor: nearest darkest cell
            self.play_ui_click()  # <- som de clique
            now = pygame.time.get_ticks(); idx = self.pal.idx_from_value(self.current_value)
            if button == 1 and self._last_sphere_click and self._last_sphere_click[1] == idx and now - self._last_sphere_click[0] <= DOUBLE_CLICK_MS:
                self._last_sphere_click = None
                self.open_char_table(idx)                         # double click on the sphere: palette editor
                return True
            self._last_sphere_click = (now, idx)
            self._picker_grabbed = "sphere"
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
        r_eff=self.eff_radius(); a_eff=self.eff_alpha()
        if not self.stroke_started: self.fade_dist = 0.0; self.fade_last = None       # a new stroke starts at full strength
        if self.fade_on:
            if self.fade_last is not None and self.fade_last != cell:
                self.fade_dist += math.hypot(cell[0] - self.fade_last[0], (cell[1] - self.fade_last[1]) * self.canvas.aspect)
            self.fade_last = cell
            a_eff *= self.fade_factor()

        if self.mode=="line": return
        if self.mode=="tru":
            self.tru_cursor = cell; return                # the mouse only moves the cursor

        # Highlight mode: left applies almost-white luma; right erases to default grey
        if self.mode=="hlight":
            if self.left_down:
                self.begin_stroke_if_needed()
                self.canvas.luma_disc_blend(x,y,r_eff,HLIGHT_LUMA,1.0,self.soft_edge)
                ## if r_eff==1: self.play_brush_tick()
            elif self.right_down:
                self.begin_stroke_if_needed()
                self.canvas.luma_disc_blend(x,y,r_eff,HL_ERASE_LUMA,1.0,self.soft_edge)
                ##if r_eff==1: self.play_brush_tick()
            return

        if self.mode=="smudge" and self.left_down:
            self.begin_stroke_if_needed()
            if self.smudge_last is not None and self.smudge_last != cell:
                self.smudge_move(self.smudge_last[0], self.smudge_last[1], x, y)
            self.smudge_last = (x, y)
            return

        blur_now=self.blur_active()
        smart = (self.mode=="smart")
        edge_only = (self.mode=="edge") or (smart and ctrl)     # SMART EDGE: only swap characters, no painting

        if self.left_down:
            self.begin_stroke_if_needed()
            if edge_only:
                self.smart_refine(x,y,r_eff,margin=False)
            elif blur_now:
                self.canvas.blur_disc(x,y,r_eff,a_eff,self.soft_edge)
                if smart: self.smart_refine(x,y,r_eff)
            else:
                self.canvas.paint_disc_blend(x,y,r_eff,self.current_value,a_eff,self.soft_edge)
                # reset luma to default grey regardless of opacity
                self.canvas.luma_disc_blend(x,y,r_eff,TEXT_LUMA,1.0,self.soft_edge)
                if smart: self.smart_refine(x,y,r_eff)

        elif self.right_down:
            self.begin_stroke_if_needed()
            if self.mode=="edge":
                ys,xs=self.canvas.disc_cells(x,y,r_eff)    # RMB in SMART EDGE: back to the plain tone characters
                self.canvas.ov[ys,xs]=0
            else:
                self.canvas.erase_disc_blend(x,y,r_eff,a_eff,self.soft_edge)
                if smart: self.smart_refine(x,y,r_eff)

        elif self.mid_down:
            self.begin_stroke_if_needed()
            # MID = lighten (towards 0), CTRL+MID = darken (towards 1)
            delta = (-LIGHTEN_STEP) if not ctrl else (+LIGHTEN_STEP)
            self.canvas.add_disc(x,y,r_eff, delta, a_eff, self.soft_edge)
            if smart: self.smart_refine(x,y,r_eff)

    def fade_length(self):
        """Stroke length (cells) over which the ink dies out: the slider is a speed, right = faster = shorter."""
        return FADE_LEN_MAX * (FADE_LEN_MIN / FADE_LEN_MAX) ** max(0.0, min(1.0, self.fade_speed))

    def fade_factor(self):
        """1.0 at the start of a stroke, 0.0 once the stroke has travelled fade_length() cells."""
        return max(0.0, 1.0 - self.fade_dist / self.fade_length())

    def toggle_fade(self):
        self.fade_on = not self.fade_on; self.play_ui_click()

    def set_fade_from_mouse(self, mx):
        r = self.fade_slider_rect
        if r is None: return
        frac = (mx - r.x) / float(max(1, r.w - 1))
        self.fade_speed = max(0.05, min(1.0, round(frac * 20) / 20.0)); self.fade_on = True

    def eff_alpha(self):
        """Brush opacity, scaled by pen pressure when the mode asks for it."""
        return self.brush_alpha * (self.pen.scale() if self.pen.mode in ("OPACITY", "BOTH") else 1.0)

    def eff_radius(self):
        """Brush radius in cells, scaled by pen pressure when the mode asks for it."""
        if self.pen.mode in ("SIZE", "BOTH"):
            return max(1, int(round(self.brush_radius * self.pen.scale())))
        return self.brush_radius

    def smudge_move(self, x0, y0, x1, y1):
        """Drag the ink under the brush from cell (x0,y0) to (x1,y1), one cell step at a time."""
        n = max(abs(x1-x0), abs(y1-y0))
        if n == 0: return
        k = max(0.0, min(1.0, self.eff_alpha()*SMUDGE_GAIN))
        rad = self.eff_radius()
        px, py = x0, y0
        for i in range(1, n+1):
            qx = x0 + int(round((x1-x0)*i/n)); qy = y0 + int(round((y1-y0)*i/n))
            self.canvas.smudge_step(px, py, rad, qx-px, qy-py, k)
            px, py = qx, qy

    # ---------- voice ----------
    def speak(self, text, force=False):
        """Say a short phrase with the raw voice synth (when the voice and the sound are on)."""
        if not (self.voice_on or force) or not self.sound_enabled: return False
        self.last_spoken = text
        if VOICE_CAPTIONS:
            try: self.caption = (text.upper(), [(w.upper(), a, b) for w, a, b in self.voice.timing(text)], pygame.time.get_ticks())
            except Exception as e: print("[VOICE]", e)
        try:
            if not pygame.mixer.get_init(): return True
            snd = self._voice_snd.get(text)
            if snd is None:
                snd = pygame.mixer.Sound(buffer=self.voice.render(text).tobytes()); self._voice_snd[text] = snd
            ch = pygame.mixer.Channel(VOICE_CHANNEL); ch.set_volume(1.0); ch.play(snd)
        except Exception as e:
            print("[VOICE]", e)
        return True

    def caption_words(self, ticks):
        """The words of the current caption that have been spoken by now (None when there is no caption to show)."""
        if not self.caption: return None
        text, words, t0 = self.caption
        # the frame's `ticks` is read at the start of the frame, the phrase can be spoken later in the same frame: never expire on a negative age
        el = max(0.0, (ticks - t0) / 1000.0)
        end = words[-1][2] if words else 0.0
        if el > end + VOICE_CAPTION_HOLD: self.caption = None; return None
        return [w for w, a, b in words if a - 0.02 <= el]

    def draw_caption(self, surf, ticks):
        shown = self.caption_words(ticks)
        if not shown: return
        t = self.font.render(" ".join(shown), True, VOICE_CAPTION_RGB)
        r = pygame.Rect(0, 0, t.get_width() + 20, t.get_height() + 8); r.midtop = (self.canvas_px_w // 2, 4)
        pygame.draw.rect(surf, BLACK, r, 0, border_radius=4); pygame.draw.rect(surf, (90, 75, 0), r, 1, border_radius=4)
        surf.blit(t, (r.x + 10, r.y + 4))

    def toggle_voice(self):
        if self.voice_on:
            self.speak("voice off", force=True); self.voice_on = False; self.flash("VOICE OFF")
        else:
            self.voice_on = True; self.speak("voice on"); self.flash("VOICE ON")

    def speak_mode(self, mode):
        if mode == "tru": self.speak(self._voice_rng.choice(VOICE_TRU_LINES))
        elif mode in VOICE_MODE_LINES: self.speak(VOICE_MODE_LINES[mode])

    # ---------- TRU mode: every character typed by hand ----------
    def tru_level_idx(self, k):
        """Alt+1 (darkest) .. Alt+0 (lightest) -> palette position; spreads the 10 keys over however many levels the palette has."""
        n = self.pal.n
        return (n - 1) - int(round((k - 1) / 9.0 * (n - 1)))

    def tru_put(self, ch=None, idx=None):
        """Put a palette level (idx) or a typed character at the cursor."""
        if self.tru_cursor is None: return False
        x, y = self.tru_cursor
        if not (0 <= x < self.canvas.cols and 0 <= y < self.canvas.rows): return False
        if idx is None:
            if ch == " ": idx = self.pal.n - 1
            elif ch in self.pal.chars[:self.pal.n - 1]: idx = self.pal.chars.index(ch)
        self.push_undo()
        if idx is not None:
            self.canvas.buf[y, x] = self.pal.value_from_idx(idx); self.canvas.ov[y, x] = 0
        else:
            tone = self.char_tone(ch)
            if tone is None: self.undo_stack.pop(); self.flash(f"'{ch}' IS NOT IN THE FONT"); return False
            self.canvas.buf[y, x] = tone; self.canvas.ov[y, x] = ord(ch)
        self.canvas.col[y, x] = TEXT_LUMA
        self.play_ui_click()
        return True

    def char_tone(self, ch):
        """Tone a free typed character counts as (from its ink), or None when the font cannot draw it."""
        if ch in self.edge.tone_of: return self.edge.tone_of[ch]
        cache = self.__dict__.setdefault("_char_tone_cache", {})
        if ch not in cache: cache[ch] = self._char_tone_measure(ch)
        return cache[ch]

    def _char_tone_measure(self, ch):
        m = self.font.metrics(ch)
        if not m or m[0] is None: return None
        try:
            surf = self.font.render(ch, True, (255, 255, 255), (0, 0, 0))
            a = pygame.surfarray.array3d(surf)[:, :, 0].astype(np.float32) / 255.0
        except Exception:
            return None
        ink = float(a.sum()) / max(1, self.char_w * self.char_h)
        return 1.0 - float(np.clip(ink * self.edge.K, 0.4, 1.0))

    def tru_move(self, dx, dy):
        x, y = self.tru_cursor or (0, 0)
        self.tru_cursor = (max(0, min(self.canvas.cols - 1, x + dx)), max(0, min(self.canvas.rows - 1, y + dy)))

    def tru_key(self, ev):
        """Keyboard in TRU mode. Returns True when the key was consumed (Ctrl shortcuts still go through)."""
        mods = getattr(ev, "mod", pygame.key.get_mods())
        if mods & pygame.KMOD_CTRL: return False
        key = ev.key
        if key in (pygame.K_ESCAPE, pygame.K_TAB):
            self.mode = "paint"; self.shift_blur = False; return True
        if key == pygame.K_F1: self.show_help = not self.show_help; return True
        if key in (pygame.K_LSHIFT, pygame.K_RSHIFT, pygame.K_LALT, pygame.K_RALT, pygame.K_CAPSLOCK): return True
        if self.tru_cursor is None: self.tru_cursor = self.hover_cell or (0, 0)
        if key == pygame.K_LEFT: self.tru_move(-1, 0)
        elif key == pygame.K_RIGHT: self.tru_move(1, 0)
        elif key == pygame.K_UP: self.tru_move(0, -1)
        elif key == pygame.K_DOWN: self.tru_move(0, 1)
        elif key == pygame.K_HOME: self.tru_cursor = (0, self.tru_cursor[1])
        elif key == pygame.K_END: self.tru_cursor = (self.canvas.cols - 1, self.tru_cursor[1])
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER): self.tru_cursor = (0, min(self.canvas.rows - 1, self.tru_cursor[1] + 1))
        elif key == pygame.K_BACKSPACE:
            self.tru_move(-1, 0); self.tru_put(idx=self.pal.n - 1)
        elif key == pygame.K_DELETE: self.tru_put(idx=self.pal.n - 1)
        elif (mods & pygame.KMOD_ALT) and (pygame.K_0 <= key <= pygame.K_9 or pygame.K_KP0 <= key <= pygame.K_KP9):
            d = (key - pygame.K_0) if key <= pygame.K_9 else (key - pygame.K_KP0)
            self.tru_put(idx=self.tru_level_idx(10 if d == 0 else d))     # changes the character in place
        else:
            ch = getattr(ev, "unicode", "")
            if len(ch) == 1 and ch.isprintable():
                if self.tru_put(ch=ch) and TRU_ADVANCE: self.tru_move(1, 0)
        return True

    def draw_tru_cursor(self, surf, ticks):
        if self.tru_cursor is None: return
        x = min(self.tru_cursor[0], self.canvas.cols - 1); y = min(self.tru_cursor[1], self.canvas.rows - 1)
        r = pygame.Rect(x * self.char_w, self.canvas_offset_y + y * self.char_h, self.char_w, self.char_h)
        if (ticks // TRU_BLINK_MS) % 2 == 0:
            pygame.draw.rect(surf, TRU_RGB, r, 1)
        pygame.draw.line(surf, TRU_RGB, (r.x, r.bottom - 1), (r.right - 1, r.bottom - 1), 2)

    def toggle_smart_mode(self, which):
        if self.mode == which:
            self.mode = "paint"
        else:
            if self.mode not in ("hlight", "smart", "edge", "smudge", "bomb", "tru"):
                self.prev_mode = self.mode
            self.mode, self.pt1 = which, None
            if which == "tru" and self.tru_cursor is None: self.tru_cursor = self.hover_cell or (0, 0)
        self.shift_blur = False

    def blur_active(self):
        return (self.mode=="blur") or (self.mode in ("paint","smart") and self.shift_blur)

    def smart_refine(self, cx, cy, r, margin=True):
        """Recompute the border characters of the cells under the brush disc (plus a 1 cell margin when
        painting, because new ink changes which neighbours are borders). Always computed from the TONES,
        so repeating it is stable."""
        ys, xs = self.canvas.disc_cells(cx, cy, r)
        if len(ys) == 0: return
        if margin:
            rows, cols = self.canvas.rows, self.canvas.cols
            y0 = max(0, ys.min()-1); y1 = min(rows-1, ys.max()+1); x0 = max(0, xs.min()-1); x1 = min(cols-1, xs.max()+1)
            m = np.zeros((y1-y0+3, x1-x0+3), dtype=bool)
            m[ys-y0+1, xs-x0+1] = True
            d = m.copy()
            for dy in (-1,0,1):
                for dx in (-1,0,1):
                    d |= np.roll(np.roll(m, dy, axis=0), dx, axis=1)
            yy, xx = np.nonzero(d[1:-1,1:-1])
            ys = yy + y0; xs = xx + x0
        self.canvas.ov[ys, xs] = self.edge.codes_for(self.canvas.buf, ys, xs)

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

                elif ev.type == pygame.KEYDOWN and self.popup:
                    self.popup.on_key(self, ev.key)
                    if self.popup and getattr(ev, "unicode", ""): self.popup.on_text(self, ev.unicode)

                elif ev.type == pygame.KEYDOWN and self.mode == "tru" and self.tru_key(ev):
                    pass

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
                        self.tl_toggle()

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
                        elif self.mode in ("paint", "smart"):
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
                        elif self.mode in ("smart", "edge", "smudge", "bomb", "tru"):
                            self.mode = "paint"

                    elif ctrl and (not (mods & pygame.KMOD_ALT)) and ev.key == pygame.K_s:
                        self.quick_save()

                    elif ctrl and ev.key == pygame.K_z:
                        self.undo()

                    elif ctrl and ev.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
                        self.canvas_resize_key(ev.key, shrink=shift)

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

                    elif (not ctrl) and (not shift) and ev.key == pygame.K_f:
                        self.toggle_fade()

                    elif (not ctrl) and (not shift) and ev.key == pygame.K_m:
                        self.toggle_smart_mode("smart")

                    elif (not ctrl) and (not shift) and ev.key == pygame.K_e:
                        self.toggle_smart_mode("edge")

                    elif (not ctrl) and (not shift) and ev.key == pygame.K_d:
                        self.toggle_smart_mode("smudge")

                    elif (not ctrl) and (not shift) and ev.key == pygame.K_k:
                        self.toggle_smart_mode("bomb")

                    elif ev.key == pygame.K_TAB and (not ctrl):
                        self.toggle_smart_mode("tru")

                    elif (not ctrl) and (not shift) and ev.key == pygame.K_v:
                        self.toggle_voice()

                    elif (not ctrl) and (not shift) and ev.key == pygame.K_p:
                        self.pen.cycle_mode()

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

                elif ev.type == pygame.MOUSEWHEEL and self.popup:
                    pass

                elif ev.type == pygame.MOUSEBUTTONDOWN and self.popup:
                    self.popup.on_click(self, mx, my, ev.button)

                elif ev.type == pygame.MOUSEMOTION and self.popup:
                    if getattr(self.popup, "on_drag", None) and (ev.buttons[0] if hasattr(ev, "buttons") else False):
                        self.popup.on_drag(self, mx, my)

                elif ev.type == pygame.MOUSEBUTTONUP and self.popup:
                    if getattr(self.popup, "on_release", None): self.popup.on_release(self)

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
                    self._picker_grabbed = None
                    if self.handle_picker_click(mx, my, ev.button):
                        if ev.button == 1:
                            self.picker_drag = self._picker_grabbed    # click and drag keeps changing the tone
                        continue

                    # Click nos indicadores (HLIGHT, SOFT, PAINT, BLUR, LINE, LINEAA)
                    if ev.button == 1:
                        if self.handle_mode_stack_click(mx, my):
                            continue
                        if self.smart_btn.collidepoint(mx, my):
                            self.play_ui_click(); self.toggle_smart_mode("smart"); continue
                        if self.edge_btn.collidepoint(mx, my):
                            self.play_ui_click(); self.toggle_smart_mode("edge"); continue
                        if self.smudge_btn.collidepoint(mx, my):
                            self.play_ui_click(); self.toggle_smart_mode("smudge"); continue
                        if self.bomb_btn.collidepoint(mx, my):
                            self.play_ui_click(); self.toggle_smart_mode("bomb"); continue
                        if self.tru_btn.collidepoint(mx, my):
                            self.play_ui_click(); self.toggle_smart_mode("tru"); continue

                    # Grid UI clicks
                    if ev.button == 1:
                        if self.voice_checkbox_rect.collidepoint(mx,my) or self.voice_label_rect.collidepoint(mx,my):
                            self.toggle_voice()
                        elif self.grid_checkbox_rect.collidepoint(mx,my) or self.grid_label_rect.collidepoint(mx,my):
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
                            if self.mode == "bomb":
                                cell = self.mouse_to_cell(mx, my)
                                if cell and not self.blast_busy(): self.place_bomb(cell)
                                continue
                            if self.blast_busy(): continue            # canvas is busy while debris is flying
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
                        self.picker_drag = None
                        self.smudge_last = None
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
                    if self.mode == "tru" and self.hover_cell: self.tru_cursor = self.hover_cell
                    if self.picker_drag:
                        self.picker_drag_update(mx, my)
                    if (self.left_down or self.right_down or self.mid_down) and self.hover_cell and (self.hover_cell != self.snd_last_cell):
                        self.play_brush_cell_trigger(self.hover_cell)
                    if self.show_help and self.cursor_support:
                        over = any(r.collidepoint(mx, my) for r,_ in self.help_click_zones)
                        try: pygame.mouse.set_cursor(self.cursor_hand if over else self.cursor_arrow)
                        except Exception: pass

            # the voice announces a mode change (not the temporary Shift switch out of HLIGHT)
            if self.mode != self._voice_mode:
                if not self.shift_from_hlight: self.speak_mode(self.mode)
                self._voice_mode = self.mode

            # Continuous paint
            if (self.left_down or self.right_down or self.mid_down) and (self.mode != "line"):
                self.paint_under_mouse(mx, my)

            # Timelapse (interval mode) — capture while mouse is down
            self.tl_poll_interval()

            self._update_cursor_visibility(mx, my)
            
            if self.processing_active:
                self.processing_ticks += 1

            # Bombs advance with real time
            self.update_bombs(ticks)

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