import asyncio
import os
import re
import subprocess
import json
import logging
from typing import List, Dict, Optional, Tuple, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ADBManager")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def find_adb_path() -> str:
    """Locates the ADB executable in bundled dirs or system path."""
    candidates = [
        os.path.join(BASE_DIR, "bin", "scrcpy", "adb.exe"),
        os.path.join(BASE_DIR, "bin", "platform-tools", "adb.exe"),
        "adb.exe",
        "adb"
    ]
    for path in candidates:
        if os.path.exists(path):
            return os.path.abspath(path)
    # Check PATH
    try:
        res = subprocess.run(["adb", "version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            return "adb"
    except Exception:
        pass
    return candidates[0]

def find_scrcpy_path() -> Optional[str]:
    """Locates the Scrcpy executable."""
    candidates = [
        os.path.join(BASE_DIR, "bin", "scrcpy", "scrcpy.exe"),
        "scrcpy.exe",
        "scrcpy"
    ]
    for path in candidates:
        if os.path.exists(path):
            return os.path.abspath(path)
    return None

class DeviceInfo:
    def __init__(
        self,
        serial: str,
        state: str,
        model: str = "Android Device",
        product: str = "",
        device: str = "",
        transport_id: str = "",
        connection_type: str = "USB",
        alias: str = "",
        color_tag: str = "#06b6d4", # Default cyan
        resolution: Tuple[int, int] = (1080, 2400)
    ):
        self.serial = serial
        self.state = state
        self.model = model
        self.product = product
        self.device = device
        self.transport_id = transport_id
        self.connection_type = connection_type
        self.alias = alias or serial
        self.color_tag = color_tag
        self.resolution = resolution

    def to_dict(self) -> Dict[str, Any]:
        return {
            "serial": self.serial,
            "state": self.state,
            "model": self.model,
            "product": self.product,
            "device": self.device,
            "transport_id": self.transport_id,
            "connection_type": self.connection_type,
            "alias": self.alias,
            "color_tag": self.color_tag,
            "resolution": {"width": self.resolution[0], "height": self.resolution[1]}
        }

class ADBManager:
    def __init__(self):
        self.adb_path = find_adb_path()
        self.scrcpy_path = find_scrcpy_path()
        self.devices: Dict[str, DeviceInfo] = {}
        self.alias_file = os.path.join(BASE_DIR, "device_config.json")
        self.device_aliases = self._load_device_configs()
        logger.info(f"Initialized ADBManager using ADB at: {self.adb_path}")
        logger.info(f"Scrcpy path: {self.scrcpy_path}")

    def _load_device_configs(self) -> Dict[str, Dict[str, str]]:
        if os.path.exists(self.alias_file):
            try:
                with open(self.alias_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading device_config.json: {e}")
        return {}

    def _save_device_configs(self):
        try:
            with open(self.alias_file, "w", encoding="utf-8") as f:
                json.dump(self.device_aliases, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving device_config.json: {e}")

    async def run_adb(self, args: List[str], timeout: float = 10.0) -> Tuple[int, str, str]:
        """Runs an ADB command asynchronously."""
        cmd = [self.adb_path] + args
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return proc.returncode, stdout.decode("utf-8", errors="ignore"), stderr.decode("utf-8", errors="ignore")
        except asyncio.TimeoutError:
            logger.error(f"ADB command timed out: {' '.join(cmd)}")
            return -1, "", "Timeout"
        except Exception as e:
            logger.error(f"ADB execution error: {e}")
            return -1, "", str(e)

    def run_adb_sync(self, args: List[str], timeout: float = 10.0) -> Tuple[int, bytes, bytes]:
        """Runs a synchronous ADB command (useful for raw byte streams/screencap)."""
        cmd = [self.adb_path] + args
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout
            )
            return res.returncode, res.stdout, res.stderr
        except Exception as e:
            return -1, b"", str(e).encode()

    async def refresh_devices(self) -> List[DeviceInfo]:
        """Scans for connected Android devices via ADB."""
        code, stdout, stderr = await self.run_adb(["devices", "-l"])
        if code != 0:
            logger.error(f"Failed to list devices: {stderr}")
            return list(self.devices.values())

        lines = stdout.strip().split("\n")
        discovered: Dict[str, DeviceInfo] = {}
        index = 1

        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            serial = parts[0]
            state = parts[1]

            # Parse metadata
            model = "Android"
            product = ""
            device_name = ""
            transport_id = ""

            for part in parts[2:]:
                if part.startswith("model:"):
                    model = part.split(":", 1)[1].replace("_", " ")
                elif part.startswith("product:"):
                    product = part.split(":", 1)[1]
                elif part.startswith("device:"):
                    device_name = part.split(":", 1)[1]
                elif part.startswith("transport_id:"):
                    transport_id = part.split(":", 1)[1]

            conn_type = "WIFI" if ":" in serial else "USB"

            # Check saved alias / tag
            config = self.device_aliases.get(serial, {})
            alias = config.get("alias", f"MD{index}")
            color_tag = config.get("color_tag", self._get_default_color(index))

            dev_info = DeviceInfo(
                serial=serial,
                state=state,
                model=model,
                product=product,
                device=device_name,
                transport_id=transport_id,
                connection_type=conn_type,
                alias=alias,
                color_tag=color_tag
            )

            # Detect resolution
            if state == "device":
                res = await self.get_device_resolution(serial)
                dev_info.resolution = res

            discovered[serial] = dev_info
            index += 1

        self.devices = discovered
        return list(self.devices.values())

    def _get_default_color(self, index: int) -> str:
        colors = ["#06b6d4", "#10b981", "#8b5cf6", "#f59e0b", "#ec4899", "#3b82f6", "#14b8a6", "#f43f5e"]
        return colors[(index - 1) % len(colors)]

    async def get_device_resolution(self, serial: str) -> Tuple[int, int]:
        """Gets screen resolution for a device."""
        code, stdout, _ = await self.run_adb(["-s", serial, "shell", "wm", "size"])
        if code == 0:
            # Physical size: 1080x2400 or Override size: ...
            matches = re.findall(r"(\d+)x(\d+)", stdout)
            if matches:
                last_match = matches[-1]
                return int(last_match[0]), int(last_match[1])
        return (1080, 2400)

    def update_device_config(self, serial: str, alias: Optional[str] = None, color_tag: Optional[str] = None):
        """Updates alias and color tag for a device."""
        if serial not in self.device_aliases:
            self.device_aliases[serial] = {}
        if alias is not None:
            self.device_aliases[serial]["alias"] = alias
            if serial in self.devices:
                self.devices[serial].alias = alias
        if color_tag is not None:
            self.device_aliases[serial]["color_tag"] = color_tag
            if serial in self.devices:
                self.devices[serial].color_tag = color_tag
        self._save_device_configs()

    # --- Touch and Gestures ---

    async def tap(self, serial: str, x: int, y: int) -> bool:
        """Sends tap event."""
        code, _, _ = await self.run_adb(["-s", serial, "shell", "input", "tap", str(x), str(y)])
        return code == 0

    async def swipe(self, serial: str, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> bool:
        """Sends swipe event."""
        code, _, _ = await self.run_adb([
            "-s", serial, "shell", "input", "swipe",
            str(x1), str(y1), str(x2), str(y2), str(duration_ms)
        ])
        return code == 0

    async def keyevent(self, serial: str, keycode: int) -> bool:
        """Sends Android KeyEvent."""
        code, _, _ = await self.run_adb(["-s", serial, "shell", "input", "keyevent", str(keycode)])
        return code == 0

    async def send_text(self, serial: str, text: str) -> bool:
        """Sends text. If non-ASCII / Thai / emojis, uses clipboard broadcast."""
        # Check if ASCII only
        if all(ord(c) < 128 for c in text):
            # Escape shell special chars
            safe_text = text.replace(" ", "%s").replace("&", "\\&").replace("<", "\\<").replace(">", "\\>").replace("\"", "\\\"").replace("'", "\\'")
            code, _, _ = await self.run_adb(["-s", serial, "shell", "input", "text", f'"{safe_text}"'])
            return code == 0
        else:
            # For Thai / Unicode text, use clip injection / paste
            # 1. Try set clipboard via cmd clipboard
            escaped = text.replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")
            await self.run_adb(["-s", serial, "shell", "cmd", "clipboard", "set", "text", f'"{escaped}"'])
            # 2. Paste via keyevent 279 (PASTE) or Ctrl+V
            code, _, _ = await self.run_adb(["-s", serial, "shell", "input", "keyevent", "279"])
            if code != 0:
                # Fallback to keyevent 66/paste combo
                await self.run_adb(["-s", serial, "shell", "input", "keyevent", "--longpress", "279"])
            return True

    # --- Navigation Helpers ---

    async def home(self, serial: str) -> bool:
        return await self.keyevent(serial, 3) # KEYCODE_HOME

    async def back(self, serial: str) -> bool:
        return await self.keyevent(serial, 4) # KEYCODE_BACK

    async def recent_apps(self, serial: str) -> bool:
        return await self.keyevent(serial, 187) # KEYCODE_APP_SWITCH

    async def power(self, serial: str) -> bool:
        return await self.keyevent(serial, 26) # KEYCODE_POWER

    async def wake(self, serial: str) -> bool:
        return await self.keyevent(serial, 224) # KEYCODE_WAKEUP

    async def volume_up(self, serial: str) -> bool:
        return await self.keyevent(serial, 24)

    async def volume_down(self, serial: str) -> bool:
        return await self.keyevent(serial, 25)

    # --- Wi-Fi Connection Management ---

    async def enable_tcpip(self, serial: str, port: int = 5555) -> bool:
        """Enables TCP/IP mode on a USB connected device."""
        code, _, _ = await self.run_adb(["-s", serial, "tcpip", str(port)])
        return code == 0

    async def connect_wifi(self, ip_port: str) -> Tuple[bool, str]:
        """Connects to a wireless device (e.g. 192.168.1.50:5555)."""
        code, stdout, stderr = await self.run_adb(["connect", ip_port])
        success = "connected to" in stdout.lower()
        msg = stdout if stdout else stderr
        await self.refresh_devices()
        return success, msg

    async def disconnect_wifi(self, ip_port: str) -> Tuple[bool, str]:
        """Disconnects wireless device."""
        code, stdout, stderr = await self.run_adb(["disconnect", ip_port])
        await self.refresh_devices()
        return code == 0, stdout or stderr

    # --- Scrcpy Native Window Launch ---

    def launch_scrcpy(self, serial: str, title: Optional[str] = None) -> bool:
        """Launches standalone scrcpy window for a device with hardware UHID input."""
        if not self.scrcpy_path or not os.path.exists(self.scrcpy_path):
            logger.error("Scrcpy executable not found.")
            return False
        
        window_title = title or f"MDM - {self.devices.get(serial, DeviceInfo(serial, '')).alias} ({serial})"
        cmd = [
            self.scrcpy_path,
            "-s", serial,
            "--window-title", window_title,
            "--stay-awake",
            "--mouse=uhid",
            "--keyboard=uhid",
            "--max-size", "1280",
            "--video-bit-rate", "8M"
        ]
        try:
            # Launch without CREATE_NO_WINDOW so SDL creates the GUI window
            subprocess.Popen(cmd)
            return True
        except Exception as e:
            logger.error(f"Failed to launch scrcpy: {e}")
            return False

    async def rotate_screen(self, serial: str) -> bool:
        """Toggles screen orientation between Portrait (0) and Landscape (1)."""
        # Ensure WRITE_SETTINGS is granted
        await self.run_adb(["-s", serial, "shell", "appops", "set", "com.android.shell", "WRITE_SETTINGS", "allow"])
        code, stdout, _ = await self.run_adb(["-s", serial, "shell", "settings", "get", "system", "user_rotation"])
        current_rot = 0
        try:
            current_rot = int(stdout.strip())
        except Exception:
            pass
        
        next_rot = 1 if current_rot == 0 else 0
        # Disable auto-rotate first
        await self.run_adb(["-s", serial, "shell", "settings", "put", "system", "accelerometer_rotation", "0"])
        # Set new rotation
        code, _, _ = await self.run_adb(["-s", serial, "shell", "settings", "put", "system", "user_rotation", str(next_rot)])
        return code == 0

    # --- Broadcast Actions to Multiple Devices ---

    async def broadcast_tap(self, serials: List[str], x: int, y: int, ref_resolution: Optional[Tuple[int, int]] = None):
        """Taps all selected devices concurrently, normalizing coordinates if resolutions differ."""
        tasks = []
        for s in serials:
            dev = self.devices.get(s)
            target_x, target_y = x, y
            if dev and ref_resolution and ref_resolution[0] > 0 and ref_resolution[1] > 0:
                scale_x = dev.resolution[0] / ref_resolution[0]
                scale_y = dev.resolution[1] / ref_resolution[1]
                target_x = int(x * scale_x)
                target_y = int(y * scale_y)
            tasks.append(self.tap(s, target_x, target_y))
        await asyncio.gather(*tasks)

    async def broadcast_swipe(
        self,
        serials: List[str],
        x1: int, y1: int,
        x2: int, y2: int,
        duration_ms: int = 300,
        ref_resolution: Optional[Tuple[int, int]] = None
    ):
        """Swipes all selected devices concurrently."""
        tasks = []
        for s in serials:
            dev = self.devices.get(s)
            tx1, ty1, tx2, ty2 = x1, y1, x2, y2
            if dev and ref_resolution and ref_resolution[0] > 0 and ref_resolution[1] > 0:
                scale_x = dev.resolution[0] / ref_resolution[0]
                scale_y = dev.resolution[1] / ref_resolution[1]
                tx1 = int(x1 * scale_x)
                ty1 = int(y1 * scale_y)
                tx2 = int(x2 * scale_x)
                ty2 = int(y2 * scale_y)
            tasks.append(self.swipe(s, tx1, ty1, tx2, ty2, duration_ms))
        await asyncio.gather(*tasks)

    async def broadcast_keyevent(self, serials: List[str], keycode: int):
        """Sends keyevent to all selected devices."""
        tasks = [self.keyevent(s, keycode) for s in serials]
        await asyncio.gather(*tasks)

    async def broadcast_text(self, serials: List[str], text: str):
        """Sends text to all selected devices."""
        tasks = [self.send_text(s, text) for s in serials]
        await asyncio.gather(*tasks)
