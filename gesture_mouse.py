import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['GLOG_minloglevel'] = '3'

# pyrefly: ignore[missing-import]
import cv2
import numpy as np
import time
import ctypes
import pyautogui
import math
from collections import deque
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
    - Deadzone eliminates micro-tremors when holding hand still.
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

        if dist < self.deadzone:
            return self.curr_x, self.curr_y

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
            
        for idx, dev_name in enumerate(devices):
            lower = str(dev_name).lower()
            if "integrated" in lower or "internal" in lower or "built-in" in lower:
                print(f">> Selected Laptop Default Camera: [{idx}]\n")
                return idx
                
        for idx, dev_name in enumerate(devices):
            lower = str(dev_name).lower()
            if not any(v in lower for v in ["iriun", "obs", "virtual", "droid"]):
                print(f">> Selected Camera: [{idx}]\n")
                return idx
    except Exception as e:
        print(f"Camera auto-detection note: {e}")

    return 1

# =============================================================================
# Sci-Fi Hologram HUD Drawing Functions (Iron Man / Cyberpunk Aesthetics)
# =============================================================================

def draw_corner_brackets(img, x1, y1, x2, y2, color=(255, 220, 0), length=25, thickness=2):
    """Draw futuristic sci-fi corner brackets instead of a plain rectangle"""
    # Top-Left
    cv2.line(img, (x1, y1), (x1 + length, y1), color, thickness)
    cv2.line(img, (x1, y1), (x1, y1 + length), color, thickness)
    # Top-Right
    cv2.line(img, (x2, y1), (x2 - length, y1), color, thickness)
    cv2.line(img, (x2, y1), (x2, y1 + length), color, thickness)
    # Bottom-Left
    cv2.line(img, (x1, y2), (x1 + length, y2), color, thickness)
    cv2.line(img, (x1, y2), (x1, y2 - length), color, thickness)
    # Bottom-Right
    cv2.line(img, (x2, y2), (x2 - length, y2), color, thickness)
    cv2.line(img, (x2, y2), (x2, y2 - length), color, thickness)

    # Subtle boundary lines
    overlay = img.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 1)
    cv2.addWeighted(overlay, 0.25, img, 0.75, 0, img)

    # Tech Label
    cv2.putText(img, "TARGET ZONE // 1920x1080", (x1 + 8, y1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)

def draw_arc_reactor(img, center_x, center_y, angle, radius=28, color=(255, 230, 0)):
    """Draw an animated rotating holographic arc-reactor ring on the palm"""
    cx, cy = int(center_x), int(center_y)
    
    # Outer dashed ring with rotating tick arcs
    cv2.ellipse(img, (cx, cy), (radius, radius), angle, 0, 70, color, 2, cv2.LINE_AA)
    cv2.ellipse(img, (cx, cy), (radius, radius), angle, 120, 190, color, 2, cv2.LINE_AA)
    cv2.ellipse(img, (cx, cy), (radius, radius), angle, 240, 310, color, 2, cv2.LINE_AA)

    # Inner core
    cv2.circle(img, (cx, cy), radius // 2, (0, 255, 255), 1, cv2.LINE_AA)
    cv2.circle(img, (cx, cy), 3, (255, 255, 255), cv2.FILLED)

def draw_energy_trail(img, trail_points):
    """Draw smooth glowing energy particles following the index finger tip"""
    n = len(trail_points)
    for i, pt in enumerate(trail_points):
        alpha = (i + 1) / float(n)
        r = max(2, int(8 * alpha))
        color = (int(255 * alpha), int(180 * alpha), int(255 * (1 - alpha)))
        cv2.circle(img, (int(pt[0]), int(pt[1])), r, color, cv2.FILLED, cv2.LINE_AA)

def draw_glass_hud(img, mode_text, mode_color, fps, w_cam, h_cam, active_cam_name="Integrated"):
    """Render semi-transparent glassmorphic top header and bottom controls HUD"""
    overlay = img.copy()
    
    # Top Header Bar (dark semi-transparent glass)
    cv2.rectangle(overlay, (0, 0), (w_cam, 52), (15, 15, 25), -1)
    # Bottom Controls Bar
    cv2.rectangle(overlay, (0, h_cam - 30), (w_cam, h_cam), (15, 15, 25), -1)
    
    cv2.addWeighted(overlay, 0.70, img, 0.30, 0, img)

    # Top neon border line
    cv2.line(img, (0, 52), (w_cam, 52), (255, 200, 0), 1, cv2.LINE_AA)
    cv2.line(img, (0, h_cam - 30), (w_cam, h_cam - 30), (80, 80, 80), 1, cv2.LINE_AA)

    # Left: Brand Badge
    cv2.circle(img, (18, 26), 6, (0, 255, 128), cv2.FILLED, cv2.LINE_AA)
    cv2.putText(img, "AEROGLIDE AI", (32, 32), cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

    # Center: Mode Badge Pill
    badge_w = 210
    bx1 = (w_cam - badge_w) // 2
    bx2 = bx1 + badge_w
    cv2.rectangle(img, (bx1, 10), (bx2, 42), (30, 30, 45), -1)
    cv2.rectangle(img, (bx1, 10), (bx2, 42), mode_color, 1, cv2.LINE_AA)
    
    text_size = cv2.getTextSize(mode_text, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 1)[0]
    tx = bx1 + (badge_w - text_size[0]) // 2
    cv2.putText(img, mode_text, (tx, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.52, mode_color, 1, cv2.LINE_AA)

    # Right: Tech Diagnostics
    cv2.putText(img, f"FPS: {int(fps)}", (w_cam - 110, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(img, f"CAM: {active_cam_name}", (w_cam - 110, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 180, 180), 1, cv2.LINE_AA)

    # Bottom Cheatsheet text
    shortcuts = "[Q] Exit  |  [C] Switch Cam  |  [+/-] Sens  |  [[ / ]] Smooth"
    cv2.putText(img, shortcuts, (15, h_cam - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (190, 190, 190), 1, cv2.LINE_AA)

def print_stylish_banner(w_screen, h_screen):
    """Futuristic ASCII Art Banner for Terminal"""
    banner = f"""
======================================================================
     ___    ______ ____   ____       ______ __     ____ ____  ______
    /   |  / ____// __ \ / __ \     / ____// /    /  _// __ \/ ____/
   / /| | / __/  / /_/ // / / /    / / __ / /     / / / / / / __/   
  / ___ |/ /___ / _, _// /_/ /    / /_/ // /___ _/ / / /_/ / /___   
 /_/  |_/_____//_/ |_| \____/     \____//_____//___//_____/_____/   

            >> NEXT-GEN AI HAND GESTURE VIRTUAL MOUSE <<
======================================================================
  [+] Screen Resolution : {w_screen} x {h_screen}
  [+] Active Engine     : MediaPipe Hand ML (21 Keypoints)
  [+] Cursor Engine     : Adaptive Deadzone Filter (Zero Jitter)

  GESTURE CONTROLS:
  * Index finger up only               -> Smooth Cursor Movement
  * Thumb + Index pinch                -> Instant Left Click
  * Index + Middle fingers up          -> Smooth Scroll (Up / Down)
  * Thumb + Middle pinch (Middle UP)   -> Right Click
  * Fist Clench (hold 0.5s)            -> Screen Lock (Win + L)

  KEYBOARD SHORTCUTS:
  * '+' / '-'                          -> Adjust Screen Sensitivity
  * '[' / ']'                          -> Adjust Smoothing & Speed
  * 'c'                                -> Cycle Video Input Device
  * 'q'                                -> Gracefully Exit Application
======================================================================
"""
    print(banner)

# =============================================================================
# Main Application Loop
# =============================================================================

def main():
    w_cam, h_cam = 640, 480
    
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

    cursor_filter = AdaptiveCursorFilter(deadzone=3.5, base_smooth=0.20)
    trail_points = deque(maxlen=12)

    click_pressed = False
    rc_pressed = False
    scroll_anchor_y = None
    prev_time = time.time()
    frame_count = 0

    fist_start_time = None
    last_lock_time = 0.0
    FIST_HOLD_DURATION = 0.55
    LOCK_COOLDOWN = 3.0

    CLICK_THRESHOLD = 30
    CLICK_RESET_THRESHOLD = 38
    RIGHT_CLICK_THRESHOLD = 32
    RIGHT_CLICK_RESET = 40
    SCROLL_DEADZONE = 6

    cam_index = get_laptop_camera_index()
    cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"Camera {cam_index} not opened. Trying default camera (0)...")
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        cam_index = 0

    cap.set(3, w_cam)
    cap.set(4, h_cam)

    detector = HandDetector(max_hands=1, detection_con=0.7, track_con=0.7)
    print_stylish_banner(w_screen, h_screen)

    while True:
        try:
            success, img = cap.read()
            if not success or img is None or img.size == 0:
                print("Failed to capture video from camera. Retrying...")
                time.sleep(0.5)
                continue

            frame_count += 1
            img = cv2.flip(img, 1)

            # Find Hand Landmarks with Cyberpunk styling
            img = detector.find_hands(img, draw=True)
            lm_list = detector.find_position(img, draw=False)

            mode_text = "IDLE // READY"
            mode_color = (180, 180, 180)

            # Active boundary box coordinates
            box_x1 = margin_x
            box_x2 = max(w_cam - margin_x, box_x1 + 60)
            box_y1 = margin_top
            box_y2 = max(h_cam - margin_bottom, box_y1 + 60)

            # Draw Sci-Fi Target Brackets
            draw_corner_brackets(img, box_x1, box_y1, box_x2, box_y2, color=(255, 220, 0), length=22, thickness=2)

            now = time.time()

            if len(lm_list) >= 21:
                x1, y1 = lm_list[8][1], lm_list[8][2]    # Index tip
                x2, y2 = lm_list[12][1], lm_list[12][2]  # Middle tip
                x0, y0 = lm_list[4][1], lm_list[4][2]    # Thumb tip

                # Animated Holographic Arc Reactor on palm center (Landmark 9)
                reactor_angle = (frame_count * 6) % 360
                draw_arc_reactor(img, lm_list[9][1], lm_list[9][2], reactor_angle, radius=26, color=(255, 230, 0))

                fingers = detector.fingers_up()

                pinch_dist, img, line_pinch = detector.find_distance(4, 8, img, draw=False)
                rc_dist, img, line_rc = detector.find_distance(4, 12, img, draw=False)

                is_fist = (fingers == [0, 0, 0, 0, 0])
                is_left_touch = not is_fist and (pinch_dist < CLICK_THRESHOLD)
                
                is_right_touch = (
                    not is_fist
                    and not is_left_touch 
                    and fingers[2] == 1 
                    and rc_dist < RIGHT_CLICK_THRESHOLD
                )

                if pinch_dist > CLICK_RESET_THRESHOLD:
                    click_pressed = False
                if rc_dist > RIGHT_CLICK_RESET or fingers[2] == 0:
                    rc_pressed = False

                is_scroll = (
                    not is_fist
                    and not is_left_touch 
                    and not is_right_touch 
                    and fingers[1] == 1 
                    and fingers[2] == 1 
                    and pinch_dist > CLICK_RESET_THRESHOLD
                )

                is_cursor_only = (
                    not is_fist
                    and not is_left_touch 
                    and not is_right_touch 
                    and fingers[1] == 1 
                    and fingers[2] == 0
                )

                # -------------------------------------------------------------
                # 0. FIST CLENCH: Lock Screen (Win + L) with Red Warning Ring
                # -------------------------------------------------------------
                if is_fist:
                    scroll_anchor_y = None
                    if fist_start_time is None:
                        fist_start_time = now

                    elapsed_fist = now - fist_start_time
                    remaining = max(0.0, FIST_HOLD_DURATION - elapsed_fist)

                    palm_cx = int(lm_list[9][1])
                    palm_cy = int(lm_list[9][2])
                    cv2.circle(img, (palm_cx, palm_cy), 32, (0, 0, 255), 3, cv2.LINE_AA)
                    cv2.circle(img, (palm_cx, palm_cy), 10, (0, 0, 255), cv2.FILLED, cv2.LINE_AA)

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
                # 1. LEFT CLICK: Thumb + Index touch
                # -------------------------------------------------------------
                if is_fist:
                    pass
                elif is_left_touch:
                    scroll_anchor_y = None
                    cv2.circle(img, (int(line_pinch[4]), int(line_pinch[5])), 14, (0, 255, 0), cv2.FILLED, cv2.LINE_AA)
                    if not click_pressed:
                        pyautogui.click()
                        click_pressed = True
                        mode_text = "LEFT CLICK"
                        mode_color = (0, 255, 0)
                    else:
                        mode_text = "PINCH HOLD"
                        mode_color = (0, 200, 100)

                # -------------------------------------------------------------
                # 2. RIGHT CLICK: Thumb + Middle touch (Middle extended)
                # -------------------------------------------------------------
                elif is_right_touch:
                    scroll_anchor_y = None
                    cv2.circle(img, (int(line_rc[4]), int(line_rc[5])), 12, (0, 0, 255), cv2.FILLED, cv2.LINE_AA)
                    if not rc_pressed:
                        pyautogui.rightClick()
                        rc_pressed = True
                        mode_text = "RIGHT CLICK"
                        mode_color = (0, 0, 255)
                    else:
                        mode_text = "RC HOLD"
                        mode_color = (0, 0, 180)

                # -------------------------------------------------------------
                # 3. SCROLLING (Index + Middle fingers straight UP)
                # -------------------------------------------------------------
                elif is_scroll:
                    mode_text = "SCROLL MODE"
                    mode_color = (255, 255, 0)
                    cv2.circle(img, (int(x1), int(y1)), 8, (255, 255, 0), cv2.FILLED, cv2.LINE_AA)
                    cv2.circle(img, (int(x2), int(y2)), 8, (255, 255, 0), cv2.FILLED, cv2.LINE_AA)

                    if scroll_anchor_y is None:
                        scroll_anchor_y = y1
                    else:
                        delta_y = y1 - scroll_anchor_y
                        if abs(delta_y) > SCROLL_DEADZONE:
                            scroll_amount = int(-delta_y * 12)
                            pyautogui.scroll(scroll_amount)
                            scroll_anchor_y = y1
                            mode_text = "SCROLL UP" if delta_y < 0 else "SCROLL DOWN"

                # -------------------------------------------------------------
                # 4. CURSOR MOVEMENT: Only Index finger is UP
                # -------------------------------------------------------------
                elif is_cursor_only:
                    scroll_anchor_y = None
                    raw_x = np.interp(x1, (box_x1, box_x2), (0, w_screen))
                    raw_y = np.interp(y1, (box_y1, box_y2), (0, h_screen))

                    smooth_x, smooth_y = cursor_filter.update(raw_x, raw_y)
                    target_x = int(np.clip(smooth_x, 0, w_screen - 1))
                    target_y = int(np.clip(smooth_y, 0, h_screen - 1))

                    set_mouse_pos(target_x, target_y)

                    # Update Motion Trail
                    trail_points.append((x1, y1))
                    draw_energy_trail(img, trail_points)

                    # Target reticle on index finger
                    cv2.circle(img, (int(x1), int(y1)), 8, (255, 0, 220), cv2.FILLED, cv2.LINE_AA)
                    cv2.circle(img, (int(x1), int(y1)), 14, (0, 255, 255), 1, cv2.LINE_AA)

                    mode_text = f"TARGET [{target_x}, {target_y}]"
                    mode_color = (0, 255, 255)
                else:
                    scroll_anchor_y = None
            else:
                fist_start_time = None
                click_pressed = False
                rc_pressed = False
                scroll_anchor_y = None
                cursor_filter.reset()
                trail_points.clear()

            # Calculate FPS
            time_diff = now - prev_time
            fps = 1.0 / time_diff if time_diff > 0.001 else 30.0
            prev_time = now

            # Render Sci-Fi Glassmorphic HUD Overlays
            cam_label = "BUILT-IN" if cam_index == 1 else f"DEV_{cam_index}"
            draw_glass_hud(img, mode_text, mode_color, fps, w_cam, h_cam, active_cam_name=cam_label)

            cv2.imshow("AeroGlide-Vision // Holographic HUD", img)

            # Keyboard Controls
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('c'):
                cap.release()
                cam_index = (cam_index + 1) % 3
                print(f"Switching camera -> Index: {cam_index}")
                cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
                cap.set(3, w_cam)
                cap.set(4, h_cam)
            elif key in [ord('+'), ord('=')]:
                margin_x = min(margin_x + 10, 220)
                margin_bottom = min(margin_bottom + 10, 200)
                print(f"[HUD] Sensitivity Increased: MarginX={margin_x}, MarginBottom={margin_bottom}")
            elif key in [ord('-'), ord('_')]:
                margin_x = max(margin_x - 10, 80)
                margin_bottom = max(margin_bottom - 10, 80)
                print(f"[HUD] Sensitivity Decreased: MarginX={margin_x}, MarginBottom={margin_bottom}")
            elif key == ord('['):
                cursor_filter.base_smooth = max(cursor_filter.base_smooth - 0.03, 0.06)
                cursor_filter.deadzone = min(cursor_filter.deadzone + 0.5, 6.0)
                print(f"[HUD] Smooth Mode: Smooth={cursor_filter.base_smooth:.2f}, Deadzone={cursor_filter.deadzone}")
            elif key == ord(']'):
                cursor_filter.base_smooth = min(cursor_filter.base_smooth + 0.03, 0.35)
                cursor_filter.deadzone = max(cursor_filter.deadzone - 0.5, 1.5)
                print(f"[HUD] Fast Response: Smooth={cursor_filter.base_smooth:.2f}, Deadzone={cursor_filter.deadzone}")

        except Exception as loop_err:
            print(f"HUD loop warning: {loop_err}")
            time.sleep(0.01)

    cap.release()
    cv2.destroyAllWindows()
    print("AeroGlide-Vision terminated gracefully.")

if __name__ == "__main__":
    main()
