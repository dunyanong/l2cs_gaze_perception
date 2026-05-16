import pathlib
import threading
import time

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from sensor_msgs.msg import Image, CameraInfo
from vision_msgs.msg import Detection2D, Detection2DArray, ObjectHypothesisWithPose
from visualization_msgs.msg import Marker, MarkerArray
from geometry_msgs.msg import Point, Pose, Quaternion, TransformStamped
from std_msgs.msg import Header
from cv_bridge import CvBridge
from tf2_ros import TransformBroadcaster
from ament_index_python.packages import get_package_share_directory

from l2cs import Pipeline, render, select_device

SHARE_DIR = pathlib.Path(get_package_share_directory('l2cs_gaze_perception'))
DEFAULT_MODEL = str(SHARE_DIR / 'models' / 'L2CSNet_gaze360.pkl')


class GazeNode(Node):
    def __init__(self):
        super().__init__('gaze_node')

        self.get_logger().info('L2CS-Net gaze pipeline node starting...')

        # --- Parameters ---
        self.declare_parameter('camera_id', 0)
        self.declare_parameter('model_path', DEFAULT_MODEL)
        self.declare_parameter('model_arch', 'ResNet50')
        self.declare_parameter('device', 0)
        self.declare_parameter('confidence_threshold', 0.5)
        self.declare_parameter('max_faces', 3)
        self.declare_parameter('publish_fps', 30)
        self.declare_parameter('resolution_width', 640)
        self.declare_parameter('resolution_height', 480)

        camera_id = self.get_parameter('camera_id').value
        model_path = pathlib.Path(self.get_parameter('model_path').value)
        model_arch = self.get_parameter('model_arch').value
        device_val = self.get_parameter('device').value
        device_str = str(device_val)
        self.conf_threshold = self.get_parameter('confidence_threshold').value
        self.max_faces = self.get_parameter('max_faces').value
        pub_fps = self.get_parameter('publish_fps').value
        width = self.get_parameter('resolution_width').value
        height = self.get_parameter('resolution_height').value

        # --- Camera ---
        self.cap = cv2.VideoCapture(camera_id)
        if not self.cap.isOpened():
            self.get_logger().fatal(f'Cannot open camera {camera_id}')
            raise RuntimeError(f'Cannot open camera {camera_id}')
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
        time.sleep(1.0)
        self.get_logger().info(f'Camera opened: {camera_id} ({width}x{height})')

        # --- L2CS Pipeline ---
        device = select_device(device_str)
        self.pipeline = Pipeline(
            weights=model_path,
            arch=model_arch,
            device=device,
            confidence_threshold=self.conf_threshold,
        )
        self.get_logger().info(f'Model loaded: {model_arch} on {device}')

        # --- Bridge ---
        self.bridge = CvBridge()

        # --- TF ---
        self.tf_broadcaster = TransformBroadcaster(self)

        # --- Publishers ---
        qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1,
        )

        self.pub_raw = self.create_publisher(Image, 'gaze/image_raw', qos)
        self.pub_annotated = self.create_publisher(Image, 'gaze/image_annotated', qos)
        self.pub_detections = self.create_publisher(Detection2DArray, 'gaze/detections', qos)
        self.pub_markers = self.create_publisher(MarkerArray, 'gaze/markers', qos)

        # --- Timer ---
        timer_period = 1.0 / pub_fps
        self.timer = self.create_timer(timer_period, self.timer_callback)
        self.frame_count = 0
        self.fps = 0.0

        self.get_logger().info('Gaze node ready')

    def timer_callback(self):
        start_time = time.time()

        success, frame = self.cap.read()
        if not success:
            self.get_logger().warn('Failed to grab frame')
            return

        # Run gaze pipeline
        results = self.pipeline.step(frame)

        # Annotate frame
        frame_annotated = render(frame.copy(), results)

        # Compute FPS
        self.frame_count += 1
        elapsed = time.time() - start_time
        self.fps = 1.0 / elapsed if elapsed > 0 else 0.0
        cv2.putText(
            frame_annotated, f'FPS: {self.fps:.1f}', (10, 20),
            cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, (0, 255, 0), 1, cv2.LINE_AA,
        )

        # Publish raw image
        stamp = self.get_clock().now().to_msg()
        raw_msg = self.bridge.cv2_to_imgmsg(frame, 'bgr8')
        raw_msg.header.stamp = stamp
        raw_msg.header.frame_id = 'camera_optical_frame'
        self.pub_raw.publish(raw_msg)

        # Publish annotated image
        anno_msg = self.bridge.cv2_to_imgmsg(frame_annotated, 'bgr8')
        anno_msg.header.stamp = stamp
        anno_msg.header.frame_id = 'camera_optical_frame'
        self.pub_annotated.publish(anno_msg)

        # Publish detections + markers + TF
        if results.pitch.shape[0] > 0:
            n_faces = min(results.pitch.shape[0], self.max_faces)
            det_array = Detection2DArray()
            det_array.header.stamp = stamp
            det_array.header.frame_id = 'camera_optical_frame'

            marker_array = MarkerArray()

            for i in range(n_faces):
                pitch = float(results.pitch[i])
                yaw = float(results.yaw[i])
                bbox = results.bboxes[i]
                score = float(results.scores[i])

                # Detection2D message
                det = Detection2D()
                det.header.stamp = stamp
                det.header.frame_id = 'camera_optical_frame'

                bbox_w = bbox[2] - bbox[0]
                bbox_h = bbox[3] - bbox[1]
                det.bbox.center.position.x = float(bbox[0] + bbox_w / 2.0)
                det.bbox.center.position.y = float(bbox[1] + bbox_h / 2.0)
                det.bbox.size_x = float(bbox_w)
                det.bbox.size_y = float(bbox_h)

                hyp = ObjectHypothesisWithPose()
                hyp.hypothesis.class_id = 'face'
                hyp.hypothesis.score = score

                # Encode gaze as pose orientation (RPY: roll=0, pitch, yaw)
                q = self.euler_to_quaternion(0.0, pitch, yaw)
                hyp.pose.pose.orientation.x = q[0]
                hyp.pose.pose.orientation.y = q[1]
                hyp.pose.pose.orientation.z = q[2]
                hyp.pose.pose.orientation.w = q[3]

                det.results.append(hyp)
                det_array.detections.append(det)

                # Marker for RViz
                marker = Marker()
                marker.header.stamp = stamp
                marker.header.frame_id = 'camera_optical_frame'
                marker.ns = 'faces'
                marker.id = i
                marker.type = Marker.CUBE
                marker.action = Marker.ADD
                marker.pose.position.x = float(bbox[0] + bbox_w / 2.0)
                marker.pose.position.y = float(bbox[1] + bbox_h / 2.0)
                marker.pose.position.z = 0.0
                marker.scale.x = float(bbox_w)
                marker.scale.y = float(bbox_h)
                marker.scale.z = 0.05
                marker.color.a = 0.4
                marker.color.g = 1.0
                marker_array.markers.append(marker)

                # Gaze ray marker (arrow)
                gaze_len = 100.0
                dx = -gaze_len * np.sin(yaw) * np.cos(pitch)
                dy = -gaze_len * np.sin(pitch)
                arrow = Marker()
                arrow.header.stamp = stamp
                arrow.header.frame_id = 'camera_optical_frame'
                arrow.ns = 'gaze_rays'
                arrow.id = i
                arrow.type = Marker.ARROW
                arrow.action = Marker.ADD
                arrow.points = [
                    Point(x=float(bbox[0] + bbox_w / 2.0), y=float(bbox[1] + bbox_h / 2.0), z=0.0),
                    Point(x=float(bbox[0] + bbox_w / 2.0 + dx), y=float(bbox[1] + bbox_h / 2.0 + dy), z=0.0),
                ]
                arrow.scale.x = 3.0
                arrow.scale.y = 5.0
                arrow.scale.z = 0.0
                arrow.color.a = 1.0
                arrow.color.r = 1.0
                arrow.color.b = 1.0
                marker_array.markers.append(arrow)

                # TF: gaze ray as a transform
                t = TransformStamped()
                t.header.stamp = stamp
                t.header.frame_id = 'camera_optical_frame'
                t.child_frame_id = f'gaze_face_{i}'
                cx = bbox[0] + bbox_w / 2.0
                cy = bbox[1] + bbox_h / 2.0
                t.transform.translation.x = float(cx)
                t.transform.translation.y = float(cy)
                t.transform.translation.z = 0.0
                t.transform.rotation.x = q[0]
                t.transform.rotation.y = q[1]
                t.transform.rotation.z = q[2]
                t.transform.rotation.w = q[3]
                self.tf_broadcaster.sendTransform(t)

            self.pub_detections.publish(det_array)
            self.pub_markers.publish(marker_array)
        else:
            self.get_logger().debug('No faces detected', throttle_duration_sec=2.0)

    def euler_to_quaternion(self, roll, pitch, yaw):
        cr = np.cos(roll * 0.5)
        sr = np.sin(roll * 0.5)
        cp = np.cos(pitch * 0.5)
        sp = np.sin(pitch * 0.5)
        cy = np.cos(yaw * 0.5)
        sy = np.sin(yaw * 0.5)
        return [
            sr * cp * cy - cr * sp * sy,
            cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy,
            cr * cp * cy + sr * sp * sy,
        ]

    def destroy_node(self):
        self.cap.release()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = GazeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
