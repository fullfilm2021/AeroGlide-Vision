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
    Calculates 6-point Eye Aspect Ratio (EAR) with adaptive baseline tracking
    to reliably detect intentional winks and blinks for mouse clicking.
    """
    def __init__(self, max_faces=1, detection_con=0.6, track_con=0.6):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=max_faces,
            refine_landmarks=True,
            min_detection_confidence=detection_con,
            min_tracking_confidence=track_con
        )

        # Standard MediaPipe 6-point landmarks for both eyes
        # Anatomical Left Eye (User's Left Eye -> Left side on mirrored display)
        self.L_CORNERS = (362, 263)
        self.L_TOP = (386, 385, 387)
        self.L_BOTTOM = (374, 380, 373)

        # Anatomical Right Eye (User's Right Eye -> Right side on mirrored display)
        self.R_CORNERS = (33, 133)
        self.R_TOP = (159, 160, 158)
        self.R_BOTTOM = (145, 144, 153)

        self.results = None
        self.baseline_ear = 0.24
        self.calibrated = False

    def process(self, img):
        if img is None or img.size == 0:
            return None
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self.results = self.face_mesh.process(img_rgb)
        return self.results

    def _calc_ear(self, face_lms, corner_indices, top_indices, bottom_indices, w, h):
        c1 = (face_lms[corner_indices[0]].x * w, face_lms[corner_indices[0]].y * h)
        c2 = (face_lms[corner_indices[1]].x * w, face_lms[corner_indices[1]].y * h)
        h_dist = max(1.0, math.hypot(c1[0] - c2[0], c1[1] - c2[1]))

        v_dists = []
        for t_idx, b_idx in zip(top_indices, bottom_indices):
            t = (face_lms[t_idx].x * w, face_lms[t_idx].y * h)
            b = (face_lms[b_idx].x * w, face_lms[b_idx].y * h)
            v_dists.append(math.hypot(t[0] - b[0], t[1] - b[1]))

        ear = sum(v_dists) / (float(len(v_dists)) * h_dist)
        center = (int((c1[0] + c2[0]) / 2), int((c1[1] + c2[1]) / 2))
        return ear, center

    def get_eye_status(self, img, draw=True):
        """
        Calculates EAR for both eyes with adaptive baseline calibration.
        Returns:
            left_ear, right_ear, is_left_wink, is_right_wink, is_both_blink, l_center, r_center, baseline_ear
        """
        if not self.results or not self.results.multi_face_landmarks:
            return 0.25, 0.25, False, False, False, None, None, self.baseline_ear

        h, w, _ = img.shape
        face_lms = self.results.multi_face_landmarks[0].landmark

        ear_a, center_a = self._calc_ear(face_lms, self.L_CORNERS, self.L_TOP, self.L_BOTTOM, w, h)
        ear_b, center_b = self._calc_ear(face_lms, self.R_CORNERS, self.R_TOP, self.R_BOTTOM, w, h)

        # Geometrically map left-side eye to left_ear and right-side eye to right_ear
        if center_a[0] <= center_b[0]:
            left_ear, l_center = ear_a, center_a
            right_ear, r_center = ear_b, center_b
        else:
            left_ear, l_center = ear_b, center_b
            right_ear, r_center = ear_a, center_a

        # Adaptive baseline update when eyes are comfortably open and symmetric
        if abs(left_ear - right_ear) < 0.05 and left_ear > 0.16 and right_ear > 0.16:
            current_open = (left_ear + right_ear) / 2.0
            if not self.calibrated:
                self.baseline_ear = current_open
                self.calibrated = True
            else:
                self.baseline_ear = 0.96 * self.baseline_ear + 0.04 * current_open
                self.baseline_ear = max(0.18, min(0.36, self.baseline_ear))

        # Dynamic thresholds based on user's calibrated baseline
        wink_threshold = self.baseline_ear * 0.70
        open_threshold = self.baseline_ear * 0.82
        wink_ratio = 0.75

        # Detect Winks (one eye closed, the other open)
        is_left_wink = (
            (left_ear < wink_threshold or left_ear < right_ear * wink_ratio)
            and right_ear >= open_threshold
        )
        is_right_wink = (
            (right_ear < wink_threshold or right_ear < left_ear * wink_ratio)
            and left_ear >= open_threshold
        )

        # Detect Both Eyes Blink
        is_both_blink = (left_ear < wink_threshold and right_ear < wink_threshold)

        if draw and img is not None:
            # Draw Sci-Fi Eye Reticles
            l_color = (0, 255, 0) if is_left_wink else ((0, 165, 255) if is_both_blink else (255, 220, 0))
            r_color = (0, 0, 255) if is_right_wink else ((0, 165, 255) if is_both_blink else (255, 220, 0))

            # Left Eye Reticle
            cv2.circle(img, l_center, 14, l_color, 1, cv2.LINE_AA)
            if is_left_wink:
                cv2.circle(img, l_center, 8, (0, 255, 0), cv2.FILLED, cv2.LINE_AA)
                cv2.putText(img, "L-WINK CLICK", (l_center[0] - 45, l_center[1] - 18),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA)

            # Right Eye Reticle
            cv2.circle(img, r_center, 14, r_color, 1, cv2.LINE_AA)
            if is_right_wink:
                cv2.circle(img, r_center, 8, (0, 0, 255), cv2.FILLED, cv2.LINE_AA)
                cv2.putText(img, "R-WINK CLICK", (r_center[0] - 45, r_center[1] - 18),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1, cv2.LINE_AA)

            if is_both_blink:
                cv2.circle(img, l_center, 6, (0, 165, 255), cv2.FILLED, cv2.LINE_AA)
                cv2.circle(img, r_center, 6, (0, 165, 255), cv2.FILLED, cv2.LINE_AA)

        return left_ear, right_ear, is_left_wink, is_right_wink, is_both_blink, l_center, r_center, self.baseline_ear
