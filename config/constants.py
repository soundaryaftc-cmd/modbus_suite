DEFAULT_PORT = 502

ZONE_IP = "192.168.95.133"

# Online rovers on site (row → device ID from dashboard)
TARGET_RCS = [
    "B331001131",  # B33T05R10 — AUTO
    "B331001093",  # B33T04R03 — LOWBAT
]

MODBUS_TIMEOUT = 3

API_TIMEOUT = 3

READBACK_DELAY = 2

API_REFRESH_DELAY = 2

API_VERIFY_TIMEOUT = 20

MQTT_VERIFY_TIMEOUT = 25

# HRST may reboot the RC; allow extra time for changeEvent/xbee confirmation
HRST_MQTT_VERIFY_TIMEOUT = 60

MQTT_BROKER_PORT = 1883

# Rover command / status MQTT (xbee2 is active on most sites)
MQTT_TOPICS = [
    "xbee/response",
    "xbee1/response",
    "xbee2/response",
    "xbee2/periodicresponse",
    "changeEvent/rover/#",
]

# Map rover/API mode names to ZC Modbus/MQTT count keys
ROVER_MODE_TO_MQTT_KEY = {
    "AUTO": "AUTO",
    "MANUAL": "MANUAL",
    "WIND-STOW": "WS",
    "WIND STOW": "WS",
    "WS": "WS",
    "EMERGENCY-STOW": "ES",
    "EMERGENCY STOW": "ES",
    "ES": "ES",
    "SNOW-STOW": "SS",
    "SNOW STOW": "SS",
    "SS": "SS",
    "CLEAN-STOW": "CS",
    "CLEAN STOW": "CS",
    "CS": "CS",
    "NIGHT-STOW": "NS",
    "NIGHT STOW": "NS",
    "NS": "NS",
    "HAIL-STOW": "HS",
    "HAIL STOW": "HS",
    "HS": "HS",
    "COMMEMOR-STOW": "CMS",
    "CMS": "CMS",
    "CYCLE-TEST": "CT",
    "CT": "CT",
    "ARREST": "AR",
    "AR": "AR",
    "RETMANUAL": "RST",
    "RST": "RST",
    "LOWBAT": "LOWB",
    "LOWB": "LOWB",
    "UNKNOWN": "UNKNOWN",
}

MODE_MAP = {
    1: "AUTO",
    2: "ES",
    3: "WS",
    4: "SS",
    5: "CS",
    6: "NS",
    7: "MANUAL",
    8: "HS",
}
