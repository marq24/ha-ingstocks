from __future__ import annotations

import logging
import socket
import asyncio
import random

from typing import Any

from aiohttp import ClientTimeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class INGStocksCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, update_interval):
        self.session = async_get_clientsession(hass, family=socket.AF_INET)
        self.isin_list = []
        super().__init__(
            hass,
            _LOGGER,
            name=f"ING Stocks [MULTI]",
            update_interval=update_interval,
        )

    def isin_add(self, isin:str):
        if isin not in self.isin_list:
            _LOGGER.debug(f"Adding new ISIN {isin} to coordinator")
            self.isin_list.append(isin)

    def isin_remove(self, isin:str):
        if isin in self.isin_list:
            _LOGGER.debug(f"Remove active ISIN {isin} from coordinator")
            self.isin_list.remove(isin)

    def isin_is_empty(self) -> bool:
        return len(self.isin_list) == 0

    async def _async_update_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        errors: list[str] = []
        timeout = ClientTimeout(total=20)

        for isin in self.isin_list:
            # sleep for the second and all following isin's a random time...
            if len(data) > 0:
                await asyncio.sleep(random.uniform(1, 5))

            header_url = (
                f"https://component-api.wertpapiere.ing.de/api/v1/instrument-header?isinOrSearchTerm={isin}&isKnownIsin=true&includeAvailableExchanges=true"
            )
            keyfigures_url = (
                f"https://component-api.wertpapiere.ing.de/api/v1/share-ng/keyfigures/{isin}"
            )
            try:
                async with self.session.get(header_url, timeout=timeout) as resp:
                    if resp.status != 200:
                        _LOGGER.warning("instrumentheader HTTP %s for %s", resp.status, isin)
                        errors.append(isin)
                        continue
                    header = await resp.json()

                _LOGGER.debug(
                    "Request: %s - Status: %s - Response: %s",
                    resp.request_info.url, resp.status, str(header)[:200],
                )

                price = header.get("price")
                if price is None:
                    _LOGGER.warning("No price in instrumentheader for %s", isin)
                    errors.append(isin)
                    continue

                # keyfigures (optional, currently disabled)
                keyfigures: dict[str, Any] = {}
                keyfigures_available = False

                # async with self.session.get(keyfigures_url, timeout=20) as resp:
                #     if resp.status == 404:
                #         # bei vielen Instrumenten (ETFs etc.) normal
                #         _LOGGER.debug("No keyfigures for %s (HTTP 404).", self.isin)
                #     elif resp.status != 200:
                #         raise UpdateFailed(f"keyfigures HTTP {resp.status}")
                #     else:
                #         keyfigures = await resp.json()
                #         keyfigures_available = isinstance(keyfigures, dict)

                # 1:1 Attribute-Mapping wie in RalfEs73 sensor.py
                isin_data: dict[str, Any] = {
                    "name": header.get("name"),
                    "isin": header.get("isin") or isin,
                    "currency": header.get("currencySign"),
                    "change_percent": header.get("changePercent"),
                    "change_absolute": header.get("changeAbsolute"),
                    "exchange": header.get("exchangeName"),
                    "last_update": header.get("priceChangeDate"),
                    "price": price,
                    "keyfigures_available": bool(keyfigures_available),
                    "dividend_yield": keyfigures.get("dividendYield"),
                    "dividend_per_share": keyfigures.get("dividendPerShare"),
                    "price_earnings_ratio": keyfigures.get("priceEarningsRatio"),
                    "market_capitalization": keyfigures.get("marketCapitalization"),
                    "market_cap_currency": keyfigures.get("marketCapitalizationCurrencyIsoCode"),
                    "52w_low": keyfigures.get("fiftyTwoWeekLow"),
                    "52w_high": keyfigures.get("fiftyTwoWeekHigh"),
                }
                data[isin] = isin_data

            except TimeoutError:
                _LOGGER.warning("Timeout fetching data for %s – skipping", isin)
                errors.append(isin)
            except Exception as err:
                _LOGGER.warning("Error fetching data for %s: %s", isin, err)
                errors.append(isin)

        # Keep previous data for ISINs that failed this cycle
        if self.data:
            for isin in errors:
                if isin in self.data:
                    data[isin] = self.data[isin]
                    _LOGGER.debug("Reusing previous data for %s", isin)

        if not data:
            raise UpdateFailed(f"All ISINs failed: {errors}")

        if errors:
            _LOGGER.info("Update completed with errors for: %s", ", ".join(errors))

        return data
