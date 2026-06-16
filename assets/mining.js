// =============================================================================
// Mining, Garam, Konstruksi Dashboard
// =============================================================================

mountTopbar("mining.html");
mountFooter();

const isDark = matchMedia("(prefers-color-scheme: dark)").matches;
const geo = REMBANG_DATA.geojson;

// ---------------------------------------------------------------------------
// Helper: buat SVG peta D3 untuk sebuah div
// ---------------------------------------------------------------------------
function createMap(containerId) {
  const W = 460, H = 380;
  const svg = d3.select(`#${containerId}`).append("svg")
    .attr("viewBox", `0 0 ${W} ${H}`).attr("width", "100%");
  const proj = d3.geoMercator().fitExtent([[16,16],[W-16,H-16]], geo);
  const path = d3.geoPath(proj);
  return { svg, path };
}

// Buat peta untuk ketiga tab
const mapG = createMap("mapGalian");
const mapGr = createMap("mapGaram");
const mapK = createMap("mapKonstruksi");

function drawBaseMap(mapObj) {
  const paths = mapObj.svg.selectAll("path").data(geo.features).join("path")
    .attr("d", mapObj.path)
    .attr("stroke", isDark ? "rgba(255,255,255,.2)" : "#fff")
    .attr("stroke-width", 1)
    .style("cursor", "pointer");
  mapObj.svg.selectAll("text").data(geo.features).join("text")
    .attr("x", d => mapObj.path.centroid(d)[0])
    .attr("y", d => mapObj.path.centroid(d)[1])
    .attr("text-anchor","middle").attr("dominant-baseline","central")
    .attr("font-size","10px").attr("font-family","var(--font-body)")
    .attr("fill", isDark ? "#fff" : "#2B2B28").attr("pointer-events","none")
    .text(d => d.properties.kecamatan);
  return paths;
}

const pathsG = drawBaseMap(mapG);
const pathsGr = drawBaseMap(mapGr);
const pathsK = drawBaseMap(mapK);

// ---------------------------------------------------------------------------
// TAB SWITCHER
// ---------------------------------------------------------------------------
window.switchTab = function(name) {
  document.querySelectorAll(".tab-panel").forEach(el => el.classList.remove("active"));
  document.querySelectorAll(".tab-bar button").forEach(el => el.classList.remove("active"));
  document.getElementById(`tab-${name}`).classList.add("active");
  event.target.classList.add("active");
};

// =============================================================================
// TAB 1: GALIAN C (BSI)
// =============================================================================
const galian = REMBANG_DATA.galianC;
const GALIAN_PERIODS = [...new Set(galian.map(d => d.periode))].sort();
const galianByPeriod = {};
for (const r of galian) {
  if (!galianByPeriod[r.periode]) galianByPeriod[r.periode] = {};
  galianByPeriod[r.periode][r.kecamatan] = r;
}

let galianPeriodIdx = GALIAN_PERIODS.length - 1;
const galianSlider = document.getElementById("galianSlider");
galianSlider.max = GALIAN_PERIODS.length - 1;
galianSlider.value = galianPeriodIdx;
galianSlider.addEventListener("input", () => { galianPeriodIdx = +galianSlider.value; renderGalian(); });

const scaleGalian = makeScale("ntl", [-0.05, 0.1]); // BSI range

function renderGalian() {
  const p = GALIAN_PERIODS[galianPeriodIdx];
  document.getElementById("galianPeriodLabel").textContent = "Periode: " + fmtPeriode(p);
  pathsG.attr("fill", d => {
    const row = galianByPeriod[p] && galianByPeriod[p][d.properties.kecamatan];
    return row && row.bsi_mean !== null ? scaleGalian(row.bsi_mean) : "#EDEAE2";
  });
  pathsG
    .on("mouseenter", function(ev, d) {
      const kec = d.properties.kecamatan;
      const row = galianByPeriod[p] && galianByPeriod[p][kec];
      document.getElementById("tooltipGalian").innerHTML =
        `${kec}: BSI ${fmtNum(row?.bsi_mean,4)}<div class="sub">BSI frac: ${fmtNum(row?.bsi_high_fraction,4)} | Limestone: ${fmtNum(row?.limestone_ratio_mean,4)}</div>`;
      d3.select(this).attr("stroke","#2B2B28").attr("stroke-width",2);
    })
    .on("mouseleave", function() {
      document.getElementById("tooltipGalian").innerHTML = "Arahkan kursor ke kecamatan";
      d3.select(this).attr("stroke", isDark?"rgba(255,255,255,.2)":"#fff").attr("stroke-width",1);
    });
  renderLegend("legendGalian","ntl","BSI rendah (−0.05)","BSI tinggi (0.10)");
  // Rank table
  const rows = KECAMATAN_LIST
    .map(kec => ({ kec, r: galianByPeriod[p] && galianByPeriod[p][kec] }))
    .filter(x => x.r && x.r.bsi_mean !== null)
    .sort((a,b) => b.r.bsi_mean - a.r.bsi_mean);
  document.getElementById("rankGalian").innerHTML = rows.map(({kec,r}) =>
    `<tr><td>${kec}</td><td class="num">${fmtNum(r.bsi_mean,4)}</td><td class="num">${fmtNum(r.bsi_high_fraction,4)}</td></tr>`
  ).join("");
}
renderGalian();

// Trend chart galian C
const galianKecSelect = document.getElementById("galianKecSelect");
galianKecSelect.innerHTML = KECAMATAN_LIST.map(k => `<option value="${k}">${k}</option>`).join("");
galianKecSelect.value = "Gunem";
let galianChart = null;

function renderGalianTrend() {
  const kec = galianKecSelect.value;
  const rows = galian.filter(d => d.kecamatan === kec).sort((a,b) => a.periode > b.periode ? 1 : -1);
  if (galianChart) galianChart.destroy();
  galianChart = new Chart(document.getElementById("galianTrendChart"), {
    type: "line",
    data: {
      labels: rows.map(d => d.periode),
      datasets: [
        { label:"BSI mean", data:rows.map(d=>d.bsi_mean), borderColor:"#BA7517",
          backgroundColor:"rgba(186,117,23,0.06)", tension:0.15, pointRadius:3,
          fill:true, clip: false },
        { label:"BSI high frac", data:rows.map(d=>d.bsi_high_fraction), borderColor:"#993C1D",
          borderDash:[4,3], tension:0.15, pointRadius:2,
          fill:false, yAxisID:"y1", clip: false },
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { top: 24, right: 16, bottom: 8, left: 8 } },
      plugins:{ legend:{display:false}, tooltip:{mode:"index",intersect:false} },
      scales:{
        x:{ ticks:{autoSkip:true,maxTicksLimit:12,maxRotation:45} },
        y:{ title:{display:true,text:"BSI mean"},
            suggestedMin: -0.28, suggestedMax: 0.24,
            ticks:{ callback: v => v.toFixed(2) } },
        y1:{ type:"linear", position:"right",
             title:{display:true,text:"BSI frac"},
             grid:{drawOnChartArea:false},
             min: 0, max: 1.05 }
      }
    }
  });
}
galianKecSelect.addEventListener("change", renderGalianTrend);
renderGalianTrend();

// =============================================================================
// TAB 2: TAMBAK GARAM (SAR + NDWI)
// =============================================================================
const garam = REMBANG_DATA.tambakGaram;
const GARAM_PERIODS = [...new Set(garam.map(d => d.periode))].sort();
const garamByPeriod = {};
for (const r of garam) {
  if (!garamByPeriod[r.periode]) garamByPeriod[r.periode] = {};
  garamByPeriod[r.periode][r.kecamatan] = r;
}

let garamPeriodIdx = GARAM_PERIODS.length - 1;
const garamSlider = document.getElementById("garamSlider");
garamSlider.max = GARAM_PERIODS.length - 1;
garamSlider.value = garamPeriodIdx;
garamSlider.addEventListener("input", () => { garamPeriodIdx = +garamSlider.value; renderGaram(); });

// SAR VV: nilai lebih rendah = lebih aktif. Range biasanya -12 sampai -8
const scaleGaram = makeScale("gray", [-11, -8]); // dark = rendah = aktif

function renderGaram() {
  const p = GARAM_PERIODS[garamPeriodIdx];
  document.getElementById("garamPeriodLabel").textContent = "Periode: " + fmtPeriode(p);
  pathsGr.attr("fill", d => {
    const row = garamByPeriod[p] && garamByPeriod[p][d.properties.kecamatan];
    return row && row.sar_vv_median !== null ? scaleGaram(row.sar_vv_median) : "#EDEAE2";
  });
  pathsGr
    .on("mouseenter", function(ev, d) {
      const kec = d.properties.kecamatan;
      const row = garamByPeriod[p] && garamByPeriod[p][kec];
      document.getElementById("tooltipGaram").innerHTML =
        `${kec}: SAR VV ${fmtNum(row?.sar_vv_median,2)}<div class="sub">NDWI: ${fmtNum(row?.ndwi_mean,4)} | Water frac: ${fmtNum(row?.ndwi_water_fraction,4)}</div>`;
      d3.select(this).attr("stroke","#2B2B28").attr("stroke-width",2);
    })
    .on("mouseleave", function() {
      document.getElementById("tooltipGaram").innerHTML = "Arahkan kursor ke kecamatan";
      d3.select(this).attr("stroke", isDark?"rgba(255,255,255,.2)":"#fff").attr("stroke-width",1);
    });
  renderLegend("legendGaram","gray","SAR rendah (tambak aktif, −11)","SAR tinggi (−8)");
  const rows = KECAMATAN_LIST
    .map(kec => ({ kec, r: garamByPeriod[p] && garamByPeriod[p][kec] }))
    .filter(x => x.r && x.r.sar_vv_median !== null)
    .sort((a,b) => a.r.sar_vv_median - b.r.sar_vv_median); // SAR rendah = lebih aktif = di atas
  document.getElementById("rankGaram").innerHTML = rows.map(({kec,r}) =>
    `<tr><td>${kec}</td><td class="num">${fmtNum(r.sar_vv_median,2)}</td><td class="num">${fmtNum(r.ndwi_mean,4)}</td></tr>`
  ).join("");
}
renderGaram();

// Trend chart: SAR VV rata-rata Kaliori+Rembang+Lasem vs produksi garam riil
const TAMBAK_KEC = ["Kaliori","Rembang","Lasem"];
const sarByPeriod = {};
for (const p of GARAM_PERIODS) {
  const vals = TAMBAK_KEC.map(k => garamByPeriod[p]?.[k]?.sar_vv_median).filter(v => v !== null && v !== undefined);
  sarByPeriod[p] = vals.length ? vals.reduce((a,b) => a+b,0)/vals.length : null;
}

// Data produksi garam riil (dari analisis)
const garamProduksi = {
  "2023Q1":0,"2023Q2":1087,"2023Q3":110041,"2023Q4":59484,
  "2024Q1":0,"2024Q2":11411,"2024Q3":119979,"2024Q4":59953,
  "2025Q1":0,"2025Q2":11500.97,"2025Q3":5746.99
};

new Chart(document.getElementById("garamTrendChart"), {
  type: "line",
  data: {
    labels: GARAM_PERIODS,
    datasets: [
      { label:"SAR VV fokus tambak", data:GARAM_PERIODS.map(p=>sarByPeriod[p]),
        borderColor:"#185FA5", backgroundColor:"rgba(24,95,165,0.07)",
        yAxisID:"y", tension:0.15, pointRadius:2, fill:true },
      { label:"Produksi garam (ton)", data:GARAM_PERIODS.map(p=>garamProduksi[p]??null),
        borderColor:"#BA7517", borderDash:[5,3],
        yAxisID:"y1", tension:0.15, pointRadius:3, spanGaps:false, fill:false },
    ]
  },
  options: { responsive:true, maintainAspectRatio:false,
    plugins:{legend:{display:false}},
    scales:{
      x:{ticks:{autoSkip:true,maxTicksLimit:12,maxRotation:45}},
      y:{position:"left",title:{display:true,text:"SAR VV (dB)"}},
      y1:{position:"right",title:{display:true,text:"Produksi (ton)"},
          grid:{drawOnChartArea:false},min:0}
    }
  }
});

// =============================================================================
// TAB 3: KONSTRUKSI (NDBI + GHSL)
// =============================================================================
const ndbi = REMBANG_DATA.ndbi;
const NDBI_PERIODS = [...new Set(ndbi.map(d => d.periode))].sort();
const ndbiByPeriod = {};
for (const r of ndbi) {
  if (!ndbiByPeriod[r.periode]) ndbiByPeriod[r.periode] = {};
  ndbiByPeriod[r.periode][r.kecamatan] = r;
}

let konstruksiPeriodIdx = NDBI_PERIODS.length - 1;
const konstruksiSlider = document.getElementById("konstruksiSlider");
konstruksiSlider.max = NDBI_PERIODS.length - 1;
konstruksiSlider.value = konstruksiPeriodIdx;
konstruksiSlider.addEventListener("input", () => { konstruksiPeriodIdx = +konstruksiSlider.value; renderKonstruksi(); });

const scaleNDBI = makeScale("ntl", [-0.15, 0.1]); // NDBI range

function renderKonstruksi() {
  const p = NDBI_PERIODS[konstruksiPeriodIdx];
  document.getElementById("konstruksiPeriodLabel").textContent = "Periode: " + fmtPeriode(p);
  pathsK.attr("fill", d => {
    const row = ndbiByPeriod[p] && ndbiByPeriod[p][d.properties.kecamatan];
    return row && row.ndbi_mean !== null ? scaleNDBI(row.ndbi_mean) : "#EDEAE2";
  });
  pathsK
    .on("mouseenter", function(ev, d) {
      const kec = d.properties.kecamatan;
      const row = ndbiByPeriod[p] && ndbiByPeriod[p][kec];
      document.getElementById("tooltipKonstruksi").innerHTML =
        `${kec}: NDBI ${fmtNum(row?.ndbi_mean,4)}<div class="sub">NDBI frac: ${fmtNum(row?.ndbi_fraction,4)} | Urban Idx: ${fmtNum(row?.urban_index_mean,4)}</div>`;
      d3.select(this).attr("stroke","#2B2B28").attr("stroke-width",2);
    })
    .on("mouseleave", function() {
      document.getElementById("tooltipKonstruksi").innerHTML = "Arahkan kursor ke kecamatan";
      d3.select(this).attr("stroke", isDark?"rgba(255,255,255,.2)":"#fff").attr("stroke-width",1);
    });
  renderLegend("legendKonstruksi","ntl","NDBI rendah (−0.15)","NDBI tinggi (0.10)");
  const rows = KECAMATAN_LIST
    .map(kec => ({ kec, r: ndbiByPeriod[p] && ndbiByPeriod[p][kec] }))
    .filter(x => x.r && x.r.ndbi_mean !== null)
    .sort((a,b) => b.r.ndbi_mean - a.r.ndbi_mean);
  document.getElementById("rankKonstruksi").innerHTML = rows.map(({kec,r}) =>
    `<tr><td>${kec}</td><td class="num">${fmtNum(r.ndbi_mean,4)}</td><td class="num">${fmtNum(r.urban_index_mean,4)}</td></tr>`
  ).join("");
}
renderKonstruksi();

// Trend chart NDBI per kecamatan
const konstruksiKecSelect = document.getElementById("konstruksiKecSelect");
konstruksiKecSelect.innerHTML = KECAMATAN_LIST.map(k => `<option value="${k}">${k}</option>`).join("");
konstruksiKecSelect.value = "Rembang";
let konstruksiChart = null;

function renderKonstruksiTrend() {
  const kec = konstruksiKecSelect.value;
  const rows = ndbi.filter(d => d.kecamatan === kec).sort((a,b) => a.periode > b.periode ? 1 : -1);
  if (konstruksiChart) konstruksiChart.destroy();
  konstruksiChart = new Chart(document.getElementById("konstruksiTrendChart"), {
    type:"line",
    data:{
      labels:rows.map(d=>d.periode),
      datasets:[
        { label:"NDBI mean", data:rows.map(d=>d.ndbi_mean), borderColor:"#1F4E78",
          backgroundColor:"rgba(31,78,120,0.08)", tension:0.15, pointRadius:2, fill:true, spanGaps:true },
        { label:"Urban Index", data:rows.map(d=>d.urban_index_mean), borderColor:"#BA7517",
          borderDash:[4,3], tension:0.15, pointRadius:2, fill:false, spanGaps:true },
      ]
    },
    options:{ responsive:true, maintainAspectRatio:false,
      layout: { padding: { top: 16 } },
      plugins:{legend:{display:false}},
      scales:{
        x:{ticks:{autoSkip:true,maxTicksLimit:12,maxRotation:45}},
        y:{title:{display:true,text:"Nilai indeks"}, beginAtZero:false}
      }
    }
  });
}
konstruksiKecSelect.addEventListener("change", renderKonstruksiTrend);
renderKonstruksiTrend();

// GHSL delta chart
const ghslDelta = REMBANG_DATA.ghslDelta;
const delta2025 = ghslDelta.filter(d => d.epoch_dari === 2020)
  .sort((a,b) => b.delta_buildup_m2 - a.delta_buildup_m2);

new Chart(document.getElementById("ghslDeltaChart"), {
  type:"bar",
  data:{
    labels: delta2025.map(d=>d.kecamatan),
    datasets:[{
      label:"Pertambahan area terbangun (m²)",
      data: delta2025.map(d=>d.delta_buildup_m2),
      backgroundColor: delta2025.map(d =>
        d.delta_buildup_m2 > 90000 ? "#1F4E78" :
        d.delta_buildup_m2 > 60000 ? "#2E75B6" :
        d.delta_buildup_m2 > 45000 ? "#378ADD" : "#85B7EB"
      ),
      borderRadius:3,
    }]
  },
  options:{ indexAxis:"y", responsive:true, maintainAspectRatio:false,
    plugins:{legend:{display:false}},
    scales:{
      x:{ticks:{callback:v=>(v/1000).toFixed(0)+"k"},
         title:{display:true,text:"m²"}},
      y:{ticks:{font:{size:11}}}
    }
  }
});
