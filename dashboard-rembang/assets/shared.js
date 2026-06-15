// =============================================================================
// SIMAK Rembang - Shared helpers
// =============================================================================

const NAV_ITEMS = [
  { href: "index.html", label: "Beranda" },
  { href: "ndvi.html", label: "NDVI · Vegetasi" },
  { href: "ntl.html", label: "NTL · Cahaya Malam" },
  { href: "gfw.html", label: "Perikanan Tangkap" },
];

function renderTopbar(activeHref) {
  const nav = NAV_ITEMS.map(item => {
    const cls = item.href === activeHref ? "active" : "";
    return `<a href="${item.href}" class="${cls}">${item.label}</a>`;
  }).join("");

  return `
    <div class="topbar">
      <div class="brand">
        <span class="mark">SIMAK Rembang</span>
        <span class="sub">Sistem Indikator Monitoring Awal Kewilayahan</span>
      </div>
      <nav>${nav}</nav>
    </div>
  `;
}

function mountTopbar(activeHref) {
  const el = document.getElementById("topbar");
  if (el) el.outerHTML = renderTopbar(activeHref);
}

function renderFooter() {
  return `
    <footer>
      <span>SIMAK Rembang &mdash; eksplorasi big data untuk proksi PDRB Kabupaten Rembang</span>
      <span>Sumber: Google Earth Engine (Sentinel-2, VIIRS), Global Fishing Watch, BPS Kab. Rembang</span>
    </footer>
  `;
}

function mountFooter() {
  const el = document.getElementById("footer");
  if (el) el.outerHTML = renderFooter();
}

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------
function fmtNum(x, digits = 2) {
  if (x === null || x === undefined || isNaN(x)) return "\u2013";
  return Number(x).toLocaleString("id-ID", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function fmtPeriode(periode) {
  // "2024Q2" -> "Q2 2024"
  const m = periode.match(/^(\d{4})Q(\d)$/);
  if (!m) return periode;
  return `Q${m[2]} ${m[1]}`;
}

// ---------------------------------------------------------------------------
// Color ramps (consistent with style.css accent colors)
// ---------------------------------------------------------------------------
const RAMPS = {
  ndvi: ["#EAF3DE", "#C0DD97", "#97C459", "#639922", "#3B6D11", "#27500A", "#173404"],
  ntl: ["#FAEEDA", "#FAC775", "#EF9F27", "#BA7517", "#854F0B", "#633806", "#412402"],
  gfw: ["#FAECE7", "#F5C4B3", "#F0997B", "#D85A30", "#993C1D", "#712B13", "#4A1B0C"],
  gray: ["#F1EFE8", "#D3D1C7", "#B4B2A9", "#888780", "#5F5E5A", "#444441", "#2C2C2A"],
};

function makeScale(ramp, domain) {
  // returns a function value -> color, quantize across 7 buckets
  const [lo, hi] = domain;
  const colors = RAMPS[ramp];
  return function (v) {
    if (v === null || v === undefined || isNaN(v)) return "#EDEAE2";
    let t = (v - lo) / (hi - lo);
    t = Math.max(0, Math.min(1, t));
    const idx = Math.min(colors.length - 1, Math.floor(t * colors.length));
    return colors[idx];
  };
}

function renderLegend(containerId, ramp, lowLabel, highLabel) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const swatches = RAMPS[ramp].map(c => `<span style="background:${c}"></span>`).join("");
  el.innerHTML = `<span>${lowLabel}</span><div class="ramp">${swatches}</div><span>${highLabel}</span>`;
}

// ---------------------------------------------------------------------------
// 14 kecamatan list (consistent order, matches GeoJSON)
// ---------------------------------------------------------------------------
const KECAMATAN_LIST = [
  "Sumber", "Bulu", "Gunem", "Sale", "Sarang", "Sedan", "Pamotan",
  "Sulang", "Kaliori", "Rembang", "Pancur", "Kragan", "Sluke", "Lasem",
];
