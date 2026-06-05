# L2CS Gaze Perception

ROS2 Humble package for real-time webcam-based gaze estimation using [L2CS-Net](https://github.com/Ahmednull/L2CS-Net) (ResNet50 backbone, pre-trained on Gaze360).

## File Structure

```
l2cs_gaze_perception/
├── src/
│   └── gaze/
│       ├── __init__.py               Package init
│       ├── gaze_node.py              Main ROS2 node (pipeline entry point)
│       └── visualization.py          Marker helpers for RViz (bbox, gaze ray)
├── config/
│   └── gaze_params.yaml              ROS2 parameter file
├── launch/
│   └── gaze_pipeline.launch.py       Launch file
├── rviz/
│   └── gaze_pipeline.rviz            Pre-configured RViz2 layout
├── models/
│   └── L2CSNet_gaze360.pkl          Pre-trained weights
├── resource/
│   └── l2cs_gaze_perception          Ament index marker
├── package.xml                       ROS2 package manifest
├── setup.cfg                         Setuptools config
└── setup.py                          Build/install script
```

## Published Topics

| Topic | Type | Description |
|---|---|---|
| `/gaze/image_raw` | `sensor_msgs/Image` | Raw camera frame |
| `/gaze/image_annotated` | `sensor_msgs/Image` | Frame with bounding boxes & gaze arrows |
| `/gaze/detections` | `vision_msgs/Detection2DArray` | Face detections with gaze as pose |
| `/gaze/markers` | `visualization_msgs/MarkerArray` | RViz visualization markers |

## Setup

### 1. Install system dependencies

```bash
sudo apt update
sudo apt install python3-pip python3-opencv
```

### 2. Install Python dependencies

```bash
pip install face_detection@git+https://github.com/elliottzheng/face-detection.git
```

Install PyTorch with CUDA (recommended):

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

If you only have CPU:

```bash
pip install torch torchvision
```

### 3. Install L2CS-Net

```bash
cp -r src/L2CS-Net/l2cs /usr/local/lib/python3.10/dist-packages/l2cs
```

Or install via pip from the local source:

```bash
pip install src/L2CS-Net/
```

### 4. Fix numpy compatibility (ROS Humble + OpenCV)

ROS Humble's `cv_bridge` requires numpy 1.x:

```bash
pip install 'numpy<2' 'opencv-python-headless<4.9'
```

### 5. Build and source

```bash
cd <your_ros2_ws>
colcon build --packages-select l2cs_gaze_perception
source install/setup.bash
```

## Usage

### Basic usage (recommended)

```bash
ros2 launch l2cs_gaze_perception gaze_pipeline.launch.py
```

This uses the model and config from the installed package automatically.

Override arguments (e.g. different camera or GPU):

```bash
ros2 launch l2cs_gaze_perception gaze_pipeline.launch.py \
    camera_id:=2 \
    device:=0
```

Use a custom model:

```bash
ros2 launch l2cs_gaze_perception gaze_pipeline.launch.py \
    model_path:=/absolute/path/to/L2CSNet_gaze360.pkl
```

Or run the node directly (node uses its own built-in default paths):

```bash
ros2 run l2cs_gaze_perception gaze_node --ros-args \
    -p camera_id:=0 \
    -p device:=0
```

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `camera_id` | `0` | Camera device index |
| `model_path` | `<package_share>/models/L2CSNet_gaze360.pkl` | Model weights path (absolute path recommended) |
| `model_arch` | `ResNet50` | Backbone architecture |
| `device` | `0` | GPU index (integer), or use `"cpu"` (`-p "device:='cpu'"`) |
| `confidence_threshold` | `0.5` | Face detection confidence |
| `max_faces` | `3` | Max faces to track |
| `publish_fps` | `30` | Target publish rate |
| `resolution_width` | `640` | Camera width |
| `resolution_height` | `480` | Camera height |

> **`device` parameter**: Pass as integer (`-p device:=0`) for CUDA GPU. For CPU, use the string form: `-p "device:='cpu'"`.

## RViz Visualization

A pre-configured RViz layout is included. Launch it after starting the node:

```bash
ros2 run rviz2 rviz2 -d $(ros2 pkg prefix l2cs_gaze_perception)/share/l2cs_gaze_perception/rviz/gaze_pipeline.rviz
```

The config sets up the following displays automatically:

| Display | Topic | Description |
|---|---|---|
| **Image** | `/gaze/image_annotated` | Annotated camera feed with bounding boxes and gaze arrows |
| **MarkerArray** | `/gaze/markers` | 3D face bounding box cubes and gaze ray arrows |
| **TF** | — | `gaze_face_{i}` transforms in `camera_optical_frame` |

All topics are configured with `BEST_EFFORT` QoS to match the node's publisher.

### What you'll see

- **Annotated image** with green bounding boxes and cyan gaze arrows overlaid
- **3D markers** (semi-transparent green cubes = face bboxes, magenta arrows = gaze rays)
- **TF axes** for each detected face (`gaze_face_0`, `gaze_face_1`, ...)
- Fixed frame is set to `camera_optical_frame`

### Manual setup (if not using the config file)

| Step | Action |
|---|---|
| 1 | Set **Global Options → Fixed Frame** to `camera_optical_frame` |
| 2 | **Add → By topic** → `/gaze/image_annotated` as **Image** display |
| 3 | **Add → By topic** → `/gaze/markers` as **MarkerArray** display |
| 4 | In the Image display → **QoS Profile → Reliability**, set to `Best Effort` |

> If the image is blank in RViz, this QoS mismatch is the most common cause.

## WSL2 Setup (USB Webcam)

WSL2 does not expose host webcams by default. Use [usbipd-win](https://github.com/dorssel/usbipd-win) to attach your USB webcam into the WSL2 kernel.

### Prerequisites

- A **USB webcam** (internal MIPI/ISP laptop cameras are not supported via usbipd)
- `usbipd-win` installed on Windows: `winget install usbipd`

### One-time setup (Windows — Admin PowerShell)

```powershell
# List USB devices and find your camera's BUSID
usbipd list

# Bind (share) the camera — only needed once
usbipd bind --busid <BUSID>
```

### Every session (before launching the node)

**Step 1 — Attach the camera into WSL (Windows Admin PowerShell):**

```powershell
usbipd attach --wsl --busid <BUSID>
```

**Step 2 — Load the UVC driver and verify the device (WSL terminal):**

```bash
sudo modprobe uvcvideo
ls -l /dev/video*          # should show /dev/video0 (and /dev/video1)
v4l2-ctl --list-devices    # confirm camera name
```

**Step 3 — Launch the node as normal:**

```bash
ros2 launch l2cs_gaze_perception gaze_pipeline.launch.py
```

### Notes

- The attach **does not persist** across WSL restarts or camera replugs — repeat Steps 1–2 each session.
- While attached to WSL, **Windows cannot use the camera** (Teams, browser, etc.). Run `usbipd detach --busid <BUSID>` to return it to Windows.
- Run `sudo modprobe uvcvideo` again if `/dev/video*` disappears after a WSL restart.

## TF Frames

Each detected face gets a transform `gaze_face_{i}` in the `camera_optical_frame` with orientation encoding the gaze direction (pitch/yaw).

## License

MIT
