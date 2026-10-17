"""Facturas: servicios que se pagan, sus precios, vencimientos y lo pagado cada mes."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .nucleo import Facturas, FacturasConfigEntry
from .panel import quitar_panel, registrar_panel
from .servicios import registrar_acciones
from .websocket import registrar_comandos

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATAFORMAS = [Platform.SENSOR, Platform.TODO, Platform.CALENDAR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Registra las acciones y los comandos WebSocket (existen aunque la integración no esté configurada)."""
    registrar_acciones(hass)
    registrar_comandos(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: FacturasConfigEntry) -> bool:
    facturas = await Facturas.crear(hass, entry)
    await facturas.iniciar()
    entry.runtime_data = facturas
    entry.async_on_unload(facturas.detener)
    await hass.config_entries.async_forward_entry_setups(entry, PLATAFORMAS)
    await registrar_panel(hass)
    entry.async_on_unload(lambda: quitar_panel(hass))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FacturasConfigEntry) -> bool:
    # Los datos en .storage/facturas no se borran nunca desde acá, ni al quitar la integración:
    # si se vuelve a agregar, el historial sigue ahí.
    return await hass.config_entries.async_unload_platforms(entry, PLATAFORMAS)
