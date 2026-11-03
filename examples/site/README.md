# A routed site

Two pages, one shell, and an address bar that follows. The app is `app.py`; the demo is
`walkthrough.py`; the whole thing is one `App(routes=…, shell=…)`.

```
python3 -m examples.site.app --port 8200          # then http://127.0.0.1:8200/?from=paste
python3 -m examples.site.walkthrough --auto       # six steps, prints the frames
python3 tools/gate_site.py                        # 18 assertions: a socket and real Chromium
```

What it is here to show, and where each promise is asserted:

| promise | where it lives | asserted by |
|---|---|---|
| the shell and the first page arrive in **one frame** | `app.py` `shell()`, `reflux/app.py` `draw_page` | `gate_site` 1, `test_shell_and_events` |
| a page turn writes **only** the `routes` slot | `app.py` `go()` | `gate_site` 6, 12–13 |
| the address bar follows, and back comes home | `markers.page` + `www/static/reflux.js` | `gate_site` 12, 14 |
| a pasted address (with its query) opens that page | `reflux:hello` → `session.query` | `gate_site` 8, 17 |
| `connect` / `location` / `disconnect` reach the app | `make_app()` registers all three | `gate_site` 3, 7, 10 |
| no client can send those three | `reflux/ingest.py` | `test_shell_and_events` `TestTheWireRefusesHostEvents` |

Two things this example does *not* do, on purpose: it does not persist anything (a refresh is a new
session, as `DESIGN` says), and it does not render on the server — a deep link costs one connection
round trip before the first pixel.

The downlink's address is a path only. The query belongs to the browser: it comes **up** with
`hello` / `nav`, and a page turn never writes it back. If an app needs `?tab=2` to survive a
navigation, it puts that in the path it declares (or keeps it in its own state) — that is a design
choice recorded in `docs/DESIGN.md`, not an omission here.