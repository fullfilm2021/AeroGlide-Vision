# pyrefly: ignore[missing-import]
import cv2
import numpy as np
import time
import ctypes
import pyautogui
import math
from HandTrackingModule import HandDetector

# Set Windows DPI Awareness so full resolution is tracked accurately
try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

# Prevent PyAutoGUI from crashing when mouse hits screen corners
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.001

def set_mouse_pos(x, y):
    """Direct hardware cursor movement via Windows API"""
    try:
        ctypes.windll.user32.SetCursorPos(int(x), int(y))
    except Exception:
        pyautogui.moveTo(x, y)

class AdaptiveCursorFilter:
    """
    Adaptive Smoothing Filter with Deadzone:
    - Deadzone eliminates micro-tremors and webcam sensor noise when holding hand still.
    - Dynamic alpha adapts to movement speed: slow moves are buttery smooth, fast swipes have zero lag.
    """
    def __init__(self, deadzone=3.5, base_smooth=0.20):
        self.curr_x = None
        self.curr_y = None
        self.deadzone = deadzone
        self.base_smooth = base_smooth

    def update(self, target_x, target_y):
        if self.curr_x is None:
            self.curr_x = float(target_x)
            self.curr_y = float(target_y)
            return self.curr_x, self.curr_y

        dx = float(target_x) - self.curr_x
        dy = float(target_y) - self.curr_y
        dist = math.hypot(dx, dy)

        # 1. Deadzone: ignore micro-tremors
        if dist < self.deadzone:
            return self.curr_x, self.curr_y

        # 2. Dynamic speed-based smoothing factor
        speed_factor = min(max((dist - self.deadzone) / 45.0, 0.0), 1.0)
        alpha = self.base_smooth + (0.75 - self.base_smooth) * speed_factor

        self.curr_x += alpha * dx
        self.curr_y += alpha * dy
        return self.curr_x, self.curr_y

    def reset(self):
        self.curr_x = None
        self.curr_y = None

def get_laptop_camera_index():
    """Automatically detect laptop's built-in Integrated Camera"""
    try:
        # pyrefly: ignore[missing-import]
        from pygrabber.dshow_graph import FilterGraph
        devices = FilterGraph().get_input_devices()
        print("\nScanning connected cameras:")
        for idx, dev_name in enumerate(devices):
            safe_name = str(dev_name).encode('ascii', 'replace').decode('ascii')
            print(f"  [{idx}] {safe_name}")
            
        # 1. Look for 'Integrated Camera' or 'Internal'
        for idx, dev_name in enumerate(devices):
            lower = str(dev_name).lower()
            if "integrated" in lower or "internal" in lower or "built-in" in lower:
                print(f">> Selected Laptop Default Camera: [{idx}]\n")
                return idx
                
        # 2. Otherwise pick the first non-virtual camera
        for idx, dev_name in enumerate(devices):
            lower = str(dev_name).lower()
            if not any(v in lower for v in ["iriun", "obs", "virtual", "droid"]):
                print(f">> Selected Camera: [{idx}]\n")
                return idx
    except Exception as e:
        print(f"Camera auto-detection note: {e}")

    # Fallback to Index 1 (Integrated Camera on this laptop)
    return 1

def main():
    # Camera Dimensions
    w_cam, h_cam = 640, 480
    
    # Screen Dimensions
    try:
        user32 = ctypes.windll.user32
        w_screen = user32.GetSystemMetrics(0)
        h_screen = user32.GetSystemMetrics(1)
    except Exception:
        w_screen, h_screen = pyautogui.size()
    
    # Active Interaction Box
    margin_x = 150
    margin_top = 70
    margin_bottom = 150

    # Adaptive Filter
    cursor_filter = AdaptiveCursorFilter(deadzone=3.5, base_smooth=0.20)

    # State Machine Constants
    STATE_IDLE = "IDLE"
    STATE_CURSOR = "CURSOR"
    STATE_PINCH_DOWN = "PINCH"
    STATE_DRAGGING = "DRAG"
    STATE_SCROLLING = "SCROLL"

    # Click Hysteresis Latch (Instant on touch, resets on open)
    click_pressed = False
    rc_pressed = False
    scroll_anchor_y = None
    prev_time = time.time()

    # Fist Clench Screen Lock state
    fist_start_time = None
    last_lock_time = 0.0
    FIST_HOLD_DURATION = 0.55       # Hold fist for 0.55s to lock workstation
    LOCK_COOLDOWN = 3.0             # Seconds between lock triggers

    # Gesture Thresholds
    CLICK_THRESHOLD = 30           # Instant click when fingers touch (< 30px)
    CLICK_RESET_THRESHOLD = 38     # Release distance to unlock next click (> 38px)
    RIGHT_CLICK_THRESHOLD = 32     # Thumb + Middle touch with Middle extended
    RIGHT_CLICK_RESET = 40         # Release distance to unlock next right click
    SCROLL_DEADZONE = 6            # Vertical movement needed to trigger scroll

    # Auto-select laptop default webcam
    cam_index = get_laptop_camera_index()
    cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"Camera {cam_index} not opened. Trying default camera (0)...")
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        cam_index = 0

    cap.set(3, w_cam)
    cap.set(4, h_cam)

    detector = HandDetector(max_hands=1, detection_con=0.7, track_con=0.7)

    print("=" * 65)
    print("AeroGlide-Vision: AI Hand Gesture Virtual Mouse")
    print("-----------------------------------------------------------------")
    print(f"Screen Resolution: {w_screen} x {h_screen}")
    print("1. Index finger up only             -> Move Cursor")
    print("2. Thumb + Index pinch              -> Left Click (Instant)")
    print("3. Index + Middle fingers up        -> Scroll (Hand Up = UP, Down = DOWN)")
    print("4. Thumb + Middle pinch (Middle UP) -> Right Click")
    print("5. Fist Clench (hold 0.5s)          -> Lock Screen (Win + L)")
    print("6. '+' or '-' on keyboard           -> Adjust Sensitivity")
    print("7. '[' or ']' on keyboard           -> Adjust Smoothness")
    print("8. 'c' on keyboard                  -> Switch Camera")
    print("9. 'q' on keyboard                  -> Exit")
    print("=" * 65)

    while True:
        try:
            success, img = cap.read()
            if not success or img is None or img.size == 0:
                print("Failed to capture video from camera. Retrying...")
                time.sleep(0.5)
                continue

            # 1. Flip image horizontally for natural mirroring
            img = cv2.flip(img, 1)

            # 2. Find Hand Landmarks
            img = detector.find_hands(img, draw=True)
            lm_list = detector.find_position(img, draw=False)

            mode_text = "Idle"
            mode_color = (200, 200, 200)

            # Active boundary box coordinates
            box_x1 = margin_x
            box_x2 = max(w_cam - margin_x, box_x1 + 60)
            box_y1 = margin_top
            box_y2 = max(h_cam - margin_bottom, box_y1 + 60)

            # Draw Active Interaction Box (Neon Green Border)
            cv2.rectangle(img, (box_x1, box_y1), (box_x2, box_y2), (0, 255, 128), 2)
            cv2.putText(
                img, 
                "Full Screen Area", 
                (box_x1 + 10, box_y1 + 25), 
                cv2.FONT_HERSHEY_SIMPLEX, 
                0.6, 
                (0, 255, 128), 
                1
            )

            now = time.time()

            if len(lm_list) >= 21:
                x1, y1 = lm_list[8][1], lm_list[8][2]    # Index tip
                x2, y2 = lm_list[12][1], lm_list[12][2]  # Middle tip
                x0, y0 = lm_list[4][1], lm_list[4][2]    # Thumb tip

                fingers = detector.fingers_up()

                # Distances
                pinch_dist, img, line_pinch = detector.find_distance(4, 8, img, draw=False)
                rc_dist, img, line_rc = detector.find_distance(4, 12, img, draw=False)

                # Intent classification
                is_fist = (fingers == [0, 0, 0, 0, 0])
                is_left_touch = not is_fist and (pinch_dist < CLICK_THRESHOLD)
                
                # Right click requires middle finger to be UP/EXTENDED (fingers[2] == 1)
                is_right_touch = (
                    not is_fist
                    and not is_left_touch 
                    and fingers[2] == 1 
                    and rc_dist < RIGHT_CLICK_THRESHOLD
                )

                # Reset click latches when fingers separate
                if pinch_dist > CLICK_RESET_THRESHOLD:
                    click_pressed = False
                if rc_dist > RIGHT_CLICK_RESET or fingers[2] == 0:
                    rc_pressed = False

                # Scroll: Index and Middle UP, fingers open
                is_scroll = (
                    not is_fist
                    and not is_left_touch 
                    and not is_right_touch 
                    and fingers[1] == 1 
                    and fingers[2] == 1 
                    and pinch_dist > CLICK_RESET_THRESHOLD
                )

                # Cursor Move: Only Index finger is UP
                is_cursor_only = (
                    not is_fist
                    and not is_left_touch 
                    and not is_right_touch 
                    and fingers[1] == 1 
                    and fingers[2] == 0
                )

                # -------------------------------------------------------------
                # 0. FIST CLENCH: Lock Screen (Win + L) when held for 0.5s
                # -------------------------------------------------------------
                if is_fist:
                    scroll_anchor_y = None
                    if fist_start_time is None:
                        fist_start_time = now

                    elapsed_fist = now - fist_start_time
                    remaining = max(0.0, FIST_HOLD_DURATION - elapsed_fist)

                    # Red Iron Man targeting circle in center of palm
                    palm_cx = int(lm_list[9][1])
                    palm_cy = int(lm_list[9][2])
                    cv2.circle(img, (palm_cx, palm_cy), 28, (0, 0, 255), 3)
                    cv2.circle(img, (palm_cx, palm_cy), 8, (0, 0, 255), cv2.FILLED)

                    mode_text = f"LOCKING IN {remaining:.1f}s"
                    mode_color = (0, 0, 255)

                    if elapsed_fist >= FIST_HOLD_DURATION and (now - last_lock_time > LOCK_COOLDOWN):
                        mode_text = "SCREEN LOCKED!"
                        try:
                            ctypes.windll.user32.LockWorkStation()
                        except Exception as lock_err:
                            print(f"LockWorkStation error: {lock_err}")
                        last_lock_time = now
                        fist_start_time = None
                else:
                    fist_start_time = None

                # -------------------------------------------------------------
                # 1. LEFT CLICK: Thumb + Index touch (Instant click, smooth latch)
                # -------------------------------------------------------------
                if is_fist:
                    pass
                elif is_left_touch:
                    scroll_anchor_y = None
                    cv2.circle(img, (int(line_pinch[4]), int(line_pinch[5])), 14, (0, 255, 0), cv2.FILLED)
                    if not click_pressed:
                        pyautogui.click()
                        click_pressed = True
                        mode_text = "Left Click!"
                        mode_color = (0, 255, 0)
                    else:
                        mode_text = "Holding..."
                        mode_color = (0, 200, 100)

                # -------------------------------------------------------------
                # 2. RIGHT CLICK: Thumb + Middle touch (With Middle finger extended)
                # -------------------------------------------------------------
                elif is_right_touch:
                    scroll_anchor_y = None
                    cv2.circle(img, (int(line_rc[4]), int(line_rc[5])), 12, (0, 0, 255), cv2.FILLED)
                    if not rc_pressed:
                        pyautogui.rightClick()
                        rc_pressed = True
                        mode_text = "Right Click!"
                        mode_color = (0, 0, 255)
                    else:
                        mode_text = "Holding..."
                        mode_color = (0, 0, 180)

                # -------------------------------------------------------------
                # 4. SCROLLING (Index + Middle fingers straight UP)
                # -------------------------------------------------------------
                elif is_scroll:
                    mode_text = "Scrolling Mode"
                    mode_color = (255, 255, 0)
                    cv2.circle(img, (int(x1), int(y1)), 8, (255, 255, 0), cv2.FILLED)
                    cv2.circle(img, (int(x2), int(y2)), 8, (255, 255, 0), cv2.FILLED)

                    if scroll_anchor_y is None:
                        scroll_anchor_y = y1
                        state = STATE_SCROLLING
                    else:
                        delta_y = y1 - scroll_anchor_y
                        if abs(delta_y) > SCROLL_DEADZONE:
                            scroll_amount = int(-delta_y * 12)
                            pyautogui.scroll(scroll_amount)
                            scroll_anchor_y = y1
                            mode_text = "Scroll UP" if delta_y < 0 else "Scroll DOWN"

                # -------------------------------------------------------------
                # 5. CURSOR MOVEMENT (Only Index finger is UP)
                # -------------------------------------------------------------
                elif is_cursor_only:
                    scroll_anchor_y = None
                    raw_x = np.interp(x1, (box_x1, box_x2), (0, w_screen))
                    raw_y = np.interp(y1, (box_y1, box_y2), (0, h_screen))

                    smooth_x, smooth_y = cursor_filter.update(raw_x, raw_y)
                    target_x = int(np.clip(smooth_x, 0, w_screen - 1))
                    target_y = int(np.clip(smooth_y, 0, h_screen - 1))

                    set_mouse_pos(target_x, target_y)
                    cv2.circle(img, (int(x1), int(y1)), 9, (255, 0, 200), cv2.FILLED)

                    mode_text = f"Moving ({target_x}, {target_y})"
                    mode_color = (0, 255, 255)
                    state = STATE_CURSOR
                else:
                    scroll_anchor_y = None
                    state = STATE_IDLE
            else:
                # No hand detected: reset states
                fist_start_time = None
                click_pressed = False
                rc_pressed = False
                state = STATE_IDLE
                scroll_anchor_y = None
                cursor_filter.reset()

            # Calculate Frame Rate (FPS)
            time_diff = now - prev_time
            fps = 1.0 / time_diff if time_diff > 0.001 else 30.0
            prev_time = now

            # Draw HUD overlays
            cv2.rectangle(img, (0, 0), (w_cam, 50), (20, 20, 20), cv2.FILLED)
            cv2.putText(img, f"FPS: {int(fps)}", (10, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
            cv2.putText(img, f"Mode: {mode_text}", (130, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.65, mode_color, 2)
            cv2.putText(img, "Q: Exit", (540, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1)

            cv2.imshow("AeroGlide-Vision - Hand Gesture Controller", img)

            # Keyboard Controls
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('c'):
                # Cycle through cameras safely
                cap.release()
                cam_index = (cam_index + 1) % 3
                print(f"Switching to camera index: {cam_index}")
                cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
                cap.set(3, w_cam)
                cap.set(4, h_cam)
            elif key in [ord('+'), ord('=')]:
                # Increase sensitivity (shrink box margins)
                margin_x = min(margin_x + 10, 220)
                margin_bottom = min(margin_bottom + 10, 200)
                print(f"Sensitivity increased. Margin X: {margin_x}, Bottom: {margin_bottom}")
            elif key in [ord('-'), ord('_')]:
                # Decrease sensitivity (expand box)
                margin_x = max(margin_x - 10, 80)
                margin_bottom = max(margin_bottom - 10, 80)
                print(f"Sensitivity decreased. Margin X: {margin_x}, Bottom: {margin_bottom}")
            elif key == ord('['):
                cursor_filter.base_smooth = max(cursor_filter.base_smooth - 0.03, 0.06)
                cursor_filter.deadzone = min(cursor_filter.deadzone + 0.5, 6.0)
                print(f"Smoother mode enabled (base_smooth={cursor_filter.base_smooth:.2f}, deadzone={cursor_filter.deadzone})")
            elif key == ord(']'):
                cursor_filter.base_smooth = min(cursor_filter.base_smooth + 0.03, 0.35)
                cursor_filter.deadzone = max(cursor_filter.deadzone - 0.5, 1.5)
                print(f"Faster response enabled (base_smooth={cursor_filter.base_smooth:.2f}, deadzone={cursor_filter.deadzone})")

        except Exception as loop_err:
            print(f"Warning in gesture loop: {loop_err}")
            time.sleep(0.01)

    cap.release()
    cv2.destroyAllWindows()
    print("Application closed gracefully.")

if __name__ == "__main__":
    main()
