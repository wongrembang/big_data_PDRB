// =============================================================================
// GFW (Fishing Effort) Dashboard
// =============================================================================

mountTopbar("gfw.html");
mountFooter();

const monthly = REMBANG_DATA.gfwMonthly; // [{date, total_fishing_hours, jumlah_kapal_unik}]
const geartypeMonthly = REMBANG_DATA.gfwGeartypeMonthly; // [{date, geartype, hours}]
const vesselSummary = REMBANG_DATA.gfwVesselSummary; // [{mmsi, shipName, vesselType, flag, total_hours, bulan_aktif, geartype_utama}]

// ---------------------------------------------------------------------------
// Metrics
// ---------------------------------------------------------------------------
const totalHours = monthly.reduce((s, d) => s + (d.total_fishing_hours || 0), 0);
document.getElementById("metricTotalHours").textContent = fmtNum(totalHours, 1);

const totalVessels = vesselSummary.length;
document.getElementById("metricTotalVessels").textContent = totalVessels;

const since2024 = monthly.filter(d => d.date >= "2024-06");
const avgVessels = since2024.reduce((s, d) => s + d.jumlah_kapal_unik, 0) / since2024.length;
document.getElementById("metricAvgVessels").textContent = fmtNum(avgVessels, 1);

// ---------------------------------------------------------------------------
// Trend chart
// ---------------------------------------------------------------------------
const labels = monthly.map(d => d.date);
const hours = monthly.map(d => d.total_fishing_hours);
const vessels = monthly.map(d => d.jumlah_kapal_unik);

new Chart(document.getElementById("trendChart"), {
  type: "line",
  data: {
    labels,
    datasets: [
      {
        label: "Total jam penangkapan",
        data: hours,
        borderColor: "#993C1D",
        backgroundColor: "rgba(153,60,29,0.08)",
        yAxisID: "y",
        tension: 0.2,
        pointRadius: 2,
        fill: true,
      },
      {
        label: "Jumlah kapal unik",
        data: vessels,
        borderColor: "#1F4E78",
        borderDash: [5, 3],
        yAxisID: "y1",
        tension: 0.2,
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
      y: { type: "linear", position: "left", title: { display: true, text: "Jam penangkapan" }, beginAtZero: true },
      y1: { type: "linear", position: "right", title: { display: true, text: "Jumlah kapal" }, beginAtZero: true, grid: { drawOnChartArea: false } },
    }
  }
});

// ---------------------------------------------------------------------------
// Geartype stacked chart
// ---------------------------------------------------------------------------
const GEARTYPE_COLORS = {
  "INCONCLUSIVE": "#D3D1C7",
  "FISHING": "#D85A30",
  "SET_LONGLINES": "#993C1D",
  "PURSE_SEINES": "#F0997B",
  "SET_GILLNETS": "#854F0B",
  "POLE_AND_LINE": "#FAC775",
  "FIXED_GEAR": "#712B13",
  "TRAWLERS": "#4A1B0C",
  "DREDGE_FISHING": "#BA7517",
};

const geartypes = [...new Set(geartypeMonthly.map(d => d.geartype))];
const gMonths = [...new Set(geartypeMonthly.map(d => d.date))].sort();

const gByMonth = {};
for (const row of geartypeMonthly) {
  if (!gByMonth[row.date]) gByMonth[row.date] = {};
  gByMonth[row.date][row.geartype] = row.hours;
}

const geartypeDatasets = geartypes.map(g => ({
  label: g,
  data: gMonths.map(m => (gByMonth[m] && gByMonth[m][g]) || 0),
  backgroundColor: GEARTYPE_COLORS[g] || "#888780",
}));

new Chart(document.getElementById("geartypeChart"), {
  type: "bar",
  data: { labels: gMonths, datasets: geartypeDatasets },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { stacked: true, ticks: { autoSkip: true, maxTicksLimit: 12, maxRotation: 45 } },
      y: { stacked: true, title: { display: true, text: "Jam" } },
    }
  }
});

// Custom legend for geartype
const legendHtml = geartypes.map(g => `
  <span style="display:flex;align-items:center;gap:4px">
    <span style="width:10px;height:10px;border-radius:2px;background:${GEARTYPE_COLORS[g] || '#888780'}"></span>${g}
  </span>
`).join("");
document.querySelector("#geartypeChart").insertAdjacentHTML("afterend",
  `<div style="display:flex;gap:14px;flex-wrap:wrap;margin-top:8px;font-size:12px;color:var(--ink-soft)">${legendHtml}</div>`);

// ---------------------------------------------------------------------------
// Vessel table
// ---------------------------------------------------------------------------
const tbody = document.getElementById("vesselTable");
tbody.innerHTML = vesselSummary.slice(0, 15).map(v => `
  <tr>
    <td>${v.shipName || "(tidak ada nama)"}</td>
    <td>${v.geartype_utama || "\u2013"}</td>
    <td class="num">${v.bulan_aktif}</td>
    <td class="num">${fmtNum(v.total_hours, 1)}</td>
  </tr>
`).join("");
