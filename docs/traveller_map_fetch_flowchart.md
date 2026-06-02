# traveller_map_fetch.py — CLI execution flowchart

Traces every function called when running `python traveller_map_fetch.py`.

Unlike the other CLI scripts, this one populates `atmosphere_detail` on the
mainworld inside `generate_system_from_map`, because the canonical UWP is used
verbatim rather than rolled, so those sub-procedures must be called explicitly.

```mermaid
flowchart TD
    ENTRY["traveller_map_fetch.py"] --> MAIN["main()"]

    MAIN --> ARGS["argparse: --sector required, --name OR --hex required, --seed --detail --format --json --html"]

    ARGS --> FMT1{"--html flag?"}
    FMT1 -- yes --> RES_HTML["out_format=html, want_detail=True"]
    FMT1 -- no  --> FMT2{"--json flag?"}
    FMT2 -- yes --> RES_JSON["out_format=json, want_detail=args.detail"]
    FMT2 -- no  --> RES_TEXT["out_format=text"]

    RES_HTML & RES_JSON & RES_TEXT --> FETCH

    subgraph GSM ["generate_system_from_map(name, sector, hex_pos, seed, attach)"]
        direction TB
        FETCH["fetch_world_data — HTTP GET to travellermap.com"]
        SEED["rng = random.Random(seed)"]
        STARS["reconstruct_star_system — canonical stellar types from star string"]
        ORBS["generate_orbits(stellar, rng) — procedural orbit placement"]
        RWORLD["reconstruct_world(map_data) — canonical UWP used verbatim"]
        RECON["_reconcile_orbit_types — align slot types with PBG counts"]
        STAMP["set canonical_profile on mainworld orbit slot"]
        TEMP["generate_temperature_from_orbit — derive temp from HZ deviation"]
        ATMDET["generate_atmosphere_detail — pressure, taints, subtypes"]
        GASMIX["generate_gas_mix"]
        UNUSUB["generate_unusual_subtype"]
        HYDRODET["generate_hydrographic_detail"]
        ATTQ{"attach=True?"}
        ATTD["attach_detail(system, rng) — secondary world SAH and moon profiles"]
        SYSRET(["return TravellerSystem"])

        FETCH --> SEED --> STARS --> ORBS --> RWORLD --> RECON --> STAMP
        STAMP --> TEMP --> ATMDET --> GASMIX --> UNUSUB --> HYDRODET --> ATTQ
        ATTQ -- yes --> ATTD --> SYSRET
        ATTQ -- no  --> SYSRET
    end

    SYSRET --> ERRQ{"exception raised?"}
    ERRQ -- LookupError --> E1["sys.exit: Not found"]
    ERRQ -- URLError    --> E2["sys.exit: Network error"]
    ERRQ -- other       --> E3["sys.exit: Error message"]
    ERRQ -- none        --> OUTQ{"out_format?"}

    OUTQ -- json --> OJ["system.to_json()"]
    OUTQ -- html --> OH["system.to_html(detail_attached)"]
    OUTQ -- text --> OT["system.summary()"]

    OJ & OH & OT --> STDOUT["stdout"]
```
