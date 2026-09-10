# EspiFi board configuration for the Axiometa Genesis Mini on the open STARLINK network.
# EFM is reached through StarlinkAI's C2 relay, the same path the AMOLED board uses.
CONFIG = {
    "efm": "http://192.168.1.245:10090",
    "agent_class": "AXIOMETA",
    "wifi_ssid": "STARLINK",
    "wifi_password": "",
    "heartbeat_ms": 5000,
}
