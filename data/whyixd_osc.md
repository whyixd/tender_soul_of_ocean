# Whyixd OSC 

## People

`/whyixd/people/counts` → people count in 4 area

`/whyixd/people/vector` → calculate basic on `/people/counts`

## Wind

`/whyixd/wind/speed` → raw data from sensor (m/s)

`/whyixd/wind/angle` → raw data from sensor (0~360°)

`/whyixd/wind/vector` → calculate basic on `wind/angle`

## Composite

`/whyixd/composite/weight` → calculate basic on `people` and `wind`

`/whyixd/composite/level` → basic on `composite/weight` and `composite/threshold` (0,1,2 represent Low, medium, high)

`/whyixd/composite/threshold` → define by whyixd, default is [0,0.3,0.8,1]

## Light

`/whyixd/light/vector` → calculate basic on `people/vector` and `wind/vector` and `composite/weight`

`/whyixd/light/dmx` → realtime light output data

## Run demo

Double click to launch `run`, a window will pop up ask to choose a folder, please select `tender_soul_of_ocean_Klong` after that a terminal window will pop up and browser will automatic open and rederict to "http://localhost:5000" if it show error or no connection please reflash webpage.

If need to change osc destination ip, open  `osc_config.json` under `tsoo/tender_soul_of_ocean_Klong` change to target ip save then close and relunch the program.

```json
{
    "address": "127.0.0.1",
    "port": 5005
}
```