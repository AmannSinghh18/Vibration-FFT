(() => {
  "use strict";

  const state = { file: null, phase1: null, phase2: null, busy: false, gridVisible: true, viewVersion: 0 };
  const el = (id) => document.getElementById(id);
  const fileInput = el("uff-file");
  const dropzone = el("dropzone");
  const plotId = "spectrum-plot";
  const analysisInputs = [el("sideband-analysis"), el("harmonic-markers")];

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
    })[character]);
  }

  function setMessage(text, type = "") {
    const node = el("message");
    node.textContent = text;
    node.className = `message ${type}`;
  }

  function setStatus(text, ready = false) {
    el("service-status").textContent = text;
    el("service-status").previousElementSibling.classList.toggle("ready", ready);
  }

  function setBusy(busy, message = "") {
    state.busy = busy;
    el("analyze-button").disabled = busy || (state.file && !state.file.name.toLowerCase().endsWith(".uff"));
    analysisInputs.forEach((input) => { input.disabled = busy; });
    if (message) setMessage(message, "loading");
  }

  function selectFile(file) {
    if (!file) return;
    state.file = file;
    el("selected-file").textContent = file.name;
    const valid = file.name.toLowerCase().endsWith(".uff");
    el("analyze-button").disabled = !valid;
    setStatus(valid ? "Ready to analyze" : "Invalid file", valid);
    if (!valid) setMessage("Please choose a file with the .uff extension.", "error");
    else setMessage("");
  }

  fileInput.addEventListener("change", () => selectFile(fileInput.files[0]));
  ["dragenter", "dragover"].forEach((eventName) => dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.add("is-dragging");
  }));
  ["dragleave", "drop"].forEach((eventName) => dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.remove("is-dragging");
  }));
  dropzone.addEventListener("drop", (event) => selectFile(event.dataTransfer.files[0]));

  const analysisToggle = el("analysis-toggle");
  const analysisMenu = el("analysis-menu");
  analysisToggle.addEventListener("click", (event) => {
    event.stopPropagation();
    const open = analysisToggle.getAttribute("aria-expanded") === "true";
    analysisToggle.setAttribute("aria-expanded", String(!open));
    analysisMenu.hidden = open;
  });
  document.addEventListener("click", (event) => {
    if (!analysisMenu.hidden && !analysisMenu.contains(event.target) && event.target !== analysisToggle) {
      analysisMenu.hidden = true;
      analysisToggle.setAttribute("aria-expanded", "false");
    }
  });
  window.addEventListener("resize", () => {
    if (typeof Plotly !== "undefined" && state.phase1) Plotly.Plots.resize(plotId);
  });

  async function request(endpoint, includeSidebands = false) {
    if (!state.file) throw new Error("Choose a .uff file before analyzing.");
    const form = new FormData();
    form.append("file", state.file);
    if (endpoint.includes("phase2")) form.append("sideband_analysis", String(includeSidebands));
    const response = await fetch(endpoint, { method: "POST", body: form });
    let payload = {};
    try { payload = await response.json(); } catch (_) { /* handled below */ }
    if (!response.ok) throw new Error(payload.error || "The analysis service returned an error.");
    return payload;
  }

  function formatNumber(value, digits = 2) {
    if (value === null || value === undefined || value === "") return "—";
    return Number(value).toLocaleString(undefined, { maximumFractionDigits: digits });
  }

  function renderMetadata(result) {
    const metadata = result.metadata;
    const span = metadata.sample_rate_hz ? metadata.sample_count / metadata.sample_rate_hz : 0;
    const resolution = span ? 1 / span : 0;
    const fields = [
      ["Filename", result.filename], ["Channel", metadata.quantity],
      ["Resolution", `${formatNumber(resolution, 4)} Hz`], ["Span", `${formatNumber(span, 2)} s`], ["Status", "Processed"],
    ];
    el("metadata").innerHTML = fields.map(([label, value]) => (
      `<div><dt>${escapeHtml(label)}</dt><dd title="${escapeHtml(value)}">${escapeHtml(value)}</dd></div>`
    )).join("");
  }

  function plotLayout(result, annotations = {}) {
    const reference = result.metadata.reference;
    const isVelocity = result.spectrum.unit.includes("mm/s");
    return {
      uirevision: `${result.filename}-${state.viewVersion}`,
      margin: { l: 72, r: 25, t: 18, b: 52 },
      paper_bgcolor: "#ffffff", plot_bgcolor: "#fbfcfc",
      font: { family: "IBM Plex Mono, Consolas, monospace", color: "#243342", size: 11 },
      hovermode: "closest", showlegend: true,
      legend: { orientation: "h", y: 1.08, x: 0, font: { size: 10, color: "#52697d" } },
      xaxis: {
        title: { text: "Frequency [Hz]", font: { size: 11, color: "#5b7893" } },
        range: reference.x_limit, dtick: reference.x_tick, showgrid: state.gridVisible,
        gridcolor: "#dfe7eb", zerolinecolor: "#c5d0d7", linecolor: "#8193a0", ticks: "outside",
      },
      yaxis: {
        title: { text: `${isVelocity ? "v" : "a"} rms [${result.spectrum.unit}]`, font: { size: 11, color: "#5b7893" } },
        range: reference.y_limit, dtick: reference.y_tick, showgrid: state.gridVisible,
        gridcolor: "#dfe7eb", zerolinecolor: "#c5d0d7", linecolor: "#8193a0", ticks: "outside",
      },
      annotations: annotations.labels || [], shapes: annotations.shapes || [],
    };
  }

  function baseTrace(result) {
    return {
      x: result.spectrum.frequencies, y: result.spectrum.amplitudes,
      type: "scattergl", mode: "lines", name: "Spectrum",
      line: { color: "#126a82", width: 1.25 },
      hovertemplate: "f = %{x:.3f} Hz<br>RMS = %{y:.5g}<extra></extra>",
    };
  }

  function resetAnalysisState() {
    state.phase2 = null;
    el("analysis-counts").textContent = "Hover for values";
    el("peak-table-wrap").classList.add("hidden");
    analysisInputs.forEach((input) => { input.checked = false; });
  }

  function renderPlot(traces, layout) {
    const node = el(plotId);
    if (node.classList.contains("js-plotly-plot")) Plotly.purge(node);
    node.replaceChildren();
    return Plotly.newPlot(node, traces, layout, {
      responsive: true, scrollZoom: true, displayModeBar: true, displaylogo: false,
      modeBarButtonsToRemove: ["lasso2d", "select2d"],
    });
  }

  function renderBaseline() {
    if (!state.phase1 || typeof Plotly === "undefined") return;
    state.phase2 = null;
    state.viewVersion += 1;
    el("analysis-counts").textContent = "Baseline spectrum";
    el("peak-table-wrap").classList.add("hidden");
    renderPlot([baseTrace(state.phase1)], plotLayout(state.phase1));
  }

  function renderPhase1(result) {
    state.phase1 = result;
    renderMetadata(result);
    resetAnalysisState();
    setStatus("File processed", true);
    renderBaseline();
  }

  function phase2Traces(result) {
    const peaks = result.analysis.peaks;
    const matched = peaks.filter((peak) => peak.match_status);
    const unmatched = peaks.filter((peak) => !peak.match_status);
    const sidebands = result.analysis.sidebands;
    const peakHover = (peak) => `${peak.frequency_hz.toFixed(3)} Hz<br>RMS ${peak.amplitude.toPrecision(5)}<br>${peak.match_status ? `${peak.characteristic} | ${peak.component}` : "No table match"}`;
    const peakTrace = (items, name, color, symbol) => ({
      x: items.map((peak) => peak.frequency_hz), y: items.map((peak) => peak.amplitude),
      type: "scatter", mode: "markers", name,
      marker: { color, size: 8, symbol, line: { color: "#10161b", width: 1 } },
      text: items.map(peakHover), hovertemplate: "%{text}<extra></extra>",
    });
    const sidebandTrace = {
      x: sidebands.map((item) => item.frequency_hz), y: sidebands.map((item) => item.amplitude),
      type: "scatter", mode: "markers", name: "Sidebands",
      marker: { color: "#e3a14d", size: 7, symbol: "circle-open", line: { width: 1.5 } },
      text: sidebands.map((item) => `${item.frequency_hz.toFixed(3)} Hz<br>${item.side} sideband | ${item.spacing_name}`),
      hovertemplate: "%{text}<extra></extra>",
    };
    return [baseTrace(result), peakTrace(matched, "Matched characteristics", "#d66b6b", "triangle-up"), peakTrace(unmatched, "Unmatched significant peaks", "#8fc2a5", "diamond"), ...(sidebands.length ? [sidebandTrace] : [])];
  }

  function phase2Annotations(result) {
    const strongest = [...result.analysis.peaks].sort((a, b) => b.amplitude - a.amplitude).slice(0, 12);
    const labels = strongest.map((peak, index) => ({
      x: peak.frequency_hz, y: peak.amplitude, xref: "x", yref: "y", text: `${peak.frequency_hz.toFixed(2)} Hz`, showarrow: true, arrowhead: 0,
      ax: 0, ay: index % 2 ? -28 : 28, font: { size: 9, color: peak.match_status ? "#ed9a9a" : "#a9d5b9" },
      bgcolor: "#ffffffee", bordercolor: peak.match_status ? "#d7a4a4" : "#a9cdb6", borderwidth: 1, borderpad: 2,
    }));
    const shapes = result.analysis.peaks.filter((peak) => peak.match_status).map((peak) => ({ type: "line", x0: peak.frequency_hz, x1: peak.frequency_hz, y0: 0, y1: peak.amplitude, line: { color: "#bd5e67", width: 1, dash: "dot" } }));
    return { labels, shapes };
  }

  function renderPeakTable(result) {
    el("peak-table").innerHTML = result.analysis.peaks.map((peak) => (
      `<tr><td>${formatNumber(peak.frequency_hz, 3)}</td><td>${formatNumber(peak.amplitude, 5)}</td>` +
      `<td class="${peak.match_status ? "match-yes" : "match-no"}">${peak.match_status ? "Yes" : "No"}</td>` +
      `<td>${escapeHtml(peak.characteristic ? `${peak.characteristic} | ${peak.component}` : "—")}</td>` +
      `<td>${formatNumber(peak.difference_hz, 3)}</td><td>${peak.sidebands.length || "—"}</td></tr>`
    )).join("");
    el("peak-table-wrap").classList.remove("hidden");
  }

  function renderPhase2(result) {
    state.phase2 = result;
    state.viewVersion += 1;
    const counts = result.analysis.counts;
    el("analysis-counts").textContent = `${counts.detected_peaks} peaks | ${counts.matched_peaks} matches | ${counts.sideband_hits} sideband hits`;
    renderPlot(phase2Traces(result), plotLayout(result, phase2Annotations(result)));
    renderPeakTable(result);
  }

  async function runPhase2() {
    if (!state.file || !state.phase1 || state.busy) return;
    const sidebands = el("sideband-analysis").checked;
    setBusy(true, sidebands ? "Running sideband analysis..." : "Running analysis...");
    try {
      renderPhase2(await request("/api/analyze/phase2", sidebands));
      setMessage("Analysis result ready in the spectrum view.", "success");
    } catch (error) {
      console.error(error);
      setMessage(error.message || "Unable to complete the analysis.", "error");
    } finally { setBusy(false); }
  }

  el("upload-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.busy) return;
    setBusy(true, "Processing UFF file...");
    try {
      renderPhase1(await request("/api/analyze"));
      setMessage("Spectrum ready.", "success");
    } catch (error) {
      console.error(error);
      setStatus("Awaiting file");
      setMessage(error.message || "Unable to process the UFF file.", "error");
    } finally { setBusy(false); }
  });

  analysisInputs.forEach((input) => input.addEventListener("change", () => {
    if (!state.phase1) {
      input.checked = false;
      setMessage("Upload and analyze a .uff file before selecting analysis options.", "error");
      return;
    }
    if (analysisInputs.every((option) => !option.checked)) {
      renderBaseline();
      setMessage("Baseline spectrum restored.", "success");
    } else runPhase2();
  }));

  if (typeof Plotly === "undefined") setMessage("The interactive plotting library could not be loaded. Check network access and refresh.", "error");
})();