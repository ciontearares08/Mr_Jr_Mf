# Wheat model

`wheat.apsimx` is the APSIM NG wheat model that the sim service runs. It is calibrated for Danish winter wheat against the field trials of Kumar et al. 2023.

| Item          | Value                                                                                                                                                                                                                                |
| :------------ | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| APSIM version | 2026.9.8110.0, set by `APSIM_VERSION` in `apps/sim/Dockerfile`. At load time, APSIM upgrades the file to its own version.                                                                                                            |
| Crop          | Winter wheat                                                                                                                                                                                                                         |
| Cultivar      | DK_Winter: APSIM's Claire with Danish changes (see "Cultivar")                                                                                                                                                                       |
| Clock         | 2025-09-01 to 2026-08-31, one winter wheat season. `run_season()` replaces it with the first and last day of the weather file it is given                                                                                            |
| Weather       | `tests/fixtures/Copenhagen_2025-26.met`, the DMI file from S2-04 (cell 10km_617_72, 1 Sep 2025 to 31 Aug 2026). The model refers to it by a path relative to `models/`. `run_season()` replaces it with the weather file it is given |
| Soil          | Flakkebjerg, Zealand: sandy loam from Kumar et al. 2023 Table 4, in 7 layers to 180 cm (see "Soil")                                                                                                                                  |
| Source paper  | Kumar et al. 2023, Plants 12:986: soils, trial management and observed yields used for the calibration                                                                                                                               |

## Cultivar

DK_Winter is a cultivar node under Wheat. It copies Claire's parameters and changes these:

| Parameter                                       | Value                    | Why                                                                               |
| :---------------------------------------------- | :----------------------- | :-------------------------------------------------------------------------------- |
| Grain filling duration                          | 750 °C·d                 | Kumar et al. 2023 (Danish cultivar)                                               |
| Maximum grain size                              | 0.045 g                  | Kumar et al. 2023                                                                 |
| Tillering rate                                  | 0.5 new tillers per leaf | The default kept tillering all winter (6000–7000 stems/m²); now 600–1000 stems/m² |
| Grains per gram of stem                         | 26                       | APSIM default; fits best once the soil N is realistic                             |
| Extra leaf death under water stress             | off (0)                  | Water stress already lowers growth; the default made the canopy collapse in July  |
| Leaf critical N concentration (until flowering) | 0.85 × default           | Calibrated: the crop needs less leaf N for full growth                            |
| Root nitrate uptake (KNO3)                      | 0.04                     | Calibrated: roots take up fertiliser N faster                                     |
| Size of the largest leaves                      | 1600 mm²                 | Calibrated so peak LAI matches Danish wheat (about 6–7) and Sentinel-2 LAI        |

## Soil

Flakkebjerg sandy loam from Kumar et al. 2023 Table 4. The table gives a topsoil and a subsoil. The layers in between are a mix of the two, and the deeper layers copy the subsoil.

| Setting                | Value                                                      |
| :--------------------- | :--------------------------------------------------------- |
| Starting nitrate       | 60 kg N/ha in the profile                                  |
| Inert carbon           | Active carbon in the top two layers capped at 2.0 %        |
| Starting soil water    | 60 % of plant-available water                              |
| Surface residue        | 1000 kg/ha wheat straw                                     |
| Soil evaporation dates | Summer from 1-Apr, winter from 1-Oct (northern hemisphere) |
| Wheat lower limit (LL) | Equal to LL15                                              |

`dk_soils_7layer.json` has all 7 Kumar trial soils (Rødby, Haderslev, Svenstrup, Flakkebjerg, Brønderslev, Horsens, Sæby) in the same 7 layers, with their coordinates, for choosing the nearest soil per field later (S4-35).

## Sowing rule

The manager "Sow using a variable rule" sows inside a date window.

| Setting      | Value                                                                                                             |
| :----------- | :---------------------------------------------------------------------------------------------------------------- |
| Window       | 15-sep to 15-oct                                                                                                  |
| Conditions   | Extractable soil water above 10 mm and at least 5 mm of rain in the last 7 days                                   |
| Last day     | If the conditions are never met, the crop is sown on the last day of the window, so every field gets a prediction |
| Cultivar     | DK_Winter                                                                                                         |
| Population   | 300 plants/m²                                                                                                     |
| Row spacing  | 125 mm                                                                                                            |
| Sowing depth | 30 mm                                                                                                             |

## Fertiliser

| Manager             | When              | Amount              |
| :------------------ | :---------------- | :------------------ |
| Fertilise at sowing | On the sowing day | 20 kg N/ha as NO3N  |
| Fertilise in spring | 20 March          | 150 kg N/ha as NO3N |

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
| `[Wheat].Grain.Total.N`              | `grain_n`          |

APSIM fills `stage` only on the day that a stage starts. On the other days, `stage` is empty.

## Soil limits

The waterlogging and soil water alerts compare `sw_N` with these limits. The limits do not change during the season. The values are volumetric water content (mm/mm).

| Layer | Depth (cm) | LL15  | DUL   | SAT   |
| :---- | :--------- | :---- | :---- | :---- |
| 1     | 0 to 15    | 0.090 | 0.260 | 0.400 |
| 2     | 15 to 30   | 0.100 | 0.263 | 0.389 |
| 3     | 30 to 60   | 0.110 | 0.267 | 0.373 |
| 4     | 60 to 90   | 0.120 | 0.270 | 0.350 |
| 5     | 90 to 120  | 0.120 | 0.270 | 0.350 |
| 6     | 120 to 150 | 0.120 | 0.270 | 0.350 |
| 7     | 150 to 180 | 0.120 | 0.270 | 0.350 |

LL15 is the water content at 15 bar, the driest soil that a plant can use. DUL (drained upper limit) is the water content after free drainage stops. SAT is the water content of a soil with full pores.

## Accuracy

Calibrated against 132 yield points from Kumar et al. 2023: 20 trials at 7 Danish sites, 2016–2020, 0 to 303 kg N/ha. The observed yields were read from the paper's Figure 4 (about ±300 kg/ha).

| RMSE (kg/ha)                     | This model | Kumar et al. 2023 |
| :------------------------------- | ---------: | ----------------: |
| Calibration trials               |       1467 |              1491 |
| Evaluation trials                |       1470 |              1296 |
| Leave one site out               |       1487 |                   |
| Leave one year out               |       1485 |                   |
| This file, 48 Flakkebjerg points |       1036 |                   |

The model is within ±1.4 t/ha of the field yield for 2 in 3 trial points, and within ±2.8 t/ha for 19 in 20. Peak LAI at 150 kg N/ha or more is 4.2 to 7.5 (mean 6.1).

`tests/test_model_accuracy.py` runs this file on the 48 Flakkebjerg points and fails if the RMSE goes above 1150 kg/ha, the bias outside ±600 kg/ha, or a trial stops responding to N.

Known limits:

- Rødby (Lolland) is 2.2 to 2.7 t/ha too low in 2018 and 2020.
- Grains are too light (about 37 g per 1000 grains; Danish crops 45–50 g). The total yield fits.
- At one N rate, the model separates sites and seasons only weakly (r² 0.14 to 0.24), so the website shows yield as a range.
- Fields away from Flakkebjerg use the same soil, so expect larger errors there.

## Stages

`stages.json` lists each stage name in the `stage` column, with a short farmer name and its Zadoks code. The `note` fields stay empty until S2-15.
