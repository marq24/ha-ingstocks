# config_flow.py
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

from .const import (
    DOMAIN,
    CONF_ISIN,
    CONF_ISINS,
    CONF_ISIN_CONFIG,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_INSTRUMENT_TYPE,
    CONF_QUANTITY,
    CONF_SELECTED_ISIN,
    ADD_NEW_ISIN,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_QUANTITY,
    INSTRUMENT_TYPE_OPTIONS,
    INSTRUMENT_TYPE_AUTO,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    def __init__(self) -> None:
        self._existing_entry: config_entries.ConfigEntry | None = None
        self._editing_isin: str | None = None

    # ------------------------------------------------------------------
    # STEP: user  (initial add or redirect to select_isin)
    # ------------------------------------------------------------------
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entries = self._async_current_entries()
        if entries:
            # Integration already set up → manage ISINs on existing entry
            self._existing_entry = entries[0]
            return await self.async_step_select_isin()

        # First-time setup: ISIN + global scan_interval
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_ISIN): str,
                        vol.Optional(CONF_NAME, default=""): str,
                        vol.Required(
                            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                        ): vol.All(int, vol.Range(min=1, max=360)),
                        vol.Required(
                            CONF_INSTRUMENT_TYPE, default=INSTRUMENT_TYPE_AUTO
                        ): vol.In(INSTRUMENT_TYPE_OPTIONS),
                        vol.Optional(CONF_QUANTITY, default=DEFAULT_QUANTITY): vol.All(
                            vol.Coerce(float), vol.Range(min=0)
                        ),
                    }
                ),
            )

        isin = user_input[CONF_ISIN].strip().upper()
        name = (user_input.get(CONF_NAME) or "").strip()
        scan_interval = int(user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        instrument_type = user_input.get(CONF_INSTRUMENT_TYPE, INSTRUMENT_TYPE_AUTO)
        quantity = float(user_input.get(CONF_QUANTITY, DEFAULT_QUANTITY))

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title="ING Stocks",
            data={
                CONF_SCAN_INTERVAL: scan_interval,
                CONF_ISINS: [isin],
                CONF_ISIN_CONFIG: {
                    isin: {
                        CONF_NAME: name,
                        CONF_QUANTITY: quantity,
                        CONF_INSTRUMENT_TYPE: instrument_type,
                    }
                },
            },
        )

    # ------------------------------------------------------------------
    # STEP: reconfigure  (entry menu → select_isin)
    # ------------------------------------------------------------------
    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._existing_entry = self._get_reconfigure_entry()
        return await self.async_step_select_isin()

    # ------------------------------------------------------------------
    # STEP: select_isin  (list existing ISINs + "Add new")
    # ------------------------------------------------------------------
    async def async_step_select_isin(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._existing_entry is not None
        entry_data = self._existing_entry.data
        isins: list[str] = list(entry_data.get(CONF_ISINS, []))
        isin_config: dict[str, dict] = entry_data.get(CONF_ISIN_CONFIG, {})

        # Build selectable options: "ISIN - Name" for each existing + add-new
        options: dict[str, str] = {}
        for isin in isins:
            cfg = isin_config.get(isin, {})
            label = cfg.get(CONF_NAME) or isin
            if label != isin:
                label = f"{isin} – {label}"
            options[isin] = label
        options[ADD_NEW_ISIN] = "➕ Add new ISIN"

        if user_input is None:
            current_scan = int(
                entry_data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            )
            return self.async_show_form(
                step_id="select_isin",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_SELECTED_ISIN): vol.In(options),
                        vol.Required(
                            CONF_SCAN_INTERVAL, default=current_scan
                        ): vol.All(int, vol.Range(min=1, max=360)),
                    }
                ),
            )

        # Save potentially updated scan_interval
        new_scan = int(user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        if new_scan != int(entry_data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)):
            new_data = dict(entry_data)
            new_data[CONF_SCAN_INTERVAL] = new_scan
            self.hass.config_entries.async_update_entry(
                self._existing_entry, data=new_data
            )

        selected = user_input[CONF_SELECTED_ISIN]
        if selected == ADD_NEW_ISIN:
            return await self.async_step_add_isin()

        self._editing_isin = selected
        return await self.async_step_edit_isin()

    # ------------------------------------------------------------------
    # STEP: add_isin
    # ------------------------------------------------------------------
    async def async_step_add_isin(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._existing_entry is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            isin = user_input[CONF_ISIN].strip().upper()
            existing_isins = list(
                self._existing_entry.data.get(CONF_ISINS, [])
            )

            if isin in existing_isins:
                errors[CONF_ISIN] = "isin_already_configured"
            else:
                name = (user_input.get(CONF_NAME) or "").strip()
                instrument_type = user_input.get(
                    CONF_INSTRUMENT_TYPE, INSTRUMENT_TYPE_AUTO
                )
                quantity = float(user_input.get(CONF_QUANTITY, DEFAULT_QUANTITY))

                new_data = dict(self._existing_entry.data)
                new_data[CONF_ISINS] = existing_isins + [isin]
                new_data[CONF_ISIN_CONFIG] = dict(
                    new_data.get(CONF_ISIN_CONFIG, {})
                )
                new_data[CONF_ISIN_CONFIG][isin] = {
                    CONF_NAME: name,
                    CONF_QUANTITY: quantity,
                    CONF_INSTRUMENT_TYPE: instrument_type,
                }

                self.hass.config_entries.async_update_entry(
                    self._existing_entry, data=new_data
                )
                await self.hass.config_entries.async_reload(
                    self._existing_entry.entry_id
                )
                return self.async_abort(reason="reconfigured")

        return self.async_show_form(
            step_id="add_isin",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ISIN): str,
                    vol.Optional(CONF_NAME, default=""): str,
                    vol.Required(
                        CONF_INSTRUMENT_TYPE, default=INSTRUMENT_TYPE_AUTO
                    ): vol.In(INSTRUMENT_TYPE_OPTIONS),
                    vol.Optional(CONF_QUANTITY, default=DEFAULT_QUANTITY): vol.All(
                        vol.Coerce(float), vol.Range(min=0)
                    ),
                }
            ),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # STEP: edit_isin  (ISIN is read-only, shown in description)
    # ------------------------------------------------------------------
    async def async_step_edit_isin(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._existing_entry is not None
        assert self._editing_isin is not None
        isin = self._editing_isin
        isin_config = self._existing_entry.data.get(CONF_ISIN_CONFIG, {})
        cfg = isin_config.get(isin, {})

        if user_input is not None:
            name = (user_input.get(CONF_NAME) or "").strip()
            instrument_type = user_input.get(
                CONF_INSTRUMENT_TYPE, INSTRUMENT_TYPE_AUTO
            )
            quantity = float(user_input.get(CONF_QUANTITY, DEFAULT_QUANTITY))

            new_data = dict(self._existing_entry.data)
            new_data[CONF_ISIN_CONFIG] = dict(new_data.get(CONF_ISIN_CONFIG, {}))
            new_data[CONF_ISIN_CONFIG][isin] = {
                CONF_NAME: name,
                CONF_QUANTITY: quantity,
                CONF_INSTRUMENT_TYPE: instrument_type,
            }

            self.hass.config_entries.async_update_entry(
                self._existing_entry, data=new_data
            )
            await self.hass.config_entries.async_reload(
                self._existing_entry.entry_id
            )
            return self.async_abort(reason="reconfigured")

        return self.async_show_form(
            step_id="edit_isin",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NAME, default=cfg.get(CONF_NAME, "")
                    ): str,
                    vol.Required(
                        CONF_INSTRUMENT_TYPE,
                        default=cfg.get(CONF_INSTRUMENT_TYPE, INSTRUMENT_TYPE_AUTO),
                    ): vol.In(INSTRUMENT_TYPE_OPTIONS),
                    vol.Optional(
                        CONF_QUANTITY,
                        default=float(cfg.get(CONF_QUANTITY, DEFAULT_QUANTITY)),
                    ): vol.All(vol.Coerce(float), vol.Range(min=0)),
                }
            ),
            description_placeholders={CONF_ISIN: isin},
        )
