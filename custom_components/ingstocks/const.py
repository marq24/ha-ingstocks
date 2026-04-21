# const.py
DOMAIN = "ingstocks"

COORDINATOR_KEY = "multi_coordinator"
DELAYED_TASK_KEY = "delayed_task"

CONF_ISIN = "isin"
CONF_NAME = "name"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_INSTRUMENT_TYPE = "instrument_type"
CONF_QUANTITY = "quantity"  # NEU

DEFAULT_SCAN_INTERVAL = 15
DEFAULT_QUANTITY = 0.0  # NEU (0 = deaktiviert/kein Positionswert)

INSTRUMENT_TYPE_AUTO = "auto"
INSTRUMENT_TYPE_ETF = "etf"
INSTRUMENT_TYPE_STOCK = "stock"

INSTRUMENT_TYPE_OPTIONS = [
    INSTRUMENT_TYPE_AUTO,
    INSTRUMENT_TYPE_ETF,
    INSTRUMENT_TYPE_STOCK,
]