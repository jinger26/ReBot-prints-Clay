#!/usr/bin/env python3
"""
ReBot prints Clay — send the reBot Arm B601-RS to its home (zero) position.

Home = every joint at 0 rad (the folded rest pose set during calibration),
including motor 7 (gripper / auger motor).

What it does
------------
1. Reads all 7 joints (motors still OFF) and shows how far each is from home.
2. Joints already within 0.5° of home are left alone. If everything is
   already home, nothing is switched on.
3. Switches motors on HOLDING THEIR CURRENT POSITION (no jump), with gravity
   compensation from Seeed's SDK.
4. Moves slowly and smoothly to zero (arm and motor 7 together).
5. Switches all motors off. At home the arm rests on its own stops.

Ctrl+C: the arm freezes where it is, then motors are switched off — be
ready to support the arm if it is not near home when you press it.

Needs: motorbridge, pin, numpy, pyyaml and Seeed's SDK cloned at
~/rebot/reBotArm_control_py (see software/README.md). Close SenseCraft
Robotics and motorbridge-gateway first.

Usage
-----
    python home.py                 # default max joint speed 0.4 rad/s
    python home.py --speed 0.2     # slower
"""

from __future__ import annotations

import argparse
import math
import signal
import sys
import time
from pathlib import Path

import numpy as np

ap = argparse.ArgumentParser(description="Send the reBot arm to home (all joints 0)")
ap.add_argument("--sdk", default=str(Path.home() / "rebot" / "reBotArm_control_py"))
ap.add_argument("--speed", type=float, default=0.4, help="max joint speed in rad/s (default 0.4)")
ap.add_argument("--yes", action="store_true", help="skip the GO confirmation")
args = ap.parse_args()

sdk = Path(args.sdk).expanduser()
if not (sdk / "reBotArm_control_py").is_dir():
    sys.exit(f"SDK not found at {sdk}. See software/README.md.")
sys.path.insert(0, str(sdk))

from reBotArm_control_py.actuator import RebotArm  # noqa: E402
from reBotArm_control_py.controllers import RebotArmEndPose  # noqa: E402

N_ARM = 6
AT_HOME = math.radians(0.5)
PARAM_MECH_POS = 0x7019  # RobStride mechPos (rad) — readable while motor is off


def read_joints(arm) -> np.ndarray:
    names = [jc.name for jc in arm._all_joints]
    motors = [arm._motor_map[n] for n in names]
    ctrls = list(arm._ctrl_map.values())
    for m in motors:
        try:
            m.request_feedback()
        except Exception:
            pass
    time.sleep(0.02)
    for c in ctrls:
        for _ in range(len(motors) * 2):
            try:
                c.poll_feedback_once()
            except Exception:
                pass
    q = np.full(len(motors), np.nan)
    for i, m in enumerate(motors):
        st = m.get_state()
        if st is not None:
            q[i] = st.pos
        else:
            try:
                q[i] = float(m.robstride_get_param_f32(PARAM_MECH_POS, 300))
            except Exception:
                pass
    missing = [n for n, v in zip(names, q) if np.isnan(v)]
    if missing:
        raise RuntimeError(f"No feedback from: {', '.join(missing)}. Check 48 V power, CAN cable, "
                           "and that SenseCraft / motorbridge-gateway are closed.")
    return q


def main() -> None:
    arm = RebotArm()
    print(f"Connecting on '{arm._channel}' ...")
    arm.connect()
    names = [jc.name for jc in arm._all_joints]
    try:
        q0 = np.median([read_joints(arm) for _ in range(3)], axis=0)
    except RuntimeError as e:
        arm.disconnect()
        sys.exit(f"Stopped, nothing moved: {e}")

    print("\nJoint        now      → home")
    for n, v in zip(names, q0):
        flag = "" if abs(v) < AT_HOME else "   (will move)"
        print(f"  {n:<9} {math.degrees(v):+7.1f}°  →  0.0°{flag}")

    if np.all(np.abs(q0) < AT_HOME):
        print("\nAlready at home. Nothing to do.")
        arm.disconnect()
        return

    t_move = max(1.0, 2.0 * float(np.max(np.abs(q0))) / args.speed)
    print(f"\nMove time ≈ {t_move:.1f} s (max {args.speed} rad/s).")
    if not args.yes:
        print("Check: clear space around the arm, hand near the 48 V power switch.")
        if input("Type GO to go home: ").strip() != "GO":
            arm.disconnect()
            print("Cancelled, nothing moved.")
            return

    ctrl = RebotArmEndPose(arm)
    # Hold the current pose when motors switch on (SDK default target is 0 = a jump).
    ctrl._q_target = q0[:N_ARM].copy()
    ctrl._qd_target = np.zeros(N_ARM)
    has_grip = arm.has_gripper and len(q0) > N_ARM
    if has_grip:
        ctrl._gripper_target = float(q0[N_ARM])

    stop = {"flag": False}

    def on_sigint(*_):
        stop["flag"] = True

    signal.signal(signal.SIGINT, on_sigint)

    ctrl.start()
    try:
        time.sleep(0.8)  # settle holding position
        print("Going home ...")
        n = max(2, int(t_move * 100))
        t0 = time.monotonic()
        for i in range(n + 1):
            if stop["flag"]:
                print("\nCtrl+C — freezing here.")
                q_now = read_joints(arm)
                ctrl._q_target[:] = q_now[:N_ARM]
                if has_grip:
                    ctrl._gripper_target = float(q_now[N_ARM])
                time.sleep(0.5)
                break
            s = i / n
            k = 1.0 - (10 * s**3 - 15 * s**4 + 6 * s**5)  # min-jerk from 1 → 0
            ctrl._q_target[:] = q0[:N_ARM] * k
            if has_grip:
                ctrl._gripper_target = float(q0[N_ARM] * k)
            sleep = t0 + (i + 1) / 100 - time.monotonic()
            if sleep > 0:
                time.sleep(sleep)
        else:
            time.sleep(1.0)
            q_end = read_joints(arm)
            worst = float(np.max(np.abs(q_end)))
            print(f"Home reached (largest remaining offset {math.degrees(worst):.1f}°).")
    finally:
        # Disable without the SDK's own safe_home (we already handled the motion).
        ctrl._running = False
        arm.disconnect()
        print("Motors off.")


if __name__ == "__main__":
    main()
