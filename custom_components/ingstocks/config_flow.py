# config_flow.py
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_ISIN,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_INSTRUMENT_TYPE,
    CONF_QUANTITY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_QUANTITY,
    INSTRUMENT_TYPE_OPTIONS,
    INSTRUMENT_TYPE_AUTO,
)

from homeassistant.config_entries import ConfigFlowResult, SOURCE_RECONFIGURE

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._default_isin = ""
        self._default_name = ""
        self._default_scan_interval = DEFAULT_SCAN_INTERVAL
        self._default_instrument_type = INSTRUMENT_TYPE_AUTO
        self._default_quantity = DEFAULT_QUANTITY

    async def async_step_reconfigure(self, user_input: dict | None = None) -> ConfigFlowResult:
        entry_data = self._get_reconfigure_entry().data
        self._default_isin = entry_data.get(CONF_ISIN, "")
        self._default_name = entry_data.get(CONF_NAME, "")
        self._default_scan_interval = entry_data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        self._default_instrument_type = entry_data.get(CONF_INSTRUMENT_TYPE, INSTRUMENT_TYPE_AUTO)
        self._default_quantity = entry_data.get(CONF_QUANTITY, DEFAULT_QUANTITY)
        return await self.async_step_user()

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        is_reconfigure = self.source == SOURCE_RECONFIGURE
        if user_input is None:
            isin = getattr(self, '_default_isin', "")
            name = getattr(self, '_default_name', "")
            scan_interval = getattr(self, '_default_scan_interval', DEFAULT_SCAN_INTERVAL)
            instrument_type = getattr(self, '_default_instrument_type', INSTRUMENT_TYPE_AUTO)
            quantity = getattr(self, '_default_quantity', DEFAULT_QUANTITY)

            fields = {}
            if not is_reconfigure:
                fields[vol.Required(CONF_ISIN, default=isin)] = str
            fields[vol.Optional(CONF_NAME, default=name)] = str
            fields[vol.Required(CONF_SCAN_INTERVAL, default=scan_interval)] = vol.All(int, vol.Range(min=1, max=360))
            fields[vol.Required(CONF_INSTRUMENT_TYPE, default=instrument_type)] = vol.In(INSTRUMENT_TYPE_OPTIONS)
            fields[vol.Optional(CONF_QUANTITY, default=quantity)] = vol.All(vol.Coerce(float), vol.Range(min=0))

            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(fields),
                description_placeholders={CONF_ISIN: f" {getattr(self, '_default_isin', "")}"} if is_reconfigure else {CONF_ISIN: ""},
            )

        # On reconfigure, ISIN is not in user_input – reuse stored value
        isin = (self._default_isin if is_reconfigure else user_input[CONF_ISIN]).strip().upper()
        name = (user_input.get(CONF_NAME) or "").strip()
        scan_interval = int(user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        instrument_type = user_input.get(CONF_INSTRUMENT_TYPE, INSTRUMENT_TYPE_AUTO)
        quantity = float(user_input.get(CONF_QUANTITY, DEFAULT_QUANTITY))
        title = name if name else f"ING {isin}"

        data = {
            CONF_ISIN: isin,
            CONF_NAME: name,
            CONF_SCAN_INTERVAL: scan_interval,
            CONF_INSTRUMENT_TYPE: instrument_type,
            CONF_QUANTITY: quantity,
        }

        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_reload_and_abort(
                entry=self._get_reconfigure_entry(),
                data=data,
                title=title,
            )

        await self.async_set_unique_id(f"{DOMAIN}_{isin}")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=title, data=data)
