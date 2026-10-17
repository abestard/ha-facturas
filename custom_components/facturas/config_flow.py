"""Instalación desde la interfaz: una sola instancia, con moneda principal y días de aviso."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DIAS_AVISO_PREDETERMINADOS,
    DOMAIN,
    MONEDA_PREDETERMINADA,
    OPCION_DIAS_AVISO,
    OPCION_MONEDA,
)
from .logica import MONEDAS


def _esquema(valores: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                OPCION_MONEDA, default=valores.get(OPCION_MONEDA, MONEDA_PREDETERMINADA)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=list(MONEDAS), translation_key=OPCION_MONEDA)
            ),
            vol.Required(
                OPCION_DIAS_AVISO, default=valores.get(OPCION_DIAS_AVISO, DIAS_AVISO_PREDETERMINADOS)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=30, step=1, mode=selector.NumberSelectorMode.BOX)
            ),
        }
    )


def _limpiar(entrada: dict[str, Any]) -> dict[str, Any]:
    return {**entrada, OPCION_DIAS_AVISO: int(entrada[OPCION_DIAS_AVISO])}


class FacturasConfigFlow(ConfigFlow, domain=DOMAIN):
    """Alta de la integración (``single_config_entry`` en el manifiesto evita una segunda)."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="Facturas", data={}, options=_limpiar(user_input))
        return self.async_show_form(step_id="user", data_schema=_esquema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> FacturasOptionsFlow:
        return FacturasOptionsFlow()


class FacturasOptionsFlow(OptionsFlowWithReload):
    """Cambiar la moneda principal y los días de aviso."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=_limpiar(user_input))
        return self.async_show_form(step_id="init", data_schema=_esquema(dict(self.config_entry.options)))
