import streamlit as st
import time
import os
import sys
import subprocess
import zmq
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime
import psutil

# Optional docker import
try:
    import docker
    _DOCKER_AVAILABLE = True
except ImportError:
    _DOCKER_AVAILABLE = False

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="GangaMitra - River Cleaning Robot Simulation",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    .stApp { background-color: #0a1a2f; }
    .main-header {
        font-size: 3rem; color: #4ecdc4; text-align: center;
        padding: 1rem; background: linear-gradient(90deg, #1a3a5f, #0a1a2f);
        border-radius: 10px; margin-bottom: 2rem;
    }
    .status-box {
        padding: 1rem; border-radius: 10px; background-color: #1e3a5f;
        border-left: 5px solid #4ecdc4; margin: 1rem 0;
    }
    .metric-card {
        background-color: #1e3a5f; padding: 1rem; border-radius: 10px;
        text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .metric-value { font-size: 2rem; font-weight: bold; color: #4ecdc4; }
    .metric-label { color: #a0b8cc; font-size: 0.9rem; }
    .log-container {
        background-color: #0d2b3e; padding: 1rem; border-radius: 10px;
        height: 300px; overflow-y: auto; font-family: monospace; font-size: 0.9rem;
    }
    .success-badge { background-color: #27ae60; color: white; padding: 0.2rem 0.5rem; border-radius: 5px; font-size: 0.8rem; }
    .warning-badge { background-color: #f39c12; color: white; padding: 0.2rem 0.5rem; border-radius: 5px; font-size: 0.8rem; }
    .error-badge   { background-color: #e74c3c; color: white; padding: 0.2rem 0.5rem; border-radius: 5px; font-size: 0.8rem; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session-state initialisation
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "processes": {},            # name -> Popen
    "process_pids": {},         # name -> pid  (survives Streamlit serialisation)
    "running": False,
    "logs": [],
    "docker_available": False,
    "docker_client": None,
    "live_metrics": {
        "frame": 0,
        "debris_count": 0,
        "latency_ms": 0,
        "avg_traversability": 0.0,
    },
    "metrics_history": {
        "timestamps": [],
        "latency": [],
        "debris_count": [],
        "fps": [],
        "traversability": [],
    },
}

for key, default in _DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Docker check (only once)
if _DOCKER_AVAILABLE and st.session_state.docker_client is None:
    try:
        st.session_state.docker_client = docker.from_env()
        st.session_state.docker_client.ping()
        st.session_state.docker_available = True
    except Exception:
        st.session_state.docker_available = False

# ---------------------------------------------------------------------------
# Helper – resolve script paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def _script(name):
    """Return the absolute path to a sibling script."""
    return os.path.join(SCRIPT_DIR, name)

# Map terrain-mode labels to the correct script files
SIM_SCRIPTS = {
    "Real-time (Generator)": "simulation_with_robot.py",
    "Smooth Morphing": os.path.join("useless trials", "test1_smooth_morphing.py"),
    "Strip-based Progressive": os.path.join("useless trials", "test2_strip_terrain.py"),
}

# ---------------------------------------------------------------------------
# Process management helpers
# ---------------------------------------------------------------------------
def _add_log(component, message, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.logs.append(f"[{ts}] [{level}] [{component}] {message}")
    # keep last 200 entries
    if len(st.session_state.logs) > 200:
        st.session_state.logs = st.session_state.logs[-200:]


def _is_running(name):
    """Check whether a managed subprocess is still alive."""
    pid = st.session_state.process_pids.get(name)
    if pid is None:
        return False
    try:
        proc = psutil.Process(pid)
        return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def _start_process(name, cmd):
    """Launch a subprocess and track it."""
    if _is_running(name):
        _add_log(name, "Already running - skipping", "WARNING")
        return
    try:
        # Log the command we're about to run
        _add_log(name, f"Launching: {' '.join(cmd)}", "DEBUG")
        kwargs = dict(
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            cwd=SCRIPT_DIR,
        )
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        proc = subprocess.Popen(cmd, **kwargs)
        st.session_state.processes[name] = proc
        st.session_state.process_pids[name] = proc.pid
        _add_log(name, f"Started (PID {proc.pid})")
        
        # Check if process died immediately
        time.sleep(0.1)
        if proc.poll() is not None:
            # Process has already exited
            stdout_data = proc.stdout.read() if proc.stdout else ''
            _add_log(name, f"Process died immediately! Exit code: {proc.returncode}", "ERROR")
            if stdout_data.strip():
                for line in stdout_data.strip().split('\n')[:5]:  # First 5 lines
                    _add_log(name, f"  {line}", "ERROR")
    except Exception as e:
        _add_log(name, f"Failed to start: {e}", "ERROR")


def _stop_process(name):
    """Kill a managed subprocess tree."""
    pid = st.session_state.process_pids.get(name)
    if pid is None:
        return
    try:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            child.kill()
        parent.kill()
        _add_log(name, "Stopped")
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    st.session_state.processes.pop(name, None)
    st.session_state.process_pids.pop(name, None)


def _stop_all():
    """Stop all managed processes and free ZMQ ports."""
    for name in list(st.session_state.process_pids.keys()):
        _stop_process(name)
    # Also stop Docker pathway container if running
    if st.session_state.docker_available and st.session_state.docker_client:
        try:
            for c in st.session_state.docker_client.containers.list():
                if "gangamitra" in c.name.lower():
                    c.stop(timeout=3)
                    _add_log("Pathway", "Docker container stopped")
        except Exception:
            pass
    
    # Kill any orphaned Python processes still holding ZMQ ports
    try:
        import socket
        for port in [5555, 5556, 5557]:
            try:
                # Try to connect - if it fails, port is free
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.1)
                result = sock.connect_ex(('localhost', port))
                sock.close()
                
                if result == 0:  # Port is in use
                    # Find and kill the process
                    for proc in psutil.process_iter(['pid', 'name', 'connections']):
                        try:
                            if proc.info['name'] == 'python.exe' or proc.info['name'] == 'python':
                                connections = proc.connections()
                                for conn in connections:
                                    if hasattr(conn, 'laddr') and conn.laddr.port == port:
                                        _add_log("System", f"Killing orphaned process on port {port} (PID {proc.pid})", "WARNING")
                                        proc.kill()
                                        break
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
            except Exception:
                pass
    except Exception as e:
        _add_log("System", f"Port cleanup warning: {e}", "WARNING")
    
    st.session_state.running = False


def start_all(components, terrain_mode):
    """Start the selected components."""
    _stop_all()  # clean slate - includes port cleanup
    time.sleep(0.5)  # Give ports time to be released

    python = sys.executable

    # 1. Generator
    if components.get("generator"):
        _start_process("Generator", [python, _script("generator.py")])

    # 2. Pathway pipeline
    if components.get("pathway"):
        if st.session_state.docker_available and st.session_state.docker_client:
            try:
                st.session_state.docker_client.containers.run(
                    "gangamitra-pathway",
                    detach=True,
                    name="gangamitra-pathway",
                    ports={"5556/tcp": 5556, "5557/tcp": 5557},
                    remove=True,
                )
                _add_log("Pathway", "Docker container started")
            except Exception as e:
                _add_log("Pathway", f"Docker failed ({e}), falling back to local", "WARNING")
                _start_process("Pathway", [python, _script("pathway_pipeline.py")])
        else:
            _start_process("Pathway", [python, _script("pathway_pipeline.py")])

    # 3. Simulator
    if components.get("simulator"):
        sim_script = SIM_SCRIPTS.get(terrain_mode, "simulation_with_robot.py")
        _start_process("Simulator", [python, _script(sim_script)])

    # 4. Dashboard (matplotlib-based live dashboard)
    if components.get("dashboard"):
        _start_process("Dashboard", [python, _script("dashboard.py")])

    st.session_state.running = True
    _add_log("System", "All selected components started")


# ---------------------------------------------------------------------------
# ZMQ helpers – poll live metrics from pathway dashboard port (5557)
# ---------------------------------------------------------------------------
@st.cache_resource
def _zmq_context():
    return zmq.Context()


def _poll_metrics():
    """Non-blocking poll onto ZMQ ports for fresh data."""
    ctx = _zmq_context()

    # Dashboard metrics from pathway (port 5557)
    try:
        sock = ctx.socket(zmq.SUB)
        sock.setsockopt(zmq.CONFLATE, 1)          # keep only latest
        sock.setsockopt_string(zmq.SUBSCRIBE, "")
        sock.RCVTIMEO = 300                         # ms
        sock.connect("tcp://localhost:5557")
        msg = sock.recv_json()
        sock.close()

        st.session_state.live_metrics["frame"] = msg.get("sequence_id", 0)
        st.session_state.live_metrics["debris_count"] = msg.get("debris_count", 0)
        st.session_state.live_metrics["latency_ms"] = round(msg.get("latency_ms", 0), 1)
        st.session_state.live_metrics["avg_traversability"] = round(
            msg.get("avg_traversability", 0), 2
        )

        # Append to history
        h = st.session_state.metrics_history
        h["timestamps"].append(msg.get("sequence_id", len(h["timestamps"])))
        h["latency"].append(msg.get("latency_ms", 0))
        h["debris_count"].append(msg.get("debris_count", 0))
        h["fps"].append(msg.get("compute_time_ms", 0))
        h["traversability"].append(msg.get("avg_traversability", 0))

        # Cap at 200
        for k in h:
            if len(h[k]) > 200:
                h[k] = h[k][-200:]

        return True
    except zmq.Again:
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown('<div class="main-header">🌊 GangaMitra Control Center</div>', unsafe_allow_html=True)

# Component names used across the app
comp_names = ["Generator", "Pathway", "Simulator", "Dashboard"]

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🎮 Control Panel")

    # Component selection
    st.markdown("### Components")
    run_generator = st.checkbox("Generator", value=True, key="gen_check")
    run_pathway   = st.checkbox("Pathway Pipeline", value=True, key="path_check")
    run_simulator = st.checkbox("Simulator", value=True, key="sim_check")
    run_dashboard = st.checkbox("Dashboard", value=True, key="dash_check")

    # Mode selection
    st.markdown("### Simulation Mode")
    terrain_mode = st.selectbox(
        "Terrain Update Mode",
        list(SIM_SCRIPTS.keys()),
    )

    # Robot control
    st.markdown("### Robot Control")
    robot_speed = st.slider("Speed", 0.0, 3.0, 1.5)
    robot_control = st.radio("Control Mode", ["Manual (Arrow Keys)", "Auto Navigate", "Follow Path"])

    # Actions
    st.markdown("### Actions")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 Start All", type="primary"):
            with st.spinner("Starting components..."):
                components = {
                    "generator": run_generator,
                    "pathway": run_pathway,
                    "simulator": run_simulator,
                    "dashboard": run_dashboard,
                }
                start_all(components, terrain_mode)
                time.sleep(0.5)  # Give processes a moment to start
            
            # Count how many actually started
            started = sum(1 for name in comp_names if _is_running(name))
            selected = sum(components.values())
            
            if started > 0:
                st.success(f"✓ Started {started}/{selected} components. Check Logs tab for details.")
            else:
                st.error("❌ Failed to start components. Check Logs tab for errors.")
            
            time.sleep(1)  # Show the message briefly
            st.rerun()
    with col2:
        if st.button("🛑 Stop All"):
            _stop_all()
            st.rerun()

    # Docker status
    st.markdown("### 🐳 Docker Status")
    if st.session_state.docker_available:
        st.markdown('<span class="success-badge">✓ Docker Running</span>', unsafe_allow_html=True)
        try:
            containers = st.session_state.docker_client.containers.list()
            st.write(f"Active containers: {len(containers)}")
        except Exception:
            st.write("Could not list containers")
    else:
        reason = "package not installed" if not _DOCKER_AVAILABLE else "daemon not reachable"
        st.markdown(f'<span class="warning-badge">⚠ Docker Not Available ({reason})</span>', unsafe_allow_html=True)

    # System stats
    st.markdown("### 💻 System Stats")
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    st.progress(cpu_percent / 100, text=f"CPU: {cpu_percent}%")
    st.progress(memory.percent / 100, text=f"Memory: {memory.percent}%")

# ---------------------------------------------------------------------------
# Try to get fresh metrics from running pipeline
# ---------------------------------------------------------------------------
if st.session_state.running:
    _poll_metrics()

lm = st.session_state.live_metrics

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Live Dashboard",
    "🗺️ Terrain View",
    "🤖 Robot Simulator",
    "📈 Metrics",
    "📋 Logs",
])

# ======================================================================
# Tab 1 - Live Dashboard
# ======================================================================
with tab1:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            f'<div class="metric-card"><div class="metric-value">{lm["frame"]}</div>'
            f'<div class="metric-label">Current Frame</div></div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f'<div class="metric-card"><div class="metric-value">{lm["debris_count"]}</div>'
            f'<div class="metric-label">Debris Count</div></div>',
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f'<div class="metric-card"><div class="metric-value">{lm["latency_ms"]} ms</div>'
            f'<div class="metric-label">Latency</div></div>',
            unsafe_allow_html=True,
        )
    with col4:
        trav_pct = int(lm["avg_traversability"] * 100) if lm["avg_traversability"] else 0
        st.markdown(
            f'<div class="metric-card"><div class="metric-value">{trav_pct}%</div>'
            f'<div class="metric-label">Traversability</div></div>',
            unsafe_allow_html=True,
        )

    # Live metrics charts
    st.markdown("### 📈 Real-time Metrics")
    chart_placeholder = st.empty()

    h = st.session_state.metrics_history
    n = len(h["timestamps"])
    if n > 1:
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=("Processing Latency", "Debris Count", "Compute Time", "Traversability"),
        )
        xs = h["timestamps"][-50:]
        fig.add_trace(go.Scatter(x=xs, y=h["latency"][-50:],       mode="lines", name="Latency (ms)",    line=dict(color="#4ecdc4", width=2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=xs, y=h["debris_count"][-50:],  mode="lines", name="Debris",           line=dict(color="#ff6b6b", width=2)), row=1, col=2)
        fig.add_trace(go.Scatter(x=xs, y=h["fps"][-50:],           mode="lines", name="Compute (ms)",     line=dict(color="#feca57", width=2)), row=2, col=1)
        fig.add_trace(go.Scatter(x=xs, y=h["traversability"][-50:],mode="lines", name="Traversability",   line=dict(color="#48dbfb", width=2)), row=2, col=2)
        fig.update_layout(
            height=500, showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(30,58,95,0.3)",
            font=dict(color="white"),
        )
        fig.update_xaxes(gridcolor="rgba(255,255,255,0.1)")
        fig.update_yaxes(gridcolor="rgba(255,255,255,0.1)")
        chart_placeholder.plotly_chart(fig, use_container_width=True)
    else:
        chart_placeholder.info("Start the pipeline to see live charts.")

    # Component status
    st.markdown("### 🚦 Component Status")
    status_cols = st.columns(4)
    for i, name in enumerate(comp_names):
        with status_cols[i]:
            alive = _is_running(name)
            badge = "success-badge" if alive else "error-badge"
            icon = "🟢 Running" if alive else "⚫ Stopped"
            st.markdown(f"**{name}**<br><span class='{badge}'>{icon}</span>", unsafe_allow_html=True)

# ======================================================================
# Tab 2 - Terrain View
# ======================================================================
with tab2:
    st.markdown("### 🗺️ Terrain Visualization")

    view_col1, view_col2, view_col3 = st.columns(3)
    with view_col1:
        view_mode = st.selectbox("View Mode", ["3D Perspective", "Top-down 2D", "Height Map", "Traversability Heatmap"])
    with view_col2:
        show_water = st.checkbox("Show Water", True)
    with view_col3:
        show_grid = st.checkbox("Show Grid", False)

    if _is_running("Simulator"):
        st.success("Simulator is running - terrain is rendered in the PyBullet GUI window.")
    else:
        st.info("Start the Simulator component to see the terrain in PyBullet.")

# ======================================================================
# Tab 3 - Robot Simulator
# ======================================================================
with tab3:
    st.markdown("### 🤖 Robot Control & Visualization")

    control_col1, control_col2 = st.columns([1, 2])
    with control_col1:
        st.markdown("#### Manual Control")
        st.markdown("""
        Use the **PyBullet window** for real-time control:
        - **↑** Move Forward
        - **↓** Move Backward
        - **←** Turn Left
        - **→** Turn Right
        - **Space** Stop
        """)
        st.markdown("#### Auto Control")
        st.slider("Target Speed", 0.0, 2.0, 1.0, key="target_speed")
        st.selectbox("Navigation Mode", ["Goal Seeking", "Obstacle Avoidance", "Path Following"], key="nav_mode")
        if st.button("Reset Robot"):
            st.success("Robot reset signal sent (requires simulator restart)")

    with control_col2:
        if _is_running("Simulator"):
            st.success("Robot simulation is active in the PyBullet GUI window.")
        else:
            st.info("Start the Simulator to control the robot.")

    # Robot stats
    st.markdown("#### Robot Statistics")
    stat_cols = st.columns(5)
    stats = [
        ("Position X", "—"),
        ("Position Y", "—"),
        ("Speed", f"{robot_speed:.1f} m/s"),
        ("Terrain", "—"),
        ("Debris Hit", f"{lm.get('debris_count', 0)}"),
    ]
    for i, (label, value) in enumerate(stats):
        with stat_cols[i]:
            st.metric(label, value)

# ======================================================================
# Tab 4 - Advanced Metrics
# ======================================================================
with tab4:
    st.markdown("### 📊 Detailed Performance Metrics")

    time_range = st.select_slider("Time Range", options=["1 min", "5 min", "15 min", "30 min", "1 hour"])

    metric_tabs = st.tabs(["Pipeline Performance", "Robot Performance", "Terrain Statistics", "System Health"])

    with metric_tabs[0]:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Throughput")
            if h["latency"]:
                st.line_chart(pd.DataFrame({"Latency (ms)": h["latency"][-60:]}))
            else:
                st.info("No data yet.")
        with c2:
            st.markdown("#### Compute Time")
            if h["fps"]:
                st.line_chart(pd.DataFrame({"Compute (ms)": h["fps"][-60:]}))
            else:
                st.info("No data yet.")

    with metric_tabs[1]:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Path Efficiency")
            st.metric("Frames Processed", lm["frame"])
            st.metric("Avg Latency", f'{np.mean(h["latency"][-30:]):.1f} ms' if h["latency"] else "—")
        with c2:
            st.markdown("#### Interaction Metrics")
            st.metric("Debris Detected", lm["debris_count"])
            st.metric("Avg Traversability", f'{lm["avg_traversability"]:.2f}')

    with metric_tabs[2]:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Traversability Over Time")
            if h["traversability"]:
                st.line_chart(pd.DataFrame({"Traversability": h["traversability"][-60:]}))
            else:
                st.info("No data yet.")
        with c2:
            st.markdown("#### Debris Over Time")
            if h["debris_count"]:
                st.line_chart(pd.DataFrame({"Debris": h["debris_count"][-60:]}))
            else:
                st.info("No data yet.")

    with metric_tabs[3]:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Resource Usage")
            st.progress(psutil.cpu_percent() / 100, text=f"CPU: {psutil.cpu_percent()}%")
            mem = psutil.virtual_memory()
            st.progress(mem.percent / 100, text=f"Memory: {mem.percent}%")
        with c2:
            st.markdown("#### Component Health")
            for name in comp_names:
                icon = "✅" if _is_running(name) else "❌"
                st.markdown(f"{icon} {name}: {'Healthy' if _is_running(name) else 'Stopped'}")

# ======================================================================
# Tab 5 - Logs
# ======================================================================
with tab5:
    st.markdown("### 📋 System Logs")

    log_col1, log_col2, log_col3 = st.columns(3)
    with log_col1:
        log_level = st.selectbox("Log Level", ["ALL", "DEBUG", "INFO", "WARNING", "ERROR"])
    with log_col2:
        log_component = st.selectbox("Component", ["All", "Generator", "Pathway", "Simulator", "Dashboard", "System"])
    with log_col3:
        if st.button("Clear Logs"):
            st.session_state.logs = []
            st.rerun()

    # Collect stdout from running processes (last few lines)
    for name, proc in list(st.session_state.processes.items()):
        if proc and proc.stdout and proc.poll() is not None:
            try:
                remaining = proc.stdout.read()
                if remaining:
                    for line in remaining.strip().split("\n")[-5:]:
                        _add_log(name, line.strip())
            except Exception:
                pass

    # Filter and display
    filtered = st.session_state.logs
    if log_level != "ALL":
        filtered = [entry for entry in filtered if f"[{log_level}]" in entry]
    if log_component != "All":
        filtered = [entry for entry in filtered if f"[{log_component}]" in entry]

    st.markdown('<div class="log-container">', unsafe_allow_html=True)
    if not filtered:
        st.markdown("<span style='color: #a0b8cc;'>No log entries yet. Start the pipeline to see logs.</span>", unsafe_allow_html=True)
    for log in filtered[-50:]:
        if "[ERROR]" in log:
            color = "#e74c3c"
        elif "[WARNING]" in log:
            color = "#f39c12"
        elif "[DEBUG]" in log:
            color = "#a0b8cc"
        else:
            color = "#4ecdc4"
        st.markdown(f"<span style='color: {color};'>{log}</span>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Auto-refresh while running (every 3 seconds)
# ---------------------------------------------------------------------------
if st.session_state.running:
    # Verify at least one process is still alive
    any_alive = any(_is_running(n) for n in comp_names)
    if any_alive:
        time.sleep(3)
        st.rerun()
    else:
        st.session_state.running = False
        _add_log("System", "All processes have exited", "WARNING")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #a0b8cc; padding: 1rem;'>"
    "🌊 GangaMitra - Autonomous River Cleaning Robot Simulation | "
    "Made with ❤️ for the Environment"
    "</div>",
    unsafe_allow_html=True,
)