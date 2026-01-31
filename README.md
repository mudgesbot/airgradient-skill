# 🌬️ AirGradient Skill

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![OpenClaw Skill](https://img.shields.io/badge/openclaw-skill-purple.svg)](https://github.com/openclaw/openclaw)

An [OpenClaw](https://github.com/openclaw/openclaw) (formerly Clawdbot, Moltbot) skill for monitoring [AirGradient](https://www.airgradient.com/) air quality devices via their local API. Track PM2.5, CO2, temperature, humidity, and more — with alerts, history, and cron support.

<p align="center">
  <img src="https://www.airgradient.com/media/images/I-9PSL_DIY_PRO_45_PCB_front.original.png" width="200" alt="AirGradient I-9PSL">
</p>

## ✨ Features

- 📊 **Real-time monitoring** — Current readings with formatted output
- 🚨 **Threshold alerts** — Configurable warnings for PM2.5, CO2, temp, humidity
- 📈 **Historical data** — SQLite storage for trends and analysis
- 🎨 **Beautiful CLI** — Color-coded output with emoji indicators
- ⏰ **Cron-friendly** — Exit codes for scripting and automation
- 🔧 **Zero dependencies** — Falls back to urllib if `requests` is unavailable

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/mudgesbot/airgradient-skill.git
cd airgradient-skill

# (Optional) Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install requests  # optional, uses urllib as fallback
```

## ⚙️ Configuration

1. Copy the example config:
```bash
cp config/config.example.yaml config/config.yaml
```

2. Edit `config/config.yaml` with your device details:
```yaml
devices:
  - name: living-room
    hostname: airgradient_XXXXXX.local  # or IP address
    label: "Living Room Sensor"

thresholds:
  pm25:
    warn: 12      # µg/m³
    critical: 35
  co2:
    warn: 1000    # ppm
    critical: 2000
  temp_c:
    min: 18
    max: 26
  humidity:
    min: 30
    max: 70
```

## 🚀 Usage

### Commands

| Command | Description |
|---------|-------------|
| `ag status` | Formatted current readings with color indicators |
| `ag readings [--json]` | Raw sensor data |
| `ag history [--days N]` | Historical readings from SQLite |
| `ag alerts` | Check thresholds (returns exit codes) |
| `ag store` | Store current reading to database |
| `ag config show` | Display current configuration |
| `ag config set <key> <value>` | Update a config value |

### Examples

```bash
# Check current air quality
python scripts/airgradient.py status

# Get readings as JSON
python scripts/airgradient.py readings --json

# Check for alerts (useful in scripts)
python scripts/airgradient.py alerts
echo $?  # 0=OK, 1=Warning, 2=Critical

# View last 7 days of history
python scripts/airgradient.py history --days 7

# Store a reading (for cron)
python scripts/airgradient.py store
```

### Sample Output

```
🌡️ AirGradient Status — living-room

📊 Air Quality
  PM2.5:  4.8 µg/m³  ✅ Excellent
  CO2:    519 ppm  ✅ Fresh
  TVOC:   83 index  ✅
  NOx:    1 index  ✅

🌡️ Climate
  Temp:   19.6 °C  ✅ OK
  Humid:  33.7 %  ✅ OK

📶 Device
  WiFi:   -42 dBm (Good)
  Model:  I-9PSL
  FW:     3.6.0
```

## ⏰ Cron Setup

Store readings every 15 minutes and alert on bad air quality:

```cron
# Store readings
*/15 * * * * cd /path/to/airgradient-skill && python scripts/airgradient.py store

# Check alerts and notify (example with Clawdbot)
*/15 * * * * cd /path/to/airgradient-skill && python scripts/airgradient.py alerts || openclaw notify "Air quality alert!"
```

## 🔧 Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All OK |
| `1` | Warning threshold exceeded |
| `2` | Critical threshold exceeded |
| `3` | Error (network/config/database) |

## 📁 Project Structure

```
airgradient-skill/
├── scripts/
│   └── airgradient.py    # Main CLI script
├── config/
│   ├── config.example.yaml
│   └── config.yaml       # Your config (gitignored)
├── data/
│   └── airgradient.db    # SQLite database (gitignored)
├── references/
│   └── api.md            # AirGradient API documentation
├── SKILL.md              # OpenClaw skill manifest
└── README.md
```

## 🔌 AirGradient API

This skill uses the local API endpoint:
```
GET http://<device-hostname>/measures/current
```

See [references/api.md](references/api.md) for full API documentation.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

## 🔗 Links

- [AirGradient](https://www.airgradient.com/) — Air quality monitors
- [OpenClaw](https://github.com/openclaw/openclaw) — AI assistant framework (formerly Clawdbot, Moltbot)
- [ClawdHub](https://clawdhub.com) — Skill marketplace
