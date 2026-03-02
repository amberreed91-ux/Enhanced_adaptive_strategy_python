import json
from pathlib import Path

import yaml

from automation.chimera_executor import ChimeraExecutionService


def _write_test_config(tmp_path: Path, *, allowed_symbols: list[str]) -> Path:
    base_cfg = yaml.safe_load(Path("config/config.yaml").read_text(encoding="utf-8"))
    base_cfg["automation"]["state_dir"] = str(tmp_path / "state")
    base_cfg["automation"]["audit_log_file"] = str(tmp_path / "audit.jsonl")
    base_cfg["automation"]["allowed_symbols"] = allowed_symbols
    base_cfg["automation"]["cooldown_seconds"] = 0
    base_cfg["daily_limits"]["max_daily_trades"] = 200
    base_cfg["bookmap_bridge"]["enabled"] = False
    base_cfg["automation"]["risk_guard"]["enabled"] = True
    base_cfg["automation"]["risk_guard"]["max_daily_loss_usd"] = 10.0
    base_cfg["automation"]["risk_guard"]["session_lockout"]["enabled"] = False
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.safe_dump(base_cfg, sort_keys=False), encoding="utf-8")
    return cfg_path


def _write_options_config(tmp_path: Path) -> Path:
    base_cfg = yaml.safe_load(Path("config/config.yaml").read_text(encoding="utf-8"))
    base_cfg["automation"]["state_dir"] = str(tmp_path / "state")
    base_cfg["automation"]["audit_log_file"] = str(tmp_path / "audit.jsonl")
    base_cfg["automation"]["allowed_symbols"] = []
    base_cfg["automation"]["allowed_symbol_patterns"] = ["SPY_*_C"]
    base_cfg["automation"]["cooldown_seconds"] = 0
    base_cfg["daily_limits"]["max_daily_trades"] = 200
    base_cfg["bookmap_bridge"]["enabled"] = False
    base_cfg["automation"]["risk_guard"]["enabled"] = True
    base_cfg["automation"]["risk_guard"]["max_daily_loss_usd"] = 100000.0
    base_cfg["automation"]["risk_guard"]["session_lockout"]["enabled"] = False
    cfg_path = tmp_path / "config_options.yaml"
    cfg_path.write_text(yaml.safe_dump(base_cfg, sort_keys=False), encoding="utf-8")
    return cfg_path


def test_daily_loss_guard_and_audit_log(tmp_path: Path):
    cfg_path = _write_test_config(tmp_path, allowed_symbols=["MNQ1!"])
    service = ChimeraExecutionService(config_path=str(cfg_path))

    _, open_long = service.process_payload({"symbol": "MNQ1!", "action": "buy", "price": 100.0})
    assert open_long["ok"] is True

    _, reverse_short = service.process_payload({"symbol": "MNQ1!", "action": "sell", "price": 90.0})
    assert reverse_short["ok"] is True
    assert float(reverse_short["realized_pnl_usd"]) < 0

    _, blocked = service.process_payload({"symbol": "MNQ1!", "action": "buy", "price": 91.0})
    assert blocked["ok"] is False
    assert blocked["reason"] == "daily_loss_limit"

    audit_file = tmp_path / "audit.jsonl"
    assert audit_file.exists()
    lines = [json.loads(x) for x in audit_file.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(lines) == 3
    assert lines[-1]["risk_reason"] == "daily_loss_limit"


def test_broker_routing_to_oanda(tmp_path: Path):
    cfg_path = _write_test_config(tmp_path, allowed_symbols=["EUR_USD"])
    service = ChimeraExecutionService(config_path=str(cfg_path))

    _, body = service.process_payload({"symbol": "EUR_USD", "action": "buy", "price": 1.1000})
    assert body["ok"] is True
    assert body["broker"] == "oanda"
    assert body["profile"] == "scalp"


def test_option_symbol_pattern_and_multiplier_pnl(tmp_path: Path):
    cfg_path = _write_options_config(tmp_path)
    service = ChimeraExecutionService(config_path=str(cfg_path))

    symbol = "SPY_20260320_500_C"
    # Open
    _, open_body = service.process_payload(
        {
            "symbol": symbol,
            "action": "buy",
            "price": 2.00,
            "instrument_type": "OPTION",
        }
    )
    assert open_body["ok"] is True

    # Close at +0.10 option premium => +$10 with x100 contract multiplier.
    _, close_body = service.process_payload(
        {
            "symbol": symbol,
            "action": "flat",
            "price": 2.10,
            "instrument_type": "OPTION",
        }
    )
    assert close_body["ok"] is True
    assert float(close_body["realized_pnl_usd"]) == 10.0
