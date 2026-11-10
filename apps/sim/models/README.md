# Wheat model

`wheat.apsimx` is the APSIM NG wheat model that the sim service runs. It produced `tests/fixtures/zealand_cleaned.csv`.

| Item          | Value                                                                                                                                                                 |
| :------------ | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| APSIM version | 2026.9.8110.0, set by `APSIM_VERSION` in `apps/sim/Dockerfile`. The model was first built in 2024.6.7516.0. At load time, APSIM upgrades the file to its own version. |
| Cultivar      | Hartog                                                                                                                                                                |
| Sowing date   | 15-Apr. `run_season()` replaces it with the date that you give.                                                                                                       |
| Soil          | Black Vertosol (clay), Norwin, Queensland, APSoil number 900                                                                                                          |
| Weather       | `tests/fixtures/Copenhagen_Weather.met`, Copenhagen 2025                                                                                                              |
| Clock         | 2025-01-01 to 2025-12-31                                                                                                                                              |
| Source paper  | Not known yet. Rares adds it.                                                                                                                                         |

## Report output

The Report node writes one row per day. `run_season()` returns a `SeasonResult`: the rows from sowing to harvest ripe and renames these columns, and the sowing data:

| Report variable                      | Column             |
| :----------------------------------- | :----------------- |
| `[Clock].Today`                      | `date`             |
| `[Wheat].LAI`                        | `lai`              |
| `[Wheat].Phenology.Zadok.Stage`      | `zadoks`           |
| `[Wheat].Phenology.CurrentStageName` | `stage`            |
| `[Wheat].AboveGround.Wt`             | `biomass`          |
| `[Wheat].Grain.Total.Wt*10 as Yield` | `yield`            |
| `[Soil].SoilWater.PAW`               | `paw_1` to `paw_7` |
| `[Soil].SoilWater.SW`                | `sw_1` to `sw_7`   |
| `[Wheat].SowingDate as SowingDate`   | `sowing_date`      |
| `[Wheat].AboveGround.N`              | `biomass_n`        |
| `[Wheat].Grain.Protein`              | `grain_protein`    |
| `[Wheat].Grain.Size`                 | `grain_size`       |
| `[Wheat].Grain.Number`               | `grain_number`     |
| `[Wheat].Grain.Total.Wt`             | `grain_wt`         |

APSIM fills `stage` only on the day that a stage starts. On the other days, `stage` is empty.

## Soil limits

The waterlogging and soil water alerts compare `sw_N` with these limits. The limits do not change during the season. The values are volumetric water content (mm/mm).

| Layer | Depth (cm) | LL15  | DUL   | SAT   |
| :---- | :--------- | :---- | :---- | :---- |
| 1     | 0 to 15    | 0.261 | 0.521 | 0.589 |
| 2     | 15 to 30   | 0.248 | 0.497 | 0.566 |
| 3     | 30 to 60   | 0.280 | 0.488 | 0.557 |
| 4     | 60 to 90   | 0.280 | 0.480 | 0.533 |
| 5     | 90 to 120  | 0.280 | 0.472 | 0.527 |
| 6     | 120 to 150 | 0.280 | 0.457 | 0.531 |
| 7     | 150 to 180 | 0.280 | 0.452 | 0.522 |

LL15 is the water content at 15 bar, the driest soil that a plant can use. DUL (drained upper limit) is the water content after free drainage stops. SAT is the water content of a soil with full pores.

## Stages

`stages.json` lists each stage name in the `stage` column, with a short farmer name and its Zadoks code. The `note` fields stay empty until S2-15.
