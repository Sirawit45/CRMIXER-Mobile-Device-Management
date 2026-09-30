import os
import asyncio
import logging
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager

from app.adb_manager import ADBManager
from app.stream_manager import StreamManager
from app.automation import AutomationEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MDMServer")

adb_manager = ADBManager()
stream_manager = StreamManager(adb_manager)
automation_engine = AutomationEngine(adb_manager)

# Event subscribers
event_subscribers: List[WebSocket] = []

async def broadcast_event(event_type: str, data: dict):
    msg = {"type": event_type, "data": data}
    dead = []
    for ws in event_subscribers:
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in event_subscribers:
            event_subscribers.remove(ws)

async def device_scanner_loop():
    """Periodically refreshes connected devices and notifies UI."""
    last_serials = set()
    while True:
        try:
            devices = await adb_manager.refresh_devices()
            current_serials = {d.serial for d in devices}
            if current_serials != last_serials:
                last_serials = current_serials
                await broadcast_event("devices_changed", {
                    "devices": [d.to_dict() for d in devices]
                })
        except Exception as e:
            logger.error(f"Error in device scanner loop: {e}")
        await asyncio.sleep(4.0)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await adb_manager.refresh_devices()
    scanner_task = asyncio.create_task(device_scanner_loop())
    yield
    # Shutdown
    scanner_task.cancel()

app = FastAPI(title="CRMIXER Mobile Device Management", lifespan=lifespan)

# Static files directory
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h1>CRMIXER MDM Initializing...</h1>")

# --- Request Models ---

class AliasUpdateRequest(BaseModel):
    alias: Optional[str] = None
    color_tag: Optional[str] = None

class WifiConnectRequest(BaseModel):
    ip_port: str

class TapRequest(BaseModel):
    x: int
    y: int

class SwipeRequest(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int
    duration_ms: int = 300

class TextRequest(BaseModel):
    text: str

class BroadcastTapRequest(BaseModel):
    serials: List[str]
    x: int
    y: int
    ref_width: Optional[int] = None
    ref_height: Optional[int] = None

class BroadcastSwipeRequest(BaseModel):
    serials: List[str]
    x1: int
    y1: int
    x2: int
    y2: int
    duration_ms: int = 300
    ref_width: Optional[int] = None
    ref_height: Optional[int] = None

class BroadcastKeyeventRequest(BaseModel):
    serials: List[str]
    keycode: int

class BroadcastTextRequest(BaseModel):
    serials: List[str]
    text: str

class BroadcastNavRequest(BaseModel):
    serials: List[str]
    action: str # "home", "back", "recent", "power", "wake", "vol_up", "vol_down"

class AutoScrollRequest(BaseModel):
    serials: List[str]
    min_delay: float = 4.0
    max_delay: float = 10.0
    auto_like_prob: float = 0.2

# --- REST Endpoints ---

@app.get("/api/devices")
async def get_devices():
    devices = list(adb_manager.devices.values())
    return {"devices": [d.to_dict() for d in devices]}

@app.post("/api/devices/refresh")
async def refresh_devices():
    devices = await adb_manager.refresh_devices()
    return {"devices": [d.to_dict() for d in devices]}

@app.post("/api/devices/connect_wifi")
async def connect_wifi(req: WifiConnectRequest):
    success, msg = await adb_manager.connect_wifi(req.ip_port)
    return {"success": success, "message": msg}

@app.post("/api/devices/disconnect_wifi")
async def disconnect_wifi(req: WifiConnectRequest):
    success, msg = await adb_manager.disconnect_wifi(req.ip_port)
    return {"success": success, "message": msg}

@app.post("/api/devices/{serial}/enable_tcpip")
async def enable_tcpip(serial: str, port: int = 5555):
    success = await adb_manager.enable_tcpip(serial, port)
    return {"success": success}

@app.post("/api/devices/{serial}/config")
async def update_device_config(serial: str, req: AliasUpdateRequest):
    adb_manager.update_device_config(serial, req.alias, req.color_tag)
    return {"success": True}

@app.post("/api/devices/{serial}/scrcpy")
async def launch_scrcpy(serial: str):
    success = adb_manager.launch_scrcpy(serial)
    return {"success": success}

@app.post("/api/devices/{serial}/rotate")
async def device_rotate(serial: str):
    success = await adb_manager.rotate_screen(serial)
    return {"success": success}

# --- Single Device Actions ---

@app.post("/api/devices/{serial}/tap")
async def device_tap(serial: str, req: TapRequest):
    success = await adb_manager.tap(serial, req.x, req.y)
    return {"success": success}

@app.post("/api/devices/{serial}/swipe")
async def device_swipe(serial: str, req: SwipeRequest):
    success = await adb_manager.swipe(serial, req.x1, req.y1, req.x2, req.y2, req.duration_ms)
    return {"success": success}

@app.post("/api/devices/{serial}/keyevent")
async def device_keyevent(serial: str, keycode: int):
    success = await adb_manager.keyevent(serial, keycode)
    return {"success": success}

@app.post("/api/devices/{serial}/text")
async def device_text(serial: str, req: TextRequest):
    success = await adb_manager.send_text(serial, req.text)
    return {"success": success}

# --- Broadcast Actions ---

@app.post("/api/broadcast/tap")
async def broadcast_tap(req: BroadcastTapRequest):
    ref_res = (req.ref_width, req.ref_height) if req.ref_width and req.ref_height else None
    await adb_manager.broadcast_tap(req.serials, req.x, req.y, ref_res)
    return {"success": True}

@app.post("/api/broadcast/swipe")
async def broadcast_swipe(req: BroadcastSwipeRequest):
    ref_res = (req.ref_width, req.ref_height) if req.ref_width and req.ref_height else None
    await adb_manager.broadcast_swipe(req.serials, req.x1, req.y1, req.x2, req.y2, req.duration_ms, ref_res)
    return {"success": True}

@app.post("/api/broadcast/keyevent")
async def broadcast_keyevent(req: BroadcastKeyeventRequest):
    await adb_manager.broadcast_keyevent(req.serials, req.keycode)
    return {"success": True}

@app.post("/api/broadcast/text")
async def broadcast_text(req: BroadcastTextRequest):
    await adb_manager.broadcast_text(req.serials, req.text)
    return {"success": True}

@app.post("/api/broadcast/navigation")
async def broadcast_navigation(req: BroadcastNavRequest):
    action_map = {
        "home": 3,
        "back": 4,
        "recent": 187,
        "power": 26,
        "wake": 224,
        "vol_up": 24,
        "vol_down": 25
    }
    keycode = action_map.get(req.action.lower())
    if keycode:
        await adb_manager.broadcast_keyevent(req.serials, keycode)
        return {"success": True}
    raise HTTPException(status_code=400, detail="Unknown navigation action")

# --- Automation Endpoints ---

@app.post("/api/automation/auto_scroll/start")
async def start_auto_scroll(req: AutoScrollRequest):
    result = await automation_engine.start_auto_scroller(
        req.serials,
        req.min_delay,
        req.max_delay,
        req.auto_like_prob
    )
    return {"success": True, "task": result}

@app.post("/api/automation/auto_scroll/stop")
async def stop_auto_scroll():
    success = automation_engine.stop_task("auto_scroller")
    return {"success": success}

@app.get("/api/automation/status")
async def get_automation_status():
    return {"tasks": automation_engine.get_all_tasks()}

# --- WebSockets ---

@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    await websocket.accept()
    event_subscribers.append(websocket)
    try:
        # Send initial device list
        devices = list(adb_manager.devices.values())
        await websocket.send_json({
            "type": "devices_changed",
            "data": {"devices": [d.to_dict() for d in devices]}
        })
        while True:
            # Keep alive and listen for client heartbeats/messages
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in event_subscribers:
            event_subscribers.remove(websocket)

@app.websocket("/ws/stream/{serial}")
async def websocket_stream(websocket: WebSocket, serial: str):
    await websocket.accept()
    await stream_manager.connect_client(serial, websocket)
    try:
        while True:
            # Client can send interactive touch events over the same stream socket
            data = await websocket.receive_json()
            evt_type = data.get("type")
            if evt_type == "tap":
                await adb_manager.tap(serial, data["x"], data["y"])
            elif evt_type == "swipe":
                await adb_manager.swipe(serial, data["x1"], data["y1"], data["x2"], data["y2"], data.get("duration_ms", 300))
            elif evt_type == "keyevent":
                await adb_manager.keyevent(serial, data["keycode"])
    except WebSocketDisconnect:
        await stream_manager.disconnect_client(serial, websocket)
    except Exception as e:
        logger.error(f"Stream WS error for {serial}: {e}")
        await stream_manager.disconnect_client(serial, websocket)
