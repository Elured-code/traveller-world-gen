# system_map.py — CLI execution flowchart

Traces every function called when running `python system_map.py`.

This is the only CLI script that always calls `attach_detail` unconditionally —
the SVG map needs secondary world data for every orbit slot to populate the
orbit table.

```mermaid
flowchart TD
    ENTRY["system_map.py"] --> MAIN["main()"]

    MAIN --> ARGS["argparse: --name --seed --out --width --white-bg"]

    ARGS --> SEEDQ{"--seed provided?"}
    SEEDQ -- yes --> USEED["seed = args.seed"]
    SEEDQ -- no  --> RSEED["seed = secrets.randbelow(2^31)"]

    USEED & RSEED --> PRINT_SEED["print seed to stdout"]

    PRINT_SEED --> GFS_START

    subgraph GFS ["generate_full_system(name, seed)"]
        direction LR
        GFS_START["generate_stellar_data — WBH stars, age, multiples"]
        GFS_ORBS["generate_orbits — MAO, HZCO, spread, slot placement"]
        GFS_MW["generate_mainworld_at_orbit — physical steps 1-4"]
        GFS_RET(["return TravellerSystem"])

        GFS_START --> GFS_ORBS --> GFS_MW --> GFS_RET
    end

    GFS_RET --> ATT["attach_detail(system) — always; populates all orbit slots and moons"]
    ATT --> SUMM["system.summary() — print to stdout"]
    SUMM --> PAL{"--white-bg?"}
    PAL -- yes --> PLIT["palette = PALETTE_LIGHT"]
    PAL -- no  --> PDARK["palette = PALETTE_DARK"]

    PLIT & PDARK --> SVG["build_svg(system, canvas_w, palette) — generate SVG string"]

    SVG --> SAVE["save_output(svg_str, out_path) — write SVG file"]
    SAVE --> OPEN["_open_file(out_path) — open in default viewer"]
    OPEN --> DONE["print path and dimensions to stdout"]
```
