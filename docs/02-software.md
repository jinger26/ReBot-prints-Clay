# 02 · Software: SenseCraft, MotorBridge, calibration, LeRobot, ROS 2

Pick a path:

| Path | OS | Good for |
|---|---|---|
| **SenseCraft Robotics** | Windows, macOS | No-code: calibrate → teleop → record → train (ACT) → run |
| **MotorBridge** | Linux, macOS, Windows | Motor scan, zero calibration, parameters, Python scripting |
| **LeRobot** | Ubuntu 22.04/24.04 | Imitation learning with leader/follower arms |
| **ROS 2** (Jazzy / Humble) | Ubuntu 22.04+ | Motion planning, MoveIt 2, integration |

Whatever you pick, **do the MotorBridge calibration once** after assembly.

---

## SenseCraft Robotics (no-code)

1. Download from [sensecraft.seeed.cc](https://sensecraft.seeed.cc/en/download) and sign in with a Seeed account.
2. Create a project → **Device setup**: select *reBot Arm 102 + B601 RS*, bind the serial/CAN ports, run calibration (leader zero, then follower zero), verify teleop, bind cameras.
3. **Record** demonstrations — ~10 episodes per batch, 20–30 good episodes for a first model.
4. **Train** an ACT policy (default 10,000 steps) in the cloud (uses credits) or locally (needs a compatible GPU).
5. **Run** the model (cloud or local inference).

## Python environment

Install [Miniforge](https://github.com/conda-forge/miniforge):

```bash
wget "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
bash Miniforge3-$(uname)-$(uname -m).sh
```

```bash
conda create -y -n rebot python=3.12
conda activate rebot
pip install motorbridge
```

## MotorBridge: scan & calibrate the follower

Check that motors 1–7 respond:

```bash
motorbridge-cli scan --vendor robstride --channel can0 --start-id 1 --end-id 7 --timeout-ms 300
```

Start the local gateway and open [MotorBridge Studio](https://motorbridge.github.io/motorbridge-studio/):

```bash
motorbridge-gateway --bind 127.0.0.1:9002
```

In the web UI:

1. **Scan** — all joints 1–7 should be online.
2. **Zero calibration** — put the arm in its zero pose, then one-click write zero.
3. **Initialize parameters** — select model `rebot-arm-robstride`:
   - *Read Parameters* (note the current values)
   - *Apply Default Template*
   - *Write Parameters* and confirm. **Don't cut power or unplug motors while writing.**
   - Readback should report that it matches.

> If position mode behaves strangely, the parameters were probably never written — redo step 3.

## LeRobot

```bash
mkdir ~/rebot_lerobot && cd ~/rebot_lerobot
git clone https://github.com/Seeed-Projects/lerobot.git
conda create -y -n lerobot python=3.12
conda activate lerobot
pip install -e ./lerobot
pip install lerobot-teleoperator-rebot-arm-102 lerobot-robot-seeed-b601 motorbridge
conda install ffmpeg -c conda-forge
```

**Calibrate follower** (once, arm at zero pose with gripper closed):

```bash
lerobot-calibrate --robot.type=seeed_b601_rs_follower --robot.port=can0 \
  --robot.id=follower1 --robot.can_adapter=socketcan
```

**Calibrate leader:**

```bash
sudo chmod 666 /dev/ttyUSB0
lerobot-calibrate --teleop.type=rebot_arm_102_leader --teleop.port=/dev/ttyUSB0 \
  --teleop.id=rebot_arm_102_leader
```

Calibration files live in `~/.cache/huggingface/lerobot/calibration/` — delete them to recalibrate.

**Teleoperate:**

```bash
lerobot-teleoperate \
  --robot.type=seeed_b601_rs_follower --robot.port=can0 --robot.id=follower1 --robot.can_adapter=socketcan \
  --teleop.type=rebot_arm_102_leader --teleop.port=/dev/ttyUSB0 --teleop.id=rebot_arm_102_leader
```

**Record a dataset** (2 cameras, 5 episodes):

```bash
lerobot-record --robot.type=seeed_b601_rs_follower --robot.port=can0 --robot.id=follower1 \
  --robot.can_adapter=socketcan \
  --robot.cameras="{ front: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: "MJPG"}, side: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30, fourcc: "MJPG"}}" \
  --teleop.type=rebot_arm_102_leader --teleop.port=/dev/ttyUSB0 --teleop.id=rebot_arm_102_leader \
  --display_data=true --dataset.repo_id=seeed_rebot_b601_rs/test --dataset.num_episodes=5 \
  --dataset.single_task="Grab the black cube" --dataset.push_to_hub=false \
  --dataset.episode_time_s=30 --dataset.reset_time_s=30
```

Keys while recording: **→** end episode early · **←** re-record · **Esc** stop and save.

Replay an episode:

```bash
lerobot-replay --robot.type=seeed_b601_rs_follower --robot.port=can0 --robot.can_adapter=socketcan \
  --robot.id=follower1 --dataset.repo_id=seeed_rebot_b601_rs/test --dataset.episode=0
```

For training and evaluation see the [LeRobot wiki page](https://wiki.seeedstudio.com/rebot_arm_b601_rs_lerobot/).

## ROS 2 (Jazzy, Humble also supported)

```bash
sudo apt update
sudo apt install -y python3-colcon-common-extensions python3-pip git
sudo apt install -y ros-${ROS_DISTRO}-control-msgs ros-${ROS_DISTRO}-trajectory-msgs \
  ros-${ROS_DISTRO}-tf-transformations ros-${ROS_DISTRO}-robot-state-publisher \
  ros-${ROS_DISTRO}-rviz2 ros-${ROS_DISTRO}-pinocchio

cd ~
git clone https://github.com/Seeed-Projects/reBotArmController_ROS2.git rebotarm_ros2
cd ~/rebotarm_ros2
mkdir -p third_party
git clone https://github.com/Seeed-Projects/reBotArm_control_py.git third_party/reBotArm_control_py
source /opt/ros/${ROS_DISTRO}/setup.bash
colcon build --symlink-install
source install/setup.bash
```

Bring up (add `use_rviz:=true` for RViz):

```bash
ros2 launch rebotarm_bringup bringup.launch.py model:=rs channel:=can0
```

Useful interfaces: topic `/rebotarm/joint_states`; services `/rebotarm/enable`, `/rebotarm/disable`, `/rebotarm/safe_home`; actions `/rebotarm/move_to_pose`, `/rebotarm/follow_joint_trajectory`.
Demos: `ros2 run rebotarmcontroller MoveTo` · `GravityCompensation` · `GripperControl`.
MoveIt 2 sim: `ros2 launch rebotarm_moveit_config demo.launch.py model:=rs`.

Next: [03 · Clay extruder](03-clay-extruder.md)
