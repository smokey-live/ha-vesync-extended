"""Integration constants and exact supported model identifiers."""

DOMAIN = "vesync_extended"
CONF_READ_ONLY = "read_only"
CONF_POLL_INTERVAL = "poll_interval"
DEFAULT_POLL_INTERVAL = 60
PLATFORMS = ["fan", "humidifier", "sensor", "switch"]
PURIFIER_MODELS = frozenset({"LAP-P501S-WUSR", "LAP-P501S-AUSR"})
HUMIDIFIER_MODELS = frozenset({"LUH-N451S-WUS"})
SUPPORTED_MODELS = PURIFIER_MODELS | HUMIDIFIER_MODELS
PURIFIER_MODES = ("manual", "auto", "sleep", "pet")
HUMIDIFIER_MODES = ("manual", "auto", "sleep")
