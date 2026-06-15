// =============================================================================
// NTL Dashboard
// =============================================================================

mountTopbar("ntl.html");
mountFooter();

// ---------------------------------------------------------------------------
// Data prep
// ---------------------------------------------------------------------------
const satTimeseries = REMBANG_DATA.satelitTimeseries;
const pdrbTotal = REMBANG_DATA.pdrbTotal; // [{periode, tahun, triwulan_num, pdrb_total_adhb, pdrb_total_adhk}]

// Hanya periode dengan ntl_recommended = true
const ntlRows = satTimeseries.filter(d => d.ntl_recommended);
const PERIODS = [...new Set(ntlRows.map(d => d.periode))].sort();

const byPeriod = {};
for (const row of ntlRows) {
  if (!byPeriod[row.periode]) byPeriod[row.periode] = {};
  byPeriod[row.periode][row.kecamatan] = row;
}

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
  .attr("aria-label", "Peta choropleth 14 kecamatan Kabupaten Rembang menunjukkan nilai NTL relatif");

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
  return row ? row.ntl_relative : null;
}

function renderMap() {
  const periode = PERIODS[currentPeriodIdx];
  document.getElementById("periodLabel").textContent = "Periode: " + fmtPeriode(periode);

  const scale = makeScale("ntl", [0.3, 2.5]);

  mapPaths
    .attr("fill", d => scale(valueFor(d.properties.kecamatan, periode)))
    .on("mouseenter", function (event, d) {
      const kec = d.properties.kecamatan;
      const v = valueFor(kec, periode);
      const row = byPeriod[periode][kec];
      document.getElementById("tooltip").innerHTML =
        `${kec}: ${v !== null ? fmtNum(v, 2) : "\u2013"}` +
        `<div class="sub">NTL median (radiance): ${fmtNum(row.ntl_median, 2)}</div>`;
      d3.select(this).attr("stroke", isDark ? "#fff" : "#2B2B28").attr("stroke-width", 2);
    })
    .on("mouseleave", function () {
      document.getElementById("tooltip").innerHTML = "Arahkan kursor ke kecamatan untuk melihat nilai";
      d3.select(this).attr("stroke", isDark ? "rgba(255,255,255,.25)" : "#fff").attr("stroke-width", 1);
    });

  renderLegend("legend", "ntl", "redup (0,3)", "terang (2,5)");
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
      <td class="num">${fmtNum(r.v, 2)}</td>
    </tr>
  `).join("");
}

const slider = document.getElementById("periodSlider");
slider.max = PERIODS.length - 1;
slider.value = currentPeriodIdx;
slider.addEventListener("input", () => {
  currentPeriodIdx = Number(slider.value);
  renderMap();
});

renderMap();

// ---------------------------------------------------------------------------
// Trend chart (per kecamatan)
// ---------------------------------------------------------------------------
const kecSelect = document.getElementById("kecSelect");
kecSelect.innerHTML = KECAMATAN_LIST.map(k => `<option value="${k}">${k}</option>`).join("");
kecSelect.value = "Rembang";

let trendChart = null;

function renderTrendChart() {
  const kec = kecSelect.value;
  const rows = PERIODS.map(p => ({ periode: p, v: valueFor(kec, p) }));

  const labels = rows.map(d => d.periode);
  const values = rows.map(d => d.v);
  const refLine = rows.map(() => 1.0);

  if (trendChart) trendChart.destroy();
  trendChart = new Chart(document.getElementById("trendChart"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "NTL relatif",
          data: values,
          borderColor: "#BA7517",
          backgroundColor: "rgba(186,117,23,0.08)",
          pointRadius: 2,
          spanGaps: true,
          tension: 0.15,
          fill: true,
        },
        {
          label: "Rata-rata kabupaten (=1,0)",
          data: refLine,
          borderColor: "#888780",
          borderDash: [4, 4],
          pointRadius: 0,
          fill: false,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { top: 16 } },
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { autoSkip: true, maxTicksLimit: 14, maxRotation: 45 } },
        y: { title: { display: true, text: "NTL relatif" }, beginAtZero: true },
      }
    }
  });
}

kecSelect.addEventListener("change", renderTrendChart);
renderTrendChart();

// ---------------------------------------------------------------------------
// Correlation chart (NTL kabupaten vs PDRB Total)
// ---------------------------------------------------------------------------
function kabupatenNtlByPeriod(periode) {
  const vals = KECAMATAN_LIST
    .map(kec => byPeriod[periode] && byPeriod[periode][kec] ? byPeriod[periode][kec].ntl_median : null)
    .filter(v => v !== null);
  if (!vals.length) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

const pdrbByPeriod = {};
for (const row of pdrbTotal) pdrbByPeriod[row.periode] = row.pdrb_total_adhb;

const corrLabels = PERIODS.filter(p => pdrbByPeriod[p] !== undefined && pdrbByPeriod[p] !== null);
const corrNtl = corrLabels.map(p => kabupatenNtlByPeriod(p));
const corrPdrb = corrLabels.map(p => pdrbByPeriod[p]);

new Chart(document.getElementById("correlationChart"), {
  type: "line",
  data: {
    labels: corrLabels,
    datasets: [
      {
        label: "NTL rata-rata kabupaten",
        data: corrNtl,
        borderColor: "#BA7517",
        backgroundColor: "rgba(186,117,23,0.08)",
        yAxisID: "y",
        tension: 0.15,
        pointRadius: 2,
      },
      {
        label: "PDRB Total (ADHB)",
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
      y: { type: "linear", position: "left", title: { display: true, text: "NTL (radiance)" }, min: 0 },
      y1: { type: "linear", position: "right", title: { display: true, text: "PDRB (juta Rp)" }, grid: { drawOnChartArea: false } },
    }
  }
});
