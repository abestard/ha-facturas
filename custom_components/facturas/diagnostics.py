"""Diagnóstico descargable (Ajustes → Dispositivos y servicios → Facturas → Descargar diagnóstico)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import logica
from .nucleo import FacturasConfigEntry

# Los correos de los remitentes no hacen falta para investigar un problema.
OCULTAR = {"remitente"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: FacturasConfigEntry) -> dict[str, Any]:
    facturas = entry.runtime_data
    datos, hoy = facturas.datos, facturas.hoy()
    return {
        "opciones": dict(entry.options),
        "hoy": hoy.isoformat(),
        "zona_horaria": hass.config.time_zone,
        "cantidades": {
            "servicios": len(datos.servicios),
            "activos": sum(s.activo for s in datos.servicios.values()),
            "pagos": len(datos.pagos),
            "pendientes": len(logica.pendientes(datos, hoy)),
        },
        "resumen_mes": {k: v for k, v in logica.resumen_mes(datos, hoy).items() if k != "pagos_vencidos_anteriores"},
        "datos": async_redact_data(datos.a_dict(), OCULTAR),
    }
