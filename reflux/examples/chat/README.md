# An AI chat app

One page, one composer, a backend that streams. This is the example that shows what a reflux
application looks like when the interesting work is on the server: a conversation per connection, a
reply that arrives in chunks, a stop that stops, a second message refused with a reason, and a model
that can fail without taking the page down.

```
python3 -m reflux.examples.chat.app --port 8100     # the app, then open http://127.0.0.1:8100/
python3 -m reflux.examples.chat.walkthrough --auto  # the same backend, no browser
python3 tools/gate_chat.py                          # 12 assertions over a socket and a browser
```

| file | what it is |
| --- | --- |
| `app.py` | the application: the page, `chat.send` / `chat.stop`, the streaming worker, the app's limits |
| `model.py` | the model seam: `Scripted` (offline, deterministic) and `OpenAI` (SSE, env-configured) |
| `walkthrough.py` | the six behaviours, one Enter at a time, printed as frames |
| `client.py` | a stdlib WebSocket client — what the walkthrough and the gate talk through |

The composer submits with its **发送** button: in this vocabulary a form's submit is a *click*
(`gate_t4`), not an Enter inside its text input.

## What the backend does

1. **A conversation per connection.** The transcript's *display* is the page tree (rows in a rack), so
   the backend only keeps what a model needs: turns, and how many of them the window holds. State hangs
   off the `Session`, so it dies with the socket — reflux's model is that the socket *is* the state,
   and a refresh is a new conversation. Nothing is persisted; there is no account, no history, no
   database.
2. **Streaming.** A worker thread per reply appends chunks with
   `wire.patch(slot, "/bind/value/default", chunk, op="append")`. Frames queue on the session and one
   writer drains them, so a slow client blocks its own writer and never a model call.
3. **Single flight.** A second message while one is streaming is refused **with a reason on the status
   line** — the composer stays enabled, so that send is a real event and gets a real answer.
4. **Stop.** `chat.stop` sets an event the worker checks at chunk boundaries; the bubble gets a `⏹` and
   the status line says so. The half sentence is **not** added to the context: a truncated reply is
   worse for the next turn than no reply at all. (The visible transcript and the model's context
   therefore differ by exactly the stopped replies — that is the choice, not an oversight.)
5. **A failing model is a bubble.** The exception becomes text in the reply slot plus a status line.
   It never travels up the frame path; a raised handler would only be logged, and the reader would see
   a reply that silently stopped mid-sentence.
6. **Application limits.** Empty and oversized messages are refused here. `MAX_CHARS` is this app's
   rule — the ingest boundary checks the *shape* of a frame, which is the protocol's business, and has
   no opinion about how long a prompt may be.

The status line after each turn is `就绪 · <model> · <turns> 轮（窗口 n/N，裁掉 m）`: turns ever
recorded, turns the model would see, turns dropped. When it trims, that is the honest signal that the
model's view is narrower than the reader's.

## The model seam

```python
class Model(Protocol):
    name: str
    def reply(self, context: list[Turn]) -> Iterator[str]: ...
```

`Scripted` is the default: offline, deterministic, no key, and its answer states what the backend just
did (turn number, window, chunk delay) so a demo run reads as documentation.

`OpenAI` speaks the OpenAI-compatible `/chat/completions` SSE form:

```
OPENAI_BASE_URL=https://api.example/v1 OPENAI_API_KEY=… OPENAI_MODEL=… \
  python3 -m reflux.examples.chat.app --model openai
```

It has **not** been exercised against a live provider from this repo — there is no key here. Its
request body and SSE reader are tested against a local stub (`tests/test_chat_example.py`), which
covers the part that can be wrong independently of the vendor; everything past that is the vendor's.

## What this example deliberately does not do

- No persistence, sessions, auth, or history across reloads (`Session` + `app.py`'s docstring).
- No tool calls, no retrieval, no multi-part content: one text in, one stream of chunks out.
- No token accounting or rate limiting — a deployment's concerns, not an example's.

## Run it against a running app

```
python3 -m reflux.examples.chat.app --port 8100
python3 -m reflux.examples.chat.walkthrough --attach --port 8100
```

`--delay` paces the chunks, `--window` sets the context window (small values make the trimming step
visible in a few messages), and `--model openai` swaps the seam. Without `--attach`, the walkthrough
starts its own app on a free port and shuts it down on exit.