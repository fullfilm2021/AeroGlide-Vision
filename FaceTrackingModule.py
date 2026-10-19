import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['GLOG_minloglevel'] = '3'

# pyrefly: ignore[missing-import]
import cv2
# pyrefly: ignore[missing-import]
import mediapipe as mp
import math

class FaceEyeDetector:
    """
    Real-time Face & Eye tracking module using MediaPipe FaceMesh.
    Calculates Eye Aspect Ratio (EAR) to detect intentional winks/blinks for mouse clicks.
    """
    def __init__(self, max_faces=1, detection_con=0.6, track_con=0.6):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=max_faces,
            refine_landmarks=False,
            min_detection_confidence=detection_con,
            min_tracking_confidence=track_con
        )
        # Landmark indices for eyes
        # Left Eye (in mirrored image): outer, inner, top, bottom
        self.LEFT_EYE = [33, 133, 159, 145]
        # Right Eye (in mirrored image): inner, outer, top, bottom
        self.RIGHT_EYE = [362, 263, 386, 374]
        self.results = None

    def process(self, img):
        if img is None or img.size == 0:
            return None
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self.results = self.face_mesh.process(img_rgb)
        return self.results

    def get_eye_status(self, img, draw=True, blink_threshold=0.18):
        """
        Calculates Eye Aspect Ratio (EAR) for both eyes.
        Returns:
            left_ear, right_ear, is_left_wink, is_right_wink, (l_cx, l_cy), (r_cx, r_cy)
        """
        if not self.results or not self.results.multi_face_landmarks:
            return 0.3, 0.3, False, False, None, None

        h, w, _ = img.shape
        face_lms = self.results.multi_face_landmarks[0].landmark

        # Left Eye Landmarks
        l_corner1 = (face_lms[self.LEFT_EYE[0]].x * w, face_lms[self.LEFT_EYE[0]].y * h)
        l_corner2 = (face_lms[self.LEFT_EYE[1]].x * w, face_lms[self.LEFT_EYE[1]].y * h)
        l_top = (face_lms[self.LEFT_EYE[2]].x * w, face_lms[self.LEFT_EYE[2]].y * h)
        l_bottom = (face_lms[self.LEFT_EYE[3]].x * w, face_lms[self.LEFT_EYE[3]].y * h)

        # Right Eye Landmarks
        r_corner1 = (face_lms[self.RIGHT_EYE[0]].x * w, face_lms[self.RIGHT_EYE[0]].y * h)
        r_corner2 = (face_lms[self.RIGHT_EYE[1]].x * w, face_lms[self.RIGHT_EYE[1]].y * h)
        r_top = (face_lms[self.RIGHT_EYE[2]].x * w, face_lms[self.RIGHT_EYE[2]].y * h)
        r_bottom = (face_lms[self.RIGHT_EYE[3]].x * w, face_lms[self.RIGHT_EYE[3]].y * h)

        # Left Eye EAR
        l_h_dist = max(1.0, math.hypot(l_corner1[0] - l_corner2[0], l_corner1[1] - l_corner2[1]))
        l_v_dist = math.hypot(l_top[0] - l_bottom[0], l_top[1] - l_bottom[1])
        left_ear = l_v_dist / l_h_dist

        # Right Eye EAR
        r_h_dist = max(1.0, math.hypot(r_corner1[0] - r_corner2[0], r_corner1[1] - r_corner2[1]))
        r_v_dist = math.hypot(r_top[0] - r_bottom[0], r_top[1] - r_bottom[1])
        right_ear = r_v_dist / r_h_dist

        l_center = (int((l_corner1[0] + l_corner2[0]) / 2), int((l_top[1] + l_bottom[1]) / 2))
        r_center = (int((r_corner1[0] + r_corner2[0]) / 2), int((r_top[1] + r_bottom[1]) / 2))

        # Intentional Wink detection (one eye closed while the other eye is open)
        # and full blink detection (both eyes closed)
        is_left_wink = (left_ear < blink_threshold and right_ear >= (blink_threshold + 0.05))
        is_right_wink = (right_ear < blink_threshold and left_ear >= (blink_threshold + 0.05))
        is_both_blink = (left_ear < blink_threshold and right_ear < blink_threshold)

        if draw and img is not None:
            # Sci-Fi Hologram Eye Rings
            # Left Eye: Green pulse on left wink, cyan when open
            l_color = (0, 255, 0) if is_left_wink else ((0, 165, 255) if is_both_blink else (255, 220, 0))
            cv2.circle(img, l_center, 12, l_color, 1, cv2.LINE_AA)
            if is_left_wink:
                cv2.circle(img, l_center, 6, (0, 255, 0), cv2.FILLED, cv2.LINE_AA)
                cv2.putText(img, "L-WINK", (l_center[0] - 25, l_center[1] - 16),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 255, 0), 1, cv2.LINE_AA)

            # Right Eye: Red pulse on right wink, cyan when open
            r_color = (0, 0, 255) if is_right_wink else ((0, 165, 255) if is_both_blink else (255, 220, 0))
            cv2.circle(img, r_center, 12, r_color, 1, cv2.LINE_AA)
            if is_right_wink:
                cv2.circle(img, r_center, 6, (0, 0, 255), cv2.FILLED, cv2.LINE_AA)
                cv2.putText(img, "R-WINK", (r_center[0] - 25, r_center[1] - 16),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 0, 255), 1, cv2.LINE_AA)

            if is_both_blink:
                cv2.circle(img, l_center, 5, (0, 165, 255), cv2.FILLED, cv2.LINE_AA)
                cv2.circle(img, r_center, 5, (0, 165, 255), cv2.FILLED, cv2.LINE_AA)

        return left_ear, right_ear, is_left_wink, is_right_wink, is_both_blink, l_center, r_center
