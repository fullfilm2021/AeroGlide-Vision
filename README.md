# AeroGlide-Vision

**AeroGlide-Vision** is a next-generation AI-powered hand gesture virtual mouse and holographic cursor controller built with Python, OpenCV, and MediaPipe. Control your computer mouse, click, and scroll smoothly in the air without touching any hardware.

## Requirements
- Python 3.9+ (Python 3.11 recommended)
- Dependencies: `opencv-python`, `mediapipe==0.10.14`, `pyautogui`, `numpy`, `pygrabber`

## Installation
Install dependencies via pip:
```bash
pip install opencv-python mediapipe==0.10.14 pyautogui numpy pygrabber
```

## How to Run

### Option 1: Double-Click
Run `run_mouse.bat` directly from the file explorer.

### Option 2: Command Line / PowerShell
```powershell
python gesture_mouse.py
```

---

## Gesture Controls

| Gesture | Action | Description |
| :--- | :--- | :--- |
| **Only Index Finger Up** | **Cursor Movement** | Move hand within the active green box to smoothly control cursor across the entire screen. |
| **Thumb + Index Pinch (<30px)** | **Left Click** | Touch thumb tip and index finger tip together for an instant left click. Separate fingers to click again. |
| **Index + Middle Fingers Up** | **Scroll** | Move hand upward to scroll UP; move hand downward to scroll DOWN. |
| **Thumb + Middle Touch** | **Right Click** | Keep middle finger extended and touch thumb to middle fingertip for right click. |
| **Fist Clench (Hold 0.5s)** | **Lock Screen** | Make a tight fist to trigger instant Windows workstation lock (`Win + L`). A red HUD ring confirms before locking. |
| **Right Eye Wink** | **Eye Left Click** | Wink right eye to instantly trigger a left mouse click (Primary click). |
| **Left Eye Wink** | **Eye Right Click** | Wink left eye to trigger a right mouse click. |
| **Key 'b'** | **Toggle Eye Click** | Enable or disable eye blink clicking in real-time. |
| **Key '+' or '-'** | **Sensitivity** | Increase or decrease cursor sensitivity in real-time. |
| **Key '[' or ']'** | **Smoothness** | Adjust cursor smoothing (`[` for smoother, `]` for faster response). |
| **Key 'c'** | **Switch Camera** | Toggle between laptop built-in webcam and external/virtual cameras. |
| **Key 'q'** | **Exit** | Close camera window and exit application. |

---

## Full Screen Active Region
- A green boundary box (`Full Screen Area`) is drawn on the camera window.
- Moving your finger to the edges of this box maps proportionally to all 4 corners of your screen (0 to 1920 width, 0 to 1080 height).
- You do not need to move your arm across the entire camera view; comfortable, compact hand movements cover the whole monitor.

---

## Features
- **Adaptive Cursor Filter & Deadzone**: Cancels hand micro-tremors when pointing while preserving high-speed swipe responsiveness.
- **Hysteresis Latch Clicking**: Instantaneous click upon touch with zero accidental repeated firing.
- **AI Eye Wink Trigger**: FaceMesh-powered Eye Aspect Ratio (EAR) detector allows hands-free clicking by winking (Right Eye for Left Click, Left Eye for Right Click).
- **Auto-Detect Laptop Camera**: Automatically prioritizes built-in integrated webcams over virtual camera drivers (such as Iriun, OBS).
