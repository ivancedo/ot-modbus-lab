// --- station physics: one step() per second, straight from the slaves ---
const STATIONS = [
  {
    key: "conveyor", name: "Conveyor", ip: "172.20.0.10",
    role: "Brings the part into the cell", unit: "%",
    pv: 0, coils: { MOTOR: false },
    step(on) { this.pv = clamp(this.pv + (on.MOTOR ? 5 : -10), 0, 100); },
    flags() { return [{ name: "IN_PLACE", on: this.pv >= 99 }]; },
  },
  {
    key: "temperature", name: "Temperature", ip: "172.20.0.11",
    role: "Part temperature sensor", unit: "°C",
    pv: 20, coils: { HEAT: false },
    step(on) { this.pv = clamp(this.pv + (on.HEAT ? 2 : -1), 20, 80); },
    flags() { return [{ name: "AT_TEMP", on: this.pv >= 70 }]; },
    hot: true,
  },
  {
    key: "heater", name: "Heater", ip: "172.20.0.12",
    role: "Heating element output", unit: "%",
    pv: 0, coils: { ENABLE: false },
    step(on) { this.pv = clamp(this.pv + (on.ENABLE ? 10 : -20), 0, 100); },
    flags() { return [{ name: "HOT", on: this.pv >= 90 }]; },
    hot: true,
  },
  {
    key: "pressure", name: "Pressure", ip: "172.20.0.13",
    role: "Sealed vessel sensor", unit: "kPa", max: 250,
    pv: 0, coils: { BUILD: false, VENT: false },
    step(on) {
      // VENT always wins over BUILD; with neither, it leaks down slowly.
      const d = on.VENT ? -10 : on.BUILD ? 6 : -1;
      this.pv = clamp(this.pv + d, 0, 250);
    },
    flags() {
      return [
        { name: "AT_PRESSURE", on: this.pv >= 150 },
        { name: "OVERPRESSURE", on: this.pv >= 200, alarm: true },
      ];
    },
  },
  {
    key: "relief", name: "Relief Valve", ip: "172.20.0.14",
    role: "Releases the vessel", unit: "%",
    pv: 0, coils: { OPEN: false },
    step(on) { this.pv = clamp(this.pv + (on.OPEN ? 20 : -20), 0, 100); },
    flags() { return [{ name: "VENTED", on: this.pv >= 90 }]; },
  },
];

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

// --- controller: the recipe state machine, from master.py ---
const RECIPE = {
  IDLE:         { conveyor: { MOTOR: true } },
  HEATING:      { heater: { ENABLE: true }, temperature: { HEAT: true } },
  PRESSURIZING: { heater: { ENABLE: true }, temperature: { HEAT: true },
                  pressure: { BUILD: true } },
  RELEASE:      { pressure: { VENT: true }, relief: { OPEN: true } },
};

function advance(state, pv) {
  if (state === "IDLE" && pv.conveyor >= 99) return "HEATING";
  if (state === "HEATING" && pv.temperature >= 70) return "PRESSURIZING";
  if (state === "PRESSURIZING" && pv.pressure >= 150) return "RELEASE";
  if (state === "RELEASE" && pv.pressure <= 10) return "IDLE";
  return state;
}

// --- running state ---
let state = "IDLE";
let batches = 0;
let timer = null;

function tick() {
  // Controller drives each coil to what the current state calls for.
  const wanted = RECIPE[state] || {};
  for (const s of STATIONS) {
    for (const coil in s.coils) {
      s.coils[coil] = !!(wanted[s.key] && wanted[s.key][coil]);
    }
  }

  // Each station advances one step under those commands.
  for (const s of STATIONS) s.step(s.coils);

  // Move the recipe forward when the stage we're waiting on crosses its line.
  const pv = {};
  for (const s of STATIONS) pv[s.key] = s.pv;
  const next = advance(state, pv);
  if (state === "RELEASE" && next === "IDLE") batches++;
  state = next;

  render();
}

// --- rendering ---
const line = document.getElementById("stationLine");

function build() {
  line.innerHTML = "";
  for (const s of STATIONS) {
    const card = document.createElement("div");
    card.className = "card";
    card.id = "card-" + s.key;
    card.innerHTML = `
      <div class="card-head">
        <h2>${s.name}</h2><span class="ip">${s.ip}</span>
      </div>
      <p class="role">${s.role}</p>
      <div class="reading">
        <span class="val" data-val>0</span><span class="unit">${s.unit}</span>
      </div>
      <div class="bar${s.hot ? " hot" : ""}"><i data-bar></i></div>
      <div class="tags" data-tags></div>`;
    line.appendChild(card);
  }
}

function render() {
  // Recipe steps
  document.querySelectorAll(".step").forEach(el =>
    el.classList.toggle("active", el.dataset.state === state));
  document.getElementById("batchCount").textContent = batches;

  for (const s of STATIONS) {
    const card = document.getElementById("card-" + s.key);
    const anyCoil = Object.values(s.coils).some(Boolean);
    card.classList.toggle("live", anyCoil);

    card.querySelector("[data-val]").textContent = Math.round(s.pv);
    const pct = (s.pv / (s.max || 100)) * 100;
    card.querySelector("[data-bar]").style.width = pct + "%";

    const tags = card.querySelector("[data-tags]");
    tags.innerHTML = "";
    for (const coil in s.coils) {
      tags.appendChild(tag(coil, s.coils[coil] ? "coil-on" : ""));
    }
    for (const f of s.flags()) {
      let cls = f.on ? "flag-on" : "";
      if (f.on && f.alarm) cls += " alarm";
      tags.appendChild(tag(f.name, cls));
    }
  }
}

function tag(text, cls) {
  const el = document.createElement("span");
  el.className = "tag " + cls;
  el.textContent = text;
  return el;
}

// --- controls ---
const playBtn = document.getElementById("playBtn");
const speedSel = document.getElementById("speedSel");

function start() {
  stop();
  timer = setInterval(tick, Number(speedSel.value));
  playBtn.textContent = "Pause";
}
function stop() {
  if (timer) clearInterval(timer);
  timer = null;
}

playBtn.onclick = () => {
  if (timer) { stop(); playBtn.textContent = "Resume"; }
  else start();
};
speedSel.onchange = () => { if (timer) start(); };
document.getElementById("resetBtn").onclick = () => {
  state = "IDLE"; batches = 0;
  STATIONS[0].pv = 0; STATIONS[1].pv = 20; STATIONS[2].pv = 0;
  STATIONS[3].pv = 0; STATIONS[4].pv = 0;
  for (const s of STATIONS) for (const c in s.coils) s.coils[c] = false;
  render();
};

build();
render();
start();
