#!/usr/bin/env python3
"""
Start the full Chimera paper automation stack:
1) Chimera Streamlit app (bridge writer)
2) Chimera executor webhook server
"""
from __future__ import annotations

import argparse
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
import yaml


def _check_executor_status(host: str, port: int, timeout: float = 2.0) -> bool:
    url = f"http://{host}:{port}/status"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return int(resp.status) == 200
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def _load_l2_bridge_defaults(config_path: str) -> dict:
    try:
        payload = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            automation = payload.get("automation", {}) if isinstance(payload.get("automation", {}), dict) else {}
            bridge = automation.get("l2_bridge", {}) if isinstance(automation.get("l2_bridge", {}), dict) else {}
            return bridge
    except Exception:
        pass
    return {}


def _is_port_in_use(host: str, port: int) -> bool:
    # Prefer lsof because local socket probes can be blocked in sandboxed contexts.
    try:
        proc = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{int(port)}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return True
    except Exception:
        pass

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex((host, int(port))) == 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Chimera app + executor together")
    parser.add_argument("--config", default="config/config.yaml", help="Path to config YAML")
    parser.add_argument("--executor-host", default="127.0.0.1", help="Executor host")
    parser.add_argument("--executor-port", type=int, default=8787, help="Executor port")
    parser.add_argument("--app-port", type=int, default=8501, help="Streamlit app port")
    parser.add_argument("--with-bridge", action="store_true", help="Also run L2 bridge writer")
    parser.add_argument("--bridge-symbol", default=None, help="Bridge symbol metadata")
    parser.add_argument("--bridge-broker", default=None, help="Bridge broker label")
    parser.add_argument(
        "--bridge-provider",
        default=None,
        choices=["file-poll", "binance-rest", "synthetic"],
        help="Bridge provider",
    )
    parser.add_argument("--bridge-input-file", default=None, help="Bridge input file")
    parser.add_argument("--bridge-output-file", default=None, help="Bridge output file")
    args = parser.parse_args()
    bridge_defaults = _load_l2_bridge_defaults(args.config)
    bridge_symbol = args.bridge_symbol or str(bridge_defaults.get("symbol", "MGC1!"))
    bridge_broker = args.bridge_broker or str(bridge_defaults.get("broker", "tradovate"))
    bridge_provider = args.bridge_provider or str(bridge_defaults.get("provider", "file-poll"))
    bridge_input_file = args.bridge_input_file or str(bridge_defaults.get("input_file", "data/bridges/tradovate_l2.json"))
    bridge_output_file = args.bridge_output_file or str(bridge_defaults.get("output_file", "data/live_l2_snapshot.json"))

    app_host = "127.0.0.1"
    if _is_port_in_use(args.executor_host, args.executor_port):
        print(
            f"Cannot start stack: executor port {args.executor_host}:{args.executor_port} is already in use.\n"
            "Stop the existing process or choose a different --executor-port."
        )
        return
    if _is_port_in_use(app_host, args.app_port):
        print(
            f"Cannot start stack: app port {app_host}:{args.app_port} is already in use.\n"
            "Stop the existing process or choose a different --app-port."
        )
        return

    root = Path(__file__).resolve().parent
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    app_log = log_dir / f"chimera_app_{timestamp}.log"
    exec_log = log_dir / f"chimera_executor_{timestamp}.log"
    bridge_log = log_dir / f"chimera_l2_bridge_{timestamp}.log"

    print("Starting Chimera stack...")
    print(f"Config: {args.config}")

    exec_cmd = [
        sys.executable,
        str(root / "run_chimera_executor.py"),
        "--config",
        args.config,
        "--host",
        args.executor_host,
        "--port",
        str(args.executor_port),
    ]
    app_cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(root / "bookmap_engine" / "app_streamlit.py"),
        "--server.port",
        str(args.app_port),
        "--server.address",
        app_host,
    ]
    bridge_cmd = [
        sys.executable,
        str(root / "run_chimera_l2_bridge.py"),
        "--config",
        args.config,
        "--symbol",
        bridge_symbol,
        "--broker",
        bridge_broker,
        "--provider",
        bridge_provider,
        "--input-file",
        bridge_input_file,
        "--output-file",
        bridge_output_file,
    ]

    with (
        app_log.open("w", encoding="utf-8") as app_out,
        exec_log.open("w", encoding="utf-8") as exec_out,
        bridge_log.open("w", encoding="utf-8") as bridge_out,
    ):
        exec_proc = subprocess.Popen(exec_cmd, cwd=str(root), stdout=exec_out, stderr=subprocess.STDOUT)
        app_proc = subprocess.Popen(app_cmd, cwd=str(root), stdout=app_out, stderr=subprocess.STDOUT)
        bridge_proc = None
        if args.with_bridge:
            bridge_proc = subprocess.Popen(bridge_cmd, cwd=str(root), stdout=bridge_out, stderr=subprocess.STDOUT)

        print(f"Executor PID: {exec_proc.pid} | logs: {exec_log}")
        print(f"App PID:      {app_proc.pid} | logs: {app_log}")
        if bridge_proc is not None:
            print(f"Bridge PID:   {bridge_proc.pid} | logs: {bridge_log}")
        print(f"App URL:      http://127.0.0.1:{args.app_port}")
        print(f"Executor URL: http://{args.executor_host}:{args.executor_port}/status")

        # Give processes a moment to boot.
        time.sleep(2.5)
        exec_ok = _check_executor_status(args.executor_host, args.executor_port)
        print(f"Executor status: {'UP' if exec_ok else 'NOT READY'}")
        print("Press Ctrl+C to stop both processes.")

        try:
            while True:
                if exec_proc.poll() is not None:
                    print("Executor process exited. Stopping app.")
                    break
                if app_proc.poll() is not None:
                    print("App process exited. Stopping executor.")
                    break
                if bridge_proc is not None and bridge_proc.poll() is not None:
                    print("Bridge process exited. Stopping app and executor.")
                    break
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("\nStopping Chimera stack...")
        finally:
            all_procs = [app_proc, exec_proc]
            if bridge_proc is not None:
                all_procs.append(bridge_proc)
            for proc in all_procs:
                if proc.poll() is None:
                    proc.terminate()
            time.sleep(1.0)
            for proc in all_procs:
                if proc.poll() is None:
                    proc.kill()
            print("Stopped.")


if __name__ == "__main__":
    main()
