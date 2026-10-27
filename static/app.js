"use strict";

const TITLES = {
  dashboard: "Fleet overview",
  vehicles: "Vehicles",
  drivers: "Drivers",
  assignments: "Assignments",
  maintenance: "Maintenance",
  fuel: "Fuel logs",
  tires: "Tire Monitoring Sheet",
  trips: "Movement workflow",
  payroll: "Payroll",
  revenue: "Revenue & hauling performance",
};

const RESOURCE_CONFIG = {
  vehicles: {
    api: "vehicles",
    title: "Truck registry",
    singular: "truck",
    fields: [
      { name: "plate_number", label: "Registration number", required: true },
      { name: "make", label: "Make", required: true },
      { name: "model", label: "Model", required: true },
      { name: "year", label: "Year", type: "number", required: true, min: 1900 },
      { name: "color", label: "Color" },
      {
        name: "status",
        label: "Status",
        type: "select",
        options: [["active", "Active"], ["available", "Available"], ["assigned", "Assigned"], ["inactive", "Inactive"], ["maintenance", "Under maintenance"]],
      },
      { name: "odometer", label: "Odometer (km)", type: "number", min: 0, value: 0 },
      { name: "registration_expiry", label: "Registration expiry", type: "date" },
      { name: "insurance_expiry", label: "Insurance expiry", type: "date" },
    ],
    columns: [
      ["id", "Truck ID"],
      ["plate_number", "Registration"],
      ["make", "Make"],
      ["model", "Model"],
      ["year", "Year"],
      ["odometer", "Odometer", (value) => `${formatNumber(value)} km`],
      ["status", "Status", statusBadge],
      ["_actions", "Actions", fleetAssetEditButton],
    ],
  },
  trailers: {
    api: "trailers",
    title: "Trailer registry",
    singular: "trailer",
    fields: [
      { name: "plate_number", label: "Trailer plate number", required: true },
      { name: "year_model", label: "Year model", type: "number", min: 1900 },
      { name: "make_model", label: "Make/model" },
      { name: "mv_file_no", label: "MV file number" },
      { name: "engine_no", label: "Engine number" },
      { name: "chassis_no", label: "Chassis number" },
      { name: "pallet_capacity", label: "Pallet capacity (confirm from trailer records)", type: "number", min: 1, step: 1 },
      { name: "trailer_type", label: "Trailer type" },
      {
        name: "status",
        label: "Status",
        type: "select",
        options: [["active", "Active"], ["inactive", "Inactive"], ["maintenance", "Under maintenance"]],
      },
      { name: "remarks", label: "Remarks", type: "textarea" },
    ],
    columns: [
      ["id", "Trailer ID"],
      ["plate_number", "Trailer Plate"],
      ["pallet_capacity", "Pallet Capacity", displayPalletCapacity],
    ],
  },
  drivers: {
    api: "drivers",
    title: "Driver directory",
    singular: "driver",
    fields: [
      { name: "name", label: "Full name", required: true },
      { name: "license_number", label: "License number", required: true },
      { name: "phone", label: "Phone", type: "tel" },
      { name: "email", label: "Email", type: "email" },
      {
        name: "status",
        label: "Status",
        type: "select",
        options: [["active", "Active"], ["inactive", "Inactive"]],
      },
    ],
    columns: [
      ["name", "Driver"],
      ["license_number", "License"],
      ["phone", "Phone"],
      ["email", "Email"],
      ["status", "Status", statusBadge],
    ],
  },
  assignments: {
    api: "assignments",
    title: "Vehicle assignments",
    singular: "assignment",
    fields: [
      { name: "driver_id", label: "Driver", type: "driver", required: true },
      { name: "vehicle_id", label: "Vehicle", type: "vehicle", required: true },
      { name: "assigned_date", label: "Assigned date", type: "date" },
      { name: "notes", label: "Notes", type: "textarea" },
    ],
    columns: [
      ["driver_name", "Driver"],
      ["plate_number", "Vehicle"],
      ["make", "Make"],
      ["assigned_date", "Assigned"],
      ["returned_date", "Returned"],
    ],
  },
  maintenance: {
    api: "maintenance",
    title: "Maintenance records",
    singular: "maintenance record",
    fields: [
      { name: "vehicle_id", label: "Vehicle", type: "vehicle", required: true },
      { name: "service_type", label: "Service type", required: true },
      { name: "description", label: "Description", type: "textarea" },
      { name: "cost", label: "Cost", type: "number", min: 0, step: "0.01", value: 0 },
      { name: "performed_on", label: "Service date", type: "date" },
    ],
    columns: [
      ["plate_number", "Vehicle"],
      ["service_type", "Service"],
      ["description", "Description"],
      ["performed_on", "Date"],
      ["cost", "Cost", formatCurrency],
    ],
  },
  fuel: {
    api: "fuel",
    title: "Fuel logs",
    singular: "fuel log",
    fields: [
      { name: "vehicle_id", label: "Vehicle", type: "vehicle", required: true },
      { name: "fuel_type", label: "Fuel type", required: true },
      { name: "fuel_allocation", label: "Fuel allocation (₱)", type: "number", min: 0, step: "0.01" },
      { name: "actual_expense", label: "Actual expense (₱)", type: "currency", min: 0, step: "0.01", placeholder: "0.00" },
      { name: "quantity", label: "Quantity (L)", type: "number", min: 0.01, step: "0.01" },
      { name: "price_per_liter", label: "Price per liter", type: "number", min: 0.01, step: "0.01" },
      { name: "total_cost", label: "Total cost (optional)", type: "currency", min: 0, step: "0.01", placeholder: "0.00" },
      { name: "logged_on", label: "Date", type: "date" },
      { name: "remarks", label: "Remarks", type: "textarea", placeholder: "Optional fuel notes, shortages, etc." },
      { name: "invoice_image", label: "Fuel invoice / receipt image", type: "file", accept: "image/jpeg,image/png,image/webp", capture: "environment" },
    ],
    columns: [
      ["plate_number", "Vehicle"],
      ["trip_ism_no", "Linked Trip", (value, row) => value ? escapeHtml(value) : (row.trip_id ? `Trip #${row.trip_id}` : "—")],
      ["trip_route", "Route", (value, row) => row.trip_origin && row.trip_destination ? `${escapeHtml(row.trip_origin)} → ${escapeHtml(row.trip_destination)}` : (value ? escapeHtml(value) : "—")],
      ["fuel_allocation", "Allocation", (value) => value != null ? formatCurrency(value) : "—"],
      ["actual_expense", "Actual Expense", (value) => value != null ? formatCurrency(value) : "—"],
      ["fuel_type", "Fuel"],
      ["quantity", "Quantity", (value) => value != null ? `${formatNumber(value)} L` : "—"],
      ["total_cost", "Total Cost", (value) => value != null ? formatCurrency(value) : "—"],
      ["logged_on", "Date"],
      ["invoice_image_url", "Receipt", (value) => formatImageLink(value, "Fuel invoice")],
    ],
  },
  trips: {
    api: "trips",
    title: "Trip history",
    singular: "trip",
    fields: [
      { name: "ism_no", label: "ISM No" },
      { name: "shipment_date", label: "Shipment date", type: "date", required: true },
      { name: "time_in", label: "Time in", type: "time" },
      { name: "time_out", label: "Time out", type: "time" },
      { name: "truck_id", label: "Truck", type: "truck", required: true },
      { name: "trailer_id", label: "Trailer", type: "trailer", required: true },
      { name: "driver_id", label: "Driver", type: "driver", required: true },
      { name: "origin", label: "Origin", type: "origin", required: true },
      { name: "destination", label: "Destination", type: "destination", required: true },
      { name: "fuel_allocation", label: "Fuel Allocation (₱)", type: "fuel_allocation", min: 0, step: "0.01" },
      { name: "actual_fuel_expense", label: "Actual Fuel Expense", type: "currency", min: 0, step: "0.01", placeholder: "0.00" },
      { name: "invoice_image", label: "Fuel Invoice / Receipt", type: "file", accept: "image/jpeg,image/png,image/webp", capture: "environment" },
      { name: "fuel_remarks", label: "Fuel Remarks", type: "textarea", placeholder: "Optional notes about fuel purchases, shortages, etc." },
      { name: "load_details", label: "Load" },
      { name: "trip_fuel", label: "Trip/Fuel" },
      { name: "manifest_image", label: "Load manifest image", type: "file", accept: "image/jpeg,image/png,image/webp", capture: "environment" },
      { name: "notes", label: "Notes", type: "textarea" },
    ],
    columns: [
      ["ism_no", "ISM NO"],
      ["shipment_date", "SHIPMENT DATE"],
      ["origin", "ORIGIN"],
      ["destination", "DESTINATION"],
      ["route_number", "ROUTE NO."],
      ["truck_plate_number", "TRUCK PLATE"],
      ["trailer_plate_number", "TRAILER PLATE"],
      ["pallet_capacity", "PALLET CAPACITY", displayPalletCapacity],
      ["truck_route_rate", "TRIP RATE", displayTruckRate],
      ["fuel_allocation", "FUEL ALLOCATION", (value) => value != null ? formatCurrency(value) : "—"],
      ["actual_fuel_expense", "ACTUAL FUEL", (value, row) => value != null ? formatCurrency(value) : (row.actual_expense != null ? formatCurrency(row.actual_expense) : "—")],
      ["time_in", "TIME IN"],
      ["time_out", "TIME OUT"],
      ["load_details", "LOAD"],
      ["driver_name", "DRIVER"],
      ["trip_fuel", "TRIP/FUEL"],
      ["manifest_image_url", "MANIFEST", (value) => formatImageLink(value, "Load manifest")],
      ["fuel_invoice_image_url", "FUEL RECEIPT", (value) => formatImageLink(value, "Fuel invoice")],
    ],
  },
};

function isoDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatImageLink(url, label = "Image") {
  return url
    ? `<button class="text-button image-preview-link" type="button" data-action="preview-image" data-image-url="${escapeHtml(url)}" data-image-title="${escapeHtml(label)}" data-image-alt="${escapeHtml(label)}">View image</button>`
    : "—";
}

const today = new Date();
function dateInBusinessTimezone(date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Manila",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

const businessToday = dateInBusinessTimezone();
const SESSION_IDLE_TIMEOUT_MS = 3 * 60 * 1000;
const SESSION_ACTIVITY_PING_INTERVAL_MS = 30 * 1000;
const state = {
  data: null,
  page: "dashboard",
  search: "",
  csrfToken: "",
  notifications: [],
  unreadNotifications: 0,
  notificationTarget: null,
  payroll: null,
  payrollKey: "",
  payrollRequestedKey: "",
  tires: {
    items: [],
    summary: null,
    total: 0,
    page: 1,
    page_size: 25,
    search: "",
    asset_type: "",
    asset_id: "",
    status: "",
    date_from: "",
    date_to: "",
    lifespan_min: "",
    lifespan_max: "",
    condition: "",
    sort_by: "date_installed",
    sort_dir: "desc",
    warning_percent: 20,
    requestedKey: "",
    loading: false,
    error: "",
  },
  revenue: {
    start_date: `${businessToday.slice(0, 7)}-01`,
    end_date: businessToday,
    preset: "this_month",
    bucket: "day",
    filters_open: false,
    origin: "",
    destination: "",
    route_number: "",
    driver_id: "",
    truck_id: "",
    trailer_id: "",
    pallet_capacity: "",
    search: "",
    route_search: "",
    route_sort_by: "revenue",
    route_sort_dir: "desc",
    page: 1,
    sort_by: "shipment_date",
    sort_dir: "desc",
    report: null,
    reportKey: "",
    loading: false,
    error: "",
    selectedTripId: "",
  },
  tripsGroupBy: "",
  selectedTripIds: new Set(),
  bulkDeletingTrips: false,
  vehicleSection: "trucks",
  editingTrip: null,
  dispatch: {
    tab: "departures",
    movements: [],
    total: 0,
    locations: [],
    users: [],
    assignments: [],
    loaded: false,
    loading: false,
    requestId: 0,
    error: "",
    search: "",
    page: 1,
    departureOrigin: "",
    loadCatalog: [],
    loadCatalogLoaded: false,
    loadCatalogLoading: false,
    loadCatalogError: "",
    loadCatalogSearch: "",
    loadCatalogSection: "",
    departureLoadItems: [],
    departureWizardStep: 0,
    departureDriver: "",
    departureTruck: "",
    departureTrailer: "",
    departureDestination: "",
    departureLoadType: "",
    departurePalletQuantity: "",
    departureIsm: "",
    departureAt: "",
    departureFuelAllocation: "",
    departureFuelExpense: "",
    departureFuelRemarks: "",
    previewUrls: {},
    dashboard: {
      arrivals: [],
      arrivalsTotal: 0,
      departures: [],
      departuresTotal: 0,
      locations: [],
      loaded: false,
      loading: false,
      requestId: 0,
      error: "",
    },
  },
  tripWizard: {
    step: 0,
    dirty: false,
    createdTripId: null,
    manifestUploaded: false,
    invoiceUploaded: false,
    objectUrls: {},
    submitting: false,
  },
  payrollPeriod: {
    start_date: isoDate(new Date(today.getFullYear(), today.getMonth(), 1)),
    end_date: isoDate(new Date(today.getFullYear(), today.getMonth() + 1, 0)),
  },
  payrollFilters: { driver_id: "", ism_no: "", origin: "", destination: "" },
};
const view = document.querySelector("#app-view");
const appShell = document.querySelector(".app-shell");
const sidebarToggle = document.querySelector("#sidebar-collapse");
const mobileNavToggle = document.querySelector("#mobile-nav-toggle");
const navigation = document.querySelector("#main-navigation");

view.addEventListener("toggle", (event) => {
  if (event.target.matches?.("details[data-revenue-filters]")) {
    state.revenue.filters_open = event.target.open;
  }
}, true);
let idleLogoutTimer;
let lastActivityPing = 0;
let searchRenderTimer;
let notificationPollTimer;
let notificationFetchInProgress = false;

function setSidebarCollapsed(collapsed) {
  appShell.classList.toggle("sidebar-collapsed", collapsed);
  sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
  sidebarToggle.setAttribute("aria-label", collapsed ? "Expand navigation" : "Collapse navigation");
  sidebarToggle.title = collapsed ? "Expand navigation" : "Collapse navigation";
}

function closeMegaMenu(restoreFocus = false) {
  const openGroup = navigation.querySelector(".nav-group.is-open");
  navigation.querySelectorAll("[data-nav-category]").forEach((group) => {
    group.classList.remove("is-open");
    const toggle = group.querySelector(".nav-category-toggle");
    const panel = group.querySelector(".nav-mega-panel");
    toggle.setAttribute("aria-expanded", "false");
    panel.hidden = true;
    panel.style.removeProperty("left");
    panel.style.removeProperty("top");
    panel.style.removeProperty("width");
  });
  if (restoreFocus && openGroup) openGroup.querySelector(".nav-category-toggle").focus();
}

function positionMegaMenu(group) {
  const panel = group.querySelector(".nav-mega-panel");
  const toggle = group.querySelector(".nav-category-toggle");
  const toggleRect = toggle.getBoundingClientRect();
  let left = toggleRect.right + 12;
  let width = Math.min(540, window.innerWidth - left - 16);
  if (width < 360) {
    left = 8;
    width = Math.min(540, window.innerWidth - 16);
  }
  panel.style.left = `${left}px`;
  panel.style.width = `${width}px`;
  panel.style.top = "12px";
  const panelHeight = panel.getBoundingClientRect().height;
  const top = Math.min(Math.max(12, toggleRect.top - 12), window.innerHeight - panelHeight - 12);
  panel.style.top = `${Math.max(12, top)}px`;
}

function openMegaMenu(group) {
  closeMegaMenu();
  group.classList.add("is-open");
  const toggle = group.querySelector(".nav-category-toggle");
  const panel = group.querySelector(".nav-mega-panel");
  toggle.setAttribute("aria-expanded", "true");
  panel.hidden = false;
  if (!window.matchMedia("(max-width: 760px)").matches) positionMegaMenu(group);
}

function setMobileNavigationOpen(open) {
  document.querySelector(".sidebar").classList.toggle("is-mobile-open", open);
  mobileNavToggle.setAttribute("aria-expanded", String(open));
}

let sidebarInitiallyCollapsed = false;
try {
  sidebarInitiallyCollapsed = localStorage.getItem("glfs-sidebar-collapsed") === "true";
} catch {
  sidebarInitiallyCollapsed = false;
}
setSidebarCollapsed(sidebarInitiallyCollapsed);
sidebarToggle.addEventListener("click", () => {
  const collapsed = !appShell.classList.contains("sidebar-collapsed");
  setSidebarCollapsed(collapsed);
  try {
    localStorage.setItem("glfs-sidebar-collapsed", String(collapsed));
  } catch {
    // The navigation remains usable for this page if preference storage is unavailable.
  }
  closeMegaMenu();
});

mobileNavToggle.addEventListener("click", () => {
  const open = mobileNavToggle.getAttribute("aria-expanded") !== "true";
  setMobileNavigationOpen(open);
  if (!open) closeMegaMenu();
});

navigation.addEventListener("click", (event) => {
  const toggle = event.target.closest(".nav-category-toggle");
  if (toggle) {
    const group = toggle.closest("[data-nav-category]");
    if (toggle.getAttribute("aria-expanded") === "true") {
      closeMegaMenu();
    } else {
      openMegaMenu(group);
    }
    return;
  }
  const link = event.target.closest(".nav-link");
  if (link) {
    if (link.dataset.dispatchTab) {
      state.dispatch.tab = link.dataset.dispatchTab;
      state.dispatch.page = 1;
      state.dispatch.loaded = false;
      if (state.page === "trips" && location.hash === "#trips") {
        loadDispatchWorkflow({ force: true });
      }
    }
    closeMegaMenu();
    setMobileNavigationOpen(false);
  }
});

document.addEventListener("click", (event) => {
  if (!navigation.contains(event.target)) closeMegaMenu();
  if (!document.querySelector(".sidebar").contains(event.target)) setMobileNavigationOpen(false);
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  const hadOpenMenu = Boolean(navigation.querySelector(".nav-group.is-open"));
  const hadOpenDrawer = mobileNavToggle.getAttribute("aria-expanded") === "true";
  if (!hadOpenMenu && !hadOpenDrawer) return;
  closeMegaMenu(hadOpenMenu && !hadOpenDrawer);
  if (hadOpenDrawer) {
    setMobileNavigationOpen(false);
    mobileNavToggle.focus();
  }
});

window.addEventListener("resize", () => {
  const openGroup = navigation.querySelector(".nav-group.is-open");
  if (!openGroup) return;
  if (window.matchMedia("(max-width: 760px)").matches) {
    const panel = openGroup.querySelector(".nav-mega-panel");
    panel.style.removeProperty("left");
    panel.style.removeProperty("top");
    panel.style.removeProperty("width");
  } else {
    positionMegaMenu(openGroup);
  }
});

function returnToSignIn(expired = false) {
  window.location.replace(expired ? "/login?expired=1" : "/login");
}

function registerSessionActivity() {
  window.clearTimeout(idleLogoutTimer);
  idleLogoutTimer = window.setTimeout(() => returnToSignIn(true), SESSION_IDLE_TIMEOUT_MS);

  const now = Date.now();
  if (now - lastActivityPing < SESSION_ACTIVITY_PING_INTERVAL_MS) return;
  lastActivityPing = now;
  fetch("/api/auth/me", { cache: "no-store" })
    .then(async (response) => {
      if (response.status === 401) {
        const payload = await response.json().catch(() => ({}));
        returnToSignIn(payload.error?.toLowerCase().includes("inactivity"));
      }
    })
    .catch(() => showToast("Could not verify the session. Check your connection.", "error"));
}

for (const eventName of ["pointerdown", "keydown", "scroll", "touchstart"]) {
  window.addEventListener(eventName, registerSessionActivity, { passive: true });
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

function formatNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? new Intl.NumberFormat().format(number) : "—";
}

function formatCurrency(value) {
  const number = Number(value);
  return Number.isFinite(number)
    ? new Intl.NumberFormat("en-PH", {
      style: "currency",
      currency: "PHP",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(number)
    : "—";
}

function displayTruckRate(value) {
  return value === null || value === undefined || value === ""
    ? '<span class="rate-unconfigured">Rate not configured</span>'
    : escapeHtml(formatCurrency(value));
}

function displayPalletCapacity(value) {
  return value === null || value === undefined || value === ""
    ? "Unknown"
    : `${escapeHtml(value)} pallets`;
}

function fleetAssetEditButton(_value, row) {
  const assetType = row._asset_type || "truck";
  const resource = assetType === "trailer" ? "trailers" : "vehicles";
  return `<span class="fleet-asset-actions"><button class="button button-secondary button-small" type="button" data-action="edit-fleet-asset" data-asset-type="${escapeHtml(assetType)}" data-id="${escapeHtml(row.id)}">Edit</button><button class="icon-button delete-button" type="button" data-action="delete" data-resource="${resource}" data-id="${escapeHtml(row.id)}" aria-label="Delete ${escapeHtml(assetType)}">×</button></span>`;
}

function statusBadge(value) {
  const status = String(value || "unknown").toLowerCase();
  return `<span class="badge badge-${escapeHtml(status)}">${escapeHtml(status.replaceAll("_", " "))}</span>`;
}

function showToast(message, kind = "success") {
  const region = document.querySelector("#toast-region");
  region.innerHTML = `<div class="toast toast-${kind}" role="status">${escapeHtml(message)}</div>`;
  window.setTimeout(() => {
    region.replaceChildren();
  }, 4500);
}

let dataLoadPromise = null;

function collectionKeyForResource(resource) {
  return resource === "fuel" ? "fuel_logs" : resource;
}

function hydrateResourceRecord(resource, record) {
  const hydrated = { ...record };
  const findById = (collection, id) => collection?.find((item) => String(item.id) === String(id));
  if (resource === "fuel" || resource === "maintenance") {
    const vehicle = findById(state.data.vehicles, hydrated.vehicle_id);
    if (vehicle) hydrated.plate_number = vehicle.plate_number;
  } else if (resource === "assignments") {
    const driver = findById(state.data.drivers, hydrated.driver_id);
    const vehicle = findById(state.data.vehicles, hydrated.vehicle_id);
    if (driver) hydrated.driver_name = driver.name;
    if (vehicle) {
      hydrated.plate_number = vehicle.plate_number;
      hydrated.make = vehicle.make;
      hydrated.model = vehicle.model;
    }
    if (vehicle && !["assigned", "inactive", "maintenance"].includes(vehicle.status)) {
      vehicle.status = "assigned";
    }
  } else if (resource === "trips") {
    const truck = findById(state.data.vehicles, hydrated.truck_id ?? hydrated.vehicle_id);
    const trailer = findById(state.data.trailers, hydrated.trailer_id);
    const driver = findById(state.data.drivers, hydrated.driver_id);
    if (truck) {
      hydrated.plate_number = truck.plate_number;
      hydrated.truck_plate_number = truck.plate_number;
      hydrated.make = truck.make;
      hydrated.model = truck.model;
    }
    if (trailer) {
      hydrated.trailer_plate_number = trailer.plate_number;
      hydrated.pallet_capacity = hydrated.pallet_capacity ?? trailer.pallet_capacity;
      hydrated.trailer_type = trailer.trailer_type;
      hydrated.trailer_status = trailer.status;
    }
    if (driver) hydrated.driver_name = driver.name;
  }
  return hydrated;
}

function refreshDashboardSummary() {
  if (!state.data) return;
  const { vehicles = [], drivers = [], fuel_logs: fuelLogs = [], maintenance = [], trips = [] } = state.data;
  if (state.data.user?.role === "dispatcher") {
    const todayLabel = isoDate(new Date());
    state.data.dashboard = {
      total_trips: trips.length,
      today_trips: trips.filter((trip) => String(trip.shipment_date || "").slice(0, 10) === todayLabel).length,
      total_fuel_logs: fuelLogs.length,
      total_maintenance: maintenance.length,
    };
    return;
  }
  state.data.dashboard = {
    total_vehicles: vehicles.length,
    active_drivers: drivers.filter((driver) => driver.status === "active").length,
    assigned_vehicles: vehicles.filter((vehicle) => vehicle.status === "assigned").length,
    total_fuel_spend: fuelLogs.reduce((total, item) => total + Number(item.total_cost || 0), 0),
    total_maintenance: maintenance.reduce((total, item) => total + Number(item.cost || 0), 0),
    recent_trips: trips.length,
  };
}

function upsertResourceRecord(resource, record) {
  if (!state.data || !record) return false;
  const key = collectionKeyForResource(resource);
  const collection = state.data[key];
  if (!Array.isArray(collection)) return false;
  const targetId = record.id == null ? null : String(record.id);
  if (targetId === null) {
    collection.push(record);
    return true;
  }
  const index = collection.findIndex((item) => String(item.id) === targetId);
  if (index >= 0) {
    collection[index] = hydrateResourceRecord(resource, { ...collection[index], ...record });
  } else {
    collection.push(hydrateResourceRecord(resource, record));
  }
  refreshDashboardSummary();
  return true;
}

function removeResourceRecord(resource, recordId) {
  if (!state.data) return false;
  const key = collectionKeyForResource(resource);
  const collection = state.data[key];
  if (!Array.isArray(collection)) return false;
  const targetId = String(recordId);
  const initialLength = collection.length;
  const updated = collection.filter((item) => String(item.id) !== targetId);
  if (updated.length === initialLength) return false;
  state.data[key] = updated;
  refreshDashboardSummary();
  return true;
}

async function api(path, options = {}) {
  const headers = {
    ...(options.body && !(options.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
    ...options.headers,
  };
  if (["POST", "PUT", "PATCH", "DELETE"].includes(options.method?.toUpperCase())) {
    headers["X-CSRF-Token"] = state.csrfToken;
  }
  const response = await fetch(path, {
    ...options,
    headers,
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) {
      returnToSignIn(payload.error?.toLowerCase().includes("inactivity"));
    }
    throw new Error(payload.error || `Request failed (${response.status})`);
  }
  return payload;
}

function renderNotificationItems() {
  const list = document.querySelector("#notification-list");
  if (!list) return;
  const dispatcherFilter = document.querySelector("#notification-dispatcher-filter").value.trim().toLocaleLowerCase();
  const typeFilter = document.querySelector("#notification-type-filter").value;
  const dateFilter = document.querySelector("#notification-date-filter").value;
  const statusFilter = document.querySelector("#notification-status-filter").value;
  const filtered = state.notifications.filter((notification) =>
    (!dispatcherFilter || `${notification.actor_name} ${notification.actor_email}`.toLocaleLowerCase().includes(dispatcherFilter))
    && (!typeFilter || notification.notification_type === typeFilter)
    && (!dateFilter || String(notification.created_at || "").slice(0, 10) === dateFilter)
    && (!statusFilter || (notification.is_read ? "read" : "unread") === statusFilter),
  );
  if (!filtered.length) {
    list.innerHTML = `<p class="notification-empty">${state.notifications.length ? "No notifications match these filters." : "You’re all caught up."}</p>`;
    return;
  }
  list.innerHTML = filtered.map((notification) => {
    const createdAt = new Date(notification.created_at);
    const readableDate = Number.isNaN(createdAt.getTime())
      ? ""
      : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(createdAt);
    return `
      <button class="notification-item ${notification.is_read ? "" : "unread"}" type="button" data-notification-id="${escapeHtml(notification.id)}">
        <span class="notification-item-title">${escapeHtml(notification.title)}</span>
        <span class="notification-item-message">${escapeHtml(notification.message)}</span>
        <span class="notification-item-meta"><span>Record #${escapeHtml(notification.record_id)}</span><time datetime="${escapeHtml(notification.created_at)}">${escapeHtml(readableDate)}</time></span>
      </button>`;
  }).join("");
}

function setUnreadNotificationCount(count) {
  state.unreadNotifications = Number.isFinite(Number(count)) ? Number(count) : 0;
  const badge = document.querySelector("#notification-count");
  const button = document.querySelector("#notification-toggle");
  badge.textContent = state.unreadNotifications > 99 ? "99+" : String(state.unreadNotifications);
  badge.hidden = state.unreadNotifications === 0;
  button.setAttribute(
    "aria-label",
    `Notifications${state.unreadNotifications ? `, ${state.unreadNotifications} unread` : ""}`,
  );
}

async function refreshNotifications(loadList = false) {
  if (notificationFetchInProgress || state.data?.user?.role !== "administrator") return;
  notificationFetchInProgress = true;
  try {
    const result = await api("/api/notifications/unread-count");
    setUnreadNotificationCount(result.unread_count);
    const center = document.querySelector("#notification-center");
    if (loadList || !center.hidden) {
      const listing = await api("/api/notifications");
      state.notifications = listing.notifications || [];
      renderNotificationItems();
    }
    document.querySelector("#notification-error").hidden = true;
  } catch (error) {
    const errorMessage = document.querySelector("#notification-error");
    errorMessage.textContent = error.message || "Could not load notifications.";
    errorMessage.hidden = false;
  } finally {
    notificationFetchInProgress = false;
  }
}

function initializeNotificationPolling() {
  const adminCenter = document.querySelector("#notification-menu-wrap");
  const isAdmin = state.data?.user?.role === "administrator";
  adminCenter.hidden = !isAdmin;
  window.clearInterval(notificationPollTimer);
  if (!isAdmin) return;
  refreshNotifications();
  notificationPollTimer = window.setInterval(() => {
    if (!document.hidden) refreshNotifications();
  }, 12000);
}

async function loadData({ force = false } = {}) {
  if (!force && dataLoadPromise) {
    return dataLoadPromise;
  }
  view.setAttribute("aria-busy", "true");
  dataLoadPromise = (async () => {
    try {
      state.data = await api("/api/bootstrap");
      state.csrfToken = state.data.csrf_token || "";
      const user = state.data.user || {};
      document.querySelector("#signed-in-user").textContent =
        `${user.email || ""}${user.role ? ` · ${user.role}` : ""}`;
      registerSessionActivity();
      render();
      if (user.role === "dispatcher") {
        state.dispatch.dashboard.loaded = false;
        loadDispatcherDashboard();
      }
      initializeNotificationPolling();
      return state.data;
    } catch (error) {
      view.innerHTML = `
        <section class="error-card">
          <p class="eyebrow">Connection problem</p>
          <h1>Could not load fleet data</h1>
          <p>${escapeHtml(error.message)}</p>
          <button class="button button-primary" data-action="retry" type="button">Try again</button>
        </section>`;
      return null;
    } finally {
      dataLoadPromise = null;
      view.setAttribute("aria-busy", "false");
    }
  })();
  return dataLoadPromise;
}

function header(eyebrow, title, description = "", action = "") {
  return `
    <div class="page-heading mb-5 flex flex-col items-start justify-between gap-[18px] sm:flex-row sm:items-center">
      <div>
        <p class="eyebrow">${escapeHtml(eyebrow)}</p>
        <h1>${escapeHtml(title)}</h1>
        ${description ? `<p class="page-description">${escapeHtml(description)}</p>` : ""}
      </div>
      <div class="page-heading-actions flex flex-wrap gap-2.5">
        ${action}
        <button class="button button-secondary" data-action="refresh" type="button">↻ Refresh</button>
      </div>
    </div>`;
}

function statCard(label, value, tone, icon, detail = "") {
  return `
    <article class="stat-card flex min-h-[82px] items-center gap-3 overflow-hidden rounded-[var(--radius-card)] border border-[var(--border)] bg-[var(--surface)] p-[15px]">
      <div class="stat-icon ${tone} grid size-[41px] shrink-0 place-items-center rounded-[var(--radius-inset)] text-lg" aria-hidden="true">${icon}</div>
      <div class="stat-copy grid min-w-0 gap-[5px]">
        <span class="truncate text-xs text-[var(--muted)]">${escapeHtml(label)}</span>
        <strong class="text-xl font-extrabold tracking-[-0.5px]">${escapeHtml(value)}</strong>
        ${detail ? `<small>${escapeHtml(detail)}</small>` : ""}
      </div>
    </article>`;
}

function tableMarkup(rows, columns, resource, options = {}) {
  if (!rows.length) {
    return `<div class="empty-state"><span aria-hidden="true">⌁</span><strong>${escapeHtml(options.empty || "Nothing here yet")}</strong><small>Records you add will appear here.</small></div>`;
  }
  const selectionHeader = options.selectTrips
    ? '<th class="trip-select-column" scope="col"><span class="sr-only">Select trip</span></th>'
    : "";
  const headings = columns.map(([, label]) => `<th scope="col">${escapeHtml(label)}</th>`).join("");
  const actionHeader = resource ? '<th class="action-column" scope="col">Action</th>' : "";
  const body = rows.map((row) => {
    const selectionCell = options.selectTrips
      ? `<td class="trip-select-column" data-label="Select trip"><input type="checkbox" data-trip-select="${escapeHtml(row.id)}" aria-label="Select trip ${escapeHtml(row.ism_no || row.id)}" ${state.selectedTripIds.has(String(row.id)) ? "checked" : ""} ${state.bulkDeletingTrips ? "disabled" : ""} /></td>`
      : "";
    const cells = columns.map(([key, label, formatter]) => {
      const value = formatter ? formatter(row[key], row) : escapeHtml(row[key] ?? "—");
      return `<td data-label="${escapeHtml(label)}">${value}</td>`;
    }).join("");
    const action = resource
        ? `<td class="action-column" data-label="Action"><button class="icon-button delete-button" type="button" data-action="delete" data-resource="${escapeHtml(resource)}" data-id="${escapeHtml(row.id)}" aria-label="Delete ${escapeHtml(RESOURCE_CONFIG[resource]?.singular || "record")}">×</button></td>`
      : "";
    const rowAttributes = options.rowAction
        ? `tabindex="0" role="button" class="clickable-row" data-action="${escapeHtml(options.rowAction)}" data-id="${escapeHtml(row.id)}" data-record-id="${escapeHtml(row.id)}" aria-label="${escapeHtml(options.rowLabel ? options.rowLabel(row) : `View trip ${row.ism_no || row.id}`)}"`
        : (resource ? `data-record-id="${escapeHtml(row.id)}"` : "");
    return `<tr ${rowAttributes}>${selectionCell}${cells}${action}</tr>`;
  }).join("");
  return `<div class="table-wrap"><table><thead><tr>${selectionHeader}${headings}${actionHeader}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function panel(title, content, link = "") {
  return `
    <section class="panel min-w-0 rounded-[var(--radius-card)] border border-[var(--border)] bg-[var(--surface)] p-[17px]">
      <div class="panel-heading mb-[14px] flex items-center justify-between gap-[13px]">
        <h2>${escapeHtml(title)}</h2>
        ${link ? `<a class="text-link" href="#${escapeHtml(link)}">View all <span aria-hidden="true">→</span></a>` : ""}
      </div>
      ${content}
    </section>`;
}

function renderDashboard() {
  const data = state.data;
  const summary = data.dashboard;
  if (data.user?.role === "dispatcher") {
    return renderDispatcherDashboard(data, summary);
  }
  return `
    ${header("OPERATIONS", "Fleet overview", "Monitor vehicles, drivers, and daily fleet activity.")}
    <div class="stats-grid">
      ${statCard("Total vehicles", formatNumber(summary.total_vehicles), "blue", "▰")}
      ${statCard("Active drivers", formatNumber(summary.active_drivers), "green", "♙")}
      ${statCard("Assigned vehicles", formatNumber(summary.assigned_vehicles), "purple", "⇄")}
      ${statCard("Fuel spend", formatCurrency(summary.total_fuel_spend), "orange", "◉")}
      ${statCard("Maintenance spend", formatCurrency(summary.total_maintenance), "red", "⚙")}
      ${statCard("Trips recorded", formatNumber(summary.recent_trips), "teal", "⌁")}
    </div>
    <div class="dashboard-grid">
      ${panel("Trucks", tableMarkup(data.vehicles.slice(0, 5), [
        ["plate_number", "Truck plate"],
        ["make", "Make"],
        ["model", "Model"],
        ["status", "Status", statusBadge],
      ], null, { empty: "No trucks registered" }), "vehicles")}
      ${panel("Recent trips", tableMarkup(data.trips.slice(0, 5), [
        ["origin", "Origin"],
        ["destination", "Destination"],
        ["plate_number", "Plate no"],
        ["driver_name", "Driver"],
        ["shipment_date", "Shipment date"],
      ], null, { empty: "No trips recorded", rowAction: "trip-details" }), "trips")}
      ${panel("Vehicle assignments", tableMarkup(data.assignments.slice(0, 5), RESOURCE_CONFIG.assignments.columns, null, { empty: "No assignments yet" }), "assignments")}
      ${panel("Maintenance", tableMarkup(data.maintenance.slice(0, 5), RESOURCE_CONFIG.maintenance.columns, null, { empty: "No maintenance records" }), "maintenance")}
    </div>
    ${tripDetailsDialogMarkup()}`;
}

async function loadDispatcherDashboard({ force = false } = {}) {
  const dashboard = state.dispatch.dashboard;
  if (state.data?.user?.role !== "dispatcher"
      || dashboard.loading
      || (dashboard.loaded && !force)) return;

  const requestId = ++dashboard.requestId;
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 20000);
  dashboard.loading = true;
  dashboard.error = "";
  try {
    const requests = [
      api("/api/dispatch/movements?queue=arrivals&page=1&page_size=5", {
        signal: controller.signal,
      }),
      api("/api/dispatch/movements?queue=departures&page=1&page_size=5", {
        signal: controller.signal,
      }),
      api("/api/dispatch/locations", { signal: controller.signal }),
    ];
    const [arrivals, departures, locationResult] = await Promise.all(requests);
    if (requestId !== dashboard.requestId) return;
    dashboard.arrivals = arrivals.movements || [];
    dashboard.arrivalsTotal = Number(arrivals.total || 0);
    dashboard.departures = departures.movements || [];
    dashboard.departuresTotal = Number(departures.total || 0);
    dashboard.locations = (locationResult.locations || []).filter(
      (location) => location.can_depart || location.can_arrive,
    );
    dashboard.loaded = true;
  } catch (error) {
    if (requestId === dashboard.requestId) {
      dashboard.error = controller.signal.aborted
        ? "Dispatch data did not load within 20 seconds. Check your connection and retry."
        : error.message || "Could not load your dispatch dashboard.";
    }
  } finally {
    window.clearTimeout(timeoutId);
    if (requestId === dashboard.requestId) {
      dashboard.loading = false;
      if (state.page === "dashboard") render();
    }
  }
}

function renderDispatcherDashboard(data, summary) {
  const dashboard = state.dispatch.dashboard;
  const locations = dashboard.locations;
  const assignedLocationText = locations.length
    ? locations.map((location) => `${location.name} (${location.id})`).join(", ")
    : dashboard.loaded ? "No active location assignment" : "Loading assigned locations…";
  const operationalDate = new Intl.DateTimeFormat("en-PH", {
    dateStyle: "full",
    timeZone: "Asia/Manila",
  }).format(new Date());
  const queueCard = (label, total, tab, description) => `
    <button class="dispatcher-summary-card" type="button" data-action="dispatcher-open-queue" data-tab="${tab}">
      <span>${escapeHtml(label)}</span>
      <strong>${dashboard.loaded ? formatNumber(total) : "—"}</strong>
      <small>${escapeHtml(dashboard.loaded ? description : "Loading authorized queue…")}</small>
    </button>`;
  const priorityContent = !dashboard.loaded && !dashboard.error
    ? '<div class="dispatcher-dashboard-state" role="status">Loading arrival tasks…</div>'
    : dashboard.error && !dashboard.loaded
      ? `<div class="dispatcher-dashboard-state dispatcher-dashboard-error" role="alert">
          <p>${escapeHtml(dashboard.error)}</p>
          <button class="button button-secondary" type="button" data-action="dispatcher-dashboard-retry">Retry</button>
        </div>`
      : dashboard.arrivals.length
        ? `<div class="dispatch-movement-list dispatcher-arrival-list">
            ${dashboard.arrivals.map((movement) => dispatchMovementCard(movement, "arrivals")).join("")}
          </div>
          ${dashboard.arrivalsTotal > dashboard.arrivals.length
            ? '<button class="button button-secondary dispatcher-view-all" type="button" data-action="dispatcher-open-queue" data-tab="arrivals">View all pending arrivals</button>'
            : ""}`
        : '<div class="dispatcher-dashboard-state"><strong>No pending arrivals</strong><span>New receiving tasks will appear here.</span></div>';

  return `
    <section class="dispatcher-dashboard">
      <header class="dispatcher-welcome">
        <div>
          <p class="eyebrow">DISPATCHER WORKSPACE</p>
          <h1>Good ${new Date().getHours() < 12 ? "morning" : "day"}, ${escapeHtml(data.user?.full_name || data.user?.email || "Dispatcher")}</h1>
          <p class="dispatcher-date">${escapeHtml(operationalDate)}</p>
        </div>
        <div class="dispatcher-location" aria-live="polite">
          <span class="dispatcher-location-label">Assigned location${locations.length === 1 ? "" : "s"}</span>
          <strong>${escapeHtml(assignedLocationText)}</strong>
        </div>
      </header>

      <nav class="dispatcher-quick-actions" aria-label="Dispatch shortcuts">
        <a class="button button-primary dispatcher-primary-action" href="/dispatcher/add-trip">Record Departure</a>
        <button class="button button-secondary dispatcher-secondary-action" type="button"
          data-action="dispatcher-open-queue" data-tab="arrivals">Open Pending Arrivals</button>
      </nav>

      <section aria-labelledby="dispatcher-summary-title">
        <div class="dispatcher-section-heading">
          <div><p class="eyebrow">TODAY AT A GLANCE</p><h2 id="dispatcher-summary-title">Operational queues</h2></div>
        </div>
        <div class="dispatcher-summary-grid">
          ${queueCard("Pending arrivals", dashboard.arrivalsTotal, "arrivals", "Receiving locations you can access")}
          ${queueCard("Open outbound movements", dashboard.departuresTotal, "departures", "Open movements at departure locations")}
          <article class="dispatcher-summary-card dispatcher-summary-static">
            <span>Trip records today</span>
            <strong>${formatNumber(summary.today_trips)}</strong>
            <small>Trip records dated today for your account</small>
          </article>
        </div>
        <p class="dispatcher-queue-note">Queue totals reflect your location permissions. A movement may appear in both queues when your account is authorized at both locations.</p>
      </section>

      <div class="dispatcher-queues-grid">
        <section class="dispatcher-priority-panel" aria-labelledby="dispatcher-priority-title">
          <div class="dispatcher-section-heading">
            <div><p class="eyebrow">PRIORITY ACTIONS</p><h2 id="dispatcher-priority-title">Arrivals to handle</h2></div>
            <button class="button button-secondary button-small" type="button" data-action="dispatcher-dashboard-retry">Refresh</button>
          </div>
          ${priorityContent}
        </section>

        <section class="dispatcher-active-panel" aria-labelledby="dispatcher-active-title">
          <div class="dispatcher-section-heading">
            <div><p class="eyebrow">IN TRANSIT</p><h2 id="dispatcher-active-title">Open outbound movements</h2></div>
            <button class="text-button" type="button" data-action="dispatcher-open-queue" data-tab="departures">View outbound queue →</button>
          </div>
          ${!dashboard.loaded && !dashboard.error
            ? '<div class="dispatcher-dashboard-state" role="status">Loading active movements…</div>'
            : dashboard.departures.length
              ? `<div class="dispatch-movement-list dispatcher-active-list">
                  ${dashboard.departures.slice(0, 3).map((movement) => dispatchMovementCard(movement, "departures")).join("")}
                </div>`
              : dashboard.error && !dashboard.loaded
                ? ""
                : '<div class="dispatcher-dashboard-state"><strong>No open outbound movements</strong><span>Movements created from your assigned locations will appear here.</span></div>'}
        </section>
      </div>

      <details class="dispatcher-records">
        <summary>My other records</summary>
        <div class="dashboard-grid">
          ${panel("My trip records", tableMarkup(data.trips.slice(0, 5), [
            ["ism_no", "ISM no"],
            ["origin", "Origin"],
            ["destination", "Destination"],
            ["shipment_date", "Shipment date"],
          ], null, { empty: "No trip records", rowAction: "trip-details" }), "trips")}
          ${panel("My fuel logs", tableMarkup(data.fuel_logs.slice(0, 5), RESOURCE_CONFIG.fuel.columns, null, { empty: "No fuel logs recorded" }), "fuel")}
          ${panel("My maintenance", tableMarkup(data.maintenance.slice(0, 5), RESOURCE_CONFIG.maintenance.columns, null, { empty: "No maintenance records" }), "maintenance")}
        </div>
      </details>
      ${tripDetailsDialogMarkup()}
    </section>`;
}

function optionMarkup(type, idPrefix = "field") {
  const records = type === "vehicle" || type === "truck"
    ? state.data.vehicles
    : type === "trailer" ? state.data.trailers || [] : state.data.drivers;
  const allowed = records.filter((record) => {
    if (type === "truck") {
      const eligible = ["active", "available", "assigned"].includes(record.status);
      return eligible || (idPrefix === "trip-edit-field"
        && String(record.id) === String(state.editingTrip?.truck_id || state.editingTrip?.vehicle_id));
    }
    if (type === "trailer") {
      const eligible = record.status === "active"
        && Number.isInteger(Number(record.pallet_capacity))
        && Number(record.pallet_capacity) > 0;
      return eligible || (idPrefix === "trip-edit-field"
        && String(record.id) === String(state.editingTrip?.trailer_id || ""));
    }
    return true;
  });
  const label = type === "vehicle" || type === "truck"
    ? (record) => `${record.plate_number} · ${record.make} ${record.model}`
    : type === "trailer"
      ? (record) => `${record.plate_number} · ${record.pallet_capacity} pallets${record.status === "active" ? "" : ` · ${record.status}`}`
      : (record) => record.name;
  const options = allowed.map((record) => `<option value="${escapeHtml(record.id)}">${escapeHtml(label(record))}</option>`).join("");
  const noun = type === "truck" ? "a truck" : type === "trailer" ? "a trailer" : type === "vehicle" ? "a vehicle" : "a driver";
  return `<option value="">Select ${noun}</option>${options}`;
}

function routeOptionsMarkup(originCode, selected = "") {
  const routes = state.data.truck_routes || [];
  const destinations = routes.filter((route) =>
    route.active !== false
      && route.origin_code === originCode
      && route.destination_code !== originCode,
  );
  return `<option value="">${originCode ? "Select a destination" : "Select an origin first"}</option>${destinations.map((route) =>
    `<option value="${escapeHtml(route.destination_code)}" ${route.destination_code === selected ? "selected" : ""}>${escapeHtml(route.destination_name)} (${escapeHtml(route.destination_code)})</option>`,
  ).join("")}`;
}

function tripRouteRate(form) {
  const origin = form.elements.namedItem("origin")?.value || "";
  const destination = form.elements.namedItem("destination")?.value || "";
  const trailerId = form.elements.namedItem("trailer_id")?.value || "";
  const route = (state.data.truck_routes || []).find((item) =>
    item.active !== false
      && item.origin_code === origin
      && item.destination_code === destination,
  );
  const trailer = (state.data.trailers || []).find((item) => String(item.id) === String(trailerId));
  const capacity = Number(trailer?.pallet_capacity);
  const rateRecord = route && [36, 46].includes(capacity)
    ? (state.data.truck_route_rates || []).find((item) =>
    item.active !== false && (item.route_id != null
        ? String(item.route_id) === String(route.id) && Number(item.pallet_capacity) === capacity
        : item.origin_code === origin && item.destination_code === destination
        && Number(item.pallet_capacity) === capacity),
    )
    : null;
  return {
    route,
    capacity: [36, 46].includes(capacity) ? capacity : null,
    rate: rateRecord?.hauling_rate ?? null,
    configured: Boolean(route && rateRecord && rateRecord.hauling_rate !== null
      && rateRecord.hauling_rate !== undefined),
  };
}

function tripRateFieldsChanged(form) {
  if (!form.classList.contains("trip-edit-form")) return true;
  return form.elements.namedItem("origin")?.value !== form.dataset.originalOrigin
    || form.elements.namedItem("destination")?.value !== form.dataset.originalDestination
    || form.elements.namedItem("trailer_id")?.value !== form.dataset.originalTrailerId;
}

function refreshTripRouteSummary(form) {
  const summary = form.querySelector(".trip-route-summary");
  if (!summary) return;
  const useSaved = form.classList.contains("trip-edit-form") && !tripRateFieldsChanged(form);
  let route;
  let capacity;
  let rate;
  let configured;
  let pair;
  let routeNumber;
  if (useSaved) {
    routeNumber = form.dataset.savedRouteNumber || "";
    pair = form.dataset.savedRoutePair || "";
    capacity = form.dataset.savedPalletCapacity || "";
    rate = form.dataset.savedTruckRate || "";
    configured = rate !== "";
  } else {
    const resolved = tripRouteRate(form);
    route = resolved.route;
    capacity = resolved.capacity;
    rate = resolved.rate;
    configured = resolved.configured;
    pair = route?.route_pair || "";
    routeNumber = route?.route_number || "";
  }
  const noLocation = !form.elements.namedItem("origin")?.value
    || !form.elements.namedItem("destination")?.value;
  summary.innerHTML = `
    <div><span>Route No.</span><strong>${escapeHtml(routeNumber || "—")}</strong></div>
    <div><span>Route Pair</span><strong>${escapeHtml(pair || "—")}</strong></div>
    <div><span>Pallet Capacity</span><strong>${capacity ? `${escapeHtml(capacity)} pallets` : "Unknown"}</strong></div>
    <div><span>Trip Rate</span><strong>${configured ? escapeHtml(formatCurrency(rate)) : "Rate not configured"}</strong></div>`;
  summary.setAttribute("aria-label", noLocation
    ? "Route information. Select an origin, destination, and vehicle."
    : "Resolved route information");
  const submit = form.querySelector('button[type="submit"]');
  if (!submit) return;
  const validityNeeded = !useSaved && !configured;
  const missingOptions = form.classList.contains("record-form")
    && (!state.data.vehicles.some((item) => ["active", "available", "assigned"].includes(item.status))
    || !(state.data.trailers || []).some((item) =>
      item.status === "active" && Number(item.pallet_capacity) > 0)
    || !state.data.drivers.length);
  submit.disabled = validityNeeded || missingOptions;
}

function refreshTripDestinationOptions(form) {
  const origin = form.elements.namedItem("origin");
  const destination = form.elements.namedItem("destination");
  if (!origin || !destination) return;
  const selected = destination.value;
  const options = routeOptionsMarkup(origin.value, selected);
  destination.innerHTML = options;
  destination.disabled = !origin.value;
  const preserveLegacySelection = form.classList.contains("trip-edit-form")
    && origin.value === form.dataset.originalOrigin
    && selected === form.dataset.originalDestination
    && selected !== "";
  if (preserveLegacySelection && ![...destination.options].some((option) => option.value === selected)) {
    destination.insertAdjacentHTML(
      "beforeend",
      `<option value="${escapeHtml(selected)}" selected>${escapeHtml(selected)} (saved, route not configured)</option>`,
    );
  }
  if (selected && ![...destination.options].some((option) => option.value === selected)) {
    destination.value = "";
  }
  refreshTripRouteSummary(form);
}

function fieldMarkup(field, idPrefix = "field") {
  const required = field.required ? "required" : "";
  const min = field.min !== undefined ? `min="${escapeHtml(field.min)}"` : "";
  const step = field.step ? `step="${escapeHtml(field.step)}"` : "";
  const value = field.value !== undefined ? `value="${escapeHtml(field.value)}"` : "";
  const id = `${idPrefix}-${field.name}`;
  let control;
  if (field.type === "select") {
    control = `<select id="${id}" name="${field.name}" ${required}>${field.options.map(([key, label]) => `<option value="${escapeHtml(key)}">${escapeHtml(label)}</option>`).join("")}</select>`;
  } else if (field.type === "origin") {
    const routes = state.data.truck_routes || [];
    const origins = [...new Map(routes
      .filter((route) => route.active !== false)
      .map((route) => [route.origin_code, route.origin_name])).entries()];
    control = `<select id="${id}" name="${field.name}" ${required}><option value="">Select an origin</option>${origins.map(([code, name]) =>
      `<option value="${escapeHtml(code)}">${escapeHtml(name)} (${escapeHtml(code)})</option>`,
    ).join("")}</select>`;
  } else if (field.type === "destination") {
    control = `<select id="${id}" name="${field.name}" ${required} disabled>${routeOptionsMarkup("")}</select>`;
  } else if (field.type === "file") {
    control = `<input id="${id}" name="${field.name}" type="file" accept="${escapeHtml(field.accept)}" ${idPrefix === "trip-wizard-field" ? 'capture="environment"' : ""} /><small class="field-hint">JPG, PNG, or WEBP image</small>`;
  } else if (["vehicle", "truck", "trailer", "driver"].includes(field.type)) {
    const records = field.type === "vehicle" || field.type === "truck"
      ? state.data.vehicles
      : field.type === "trailer" ? state.data.trailers || [] : state.data.drivers;
    const hasOptions = records.length > 0;
    const hasEligibleOptions = field.type === "trailer"
      ? records.some((record) => record.status === "active" && Number(record.pallet_capacity) > 0)
        || (idPrefix === "trip-edit-field" && Boolean(state.editingTrip?.trailer_id))
      : hasOptions;
    const hint = !hasEligibleOptions
      ? `<small class="field-hint">${field.type === "trailer" && hasOptions
        ? "Set pallet capacity for an active trailer before assigning it to a trip."
        : `Add an active ${field.type} first.`}</small>`
      : "";
    control = `<select id="${id}" name="${field.name}" ${required} ${hasEligibleOptions ? "" : "disabled"}>${optionMarkup(field.type, idPrefix)}</select>${hint}`;
  } else if (field.type === "textarea") {
    control = `<textarea id="${id}" name="${field.name}" rows="3" ${required}></textarea>`;
  } else {
    const inputType = field.type === "currency" || field.type === "fuel_allocation"
      ? "number"
      : field.type || "text";
    control = `<input id="${id}" name="${field.name}" type="${escapeHtml(inputType)}" ${min} ${step} ${value} ${required} />`;
  }
  return `<label class="form-field" for="${id}"><span>${escapeHtml(field.label)}${field.required ? " *" : ""}</span>${control}</label>`;
}

function filterRows(rows, columns) {
  const term = state.search.trim().toLocaleLowerCase();
  if (!term) return rows;
  return rows.filter((row) => columns.some(([key]) => String(row[key] ?? "").toLocaleLowerCase().includes(term)));
}

const TRIP_HISTORY_COLUMNS = [
  ["ism_no", "ISM No"],
  ["shipment_date", "Shipment date"],
  ["origin", "Route", (origin, trip) =>
    `${escapeHtml(origin || "—")} → ${escapeHtml(trip.destination || "—")}`],
  ["truck_plate_number", "Truck"],
  ["trailer_plate_number", "Trailer"],
  ["driver_name", "Driver"],
];

function groupedTripMarkup(rows, config) {
  const groupOptions = [
    ["driver_name", "Driver"],
    ["truck_plate_number", "Truck"],
    ["origin", "Origin"],
    ["destination", "Destination"],
  ];
  const selectedGroup = groupOptions.find(([key]) => key === state.tripsGroupBy);
  if (!selectedGroup) {
    return tableMarkup(
      rows,
      TRIP_HISTORY_COLUMNS,
      state.data.user?.role === "dispatcher" ? null : config.api,
      {
        empty: "No trip records",
        rowAction: "trip-details",
        selectTrips: state.data.user?.role !== "dispatcher",
      },
    );
  }

  const [groupKey, groupLabel] = selectedGroup;
  const groups = new Map();
  for (const trip of rows) {
    const value = String(trip[groupKey] || `Unassigned ${groupLabel.toLowerCase()}`);
    if (!groups.has(value)) groups.set(value, []);
    groups.get(value).push(trip);
  }

  return [...groups.entries()]
    .sort(([left], [right]) => left.localeCompare(right, undefined, { sensitivity: "base" }))
    .map(([groupName, trips]) => `
      <section class="trip-group" aria-label="${escapeHtml(groupLabel)}: ${escapeHtml(groupName)}">
        <div class="trip-group-heading">
          <h3>${escapeHtml(groupName)}</h3>
          <span class="record-count">${formatNumber(trips.length)} ${trips.length === 1 ? "trip" : "trips"}</span>
        </div>
        ${tableMarkup(
          trips,
          TRIP_HISTORY_COLUMNS,
          state.data.user?.role === "dispatcher" ? null : config.api,
          {
            empty: "No trip records",
            rowAction: "trip-details",
            selectTrips: state.data.user?.role !== "dispatcher",
          },
        )}
      </section>`)
    .join("") || `<p class="trip-empty">No trip records</p>`;
}

function tripDetailsDialogMarkup() {
  return `
    <dialog class="record-dialog trip-details-dialog" aria-labelledby="trip-details-title">
      <div class="dialog-header">
        <div><p class="eyebrow">TRIP DETAILS</p><h2 id="trip-details-title">Trip</h2></div>
        <button class="icon-button dialog-close" data-action="close-trip-details" type="button" aria-label="Close trip details">×</button>
      </div>
      <div class="trip-details-content"></div>
    </dialog>`;
}

const TRIP_HISTORY_FIELDS = [
  ["ism_no", "ISM No"],
  ["shipment_date", "Shipment date"],
  ["time_in", "Time in"],
  ["time_out", "Time out"],
  ["origin", "Origin"],
  ["destination", "Destination"],
  ["truck_id", "Truck"],
  ["trailer_id", "Trailer"],
  ["driver_id", "Driver"],
  ["load_details", "Load"],
  ["trip_fuel", "Trip/Fuel"],
  ["notes", "Notes"],
  ["route", "Route"],
  ["route_number", "Route No."],
  ["route_pair", "Route pair"],
  ["pallet_capacity", "Pallet capacity"],
  ["truck_route_rate", "Truck hauling rate"],
  ["trip_rate_review_required", "Rate review required"],
  ["manifest_object_path", "Load manifest image"],
];

function tripHistoryValue(field, value) {
  if (field === "manifest_object_path") return value ? "Attached" : "Not attached";
  if (value === null || value === undefined || value === "") return "—";
  if (field === "vehicle_id") {
    const vehicle = state.data.vehicles.find((item) => String(item.id) === String(value));
    return vehicle ? `${vehicle.plate_number} · ${vehicle.make} ${vehicle.model}` : value;
  }
  if (field === "truck_id") {
    const truck = state.data.vehicles.find((item) => String(item.id) === String(value));
    return truck ? `${truck.plate_number} · ${truck.make} ${truck.model}` : value;
  }
  if (field === "trailer_id") {
    const trailer = (state.data.trailers || []).find((item) => String(item.id) === String(value));
    return trailer ? `${trailer.plate_number} · ${trailer.pallet_capacity} pallets` : value;
  }
  if (field === "driver_id") {
    const driver = state.data.drivers.find((item) => String(item.id) === String(value));
    return driver ? driver.name : value;
  }
  return value;
}

function renderTripHistory(entries) {
  if (!entries.length) return "<p>No edits recorded yet.</p>";
  return `<ol class="trip-history-list">${entries.map((entry) => {
    const changes = TRIP_HISTORY_FIELDS
      .filter(([field]) => JSON.stringify(entry.old_values?.[field]) !== JSON.stringify(entry.new_values?.[field]))
      .map(([field, label]) => `
        <li>
          <strong>${escapeHtml(label)}</strong>
          <span>${escapeHtml(tripHistoryValue(field, entry.old_values?.[field]))} → ${escapeHtml(tripHistoryValue(field, entry.new_values?.[field]))}</span>
        </li>`)
      .join("");
    const editedAt = new Date(entry.edited_at);
    const dateLabel = Number.isNaN(editedAt.getTime()) ? entry.edited_at : editedAt.toLocaleString();
    return `<li class="trip-history-entry">
      <div class="trip-history-meta">
        <strong>${escapeHtml(entry.edited_by_email || (entry.edited_by ? `User ${entry.edited_by}` : "Unknown user"))}</strong>
        <time>${escapeHtml(dateLabel)}</time>
      </div>
      <ul>${changes || "<li>Trip updated.</li>"}</ul>
    </li>`;
  }).join("")}</ol>`;
}

async function loadTripEditHistory(tripId, container) {
  try {
    const result = await api(`/api/trips/${encodeURIComponent(tripId)}/history`);
    if (container.isConnected) container.innerHTML = renderTripHistory(result.history || []);
  } catch (error) {
    if (container.isConnected) {
      container.innerHTML = `<p class="dialog-error" role="alert">${escapeHtml(error.message || "Could not load edit history.")}</p>`;
    }
  }
}

function closeAllDialogs() {
  document.querySelectorAll("dialog[open]").forEach((dialog) => {
    dialog.close();
  });
}

function openFleetAssetEditor(assetType, assetId) {
  const config = assetType === "trailer" ? RESOURCE_CONFIG.trailers : RESOURCE_CONFIG.vehicles;
  const collection = assetType === "trailer" ? state.data.trailers || [] : state.data.vehicles;
  const record = collection.find((item) => String(item.id) === String(assetId));
  const dialog = view.querySelector(".fleet-edit-dialog");
  if (!record || !dialog) return;
  const form = dialog.querySelector(".fleet-edit-form");
  form.dataset.assetType = assetType;
  form.dataset.assetId = String(assetId);
  dialog.querySelector("#fleet-edit-title").textContent =
    `Edit ${assetType === "trailer" ? "trailer" : "truck"} ${record.plate_number}`;
  form.querySelector(".dialog-fields").innerHTML = config.fields.map((field) =>
    fieldMarkup(field, "fleet-edit-field"),
  ).join("");
  for (const field of config.fields) {
    const control = form.elements.namedItem(field.name);
    if (control) control.value = record[field.name] ?? "";
  }
  form.querySelector(".dialog-error").hidden = true;
  closeAllDialogs();
  if (!dialog.open) dialog.showModal();
}

function openFleetAssetDetails(assetId) {
  const trailer = (state.data.trailers || []).find((item) => String(item.id) === String(assetId));
  const dialog = view.querySelector(".trailer-details-dialog");
  if (!trailer || !dialog) return;
  dialog.dataset.trailerId = String(trailer.id);
  dialog.querySelector("#trailer-details-title").textContent =
    trailer.plate_number ? `Trailer ${trailer.plate_number}` : `Trailer #${trailer.id}`;
  const details = [
    ["Trailer ID", trailer.id],
    ["Plate number", trailer.plate_number],
    ["Pallet capacity", trailer.pallet_capacity ? `${trailer.pallet_capacity} pallets` : "Not set — review required"],
    ["Year model", trailer.year_model],
    ["Make/model", trailer.make_model],
    ["MV file number", trailer.mv_file_no],
    ["Engine number", trailer.engine_no],
    ["Chassis number", trailer.chassis_no],
    ["Trailer type", trailer.trailer_type],
    ["Status", trailer.status],
    ["Capacity review", trailer.capacity_review_required ? "Needed" : "Complete"],
    ["Remarks", trailer.remarks],
  ];
  dialog.querySelector(".trailer-details-content").innerHTML = details.map(([label, value]) => {
    const placeholderValue = typeof value === "string" && /^(0|n\/?a|null)$/i.test(value.trim());
    const displayValue = placeholderValue ? "Not provided" : value ?? "—";
    const renderedValue = label === "Status"
      ? statusBadge(displayValue)
      : label === "Capacity review"
        ? `<span class="badge ${trailer.capacity_review_required ? "badge-maintenance" : "badge-active"}">${escapeHtml(displayValue)}</span>`
        : escapeHtml(displayValue);
    return `
      <div class="trip-detail-item">
        <dt>${escapeHtml(label)}</dt>
        <dd>${renderedValue}</dd>
      </div>`;
  }).join("");
  closeAllDialogs();
  if (!dialog.open) dialog.showModal();
}

function editTrailerFromDetails() {
  const dialog = view.querySelector(".trailer-details-dialog");
  const trailerId = dialog?.dataset.trailerId;
  if (!trailerId) return;
  dialog.close();
  openFleetAssetEditor("trailer", trailerId);
}

function deleteTrailerFromDetails() {
  const dialog = view.querySelector(".trailer-details-dialog");
  const trailerId = dialog?.dataset.trailerId;
  if (!trailerId) return;
  const button = document.createElement("button");
  button.dataset.resource = "trailers";
  button.dataset.id = trailerId;
  deleteRecord(button);
}

async function updateFleetAsset(form) {
  if (!form.reportValidity()) return;
  const assetType = form.dataset.assetType;
  const config = assetType === "trailer" ? RESOURCE_CONFIG.trailers : RESOURCE_CONFIG.vehicles;
  const payload = Object.fromEntries(new FormData(form).entries());
  for (const field of config.fields) {
    if (field.type === "number") {
      payload[field.name] = payload[field.name] === "" ? null : Number(payload[field.name]);
    } else if (payload[field.name] === "") {
      payload[field.name] = null;
    }
  }
  const button = form.querySelector('button[type="submit"]');
  const error = form.querySelector(".dialog-error");
  button.disabled = true;
  error.hidden = true;
  try {
    const result = await api(`/api/${config.api}/${encodeURIComponent(form.dataset.assetId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    const record = result?.data || { ...payload, id: form.dataset.assetId };
    upsertResourceRecord(config.api, record);
    view.querySelector(".fleet-edit-dialog")?.close();
    showToast(`${assetType === "trailer" ? "Trailer" : "Truck"} updated.`);
    render();
  } catch (updateError) {
    error.textContent = updateError.message || "Could not update this fleet record.";
    error.hidden = false;
  } finally {
    if (button.isConnected) button.disabled = false;
  }
}

const TRIP_WIZARD_STEPS = [
  { title: "Trip Details" },
  { title: "Driver and Vehicle Assignment" },
  { title: "Load Information" },
  { title: "Fuel Details" },
  { title: "Review Trip" },
];

function wizardFieldsMarkup(config, names) {
  return names.map((name) => {
    const field = config.fields.find((item) => item.name === name);
    return field ? fieldMarkup(field, "trip-wizard-field") : "";
  }).join("");
}

function tripCreationWizardMarkup(config, needsReferences, standalone = false) {
  const steps = TRIP_WIZARD_STEPS.map((step, index) => `
    <li class="trip-wizard-progress-item">
      <button class="trip-wizard-progress-step" type="button" data-action="trip-wizard-go-step"
        data-step="${index}" aria-label="Step ${index + 1}: ${escapeHtml(step.title)}">
        <span class="trip-wizard-step-number">${index + 1}</span>
        <span class="trip-wizard-step-name">${escapeHtml(step.title)}</span>
      </button>
    </li>`).join("");
  const loadType = fieldMarkup({
    name: "load_type",
    label: "Load type",
    type: "select",
    options: [["", "Select load type"], ["Full", "Full"], ["Empty", "Empty"]],
  }, "trip-wizard-field");
  const fuelFields = wizardFieldsMarkup(config, [
    "fuel_allocation", "actual_fuel_expense", "invoice_image", "fuel_remarks",
  ]);
  const cancelLabel = standalone ? "Back to Trips" : "Cancel";
  const wrapper = standalone
    ? `<section class="trip-wizard-page" aria-labelledby="trip-wizard-title">`
    : `<dialog class="record-dialog trip-wizard-dialog" aria-labelledby="trip-wizard-title">`;
  const closeTag = standalone ? "</section>" : "</dialog>";
  const closeButton = standalone
    ? `<a class="button button-secondary trip-wizard-cancel" href="/#trips" data-action="trip-wizard-cancel">${cancelLabel}</a>`
    : `<button class="icon-button dialog-close" data-action="trip-wizard-cancel" type="button" aria-label="Cancel trip creation">×</button>`;

  return `
    ${wrapper}
      ${standalone ? `<div class="page-heading"><div><p class="eyebrow">DISPATCHER</p><h1 id="trip-wizard-title">Add New Trip</h1><p class="page-description">Create a shipment record, confirm its route and rate, then save the trip and any supporting document.</p></div><a class="button button-secondary" href="#trips">Back to Trips</a></div>` : `<div class="dialog-header"><div><p class="eyebrow">NEW TRIP · STEP <span data-wizard-current-step>1</span> OF ${TRIP_WIZARD_STEPS.length}</p><h2 id="trip-wizard-title">Trip Details</h2></div>${closeButton}</div>`}
      <form class="trip-wizard-form" data-form="trips" novalidate>
        <div class="trip-wizard-content">
          <div class="trip-wizard-progress-wrap">
            <progress class="trip-wizard-progress-bar" max="${TRIP_WIZARD_STEPS.length}" value="1" aria-label="Trip creation progress"></progress>
            <ol class="trip-wizard-progress">${steps}</ol>
          </div>
          <section class="trip-wizard-step" data-step="0" aria-labelledby="trip-wizard-step-title-0">
            <h3 id="trip-wizard-step-title-0" tabindex="-1">Trip Details</h3>
            <p class="trip-wizard-instruction">Enter the shipment date, route, and trip reference.</p>
            <div class="dialog-fields">${wizardFieldsMarkup(config, ["shipment_date", "origin", "destination", "ism_no", "time_in", "time_out"])}</div>
            <section class="trip-route-summary trip-wizard-route-summary" aria-live="polite" aria-label="Detected route information"></section>
            <p class="trip-wizard-field-error" data-wizard-route-error role="alert" hidden></p>
          </section>
          <section class="trip-wizard-step" data-step="1" aria-labelledby="trip-wizard-step-title-1" hidden>
            <h3 id="trip-wizard-step-title-1" tabindex="-1">Driver and Vehicle Assignment</h3>
            <p class="trip-wizard-instruction">Select an eligible truck, configured trailer, and driver.</p>
            <div class="dialog-fields">${wizardFieldsMarkup(config, ["driver_id", "truck_id", "trailer_id"])}</div>
            <section class="trip-wizard-selection-summary" aria-live="polite"></section>
            <section class="trip-route-summary trip-wizard-assignment-route-summary" aria-live="polite" aria-label="Route rate and trailer capacity"></section>
            <p class="trip-wizard-field-error" data-wizard-assignment-error role="alert" hidden></p>
          </section>
          <section class="trip-wizard-step" data-step="2" aria-labelledby="trip-wizard-step-title-2" hidden>
            <h3 id="trip-wizard-step-title-2" tabindex="-1">Load Information</h3>
            <p class="trip-wizard-instruction">Record the load in the existing trip details field and attach documentation if available.</p>
            <div class="dialog-fields">
              ${loadType}
              ${wizardFieldsMarkup(config, ["load_details", "trip_fuel", "notes", "manifest_image"])}
            </div>
            <p class="trip-wizard-field-hint">Load type is recorded with the existing load details.</p>
            <div class="trip-wizard-image-preview" data-image-preview="manifest_image" hidden>
              <img alt="Selected load manifest preview" />
            </div>
          </section>
          <section class="trip-wizard-step" data-step="3" aria-labelledby="trip-wizard-step-title-3" hidden>
            <h3 id="trip-wizard-step-title-3" tabindex="-1">Fuel Details</h3>
            <p class="trip-wizard-instruction">Allocation is a monetary value in Philippine pesos. Liters are only shown when a quantity is recorded.</p>
            <div class="trip-wizard-route-card" aria-live="polite"></div>
            <div class="dialog-fields">${fuelFields}</div>
            <p class="trip-wizard-field-hint">Fuel allocation and actual expense are stored separately. Fuel entries and invoice images are optional under the current workflow.</p>
            <div class="trip-wizard-image-preview" data-image-preview="invoice_image" hidden>
              <img alt="Selected fuel invoice preview" />
            </div>
          </section>
          <section class="trip-wizard-step" data-step="4" aria-labelledby="trip-wizard-step-title-4" hidden>
            <h3 id="trip-wizard-step-title-4" tabindex="-1">Review Trip</h3>
            <p class="trip-wizard-instruction">Check each section. Use Edit to return to a step without losing your entries.</p>
            <div class="trip-wizard-review"></div>
            <p class="trip-wizard-save-error" role="alert" hidden></p>
          </section>
          <p class="dialog-error trip-wizard-error" role="alert" hidden></p>
          <div class="trip-wizard-actions">
            <button class="button button-secondary trip-wizard-back" data-action="trip-wizard-back" type="button" hidden>Back</button>
            <button class="button button-secondary trip-wizard-cancel" data-action="trip-wizard-cancel" type="button">${cancelLabel}</button>
            <button class="button button-secondary trip-wizard-continue" data-action="trip-wizard-continue" type="button">Continue</button>
            <button class="button button-primary trip-wizard-submit" data-action="trip-wizard-submit" type="button" hidden ${needsReferences ? "disabled" : ""}>Confirm and Save Trip</button>
          </div>
        </div>
      </form>
    ${closeTag}`;
}

function tripWizardForm() {
  return view.querySelector(".trip-wizard-form");
}

function tripWizardRecord(form, name) {
  const id = form.elements.namedItem(name)?.value;
  const collection = name === "driver_id"
    ? state.data.drivers
    : name === "truck_id" ? state.data.vehicles : state.data.trailers || [];
  return collection.find((record) => String(record.id) === String(id));
}

function tripWizardRoute(form) {
  const origin = form.elements.namedItem("origin")?.value;
  const destination = form.elements.namedItem("destination")?.value;
  return (state.data.truck_routes || []).find((route) =>
    route.active !== false
      && route.origin_code === origin
      && route.destination_code === destination,
  );
}

function tripWizardRouteSummaryMarkup(form, includeRate) {
  const route = tripWizardRoute(form);
  const allocation = route?.fuel_allocation;
  const resolved = tripRouteRate(form);
  return `
    <div><span>Route No.</span><strong>${escapeHtml(route?.route_number || "—")}</strong></div>
    <div><span>Route</span><strong>${escapeHtml(route?.route_pair || (route ? `${route.origin_name} → ${route.destination_name}` : "No matching route"))}</strong></div>
    <div><span>Trailer capacity</span><strong>${escapeHtml(resolved.capacity ? `${resolved.capacity} pallets` : "Select a configured trailer")}</strong></div>
    <div><span>Trip rate</span><strong>${includeRate && resolved.configured ? escapeHtml(formatCurrency(resolved.rate)) : includeRate ? "Rate not configured" : route ? "Determined by trailer capacity" : "No valid route"}</strong></div>
    ${allocation != null ? `<div><span>Fuel allocation</span><strong>${escapeHtml(formatCurrency(allocation))}</strong></div>` : ""}`;
}

function tripWizardImagePreview(form, fieldName) {
  const file = form.elements.namedItem(fieldName)?.files?.[0];
  const preview = form.querySelector(`[data-image-preview="${fieldName}"]`);
  if (!preview) return "";
  if (!file) {
    preview.hidden = true;
    return "";
  }
  return escapeHtml(state.tripWizard.objectUrls[fieldName] || "");
}

function tripWizardReviewMarkup(form) {
  const value = (name) => form.elements.namedItem(name)?.value || "";
  const route = tripWizardRoute(form);
  const resolved = tripRouteRate(form);
  const driver = tripWizardRecord(form, "driver_id");
  const truck = tripWizardRecord(form, "truck_id");
  const trailer = tripWizardRecord(form, "trailer_id");
  const allocation = value("fuel_allocation");
  const actualExpense = value("actual_fuel_expense");
  const section = (step, title, rows, image = "") => `
    <section class="trip-wizard-review-section">
      <div class="trip-wizard-review-heading"><h4>${escapeHtml(title)}</h4><button class="button button-secondary button-small" type="button" data-action="trip-wizard-go-step" data-step="${step}">Edit</button></div>
      <dl>${rows.map(([label, content]) => `<div><dt>${escapeHtml(label)}</dt><dd>${content || "—"}</dd></div>`).join("")}</dl>
      ${image}
    </section>`;
  const imageMarkup = (src, alt, emptyText) => src
    ? `<img class="trip-wizard-review-image" src="${src}" alt="${escapeHtml(alt)}" />`
    : `<p class="trip-wizard-review-note">${escapeHtml(emptyText)}</p>`;
  const imageLinkMarkup = (fieldName, alt, emptyText) => {
    const file = form.elements.namedItem(fieldName)?.files?.[0];
    return file ? imageMarkup(
      tripWizardImagePreview(form, fieldName),
      alt,
      emptyText,
    ) : `<p class="trip-wizard-review-note">${escapeHtml(emptyText)}</p>`;
  };
  return `
    ${section(0, "Trip Details", [
      ["Date", escapeHtml(value("shipment_date"))],
      ["Time in", escapeHtml(value("time_in"))],
      ["Time out", escapeHtml(value("time_out"))],
      ["Origin", escapeHtml(route?.origin_name || value("origin"))],
      ["Destination", escapeHtml(route?.destination_name || value("destination"))],
      ["Route number", escapeHtml(route?.route_number || "—")],
      ["ISM / reference", escapeHtml(value("ism_no"))],
      ["Trip rate", resolved.configured ? escapeHtml(formatCurrency(resolved.rate)) : "Rate not configured"],
    ])}
    ${section(1, "Driver and Vehicles", [
      ["Driver", escapeHtml(driver?.name || "—")],
      ["Truck", escapeHtml(truck ? `${truck.plate_number} · ${truck.make} ${truck.model}` : "—")],
      ["Trailer", escapeHtml(trailer?.plate_number || "—")],
      ["Trailer pallet capacity", escapeHtml(trailer?.pallet_capacity ? `${trailer.pallet_capacity} pallets` : "Unknown")],
    ])}
    ${section(2, "Load Information", [
      ["Load type", escapeHtml(value("load_type"))],
      ["Load details", escapeHtml(value("load_details"))],
      ["Trip/Fuel", escapeHtml(value("trip_fuel"))],
      ["Notes", escapeHtml(value("notes"))],
    ], imageLinkMarkup("manifest_image", "Selected load manifest", "No manifest image selected."))}
    ${section(3, "Fuel Allocation", [
      ["Selected route", escapeHtml(route ? `${route.origin_name} → ${route.destination_name}` : "—")],
      ["Configured allocation", route?.fuel_allocation == null ? "Not configured" : escapeHtml(formatCurrency(route.fuel_allocation))],
      ["Fuel allocation amount", allocation ? escapeHtml(formatCurrency(allocation)) : "Not entered"],
      ["Actual fuel expenditure", actualExpense ? escapeHtml(formatCurrency(actualExpense)) : "Not entered"],
      ["Fuel remarks", escapeHtml(value("fuel_remarks"))],
    ], imageLinkMarkup("invoice_image", "Selected fuel invoice", "No fuel invoice selected."))}`;
}

function updateTripWizard(form) {
  const step = state.tripWizard.step;
  const current = TRIP_WIZARD_STEPS[step];
  form.querySelectorAll(".trip-wizard-step").forEach((panel, index) => {
    panel.hidden = index !== step;
  });
  const dialog = form.closest(".trip-wizard-dialog");
  if (dialog) {
    const stepMarker = dialog.querySelector("[data-wizard-current-step]");
    const title = dialog.querySelector("#trip-wizard-title");
    if (stepMarker) stepMarker.textContent = String(step + 1);
    if (title) title.textContent = current.title;
  }
  const isStandalonePage = window.location.pathname === "/dispatcher/add-trip";
  if (isStandalonePage) {
    const title = form.closest(".trip-wizard-page")?.querySelector("#trip-wizard-title");
    if (title) title.textContent = current.title;
  }
  form.querySelector(".trip-wizard-progress-bar").value = step + 1;
  form.querySelectorAll(".trip-wizard-progress-step").forEach((button, index) => {
    button.classList.toggle("is-complete", index < step);
    button.classList.toggle("is-current", index === step);
    if (index === step) button.setAttribute("aria-current", "step");
    else button.removeAttribute("aria-current");
    button.disabled = index >= step;
  });
  if (state.tripWizard.createdTripId) lockTripWizardForm(form);
  else form.querySelectorAll("input, select, textarea").forEach((control) => {
    control.disabled = false;
  });
  form.querySelector(".trip-wizard-back").hidden = step === 0;
  form.querySelector(".trip-wizard-continue").hidden = step === TRIP_WIZARD_STEPS.length - 1;
  form.querySelector(".trip-wizard-submit").hidden = step !== TRIP_WIZARD_STEPS.length - 1;
  form.querySelector(".trip-wizard-error").hidden = true;
  form.querySelector(".trip-wizard-route-summary").innerHTML =
    tripWizardRouteSummaryMarkup(form, false);
  form.querySelector(".trip-wizard-assignment-route-summary").innerHTML =
    tripWizardRouteSummaryMarkup(form, true);
  form.querySelector(".trip-wizard-selection-summary").innerHTML =
    tripWizardAssignmentSummaryMarkup(form);
  const route = tripWizardRoute(form);
  form.querySelector(".trip-wizard-route-card").innerHTML = route
    ? `<strong>${escapeHtml(route.origin_name)} → ${escapeHtml(route.destination_name)}</strong><span>Route ${escapeHtml(route.route_number)}${route.fuel_allocation == null ? "" : ` · configured fuel allocation ${escapeHtml(formatCurrency(route.fuel_allocation))}`}</span>`
    : `<span class="trip-wizard-route-warning">Choose a valid origin and destination to see route allocation.</span>`;
  if (step === 3) applyTripWizardFuelAllocation(form);
  if (step === 4) {
    form.querySelector(".trip-wizard-review").innerHTML = tripWizardReviewMarkup(form);
  }
}

function tripWizardAssignmentSummaryMarkup(form) {
  const driver = tripWizardRecord(form, "driver_id");
  const truck = tripWizardRecord(form, "truck_id");
  const trailer = tripWizardRecord(form, "trailer_id");
  const items = [
    ["Driver", driver?.name || "Not selected"],
    ["Truck", truck ? `${truck.plate_number} · ${truck.make} ${truck.model}` : "Not selected"],
    ["Trailer", trailer ? `${trailer.plate_number} · ${trailer.pallet_capacity || "Unknown"} pallets` : "Not selected"],
  ];
  return `<dl>${items.map(([label, detail]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(detail)}</dd></div>`).join("")}</dl>`;
}

function applyTripWizardFuelAllocation(form) {
  const input = form.elements.namedItem("fuel_allocation");
  const route = tripWizardRoute(form);
  if (!input) return;
  if (route?.fuel_allocation !== null && route?.fuel_allocation !== undefined) {
    input.value = String(route.fuel_allocation);
    input.readOnly = true;
    input.dataset.configuredAllocation = "true";
    input.removeAttribute("aria-invalid");
  } else {
    if (input.dataset.configuredAllocation === "true") input.value = "";
    input.readOnly = false;
    delete input.dataset.configuredAllocation;
  }
}

function tripWizardStepValid(form, step) {
  const panel = form.querySelector(`.trip-wizard-step[data-step="${step}"]`);
  const customError = form.querySelector(step === 0
    ? "[data-wizard-route-error]"
    : "[data-wizard-assignment-error]");
  if (customError) {
    customError.hidden = true;
    customError.textContent = "";
  }
  const controls = [...panel.querySelectorAll("input, select, textarea")];
  for (const control of controls) {
    if (control.type === "file" && control.files?.[0]) {
      const file = control.files[0];
      const supportedMimeType = ["image/jpeg", "image/png", "image/webp"].includes(file.type);
      const supportedExtension = !file.type && /\.(jpe?g|png|webp)$/i.test(file.name);
      if (!supportedMimeType && !supportedExtension) {
        control.setCustomValidity("Choose a JPG, PNG, or WEBP image.");
        control.reportValidity();
        return false;
      }
      if (file.size > 10 * 1024 * 1024) {
        control.setCustomValidity("Image files must be 10 MB or smaller.");
        control.reportValidity();
        return false;
      }
      control.setCustomValidity("");
    }
    if (!control.reportValidity()) return false;
  }
  if (step === 0 && !tripWizardRoute(form)) {
    const error = form.querySelector("[data-wizard-route-error]");
    error.textContent = "No configured route matches these locations. Choose a valid origin and destination.";
    error.hidden = false;
    return false;
  }
  if (step === 1) {
    const truck = tripWizardRecord(form, "truck_id");
    const trailer = tripWizardRecord(form, "trailer_id");
    const resolved = tripRouteRate(form);
    const assignmentError = form.querySelector("[data-wizard-assignment-error]");
    const issue = !truck || !["active", "available", "assigned"].includes(truck.status)
      ? "Choose an available truck."
      : !trailer || trailer.status !== "active" || Number(trailer.pallet_capacity) <= 0
        ? "Choose an active trailer with a configured pallet capacity."
        : !resolved.configured ? "No trip rate is configured for this route and trailer capacity."
          : "";
    if (issue) {
      assignmentError.textContent = issue;
      assignmentError.hidden = false;
      return false;
    }
  }
  return true;
}

function tripWizardAdvance(form) {
  const step = state.tripWizard.step;
  if (!tripWizardStepValid(form, step)) return;
  state.tripWizard.step = Math.min(step + 1, TRIP_WIZARD_STEPS.length - 1);
  updateTripWizard(form);
  form.querySelector(`.trip-wizard-step[data-step="${state.tripWizard.step}"] h3`)?.focus();
}

function resetTripWizard(form) {
  Object.values(state.tripWizard.objectUrls).forEach((url) => URL.revokeObjectURL(url));
  form.reset();
  form.querySelectorAll("input, select, textarea").forEach((control) => {
    control.disabled = false;
    control.setCustomValidity("");
  });
  form.querySelectorAll(".trip-wizard-image-preview").forEach((preview) => {
    preview.hidden = true;
    preview.querySelector("img").removeAttribute("src");
  });
  const dateControl = form.elements.namedItem("shipment_date");
  if (dateControl) dateControl.value = isoDate(new Date());
  state.tripWizard = {
    step: 0,
    dirty: false,
    createdTripId: null,
    manifestUploaded: false,
    invoiceUploaded: false,
    objectUrls: {},
    submitting: false,
  };
  refreshTripDestinationOptions(form);
  updateTripWizard(form);
}

function lockTripWizardForm(form) {
  form.querySelectorAll("input, select, textarea").forEach((control) => {
    if (control.type !== "file") {
      control.disabled = true;
      return;
    }
    const uploaded = control.name === "manifest_image"
      ? state.tripWizard.manifestUploaded
      : state.tripWizard.invoiceUploaded;
    control.disabled = uploaded;
  });
}

function tireQueryKey() {
  const {
    items, summary, total, loading, error, requestedKey, warning_percent, ...filters
  } = state.tires;
  return JSON.stringify(filters);
}

async function loadTireMonitoring() {
  const key = tireQueryKey();
  state.tires.requestedKey = key;
  state.tires.loading = true;
  state.tires.error = "";
  if (state.page === "tires") render();
  const params = new URLSearchParams();
  for (const keyName of [
    "search", "asset_type", "asset_id", "status", "date_from", "date_to",
    "lifespan_min", "lifespan_max", "condition", "sort_by", "sort_dir",
  ]) {
    if (state.tires[keyName]) params.set(keyName, state.tires[keyName]);
  }
  params.set("page", String(state.tires.page));
  params.set("page_size", String(state.tires.page_size));
  try {
    const result = await api(`/api/tires?${params.toString()}`);
    if (key !== tireQueryKey() || state.page !== "tires") return;
    state.tires.items = result.data || [];
    state.tires.summary = result.summary || {};
    state.tires.total = Number(result.total || 0);
    state.tires.warning_percent = Number(result.warning_percent ?? 20);
  } catch (error) {
    if (key !== tireQueryKey() || state.page !== "tires") return;
    state.tires.error = error.message || "Could not load tire records.";
  } finally {
    if (key === state.tires.requestedKey) {
      state.tires.loading = false;
      if (state.page === "tires") render();
    }
  }
}

function tireLifeMarkup(row) {
  if (row.remaining_lifespan_pct === null || row.remaining_lifespan_pct === undefined
      || row.remaining_lifespan_pct === "") return "N/A";
  const value = Number(row.remaining_lifespan_pct);
  if (!Number.isFinite(value)) return "N/A";
  const percent = Math.max(0, Math.min(100, value));
  const warning = percent <= state.tires.warning_percent;
  return `<span class="tire-life ${warning ? "is-warning" : ""}">
    <span class="tire-life-track" role="progressbar" aria-label="Remaining tire lifespan"
      aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percent.toFixed(1)}">
      <span style="width:${percent}%"></span>
    </span><strong>${percent.toFixed(1)}%</strong></span>`;
}

function tireStatusBadge(status) {
  const label = status === "installed" ? "Installed" : status === "replaced" ? "Replaced" : "Removed";
  return `<span class="badge badge-${escapeHtml(status)}">${label}</span>`;
}

function tireMonitoringTable() {
  const labels = [
    "Reference No.", "Brand", "Size", "Type", "Serial No.", "Supplier",
    "Date Installed", "Date Replaced", "Life Span (%)", "Reason", "Remarks", "Plate Number",
  ];
  const records = state.tires.items;
  if (state.tires.loading) {
    return '<div class="empty-state" role="status"><strong>Loading tire records…</strong></div>';
  }
  if (state.tires.error) {
    return `<div class="error-card tire-error"><p class="eyebrow">TIRE RECORDS</p><h2>Could not load tire data</h2><p>${escapeHtml(state.tires.error)}</p><button class="button button-primary" data-action="tire-retry" type="button">Try again</button></div>`;
  }
  if (!records.length) {
    return '<div class="empty-state"><span aria-hidden="true">◉</span><strong>No tire records match these filters</strong><small>Add a tire or adjust the filters.</small></div>';
  }
  return `<div class="table-wrap tire-table-wrap"><table class="tire-table">
    <thead><tr>${labels.map((label) => `<th scope="col">${escapeHtml(label)}</th>`).join("")}<th scope="col">Status</th><th scope="col">Actions</th></tr></thead>
    <tbody>${records.map((row) => {
      const rowValues = [
        row.reference_no, row.brand, row.size, row.tire_type, row.serial_no,
        row.supplier, row.date_installed, row.date_replaced || "—",
      ];
      return `<tr>
        ${rowValues.map((value, index) => `<td data-label="${labels[index]}">${escapeHtml(value || "—")}</td>`).join("")}
        <td data-label="Life Span (%)">${tireLifeMarkup(row)}</td>
        <td data-label="Reason"><span class="tire-cell-detail" title="${escapeHtml(row.reason || "")}">${escapeHtml(row.reason || "—")}</span></td>
        <td data-label="Remarks"><span class="tire-cell-detail" title="${escapeHtml(row.remarks || "")}">${escapeHtml(row.remarks || "—")}</span></td>
        <td data-label="Plate Number"><strong>${escapeHtml(row.plate_number || "—")}</strong><small class="tire-asset-type">${escapeHtml(row.asset_type || "")}</small></td>
        <td data-label="Status">${tireStatusBadge(row.status)}</td>
        <td data-label="Actions" class="tire-actions">
          <button class="button button-secondary button-small" type="button" data-action="tire-view" data-id="${escapeHtml(row.id)}">View</button>
          ${state.data.user?.role === "administrator" ? `
            <button class="button button-secondary button-small" type="button" data-action="tire-edit" data-id="${escapeHtml(row.id)}">Edit</button>
            ${row.status === "installed" ? `<button class="button button-secondary button-small" type="button" data-action="tire-replace" data-id="${escapeHtml(row.id)}">Replace</button><button class="button button-secondary button-small tire-remove-button" type="button" data-action="tire-remove" data-id="${escapeHtml(row.id)}">Remove</button>` : ""}
          ` : ""}
        </td>
      </tr>`;
    }).join("")}</tbody>
  </table></div>`;
}

function updateTireAssetOptions(form) {
  const assetType = form.elements.namedItem("asset_type")?.value;
  const select = form.elements.namedItem("asset_id");
  if (!select) return;
  const records = assetType === "truck"
    ? state.data.vehicles || []
    : assetType === "trailer" ? state.data.trailers || [] : [];
  select.innerHTML = `<option value="">${records.length ? "Select a plate number" : "No matching assets available"}</option>${records.map((record) =>
    `<option value="${escapeHtml(assetType)}:${escapeHtml(record.id)}">${escapeHtml(record.plate_number)}</option>`,
  ).join("")}`;
  select.disabled = records.length === 0;
}

function tireFormField(name, label, type = "text", value = "", options = {}) {
  const id = `tire-${options.form || "record"}-${name}`;
  const required = options.required ? "required" : "";
  const min = options.min !== undefined ? `min="${escapeHtml(options.min)}"` : "";
  const max = options.max !== undefined ? `max="${escapeHtml(options.max)}"` : "";
  const step = options.step ? `step="${escapeHtml(options.step)}"` : "";
  const placeholder = options.placeholder ? `placeholder="${escapeHtml(options.placeholder)}"` : "";
  if (type === "textarea") {
    return `<label class="form-field" for="${id}"><span>${escapeHtml(label)}${options.required ? " *" : ""}</span><textarea id="${id}" name="${name}" rows="3" ${required}>${escapeHtml(value)}</textarea></label>`;
  }
  return `<label class="form-field" for="${id}"><span>${escapeHtml(label)}${options.required ? " *" : ""}</span><input id="${id}" name="${name}" type="${type}" value="${escapeHtml(value)}" ${min} ${max} ${step} ${placeholder} ${required} /></label>`;
}

function tireRecordFormMarkup(mode, row = {}) {
  const isReplace = mode === "replace";
  const isEdit = mode === "edit";
  const formId = isReplace ? "tire-replace-form" : isEdit ? "tire-edit-form" : "tire-record-form";
  const title = isReplace ? "Replace tire" : isEdit ? "Edit tire details" : "Add tire record";
  const fields = [];
  if (!isEdit) {
    if (!isReplace) {
      fields.push(`<label class="form-field" for="tire-record-asset-type"><span>Asset Type *</span><select id="tire-record-asset-type" name="asset_type" required><option value="">Select asset type</option><option value="truck">Truck</option><option value="trailer">Trailer</option></select></label>`);
      fields.push(`<label class="form-field" for="tire-record-asset_id"><span>Plate Number *</span><select id="tire-record-asset_id" name="asset_id" required><option value="">Select asset type first</option></select></label>`);
    } else {
      fields.push(`<label class="form-field" for="tire-replace-plate"><span>Assigned asset</span><input id="tire-replace-plate" value="${escapeHtml(`${row.plate_number || "—"} · ${capitalize(row.asset_type || "")}`)}" readonly /></label>`);
      fields.push(tireFormField("date_replaced", "Replacement Date", "date", businessToday, { required: true, form: "replace" }));
      fields.push(tireFormField("reason", "Replacement Reason", "text", "", { required: true, form: "replace" }));
    }
  }
  fields.push(tireFormField("brand", "Brand", "text", isReplace ? row.brand : row.brand || "", { required: true, form: isReplace ? "replace" : isEdit ? "edit" : "record" }));
  fields.push(tireFormField("size", "Size", "text", row.size || "", { required: true, placeholder: "e.g. 11R22.5", form: isReplace ? "replace" : isEdit ? "edit" : "record" }));
  fields.push(tireFormField("tire_type", "Type", "text", row.tire_type || "", { required: true, placeholder: "Steer, drive, trailer…", form: isReplace ? "replace" : isEdit ? "edit" : "record" }));
  fields.push(tireFormField(
    "serial_no",
    "Serial No. (optional)",
    "text",
    isEdit ? row.serial_no || "" : "",
    { form: isReplace ? "replace" : isEdit ? "edit" : "record" },
  ));
  fields.push(tireFormField("supplier", "Supplier", "text", row.supplier || "", { form: isReplace ? "replace" : isEdit ? "edit" : "record" }));
  if (isEdit) {
    fields.push(`<div class="tire-edit-assignment"><strong>Assigned asset</strong><span>${escapeHtml(row.plate_number || "—")} · ${escapeHtml(capitalize(row.asset_type || ""))}</span><small>Installed ${escapeHtml(row.date_installed || "—")}; assignment and installation history cannot be edited.</small></div>`);
  } else if (!isReplace) {
    fields.push(tireFormField("date_installed", "Date Installed", "date", businessToday, { required: true, form: "record" }));
  }
  fields.push(tireFormField(
    "remaining_lifespan_pct",
    "Life Span (%)",
    "number",
    isReplace ? 100 : (row.remaining_lifespan_pct ?? 100),
    { required: true, min: 0, max: 100, step: "0.1", form: isReplace ? "replace" : isEdit ? "edit" : "record" },
  ));
  if (isEdit && row.reason) fields.push(tireFormField("reason", "Reason", "text", row.reason, { form: "edit" }));
  fields.push(tireFormField("remarks", "Remarks", "textarea", row.remarks || "", { form: isReplace ? "replace" : isEdit ? "edit" : "record" }));
  return `<div class="dialog-header"><div><p class="eyebrow">TIRE MONITORING</p><h2 id="tire-dialog-title">${title}</h2></div><button class="icon-button dialog-close" data-action="close-tire-dialog" type="button" aria-label="Close tire form">×</button></div>
    <form class="dialog-form tire-record-form" id="${formId}" data-tire-id="${escapeHtml(row.id || "")}">
      <div class="dialog-fields">${fields.join("")}</div>
      ${isReplace ? '<p class="field-hint">The replaced tire remains in the history, and the new tire is assigned to the same asset.</p>' : ""}
      <p class="field-hint">Life span is the recorded remaining-life percentage; inspect tread and tire condition physically.</p>
      <p class="dialog-error" role="alert" hidden></p>
      <div class="dialog-actions"><button class="button button-secondary" data-action="close-tire-dialog" type="button">Cancel</button><button class="button button-primary" type="submit">${isReplace ? "Confirm replacement" : isEdit ? "Save changes" : "Save tire"}</button></div>
    </form>`;
}

function renderTireMonitoring() {
  const tires = state.tires;
  const summary = tires.summary || {};
  const summaryValue = (key) => tires.summary
    ? formatNumber(summary[key] || 0)
    : "—";
  const admin = state.data.user?.role === "administrator";
  const selectedType = tires.asset_type;
  const assets = selectedType === "truck" ? state.data.vehicles || []
    : selectedType === "trailer" ? state.data.trailers || [] : [];
  const maxPage = Math.max(1, Math.ceil(tires.total / tires.page_size));
  return `
    ${header("FUEL & MAINTENANCE", "Tire Monitoring Sheet", "Track truck and trailer tire assignments, replacement history, and estimated remaining service life.", `<button class="button button-secondary" data-action="tire-export" type="button" ${tires.loading ? "disabled" : ""}>Export CSV</button><button class="button button-primary" data-action="tire-add" type="button" ${tires.loading ? "disabled" : ""}><span aria-hidden="true">＋</span> Add Tire</button>`)}
    <section class="tire-monitoring-page">
      <div class="stats-grid tire-summary-grid">
        ${statCard("Total Tire Records", summaryValue("total_records"), "blue", "◉")}
        ${statCard("Currently Installed", summaryValue("installed_tires"), "green", "✓")}
        ${statCard("Near End of Lifespan", summaryValue("near_end_tires"), "pink", "⌁", `At or below ${tires.warning_percent}% remaining`)}
        ${statCard("Replaced Tires", summaryValue("replaced_tires"), "sky", "↻")}
      </div>
      <section class="panel records-panel tire-records-panel">
        <div class="panel-heading records-heading">
          <div><p class="eyebrow">TIRE HISTORY</p><h2>Records</h2></div>
          <span class="record-count">${formatNumber(tires.total)} ${tires.total === 1 ? "record" : "records"}</span>
        </div>
        <form class="tire-filters" id="tire-filter-form">
          <label class="search-box tire-search"><span class="sr-only">Search tires</span><span aria-hidden="true">⌕</span><input type="search" id="tire-search" name="search" placeholder="Reference, brand, size, serial, supplier…" value="${escapeHtml(tires.search)}" /></label>
          <label class="form-field"><span>Asset Type</span><select name="asset_type" data-tire-filter><option value="">All assets</option><option value="truck" ${selectedType === "truck" ? "selected" : ""}>Truck</option><option value="trailer" ${selectedType === "trailer" ? "selected" : ""}>Trailer</option></select></label>
          <label class="form-field"><span>Plate Number</span><select name="asset_id" data-tire-filter ${selectedType ? "" : "disabled"}><option value="">All plates</option>${assets.map((asset) => `<option value="${escapeHtml(asset.id)}" ${String(asset.id) === tires.asset_id ? "selected" : ""}>${escapeHtml(asset.plate_number)}</option>`).join("")}</select></label>
          <label class="form-field"><span>Tire Status</span><select name="status" data-tire-filter><option value="">All statuses</option><option value="installed" ${tires.status === "installed" ? "selected" : ""}>Installed</option><option value="replaced" ${tires.status === "replaced" ? "selected" : ""}>Replaced</option><option value="removed" ${tires.status === "removed" ? "selected" : ""}>Removed</option></select></label>
          <label class="form-field"><span>Installed From</span><input type="date" name="date_from" value="${escapeHtml(tires.date_from)}" data-tire-filter /></label>
          <label class="form-field"><span>Installed To</span><input type="date" name="date_to" value="${escapeHtml(tires.date_to)}" data-tire-filter /></label>
          <label class="form-field"><span>Life Span Min (%)</span><input type="number" name="lifespan_min" min="0" max="100" value="${escapeHtml(tires.lifespan_min)}" data-tire-filter /></label>
          <label class="form-field"><span>Life Span Max (%)</span><input type="number" name="lifespan_max" min="0" max="100" value="${escapeHtml(tires.lifespan_max)}" data-tire-filter /></label>
          <label class="form-field"><span>Condition</span><select name="condition" data-tire-filter><option value="">Any condition</option><option value="near_end" ${tires.condition === "near_end" ? "selected" : ""}>Near end (≤ ${tires.warning_percent}%)</option><option value="above_warning" ${tires.condition === "above_warning" ? "selected" : ""}>Above warning level</option></select></label>
          <label class="form-field"><span>Sort By</span><select name="sort_by" data-tire-filter><option value="date_installed" ${tires.sort_by === "date_installed" ? "selected" : ""}>Installation date</option><option value="lifespan" ${tires.sort_by === "lifespan" ? "selected" : ""}>Lifespan</option><option value="brand" ${tires.sort_by === "brand" ? "selected" : ""}>Brand</option><option value="plate" ${tires.sort_by === "plate" ? "selected" : ""}>Plate number</option></select></label>
          <label class="form-field"><span>Sort Direction</span><select name="sort_dir" data-tire-filter><option value="desc" ${tires.sort_dir === "desc" ? "selected" : ""}>Descending</option><option value="asc" ${tires.sort_dir === "asc" ? "selected" : ""}>Ascending</option></select></label>
          <button class="button button-secondary button-small tire-reset-button" type="button" data-action="tire-reset">Reset filters</button>
        </form>
        ${tireMonitoringTable()}
        <div class="tire-pagination" aria-label="Tire record pages">
          <span>Page ${tires.page} of ${maxPage} · ${formatNumber(tires.total)} records</span>
          <div><button class="button button-secondary button-small" type="button" data-action="tire-page" data-page="${tires.page - 1}" ${tires.page <= 1 || tires.loading ? "disabled" : ""}>Previous</button><button class="button button-secondary button-small" type="button" data-action="tire-page" data-page="${tires.page + 1}" ${tires.page >= maxPage || tires.loading ? "disabled" : ""}>Next</button></div>
        </div>
      </section>
      <p class="tire-lifespan-note">Life Span (%) is the recorded estimate of remaining tire life. New tires default to 100%; update the percentage after inspections or service. It does not replace physical tread inspection.</p>
      <dialog class="record-dialog tire-dialog" id="tire-dialog" aria-labelledby="tire-dialog-title"><div id="tire-dialog-content"></div></dialog>
    </section>`;
}

function tireDialogContent(markup, focusSelector = "input, select, textarea") {
  const dialog = view.querySelector("#tire-dialog");
  const content = view.querySelector("#tire-dialog-content");
  if (!dialog || !content) return null;
  content.innerHTML = markup;
  if (!dialog.open) dialog.showModal();
  content.querySelector(focusSelector)?.focus();
  return dialog;
}

function tireHistoryMarkup(entries) {
  if (!entries.length) return '<p class="tire-history-empty">No audit history is available.</p>';
  return `<ol class="tire-history-list">${entries.map((entry) => {
    const timestamp = new Date(entry.created_at);
    const timeLabel = Number.isNaN(timestamp.getTime())
      ? entry.created_at || ""
      : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(timestamp);
    const snapshot = entry.new_values && JSON.stringify(entry.new_values, null, 2);
    return `<li><div><strong>${escapeHtml(capitalize(entry.action || "updated"))}</strong><time>${escapeHtml(timeLabel)}</time></div>
      <small>Recorded by ${escapeHtml(entry.actor_id || "system")}</small>
      ${snapshot ? `<details><summary>View recorded details</summary><pre>${escapeHtml(snapshot)}</pre></details>` : ""}
    </li>`;
  }).join("")}</ol>`;
}

async function openTireDetails(tireId) {
  const dialog = view.querySelector("#tire-dialog");
  if (!dialog) return;
  tireDialogContent('<div class="dialog-header"><div><p class="eyebrow">TIRE MONITORING</p><h2 id="tire-dialog-title">Loading tire details…</h2></div><button class="icon-button dialog-close" data-action="close-tire-dialog" type="button" aria-label="Close tire details">×</button></div><p class="loading-card">Loading record and audit history…</p>', ".loading-card");
  try {
    const result = await api(`/api/tires/${encodeURIComponent(tireId)}`);
    const row = result.data;
    const entries = [
      ["Reference No.", row.reference_no],
      ["Asset", `${row.plate_number || "—"} · ${capitalize(row.asset_type || "")}`],
      ["Status", tireStatusBadge(row.status)],
      ["Brand", row.brand],
      ["Size", row.size],
      ["Type", row.tire_type],
      ["Serial No.", row.serial_no],
      ["Supplier", row.supplier],
      ["Date Installed", row.date_installed],
      ["Date Replaced", row.date_replaced],
      ["Replaces Tire", result.replaces ? `${result.replaces.reference_no} · ${result.replaces.brand} ${result.replaces.size}` : null],
      ["Replacement Tire", result.replacement ? `${result.replacement.reference_no} · ${result.replacement.brand} ${result.replacement.size}` : null],
      ["Remaining Lifespan", tireLifeMarkup(row)],
      ["Reason", row.reason],
      ["Remarks", row.remarks],
      ["Created", row.created_at],
    ];
    const detailRows = entries.map(([label, value]) =>
      `<div class="tire-detail-row"><dt>${escapeHtml(label)}</dt><dd>${label === "Status" || label === "Remaining Lifespan" ? value || "—" : escapeHtml(value || "—")}</dd></div>`,
    ).join("");
    const adminActions = state.data.user?.role === "administrator" ? `
      <button class="button button-secondary" data-action="tire-edit" data-id="${escapeHtml(row.id)}" type="button">Edit details</button>
      ${row.status === "installed" ? `<button class="button button-secondary" data-action="tire-replace" data-id="${escapeHtml(row.id)}" type="button">Replace tire</button><button class="button button-secondary tire-remove-button" data-action="tire-remove" data-id="${escapeHtml(row.id)}" type="button">Remove tire</button>` : ""}
    ` : "";
    tireDialogContent(`
      <div class="dialog-header"><div><p class="eyebrow">TIRE MONITORING · ${escapeHtml(row.reference_no)}</p><h2 id="tire-dialog-title">Tire details</h2></div><button class="icon-button dialog-close" data-action="close-tire-dialog" type="button" aria-label="Close tire details">×</button></div>
      <div class="tire-details-content"><dl class="tire-details-grid">${detailRows}</dl>
        <section class="tire-history"><h3>Assignment and audit history</h3>${tireHistoryMarkup(result.history || [])}</section>
        <div class="dialog-actions">${adminActions}<button class="button button-secondary" data-action="close-tire-dialog" type="button">Close</button></div>
      </div>`, ".tire-details-content");
  } catch (error) {
    tireDialogContent(`<div class="dialog-header"><div><p class="eyebrow">TIRE MONITORING</p><h2 id="tire-dialog-title">Could not load details</h2></div><button class="icon-button dialog-close" data-action="close-tire-dialog" type="button" aria-label="Close tire details">×</button></div><div class="tire-details-content"><p class="dialog-error">${escapeHtml(error.message)}</p><button class="button button-secondary" data-action="close-tire-dialog" type="button">Close</button></div>`, ".tire-details-content");
  }
}

async function openTireEdit(tireId) {
  try {
    const result = await api(`/api/tires/${encodeURIComponent(tireId)}`);
    tireDialogContent(tireRecordFormMarkup("edit", result.data));
  } catch (error) {
    showToast(error.message, "error");
  }
}

function openTireRemove(tireId) {
  const row = state.tires.items.find((item) => String(item.id) === String(tireId));
  if (!row) return;
  tireDialogContent(`
    <div class="dialog-header"><div><p class="eyebrow">TIRE MONITORING</p><h2 id="tire-dialog-title">Remove tire</h2></div><button class="icon-button dialog-close" data-action="close-tire-dialog" type="button" aria-label="Close removal form">×</button></div>
    <form class="dialog-form tire-record-form" id="tire-remove-form" data-tire-id="${escapeHtml(row.id)}">
      <p>Remove <strong>${escapeHtml(row.reference_no)}</strong> from <strong>${escapeHtml(row.plate_number || "—")}</strong>. The record will be retained in history.</p>
      <div class="dialog-fields">${tireFormField("date_replaced", "Removal Date", "date", businessToday, { required: true, form: "remove" })}${tireFormField("reason", "Removal Reason", "text", "", { required: true, form: "remove" })}</div>
      <p class="dialog-error" role="alert" hidden></p>
      <div class="dialog-actions"><button class="button button-secondary" data-action="close-tire-dialog" type="button">Cancel</button><button class="button button-primary tire-remove-button" type="submit">Confirm removal</button></div>
    </form>`);
}

async function submitTireForm(form) {
  const mode = form.id === "tire-edit-form" ? "edit"
    : form.id === "tire-replace-form" ? "replace"
      : form.id === "tire-remove-form" ? "remove" : "create";
  if (mode === "replace" && !window.confirm("Replace this tire? The current record will be retained and marked replaced.")) return;
  if (mode === "remove" && !window.confirm("Remove this tire? Its record will be retained and marked removed.")) return;

  const submit = form.querySelector('button[type="submit"]');
  const errorMessage = form.querySelector(".dialog-error");
  const payload = Object.fromEntries(new FormData(form).entries());
  if (payload.remaining_lifespan_pct !== undefined) {
    payload.remaining_lifespan_pct = Number(payload.remaining_lifespan_pct);
  }
  if (mode === "create") {
    const [assetType, rawId] = String(payload.asset_id || "").split(":");
    if (!assetType || !rawId) {
      errorMessage.textContent = "Select a valid truck or trailer.";
      errorMessage.hidden = false;
      return;
    }
    delete payload.asset_id;
    payload.asset_type = assetType;
    payload[assetType === "truck" ? "vehicle_id" : "trailer_id"] = Number(rawId);
  }
  submit.disabled = true;
  errorMessage.hidden = true;
  try {
    const tireId = encodeURIComponent(form.dataset.tireId);
    const endpoint = mode === "edit" ? `/api/tires/${tireId}`
      : mode === "replace" ? `/api/tires/${tireId}/replace`
        : mode === "remove" ? `/api/tires/${tireId}/remove` : "/api/tires";
    await api(endpoint, {
      method: mode === "edit" ? "PATCH" : "POST",
      body: JSON.stringify(payload),
    });
    form.closest("dialog")?.close();
    showToast(mode === "replace" ? "Tire replacement recorded; the previous tire remains in history."
      : mode === "remove" ? "Tire removal recorded; the tire history was preserved."
        : mode === "edit" ? "Tire details updated."
          : "Tire record saved.");
    state.tires.requestedKey = "";
    render();
  } catch (error) {
    errorMessage.textContent = error.message || "Could not save this tire record.";
    errorMessage.hidden = false;
  } finally {
    if (submit.isConnected) submit.disabled = false;
  }
}

async function exportTireMonitoring(button) {
  const params = new URLSearchParams();
  for (const key of [
    "search", "asset_type", "asset_id", "status", "date_from", "date_to",
    "lifespan_min", "lifespan_max", "condition", "sort_by", "sort_dir",
  ]) {
    if (state.tires[key]) params.set(key, state.tires[key]);
  }
  params.set("export", "csv");
  button.disabled = true;
  try {
    const response = await fetch(`/api/tires?${params.toString()}`, { cache: "no-store" });
    if (!response.ok) {
      const result = await response.json().catch(() => ({}));
      if (response.status === 401) returnToSignIn();
      throw new Error(result.error || `Export failed (${response.status})`);
    }
    const objectUrl = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = "tire-monitoring.csv";
    link.click();
    URL.revokeObjectURL(objectUrl);
  } catch (error) {
    showToast(error.message || "Could not export tire records.", "error");
  } finally {
    if (button.isConnected) button.disabled = false;
  }
}

async function loadDispatchWorkflow({ force = false } = {}) {
  if ((state.dispatch.loading && !force) || (state.dispatch.loaded && !force)) return;
  const requestId = ++state.dispatch.requestId;
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 20000);
  state.dispatch.loading = true;
  state.dispatch.error = "";
  try {
    const params = new URLSearchParams({
      queue: state.dispatch.tab,
      page: String(state.dispatch.page),
      page_size: "25",
      search: state.dispatch.search,
    });
    const requests = [
      api(`/api/dispatch/movements?${params.toString()}`, { signal: controller.signal }),
      api("/api/dispatch/locations", { signal: controller.signal }),
    ];
    if (state.data.user?.role === "administrator") {
      requests.push(
        api("/api/dispatch/users", { signal: controller.signal }),
        api("/api/dispatch/assignments", { signal: controller.signal }),
      );
    }
    const [movementResult, locationResult, userResult, assignmentResult] = await Promise.all(requests);
    if (requestId !== state.dispatch.requestId) return;
    state.dispatch.movements = movementResult.movements || [];
    state.dispatch.total = Number(movementResult.total || 0);
    state.dispatch.locations = locationResult.locations || [];
    state.dispatch.users = userResult?.users || [];
    state.dispatch.assignments = assignmentResult?.assignments || [];
    state.dispatch.loaded = true;
  } catch (error) {
    if (requestId === state.dispatch.requestId) {
      state.dispatch.error = controller.signal.aborted
        ? "The dispatch service did not respond within 20 seconds. Check that the server is running and the location-dispatch database migration has been applied, then retry."
        : error.message || "Could not load dispatch movements.";
    }
  } finally {
    window.clearTimeout(timeoutId);
    if (requestId === state.dispatch.requestId) {
      state.dispatch.loading = false;
      if (state.page === "trips") render();
    }
  }
}

async function loadDispatchLoadCatalog({ force = false } = {}) {
  if (state.dispatch.loadCatalogLoading
      || (state.dispatch.loadCatalogLoaded && !force)) return;
  state.dispatch.loadCatalogLoading = true;
  state.dispatch.loadCatalogError = "";
  try {
    const result = await api("/api/dispatch/load-catalog");
    if (!Array.isArray(result.products)) {
      throw new Error("The load catalog response was invalid.");
    }
    state.dispatch.loadCatalog = result.products;
    state.dispatch.loadCatalogLoaded = true;
  } catch (error) {
    state.dispatch.loadCatalogError = error.message === "Not found"
      ? "The running app server does not have the load-catalog API yet. Restart or redeploy the Flask app, then retry."
      : error.message || "Could not load the product catalog.";
  } finally {
    state.dispatch.loadCatalogLoading = false;
    if (state.page === "trips"
        && window.location.pathname === "/dispatcher/add-trip"
        && !window.location.hash) {
      refreshDispatchCatalogStage(view.querySelector(".dispatch-departure-form"));
    }
  }
}

function dispatchStatusLabel(status) {
  return ({
    awaiting_arrival: "Awaiting Arrival",
    arrival_submitted: "Arrival Submitted",
    needs_correction: "Needs Correction",
    completed: "Completed",
  })[status] || "Unknown";
}

function dispatchDateTime(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? String(value)
    : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

function dispatchLocalDateTimeNow() {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Manila",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}T${values.hour}:${values.minute}`;
}

function dispatchLoadItemsMarkup() {
  const items = state.dispatch.departureLoadItems;
  if (!items.length) return '<p class="dispatch-load-empty">No products added yet.</p>';
  return `<ul class="dispatch-load-item-list">${items.map((item) => {
    const product = state.dispatch.loadCatalog.find(
      (candidate) => Number(candidate.id) === Number(item.product_id),
    );
    if (!product) return "";
    return `<li><span><strong>${escapeHtml(product.brand)}</strong><small>${escapeHtml(product.section)}${product.packing ? ` · ${escapeHtml(product.packing)}` : ""}${product.quantity == null ? "" : ` · ${formatNumber(product.quantity)} units in pack`}</small></span><span class="dispatch-load-item-quantity">${formatNumber(item.pallet_quantity)} ${Number(item.pallet_quantity) === 1 ? "pallet" : "pallets"}</span><button class="button button-secondary button-small" type="button" data-action="dispatch-remove-load-item" data-product-id="${escapeHtml(product.id)}" aria-label="Remove ${escapeHtml(product.brand)}">Remove</button></li>`;
  }).join("")}</ul>`;
}

function dispatchProductCatalogMarkup() {
  const sections = [...new Set(state.dispatch.loadCatalog.map((product) => product.section))];
  const search = state.dispatch.loadCatalogSearch.trim().toLocaleLowerCase();
  const products = state.dispatch.loadCatalog.filter((product) =>
    (!state.dispatch.loadCatalogSection || product.section === state.dispatch.loadCatalogSection)
    && (!search || `${product.brand} ${product.section} ${product.packing}`.toLocaleLowerCase().includes(search)),
  );
  const sectionFilters = [
    `<button class="dispatch-catalog-filter ${state.dispatch.loadCatalogSection ? "" : "is-active"}" type="button" data-action="dispatch-load-section" data-section="" aria-pressed="${!state.dispatch.loadCatalogSection}">All products</button>`,
    ...sections.map((section) =>
      `<button class="dispatch-catalog-filter ${state.dispatch.loadCatalogSection === section ? "is-active" : ""}" type="button" data-action="dispatch-load-section" data-section="${escapeHtml(section)}" aria-pressed="${state.dispatch.loadCatalogSection === section}">${escapeHtml(section)}</button>`,
    ),
  ].join("");
  const cards = products.length
    ? `<div class="dispatch-product-grid">${products.map((product) => {
      const selected = state.dispatch.departureLoadItems.find(
        (item) => Number(item.product_id) === Number(product.id),
      );
      return `<article class="dispatch-product-card ${selected ? "is-selected" : ""}">
        <button class="dispatch-product-card-select" type="button" data-action="dispatch-select-load-product" data-product-id="${escapeHtml(product.id)}" aria-pressed="${Boolean(selected)}">
          <span class="dispatch-product-visual"><span class="dispatch-product-art" aria-hidden="true"><svg viewBox="0 0 48 48"><path d="M8 15.5 24 7l16 8.5v18L24 42 8 33.5v-18Z"/><path d="m8.5 15.7 15.5 8.5 15.5-8.5M24 24v17.5M16 11.3l16 8.8"/></svg></span>${selected ? '<span class="dispatch-product-selected-badge"><span aria-hidden="true">✓</span> Selected</span>' : ""}</span>
          <span class="dispatch-product-card-copy"><span class="dispatch-product-section">${escapeHtml(product.section)}</span><strong>${escapeHtml(product.brand)}</strong><span>${product.packing ? escapeHtml(product.packing) : "Packing not specified"}</span>${product.quantity == null ? "" : `<small>${formatNumber(product.quantity)} units in pack</small>`}</span>
        </button>
        ${selected ? `<div class="dispatch-product-quantity" aria-label="Selected pallet quantity">
          <button class="dispatch-product-quantity-button" type="button" data-action="dispatch-adjust-load-product" data-product-id="${escapeHtml(product.id)}" data-delta="-1" aria-label="Remove one pallet of ${escapeHtml(product.brand)}" ${selected.pallet_quantity <= 1 ? "disabled" : ""}>−</button>
          <span>${formatNumber(selected.pallet_quantity)} ${Number(selected.pallet_quantity) === 1 ? "pallet" : "pallets"}</span>
          <button class="dispatch-product-quantity-button" type="button" data-action="dispatch-adjust-load-product" data-product-id="${escapeHtml(product.id)}" data-delta="1" aria-label="Add one pallet of ${escapeHtml(product.brand)}">+</button>
        </div>` : ""}
      </article>`;
    }).join("")}</div>`
    : '<p class="dispatch-catalog-empty">No products match your search. Try a different name or section.</p>';
  return `<div class="dispatch-catalog-toolbar">
      <label class="search-box dispatch-catalog-search"><span class="sr-only">Search load products</span><span aria-hidden="true">⌕</span><input type="search" name="load_catalog_search" placeholder="Search products or packing" value="${escapeHtml(state.dispatch.loadCatalogSearch)}" autocomplete="off" /></label>
      <div class="dispatch-catalog-filters" role="group" aria-label="Filter load products by section">${sectionFilters}</div>
    </div>
    <div class="dispatch-product-results" aria-live="polite">${cards}</div>`;
}

function renderDispatchLoadSelection(form) {
  const selected = form.querySelectorAll(".dispatch-selected-load");
  const hiddenInput = form.elements.namedItem("load_items");
  selected.forEach((container) => {
    container.innerHTML = container.closest(".dispatch-wizard-step")?.dataset.step === "4"
      && form.elements.namedItem("load_type").value === "EMPTIES"
      ? '<p class="dispatch-load-empty">Product selection is not required for empty-container movements.</p>'
      : dispatchLoadItemsMarkup();
  });
  const catalog = form.querySelector(".dispatch-product-catalog");
  if (catalog) catalog.innerHTML = dispatchProductCatalogMarkup();
  if (hiddenInput) {
    hiddenInput.value = JSON.stringify(
      form.elements.namedItem("load_type").value === "FULLS"
        ? state.dispatch.departureLoadItems
        : [],
    );
  }
}

function dispatchCatalogStepMarkup() {
  if (state.dispatch.loadCatalogLoading) {
    return '<p class="dispatch-catalog-empty" role="status">Loading load catalog…</p>';
  }
  if (state.dispatch.loadCatalogError) {
    return `<div class="dispatch-load-catalog-error" role="alert"><p>${escapeHtml(state.dispatch.loadCatalogError)}</p><button class="button button-secondary button-small" type="button" data-action="dispatch-load-catalog-retry">Retry</button></div>`;
  }
  if (!state.dispatch.loadCatalog.length) {
    return '<p class="dispatch-catalog-empty">No active products are available in the load catalog.</p>';
  }
  return `<div class="dispatch-product-catalog">${dispatchProductCatalogMarkup()}</div>`;
}

function refreshDispatchCatalogStage(form) {
  const stage = form?.querySelector(".dispatch-catalog-stage");
  if (stage) stage.innerHTML = dispatchCatalogStepMarkup();
}

function dispatchWizardReviewMarkup(form) {
  const value = (name) => form.elements.namedItem(name)?.value || "Not provided";
  const labelFor = (name, id) => {
    const options = [...(form.elements.namedItem(name)?.options || [])];
    return options.find((option) => option.value === id)?.textContent.trim() || id || "Not selected";
  };
  const productSummary = value("load_type") === "EMPTIES"
    ? "Empty containers (product selection not required)"
    : state.dispatch.departureLoadItems.map((item) => {
      const product = state.dispatch.loadCatalog.find(
        (candidate) => Number(candidate.id) === Number(item.product_id),
      );
      return product
        ? `${product.section} · ${product.brand}${product.packing ? ` (${product.packing})` : ""} — ${formatNumber(item.pallet_quantity)} ${Number(item.pallet_quantity) === 1 ? "pallet" : "pallets"}`
        : "";
    }).filter(Boolean).join(", ") || "No products selected";
  const manifest = form.elements.namedItem("departure_manifest").files?.[0]?.name || "Not attached";
  const invoice = form.elements.namedItem("fuel_invoice").files?.[0]?.name || "Not attached";
  const rows = [
    ["Driver", labelFor("driver_id", value("driver_id"))],
    ["Truck", labelFor("truck_id", value("truck_id"))],
    ["Trailer", labelFor("trailer_id", value("trailer_id"))],
    ["Route", `${labelFor("origin_location_id", value("origin_location_id"))} → ${labelFor("destination_location_id", value("destination_location_id"))}`],
    ["Load type", value("load_type")],
    ["Pallet quantity", value("pallet_quantity")],
    ["Trailer contents", productSummary],
    ["ISM number", value("ism_no")],
    ["Departure time", value("departure_at")],
    ["Fuel allocation", value("fuel_allocation") ? `${formatNumber(value("fuel_allocation"))} L` : "Not entered"],
    ["Actual fuel expense", value("actual_fuel_expense") ? `${formatCurrency(value("actual_fuel_expense"))}` : "Not entered"],
    ["Fuel remarks", value("fuel_remarks")],
    ["Departure manifest", manifest],
    ["Fuel invoice", invoice],
  ];
  return `<dl>${rows.map(([label, content]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(content)}</dd></div>`).join("")}</dl>`;
}

function setDispatchWizardStep(form, step, { focus = false } = {}) {
  const stepDescriptions = [
    "Choose the driver for this movement.",
    "Assign an active truck and trailer.",
    "Select an origin and an active destination route.",
    "Choose the products this trailer will carry.",
    "Record the load type and pallet quantity.",
    "Enter departure references, fuel details, and documentation.",
    "Review the movement details before recording it.",
  ];
  const steps = [...form.querySelectorAll(".dispatch-wizard-step")];
  const index = Math.max(0, Math.min(step, steps.length - 1));
  state.dispatch.departureWizardStep = index;
  steps.forEach((section, sectionIndex) => {
    section.hidden = sectionIndex !== index;
  });
  form.querySelector("[data-dispatch-wizard-current]").textContent = String(index + 1);
  form.querySelector("[data-dispatch-wizard-description]").textContent = stepDescriptions[index];
  form.querySelector(".dispatch-wizard-progress-wrap progress").value = index + 1;
  form.querySelectorAll(".dispatch-wizard-progress-step").forEach((item, itemIndex) => {
    item.classList.toggle("is-active", itemIndex === index);
    item.classList.toggle("is-complete", itemIndex < index);
    if (itemIndex === index) item.setAttribute("aria-current", "step");
    else item.removeAttribute("aria-current");
  });
  form.querySelector('[data-action="dispatch-wizard-back"]').hidden = index === 0;
  form.querySelector(".dispatch-wizard-cancel").hidden = index === steps.length - 1;
  form.querySelector('[data-action="dispatch-wizard-continue"]').hidden = index === steps.length - 1;
  form.querySelector(".dispatch-wizard-submit").hidden = index !== steps.length - 1;
  const error = form.querySelector(".dispatch-form-error");
  error.hidden = true;
  if (index === steps.length - 1) {
    form.querySelector(".dispatch-wizard-review").innerHTML = dispatchWizardReviewMarkup(form);
  }
  if (focus) steps[index].querySelector("h3")?.focus();
}

function validateDispatchWizardStep(form, stepIndex) {
  const section = form.querySelector(`.dispatch-wizard-step[data-step="${stepIndex}"]`);
  const error = form.querySelector(".dispatch-form-error");
  error.hidden = true;
  if (stepIndex === 4 && form.elements.namedItem("load_type").value === "FULLS"
      && !state.dispatch.departureLoadItems.length) {
    error.textContent = "Select at least one product in the Load Catalog step for a FULLS movement.";
    error.hidden = false;
    return false;
  }
  if (stepIndex === 4) validateDispatchPalletQuantity(form);
  for (const field of section.querySelectorAll("input, select, textarea")) {
    if (!field.required || field.disabled || field.checkValidity()) continue;
    field.reportValidity();
    return false;
  }
  return true;
}

function dispatchMovementCard(movement, mode) {
  const isAdmin = state.data.user?.role === "administrator";
  const isVerified = Boolean(movement.ism_no && movement.arrival_verified_at);
  const status = dispatchStatusLabel(movement.status);
  const isArrivalQueue = mode === "arrivals";
  const locationLine = `${movement.origin_location_name || movement.origin_location_id} → ${movement.destination_location_name || movement.destination_location_id}`;
  const userId = String(state.data.user?.id || "");
  const canViewIsm = isAdmin || (isArrivalQueue
    ? isVerified
    : String(movement.departure_user_id || "") === userId
      || state.dispatch.dashboard.locations.some(
        (location) => location.id === movement.origin_location_id && location.can_depart,
      ));
  const contentSummary = Array.isArray(movement.load_items) && movement.load_items.length
    ? movement.load_items.map((item) => {
      const productLabel = `${item.brand}${item.packing ? ` (${item.packing})` : ""}`;
      if (item.pallet_quantity != null) {
        return `${productLabel} × ${formatNumber(item.pallet_quantity)} ${Number(item.pallet_quantity) === 1 ? "pallet" : "pallets"}`;
      }
      return `${productLabel} × ${formatNumber(item.quantity)} legacy quantity`;
    }).join(", ")
    : "No product details";
  const detailLines = [
    ["Truck", movement.truck_plate || `#${movement.truck_id}`],
    ["Driver", movement.driver_name || "—"],
    ["Trailer", movement.trailer_plate || `#${movement.trailer_id}`],
    ["Load", `${movement.load_type} · ${formatNumber(movement.pallet_quantity)} pallets`],
    ["Contents", contentSummary],
    ["Departed", dispatchDateTime(movement.departure_at)],
    ...(movement.arrival_at ? [["Arrived", dispatchDateTime(movement.arrival_at)]] : []),
    ...(canViewIsm && movement.ism_no ? [["ISM", movement.ism_no]] : []),
  ];
  const manifestLinks = [
    movement.departure_manifest_path
      ? `<a href="/api/dispatch/movements/${encodeURIComponent(movement.id)}/documents/departure" target="_blank" rel="noopener">Departure manifest</a>`
      : "",
    movement.arrival_manifest_path
      ? `<a href="/api/dispatch/movements/${encodeURIComponent(movement.id)}/documents/arrival" target="_blank" rel="noopener">Arrival manifest</a>`
      : "",
    movement.fuel_invoice_path
      ? `<a href="/api/dispatch/movements/${encodeURIComponent(movement.id)}/documents/fuel_invoice" target="_blank" rel="noopener">Fuel invoice</a>`
      : "",
  ].filter(Boolean).join(" · ");
  let actions = "";
  if (isArrivalQueue && !isAdmin && !isVerified
      && ["awaiting_arrival", "needs_correction"].includes(movement.status)) {
    actions = `
      <form class="dispatch-verify-form" data-movement-id="${escapeHtml(movement.id)}">
        <label class="form-field"><span>Enter ISM from the physical manifest</span><input name="ism_no" autocomplete="off" required maxlength="120" /></label>
        <p class="dialog-error" role="alert" hidden></p>
        <button class="button button-primary" type="submit">Verify ISM</button>
      </form>`;
  } else if (isArrivalQueue && !isAdmin && isVerified
      && ["awaiting_arrival", "needs_correction"].includes(movement.status)) {
    actions = `
      <form class="dispatch-arrival-form" data-movement-id="${escapeHtml(movement.id)}">
        <div class="dialog-fields">
          <label class="form-field"><span>Actual arrival date and time</span><input name="arrival_at" type="datetime-local" required /></label>
          <label class="form-field"><span>Arrival fuel expense (optional)</span><input name="arrival_fuel_expense" type="number" min="0" step="0.01" /></label>
          <label class="form-field"><span>Arrival manifest / documentation</span><input name="arrival_manifest" type="file" data-dispatch-preview="arrival_manifest" accept="image/jpeg,image/png,image/webp" capture="environment" required /><img class="dispatch-image-preview" data-dispatch-preview="arrival_manifest" alt="Arrival document preview" hidden /></label>
        </div>
        <p class="dialog-error" role="alert" hidden></p>
        <button class="button button-primary" type="submit">Record Arrival for Review</button>
      </form>`;
  } else if (isAdmin && movement.status === "arrival_submitted") {
    actions = `
      <div class="dispatch-review-actions">
        <button class="button button-primary" type="button" data-action="dispatch-finalize" data-id="${escapeHtml(movement.id)}">Finalize movement</button>
        <button class="button button-secondary" type="button" data-action="dispatch-correction-toggle" data-id="${escapeHtml(movement.id)}">Request correction</button>
      </div>
      <form class="dispatch-correction-form" data-movement-id="${escapeHtml(movement.id)}" hidden>
        <label class="form-field"><span>Correction reason</span><textarea name="reason" rows="2" required maxlength="1000"></textarea></label>
        <p class="dialog-error" role="alert" hidden></p>
        <button class="button button-secondary" type="submit">Send correction request</button>
      </form>`;
  }
  if (isAdmin && mode === "completed" && movement.status === "completed") {
    actions += `<button class="button button-secondary button-small" type="button" data-action="dispatch-delete-completed" data-id="${escapeHtml(movement.id)}" data-trip-id="${escapeHtml(movement.canonical_trip_id)}">Delete completed trip</button>`;
  }
  return `<article class="panel dispatch-movement-card">
    <div class="dispatch-movement-heading">
      <div><p class="eyebrow">${escapeHtml(movement.origin_location_id)} → ${escapeHtml(movement.destination_location_id)}</p><h3>${escapeHtml(locationLine)}</h3></div>
      <span class="badge badge-${escapeHtml(movement.status)}">${escapeHtml(status)}</span>
    </div>
    <dl class="dispatch-movement-details">${detailLines.map(([label, value]) =>
      `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`,
    ).join("")}</dl>
    ${isArrivalQueue && !isAdmin && !isVerified
      ? '<p class="dispatch-ism-hidden">ISM is hidden until you verify the physical manifest.</p>'
      : ""}
    ${manifestLinks ? `<p class="dispatch-document-links">${manifestLinks}</p>` : ""}
    ${actions}
    <div><button class="button button-secondary button-small" type="button" data-action="dispatch-history" data-id="${escapeHtml(movement.id)}">View movement history</button></div>
    <div class="dispatch-history" data-history-for="${escapeHtml(movement.id)}" hidden></div>
  </article>`;
}

function dispatchDepartureForm() {
  const isAdmin = state.data.user?.role === "administrator";
  const originOptions = state.dispatch.locations.filter((location) =>
    isAdmin || location.can_depart,
  );
  const originId = state.dispatch.departureOrigin || originOptions[0]?.id || "";
  const destinationOptions = (state.data.truck_routes || [])
    .filter((route) => route.active !== false && route.origin_code === originId)
    .map((route) => ({
      id: route.destination_code,
      name: route.destination_name,
    }));
  const uniqueDestinations = [...new Map(destinationOptions.map((item) => [item.id, item])).values()];
  const trucks = (state.data.vehicles || []).filter((item) =>
    ["active", "available", "assigned"].includes(item.status),
  );
  const trailers = (state.data.trailers || []).filter((item) =>
    item.status === "active" && Number(item.pallet_capacity) > 0,
  );
  const drivers = (state.data.drivers || []).filter((item) =>
    item.status === "active",
  );
  const wizardSteps = [
    "Driver", "Truck & Trailer", "Route", "Load Catalog",
    "Load Details", "Departure Details", "Review",
  ];
  const progress = wizardSteps.map((title, index) => `
    <li><span class="dispatch-wizard-progress-step" aria-label="Step ${index + 1}: ${title}">
      <span>${index + 1}</span><small>${title}</small>
    </span></li>`).join("");
  const selectedTrailer = trailers.find(
    (trailer) => String(trailer.id) === String(state.dispatch.departureTrailer || ""),
  );
  const selectedItems = state.dispatch.departureLoadItems;
  const selectedContents = selectedItems.length
    ? dispatchLoadItemsMarkup()
    : '<p class="dispatch-load-empty">No products selected.</p>';
  return `<section class="panel dispatch-form-panel dispatch-wizard-panel">
    ${!originOptions.length
      ? '<p class="empty-state">No departure location is assigned to this account. Ask an administrator to configure access.</p>'
      : ""}
    <form class="dispatch-departure-form" novalidate>
      <header class="dispatch-wizard-header">
        <div><p class="eyebrow">NEW DEPARTURE · STEP <span data-dispatch-wizard-current>1</span> OF ${wizardSteps.length}</p><h2 data-dispatch-wizard-title>Create a movement</h2><p data-dispatch-wizard-description>Choose the driver for this movement.</p></div>
        <a class="button button-secondary" href="#trips">Cancel</a>
      </header>
      <div class="dispatch-wizard-progress-wrap"><progress max="${wizardSteps.length}" value="${state.dispatch.departureWizardStep + 1}" aria-label="Departure creation progress"></progress><ol>${progress}</ol></div>
      <div class="dispatch-wizard-content">
        <section class="dispatch-wizard-step" data-step="0" aria-labelledby="dispatch-step-title-0">
          <h3 id="dispatch-step-title-0" tabindex="-1">Choose a driver</h3><p class="dispatch-wizard-instruction">Select the active driver assigned to this departure.</p>
          <label class="form-field"><span>Driver</span><select name="driver_id" required><option value="">Select driver</option>
            ${drivers.map((driver) => `<option value="${escapeHtml(driver.id)}" ${String(state.dispatch.departureDriver || "") === String(driver.id) ? "selected" : ""}>${escapeHtml(driver.name)}</option>`).join("")}
          </select></label>
        </section>
        <section class="dispatch-wizard-step" data-step="1" aria-labelledby="dispatch-step-title-1" hidden>
          <h3 id="dispatch-step-title-1" tabindex="-1">Choose truck and trailer</h3><p class="dispatch-wizard-instruction">Only active fleet vehicles are available for selection.</p>
          <div class="dialog-fields">
            <label class="form-field"><span>Truck</span><select name="truck_id" required><option value="">Select truck</option>
              ${trucks.map((truck) => `<option value="${escapeHtml(truck.id)}" ${String(state.dispatch.departureTruck || "") === String(truck.id) ? "selected" : ""}>${escapeHtml(truck.plate_number)} · ${escapeHtml(truck.make || "")} ${escapeHtml(truck.model || "")}</option>`).join("")}
            </select></label>
            <label class="form-field"><span>Trailer</span><select name="trailer_id" required><option value="">Select trailer</option>
              ${trailers.map((trailer) => `<option value="${escapeHtml(trailer.id)}" ${String(state.dispatch.departureTrailer || "") === String(trailer.id) ? "selected" : ""}>${escapeHtml(trailer.plate_number)} · ${escapeHtml(trailer.pallet_capacity || "Capacity unknown")} pallets</option>`).join("")}
            </select></label>
          </div>
          <div class="dispatch-trailer-capacity" data-dispatch-trailer-capacity>${selectedTrailer ? `Selected trailer capacity: <strong>${formatNumber(selectedTrailer.pallet_capacity)} pallets</strong>` : "Select a trailer to see its pallet capacity."}</div>
        </section>
        <section class="dispatch-wizard-step" data-step="2" aria-labelledby="dispatch-step-title-2" hidden>
          <h3 id="dispatch-step-title-2" tabindex="-1">Choose origin and destination</h3><p class="dispatch-wizard-instruction">Destinations are limited to active routes from your assigned departure location.</p>
          <div class="dialog-fields">
            <label class="form-field"><span>Origin</span><select name="origin_location_id" data-dispatch-origin required>
              <option value="">Select origin</option>${originOptions.map((location) => `<option value="${escapeHtml(location.id)}" ${location.id === originId ? "selected" : ""}>${escapeHtml(location.name)} (${escapeHtml(location.id)})</option>`).join("")}
            </select></label>
            <label class="form-field"><span>Destination</span><select name="destination_location_id" required><option value="">Select destination</option>
              ${uniqueDestinations.map((location) => `<option value="${escapeHtml(location.id)}" ${String(state.dispatch.departureDestination || "") === String(location.id) ? "selected" : ""}>${escapeHtml(location.name)} (${escapeHtml(location.id)})</option>`).join("")}
            </select></label>
          </div>
        </section>
        <section class="dispatch-wizard-step" data-step="3" aria-labelledby="dispatch-step-title-3" hidden>
          <h3 id="dispatch-step-title-3" tabindex="-1">Browse the load catalog</h3><p class="dispatch-wizard-instruction">Select every product going on this trailer. Pack quantities can be adjusted on each selected card.</p>
          <div class="dispatch-catalog-stage">${dispatchCatalogStepMarkup()}</div>
          <div class="dispatch-selected-load" aria-live="polite">${selectedContents}</div>
        </section>
        <section class="dispatch-wizard-step" data-step="4" aria-labelledby="dispatch-step-title-4" hidden>
          <h3 id="dispatch-step-title-4" tabindex="-1">Load type and pallet quantity</h3><p class="dispatch-wizard-instruction">Record whether this trailer carries full goods or empty containers, and enter its pallet count.</p>
          <div class="dialog-fields">
            <label class="form-field"><span>Load type</span><select name="load_type" required><option value="">Select load type</option><option value="FULLS" ${state.dispatch.departureLoadType === "FULLS" ? "selected" : ""}>FULLS</option><option value="EMPTIES" ${state.dispatch.departureLoadType === "EMPTIES" ? "selected" : ""}>EMPTIES</option></select></label>
            <label class="form-field"><span>Pallet quantity</span><input name="pallet_quantity" type="number" min="1" step="1" required value="${escapeHtml(state.dispatch.departurePalletQuantity || "")}" /></label>
          </div>
          <div class="dispatch-trailer-capacity" data-dispatch-trailer-capacity>${selectedTrailer ? `Trailer capacity: <strong>${formatNumber(selectedTrailer.pallet_capacity)} pallets</strong>` : "Select a trailer in the previous step to view its capacity."}</div>
          <section class="dispatch-load-summary" aria-labelledby="dispatch-load-summary-title"><h4 id="dispatch-load-summary-title">Selected trailer contents</h4><div class="dispatch-selected-load" aria-live="polite">${state.dispatch.departureLoadType === "EMPTIES" ? '<p class="dispatch-load-empty">Product selection is not required for empty-container movements.</p>' : selectedContents}</div></section>
        </section>
        <section class="dispatch-wizard-step" data-step="5" aria-labelledby="dispatch-step-title-5" hidden>
          <h3 id="dispatch-step-title-5" tabindex="-1">Departure details and documentation</h3><p class="dispatch-wizard-instruction">Enter the departure reference and time, then attach the required departure manifest.</p>
          <div class="dialog-fields">
            <label class="form-field"><span>ISM number</span><input name="ism_no" required maxlength="120" autocomplete="off" value="${escapeHtml(state.dispatch.departureIsm || "")}" /></label>
            <label class="form-field"><span>Departure date and time</span><input name="departure_at" type="datetime-local" value="${escapeHtml(state.dispatch.departureAt || dispatchLocalDateTimeNow())}" required /></label>
            <label class="form-field"><span>Fuel allocation (L)</span><input name="fuel_allocation" type="number" min="0" step="0.01" placeholder="Liters" value="${escapeHtml(state.dispatch.departureFuelAllocation || "")}" /></label>
            <label class="form-field"><span>Actual fuel expense (₱)</span><input name="actual_fuel_expense" type="number" min="0" step="0.01" value="${escapeHtml(state.dispatch.departureFuelExpense || "")}" /></label>
            <label class="form-field"><span>Fuel remarks</span><input name="fuel_remarks" maxlength="500" value="${escapeHtml(state.dispatch.departureFuelRemarks || "")}" /></label>
            <label class="form-field"><span>Departure manifest / required documentation</span><input name="departure_manifest" type="file" data-dispatch-preview="departure_manifest" accept="image/jpeg,image/png,image/webp" capture="environment" required /><img class="dispatch-image-preview" data-dispatch-preview="departure_manifest" alt="Departure document preview" hidden /></label>
            <label class="form-field"><span>Fuel invoice (if applicable)</span><input name="fuel_invoice" type="file" data-dispatch-preview="fuel_invoice" accept="image/jpeg,image/png,image/webp" capture="environment" /><img class="dispatch-image-preview" data-dispatch-preview="fuel_invoice" alt="Fuel invoice preview" hidden /></label>
          </div>
        </section>
        <section class="dispatch-wizard-step" data-step="6" aria-labelledby="dispatch-step-title-6" hidden>
          <h3 id="dispatch-step-title-6" tabindex="-1">Review and confirm</h3><p class="dispatch-wizard-instruction">Review the departure details before recording the movement.</p>
          <div class="dispatch-wizard-review" aria-live="polite"></div>
        </section>
        <p class="dialog-error dispatch-form-error" role="alert" hidden></p>
      </div>
      <footer class="dispatch-wizard-actions">
        <button class="button button-secondary dispatch-wizard-back" type="button" data-action="dispatch-wizard-back" hidden>Back</button>
        <a class="button button-secondary dispatch-wizard-cancel" href="#trips">Cancel</a>
        <button class="button button-primary dispatch-wizard-continue" type="button" data-action="dispatch-wizard-continue">Continue</button>
        <button class="button button-primary dispatch-wizard-submit" type="submit" hidden>Confirm and Record Departure</button>
      </footer>
      <p class="page-description dispatch-availability-message" role="status" hidden></p>
      <input type="hidden" name="load_items" value="${escapeHtml(JSON.stringify(selectedItems))}" />
    </form>
  </section>`;
}

function dispatchAdminSetup() {
  if (state.data.user?.role !== "administrator") return "";
  const locations = state.dispatch.locations;
  const users = state.dispatch.users;
  return `<section class="panel dispatch-admin-setup">
    <div class="panel-heading"><div><p class="eyebrow">ADMINISTRATION</p><h2>Dispatcher access and locations</h2></div></div>
    <div class="dispatch-admin-forms">
      <form class="dispatch-assignment-form">
        <h3>Assign a dispatcher</h3>
        <label class="form-field"><span>Dispatcher account</span><select name="user_id" required><option value="">Select account</option>
          ${users.map((user) => `<option value="${escapeHtml(user.user_id)}">${escapeHtml(user.email || user.full_name || user.user_id)}</option>`).join("")}
        </select></label>
        <label class="form-field"><span>Location</span><select name="location_id" required><option value="">Select location</option>
          ${locations.map((location) => `<option value="${escapeHtml(location.id)}">${escapeHtml(location.name)} (${escapeHtml(location.id)})</option>`).join("")}
        </select></label>
        <label class="dispatch-permission"><input name="can_depart" type="checkbox" checked /> May create departures</label>
        <label class="dispatch-permission"><input name="can_arrive" type="checkbox" checked /> May receive arrivals</label>
        <p class="dialog-error" role="alert" hidden></p>
        <button class="button button-secondary" type="submit" ${users.length ? "" : "disabled"}>Save assignment</button>
        ${users.length ? "" : '<small>Dispatcher accounts must first be marked as dispatchers in Auth metadata. Location permissions are granted only when an administrator assigns them.</small>'}
      </form>
      <form class="dispatch-location-form">
        <h3>Configure a location</h3>
        <label class="form-field"><span>Stable location ID</span><input name="id" required maxlength="32" pattern="[A-Z0-9_-]+" placeholder="e.g. DAV1" /></label>
        <label class="form-field"><span>Display name</span><input name="name" required maxlength="120" /></label>
        <p class="dialog-error" role="alert" hidden></p>
        <button class="button button-secondary" type="submit">Save location</button>
      </form>
    </div>
    <div class="dispatch-assignment-list">
      ${state.dispatch.assignments.length
        ? state.dispatch.assignments.map((assignment) => `<p><strong>${escapeHtml(assignment.email || assignment.user_id)}</strong> · ${escapeHtml(assignment.location_name)} (${escapeHtml(assignment.location_id)}) · ${assignment.can_depart ? "Departures" : ""}${assignment.can_depart && assignment.can_arrive ? " / " : ""}${assignment.can_arrive ? "Arrivals" : ""}</p>`).join("")
        : '<p class="empty-state">No dispatcher location assignments are configured yet.</p>'}
    </div>
  </section>`;
}

function renderDispatchWorkflow() {
  const isDispatcherAddTripPage = state.data.user?.role === "dispatcher"
    && window.location.pathname === "/dispatcher/add-trip"
    && !window.location.hash;
  if (isDispatcherAddTripPage
      && !state.dispatch.loadCatalogLoaded
      && !state.dispatch.loadCatalogLoading
      && !state.dispatch.loadCatalogError) {
    loadDispatchLoadCatalog();
  }
  if (state.dispatch.error && !state.dispatch.loaded) {
    return `${header("LOCATION DISPATCH", "Movement workflow", "Securely hand off each movement from departure through arrival.", '<button class="button button-secondary" data-action="dispatch-reload" type="button">Retry</button>')}<section class="error-card"><p>${escapeHtml(state.dispatch.error)}</p></section>`;
  }
  if (!state.dispatch.loaded && !state.dispatch.loading) {
    loadDispatchWorkflow();
  }
  if (state.dispatch.loading && !state.dispatch.loaded) {
    return `${header("LOCATION DISPATCH", "Movement workflow", "Securely hand off each movement from departure through arrival.")}<section class="panel"><p>Loading dispatch workflow…</p></section>`;
  }

  const isAdmin = state.data.user?.role === "administrator";
  if (isDispatcherAddTripPage) {
    return `${header("LOCATION DISPATCH", "Add Trip", "Create a new movement and submit its departure manifest.", '<a class="button button-secondary" href="#trips">Movement Queues</a>')}
      ${dispatchDepartureForm()}`;
  }

  const tab = state.dispatch.tab;
  const eligible = state.dispatch.movements;
  const pageSize = 25;
  const pageCount = Math.max(1, Math.ceil(state.dispatch.total / pageSize));
  state.dispatch.page = Math.min(state.dispatch.page, pageCount);
  const pageRows = eligible;
  const pageMarkup = pageCount > 1 ? `<nav class="pagination" aria-label="Dispatch movements pages">
    <button class="button button-secondary button-small" data-action="dispatch-page" data-page="${Math.max(1, state.dispatch.page - 1)}" ${state.dispatch.page === 1 ? "disabled" : ""}>Previous</button>
    <span>Page ${state.dispatch.page} of ${pageCount}</span>
    <button class="button button-secondary button-small" data-action="dispatch-page" data-page="${Math.min(pageCount, state.dispatch.page + 1)}" ${state.dispatch.page === pageCount ? "disabled" : ""}>Next</button>
  </nav>` : "";
  const listMarkup = pageRows.length
    ? `<div class="dispatch-movement-list">${pageRows.map((row) => dispatchMovementCard(row, tab)).join("")}</div>${pageMarkup}`
    : `<div class="empty-state"><span>↗</span><strong>No ${tab === "departures" ? "departures" : tab === "arrivals" ? "incoming movements" : "completed movements"} found</strong><small>${state.dispatch.search ? "Try another search." : "New movements will appear here when they match this workflow."}</small></div>`;
  const legacyRows = isAdmin
    ? `<section class="panel records-panel"><div class="panel-heading"><div><p class="eyebrow">HISTORICAL RECORDS</p><h2>Trips recorded before the dispatch workflow</h2></div></div>
        ${tableMarkup(state.data.trips || [], RESOURCE_CONFIG.trips.columns, RESOURCE_CONFIG.trips.api, { empty: "No historical trip records", rowAction: "trip-details" })}</section>`
    : "";
  return `
    ${header("LOCATION DISPATCH", "Departure → Arrival", "One movement ID. The receiving dispatcher verifies the manifest before arrival; only admins finalize financial trips.", '<button class="button button-secondary" data-action="dispatch-reload" type="button">Refresh</button>')}
    ${isAdmin ? dispatchAdminSetup() : ""}
    <section class="panel records-panel dispatch-queue-panel">
      <div class="panel-heading records-heading">
        <div><p class="eyebrow">MOVEMENT QUEUES</p><h2>${tab === "departures" ? "Departures" : tab === "arrivals" ? "Arrivals" : "Completed Trips"}</h2></div>
        <label class="search-box"><span class="sr-only">Search movements</span><span aria-hidden="true">⌕</span><input type="search" id="dispatch-search" placeholder="Search movements" value="${escapeHtml(state.dispatch.search)}" /></label>
      </div>
      <nav class="trip-view-tabs" aria-label="Dispatch workflow">
        ${[["departures", "Departures"], ["arrivals", "Arrivals"], ["completed", "Completed Trips"]].map(([key, label]) =>
          `<button class="trip-view-tab ${tab === key ? "trip-view-tab-active" : ""}" type="button" data-action="dispatch-tab" data-tab="${key}" aria-pressed="${tab === key}">${label}</button>`,
        ).join("")}
      </nav>
      <p class="record-count">${formatNumber(state.dispatch.total)} ${state.dispatch.total === 1 ? "movement" : "movements"}</p>
      ${listMarkup}
    </section>
    ${tab === "completed" ? legacyRows : ""}`;
}

async function uploadDispatchDocument(movementId, kind, file) {
  if (!file || file.size === 0) {
    throw new Error(`${kind === "arrival" ? "Arrival" : "Departure"} documentation is required.`);
  }
  const body = new FormData();
  body.append("image", file);
  await api(
    `/api/dispatch/movements/${encodeURIComponent(movementId)}/documents/${kind}`,
    { method: "POST", body },
  );
}

async function refreshDispatcherDispatchView() {
  if (state.page === "dashboard" && state.data?.user?.role === "dispatcher") {
    state.dispatch.dashboard.loaded = false;
    await loadDispatcherDashboard({ force: true });
    return;
  }
  state.dispatch.loaded = false;
  await loadDispatchWorkflow({ force: true });
}

async function deleteCompletedDispatchMovement(button) {
  const movementId = button.dataset.id;
  const tripId = button.dataset.tripId;
  if (!movementId || !tripId || !window.confirm(
    `Delete completed trip #${tripId}, its dispatch movement, audit history, and uploaded documents? This cannot be undone. Trips referenced by payroll or other protected financial records cannot be deleted.`,
  )) return;

  button.disabled = true;
  try {
    const result = await api(
      `/api/dispatch/movements/${encodeURIComponent(movementId)}`,
      { method: "DELETE" },
    );
    removeResourceRecord("trips", result.trip_id);
    if (state.dispatch.page > 1 && state.dispatch.movements.length === 1) {
      state.dispatch.page -= 1;
    }
    state.dispatch.loaded = false;
    await loadDispatchWorkflow({ force: true });
    showToast(
      result.warning || "Completed trip deleted.",
      result.warning ? "error" : "success",
    );
  } catch (error) {
    showToast(error.message || "Could not delete the completed trip.", "error");
    if (button.isConnected) button.disabled = false;
  }
}

async function submitDispatchDeparture(form) {
  if (form.dataset.submitting === "true") return;
  const errorElement = form.querySelector(".dispatch-form-error");
  if (form.elements.namedItem("load_type").value === "FULLS"
      && !state.dispatch.departureLoadItems.length) {
    setDispatchWizardStep(form, 3, { focus: true });
    errorElement.textContent = "Add at least one product to the trailer contents.";
    errorElement.hidden = false;
    form.querySelector(".dispatch-product-card-select")?.focus();
    return;
  }
  form.dataset.submitting = "true";
  const submit = form.querySelector('button[type="submit"]');
  submit.disabled = true;
  submit.textContent = "Saving departure…";
  errorElement.hidden = true;
  try {
    let movementId = form.dataset.movementId;
    if (!movementId) {
      const values = Object.fromEntries(new FormData(form).entries());
      const result = await api("/api/dispatch/movements", {
        method: "POST",
        body: JSON.stringify({
          origin_location_id: values.origin_location_id,
          destination_location_id: values.destination_location_id,
          ism_no: values.ism_no,
          truck_id: values.truck_id,
          driver_id: values.driver_id,
          trailer_id: values.trailer_id,
          load_type: values.load_type,
          pallet_quantity: values.pallet_quantity,
          load_items: values.load_type === "FULLS"
            ? state.dispatch.departureLoadItems
            : [],
          departure_at: values.departure_at,
          fuel_allocation: values.fuel_allocation || null,
          actual_fuel_expense: values.actual_fuel_expense || null,
          fuel_remarks: values.fuel_remarks || null,
        }),
      });
      movementId = result.id;
      if (!movementId) throw new Error("Departure was saved without a movement ID.");
      form.dataset.movementId = movementId;
      for (const control of form.elements) {
        if (!["departure_manifest", "fuel_invoice"].includes(control.name)) control.disabled = true;
      }
    }
    if (form.dataset.departureUploaded !== "true") {
      submit.textContent = "Uploading departure manifest…";
      await uploadDispatchDocument(
        movementId, "departure", form.elements.namedItem("departure_manifest").files?.[0],
      );
      form.dataset.departureUploaded = "true";
      form.elements.namedItem("departure_manifest").disabled = true;
    }
    const invoice = form.elements.namedItem("fuel_invoice").files?.[0];
    if (invoice && form.dataset.fuelInvoiceUploaded !== "true") {
      submit.textContent = "Uploading fuel invoice…";
      await uploadDispatchDocument(movementId, "fuel_invoice", invoice);
      form.dataset.fuelInvoiceUploaded = "true";
      form.elements.namedItem("fuel_invoice").disabled = true;
    }
    showToast("Departure saved. It will enter the receiving queue with the required manifest.");
    state.dispatch.loaded = false;
    state.dispatch.loading = false;
    state.dispatch.departureLoadItems = [];
    state.dispatch.departureWizardStep = 0;
    state.dispatch.departureDriver = "";
    state.dispatch.departureTruck = "";
    state.dispatch.departureTrailer = "";
    state.dispatch.departureDestination = "";
    state.dispatch.departureLoadType = "";
    state.dispatch.departurePalletQuantity = "";
    state.dispatch.departureIsm = "";
    state.dispatch.departureAt = "";
    state.dispatch.departureFuelAllocation = "";
    state.dispatch.departureFuelExpense = "";
    state.dispatch.departureFuelRemarks = "";
    state.dispatch.loadCatalogSearch = "";
    state.dispatch.loadCatalogSection = "";
    if (window.location.pathname === "/dispatcher/add-trip" && !window.location.hash) {
      window.location.hash = "trips";
      return;
    }
    await refreshDispatcherDispatchView();
  } catch (error) {
    errorElement.textContent = form.dataset.movementId
      ? `Movement ${form.dataset.movementId} was saved, but its documentation was not fully uploaded. Retry to finish without creating a duplicate. ${error.message}`
      : error.message || "Could not save this departure.";
    errorElement.hidden = false;
  } finally {
    form.dataset.submitting = "false";
    if (submit.isConnected) {
      submit.disabled = false;
      submit.textContent = form.dataset.movementId
        ? "Retry document upload"
        : "Confirm and Record Departure";
    }
  }
}

async function submitDispatchVerification(form) {
  if (form.dataset.submitting === "true") return;
  form.dataset.submitting = "true";
  const submit = form.querySelector('button[type="submit"]');
  const errorElement = form.querySelector('[role="alert"]');
  submit.disabled = true;
  submit.textContent = "Verifying ISM…";
  errorElement.hidden = true;
  try {
    const result = await api(
      `/api/dispatch/movements/${encodeURIComponent(form.dataset.movementId)}/verify`,
      {
        method: "POST",
        body: JSON.stringify({
          ism_no: form.elements.namedItem("ism_no").value,
        }),
      },
    );
    if (!result?.verified) {
      errorElement.textContent = "The ISM did not match. Check the physical manifest and try again.";
      errorElement.hidden = false;
      return;
    }
    showToast("ISM verified. The departure details are now available for arrival entry.");
    await refreshDispatcherDispatchView();
  } catch (error) {
    errorElement.textContent = error.message || "Could not verify the ISM.";
    errorElement.hidden = false;
  } finally {
    form.dataset.submitting = "false";
    if (submit.isConnected) {
      submit.disabled = false;
      submit.textContent = "Verify ISM";
    }
  }
}

async function submitDispatchArrival(form) {
  if (form.dataset.submitting === "true") return;
  form.dataset.submitting = "true";
  const submit = form.querySelector('button[type="submit"]');
  const errorElement = form.querySelector('[role="alert"]');
  submit.disabled = true;
  errorElement.hidden = true;
  try {
    if (form.dataset.arrivalUploaded !== "true") {
      submit.textContent = "Uploading arrival document…";
      await uploadDispatchDocument(
        form.dataset.movementId,
        "arrival",
        form.elements.namedItem("arrival_manifest").files?.[0],
      );
      form.dataset.arrivalUploaded = "true";
      form.elements.namedItem("arrival_manifest").disabled = true;
    }
    const values = Object.fromEntries(new FormData(form).entries());
    await api(
      `/api/dispatch/movements/${encodeURIComponent(form.dataset.movementId)}/arrival`,
      {
        method: "POST",
        body: JSON.stringify({
          arrival_at: values.arrival_at,
          arrival_fuel_expense: values.arrival_fuel_expense || null,
        }),
      },
    );
    showToast("Arrival submitted for admin review.");
    await refreshDispatcherDispatchView();
  } catch (error) {
    errorElement.textContent = error.message || "Could not submit this arrival.";
    errorElement.hidden = false;
  } finally {
    form.dataset.submitting = "false";
    if (submit.isConnected) {
      submit.disabled = false;
      submit.textContent = "Record Arrival for Review";
    }
  }
}

async function submitDispatchAssignment(form) {
  const submit = form.querySelector('button[type="submit"]');
  const errorElement = form.querySelector('[role="alert"]');
  submit.disabled = true;
  errorElement.hidden = true;
  try {
    await api("/api/dispatch/assignments", {
      method: "POST",
      body: JSON.stringify({
        user_id: form.elements.namedItem("user_id").value,
        location_id: form.elements.namedItem("location_id").value,
        can_depart: form.elements.namedItem("can_depart").checked,
        can_arrive: form.elements.namedItem("can_arrive").checked,
      }),
    });
    showToast("Dispatcher location access saved.");
    state.dispatch.loaded = false;
    await loadDispatchWorkflow({ force: true });
  } catch (error) {
    errorElement.textContent = error.message || "Could not save the assignment.";
    errorElement.hidden = false;
  } finally {
    if (submit.isConnected) submit.disabled = false;
  }
}

async function submitDispatchLocation(form) {
  const submit = form.querySelector('button[type="submit"]');
  const errorElement = form.querySelector('[role="alert"]');
  submit.disabled = true;
  errorElement.hidden = true;
  try {
    await api("/api/dispatch/locations", {
      method: "POST",
      body: JSON.stringify({
        id: form.elements.namedItem("id").value.trim().toUpperCase(),
        name: form.elements.namedItem("name").value.trim(),
        active: true,
      }),
    });
    showToast("Dispatch location saved.");
    state.dispatch.loaded = false;
    await loadDispatchWorkflow({ force: true });
  } catch (error) {
    errorElement.textContent = error.message || "Could not save the location.";
    errorElement.hidden = false;
  } finally {
    if (submit.isConnected) submit.disabled = false;
  }
}

async function submitDispatchCorrection(form) {
  const submit = form.querySelector('button[type="submit"]');
  const errorElement = form.querySelector('[role="alert"]');
  submit.disabled = true;
  errorElement.hidden = true;
  try {
    await api(
      `/api/dispatch/movements/${encodeURIComponent(form.dataset.movementId)}/correction`,
      {
        method: "POST",
        body: JSON.stringify({ reason: form.elements.namedItem("reason").value.trim() }),
      },
    );
    showToast("Correction request recorded in movement history.");
    state.dispatch.loaded = false;
    await loadDispatchWorkflow({ force: true });
  } catch (error) {
    errorElement.textContent = error.message || "Could not request a correction.";
    errorElement.hidden = false;
  } finally {
    if (submit.isConnected) submit.disabled = false;
  }
}

async function finalizeDispatchMovement(button) {
  if (!window.confirm("Finalize this movement as one canonical trip for revenue and payroll?")) return;
  button.disabled = true;
  try {
    const result = await api(
      `/api/dispatch/movements/${encodeURIComponent(button.dataset.id)}/finalize`,
      { method: "POST", body: JSON.stringify({}) },
    );
    showToast(`Movement finalized as trip #${result.trip_id}.`);
    state.dispatch.loaded = false;
    await loadDispatchWorkflow({ force: true });
    const refreshed = await api("/api/bootstrap");
    state.data = refreshed;
    state.csrfToken = refreshed.csrf_token || state.csrfToken;
    render();
  } catch (error) {
    showToast(error.message || "Could not finalize this movement.", "error");
  } finally {
    if (button.isConnected) button.disabled = false;
  }
}

async function loadDispatchHistory(button) {
  const panel = button.closest(".dispatch-movement-card")?.querySelector(".dispatch-history");
  if (!panel) return;
  if (!panel.hidden) {
    panel.hidden = true;
    button.textContent = "View movement history";
    return;
  }
  panel.hidden = false;
  panel.innerHTML = "<p>Loading history…</p>";
  button.disabled = true;
  try {
    const result = await api(
      `/api/dispatch/movements/${encodeURIComponent(button.dataset.id)}/history`,
    );
    panel.innerHTML = result.history?.length
      ? `<ol>${result.history.map((entry) => `<li><strong>${escapeHtml(entry.action.replaceAll("_", " "))}</strong> · ${escapeHtml(dispatchDateTime(entry.created_at))}<br /><small>${escapeHtml(JSON.stringify(entry.details || {}))}</small></li>`).join("")}</ol>`
      : "<p>No workflow events recorded.</p>";
    button.textContent = "Hide movement history";
  } catch (error) {
    panel.innerHTML = `<p class="dialog-error">${escapeHtml(error.message || "Could not load history.")}</p>`;
  } finally {
    button.disabled = false;
  }
}

function refreshDispatchDestinations(form) {
  const origin = form.elements.namedItem("origin_location_id")?.value;
  const destination = form.elements.namedItem("destination_location_id");
  if (!destination) return;
  const currentValue = destination.value;
  const routes = (state.data.truck_routes || []).filter((route) =>
    route.active !== false && route.origin_code === origin,
  );
  const destinations = [...new Map(routes.map((route) => [
    route.destination_code,
    { id: route.destination_code, name: route.destination_name },
  ])).values()];
  destination.innerHTML = `<option value="">Select destination</option>${destinations.map((location) =>
    `<option value="${escapeHtml(location.id)}">${escapeHtml(location.name)} (${escapeHtml(location.id)})</option>`,
  ).join("")}`;
  if (destinations.some((location) => location.id === currentValue)) {
    destination.value = currentValue;
  }
  state.dispatch.departureDestination = destination.value;
  updateDispatchDepartureAvailability(form);
}

function updateDispatchDepartureAvailability(form) {
  const origin = form.elements.namedItem("origin_location_id")?.value || "";
  const destination = form.elements.namedItem("destination_location_id");
  const submit = form.querySelector('button[type="submit"]');
  const message = form.querySelector(".dispatch-availability-message");
  if (!destination || !submit || !message) return;

  const hasActiveRoute = (state.data.truck_routes || []).some((route) =>
    route.active !== false
      && route.origin_code === origin
      && route.destination_code !== origin,
  );
  const hasTrucks = (state.data.vehicles || []).some((item) =>
    ["active", "available", "assigned"].includes(item.status),
  );
  const hasTrailers = (state.data.trailers || []).some((item) =>
    item.status === "active" && Number(item.pallet_capacity) > 0,
  );
  const hasDrivers = (state.data.drivers || []).some((item) =>
    item.status === "active",
  );
  const reasons = [];
  if (!origin) reasons.push("Select an active origin.");
  if (!hasActiveRoute) reasons.push("No active route is configured from this origin.");
  if (!hasTrucks || !hasDrivers || !hasTrailers) {
    reasons.push("Active trucks, drivers, and trailers are required before a departure can be created.");
  }
  submit.disabled = reasons.length > 0;
  message.textContent = reasons.join(" ");
  message.hidden = reasons.length === 0;
}

function validateDispatchPalletQuantity(form) {
  const trailerId = form.elements.namedItem("trailer_id")?.value;
  const quantity = form.elements.namedItem("pallet_quantity");
  if (!quantity) return;
  const trailer = (state.data.trailers || []).find((item) =>
    String(item.id) === String(trailerId),
  );
  const capacity = Number(trailer?.pallet_capacity);
  if (Number.isFinite(capacity) && capacity > 0) {
    quantity.max = String(capacity);
    quantity.setCustomValidity(
      Number(quantity.value) > capacity
        ? `Pallet quantity cannot exceed this trailer's capacity of ${capacity}.`
        : "",
    );
  } else {
    quantity.removeAttribute("max");
    quantity.setCustomValidity("");
  }
}

function renderResource(page) {
  if (page === "trips") return renderDispatchWorkflow();
  if (page === "tires") return renderTireMonitoring();
  if (page === "vehicles") return renderVehicleManagement();
  const config = RESOURCE_CONFIG[page];
  const listKey = page === "fuel" ? "fuel_logs" : page;
  const rows = filterRows(state.data[listKey], config.columns);
  if (page === "trips") {
    const visibleTripIds = new Set(rows.map((trip) => String(trip.id)));
    state.selectedTripIds = new Set(
      [...state.selectedTripIds].filter((tripId) => visibleTripIds.has(tripId)),
    );
  }
  const hasOptions = config.fields.some((field) =>
    ["vehicle", "truck", "trailer", "driver"].includes(field.type),
  );
  if (page === "trips") {
    const needsReferences = config.fields.some(
      (field) =>
        (field.type === "truck" && !state.data.vehicles.some((item) => ["active", "available", "assigned"].includes(item.status))) ||
        (field.type === "trailer" && !(state.data.trailers || []).some((item) => item.status === "active")) ||
        (field.type === "driver" && !state.data.drivers.length),
    );
    return `
      ${header(
        "FLEET DATA",
        config.title,
        "Review trip details or view them independently by driver, truck, origin, or destination.",
        '<button class="button button-secondary" data-action="trip-export" type="button">Export Excel</button><button class="button button-primary" data-action="new-record" type="button"><span aria-hidden="true">＋</span> Add Trip</button>',
      )}
      <section class="panel records-panel trips-report">
        <div class="panel-heading records-heading">
          <div><p class="eyebrow">SHIPMENT MANIFEST</p><h2>${escapeHtml(config.title)}</h2></div>
          <label class="search-box"><span class="sr-only">Search trips</span><span aria-hidden="true">⌕</span><input type="search" id="record-search" placeholder="Search trips" value="${escapeHtml(state.search)}" /></label>
        </div>
        <nav class="trip-view-tabs" aria-label="Trip views">
          <button class="trip-view-tab ${state.tripsGroupBy ? "" : "trip-view-tab-active"}" type="button" data-action="trip-group" data-group-by="" aria-pressed="${!state.tripsGroupBy}">All trips</button>
          <button class="trip-view-tab ${state.tripsGroupBy === "driver_name" ? "trip-view-tab-active" : ""}" type="button" data-action="trip-group" data-group-by="driver_name" aria-pressed="${state.tripsGroupBy === "driver_name"}">By driver</button>
          <button class="trip-view-tab ${state.tripsGroupBy === "truck_plate_number" ? "trip-view-tab-active" : ""}" type="button" data-action="trip-group" data-group-by="truck_plate_number" aria-pressed="${state.tripsGroupBy === "truck_plate_number"}">By truck</button>
          <button class="trip-view-tab ${state.tripsGroupBy === "origin" ? "trip-view-tab-active" : ""}" type="button" data-action="trip-group" data-group-by="origin" aria-pressed="${state.tripsGroupBy === "origin"}">By origin</button>
          <button class="trip-view-tab ${state.tripsGroupBy === "destination" ? "trip-view-tab-active" : ""}" type="button" data-action="trip-group" data-group-by="destination" aria-pressed="${state.tripsGroupBy === "destination"}">By destination</button>
        </nav>
        ${state.data.user?.role !== "dispatcher" ? `
          <div class="trip-bulk-actions" aria-label="Bulk trip actions">
            <span class="record-count" aria-live="polite">${formatNumber(state.selectedTripIds.size)} selected</span>
            <button class="button button-secondary button-small" type="button" data-action="select-visible-trips" ${rows.length && !state.bulkDeletingTrips ? "" : "disabled"}>Select all ${formatNumber(rows.length)} visible</button>
            <button class="button button-secondary button-small" type="button" data-action="clear-trip-selection" ${state.selectedTripIds.size && !state.bulkDeletingTrips ? "" : "disabled"}>Clear selection</button>
            <button class="button button-secondary button-small trip-bulk-delete-button" type="button" data-action="bulk-delete-trips" ${state.selectedTripIds.size && !state.bulkDeletingTrips ? "" : "disabled"}>${state.bulkDeletingTrips ? "Deleting…" : "Delete selected"}</button>
          </div>` : ""}
        <p class="record-count trip-table-hint">${formatNumber(rows.length)} ${rows.length === 1 ? "record" : "records"} · Select a trip to view full details</p>
        <div class="trip-view-content">
          ${groupedTripMarkup(rows, config)}
        </div>
      </section>
      ${tripCreationWizardMarkup(config, needsReferences)}
      ${tripDetailsDialogMarkup()}`;
  }
  if (page === "fuel") {
    return `
      ${header("FLEET DATA", config.title, "Review previously recorded fuel logs.")}
      <section class="panel records-panel">
        <div class="panel-heading records-heading">
          <div><p class="eyebrow">RECORDS</p><h2>${escapeHtml(config.title)}</h2></div>
          <label class="search-box"><span class="sr-only">Search ${escapeHtml(config.title.toLowerCase())}</span><span aria-hidden="true">⌕</span><input type="search" id="record-search" placeholder="Search records" value="${escapeHtml(state.search)}" /></label>
        </div>
        <p class="record-count">${formatNumber(rows.length)} ${rows.length === 1 ? "record" : "records"}</p>
        ${tableMarkup(rows, config.columns, state.data.user?.role === "dispatcher" ? null : config.api, { empty: `No ${config.singular} records` })}
      </section>`;
  }

  function renderVehicleManagement() {
    const isTrailer = state.vehicleSection === "trailers";
    const config = isTrailer ? RESOURCE_CONFIG.trailers : RESOURCE_CONFIG.vehicles;
    const records = isTrailer ? state.data.trailers || [] : state.data.vehicles || [];
    const rows = filterRows(records.map((record) => ({
      ...record,
      _asset_type: isTrailer ? "trailer" : "truck",
    })), config.columns);
    return `
      ${header("FLEET DATA", "Vehicles", "Manage trucks and trailers independently. Pallet capacity belongs to the trailer.")}
      <nav class="trip-view-tabs fleet-asset-tabs" aria-label="Vehicle types">
        <button class="trip-view-tab ${!isTrailer ? "trip-view-tab-active" : ""}" type="button" data-action="fleet-section" data-section="trucks" aria-pressed="${!isTrailer}">Trucks</button>
        <button class="trip-view-tab ${isTrailer ? "trip-view-tab-active" : ""}" type="button" data-action="fleet-section" data-section="trailers" aria-pressed="${isTrailer}">Trailers</button>
      </nav>
      <div class="resource-layout">
        <section class="panel form-panel">
          <div class="panel-heading"><div><p class="eyebrow">NEW ${isTrailer ? "TRAILER" : "TRUCK"}</p><h2>Add ${isTrailer ? "trailer" : "truck"}</h2></div></div>
          <form class="record-form" data-form="${isTrailer ? "trailers" : "vehicles"}">
            <div class="form-fields">${config.fields.map(fieldMarkup).join("")}</div>
            <p class="dialog-error" role="alert" hidden></p>
            <button class="button button-primary" type="submit">Save ${isTrailer ? "trailer" : "truck"}</button>
          </form>
        </section>
        <section class="panel records-panel">
          <div class="panel-heading records-heading">
            <div><p class="eyebrow">${isTrailer ? "TRAILER REGISTER" : "TRUCK REGISTER"}</p><h2>${escapeHtml(config.title)}</h2></div>
            <label class="search-box"><span class="sr-only">Search ${isTrailer ? "trailers" : "trucks"}</span><span aria-hidden="true">⌕</span><input type="search" id="record-search" placeholder="Search ${isTrailer ? "trailers" : "trucks"}" value="${escapeHtml(state.search)}" /></label>
          </div>
          <p class="record-count">${formatNumber(rows.length)} ${rows.length === 1 ? config.singular : `${config.singular}s`}</p>
          ${tableMarkup(rows, config.columns, null, {
            empty: `No ${config.singular} records`,
            rowAction: isTrailer ? "trailer-details" : undefined,
            rowLabel: isTrailer ? (row) => `View trailer ${row.plate_number || row.id} details` : undefined,
          })}
        </section>
      </div>
      ${isTrailer ? `
        <dialog class="record-dialog trailer-details-dialog" aria-labelledby="trailer-details-title">
          <div class="dialog-header">
            <div><p class="eyebrow">TRAILER DETAILS</p><h2 id="trailer-details-title">Trailer</h2></div>
            <button class="icon-button dialog-close" data-action="close-trailer-details" type="button" aria-label="Close trailer details">×</button>
          </div>
          <dl class="trip-details-grid trailer-details-content"></dl>
          <div class="dialog-actions">
            <button class="button button-secondary" data-action="delete-trailer-detail" type="button">Delete trailer</button>
            <button class="button button-primary" data-action="edit-trailer-detail" type="button">Edit trailer</button>
          </div>
        </dialog>` : ""}
      <dialog class="record-dialog fleet-edit-dialog" aria-labelledby="fleet-edit-title">
        <div class="dialog-header">
          <div><p class="eyebrow">FLEET ASSET</p><h2 id="fleet-edit-title">Edit record</h2></div>
          <button class="icon-button dialog-close" data-action="close-fleet-edit" type="button" aria-label="Close edit dialog">×</button>
        </div>
        <form class="dialog-form fleet-edit-form">
          <div class="dialog-fields"></div>
          <p class="dialog-error" role="alert" hidden></p>
          <div class="dialog-actions">
            <button class="button button-secondary" data-action="close-fleet-edit" type="button">Cancel</button>
            <button class="button button-primary" type="submit">Save changes</button>
          </div>
        </form>
      </dialog>`;
  }
  return `
    ${header("FLEET DATA", config.title, `Create and review ${config.singular} records.`)}
    <div class="resource-layout">
      <section class="panel form-panel">
        <div class="panel-heading"><div><p class="eyebrow">NEW RECORD</p><h2>Add ${escapeHtml(config.singular)}</h2></div></div>
        <form class="record-form" data-form="${page}">
          <div class="form-fields">${config.fields.map(fieldMarkup).join("")}</div>
          <button class="button button-primary" type="submit" ${hasOptions && config.fields.some((field) => (field.type === "vehicle" && !state.data.vehicles.length) || (field.type === "driver" && !state.data.drivers.length)) ? "disabled" : ""}>
            <span aria-hidden="true">＋</span> Save ${escapeHtml(config.singular)}
          </button>
        </form>
      </section>
      <section class="panel records-panel">
        <div class="panel-heading records-heading">
          <div><p class="eyebrow">RECORDS</p><h2>${escapeHtml(config.title)}</h2></div>
          <label class="search-box"><span class="sr-only">Search ${escapeHtml(config.title.toLowerCase())}</span><span aria-hidden="true">⌕</span><input type="search" id="record-search" placeholder="Search records" value="${escapeHtml(state.search)}" /></label>
        </div>
        <p class="record-count">${formatNumber(rows.length)} ${rows.length === 1 ? "record" : "records"}</p>
        ${tableMarkup(rows, config.columns, state.data.user?.role === "dispatcher" || page === "trips" ? null : config.api, { empty: `No ${config.singular} records` })}
      </section>
    </div>`;
}

function payrollOptionMarkup(records, selected, key, entityLabel, displayField) {
  return `<option value="">All ${entityLabel}s</option>${records.map((record) =>
    `<option value="${escapeHtml(record[key])}" ${String(record[key]) === String(selected) ? "selected" : ""}>${escapeHtml(record[displayField])}</option>`,
  ).join("")}`;
}

function payrollRows() {
  const report = state.payroll || { trips: [], drivers: [] };
  const filters = state.payrollFilters;
  const search = filters.ism_no.trim().toLocaleLowerCase();
  return report.trips.filter((trip) =>
    (!filters.driver_id || String(trip.driver_id) === filters.driver_id)
    && (!search || String(trip.ism_no || "").toLocaleLowerCase().includes(search))
    && (!filters.origin || trip.origin === filters.origin)
    && (!filters.destination || trip.destination === filters.destination),
  );
}

function sumCurrency(rows, field) {
  const cents = rows.reduce((total, row) => total + Math.round(Number(row[field] || 0) * 100), 0);
  return cents / 100;
}

function revenueDateOffset(value, days) {
  const date = new Date(`${value}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function revenueRangeForPreset(preset) {
  const end = dateInBusinessTimezone();
  const day = new Date(`${end}T00:00:00Z`);
  if (preset === "today") return { start_date: end, end_date: end };
  if (preset === "this_week") {
    const mondayOffset = (day.getUTCDay() + 6) % 7;
    return { start_date: revenueDateOffset(end, -mondayOffset), end_date: end };
  }
  if (preset === "this_year") return { start_date: `${end.slice(0, 4)}-01-01`, end_date: end };
  return { start_date: `${end.slice(0, 7)}-01`, end_date: end };
}

function revenueQueryParams() {
  const revenue = state.revenue;
  const params = new URLSearchParams({
    start_date: revenue.start_date,
    end_date: revenue.end_date,
    page: String(revenue.page),
    page_size: "25",
    sort_by: revenue.sort_by,
    sort_dir: revenue.sort_dir,
    bucket: revenue.bucket,
  });
  for (const key of [
    "origin", "destination", "route_number", "driver_id", "truck_id",
    "trailer_id", "pallet_capacity", "search",
  ]) {
    if (revenue[key]) params.set(key, revenue[key]);
  }
  return params;
}

function revenueQueryKey() {
  return revenueQueryParams().toString();
}

let revenueAbortController = null;
let revenueRequestId = 0;
let revenueSearchTimer = null;

async function loadRevenueReport() {
  if (state.page !== "revenue") return;
  const params = revenueQueryParams();
  const queryKey = params.toString();
  if (state.revenue.reportKey === queryKey || state.revenue.inflightKey === queryKey) return;
  revenueAbortController?.abort();
  const controller = new AbortController();
  revenueAbortController = controller;
  const requestId = ++revenueRequestId;
  state.revenue.inflightKey = queryKey;
  state.revenue.loading = true;
  state.revenue.error = "";
  state.revenue.report = null;
  render();
  try {
    const result = await api(`/api/revenue?${params}`, { signal: controller.signal });
    if (requestId !== revenueRequestId) return;
    state.revenue.report = result;
    state.revenue.reportKey = queryKey;
  } catch (error) {
    if (requestId !== revenueRequestId || error.name === "AbortError") return;
    state.revenue.error = error.message || "Could not load the Revenue dashboard.";
    state.revenue.reportKey = queryKey;
  } finally {
    if (requestId === revenueRequestId) {
      state.revenue.loading = false;
      state.revenue.inflightKey = "";
      if (state.page === "revenue") render();
    }
  }
}

function revenueOption(records, value, label) {
  return records.map((record) => {
    const selected = String(record.value) === String(value) ? "selected" : "";
    return `<option value="${escapeHtml(record.value)}" ${selected}>${escapeHtml(record.label)}</option>`;
  }).join("");
}

function revenueChartBars(items, labelField, valueField, countField, formatter = formatCurrency) {
  if (!items.length) return '<p class="revenue-empty-chart">No eligible trips in this selection.</p>';
  const max = Math.max(...items.map((item) => Number(item[valueField] || 0)), 0);
  return `<ol class="revenue-bars">${items.map((item) => {
    const value = Number(item[valueField] || 0);
    const width = max > 0 ? Math.max(2, (value / max) * 100) : 0;
    return `<li>
      <div class="revenue-bar-heading"><span>${escapeHtml(item[labelField] ?? "Unknown")}</span><strong>${escapeHtml(formatter(value))}</strong></div>
      <div class="revenue-bar-track" role="img" aria-label="${escapeHtml(item[labelField] ?? "Unknown")}: ${escapeHtml(formatter(value))}">
        <span style="width:${width.toFixed(2)}%"></span>
      </div>
      <small>${formatNumber(item[countField])} ${item[countField] === 1 ? "trip" : "trips"}</small>
    </li>`;
  }).join("")}</ol>`;
}

function revenueTrendMarkup(report) {
  const items = report.trend || [];
  if (!items.length) return '<p class="revenue-empty-chart">No eligible trips in this selection.</p>';
  const maxRevenue = Math.max(...items.map((item) => Number(item.revenue || 0)), 0);
  const maxTrips = Math.max(...items.map((item) => Number(item.trips || 0)), 0);
  return `<div class="revenue-trend" role="list" aria-label="Hauling revenue trend">
    ${items.map((item) => {
      const revenueHeight = maxRevenue ? Math.max(4, (Number(item.revenue || 0) / maxRevenue) * 100) : 0;
      const tripHeight = maxTrips ? Math.max(4, (Number(item.trips || 0) / maxTrips) * 100) : 0;
      return `<div class="revenue-trend-column" role="listitem" title="${escapeHtml(item.date)} · ${escapeHtml(formatCurrency(item.revenue))} · ${formatNumber(item.trips)} trips">
        <strong>${escapeHtml(formatCurrency(item.revenue))}</strong>
        <span class="revenue-trend-bars" aria-hidden="true">
          <i class="revenue-trend-bar" style="height:${revenueHeight.toFixed(2)}%"></i>
          <i class="revenue-trend-trip-bar" style="height:${tripHeight.toFixed(2)}%"></i>
        </span>
        <small>${escapeHtml(item.date)}</small>
        <span class="sr-only">${formatNumber(item.trips)} trips</span>
      </div>`;
    }).join("")}
  </div><p class="revenue-chart-note"><span class="revenue-legend-revenue">Revenue</span><span class="revenue-legend-trips">Trip volume</span> Bars use independent scales.</p>`;
}

function revenueExpensesMarkup(report) {
  const expenses = report.expenses || {};
  const rows = [
    ["Fuel costs", expenses.fuel_cost, `${formatNumber(expenses.fuel_log_count || 0)} records; ${formatNumber(expenses.fuel_missing_cost_count || 0)} without recorded cost`],
    ["Driver payroll expense", expenses.payroll_cost, `${formatNumber(expenses.payroll_recorded_trip_count || 0)} reviewed or finalized gross-pay items`],
    ["Maintenance", expenses.maintenance_cost, `${formatNumber(expenses.maintenance_record_count || 0)} service records`],
  ];
  const net = expenses.net_operating_revenue_available
    ? formatCurrency(expenses.net_operating_revenue)
    : "Unavailable";
  return `<article class="panel revenue-chart-panel revenue-expenses-panel">
    <div class="panel-heading"><div><p class="eyebrow">RECORDED COSTS</p><h2>Operating cost coverage</h2></div><span class="badge">Provisional</span></div>
    <dl class="revenue-expense-list">${rows.map(([label, amount, detail]) => `
      <div><dt>${escapeHtml(label)}<small>${escapeHtml(detail)}</small></dt><dd>${escapeHtml(formatCurrency(amount))}</dd></div>`).join("")}
      <div class="revenue-net-row"><dt>Net operating revenue<small>${escapeHtml(expenses.scope_note || "")}</small></dt><dd>${escapeHtml(net)}</dd></div>
    </dl>
    <p class="revenue-chart-note">Net subtracts recorded fuel, reviewed/finalized gross payroll, and maintenance costs. Payroll cash advances are not counted a second time. General operating expenses are not available in the current schema, so this is not a final profit figure.</p>
  </article>`;
}

function revenueRouteTableMarkup(report) {
  if (!(report.by_route || []).length) return "";
  const term = state.revenue.route_search.trim().toLocaleLowerCase();
  const direction = state.revenue.route_sort_dir === "asc" ? 1 : -1;
  const rows = (report.by_route || [])
    .filter((route) => !term || [
      route.route_label,
      route.route_number,
      route.origin,
      route.destination,
    ].some((value) => String(value ?? "").toLocaleLowerCase().includes(term)))
    .map((route) => ({
      ...route,
      average_revenue: route.trips ? Number(route.revenue) / Number(route.trips) : 0,
    }))
    .sort((left, right) => {
      const key = state.revenue.route_sort_by;
      const a = key === "label" ? String(left.route_label || "") : Number(left[key] || 0);
      const b = key === "label" ? String(right.route_label || "") : Number(right[key] || 0);
      const compared = typeof a === "string" ? a.localeCompare(b) : a - b;
      return compared === 0 ? String(left.route_label || "").localeCompare(String(right.route_label || "")) : compared * direction;
    });
  const columns = [
    ["route_number", "Route no."],
    ["route_label", "Route"],
    ["trips", "Trips", (value) => formatNumber(value)],
    ["revenue", "Recognized revenue", (value) => formatCurrency(value)],
    ["average_revenue", "Average per trip", (value) => formatCurrency(value)],
  ];
  return `<article class="panel revenue-chart-panel revenue-routes-panel">
    <div class="panel-heading"><div><p class="eyebrow">ROUTE PERFORMANCE</p><h2>Revenue by route</h2></div></div>
    <form class="revenue-route-tools" data-revenue-form="routes">
      <label class="search-box"><span aria-hidden="true">⌕</span><span class="sr-only">Filter routes</span><input name="route_search" type="search" placeholder="Filter routes" value="${escapeHtml(state.revenue.route_search)}" /></label>
      <label class="form-field"><span>Sort by</span><select name="route_sort_by">
        <option value="revenue" ${state.revenue.route_sort_by === "revenue" ? "selected" : ""}>Revenue</option>
        <option value="trips" ${state.revenue.route_sort_by === "trips" ? "selected" : ""}>Trip count</option>
        <option value="average_revenue" ${state.revenue.route_sort_by === "average_revenue" ? "selected" : ""}>Average revenue</option>
        <option value="label" ${state.revenue.route_sort_by === "label" ? "selected" : ""}>Route name</option>
      </select></label>
      <label class="form-field"><span>Direction</span><select name="route_sort_dir">
        <option value="desc" ${state.revenue.route_sort_dir === "desc" ? "selected" : ""}>Descending</option>
        <option value="asc" ${state.revenue.route_sort_dir === "asc" ? "selected" : ""}>Ascending</option>
      </select></label>
    </form>
    <div class="table-wrap revenue-route-table">${tableMarkup(rows, columns, null, { empty: "No routes match this filter" })}</div>
  </article>`;
}

function revenuePerformanceMarkup(report) {
  const panels = [];
  if ((report.trend || []).length) {
    panels.push(`<article class="panel revenue-chart-panel revenue-trend-panel"><div class="panel-heading"><div><p class="eyebrow">HAULING RATE REVENUE AND TRIP VOLUME</p><h2>Revenue trend</h2></div><span class="badge">${escapeHtml(state.revenue.bucket)}</span></div>${revenueTrendMarkup(report)}</article>`);
  }
  const breakdowns = [
    ["by_driver", "ASSOCIATED REVENUE", "Revenue by driver", "driver_name"],
    ["by_truck", "FLEET PERFORMANCE", "Revenue by truck", "truck_plate_number"],
    ["by_trailer", "TRAILER PERFORMANCE", "Revenue by trailer", "trailer_plate_number"],
  ];
  for (const [key, eyebrow, title, labelField] of breakdowns) {
    const rows = report[key] || [];
    if (!rows.length) continue;
    const note = key === "by_driver"
      ? '<p class="revenue-chart-note">Hauling revenue associated with assigned trips; not driver salary or profit.</p>'
      : "";
    panels.push(`<article class="panel revenue-chart-panel"><div class="panel-heading"><div><p class="eyebrow">${eyebrow}</p><h2>${title}</h2></div></div>${note}${revenueChartBars(rows, labelField, "revenue", "trips")}</article>`);
  }
  const combinations = (report.by_truck_trailer || []).map((row) => ({
    ...row,
    asset_label: `${row.truck_plate_number} + ${row.trailer_plate_number}`,
  }));
  if (combinations.length) {
    panels.push(`<article class="panel revenue-chart-panel"><div class="panel-heading"><div><p class="eyebrow">ASSET COMBINATIONS</p><h2>Revenue by truck + trailer</h2></div></div>${revenueChartBars(combinations, "asset_label", "revenue", "trips")}</article>`);
  }
  const capacities = (report.by_capacity || []).map((row) => ({
    ...row,
    capacity_label: row.pallet_capacity == null ? "Unknown capacity" : `${formatNumber(row.pallet_capacity)} pallets`,
  }));
  if (capacities.length) {
    panels.push(`<article class="panel revenue-chart-panel"><div class="panel-heading"><div><p class="eyebrow">TRAILER CONFIGURATION</p><h2>Revenue by pallet capacity</h2></div></div>${revenueChartBars(capacities, "capacity_label", "revenue", "trips")}</article>`);
  }
  const volume = (report.trip_volume || []).map((row) => ({ ...row, bucket_label: row.date }));
  if (volume.length) {
    panels.push(`<article class="panel revenue-chart-panel"><div class="panel-heading"><div><p class="eyebrow">VOLUME</p><h2>Rate-backed trip volume</h2></div></div>${revenueChartBars(volume, "bucket_label", "trips", "trips", formatNumber)}</article>`);
  }
  const routeTable = revenueRouteTableMarkup(report);
  if (routeTable) panels.push(routeTable);
  return panels.length ? `<section class="revenue-chart-grid">${panels.join("")}</section>` : "";
}

function revenueRecentTripsMarkup(report) {
  const columns = [
    ["shipment_date", "Trip date"],
    ["id", "Trip ID"],
    ["ism_no", "ISM / reference"],
    ["route_pair", "Route", (_value, row) => escapeHtml(row.route_pair || `${row.origin || "Unknown"} → ${row.destination || "Unknown"}`)],
    ["driver_name", "Driver"],
    ["truck_plate_number", "Truck"],
    ["trailer_plate_number", "Trailer"],
    ["recognized_revenue", "Hauling rate revenue", (value) => formatCurrency(value)],
  ];
  return `<section class="panel revenue-ledger-panel">
    <div class="panel-heading"><div><p class="eyebrow">LATEST ACTIVITY</p><h2>Recent trips</h2><p class="page-description">Select a row to open its trip record. Rate revenue is zero only for cancelled trips or trips without a verified saved hauling-rate snapshot.</p></div></div>
    <div class="table-wrap revenue-recent-table">${tableMarkup(report.recent_trips || [], columns, null, { empty: "No trips in this date range", rowAction: "trip-details" })}</div>
  </section>`;
}

function revenueStatusBadge(status) {
  const labels = { pending: "Pending", eligible: "Eligible", cancelled: "Cancelled" };
  return `<span class="badge badge-revenue-${escapeHtml(status || "pending")}">${escapeHtml(labels[status] || "Pending")}</span>`;
}

function revenueLedgerMarkup(report) {
  const ledger = report.ledger || { items: [], page: 1, page_size: 25, total: 0 };
  const items = ledger.items || [];
  const columns = [
    ["shipment_date", "Trip date"],
    ["id", "Trip ID", (value, row) => `<button class="text-button revenue-trip-link" type="button" data-action="revenue-trip-details" data-id="${escapeHtml(value)}">${escapeHtml(value)}</button>`],
    ["ism_no", "ISM / reference"],
    ["origin", "Origin"],
    ["destination", "Destination"],
    ["route_number", "Route"],
    ["driver_name", "Driver"],
    ["truck_plate_number", "Truck"],
    ["trailer_plate_number", "Trailer"],
    ["pallet_capacity", "Capacity", (value) => value == null ? "Unknown" : `${formatNumber(value)} pallets`],
    ["applied_rate", "Applied rate", (value) => value == null ? "Missing" : formatCurrency(value)],
    ["revenue_status", "Status", (value, row) =>
      `${revenueStatusBadge(value)}${value === "cancelled" ? '<small class="revenue-invalid-note">Excluded from rate revenue</small>' : !row.revenue_eligible ? '<small class="revenue-invalid-note">Rate snapshot requires review</small>' : ""}`],
    ["adjustments", "Adjustments", (value, row) => {
      const entries = row.adjustment_details || [];
      if (!entries.length) return formatCurrency(value);
      return `<details class="revenue-adjustment-list"><summary>${formatCurrency(value)} · ${entries.length}</summary><ul>${entries.map((entry) =>
        `<li>${escapeHtml(formatCurrency(entry.amount))} — ${escapeHtml(entry.reason)} <small>${escapeHtml(entry.created_at)}</small></li>`,
      ).join("")}</ul></details>`;
    }],
    ["recognized_revenue", "Hauling rate revenue", (value) => formatCurrency(value)],
    ["_manage", "Manage", (_value, row) => `<button class="button button-secondary button-small" type="button" data-action="revenue-manage-trip" data-id="${escapeHtml(row.id)}">Manage</button>`],
  ];
  const table = tableMarkup(items, columns, null, {
    empty: "No trips match these filters",
    rowAction: "trip-details",
    rowLabel: (row) => `View trip ${row.ism_no || row.id}`,
  });
  const first = ledger.total ? ((ledger.page - 1) * ledger.page_size) + 1 : 0;
  const last = Math.min(ledger.page * ledger.page_size, ledger.total);
  const pageCount = Math.max(1, Math.ceil(ledger.total / ledger.page_size));
  return `
    <div class="panel-heading revenue-ledger-heading">
      <div><p class="eyebrow">TRIP-LEVEL DETAIL</p><h2>Revenue Ledger</h2>
      <p class="page-description">Hauling rate total for these filters: <strong>${escapeHtml(formatCurrency(report.summary.total_revenue))}</strong></p></div>
      <span class="record-count">${formatNumber(ledger.total)} matching trips</span>
    </div>
    <form class="revenue-ledger-tools" data-revenue-form="ledger">
      <label class="search-box"><span aria-hidden="true">⌕</span><span class="sr-only">Search ledger</span><input name="search" type="search" maxlength="120" placeholder="Search trip, driver, or vehicle" value="${escapeHtml(state.revenue.search)}" /></label>
      <label class="form-field"><span>Sort ledger by</span><select name="sort_by">
        <option value="shipment_date" ${state.revenue.sort_by === "shipment_date" ? "selected" : ""}>Trip date</option>
        <option value="id" ${state.revenue.sort_by === "id" ? "selected" : ""}>Trip ID</option>
        <option value="route" ${state.revenue.sort_by === "route" ? "selected" : ""}>Route</option>
        <option value="revenue" ${state.revenue.sort_by === "revenue" ? "selected" : ""}>Hauling rate revenue</option>
      </select></label>
      <label class="form-field"><span>Direction</span><select name="sort_dir">
        <option value="desc" ${state.revenue.sort_dir === "desc" ? "selected" : ""}>Descending</option>
        <option value="asc" ${state.revenue.sort_dir === "asc" ? "selected" : ""}>Ascending</option>
      </select></label>
    </form>
    ${state.revenue.selectedTripId ? revenueManagePanel(items.find((item) => String(item.id) === String(state.revenue.selectedTripId))) : ""}
    <div class="table-wrap revenue-ledger-table">${table}</div>
    <div class="revenue-pagination">
      <span>Showing ${formatNumber(first)}–${formatNumber(last)} of ${formatNumber(ledger.total)}</span>
      <div><button class="button button-secondary button-small" data-action="revenue-page" data-page="${Math.max(1, ledger.page - 1)}" ${ledger.page <= 1 ? "disabled" : ""}>Previous</button>
      <span>Page ${formatNumber(ledger.page)} of ${formatNumber(pageCount)}</span>
      <button class="button button-secondary button-small" data-action="revenue-page" data-page="${Math.min(pageCount, ledger.page + 1)}" ${ledger.page >= pageCount ? "disabled" : ""}>Next</button></div>
    </div>`;
}

function revenueManagePanel(trip) {
  if (!trip) return "";
  return `<section class="panel revenue-manage-panel" aria-label="Manage trip revenue">
    <div class="panel-heading"><div><p class="eyebrow">MANAGEMENT ACTION</p><h2>Trip #${escapeHtml(trip.id)} · ${escapeHtml(trip.ism_no || "No ISM reference")}</h2></div>
      <button class="button button-secondary button-small" type="button" data-action="revenue-close-manage">Close</button></div>
    <p class="page-description">Revenue status changes require a reason and are audit-logged. Rate adjustments are append-only, auditable, and cannot reduce recognized revenue below zero.</p>
    <div class="revenue-management-forms">
      <form data-revenue-form="status" data-trip-id="${escapeHtml(trip.id)}">
        <label class="form-field"><span>Revenue status</span><select name="status">
          <option value="pending" ${trip.revenue_status === "pending" ? "selected" : ""}>Pending</option>
          <option value="eligible" ${trip.revenue_status === "eligible" ? "selected" : ""}>Eligible</option>
          <option value="cancelled" ${trip.revenue_status === "cancelled" ? "selected" : ""}>Cancelled</option>
        </select></label>
        <label class="form-field"><span>Reason</span><input name="reason" maxlength="1000" required /></label>
        <button class="button button-primary" type="submit">Save status</button>
      </form>
      <form data-revenue-form="adjustment" data-trip-id="${escapeHtml(trip.id)}">
        <label class="form-field"><span>Adjustment (₱; use negative to reverse)</span><input name="amount" type="number" step="0.01" required /></label>
        <label class="form-field"><span>Reason</span><input name="reason" maxlength="1000" required /></label>
        <button class="button button-secondary" type="submit">Add audited adjustment</button>
      </form>
    </div>
  </section>`;
}

function revenueDashboardMarkup(report) {
  const revenue = state.revenue;
  const routes = state.data.truck_routes || [];
  const drivers = state.data.drivers || [];
  const trucks = state.data.vehicles || [];
  const trailers = state.data.trailers || [];
  const routeNumbers = [...new Set(routes.map((route) => route.route_number).filter((value) => value != null))]
    .sort((left, right) => left - right);
  const capacities = [...new Set(trailers.map((trailer) => trailer.pallet_capacity).filter((value) => value != null))]
    .sort((left, right) => left - right);
  const start = revenue.start_date;
  const end = revenue.end_date;
  const isCurrentReport = report && revenue.reportKey === revenueQueryKey();
  const selectedReport = isCurrentReport ? report : null;
  const summary = selectedReport?.summary;
  const routeOptions = [...new Set(routes.map((route) => route.origin_code))].sort();
  const destinationOptions = [...new Set(routes.map((route) => route.destination_code))].sort();
  const options = selectedReport ? `
    <div class="stats-grid revenue-kpis">
      ${statCard("Total hauling rate revenue", formatCurrency(summary.total_revenue), "teal", "₱", "Verified saved trip rates and audited adjustments")}
      ${statCard("Rate-backed trips", formatNumber(summary.eligible_trips), "blue", "⌁", "Verified rate snapshot; cancelled trips excluded")}
      ${statCard("Average rate per trip", summary.average_revenue == null ? "—" : formatCurrency(summary.average_revenue), "green", "↗", "Hauling rate revenue divided by rate-backed trips")}
      ${statCard("Recorded fuel costs", formatCurrency(selectedReport.expenses?.fuel_cost), "orange", "⛽", `${formatNumber(selectedReport.expenses?.fuel_log_count || 0)} fuel logs`)}
      ${statCard("Payroll expenses", formatCurrency(selectedReport.expenses?.payroll_cost), "red", "₱", `${formatNumber(selectedReport.expenses?.payroll_recorded_trip_count || 0)} reviewed/finalized items; included in net`)}
      ${statCard("Net operating revenue", selectedReport.expenses?.net_operating_revenue_available ? formatCurrency(selectedReport.expenses.net_operating_revenue) : "Unavailable", "purple", "Δ", "Provisional; recorded expenses only")}
    </div>
    ${revenuePerformanceMarkup(selectedReport)}
    <section class="revenue-chart-grid">${revenueExpensesMarkup(selectedReport)}</section>
    ${revenueRecentTripsMarkup(selectedReport)}
    <section class="panel revenue-ledger-panel">${revenueLedgerMarkup(selectedReport)}</section>
    ${tripDetailsDialogMarkup()}` : `
      <div class="revenue-loading-grid" role="status" aria-live="polite"><span>Loading revenue report…</span>
        <div class="revenue-loading-cards"><i></i><i></i><i></i><i></i><i></i><i></i></div>
        <i class="revenue-loading-chart"></i><i class="revenue-loading-ledger"></i>
      </div>`;
  return `<div class="revenue-page">
    ${header("FINANCE", "Revenue & hauling performance", "Hauling rate totals use each trip's verified saved rate snapshot. Pending trips with a verified rate are included; cancelled or unverified trips are excluded.")}
    <details class="panel revenue-filter-panel" data-revenue-filters ${revenue.filters_open ? "open" : ""}>
      <summary class="revenue-filter-summary">
        <span><span class="eyebrow">REPORT FILTERS</span><strong>${escapeHtml(start)} through ${escapeHtml(end)}</strong></span>
        <span class="revenue-filter-toggle">${revenue.filters_open ? "Hide filters" : "Show filters"}</span>
      </summary>
      <form class="revenue-filters" data-revenue-form="filters">
        <label class="form-field"><span>Date range</span><select name="preset">
          <option value="today" ${revenue.preset === "today" ? "selected" : ""}>Today</option>
          <option value="this_week" ${revenue.preset === "this_week" ? "selected" : ""}>This week</option>
          <option value="this_month" ${revenue.preset === "this_month" ? "selected" : ""}>This month</option>
          <option value="this_year" ${revenue.preset === "this_year" ? "selected" : ""}>This year</option>
          <option value="custom" ${revenue.preset === "custom" ? "selected" : ""}>Custom range</option>
        </select></label>
        <label class="form-field"><span>Trend grouping</span><select name="bucket">
          <option value="day" ${revenue.bucket === "day" ? "selected" : ""}>Daily</option>
          <option value="week" ${revenue.bucket === "week" ? "selected" : ""}>Weekly</option>
          <option value="month" ${revenue.bucket === "month" ? "selected" : ""}>Monthly</option>
        </select></label>
        <label class="form-field"><span>From</span><input name="start_date" type="date" value="${escapeHtml(start)}" required /></label>
        <label class="form-field"><span>Through</span><input name="end_date" type="date" value="${escapeHtml(end)}" required /></label>
        <label class="form-field"><span>Origin</span><select name="origin"><option value="">All origins</option>${revenueOption(routeOptions.map((value) => ({ value, label: value })), revenue.origin)}</select></label>
        <label class="form-field"><span>Destination</span><select name="destination"><option value="">All destinations</option>${revenueOption(destinationOptions.map((value) => ({ value, label: value })), revenue.destination)}</select></label>
        <label class="form-field"><span>Route number</span><select name="route_number"><option value="">All routes</option>${revenueOption(routeNumbers.map((value) => ({ value, label: `Route ${value}` })), revenue.route_number)}</select></label>
        <label class="form-field"><span>Driver</span><select name="driver_id"><option value="">All drivers</option>${revenueOption(drivers.map((row) => ({ value: row.id, label: row.name })), revenue.driver_id)}</select></label>
        <label class="form-field"><span>Truck</span><select name="truck_id"><option value="">All trucks</option>${revenueOption(trucks.map((row) => ({ value: row.id, label: `${row.plate_number} · ${row.make || ""} ${row.model || ""}`.trim() })), revenue.truck_id)}</select></label>
        <label class="form-field"><span>Trailer</span><select name="trailer_id"><option value="">All trailers</option>${revenueOption(trailers.map((row) => ({ value: row.id, label: row.plate_number })), revenue.trailer_id)}</select></label>
        <label class="form-field"><span>Pallet capacity</span><select name="pallet_capacity"><option value="">All capacities</option>${revenueOption(capacities.map((value) => ({ value, label: `${formatNumber(value)} pallets` })), revenue.pallet_capacity)}</select></label>
        <button class="button button-secondary revenue-reset" type="button" data-action="revenue-reset">Reset filters</button>
      </form>
    </details>
    ${revenue.error ? `<section class="error-card revenue-error" role="alert"><p>${escapeHtml(revenue.error)}</p><button class="button button-primary" type="button" data-action="revenue-retry">Retry</button></section>` : ""}
    ${options}
  </div>`;
}

function renderPayroll() {
  const report = state.payroll;
  const [startDate, endDate] = [state.payrollPeriod.start_date, state.payrollPeriod.end_date];
  const key = `${startDate}:${endDate}`;
  if (state.payrollKey !== key && state.payrollRequestedKey !== key) {
    state.payrollRequestedKey = key;
    api(`/api/payroll?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`)
      .then((result) => {
        state.payroll = result;
        state.payrollKey = key;
        if (state.page === "payroll") render();
      })
      .catch((error) => {
        state.payrollRequestedKey = "";
        if (state.page === "payroll") {
          view.innerHTML = `${header("PAYROLL", "Payroll", "Driver earnings and payroll review.")}<div class="error-card"><p>${escapeHtml(error.message)}</p><button class="button button-primary" data-action="payroll-reload" type="button">Retry</button></div>`;
        }
      });
  }

  const drivers = report?.drivers || [];
  const allTrips = report?.trips || [];
  const visibleTrips = payrollRows();
  const selectedDriver = state.payrollFilters.driver_id;
  const driverSummaries = drivers.filter((driver) =>
    !selectedDriver || String(driver.driver_id) === selectedDriver,
  );
  const totals = {
    gross: sumCurrency(driverSummaries, "gross_pay"),
    advances: sumCurrency(driverSummaries, "cash_advances"),
    overdraft: sumCurrency(driverSummaries.map((driver) => ({
      outstanding: driver.remaining_overdraft ?? driver.overdraft_balance,
    })), "outstanding"),
    net: sumCurrency(driverSummaries.map((driver) => ({
      payable: driver.final_net_pay ?? Math.max(Number(driver.net_before_overdraft || 0), 0),
    })), "payable"),
  };
  const visibleTripIds = new Set(
    visibleTrips.filter((trip) => trip.eligible).map((trip) => String(trip.id)),
  );
  const eligibleTripCounts = new Map();
  for (const trip of allTrips) {
    if (!trip.eligible || !visibleTripIds.has(String(trip.id))) continue;
    const key = trip.driver_key || `id:${trip.driver_id}`;
    eligibleTripCounts.set(key, (eligibleTripCounts.get(key) || 0) + 1);
  }
  const visibleTripsByDriver = new Map();
  for (const trip of visibleTrips) {
    const key = trip.driver_key || `id:${trip.driver_id}`;
    const driverTrips = visibleTripsByDriver.get(key) || [];
    driverTrips.push(trip);
    visibleTripsByDriver.set(key, driverTrips);
  }
  const advancesByDriver = new Map();
  for (const advance of report?.cash_advances || []) {
    const key = String(advance.driver_id);
    const driverAdvances = advancesByDriver.get(key) || [];
    driverAdvances.push(advance);
    advancesByDriver.set(key, driverAdvances);
  }
  const visibleSummary = driverSummaries.map((driver) => ({
    ...driver,
    total_trips: eligibleTripCounts.get(
      driver.driver_key || `id:${driver.driver_id}`,
    ) || 0,
  }));
  const status = report?.status || "draft";
  const isDraft = status === "draft";
  const tripColumns = [
    ["payroll_date", "Date"],
    ["driver_name", "Driver Name"],
    ["ism_no", "ISM Number"],
    ["origin", "Origin"],
    ["destination", "Destination"],
    ["rate", "Trip Rate", (value) => value == null ? "Unconfigured Route" : formatCurrency(value)],
    ["truck_route_rate", "Truck Hauling Rate", displayTruckRate],
    ["issue", "Review"],
  ];
  const origins = [...new Set(allTrips.map((trip) => trip.origin).filter(Boolean))].sort();
  const destinations = [...new Set(allTrips.map((trip) => trip.destination).filter(Boolean))].sort();
  const driverCards = visibleSummary.map((driver) => {
    const driverKey = driver.driver_key || `id:${driver.driver_id}`;
    const driverTrips = visibleTripsByDriver.get(driverKey) || [];
    const cashAdvances = advancesByDriver.get(String(driver.driver_id)) || [];
    return `
      <details class="payroll-driver-details">
        <summary>
          <span><strong>${escapeHtml(driver.driver_name)}</strong><small>${formatNumber(driver.total_trips)} eligible trips</small></span>
          <span class="payroll-summary-amount">${formatCurrency(driver.gross_pay)}</span>
          <span class="badge badge-${escapeHtml(status)}">${escapeHtml(status)}</span>
          <span class="button button-secondary button-small">View Details</span>
        </summary>
        <div class="payroll-driver-body">
          <section class="payroll-breakdown payroll-earnings">
            <div class="payroll-breakdown-heading"><p class="eyebrow">EARNINGS BREAKDOWN</p><span>${formatNumber(driverTrips.length)} trip line items</span></div>
            ${tableMarkup(driverTrips, tripColumns, null, { empty: "No trips for this driver in the selected filters" })}
          </section>
          <div class="payroll-breakdown-columns">
            <section class="payroll-breakdown payroll-deductions">
              <div class="payroll-breakdown-heading"><p class="eyebrow">DEDUCTIONS &amp; ADJUSTMENTS</p></div>
              <div class="table-wrap payroll-deductions-wrap">
                <table class="payroll-deductions-table">
                  <tbody>
                    <tr><th scope="row">Cash advances</th><td>${formatCurrency(driver.cash_advances)}</td></tr>
                    <tr><th scope="row">Claims</th><td>Coming Soon</td></tr>
                    <tr><th scope="row">Opening overdraft</th><td>${formatCurrency(driver.opening_overdraft)}</td></tr>
                    <tr><th scope="row">New overdraft</th><td>${formatCurrency(driver.new_overdraft)}</td></tr>
                    <tr><th scope="row">Overdraft deduction</th><td>${formatCurrency(driver.overdraft_deduction)}</td></tr>
                    <tr><th scope="row">Outstanding overdraft</th><td>${formatCurrency(driver.remaining_overdraft ?? driver.overdraft_balance)}</td></tr>
                  </tbody>
                </table>
              </div>
            </section>
            <section class="payroll-net-summary">
              <p class="eyebrow">NET PAY SUMMARY</p>
              <div><span>Gross earnings</span><strong>${formatCurrency(driver.gross_pay)}</strong></div>
              <div><span>Net before overdraft</span><strong>${formatCurrency(driver.net_before_overdraft)}</strong></div>
              <div class="payroll-net-pay"><span>Final net pay</span><strong>${formatCurrency(driver.final_net_pay ?? Math.max(Number(driver.net_before_overdraft || 0), 0))}</strong></div>
              <div><span>Remaining amount due</span><strong>${formatCurrency(driver.remaining_amount_due)}</strong></div>
            </section>
          </div>
          ${driver.overdraft_transactions?.length ? `<div><p class="eyebrow">OVERDRAFT TRANSACTION HISTORY</p>${tableMarkup(driver.overdraft_transactions, [
            ["effective_date", "Date"],
            ["transaction_type", "Transaction"],
            ["amount", "Amount", formatCurrency],
            ["remarks", "Remarks"],
          ], null, { empty: "No overdraft transactions" })}</div>` : ""}
          ${cashAdvances.length ? `<p class="record-count">Cash advances: ${cashAdvances.map((advance) => `${escapeHtml(advance.advance_date)} · ${formatCurrency(advance.amount)}${advance.remarks ? ` · ${escapeHtml(advance.remarks)}` : ""}`).join(" | ")}</p>` : ""}
        </div>
      </details>`;
  }).join("");
  return `
    <div class="payroll-page">
    ${header("FINANCE", "Payroll", "Review route-based earnings, advances, overdrafts, and driver payroll.", '<button class="button button-secondary" data-action="payroll-export" type="button">Export Excel</button>')}
    <section class="panel payroll-period-bar payroll-section payroll-period-details">
      <div class="panel-heading"><div><p class="eyebrow">PAY PERIOD</p><h2>Employee &amp; pay period details</h2></div><span class="badge badge-${escapeHtml(status)}">${escapeHtml(status)}</span></div>
      <form id="payroll-period-form" class="payroll-toolbar">
        <label class="form-field"><span>Period start</span><input name="start_date" type="date" value="${escapeHtml(startDate)}" required /></label>
        <label class="form-field"><span>Period end</span><input name="end_date" type="date" value="${escapeHtml(endDate)}" required /></label>
        <button class="button button-primary" type="submit">Generate Report</button>
      </form>
      <div class="payroll-filter-grid">
        <label class="form-field"><span>Driver</span><select id="payroll-driver-filter">${payrollOptionMarkup(state.data.drivers, selectedDriver, "id", "driver", "name")}</select></label>
        <label class="form-field"><span>Search ISM number</span><input id="payroll-ism-filter" type="search" placeholder="Search ISM" value="${escapeHtml(state.payrollFilters.ism_no)}" /></label>
        <label class="form-field"><span>Origin</span><select id="payroll-origin-filter"><option value="">All origins</option>${origins.map((origin) => `<option ${origin === state.payrollFilters.origin ? "selected" : ""} value="${escapeHtml(origin)}">${escapeHtml(origin)}</option>`).join("")}</select></label>
        <label class="form-field"><span>Destination</span><select id="payroll-destination-filter"><option value="">All destinations</option>${destinations.map((destination) => `<option ${destination === state.payrollFilters.destination ? "selected" : ""} value="${escapeHtml(destination)}">${escapeHtml(destination)}</option>`).join("")}</select></label>
      </section>
    </div>
    <div class="stats-grid payroll-stats">
      ${statCard("Total Drivers", formatNumber(driverSummaries.length), "blue", "♙")}
      ${statCard("Total Trips", formatNumber(visibleTrips.filter((trip) => trip.eligible).length), "teal", "⌁")}
      ${statCard("Total Gross Payroll", formatCurrency(totals.gross), "green", "₱")}
      ${statCard("Total Cash Advances", formatCurrency(totals.advances), "orange", "↓")}
      ${statCard("Total Overdraft Balance", formatCurrency(totals.overdraft), "red", "↗")}
      ${statCard("Total Net Payable", formatCurrency(totals.net), "purple", "✓")}
    </div>
    <section class="panel payroll-workflow">
      <div><p class="eyebrow">PAYROLL WORKFLOW</p><h2>${escapeHtml(status === "finalized" ? "Payroll finalized" : status === "reviewed" ? "Ready for finalization" : "Draft payroll")}</h2><p class="page-description">Draft earnings use origin and destination only. A registered driver and ISM number are required when reviewing payroll. Claims are not deducted.</p></div>
      <div class="page-heading-actions">
        ${isDraft ? '<button class="button button-secondary" data-action="payroll-review" type="button">Review Payroll</button>' : ""}
        ${status === "reviewed" ? '<label class="settlement-toggle"><input id="settle-overdraft" type="checkbox" /> Settle overdraft from payable amount</label><button class="button button-primary" data-action="payroll-finalize" type="button">Finalize Payroll</button>' : ""}
      </div>
    </section>
    ${report?.issues?.length ? `<section class="panel payroll-issues"><div class="panel-heading"><div><p class="eyebrow">REQUIRES REVIEW</p><h2>${formatNumber(report.issues.length)} trips need attention</h2></div></div><p class="page-description">These trips are excluded from earnings. Resolve the origin, destination, route, or duplicate-payroll issue shown for each trip in the Trips data.</p>${tableMarkup(report.issues, tripColumns, null, { empty: "No review issues" })}</section>` : ""}
    <section class="panel payroll-advances">
      <div class="panel-heading"><div><p class="eyebrow">CASH ADVANCES</p><h2>Record an advance</h2></div></div>
      ${isDraft ? `<form id="cash-advance-form" class="payroll-entry-form">
        <label class="form-field"><span>Driver</span><select name="driver_id" required><option value="">Select driver</option>${state.data.drivers.map((driver) => `<option value="${escapeHtml(driver.id)}">${escapeHtml(driver.name)}</option>`).join("")}</select></label>
        <label class="form-field"><span>Date</span><input name="advance_date" type="date" min="${escapeHtml(startDate)}" max="${escapeHtml(endDate)}" required /></label>
        <label class="form-field"><span>Amount (₱)</span><input name="amount" type="number" min="0.01" step="0.01" required /></label>
        <label class="form-field"><span>Reference (optional)</span><input name="reference" type="text" maxlength="100" /></label>
        <label class="form-field"><span>Remarks (optional)</span><input name="remarks" type="text" maxlength="500" /></label>
        <button class="button button-primary" type="submit">Add Advance</button>
      </form>` : '<p class="page-description">Cash advances are locked after payroll review.</p>'}
    </section>
    <section class="panel payroll-advances">
      <div class="panel-heading"><div><p class="eyebrow">OVERDRAFT LEDGER</p><h2>Record an approved overdraft transaction</h2></div></div>
      <form id="overdraft-form" class="payroll-entry-form">
        <label class="form-field"><span>Driver</span><select name="driver_id" required><option value="">Select driver</option>${state.data.drivers.map((driver) => `<option value="${escapeHtml(driver.id)}">${escapeHtml(driver.name)}</option>`).join("")}</select></label>
        <label class="form-field"><span>Transaction</span><select name="transaction_type"><option value="opening">Opening balance</option><option value="new">New overdraft</option></select></label>
        <label class="form-field"><span>Effective date</span><input name="effective_date" type="date" value="${escapeHtml(endDate)}" required /></label>
        <label class="form-field"><span>Amount (₱)</span><input name="amount" type="number" min="0.01" step="0.01" required /></label>
        <label class="form-field"><span>Remarks</span><input name="remarks" type="text" maxlength="500" required /></label>
        <button class="button button-secondary" type="submit">Record Overdraft</button>
      </form>
      <p class="page-description">Overdraft entries require an explicit administrator action; negative payroll is never converted automatically.</p>
    </section>
    <section class="panel payroll-drivers">
      <div class="panel-heading"><div><p class="eyebrow">DRIVER STATEMENTS</p><h2>Payroll by driver</h2></div><span class="record-count">${formatNumber(visibleSummary.length)} drivers</span></div>
      ${driverCards || '<div class="empty-state"><span>₱</span><strong>No payroll results</strong><small>Select a period and generate the report.</small></div>'}
    </section>
    ${report?.audit_history?.length ? `<section class="panel payroll-issues"><div class="panel-heading"><div><p class="eyebrow">AUDIT HISTORY</p><h2>Payroll period activity</h2></div></div>${tableMarkup(report.audit_history.map((entry) => ({
      created_at: entry.created_at,
      action: entry.action,
      actor_id: entry.actor_id,
      details: JSON.stringify(entry.details || {}),
    })), [
      ["created_at", "Date"],
      ["action", "Action"],
      ["actor_id", "User"],
      ["details", "Details"],
    ], null, { empty: "No payroll changes recorded" })}</section>` : ""}
    <section class="panel records-panel trips-report payroll-trip-report">
      <div class="panel-heading"><div><p class="eyebrow">TRIP LINE ITEMS</p><h2>Payroll report detail</h2></div><span class="record-count">${formatNumber(visibleTrips.length)} trips</span></div>
      ${tableMarkup(visibleTrips, tripColumns, null, { empty: "No trips in this payroll period" })}
    </section>`;
}

function render() {
  if (!state.data) return;
  for (const url of Object.values(state.dispatch.previewUrls)) {
    URL.revokeObjectURL(url);
  }
  state.dispatch.previewUrls = {};
  navigation.hidden = false;
  const isDedicatedAddTripPage =
    window.location.pathname === "/dispatcher/add-trip" && !window.location.hash;
  const dispatcherPages = new Set(["dashboard", "trips", "fuel", "maintenance", "tires"]);
  const isDispatcher = state.data.user?.role === "dispatcher";
  if (isDedicatedAddTripPage) {
    state.page = "trips";
  } else {
    state.page = location.hash.slice(1) in TITLES ? location.hash.slice(1) : "dashboard";
  }
  if (state.page !== "trips" && isDispatcher) {
    state.dispatch.tab = "departures";
  }
  if (isDispatcher && !dispatcherPages.has(state.page)) {
    location.hash = "dashboard";
    state.page = "dashboard";
  }
  document.querySelectorAll(".nav-link").forEach((link) => {
    link.hidden = (isDispatcher && link.dataset.page && !dispatcherPages.has(link.dataset.page))
      || (link.dataset.role === "administrator" && isDispatcher);
  });
  document.querySelectorAll(".nav-group").forEach((group) => {
    group.hidden = !group.querySelector(".nav-link:not([hidden])");
  });
  document.title = `${TITLES[state.page]} · Good Luck Forwarding Systems Inc.`;
  const isAddTripRoute =
    window.location.pathname === "/dispatcher/add-trip" && !window.location.hash;
  document.querySelectorAll(".nav-link[data-page]").forEach((link) => {
    const active = link.dataset.dispatchTab
      ? state.page === "trips" && state.dispatch.tab === link.dataset.dispatchTab && !isAddTripRoute
      : link.dataset.navRoute === "add-trip"
      ? isAddTripRoute
      : !link.dataset.navRoute && link.dataset.page === state.page && !isAddTripRoute;
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  document.querySelectorAll("[data-nav-category]").forEach((group) => {
    group.classList.toggle("has-active-page", Boolean(group.querySelector(".nav-link.active")));
  });
  if (isDedicatedAddTripPage && !isDispatcher) {
    const config = RESOURCE_CONFIG.trips;
    const needsReferences = config.fields.some(
      (field) =>
        (field.type === "truck" && !state.data.vehicles.some((item) => ["active", "available", "assigned"].includes(item.status))) ||
        (field.type === "trailer" && !(state.data.trailers || []).some((item) => item.status === "active")) ||
        (field.type === "driver" && !state.data.drivers.length),
    );
    view.innerHTML = tripCreationWizardMarkup(config, needsReferences, true);
  } else {
    view.innerHTML = state.page === "dashboard"
      ? renderDashboard()
      : state.page === "payroll" ? renderPayroll()
        : state.page === "revenue" ? revenueDashboardMarkup(state.revenue.report)
          : renderResource(state.page);
  }
  const dispatchDepartureForm = view.querySelector(".dispatch-departure-form");
  if (dispatchDepartureForm) {
    setDispatchWizardStep(dispatchDepartureForm, state.dispatch.departureWizardStep);
    validateDispatchPalletQuantity(dispatchDepartureForm);
    updateDispatchDepartureAvailability(dispatchDepartureForm);
  }
  if (state.page === "revenue" && !state.revenue.loading
      && state.revenue.reportKey !== revenueQueryKey()) {
    loadRevenueReport();
  }
  if (state.page === "tires" && (
    state.tires.requestedKey !== tireQueryKey()
    || (!state.tires.loading && !state.tires.summary && !state.tires.error)
  )) {
    loadTireMonitoring();
  }
  view.querySelectorAll('form[data-form="trips"]:not(.trip-wizard-form), .trip-edit-form').forEach((form) => {
    refreshTripDestinationOptions(form);
  });
  const wizardForm = tripWizardForm();
  if (wizardForm) {
    if (!wizardForm.elements.namedItem("shipment_date").value) {
      wizardForm.elements.namedItem("shipment_date").value = isoDate(new Date());
    }
    refreshTripDestinationOptions(wizardForm);
    updateTripWizard(wizardForm);
    if (!window.location.pathname.endsWith("/dispatcher/add-trip")) {
      wizardForm.closest(".trip-wizard-dialog").addEventListener("close", () => {
        resetTripWizard(wizardForm);
      });
    }
  }
  if (state.notificationTarget?.module === state.page) {
    const recordRow = [...view.querySelectorAll("[data-record-id]")].find(
      (row) => row.dataset.recordId === String(state.notificationTarget.recordId),
    );
    state.notificationTarget = null;
    if (recordRow) {
      recordRow.classList.add("notification-highlight");
      recordRow.scrollIntoView({ behavior: "smooth", block: "center" });
      window.setTimeout(() => recordRow.classList.remove("notification-highlight"), 4000);
    }
  }
}

function tripFuelRecords(tripId) {
  return (state.data?.fuel_logs || []).filter(
    (record) => String(record.trip_id) === String(tripId),
  );
}

function tripConfiguredFuelAllocation(trip) {
  const routes = state.data?.truck_routes || [];
  const route = routes.find((record) => String(record.id) === String(trip.route_id))
    || routes.find((record) =>
      [record.origin_code, record.origin_name].some(
        (location) => String(location || "").toUpperCase() === String(trip.origin || "").toUpperCase(),
      )
        && [record.destination_code, record.destination_name].some(
          (location) => String(location || "").toUpperCase() === String(trip.destination || "").toUpperCase(),
        ),
    );
  if (route?.fuel_allocation === null || route?.fuel_allocation === undefined) return null;
  const amount = Number(route.fuel_allocation);
  return Number.isFinite(amount) ? amount : null;
}

function fuelRecordStatus(record) {
  const statuses = {
    pending: "Pending",
    submitted: "Submitted",
    verified: "Verified",
    missing: "Missing",
  };
  const status = String(record.status || record.record_status || "").trim().toLowerCase();
  return statuses[status] || "Submitted";
}

function fuelStatusBadge(status) {
  const className = status.toLowerCase().replaceAll(" ", "_");
  return `<span class="badge badge-${escapeHtml(className)}">${escapeHtml(status)}</span>`;
}

function fuelSubmissionDetails(record) {
  const createdAt = record.created_at ? new Date(record.created_at) : null;
  const hasTimestamp = createdAt && !Number.isNaN(createdAt.getTime());
  const date = hasTimestamp
    ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(createdAt)
    : record.logged_on || "Not recorded";
  const time = hasTimestamp
    ? new Intl.DateTimeFormat(undefined, { timeStyle: "short" }).format(createdAt)
    : "Not recorded";
  const currentUser = state.data?.user || {};
  const submitter = record.created_by
    ? (String(record.created_by) === String(currentUser.id)
      ? currentUser.full_name || currentUser.email || "Current dispatcher"
      : `Dispatcher ID ${record.created_by}`)
    : "Not recorded";
  return {
    date,
    dateLabel: hasTimestamp || !record.logged_on ? "Submission date" : "Record date",
    time,
    submitter,
  };
}

function fuelInvoiceMarkup(record, tripTitle) {
  if (!record.invoice_image_url) {
    return `<p class="fuel-invoice-empty">No invoice image uploaded for this record.</p>`;
  }
  const imageUrl = escapeHtml(record.invoice_image_url);
  const recordId = escapeHtml(record.id);
  return `
    <div class="fuel-invoice-media">
      <button class="fuel-invoice-image-button" type="button" data-action="preview-image"
        data-image-title="Fuel invoice"
        data-image-url="${imageUrl}" data-image-alt="Fuel invoice for ${escapeHtml(tripTitle)} (record #${recordId})"
        aria-label="Enlarge fuel invoice for record ${recordId}" disabled>
        <img class="fuel-invoice-thumbnail" src="${imageUrl}" alt="Fuel invoice thumbnail for ${escapeHtml(tripTitle)}"
          loading="lazy" />
      </button>
      <p class="fuel-invoice-image-loading" role="status">Loading invoice image…</p>
      <p class="fuel-invoice-image-error" role="alert" hidden>Invoice image is unavailable.</p>
    </div>`;
}

function updateFuelInvoiceImageState(container) {
  container.querySelectorAll(".fuel-invoice-thumbnail").forEach((image) => {
    const media = image.closest(".fuel-invoice-media");
    const button = media.querySelector(".fuel-invoice-image-button");
    const loading = media.querySelector(".fuel-invoice-image-loading");
    const error = media.querySelector(".fuel-invoice-image-error");
    const markLoaded = () => {
      media.classList.add("is-loaded");
      button.disabled = false;
      loading.hidden = true;
    };
    const markUnavailable = () => {
      media.classList.add("is-error");
      button.disabled = true;
      image.hidden = true;
      loading.hidden = true;
      error.hidden = false;
    };
    image.addEventListener("load", markLoaded, { once: true });
    image.addEventListener("error", markUnavailable, { once: true });
    if (image.complete) {
      if (image.naturalWidth > 0) markLoaded();
      else markUnavailable();
    }
  });
}

function openImagePreview(button) {
  const previewDialog = document.querySelector(".image-preview-dialog");
  const previewImage = previewDialog?.querySelector("img");
  const loading = previewDialog?.querySelector(".fuel-invoice-image-loading");
  const error = previewDialog?.querySelector(".fuel-invoice-image-error");
  if (!previewDialog || !previewImage || !loading || !error) return;

  previewDialog.querySelector("#image-preview-title").textContent =
    `${button.dataset.imageTitle || "Image"} preview`;
  previewImage.hidden = true;
  loading.hidden = false;
  error.hidden = true;
  previewImage.alt = button.dataset.imageAlt || button.dataset.imageTitle || "Image preview";
  previewImage.onload = () => {
    previewImage.hidden = false;
    loading.hidden = true;
  };
  previewImage.onerror = () => {
    previewImage.hidden = true;
    loading.hidden = true;
    error.hidden = false;
  };
  previewImage.src = button.dataset.imageUrl;
  if (previewImage.complete) {
    if (previewImage.naturalWidth > 0) {
      previewImage.hidden = false;
      loading.hidden = true;
    } else {
      loading.hidden = true;
      error.hidden = false;
    }
  }
  if (!previewDialog.open) previewDialog.showModal();
}

function tripFuelDetailsMarkup(trip, tripTitle) {
  const records = tripFuelRecords(trip.id);
  const savedAllocations = records
    .map((record) => record.fuel_allocation)
    .filter((amount) => amount !== null && amount !== undefined && Number.isFinite(Number(amount)))
    .map(Number);
  const configuredAllocation = tripConfiguredFuelAllocation(trip);
  const allocationTotal = savedAllocations.length
    ? savedAllocations.reduce((total, amount) => total + amount, 0)
    : configuredAllocation;
  const allocationSource = savedAllocations.length
    ? "Saved fuel record allocation"
    : configuredAllocation !== null ? "Configured route allocation" : "Not recorded";
  const costs = records
    .map((record) => record.total_cost ?? record.actual_expense)
    .filter((amount) => amount !== null && amount !== undefined && Number.isFinite(Number(amount)))
    .map(Number);
  const totalCost = costs.length ? costs.reduce((total, amount) => total + amount, 0) : null;
  const invoiceCount = records.filter((record) => record.invoice_image_url).length;
  const statuses = [...new Set(records.map(fuelRecordStatus))];
  const overallStatus = statuses.length === 0
    ? "Missing"
    : statuses.length === 1 ? statuses[0] : "Multiple statuses";
  const recordsMarkup = records.map((record) => {
    const submission = fuelSubmissionDetails(record);
    const status = fuelRecordStatus(record);
    const quantity = record.quantity === null || record.quantity === undefined
      ? ""
      : `<div class="trip-detail-item"><dt>Fuel quantity</dt><dd>${escapeHtml(formatNumber(record.quantity))} L</dd></div>`;
    return `
      <article class="fuel-record-card">
        <div class="fuel-record-heading">
          <h4>Fuel record #${escapeHtml(record.id)}</h4>
          ${fuelStatusBadge(status)}
        </div>
        <dl class="trip-details-grid fuel-record-details">
          <div class="trip-detail-item"><dt>Fuel allocation amount</dt><dd>${record.fuel_allocation == null ? "Not recorded" : escapeHtml(formatCurrency(record.fuel_allocation))}</dd></div>
          <div class="trip-detail-item"><dt>Fuel cost / allocated value</dt><dd>${record.total_cost == null && record.actual_expense == null ? "Not recorded" : escapeHtml(formatCurrency(record.total_cost ?? record.actual_expense))}</dd></div>
          ${quantity}
          <div class="trip-detail-item"><dt>${escapeHtml(submission.dateLabel)}</dt><dd>${escapeHtml(submission.date)}</dd></div>
          <div class="trip-detail-item"><dt>Submission time</dt><dd>${escapeHtml(submission.time)}</dd></div>
          <div class="trip-detail-item"><dt>Submitting dispatcher</dt><dd>${escapeHtml(submission.submitter)}</dd></div>
        </dl>
        <div class="fuel-record-invoice">
          <h5>Fuel invoice / receipt</h5>
          ${fuelInvoiceMarkup(record, tripTitle)}
        </div>
      </article>`;
  }).join("");

  return `
    <section class="fuel-allocation-section" aria-labelledby="fuel-allocation-title">
      <div class="fuel-allocation-heading">
        <div><p class="eyebrow">TRIP FUEL</p><h3 id="fuel-allocation-title">Fuel Allocation Details</h3></div>
        ${fuelStatusBadge(overallStatus)}
      </div>
      <dl class="fuel-allocation-summary">
        <div class="trip-detail-item">
          <dt>Total Fuel Allocation</dt>
          <dd>${allocationTotal === null ? "Not configured" : escapeHtml(formatCurrency(allocationTotal))}</dd>
          <small>${escapeHtml(allocationSource)}</small>
        </div>
        <div class="trip-detail-item">
          <dt>Total Fuel Cost / Allocated Value</dt>
          <dd>${totalCost === null ? "Not recorded" : escapeHtml(formatCurrency(totalCost))}</dd>
        </div>
        <div class="trip-detail-item"><dt>Number of Fuel Records</dt><dd>${formatNumber(records.length)}</dd></div>
        <div class="trip-detail-item"><dt>Invoice Image Preview</dt><dd>${formatNumber(invoiceCount)} ${invoiceCount === 1 ? "image" : "images"}</dd></div>
      </dl>
      ${records.length
        ? `<div class="fuel-record-list">${recordsMarkup}</div>`
        : `<p class="fuel-record-empty">No fuel record submitted for this trip.</p>`}
    </section>`;
}

function openTripDetails(tripId) {
  const trip = state.data?.trips.find((record) => String(record.id) === String(tripId));
  const dialog = view.querySelector(".trip-details-dialog");
  if (!trip || !dialog) return;

  const trailer = (state.data.trailers || []).find(
    (record) => String(record.id) === String(trip.trailer_id),
  );
  const trailerLabel = trip.trailer_plate_number
    || trailer?.plate_number
    || (trip.trailer_id ? `Trailer #${trip.trailer_id}` : "Not assigned");
  const title = trip.ism_no ? `Trip ${trip.ism_no}` : `Trip #${trip.id}`;
  dialog.querySelector("#trip-details-title").textContent = title;
  state.editingTrip = trip;
  const detailFields = [
    ["Shipment date", trip.shipment_date],
    ["Time in", trip.time_in],
    ["Time out", trip.time_out],
    ["Origin", trip.origin],
    ["Destination", trip.destination],
    ["Truck", [trip.truck_plate_number || trip.plate_number, trip.make, trip.model].filter(Boolean).join(" · ")],
    ["Trailer", trailerLabel],
    ["Driver", trip.driver_name],
    ["Route No.", trip.route_number],
    ["Route Pair", trip.route_pair],
    ["Pallet Capacity", trip.pallet_capacity ? `${trip.pallet_capacity} pallets` : "Unknown"],
    ["Truck Hauling Rate", trip.truck_route_rate == null ? "Rate not configured" : formatCurrency(trip.truck_route_rate)],
    ["Rate review", trip.trip_rate_review_required ? "Required" : "Not required"],
    ["Load", trip.load_details],
    ["Trip/Fuel", trip.trip_fuel],
    ["Route", trip.route],
    ["Notes", trip.notes],
  ];
  const detailsMarkup = detailFields
    .filter(([, value]) => value !== null && value !== undefined && String(value).trim())
    .map(([label, value]) => `
      <div class="trip-detail-item">
        <dt>${escapeHtml(label)}</dt>
        <dd>${escapeHtml(value)}</dd>
      </div>`)
    .join("");
  const departureIsSet = Boolean(trip.time_out);
  const arrivalIsSet = Boolean(trip.time_in);
  const tripTimeControlsMarkup = `
    <div class="trip-detail-actions trip-time-actions">
      <button class="button button-secondary" data-action="record-trip-time-out" type="button" ${departureIsSet ? "disabled" : ""}>
        ${departureIsSet ? "Departure recorded" : "Record departure"}
      </button>
      <button class="button button-secondary" data-action="record-trip-time-in" type="button" ${arrivalIsSet ? "disabled" : ""}>
        ${arrivalIsSet ? "Arrival recorded" : "Record arrival"}
      </button>
    </div>
    <form class="trip-time-record-form" data-trip-id="${escapeHtml(trip.id)}" data-time-kind="out" hidden>
      <div class="dialog-fields">
        <label class="form-field">
          <span>Departure time</span>
          <input name="time_value" type="time" required value="${trip.time_out || ""}" />
        </label>
        <label class="form-field">
          <span>Departure location</span>
          <select name="location" required>
            ${(state.data?.warehouses || []).map((warehouse) => `<option value="${escapeHtml(warehouse.name || warehouse.code || warehouse)}" ${warehouse.name === trip.origin || warehouse.code === trip.origin ? "selected" : ""}>${escapeHtml(warehouse.name || warehouse.code || warehouse)}</option>`).join("") || `<option value="${escapeHtml(trip.origin || "")}">${escapeHtml(trip.origin || "Choose origin")}</option>`}
          </select>
        </label>
      </div>
      <p class="dialog-error" role="alert" hidden></p>
      <div class="dialog-actions">
        <button class="button button-secondary" data-action="cancel-trip-time-record" type="button">Cancel</button>
        <button class="button button-primary" type="submit">Save departure</button>
      </div>
    </form>
    <form class="trip-time-record-form" data-trip-id="${escapeHtml(trip.id)}" data-time-kind="in" hidden>
      <div class="dialog-fields">
        <label class="form-field">
          <span>Arrival time</span>
          <input name="time_value" type="time" required value="${trip.time_in || ""}" />
        </label>
        <label class="form-field">
          <span>Arrival location</span>
          <select name="location" required>
            ${(state.data?.warehouses || []).map((warehouse) => `<option value="${escapeHtml(warehouse.name || warehouse.code || warehouse)}" ${warehouse.name === trip.destination || warehouse.code === trip.destination ? "selected" : ""}>${escapeHtml(warehouse.name || warehouse.code || warehouse)}</option>`).join("") || `<option value="${escapeHtml(trip.destination || "")}">${escapeHtml(trip.destination || "Choose destination")}</option>`}
          </select>
        </label>
      </div>
      <p class="dialog-error" role="alert" hidden></p>
      <div class="dialog-actions">
        <button class="button button-secondary" data-action="cancel-trip-time-record" type="button">Cancel</button>
        <button class="button button-primary" type="submit">Save arrival</button>
      </div>
    </form>`;
  const imageMarkup = trip.manifest_image_url
    ? `<section class="trip-manifest-preview">
        <h3>Load manifest</h3>
        <button class="image-preview-button" type="button" data-action="preview-image"
          data-image-url="${escapeHtml(trip.manifest_image_url)}" data-image-title="Load manifest"
          data-image-alt="Load manifest for ${escapeHtml(title)}">
          <img src="${escapeHtml(trip.manifest_image_url)}" alt="Load manifest for ${escapeHtml(title)}" />
        </button>
      </section>`
    : `<section class="trip-manifest-preview"><h3>Load manifest</h3><p>No manifest image uploaded yet.</p></section>`;
  const editFields = RESOURCE_CONFIG.trips.fields
    .filter((field) => field.type !== "file")
    .map((field) => ["truck_id", "trailer_id", "driver_id"].includes(field.name)
      ? { ...field, required: false }
      : field);
  dialog.querySelector(".trip-details-content").innerHTML = `
    <dl class="trip-details-grid">${detailsMarkup || "<p>No trip details available.</p>"}</dl>
    ${tripTimeControlsMarkup}
    <div class="trip-detail-actions">
      <button class="button button-secondary" data-action="edit-trip" type="button">Edit trip details</button>
    </div>
    <form class="trip-edit-form" data-trip-id="${escapeHtml(trip.id)}" hidden>
      <div class="dialog-fields">${editFields.map((field) => fieldMarkup(field, "trip-edit-field")).join("")}</div>
      <section class="trip-route-summary" aria-live="polite" aria-label="Resolved route information"></section>
      <p class="dialog-error" role="alert" hidden></p>
      <div class="dialog-actions">
        <button class="button button-secondary" data-action="cancel-trip-edit" type="button">Cancel</button>
        <button class="button button-primary" type="submit">Save changes</button>
      </div>
    </form>
    ${tripFuelDetailsMarkup(trip, title)}
    ${imageMarkup}
    <form class="trip-manifest-upload" data-trip-id="${escapeHtml(trip.id)}">
      <label class="form-field">
        <span>${trip.manifest_image_url ? "Replace load manifest image" : "Upload load manifest image"}</span>
        <input name="image" type="file" accept="image/jpeg,image/png,image/webp" required />
        <small class="field-hint">JPG, PNG, or WEBP image, up to 10 MB.</small>
      </label>
      <p class="dialog-error" role="alert" hidden></p>
      <button class="button button-secondary" type="submit">${trip.manifest_image_url ? "Replace image" : "Upload image"}</button>
    </form>
    <section class="trip-edit-history">
      <h3>Edit history</h3>
      <div class="trip-history-content" aria-live="polite"><p>Loading edit history…</p></div>
    </section>`;
  updateFuelInvoiceImageState(dialog.querySelector(".trip-details-content"));
  const editForm = dialog.querySelector(".trip-edit-form");
  editForm.dataset.originalOrigin = String(trip.origin || "");
  editForm.dataset.originalDestination = String(trip.destination || "");
  editForm.dataset.originalTruckId = String(trip.truck_id || trip.vehicle_id || "");
  editForm.dataset.originalTrailerId = String(trip.trailer_id || "");
  editForm.dataset.savedRouteNumber = String(trip.route_number ?? "");
  editForm.dataset.savedRoutePair = String(trip.route_pair || "");
  editForm.dataset.savedPalletCapacity = String(trip.pallet_capacity ?? "");
  editForm.dataset.savedTruckRate = trip.truck_route_rate == null ? "" : String(trip.truck_route_rate);
  const originControl = editForm.elements.namedItem("origin");
  if (trip.origin && ![...originControl.options].some((option) => option.value === trip.origin)) {
    originControl.insertAdjacentHTML(
      "beforeend",
      `<option value="${escapeHtml(trip.origin)}">${escapeHtml(trip.origin)} (saved, route not configured)</option>`,
    );
  }
  const destinationControl = editForm.elements.namedItem("destination");
  if (trip.destination && ![...destinationControl.options].some((option) => option.value === trip.destination)) {
    destinationControl.insertAdjacentHTML(
      "beforeend",
      `<option value="${escapeHtml(trip.destination)}">${escapeHtml(trip.destination)} (saved, route not configured)</option>`,
    );
  }
  for (const field of editFields) {
    const control = editForm.elements.namedItem(field.name);
    if (!control) continue;
    const value = field.name === "truck_id" ? trip.truck_id || trip.vehicle_id : trip[field.name];
    control.value = field.type === "time" && value ? String(value).slice(0, 5) : value ?? "";
  }
  refreshTripDestinationOptions(editForm);
  loadTripEditHistory(tripId, dialog.querySelector(".trip-history-content"));
  if (!dialog.open) dialog.showModal();
}

async function updateTripRecord(form) {
  if (!form.reportValidity()) return;
  const tripId = form.dataset.tripId;
  const payload = Object.fromEntries(new FormData(form).entries());
  for (const field of RESOURCE_CONFIG.trips.fields) {
    if (field.type === "file") continue;
    if (["vehicle", "truck", "trailer", "driver"].includes(field.type) && payload[field.name] === "") {
      payload[field.name] = null;
    } else if (field.type === "number" || ["vehicle", "truck", "trailer", "driver"].includes(field.type)) {
      payload[field.name] = Number(payload[field.name]);
    } else if (payload[field.name] === "") {
      payload[field.name] = null;
    }
  }
  const submit = form.querySelector('button[type="submit"]');
  const errorMessage = form.querySelector(".dialog-error");
  submit.disabled = true;
  errorMessage.hidden = true;
  try {
    const result = await api(`/api/trips/${encodeURIComponent(tripId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    const record = result?.data || { ...state.data.trips.find((item) => String(item.id) === String(tripId)), ...payload, id: tripId };
    upsertResourceRecord("trips", record);
    showToast("Trip details updated.");
    render();
    openTripDetails(tripId);
  } catch (error) {
    errorMessage.textContent = error.message || "Could not update this trip.";
    errorMessage.hidden = false;
    submit.disabled = false;
  }
}

async function recordTripTime(form, endpoint) {
  if (!form || !form.reportValidity()) return;
  const tripId = form.dataset.tripId;
  const timeValue = form.elements.time_value?.value || "";
  const locationValue = form.elements.location?.value || "";
  const button = form.querySelector('button[type="submit"]');
  const errorMessage = form.querySelector(".dialog-error");
  button.disabled = true;
  errorMessage.hidden = true;
  try {
    const result = await api(`/api/trips/${encodeURIComponent(tripId)}${endpoint}`, {
      method: "POST",
      body: JSON.stringify({
        time_value: timeValue,
        location: locationValue,
      }),
    });
    const record = result?.data || { ...state.data.trips.find((item) => String(item.id) === String(tripId)), id: tripId };
    upsertResourceRecord("trips", record);
    showToast(endpoint.includes("time-out") ? "Departure recorded." : "Arrival recorded.");
    render();
    openTripDetails(tripId);
  } catch (error) {
    errorMessage.textContent = error.message || "Could not record this trip time.";
    errorMessage.hidden = false;
    button.disabled = false;
  }
}

async function uploadTripManifest(form) {
  if (!form.reportValidity()) return;
  const tripId = form.dataset.tripId;
  const image = form.elements.image.files[0];
  const button = form.querySelector('button[type="submit"]');
  const errorMessage = form.querySelector(".dialog-error");
  const body = new FormData();
  body.append("image", image);
  button.disabled = true;
  errorMessage.hidden = true;
  try {
    await api(`/api/trips/${encodeURIComponent(tripId)}/manifest`, {
      method: "POST",
      body,
    });
    const trip = state.data.trips.find((record) => String(record.id) === String(tripId));
    if (trip) trip.manifest_image_url = `/api/trips/${encodeURIComponent(tripId)}/manifest`;
    openTripDetails(tripId);
    showToast("Load manifest image uploaded.");
  } catch (error) {
    errorMessage.textContent = error.message || "Could not upload the manifest image.";
    errorMessage.hidden = false;
    button.disabled = false;
  }
}

async function submitTripWizard(form) {
  if (state.tripWizard.submitting) return;
  for (let step = 0; step < TRIP_WIZARD_STEPS.length - 1; step += 1) {
    if (!tripWizardStepValid(form, step)) {
      state.tripWizard.step = step;
      updateTripWizard(form);
      form.querySelector(`.trip-wizard-step[data-step="${step}"]`)?.scrollIntoView({ block: "start" });
      return;
    }
  }
  const saveButton = form.querySelector(".trip-wizard-submit");
  const saveError = form.querySelector(".trip-wizard-save-error");
  const dialog = form.closest(".trip-wizard-dialog");
  saveError.hidden = true;
  saveError.textContent = "";
  state.tripWizard.submitting = true;
  saveButton.disabled = true;
  saveButton.textContent = state.tripWizard.createdTripId ? "Retrying uploads…" : "Saving trip…";
  if (dialog) dialog.setAttribute("aria-busy", "true");
  try {
    let tripId = state.tripWizard.createdTripId;
    if (!tripId) {
      const formData = new FormData(form);
      const payload = Object.fromEntries(formData.entries());
      const manifestImage = formData.get("manifest_image");
      const invoiceImage = formData.get("invoice_image");
      delete payload.manifest_image;
      delete payload.invoice_image;
      const loadType = String(payload.load_type || "").trim();
      delete payload.load_type;
      if (loadType) {
        const loadDetails = String(payload.load_details || "").trim();
        payload.load_details = loadDetails ? `${loadType} — ${loadDetails}` : loadType;
      }
      for (const name of ["driver_id", "truck_id", "trailer_id"]) {
        payload[name] = Number(payload[name]);
      }
      for (const name of ["fuel_allocation", "actual_fuel_expense"]) {
        payload[name] = payload[name] === "" ? null : Number(payload[name]);
      }
      for (const name of ["ism_no", "shipment_date", "origin", "destination", "load_details", "trip_fuel", "notes", "fuel_remarks"]) {
        if (payload[name] === "") payload[name] = null;
      }
      const result = await api("/api/trips", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (!result?.data?.id) throw new Error("Trip was saved without a trip ID. Refresh the trip list before retrying.");
      tripId = result.data.id;
      state.tripWizard.createdTripId = tripId;
      upsertResourceRecord("trips", result.data);
      if (result.data.fuel_log) upsertResourceRecord("fuel", result.data.fuel_log);
      state.tripWizard.manifestUploaded = !manifestImage || manifestImage.size === 0;
      state.tripWizard.invoiceUploaded = !invoiceImage || invoiceImage.size === 0;
      lockTripWizardForm(form);
    }

    const uploads = [
      {
        field: "manifest_image",
        uploaded: "manifestUploaded",
        endpoint: `/api/trips/${encodeURIComponent(tripId)}/manifest`,
        imageField: "manifest_image_url",
      },
      {
        field: "invoice_image",
        uploaded: "invoiceUploaded",
        endpoint: `/api/trips/${encodeURIComponent(tripId)}/fuel-invoice`,
        imageField: "fuel_invoice_image_url",
      },
    ];
    for (const upload of uploads) {
      const image = form.elements.namedItem(upload.field).files?.[0];
      if (!image || image.size === 0 || state.tripWizard[upload.uploaded]) continue;
      const body = new FormData();
      body.append("image", image);
      await api(upload.endpoint, { method: "POST", body });
      state.tripWizard[upload.uploaded] = true;
      lockTripWizardForm(form);
      const trip = state.data.trips.find((record) => String(record.id) === String(tripId));
      if (trip) trip[upload.imageField] = upload.endpoint;
    }

    try {
      const refreshed = await api("/api/bootstrap");
      state.data = refreshed;
      state.csrfToken = refreshed.csrf_token || state.csrfToken;
    } catch (refreshError) {
      showToast(`Trip saved, but the trip list could not be refreshed: ${refreshError.message}`, "error");
    }
    const dialog = form.closest(".trip-wizard-dialog");
    if (dialog && typeof dialog.close === "function") dialog.close();
    render();
    if (window.location.pathname === "/dispatcher/add-trip") {
      window.location.href = "/#trips";
      return;
    }
    showToast("Trip saved successfully.");
  } catch (error) {
    saveError.textContent = state.tripWizard.createdTripId
      ? `Trip #${state.tripWizard.createdTripId} was saved, but an upload did not finish. Your entries are retained; confirm again to retry the remaining upload. ${error.message}`
      : error.message || "Could not save this trip.";
    saveError.hidden = false;
  } finally {
    state.tripWizard.submitting = false;
    const dialog = form.closest(".trip-wizard-dialog");
    if (dialog) dialog.removeAttribute("aria-busy");
    if (saveButton.isConnected) {
      saveButton.disabled = false;
      saveButton.textContent = "Confirm and Save Trip";
    }
  }
}

async function submitForm(form) {
  const page = form.dataset.form;
  const config = RESOURCE_CONFIG[page];
  const formData = new FormData(form);
  const manifestImage = formData.get("manifest_image");
  const invoiceImage = formData.get("invoice_image");
  const payload = Object.fromEntries(formData.entries());
  delete payload.manifest_image;
  delete payload.invoice_image;
  for (const field of config.fields) {
    if (field.type === "number" && payload[field.name] !== "") {
      payload[field.name] = Number(payload[field.name]);
    } else if (["vehicle", "truck", "trailer", "driver"].includes(field.type)) {
      payload[field.name] = Number(payload[field.name]);
    } else if (payload[field.name] === "") {
      payload[field.name] = null;
    }
  }
  const submit = form.querySelector('button[type="submit"]');
  submit.disabled = true;
  try {
    const result = await api(`/api/${config.api}`, { method: "POST", body: JSON.stringify(payload) });
    const image = page === "trips" ? manifestImage : page === "fuel" ? invoiceImage : null;
    if (result?.data) {
      upsertResourceRecord(page, result.data);
    }
    if (image instanceof File && image.size > 0) {
      const uploadBody = new FormData();
      uploadBody.append("image", image);
      const imageEndpoint = page === "trips"
        ? `/api/trips/${encodeURIComponent(result.data.id)}/manifest`
        : `/api/fuel/${encodeURIComponent(result.data.id)}/invoice`;
      try {
        await api(imageEndpoint, { method: "POST", body: uploadBody });
        const imageField = page === "trips" ? "manifest_image_url" : "invoice_image_url";
        upsertResourceRecord(page, { ...result.data, [imageField]: imageEndpoint });
      } catch (error) {
        showToast(`${capitalize(config.singular)} saved, but its image was not uploaded: ${error.message}`, "error");
        state.search = "";
        render();
        return;
      }
      const revenueRoutes = event.target.closest('form[data-revenue-form="routes"]');
      if (revenueRoutes && event.target.name !== "route_search") {
        state.revenue.route_sort_by = revenueRoutes.elements.namedItem("route_sort_by").value;
        state.revenue.route_sort_dir = revenueRoutes.elements.namedItem("route_sort_dir").value;
        render();
        return;
      }
    }
    showToast(`${capitalize(config.singular)} saved successfully.`);
    state.search = "";
    const dialog = form.closest("dialog");
    if (dialog?.open) dialog.close();
    render();
  } catch (error) {
    const errorMessage = form.querySelector(".dialog-error");
    if (errorMessage) {
      errorMessage.textContent = error.message;
      errorMessage.hidden = false;
    } else {
      showToast(error.message, "error");
    }
  } finally {
    if (submit.isConnected) submit.disabled = false;
  }
}

function capitalize(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

async function deleteRecord(button) {
  const config = Object.values(RESOURCE_CONFIG).find((item) => item.api === button.dataset.resource);
  const confirmation = config?.api === "trips"
    ? "Delete this trip? This cannot be undone. Trips referenced by payroll or completed dispatch history cannot be deleted."
    : `Delete this ${config?.singular}? Related history may also be removed.`;
  if (!config || !window.confirm(confirmation)) return;
  button.disabled = true;
  try {
    await api(`/api/${config.api}/${encodeURIComponent(button.dataset.id)}`, { method: "DELETE" });
    removeResourceRecord(config.api, button.dataset.id);
    showToast(`${capitalize(config.singular)} deleted.`);
    render();
  } catch (error) {
    showToast(error.message, "error");
    button.disabled = false;
  }
}

async function deleteSelectedTrips(button) {
  const selectedIds = [...state.selectedTripIds];
  if (!selectedIds.length || state.bulkDeletingTrips) return;
  const count = selectedIds.length;
  if (!window.confirm(
    `Delete ${count} selected ${count === 1 ? "trip" : "trips"}? This cannot be undone. Trips referenced by payroll or completed dispatch history cannot be deleted.`,
  )) return;

  state.bulkDeletingTrips = true;
  button.disabled = true;
  const failures = [];
  let deletedCount = 0;
  for (const tripId of selectedIds) {
    try {
      await api(`/api/trips/${encodeURIComponent(tripId)}`, { method: "DELETE" });
      removeResourceRecord("trips", tripId);
      state.selectedTripIds.delete(tripId);
      deletedCount += 1;
    } catch (error) {
      failures.push({ tripId, message: error.message });
    }
  }
  state.bulkDeletingTrips = false;
  render();
  if (failures.length) {
    const failureDetails = failures
      .map(({ tripId, message }) => `#${tripId}: ${message}`)
      .join("; ");
    showToast(
      `Deleted ${deletedCount} of ${count} trips. Could not delete ${failureDetails}`,
      "error",
    );
  } else {
    showToast(`${deletedCount} ${deletedCount === 1 ? "trip" : "trips"} deleted.`);
  }
}

async function submitPayrollForm(form) {
  const values = Object.fromEntries(new FormData(form).entries());
  const submit = form.querySelector('button[type="submit"]');
  submit.disabled = true;
  try {
    if (form.id === "payroll-period-form") {
      if (values.start_date > values.end_date) {
        throw new Error("Period start must be on or before period end.");
      }
      state.payrollPeriod = { start_date: values.start_date, end_date: values.end_date };
      state.payroll = null;
      state.payrollKey = "";
      state.payrollRequestedKey = "";
      render();
      return;
    }
    if (form.id === "cash-advance-form") {
      values.driver_id = Number(values.driver_id);
      values.amount = Number(values.amount);
      values.start_date = state.payrollPeriod.start_date;
      values.end_date = state.payrollPeriod.end_date;
      await api("/api/payroll/cash-advances", { method: "POST", body: JSON.stringify(values) });
      showToast("Cash advance recorded.");
    } else if (form.id === "overdraft-form") {
      values.driver_id = Number(values.driver_id);
      values.amount = Number(values.amount);
      await api("/api/payroll/overdrafts", { method: "POST", body: JSON.stringify(values) });
      showToast("Overdraft transaction recorded.");
    }
    await reloadPayroll();
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    if (submit.isConnected) submit.disabled = false;
  }
}

async function reloadPayroll() {
  const { start_date: startDate, end_date: endDate } = state.payrollPeriod;
  state.payroll = await api(
    `/api/payroll?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`,
  );
  state.payrollKey = `${startDate}:${endDate}`;
  state.payrollRequestedKey = state.payrollKey;
  if (state.page === "payroll") render();
}

async function submitRevenueManagementForm(form) {
  if (!form.reportValidity()) return;
  const action = form.dataset.revenueForm;
  const tripId = form.dataset.tripId;
  const values = Object.fromEntries(new FormData(form).entries());
  const submit = form.querySelector('button[type="submit"]');
  submit.disabled = true;
  try {
    if (action === "status") {
      const result = await api(`/api/revenue/trips/${encodeURIComponent(tripId)}/status`, {
        method: "POST",
        body: JSON.stringify(values),
      });
      const saved = state.data.trips.find((trip) => String(trip.id) === String(tripId));
      if (saved && result.trip) Object.assign(saved, result.trip);
      showToast("Trip revenue status saved and audit-logged.");
    } else if (action === "adjustment") {
      form.dataset.idempotencyKey ||= crypto.randomUUID();
      await api(`/api/revenue/trips/${encodeURIComponent(tripId)}/adjustments`, {
        method: "POST",
        body: JSON.stringify({
          amount: values.amount,
          reason: values.reason,
          idempotency_key: form.dataset.idempotencyKey,
        }),
      });
      form.dataset.idempotencyKey = "";
      form.reset();
      showToast("Audited revenue adjustment recorded.");
    } else {
      throw new Error("Unknown revenue management action.");
    }
    state.revenue.reportKey = "";
    state.revenue.report = null;
    state.revenue.page = 1;
    await loadRevenueReport();
  } catch (error) {
    showToast(error.message || "Could not save the revenue change.", "error");
    if (submit.isConnected) submit.disabled = false;
  }
}

async function payrollWorkflowAction(action) {
  const { start_date: startDate, end_date: endDate } = state.payrollPeriod;
  const button = view.querySelector(`[data-action="${action}"]`);
  if (button) button.disabled = true;
  try {
    if (action === "payroll-review") {
      state.payroll = await api("/api/payroll/review", {
        method: "POST",
        body: JSON.stringify({ start_date: startDate, end_date: endDate }),
      });
      showToast("Payroll reviewed. Verify the details before finalizing.");
    } else if (action === "payroll-finalize") {
      const settleOverdraft = Boolean(view.querySelector("#settle-overdraft")?.checked);
      if (!window.confirm("Finalize and lock this payroll period?")) {
        if (button?.isConnected) button.disabled = false;
        return;
      }
      state.payroll = await api("/api/payroll/finalize", {
        method: "POST",
        body: JSON.stringify({
          start_date: startDate,
          end_date: endDate,
          settle_overdraft: settleOverdraft,
        }),
      });
      showToast("Payroll finalized and locked.");
    }
    state.payrollKey = `${startDate}:${endDate}`;
    state.payrollRequestedKey = state.payrollKey;
    render();
  } catch (error) {
    showToast(error.message, "error");
    if (button?.isConnected) button.disabled = false;
  }
}

async function exportPayrollReport() {
  const button = view.querySelector('[data-action="payroll-export"]');
  if (button) button.disabled = true;
  try {
    const params = new URLSearchParams({
      start_date: state.payrollPeriod.start_date,
      end_date: state.payrollPeriod.end_date,
    });
    for (const [key, value] of Object.entries(state.payrollFilters)) {
      if (value.trim()) params.set(key, value.trim());
    }
    const response = await fetch(`/api/payroll/export?${params}`, { cache: "no-store" });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      if (response.status === 401) {
        returnToSignIn(payload.error?.toLowerCase().includes("inactivity"));
      }
      if (response.status === 404) {
        throw new Error(
          "The payroll Excel export endpoint is unavailable. Restart the Flask server or redeploy the latest app, then refresh this page.",
        );
      }
      throw new Error(payload.error || `Payroll export failed (${response.status}).`);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `payroll-${state.payrollPeriod.start_date}-to-${state.payrollPeriod.end_date}.xlsx`;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) {
    showToast(error.message || "Could not export the payroll report.", "error");
  } finally {
    if (button?.isConnected) button.disabled = false;
  }
}

async function exportTripHistory() {
  const button = view.querySelector('[data-action="trip-export"]');
  button.disabled = true;
  try {
    const params = new URLSearchParams();
    if (state.tripsGroupBy) params.set("group_by", state.tripsGroupBy);
    if (state.search.trim()) params.set("search", state.search.trim());
    const query = params.toString();
    const response = await fetch(`/api/export/trips${query ? `?${query}` : ""}`, { cache: "no-store" });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      if (response.status === 401) {
        returnToSignIn(payload.error?.toLowerCase().includes("inactivity"));
      }
      throw new Error(payload.error || `Trip export failed (${response.status}).`);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `trip_history${state.tripsGroupBy ? `-by-${state.tripsGroupBy.replace("_name", "")}` : ""}.xlsx`;
    anchor.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    showToast(error.message || "Could not export trip history.", "error");
  } finally {
    if (button.isConnected) button.disabled = false;
  }
}

view.addEventListener("submit", (event) => {
  const dispatchDeparture = event.target.closest(".dispatch-departure-form");
  if (dispatchDeparture) {
    event.preventDefault();
    if (dispatchDeparture.dataset.movementId) {
      submitDispatchDeparture(dispatchDeparture);
      return;
    }
    for (let step = 0; step < 6; step += 1) {
      if (validateDispatchWizardStep(dispatchDeparture, step)) continue;
      setDispatchWizardStep(dispatchDeparture, step, { focus: true });
      return;
    }
    setDispatchWizardStep(dispatchDeparture, 6);
    submitDispatchDeparture(dispatchDeparture);
    return;
  }
  const dispatchVerify = event.target.closest(".dispatch-verify-form");
  if (dispatchVerify) {
    event.preventDefault();
    if (dispatchVerify.reportValidity()) submitDispatchVerification(dispatchVerify);
    return;
  }
  const dispatchArrival = event.target.closest(".dispatch-arrival-form");
  if (dispatchArrival) {
    event.preventDefault();
    if (dispatchArrival.reportValidity()) submitDispatchArrival(dispatchArrival);
    return;
  }
  const dispatchAssignment = event.target.closest(".dispatch-assignment-form");
  if (dispatchAssignment) {
    event.preventDefault();
    if (dispatchAssignment.reportValidity()) submitDispatchAssignment(dispatchAssignment);
    return;
  }
  const dispatchLocation = event.target.closest(".dispatch-location-form");
  if (dispatchLocation) {
    event.preventDefault();
    if (dispatchLocation.reportValidity()) submitDispatchLocation(dispatchLocation);
    return;
  }
  const dispatchCorrection = event.target.closest(".dispatch-correction-form");
  if (dispatchCorrection) {
    event.preventDefault();
    if (dispatchCorrection.reportValidity()) submitDispatchCorrection(dispatchCorrection);
    return;
  }
  const tireForm = event.target.closest(".tire-record-form");
  if (tireForm) {
    event.preventDefault();
    if (tireForm.reportValidity()) submitTireForm(tireForm);
    return;
  }
  const revenueForm = event.target.closest("form[data-revenue-form]");
  if (revenueForm && ["status", "adjustment"].includes(revenueForm.dataset.revenueForm)) {
    event.preventDefault();
    submitRevenueManagementForm(revenueForm);
    return;
  }
  const tripWizard = event.target.closest(".trip-wizard-form");
  if (tripWizard) {
    event.preventDefault();
    if (state.tripWizard.step === TRIP_WIZARD_STEPS.length - 1) submitTripWizard(tripWizard);
    else tripWizardAdvance(tripWizard);
    return;
  }
  const fleetEditForm = event.target.closest(".fleet-edit-form");
  if (fleetEditForm) {
    event.preventDefault();
    updateFleetAsset(fleetEditForm);
    return;
  }
  const tripEditForm = event.target.closest(".trip-edit-form");
  if (tripEditForm) {
    event.preventDefault();
    updateTripRecord(tripEditForm);
    return;
  }
  const manifestForm = event.target.closest(".trip-manifest-upload");
  if (manifestForm) {
    event.preventDefault();
    uploadTripManifest(manifestForm);
    return;
  }
  const payrollForm = event.target.closest("#payroll-period-form, #cash-advance-form, #overdraft-form");
  if (payrollForm) {
    event.preventDefault();
    if (payrollForm.reportValidity()) submitPayrollForm(payrollForm);
    return;
  }
  const form = event.target.closest(".record-form");
  if (!form) return;
  event.preventDefault();
  if (form.reportValidity()) submitForm(form);
});

view.addEventListener("input", (event) => {
  const dispatchForm = event.target.closest(".dispatch-departure-form");
  if (dispatchForm) {
    const stateFields = {
      ism_no: "departureIsm",
      departure_at: "departureAt",
      fuel_allocation: "departureFuelAllocation",
      actual_fuel_expense: "departureFuelExpense",
      fuel_remarks: "departureFuelRemarks",
      pallet_quantity: "departurePalletQuantity",
    };
    const stateField = stateFields[event.target.name];
    if (stateField) state.dispatch[stateField] = event.target.value;
    if (event.target.name === "pallet_quantity") validateDispatchPalletQuantity(dispatchForm);
    if (event.target.name === "load_catalog_search") {
      const position = event.target.selectionStart;
      state.dispatch.loadCatalogSearch = event.target.value;
      const catalog = dispatchForm.querySelector(".dispatch-product-catalog");
      if (catalog) {
        catalog.innerHTML = dispatchProductCatalogMarkup();
        const searchInput = catalog.querySelector('[name="load_catalog_search"]');
        searchInput?.focus();
        searchInput?.setSelectionRange(position, position);
      }
      return;
    }
    if (state.dispatch.departureWizardStep === 6) {
      dispatchForm.querySelector(".dispatch-wizard-review").innerHTML =
        dispatchWizardReviewMarkup(dispatchForm);
    }
  }
  const wizardForm = event.target.closest(".trip-wizard-form");
  if (wizardForm) {
    state.tripWizard.dirty = true;
    if (state.tripWizard.step === 4) {
      wizardForm.querySelector(".trip-wizard-review").innerHTML =
        tripWizardReviewMarkup(wizardForm);
    }
    return;
  }
  if (event.target.id === "payroll-ism-filter") {
    const position = event.target.selectionStart;
    state.payrollFilters.ism_no = event.target.value;
    render();
    const nextInput = document.querySelector("#payroll-ism-filter");
    nextInput?.focus();
    nextInput?.setSelectionRange(position, position);
    return;
  }
  if (event.target.matches('form[data-revenue-form="ledger"] input[name="search"]')) {
    state.revenue.search = event.target.value.trim();
    state.revenue.page = 1;
    window.clearTimeout(revenueSearchTimer);
    revenueSearchTimer = window.setTimeout(() => {
      state.revenue.reportKey = "";
      loadRevenueReport();
    }, 220);
    return;
  }
  if (event.target.matches('form[data-revenue-form="routes"] input[name="route_search"]')) {
    const position = event.target.selectionStart;
    state.revenue.route_search = event.target.value;
    render();
    const nextInput = view.querySelector('form[data-revenue-form="routes"] input[name="route_search"]');
    nextInput?.focus();
    nextInput?.setSelectionRange(position, position);
    return;
  }
  if (event.target.id === "tire-search") {
    state.tires.search = event.target.value;
    state.tires.page = 1;
    window.clearTimeout(searchRenderTimer);
    searchRenderTimer = window.setTimeout(() => {
      state.tires.requestedKey = "";
      render();
    }, 220);
    return;
  }
  if (event.target.id === "dispatch-search") {
    const position = event.target.selectionStart;
    const restoreFocus = document.activeElement === event.target;
    state.dispatch.search = event.target.value.trim();
    state.dispatch.page = 1;
    window.clearTimeout(searchRenderTimer);
    searchRenderTimer = window.setTimeout(() => {
      state.dispatch.loaded = false;
      loadDispatchWorkflow({ force: true }).then(() => {
        if (!restoreFocus) return;
        const nextInput = document.querySelector("#dispatch-search");
        nextInput?.focus();
        nextInput?.setSelectionRange(position, position);
      });
    }, 140);
    return;
  }
  if (event.target.id !== "record-search") return;
  const position = event.target.selectionStart;
  const restoreFocus = document.activeElement === event.target;
  state.search = event.target.value;
  window.clearTimeout(searchRenderTimer);
  searchRenderTimer = window.setTimeout(() => {
    render();
    if (!restoreFocus) return;
    const nextInput = document.querySelector("#record-search");
    nextInput?.focus();
    nextInput?.setSelectionRange(position, position);
  }, 140);
});

view.addEventListener("click", (event) => {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  if (button.dataset.action === "dispatcher-open-queue") {
    state.dispatch.tab = button.dataset.tab === "departures" ? "departures" : "arrivals";
    state.dispatch.page = 1;
    state.dispatch.loaded = false;
    if (location.hash === "#trips" && state.page === "trips") {
      loadDispatchWorkflow({ force: true });
    } else {
      location.hash = "trips";
    }
    return;
  }
  if (button.dataset.action === "dispatcher-dashboard-retry") {
    loadDispatcherDashboard({ force: true });
    return;
  }
  if (button.dataset.action === "dispatch-tab") {
    state.dispatch.tab = button.dataset.tab;
    state.dispatch.page = 1;
    state.dispatch.loaded = false;
    loadDispatchWorkflow({ force: true });
    return;
  }
  if (button.dataset.action === "dispatch-wizard-continue"
      || button.dataset.action === "dispatch-wizard-back") {
    const form = button.closest(".dispatch-departure-form");
    if (!form) return;
    const currentStep = state.dispatch.departureWizardStep;
    if (button.dataset.action === "dispatch-wizard-back") {
      setDispatchWizardStep(form, currentStep - 1, { focus: true });
      return;
    }
    if (validateDispatchWizardStep(form, currentStep)) {
      setDispatchWizardStep(form, currentStep + 1, { focus: true });
    }
    return;
  }
  if (button.dataset.action === "dispatch-select-load-product"
      || button.dataset.action === "dispatch-adjust-load-product") {
    const form = button.closest(".dispatch-departure-form");
    if (!form) return;
    const productId = Number(button.dataset.productId);
    const existing = state.dispatch.departureLoadItems.find(
      (item) => Number(item.product_id) === productId,
    );
    if (button.dataset.action === "dispatch-select-load-product") {
      if (existing) {
        state.dispatch.departureLoadItems = state.dispatch.departureLoadItems.filter(
          (item) => Number(item.product_id) !== productId,
        );
      } else if (state.dispatch.loadCatalog.some((item) => Number(item.id) === productId)) {
        state.dispatch.departureLoadItems.push({ product_id: productId, pallet_quantity: 1 });
      }
    } else if (existing) {
      const nextQuantity = existing.pallet_quantity + Number(button.dataset.delta || 0);
      if (nextQuantity < 1) {
        state.dispatch.departureLoadItems = state.dispatch.departureLoadItems.filter(
          (item) => Number(item.product_id) !== productId,
        );
      } else {
        existing.pallet_quantity = nextQuantity;
      }
    }
    renderDispatchLoadSelection(form);
    form.querySelector(".dispatch-form-error").hidden = true;
    return;
  }
  if (button.dataset.action === "dispatch-load-section") {
    const form = button.closest(".dispatch-departure-form");
    if (!form) return;
    state.dispatch.loadCatalogSection = button.dataset.section || "";
    const catalog = form.querySelector(".dispatch-product-catalog");
    if (catalog) catalog.innerHTML = dispatchProductCatalogMarkup();
    return;
  }
  if (button.dataset.action === "dispatch-remove-load-item") {
    const form = button.closest(".dispatch-departure-form");
    state.dispatch.departureLoadItems = state.dispatch.departureLoadItems.filter(
      (item) => Number(item.product_id) !== Number(button.dataset.productId),
    );
    if (form) renderDispatchLoadSelection(form);
    return;
  }
  if (button.dataset.action === "dispatch-load-catalog-retry") {
    const form = button.closest(".dispatch-departure-form");
    state.dispatch.loadCatalogLoaded = false;
    state.dispatch.loadCatalogError = "";
    loadDispatchLoadCatalog({ force: true });
    refreshDispatchCatalogStage(form);
    return;
  }
  if (button.dataset.action === "dispatch-page") {
    state.dispatch.page = Number(button.dataset.page) || 1;
    state.dispatch.loaded = false;
    loadDispatchWorkflow({ force: true });
    return;
  }
  if (button.dataset.action === "dispatch-reload") {
    state.dispatch.loaded = false;
    loadDispatchWorkflow({ force: true });
    return;
  }
  if (button.dataset.action === "dispatch-finalize") {
    finalizeDispatchMovement(button);
    return;
  }
  if (button.dataset.action === "dispatch-delete-completed") {
    deleteCompletedDispatchMovement(button);
    return;
  }
  if (button.dataset.action === "dispatch-correction-toggle") {
    const form = button.closest(".dispatch-movement-card")?.querySelector(".dispatch-correction-form");
    if (form) {
      form.hidden = false;
      form.querySelector("textarea")?.focus();
    }
    return;
  }
  if (button.dataset.action === "dispatch-history") {
    loadDispatchHistory(button);
    return;
  }
  if (button.dataset.action === "tire-add") {
    const dialog = tireDialogContent(tireRecordFormMarkup("create"));
    if (dialog) updateTireAssetOptions(dialog.querySelector("#tire-record-form"));
    return;
  }
  if (button.dataset.action === "tire-view") {
    openTireDetails(button.dataset.id);
    return;
  }
  if (button.dataset.action === "tire-edit") {
    openTireEdit(button.dataset.id);
    return;
  }
  if (button.dataset.action === "tire-replace") {
    const row = state.tires.items.find((item) => String(item.id) === String(button.dataset.id));
    if (row) tireDialogContent(tireRecordFormMarkup("replace", row));
    return;
  }
  if (button.dataset.action === "tire-remove") {
    openTireRemove(button.dataset.id);
    return;
  }
  if (button.dataset.action === "tire-export") {
    exportTireMonitoring(button);
    return;
  }
  if (button.dataset.action === "close-tire-dialog") {
    button.closest("dialog")?.close();
    return;
  }
  if (button.dataset.action === "tire-page") {
    state.tires.page = Math.max(1, Number(button.dataset.page) || 1);
    state.tires.requestedKey = "";
    render();
    return;
  }
  if (button.dataset.action === "tire-reset") {
    Object.assign(state.tires, {
      page: 1, search: "", asset_type: "", asset_id: "", status: "",
      date_from: "", date_to: "", lifespan_min: "", lifespan_max: "",
      condition: "", sort_by: "date_installed", sort_dir: "desc",
      requestedKey: "",
    });
    render();
    return;
  }
  if (button.dataset.action === "tire-retry" || button.dataset.action === "refresh") {
    if (state.page === "tires") {
      state.tires.requestedKey = "";
      render();
    } else {
      loadData({ force: true });
    }
    return;
  }
  if (button.dataset.action === "fleet-section") {
    state.vehicleSection = button.dataset.section === "trailers" ? "trailers" : "trucks";
    render();
    return;
  }
  if (button.dataset.action === "edit-fleet-asset") {
    openFleetAssetEditor(button.dataset.assetType, button.dataset.id);
    return;
  }
  if (button.dataset.action === "trailer-details") {
    if (event.target.closest("a, button")) return;
    openFleetAssetDetails(button.dataset.id);
    return;
  }
  if (button.dataset.action === "trip-wizard-go-step") {
    const form = button.closest(".trip-wizard-form");
    const step = Number(button.dataset.step);
    if (form && Number.isInteger(step) && step >= 0 && step < state.tripWizard.step) {
      state.tripWizard.step = step;
      updateTripWizard(form);
      form.querySelector(`.trip-wizard-step[data-step="${step}"] h3`)?.focus();
    }
    return;
  }
  if (button.dataset.action === "trip-wizard-continue") {
    const form = button.closest(".trip-wizard-form");
    if (form) tripWizardAdvance(form);
    return;
  }
  if (button.dataset.action === "trip-wizard-back") {
    const form = button.closest(".trip-wizard-form");
    if (form && state.tripWizard.step > 0) {
      state.tripWizard.step -= 1;
      updateTripWizard(form);
      form.querySelector(`.trip-wizard-step[data-step="${state.tripWizard.step}"] h3`)?.focus();
    }
    return;
  }
  if (button.dataset.action === "trip-wizard-cancel") {
    const form = button.closest(".trip-wizard-form");
    if (form) cancelTripWizard(form);
    return;
  }
  if (button.dataset.action === "trip-wizard-submit") {
    const form = button.closest(".trip-wizard-form");
    if (form) submitTripWizard(form);
    return;
  }
  if (button.dataset.action === "edit-trailer-detail") {
    editTrailerFromDetails();
    return;
  }
  if (button.dataset.action === "delete-trailer-detail") {
    deleteTrailerFromDetails();
    return;
  }
  if (button.dataset.action === "trip-details") {
    if (event.target.closest("a, button, input")) return;
    openTripDetails(button.dataset.id);
    return;
  }
  if (button.dataset.action === "revenue-trip-details") {
    openTripDetails(button.dataset.id);
    return;
  }
  if (button.dataset.action === "revenue-manage-trip") {
    state.revenue.selectedTripId = button.dataset.id;
    render();
    view.querySelector(".revenue-manage-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  if (button.dataset.action === "revenue-close-manage") {
    state.revenue.selectedTripId = "";
    render();
    return;
  }
  if (button.dataset.action === "revenue-page") {
    state.revenue.page = Number(button.dataset.page) || 1;
    state.revenue.reportKey = "";
    loadRevenueReport();
    return;
  }
  if (button.dataset.action === "revenue-retry") {
    state.revenue.reportKey = "";
    state.revenue.error = "";
    loadRevenueReport();
    return;
  }
  if (button.dataset.action === "revenue-reset") {
    Object.assign(state.revenue, revenueRangeForPreset("this_month"), {
      preset: "this_month",
      bucket: "day",
      origin: "",
      destination: "",
      route_number: "",
      driver_id: "",
      truck_id: "",
      trailer_id: "",
      pallet_capacity: "",
      search: "",
      page: 1,
      sort_by: "shipment_date",
      sort_dir: "desc",
      reportKey: "",
    });
    render();
    return;
  }
  if (button.dataset.action === "retry" || button.dataset.action === "refresh") loadData();
  if (button.dataset.action === "payroll-reload") {
    state.payrollRequestedKey = "";
    render();
  }
  if (button.dataset.action === "payroll-review" || button.dataset.action === "payroll-finalize") {
    payrollWorkflowAction(button.dataset.action);
  }
  if (button.dataset.action === "payroll-export") exportPayrollReport();
  if (button.dataset.action === "trip-export") exportTripHistory();
  if (button.dataset.action === "trip-group") {
    state.tripsGroupBy = button.dataset.groupBy || "";
    render();
  }
  if (button.dataset.action === "select-visible-trips") {
    for (const trip of filterRows(state.data.trips, RESOURCE_CONFIG.trips.columns)) {
      state.selectedTripIds.add(String(trip.id));
    }
    render();
  }
  if (button.dataset.action === "clear-trip-selection") {
    state.selectedTripIds.clear();
    render();
  }
  if (button.dataset.action === "bulk-delete-trips") {
    deleteSelectedTrips(button);
  }
  if (button.dataset.action === "new-record") {
    const isTrips = state.page === "trips";
    const dialog = isTrips
      ? view.querySelector(".trip-wizard-dialog")
      : view.querySelector(".record-dialog");
    if (dialog && !dialog.open) {
      if (isTrips) resetTripWizard(dialog.querySelector(".trip-wizard-form"));
      dialog.showModal();
      dialog.querySelector("input, select, textarea")?.focus();
    }
  }
  if (button.dataset.action === "close-record") {
    button.closest("dialog")?.close();
  }
  if (button.dataset.action === "close-trip-details") {
    button.closest("dialog")?.close();
  }
  if (button.dataset.action === "close-fleet-edit") {
    button.closest("dialog")?.close();
  }
  if (button.dataset.action === "close-trailer-details") {
    button.closest("dialog")?.close();
  }
  if (button.dataset.action === "edit-trip") {
    const form = button.closest(".trip-details-content").querySelector(".trip-edit-form");
    form.hidden = false;
    button.hidden = true;
    form.querySelector("input, select, textarea")?.focus();
  }
  if (button.dataset.action === "cancel-trip-edit") {
    const form = button.closest(".trip-edit-form");
    form.hidden = true;
    form.closest(".trip-details-content").querySelector('[data-action="edit-trip"]').hidden = false;
  }
  if (button.dataset.action === "record-trip-time-out") {
    const content = button.closest(".trip-details-content");
    const form = content?.querySelector('.trip-time-record-form[data-time-kind="out"]');
    if (!form) return;
    form.hidden = false;
    form.querySelector("input, select")?.focus();
    return;
  }
  if (button.dataset.action === "record-trip-time-in") {
    const content = button.closest(".trip-details-content");
    const form = content?.querySelector('.trip-time-record-form[data-time-kind="in"]');
    if (!form) return;
    form.hidden = false;
    form.querySelector("input, select")?.focus();
    return;
  }
  if (button.dataset.action === "cancel-trip-time-record") {
    const form = button.closest(".trip-time-record-form");
    if (!form) return;
    form.hidden = true;
    return;
  }
  if (button.dataset.action === "delete") deleteRecord(button);
});

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-action]");
  if (button?.dataset.action === "preview-image") {
    openImagePreview(button);
    return;
  }
  if (button?.dataset.action === "close-image-preview") {
    button.closest("dialog")?.close();
    return;
  }
  const previewDialog = event.target.closest(".image-preview-dialog");
  if (previewDialog && event.target === previewDialog) previewDialog.close();
});

function cancelTripWizard(form) {
  if (state.tripWizard.submitting) return;
  if (state.tripWizard.dirty) {
    const message = state.tripWizard.createdTripId
      ? `Trip #${state.tripWizard.createdTripId} is already saved. Leave this page and discard any remaining image retry?`
      : "Discard the trip information entered so far?";
    if (!window.confirm(message)) return;
  }
  if (window.location.pathname === "/dispatcher/add-trip") {
    window.location.href = "/#trips";
    return;
  }
  const dialog = form.closest(".trip-wizard-dialog");
  if (dialog) dialog.close();
}

view.addEventListener("cancel", (event) => {
  const dialog = event.target;
  if (!dialog.classList?.contains("trip-wizard-dialog")) return;
  if (state.tripWizard.submitting) {
    event.preventDefault();
    return;
  }
  if (state.tripWizard.dirty) {
    event.preventDefault();
    cancelTripWizard(dialog.querySelector(".trip-wizard-form"));
  }
}, true);

view.addEventListener("change", (event) => {
  if (event.target.matches("input[type='file'][data-dispatch-preview]")) {
    const name = event.target.name;
    const prior = state.dispatch.previewUrls[name];
    if (prior) URL.revokeObjectURL(prior);
    const file = event.target.files?.[0];
    const preview = event.target.form?.querySelector(`img[data-dispatch-preview="${name}"]`);
    if (file && preview) {
      const url = URL.createObjectURL(file);
      state.dispatch.previewUrls[name] = url;
      preview.src = url;
      preview.hidden = false;
    } else if (preview) {
      delete state.dispatch.previewUrls[name];
      preview.removeAttribute("src");
      preview.hidden = true;
    }
  }
  if (event.target.matches("#tire-record-asset-type")) {
    updateTireAssetOptions(event.target.form);
  }
  if (event.target.matches("[data-dispatch-origin]")) {
    state.dispatch.departureOrigin = event.target.value;
    state.dispatch.departureDestination = "";
    refreshDispatchDestinations(event.target.form);
  }
  const dispatchForm = event.target.form?.matches(".dispatch-departure-form")
    ? event.target.form
    : null;
  if (dispatchForm) {
    const stateFields = {
      driver_id: "departureDriver",
      truck_id: "departureTruck",
      trailer_id: "departureTrailer",
      destination_location_id: "departureDestination",
      load_type: "departureLoadType",
    };
    const stateField = stateFields[event.target.name];
    if (stateField) state.dispatch[stateField] = event.target.value;
    if (event.target.name === "load_type") {
      const emptySummary = dispatchForm.querySelector(
        '.dispatch-wizard-step[data-step="4"] .dispatch-selected-load',
      );
      if (emptySummary) {
        emptySummary.innerHTML = event.target.value === "EMPTIES"
          ? '<p class="dispatch-load-empty">Product selection is not required for empty-container movements.</p>'
          : dispatchLoadItemsMarkup();
      }
      renderDispatchLoadSelection(dispatchForm);
      dispatchForm.querySelector(".dispatch-form-error").hidden = true;
    }
    if (["trailer_id", "pallet_quantity"].includes(event.target.name)) {
      validateDispatchPalletQuantity(dispatchForm);
    }
    if (event.target.name === "trailer_id") {
      const trailer = (state.data.trailers || []).find(
        (item) => String(item.id) === String(event.target.value),
      );
      dispatchForm.querySelectorAll("[data-dispatch-trailer-capacity]").forEach((element) => {
        element.innerHTML = trailer
          ? `Trailer capacity: <strong>${formatNumber(trailer.pallet_capacity)} pallets</strong>`
          : "Select a trailer to see its pallet capacity.";
      });
    }
    if (state.dispatch.departureWizardStep === 6) {
      dispatchForm.querySelector(".dispatch-wizard-review").innerHTML =
        dispatchWizardReviewMarkup(dispatchForm);
    }
  }
  const form = event.target.closest(".trip-wizard-form");
  if (!form) return;
  state.tripWizard.dirty = true;
  if (event.target.type === "file") {
    event.target.setCustomValidity("");
    const prior = state.tripWizard.objectUrls[event.target.name];
    if (prior) URL.revokeObjectURL(prior);
    const file = event.target.files?.[0];
    const preview = form.querySelector(`[data-image-preview="${event.target.name}"]`);
    if (file && preview) {
      const url = URL.createObjectURL(file);
      state.tripWizard.objectUrls[event.target.name] = url;
      preview.querySelector("img").src = url;
      preview.hidden = false;
    } else if (preview) {
      delete state.tripWizard.objectUrls[event.target.name];
      preview.hidden = true;
    }
    if (state.tripWizard.step === 4) {
      form.querySelector(".trip-wizard-review").innerHTML = tripWizardReviewMarkup(form);
    }
    return;
  }
  if (["origin", "destination", "driver_id", "truck_id", "trailer_id"].includes(event.target.name)) {
    if (event.target.name === "origin") refreshTripDestinationOptions(form);
    updateTripWizard(form);
  }
});

view.addEventListener("keydown", (event) => {
  const trailerRow = event.target.closest('tr[data-action="trailer-details"]');
  if (trailerRow && ["Enter", " "].includes(event.key)) {
    event.preventDefault();
    openFleetAssetDetails(trailerRow.dataset.id);
    return;
  }
  const row = event.target.closest('tr[data-action="trip-details"]');
  if (!row || event.target.matches("input") || !["Enter", " "].includes(event.key)) return;
  event.preventDefault();
  openTripDetails(row.dataset.id);
});

view.addEventListener("change", (event) => {
  const tireFilters = event.target.closest("#tire-filter-form");
  if (tireFilters && event.target.matches("[data-tire-filter]")) {
    const values = Object.fromEntries(new FormData(tireFilters).entries());
    if (event.target.name === "asset_type") values.asset_id = "";
    for (const [key, value] of Object.entries(values)) {
      if (key in state.tires) state.tires[key] = value;
    }
    state.tires.page = 1;
    state.tires.requestedKey = "";
    render();
    return;
  }
  if (event.target.matches("[data-trip-select]")) {
    const tripId = String(event.target.dataset.tripSelect);
    if (event.target.checked) state.selectedTripIds.add(tripId);
    else state.selectedTripIds.delete(tripId);
    render();
    return;
  }
  const wizardForm = event.target.closest(".trip-wizard-form");
  if (wizardForm) return;
  const tripForm = event.target.closest('form[data-form="trips"], .trip-edit-form');
  if (tripForm && ["origin", "destination", "truck_id", "trailer_id"].includes(event.target.name)) {
    if (event.target.name === "origin") refreshTripDestinationOptions(tripForm);
    else refreshTripRouteSummary(tripForm);
    return;
  }
  const revenueFilters = event.target.closest('form[data-revenue-form="filters"]');
  if (revenueFilters) {
    const values = Object.fromEntries(new FormData(revenueFilters).entries());
    const targetName = event.target.name;
    if (targetName === "preset") {
      state.revenue.preset = values.preset;
      if (values.preset !== "custom") Object.assign(state.revenue, revenueRangeForPreset(values.preset));
    } else {
      Object.assign(state.revenue, {
        bucket: values.bucket,
        origin: values.origin,
        destination: values.destination,
        route_number: values.route_number,
        driver_id: values.driver_id,
        truck_id: values.truck_id,
        trailer_id: values.trailer_id,
        pallet_capacity: values.pallet_capacity,
      });
      if (targetName === "start_date" || targetName === "end_date") {
        state.revenue.start_date = values.start_date;
        state.revenue.end_date = values.end_date;
        state.revenue.preset = "custom";
      }
    }
    state.revenue.page = 1;
    state.revenue.reportKey = "";
    render();
    return;
  }
  const revenueLedger = event.target.closest('form[data-revenue-form="ledger"]');
  if (revenueLedger && event.target.name !== "search") {
    state.revenue.sort_by = revenueLedger.elements.namedItem("sort_by").value;
    state.revenue.sort_dir = revenueLedger.elements.namedItem("sort_dir").value;
    state.revenue.page = 1;
    state.revenue.reportKey = "";
    render();
    return;
  }
  const filterMap = {
    "payroll-driver-filter": "driver_id",
    "payroll-origin-filter": "origin",
    "payroll-destination-filter": "destination",
  };
  const key = filterMap[event.target.id];
  if (!key) return;
  state.payrollFilters[key] = event.target.value;
  render();
});

document.querySelectorAll(".nav-link").forEach((link) => {
  link.addEventListener("click", () => {
    state.search = "";
    window.clearTimeout(searchRenderTimer);
  });
});

const notificationMenu = document.querySelector("#notification-center");
const notificationMenuWrap = document.querySelector("#notification-menu-wrap");
const notificationToggle = document.querySelector("#notification-toggle");

notificationToggle.addEventListener("click", async () => {
  notificationMenu.hidden = !notificationMenu.hidden;
  notificationToggle.setAttribute("aria-expanded", String(!notificationMenu.hidden));
  if (!notificationMenu.hidden) await refreshNotifications(true);
});

document.querySelector("#notification-dispatcher-filter").addEventListener("input", renderNotificationItems);
for (const filterId of [
  "notification-type-filter",
  "notification-date-filter",
  "notification-status-filter",
]) {
  document.querySelector(`#${filterId}`).addEventListener("change", renderNotificationItems);
}

document.querySelector("#notifications-read-all").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  button.disabled = true;
  try {
    await api("/api/notifications/read-all", { method: "PATCH" });
    await refreshNotifications(true);
  } catch (error) {
    const errorMessage = document.querySelector("#notification-error");
    errorMessage.textContent = error.message;
    errorMessage.hidden = false;
  } finally {
    button.disabled = false;
  }
});

document.querySelector("#notification-list").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-notification-id]");
  if (!button) return;
  const notification = state.notifications.find(
    (item) => String(item.id) === button.dataset.notificationId,
  );
  if (!notification) return;
  button.disabled = true;
  try {
    await api(`/api/notifications/${encodeURIComponent(notification.id)}/read`, {
      method: "PATCH",
    });
    await refreshNotifications(true);
    notificationMenu.hidden = true;
    notificationToggle.setAttribute("aria-expanded", "false");
    const destination = notification.module;
    if (!["trips", "fuel", "maintenance"].includes(destination)) {
      throw new Error("This notification does not have a supported destination.");
    }
    state.search = "";
    const nextHash = `#${destination}`;
    if (window.location.hash !== nextHash) {
      const hashChanged = new Promise((resolve) => {
        window.addEventListener("hashchange", resolve, { once: true });
      });
      window.location.hash = destination;
      await hashChanged;
    }
    state.notificationTarget = {
      module: destination,
      recordId: notification.record_id,
    };
    const loadedData = await loadData();
    if (!loadedData) return;
    if (destination === "trips") openTripDetails(notification.record_id);
  } catch (error) {
    const errorMessage = document.querySelector("#notification-error");
    errorMessage.textContent = error.message;
    errorMessage.hidden = false;
  }
});

document.addEventListener("click", (event) => {
  if (!notificationMenuWrap.contains(event.target)) {
    notificationMenu.hidden = true;
    notificationToggle.setAttribute("aria-expanded", "false");
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !notificationMenu.hidden) {
    notificationMenu.hidden = true;
    notificationToggle.setAttribute("aria-expanded", "false");
    notificationToggle.focus();
  }
});

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) refreshNotifications();
});

document.querySelector("#sign-out").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  button.disabled = true;
  try {
    const response = await fetch("/api/auth/logout", {
      method: "POST",
      headers: { "X-CSRF-Token": state.csrfToken },
      cache: "no-store",
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.error || `Sign out failed (${response.status}).`);
    }
    returnToSignIn();
  } catch (error) {
    showToast(error.message, "error");
    button.disabled = false;
  }
});

window.addEventListener("hashchange", () => {
  state.search = "";
  window.clearTimeout(searchRenderTimer);
  closeMegaMenu();
  setMobileNavigationOpen(false);
  render();
});

if (!location.hash && window.location.pathname !== "/dispatcher/add-trip") {
  location.hash = "dashboard";
}
loadData();
