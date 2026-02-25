"""
ClawDBot – Premium animált terminál chat
Sárga-narancs téma · Forgó animációk · Rich Live spinner
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
CHAT_TIMEOUT_SECONDS = float(os.environ.get("CHAT_TIMEOUT_SECONDS", "300"))
CHAT_MAX_TOKENS = int(os.environ.get("CHAT_MAX_TOKENS", "512"))

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
    from rich.text    import Text
    from rich         import box as rbox
except ImportError:  _miss.append("rich>=13.0")

if _miss:
    print(f"pip install {' '.join(_miss)}")
    sys.exit(1)

console = Console(highlight=False)

# ── ANSI – Sárga / Narancs / Arany téma ─────────────────────────────────────
R   = "\033[0m"
B   = "\033[1m"
D   = "\033[2m"
I   = "\033[3m"
# Sárga-narancs paletta
ORG  = "\033[38;5;214m"   # narancs
YLW  = "\033[38;5;220m"   # arany sárga
LYLW = "\033[38;5;228m"   # halvány sárga
AMBER = "\033[38;5;208m"  # amber/mély narancs
HONEY = "\033[38;5;178m"  # méz
WHT  = "\033[97m"
DIM  = "\033[38;5;242m"
RED  = "\033[91m"
BLK  = "\033[38;5;236m"

TL,TR = "╭","╮"
BL,BR = "╰","╯"
V,H   = "│","─"
DL,DR = "├","┤"

FIRE_SPARKS = ["✦", "✧", "⚡", "★", "◆", "◇", "✦", "⚡"]

# ── Logo ─────────────────────────────────────────────────────────────────────
LOGO_LINES = [
    (ORG,   "   ██████╗██╗      █████╗ ██╗    ██╗"),
    (ORG,   "  ██╔════╝██║     ██╔══██╗██║    ██║"),
    (YLW,   "  ██║     ██║     ███████║██║ █╗ ██║"),
    (YLW,   "  ██║     ██║     ██╔══██║██║███╗██║"),
    (AMBER, "  ╚██████╗███████╗██║  ██║╚███╔███╔╝"),
    (AMBER, "   ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝"),
    ("",    ""),
    (YLW,   "  ██████╗  ██████╗ ████████╗"),
    (ORG,   "  ██╔══██╗██╔═══██╗╚══██╔══╝"),
    (ORG,   "  ██████╔╝██║   ██║   ██║   "),
    (AMBER, "  ██╔══██╗██║   ██║   ██║   "),
    (AMBER, "  ██████╔╝╚██████╔╝   ██║   "),
    (YLW,   "  ╚═════╝  ╚═════╝    ╚═╝   "),
]

# ── Boot animáció ────────────────────────────────────────────────────────────
async def boot_animation():
    os.system("cls" if os.name == "nt" else "clear")

    boot_items = [
        (YLW,   "CUDA runtime",         "v12.x"),
        (ORG,   "GPU 0 online",         "RTX series"),
        (ORG,   "GPU 1 online",         "GTX series"),
        (AMBER, "LLM Engine",           "loading model"),
        (YLW,   "VRAM split",           "multi-GPU · auto"),
        (HONEY, f"{BOT_NAME}",          "initializing"),
    ]

    spinners = itertools.cycle(["◐", "◓", "◑", "◒"])

    for color, label, detail in boot_items:
        sp = next(spinners)
        tag = f"{color}{B}[{sp} OK]{R}"
        print(f"  {tag}  {DIM}{label:<22s}{R} {D}{detail}{R}")
        await asyncio.sleep(0.12)

    await asyncio.sleep(0.3)
    os.system("cls" if os.name == "nt" else "clear")

    for color, line in LOGO_LINES:
        if color:
            print(f"{color}{B}{line}{R}")
        else:
            print()
        await asyncio.sleep(0.04)

    w = console.width
    print()
    sparks = f"{ORG}{''.join(FIRE_SPARKS[:4])}{R}"
    sub1 = f"{sparks}  {YLW}{B}ClawDBot Coder{R}  {DIM}·  GPU Accelerated  ·  Local LLM{R}  {sparks}"
    sub2 = f"{DIM}ws › {RUST_WS_URL}{R}"
    center_pad1 = " " * max(0, (w - 60) // 2)
    center_pad2 = " " * max(0, (w - len(RUST_WS_URL) - 10) // 2)
    print(f"{center_pad1}{sub1}")
    print(f"{center_pad2}{sub2}")

    separator = f"{AMBER}{H * w}{R}"
    print(f"\n{separator}\n")

# ── Szerver várakozás ────────────────────────────────────────────────────────
async def wait_for_server() -> bool:
    url = RUST_WS_URL.replace("ws://", "http://").replace("/ws/chat", "/health")
    orbit = itertools.cycle(["◐","◓","◑","◒"])
    dots_cycle = itertools.cycle(["·  ", "·· ", "···", " ··", "  ·", "   "])

    for i in range(45):
        try:
            urllib.request.urlopen(url, timeout=1)
            sys.stdout.write(f"\r  {YLW}{B}★{R}  {ORG}Szerver elérhető!{R}{' ' * 30}\n\n")
            sys.stdout.flush()
            return True
        except Exception:
            s = next(orbit)
            d = next(dots_cycle)
            sys.stdout.write(f"\r  {ORG}{s}{R}  {DIM}Kapcsolódás{d}{R}")
            sys.stdout.flush()
            await asyncio.sleep(2)
    print()
    return False

# ── Segédfüggvények ──────────────────────────────────────────────────────────
def _wrap(text: str, width: int) -> list[str]:
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

# ── Felhasználó buborék (sárga, jobbra) ─────────────────────────────────────
def user_bubble(text: str):
    tw = _term_w()
    content_w = min(tw - 12, 62)
    lines     = _wrap(text, content_w)
    inner_w   = max(len(l) for l in lines)
    box_w     = inner_w + 4

    indent = " " * max(0, tw - box_w - 6)

    print()
    print(f"{indent}  {YLW}{TL}{H * box_w}{TR}{R} {ORG}{B}●{R}")
    for line in lines:
        rpad = inner_w - len(line)
        print(f"{indent}  {YLW}{V}{R}  {WHT}{line}{R}{' ' * (rpad + 2)}{YLW}{V}{R}")
    print(f"{indent}  {YLW}{BL}{H * box_w}{BR}{R}")
    print()

# ── Bot thinking spinner (narancs forgó) ─────────────────────────────────────
async def thinking_bubble(ws, timeout: float = CHAT_TIMEOUT_SECONDS):
    deadline = asyncio.get_event_loop().time() + timeout
    orbit = ["◐","◓","◑","◒"]
    fire  = ["🔥","✨","⚡","💡","🔥","✨","⚡","💡"]
    i = 0

    with Live(console=console, refresh_per_second=12, transient=True) as live:
        while True:
            s = orbit[i % len(orbit)]
            f = fire[i % len(fire)]
            live.update(Panel(
                f"[bold yellow]{s}[/]  [yellow]gondolkodik[/] {f}",
                title=f"[bold dark_orange]◉ {escape(BOT_NAME)}[/]",
                subtitle="[dim yellow]···[/]",
                border_style="dark_orange",
                box=rbox.ROUNDED,
                width=36,
                padding=(0, 1),
            ))

            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise asyncio.TimeoutError()

            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=min(0.25, remaining))
                msg = json.loads(raw)
                msg_type = msg.get("type")
                if msg_type in ("reply", "error"):
                    return msg
            except asyncio.TimeoutError:
                pass

            await asyncio.sleep(0.05)
            i += 1

# ── Bot válasz buborék (narancs keret) ───────────────────────────────────────
async def bot_bubble_typing(text: str, ts: str = ""):
    tw        = _term_w()
    content_w = min(tw - 10, 70)
    lines     = _wrap(text, content_w)
    inner_w   = max(len(l) for l in lines)
    box_w     = inner_w + 4

    print(f"\n  {ORG}{B}◉ {BOT_NAME}{R}")
    sys.stdout.write(f"  {AMBER}{TL}{H * box_w}{TR}{R}\n")
    sys.stdout.flush()

    for line in lines:
        rpad = inner_w - len(line)
        sys.stdout.write(f"  {AMBER}{V}{R}  {LYLW}{line}{R}{' ' * (rpad + 2)}{AMBER}{V}{R}\n")
        sys.stdout.flush()

    if ts:
        meta    = f" {ts} "
        left_h  = max(1, box_w - len(meta) - 1)
        sys.stdout.write(f"  {AMBER}{BL}{H * left_h}{DL}{DIM}{meta}{R}{AMBER}{DR}{H}{BR}{R}\n\n")
    else:
        sys.stdout.write(f"  {AMBER}{BL}{H * box_w}{BR}{R}\n\n")
    sys.stdout.flush()

# ── Hiba buborék ─────────────────────────────────────────────────────────────
def error_bubble(msg: str):
    console.print(Panel(
        f"[bold red]{escape(msg)}[/]",
        border_style="red",
        box=rbox.HEAVY,
        padding=(0, 2),
    ))

# ── Súgó ─────────────────────────────────────────────────────────────────────
def show_help():
    console.print(Panel(
        "[bold yellow]/help[/]      Súgó\n"
        "[bold yellow]/clear[/]     Képernyő törlése\n"
        "[bold yellow]/session[/]   Session ID\n"
        "[bold yellow]/quit[/]      Kilépés",
        title="[bold dark_orange]★ Parancsok[/]",
        border_style="dark_orange",
        box=rbox.ROUNDED,
        padding=(0, 2),
        width=36,
    ))

# ── Üdvözlő panel ───────────────────────────────────────────────────────────
def welcome_panel(session_id: str, bot: str):
    console.print(Panel(
        f"[bold yellow]★ Kapcsolódva![/]\n\n"
        f"[dim]Session  [bold yellow]{session_id}[/][/]\n"
        f"[dim]Bot      [bold dark_orange]{bot}[/][/]\n\n"
        f"[dim]Írd: [bold yellow]/help[/][dim] a parancsokért[/]",
        title=f"[bold dark_orange]◉ {bot}[/]",
        border_style="dark_orange",
        box=rbox.DOUBLE,
        padding=(0, 2),
        width=52,
    ))
    console.print()

# ── Prompt ───────────────────────────────────────────────────────────────────
def read_input() -> str:
    print(f"{ORG}{B}╭─ Te{R}")
    return input(f"{ORG}╰─▶ {R}").strip()

# ── Fő chat hurok ───────────────────────────────────────────────────────────
async def chat_loop():
    await boot_animation()

    ok = await wait_for_server()
    if not ok:
        error_bubble(
            "A szerver nem elérhető 90s után.\n"
            "Futtasd: .\\scripts\\start_all.bat"
        )
        return

    try:
        async with websockets.connect(RUST_WS_URL, ping_interval=None) as ws:
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

                user_bubble(user_text)
                await ws.send(json.dumps({"message": user_text, "max_tokens": CHAT_MAX_TOKENS}))

                try:
                    resp = await thinking_bubble(ws, timeout=CHAT_TIMEOUT_SECONDS)
                except asyncio.TimeoutError:
                    error_bubble(f"Timeout – {int(CHAT_TIMEOUT_SECONDS)}s alatt nem érkezett válasz.")
                    continue
                except Exception as e:
                    error_bubble(str(e))
                    continue

                if resp.get("type") == "reply":
                    ts = datetime.now().strftime("%H:%M:%S")
                    await bot_bubble_typing(resp.get("data", ""), ts=ts)
                elif resp.get("type") == "error":
                    error_bubble(resp.get("message", "Ismeretlen hiba"))

    except (OSError, websockets.exceptions.ConnectionClosedError):
        error_bubble(f"Kapcsolat elutasítva: {RUST_WS_URL}")
    except Exception as e:
        error_bubble(str(e))

    print()
    console.print(Rule("[bold yellow]★ Viszlát! ★[/]", style="dark_orange"))
    print()


if __name__ == "__main__":
    asyncio.run(chat_loop())
