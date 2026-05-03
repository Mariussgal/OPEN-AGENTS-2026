"""
Onchor.ai — UI / branding du CLI terminal.

Centralise le logo ASCII, la palette de couleurs et les helpers d'affichage
(rich) to keep UX consistent across all commands.
"""

from __future__ import annotations

from rich.align import Align
from rich.console import Console, Group
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme


# ─── Palette Onchor ────────────────────────────────────────────────────────────
# Chosen for dark terminal usage, without gradients or visual noise.
ONCHOR_THEME = Theme(
    {
        "brand": "bold #7C5CFF",       # violet Onchor
        "brand.dim": "#5B47BF",
        "accent": "bold #00E0B8",      # green/teal — success and highlights
        "muted": "grey58",
        "info": "cyan",
        "warn": "yellow",
        "danger": "bold red",
        "ok": "bold green",
        "label": "bold #C8C2E2",
        "rule": "#3A3358",
    }
)

console = Console(theme=ONCHOR_THEME, highlight=False)


# ─── Logos ASCII ───────────────────────────────────────────────────────────────
# Logo texte "Onchor-AI" — style slant.
ASCII_LOGO = r"""   ____             __                     ___    ____
  / __ \____  _____/ /_  ____  _____      /   |  /  _/
 / / / / __ \/ ___/ __ \/ __ \/ ___/_____/ /| |  / /  
/ /_/ / / / / /__/ / / / /_/ / /  /_____/ ___ |_/ /   
\____/_/ /_/\___/_/ /_/\____/_/        /_/  |_/___/   
                                                      """

# Iconic logo — sphere / Onchor "anchor seal".
ASCII_ICON = r"""                                                                                     
                                          .:                                         
                                         ..::                                        
                                       :...:::                                       
                                       ....::::                                      
                                     ......:::::                                     
                                    .......::::::                                    
                                   ........:::::::                                   
                                  .........::::::::                                  
                                 ..........:::::::::                                 
                                ...........::::::::::                                
                               ............:::::::::::                               
                              .............::::::::::::                              
                             ..............:::::::::::::                             
                            ............:::---:::::::::::                            
                           ........::::::::-------:::::::::                          
                          .....::::::::::::-----------::::::                         
                         .:::::::::::::::::----------------::                        
                          :::::::::::::::::----------------                          
                        :.   ::::::::::::::-------------   ::                        
      ..                 :...   :::::::::::----------   ::::                 ::      
      ....                .....:   ::::::::-------    :::::                ::::      
      .......               .......   :::::----   :::::::               :::::::      
      .........              .........   ::-   :::::::::              :::::::::      
      ...........:            ...........    ::::::::::             :::::::::::      
      ..............            ...........:::::::::::           ::::::::::::::      
      .................          ..........:::::::::           ::::::::::::::::      
      .................           .........::::::::           :::::::::::::::::      
      .............                 .......::::::.                :::::::::::::      
      ...............               .......::::::                ::::::::::::::      
      ................              .......::::::              ::::::::::::::::      
      ...   :...........            .......::::::            ::::::::::::   :::      
      :      ..............:       ........::::::::       ::::::::::::::      :      
               ............................:::::::::::::::::::::::::::               
                 ..........................::::::::::::::::::::::::::                
                  .........................::::::::::::::::::::::::                  
                    .......................::::::::::::::::::::::                    
                       ....................:::::::::::::::::::                       
                           ................::::::::::::::::                          
                              .............::::::::::::                              
                                  .........::::::::                                  
                                     ......::::::                                    
                                       ....:::                                       
                                         ..::                                        
                                          .                                          
                                                                                     """

TAGLINE = "Solidity Security Copilot · Persistent Collective Memory"
SUBLINE = "ETHGlobal Open Agents 2026 · CNM Agency"


def _downsample(art: str, vstep: int = 2, hstep: int = 2) -> str:
    """Downsample ASCII art by keeping 1 line per `vstep` and 1 char per `hstep`."""
    lines = art.split("\n")
    return "\n".join(line[::hstep] for line in lines[::vstep])


# Available icon sizes — computed at load time.
ASCII_ICON_LARGE = ASCII_ICON                          # ~45 lignes × ~85 cols
ASCII_ICON_MEDIUM = _downsample(ASCII_ICON, 2, 2)      # ~23 lignes × ~43 cols
ASCII_ICON_SMALL = _downsample(ASCII_ICON, 3, 3)       # ~15 lignes × ~28 cols

ICON_SIZES = {
    "none": None,
    "small": ASCII_ICON_SMALL,
    "medium": ASCII_ICON_MEDIUM,
    "large": ASCII_ICON_LARGE,
}


def render_banner(icon_size: str = "medium") -> Panel:
    """Build banner (icon + logo + tagline) inside a Panel.

    icon_size : 'none' | 'small' | 'medium' | 'large'
    """
    parts = []
    icon_art = ICON_SIZES.get(icon_size, ASCII_ICON_MEDIUM)
    if icon_art:
        # Text() (not from_markup) -> `.`, `:`, `-` are not interpreted.
        icon = Text(icon_art, style="brand", no_wrap=True)
        parts.append(Align.center(icon))

    logo = Text(ASCII_LOGO, style="brand", no_wrap=True)
    tagline = Text(TAGLINE, style="accent", justify="center")
    subline = Text(SUBLINE, style="muted", justify="center")

    parts.extend([
        Align.center(logo),
        Align.center(tagline),
        Align.center(subline),
    ])

    return Panel(
        Padding(Group(*parts), (0, 2)),
        border_style="brand.dim",
        padding=(1, 2),
    )


def show_banner(icon_size: str = "medium") -> None:
    """Print banner in console (called at startup)."""
    console.print(render_banner(icon_size=icon_size))


# ─── Helpers d'affichage ───────────────────────────────────────────────────────
def info(msg: str) -> None:
    console.print(f"[info]ℹ[/info] {msg}")


def success(msg: str) -> None:
    console.print(f"[ok]✔[/ok] {msg}")


def warn(msg: str) -> None:
    console.print(f"[warn]![/warn] {msg}")


def error(msg: str) -> None:
    console.print(f"[danger]✘[/danger] {msg}")


def section(title: str) -> None:
    """Small, minimal section separator."""
    console.rule(f"[label]{title}[/label]", style="rule")


def kv_panel(title: str, items: dict[str, str]) -> Panel:
    """Small key/value panel to summarize config, balance, verdict, etc."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="label", justify="right", no_wrap=True)
    table.add_column(style="white", overflow="fold", no_wrap=False)
    for k, v in items.items():
        table.add_row(k, v)
    return Panel(
        table,
        title=f"[brand]{title}[/brand]",
        border_style="brand.dim",
        expand=True,
    )


def credentials_summary_table(rows: list[dict[str, str]]) -> Table:
    """Onboarding table: credential · status · detail."""
    table = Table(
        show_header=True,
        header_style="label",
        border_style="rule",
        expand=True,
    )
    table.add_column("Credential", overflow="fold", style="label")
    table.add_column("Status", justify="center", width=14)
    table.add_column("Detail", overflow="fold", style="white")

    for r in rows:
        raw_st = str(r.get("status", "") or "").strip().lower()
        if raw_st in ("valid", "ok", "validated"):
            st = "[ok]✓ validated[/ok]"
        elif raw_st in ("invalid", "bad", "error"):
            st = "[danger]✗ invalid[/danger]"
        elif raw_st in ("skip", "skipped", "optional"):
            st = "[muted]— skipped[/muted]"
        else:
            st = f"[muted]{r.get('status', '—')}[/muted]"
        table.add_row(r.get("name", "—"), st, str(r.get("detail", "")))

    return table


# ─── Verdict & findings ────────────────────────────────────────────────────────
SEVERITY_STYLES = {
    "HIGH": "danger",
    "MEDIUM": "warn",
    "MED": "warn",
    "LOW": "info",
    "INFO": "muted",
}


def verdict_panel(verdict: str, risk_score: float | None = None) -> Panel:
    """Colorized final verdict panel."""
    v = (verdict or "UNKNOWN").upper()
    if v in {"CERTIFIED", "SAFE"}:
        style, icon = "ok", "✔"
    elif v in {"FINDINGS_FOUND", "HIGH_RISK", "RISK"}:
        style, icon = "danger", "✘"
    else:
        style, icon = "warn", "!"

    score = f"  ·  risk score: [bold]{risk_score:.1f}/10[/bold]" if risk_score is not None else ""
    body = Text.from_markup(f"[{style}]{icon}  Verdict: {v}[/{style}]{score}")
    return Panel(Align.center(body), border_style=style, padding=(1, 2))


def findings_table(findings: list[dict]) -> Table:
    """Findings table (severity / file / line / description)."""
    table = Table(
        show_header=True,
        header_style="label",
        border_style="rule",
        expand=True,
    )
    table.add_column("Sev", width=8)
    table.add_column("File", style="info", overflow="fold")
    table.add_column("Line", justify="right", width=6, style="muted")
    table.add_column("Description", overflow="fold")

    for f in findings:
        sev = (f.get("severity") or "INFO").upper()
        sev_style = SEVERITY_STYLES.get(sev, "muted")
        table.add_row(
            f"[{sev_style}]{sev}[/{sev_style}]",
            str(f.get("file") or f.get("contract") or "—"),
            str(f.get("line") or "—"),
            str(f.get("description") or f.get("title") or "—"),
        )
    return table
