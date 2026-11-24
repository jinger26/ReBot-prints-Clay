# Software

| Script | What it does | Hardware-tested |
|---|---|---|
| [`motor7_test.py`](motor7_test.py) | Turns motor 7 (gripper / auger motor) by a set angle (default 45° counter-clockwise), or spins it continuously with `--spin`. Only motor 7 is switched on. | ✅ 2026-11-24: 90°, 360°, 30 s spin at 7.5 RPM |
| [`home.py`](home.py) | Slowly returns all 7 joints to home (0°). Shows what will move and asks for `GO`. | Not yet (checked up to the `GO` prompt) |
| [`circle_test.py`](circle_test.py) | Traces a small horizontal circle in the air at constant height, speed and tool orientation. First printing-style motion test. | Not yet (planner verified offline) |

## Setup (macOS or Linux)

```bash
conda activate rebot
pip install motorbridge pin pyyaml numpy matplotlib
git clone https://github.com/Seeed-Projects/reBotArm_control_py.git ~/rebot/reBotArm_control_py
```

macOS also needs the PCBUSB library (`libPCBUSB.dylib` in `~/.local/lib`, no `sudo` needed, or `/usr/local/lib`). See [docs/01-getting-started.md](../docs/01-getting-started.md).

**Before running any script:** quit SenseCraft Robotics (⌘Q) and stop `motorbridge-gateway` (Ctrl+C). Only one program can use the CAN adapter at a time. If it's still held you'll see `PCAN_ERROR_INITIALIZE` or "no feedback".

## motor7_test.py

```bash
python motor7_test.py                    # 45° counter-clockwise
python motor7_test.py --deg 90           # 90° counter-clockwise
python motor7_test.py --deg 360          # one full revolution (8 s)
python motor7_test.py --cw --return      # clockwise, then back
python motor7_test.py --spin 30          # keep turning for 30 s at 7.5 RPM
python motor7_test.py --spin 30 --rpm 15 # faster
```

- Angle moves use soft position control (MIT mode). Expect to land 1–2° short of the target.
- `--spin` uses velocity mode, because RobStride MIT position targets are limited to about ±720°.
- It stops automatically if the motor is blocked. Ctrl+C switches it off.
- "Counter-clockwise" = looking at the motor's output face. Use `--flip` if your motor turns the other way.

## home.py

```bash
python home.py
python home.py --speed 0.2   # slower
```

Motors switch on holding their current position, then move smoothly to 0° with gravity compensation, then switch off. **Only use it after zero calibration** (see below). Otherwise "home" may be far from the real rest pose.

## circle_test.py

```bash
python circle_test.py --read           # live joint angles, motors off
python circle_test.py --dry-run --plot # plan only, no hardware
python circle_test.py                  # real run: 5 cm circle, 15 mm/s, 2 laps
```

- Move the arm out of the folded home pose first (e.g. J2 ≈ J3 ≈ 0.8 rad). At home, joints 2 and 3 sit on their end stops and the circle is rejected.
- The circle starts and ends at the current position. The whole path is checked (IK, joint limits, joint speed) before any motor is switched on, and it asks for `GO`.
- Ctrl+C freezes the arm, then it returns slowly to home.

## Lessons learned

- **Reading positions with motors off:** a switched-off RobStride motor ignores status requests but answers parameter reads. The scripts fall back to the `mechPos` parameter (`0x7019`, rad). The SDK's `get_state()` silently returns `0.0` for motors that didn't answer, which looks like "joint at zero".
- **Zero calibration per arm:** after swapping arms, check that the joints read ≈ 0° in the physical home pose (`python home.py` and answer no at `GO`). If not, redo zero calibration in MotorBridge Studio. Or set zero per motor with MotorBridge's `set_zero_position()` + `store_parameters()`, motors off. SenseCraft keeps its own separate calibration.
