/**
 * CRMIXER Mobile Device Management - Client Controller
 */

// Application State
const state = {
  devices: [],
  selectedSerials: new Set(),
  masterSerial: null,
  masterSyncEnabled: false,
  streamSockets: new Map(), // serial -> WebSocket
  canvases: new Map(),      // serial -> HTMLCanvasElement
  fpsCounters: new Map(),   // serial -> { count, lastTime, fps }
  gridLayout: 'auto',
  colorPalette: ["#06b6d4", "#10b981", "#8b5cf6", "#f59e0b", "#ec4899", "#3b82f6", "#14b8a6", "#f43f5e"]
};

// Initialize App
document.addEventListener("DOMContentLoaded", () => {
  initIcons();
  initEventWebSocket();
  initUIEventListeners();
  fetchDevices();
  pollAutomationStatus();
});

function initIcons() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

// --- WebSocket Event System ---

let eventSocket = null;
function initEventWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/events`;
  
  eventSocket = new WebSocket(wsUrl);

  eventSocket.onopen = () => {
    console.log("Connected to event stream");
  };

  eventSocket.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === "devices_changed") {
        updateDeviceList(msg.data.devices);
      }
    } catch (e) {
      console.error("Error parsing event WS message:", e);
    }
  };

  eventSocket.onclose = () => {
    console.warn("Event WS closed. Reconnecting in 3s...");
    setTimeout(initEventWebSocket, 3000);
  };
}

// --- Fetch & Update Devices ---

async function fetchDevices() {
  try {
    const res = await fetch("/api/devices");
    const data = await res.json();
    updateDeviceList(data.devices);
  } catch (e) {
    console.error("Failed to fetch devices:", e);
  }
}

function updateDeviceList(newDevices) {
  state.devices = newDevices;
  
  // Default select all if new devices appeared
  const currentSerials = new Set(newDevices.map(d => d.serial));
  newDevices.forEach(d => {
    if (!state.selectedSerials.has(d.serial)) {
      state.selectedSerials.add(d.serial);
    }
  });

  // Remove disconnected devices from selection
  for (let s of state.selectedSerials) {
    if (!currentSerials.has(s)) {
      state.selectedSerials.delete(s);
    }
  }

  // Ensure master is valid
  if (state.masterSerial && !currentSerials.has(state.masterSerial)) {
    state.masterSerial = null;
  }
  if (!state.masterSerial && newDevices.length > 0) {
    state.masterSerial = newDevices[0].serial;
  }

  renderHeaderStats();
  renderDevicesGrid();
}

function renderHeaderStats() {
  const count = state.devices.length;
  document.getElementById("online-count").textContent = count;
  document.getElementById("selected-count-badge").textContent = `${state.selectedSerials.size} of ${count} selected`;
}

// --- Render Devices Grid ---

function renderDevicesGrid() {
  const container = document.getElementById("devices-container");
  const emptyView = document.getElementById("empty-state-view");

  if (state.devices.length === 0) {
    container.style.display = "none";
    emptyView.style.display = "flex";
    return;
  }

  container.style.display = "grid";
  emptyView.style.display = "none";

  // Rebuild grid preserving canvas elements if possible
  const existingCards = new Map();
  container.querySelectorAll(".device-card").forEach(el => {
    existingCards.set(el.dataset.serial, el);
  });

  // Remove cards that are no longer present
  for (let [serial, cardEl] of existingCards) {
    if (!state.devices.find(d => d.serial === serial)) {
      closeStream(serial);
      cardEl.remove();
    }
  }

  // Create or update device cards
  state.devices.forEach((dev) => {
    let card = existingCards.get(dev.serial);
    if (!card) {
      card = createDeviceCard(dev);
      container.appendChild(card);
      initStream(dev.serial);
    } else {
      updateCardUI(card, dev);
    }
  });

  initIcons();
}

function createDeviceCard(dev) {
  const card = document.createElement("div");
  card.className = "device-card";
  card.dataset.serial = dev.serial;
  if (state.selectedSerials.has(dev.serial)) card.classList.add("selected");
  if (state.masterSerial === dev.serial) card.classList.add("master");

  card.innerHTML = `
    <div class="card-header">
      <div class="card-header-left">
        <input type="checkbox" class="device-checkbox" ${state.selectedSerials.has(dev.serial) ? "checked" : ""}>
        <div class="color-dot" style="background-color: ${dev.color_tag}; color: ${dev.color_tag};" title="Click to change color"></div>
        <span class="device-alias" title="Click to rename">${dev.alias}</span>
        <span class="badge ${dev.connection_type === 'WIFI' ? 'badge-wifi' : 'badge-usb'}">${dev.connection_type}</span>
        ${state.masterSerial === dev.serial ? '<span class="badge badge-master">MASTER</span>' : ''}
      </div>
      <div class="card-header-actions">
        <button class="icon-btn btn-set-master" title="Set as Master Sync Device">
          <i data-lucide="crown" style="width: 14px; height: 14px; color: ${state.masterSerial === dev.serial ? '#f59e0b' : 'inherit'};"></i>
        </button>
        <button class="icon-btn btn-card-scrcpy" title="Open Native Scrcpy 60 FPS Window">
          <i data-lucide="external-link" style="width: 14px; height: 14px;"></i>
        </button>
        <button class="icon-btn btn-card-power" title="Power / Lock">
          <i data-lucide="power" style="width: 13px; height: 13px;"></i>
        </button>
        <button class="icon-btn btn-card-rotate" title="Rotate Screen">
          <i data-lucide="rotate-cw" style="width: 13px; height: 13px;"></i>
        </button>
      </div>
    </div>
    
    <div class="screen-container">
      <canvas class="screen-canvas" width="${dev.resolution.width}" height="${dev.resolution.height}"></canvas>
      <div class="screen-placeholder" id="placeholder-${dev.serial}">
        <i data-lucide="loader" class="animate-spin" style="width: 24px; height: 24px;"></i>
        <span>Connecting Screen...</span>
      </div>
    </div>

    <div class="card-footer">
      <span class="dev-model" title="${dev.serial}">${dev.model}</span>
      <span class="dev-fps" id="fps-${dev.serial}">-- FPS</span>
      <span class="dev-res">${dev.resolution.width}x${dev.resolution.height}</span>
    </div>
  `;

  // Attach card event handlers
  setupCardEvents(card, dev);

  const canvas = card.querySelector("canvas");
  state.canvases.set(dev.serial, canvas);
  setupCanvasTouchEvents(canvas, dev);

  return card;
}

function updateCardUI(card, dev) {
  card.className = `device-card ${state.selectedSerials.has(dev.serial) ? "selected" : ""} ${state.masterSerial === dev.serial ? "master" : ""}`;
  const checkbox = card.querySelector(".device-checkbox");
  if (checkbox) checkbox.checked = state.selectedSerials.has(dev.serial);

  const aliasSpan = card.querySelector(".device-alias");
  if (aliasSpan && aliasSpan.textContent !== dev.alias) aliasSpan.textContent = dev.alias;

  const dot = card.querySelector(".color-dot");
  if (dot) {
    dot.style.backgroundColor = dev.color_tag;
    dot.style.color = dev.color_tag;
  }
}

function setupCardEvents(card, dev) {
  const serial = dev.serial;

  // Checkbox toggle
  const checkbox = card.querySelector(".device-checkbox");
  checkbox.addEventListener("change", (e) => {
    if (e.target.checked) {
      state.selectedSerials.add(serial);
      card.classList.add("selected");
    } else {
      state.selectedSerials.delete(serial);
      card.classList.remove("selected");
    }
    renderHeaderStats();
  });

  // Color dot click to cycle colors
  const dot = card.querySelector(".color-dot");
  dot.addEventListener("click", async (e) => {
    e.stopPropagation();
    const currIdx = state.colorPalette.indexOf(dev.color_tag);
    const nextColor = state.colorPalette[(currIdx + 1) % state.colorPalette.length];
    dev.color_tag = nextColor;
    dot.style.backgroundColor = nextColor;
    dot.style.color = nextColor;
    card.style.borderColor = nextColor;
    await fetch(`/api/devices/${serial}/config`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ color_tag: nextColor })
    });
  });

  // Inline Rename alias (Works on Desktop App without window.prompt)
  const aliasSpan = card.querySelector(".device-alias");
  aliasSpan.addEventListener("click", (e) => {
    e.stopPropagation();
    const currentName = dev.alias;
    const input = document.createElement("input");
    input.type = "text";
    input.value = currentName;
    input.className = "input-control";
    input.style.width = "70px";
    input.style.padding = "1px 4px";
    input.style.fontSize = "12px";
    input.style.fontWeight = "700";
    
    aliasSpan.replaceWith(input);
    input.focus();
    input.select();

    const saveAlias = async () => {
      const newName = input.value.trim() || currentName;
      dev.alias = newName;
      aliasSpan.textContent = newName;
      input.replaceWith(aliasSpan);
      await fetch(`/api/devices/${serial}/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ alias: newName })
      });
    };

    input.addEventListener("keydown", (ke) => {
      if (ke.key === "Enter") saveAlias();
      else if (ke.key === "Escape") input.replaceWith(aliasSpan);
    });
    input.addEventListener("blur", saveAlias);
  });

  // Set as master
  const masterBtn = card.querySelector(".btn-set-master");
  masterBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    state.masterSerial = serial;
    renderDevicesGrid();
  });

  // Launch scrcpy native window (60 FPS hardware accelerated)
  const scrcpyBtn = card.querySelector(".btn-card-scrcpy");
  scrcpyBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    scrcpyBtn.style.color = "#06b6d4";
    setTimeout(() => { scrcpyBtn.style.color = "inherit"; }, 1000);
    await fetch(`/api/devices/${serial}/scrcpy`, { method: "POST" });
  });

  // Power button
  const powerBtn = card.querySelector(".btn-card-power");
  powerBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    powerBtn.style.color = "#ef4444";
    setTimeout(() => { powerBtn.style.color = "inherit"; }, 1000);
    await fetch(`/api/devices/${serial}/keyevent?keycode=26`, { method: "POST" });
  });

  // Rotate button
  const rotateBtn = card.querySelector(".btn-card-rotate");
  rotateBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    rotateBtn.style.color = "#10b981";
    setTimeout(() => { rotateBtn.style.color = "inherit"; }, 1000);
    await fetch(`/api/devices/${serial}/rotate`, { method: "POST" });
  });
}

// --- Screen Streaming via WebSockets ---

function initStream(serial) {
  if (state.streamSockets.has(serial)) return;

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/stream/${serial}`;
  const ws = new WebSocket(wsUrl);
  ws.binaryType = "blob";

  const canvas = state.canvases.get(serial);
  const ctx = canvas ? canvas.getContext("2d") : null;
  const fpsEl = document.getElementById(`fps-${serial}`);

  state.fpsCounters.set(serial, { count: 0, lastTime: performance.now(), fps: 0 });

  ws.onmessage = (event) => {
    if (event.data instanceof Blob) {
      const placeholder = document.getElementById(`placeholder-${serial}`);
      if (placeholder) {
        placeholder.style.display = "none";
      }

      const img = new Image();
      const url = URL.createObjectURL(event.data);
      img.onload = () => {
        if (canvas) {
          if (canvas.width !== img.naturalWidth || canvas.height !== img.naturalHeight) {
            canvas.width = img.naturalWidth;
            canvas.height = img.naturalHeight;
          }
          if (ctx) {
            ctx.drawImage(img, 0, 0);
          }
        }
        URL.revokeObjectURL(url);

        // Calculate FPS
        const counter = state.fpsCounters.get(serial);
        if (counter) {
          counter.count++;
          const now = performance.now();
          if (now - counter.lastTime >= 1000) {
            counter.fps = Math.round((counter.count * 1000) / (now - counter.lastTime));
            counter.count = 0;
            counter.lastTime = now;
            if (fpsEl) fpsEl.textContent = `${counter.fps} FPS`;
          }
        }
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
      };
      img.src = url;
    }
  };

  ws.onclose = () => {
    state.streamSockets.delete(serial);
    if (state.devices.find(d => d.serial === serial)) {
      setTimeout(() => initStream(serial), 2000);
    }
  };

  state.streamSockets.set(serial, ws);
}

function closeStream(serial) {
  if (state.streamSockets.has(serial)) {
    const ws = state.streamSockets.get(serial);
    ws.close();
    state.streamSockets.delete(serial);
  }
}

// --- Interactive Touch & Mouse Events ---

function setupCanvasTouchEvents(canvas, dev) {
  const serial = dev.serial;
  let isPointerDown = false;
  let startX = 0, startY = 0;
  let startTime = 0;

  function getDeviceCoordinates(e) {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const clientX = e.clientX ?? (e.touches && e.touches[0].clientX);
    const clientY = e.clientY ?? (e.touches && e.touches[0].clientY);
    const x = Math.round((clientX - rect.left) * scaleX);
    const y = Math.round((clientY - rect.top) * scaleY);
    return {
      x: Math.max(0, Math.min(canvas.width, x)),
      y: Math.max(0, Math.min(canvas.height, y))
    };
  }

  // Mouse Down
  canvas.addEventListener("mousedown", (e) => {
    if (e.button === 0) { // Left click
      isPointerDown = true;
      const coords = getDeviceCoordinates(e);
      startX = coords.x;
      startY = coords.y;
      startTime = Date.now();
    }
  });

  // Mouse Up
  canvas.addEventListener("mouseup", (e) => {
    if (!isPointerDown) return;
    isPointerDown = false;

    if (e.button === 0) {
      const coords = getDeviceCoordinates(e);
      const endX = coords.x;
      const endY = coords.y;
      const dist = Math.hypot(endX - startX, endY - startY);
      const duration = Math.max(100, Date.now() - startTime);

      if (dist < 10) {
        // Tap
        dispatchTap(serial, startX, startY, canvas.width, canvas.height);
      } else {
        // Swipe
        dispatchSwipe(serial, startX, startY, endX, endY, duration, canvas.width, canvas.height);
      }
    }
  });

  // Right Click -> Back
  canvas.addEventListener("contextmenu", (e) => {
    e.preventDefault();
    dispatchKeyevent(serial, 4); // KEYCODE_BACK
  });

  // Middle Click -> Home
  canvas.addEventListener("auxclick", (e) => {
    if (e.button === 1) {
      e.preventDefault();
      dispatchKeyevent(serial, 3); // KEYCODE_HOME
    }
  });

  // Wheel -> Scroll
  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    const coords = getDeviceCoordinates(e);
    const dy = e.deltaY;
    const distance = Math.round(canvas.height * 0.25);
    const startY = coords.y;
    const endY = dy > 0 ? Math.max(0, startY - distance) : Math.min(canvas.height, startY + distance);
    dispatchSwipe(serial, coords.x, startY, coords.x, endY, 200, canvas.width, canvas.height);
  }, { passive: false });
}

// --- Action Dispatchers (With Master-Slave Support) ---

async function dispatchTap(originSerial, x, y, refW, refH) {
  if (state.masterSyncEnabled && originSerial === state.masterSerial) {
    // Broadcast to all selected devices
    const targetSerials = Array.from(state.selectedSerials);
    await fetch("/api/broadcast/tap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        serials: targetSerials,
        x: x,
        y: y,
        ref_width: refW,
        ref_height: refH
      })
    });
  } else {
    // Single device tap
    await fetch(`/api/devices/${originSerial}/tap`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ x, y })
    });
  }
}

async function dispatchSwipe(originSerial, x1, y1, x2, y2, duration, refW, refH) {
  if (state.masterSyncEnabled && originSerial === state.masterSerial) {
    const targetSerials = Array.from(state.selectedSerials);
    await fetch("/api/broadcast/swipe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        serials: targetSerials,
        x1, y1, x2, y2,
        duration_ms: duration,
        ref_width: refW,
        ref_height: refH
      })
    });
  } else {
    await fetch(`/api/devices/${originSerial}/swipe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ x1, y1, x2, y2, duration_ms: duration })
    });
  }
}

async function dispatchKeyevent(originSerial, keycode) {
  if (state.masterSyncEnabled && originSerial === state.masterSerial) {
    const targetSerials = Array.from(state.selectedSerials);
    await fetch("/api/broadcast/keyevent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ serials: targetSerials, keycode })
    });
  } else {
    await fetch(`/api/devices/${originSerial}/keyevent?keycode=${keycode}`, { method: "POST" });
  }
}

// --- UI Controls & Event Listeners ---

function initUIEventListeners() {
  // Open Scrcpy 60 FPS for all selected devices
  const openScrcpyBtn = document.getElementById("btn-open-scrcpy-all");
  if (openScrcpyBtn) {
    openScrcpyBtn.addEventListener("click", async () => {
      const serials = Array.from(state.selectedSerials);
      if (serials.length === 0) {
        alert("Please select at least one device!");
        return;
      }
      for (let s of serials) {
        await fetch(`/api/devices/${s}/scrcpy`, { method: "POST" });
      }
    });
  }

  // Refresh Devices
  document.getElementById("btn-refresh").addEventListener("click", async () => {
    const btn = document.getElementById("btn-refresh");
    btn.innerHTML = `<i data-lucide="loader" class="animate-spin" style="width: 14px; height: 14px;"></i> Scanning...`;
    initIcons();
    await fetch("/api/devices/refresh", { method: "POST" });
    await fetchDevices();
    btn.innerHTML = `<i data-lucide="refresh-cw" style="width: 14px; height: 14px;"></i> Refresh`;
    initIcons();
  });

  // Select All / Clear
  document.getElementById("btn-select-all").addEventListener("click", () => {
    state.devices.forEach(d => state.selectedSerials.add(d.serial));
    document.querySelectorAll(".device-card").forEach(c => {
      c.classList.add("selected");
      c.querySelector(".device-checkbox").checked = true;
    });
    renderHeaderStats();
  });

  document.getElementById("btn-clear-selection").addEventListener("click", () => {
    state.selectedSerials.clear();
    document.querySelectorAll(".device-card").forEach(c => {
      c.classList.remove("selected");
      c.querySelector(".device-checkbox").checked = false;
    });
    renderHeaderStats();
  });

  // Master Sync Toggle
  const syncToggle = document.getElementById("master-sync-toggle");
  syncToggle.addEventListener("change", (e) => {
    state.masterSyncEnabled = e.target.checked;
    const banner = document.getElementById("devices-online-badge");
    if (state.masterSyncEnabled) {
      banner.style.borderColor = "#f59e0b";
      banner.style.color = "#f59e0b";
    } else {
      banner.style.borderColor = "rgba(16,185,129,0.3)";
      banner.style.color = "#10b981";
    }
  });

  // Navigation Buttons
  document.querySelectorAll(".btn-nav").forEach(btn => {
    btn.addEventListener("click", async () => {
      const action = btn.dataset.nav;
      const serials = Array.from(state.selectedSerials);
      if (serials.length === 0) return;
      await fetch("/api/broadcast/navigation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ serials, action })
      });
    });
  });

  // Broadcast Text
  document.getElementById("btn-broadcast-text").addEventListener("click", async () => {
    const input = document.getElementById("broadcast-text-input");
    const text = input.value;
    const serials = Array.from(state.selectedSerials);
    if (!text || serials.length === 0) return;
    await fetch("/api/broadcast/text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ serials, text })
    });
  });

  // Broadcast Tap
  document.getElementById("btn-broadcast-tap").addEventListener("click", async () => {
    const x = parseInt(document.getElementById("tap-x").value) || 360;
    const y = parseInt(document.getElementById("tap-y").value) || 640;
    const serials = Array.from(state.selectedSerials);
    if (serials.length === 0) return;
    await fetch("/api/broadcast/tap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ serials, x, y, ref_width: 720, ref_height: 1600 })
    });
  });

  // Broadcast Swipe
  document.getElementById("btn-broadcast-swipe").addEventListener("click", async () => {
    const x1 = parseInt(document.getElementById("swipe-x1").value) || 360;
    const y1 = parseInt(document.getElementById("swipe-y1").value) || 900;
    const x2 = parseInt(document.getElementById("swipe-x2").value) || 360;
    const y2 = parseInt(document.getElementById("swipe-y2").value) || 300;
    const duration = parseInt(document.getElementById("swipe-dur").value) || 300;
    const serials = Array.from(state.selectedSerials);
    if (serials.length === 0) return;
    await fetch("/api/broadcast/swipe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ serials, x1, y1, x2, y2, duration_ms: duration, ref_width: 720, ref_height: 1600 })
    });
  });

  // Swipe Presets
  document.querySelectorAll(".btn-preset-swipe").forEach(btn => {
    btn.addEventListener("click", async () => {
      const preset = btn.dataset.preset;
      let x1 = 360, y1 = 900, x2 = 360, y2 = 300;
      if (preset === "up") { x1 = 360; y1 = 900; x2 = 360; y2 = 250; }
      else if (preset === "down") { x1 = 360; y1 = 300; x2 = 360; y2 = 950; }
      else if (preset === "left") { x1 = 600; y1 = 600; x2 = 100; y2 = 600; }
      else if (preset === "right") { x1 = 100; y1 = 600; x2 = 600; y2 = 600; }

      const serials = Array.from(state.selectedSerials);
      if (serials.length === 0) return;
      await fetch("/api/broadcast/swipe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ serials, x1, y1, x2, y2, duration_ms: 280, ref_width: 720, ref_height: 1600 })
      });
    });
  });

  // Grid Layout Selector
  const gridSelect = document.getElementById("grid-layout-select");
  gridSelect.addEventListener("change", (e) => {
    const val = e.target.value;
    const container = document.getElementById("devices-container");
    container.className = `devices-grid grid-${val}`;
  });

  // Auto Double-Tap Like Slider
  const likeSlider = document.getElementById("auto-like-prob");
  likeSlider.addEventListener("input", (e) => {
    document.getElementById("like-prob-text").textContent = `${e.target.value}%`;
  });

  // TikTok Bot Start / Stop
  document.getElementById("btn-start-auto").addEventListener("click", async () => {
    const minDelay = parseFloat(document.getElementById("auto-min-delay").value) || 4.0;
    const maxDelay = parseFloat(document.getElementById("auto-max-delay").value) || 10.0;
    const prob = (parseInt(likeSlider.value) || 20) / 100.0;
    const serials = Array.from(state.selectedSerials);
    if (serials.length === 0) {
      alert("Please select at least one device first!");
      return;
    }
    await fetch("/api/automation/auto_scroll/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ serials, min_delay: minDelay, max_delay: maxDelay, auto_like_prob: prob })
    });
    pollAutomationStatus();
  });

  document.getElementById("btn-stop-auto").addEventListener("click", async () => {
    await fetch("/api/automation/auto_scroll/stop", { method: "POST" });
    pollAutomationStatus();
  });

  // Wi-Fi Connect Modal
  const modal = document.getElementById("wifi-modal");
  document.getElementById("btn-wifi-modal").addEventListener("click", () => {
    modal.style.display = "flex";
  });
  document.getElementById("btn-close-wifi-modal").addEventListener("click", () => {
    modal.style.display = "none";
  });
  document.getElementById("btn-submit-wifi-connect").addEventListener("click", async () => {
    const ipPort = document.getElementById("wifi-ip-input").value.trim();
    if (!ipPort) return;
    const res = await fetch("/api/devices/connect_wifi", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ip_port: ipPort })
    });
    const data = await res.json();
    alert(data.message || (data.success ? "Connected successfully!" : "Connection failed"));
    modal.style.display = "none";
    await fetchDevices();
  });
  document.getElementById("btn-submit-wifi-disconnect").addEventListener("click", async () => {
    const ipPort = document.getElementById("wifi-ip-input").value.trim();
    if (!ipPort) return;
    await fetch("/api/devices/disconnect_wifi", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ip_port: ipPort })
    });
    modal.style.display = "none";
    await fetchDevices();
  });
}

// --- Automation Status Polling ---

async function pollAutomationStatus() {
  try {
    const res = await fetch("/api/automation/status");
    const data = await res.json();
    const task = data.tasks && data.tasks.auto_scroller;
    const statusText = document.getElementById("bot-status-text");
    if (task && task.running) {
      statusText.innerHTML = `<span style="color: #10b981;">● RUNNING:</span> ${task.status}`;
      setTimeout(pollAutomationStatus, 2000);
    } else {
      statusText.textContent = "Status: Ready";
    }
  } catch (e) {
    // Ignore polling errors
  }
}
