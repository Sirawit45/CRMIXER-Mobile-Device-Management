import asyncio
import logging
import random
from typing import List, Dict, Optional
from app.adb_manager import ADBManager

logger = logging.getLogger("AutomationEngine")

class AutomationTask:
    def __init__(self, name: str, serials: List[str]):
        self.name = name
        self.serials = serials
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.count = 0
        self.status_message = "Ready"

    def to_dict(self):
        return {
            "name": self.name,
            "serials": self.serials,
            "running": self.running,
            "count": self.count,
            "status": self.status_message
        }

class AutomationEngine:
    def __init__(self, adb_manager: ADBManager):
        self.adb = adb_manager
        self.active_tasks: Dict[str, AutomationTask] = {}

    def is_task_running(self, task_name: str) -> bool:
        task = self.active_tasks.get(task_name)
        return task.running if task else False

    async def start_auto_scroller(
        self,
        serials: List[str],
        min_delay: float = 4.0,
        max_delay: float = 12.0,
        auto_like_prob: float = 0.2
    ):
        """Starts automated video scrolling (TikTok / Shorts / Reels) across selected devices."""
        task_id = "auto_scroller"
        if task_id in self.active_tasks and self.active_tasks[task_id].running:
            self.stop_task(task_id)

        task = AutomationTask("TikTok / Reels Auto-Scroller", serials)
        task.running = True
        self.active_tasks[task_id] = task

        async def _scroller_worker():
            logger.info(f"Auto-scroller started on devices: {serials}")
            task.status_message = f"Running on {len(serials)} device(s)..."
            try:
                while task.running:
                    # Random delay to simulate human watch time
                    delay = random.uniform(min_delay, max_delay)
                    task.status_message = f"Watching video (waiting {delay:.1f}s)... [Iter: {task.count}]"
                    await asyncio.sleep(delay)

                    if not task.running:
                        break

                    # Random like if enabled
                    if random.random() < auto_like_prob:
                        task.status_message = "Random double-tap like..."
                        for s in serials:
                            dev = self.adb.devices.get(s)
                            w, h = dev.resolution if dev else (1080, 2400)
                            cx, cy = w // 2 + random.randint(-50, 50), h // 2 + random.randint(-50, 50)
                            # Double tap
                            await self.adb.tap(s, cx, cy)
                            await asyncio.sleep(0.1)
                            await self.adb.tap(s, cx, cy)
                        await asyncio.sleep(0.5)

                    # Swipe up with natural randomization
                    task.status_message = "Swiping to next video..."
                    for s in serials:
                        dev = self.adb.devices.get(s)
                        w, h = dev.resolution if dev else (1080, 2400)
                        start_x = w // 2 + random.randint(-40, 40)
                        start_y = int(h * 0.75) + random.randint(-30, 30)
                        end_x = start_x + random.randint(-20, 20)
                        end_y = int(h * 0.25) + random.randint(-30, 30)
                        duration = random.randint(220, 350)
                        asyncio.create_task(self.adb.swipe(s, start_x, start_y, end_x, end_y, duration))

                    task.count += 1
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Auto-scroller error: {e}")
                task.status_message = f"Error: {e}"
            finally:
                task.running = False
                task.status_message = "Stopped"
                logger.info("Auto-scroller stopped")

        task.task = asyncio.create_task(_scroller_worker())
        return task.to_dict()

    def stop_task(self, task_id: str):
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            task.running = False
            if task.task:
                task.task.cancel()
                task.task = None
            task.status_message = "Stopped"
            return True
        return False

    def get_all_tasks(self) -> Dict[str, dict]:
        return {tid: t.to_dict() for tid, t in self.active_tasks.items()}

    async def install_apk(self, serials: List[str], apk_path: str) -> Dict[str, str]:
        """Installs an APK across multiple devices concurrently."""
        results = {}
        for s in serials:
            code, stdout, stderr = await self.adb.run_adb(["-s", s, "install", "-r", apk_path])
            results[s] = "Success" if code == 0 else f"Failed: {stderr or stdout}"
        return results

    async def launch_package(self, serials: List[str], package_name: str):
        """Launches an app package on multiple devices."""
        for s in serials:
            await self.adb.run_adb(["-s", s, "shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"])

    async def stop_package(self, serials: List[str], package_name: str):
        """Force stops an app package on multiple devices."""
        for s in serials:
            await self.adb.run_adb(["-s", s, "shell", "am", "force-stop", package_name])
