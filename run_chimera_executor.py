#!/usr/bin/env python3
"""
Run Chimera TradingView webhook executor (Tradovate paper mode scaffold).
"""
import argparse

from automation.chimera_executor import run_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Chimera execution webhook server")
    parser.add_argument("--config", default="config/config.yaml", help="Path to config YAML")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8787, help="Bind port")
    args = parser.parse_args()
    run_server(config_path=args.config, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

