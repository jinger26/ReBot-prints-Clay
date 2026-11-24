# 04 · Troubleshooting

| Problem | Fix |
|---|---|
| Motors don't show up in scan | Check 48 V power is on, DIP switch at **120R**, CAN H/L not swapped (red → H, black → L), `can0` is up at 1 Mbps. |
| `can0` doesn't exist (Linux) | PEAK driver built with plain `make`. Rebuild with `make netdev`, then `sudo modprobe pcan`. |
| USB-CAN adapter not recognised | Wrong firmware. Flash `USB2CAN` (switch to BOOT, flash, back to 120R). |
| macOS: `load PCBUSB failed` | Create the symlink: `sudo ln -sf /usr/local/lib/libPCBUSB.dylib /usr/local/lib/PCBUSB`. |
| Leader arm port missing / `/dev/ttyACM0` vanishes | `brltty` grabbed it: `sudo apt remove brltty`. Check with `ls /dev/ttyUSB*` and `sudo dmesg \| grep ttyUSB`. |
| Low frame rate teleop on macOS | Outdated WCH CH34x driver installed. Remove it and use the built-in Apple driver. |
| Position mode acts oddly | Motor parameters never written. Run *Write Parameters* in MotorBridge Studio. |
| Camera index changes after reboot | Re-run `lerobot-find-cameras opencv`. |
| Keys don't work during `lerobot-record` (Linux) | Set `$DISPLAY`, or `pip install pynput==1.6.8`. |
| ffmpeg "No valid stream found" | `conda install ffmpeg=7.1.1 -c conda-forge`. |
| PyTorch not using GPU | `python -c "import torch; print(torch.cuda.is_available())"`. RTX 50-series needs the cu128 nightly build. |
| ROS 2: "start point deviates" | Reset the start state and replan. Don't just raise the timeout. |

Still stuck? [Seeed Discord](https://discord.com/invite/QqMgVwHT3X) · [Seeed forum](https://forum.seeedstudio.com/) · [ROS 2 issues](https://github.com/Seeed-Projects/reBotArmController_ROS2/issues)
