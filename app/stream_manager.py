import asyncio
import io
import logging
import time
import subprocess
import cv2
import numpy as np
from typing import Dict, Set, Optional
from fastapi import WebSocket
from app.adb_manager import ADBManager

logger = logging.getLogger("StreamManager")

class DeviceStreamer:
    def __init__(self, serial: str, adb_manager: ADBManager, target_fps: int = 15, quality: int = 60, target_width: int = 480):
        self.serial = serial
        self.adb = adb_manager
        self.target_fps = target_fps
        self.quality = quality
        self.target_width = target_width
        self.clients: Set[WebSocket] = set()
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.last_frame: Optional[bytes] = None
        self.fps_actual = 0.0

    async def add_client(self, ws: WebSocket):
        self.clients.add(ws)
        # Send immediately cached frame if available
        if self.last_frame:
            try:
                await ws.send_bytes(self.last_frame)
            except Exception:
                pass

        if not self.running:
            self.running = True
            self.task = asyncio.create_task(self._capture_loop())

    async def remove_client(self, ws: WebSocket):
        self.clients.discard(ws)
        if len(self.clients) == 0:
            self.running = False
            if self.task:
                self.task.cancel()
                self.task = None

    def _capture_single_frame(self) -> Optional[bytes]:
        """Captures a single frame using fast raw screencap, falling back to PNG screencap."""
        # 1. Try raw screencap (Fastest: ~0.5s-0.7s)
        try:
            cmd = [self.adb.adb_path, "-s", self.serial, "exec-out", "screencap"]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=4.0)
            if res.returncode == 0 and len(res.stdout) > 16:
                header = res.stdout[:16]
                w = int.from_bytes(header[0:4], 'little')
                h = int.from_bytes(header[4:8], 'little')
                expected_len = 16 + w * h * 4
                if len(res.stdout) >= expected_len:
                    raw_pixels = res.stdout[16:expected_len]
                    rgba = np.frombuffer(raw_pixels, dtype=np.uint8).reshape((h, w, 4))
                    if self.target_width and w > self.target_width:
                        scale = self.target_width / w
                        new_h = int(h * scale)
                        small = cv2.resize(rgba, (self.target_width, new_h), interpolation=cv2.INTER_AREA)
                        bgr = cv2.cvtColor(small, cv2.COLOR_RGBA2BGR)
                    else:
                        bgr = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)

                    _, jpeg = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
                    return jpeg.tobytes()
        except Exception as e:
            logger.debug(f"Raw screencap failed for {self.serial}: {e}")

        # 2. Fallback to screencap -p (PNG)
        try:
            cmd = [self.adb.adb_path, "-s", self.serial, "exec-out", "screencap", "-p"]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=6.0)
            if res.returncode == 0 and len(res.stdout) > 100:
                nparr = np.frombuffer(res.stdout, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is not None:
                    h, w = img.shape[:2]
                    if self.target_width and w > self.target_width:
                        scale = self.target_width / w
                        new_h = int(h * scale)
                        img = cv2.resize(img, (self.target_width, new_h), interpolation=cv2.INTER_AREA)
                    _, jpeg = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
                    return jpeg.tobytes()
        except Exception as e:
            logger.error(f"PNG screencap fallback failed for {self.serial}: {e}")

        return None

    async def _capture_loop(self):
        """Asynchronously captures screen frames and broadcasts to WebSocket clients."""
        logger.info(f"Started screen capture loop for {self.serial}")
        frame_count = 0
        fps_timer = time.time()
        loop = asyncio.get_running_loop()

        while self.running:
            start_time = time.time()
            try:
                # Capture frame in executor thread
                jpeg_bytes = await loop.run_in_executor(None, self._capture_single_frame)

                if jpeg_bytes and len(jpeg_bytes) > 0:
                    self.last_frame = jpeg_bytes

                    dead_clients = set()
                    for client in list(self.clients):
                        try:
                            await client.send_bytes(jpeg_bytes)
                        except Exception:
                            dead_clients.add(client)

                    for dead in dead_clients:
                        self.clients.discard(dead)

                    frame_count += 1
                    now = time.time()
                    if now - fps_timer >= 1.0:
                        self.fps_actual = frame_count / (now - fps_timer)
                        frame_count = 0
                        fps_timer = now

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in capture loop for {self.serial}: {e}")
                await asyncio.sleep(0.5)

            # Minimal sleep to allow other async tasks
            elapsed = time.time() - start_time
            sleep_time = max(0.01, (1.0 / self.target_fps) - elapsed)
            await asyncio.sleep(sleep_time)

        logger.info(f"Stopped screen capture loop for {self.serial}")

class StreamManager:
    def __init__(self, adb_manager: ADBManager):
        self.adb = adb_manager
        self.streamers: Dict[str, DeviceStreamer] = {}

    def get_streamer(self, serial: str) -> DeviceStreamer:
        if serial not in self.streamers:
            self.streamers[serial] = DeviceStreamer(serial, self.adb)
        return self.streamers[serial]

    async def connect_client(self, serial: str, ws: WebSocket):
        streamer = self.get_streamer(serial)
        await streamer.add_client(ws)

    async def disconnect_client(self, serial: str, ws: WebSocket):
        if serial in self.streamers:
            await self.streamers[serial].remove_client(ws)
