# CRMIXER - Mobile Device Management (MDM) & Phone Farm Controller 📱⚡

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Scrcpy](https://img.shields.io/badge/Scrcpy-v4.1-orange.svg)](https://github.com/Genymobile/scrcpy)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()
[![License](https://img.shields.io/badge/license-MIT-purple.svg)]()

A modern, high-performance **Multi-Device Android Control & Management Platform** (Phone Farm Controller) inspired by CRMIXER MDM. It allows real-time low-latency screen mirroring, master-slave touch synchronization, multi-device broadcast actions, and automated tasks directly from a native desktop application.

โปรแกรมควบคุมและจัดการสมาร์ตโฟน Android หลายเครื่องพร้อมกันบนคอมพิวเตอร์ พร้อมระบบสตรีมมิ่งหน้าจอความเร็วสูง, สั่งการพร้อมกันแบบ Broadcast, ซิงค์การควบคุม Master-Slave และบอทปัดวิดีโออัตโนมัติ

---

## 🌟 Key Features (คุณสมบัติเด่น)

- 📺 **Real-Time Screen Mirroring:** Low-latency WebSockets + Canvas streaming + Native 60 FPS Scrcpy window launcher with hardware acceleration.
- 🖱️ **Direct Touch & Gestures:** Mouse click to tap, drag to swipe, right-click for Back, middle-click for Home, wheel to scroll.
- 👑 **Master-Slave Synchronization:** Control one primary "Master" device, and all actions are normalized and replicated across all selected "Slave" devices in real time.
- 📡 **Multi-Device Broadcast:**
  - **Broadcast Text:** Send Thai/English text, URLs, and emojis to all selected phones simultaneously.
  - **Broadcast Tap (X, Y):** Tap precise screen coordinates across multiple phones.
  - **Broadcast Swipe:** Swipe up, down, left, right with duration controls.
  - **Hardware Navigation:** Trigger Home, Back, Recent Apps, Power (Lock/Unlock), Volume +/-, and Wake.
- 🤖 **TikTok / Reels Auto-Scroller Bot:** Built-in automation loop with natural randomized watch delays and auto double-tap likes.
- 📶 **Wireless Wi-Fi ADB:** Connect and manage devices wirelessly via IP:Port without cables.
- 🎨 **Custom Tags & Rename:** Click any device name (`MD1`, etc.) to rename inline, or click the color dot to assign color tags.
- 🖥️ **Standalone Desktop Window:** Runs as a dedicated native desktop application (via PyWebView) with no browser address bars.

---

## 🏗️ System Architecture (สถาปัตยกรรมระบบ)

```
 ┌─────────────────────────────────────────────────────────────┐
 │                🖥️ Native Desktop Application               │
 │  - Cyber Dark UI (Auto-fit Grid, 1x1, 2x2, 3x3, 4x4)        │
 │  - Real-time Canvas Screen Stream (WebSockets)              │
 │  - Control Sidebar (Broadcast Text, Tap, Swipe, Navigation) │
 │  - Master-Slave Sync Engine & Auto-Scroller Bot             │
 └──────────────────────────────┬──────────────────────────────┘
                                │ WebSocket & REST API
 ┌──────────────────────────────▼──────────────────────────────┐
 │                ⚡ Backend (Python FastAPI)                  │
 │  - `adb_manager.py` (Device Discovery, Input, Wi-Fi)        │
 │  - `stream_manager.py` (Fast Raw Screen Frame Pipeline)     │
 │  - `automation.py` (Macro loops & TikTok Auto-Scroller)     │
 │  - `server.py` (FastAPI Server & WebSocket Router)          │
 └──────────────────────────────┬──────────────────────────────┘
                                │ ADB Protocol (USB / Wi-Fi)
 ┌──────────────────────────────▼──────────────────────────────┐
 │                📱 Android Devices (MD1, MD2, ... MDN)       │
 └─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start (วิธีเริ่มต้นใช้งาน)

### 1. Prerequisites (สิ่งที่ต้องมี)
- Python 3.10 or higher
- Android Phone with **USB Debugging** enabled

### 2. Installation (การติดตั้ง)
Clone the repository and install requirements:
```bash
git clone https://github.com/<YOUR_USERNAME>/CRMIXER-Mobile-Device-Management.git
cd CRMIXER-Mobile-Device-Management
pip install -r requirements.txt
```

### 3. Launch the Application (การเปิดโปรแกรม)
**On Windows:**
Double-click:
```bash
run.bat
```
or run via Python:
```bash
python desktop_app.py
```
*(On first run, the system will automatically download and setup portable ADB and Scrcpy binaries if not present).*

---

## 📱 Android Phone Setup (การตั้งค่าโทรศัพท์)

1. Go to **Settings** → **About phone**.
2. Tap **Build number** 7 times until you see *"You are now a developer!"*.
3. Go back to **Settings** → **Developer options**.
4. Enable **USB debugging**.
5. Connect phone to PC via USB cable and tap **"Always allow from this computer"**.

> [!NOTE]
> **For Xiaomi / POCO / Redmi users:**  
> In Developer options, also enable **"USB debugging (Security settings)"** to allow touch input injection from PC, or click the **`[ Open 60 FPS Control ]`** button in the app to use kernel-level hardware UHID input!

---

## 📁 Project Structure (โครงสร้างไฟล์)

```
├── app/
│   ├── __init__.py
│   ├── adb_manager.py       # ADB command dispatcher & Wi-Fi manager
│   ├── stream_manager.py    # Screen frame streaming pipeline
│   ├── automation.py        # Automation & TikTok bot engine
│   ├── server.py            # FastAPI REST & WebSocket server
│   └── static/
│       ├── index.html       # Cyber Dark UI layout
│       ├── style.css        # Responsive styling & themes
│       └── app.js           # Client WebSocket & touch dispatcher
├── bin/                     # Portable ADB & Scrcpy binaries (auto-downloaded)
├── setup_binaries.py        # Binary package downloader
├── desktop_app.py           # Native Desktop window entrypoint
├── start.py                 # Web launcher entrypoint
├── run.bat                  # One-click Windows launcher
├── requirements.txt         # Python dependencies
├── .gitignore
└── README.md
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
