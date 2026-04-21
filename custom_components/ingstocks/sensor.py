from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_INSTRUMENT_TYPE,
    CONF_QUANTITY,
    DEFAULT_QUANTITY,
    INSTRUMENT_TYPE_AUTO, COORDINATOR_KEY,
)
from .coordinator import INGStocksCoordinator

_LOGGER = logging.getLogger(__name__)


def _safe_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _get_quantity(entry: ConfigEntry) -> float:
    q = entry.options.get(CONF_QUANTITY, entry.data.get(CONF_QUANTITY, DEFAULT_QUANTITY))
    try:
        qf = float(q)
        return qf if qf >= 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: INGStocksCoordinator = hass.data[DOMAIN][COORDINATOR_KEY]
    isin = hass.data[DOMAIN][entry.entry_id]

    custom_name = entry.options.get(CONF_NAME, entry.data.get(CONF_NAME))
    if custom_name:
        coordinator.display_name = custom_name
    else:
        coordinator.display_name = (coordinator.data or {}).get("name") or entry.title

    instrument_type = entry.options.get(
        CONF_INSTRUMENT_TYPE,
        entry.data.get(CONF_INSTRUMENT_TYPE, INSTRUMENT_TYPE_AUTO),
    )

    monetary_unit = "€"

    # Preis & Änderungen IMMER anlegen (unabhängig von Keyfigures)
    sensors: list[SensorEntity] = [
        INGStockValueSensor(
            coordinator, entry, instrument_type,
            key="price",
            entity_name="Preis",
            unique_suffix="price",
            device_class=SensorDeviceClass.MONETARY,
            unit=monetary_unit,
            precision=2,
        ),
        INGStockValueSensor(
            coordinator, entry, instrument_type,
            key="change_percent",
            entity_name="Änderung %",
            unique_suffix="change_percent",
            device_class=None,
            unit="%",
            precision=2,
        ),
        INGStockValueSensor(
            coordinator, entry, instrument_type,
            key="change_absolute",
            entity_name="Änderung",
            unique_suffix="change_absolute",
            device_class=SensorDeviceClass.MONETARY,
            unit=monetary_unit,
            precision=3,
        ),
        INGStockLastUpdateSensor(coordinator, entry),
    ]

    # Positionswert nur bei quantity > 0
    if _get_quantity(entry) > 0:
        sensors.append(
            INGStockPositionValueSensor(
                coordinator=coordinator,
                entry=entry,
                instrument_type=instrument_type,
                unit=monetary_unit,
            )
        )

    # Keyfigures-Sensoren: IMMER anlegen, aber werden None wenn API nichts liefert.
    # Dadurch verschwinden Entities nicht mehr aus der Registry.
    sensors.extend(
        [
            INGStockValueSensor(
                coordinator, entry, instrument_type,
                key="dividend_yield",
                entity_name="Dividendenrendite",
                unique_suffix="dividend_yield",
                device_class=None,
                unit="%",
                precision=4,
            ),
            INGStockValueSensor(
                coordinator, entry, instrument_type,
                key="dividend_per_share",
                entity_name="Dividende je Anteil",
                unique_suffix="dividend_per_share",
                device_class=SensorDeviceClass.MONETARY,
                unit=monetary_unit,
                precision=3,
            ),
            INGStockValueSensor(
                coordinator, entry, instrument_type,
                key="price_earnings_ratio",
                entity_name="KGV",
                unique_suffix="price_earnings_ratio",
                device_class=None,
                unit=None,
                precision=2,
            ),
            INGStockValueSensor(
                coordinator, entry, instrument_type,
                key="market_capitalization",
                entity_name="Marktkapitalisierung",
                unique_suffix="market_capitalization",
                device_class=None,
                unit=None,
                precision=0,
            ),
            # Market cap currency als "Wert" (Text), bleibt aber Entity-stabil
            INGStockTextSensor(
                coordinator, entry, instrument_type,
                key="market_cap_currency",
                entity_name="Marktkap.-Währung",
                unique_suffix="market_cap_currency",
            ),
            INGStockValueSensor(
                coordinator, entry, instrument_type,
                key="52w_low",
                entity_name="52W Tief",
                unique_suffix="52w_low",
                device_class=SensorDeviceClass.MONETARY,
                unit=monetary_unit,
                precision=3,
            ),
            INGStockValueSensor(
                coordinator, entry, instrument_type,
                key="52w_high",
                entity_name="52W Hoch",
                unique_suffix="52w_high",
                device_class=SensorDeviceClass.MONETARY,
                unit=monetary_unit,
                precision=3,
            ),
        ]
    )

    async_add_entities(sensors, False)


class INGStockBaseSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: INGStocksCoordinator, entry: ConfigEntry):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self.isin = entry.data.get("isin", None)

    @property
    def available(self) -> bool:
        # Bei fehlenden Keyfigures sollen Entities trotzdem existieren, aber eben None als value haben.
        return self.coordinator.last_update_success and self.coordinator.data.get(self.isin, {}).get("price") is not None

    @property
    def device_info(self):
        d = self.coordinator.data.get(self.isin, {})
        return {
            "identifiers": {(DOMAIN, self.isin)},
            "name": self.coordinator.display_name or d.get("name") or self.entry.title,
            "manufacturer": "ING (component-api.wertpapiere.ing.de)",
            "model": self.isin,
        }

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))


class INGStockValueSensor(INGStockBaseSensor):
    def __init__(
        self,
        coordinator: INGStocksCoordinator,
        entry: ConfigEntry,
        instrument_type: str,
        key: str,
        entity_name: str,
        unique_suffix: str,
        device_class: SensorDeviceClass | None,
        unit: str | None,
        precision: int | None,
    ):
        super().__init__(coordinator, entry)
        self.instrument_type = instrument_type
        self.key = key
        self._precision = precision

        self._attr_name = entity_name
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit

        # 🔒 Stabiler Unique-ID-Suffix (ändert sich nicht, auch wenn entity_name übersetzt/umbenannt wird)
        self._attr_unique_id = f"{DOMAIN}_{self.isin}_{unique_suffix}"

        if device_class == SensorDeviceClass.MONETARY:
            self._attr_state_class = None
        else:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def icon(self) -> str | None:
        d = self.coordinator.data.get(self.isin, {})

        if self.key == "price":
            return "mdi:chart-line"

        if self.key in ("change_percent", "change_absolute"):
            v = _safe_float(d.get(self.key))
            if v is None:
                return "mdi:trending-neutral"
            if v > 0:
                return "mdi:trending-up"
            if v < 0:
                return "mdi:trending-down"
            return "mdi:trending-neutral"

        if self.key == "dividend_yield":
            return "mdi:cash-percent"
        if self.key == "dividend_per_share":
            return "mdi:cash"
        if self.key == "price_earnings_ratio":
            return "mdi:calculator-variant"
        if self.key == "market_capitalization":
            return "mdi:bank"
        if self.key in ("52w_low", "52w_high"):
            return "mdi:arrow-expand-vertical"

        return "mdi:finance"

    @property
    def extra_state_attributes(self):
        d = self.coordinator.data.get(self.isin, {})
        quantity = _get_quantity(self.entry)

        return {
            "name": d.get("name"),
            "isin": d.get("isin"),
            "currency": d.get("currency"),
            "change_percent": d.get("change_percent"),
            "change_absolute": d.get("change_absolute"),
            "exchange": d.get("exchange"),
            "last_update": d.get("last_update"),

            "dividend_yield": d.get("dividend_yield"),
            "dividend_per_share": d.get("dividend_per_share"),
            "price_earnings_ratio": d.get("price_earnings_ratio"),
            "market_capitalization": d.get("market_capitalization"),
            "market_cap_currency": d.get("market_cap_currency"),
            "52w_low": d.get("52w_low"),
            "52w_high": d.get("52w_high"),

            "instrument_type_selected": self.instrument_type,
            "quantity": quantity,
        }

    @property
    def native_value(self):
        value = self.coordinator.data.get(self.isin, {}).get(self.key)
        if value is None:
            return None

        if self._precision is not None:
            f = _safe_float(value)
            if f is not None:
                return round(f, self._precision)

        return value


class INGStockTextSensor(INGStockBaseSensor):
    """Text sensor for values like market_cap_currency to keep entity stable."""

    _attr_device_class = None
    _attr_state_class = None

    def __init__(
        self,
        coordinator: INGStocksCoordinator,
        entry: ConfigEntry,
        instrument_type: str,
        key: str,
        entity_name: str,
        unique_suffix: str,
    ):
        super().__init__(coordinator, entry)
        self.instrument_type = instrument_type
        self.key = key
        self._attr_name = entity_name
        self._attr_unique_id = f"{DOMAIN}_{self.isin}_{unique_suffix}"

    @property
    def icon(self) -> str | None:
        return "mdi:currency-sign"

    @property
    def extra_state_attributes(self):
        d = self.coordinator.data.get(self.isin, {})
        return {
            "name": d.get("name"),
            "isin": d.get("isin"),
            "exchange": d.get("exchange"),
            "currency": d.get("currency"),
            "last_update": d.get("last_update"),
            "instrument_type_selected": self.instrument_type,
        }

    @property
    def native_value(self):
        v = self.coordinator.data.get(self.isin, {}).get(self.key)
        return str(v) if v is not None else None


class INGStockPositionValueSensor(INGStockBaseSensor):
    """Positionswert (price * quantity)."""

    def __init__(
        self,
        coordinator: INGStocksCoordinator,
        entry: ConfigEntry,
        instrument_type: str,
        unit: str,
    ):
        super().__init__(coordinator, entry)
        self.instrument_type = instrument_type
        self._attr_name = "Positionswert"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = None
        self._attr_unique_id = f"{DOMAIN}_{self.isin}_position_value"

    @property
    def icon(self) -> str | None:
        return "mdi:briefcase"

    @property
    def extra_state_attributes(self):
        d = self.coordinator.data.get(self.isin, {})
        return {
            "name": d.get("name"),
            "isin": d.get("isin"),
            "exchange": d.get("exchange"),
            "currency": d.get("currency"),
            "last_update": d.get("last_update"),
            "instrument_type_selected": self.instrument_type,
            "quantity": _get_quantity(self.entry),
            "unit_price": d.get("price"),
        }

    @property
    def native_value(self):
        d = self.coordinator.data.get(self.isin, {})
        price = _safe_float(d.get("price"))
        quantity = _get_quantity(self.entry)
        if price is None or quantity <= 0:
            return None
        return round(price * quantity, 2)


class INGStockLastUpdateSensor(INGStockBaseSensor):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_name = "Letztes Update"
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: INGStocksCoordinator, entry: ConfigEntry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{DOMAIN}_{self.isin}_last_update"

    @property
    def native_value(self):
        raw = self.coordinator.data.get(self.isin, {}).get("last_update")
        if not raw:
            return None
        dt = dt_util.parse_datetime(raw)
        return dt_util.as_utc(dt) if dt else None