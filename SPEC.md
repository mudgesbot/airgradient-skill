# AirGradient Skill - Specification

## Overview
A Clawdbot skill for monitoring AirGradient air quality devices via their local API.

## Device Info (Olaf's Device)
- **Hostname:** `airgradient_d83bda1d50f0.local`
- **Model:** I-9PSL
- **Firmware:** 3.6.0
- **API Endpoint:** `http://airgradient_d83bda1d50f0.local/measures/current`

## API Response Format
```json
{
  "pm01": 0,
  "pm02": 1.5,
  "pm10": 1.5,
  "pm02Compensated": 6.78,
  "atmp": 18.71,
  "atmpCompensated": 18.71,
  "rhum": 35.77,
  "rhumCompensated": 35.77,
  "rco2": 482.33,
  "tvocIndex": 68,
  "tvocRaw": 31989,
  "noxIndex": 1,
  "noxRaw": 17257.25,
  "wifi": -38,
  "ledMode": "co2",
  "serialno": "d83bda1d50f0",
  "firmware": "3.6.0",
  "model": "I-9PSL"
}
```

## Features Required

### 1. CLI Tool (`airgradient` or `ag`)
- `ag status` - Current readings, nicely formatted
- `ag readings [--json]` - Raw sensor data
- `ag history [--days N]` - Historical data (if we store it)
- `ag alerts` - Check current alerts
- `ag config` - Show/edit configuration

### 2. Configuration
- Store device hostname(s) in config file
- Support multiple devices
- Configurable alert thresholds:
  - PM2.5: warn > 12 µg/m³, critical > 35 µg/m³
  - CO2: warn > 1000 ppm, critical > 2000 ppm
  - Temperature: configurable range
  - Humidity: warn < 30% or > 70%

### 3. Data Storage
- SQLite database for historical data
- Store readings periodically (for cron job integration)
- Query historical trends

### 4. Alert System
- Check readings against thresholds
- Return alert status for cron job integration
- Support for notifications (exit codes for scripting)

## Technical Requirements
- Python 3.10+
- No heavy dependencies (requests, sqlite3 only)
- mDNS discovery support (optional, nice-to-have)
- Proper error handling (device offline, network issues)

## Skill Structure
```
airgradient-skill/
├── SKILL.md              # Clawdbot skill documentation
├── scripts/
│   └── airgradient.py    # Main CLI tool
├── references/
│   └── api.md            # API documentation
└── config/
    └── config.example.yaml
```

## Air Quality Standards (EPA/WHO)
- **PM2.5 (24h average):**
  - Good: 0-12 µg/m³
  - Moderate: 12.1-35.4 µg/m³
  - Unhealthy for sensitive: 35.5-55.4 µg/m³
  - Unhealthy: 55.5-150.4 µg/m³

- **CO2:**
  - Fresh air: < 600 ppm
  - Good: 600-1000 ppm
  - Moderate: 1000-2000 ppm
  - Poor: > 2000 ppm

- **Humidity:**
  - Optimal: 30-60%
  - Dry: < 30%
  - Humid: > 70%

## Example Output
```
🌡️ AirGradient Status — airgradient_d83bda1d50f0

📊 Air Quality
  PM2.5:  1.5 µg/m³  ✅ Excellent
  CO2:    482 ppm    ✅ Fresh
  TVOC:   68 index   ✅ Good
  NOx:    1 index    ✅ Good

🌡️ Climate
  Temp:   18.7°C
  Humid:  35.8%      ⚠️ Slightly dry

📶 Device
  WiFi:   -38 dBm (Good)
  Model:  I-9PSL
  FW:     3.6.0
```

## Integration with Clawdbot
The skill should work with Clawdbot cron jobs:
- Morning air quality check
- Alert on poor air quality
- Daily summary reports
