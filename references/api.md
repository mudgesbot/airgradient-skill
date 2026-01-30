# AirGradient Local API

## Endpoint

```
GET http://<device-hostname>/measures/current
```

Example:

```
http://airgradient_d83bda1d50f0.local/measures/current
```

## Response (example)

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

## Fields

- `pm01`, `pm02`, `pm10`: particulate matter in µg/m³
- `pm02Compensated`: PM2.5 with internal compensation
- `atmp`, `atmpCompensated`: temperature in °C
- `rhum`, `rhumCompensated`: relative humidity in %
- `rco2`: CO2 in ppm
- `tvocIndex`, `noxIndex`: VOC/NOx indices
- `tvocRaw`, `noxRaw`: raw sensor values
- `wifi`: signal strength in dBm
- `ledMode`, `serialno`, `firmware`, `model`: device metadata

## Errors

- If the device is offline or unreachable, the request will fail.
- If the endpoint returns invalid JSON, the CLI reports an error.
