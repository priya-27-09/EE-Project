// ** Restored wizard.js from backup **
/**
 * AI Civic Guardian — Complaint Registration Wizard Controller
 */

// Mapping of deterministic backend departments for live UI preview
const ISSUE_DEPT_MAP = {
  pothole: "Roads & Highways",
  damaged_road: "Roads & Highways",
  garbage_overflow: "Solid Waste Management",
  illegal_dumping: "Solid Waste Management",
  water_leakage: "Water Supply & Sewerage",
  sewage_overflow: "Water Supply & Sewerage",
  broken_street_light: "Electricity & Street Lighting",
  drainage_problem: "Drainage & Flood Management",
  traffic_issue: "Traffic & Transportation",
  building_damage: "Building & Construction",
  park_damage: "Parks & Public Spaces",
  environmental_pollution: "Environmental Protection",
};

const ISSUE_LABELS = {
  pothole: "Pothole",
  damaged_road: "Damaged Road",
  garbage_overflow: "Garbage Overflow",
  illegal_dumping: "Illegal Dumping",
  water_leakage: "Water Leakage",
  sewage_overflow: "Sewage Overflow",
  broken_street_light: "Broken Street Light",
  drainage_problem: "Drainage Problem",
  traffic_issue: "Traffic Issue",
  building_damage: "Building Damage",
  park_damage: "Park / Public Space",
  environmental_pollution: "Environmental Pollution",
};

// Wizard State Object
const WizardState = {
  currentStep: 1,
  evidenceFile: null,
  latitude: null,
  longitude: null,
  accuracy: null,
  location_source: null,
  place_name: null,
  address: null,
  description: "",
  language: "en",
  issueType: null,
  createdComplaintId: null,
  aiResult: null,
  aiStatus: "IDLE", // IDLE, UPLOADING, VALIDATING, PROCESSING, SUCCESS, MULTIPLE, NO_DETECTION, UNAVAILABLE, ERROR
};

// Enforce citizen authentication before accessing wizard
if (!ApiClient.isAuthenticated()) {
  window.location.href = "/login?next=/complaints/new";
}

function showWizardAlert(msg, type = "danger") {
  const box = document.getElementById("wizard-alert");
  if (box) {
    box.className = `alert alert-${type}`;
    box.textContent = msg;
    box.style.display = "block";
    box.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

function hideWizardAlert() {
  const box = document.getElementById("wizard-alert");
  if (box) box.style.display = "none";
}

function resetAIBoxes() {
  const loadingBox = document.getElementById("ai-loading-box");
  const resultBox = document.getElementById("ai-result-box");
  const unavailBox = document.getElementById("ai-unavailable-box");
  const noDetBox = document.getElementById("ai-no-detection-box");
  const errBox = document.getElementById("ai-error-box");
  const multBox = document.getElementById("ai-multiple-detections-box");
  const demoBadge = document.getElementById("ai-demo-badge");
  const unvalidatedBox = document.getElementById("ai-unvalidated-class-box");
  const demoTriggerBox = document.getElementById("demo-inference-trigger-box");

  if (loadingBox) loadingBox.style.display = "none";
  if (resultBox) resultBox.style.display = "none";
  if (unavailBox) unavailBox.style.display = "none";
  if (noDetBox) noDetBox.style.display = "none";
  if (errBox) errBox.style.display = "none";
  if (multBox) multBox.style.display = "none";
  if (demoBadge) demoBadge.style.display = "none";
  if (unvalidatedBox) unvalidatedBox.style.display = "none";
  if (demoTriggerBox) demoTriggerBox.style.display = "none";
}

async function triggerAIDetection(file) {
  if (!file) {
    resetAIBoxes();
    const unavail = document.getElementById("ai-unavailable-box");
    if (unavail) {
      unavail.style.display = "flex";
      const msg = document.getElementById("ai-unavailable-msg");
      if (msg) msg.textContent = "No photographic evidence provided. Please choose a category manually below.";
    }
    return;
  }

  const ext = file.name.split(".").pop().toLowerCase();
  const isImage = ["jpg", "jpeg", "png", "webp", "bmp"].includes(ext);
  if (!isImage) {
    resetAIBoxes();
    const unavail = document.getElementById("ai-unavailable-box");
    if (unavail) {
      unavail.style.display = "flex";
      const msg = document.getElementById("ai-unavailable-msg");
      if (msg) msg.textContent = `Uploaded evidence file (${ext.toUpperCase()}) is not an image. AI object detection operates on image evidence. Please select a category manually below.`;
    }
    return;
  }

  resetAIBoxes();
  const loadingBox = document.getElementById("ai-loading-box");
  const loadingMsg = document.getElementById("ai-loading-msg");

  // State 1: Uploading
  WizardState.aiStatus = "UPLOADING";
  if (loadingBox) loadingBox.style.display = "block";
  if (loadingMsg) loadingMsg.textContent = "Uploading image evidence to secure AI gateway...";

  // State 2: Validating
  await new Promise((r) => setTimeout(r, 200));
  WizardState.aiStatus = "VALIDATING";
  if (loadingMsg) loadingMsg.textContent = "Validating image raster & integrity constraints...";

  // State 3: Processing
  await new Promise((r) => setTimeout(r, 200));
  WizardState.aiStatus = "PROCESSING";
  if (loadingMsg) loadingMsg.textContent = "Executing Ultralytics YOLO deep learning inference...";

  try {
    const res = await ApiClient.runAIInference(file);

    if (loadingBox) loadingBox.style.display = "none";

    // State: AI Model Unavailable
    if (res.error_code === "AI_MODEL_NOT_AVAILABLE") {
      WizardState.aiStatus = "UNAVAILABLE";
      WizardState.aiResult = null;
      const unavail = document.getElementById("ai-unavailable-box");
      if (unavail) {
        unavail.style.display = "flex";
        const msg = document.getElementById("ai-unavailable-msg");
        if (msg) msg.textContent = "Image uploaded successfully. Please confirm the issue category to continue.";
      }
      return;
    }

    // State: No Detection
    if (res.error_code === "AI_NO_DETECTION") {
      WizardState.aiStatus = "NO_DETECTION";
      WizardState.aiResult = null;
      const noDet = document.getElementById("ai-no-detection-box");
      if (noDet) noDet.style.display = "flex";
      return;
    }

    // State: Success
    if (res.success && res.issue) {
      WizardState.aiStatus = "SUCCESS";
      WizardState.aiResult = res;

      const resultBox = document.getElementById("ai-result-box");
      if (resultBox) resultBox.style.display = "block";

      const nameEl = document.getElementById("ai-detected-issue-name");
      if (nameEl) nameEl.textContent = res.issue.class_name;

      const confEl = document.getElementById("ai-confidence-value");
      if (confEl) confEl.textContent = `${(res.issue.confidence * 100).toFixed(1)}%`;

      const sevValEl = document.getElementById("ai-severity-value");
      if (sevValEl) sevValEl.textContent = res.severity ? res.severity.level : "MEDIUM";

      const sevPill = document.getElementById("ai-severity-pill");
      if (sevPill && res.severity) {
        sevPill.className = `ai-stat-pill pill-severity-${res.severity.level.toLowerCase()}`;
      }

      const sevReasonEl = document.getElementById("ai-severity-reason");
      if (sevReasonEl && res.severity) {
        sevReasonEl.textContent = `Risk Assessment: ${res.severity.reason || "Standard municipal response protocol"}`;
      }

      const deptValEl = document.getElementById("ai-dept-value");
      if (deptValEl && res.department) deptValEl.textContent = res.department.name;

      // State: Multiple Detections Check
      if (res.detections && res.detections.length > 1) {
        WizardState.aiStatus = "MULTIPLE";
        const multBox = document.getElementById("ai-multiple-detections-box");
        const multList = document.getElementById("ai-multiple-detections-list");
        if (multBox && multList) {
          multBox.style.display = "block";
          const otherDets = res.detections.map((d) => `${d.class_name} (${(d.confidence * 100).toFixed(1)}%)`).join(", ");
          multList.textContent = otherDets;
        }
      }

      // Pre-select detected issue in the grid for citizen confirmation
      if (res.issue.issue_type) {
        WizardState.issueType = res.issue.issue_type;
        const grid = document.getElementById("issue-selection-grid");
        if (grid) {
          grid.querySelectorAll(".issue-card-btn").forEach((card) => {
            if (card.getAttribute("data-issue") === res.issue.issue_type) {
              card.classList.add("selected");
            } else {
              card.classList.remove("selected");
            }
          });
        }
      }
    }
  } catch (err) {
    if (loadingBox) loadingBox.style.display = "none";
    WizardState.aiStatus = "ERROR";
    WizardState.aiResult = null;
    const errBox = document.getElementById("ai-error-box");
    const errMsg = document.getElementById("ai-error-msg");
    if (errBox) errBox.style.display = "flex";
    if (errMsg) errMsg.textContent = err.message || "Failed to communicate with AI inference endpoint.";
  }
}

async function triggerAIDemoDetection(file) {
  if (!file) return;

  resetAIBoxes();
  const loadingBox = document.getElementById("ai-loading-box");
  const loadingMsg = document.getElementById("ai-loading-msg");

  WizardState.aiStatus = "PROCESSING";
  if (loadingBox) loadingBox.style.display = "block";
  if (loadingMsg) loadingMsg.textContent = "Executing isolated experimental baseline demo inference (best.pt)...";

  try {
    const res = await ApiClient.runAIDemoInference(file);

    if (loadingBox) loadingBox.style.display = "none";

    if (res.error_code === "DEMO_MODE_DISABLED") {
      WizardState.aiStatus = "UNAVAILABLE";
      const errBox = document.getElementById("ai-error-box");
      const errMsg = document.getElementById("ai-error-msg");
      if (errBox) errBox.style.display = "flex";
      if (errMsg) errMsg.textContent = res.message || "Experimental baseline demo inference is currently disabled.";
      return;
    }

    if (res.error_code === "AI_NO_DETECTION") {
      WizardState.aiStatus = "NO_DETECTION";
      WizardState.aiResult = null;
      const noDet = document.getElementById("ai-no-detection-box");
      if (noDet) noDet.style.display = "flex";
      return;
    }

    if (res.success && res.issue) {
      WizardState.aiStatus = "SUCCESS";
      WizardState.aiResult = res;

      const resultBox = document.getElementById("ai-result-box");
      if (resultBox) resultBox.style.display = "block";

      const demoBadge = document.getElementById("ai-demo-badge");
      if (demoBadge) demoBadge.style.display = "inline-block";

      const unvalidatedBox = document.getElementById("ai-unvalidated-class-box");
      const unvalidatedMsg = document.getElementById("ai-unvalidated-class-msg");
      if (res.is_unvalidated_class) {
        if (unvalidatedBox) unvalidatedBox.style.display = "block";
        if (unvalidatedMsg && res.warning) unvalidatedMsg.textContent = res.warning;
      } else {
        if (unvalidatedBox) unvalidatedBox.style.display = "none";
      }

      const nameEl = document.getElementById("ai-detected-issue-name");
      if (nameEl) nameEl.textContent = res.issue.class_name;

      const confEl = document.getElementById("ai-confidence-value");
      if (confEl) confEl.textContent = `${(res.issue.confidence * 100).toFixed(1)}%`;

      const sevValEl = document.getElementById("ai-severity-value");
      if (sevValEl) sevValEl.textContent = res.severity ? res.severity.level : "MEDIUM";

      const sevPill = document.getElementById("ai-severity-pill");
      if (sevPill && res.severity) {
        sevPill.className = `ai-stat-pill pill-severity-${res.severity.level.toLowerCase()}`;
      }

      const sevReasonEl = document.getElementById("ai-severity-reason");
      if (sevReasonEl && res.severity) {
        sevReasonEl.textContent = `Risk Assessment: ${res.severity.reason || "Standard municipal response protocol"}`;
      }

      const deptValEl = document.getElementById("ai-dept-value");
      if (deptValEl && res.department) deptValEl.textContent = res.department.name;

      if (res.detections && res.detections.length > 1) {
        WizardState.aiStatus = "MULTIPLE";
        const multBox = document.getElementById("ai-multiple-detections-box");
        const multList = document.getElementById("ai-multiple-detections-list");
        if (multBox && multList) {
          multBox.style.display = "block";
          const otherDets = res.detections.map((d) => `${d.class_name} (${(d.confidence * 100).toFixed(1)}%)`).join(", ");
          multList.textContent = otherDets;
        }
      }

      if (res.issue.issue_type) {
        WizardState.issueType = res.issue.issue_type;
        const grid = document.getElementById("issue-selection-grid");
        if (grid) {
          grid.querySelectorAll(".issue-card-btn").forEach((card) => {
            if (card.getAttribute("data-issue") === res.issue.issue_type) {
              card.classList.add("selected");
            } else {
              card.classList.remove("selected");
            }
          });
        }
      }
    }
  } catch (err) {
    if (loadingBox) loadingBox.style.display = "none";
    WizardState.aiStatus = "ERROR";
    WizardState.aiResult = null;
    const errBox = document.getElementById("ai-error-box");
    const errMsg = document.getElementById("ai-error-msg");
    if (errBox) errBox.style.display = "flex";
    if (errMsg) errMsg.textContent = err.message || "Failed to communicate with AI demo inference endpoint.";
  }
}

function setWizardStep(step) {
  hideWizardAlert();
  WizardState.currentStep = step;

  // Toggle panes
  for (let i = 1; i <= 5; i++) {
    const pane = document.getElementById(`pane-step-${i}`);
    if (pane) pane.style.display = i === step ? "block" : "none";

    const navItem = document.getElementById(`step-nav-${i}`);
    if (navItem) {
      navItem.classList.remove("active", "completed");
      if (i === step) navItem.classList.add("active");
      else if (i < step) navItem.classList.add("completed");
    }
  }

  // When switching to Step 2, ensure map is properly rendered and sized
  if (step === 2) {
    setTimeout(() => {
      initWizardMap();
      if (wizardMap) {
        wizardMap.invalidateSize();
        if (WizardState.latitude && WizardState.longitude) {
          placeMapMarker(WizardState.latitude, WizardState.longitude);
        }
      }
    }, 200);
  }

  // Trigger AI analysis when moving to Step 4
  if (step === 4) {
    if (WizardState.evidenceFile) {
      const ext = WizardState.evidenceFile.name.split(".").pop().toLowerCase();
      const isImg = ["jpg", "jpeg", "png", "webp", "bmp"].includes(ext);
      if (isImg && !WizardState.aiResult) {
        triggerAIDetection(WizardState.evidenceFile);
      } else if (!isImg) {
        triggerAIDetection(null);
      }
    } else {
      triggerAIDetection(null);
    }
  }

  // Populate review on Step 5
  if (step === 5) {
    populateReviewStep();
  }

  window.scrollTo({ top: 0, behavior: "smooth" });
}

// Handle File Selection & Previews
function handleSelectedFile(file) {
  if (!file) return;

  const ext = file.name.split(".").pop().toLowerCase();
  const allowed = ["jpg", "jpeg", "png", "webp", "mp4", "webm", "mov", "avi", "wav", "mp3", "m4a"];
  if (!allowed.includes(ext)) {
    showWizardAlert(`Unsupported file extension '.${ext}'. Supported: JPG, PNG, WebP, MP4, WebM, WAV, MP3, M4A`);
    return;
  }

  // File size checks
  const isImage = ["jpg", "jpeg", "png", "webp"].includes(ext);
  const isAudio = ["wav", "mp3", "m4a"].includes(ext);
  const isVideo = ["mp4", "webm", "mov", "avi"].includes(ext);

  if (isImage && file.size > 10 * 1024 * 1024) {
    showWizardAlert("Image size exceeds 10 MB limit.");
    return;
  }
  if (isAudio && file.size > 20 * 1024 * 1024) {
    showWizardAlert("Audio size exceeds 20 MB limit.");
    return;
  }
  if (isVideo && file.size > 50 * 1024 * 1024) {
    showWizardAlert("Video size exceeds 50 MB limit.");
    return;
  }

  hideWizardAlert();
  WizardState.evidenceFile = file;

  // Render preview
  const container = document.getElementById("evidence-preview-container");
  const thumbBox = document.getElementById("preview-thumb-box");
  const filenameEl = document.getElementById("preview-filename");
  const filesizeEl = document.getElementById("preview-filesize");

  filenameEl.textContent = file.name;
  filesizeEl.textContent = `${(file.size / (1024 * 1024)).toFixed(2)} MB (${file.type || ext})`;

  thumbBox.innerHTML = "";
  if (isImage) {
    const img = document.createElement("img");
    img.className = "preview-media-thumb";
    img.src = URL.createObjectURL(file);
    thumbBox.appendChild(img);
  } else if (isVideo) {
    thumbBox.innerHTML = `<span style="font-size: 2rem;">🎥</span>`;
  } else if (isAudio) {
    thumbBox.innerHTML = `<span style="font-size: 2rem;">🎤</span>`;
  }

  container.style.display = "block";
}

function removeEvidence() {
  WizardState.evidenceFile = null;
  WizardState.aiResult = null;
  WizardState.aiStatus = "IDLE";
  document.getElementById("evidence-preview-container").style.display = "none";
  document.getElementById("input-photo").value = "";
  document.getElementById("input-video").value = "";
  document.getElementById("input-audio").value = "";
  resetAIBoxes();
}

// ── Location & Interactive Map Controller ──
let wizardMap = null;
let wizardMarker = null;
const COIMBATORE_LAT = 11.0168;
const COIMBATORE_LON = 76.9558;

function initWizardMap() {
  if (wizardMap) return wizardMap;
  const mapContainer = document.getElementById("wizard-location-map");
  if (!mapContainer || typeof L === "undefined") return null;
  try {
    wizardMap = L.map("wizard-location-map", { scrollWheelZoom: true }).setView([COIMBATORE_LAT, COIMBATORE_LON], 12);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(wizardMap);

    // Allow citizen to click directly on the map to set or move the marker
    wizardMap.on("click", function (e) {
      const lat = parseFloat(e.latlng.lat.toFixed(6));
      const lon = parseFloat(e.latlng.lng.toFixed(6));
      applySelectedLocation(lat, lon, `Pin Location (${lat}, ${lon})`, `Latitude: ${lat}, Longitude: ${lon}`, "MANUAL_MAP");
      resolveAddressForCoordinates(lat, lon);
      const markerStatus = document.getElementById("map-marker-status");
      if (markerStatus) markerStatus.textContent = `Pin placed at Lat: ${lat}, Lon: ${lon}`;
      const statusEl = document.getElementById("gps-status-message");
      if (statusEl) statusEl.innerHTML = `<span style="color: var(--success-green); font-weight: 700;">✓ Map Location Selected:</span> Latitude: ${lat}, Longitude: ${lon}`;
    });
  } catch (e) {
    console.warn("Map init failed:", e);
  }
  return wizardMap;
}

function placeMapMarker(lat, lon) {
  if (!wizardMap) initWizardMap();
  if (!wizardMap) return;
  if (wizardMarker) {
    wizardMarker.setLatLng([lat, lon]);
  } else {
    wizardMarker = L.marker([lat, lon], { draggable: true }).addTo(wizardMap);
    wizardMarker.on("dragend", function () {
      const pos = wizardMarker.getLatLng();
      const newLat = parseFloat(pos.lat.toFixed(6));
      const newLon = parseFloat(pos.lng.toFixed(6));
      applySelectedLocation(newLat, newLon, `Pin Location (${newLat}, ${newLon})`, `Latitude: ${newLat}, Longitude: ${newLon}`, "MANUAL_PIN_DRAG");
      resolveAddressForCoordinates(newLat, newLon);
      const markerStatus = document.getElementById("map-marker-status");
      if (markerStatus) markerStatus.textContent = `Pin moved to Lat: ${newLat}, Lon: ${newLon}`;
      const statusEl = document.getElementById("gps-status-message");
      if (statusEl) statusEl.innerHTML = `<span style="color: var(--success-green); font-weight: 700;">✓ Pin Position Updated:</span> Latitude: ${newLat}, Longitude: ${newLon}`;
    });
  }
  wizardMarker.bindPopup(`<b>Selected Issue Spot</b><br>Lat: ${lat}<br>Lon: ${lon}`);
  wizardMap.setView([lat, lon], Math.max(wizardMap.getZoom(), 15));
}

function applySelectedLocation(lat, lon, placeName, displayName, source = "MANUAL") {
  lat = parseFloat(Number(lat).toFixed(6));
  lon = parseFloat(Number(lon).toFixed(6));

  const latInput = document.getElementById("input-latitude");
  const lonInput = document.getElementById("input-longitude");
  if (latInput) latInput.value = lat;
  if (lonInput) lonInput.value = lon;

  WizardState.latitude = lat;
  WizardState.longitude = lon;
  WizardState.location_source = source;
  if (placeName) WizardState.place_name = placeName;
  if (displayName) WizardState.address = displayName;

  const card = document.getElementById("selected-location-card");
  if (card) {
    card.style.display = "flex";
    const nameEl = document.getElementById("selected-place-name");
    const addrEl = document.getElementById("selected-address-text");
    if (nameEl) nameEl.textContent = placeName || `Coordinates (${lat}, ${lon})`;
    if (addrEl) addrEl.textContent = displayName || `Latitude: ${lat}, Longitude: ${lon}`;
  }

  placeMapMarker(lat, lon);

  const resultsBox = document.getElementById("location-search-results-box");
  if (resultsBox) resultsBox.style.display = "none";
}

async function resolveAddressForCoordinates(lat, lon) {
  try {
    const res = await ApiClient.reverseGeocode(lat, lon);
    if (res && (res.place_name || res.display_name)) {
      const pName = res.place_name || `Area (${lat}, ${lon})`;
      const dName = res.display_name || `Latitude: ${lat}, Longitude: ${lon}`;
      WizardState.place_name = pName;
      WizardState.address = dName;
      const nameEl = document.getElementById("selected-place-name");
      const addrEl = document.getElementById("selected-address-text");
      if (nameEl) nameEl.textContent = pName;
      if (addrEl) addrEl.textContent = dName;
    }
  } catch (err) {
    // Reverse geocode failed silently; lat/lon still preserved
  }
}

// Geolocation Handling
function requestGeolocation() {
  const statusMsg = document.getElementById("gps-status-message");
  const btn = document.getElementById("btn-get-gps");

  if (!navigator.geolocation) {
    if (statusMsg) {
      statusMsg.innerHTML = `<span style="color: var(--danger-red); font-weight: 600;">⚠️ Geolocation is not supported by your browser.</span> You can enter coordinates manually or click on the map.`;
    }
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳</span> <span>Detecting GPS Location...</span>`;
  }
  if (statusMsg) {
    statusMsg.innerHTML = `<span style="color: var(--primary-navy); font-weight: 600;">📡 Requesting high-accuracy GPS coordinates from your device sensor... Please grant permission if prompted.</span>`;
  }

  const geoOptions = {
    enableHighAccuracy: true,
    timeout: 15000,
    maximumAge: 0,
  };

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = `📍 <span>Use My Current Location</span>`;
      }
      const lat = parseFloat(pos.coords.latitude.toFixed(6));
      const lon = parseFloat(pos.coords.longitude.toFixed(6));
      const accuracy = pos.coords.accuracy ? Math.round(pos.coords.accuracy) : null;

      WizardState.accuracy = accuracy;
      WizardState.location_source = "GPS";

      if (statusMsg) {
        const accText = accuracy ? ` (Accuracy: ±${accuracy}m)` : "";
        statusMsg.innerHTML = `
          <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem;">
            <span style="color: var(--success-green); font-weight: 700;">✓ GPS Location Acquired: Latitude ${lat}, Longitude ${lon}${accText}</span>
            <button type="button" class="btn btn-secondary btn-sm" id="btn-gps-retake" style="padding: 0.15rem 0.5rem; font-size: 0.75rem;">🔄 Retake GPS</button>
          </div>
        `;
        const retakeBtn = document.getElementById("btn-gps-retake");
        if (retakeBtn) retakeBtn.addEventListener("click", requestGeolocation);
      }

      applySelectedLocation(lat, lon, `GPS Location (${lat}, ${lon})`, `Latitude: ${lat}, Longitude: ${lon}${accuracy ? ` (Accuracy: ±${accuracy}m)` : ""}`, "GPS");
      resolveAddressForCoordinates(lat, lon);
    },
    (err) => {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = `📍 <span>Use My Current Location</span>`;
      }
      let reason = "Unable to retrieve device location.";
      if (err.code === err.PERMISSION_DENIED) {
        reason = "Location permission denied. Please allow location access in your browser address bar, or click directly on the map below.";
      } else if (err.code === err.POSITION_UNAVAILABLE) {
        reason = "GPS sensor or location provider is unavailable. Please click on the map or search by place name.";
      } else if (err.code === err.TIMEOUT) {
        reason = "GPS request timed out. You may retry or click directly on the map.";
      }
      if (statusMsg) {
        statusMsg.innerHTML = `
          <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem;">
            <span style="color: var(--warning-amber); font-weight: 600;">⚠️ ${reason}</span>
            <button type="button" class="btn btn-primary btn-sm" id="btn-gps-retry-err" style="padding: 0.15rem 0.5rem; font-size: 0.75rem;">🔄 Retry GPS</button>
          </div>
        `;
        const retryErrBtn = document.getElementById("btn-gps-retry-err");
        if (retryErrBtn) retryErrBtn.addEventListener("click", requestGeolocation);
      }
    },
    geoOptions
  );
}

// Populate Review Step Summary
function populateReviewStep() {
  // Description
  const descInput = document.getElementById("input-description").value.trim();
  WizardState.description = descInput;
  document.getElementById("review-description").textContent = descInput || "(No text provided — reported with media)";

  // Language
  WizardState.language = document.getElementById("input-language").value;

  // Location
  const latVal = parseFloat(document.getElementById("input-latitude").value);
  const lonVal = parseFloat(document.getElementById("input-longitude").value);
  if (!isNaN(latVal) && !isNaN(lonVal)) {
    WizardState.latitude = latVal;
    WizardState.longitude = lonVal;
    // Show place name from selected-location-card if available, else raw coordinates
    const selectedPlaceName = document.getElementById("selected-place-name");
    const selectedAddress = document.getElementById("selected-address-text");
    const placeTxt = selectedPlaceName ? selectedPlaceName.textContent.trim() : "";
    const addrTxt = selectedAddress ? selectedAddress.textContent.trim() : "";
    if (placeTxt && placeTxt !== "—") {
      document.getElementById("review-location").textContent = placeTxt;
      const reviewAddr = document.getElementById("review-address");
      if (reviewAddr) reviewAddr.textContent = addrTxt || `Lat: ${latVal}, Lon: ${lonVal}`;
    } else {
      document.getElementById("review-location").textContent = `Lat: ${latVal}, Lon: ${lonVal}`;
    }
  } else {
    WizardState.latitude = null;
    WizardState.longitude = null;
    document.getElementById("review-location").textContent = "Not provided";
  }

  // Evidence
  if (WizardState.evidenceFile) {
    document.getElementById("review-evidence").textContent = `${WizardState.evidenceFile.name} (${(WizardState.evidenceFile.size / (1024 * 1024)).toFixed(2)} MB)`;
  } else {
    document.getElementById("review-evidence").textContent = "None (Text only)";
  }

  // Issue & Department
  const issueKey = WizardState.issueType;
  const currentLang = typeof getSelectedLanguage === "function" ? getSelectedLanguage() : "en";
  const issueName = typeof tIssue === "function" ? tIssue(issueKey, currentLang) : (ISSUE_LABELS[issueKey] || issueKey || "None Selected");
  const deptRaw = ISSUE_DEPT_MAP[issueKey] || "Unknown";
  const deptName = typeof tDepartment === "function" ? tDepartment(deptRaw, currentLang) : deptRaw;

  document.getElementById("review-issue-name").textContent = issueName;
  document.getElementById("review-dept-name").textContent = deptName;
  document.getElementById("review-dept-box").textContent = deptName;

  // AI Classification Mode & Severity
  const aiModeEl = document.getElementById("review-ai-mode");
  const sevLevelEl = document.getElementById("review-severity-level");

  if (WizardState.aiResult && WizardState.aiResult.success && !WizardState.aiResult.is_demo) {
    const ai = WizardState.aiResult;
    const isMatchingCategory = (WizardState.issueType === (ai.issue ? ai.issue.issue_type : ""));
    if (aiModeEl) {
      if (isMatchingCategory && ai.issue) {
        aiModeEl.innerHTML = `<span style="color: var(--success-green); font-weight: 700;">✓ AI Classified (${(ai.issue.confidence * 100).toFixed(1)}% confidence) — Confirmed by Citizen</span>`;
      } else {
        aiModeEl.innerHTML = `<span>Manual citizen selection</span>`;
      }
    }
    if (sevLevelEl && isMatchingCategory && ai.severity) {
      const sevTrans = typeof tSeverity === "function" ? tSeverity(ai.severity.level, currentLang) : ai.severity.level;
      sevLevelEl.textContent = `${sevTrans} (${ai.severity.reason || "Determined severity"})`;
    } else if (sevLevelEl) {
      const baseSev = ["building_damage"].includes(issueKey) ? "CRITICAL" : ["sewage_overflow", "drainage_problem"].includes(issueKey) ? "HIGH" : ["garbage_overflow", "illegal_dumping", "park_damage"].includes(issueKey) ? "LOW" : "MEDIUM";
      const sevTrans = typeof tSeverity === "function" ? tSeverity(baseSev, currentLang) : baseSev;
      sevLevelEl.textContent = `${sevTrans} (Rule-based municipal baseline)`;
    }
  } else {
    if (aiModeEl) {
      aiModeEl.innerHTML = `<span>Manual citizen confirmation</span>`;
    }
    if (sevLevelEl) {
      const baseSev = ["building_damage"].includes(issueKey) ? "CRITICAL" : ["sewage_overflow", "drainage_problem"].includes(issueKey) ? "HIGH" : ["garbage_overflow", "illegal_dumping", "park_damage"].includes(issueKey) ? "LOW" : "MEDIUM";
      const sevTrans = typeof tSeverity === "function" ? tSeverity(baseSev, currentLang) : baseSev;
      sevLevelEl.textContent = `${sevTrans} (Rule-based municipal baseline)`;
    }
  }

  // Trigger non-blocking duplicate complaint check
  checkDuplicateInReview();
}

async function checkDuplicateInReview() {
  const checkLoadingBox = document.getElementById("duplicate-checking-box");
  const warnCard = document.getElementById("duplicate-warning-card");
  const listEl = document.getElementById("duplicate-candidates-list");
  const viewBtn = document.getElementById("btn-duplicate-view");

  if (warnCard) warnCard.style.display = "none";
  if (!WizardState.issueType) return;

  if (checkLoadingBox) checkLoadingBox.style.display = "block";

  try {
    const payload = {
      issue_type: WizardState.issueType,
      description: WizardState.description || undefined,
      latitude: WizardState.latitude,
      longitude: WizardState.longitude,
    };
    const res = await ApiClient.checkDuplicateComplaint(payload);
    if (checkLoadingBox) checkLoadingBox.style.display = "none";

    if (res.has_possible_duplicate && res.candidates && res.candidates.length > 0) {
      if (warnCard) warnCard.style.display = "flex";
      if (listEl) {
        listEl.innerHTML = "";
        res.candidates.slice(0, 3).forEach((cand) => {
          const itemDiv = document.createElement("div");
          itemDiv.style.cssText = "background: #ffffff; border: 1px solid #fde68a; border-radius: 6px; padding: 0.75rem; font-size: 0.85rem;";
          const distText = cand.distance_meters != null ? `${cand.distance_meters} m away` : "Distance unknown";
          const simText = `${(cand.text_similarity * 100).toFixed(1)}% text similarity`;
          itemDiv.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
              <strong style="color: var(--primary-navy);">${cand.complaint_id} — ${cand.issue_type_display}</strong>
              <span style="font-size: 0.75rem; background: #fef3c7; color: #92400e; padding: 0.15rem 0.5rem; border-radius: 4px; font-weight: 700;">Score: ${(cand.duplicate_score * 100).toFixed(0)}%</span>
            </div>
            <div style="color: var(--text-muted); font-size: 0.8rem; margin-bottom: 0.25rem;">
              📍 ${distText} • 📝 ${simText} • Status: ${cand.status}
            </div>
            <div style="color: #78350f; font-size: 0.8rem; font-style: italic;">
              ${cand.reason}
            </div>
          `;
          listEl.appendChild(itemDiv);
        });
      }
      if (viewBtn && res.candidates[0]) {
        viewBtn.href = `/complaints/${encodeURIComponent(res.candidates[0].complaint_id)}`;
        viewBtn.style.display = "inline-flex";
      }
    } else {
      if (warnCard) warnCard.style.display = "none";
    }
  } catch (err) {
    if (checkLoadingBox) checkLoadingBox.style.display = "none";
    if (warnCard) warnCard.style.display = "none";
  }
}

// Submission Execution
async function submitComplaint() {
  const submitBtn = document.getElementById("btn-submit-complaint");

  if (!WizardState.issueType) {
    showWizardAlert("Please select an issue category in Step 4 before submitting.");
    setWizardStep(4);
    return;
  }

  submitBtn.disabled = true;
  submitBtn.textContent = "Submitting Complaint...";
  hideWizardAlert();

  const payload = {
    issue_type: WizardState.issueType,
    description: WizardState.description || undefined,
    original_language: WizardState.language || "en",
    latitude: WizardState.latitude,
    longitude: WizardState.longitude,
    address: WizardState.address || undefined,
    place_name: WizardState.place_name || undefined,
    location_source: WizardState.location_source || undefined,
    location_accuracy: WizardState.accuracy || undefined,
  };

  // If issue category was predicted by active production AI model and confirmed by citizen
  if (WizardState.aiResult && WizardState.aiResult.success && WizardState.aiResult.issue && !WizardState.aiResult.is_demo) {
    if (WizardState.issueType === WizardState.aiResult.issue.issue_type) {
      payload.ai_confidence = WizardState.aiResult.issue.confidence;
      payload.ai_model_version = WizardState.aiResult.model_version;
      payload.is_ai_confirmed = true;
    }
  }

  try {
    const createdComplaint = await ApiClient.createComplaint(payload);
    const complaintId = createdComplaint.complaint_id;
    WizardState.createdComplaintId = complaintId;

    // Upload evidence if present
    if (WizardState.evidenceFile) {
      submitBtn.textContent = "Uploading Evidence File...";
      try {
        await ApiClient.uploadEvidence(complaintId, WizardState.evidenceFile);
      } catch (uploadErr) {
        showWizardAlert(`Complaint was created as ${complaintId}, but evidence upload failed: ${uploadErr.message}. You can attach evidence later from the details page.`, "warning");
      }
    }

    // Render success view
    document.getElementById("pane-step-5").style.display = "none";
    document.getElementById("pane-step-success").style.display = "block";
    document.getElementById("success-complaint-id").textContent = complaintId;
    const curLang = typeof getSelectedLanguage === "function" ? getSelectedLanguage() : "en";
    const rawSuccessDept = createdComplaint.department ? createdComplaint.department.name : ISSUE_DEPT_MAP[WizardState.issueType];
    document.getElementById("success-dept-name").textContent = typeof tDepartment === "function" ? tDepartment(rawSuccessDept, curLang) : rawSuccessDept;
    document.getElementById("link-track-complaint").href = `/track?id=${encodeURIComponent(complaintId)}`;

    // Setup Copy Button
    document.getElementById("btn-copy-complaint-id").addEventListener("click", () => {
      navigator.clipboard.writeText(complaintId).then(() => {
        const copyBtn = document.getElementById("btn-copy-complaint-id");
        copyBtn.textContent = "✓ Copied!";
        setTimeout(() => {
          copyBtn.innerHTML = `📋 <span data-i18n="copy_id">Copy Complaint ID</span>`;
        }, 2000);
      });
    });

    window.scrollTo({ top: 0, behavior: "smooth" });
  } catch (err) {
    submitBtn.disabled = false;
    submitBtn.textContent = "Submit Complaint";
    showWizardAlert(`Failed to lodge complaint: ${err.message}`);
  }
}

// Event Listeners
document.addEventListener("DOMContentLoaded", () => {
  // File inputs
  ["input-photo", "input-video", "input-audio"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("change", (e) => handleSelectedFile(e.target.files[0]));
  });

  const removeBtn = document.getElementById("btn-remove-evidence");
  if (removeBtn) removeBtn.addEventListener("click", removeEvidence);

  const textOnlyBtn = document.getElementById("btn-text-only");
  if (textOnlyBtn) textOnlyBtn.addEventListener("click", () => { removeEvidence(); setWizardStep(2); });

  // Step navigation
  document.getElementById("btn-step1-next").addEventListener("click", () => setWizardStep(2));
  document.getElementById("btn-get-gps").addEventListener("click", requestGeolocation);

  // ── Coordinate input listeners (manual typing or paste) ──
  const origInputLat = document.getElementById("input-latitude");
  const origInputLon = document.getElementById("input-longitude");
  function onManualCoordChange() {
    const lat = parseFloat(origInputLat ? origInputLat.value : "");
    const lon = parseFloat(origInputLon ? origInputLon.value : "");
    if (!isNaN(lat) && !isNaN(lon) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
      applySelectedLocation(lat, lon, `Manual Coordinates (${lat}, ${lon})`, `Latitude: ${lat}, Longitude: ${lon}`, "MANUAL_INPUT");
      resolveAddressForCoordinates(lat, lon);
    }
  }
  if (origInputLat) {
    origInputLat.addEventListener("change", onManualCoordChange);
  }
  if (origInputLon) {
    origInputLon.addEventListener("change", onManualCoordChange);
  }

  const searchBtn = document.getElementById("btn-search-location");
  const searchInput = document.getElementById("input-place-search");
  const searchStatus = document.getElementById("location-search-status");
  const resultsBox = document.getElementById("location-search-results-box");
  const resultsList = document.getElementById("location-results-list");

  async function performLocationSearch() {
    const query = (searchInput ? searchInput.value : "").trim();
    if (!query || query.length < 2) {
      if (searchStatus) { searchStatus.textContent = "Please enter at least 2 characters."; searchStatus.style.display = "block"; }
      return;
    }
    if (searchStatus) { searchStatus.textContent = "Searching for locations..."; searchStatus.style.display = "block"; }
    if (resultsBox) resultsBox.style.display = "none";

    try {
      const data = await ApiClient.searchLocation(query);
      if (searchStatus) searchStatus.style.display = "none";

      if (data.results && data.results.length > 0) {
        if (resultsList) resultsList.innerHTML = "";
        data.results.forEach((loc) => {
          const item = document.createElement("div");
          item.style.cssText = "padding: 0.6rem 0.85rem; cursor: pointer; border-bottom: 1px solid #f1f5f9; display: flex; justify-content: space-between; align-items: center;";
          item.innerHTML = `
            <div>
              <div style="font-weight: 600; color: var(--primary-navy); font-size: 0.9rem;">${escapeHtml(loc.place_name)}</div>
              <div style="font-size: 0.8rem; color: var(--text-muted);">${escapeHtml(loc.display_name)}</div>
            </div>
            <span style="font-size: 0.7rem; color: var(--text-light); white-space: nowrap; margin-left: 0.5rem;">${loc.latitude.toFixed(4)}, ${loc.longitude.toFixed(4)}</span>
          `;
          item.addEventListener("click", () => {
            applySelectedLocation(loc.latitude, loc.longitude, loc.place_name, loc.display_name);
          });
          item.addEventListener("mouseenter", () => { item.style.background = "#f0f9ff"; });
          item.addEventListener("mouseleave", () => { item.style.background = ""; });
          if (resultsList) resultsList.appendChild(item);
        });
        if (resultsBox) resultsBox.style.display = "block";
      } else {
        if (searchStatus) { searchStatus.textContent = data.message || `No locations found for "${query}".`; searchStatus.style.display = "block"; }
      }
    } catch (err) {
      if (searchStatus) { searchStatus.textContent = "Location search failed. You may enter coordinates manually."; searchStatus.style.display = "block"; }
    }
  }

  if (searchBtn) searchBtn.addEventListener("click", performLocationSearch);
  if (searchInput) searchInput.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); performLocationSearch(); } });

  // Initialize map when Step 2 becomes visible
  const step2Pane = document.getElementById("pane-step-2");
  if (step2Pane) {
    const mapObserver = new MutationObserver(() => {
      if (step2Pane.style.display !== "none") {
        setTimeout(() => {
          initWizardMap();
          if (wizardMap) wizardMap.invalidateSize();
          // If coordinates are already set, place marker
          const lat = parseFloat(document.getElementById("input-latitude").value);
          const lon = parseFloat(document.getElementById("input-longitude").value);
          if (!isNaN(lat) && !isNaN(lon)) {
            placeMapMarker(lat, lon);
          }
        }, 200);
      }
    });
    mapObserver.observe(step2Pane, { attributes: true, attributeFilter: ["style"] });
  }

  document.getElementById("btn-step2-prev").addEventListener("click", () => setWizardStep(1));
  document.getElementById("btn-step2-next").addEventListener("click", () => {
    const lat = parseFloat(document.getElementById("input-latitude").value);
    const lon = parseFloat(document.getElementById("input-longitude").value);
    if (!isNaN(lat) && (lat < -90 || lat > 90)) { showWizardAlert("Latitude must be between -90 and 90 degrees."); return; }
    if (!isNaN(lon) && (lon < -180 || lon > 180)) { showWizardAlert("Longitude must be between -180 and 180 degrees."); return; }
    WizardState.latitude = !isNaN(lat) ? lat : null;
    WizardState.longitude = !isNaN(lon) ? lon : null;
    if (WizardState.latitude !== null && WizardState.longitude !== null && !WizardState.place_name) {
      WizardState.place_name = `Coordinates (${WizardState.latitude}, ${WizardState.longitude})`;
    }
    setWizardStep(3);
  });

  document.getElementById("btn-step3-prev").addEventListener("click", () => setWizardStep(2));
  document.getElementById("btn-step3-next").addEventListener("click", () => {
    const descEl = document.getElementById("input-description");
    if (descEl) WizardState.description = descEl.value.trim();
    const langEl = document.getElementById("input-language");
    if (langEl) WizardState.language = langEl.value;
    setWizardStep(4);
  });

  // Language dropdown init
  const initialLang = typeof getSelectedLanguage === "function" ? getSelectedLanguage() : "en";
  WizardState.language = initialLang;
  const langSel = document.getElementById("input-language");
  if (langSel) {
    langSel.value = initialLang;
    langSel.addEventListener("change", (e) => { WizardState.language = e.target.value; });
  }

  // Dynamic i18n updates
  document.addEventListener("i18n:changed", (e) => {
    const newLang = (e.detail && e.detail.lang) || (typeof getSelectedLanguage === "function" ? getSelectedLanguage() : "en");
    WizardState.language = newLang;
    const lSel = document.getElementById("input-language");
    if (lSel) lSel.value = newLang;
    if (WizardState.currentStep === 5) {
      populateReviewStep();
    }
    if (WizardState.issueType) {
      const issueEl = document.getElementById("ai-detected-issue-name");
      if (issueEl) issueEl.textContent = typeof tIssue === "function" ? tIssue(WizardState.issueType, newLang) : WizardState.issueType;
      const deptEl = document.getElementById("ai-dept-value");
      if (deptEl) {
        const rawDept = ISSUE_DEPT_MAP[WizardState.issueType] || "";
        deptEl.textContent = typeof tDepartment === "function" ? tDepartment(rawDept, newLang) : rawDept;
      }
    }
  });

  // Issue selection grid
  const issueGrid = document.getElementById("issue-selection-grid");
  if (issueGrid) {
    issueGrid.querySelectorAll(".issue-card-btn").forEach((card) => {
      card.addEventListener("click", () => {
        issueGrid.querySelectorAll(".issue-card-btn").forEach((c) => c.classList.remove("selected"));
        card.classList.add("selected");
        WizardState.issueType = card.getAttribute("data-issue");
      });
    });
  }

  document.getElementById("btn-step4-prev").addEventListener("click", () => setWizardStep(3));
  document.getElementById("btn-step4-next").addEventListener("click", () => {
    if (!WizardState.issueType) {
      showWizardAlert("Please select an issue category from the options below.");
      return;
    }
    setWizardStep(5);
  });

  const btnConfirmAI = document.getElementById("btn-confirm-ai-prediction");
  if (btnConfirmAI) {
    btnConfirmAI.addEventListener("click", () => {
      if (WizardState.issueType) {
        setWizardStep(5);
      }
    });
  }

  // Demo AI trigger
  const btnDemoAI = document.getElementById("btn-trigger-demo-ai");
  if (btnDemoAI) {
    btnDemoAI.addEventListener("click", () => {
      if (WizardState.evidenceFile) {
        triggerAIDemoDetection(WizardState.evidenceFile);
      }
    });
  }

  // Review step actions
  document.getElementById("btn-step5-prev").addEventListener("click", () => setWizardStep(4));
  document.getElementById("btn-submit-complaint").addEventListener("click", submitComplaint);
});


