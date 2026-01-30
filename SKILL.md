---
name: airgradient
title: AirGradient Monitor
description: Monitor AirGradient air quality devices via the local API.
version: 1.0.0
config: config/config.yaml
supports:
  - cron
  - notifications
---

# AirGradient Skill

Monitor AirGradient devices on your local network, store readings, and alert on poor air quality.

## Setup

1. Copy the example config and edit it:

```
cp config/config.example.yaml config/config.yaml
```

2. Add your device hostname(s) under `devices`.

## Commands

- `ag status` — formatted current readings
- `ag readings [--json]` — raw sensor data
- `ag history [--days N] [--json]` — historical data from SQLite
- `ag alerts` — check thresholds and exit with status codes
- `ag store` — fetch and store a reading (cron-friendly)
- `ag config` — show config
- `ag config set <path> <value>` — update a simple key (e.g. thresholds.pm25.warn)

## Exit Codes (for `ag alerts`)

- `0` — OK
- `1` — Warning thresholds exceeded
- `2` — Critical thresholds exceeded
- `3` — Error (network/config/db)

## Examples

```
python scripts/airgradient.py status
python scripts/airgradient.py alerts
python scripts/airgradient.py store
python scripts/airgradient.py history --days 3
```

## Cron

Example: collect readings every 10 minutes

```
*/10 * * * * /usr/bin/python3 /path/to/airgradient-skill/scripts/airgradient.py store
```

## Notes

- Uses only `requests` and `sqlite3`.
- The default config path is `config/config.yaml` or `$AIRGRADIENT_CONFIG`.
- Historical data is stored in SQLite at `data/airgradient.db` by default.

## References

See `references/api.md` for API details.
