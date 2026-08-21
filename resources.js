/**
 * ============================================================
 * COMMUNITY RESOURCE & DONATION CONNECTOR (resources.js - FEATURE 2)
 * ============================================================
 * Allows volunteers, NGOs, and citizens to Offer Help or Request Help.
 * Features dual-tier persistence:
 *  1. Firebase Firestore (real-time cross-device sync)
 *  2. LocalStorage + BroadcastChannel fallback (offline-first live multi-tab sync)
 * Displays categorized map markers with interactive contact popups and filters.
 */

// ============================================================
// 1. FIREBASE CONFIGURATION (Optional: Paste your Firebase config here)
// ============================================================
const firebaseConfig = {
  // apiKey: "YOUR_API_KEY",
  // authDomain: "YOUR_PROJECT.firebaseapp.com",
  // projectId: "YOUR_PROJECT_ID",
  // storageBucket: "YOUR_PROJECT.appspot.com",
  // messagingSenderId: "YOUR_SENDER_ID",
  // appId: "YOUR_APP_ID"
};

let db = null;
let useFirestore = false;

// Initialize Firebase if credentials provided
if (firebaseConfig.apiKey && typeof firebase !== "undefined") {
  try {
    firebase.initializeApp(firebaseConfig);
    db = firebase.firestore();
    useFirestore = true;
    console.log("[Resources] Connected to Firebase Firestore backend.");
  } catch (err) {
    console.warn("[Resources] Firebase initialization failed, using local persistent fallback:", err);
    useFirestore = false;
  }
} else {
  console.log("[Resources] Running in Local Persistent mode with BroadcastChannel live sync.");
}

// In-Memory Resources State
let resourcesList = [];
let activeTypeFilter = "all"; // 'all' | 'offer' | 'request'
let activeCategoryFilter = "all";
let activeSearchQuery = "";
let lastSubmissionTime = 0; // Spam guard timestamp

// Cross-tab sync channel
const syncChannel = ("BroadcastChannel" in window) ? new BroadcastChannel("flood_relief_sync") : null;
if (syncChannel) {
  syncChannel.onmessage = (event) => {
    if (event.data === "reload_resources") {
      loadStoredResources();
    }
  };
}

document.addEventListener("DOMContentLoaded", () => {
  initResourcesUI();
  loadStoredResources();
});

/**
 * Initialize Modals, Forms, and Filter Event Handlers
 */
function initResourcesUI() {
  // Modal Triggers
  const btnOpenOffer = document.getElementById("btnOpenOfferModal");
  const btnOpenRequest = document.getElementById("btnOpenRequestModal");
  const navOffer = document.getElementById("navOfferHelpBtn");
  const navRequest = document.getElementById("navRequestHelpBtn");

  if (btnOpenOffer) btnOpenOffer.addEventListener("click", () => openModal("modalOfferHelp"));
  if (btnOpenRequest) btnOpenRequest.addEventListener("click", () => openModal("modalRequestHelp"));
  if (navOffer) navOffer.addEventListener("click", () => openModal("modalOfferHelp"));
  if (navRequest) navRequest.addEventListener("click", () => openModal("modalRequestHelp"));

  // Modal Closers
  document.querySelectorAll(".modal-close, .modal-backdrop").forEach(el => {
    el.addEventListener("click", (e) => {
      if (e.target === el || el.classList.contains("modal-close")) {
        const modalId = el.getAttribute("data-close") || el.id;
        closeModal(modalId);
      }
    });
  });

  // Map Pick Buttons inside Modals
  const btnPickOffer = document.getElementById("btnPickOfferLocation");
  if (btnPickOffer) {
    btnPickOffer.addEventListener("click", () => {
      if (window.switchAppView) window.switchAppView("operations");
      window.activeMapPicker = "offer";
      btnPickOffer.classList.add("active");
      closeModal("modalOfferHelp");
      window.showToast("Click on the map to set your offer location", "primary");
    });
  }

  const btnPickReq = document.getElementById("btnPickReqLocation");
  if (btnPickReq) {
    btnPickReq.addEventListener("click", () => {
      if (window.switchAppView) window.switchAppView("operations");
      window.activeMapPicker = "request";
      btnPickReq.classList.add("active");
      closeModal("modalRequestHelp");
      window.showToast("Click on the map to set your urgent request location", "danger");
    });
  }

  // Form Submissions
  const formOffer = document.getElementById("formOfferHelp");
  if (formOffer) {
    formOffer.addEventListener("submit", handleOfferSubmit);
  }

  const formRequest = document.getElementById("formRequestHelp");
  if (formRequest) {
    formRequest.addEventListener("submit", handleRequestSubmit);
  }

  // Filter Chips (All / Offers / Requests)
  document.querySelectorAll(".filter-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".filter-chip").forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      activeTypeFilter = chip.getAttribute("data-filter");
      renderResourcesListAndMarkers();
    });
  });

  // Category Filter Select
  const catFilter = document.getElementById("resourceCategoryFilter");
  if (catFilter) {
    catFilter.addEventListener("change", (e) => {
      activeCategoryFilter = e.target.value;
      renderResourcesListAndMarkers();
    });
  }

  // Search Input
  const searchInput = document.getElementById("resourceSearchInput");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      activeSearchQuery = e.target.value.toLowerCase().trim();
      renderResourcesListAndMarkers();
    });
  }
}

/**
 * Open Modal Dialog
 */
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.add("open");
}

/**
 * Close Modal Dialog
 */
function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove("open");
}

/**
 * Handle "Offer Help" Form Submission
 */
async function handleOfferSubmit(e) {
  e.preventDefault();

  // Spam Guard Check (30-second cooldown)
  const now = Date.now();
  if (now - lastSubmissionTime < 15000) {
    window.showToast("Please wait a few seconds before submitting another post.", "warning");
    return;
  }

  const locVal = document.getElementById("offerLocation").value.trim();
  if (!locVal || !locVal.includes(",")) {
    window.showToast("Please pick a location coordinate on the map", "warning");
    return;
  }

  const [lng, lat] = locVal.split(",").map(Number);
  if (isNaN(lng) || isNaN(lat)) {
    window.showToast("Invalid location coordinates", "danger");
    return;
  }

  const item = {
    id: "offer_" + Date.now(),
    type: "offer",
    name: document.getElementById("offerName").value.trim(),
    category: document.getElementById("offerType").value,
    quantity: document.getElementById("offerQuantity").value.trim(),
    location: [lng, lat],
    contact: document.getElementById("offerContact").value.trim(),
    notes: document.getElementById("offerNotes").value.trim(),
    timestamp: new Date().toISOString(),
    createdAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  };

  await saveResource(item);
  lastSubmissionTime = Date.now();

  closeModal("modalOfferHelp");
  document.getElementById("formOfferHelp").reset();
  window.showToast("🎉 Thank you! Your relief offer is now live on the map.", "success");
}

/**
 * Handle "Request Help" Form Submission
 */
async function handleRequestSubmit(e) {
  e.preventDefault();

  const now = Date.now();
  if (now - lastSubmissionTime < 15000) {
    window.showToast("Please wait a few seconds before submitting another post.", "warning");
    return;
  }

  const locVal = document.getElementById("reqLocation").value.trim();
  if (!locVal || !locVal.includes(",")) {
    window.showToast("Please pick a location coordinate on the map", "warning");
    return;
  }

  const [lng, lat] = locVal.split(",").map(Number);
  if (isNaN(lng) || isNaN(lat)) {
    window.showToast("Invalid location coordinates", "danger");
    return;
  }

  const item = {
    id: "req_" + Date.now(),
    type: "request",
    name: document.getElementById("reqName").value.trim(),
    category: document.getElementById("reqType").value,
    urgency: document.getElementById("reqUrgency").value,
    quantity: document.getElementById("reqQuantity").value.trim(),
    location: [lng, lat],
    contact: document.getElementById("reqContact").value.trim(),
    notes: document.getElementById("reqNotes").value.trim(),
    timestamp: new Date().toISOString(),
    createdAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  };

  await saveResource(item);
  lastSubmissionTime = Date.now();

  closeModal("modalRequestHelp");
  document.getElementById("formRequestHelp").reset();
  window.showToast("🚨 Your emergency request has been posted to responders.", "danger");
}

/**
 * Save Resource to Backend (Firestore or LocalStorage)
 */
async function saveResource(resourceItem) {
  if (useFirestore && db) {
    try {
      await db.collection("flood_resources").doc(resourceItem.id).set(resourceItem);
      console.log("[Firestore] Resource saved successfully:", resourceItem.id);
    } catch (err) {
      console.error("[Firestore Error] Falling back to LocalStorage:", err);
      saveLocal(resourceItem);
    }
  } else {
    saveLocal(resourceItem);
  }

  // Reload and notify other tabs
  await loadStoredResources();
  if (syncChannel) syncChannel.postMessage("reload_resources");
}

function saveLocal(item) {
  let existing = [];
  try {
    const raw = localStorage.getItem("flood_relief_resources");
    if (raw) existing = JSON.parse(raw);
  } catch (e) {}

  existing.unshift(item);
  localStorage.setItem("flood_relief_resources", JSON.stringify(existing));
}

/**
 * Load Stored Resources with Seed Defaults
 */
async function loadStoredResources() {
  if (useFirestore && db) {
    try {
      const snapshot = await db.collection("flood_resources").orderBy("timestamp", "desc").get();
      const items = [];
      snapshot.forEach(doc => items.push(doc.data()));
      if (items.length > 0) {
        resourcesList = items;
        renderResourcesListAndMarkers();
        return;
      }
    } catch (e) {
      console.warn("[Firestore] Failed to read, fallback to local:", e);
    }
  }

  // LocalStorage Fallback with Initial Seed Data
  try {
    const raw = localStorage.getItem("flood_relief_resources");
    if (raw) {
      resourcesList = JSON.parse(raw);
    } else {
      // Pre-seed realistic community offers and requests across Assam flood area
      resourcesList = getSeedReliefData();
      localStorage.setItem("flood_relief_resources", JSON.stringify(resourcesList));
    }
  } catch (e) {
    resourcesList = getSeedReliefData();
  }

  renderResourcesListAndMarkers();
}

/**
 * Render Resource Markers on Map & Sidebar List
 */
function renderResourcesListAndMarkers() {
  window.mapLayers.offers.clearLayers();
  window.mapLayers.requests.clearLayers();

  const container = document.getElementById("resourceListContainer");
  if (container) container.innerHTML = "";

  let offersCount = 0;
  let requestsCount = 0;

  // Filter Items
  const filtered = resourcesList.filter(item => {
    if (item.type === "offer") offersCount++;
    if (item.type === "request") requestsCount++;

    // Type filter
    if (activeTypeFilter !== "all" && item.type !== activeTypeFilter) return false;

    // Category filter
    if (activeCategoryFilter !== "all" && item.category !== activeCategoryFilter) return false;

    // Search query filter
    if (activeSearchQuery) {
      const matchName = (item.name || "").toLowerCase().includes(activeSearchQuery);
      const matchItem = (item.quantity || "").toLowerCase().includes(activeSearchQuery);
      const matchNotes = (item.notes || "").toLowerCase().includes(activeSearchQuery);
      if (!matchName && !matchItem && !matchNotes) return false;
    }

    return true;
  });

  // Update Counters
  const elAll = document.getElementById("countAll");
  const elOffers = document.getElementById("countOffers");
  const elRequests = document.getElementById("countRequests");
  const elStatRes = document.getElementById("statResources");

  if (elAll) elAll.textContent = resourcesList.length;
  if (elOffers) elOffers.textContent = offersCount;
  if (elRequests) elRequests.textContent = requestsCount;
  if (elStatRes) elStatRes.textContent = `${resourcesList.length}`;

  if (filtered.length === 0) {
    if (container) {
      container.innerHTML = `
        <div style="text-align: center; color: var(--text-muted); padding: 24px 10px; font-size: 13px;">
          <i class="fa-solid fa-inbox" style="font-size: 28px; margin-bottom: 8px; display: block;"></i>
          No relief entries matching your current filters.
        </div>
      `;
    }
    return;
  }

  // Render Markers and Sidebar Cards
  filtered.forEach(item => {
    const isOffer = item.type === "offer";
    const [lng, lat] = item.location;

    // 1. Custom Leaflet Marker Pin
    const markerIcon = L.divIcon({
      className: `custom-pin ${isOffer ? 'pin-offer' : 'pin-request'}`,
      html: isOffer ? '<i class="fa-solid fa-gift"></i>' : '<i class="fa-solid fa-bullhorn"></i>',
      iconSize: [28, 28],
      iconAnchor: [14, 14],
      popupAnchor: [0, -12]
    });

    const popupHtml = `
      <div style="min-width: 200px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
          <span class="popup-badge" style="${isOffer ? 'background: #d1fae5; color: #065f46;' : 'background: #fee2e2; color: #991b1b;'}">
            ${isOffer ? '🎁 Relief Offer' : '🆘 Help Request'}
          </span>
          <small style="color: #94a3b8; font-size: 11px;">${item.createdAt || 'Recent'}</small>
        </div>
        <div class="popup-title">${escapeHtml(item.name)}</div>
        <div style="font-size: 12px; color: #475569; margin: 4px 0;">
          <div><b>Item / Aid:</b> ${escapeHtml(item.quantity)}</div>
          <div><b>Category:</b> ${item.category}</div>
          ${item.urgency ? `<div><b>Urgency:</b> <span style="color: #dc2626; font-weight: 700;">${item.urgency}</span></div>` : ''}
          ${item.notes ? `<div style="margin-top: 4px; font-style: italic;">"${escapeHtml(item.notes)}"</div>` : ''}
        </div>
        <div style="margin-top: 8px; display: flex; gap: 6px;">
          <a href="tel:${escapeHtml(item.contact)}" class="btn btn-primary btn-sm" style="flex: 1; text-decoration: none; justify-content: center;">
            <i class="fa-solid fa-phone"></i> Call
          </a>
          <button class="btn btn-outline btn-sm" style="flex: 1;" onclick="window.setRouteDestination('${lng},${lat}', '${escapeHtml(item.name)}')">
            <i class="fa-solid fa-route"></i> Route
          </button>
        </div>
      </div>
    `;

    const marker = L.marker([lat, lng], { icon: markerIcon })
      .bindPopup(popupHtml)
      .bindTooltip(`${isOffer ? '🎁 Offer' : '🆘 Request'}: ${escapeHtml(item.name)}`);

    if (isOffer) {
      window.mapLayers.offers.addLayer(marker);
    } else {
      window.mapLayers.requests.addLayer(marker);
    }

    // 2. Sidebar Item Card
    if (container) {
      const card = document.createElement("div");
      card.className = "resource-item";
      card.innerHTML = `
        <div class="resource-header">
          <span class="resource-type-tag ${isOffer ? 'tag-offer' : 'tag-request'}">
            ${isOffer ? '🎁 Offer' : '🆘 Urgent Need'}
          </span>
          <span class="resource-time">${item.createdAt || 'Recent'}</span>
        </div>
        <div class="resource-name">${escapeHtml(item.name)}</div>
        <div class="resource-detail">
          <b>${item.category}:</b> ${escapeHtml(item.quantity)}
        </div>
        ${item.notes ? `<div style="font-size: 11px; color: var(--text-muted); margin-bottom: 6px;">"${escapeHtml(item.notes)}"</div>` : ''}
        <div class="resource-contact">
          <i class="fa-solid fa-phone"></i>
          <a href="tel:${escapeHtml(item.contact)}" style="color: inherit; text-decoration: none;">${escapeHtml(item.contact)}</a>
        </div>
      `;

      // Click card to zoom to marker on map
      card.addEventListener("click", () => {
        window.floodMap.flyTo([lat, lng], 13, { duration: 1.2 });
        marker.openPopup();
      });

      container.appendChild(card);
    }
  });
}

/**
 * Realistic Seed Data for Hackathon Prototype
 */
function getSeedReliefData() {
  return [
    {
      id: "seed_1",
      type: "offer",
      name: "Guwahati Community Welfare Trust",
      category: "Shelter",
      quantity: "3 halls (Capacity: 120 persons)",
      location: [91.7650, 26.1450],
      contact: "+91 94350 88771",
      notes: "Clean bedding, dry ration food, and power generator available 24/7.",
      createdAt: "10:15 AM",
      timestamp: new Date(Date.now() - 3600000).toISOString()
    },
    {
      id: "seed_2",
      type: "request",
      name: "Hajo Rural Relief Camp (Ward 3)",
      category: "Water",
      urgency: "Critical",
      quantity: "500 Liters Drinking Water & Halazone tablets",
      location: [91.5310, 26.2490],
      contact: "+91 98640 11223",
      notes: "Groundwater wells contaminated by flood surge. 45 children affected.",
      createdAt: "11:30 AM",
      timestamp: new Date(Date.now() - 1800000).toISOString()
    },
    {
      id: "seed_3",
      type: "offer",
      name: "Dispur Seva Medical Relief Team",
      category: "Medical",
      quantity: "Mobile First Aid Unit + ORS & Antibiotics",
      location: [91.7920, 26.1390],
      contact: "+91 97060 55443",
      notes: "Paramedics on standby for wound dressing and anti-venom supplies.",
      createdAt: "12:00 PM",
      timestamp: new Date(Date.now() - 1200000).toISOString()
    },
    {
      id: "seed_4",
      type: "offer",
      name: "Barpeta Volunteer Boat Rescue Squad",
      category: "Transport",
      quantity: "2 Inflatable Motorboats (12 Pax capacity)",
      location: [91.0120, 26.3250],
      contact: "+91 94351 99882",
      notes: "Available for ferrying stranded families to high-ground relief centers.",
      createdAt: "01:15 PM",
      timestamp: new Date(Date.now() - 600000).toISOString()
    },
    {
      id: "seed_5",
      type: "request",
      name: "Nalbari Lowland Village Assembly",
      category: "Food",
      urgency: "High",
      quantity: "80 Dry Ration packets (Rice, Dal, Biscuits)",
      location: [91.4460, 26.4380],
      contact: "+91 98540 33441",
      notes: "Road access blocked by 2 feet standing water. Delivery via tractor or boat.",
      createdAt: "02:00 PM",
      timestamp: new Date(Date.now() - 300000).toISOString()
    }
  ];
}
