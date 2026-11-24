#!/usr/bin/env python3
"""
ReBot prints Clay — circle path test for the reBot Arm B601-RS.

Traces a small horizontal circle in the air at constant height, constant
speed and fixed tool orientation. This is the first "printing-style" motion
test: if the arm can follow this smoothly, it can follow a spiral-vase path.

Safety design
-------------
* The circle STARTS AND ENDS AT THE ARM'S CURRENT POSITION, so there is no
  sudden approach move. Jog the arm (e.g. with teleop) to where you want the
  circle first, with room around it.
* Orientation is held constant, so the nozzle tip (wherever it is on the
  tool) traces the same circle as the SDK's end-effector frame.
* The whole joint path is computed and checked (IK error, joint limits,
  joint speed) BEFORE the motors are enabled.
* Motors are enabled holding their current position (no jump to zero).
* Speed ramps up and down smoothly.
* Ctrl+C at any time: the arm freezes where it is, then slowly returns home.

Requirements
------------
* conda env `rebot` with: motorbridge, pin (Pinocchio), numpy, pyyaml
* Seeed's SDK cloned locally:
    git clone https://github.com/Seeed-Projects/reBotArm_control_py.git ~/rebot/reBotArm_control_py
* SenseCraft Robotics and any other program using the CAN adapter CLOSED.

Usage
-----
    # 1) Plan only, no hardware — checks the math from a typical pose:
    python circle_test.py --dry-run

    # 2) Watch live joint angles while you move the arm by hand (motors off):
    python circle_test.py --read

    # 3) Real run (asks for confirmation before moving):
    python circle_test.py --radius 0.025 --speed 0.015 --loops 2
"""

from __future__ import annotations

import argparse
import math
import signal
import sys
import time
from pathlib import Path

import numpy as np

# ── CLI ─────────────────────────────────────────────────────────────────────

ap = argparse.ArgumentParser(description="reBot B601-RS circle path test")
ap.add_argument("--sdk", default=str(Path.home() / "rebot" / "reBotArm_control_py"),
                help="path to the cloned reBotArm_control_py repo")
ap.add_argument("--radius", type=float, default=0.025, help="circle radius in m (default 0.025 = 5 cm diameter)")
ap.add_argument("--speed", type=float, default=0.015, help="tool speed in m/s (default 0.015 = 15 mm/s)")
ap.add_argument("--loops", type=float, default=2.0, help="number of laps (default 2)")
ap.add_argument("--direction", choices=["ccw", "cw"], default="ccw")
ap.add_argument("--ramp", type=float, default=1.0, help="speed ramp-up/down time in s")
ap.add_argument("--dt", type=float, default=0.01, help="waypoint period in s (default 0.01 = 100 Hz)")
ap.add_argument("--max-joint-speed", type=float, default=1.0, help="abort if any joint would exceed this (rad/s)")
ap.add_argument("--dry-run", action="store_true", help="plan from a typical pose, never touch hardware")
ap.add_argument("--dry-q", type=float, nargs=6, default=[0.0, 0.8, 0.8, 0.0, 0.0, 0.0],
                help="joint angles (rad) used as the start pose in --dry-run")
ap.add_argument("--read", action="store_true",
                help="just print live joint angles (motors stay off) — use while moving the arm by hand")
ap.add_argument("--plot",action="store_true", help="save a plot of the planned path (needs matplotlib)")
ap.add_argument("--yes", action="store_true", help="skip the GO confirmation (not recommended)")
args = ap.parse_args()

sdk = Path(args.sdk).expanduser()
if not (sdk / "reBotArm_control_py").is_dir():
    sys.exit(f"SDK not found at {sdk}. Clone it first (see the header of this file) or pass --sdk.")
sys.path.insert(0, str(sdk))

import pinocchio as pin  # noqa: E402
from reBotArm_control_py.kinematics import (  # noqa: E402
    load_robot_model, get_end_effector_frame_id, compute_fk, pad_q_for_model,
)
from reBotArm_control_py.kinematics.inverse_kinematics import solve_ik, IKParams  # noqa: E402

N_ARM = 6

# ── Path planning ───────────────────────────────────────────────────────────


def arc_length_profile(total_len: float, v: float, t_ramp: float, dt: float) -> np.ndarray:
    """Distance along the path at each tick: smooth ramp up, cruise, smooth ramp down.

    Uses a cosine-shaped acceleration (velocity follows a smooth S-curve), so
    the arm never sees a step in velocity.
    """
    t_ramp = max(t_ramp, dt)
    d_ramp = v * t_ramp / 2.0  # distance covered during one ramp
    if 2 * d_ramp > total_len:  # path too short to reach cruise speed
        t_ramp = total_len / v
        d_ramp = total_len / 2.0
    t_cruise = (total_len - 2 * d_ramp) / v
    t_total = 2 * t_ramp + t_cruise
    t = np.arange(0.0, t_total + dt, dt)

    def ramp_dist(tau):  # distance at time tau into a ramp-up
        return v * (tau / 2.0 - (t_ramp / (2 * math.pi)) * np.sin(math.pi * tau / t_ramp))

    s = np.empty_like(t)
    for i, ti in enumerate(t):
        if ti < t_ramp:
            s[i] = ramp_dist(ti)
        elif ti < t_ramp + t_cruise:
            s[i] = d_ramp + v * (ti - t_ramp)
        else:
            tr = min(t_total - ti, t_ramp)
            s[i] = total_len - ramp_dist(tr)
    s[-1] = total_len
    return np.clip(s, 0.0, total_len)


def plan(q_start: np.ndarray):
    """Return (joint_path [N,6], xyz_path [N,3], report dict) for the circle."""
    model = load_robot_model()
    data = model.createData()
    fid = get_end_effector_frame_id(model)

    q_full = pad_q_for_model(model, q_start[:N_ARM], N_ARM)
    p0, R0, _ = compute_fk(model, q_full)
    p0 = np.asarray(p0, dtype=float)
    R0 = np.asarray(R0, dtype=float)

    r = args.radius
    sign = 1.0 if args.direction == "ccw" else -1.0
    # Circle in the horizontal (world XY) plane that passes through p0:
    # centre is r metres "behind" p0 along -X, we start at angle 0.
    centre = p0 - np.array([r, 0.0, 0.0])
    total_len = 2 * math.pi * r * args.loops
    s = arc_length_profile(total_len, args.speed, args.ramp, args.dt)
    theta = sign * s / r
    xyz = np.stack([centre[0] + r * np.cos(theta),
                    centre[1] + r * np.sin(theta),
                    np.full_like(theta, p0[2])], axis=1)

    ik_params = IKParams(max_iter=200, tolerance=1e-5, step_size=0.8, damping=1e-6)
    # The solver aims for 1e-5 but we accept anything under IK_ACCEPT
    # (pose error norm; 1e-4 ≈ 0.1 mm / 0.006°) — far finer than a clay bead.
    IK_ACCEPT = 1e-4
    q_prev = q_start[:N_ARM].astype(float).copy()
    path = np.zeros((len(xyz), N_ARM))
    worst_err = 0.0
    for i, p in enumerate(xyz):
        target = pin.SE3(R0, p)
        res = solve_ik(model, data, fid, target, q_prev, ik_params, controlled_joints=N_ARM)
        worst_err = max(worst_err, res.error)
        if res.error > IK_ACCEPT:
            raise RuntimeError(f"IK failed at waypoint {i}/{len(xyz)} (err={res.error:.2e}, "
                               f"limit {IK_ACCEPT:.0e}). "
                               "Try a smaller radius or start from a different pose.")
        path[i] = res.q[:N_ARM]
        q_prev = path[i]

    # Checks
    lo = model.lowerPositionLimit[:N_ARM]
    hi = model.upperPositionLimit[:N_ARM]
    margin = 0.05
    if np.any(path < lo + margin) or np.any(path > hi - margin):
        bad = np.where((path < lo + margin) | (path > hi - margin))[1]
        raise RuntimeError(f"Path comes within {margin} rad of a joint limit on joint(s) "
                           f"{sorted(set(int(b) + 1 for b in bad))}.")
    jvel = np.abs(np.diff(path, axis=0)) / args.dt
    max_jvel = jvel.max(axis=0)
    if np.any(max_jvel > args.max_joint_speed):
        j = int(np.argmax(max_jvel)) + 1
        raise RuntimeError(f"Joint {j} would move at {max_jvel.max():.2f} rad/s "
                           f"(limit {args.max_joint_speed}). Lower --speed or change pose.")
    jump = np.abs(path[0] - q_start[:N_ARM]).max()
    if jump > 0.02:
        raise RuntimeError(f"First waypoint is {jump:.3f} rad from the current pose — refusing to jump.")

    report = dict(
        start_xyz=p0, centre=centre, points=len(xyz), duration=len(xyz) * args.dt,
        worst_ik_err=worst_err, max_joint_speed=max_jvel,
    )
    return path, xyz, report


def print_report(rep):
    x, y, z = rep["start_xyz"]
    print("\n── Planned circle ─────────────────────────────")
    print(f"  start / end point : x={x:+.3f}  y={y:+.3f}  z={z:+.3f} m (current pose)")
    print(f"  diameter          : {2 * args.radius * 1000:.0f} mm, {args.loops:g} lap(s), {args.direction}")
    print(f"  tool speed        : {args.speed * 1000:.0f} mm/s, ramp {args.ramp:.1f} s")
    print(f"  duration          : {rep['duration']:.1f} s ({rep['points']} waypoints @ {1 / args.dt:.0f} Hz)")
    print(f"  worst IK error    : {rep['worst_ik_err']:.1e}")
    print("  peak joint speeds : " + "  ".join(f"J{i + 1}={v:.2f}" for i, v in enumerate(rep["max_joint_speed"])) + " rad/s")
    print("───────────────────────────────────────────────\n")


def save_plot(xyz):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed, skipping plot")
        return
    fig = plt.figure(figsize=(5, 5))
    ax = fig.add_subplot(projection="3d")
    ax.plot(xyz[:, 0], xyz[:, 1], xyz[:, 2])
    ax.scatter(*xyz[0], color="red", label="start/end")
    ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)"); ax.set_zlabel("z (m)")
    ax.legend()
    out = Path("circle_test_plan.png").resolve()
    fig.savefig(out, dpi=120)
    print(f"Plot saved to {out}")


# ── Hardware run ────────────────────────────────────────────────────────────


def read_joints_once(arm, attempts: int = 30) -> tuple[np.ndarray, list[str]]:
    """Request feedback from every motor and wait until each one has answered.

    The SDK's get_state() fills a 0.0 for any motor whose reply has not been
    received yet, which silently looks like "joint at zero". Here we keep
    polling until every motor has reported, and return the names of any that
    never did.
    """
    names = [jc.name for jc in arm._all_joints]
    motors = [arm._motor_map[n] for n in names]
    ctrls = list(arm._ctrl_map.values())
    states = [None] * len(motors)
    for _ in range(attempts):
        for m, st in zip(motors, states):
            if st is None:
                try:
                    m.request_feedback()
                except Exception:
                    pass
        time.sleep(0.01)
        for c in ctrls:
            for _ in range(len(motors) * 2):
                try:
                    c.poll_feedback_once()
                except Exception:
                    pass
        states = [m.get_state() for m in motors]
        if all(s is not None for s in states):
            break
    q = np.array([s.pos if s is not None else np.nan for s in states], dtype=float)
    # Switched-off RobStride motors don't answer status requests, but they do
    # answer parameter reads: fall back to the mechPos parameter (0x7019, rad).
    for i, m in enumerate(motors):
        if states[i] is None:
            try:
                q[i] = float(m.robstride_get_param_f32(0x7019, 300))
            except Exception:
                pass
    missing = [n for n, v in zip(names, q) if np.isnan(v)]
    return q, missing


def read_pose(arm) -> np.ndarray:
    q, missing = read_joints_once(arm)
    if missing:
        raise RuntimeError(f"No feedback from: {', '.join(missing)}. "
                           "Check 48 V power, the CAN cable to the arm, and that SenseCraft "
                           "and motorbridge-gateway are closed.")
    # average a few more reads to reject noise
    qs = [q] + [read_joints_once(arm)[0] for _ in range(4)]
    return np.nanmedian(np.array(qs), axis=0)


def check_start_pose(q: np.ndarray) -> None:
    model = load_robot_model()
    lo = model.lowerPositionLimit[:N_ARM]
    hi = model.upperPositionLimit[:N_ARM]
    near = [i + 1 for i in range(N_ARM) if q[i] < lo[i] + 0.1 or q[i] > hi[i] - 0.1]
    if near:
        raise RuntimeError(
            f"Joint(s) {near} are at/near their end stop (the folded home pose?). "
            "Move the arm by hand so the wrist is out in front and raised, e.g. "
            "J2≈0.8, J3≈0.8 rad, then run again. Use --read to watch the joint values.")


def read_live():
    from reBotArm_control_py.actuator import RebotArm
    arm = RebotArm()
    print(f"Connecting on '{arm._channel}' ... reading joints, motors stay OFF. Ctrl+C to quit.")
    arm.connect()
    try:
        while True:
            q, missing = read_joints_once(arm)
            line = "  ".join(f"J{i + 1}={q[i]:+.3f}" for i in range(N_ARM))
            if len(q) > N_ARM:
                line += f"  J7={q[N_ARM]:+.3f}"
            if missing:
                line += f"   NO FEEDBACK: {', '.join(missing)}"
            print("\r" + line + " " * 10, end="", flush=True)
            time.sleep(0.2)
    except KeyboardInterrupt:
        print()
    finally:
        arm.disconnect()


def run_hardware():
    from reBotArm_control_py.actuator import RebotArm
    from reBotArm_control_py.controllers import RebotArmEndPose

    arm = RebotArm()
    print(f"Connecting on '{arm._channel}' ...")
    arm.connect()
    try:
        q0 = read_pose(arm)
        print("Current joints (rad): " + " ".join(f"{v:+.3f}" for v in q0[:N_ARM]))
        check_start_pose(q0)
        path, xyz, rep = plan(q0)
    except RuntimeError as e:
        arm.disconnect()
        sys.exit(f"\nPlan rejected, nothing moved:\n  {e}")
    print_report(rep)
    if args.plot:
        save_plot(xyz)

    if not args.yes:
        print("Check: clear space around the arm, hand near the 48 V power switch.")
        if input("Type GO to enable motors and run the circle: ").strip() != "GO":
            arm.disconnect()
            print("Cancelled, nothing moved.")
            return

    ctrl = RebotArmEndPose(arm)
    # Hold the CURRENT pose when motors enable (the SDK default target is all-zeros = home).
    ctrl._q_target = q0[:N_ARM].copy()
    ctrl._qd_target = np.zeros(N_ARM)
    if arm.has_gripper:
        ctrl._gripper_target = float(q0[N_ARM])

    stop = {"flag": False}

    def on_sigint(*_):
        stop["flag"] = True
        print("\nCtrl+C — stopping ...")

    signal.signal(signal.SIGINT, on_sigint)

    ctrl.start()
    try:
        time.sleep(1.0)  # let the motors settle holding position
        print("Running circle ... (Ctrl+C to stop)")
        qd = np.vstack([np.diff(path, axis=0) / args.dt, np.zeros((1, N_ARM))])
        t0 = time.monotonic()
        for i in range(len(path)):
            if stop["flag"]:
                q_now, _, _ = arm.get_state()
                ctrl._qd_target[:] = 0.0
                ctrl._q_target[:] = q_now[:N_ARM]
                break
            ctrl._q_target[:] = path[i]
            ctrl._qd_target[:] = qd[i]
            sleep = t0 + (i + 1) * args.dt - time.monotonic()
            if sleep > 0:
                time.sleep(sleep)
        ctrl._qd_target[:] = 0.0
        time.sleep(1.0)

        q_end, _, _ = arm.get_state()
        model = load_robot_model()
        p_end, _, _ = compute_fk(model, pad_q_for_model(model, q_end[:N_ARM], N_ARM))
        err_mm = np.linalg.norm(np.asarray(p_end) - rep["start_xyz"]) * 1000
        print(f"Done. Final position is {err_mm:.1f} mm from the start point.")
    finally:
        print("Returning slowly to home pose, then disabling motors ...")
        ctrl.end()
        print("Motors disabled.")


# ── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if args.read:
        read_live()
    elif args.dry_run:
        print("DRY RUN — no hardware.")
        try:
            path, xyz, rep = plan(np.array(args.dry_q, dtype=float))
        except RuntimeError as e:
            sys.exit(f"Plan rejected: {e}")
        print_report(rep)
        if args.plot:
            save_plot(xyz)
    else:
        run_hardware()
