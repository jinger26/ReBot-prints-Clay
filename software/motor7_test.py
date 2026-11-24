#!/usr/bin/env python3
"""
ReBot prints Clay — turn motor 7 by a set angle (default: 45° counter-clockwise).

Motor 7 is the reBot B601-RS gripper motor; in this project it may also
drive the clay auger. Only motor 7 is switched on; the 6 arm joints stay
OFF (limp), so rest the arm somewhere stable first (folded home is fine).

What it does
------------
1. Reads where motor 7 is now.
2. Switches on ONLY motor 7, holding that position, and checks its
   position reading agrees before moving.
3. Turns smoothly by --deg degrees in the chosen direction, holds briefly.
4. With --return it turns back to the start; otherwise it stays there.
5. Switches motor 7 off.

Direction
---------
"Clockwise" = looking AT the motor's output face (the side the shaft /
spline comes out of). We assume RobStride's positive direction is
counter-clockwise from that view (right-hand rule), so counter-clockwise
is a positive angle. If the first run turns the wrong way, use --flip.

Safety
------
* Soft, springy control (low stiffness): if it meets an end stop or a
  finger it pushes gently instead of forcing.
* If the motor stops following the command (blocked), it stops and reports.
* Ctrl+C at any time switches motor 7 off immediately.

Needs only `motorbridge`. Close SenseCraft Robotics and motorbridge-gateway
first: only one program can use the CAN adapter.

Usage
-----
    python motor7_test.py                    # 45° counter-clockwise, stay there
    python motor7_test.py --return           # 45° counter-clockwise, then back
    python motor7_test.py --deg 90 --cw      # 90° clockwise
    python motor7_test.py --deg 360          # one full revolution (8 s)
    python motor7_test.py --spin 30          # keep turning for 30 s at 7.5 RPM
    python motor7_test.py --spin 30 --rpm 15 # faster
    python motor7_test.py --flip             # if it turned the wrong way
"""

from __future__ import annotations

import argparse
import math
import sys
import time

from motorbridge import Controller, Mode

ap = argparse.ArgumentParser(description="Turn reBot motor 7 by a set angle")
ap.add_argument("--deg", type=float, default=45.0, help="angle to turn in degrees (default 45)")
ap.add_argument("--cw", action="store_true", help="turn clockwise instead of counter-clockwise")
ap.add_argument("--flip", action="store_true", help="invert the direction convention if it turned the wrong way")
ap.add_argument("--return", dest="ret", action="store_true", help="turn back to the start afterwards")
ap.add_argument("--time", type=float, default=None,
                help="seconds for the turn (default: 2 s per 90°, minimum 2 s)")
ap.add_argument("--hold", type=float, default=1.0, help="seconds to hold at the end position")
ap.add_argument("--spin", type=float, default=None, metavar="SECONDS",
                help="keep turning continuously for this many seconds (speed mode, max 300)")
ap.add_argument("--rpm", type=float, default=7.5, help="speed for --spin in RPM (default 7.5, max 30)")
ap.add_argument("--channel", default="can0", help="CAN channel (macOS: can0 maps to PCAN_USBBUS1)")
ap.add_argument("--motor-id", type=lambda s: int(s, 0), default=0x07)
ap.add_argument("--feedback-id", type=lambda s: int(s, 0), default=0xFD)
ap.add_argument("--model", default="rs-00")
ap.add_argument("--kp", type=float, default=5.0, help="stiffness (default 5, soft)")
ap.add_argument("--kd", type=float, default=0.5, help="damping (default 0.5)")
args = ap.parse_args()

if args.spin is not None and not (0 < args.spin <= 300 and 0 < args.rpm <= 30):
    sys.exit("--spin must be 0–300 s and --rpm 0–30 for this test.")
if not 0 < args.deg <= 720:
    sys.exit("--deg must be between 0 and 720 (two turns) for this test.")
if args.time is None:
    args.time = max(2.0, args.deg / 90.0 * 2.0)

RATE = 100.0  # Hz
LAG_LIMIT = 0.3  # rad: stop if the motor falls this far behind the command
PARAM_MECH_POS = 0x7019  # RobStride "mechPos" parameter (rad)

# Positive motor angle = CCW seen from the output face (assumed).
sign = -1.0 if args.cw else 1.0
if args.flip:
    sign = -sign
delta = sign * math.radians(args.deg)
dir_name = "clockwise" if args.cw else "counter-clockwise"


def read_position(motor, ctrl, attempts: int = 5) -> float:
    """Motor position in rad. A switched-off RobStride doesn't answer status
    requests but does answer parameter reads, so fall back to mechPos."""
    for _ in range(attempts):
        motor.request_feedback()
        time.sleep(0.01)
        for _ in range(5):
            ctrl.poll_feedback_once()
        st = motor.get_state()
        if st is not None:
            return st.pos
    try:
        return float(motor.robstride_get_param_f32(PARAM_MECH_POS, 500))
    except Exception as e:
        raise RuntimeError("No feedback from motor 7. Check 48 V power, the CAN cable, and that "
                           "SenseCraft / motorbridge-gateway are closed.") from e


def smooth(s: float) -> float:
    """0→1 with zero speed at both ends (cosine ease)."""
    return 0.5 - 0.5 * math.cos(math.pi * min(max(s, 0.0), 1.0))


def spin(motor, ctrl) -> None:
    """Turn continuously at --rpm for --spin seconds using velocity mode.

    Speed ramps up and down over 1 s. If the motor turns much slower than
    commanded for 0.5 s (blocked / end stop), it stops. Ctrl+C stops it.
    The caller's finally-block switches the motor off.
    """
    v_target = sign * args.rpm * 2 * math.pi / 60.0  # rad/s
    ramp = 1.0
    total = args.spin + 2 * ramp
    print(f"Will turn {dir_name} at {args.rpm:g} RPM for {args.spin:g} s "
          f"(≈ {args.rpm * args.spin / 60:.1f} turns), plus 1 s ramp up/down.")
    print("Only motor 7 will be switched on. Keep fingers clear.")
    if input("Type GO to start: ").strip() != "GO":
        print("Cancelled, nothing moved.")
        return

    motor.ensure_mode(Mode.VEL, 1000)
    motor.send_vel(0.0)
    motor.enable()
    spin.enabled = True
    print("Spinning ... (Ctrl+C to stop)")
    turned = 0.0
    slow_since = None
    t0 = last = time.monotonic()
    next_print = t0 + 5
    while True:
        now = time.monotonic()
        t = now - t0
        if t >= total:
            break
        if t < ramp:
            v = v_target * smooth(t / ramp)
        elif t > total - ramp:
            v = v_target * smooth((total - t) / ramp)
        else:
            v = v_target
        motor.send_vel(v)
        ctrl.poll_feedback_once()
        st = motor.get_state()
        if st is not None:
            turned += st.vel * (now - last)
            # stall check during the cruise phase only
            if ramp < t < total - ramp and abs(st.vel) < 0.3 * abs(v_target):
                slow_since = slow_since or now
                if now - slow_since > 0.5:
                    print(f"\n  Motor 7 is turning at {st.vel:+.2f} rad/s instead of "
                          f"{v_target:+.2f} — blocked / end stop. Stopping.")
                    break
            else:
                slow_since = None
        last = now
        if now >= next_print:
            print(f"  {t:5.1f} s   {abs(turned) / (2 * math.pi):5.2f} turns")
            next_print += 5
        sleep = 1 / RATE - (time.monotonic() - now)
        if sleep > 0:
            time.sleep(sleep)
    motor.send_vel(0.0)
    time.sleep(0.3)
    print(f"Done. Turned about {abs(turned) / (2 * math.pi):.2f} turns "
          f"({math.degrees(turned):+.0f}°). If that wasn't {dir_name}, next time add --flip.")


spin.enabled = False


def main() -> None:
    print(f"Connecting on '{args.channel}' ...")
    ctrl = Controller(args.channel)
    motor = ctrl.add_robstride_motor(args.motor_id, args.feedback_id, args.model)
    enabled = False
    try:
        if args.spin is not None:
            spin(motor, ctrl)
            return
        q_start = read_position(motor, ctrl)
        q_target = q_start + delta
        print(f"Motor 7 now at {math.degrees(q_start):+.1f}°. "
              f"Will turn {args.deg:g}° {dir_name} to {math.degrees(q_target):+.1f}°"
              f"{' and back' if args.ret else ''}.")
        print("Only motor 7 will be switched on. Keep fingers clear.")
        if input("Type GO to start: ").strip() != "GO":
            print("Cancelled, nothing moved.")
            return

        motor.ensure_mode(Mode.MIT, 1000)
        motor.send_mit(q_start, 0.0, args.kp, args.kd, 0.0)  # hold current position first
        motor.enable()
        enabled = True

        # Safety: once enabled, check the motor's own position report agrees.
        st = None
        for _ in range(30):
            motor.send_mit(q_start, 0.0, args.kp, args.kd, 0.0)
            time.sleep(1 / RATE)
            for _ in range(5):
                ctrl.poll_feedback_once()
            st = motor.get_state()
            if st is not None:
                break
        if st is None:
            raise RuntimeError("Motor 7 switched on but sends no position replies — stopping.")
        if abs(st.pos - q_start) > 0.1:
            raise RuntimeError(f"Position check failed: read {q_start:+.3f} rad while off but "
                               f"{st.pos:+.3f} rad once on — stopping, nothing moved.")

        def go(q_from: float, q_to: float, label: str) -> bool:
            print(label)
            n = max(1, int(args.time * RATE))
            t0 = time.monotonic()
            for i in range(n + 1):
                q_cmd = q_from + (q_to - q_from) * smooth(i / n)
                motor.send_mit(q_cmd, 0.0, args.kp, args.kd, 0.0)
                ctrl.poll_feedback_once()
                st = motor.get_state()
                if st is not None and abs(st.pos - q_cmd) > LAG_LIMIT:
                    print(f"  Motor 7 stopped following at {math.degrees(st.pos):+.1f}° "
                          f"(commanded {math.degrees(q_cmd):+.1f}°) — blocked / end stop.")
                    return False
                sleep = t0 + (i + 1) / RATE - time.monotonic()
                if sleep > 0:
                    time.sleep(sleep)
            return True

        ok = go(q_start, q_target, f"Turning {args.deg:g}° {dir_name} ...")
        hold_at = q_target if ok else read_position(motor, ctrl)
        t_end = time.monotonic() + args.hold
        while time.monotonic() < t_end:
            motor.send_mit(hold_at, 0.0, args.kp, args.kd, 0.0)
            time.sleep(1 / RATE)
        q_now = read_position(motor, ctrl)
        print(f"  Reached {math.degrees(q_now):+.1f}° "
              f"(turned {math.degrees(q_now - q_start):+.1f}° from start).")

        if args.ret or not ok:
            go(q_now, q_start, "Turning back to the start ...")
            q_final = read_position(motor, ctrl)
            print(f"  Back at {math.degrees(q_final):+.1f}°.")
        print(f"Done. Look at which way it turned: if that wasn't {dir_name}, next time add --flip.")
    except KeyboardInterrupt:
        print("\nCtrl+C — switching motor 7 off.")
    except RuntimeError as e:
        print(f"\nStopped: {e}")
    finally:
        if spin.enabled:
            try:
                motor.send_vel(0.0)
            except Exception:
                pass
            enabled = True
        if enabled:
            try:
                motor.disable()
            except Exception as e:
                print(f"disable failed: {e}")
        try:
            ctrl.shutdown()
            ctrl.close()
        except Exception:
            pass
        if enabled:
            print("Motor 7 off.")


if __name__ == "__main__":
    main()
