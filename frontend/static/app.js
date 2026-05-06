document.addEventListener("DOMContentLoaded", function () {
  loadDashboard();
});


function loadDashboard() {
  Promise.all([
    fetch("/api/master").then(function(r) { return r.json(); }),
    fetch("/api/recommendations").then(function(r) { return r.json(); }),
  ]).then(function(results) {
    var master = results[0];
    var recs = results[1];
    renderDashboard(master, recs);
  }).catch(function(err) {
    document.getElementById("loading").innerHTML = "failed to load data: " + err.message;
  });
}


function renderDashboard(master, recs) {
  document.getElementById("loading").style.display = "none";
  document.getElementById("dashboard").style.display = "block";

  renderHeader(master);
  renderMasterScore(master);
  renderBiometrics(master);
  renderBloodworkPanels(master);
  if (master.biomechanics) {
    renderBiomechanics(master);
  }
  renderTravelImpact(master);
  renderCircadian(master);
  renderAI(recs);
}


function renderHeader(master) {
  var name = master.athlete_summary.name || "athlete";
  var sport = master.athlete_summary.sport || "";
  document.getElementById("athlete-name").textContent = name + " · " + sport;

  var ts = master.meta.generated_at || "";
  document.getElementById("meta-timestamp").textContent = ts;
}


function renderMasterScore(master) {
  var score = master.master_readiness.score;
  var risk = master.master_readiness.risk_level;
  var protocol = master.master_readiness.protocol_recommendation;

  document.getElementById("master-score").textContent = score;

  var circumference = 2 * Math.PI * 60;
  var offset = circumference - (score / 100) * circumference;
  var ring = document.getElementById("ring-fill");
  setTimeout(function() {
    ring.style.strokeDashoffset = offset;
  }, 100);

  var badgeEl = document.getElementById("risk-badge");
  badgeEl.innerHTML = '<span class="badge badge-' + risk + '">' + risk + '</span>';

  var protocolName = protocol.replace(/_/g, " ");
  document.getElementById("protocol-name").textContent = protocolName;
  document.getElementById("protocol-sub").textContent = "readiness: " + score + " / 100";

  var dest = master.athlete_summary.destination || "—";
  var tz = master.athlete_summary.timezone_shift || 0;
  var dir = master.athlete_summary.direction || "";
  var dur = master.athlete_summary.flight_duration_hours || 0;

  document.getElementById("destination-city").textContent = dest;
  document.getElementById("destination-details").textContent =
    tz + "h " + dir + " · " + dur + "h flight";
}


function renderBiometrics(master) {
  var pretravel = master.travel.components.pretravel;

  var phiAnsEl = document.getElementById("phi-ans");
  phiAnsEl.textContent = pretravel.phi_ans;
  applyColorClass(phiAnsEl, pretravel.phi_ans, true);

  var phiSlpEl = document.getElementById("phi-slp");
  phiSlpEl.textContent = pretravel.phi_slp;
  applyColorClass(phiSlpEl, pretravel.phi_slp, true);

  var wearableEl = document.getElementById("wearable-baseline");
  wearableEl.textContent = pretravel.wearable_baseline;
  applyColorClass(wearableEl, pretravel.wearable_baseline, true);

  var bwScore = master.bloodwork.bloodwork_score;
  var flags = master.bloodwork.flag_count;
  var attn = master.bloodwork.attenuation_factors;

  var bwScoreEl = document.getElementById("bloodwork-score");
  bwScoreEl.textContent = bwScore;
  applyColorClass(bwScoreEl, bwScore, true);

  var flagsEl = document.getElementById("bloodwork-flags");
  flagsEl.textContent = flags + " clinical flag" + (flags !== 1 ? "s" : "");
  if (flags > 0) flagsEl.classList.add("text-critical");
  document.getElementById("rho-hormonal").textContent = attn.rho_hormonal;
  document.getElementById("rho-iron").textContent = attn.rho_iron;
  document.getElementById("rho-muscle").textContent = attn.rho_muscle;

  renderHrvBars(master);
}


function renderHrvBars(master) {
  var container = document.getElementById("hrv-bars");
  container.innerHTML = "";

  var rbc = master.bloodwork.kinetics.rbc;
  var trajectory = rbc.rbc_trajectory || [];
  var sample = [];
  var step = Math.max(1, Math.floor(trajectory.length / 14));

  for (var i = 0; i < trajectory.length; i += step) {
    sample.push(trajectory[i]);
  }
  if (sample.length > 14) {
    sample = sample.slice(0, 14);
  }

  if (sample.length === 0) return;

  var maxVal = Math.max.apply(null, sample);
  var minVal = Math.min.apply(null, sample);
  var range = maxVal - minVal || 1;

  for (var j = 0; j < sample.length; j++) {
    var bar = document.createElement("div");
    bar.className = "bar";
    var height = ((sample[j] - minVal) / range) * 100;
    height = Math.max(8, height);
    bar.style.height = height + "%";

    if (j === sample.length - 1) {
      bar.style.background = "var(--accent)";
    }

    container.appendChild(bar);
  }
}


function renderBloodworkPanels(master) {
  var container = document.getElementById("bloodwork-panels");
  container.innerHTML = "";

  var panels = [
    { label: "ferritin", value: master.bloodwork.kinetics.iron.final_ferritin, unit: "ng/ml" },
    { label: "ck peak", value: master.bloodwork.kinetics.inflammation.peak_ck, unit: "u/l" },
    { label: "hs-crp", value: master.bloodwork.kinetics.inflammation.recovery_status.hscrp_level, unit: "mg/l" },
    { label: "homa-ir", value: master.bloodwork.kinetics.metabolic.homa_ir, unit: "" },
    { label: "glucose auc", value: master.bloodwork.kinetics.metabolic.glucose_auc, unit: "" },
    { label: "ft:c status", value: master.bloodwork.kinetics.hormones.ftc_ratio_status.status.replace(/_/g, " "), unit: "" },
  ];

  for (var i = 0; i < panels.length; i++) {
    var card = document.createElement("div");
    card.className = "mini-card";

    var val = panels[i].value;
    if (typeof val === "number") {
      val = val.toFixed(1);
    }

    card.innerHTML =
      '<div class="value">' + val + '</div>' +
      '<div class="label">' + panels[i].label + (panels[i].unit ? " (" + panels[i].unit + ")" : "") + '</div>';
    container.appendChild(card);
  }
}

function renderBiomechanics(master) {
  var bio = master.biomechanics;
  if (!bio) return;

  var scoreEl = document.getElementById("biomech-score");
  scoreEl.textContent = bio.biomechanics_composite_score;
  applyColorClass(scoreEl, bio.biomechanics_composite_score, true);

  document.getElementById("biomech-protocol").textContent = 
    bio.protocol_recommendation.replace(/_/g, " ");

  var components = bio.component_scores || {};
  
  var seqEl = document.getElementById("bio-seq");
  seqEl.textContent = components.temporal_sequencing;
  applyColorClass(seqEl, components.temporal_sequencing, true);

  var blkEl = document.getElementById("bio-blk");
  blkEl.textContent = components.block_mechanics;
  applyColorClass(blkEl, components.block_mechanics, true);

  var aerEl = document.getElementById("bio-aer");
  aerEl.textContent = components.lever_aerodynamic;
  applyColorClass(aerEl, components.lever_aerodynamic, true);

  var pwrEl = document.getElementById("bio-pwr");
  pwrEl.textContent = components.power_profiler;
  applyColorClass(pwrEl, components.power_profiler, true);

  var degEl = document.getElementById("bio-deg");
  degEl.textContent = components.technique_degradation;
  applyColorClass(degEl, components.technique_degradation, true);

  var listEl = document.getElementById("biomech-flags-list");
  listEl.innerHTML = "";

  var flags = bio.flags || [];
  for (var i = 0; i < flags.length; i++) {
    var item = flags[i];
    var li = document.createElement("li");
    li.className = "intervention-item";

    li.innerHTML =
      '<div class="intervention-dot"></div>' +
      '<div class="intervention-content">' +
        '<div class="intervention-trigger text-critical">' + item.issue.replace(/_/g, " ") + ' (' + item.source.replace(/_/g, " ") + ')</div>' +
        '<div class="intervention-action">' + item.detail + '</div>' +
      '</div>';
    listEl.appendChild(li);
  }
}


function renderTravelImpact(master) {
  var tdi = master.travel.components.degradation.tdi;
  var thermo = master.travel.components.thermoregulatory;

  var tdiEl = document.getElementById("tdi-percent");
  tdiEl.textContent = tdi.tdi_percent + "%";
  applyColorClass(tdiEl, tdi.tdi_percent, false);

  var hypEl = document.getElementById("tax-hypoxic");
  hypEl.textContent = (tdi.hypoxic_tax * 100).toFixed(1) + "%";
  applyColorClass(hypEl, tdi.hypoxic_tax * 100, false);

  var kinEl = document.getElementById("tax-kinematic");
  kinEl.textContent = (tdi.kinematic_tax * 100).toFixed(1) + "%";
  applyColorClass(kinEl, tdi.kinematic_tax * 100, false);

  var cirEl = document.getElementById("tax-circadian");
  cirEl.textContent = (tdi.circadian_tax * 100).toFixed(1) + "%";
  applyColorClass(cirEl, tdi.circadian_tax * 100, false);

  var pwrEl = document.getElementById("power-percent");
  pwrEl.textContent = thermo.expected_power_percent + "%";
  applyColorClass(pwrEl, thermo.expected_power_percent, true);
  document.getElementById("ewbgt").textContent = thermo.ewbgt + "°";
  document.getElementById("core-temp").textContent = thermo.estimated_core_temp + "°";
  document.getElementById("acclimation").textContent = thermo.acclimation_factor;

  var listEl = document.getElementById("interventions-list");
  listEl.innerHTML = "";

  var interventions = master.travel.components.degradation.interventions || [];
  for (var i = 0; i < interventions.length; i++) {
    var item = interventions[i];
    var li = document.createElement("li");
    li.className = "intervention-item";

    var dotClass = item.priority === "standard" ? "standard" : "";

    li.innerHTML =
      '<div class="intervention-dot ' + dotClass + '"></div>' +
      '<div class="intervention-content">' +
        '<div class="intervention-trigger">' + item.trigger.replace(/_/g, " ") + '</div>' +
        '<div class="intervention-action">' + item.action + '</div>' +
      '</div>';
    listEl.appendChild(li);
  }
}


function renderCircadian(master) {
  var circadian = master.travel.components.circadian;

  document.getElementById("circadian-direction").textContent = circadian.direction;
  document.getElementById("circadian-days").textContent = circadian.total_adaptation_days;

  var container = document.getElementById("circadian-timeline");
  container.innerHTML = "";

  var schedule = circadian.daily_schedule || [];

  for (var i = 0; i < schedule.length; i++) {
    var day = schedule[i];
    var el = document.createElement("div");
    el.className = "timeline-day";

    var tmin = day.tmin_current;
    var tminStr = formatHour(tmin);

    el.innerHTML =
      '<div class="day-num">day ' + day.day + '</div>' +
      '<div class="day-label">shift ' + (day.shift_details.total_shift_hours > 0 ? "+" : "") +
        day.shift_details.total_shift_hours + 'h</div>' +
      '<div class="day-tmin">tmin ' + tminStr + '</div>';
    container.appendChild(el);
  }
}


function formatHour(h) {
  while (h < 0) h += 24;
  while (h >= 24) h -= 24;
  var hours = Math.floor(h);
  var minutes = Math.round((h - hours) * 60);
  var suffix = hours >= 12 ? "pm" : "am";
  var display = hours % 12;
  if (display === 0) display = 12;
  if (minutes === 0) return display + suffix;
  return display + ":" + (minutes < 10 ? "0" : "") + minutes + suffix;
}


function renderAI(recs) {
  var container = document.getElementById("ai-content");

  if (recs.error) {
    container.textContent = "no recommendations available. run the pipeline with a gemini api key.";
    return;
  }

  var text = recs.recommendations || "";
  document.getElementById("ai-model").textContent = "gemini-2.5-flash";

  var paragraphs = text.split("\n\n");
  var html = "";
  for (var i = 0; i < paragraphs.length; i++) {
    var p = paragraphs[i].trim();
    if (p.length === 0) continue;
    html += "<p>" + escapeHtml(p) + "</p>";
  }
  container.innerHTML = html;
}


function escapeHtml(str) {
  var div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function applyColorClass(element, value, isHigherBetter) {
  element.classList.remove("text-critical", "text-warning", "text-good");
  var num = parseFloat(value);
  if (isNaN(num)) return;
  
  if (isHigherBetter) {
    if (num < 50) element.classList.add("text-critical");
    else if (num < 80) element.classList.add("text-warning");
    else element.classList.add("text-good");
  } else {
    if (num > 50) element.classList.add("text-critical");
    else if (num > 20) element.classList.add("text-warning");
    else element.classList.add("text-good");
  }
}
