"""
ClawDBot – Animált terminál chat kliens
Rich panelek + ANSI typing / spinner animációk
"""

import asyncio
import itertools
import json
import os
import sys
import urllib.request

RUST_WS_URL = os.environ.get("CLAWDBOT_WS_URL", "ws://127.0.0.1:3000/ws/chat")
BOT_NAME    = os.environ.get("CLAWDBOT_BOT_NAME", "ClawDBot")

# ── Függőség ellenőrzés ──────────────────────────────────────────────────────
_missing = []
try:
    import websockets
except ImportError:
    _missing.append("websockets>=12.0")
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.rule import Rule
    from rich.align import Align
    from rich.markup import escape
    from rich import box as rbox
except ImportError:
    _missing.append("rich>=13.0")

if _missing:
    print(f"[HIBA] pip install {' '.join(_missing)}")
    sys.exit(1)

console = Console(highlight=False)

# ── ANSI shortcut-ok (typing + spinner animációkhoz) ─────────────────────────
R  = "\033[0m"
B  = "\033[1m"
D  = "\033[2m"
CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
MAGENTA = "\033[95m"
WHITE   = "\033[97m"
RED     = "\033[91m"

# ── ASCII logó sorok ─────────────────────────────────────────────────────────
LOGO = [
    f"{CYAN}{B}  ██████╗██╗      █████╗ ██╗    ██╗██████╗ {R}",
    f"{CYAN}{B} ██╔════╝██║     ██╔══██╗██║    ██║██╔══██╗{R}",
    f"{CYAN}{B} ██║     ██║     ███████║██║ █╗ ██║██║  ██║{R}",
    f"{CYAN}{B} ██║     ██║     ██╔══██║██║███╗██║██║  ██║{R}",
    f"{CYAN}{B} ╚██████╗███████╗██║  ██║╚███╔███╔╝██████╔╝{R}",
    f"{CYAN}{B}  ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝╚═════╝ {R}",
    "",
    f"{MAGENTA}{B}  ██████╗  ██████╗ ████████╗{R}",
    f"{MAGENTA}{B}  ██╔══██╗██╔═══██╗╚══██╔══╝{R}",
    f"{MAGENTA}{B}  ██████╔╝██║   ██║   ██║   {R}",
    f"{MAGENTA}{B}  ██╔══██╗██║   ██║   ██║   {R}",
    f"{MAGENTA}{B}  ██████╔╝╚██████╔╝   ██║   {R}",
    f"{MAGENTA}{B}  ╚═════╝  ╚═════╝    ╚═╝   {R}",
]

# ── Boot animáció ─────────────────────────────────────────────────────────────

async def boot_animation():
    os.system("cls" if os.name == "nt" else "clear")

    boot_msgs = [
        (GREEN,   "CUDA drivers       OK"),
        (GREEN,   "GPU 0 detected     OK"),
        (GREEN,   "GPU 1 detected     OK"),
        (CYAN,    "WizardLM 13B FP16  loading..."),
        (CYAN,    "Multi-GPU VRAM split ..."),
        (YELLOW,  f"Starting {BOT_NAME} ..."),
    ]
    for color, msg in boot_msgs:
        print(f"  {color}[ {B}OK{R}{color} ]{R}  {D}{msg}{R}")
        await asyncio.sleep(0.08)

    await asyncio.sleep(0.25)
    os.system("cls" if os.name == "nt" else "clear")

    for i, line in enumerate(LOGO):
        print(line)
        await asyncio.sleep(0.045)

    w = console.width
    print()
    sub = "⚡  WizardLM 13B Code  ·  FP16  ·  Multi-GPU  ⚡"
    print(f"{MAGENTA}{B}{sub.center(w)}{R}")
    print(f"{D}{'ws: ' + RUST_WS_URL:^{w}}{R}")
    print()

# ── Szerver várakozás ─────────────────────────────────────────────────────────

async def wait_for_server() -> bool:
    health = RUST_WS_URL.replace("ws://", "http://").replace("/ws/chat", "/health")
    spins  = itertools.cycle(["⣾","⣽","⣻","⢿","⡿","⣟","⣯","⣷"])

    for i in range(30):
        try:
            urllib.request.urlopen(health, timeout=1)
            sys.stdout.write(f"\r  {GREEN}{B}✓ Szerver elérhető!{R}                \n")
            sys.stdout.flush()
            return True
        except Exception:
            s    = next(spins)
            dots = "." * ((i % 3) + 1) + "   "
            sys.stdout.write(f"\r  {YELLOW}{s}{R}  GPU-k betöltése{dots}")
            sys.stdout.flush()
            await asyncio.sleep(2)

    print()
    return False

# ── Thinking spinner ──────────────────────────────────────────────────────────

async def thinking_animation(ws, timeout: float = 120.0):
    """Spinner amíg a bot válaszol, visszaadja a JSON választ."""
    spins  = itertools.cycle(["⣾","⣽","⣻","⢿","⡿","⣟","⣯","⣷"])
    colors = itertools.cycle([YELLOW, "\033[93m", "\033[33m"])

    recv_task = asyncio.create_task(
        asyncio.wait_for(ws.recv(), timeout=timeout)
    )

    while not recv_task.done():
        s = next(spins)
        c = next(colors)
        sys.stdout.write(f"\r  {c}{B}{s}{R}{c}  {BOT_NAME} gondolkodik...{R}  ")
        sys.stdout.flush()
        await asyncio.sleep(0.09)

    sys.stdout.write(f"\r{' ' * 60}\r")
    sys.stdout.flush()

    raw = await recv_task
    return json.loads(raw)

# ── Typing hatás ──────────────────────────────────────────────────────────────

async def type_response(text: str):
    w = min(console.width - 6, 76)
    print(f"\n  {GREEN}{B}⚙ {BOT_NAME}{R}")
    print(f"  {D}{'─' * w}{R}")
    print("  ", end="")

    for char in text:
        if char == "\n":
            sys.stdout.write(f"\n  ")
            await asyncio.sleep(0.01)
        else:
            sys.stdout.write(f"{WHITE}{char}{R}")
            if char in ".!?":
                await asyncio.sleep(0.055)
            elif char in ",;:":
                await asyncio.sleep(0.028)
            else:
                await asyncio.sleep(0.013)
        sys.stdout.flush()

    print(f"\n  {D}{'─' * w}{R}\n")

# ── Üzenet panelek ────────────────────────────────────────────────────────────

def show_user_msg(text: str):
    console.print(
        Align.right(
            Panel(
                Text(text, style="white"),
                title=f"[bold cyan]● Te[/]",
                title_align="right",
                border_style="cyan",
                box=rbox.ROUNDED,
                padding=(0, 2),
                width=min(console.width - 4, 80),
            )
        )
    )

def show_help():
    console.print(Panel(
        "[cyan]/help[/]     Súgó\n"
        "[cyan]/clear[/]    Képernyő törlése\n"
        "[cyan]/session[/]  Session ID\n"
        "[cyan]/quit[/]     Kilépés",
        title="[bold blue]Parancsok[/]",
        border_style="blue",
        box=rbox.ROUNDED,
    ))

def show_error(msg: str):
    console.print(Panel(
        f"[bold red]{escape(msg)}[/]",
        border_style="red",
        box=rbox.HEAVY,
    ))

# ── Fő chat hurok ─────────────────────────────────────────────────────────────

async def chat_loop():
    await boot_animation()

    ok = await wait_for_server()
    if not ok:
        show_error(
            "A szerver nem érhető el 60 másodperc után.\n"
            "Futtasd: scripts\\start_all.bat"
        )
        return

    session_id = None

    try:
        async with websockets.connect(RUST_WS_URL) as ws:
            raw     = await ws.recv()
            welcome = json.loads(raw)
            session_id = welcome.get("session_id", "?")
            bot_srv    = welcome.get("bot", BOT_NAME)

            console.print(Panel(
                f"[green]✓ Kapcsolódva![/]\n"
                f"[dim]Session: [bold]{session_id}[/][/]\n"
                f"[dim]Bot:     [bold]{bot_srv}[/][/]\n\n"
                "[dim]Típus [cyan]/help[/][dim] a parancsokért[/]",
                title=f"[bold green]{BOT_NAME}[/]",
                border_style="green",
                box=rbox.DOUBLE,
            ))
            console.print()

            while True:
                try:
                    print(f"{CYAN}{B}╭─ Te{R}")
                    user_input = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: input(f"{CYAN}╰─▶ {R}")
                    )
                    user_input = user_input.strip()
                except (EOFError, KeyboardInterrupt):
                    break

                if not user_input:
                    continue

                if user_input.lower() in ("/quit", "/exit"):
                    break
                if user_input.lower() == "/help":
                    show_help()
                    continue
                if user_input.lower() == "/clear":
                    os.system("cls" if os.name == "nt" else "clear")
                    await boot_animation()
                    continue
                if user_input.lower() == "/session":
                    console.print(f"[dim]Session: {session_id}[/]")
                    continue

                show_user_msg(user_input)
                await ws.send(json.dumps({"message": user_input, "max_tokens": 512}))

                try:
                    resp = await thinking_animation(ws, timeout=120.0)
                except asyncio.TimeoutError:
                    show_error("Timeout – 120mp alatt nem érkezett válasz.")
                    continue
                except Exception as e:
                    show_error(str(e))
                    continue

                if resp.get("type") == "reply":
                    await type_response(resp.get("data", ""))
                elif resp.get("type") == "error":
                    show_error(resp.get("message", "Ismeretlen hiba"))

                console.print()

    except websockets.exceptions.ConnectionRefusedError:
        show_error(f"Kapcsolat elutasítva: {RUST_WS_URL}\nFuttasd: scripts\\start_all.bat")
    except Exception as e:
        show_error(str(e))

    console.print(Rule(f"[bold cyan]Viszlát![/]", style="cyan"))


if __name__ == "__main__":
    asyncio.run(chat_loop())
