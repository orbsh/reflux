# schema/ — the wire's snapshot

`accrete.schema.json` is a byte-exact snapshot of fluxen's wire types, exported with

    cd ~/world/fluxen && cargo run -q -p stage -- schema

- snapshot: 2026-11-19, sha256 `7e140988ee86cabc1fbacd81ef892c6905964bc4476aec31a46aef601ec18597`, 52 813 B
- shape: draft 2020-12, root `oneOf` of 24 arms (`{"properties": {"type": {"const": …}}, "$ref": "#/$defs/…"`), 55 `$defs`
- vocabulary: ADR 0032 retired `form` and `textarea` — `bundle` packs fields into one object (fields are
  named by their `tag`, the exit is the bundle's `sink`, the timing its `attrs.submit`), and a multi-line
  text area is `input` with `multiline: true`
- the export is deterministic: two exports of the same tree hash equal (measured), so a drift gate compares bytes

Why a snapshot instead of exporting at generation time: the SDK generator and the gates must not need
cargo, fluxen's checkout, or a build. Refreshing it is an explicit step:

    python3 tools/sync_schema.py           # report drift against fluxen's current export
    python3 tools/sync_schema.py --write   # accept it (then regenerate the SDK and read the diff)

Nothing here is hand-edited. `tools/gen_sdk.py` reads this file and `profile/profile.json`, and never
the other way around.