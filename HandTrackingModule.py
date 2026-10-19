import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['GLOG_minloglevel'] = '3'

# pyrefly: ignore[missing-import]
import cv2
# pyrefly: ignore[missing-import]
import mediapipe as mp
import math

class HandDetector:
    def __init__(self, mode=False, max_hands=1, detection_con=0.7, track_con=0.7):
        self.mode = mode
        self.max_hands = max_hands
        self.detection_con = detection_con
        self.track_con = track_con

        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=self.mode,
            max_num_hands=self.max_hands,
            min_detection_confidence=self.detection_con,
            min_tracking_confidence=self.track_con
        )
        self.mp_draw = mp.solutions.drawing_utils
        self.tip_ids = [4, 8, 12, 16, 20]
        self.results = None
        self.lm_list = []

    def find_hands(self, img, draw=True):
        if img is None or img.size == 0:
            return img

        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self.results = self.hands.process(img_rgb)

        if self.results and self.results.multi_hand_landmarks:
            for hand_lms in self.results.multi_hand_landmarks:
                if draw:
                    # Cyberpunk Neon Styling for Hand Skeleton
                    self.mp_draw.draw_landmarks(
                        img, hand_lms, self.mp_hands.HAND_CONNECTIONS,
                        self.mp_draw.DrawingSpec(color=(255, 220, 0), thickness=2, circle_radius=3),
                        self.mp_draw.DrawingSpec(color=(0, 255, 255), thickness=2, circle_radius=2)
                    )
        return img

    def find_position(self, img, hand_no=0, draw=True):
        self.lm_list = []
        if img is None or img.size == 0:
            return self.lm_list

        if self.results and self.results.multi_hand_landmarks:
            if hand_no < len(self.results.multi_hand_landmarks):
                my_hand = self.results.multi_hand_landmarks[hand_no]
                h, w, c = img.shape
                for id, lm in enumerate(my_hand.landmark):
                    # Keep float precision for sub-pixel accuracy and jitter reduction
                    cx, cy = float(lm.x * w), float(lm.y * h)
                    self.lm_list.append([id, cx, cy])
                    if draw and id in self.tip_ids:
                        cv2.circle(img, (int(cx), int(cy)), 6, (255, 0, 200), cv2.FILLED)
        return self.lm_list

    def fingers_up(self):
        fingers = []
        if len(self.lm_list) < 21:
            return [0, 0, 0, 0, 0]

        # Thumb: compare distance between thumb tip (4) and pinky base (17) vs thumb joint (3) and pinky base (17)
        d_tip = math.hypot(self.lm_list[4][1] - self.lm_list[17][1], self.lm_list[4][2] - self.lm_list[17][2])
        d_joint = math.hypot(self.lm_list[3][1] - self.lm_list[17][1], self.lm_list[3][2] - self.lm_list[17][2])
        if d_tip > d_joint:
            fingers.append(1)
        else:
            fingers.append(0)

        # 4 Fingers (Index: 8, Middle: 12, Ring: 16, Pinky: 20)
        for id in range(1, 5):
            if self.lm_list[self.tip_ids[id]][2] < self.lm_list[self.tip_ids[id] - 2][2]:
                fingers.append(1)
            else:
                fingers.append(0)

        return fingers

    def find_distance(self, p1, p2, img=None, draw=True, r=8, t=3):
        if len(self.lm_list) <= max(p1, p2):
            return 9999.0, img, [0, 0, 0, 0, 0, 0]

        x1, y1 = self.lm_list[p1][1], self.lm_list[p1][2]
        x2, y2 = self.lm_list[p2][1], self.lm_list[p2][2]
        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0

        length = math.hypot(x2 - x1, y2 - y1)

        if draw and img is not None:
            cv2.line(img, (int(x1), int(y1)), (int(x2), int(y2)), (255, 0, 255), t)
            cv2.circle(img, (int(x1), int(y1)), r, (255, 0, 255), cv2.FILLED)
            cv2.circle(img, (int(x2), int(y2)), r, (255, 0, 255), cv2.FILLED)
            cv2.circle(img, (int(cx), int(cy)), r, (0, 0, 255), cv2.FILLED)

        return length, img, [x1, y1, x2, y2, cx, cy]
