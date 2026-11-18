# schema/ — the wire's snapshot

`accrete.schema.json` is a byte-exact snapshot of fluxen's wire types, exported with

    cd ~/world/fluxen && cargo run -q -p stage -- schema

- snapshot: 2026-11-18, sha256 `b8759f68fb3649d2692b54bb3ae9dfe06a5c5bca8a5c81c24a4bd438b17c390c`, 54 906 B
- shape: draft 2020-12, root `oneOf` of 29 arms (`{"properties": {"type": {"const": …}}, "$ref": "#/$defs/…"`), 59 `$defs`
- the export is deterministic: two exports of the same tree hash equal (measured), so a drift gate compares bytes

Why a snapshot instead of exporting at generation time: the SDK generator and the gates must not need
cargo, fluxen's checkout, or a build. Refreshing it is an explicit step:

    python3 tools/sync_schema.py           # report drift against fluxen's current export
    python3 tools/sync_schema.py --write   # accept it (then regenerate the SDK and read the diff)

Nothing here is hand-edited. `tools/gen_sdk.py` reads this file and `profile/profile.json`, and never
the other way around.