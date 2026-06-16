# traveller_system_gen.py — CLI execution flowchart

Traces every function called when running `python traveller_system_gen.py`.

Note: `generate_mainworld_at_orbit` generates physical characteristics only
(steps 1–4, atmosphere detail, hydrographic detail).  Social steps 5–13
(population, government, TL, etc.) are deferred and `apply_mainworld_social`
is **not** called by the CLI, so the mainworld UWP carries placeholder values
for the social characteristics.

```mermaid
flowchart TD
    ENTRY["traveller_system_gen.py"] --> MAIN["main()"]

    MAIN --> ARGS["argparse: --name --count --seed --detail --nhz-atmospheres --format --json --html"]

    ARGS --> FMT1{"--html flag?"}
    FMT1 -- yes --> RES_HTML["out_format=html, want_detail=True"]
    FMT1 -- no  --> FMT2{"--json flag?"}
    FMT2 -- yes --> RES_JSON["out_format=json, want_detail=args.detail"]
    FMT2 -- no  --> RES_TEXT["out_format=text or --format value"]

    RES_HTML & RES_JSON & RES_TEXT --> LOOP["for i in range(count)"]

    LOOP --> FRNG

    subgraph GFS ["generate_full_system(name, seed, nhz_atmospheres)"]
        direction TB
        FRNG["rng = random.Random(seed)"]
        GSTELL["generate_stellar_data — WBH stars, age, multiples"]
        GORB["generate_orbits — MAO, HZCO, spread, slot placement"]
        MWCHK{"mainworld orbit found?"}
        P1["Step 1: generate_size"]
        P2["Step 2: generate_atmosphere or generate_nhz_atmosphere"]
        P3["Step 3: generate_temperature_from_orbit — orbital HZ deviation"]
        P4A["generate_atmosphere_detail — pressure, taints, subtypes"]
        P4B["Step 4: generate_hydrographics"]
        P4C["generate_gas_mix, generate_unusual_subtype"]
        P5["generate_hydrographic_detail"]
        P6["set gas_giant_count and belt_count from orbit counts"]
        PNOTE["social steps 5-13 deferred — placeholder values only"]
        NOMW["mainworld = None"]
        SYSRET(["return TravellerSystem"])

        FRNG --> GSTELL --> GORB --> MWCHK
        MWCHK -- yes --> P1 --> P2 --> P3 --> P4A --> P4B --> P4C --> P5 --> P6 --> PNOTE --> SYSRET
        MWCHK -- no  --> NOMW --> SYSRET
    end

    SYSRET --> DETQ{"want_detail?"}
    DETQ -- yes --> ATT["attach_detail(system) — secondary world SAH and moon profiles"]
    DETQ -- no  --> OUTQ{"out_format?"}
    ATT --> OUTQ

    OUTQ -- json --> OJ["system.to_json()"]
    OUTQ -- html --> OH["system.to_html(detail_attached)"]
    OUTQ -- text --> OT["system.summary()"]

    OJ & OH & OT --> STDOUT["stdout"]
```
