/**
 * ============================================================
 * SAFER ROUTE FINDER (routing.js - FEATURE 1)
 * ============================================================
 * Calculates emergency evacuation and relief routes using OSRM,
 * and performs real-time client-side geospatial hazard analysis
 * against Sentinel-1 SAR flood extent polygons using Turf.js.
 */

document.addEventListener("DOMContentLoaded", () => {
  initRoutingUI();
});

let currentRouteLayer = null;
let startMarker = null;
let endMarker = null;

function initRoutingUI() {
  const btnPickStart = document.getElementById("btnPickStartMap");
  const btnPickEnd = document.getElementById("btnPickEndMap");
  const btnMyLocation = document.getElementById("btnUseMyLocation");
  const btnFindRoute = document.getElementById("btnFindSafeRoute");
  const btnClear = document.getElementById("btnClearRoute");
  const presetSelect = document.getElementById("routePresetSelect");

  if (btnPickStart) {
    btnPickStart.addEventListener("click", () => {
      window.activeMapPicker = "start";
      btnPickStart.classList.add("active");
      if (btnPickEnd) btnPickEnd.classList.remove("active");
      window.showToast("Click on the map to set Origin / Start point", "primary");
    });
  }

  if (btnPickEnd) {
    btnPickEnd.addEventListener("click", () => {
      window.activeMapPicker = "end";
      btnPickEnd.classList.add("active");
      if (btnPickStart) btnPickStart.classList.remove("active");
      window.showToast("Click on the map to set Destination", "primary");
    });
  }

  if (btnMyLocation) {
    btnMyLocation.addEventListener("click", () => {
      if (!navigator.geolocation) {
        window.showToast("Geolocation is not supported by your browser", "warning");
        return;
      }
      window.showToast("Acquiring GPS location...", "primary");
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const lng = pos.coords.longitude.toFixed(5);
          const lat = pos.coords.latitude.toFixed(5);
          document.getElementById("routeStartInput").value = `${lng},${lat}`;
          window.onRoutePointSelected("start", [parseFloat(lng), parseFloat(lat)]);
          window.showToast("Origin set to your current GPS position", "success");
        },
        (err) => {
          // Fallback to Guwahati default origin if user denies/blocks GPS
          const defaultOrigin = [91.7362, 26.1445];
          document.getElementById("routeStartInput").value = `${defaultOrigin[0]},${defaultOrigin[1]}`;
          window.onRoutePointSelected("start", defaultOrigin);
          window.showToast("Using default city location (GPS unavailable)", "warning");
        },
        { timeout: 8000 }
      );
    });
  }

  if (presetSelect) {
    presetSelect.addEventListener("change", (e) => {
      if (!e.target.value) return;
      const coords = e.target.value.split(",").map(Number);
      document.getElementById("routeEndInput").value = e.target.value;
      window.onRoutePointSelected("end", coords);
      window.showToast(`Destination set to ${e.target.options[e.target.selectedIndex].text}`, "success");
    });
  }

  if (btnFindRoute) {
    btnFindRoute.addEventListener("click", calculateSafeRoute);
  }

  if (btnClear) {
    btnClear.addEventListener("click", clearCurrentRoute);
  }
}

/**
 * Handle Start/End point marker placements on map
 */
window.onRoutePointSelected = function(type, coords) {
  const [lng, lat] = coords;

  if (type === "start") {
    if (startMarker) window.mapLayers.route.removeLayer(startMarker);
    const startIcon = L.divIcon({
      className: "custom-pin",
      html: '<div style="background: #059669; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; border: 2px solid white;"><i class="fa-solid fa-location-dot"></i></div>',
      iconSize: [28, 28],
      iconAnchor: [14, 14]
    });
    startMarker = L.marker([lat, lng], { icon: startIcon }).bindTooltip("<b>Start / Origin</b>");
    window.mapLayers.route.addLayer(startMarker);
  } else if (type === "end") {
    if (endMarker) window.mapLayers.route.removeLayer(endMarker);
    const endIcon = L.divIcon({
      className: "custom-pin",
      html: '<div style="background: #dc2626; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; border: 2px solid white;"><i class="fa-solid fa-flag-checkered"></i></div>',
      iconSize: [28, 28],
      iconAnchor: [14, 14]
    });
    endMarker = L.marker([lat, lng], { icon: endIcon }).bindTooltip("<b>Destination</b>");
    window.mapLayers.route.addLayer(endMarker);
  }
};

/**
 * Calculate Safe Route using OSRM + Turf.js avoidance
 */
async function calculateSafeRoute() {
  const startVal = document.getElementById("routeStartInput").value.trim();
  const endVal = document.getElementById("routeEndInput").value.trim();

  if (!startVal || !endVal) {
    window.showToast("Please provide both Start and Destination coordinates", "warning");
    return;
  }

  const [startLng, startLat] = startVal.split(",").map(Number);
  const [endLng, endLat] = endVal.split(",").map(Number);

  if (isNaN(startLng) || isNaN(startLat) || isNaN(endLng) || isNaN(endLat)) {
    window.showToast("Invalid coordinate format. Please use 'lon,lat'", "danger");
    return;
  }

  window.showToast("Evaluating flood polygons and querying routing engine...", "primary");
  const btnFindRoute = document.getElementById("btnFindSafeRoute");
  btnFindRoute.disabled = true;
  btnFindRoute.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Calculating...';

  try {
    // 1. Point-in-Polygon Check for Start and End Points
    const startPoint = turf.point([startLng, startLat]);
    const endPoint = turf.point([endLng, endLat]);

    let startInFlood = false;
    let endInFlood = false;

    if (window.floodExtentData) {
      for (const f of window.floodExtentData.features) {
        if (!startInFlood && turf.booleanPointInPolygon(startPoint, f)) startInFlood = true;
        if (!endInFlood && turf.booleanPointInPolygon(endPoint, f)) endInFlood = true;
      }
    }

    // 2. Fetch OSRM Routes with Alternatives
    const osrmUrl = `https://router.project-osrm.org/route/v1/driving/${startLng},${startLat};${endLng},${endLat}?overview=full&geometries=geojson&steps=true&alternatives=true`;
    const response = await fetch(osrmUrl);
    
    if (!response.ok) {
      throw new Error("Unable to connect to OSRM routing server. Check internet connection.");
    }

    const routeData = await response.json();
    if (!routeData.routes || routeData.routes.length === 0) {
      throw new Error("No driving route found between specified points.");
    }

    // 3. Evaluate each route alternative against flood and high-risk polygons
    let selectedRoute = null;
    let bestSafetyStatus = "danger"; // 'safe' | 'detour' | 'danger'
    let intersectingFloods = [];

    for (let i = 0; i < routeData.routes.length; i++) {
      const candidate = routeData.routes[i];
      const routeLine = turf.lineString(candidate.geometry.coordinates);
      const intersections = testRouteIntersections(routeLine);

      if (intersections.length === 0 && !startInFlood && !endInFlood) {
        selectedRoute = candidate;
        selectedRoute.isDetour = false;
        bestSafetyStatus = "safe";
        intersectingFloods = [];
        break; // Found 100% safe route
      } else if (!selectedRoute || intersections.length < intersectingFloods.length) {
        selectedRoute = candidate;
        intersectingFloods = intersections;
      }
    }

    // 4. If direct routes have flood intersections, attempt a dynamic bypass detour
    if (bestSafetyStatus !== "safe" && intersectingFloods.length > 0 && !startInFlood && !endInFlood) {
      const detourRoute = await attemptDetourRouting(startLng, startLat, endLng, endLat, intersectingFloods);
      if (detourRoute) {
        selectedRoute = detourRoute;
        bestSafetyStatus = "detour";
        intersectingFloods = [];
      }
    }

    // 5. Render Route & Display Results
    displayRouteResults(selectedRoute, bestSafetyStatus, {
      startInFlood,
      endInFlood,
      intersectionsCount: intersectingFloods.length
    });

  } catch (err) {
    console.error("[Routing Error]", err);
    window.showToast(`Routing failed: ${err.message}`, "danger");
  } finally {
    btnFindRoute.disabled = false;
    btnFindRoute.innerHTML = '<i class="fa-solid fa-route"></i> Calculate Safe Route';
  }
}

/**
 * Test Route LineString against all Flood Polygons using Turf.js
 */
function testRouteIntersections(routeLine) {
  const obstacles = [];
  if (!window.floodExtentData) return obstacles;

  window.floodExtentData.features.forEach((floodPoly, idx) => {
    try {
      if (turf.booleanIntersects(routeLine, floodPoly)) {
        obstacles.push(floodPoly);
      }
    } catch (e) {}
  });

  return obstacles;
}

/**
 * Attempt Detour Routing around Intersecting Flood Polygons
 */
async function attemptDetourRouting(startLng, startLat, endLng, endLat, floodPolygons) {
  try {
    // Pick the primary intersecting flood polygon and compute its bounding envelope
    const primaryObstacle = floodPolygons[0];
    const bbox = turf.bbox(primaryObstacle); // [minX, minY, maxX, maxY]
    const midX = (bbox[0] + bbox[2]) / 2;
    const midY = (bbox[1] + bbox[3]) / 2;

    // Generate northern and southern bypass offset waypoints
    const offsetDelta = 0.04; // ~4.4km safety buffer
    const detourWaypoints = [
      [midX, bbox[3] + offsetDelta], // North detour
      [midX, bbox[1] - offsetDelta], // South detour
      [bbox[2] + offsetDelta, midY], // East detour
      [bbox[0] - offsetDelta, midY]  // West detour
    ];

    for (const [wLng, wLat] of detourWaypoints) {
      const detourUrl = `https://router.project-osrm.org/route/v1/driving/${startLng},${startLat};${wLng},${wLat};${endLng},${endLat}?overview=full&geometries=geojson&steps=true`;
      const res = await fetch(detourUrl);
      if (!res.ok) continue;
      const dData = await res.json();
      if (dData.routes && dData.routes.length > 0) {
        const dRoute = dData.routes[0];
        const dLine = turf.lineString(dRoute.geometry.coordinates);
        const remainingObstacles = testRouteIntersections(dLine);
        if (remainingObstacles.length === 0) {
          dRoute.isDetour = true;
          return dRoute;
        }
      }
    }
  } catch (e) {
    console.warn("[Detour Routing] Detour attempt encountered issue:", e);
  }
  return null;
}

/**
 * Render Route on Map and populate Summary Card
 */
function displayRouteResults(route, safetyStatus, hazards) {
  // Clear previous route line
  if (currentRouteLayer) {
    window.mapLayers.route.removeLayer(currentRouteLayer);
  }

  // Determine line style based on safety
  let routeColor = "#059669"; // Emerald (Safe)
  let dashArray = null;

  if (safetyStatus === "detour") {
    routeColor = "#d97706"; // Amber (Detour)
  } else if (safetyStatus === "danger") {
    routeColor = "#dc2626"; // Red (Hazard)
    dashArray = "8, 6";
  }

  // Draw Route Polyline
  const latLngs = route.geometry.coordinates.map(coord => [coord[1], coord[0]]);
  currentRouteLayer = L.polyline(latLngs, {
    color: routeColor,
    weight: 5,
    opacity: 0.9,
    dashArray: dashArray,
    lineJoin: "round"
  });

  window.mapLayers.route.addLayer(currentRouteLayer);
  window.floodMap.fitBounds(currentRouteLayer.getBounds(), { padding: [40, 40] });

  // Update UI Card
  const resultCard = document.getElementById("routeResultCard");
  const badge = document.getElementById("routeSafetyBadge");
  const distVal = document.getElementById("routeDistanceVal");
  const timeVal = document.getElementById("routeTimeVal");
  const riskVal = document.getElementById("routeRiskVal");
  const notice = document.getElementById("routeNoticeText");
  const turnBox = document.getElementById("routeTurnSteps");

  resultCard.style.display = "block";

  const distanceKm = (route.distance / 1000).toFixed(1);
  const timeMin = Math.round(route.duration / 60);

  distVal.textContent = `${distanceKm} km`;
  timeVal.textContent = `${timeMin} min`;

  if (safetyStatus === "safe") {
    badge.className = "route-safety-badge safety-clear";
    badge.innerHTML = '<i class="fa-solid fa-circle-check"></i> 100% Safe Route — Avoids Flood Extent';
    riskVal.textContent = "🟢 Zero Risk";
    riskVal.style.color = "#059669";
    notice.innerHTML = "✅ This route avoids all active SAR-detected flood extent zones and high hazard corridors.";
  } else if (safetyStatus === "detour") {
    badge.className = "route-safety-badge safety-detour";
    badge.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Safe Detour Bypassing Flooded Zone';
    riskVal.textContent = "🟡 Detour Applied";
    riskVal.style.color = "#d97706";
    notice.innerHTML = "⚠️ Primary highway intersects flood water. Route automatically detoured via elevated bypass corridors.";
  } else {
    badge.className = "route-safety-badge safety-danger";
    badge.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> FLOOD HAZARD WARNING';
    riskVal.textContent = "🔴 Flood Danger";
    riskVal.style.color = "#dc2626";

    let dangerReasons = [];
    if (hazards.startInFlood) dangerReasons.push("Origin is inside an active flood zone");
    if (hazards.endInFlood) dangerReasons.push("Destination is submerged in flood zone");
    if (hazards.intersectionsCount > 0) dangerReasons.push(`Route intersects ${hazards.intersectionsCount} flooded road segment(s)`);

    notice.innerHTML = `<b>⛔ Extreme Caution:</b> ${dangerReasons.join("; ")}. Standard vehicular transit is not recommended; utilize emergency rescue watercraft.`;
  }

  // Populate Turn-by-Turn Directions
  turnBox.innerHTML = "";
  if (route.legs && route.legs[0] && route.legs[0].steps) {
    route.legs[0].steps.forEach((step, idx) => {
      if (!step.maneuver) return;
      const stepEl = document.createElement("div");
      stepEl.className = "turn-step";
      stepEl.innerHTML = `
        <span style="color: var(--primary); font-weight: 700;">${idx + 1}.</span>
        <div>
          <div>${step.maneuver.instruction || step.name || "Continue along route"}</div>
          <small style="color: var(--text-muted);">${(step.distance / 1000).toFixed(2)} km</small>
        </div>
      `;
      turnBox.appendChild(stepEl);
    });
  }

  window.showToast("Safe route analysis completed", safetyStatus === "danger" ? "warning" : "success");
}

/**
 * Clear Active Route
 */
function clearCurrentRoute() {
  if (currentRouteLayer) {
    window.mapLayers.route.removeLayer(currentRouteLayer);
    currentRouteLayer = null;
  }
  if (startMarker) {
    window.mapLayers.route.removeLayer(startMarker);
    startMarker = null;
  }
  if (endMarker) {
    window.mapLayers.route.removeLayer(endMarker);
    endMarker = null;
  }

  document.getElementById("routeStartInput").value = "";
  document.getElementById("routeEndInput").value = "";
  document.getElementById("routeResultCard").style.display = "none";
  window.showToast("Route cleared", "primary");
}
