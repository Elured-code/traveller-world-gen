# traveller_world_gen.py — CLI execution flowchart

Traces every function called when running `python traveller_world_gen.py` from
the command line.  Atmosphere detail (`generate_atmosphere_detail`) is **not**
in this path — it is only populated by the API layer and gen-ui.

```mermaid
flowchart TD
    ENTRY["traveller_world_gen.py"] --> MAIN["main()"]

    MAIN --> ARGS["argparse: --name --count --seed --json --html"]

    ARGS --> RNG{"seed provided?"}
    RNG -- yes --> RNG_INIT["rng = random.Random with seed"]
    RNG -- no  --> RNG_MOD["use module-level _rng"]

    RNG_INIT --> LOOP
    RNG_MOD  --> LOOP

    LOOP["for i in range(count), assign name"] --> GW

    subgraph GW ["generate_world(name, seed, rng)"]
        direction TB
        S1["Step 1: generate_size — 2D minus 2"]
        S2["Step 2: generate_atmosphere — 2D minus 7 plus Size, min 0"]
        S3["Step 3: generate_temperature — 2D plus atm DM"]
        S4["Step 4: generate_hydrographics — 2D minus 7 plus Atm plus DMs"]
        S5["Step 5: generate_population — 2D minus 2"]
        S6["Step 6: generate_government — 2D minus 7 plus Pop"]
        CHK_POP1{"population = 0?"}
        LAW_ZERO["law_level = 0"]
        S7["Step 7: generate_law_level — 2D minus 7 plus Gov"]
        S8["Step 8: generate_starport — 2D plus Pop DM"]
        CHK_POP2{"population = 0?"}
        TL_ZERO["tech_level = 0"]
        S9["Step 9: generate_tech_level — 1D plus DMs"]
        CHK_TL{"TL below min for atm?"}
        TL_NOTE["notes: TL viability warning"]
        S10["Step 10: generate_bases — 2D per type"]
        S11A["generate_gas_giant — 2D le 9"]
        S11B["generate_gas_giant_count"]
        S11C["generate_belt_count"]
        S11D["generate_population_multiplier"]
        S12["Step 12: assign_trade_codes — 18 codes"]
        S13["Step 13: assign_travel_zone — Amber/Red/Green"]
        RET(["return World"])

        S1 --> S2 --> S3 --> S4 --> S5 --> S6
        S6 --> CHK_POP1
        CHK_POP1 -- yes --> LAW_ZERO --> S8
        CHK_POP1 -- no  --> S7 --> S8
        S8 --> CHK_POP2
        CHK_POP2 -- yes --> TL_ZERO --> CHK_TL
        CHK_POP2 -- no  --> S9 --> CHK_TL
        CHK_TL -- yes --> TL_NOTE --> S10
        CHK_TL -- no  --> S10
        S10 --> S11A --> S11B --> S11C --> S11D
        S11D --> S12 --> S13 --> RET
    end

    LOOP -- next i --> GW

    RET --> ACC["worlds.append(world)"]
    ACC --> FMT{"output format?"}

    FMT -- json-single  --> J1["world.to_json()"]
    FMT -- json-multi   --> J2["json.dumps list of to_dict()"]
    FMT -- html-single  --> H1["world.to_html() via world_card.html"]
    FMT -- html-multi   --> H2["render world_list.html"]
    FMT -- text         --> T1["world.summary()"]

    J1 & J2 & H1 & H2 & T1 --> OUT["stdout"]
```
