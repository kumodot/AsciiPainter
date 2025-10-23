# ASCII Painter v0.77

A lightweight ASCII art painting tool for drawing with monospaced characters on a grid.

**Author:** Marcelo Souza (@msouza3d)  
**Inspired by:** the work of [Vagon Parovoz](https://www.instagram.com/vagonparovoz/) and classic ANSI/ASCII art editors

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
- **PAL.txt** → default palette (light → dark)  (Optional)
- **keypress_*.wav** → keypress sound feedback (Optional)

---

## Shortcuts

### Drawing
- Left Click → Paint / Blur / Highlight  
- Right Click → Erase / Erase Highlight  
- Middle Click → Lighten  
- Ctrl + Middle Click → Darken  

### Modes
- B → Blur mode  
- L → Line mode (toggle)  
- A → Toggle line Anti-Alias  
- H → Highlight mode  
- Shift (hold) → Temporary Smooth / Blur  

### Tone & Brush
- - → Darker tone  
- = → Lighter tone  
- 1..0 → Tone deciles  
- [ / ] → Brush radius  
- Ctrl + Scroll Wheel → Change tone  
- Shift + Scroll Wheel → Opacity  
- X → Toggle darkest / lightest tone  

### Grid & Export
- G → Toggle grid  
- Ctrl+S → Save TXT + PNG  
- Ctrl+C → Copy as Markdown  
- Ctrl+Alt+C → Copy as HTML `<pre>`  
- Ctrl+Shift+C → Copy Fit (Bounding Box / Grid)  
- Ctrl+Shift+N → Toggle NBSP spaces  

### UI & Control
- Shift+H → Show/Hide Help overlay  
- Ctrl+Q → Quit (with save prompt)

---

## Credits
Created by **Marcelo Souza (@msouza3d)**  
Inspired by the work of [Vagon Parovoz](https://www.instagram.com/vagonparovoz/) and the ASCII/ANSI art community
