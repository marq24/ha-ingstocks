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
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_INSTRUMENT_TYPE,
    INSTRUMENT_TYPE_AUTO,
)
from .coordinator import INGStocksCoordinator

_LOGGER = logging.getLogger(__name__)


def _safe_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: INGStocksCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Display name (options override entry data)
    custom_name = entry.options.get(CONF_NAME, entry.data.get(CONF_NAME))
    if custom_name:
        coordinator.display_name = custom_name
    else:
        coordinator.display_name = (coordinator.data or {}).get("name") or entry.title

    instrument_type = entry.options.get(
        CONF_INSTRUMENT_TYPE,
        entry.data.get(CONF_INSTRUMENT_TYPE, INSTRUMENT_TYPE_AUTO),
    )

    # Wie bei RalfEs73: monetary sensors nutzen "€" als Einheit
    monetary_unit = "€"

    sensors: list[SensorEntity] = [
        INGStockValueSensor(
            coordinator, entry, instrument_type, "price", "Preis",
            SensorDeviceClass.MONETARY, monetary_unit, 2
        ),
        INGStockValueSensor(
            coordinator, entry, instrument_type, "change_percent", "Änderung %",
            None, "%", 2
        ),
        INGStockValueSensor(
            coordinator, entry, instrument_type, "change_absolute", "Änderung",
            SensorDeviceClass.MONETARY, monetary_unit, 3
        ),
        INGStockLastUpdateSensor(coordinator, entry),
    ]

    # Keyfigures only if available (some instruments return 404)
    if (coordinator.data or {}).get("keyfigures_available"):
        sensors.extend(
            [
                INGStockValueSensor(
                    coordinator, entry, instrument_type, "dividend_yield", "Dividendenrendite",
                    None, "%", 4
                ),
                INGStockValueSensor(
                    coordinator, entry, instrument_type, "dividend_per_share", "Dividende je Anteil",
                    SensorDeviceClass.MONETARY, monetary_unit, 3
                ),
                INGStockValueSensor(
                    coordinator, entry, instrument_type, "price_earnings_ratio", "KGV",
                    None, None, 2
                ),
                INGStockValueSensor(
                    coordinator, entry, instrument_type, "market_capitalization", "Marktkapitalisierung",
                    None, None, 0
                ),
                INGStockValueSensor(
                    coordinator, entry, instrument_type, "market_cap_currency", "Marktkap.-Währung",
                    None, None, None
                ),
                INGStockValueSensor(
                    coordinator, entry, instrument_type, "52w_low", "52W Tief",
                    SensorDeviceClass.MONETARY, monetary_unit, 3
                ),
                INGStockValueSensor(
                    coordinator, entry, instrument_type, "52w_high", "52W Hoch",
                    SensorDeviceClass.MONETARY, monetary_unit, 3
                ),
            ]
        )

    async_add_entities(sensors, True)


class INGStockBaseSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: INGStocksCoordinator, entry: ConfigEntry):
        self.coordinator = coordinator
        self.entry = entry

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and (self.coordinator.data or {}).get("price") is not None

    @property
    def device_info(self):
        d = self.coordinator.data or {}
        return {
            "identifiers": {(DOMAIN, self.coordinator.isin)},
            "name": self.coordinator.display_name or d.get("name") or self.entry.title,
            "manufacturer": "ING (component-api.wertpapiere.ing.de)",
            "model": self.coordinator.isin,
        }

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))

    async def async_update(self) -> None:
        await self.coordinator.async_request_refresh()


class INGStockValueSensor(INGStockBaseSensor):
    def __init__(
        self,
        coordinator: INGStocksCoordinator,
        entry: ConfigEntry,
        instrument_type: str,
        key: str,
        entity_name: str,
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
        self._attr_unique_id = f"{DOMAIN}_{coordinator.isin}_{key}"

        # Monetary must not be MEASUREMENT (HA rule)
        if device_class == SensorDeviceClass.MONETARY:
            self._attr_state_class = None
        else:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def icon(self) -> str | None:
        d = self.coordinator.data or {}

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
        """
        Vollständige Attributliste wie bei RalfEs73 (plus instrument_type_selected).
        Dadurch siehst du am Sensor wieder alle Kennzahlen im Attribute-Block.
        """
        d = self.coordinator.data or {}
        return {
            # Basisdaten (Ralf)
            "name": d.get("name"),
            "isin": d.get("isin"),
            "currency": d.get("currency"),
            "change_percent": d.get("change_percent"),
            "change_absolute": d.get("change_absolute"),
            "exchange": d.get("exchange"),
            "last_update": d.get("last_update"),

            # Keyfigures (Ralf)
            "dividend_yield": d.get("dividend_yield"),
            "dividend_per_share": d.get("dividend_per_share"),
            "price_earnings_ratio": d.get("price_earnings_ratio"),
            "market_capitalization": d.get("market_capitalization"),
            "market_cap_currency": d.get("market_cap_currency"),
            "52w_low": d.get("52w_low"),
            "52w_high": d.get("52w_high"),

            # Deine Option
            "instrument_type_selected": self.instrument_type,
        }

    @property
    def native_value(self):
        value = (self.coordinator.data or {}).get(self.key)
        if value is None:
            return None

        if self._precision is not None:
            f = _safe_float(value)
            if f is not None:
                return round(f, self._precision)

        return value


class INGStockLastUpdateSensor(INGStockBaseSensor):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_name = "Letztes Update"
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: INGStocksCoordinator, entry: ConfigEntry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.isin}_last_update"

    @property
    def extra_state_attributes(self):
        # Optional: auch am Timestamp-Sensor die komplette Attributliste anzeigen
        d = self.coordinator.data or {}
        return {
            "name": d.get("name"),
            "isin": d.get("isin"),
            "currency": d.get("currency"),
            "change_percent": d.get("change_percent"),
            "change_absolute": d.get("change_absolute"),
            "exchange": d.get("exchange"),
        }

    @property
    def native_value(self):
        raw = (self.coordinator.data or {}).get("last_update")
        if not raw:
            return None
        dt = dt_util.parse_datetime(raw)
        return dt_util.as_utc(dt) if dt else None
