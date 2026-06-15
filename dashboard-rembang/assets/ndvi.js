// =============================================================================
// NDVI Dashboard
// =============================================================================

mountTopbar("ndvi.html");
mountFooter();

// ---------------------------------------------------------------------------
// Data prep
// ---------------------------------------------------------------------------
const ndviCropland = REMBANG_DATA.ndviCropland; // [{kecamatan, periode, ndvi_unmasked_mean, ndvi_cropland_mean, cropland_pct}]
const satTimeseries = REMBANG_DATA.satelitTimeseries; // [{kecamatan, periode, tahun, triwulan, ndvi_mean, ndvi_source, ...}]
const pdrbTP = REMBANG_DATA.pdrbTanamanPangan; // [{periode, pdrb_tanaman_pangan}]

const PERIODS = [...new Set(ndviCropland.map(d => d.periode))].sort();

// index: periode -> kecamatan -> record
const byPeriod = {};
for (const row of ndviCropland) {
  if (!byPeriod[row.periode]) byPeriod[row.periode] = {};
  byPeriod[row.periode][row.kecamatan] = row;
}

let currentMode = "unmasked"; // "unmasked" | "cropland"
let currentPeriodIdx = PERIODS.length - 1;

// ---------------------------------------------------------------------------
// Map setup
// ---------------------------------------------------------------------------
const geo = REMBANG_DATA.geojson;
const width = 460, height = 380;
const svg = d3.select("#map").append("svg")
  .attr("viewBox", `0 0 ${width} ${height}`)
  .attr("width", "100%")
  .attr("role", "img")
  .attr("aria-label", "Peta choropleth 14 kecamatan Kabupaten Rembang menunjukkan nilai NDVI");

const projection = d3.geoMercator().fitExtent([[16, 16], [width - 16, height - 16]], geo);
const path = d3.geoPath(projection);
const isDark = matchMedia("(prefers-color-scheme: dark)").matches;

const mapPaths = svg.selectAll("path").data(geo.features).join("path")
  .attr("d", path)
  .attr("stroke", isDark ? "rgba(255,255,255,.25)" : "#fff")
  .attr("stroke-width", 1)
  .style("cursor", "pointer");

svg.selectAll("text").data(geo.features).join("text")
  .attr("x", d => path.centroid(d)[0])
  .attr("y", d => path.centroid(d)[1])
  .attr("text-anchor", "middle")
  .attr("dominant-baseline", "central")
  .attr("font-size", "10px")
  .attr("font-family", "var(--font-body)")
  .attr("fill", isDark ? "#fff" : "#2B2B28")
  .attr("pointer-events", "none")
  .text(d => d.properties.kecamatan);

function valueFor(kec, periode) {
  const row = byPeriod[periode] && byPeriod[periode][kec];
  if (!row) return null;
  return currentMode === "unmasked" ? row.ndvi_unmasked_mean : row.ndvi_cropland_mean;
}

function renderMap() {
  const periode = PERIODS[currentPeriodIdx];
  document.getElementById("periodLabel").textContent = "Periode: " + fmtPeriode(periode);

  const domain = currentMode === "unmasked" ? [0.1, 0.7] : [0.1, 0.75];
  const scale = makeScale("ndvi", domain);

  mapPaths
    .attr("fill", d => scale(valueFor(d.properties.kecamatan, periode)))
    .on("mouseenter", function (event, d) {
      const kec = d.properties.kecamatan;
      const v = valueFor(kec, periode);
      const row = byPeriod[periode][kec];
      document.getElementById("tooltip").innerHTML =
        `${kec}: ${v !== null ? fmtNum(v, 3) : "\u2013"}` +
        `<div class="sub">Persentase lahan pertanian (cropland): ${fmtNum(row.cropland_pct, 1)}%</div>`;
      d3.select(this).attr("stroke", isDark ? "#fff" : "#2B2B28").attr("stroke-width", 2);
    })
    .on("mouseleave", function () {
      document.getElementById("tooltip").innerHTML = "Arahkan kursor ke kecamatan untuk melihat nilai";
      d3.select(this).attr("stroke", isDark ? "rgba(255,255,255,.25)" : "#fff").attr("stroke-width", 1);
    });

  renderLegend("legend", "ndvi",
    currentMode === "unmasked" ? "rendah (0,1)" : "rendah (0,1)",
    currentMode === "unmasked" ? "tinggi (0,7)" : "tinggi (0,75)");

  renderRankTable(periode, scale);
}

function renderRankTable(periode, scale) {
  const rows = KECAMATAN_LIST.map(kec => ({ kec, v: valueFor(kec, periode) }))
    .filter(r => r.v !== null)
    .sort((a, b) => b.v - a.v);

  const tbody = document.getElementById("rankTable");
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${scale(r.v)};margin-right:6px;vertical-align:-1px"></span>${r.kec}</td>
      <td class="num">${fmtNum(r.v, 3)}</td>
    </tr>
  `).join("");
}

// Controls
document.getElementById("ndviModeBtns").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  document.querySelectorAll("#ndviModeBtns button").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  currentMode = btn.dataset.mode;
  renderMap();
});

const slider = document.getElementById("periodSlider");
slider.max = PERIODS.length - 1;
slider.value = currentPeriodIdx;
slider.addEventListener("input", () => {
  currentPeriodIdx = Number(slider.value);
  renderMap();
});

renderMap();

// ---------------------------------------------------------------------------
// Trend chart (per kecamatan, 2010-2026)
// ---------------------------------------------------------------------------
const kecSelect = document.getElementById("kecSelect");
kecSelect.innerHTML = KECAMATAN_LIST.map(k => `<option value="${k}">${k}</option>`).join("");
kecSelect.value = "Rembang";

let trendChart = null;

function renderTrendChart() {
  const kec = kecSelect.value;
  const rows = satTimeseries
    .filter(d => d.kecamatan === kec)
    .sort((a, b) => (a.tahun - b.tahun) || (a.triwulan - b.triwulan));

  const labels = rows.map(d => d.periode);
  const values = rows.map(d => d.ndvi_mean);
  // Color points by sensor era
  const sourceColors = { "Landsat-7": "#888780", "Landsat-8": "#B4B2A9", "Sentinel-2": "#3B6D11", "no_data": "transparent" };
  const pointColors = rows.map(d => sourceColors[d.ndvi_source] || "#888780");

  if (trendChart) trendChart.destroy();
  trendChart = new Chart(document.getElementById("trendChart"), {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "NDVI",
        data: values,
        borderColor: "#3B6D11",
        backgroundColor: "rgba(59,109,17,0.08)",
        pointBackgroundColor: pointColors,
        pointRadius: 2,
        spanGaps: true,
        tension: 0.15,
        fill: true,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { autoSkip: true, maxTicksLimit: 14, maxRotation: 45 } },
        y: { min: -0.1, max: 0.9, title: { display: true, text: "NDVI" } },
      }
    }
  });
}

kecSelect.addEventListener("change", renderTrendChart);
renderTrendChart();

// ---------------------------------------------------------------------------
// Correlation chart (NDVI cropland weighted vs PDRB Tanaman Pangan)
// ---------------------------------------------------------------------------
function weightedNdviByPeriod(periode) {
  let sumW = 0, sumWV = 0;
  for (const kec of KECAMATAN_LIST) {
    const row = byPeriod[periode] && byPeriod[periode][kec];
    if (!row || row.ndvi_cropland_mean === null || row.cropland_pct === null) continue;
    sumW += row.cropland_pct;
    sumWV += row.ndvi_cropland_mean * row.cropland_pct;
  }
  return sumW > 0 ? sumWV / sumW : null;
}

const pdrbByPeriod = {};
for (const row of pdrbTP) pdrbByPeriod[row.periode] = row.pdrb_tanaman_pangan;

const corrLabels = PERIODS.filter(p => pdrbByPeriod[p] !== undefined);
const corrNdvi = corrLabels.map(p => weightedNdviByPeriod(p));
const corrPdrb = corrLabels.map(p => pdrbByPeriod[p]);

new Chart(document.getElementById("correlationChart"), {
  type: "line",
  data: {
    labels: corrLabels,
    datasets: [
      {
        label: "NDVI lahan pertanian (tertimbang)",
        data: corrNdvi,
        borderColor: "#3B6D11",
        backgroundColor: "rgba(59,109,17,0.08)",
        yAxisID: "y",
        tension: 0.15,
        pointRadius: 2,
      },
      {
        label: "PDRB Tanaman Pangan (ADHK)",
        data: corrPdrb,
        borderColor: "#1F4E78",
        borderDash: [5, 3],
        yAxisID: "y1",
        tension: 0.15,
        pointRadius: 2,
      }
    ]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { autoSkip: true, maxTicksLimit: 12, maxRotation: 45 } },
      y: { type: "linear", position: "left", title: { display: true, text: "NDVI" }, min: 0, max: 0.8 },
      y1: { type: "linear", position: "right", title: { display: true, text: "PDRB (juta Rp)" }, grid: { drawOnChartArea: false } },
    }
  }
});
