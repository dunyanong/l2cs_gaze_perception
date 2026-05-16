import numpy as np
from visualization_msgs.msg import Marker, MarkerArray
from geometry_msgs.msg import Point
from sensor_msgs.msg import Image


def bbox_markers(
    bboxes: np.ndarray,
    frame_id: str,
    namespace: str = 'faces',
    color=(0.0, 1.0, 0.0),
    alpha: float = 0.4,
) -> MarkerArray:
    """Create RViz CUBE markers for face bounding boxes."""
    markers = MarkerArray()
    for i, bbox in enumerate(bboxes):
        x_min, y_min, x_max, y_max = bbox
        w = x_max - x_min
        h = y_max - y_min
        m = Marker()
        m.header.frame_id = frame_id
        m.ns = namespace
        m.id = i
        m.type = Marker.CUBE
        m.action = Marker.ADD
        m.pose.position.x = float(x_min + w / 2.0)
        m.pose.position.y = float(y_min + h / 2.0)
        m.pose.position.z = 0.0
        m.scale.x = float(w)
        m.scale.y = float(h)
        m.scale.z = 0.05
        m.color.a = alpha
        m.color.r = color[0]
        m.color.g = color[1]
        m.color.b = color[2]
        markers.markers.append(m)
    return markers


def gaze_ray_markers(
    bboxes: np.ndarray,
    pitches: np.ndarray,
    yaws: np.ndarray,
    frame_id: str,
    gaze_length: float = 100.0,
    namespace: str = 'gaze_rays',
) -> MarkerArray:
    """Create RViz ARROW markers for gaze direction."""
    markers = MarkerArray()
    for i in range(pitches.shape[0]):
        pitch = float(pitches[i])
        yaw = float(yaws[i])
        bbox = bboxes[i]
        cx = float(bbox[0] + (bbox[2] - bbox[0]) / 2.0)
        cy = float(bbox[1] + (bbox[3] - bbox[1]) / 2.0)
        dx = -gaze_length * np.sin(yaw) * np.cos(pitch)
        dy = -gaze_length * np.sin(pitch)

        m = Marker()
        m.header.frame_id = frame_id
        m.ns = namespace
        m.id = i
        m.type = Marker.ARROW
        m.action = Marker.ADD
        m.points = [
            Point(x=cx, y=cy, z=0.0),
            Point(x=cx + dx, y=cy + dy, z=0.0),
        ]
        m.scale.x = 3.0
        m.scale.y = 5.0
        m.scale.z = 0.0
        m.color.a = 1.0
        m.color.r = 1.0
        m.color.b = 1.0
        markers.markers.append(m)
    return markers
