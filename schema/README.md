# schema/ — the wire's snapshot

`accrete.schema.json` is a byte-exact snapshot of fluxen's wire types, exported with

    cd ~/world/fluxen && cargo run -q -p stage -- schema

- snapshot: 2026-11-19, sha256 `c4d17e282c65552ab127cbea3b48729e8fb37766e3eeb11eb1178480358a7ce4`, 49 888 B
- shape: draft 2020-12, root `oneOf` of 15 arms (`{"properties": {"type": {"const": …}}, "$ref": "#/$defs/…"`), 44 `$defs`
- vocabulary: ADR 0034/0035 — one box carries cargo, so `group`, `grab` and `dock` are gone: a frame is
  `draggable` (its cargo is its own subtree), a landing is `accept` + `sink` (a drop that cannot emit is
  a load error), and `style` is the surface `group` had. `template` became `stamp`. `tiles` gained an
  axis of its own: `dir: row | row-reverse | col | col-reverse` (absent = `col`) and
  `wrap: wrap | wrap-reverse | nowrap` (absent = `wrap`), and a grid is `tiles` with
  `fields: [{key, title?, width?, align?, selectors?}]` and `header: {selector, layers: 1 | 2}` over
  rows that are the node `entry` (was `record`; its `id` is the item's key, its fields are its
  children, each named by its `attrs.selector`, and a field whose children are entries is a nested
  list drawn as child rows — there is no colspan/rowspan). How much of the slot is on stage is
  `window: {size: N}` (was `stage: all | one`); what advances it is `step: {timer: ms}` or `{slot: name}`
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