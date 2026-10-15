import logging
import threading

from flask import Flask, jsonify, render_template_string, request
from pymodbus.client import ModbusTcpClient

# Professional log format shared by every component: wall-clock timestamp,
# fixed-width level, logger name, then the message.
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-11s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt=DATE_FORMAT)

# The werkzeug dev server logs one access line per request. The browser polls
# /api/state every 2s, which otherwise drowns the log. Keep only warnings/errors
# (4xx/5xx) from it; our own handlers log the events that actually matter.
logging.getLogger("werkzeug").setLevel(logging.WARNING)

log = logging.getLogger("hmi.web")

PLC_HOST = "172.20.0.10"    # MODBUS/TCP server address
PLC_PORT = 502              # MODBUS/TCP port
WEB_PORT = 8080             # HTTP port for the control panel
TANK_CAPACITY_L = 1000      # Tank capacity, for % <-> litres conversion

app = Flask(__name__)
client = ModbusTcpClient(PLC_HOST, port=PLC_PORT)
lock = threading.Lock()     # Guards the shared Modbus client
_plc_online = None          # Tracks PLC link state so we only log on change


def _set_plc_online(online: bool, detail: str = "") -> None:
    # Log PLC link up/down transitions once, not on every poll.
    global _plc_online
    if online != _plc_online:
        if online:
            log.info("PLC link UP (%s:%d)", PLC_HOST, PLC_PORT)
        else:
            log.error("PLC link DOWN (%s:%d)%s", PLC_HOST, PLC_PORT,
                      f": {detail}" if detail else "")
        _plc_online = online


PAGE = """
<!doctype html>
<title>Water Tank HMI</title>
<style>
  :root { --water: #29b6f6; --bg: #0f1724; --panel: #1b2636; --line: #2b3a50;
          --text: #e6edf5; --muted: #8aa0bd; --accent: #29b6f6; }
  * { box-sizing: border-box; }
  body { font-family: "Segoe UI", system-ui, sans-serif; margin: 0;
         background: var(--bg); color: var(--text); }
  .wrap { max-width: 640px; margin: 0 auto; padding: 24px 16px; }
  header { display: flex; align-items: center; justify-content: space-between;
           border-bottom: 1px solid var(--line); padding-bottom: 12px; margin-bottom: 20px; }
  header h1 { font-size: 1.15em; letter-spacing: 1px; margin: 0; font-weight: 600; }
  header .dev { color: var(--muted); font-size: .8em; }
  .hmi { display: flex; gap: 24px; }
  .tank { height: 320px; width: 170px; flex: none; position: relative;
          border: 2px solid var(--line); border-radius: 12px; overflow: hidden;
          background: linear-gradient(#0b121d, #131d2b); }
  .ticks { position: absolute; inset: 0; z-index: 2; pointer-events: none; }
  .ticks span { position: absolute; right: 6px; font-size: .7em; color: var(--muted);
                transform: translateY(-50%); }
  .ticks i { position: absolute; left: 0; width: 10px; height: 1px; background: var(--line); }
  .water { position: absolute; bottom: 0; width: 100%; background: var(--water);
           opacity: .85; transition: height .6s, background .6s; }
  .water::before, .water::after {
           content: ""; position: absolute; top: -10px; left: -50%;
           width: 200%; height: 20px; border-radius: 45%; background: var(--water); }
  .water::before { animation: wave 4s linear infinite; opacity: .6; }
  .water::after  { animation: wave 7s linear infinite; }
  @keyframes wave { from { transform: translateX(0); } to { transform: translateX(50%); } }
  .panel { flex: 1; display: flex; flex-direction: column; gap: 14px; }
  .card { background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
          padding: 12px 16px; }
  .card .label { color: var(--muted); font-size: .72em; letter-spacing: 1.5px; }
  .card .value { font-size: 2em; font-weight: 700; font-variant-numeric: tabular-nums; }
  .card .value u { font-size: .45em; color: var(--muted); text-decoration: none; margin-left: 4px; }
  .card .sub { color: var(--muted); font-size: 1em; font-variant-numeric: tabular-nums; }
  .flow.up .value { color: #3ddc84; }
  .flow.down .value { color: #ff5c6c; }
  .alarms { display: flex; gap: 12px; }
  .lamp { flex: 1; display: flex; align-items: center; gap: 8px;
          background: var(--panel); border: 1px solid var(--line);
          border-radius: 10px; padding: 12px 14px; font-weight: 600; font-size: .85em; }
  .lamp .dot { width: 12px; height: 12px; border-radius: 50%; background: #39465c; }
  .lamp.on { color: #fff; }
  .lamp.on .dot { background: #ff5c6c; box-shadow: 0 0 10px #ff5c6c;
                  animation: blink 1s steps(2) infinite; }
  @keyframes blink { 50% { opacity: .3; } }
  .controls { display: flex; gap: 12px; margin-top: 20px; }
  .switch { flex: 1; display: flex; align-items: center; justify-content: space-between;
            background: var(--panel); border: 1px solid var(--line);
            border-radius: 10px; padding: 14px 16px; font-weight: 600; }
  .switch input { display: none; }
  .slider { width: 50px; height: 26px; background: #39465c; border-radius: 26px;
            position: relative; transition: background .2s; cursor: pointer; }
  .slider::before { content: ""; position: absolute; top: 3px; left: 3px;
            width: 20px; height: 20px; background: #fff; border-radius: 50%;
            transition: transform .2s; }
  input:checked + .slider { background: var(--accent); }
  input:checked + .slider::before { transform: translateX(24px); }
</style>
<div class="wrap">
  <header>
    <h1>WATER TANK &mdash; HMI</h1>
    <span class="dev">PLC 172.20.0.10 &middot; Modbus/TCP</span>
  </header>
  <div class="hmi">
    <div class="tank">
      <div class="ticks">
        <i style="top:10%"></i><span style="top:10%">75%</span>
        <i style="top:50%"></i><span style="top:50%">50%</span>
        <i style="top:90%"></i><span style="top:90%">25%</span>
      </div>
      <div class="water" id="water"></div>
    </div>
    <div class="panel">
      <div class="card">
        <div class="label">WATER LEVEL</div>
        <div class="value"><span id="level-pct">-</span><u>%</u></div>
        <div class="sub"><span id="level-l">-</span> L</div>
      </div>
      <div class="card" id="flow-box">
        <div class="label">WATER FLOW</div>
        <div class="value"><span id="flow-pct">-</span><u>%/s</u></div>
        <div class="sub"><span id="flow-l">-</span> L/s</div>
      </div>
      <div class="alarms">
        <div class="lamp" id="low"><span class="dot"></span>LOW LEVEL</div>
        <div class="lamp" id="high"><span class="dot"></span>HIGH LEVEL</div>
      </div>
    </div>
  </div>
  <div class="controls">
    <label class="switch">PUMP
      <input type="checkbox" id="sw-pump" onchange="setCoil(0, this.checked)">
      <span class="slider"></span>
    </label>
    <label class="switch">FAUCET
      <input type="checkbox" id="sw-faucet" onchange="setCoil(1, this.checked)">
      <span class="slider"></span>
    </label>
  </div>
</div>
<script>
const sign = v => (v > 0 ? "+" : "") + v;
async function refresh() {
  const r = await fetch("/api/state");
  if (!r.ok) return;
  const s = await r.json();
  water.style.height = s.level_pct + "%";
  water.style.setProperty("--water",
    s.high_alarm ? "#ff5c6c" : s.low_alarm ? "#ffa726" : "#29b6f6");
  document.getElementById("level-pct").textContent = s.level_pct.toFixed(1);
  document.getElementById("level-l").textContent = s.level_l.toFixed(0);
  document.getElementById("flow-pct").textContent = sign(s.flow_pct_s.toFixed(2));
  document.getElementById("flow-l").textContent = sign(s.flow_l_s.toFixed(1));
  document.getElementById("flow-box").className =
    "card flow" + (s.flow_pct_s > 0 ? " up" : s.flow_pct_s < 0 ? " down" : "");
  document.getElementById("low").classList.toggle("on", s.low_alarm);
  document.getElementById("high").classList.toggle("on", s.high_alarm);
  document.getElementById("sw-pump").checked = s.pump;
  document.getElementById("sw-faucet").checked = s.faucet;
}
function setCoil(addr, on) {
  fetch("/api/coil/" + addr, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({on}),
  }).then(refresh);
}
refresh();
setInterval(refresh, 2000);
</script>
"""


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/api/state")
def state():
    # Read IR0, IR1, DI0, DI1 and CO0, CO1 (one HMI scan)
    with lock:
        if not client.connect():
            _set_plc_online(False, "connect failed")
            return jsonify(error="PLC unreachable"), 502
        rr_ir = client.read_input_registers(0, 2)
        rr_di = client.read_discrete_inputs(0, 2)
        rr_co = client.read_coils(0, 2)

    if rr_ir.isError() or rr_di.isError() or rr_co.isError():
        _set_plc_online(False, "read error")
        log.warning("PLC read error: ir=%s di=%s co=%s", rr_ir, rr_di, rr_co)
        return jsonify(error="PLC read error"), 502

    _set_plc_online(True)

    # Flow rate is a 16-bit signed value in 0.01%/s (negative = net draining)
    raw_flow = rr_ir.registers[1]
    if raw_flow >= 32768:
        raw_flow -= 65536

    level_pct = rr_ir.registers[0] / 10.0
    flow_pct_s = raw_flow / 100.0

    return jsonify(
        level_pct=level_pct,
        level_l=level_pct / 100.0 * TANK_CAPACITY_L,
        flow_pct_s=flow_pct_s,
        flow_l_s=flow_pct_s / 100.0 * TANK_CAPACITY_L,
        pump=bool(rr_co.bits[0]),
        faucet=bool(rr_co.bits[1]),
        low_alarm=bool(rr_di.bits[0]),
        high_alarm=bool(rr_di.bits[1]),
    )


COIL_NAMES = {0: "PUMP", 1: "FAUCET"}


@app.route("/api/coil/<int:addr>", methods=["POST"])
def set_coil(addr):
    # Turn a coil ON/OFF: CO0 = pump, CO1 = faucet
    on = bool(request.json.get("on", False))
    name = COIL_NAMES.get(addr, f"CO{addr}")
    src = request.remote_addr or "?"
    with lock:
        if not client.connect():
            _set_plc_online(False, "connect failed")
            log.error("Operator command FAILED (PLC unreachable): %s -> %s",
                      name, "ON" if on else "OFF")
            return jsonify(error="PLC unreachable"), 502
        rq = client.write_coil(addr, on)
    if rq.isError():
        log.error("Operator command FAILED: %s -> %s (%s)",
                  name, "ON" if on else "OFF", rq)
        return jsonify(error="write failed"), 502
    log.info("Operator command: %s -> %s  (coil %d, from %s)",
             name, "ON" if on else "OFF", addr, src)
    return jsonify(ok=True)


if __name__ == "__main__":
    log.info("=" * 60)
    log.info("Water-Tank HMI  (web control panel)")
    log.info("  serving on http://0.0.0.0:%d", WEB_PORT)
    log.info("  PLC backend %s:%d  (Modbus/TCP)", PLC_HOST, PLC_PORT)
    log.info("=" * 60)
    app.run(host="0.0.0.0", port=WEB_PORT)
