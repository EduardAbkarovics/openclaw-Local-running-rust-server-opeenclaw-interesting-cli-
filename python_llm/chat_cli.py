"""
ClawDBot – Premium animált terminál chat
Buborékok · Typing animáció · Rich Live spinner
"""

import asyncio
import itertools
import json
import os
import sys
import textwrap
import urllib.request
from datetime import datetime

RUST_WS_URL = os.environ.get("CLAWDBOT_WS_URL", "ws://127.0.0.1:3000/ws/chat")
BOT_NAME    = os.environ.get("CLAWDBOT_BOT_NAME", "ClawDBot")

# ── Függőség ellenőrzés ──────────────────────────────────────────────────────
_miss = []
try:    import websockets
except ImportError: _miss.append("websockets>=12.0")
try:
    from rich.console import Console
    from rich.panel   import Panel
    from rich.live    import Live
    from rich.align   import Align
    from rich.rule    import Rule
    from rich.markup  import escape
    from rich         import box as rbox
except ImportError:  _miss.append("rich>=13.0")

if _miss:
    print(f"pip install {' '.join(_miss)}")
    sys.exit(1)

console = Console(highlight=False)

# ── ANSI ─────────────────────────────────────────────────────────────────────
R   = "\033[0m"
B   = "\033[1m"
D   = "\033[2m"
CYN = "\033[96m"
GRN = "\033[92m"
YLW = "\033[93m"
MGT = "\033[95m"
WHT = "\033[97m"
RED = "\033[91m"
BLU = "\033[94m"
PNK = "\033[35m"

# Bubble chars
TL,TR = "╭","╮"
BL,BR = "╰","╯"
V,H   = "│","─"
DL,DR = "├","┤"

# ── Logo ──────────────────────────────────────────────────────────────────────
LOGO_LINES = [
    (CYN,  f"  ██████╗██╗      █████╗ ██╗    ██╗"),
    (CYN,  f" ██╔════╝██║     ██╔══██╗██║    ██║"),
    (CYN,  f" ██║     ██║     ███████║██║ █╗ ██║"),
    (CYN,  f" ██║     ██║     ██╔══██║██║███╗██║"),
    (CYN,  f" ╚██████╗███████╗██║  ██║╚███╔███╔╝"),
    (CYN,  f"  ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝"),
    ("",   ""),
    (MGT,  f"  ██████╗  ██████╗ ████████╗"),
    (MGT,  f"  ██╔══██╗██╔═══██╗╚══██╔══╝"),
    (MGT,  f"  ██████╔╝██║   ██║   ██║   "),
    (MGT,  f"  ██╔══██╗██║   ██║   ██║   "),
    (MGT,  f"  ██████╔╝╚██████╔╝   ██║   "),
    (MGT,  f"  ╚═════╝  ╚═════╝    ╚═╝   "),
]

# ── Boot animáció ─────────────────────────────────────────────────────────────
async def boot_animation():
    os.system("cls" if os.name == "nt" else "clear")

    boot_items = [
        (GRN,  "CUDA runtime          v12.x"),
        (GRN,  "GPU 0 online          RTX series"),
        (GRN,  "GPU 1 online          RTX series"),
        (CYN,  "WizardLM 13B Code     FP16 · loading"),
        (CYN,  "VRAM split            multi-GPU · auto"),
        (YLW,  f"{BOT_NAME:<22s}starting up"),
    ]

    for color, msg in boot_items:
        tag = f"{color}{B}[ OK ]{R}"
        print(f"  {tag}  {D}{msg}{R}")
        await asyncio.sleep(0.075)

    await asyncio.sleep(0.2)
    os.system("cls" if os.name == "nt" else "clear")

    for color, line in LOGO_LINES:
        if color:
            print(f"{color}{B}{line}{R}")
        else:
            print()
        await asyncio.sleep(0.042)

    w = console.width
    print()
    sub1 = "⚡  WizardLM 13B Code  ·  FP16  ·  Multi-GPU  ⚡"
    sub2 = f"ws › {RUST_WS_URL}"
    print(f"{MGT}{B}{sub1.center(w)}{R}")
    print(f"{D}{sub2.center(w)}{R}")
    print()

# ── Szerver várakozás ─────────────────────────────────────────────────────────
async def wait_for_server() -> bool:
    url = RUST_WS_URL.replace("ws://", "http://").replace("/ws/chat", "/health")
    spins = itertools.cycle(["⣾","⣽","⣻","⢿","⡿","⣟","⣯","⣷"])

    for i in range(30):
        try:
            urllib.request.urlopen(url, timeout=1)
            sys.stdout.write(f"\r  {GRN}{B}✓{R}  Szerver elérhető!{' ' * 20}\n\n")
            sys.stdout.flush()
            return True
        except Exception:
            s    = next(spins)
            dots = ("." * ((i % 3) + 1)).ljust(3)
            sys.stdout.write(f"\r  {YLW}{s}{R}  GPU-k betöltése{dots}")
            sys.stdout.flush()
            await asyncio.sleep(2)
    print()
    return False

# ── Segédfüggvények ───────────────────────────────────────────────────────────
def _wrap(text: str, width: int) -> list[str]:
    """Szöveg tördelése buborékhoz."""
    result = []
    for para in text.split("\n"):
        stripped = para.strip()
        if stripped:
            result.extend(textwrap.wrap(stripped, width=width) or [""])
        else:
            result.append("")
    return result or [""]

def _term_w() -> int:
    return console.width

# ── Felhasználó buborék ───────────────────────────────────────────────────────
def user_bubble(text: str):
    """Jobbra igazított cyan buborék."""
    tw = _term_w()
    content_w = min(tw - 12, 62)
    lines     = _wrap(text, content_w)
    inner_w   = max(len(l) for l in lines)
    box_w     = inner_w + 4       # 2 padding mindkét oldalon

    indent = " " * max(0, tw - box_w - 6)

    print()
    print(f"{indent}  {CYN}{TL}{H * box_w}{TR}{R} {B}●{R}")
    for line in lines:
        rpad = inner_w - len(line)
        print(f"{indent}  {CYN}{V}{R}  {WHT}{line}{R}{' ' * (rpad + 2)}{CYN}{V}{R}")
    print(f"{indent}  {CYN}{BL}{H * box_w}{BR}{R}")
    print()

# ── Bot thinking spinner ──────────────────────────────────────────────────────
async def thinking_bubble(ws, timeout: float = 120.0):
    """Rich Live spinner buborékban, automatikusan eltűnik."""
    recv_task = asyncio.create_task(
        asyncio.wait_for(ws.recv(), timeout=timeout)
    )
    spins = ["⣾","⣽","⣻","⢿","⡿","⣟","⣯","⣷"]
    dots  = ["   ", ".  ", ".. ", "..."]
    i = 0

    with Live(console=console, refresh_per_second=12, transient=True) as live:
        while not recv_task.done():
            s = spins[i % len(spins)]
            d = dots[(i // 3) % len(dots)]
            live.update(Panel(
                f"[yellow]{s}[/]  [dim white]gondolkodik{d}[/]",
                title=f"[bold green]◉ {escape(BOT_NAME)}[/]",
                subtitle="[dim]...[/]",
                border_style="dim blue",
                box=rbox.ROUNDED,
                width=34,
                padding=(0, 1),
            ))
            await asyncio.sleep(0.09)
            i += 1

    raw = await recv_task
    return json.loads(raw)

# ── Bot válasz buborék typing animációval ─────────────────────────────────────
async def bot_bubble_typing(text: str, ts: str = ""):
    """Zöld/kék buborék, karakterenként gépelt tartalommal."""
    tw        = _term_w()
    content_w = min(tw - 10, 70)
    lines     = _wrap(text, content_w)
    inner_w   = max(len(l) for l in lines)
    box_w     = inner_w + 4

    # ── Fejléc ──
    print(f"\n  {GRN}{B}◉ {BOT_NAME}{R}")
    sys.stdout.write(f"  {BLU}{TL}{H * box_w}{TR}{R}\n")
    sys.stdout.flush()

    # ── Sorok – azonnali kiírás ──
    for line in lines:
        rpad = inner_w - len(line)
        sys.stdout.write(f"  {BLU}{V}{R}  {WHT}{line}{R}{' ' * (rpad + 2)}{BLU}{V}{R}\n")
        sys.stdout.flush()

    # ── Lábléc ──
    if ts:
        meta    = f" {ts} "
        left_h  = box_w - len(meta) - 1
        sys.stdout.write(f"  {BLU}{BL}{H * left_h}{DL}{D}{meta}{R}{BLU}{DR}{H}{BR}{R}\n\n")
    else:
        sys.stdout.write(f"  {BLU}{BL}{H * box_w}{BR}{R}\n\n")
    sys.stdout.flush()

# ── Hiba buborék ──────────────────────────────────────────────────────────────
def error_bubble(msg: str):
    console.print(Panel(
        f"[bold red]{escape(msg)}[/]",
        border_style="red",
        box=rbox.HEAVY,
        padding=(0, 2),
    ))

# ── Súgó ──────────────────────────────────────────────────────────────────────
def show_help():
    console.print(Panel(
        f"[{CYN}] [bold cyan]/help[/]    [/]  Súgó\n"
        f"[{CYN}] [bold cyan]/clear[/]   [/]  Képernyő törlése\n"
        f"[{CYN}] [bold cyan]/session[/] [/]  Session ID\n"
        f"[{CYN}] [bold cyan]/quit[/]    [/]  Kilépés",
        title="[bold blue]Parancsok[/]",
        border_style="blue",
        box=rbox.ROUNDED,
        padding=(0, 2),
        width=36,
    ))

# ── Üdvözlő panel ─────────────────────────────────────────────────────────────
def welcome_panel(session_id: str, bot: str):
    console.print(Panel(
        f"[green]{B}✓ Kapcsolódva![/]\n\n"
        f"[dim]Session  [bold white]{session_id}[/][/]\n"
        f"[dim]Bot      [bold white]{bot}[/][/]\n\n"
        f"[dim]Típus [cyan]/help[/][dim] a parancsokért[/]",
        title=f"[bold green]{bot}[/]",
        border_style="green",
        box=rbox.DOUBLE,
        padding=(0, 2),
        width=50,
    ))
    console.print()

# ── Prompt ────────────────────────────────────────────────────────────────────
def read_input() -> str:
    print(f"{CYN}{B}╭─ Te{R}")
    return input(f"{CYN}╰─▶ {R}").strip()

# ── Fő chat hurok ─────────────────────────────────────────────────────────────
async def chat_loop():
    await boot_animation()

    ok = await wait_for_server()
    if not ok:
        error_bubble(
            "A szerver nem elérhető el 60s után.\n"
            "Futtasd: .\\scripts\\start_all.bat"
        )
        return

    try:
        async with websockets.connect(RUST_WS_URL) as ws:
            welcome = json.loads(await ws.recv())
            sid     = welcome.get("session_id", "?")
            bot_srv = welcome.get("bot", BOT_NAME)

            welcome_panel(sid, bot_srv)

            while True:
                try:
                    user_text = await asyncio.get_event_loop().run_in_executor(
                        None, read_input
                    )
                except (EOFError, KeyboardInterrupt):
                    break

                if not user_text:
                    continue

                # Belső parancsok
                cmd = user_text.lower()
                if cmd in ("/quit", "/exit"):
                    break
                if cmd == "/help":
                    show_help()
                    continue
                if cmd == "/clear":
                    os.system("cls" if os.name == "nt" else "clear")
                    await boot_animation()
                    welcome_panel(sid, bot_srv)
                    continue
                if cmd == "/session":
                    console.print(f"[dim]Session: {sid}[/]")
                    continue

                # Küldés
                user_bubble(user_text)
                await ws.send(json.dumps({"message": user_text, "max_tokens": 512}))

                # Thinking + válasz
                try:
                    resp = await thinking_bubble(ws, timeout=120.0)
                except asyncio.TimeoutError:
                    error_bubble("Timeout – 120s alatt nem érkezett válasz.")
                    continue
                except Exception as e:
                    error_bubble(str(e))
                    continue

                if resp.get("type") == "reply":
                    ts = datetime.now().strftime("%H:%M:%S")
                    await bot_bubble_typing(resp.get("data", ""), ts=ts)
                elif resp.get("type") == "error":
                    error_bubble(resp.get("message", "Ismeretlen hiba"))

    except websockets.exceptions.ConnectionRefusedError:
        error_bubble(f"Kapcsolat elutasítva: {RUST_WS_URL}")
    except Exception as e:
        error_bubble(str(e))

    print()
    console.print(Rule(f"[bold cyan]Viszlát![/]", style="cyan"))
    print()


if __name__ == "__main__":
    asyncio.run(chat_loop())
