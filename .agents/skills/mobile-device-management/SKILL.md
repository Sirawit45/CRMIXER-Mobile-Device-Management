---
name: mobile-device-management
description: >-
  Knowledge base, architecture, and workflow for building and extending the Multi-Device Mobile Management & Control System (MDM / Phone Farm Controller) using ADB, Scrcpy, WebSockets, and Web-based interactive GUI.
---

# Mobile Device Management & Multi-Device Control System

This skill provides comprehensive instructions, architectural design, command references, and best practices for developing, maintaining, and extending the **Mobile Device Management & Multi-Control Platform** (similar to CRMIXER MDM / Total Control / Scrcpy Web).

---

## 1. System Architecture Overview

```
 ┌─────────────────────────────────────────────────────────────┐
 │                🖥️ Native Desktop Application               │
 │  - Standalone Window (PyWebView / Native GUI Framework)     │
 │  - Multi-Device Grid (Auto-fit, 1x1, 2x2, 3x3, etc.)        │
 │  - Live Screen Streaming (Low-latency WebSocket / Canvas)   │
 │  - Interactive Touch & Gestures (Tap, Drag, Swipe, Pinch)   │
 │  - Control Sidebar (Broadcast Text, Tap, Swipe, Navigation) │
 │  - Device Cards (Power, Volume, Rotate, Status, Tags)       │
 └──────────────────────────────┬──────────────────────────────┘
                                │ WebSockets / REST API (FastAPI)
 ┌──────────────────────────────▼──────────────────────────────┐
 │                      Backend Controller                     │
 │  - Device Discovery Worker (`adb devices -l`, USB & Wi-Fi)  │
 │  - Stream Manager (Scrcpy / H.264 / MJPEG Screen Pipeline)  │
 │  - Input & Touch Dispatcher (Touch down/move/up translation)│
 │  - Synchronized Broadcast Engine (Master-Slave replication) │
 │  - Automation Engine (Macro loops, auto-scroll, tasks)      │
 └──────────────────────────────┬──────────────────────────────┘
                                │ ADB Protocol (Native ADB Binaries)
 ┌──────────────────────────────▼──────────────────────────────┐
 │                    Android Mobile Devices                   │
 │  - Device 1 (MD1)   Device 2 (MD2)   ...   Device N (MDN)   │
 └─────────────────────────────────────────────────────────────┘
```

---

## 2. Core Components & Technologies

1. **ADB (Android Debug Bridge)**:
   - Device detection: `adb devices -l`
   - Key navigation: `adb shell input keyevent <KEYCODE>`
     - Home: `3` (KEYCODE_HOME)
     - Back: `4` (KEYCODE_BACK)
     - Recent Apps: `187` (KEYCODE_APP_SWITCH)
     - Power: `26` (KEYCODE_POWER)
     - Volume Up/Down: `24` / `25`
     - Wake up: `adb shell input keyevent 224`
   - Touch & Gestures:
     - Tap: `adb shell input tap <X> <Y>`
     - Swipe: `adb shell input swipe <X1> <Y1> <X2> <Y2> [duration_ms]`
     - Drag & Drop: `adb shell input draganddrop <X1> <Y1> <X2> <Y2> [duration_ms]`
   - Text & Thai/Unicode Input:
     - Direct ASCII: `adb shell input text "<ascii_string>"`
     - Unicode/Thai Support: Uses ADB keyboard / clipboard broadcast (`adb shell am broadcast -a clipper.set -e text "<string>"` or ADBKeyBoard).

2. **Real-time Screen Streaming**:
   - **Scrcpy Integration**: High performance, 60fps, low latency (30~70ms).
   - **WebSocket Binary Stream**: Transmits screen frames or H.264 NAL units to HTML5 Canvas or WebCodecs decoder.
   - **Fallback Fast Screencap**: `adb exec-out screencap -p` or minicap / ffmpeg stream for maximum cross-device compatibility.

3. **Multi-Device Synchronization (Broadcast & Master-Slave Sync)**:
   - **Direct Broadcast**: Executes an action (e.g. tap at 360, 640 or type text) across all checked devices concurrently using asynchronous coroutines (`asyncio.gather`).
   - **Master-Slave Mirroring**: User interacts with 1 primary screen; touch coordinates are normalized `(x_norm = x / width, y_norm = y / height)` and projected onto each slave device's native resolution.

4. **Automation & Scripting**:
   - **TikTok / Reels Auto-Scroller**: Periodic swipes with configurable delay (e.g., random 5-15s), auto-like, sound toggle.
   - **Bulk App Management**: Install APK to all devices, launch package (`adb shell monkey -p <pkg> -c android.intent.category.LAUNCHER 1`), kill app (`adb shell am force-stop <pkg>`).
   - **Macro Recording**: Record user touch gestures and replay on schedule.

---

## 3. Standard Procedures & Extension Workflows

### Adding New Navigation / ADB Commands
To add a new hardware or OS action:
1. Find standard Android `KeyEvent` integer code.
2. Add API endpoint `/api/devices/{serial}/keyevent/{code}` in backend.
3. Add UI button in the sidebar or device card action bar.

### Supporting Wi-Fi ADB Devices (Wireless Phone Farm)
1. Device initially connected via USB: enable TCP/IP mode `adb -s <serial> tcpip 5555`.
2. Connect wirelessly: `adb connect <device_ip>:5555`.
3. Disconnect USB cable. The device appears seamlessly in the manager.

### Handling Screen Orientation & Coordinate Mapping
- Query device dimensions & rotation: `adb shell wm size` & `adb shell dumpsys display | grep mCurrentOrientation`.
- In Frontend Canvas:
  ```js
  const rect = canvas.getBoundingClientRect();
  const scaleX = deviceWidth / rect.width;
  const scaleY = deviceHeight / rect.height;
  const touchX = Math.round((e.clientX - rect.left) * scaleX);
  const touchY = Math.round((e.clientY - rect.top) * scaleY);
  ```

---

## 4. Broken Screen & Unresponsive Device Access Strategies

When dealing with phones with broken screens or non-functional touch digitizers:

1. **Hardware OTG Mouse / Display Hub Method (Recommended for Touch-Broken Devices)**:
   - Connect a USB-C OTG adapter with a physical USB mouse.
   - Mouse cursor appears on screen. Use mouse to unlock device and navigate to *Settings -> Developer Options -> Enable USB Debugging*.
   - For phones with DisplayPort support (Samsung Galaxy S-series / DeX, Xiaomi flagship), connect USB-C Hub to an external HDMI monitor and mouse.

2. **Custom Recovery Mode (TWRP / OrangeFox ADB Bypass)**:
   - Boot phone into Recovery (Power + Vol Up).
   - Custom recoveries (TWRP) start the ADB daemon automatically as `root` without requiring screen confirmation.
   - Inject PC RSA public key directly to `/data/misc/adb/adb_keys`:
     `adb push ~/.android/adbkey.pub /data/misc/adb/adb_keys`
   - Enable ADB by default in system settings database:
     `adb shell "sqlite3 /data/data/com.android.providers.settings/databases/settings.db \"UPDATE global SET value='1' WHERE name='adb_enabled';\""`

3. **Device Configuration & Safety Policy**:
   - For personal / daily-driver devices: **Never** silently override the user's native screen timeout, stay-awake, or personal display preferences unless explicitly requested.
   - For dedicated Phone Farm devices: Offer optional manual toggle buttons for Stay-Awake, Wi-Fi TCP/IP, and Screen Timeout.

---

## 5. Maintenance & Troubleshooting
- **Device unauthorized**: Guide user to check phone screen for "Allow USB Debugging" dialog and check "Always allow from this computer".
- **ADB Server conflict**: Run `adb kill-server` and restart daemon.
- **Latency reduction**: Lower bit-rate or max resolution (`--max-size 1024 --video-bit-rate 2M` in scrcpy).
