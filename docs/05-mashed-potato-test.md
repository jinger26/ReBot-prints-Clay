# 05 · First extrusion: mashed potato test

**Date:** 2026-11-24, about 16:20–17:01 EST
**Result:** ✅ **Extrusion works.** Material went in through the hose, the auger (driven by motor 7) carried it through the printed extruder, and it came out of the nozzle.

> 🎥 **Video:** [Watch the mashed potato extrusion test on YouTube](https://youtu.be/5tuex_aNPKw)

<p align="center">
<img src="../images/mashpotato-test/PXL_20261124_215111917.jpg" alt="Mashed potato extruded from the hose and nozzle onto the print bed" width="520">
</p>

## Why mashed potato?

Before using real clay, we tested with **instant mashed potato** as a stand-in. It's paste-like, cheap, safe and easy to clean up, so we could check the whole feed path without wasting clay or fighting clay-specific problems.

<p align="center">
<img src="../images/mashpotato-test/PXL_20261124_212011912.jpg" alt="Instant mashed potato, the filled cartridge, and the extruder parts" width="360">
</p>

## Setup

| | |
|---|---|
| Material | Instant mashed potato (prepared from flakes), loaded into a cartridge |
| Feed | Cartridge pushed with **compressed air** through a hose into the extruder's side inlet |
| Auger drive | **Motor 7** (RobStride RS-00, the arm's gripper motor) |
| Control | [`software/motor7_test.py`](../software/motor7_test.py) with `--spin` (continuous turning in velocity mode; default 7.5 RPM) |
| Arm | Stayed **still**. Only the auger turned. No arm motion yet. |
| Extruder | Printed extruder body with side feed inlet and nozzle, on the reBot B601-RS wrist |

Command used (from the [software](../software/) folder):

```bash
python motor7_test.py --spin 30
```

## Steps

1. Mix the mashed potato and fill the cartridge.
2. Connect the cartridge to the extruder's side inlet with the hose.
3. Apply compressed air to the cartridge to push potato into the extruder.
4. Run `motor7_test.py --spin` to turn the auger.
5. Watch the nozzle and collect what comes out on the bed.

<p>
<img src="../images/mashpotato-test/PXL_20261124_212212428.jpg" width="32%">
<img src="../images/mashpotato-test/PXL_20261124_213333137.jpg" width="32%">
<img src="../images/mashpotato-test/PXL_20261124_214338871.jpg" width="32%">
</p>
<p>
<img src="../images/mashpotato-test/PXL_20261124_215100873.jpg" width="32%">
<img src="../images/mashpotato-test/PXL_20261124_215105775.jpg" width="32%">
<img src="../images/mashpotato-test/PXL_20261124_220050588.jpg" width="32%">
</p>

## What we saw

- The full feed path works: compressed air → hose → side inlet → auger → nozzle.
- Motor 7 had enough torque to turn the auger through the paste.
- The output came out in **blobs and short strands**, not yet a continuous, even bead. That's expected for a first test, with manual air pressure and no tuning.

<p>
<img src="../images/mashpotato-test/PXL_20261124_220109968.jpg" alt="Inside the extruder housing after the test" width="48%">
<img src="../images/mashpotato-test/PXL_20261124_215303809.jpg" alt="Team after the test" width="48%">
</p>

## Next steps

- **Steady flow:** tune air pressure and auger RPM together (`--rpm`) and measure output per minute.
- **Real clay:** repeat with clay of a known moisture content.
- **Move the arm while extruding:** run the [circle path test](../software/README.md#circle_testpy) and turn the auger at the same time. Both motors are on the same CAN bus, so one program can do both.
- **Clean-up:** document how to take the extruder apart and clean it after each run.

## All photos

<details>
<summary>Show all 22 photos</summary>

<p>
<img src="../images/mashpotato-test/PXL_20261124_212011912.jpg" width="24%">
<img src="../images/mashpotato-test/PXL_20261124_212210130.jpg" width="24%">
<img src="../images/mashpotato-test/PXL_20261124_212212428.jpg" width="24%">
<img src="../images/mashpotato-test/PXL_20261124_212252171.jpg" width="24%">
<img src="../images/mashpotato-test/PXL_20261124_212448105.jpg" width="24%">
<img src="../images/mashpotato-test/PXL_20261124_213329685.jpg" width="24%">
<img src="../images/mashpotato-test/PXL_20261124_213333137.jpg" width="24%">
<img src="../images/mashpotato-test/PXL_20261124_213455338.jpg" width="24%">
<img src="../images/mashpotato-test/PXL_20261124_214039835.jpg" width="24%">
<img src="../images/mashpotato-test/PXL_20261124_214040450.jpg" width="24%">
<img src="../images/mashpotato-test/PXL_20261124_214200986.jpg" width="24%">
<img src="../images/mashpotato-test/PXL_20261124_214323230.jpg" width="24%">
<img src="../images/mashpotato-test/PXL_20261124_214338871.jpg" width="24%">
<img src="../images/mashpotato-test/PXL_20261124_214341743.jpg" width="24%">
<img src="../images/mashpotato-test/PXL_20261124_215100873.jpg" width="24%">
<img src="../images/mashpotato-test/PXL_20261124_215105775.jpg" width="24%">
<img src="../images/mashpotato-test/PXL_20261124_215111917.jpg" width="24%">
<img src="../images/mashpotato-test/PXL_20261124_215121218.jpg" width="24%">
<img src="../images/mashpotato-test/PXL_20261124_215121930.jpg" width="24%">
<img src="../images/mashpotato-test/PXL_20261124_215303809.jpg" width="24%">
<img src="../images/mashpotato-test/PXL_20261124_220050588.jpg" width="24%">
<img src="../images/mashpotato-test/PXL_20261124_220109968.jpg" width="24%">
</p>
</details>
