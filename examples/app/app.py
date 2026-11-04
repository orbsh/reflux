"""The application: one shell, and the pages that hang off it.

    python3 -m examples.app --port 8100             # 概览 + 对话
    python3 -m examples.app.walkthrough --auto      # the same walk, no browser

A page is a file. `dashboard.py` owns `/`, `chat.py` owns `/chat`; each declares its route on this
module's `app` with `@app.route`, and each keeps the handlers for its own events. Importing a page
module is what puts it in the table — there is no registry file to keep in step, and no factory to
put between a declaration and its handler.

The shell is the frame the pages are drawn into: it carries the nav and the `routes` slot the
framework writes to. It is drawn once per connection, so a page turn replaces one slot and leaves
the header alone.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # `python3 examples/app/app.py`, not just `-m examples.app.app`
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
from typing import Any

from reflux import ROUTES_SLOT, Routes
from reflux.app import App, Device
from reflux.sdk import builders as b
from reflux.sdk.types import Accrete

__all__ = ["app", "heard", "main", "shell"]

SHELL_ID = "shell"

# What the host said, in order — the walkthrough and the gate read it. That log is this application's
# own business; the framework hands an event over and forgets it.
heard: list[tuple[str, str, Any]] = []


def shell(device: Device) -> Accrete:
    """The frame around every page: drawn with the first page, then left alone.

    Two rows — the nav, then the page — and the shell owns the viewport height, so a page can say
    "fill the rest" (`height: 100%`) and mean it. A shell that does not do that leaves a chat page's
    message list with no height to scroll in.
    """
    return b.case(
        b.case(
            b.form(b.button("概览"), dest="go.dashboard", id="nav-dashboard"),
            b.form(b.button("对话"), dest="go.chat", id="nav-chat"),
            b.text("reflux 示例", variant="muted"),
            id="nav",
            grid={"grid-template-columns": "auto auto 1fr", "gap": "8px", "align-items": "center"},
        ),
        b.placeholder(source=ROUTES_SLOT, id="routes"),
        id=SHELL_ID,
        grid={"grid-template-rows": "auto 1fr", "height": "100vh", "padding": "16px", "gap": "12px", "box-sizing": "border-box"},
    )


# Its own table, not the module-level default: a path is declared once per table, and the default one
# is shared by every module that uses `@route`.
app = App(routes=Routes(), shell=shell)


@app.dests.register("go.dashboard")
def on_dashboard(device: Device, frame: dict) -> None:
    device.go("/")


@app.dests.register("go.chat")
def on_chat(device: Device, frame: dict) -> None:
    device.go("/chat")


@app.dests.register("connect")
def on_connect(device: Device, frame: dict) -> None:
    heard.append(("connect", device.path, dict(device.query)))


@app.dests.register("location")
def on_location(device: Device, frame: dict) -> None:
    heard.append(("location", device.path, dict(device.query)))


@app.dests.register("disconnect")
def on_disconnect(device: Device, frame: dict) -> None:
    heard.append(("disconnect", device.id, dict(device.query)))


def main() -> None:
    ap = argparse.ArgumentParser(description="The reflux example: a dashboard and a chat page.")
    ap.add_argument("--port", type=int, default=8100)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--model", choices=("scripted", "openai"), default="scripted")
    ap.add_argument("--delay", type=float, default=0.02, help="seconds between chunks")
    ap.add_argument("--window", type=int, default=12, help="turns of context the model sees")
    args = ap.parse_args()

    from . import chat  # the page modules declare their routes on import; `__init__` does this too

    chat.settings.delay = args.delay
    chat.settings.window = args.window
    chat.settings.model = chat.OpenAI() if args.model == "openai" else chat.Scripted(window=args.window)
    print(f"[app] routes={[r.path for r in app.routes]} model={chat.settings.model.name}", flush=True)
    app.serve_forever(args.port, args.host)


if __name__ == "__main__":
    main()