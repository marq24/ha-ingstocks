from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, COORDINATOR_KEY, DELAYED_TASK_KEY
from .coordinator import INGStocksCoordinator

PLATFORMS = ["sensor"]
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration (YAML hook, unused)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    isin: str = entry.data["isin"]

    if CONF_SCAN_INTERVAL in entry.options:
        scan_interval_min = int(entry.options[CONF_SCAN_INTERVAL])
        interval_source = "options"
    else:
        scan_interval_min = int(entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        interval_source = "data"

    # we have a SINGLE coordinator for ALL entries!
    coordinator: INGStocksCoordinator = hass.data.get(DOMAIN, {}).get(COORDINATOR_KEY, None)
    if coordinator is None:
        _LOGGER.info(f"ISIN {isin} create initial coordinator...")
        coordinator = INGStocksCoordinator(
            hass=hass,
            update_interval=timedelta(minutes=scan_interval_min),
        )
        coordinator.isin_add(isin)
        hass.data.setdefault(DOMAIN, {})[COORDINATOR_KEY] = coordinator
        try:
            await coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady:
            raise
        except Exception as err:
            raise ConfigEntryNotReady(str(err)) from err
    else:
        _LOGGER.info(f"ISIN {isin} added to existing coordinator...")
        coordinator.isin_add(isin)
        esc_count = 0
        while not coordinator.data and esc_count < 21:
            _LOGGER.debug(f"Waiting for initial coordinator data... {esc_count}")
            esc_count += 1
            await asyncio.sleep(2)

        # Schedule shared delayed task (single task for domain)
        _schedule_shared_delayed_task(hass)

    # we will probably don't need this...
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = isin

    _LOGGER.info(
        "ING Stocks Plus setup: ISIN=%s, scan_interval=%s min (source=%s)",
        isin,
        scan_interval_min,
        interval_source,
    )

    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _delayed_job(hass: HomeAssistant) -> None:
    """Run once, 20 seconds after being scheduled."""
    await asyncio.sleep(20)
    _LOGGER.debug("Delayed INGStocks task executed after 20s")
    # don't call the refresh for each of the config entries...
    try:
        multi_coordinator: INGStocksCoordinator = hass.data.get(DOMAIN, {}).get(COORDINATOR_KEY, None)
        await multi_coordinator._async_update_data()
    except Exception as err:
        _LOGGER.info(f"Failed to refresh multi-coordinator data: {err}")

def _schedule_shared_delayed_task(hass: HomeAssistant) -> None:
    """Create/replace one shared delayed task in hass.data."""
    domain_data = hass.data.setdefault(DOMAIN, {})

    old_task: asyncio.Task[Any] | None = domain_data.get(DELAYED_TASK_KEY)
    if old_task and not old_task.done():
        old_task.cancel()

    task = hass.loop.create_task(_delayed_job(hass))
    domain_data[DELAYED_TASK_KEY] = task


async def _async_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        isin: str = entry.data["isin"]
        multi_coordinator = hass.data.get(DOMAIN, {}).get(COORDINATOR_KEY, None)
        multi_coordinator.isin_remove(isin)
        if multi_coordinator.isin_is_empty():
            # cancel shared delayed task on final upload
            task: asyncio.Task[Any] | None = hass.data.get(DOMAIN, {}).pop(DELAYED_TASK_KEY, None)
            if task and not task.done():
                task.cancel()

            hass.data.get(DOMAIN, {}).pop(COORDINATOR_KEY, None)
    return unload_ok