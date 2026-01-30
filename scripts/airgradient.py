#!/usr/bin/env python3
"""AirGradient CLI skill for Clawdbot."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import sqlite3
try:
    import requests  # type: ignore
except ModuleNotFoundError:  # fallback for environments without requests
    import urllib.error
    import urllib.request

    class _RequestError(RuntimeError):
        pass

    class _Response:
        def __init__(self, status: int, body: bytes) -> None:
            self.status_code = status
            self._body = body

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise _RequestError(f"HTTP {self.status_code}")

        def json(self) -> Any:
            return json.loads(self._body.decode("utf-8"))

    class _RequestsShim:
        RequestException = _RequestError

        def get(self, url: str, timeout: float = 5) -> _Response:
            try:
                with urllib.request.urlopen(url, timeout=timeout) as response:
                    return _Response(response.status, response.read())
            except urllib.error.URLError as exc:
                raise _RequestError(str(exc)) from exc

    requests = _RequestsShim()

PENDING = object()


class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"


def color(text: str, code: str) -> str:
    return f"{code}{text}{Style.RESET}"


def die(msg: str, code: int = 1) -> None:
    print(color(f"❌ {msg}", Style.RED), file=sys.stderr)
    sys.exit(code)


def parse_value(raw: str) -> Any:
    if raw.startswith("\"") and raw.endswith("\""):
        return raw[1:-1]
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1]
    lower = raw.lower()
    if lower in ("true", "false"):
        return lower == "true"
    if lower in ("null", "none"):
        return None
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def parse_yaml(text: str) -> Dict[str, Any]:
    root: Dict[str, Any] = {}
    stack: List[Dict[str, Any]] = []

    class Frame:
        def __init__(self, indent: int, container: Any, last_key: Optional[str]) -> None:
            self.indent = indent
            self.container = container
            self.last_key = last_key

    frames: List[Frame] = [Frame(0, root, None)]

    lines = text.splitlines()
    for raw_line in lines:
        line = raw_line.split("#", 1)[0].rstrip("\n")
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent % 2 != 0:
            raise ValueError(f"Invalid indentation: '{raw_line}'")
        stripped = line.strip()

        while frames and indent < frames[-1].indent:
            frames.pop()
        if not frames:
            raise ValueError("Invalid indentation structure")

        frame = frames[-1]
        if indent > frame.indent:
            if indent != frame.indent + 2:
                raise ValueError(f"Invalid indentation level: '{raw_line}'")
            if isinstance(frame.container, dict):
                if frame.last_key is None:
                    raise ValueError(f"Missing key for nested mapping: '{raw_line}'")
                if frame.container.get(frame.last_key, None) is PENDING:
                    if stripped.startswith("- "):
                        frame.container[frame.last_key] = []
                    else:
                        frame.container[frame.last_key] = {}
                new_container = frame.container[frame.last_key]
            elif isinstance(frame.container, list):
                if not frame.container:
                    raise ValueError(f"List has no item to extend: '{raw_line}'")
                last = frame.container[-1]
                if last is PENDING:
                    last = {}
                    frame.container[-1] = last
                new_container = last
            else:
                raise ValueError(f"Unsupported container at indent: '{raw_line}'")
            frame = Frame(indent, new_container, None)
            frames.append(frame)

        if stripped.startswith("- "):
            item_text = stripped[2:].strip()
            container = frame.container
            if isinstance(container, dict):
                if frame.last_key is None:
                    raise ValueError(f"List item without key: '{raw_line}'")
                if container.get(frame.last_key, None) is PENDING:
                    container[frame.last_key] = []
                container = container[frame.last_key]
            if not isinstance(container, list):
                raise ValueError(f"Expected list for item: '{raw_line}'")
            if not item_text:
                container.append(PENDING)
                continue
            if ":" in item_text:
                key, rest = item_text.split(":", 1)
                key = key.strip()
                value = rest.strip()
                if value == "":
                    item = {key: PENDING}
                else:
                    item = {key: parse_value(value)}
                container.append(item)
                frame.last_key = key
            else:
                container.append(parse_value(item_text))
            continue

        if ":" not in stripped:
            raise ValueError(f"Invalid line (missing ':'): '{raw_line}'")
        key, rest = stripped.split(":", 1)
        key = key.strip()
        value = rest.strip()
        if value == "":
            frame.container[key] = PENDING
            frame.last_key = key
        else:
            frame.container[key] = parse_value(value)
            frame.last_key = key

    def finalize(obj: Any) -> Any:
        if obj is PENDING:
            return {}
        if isinstance(obj, dict):
            return {k: finalize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [finalize(v) for v in obj]
        return obj

    return finalize(root)


def load_config(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8") as handle:
        return parse_yaml(handle.read())


def config_path_from_env() -> str:
    return os.environ.get("AIRGRADIENT_CONFIG", os.path.join("config", "config.yaml"))


def normalize_device(config: Dict[str, Any], device_hint: Optional[str]) -> Dict[str, Any]:
    devices = config.get("devices") or []
    if not devices:
        raise ValueError("No devices configured. Add devices to config.yaml.")
    default_name = config.get("default_device")
    if device_hint:
        for device in devices:
            if device_hint in (device.get("name"), device.get("hostname")):
                return device
        raise ValueError(f"Device '{device_hint}' not found in config.")
    if default_name:
        for device in devices:
            if device.get("name") == default_name:
                return device
    return devices[0]


def device_endpoint(device: Dict[str, Any]) -> str:
    hostname = device.get("hostname")
    if not hostname:
        raise ValueError("Device hostname missing in config.")
    if hostname.startswith("http://") or hostname.startswith("https://"):
        return hostname.rstrip("/") + "/measures/current"
    return f"http://{hostname}/measures/current"


def fetch_reading(endpoint: str, timeout: float) -> Dict[str, Any]:
    try:
        response = requests.get(endpoint, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"Network error: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Invalid JSON response from device") from exc


def open_db(path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device TEXT NOT NULL,
            ts INTEGER NOT NULL,
            pm01 REAL,
            pm02 REAL,
            pm10 REAL,
            pm02Compensated REAL,
            atmp REAL,
            atmpCompensated REAL,
            rhum REAL,
            rhumCompensated REAL,
            rco2 REAL,
            tvocIndex REAL,
            tvocRaw REAL,
            noxIndex REAL,
            noxRaw REAL,
            wifi REAL,
            ledMode TEXT,
            serialno TEXT,
            firmware TEXT,
            model TEXT,
            raw_json TEXT
        )
        """
    )
    return conn


def store_reading(conn: sqlite3.Connection, device_name: str, data: Dict[str, Any]) -> None:
    now = int(time.time())
    payload = {
        "device": device_name,
        "ts": now,
        "pm01": data.get("pm01"),
        "pm02": data.get("pm02"),
        "pm10": data.get("pm10"),
        "pm02Compensated": data.get("pm02Compensated"),
        "atmp": data.get("atmp"),
        "atmpCompensated": data.get("atmpCompensated"),
        "rhum": data.get("rhum"),
        "rhumCompensated": data.get("rhumCompensated"),
        "rco2": data.get("rco2"),
        "tvocIndex": data.get("tvocIndex"),
        "tvocRaw": data.get("tvocRaw"),
        "noxIndex": data.get("noxIndex"),
        "noxRaw": data.get("noxRaw"),
        "wifi": data.get("wifi"),
        "ledMode": data.get("ledMode"),
        "serialno": data.get("serialno"),
        "firmware": data.get("firmware"),
        "model": data.get("model"),
        "raw_json": json.dumps(data, ensure_ascii=False),
    }
    columns = ",".join(payload.keys())
    placeholders = ",".join(["?"] * len(payload))
    conn.execute(
        f"INSERT INTO readings ({columns}) VALUES ({placeholders})",
        list(payload.values()),
    )
    conn.commit()


def format_number(value: Any, unit: str = "", decimals: int = 1) -> str:
    if value is None:
        return "n/a"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    fmt = f"{num:.{decimals}f}" if decimals >= 0 else str(num)
    return f"{fmt} {unit}".strip()


def classify_pm25(value: Optional[float]) -> str:
    if value is None:
        return "Unknown"
    if value <= 12:
        return "Excellent"
    if value <= 35.4:
        return "Moderate"
    if value <= 55.4:
        return "Unhealthy (Sensitive)"
    if value <= 150.4:
        return "Unhealthy"
    return "Hazardous"


def classify_co2(value: Optional[float]) -> str:
    if value is None:
        return "Unknown"
    if value < 600:
        return "Fresh"
    if value < 1000:
        return "Good"
    if value < 2000:
        return "Moderate"
    return "Poor"


def status_output(device: Dict[str, Any], data: Dict[str, Any], thresholds: Dict[str, Any]) -> str:
    name = device.get("name") or device.get("hostname")
    header = color(f"🌡️ AirGradient Status — {name}", Style.BOLD)

    pm25 = data.get("pm02Compensated") or data.get("pm02")
    co2 = data.get("rco2")
    tvoc = data.get("tvocIndex")
    nox = data.get("noxIndex")
    temp = data.get("atmpCompensated") or data.get("atmp")
    humid = data.get("rhumCompensated") or data.get("rhum")

    pm25_status = classify_pm25(pm25)
    co2_status = classify_co2(co2)

    quality_lines = [
        f"  PM2.5:  {format_number(pm25, 'µg/m³')}  {status_icon(pm25, thresholds.get('pm25', {}))} {pm25_status}",
        f"  CO2:    {format_number(co2, 'ppm', 0)}  {status_icon(co2, thresholds.get('co2', {}))} {co2_status}",
        f"  TVOC:   {format_number(tvoc, 'index', 0)}  {status_icon(tvoc, thresholds.get('tvoc', {}))}",
        f"  NOx:    {format_number(nox, 'index', 0)}  {status_icon(nox, thresholds.get('nox', {}))}",
    ]

    temp_range = thresholds.get("temp_c", {})
    humid_range = thresholds.get("humidity", {})

    climate_lines = [
        f"  Temp:   {format_number(temp, '°C')}  {status_icon_range(temp, temp_range)}",
        f"  Humid:  {format_number(humid, '%')}  {status_icon_range(humid, humid_range)}",
    ]

    wifi = data.get("wifi")
    wifi_quality = "Good" if wifi is not None and wifi > -60 else "Okay"

    device_lines = [
        f"  WiFi:   {format_number(wifi, 'dBm', 0)} ({wifi_quality})",
        f"  Model:  {data.get('model', 'n/a')}",
        f"  FW:     {data.get('firmware', 'n/a')}",
    ]

    sections = [
        header,
        "\n📊 Air Quality",
        "\n".join(quality_lines),
        "\n🌡️ Climate",
        "\n".join(climate_lines),
        "\n📶 Device",
        "\n".join(device_lines),
    ]
    return "\n".join(sections)


def status_icon(value: Optional[float], threshold: Dict[str, Any]) -> str:
    if value is None:
        return color("⚪", Style.GRAY)
    warn = threshold.get("warn")
    critical = threshold.get("critical")
    if critical is not None and value >= critical:
        return color("🟥", Style.RED)
    if warn is not None and value >= warn:
        return color("🟨", Style.YELLOW)
    return color("✅", Style.GREEN)


def status_icon_range(value: Optional[float], threshold: Dict[str, Any]) -> str:
    if value is None:
        return color("⚪", Style.GRAY)
    min_v = threshold.get("min")
    max_v = threshold.get("max")
    if min_v is not None and value < min_v:
        return color("⚠️ Low", Style.YELLOW)
    if max_v is not None and value > max_v:
        return color("⚠️ High", Style.YELLOW)
    return color("✅ OK", Style.GREEN)


def print_readings(data: Dict[str, Any]) -> None:
    print(color("📋 Raw Readings", Style.BOLD))
    for key in sorted(data.keys()):
        print(f"  {key}: {data[key]}")


def ensure_config(args: argparse.Namespace) -> Dict[str, Any]:
    config_path = args.config or config_path_from_env()
    try:
        config = load_config(config_path)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Config not found at {config_path}. Copy config/config.example.yaml to config/config.yaml"
        )
    config["_path"] = config_path
    return config


def thresholds_from_config(config: Dict[str, Any]) -> Dict[str, Any]:
    return config.get("thresholds", {})


def fetch_and_maybe_store(config: Dict[str, Any], device: Dict[str, Any], store: bool) -> Dict[str, Any]:
    endpoint = device_endpoint(device)
    timeout = float(config.get("network", {}).get("timeout_sec", 5))
    data = fetch_reading(endpoint, timeout)
    if store:
        db_path = config.get("storage", {}).get("db_path", os.path.join("data", "airgradient.db"))
        conn = open_db(db_path)
        store_reading(conn, device.get("name") or device.get("hostname"), data)
        conn.close()
    return data


def alerts_for_reading(data: Dict[str, Any], thresholds: Dict[str, Any]) -> List[str]:
    alerts: List[str] = []
    pm25 = data.get("pm02Compensated") or data.get("pm02")
    co2 = data.get("rco2")
    temp = data.get("atmpCompensated") or data.get("atmp")
    humid = data.get("rhumCompensated") or data.get("rhum")

    def check_level(label: str, value: Optional[float], rules: Dict[str, Any]) -> None:
        if value is None:
            return
        warn = rules.get("warn")
        critical = rules.get("critical")
        if critical is not None and value >= critical:
            alerts.append(f"CRITICAL {label}: {value}")
        elif warn is not None and value >= warn:
            alerts.append(f"WARN {label}: {value}")

    def check_range(label: str, value: Optional[float], rules: Dict[str, Any]) -> None:
        if value is None:
            return
        min_v = rules.get("min")
        max_v = rules.get("max")
        if min_v is not None and value < min_v:
            alerts.append(f"WARN {label} low: {value}")
        if max_v is not None and value > max_v:
            alerts.append(f"WARN {label} high: {value}")

    check_level("PM2.5", pm25, thresholds.get("pm25", {}))
    check_level("CO2", co2, thresholds.get("co2", {}))
    check_range("Temperature", temp, thresholds.get("temp_c", {}))
    check_range("Humidity", humid, thresholds.get("humidity", {}))

    return alerts


def print_alerts(alerts: List[str]) -> int:
    if not alerts:
        print(color("✅ No alerts", Style.GREEN))
        return 0
    severity = 1
    for alert in alerts:
        if alert.startswith("CRITICAL"):
            severity = 2
    color_code = Style.RED if severity == 2 else Style.YELLOW
    print(color("🚨 Alerts", Style.BOLD))
    for alert in alerts:
        print(color(f"  {alert}", color_code))
    return severity


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ag",
        description="AirGradient CLI for Clawdbot",
    )
    parser.add_argument("--config", help="Path to config YAML")
    parser.add_argument("--device", help="Device name or hostname")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show formatted status output")

    readings_parser = sub.add_parser("readings", help="Show raw readings")
    readings_parser.add_argument("--json", action="store_true", help="Print JSON")

    history_parser = sub.add_parser("history", help="Show historical readings")
    history_parser.add_argument("--days", type=int, default=7, help="Days of history")
    history_parser.add_argument("--json", action="store_true", help="Print JSON")

    sub.add_parser("alerts", help="Check alerts and return status code")

    config_parser = sub.add_parser("config", help="Show or edit configuration")
    config_parser.add_argument("action", nargs="?", choices=["show", "set"], default="show")
    config_parser.add_argument("key", nargs="?")
    config_parser.add_argument("value", nargs="?")

    sub.add_parser("store", help="Fetch and store a reading (cron)")

    return parser.parse_args()


def show_config(config: Dict[str, Any]) -> None:
    path = config.get("_path")
    print(color(f"📄 Config: {path}", Style.BOLD))
    try:
        with open(path, "r", encoding="utf-8") as handle:
            print(handle.read().rstrip())
    except OSError as exc:
        raise RuntimeError(f"Unable to read config: {exc}") from exc


def set_config_value(config_path: str, key_path: str, value: str) -> None:
    # Simple line-based update for key paths like thresholds.pm25.warn
    with open(config_path, "r", encoding="utf-8") as handle:
        lines = handle.readlines()

    keys = key_path.split(".")
    indent = 0
    idx = 0
    found = False

    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            idx += 1
            continue
        current_indent = len(line) - len(line.lstrip(" "))
        key = stripped.split(":", 1)[0]
        if current_indent == indent and key == keys[0]:
            if len(keys) == 1:
                lines[idx] = f"{key}: {value}\n"
                found = True
                break
            indent += 2
            keys = keys[1:]
        idx += 1

    if not found:
        raise ValueError("Key path not found in config. Edit manually.")

    with open(config_path, "w", encoding="utf-8") as handle:
        handle.writelines(lines)


def history_output(config: Dict[str, Any], device: Dict[str, Any], days: int, json_out: bool) -> None:
    db_path = config.get("storage", {}).get("db_path", os.path.join("data", "airgradient.db"))
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"No database found at {db_path}. Run 'ag store' to collect data.")

    cutoff = int(time.time() - days * 86400)
    conn = open_db(db_path)
    cursor = conn.execute(
        """
        SELECT ts, pm02Compensated, pm02, rco2, atmpCompensated, atmp, rhumCompensated, rhum
        FROM readings
        WHERE device = ? AND ts >= ?
        ORDER BY ts DESC
        """,
        (device.get("name") or device.get("hostname"), cutoff),
    )
    rows = cursor.fetchall()
    conn.close()

    if json_out:
        data = []
        for row in rows:
            data.append(
                {
                    "ts": row[0],
                    "pm25": row[1] if row[1] is not None else row[2],
                    "co2": row[3],
                    "temp": row[4] if row[4] is not None else row[5],
                    "humidity": row[6] if row[6] is not None else row[7],
                }
            )
        print(json.dumps(data, indent=2))
        return

    print(color(f"🕒 History ({days} days)", Style.BOLD))
    for row in rows[:200]:
        ts = datetime.fromtimestamp(row[0], tz=timezone.utc).astimezone()
        pm25 = row[1] if row[1] is not None else row[2]
        co2 = row[3]
        temp = row[4] if row[4] is not None else row[5]
        humid = row[6] if row[6] is not None else row[7]
        print(
            f"{ts.strftime('%Y-%m-%d %H:%M')}  PM2.5 {format_number(pm25, 'µg/m³')}  CO2 {format_number(co2, 'ppm', 0)}  Temp {format_number(temp, '°C')}  Hum {format_number(humid, '%')}"
        )


def main() -> None:
    args = parse_args()
    try:
        config = ensure_config(args)
        device = normalize_device(config, args.device)

        if args.command == "config":
            if args.action == "show":
                show_config(config)
                return
            if args.action == "set":
                if not args.key or args.value is None:
                    raise ValueError("Provide key and value. Example: ag config set thresholds.pm25.warn 15")
                set_config_value(config["_path"], args.key, args.value)
                print(color("✅ Config updated", Style.GREEN))
                return

        thresholds = thresholds_from_config(config)
        store_on_read = bool(config.get("storage", {}).get("store_on_read", False))

        if args.command == "status":
            data = fetch_and_maybe_store(config, device, store_on_read)
            print(status_output(device, data, thresholds))
            return

        if args.command == "readings":
            data = fetch_and_maybe_store(config, device, store_on_read)
            if args.json:
                print(json.dumps(data, indent=2))
            else:
                print_readings(data)
            return

        if args.command == "alerts":
            data = fetch_and_maybe_store(config, device, store_on_read)
            alerts = alerts_for_reading(data, thresholds)
            code = print_alerts(alerts)
            sys.exit(code)

        if args.command == "history":
            history_output(config, device, args.days, args.json)
            return

        if args.command == "store":
            data = fetch_and_maybe_store(config, device, True)
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            print(color(f"✅ Stored reading at {ts}", Style.GREEN))
            if config.get("storage", {}).get("echo_summary", True):
                print(status_output(device, data, thresholds))
            return

        raise ValueError("Unknown command")
    except FileNotFoundError as exc:
        die(str(exc), code=2)
    except ValueError as exc:
        die(str(exc), code=2)
    except RuntimeError as exc:
        die(str(exc), code=3)
    except Exception as exc:  # fallback
        die(f"Unexpected error: {exc}", code=3)


if __name__ == "__main__":
    main()
