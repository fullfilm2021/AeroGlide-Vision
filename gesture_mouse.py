import os
import warnings
warnings.filterwarnings('ignore')
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
from FaceTrackingModule import FaceEyeDetector

# Set Windows DPI Awareness so full resolution is tracked accurately
try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

# Prevent PyAutoGUI from crashing when mouse hits screen corners
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.001

import winsound
import threading
# pyrefly: ignore[missing-import]
import pystray
from PIL import Image, ImageDraw
import win32gui
import win32con

WINDOW_TITLE = "AeroGlide-Vision // Holographic HUD"

def create_tray_image():
    """Generate 64x64 cyberpunk tray icon with glowing green reticle"""
    img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, 60, 60), fill=(18, 22, 34), outline=(0, 255, 128), width=3)
    d.ellipse((20, 20, 44, 44), fill=(0, 255, 128))
    d.ellipse((28, 28, 36, 36), fill=(18, 22, 34))
    return img

def trigger_audio_click():
    """Non-blocking subtle audio click sound"""
    try:
        threading.Thread(target=lambda: winsound.MessageBeep(0), daemon=True).start()
    except Exception:
        pass

def hardware_left_click():
    """Direct hardware level left click via Windows API"""
    try:
        ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0) # LEFTDOWN
        time.sleep(0.012)
        ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0) # LEFTUP
    except Exception:
        pyautogui.click()
    trigger_audio_click()

def hardware_right_click():
    """Direct hardware level right click via Windows API"""
    try:
        ctypes.windll.user32.mouse_event(0x0008, 0, 0, 0, 0) # RIGHTDOWN
        time.sleep(0.012)
        ctypes.windll.user32.mouse_event(0x0010, 0, 0, 0, 0) # RIGHTUP
    except Exception:
        pyautogui.rightClick()
    trigger_audio_click()

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

def draw_corner_brackets(img, x1, y1, x2, y2, color=(0, 240, 255), length=25, thickness=2):
    """Draw futuristic Iron Man holographic corner brackets with tactical grid marks"""
    # Top-Left
    cv2.line(img, (x1, y1), (x1 + length, y1), color, thickness)
    cv2.line(img, (x1, y1), (x1, y1 + length), color, thickness)
    cv2.circle(img, (x1, y1), 3, color, cv2.FILLED)
    # Top-Right
    cv2.line(img, (x2, y1), (x2 - length, y1), color, thickness)
    cv2.line(img, (x2, y1), (x2, y1 + length), color, thickness)
    cv2.circle(img, (x2, y1), 3, color, cv2.FILLED)
    # Bottom-Left
    cv2.line(img, (x1, y2), (x1 + length, y2), color, thickness)
    cv2.line(img, (x1, y2), (x1, y2 - length), color, thickness)
    cv2.circle(img, (x1, y2), 3, color, cv2.FILLED)
    # Bottom-Right
    cv2.line(img, (x2, y2), (x2 - length, y2), color, thickness)
    cv2.line(img, (x2, y2), (x2, y2 - length), color, thickness)
    cv2.circle(img, (x2, y2), 3, color, cv2.FILLED)

    # Subtle boundary lines with cyan tint
    overlay = img.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 1)
    cv2.addWeighted(overlay, 0.20, img, 0.80, 0, img)

    # Tactical HUD Coordinates Tag
    cv2.putText(img, "STARK TGT ZONE // 1920x1080", (x1 + 8, y1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 255), 1, cv2.LINE_AA)

def draw_arc_reactor(img, center_x, center_y, frame_count, radius=30):
    """Draw an authentic multi-layer dual counter-rotating Stark Arc Reactor on palm center"""
    cx, cy = int(center_x), int(center_y)
    
    # Outer clockwise ring (3 segmented arcs)
    ang1 = (frame_count * 5) % 360
    cv2.ellipse(img, (cx, cy), (radius, radius), ang1, 0, 75, (0, 240, 255), 2, cv2.LINE_AA)
    cv2.ellipse(img, (cx, cy), (radius, radius), ang1, 120, 195, (0, 240, 255), 2, cv2.LINE_AA)
    cv2.ellipse(img, (cx, cy), (radius, radius), ang1, 240, 315, (0, 240, 255), 2, cv2.LINE_AA)

    # Middle counter-clockwise ring (4 segmented arcs)
    ang2 = (-frame_count * 4) % 360
    r_mid = max(10, radius - 8)
    cv2.ellipse(img, (cx, cy), (r_mid, r_mid), ang2, 0, 50, (255, 200, 0), 1, cv2.LINE_AA)
    cv2.ellipse(img, (cx, cy), (r_mid, r_mid), ang2, 90, 140, (255, 200, 0), 1, cv2.LINE_AA)
    cv2.ellipse(img, (cx, cy), (r_mid, r_mid), ang2, 180, 230, (255, 200, 0), 1, cv2.LINE_AA)
    cv2.ellipse(img, (cx, cy), (r_mid, r_mid), ang2, 270, 320, (255, 200, 0), 1, cv2.LINE_AA)

    # 6 Radial power nodes
    for k in range(6):
        node_ang = math.radians(ang1 + k * 60)
        nx = int(cx + (radius - 4) * math.cos(node_ang))
        ny = int(cy + (radius - 4) * math.sin(node_ang))
        cv2.circle(img, (nx, ny), 2, (0, 255, 255), cv2.FILLED, cv2.LINE_AA)

    # Core energy emitter
    cv2.circle(img, (cx, cy), 10, (255, 240, 200), 1, cv2.LINE_AA)
    cv2.circle(img, (cx, cy), 5, (0, 255, 255), cv2.FILLED, cv2.LINE_AA)
    cv2.circle(img, (cx, cy), 2, (255, 255, 255), cv2.FILLED, cv2.LINE_AA)

def draw_ironman_target_lock(img, x, y, frame_count, target_x, target_y):
    """Draw Iron Man animated holographic target lock reticle around index finger"""
    ix, iy = int(x), int(y)
    rot = (frame_count * 3) % 360

    # Rotating 4-corner diamond tick marks
    for angle_deg in [rot, rot + 90, rot + 180, rot + 270]:
        rad = math.radians(angle_deg)
        px = int(ix + 18 * math.cos(rad))
        py = int(iy + 18 * math.sin(rad))
        cv2.circle(img, (px, py), 2, (0, 255, 255), cv2.FILLED, cv2.LINE_AA)

    # Central Reticle Ring & Crosshair Lines
    cv2.circle(img, (ix, iy), 12, (0, 220, 255), 1, cv2.LINE_AA)
    cv2.line(img, (ix - 18, iy), (ix - 8, iy), (0, 255, 255), 1, cv2.LINE_AA)
    cv2.line(img, (ix + 8, iy), (ix + 18, iy), (0, 255, 255), 1, cv2.LINE_AA)
    cv2.line(img, (ix, iy - 18), (ix, iy - 8), (0, 255, 255), 1, cv2.LINE_AA)
    cv2.line(img, (ix, iy + 8), (ix, iy + 18), (0, 255, 255), 1, cv2.LINE_AA)
    cv2.circle(img, (ix, iy), 3, (255, 0, 200), cv2.FILLED, cv2.LINE_AA)

    # Floating Holographic Data Callout
    tx = ix + 24
    ty = iy - 12
    cv2.line(img, (ix + 14, iy - 6), (tx - 4, ty + 4), (0, 255, 255), 1, cv2.LINE_AA)
    cv2.rectangle(img, (tx - 2, ty - 12), (tx + 120, ty + 6), (20, 20, 35), -1)
    cv2.rectangle(img, (tx - 2, ty - 12), (tx + 120, ty + 6), (0, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(img, f"LOCK [{target_x},{target_y}]", (tx + 2, ty),
                cv2.FONT_HERSHEY_SIMPLEX, 0.34, (0, 255, 255), 1, cv2.LINE_AA)

def draw_fist_charge_meter(img, palm_cx, palm_cy, progress, remaining):
    """Draw Iron Man Repulsor overload charging ring when fist is clenched"""
    cx, cy = int(palm_cx), int(palm_cy)
    
    # Outer Danger Ring
    cv2.circle(img, (cx, cy), 36, (0, 0, 150), 1, cv2.LINE_AA)
    
    # Progress Arc from -90 deg filling up to 360 deg
    sweep_angle = int(360 * max(0.0, min(1.0, progress)))
    if sweep_angle > 0:
        cv2.ellipse(img, (cx, cy), (36, 36), -90, 0, sweep_angle, (0, 0, 255), 4, cv2.LINE_AA)

    # Inner core pulse
    core_color = (0, 0, 255) if (int(remaining * 10) % 2 == 0) else (0, 120, 255)
    cv2.circle(img, (cx, cy), 14, core_color, cv2.FILLED, cv2.LINE_AA)
    cv2.circle(img, (cx, cy), 5, (255, 255, 255), cv2.FILLED, cv2.LINE_AA)

    # Warning Text Tag
    txt = f"LOCKDOWN {int(progress * 100)}%"
    cv2.putText(img, txt, (cx - 44, cy - 44), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 0, 255), 1, cv2.LINE_AA)

def draw_energy_trail(img, trail_points):
    """Draw smooth glowing energy particles following the index finger tip"""
    n = len(trail_points)
    for i, pt in enumerate(trail_points):
        alpha = (i + 1) / float(n)
        r = max(2, int(8 * alpha))
        color = (int(255 * alpha), int(180 * alpha), int(255 * (1 - alpha)))
        cv2.circle(img, (int(pt[0]), int(pt[1])), r, color, cv2.FILLED, cv2.LINE_AA)

def draw_glass_hud(img, mode_text, mode_color, fps, w_cam, h_cam, active_cam_name="Integrated", eye_enabled=True, ear_info=None, alert_text=None, frame_count=0):
    """Render authentic Stark Industries JARVIS holographic HUD header and footer"""
    overlay = img.copy()
    
    # Top Header Bar (dark semi-transparent glass)
    cv2.rectangle(overlay, (0, 0), (w_cam, 54), (12, 14, 24), -1)
    # Bottom Controls Bar
    cv2.rectangle(overlay, (0, h_cam - 30), (w_cam, h_cam), (12, 14, 24), -1)
    
    cv2.addWeighted(overlay, 0.72, img, 0.28, 0, img)

    # Holographic neon border lines with Stark Gold accent
    cv2.line(img, (0, 54), (w_cam, 54), (0, 220, 255), 1, cv2.LINE_AA)
    cv2.line(img, (0, h_cam - 30), (w_cam, h_cam - 30), (70, 70, 80), 1, cv2.LINE_AA)

    # Left: Stark Industries / JARVIS Reactor Badge
    rot_badge = (frame_count * 6) % 360
    cv2.ellipse(img, (20, 27), (8, 8), rot_badge, 0, 180, (0, 255, 128), 2, cv2.LINE_AA)
    cv2.circle(img, (20, 27), 3, (0, 255, 255), cv2.FILLED, cv2.LINE_AA)
    cv2.putText(img, "JARVIS // MARK-L", (34, 33), cv2.FONT_HERSHEY_DUPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)

    # Center: Mode Badge with Chamfered Cyberpunk Pill
    badge_w = 210
    bx1 = (w_cam - badge_w) // 2
    bx2 = bx1 + badge_w
    cv2.rectangle(img, (bx1, 11), (bx2, 43), (25, 28, 42), -1)
    cv2.rectangle(img, (bx1, 11), (bx2, 43), mode_color, 1, cv2.LINE_AA)
    cv2.rectangle(img, (bx1 + 2, 13), (bx2 - 2, 41), (0, 120, 150), 1, cv2.LINE_AA)
    
    text_size = cv2.getTextSize(mode_text, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1)[0]
    tx = bx1 + (badge_w - text_size[0]) // 2
    cv2.putText(img, mode_text, (tx, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.48, mode_color, 1, cv2.LINE_AA)

    # Right: Diagnostics & Stark Reactor Power Gauge
    eye_label = "EYE: ON" if eye_enabled else "EYE: OFF"
    eye_color = (0, 255, 128) if eye_enabled else (120, 120, 120)
    cv2.putText(img, f"FPS: {int(fps)}", (w_cam - 110, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(img, eye_label, (w_cam - 110, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.35, eye_color, 1, cv2.LINE_AA)
    cv2.putText(img, f"CAM: {active_cam_name}", (w_cam - 110, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (180, 180, 180), 1, cv2.LINE_AA)

    # Live EAR Diagnostics
    if eye_enabled:
        if ear_info is not None:
            l_e, r_e, b_e, is_lw, is_rw = ear_info
            l_col = (0, 255, 0) if is_lw else (220, 220, 220)
            r_col = (0, 0, 255) if is_rw else (220, 220, 220)
            ear_txt = f"EAR L:[{l_e:.2f}] R:[{r_e:.2f}]"
            cv2.putText(img, ear_txt, (148, 47), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (0, 255, 220), 1, cv2.LINE_AA)
        else:
            cv2.putText(img, "EYE: NO FACE", (148, 47), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (0, 165, 255), 1, cv2.LINE_AA)

    # Center Screen Glowing Alert Banner
    if alert_text:
        alert_w = 270
        ax1 = (w_cam - alert_w) // 2
        ax2 = ax1 + alert_w
        cv2.rectangle(img, (ax1, 64), (ax2, 96), (0, 35, 15) if "LEFT" in alert_text else (0, 0, 35), -1)
        cv2.rectangle(img, (ax1, 64), (ax2, 96), (0, 255, 128) if "LEFT" in alert_text else (0, 0, 255), 2, cv2.LINE_AA)
        a_size = cv2.getTextSize(alert_text, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1)[0]
        atx = ax1 + (alert_w - a_size[0]) // 2
        cv2.putText(img, alert_text, (atx, 84), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)

    # Bottom Cheatsheet text
    shortcuts = "[Q] Exit  |  [H] Hide Tray  |  [B] Eye Click  |  [C] Cam  |  [+/-] Sens"
    cv2.putText(img, shortcuts, (15, h_cam - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (190, 190, 190), 1, cv2.LINE_AA)

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
  [+] Active Engine     : MediaPipe Hand + FaceMesh ML
  [+] Cursor Engine     : Adaptive Deadzone Filter (Zero Jitter)

  GESTURE CONTROLS:
  * Index finger up only               -> Smooth Cursor Movement
  * Thumb + Index pinch                -> Instant Left Click
  * Index + Middle fingers up          -> Smooth Scroll (Up / Down)
  * Thumb + Middle pinch (Middle UP)   -> Right Click
  * Fist Clench (hold 0.5s)            -> Screen Lock (Win + L)
  * Right Eye Wink                     -> Instant Left Click (Primary)
  * Left Eye Wink                      -> Instant Right Click

  KEYBOARD SHORTCUTS:
  * 'h'                                -> Hide Camera Window to System Tray
  * 'b'                                -> Toggle Eye Blink Click (ON/OFF)
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
    face_detector = FaceEyeDetector(max_faces=1, detection_con=0.6, track_con=0.6)

    eye_click_enabled = True
    l_wink_pressed = False
    r_wink_pressed = False
    last_click_event = None
    last_click_time = 0.0

    hud_visible = True
    app_running = True

    def show_hud(icon=None, item=None):
        nonlocal hud_visible
        hud_visible = True
        hwnd = win32gui.FindWindow(None, WINDOW_TITLE)
        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                pass

    def hide_hud(icon=None, item=None):
        nonlocal hud_visible
        hud_visible = False
        hwnd = win32gui.FindWindow(None, WINDOW_TITLE)
        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
            try:
                if icon:
                    icon.notify("AeroGlide-Vision minimized to System Tray. Gestures are still active!", "AeroGlide-Vision")
            except Exception:
                pass

    def toggle_eye(icon=None, item=None):
        nonlocal eye_click_enabled
        eye_click_enabled = not eye_click_enabled
        status_txt = "ENABLED" if eye_click_enabled else "DISABLED"
        print(f"[HUD] Eye Blink Click: {status_txt}")

    def exit_app(icon=None, item=None):
        nonlocal app_running
        app_running = False
        if icon:
            icon.stop()

    tray_menu = pystray.Menu(
        pystray.MenuItem("Show Camera HUD", show_hud, default=True),
        pystray.MenuItem("Hide Camera HUD", hide_hud),
        pystray.MenuItem("Toggle Eye Click", toggle_eye),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit AeroGlide", exit_app)
    )
    tray_icon = pystray.Icon("AeroGlide", create_tray_image(), "AeroGlide-Vision // AI Mouse", tray_menu)
    tray_icon.run_detached()

    cv2.namedWindow(WINDOW_TITLE)
    print_stylish_banner(w_screen, h_screen)

    while app_running:
        try:
            success, img = cap.read()
            if not success or img is None or img.size == 0:
                print("Failed to capture video from camera. Retrying...")
                time.sleep(0.5)
                continue

            frame_count += 1
            now = time.time()
            img = cv2.flip(img, 1)

            mode_text = "IDLE // READY"
            mode_color = (180, 180, 180)

            ear_info = None
            alert_text = None

            # Eye Blink & Wink Detection (AI Vision)
            if eye_click_enabled:
                face_detector.process(img)
                left_ear, right_ear, is_l_wink, is_r_wink, is_both_blink, l_center, r_center, base_ear = face_detector.get_eye_status(img, draw=True)

                if l_center is not None and r_center is not None:
                    ear_info = (left_ear, right_ear, base_ear, is_l_wink, is_r_wink)

                    # Dynamic reopen reset
                    reopen_thresh = base_ear * 0.78
                    if left_ear >= reopen_thresh and not is_l_wink:
                        l_wink_pressed = False
                    if right_ear >= reopen_thresh and not is_r_wink:
                        r_wink_pressed = False

                    # Right Eye Wink -> Instant Left Click (Comfortable single-eye wink)
                    if is_r_wink:
                        if not r_wink_pressed:
                            hardware_left_click()
                            r_wink_pressed = True
                            last_click_event = "EYE LEFT CLICK"
                            last_click_time = now
                    # Left Eye Wink -> Right Click
                    elif is_l_wink:
                        if not l_wink_pressed:
                            hardware_right_click()
                            l_wink_pressed = True
                            last_click_event = "EYE RIGHT CLICK"
                            last_click_time = now

            if last_click_event and (now - last_click_time < 0.65):
                alert_text = last_click_event

            # Find Hand Landmarks with Cyberpunk styling
            img = detector.find_hands(img, draw=True)
            lm_list = detector.find_position(img, draw=False)

            # Active boundary box coordinates
            box_x1 = margin_x
            box_x2 = max(w_cam - margin_x, box_x1 + 60)
            box_y1 = margin_top
            box_y2 = max(h_cam - margin_bottom, box_y1 + 60)

            # Draw Sci-Fi Target Brackets
            draw_corner_brackets(img, box_x1, box_y1, box_x2, box_y2, color=(255, 220, 0), length=22, thickness=2)

            if len(lm_list) >= 21:
                x1, y1 = lm_list[8][1], lm_list[8][2]    # Index tip
                x2, y2 = lm_list[12][1], lm_list[12][2]  # Middle tip
                x0, y0 = lm_list[4][1], lm_list[4][2]    # Thumb tip

                # Animated Holographic Arc Reactor on palm center (Landmark 9)
                draw_arc_reactor(img, lm_list[9][1], lm_list[9][2], frame_count, radius=30)

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
                # 0. FIST CLENCH: Lock Screen (Win + L) with Iron Man Charge Meter
                # -------------------------------------------------------------
                if is_fist:
                    scroll_anchor_y = None
                    if fist_start_time is None:
                        fist_start_time = now

                    elapsed_fist = now - fist_start_time
                    remaining = max(0.0, FIST_HOLD_DURATION - elapsed_fist)
                    progress = min(elapsed_fist / FIST_HOLD_DURATION, 1.0)

                    palm_cx = int(lm_list[9][1])
                    palm_cy = int(lm_list[9][2])
                    draw_fist_charge_meter(img, palm_cx, palm_cy, progress, remaining)

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
                    cv2.circle(img, (int(line_pinch[4]), int(line_pinch[5])), 16, (0, 255, 128), cv2.FILLED, cv2.LINE_AA)
                    cv2.circle(img, (int(line_pinch[4]), int(line_pinch[5])), 24, (0, 255, 255), 1, cv2.LINE_AA)
                    if not click_pressed:
                        hardware_left_click()
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
                    cv2.circle(img, (int(line_rc[4]), int(line_rc[5])), 14, (0, 0, 255), cv2.FILLED, cv2.LINE_AA)
                    cv2.circle(img, (int(line_rc[4]), int(line_rc[5])), 22, (0, 120, 255), 1, cv2.LINE_AA)
                    if not rc_pressed:
                        hardware_right_click()
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

                    # Iron Man Holographic Target Lock Reticle
                    draw_ironman_target_lock(img, x1, y1, frame_count, target_x, target_y)

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
            if hud_visible:
                draw_glass_hud(img, mode_text, mode_color, fps, w_cam, h_cam, active_cam_name=cam_label, eye_enabled=eye_click_enabled, ear_info=ear_info, alert_text=alert_text, frame_count=frame_count)
                cv2.imshow(WINDOW_TITLE, img)

                # Keyboard Controls
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('h'):
                    hide_hud(tray_icon)
                elif key == ord('b'):
                    toggle_eye()
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
            else:
                time.sleep(0.005)

        except Exception as loop_err:
            print(f"HUD loop warning: {loop_err}")
            time.sleep(0.01)

    cap.release()
    cv2.destroyAllWindows()
    try:
        tray_icon.stop()
    except Exception:
        pass
    print("AeroGlide-Vision terminated gracefully.")

if __name__ == "__main__":
    main()
