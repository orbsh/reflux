# schema/ — the wire's snapshot

`accrete.schema.json` is a byte-exact snapshot of fluxen's wire types, exported with

    cd ~/world/fluxen && cargo run -q -p stage -- schema

- snapshot: 2026-11-19, sha256 `83ddb31865446b1913b66bb661a6419d6a2b645a94d49a299ae0b5c0ad0824a7`, 49 605 B
- shape: draft 2020-12, root `oneOf` of 18 arms (`{"properties": {"type": {"const": …}}, "$ref": "#/$defs/…"`), 46 `$defs`
- vocabulary: ADR 0031 §4 replaced `rack` and `pages` with one node, `tiles` — `stage: all | one` says how
  much of the slot is on stage, `step: {timer: ms}` or `{slot: name}` says what advances it — and folded
  the table family (`table`/`thead`/`tbody`/`tr`/`th`/`td`) into it: a grid is `tiles` with
  `columns: [{key, title?, width?, align?, selectors?}]` and `header: {selector, rows: 1 | 2}` over rows
  that are the new node `record` (its `id` is the item's key; its fields are its children, each named by
  its `attrs.selector`, and a field whose children are records is a nested list drawn as child rows —
  there is no colspan/rowspan)
- vocabulary, before it: ADR 0032 retired `form` and `textarea` — `bundle` packs fields into one object
  (fields are named by their `tag`, the exit is the bundle's `sink`, the timing its `attrs.submit`), and
  a multi-line text area is `input` with `multiline: true`
- the export is deterministic: two exports of the same tree hash equal (measured), so a drift gate compares bytes

Why a snapshot instead of exporting at generation time: the SDK generator and the gates must not need
cargo, fluxen's checkout, or a build. Refreshing it is an explicit step:

    python3 tools/sync_schema.py           # report drift against fluxen's current export
    python3 tools/sync_schema.py --write   # accept it (then regenerate the SDK and read the diff)

Nothing here is hand-edited. `tools/gen_sdk.py` reads this file and `profile/profile.json`, and never
the other way around.