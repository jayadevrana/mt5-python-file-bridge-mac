#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path


DEFAULT_COMMON_FILES_DIR = Path(
    os.path.expanduser(
        "~/Library/Application Support/net.metaquotes.wine.metatrader5/"
        "drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files"
    )
)
BRIDGE_DIR_NAME = "python_bridge"
REQUEST_FILE_NAME = "order_request.txt"
RESULT_FILE_NAME = "order_result.txt"


def load_json_payload(json_text: str | None, json_file: str | None) -> dict[str, object]:
    if json_text and json_file:
        raise ValueError("Use either --json or --json-file, not both.")
    if json_text:
        return json.loads(json_text)
    if json_file:
        return json.loads(Path(json_file).read_text(encoding="utf-8"))
    return {}


def build_request_text(
    *,
    request_id: str,
    side: str,
    symbol: str,
    volume: float,
    deviation: int,
    magic: int,
    comment: str,
    sl: float | None,
    tp: float | None,
) -> str:
    lines = [
        f"request_id={request_id}",
        f"action={side.upper()}",
        f"symbol={symbol}",
        f"volume={volume:.2f}",
        "type=MARKET",
        f"deviation={deviation}",
        f"magic={magic}",
        f"comment={comment}",
    ]
    if sl is not None:
        lines.append(f"sl={sl}")
    if tp is not None:
        lines.append(f"tp={tp}")
    return "\n".join(lines) + "\n"


def parse_key_values(raw_text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in raw_text.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def wait_for_result(result_path: Path, request_id: str, timeout_seconds: int) -> dict[str, str] | None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if result_path.exists():
            values = parse_key_values(result_path.read_text(encoding="utf-8", errors="replace"))
            if values.get("request_id") == request_id:
                return values
        time.sleep(1)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a market order request to MT5 via the Common Files bridge.")
    parser.add_argument("--side", default="BUY", choices=["BUY", "SELL"], help="Order side.")
    parser.add_argument("--symbol", default="BTCUSD", help="Broker symbol.")
    parser.add_argument("--volume", type=float, default=0.01, help="Order volume.")
    parser.add_argument("--deviation", type=int, default=50, help="Allowed slippage in points.")
    parser.add_argument("--magic", type=int, default=260308, help="Magic number used by the EA.")
    parser.add_argument("--comment", default="PythonBridge", help="Order comment.")
    parser.add_argument("--sl", type=float, default=None, help="Optional stop loss price.")
    parser.add_argument("--tp", type=float, default=None, help="Optional take profit price.")
    parser.add_argument("--json", help="Inline JSON payload. Example: '{\"action\":\"BUY\",\"symbol\":\"BTCUSD\",\"volume\":0.01}'")
    parser.add_argument("--json-file", help="Path to a JSON payload file.")
    parser.add_argument(
        "--common-files-dir",
        default=str(DEFAULT_COMMON_FILES_DIR),
        help="MT5 Common/Files directory. Override if your terminal uses a different path.",
    )
    parser.add_argument(
        "--wait-timeout",
        type=int,
        default=20,
        help="Seconds to wait for the EA result after writing the request.",
    )
    args = parser.parse_args()

    try:
        payload = load_json_payload(args.json, args.json_file)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Invalid JSON payload: {exc}", file=sys.stderr)
        return 2

    side = str(payload.get("action", args.side)).upper()
    symbol = str(payload.get("symbol", args.symbol))
    volume = float(payload.get("volume", args.volume))
    deviation = int(payload.get("deviation", args.deviation))
    magic = int(payload.get("magic", args.magic))
    comment = str(payload.get("comment", args.comment))
    sl = payload.get("sl", args.sl)
    tp = payload.get("tp", args.tp)

    if side not in {"BUY", "SELL"}:
        print("Action must be BUY or SELL.", file=sys.stderr)
        return 2

    if volume <= 0:
        print("Volume must be greater than zero.", file=sys.stderr)
        return 2

    common_files_dir = Path(args.common_files_dir).expanduser()
    bridge_dir = common_files_dir / BRIDGE_DIR_NAME
    bridge_dir.mkdir(parents=True, exist_ok=True)

    request_path = bridge_dir / REQUEST_FILE_NAME
    result_path = bridge_dir / RESULT_FILE_NAME
    temp_path = bridge_dir / f"{REQUEST_FILE_NAME}.tmp"

    request_id = str(uuid.uuid4())
    request_text = build_request_text(
        request_id=request_id,
        side=side,
        symbol=symbol,
        volume=volume,
        deviation=deviation,
        magic=magic,
        comment=comment,
        sl=float(sl) if sl is not None else None,
        tp=float(tp) if tp is not None else None,
    )

    if result_path.exists():
        result_path.unlink()

    temp_path.write_text(request_text, encoding="utf-8")
    temp_path.replace(request_path)

    print(f"Request written: {request_path}")
    print(f"request_id={request_id}")

    result = wait_for_result(result_path, request_id, args.wait_timeout)
    if result is None:
        print("No result received from MT5.")
        print("Make sure the PythonBridgeTrader EA is attached to a chart and Algo Trading is enabled.")
        return 1

    print("MT5 result:")
    for key in ("status", "message", "retcode", "order", "deal", "symbol", "action", "volume"):
        value = result.get(key)
        if value:
            print(f"{key}={value}")

    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
