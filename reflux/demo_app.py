"""The demo app: the four interactions T4's gate drives, written with the SDK alone.

An echo (an input uplinks its buffer, a text watches the slot it lands in), a list (rows live in
a list slot; the row's id rides the button that removes it), and a form (one submit carries
every field it holds). The app keeps its business state and pushes exactly the change each
handler made — the interface's working state stays in the shell.

    python3 -m reflux.demo_app --port 8000
"""

from __future__ import annotations

import argparse
import json

from . import ops, ui
from .app import App
from .node import Node

ECHO, ROWS, SUBMITTED = "echo", "rows", "submitted"
ECHO_SLOT, ROWS_SLOT, SUBMITTED_SLOT = f"/slots/{ECHO}", f"/slots/{ROWS}", f"/slots/{SUBMITTED}"


def row_node(row: dict) -> dict:
    """One row: its text, and the button that removes it — the button carries the row's id."""
    return ui.row(
        ui.text(row["text"]),
        ui.button("删", event="row.remove", variant="ghost", size="sm", id=row["id"]),
        gap="sm",
        id=row["id"],
    )


class Demo:
    """Business state only — what the interface is doing is the shell's business."""

    def __init__(self) -> None:
        self.echo = ""
        self.submitted: dict = {}
        self.rows = [{"id": "row-1", "text": "第一行"}, {"id": "row-2", "text": "第二行"}]
        self.next_row = 3

    def app(self) -> App:
        app = App()
        app.view = self.view
        app.events.register("name.change")(self.on_name)
        app.events.register("row.add")(self.on_add)
        app.events.register("row.remove")(self.on_remove)
        app.events.register("login.submit")(self.on_submit)
        return app

    # --- structure ------------------------------------------------------------------------

    def view(self, session) -> list[dict]:
        """First frame: the structure, plus the rows seeded into the slot the rack reads."""
        return [
            ops.create(self.tree(), title="reflux demo"),
            ops.patch(ROWS_SLOT, [row_node(row) for row in self.rows]),
        ]

    def tree(self) -> Node:
        return ui.stack(
            ui.heading("演示", level=1),
            ui.field(
                ui.input(
                    placeholder="名字",
                    source="name",
                    event="name.change",
                    payload=["value"],
                    id="name-input",
                ),
                label="名字",
            ),
            ui.text("", source=ECHO, id="echo"),
            ui.button("加一行", event="row.add", variant="primary", id="add-row"),
            ui.rack(source=ROWS, empty_text="还没有记录", id="rows"),
            ui.form(
                ui.field(ui.input(placeholder="用户名", source="user", id="f-user"), label="用户名"),
                ui.field(
                    ui.input(placeholder="口令", kind="password", source="pass", id="f-pass"),
                    label="口令",
                ),
                submit_label="保存",
                event="login.submit",
                payload=["fields"],
                id="login",
            ),
            ui.text("", source=SUBMITTED, id="submitted"),
            gap="lg",
        )

    # --- handlers: change the app's data, push exactly that change -------------------------

    def on_name(self, session, frame) -> None:
        self.echo = frame["data"]["value"]
        session.draw(ops.patch(ECHO_SLOT, self.echo))

    def on_add(self, session, frame) -> None:
        row = {"id": f"row-{self.next_row}", "text": f"第 {self.next_row} 行"}
        self.next_row += 1
        self.rows.append(row)
        session.draw(ops.insert(ROWS_SLOT, row_node(row), anchor="end"))

    def on_remove(self, session, frame) -> None:
        row_id = frame["id"]  # the button carried the row's identity up
        self.rows = [row for row in self.rows if row["id"] != row_id]
        session.draw(ops.remove(ROWS_SLOT, id=row_id))

    def on_submit(self, session, frame) -> None:
        self.submitted = dict(frame["data"]["fields"])
        summary = json.dumps(self.submitted, ensure_ascii=False, sort_keys=True)
        session.draw(ops.patch(SUBMITTED_SLOT, f"已提交 {summary}"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="reflux.demo_app", description="Serve the demo app.")
    ap.add_argument("--port", type=int, default=8000, help="0 picks a free port (default: 8000)")
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args(argv)
    app = Demo().app()
    if args.port == 0:
        server = app.make_server(0, args.host)
        print(f"[reflux] serving the demo on http://{args.host}:{server.server_address[1]}/", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0
    app.serve_forever(args.port, args.host)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())