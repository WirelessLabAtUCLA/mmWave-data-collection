"""
Shared matplotlib style for clean, schematic-looking IEEE figures.

Look: open axes with arrow heads (no box, no grid), thick saturated lines,
light filled regions, dashed threshold lines with inline labels, and direct
annotations with thin arrows instead of boxed legends.

IEEE column widths:
    single column : 3.5  in (88.9 mm)
    double column : 7.16 in (181 mm)
"""

from pathlib import Path
import shutil

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import font_manager

SINGLE_COL = 3.5
DOUBLE_COL = 7.16

# Palette (navy / crimson on light-blue wash)
BLUE = "#165B91"
RED = "#C41E2F"
LIGHTBLUE = "#D7E6F6"
LIGHTRED = "#F2B8BE"
MIDBLUE = "#5B9BD5"
MIDRED = "#E57A84"
GRAY = "#6E6E6E"
DARK = "#2B2B2B"

COLORS = {
    "blue": BLUE, "red": RED, "vermillion": RED,
    "lightblue": LIGHTBLUE, "lightred": LIGHTRED,
    "midblue": MIDBLUE, "midred": MIDRED,
    "gray": GRAY, "dark": DARK,
    "green": "#009E73", "orange": "#E69F00",
}


def _pick_sans() -> list:
    preferred = ["Helvetica", "Arial", "Liberation Sans", "Ubuntu Sans", "DejaVu Sans"]
    available = {f.name for f in font_manager.fontManager.ttflist}
    return [f for f in preferred if f in available] or ["sans-serif"]


def apply_style(use_latex: bool = True) -> None:
    """Apply the clean figure style globally."""
    use_latex = use_latex and shutil.which("latex") is not None
    sans = _pick_sans()

    font_params: dict = {"font.family": "sans-serif", "font.sans-serif": sans}
    if use_latex:
        # Use Helvetica (or URW Nimbus Sans as the free clone) via LaTeX.
        # helvet + sfmath give a consistent sans-serif look in both text and math.
        # T1 encoding is required for proper glyph coverage in PDFs.
        font_params["text.latex.preamble"] = (
            r"\usepackage[T1]{fontenc}"
            r"\usepackage{helvet}"
            r"\usepackage[helvet]{sfmath}"
            r"\renewcommand\familydefault{\sfdefault}"
        )
    else:
        font_params.update({
            "mathtext.fontset": "custom",
            "mathtext.rm": f"{sans[0]}",
            "mathtext.it": f"{sans[0]}:italic",
            "mathtext.bf": f"{sans[0]}:bold",
            "mathtext.default": "it",
            "mathtext.cal": f"{sans[0]}:italic",
            "mathtext.sf": f"{sans[0]}",
            "mathtext.tt": f"{sans[0]}",
            "mathtext.fallback": "stix",
        })

    mpl.rcParams.update({
        **font_params,
        "text.usetex": use_latex,
        "font.size": 8,
        "axes.labelsize": 8,
        "axes.titlesize": 8,
        "legend.fontsize": 7,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "text.color": DARK,
        "axes.labelcolor": DARK,
        "xtick.color": DARK,
        "ytick.color": DARK,
        # Open axes, no grid
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.8,
        "axes.edgecolor": DARK,
        "axes.grid": False,
        "axes.axisbelow": True,
        "axes.prop_cycle": mpl.cycler(color=[BLUE, RED, MIDBLUE, MIDRED, GRAY]),
        "lines.linewidth": 1.5,
        "lines.markersize": 3.0,
        "lines.solid_capstyle": "round",
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "xtick.major.width": 0.7,
        "ytick.major.width": 0.7,
        "xtick.minor.visible": False,
        "ytick.minor.visible": False,
        # Legends (when used): no frame
        "legend.frameon": False,
        "legend.handlelength": 1.6,
        "legend.handletextpad": 0.5,
        "legend.labelspacing": 0.3,
        # Output
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.03,
        "pdf.fonttype": 42,   # TrueType (IEEE PDF eXpress compliant)
        "ps.fonttype": 42,
    })


def new_figure(width: str = "single", height: float = 2.2, **kwargs):
    """Create a figure at an IEEE column width. Returns (fig, ax)."""
    w = SINGLE_COL if width == "single" else DOUBLE_COL
    return plt.subplots(figsize=(w, height), **kwargs)


def arrow_axes(ax, color: str = DARK, size: float = 4.0, x: bool = True, y: bool = True) -> None:
    """Put arrow heads on the ends of the (left, bottom) axes lines."""
    if x:
        ax.plot(1, 0, ">", transform=ax.transAxes, color=color, ms=size, clip_on=False, zorder=10)
    if y:
        ax.plot(0, 1, "^", transform=ax.transAxes, color=color, ms=size, clip_on=False, zorder=10)


def callout(ax, text: str, xy, xytext, color: str = DARK, fontsize: float = 6.5,
            ha: str = "center", va: str = "center", arrow: bool = True,
            coords: str = "data", **kwargs):
    """Colored text with a thin arrow pointing at `xy` (like a schematic annotation)."""
    kwargs.setdefault("fontweight", "bold")
    arrowprops = dict(arrowstyle="-|>", color=color, lw=0.6, shrinkA=1, shrinkB=1,
                      mutation_scale=5) if arrow else None
    return ax.annotate(text, xy=xy, xytext=xytext, xycoords=coords, textcoords=coords,
                       color=color, fontsize=fontsize, ha=ha, va=va, arrowprops=arrowprops,
                       annotation_clip=False, **kwargs)


def hline_label(ax, y: float, text: str, color: str = RED, x: float = 0.99, ha: str = "right",
                ls: str = "--", lw: float = 1.0, fontsize: float = 6.5, dy: float = 0.0) -> None:
    """Dashed threshold line with a small inline label (axes-fraction x)."""
    ax.axhline(y, color=color, ls=ls, lw=lw, zorder=2)
    ax.text(x, y, text, transform=ax.get_yaxis_transform(), color=color, fontsize=fontsize,
            ha=ha, va="bottom", fontweight="bold")


def panel_label(ax, text: str, x: float = -0.02, y: float = 1.02, **kwargs) -> None:
    """Add an '(a)'-style label."""
    kw = dict(ha="right", va="bottom", fontsize=8, fontweight="bold", color=DARK)
    kw.update(kwargs)
    ax.text(x, y, text, transform=ax.transAxes, **kw)


def save(fig, out_dir, name: str, formats=("pdf", "png")) -> list:
    """Save a figure as vector PDF and a 300 dpi PNG preview."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for fmt in formats:
        p = out_dir / f"{name}.{fmt}"
        # explicit dpi: it is also the resolution of any rasterized artists inside the PDF
        fig.savefig(p, format=fmt, dpi=300)
        paths.append(p)
    return paths
