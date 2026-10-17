"""Sensores: previsto, pagado y lo que falta del mes, lo pagado en el año y el próximo vencimiento.

El estado va en la moneda principal (opción de la integración); los atributos llevan el
total de cada moneda por separado, sin convertir.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import logica
from .const import CODIGO_MONEDA
from .entidad import EntidadFacturas
from .nucleo import Facturas, FacturasConfigEntry


async def async_setup_entry(
    hass: HomeAssistant, entry: FacturasConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    facturas = entry.runtime_data
    async_add_entities(
        [MesPrevisto(facturas), MesPagado(facturas), MesFalta(facturas), AnioPagado(facturas), Proxima(facturas)]
    )


def _inicio(dia: date) -> datetime:
    """Medianoche local de ese día (para ``last_reset``)."""
    return datetime.combine(dia, time.min, dt_util.get_default_time_zone())


class _Monetario(EntidadFacturas, SensorEntity):
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 0

    def __init__(self, facturas: Facturas, clave: str) -> None:
        self._attr_translation_key = clave
        self._attr_native_unit_of_measurement = CODIGO_MONEDA[facturas.moneda_principal]
        super().__init__(facturas, clave, "sensor", f"facturas_{clave}")

    def _totales(self, totales: dict[str, float]) -> dict[str, Any]:
        """Pone el estado en la moneda principal y devuelve un atributo por moneda."""
        self._attr_native_value = totales.get(self.facturas.moneda_principal, 0.0)
        return dict(totales)


class MesPrevisto(_Monetario):
    def __init__(self, facturas: Facturas) -> None:
        super().__init__(facturas, "mes_previsto")

    def actualizar(self) -> None:
        r = logica.resumen_mes(self.facturas.datos, self.facturas.hoy())
        self._attr_extra_state_attributes = {
            **self._totales(r["previsto"]),
            "periodo": r["periodo"],
            "por_categoria": r["por_categoria"],
            "cantidad": r["cantidad"]["total"] - r["cantidad"]["omitidos"],
        }


class MesPagado(_Monetario):
    def __init__(self, facturas: Facturas) -> None:
        super().__init__(facturas, "mes_pagado")

    def actualizar(self) -> None:
        hoy = self.facturas.hoy()
        r = logica.resumen_mes(self.facturas.datos, hoy)
        self._attr_last_reset = _inicio(hoy.replace(day=1))
        self._attr_extra_state_attributes = {
            **self._totales(r["pagado"]),
            "periodo": r["periodo"],
            "cantidad_pagos": r["cantidad"]["pagados"],
        }


class MesFalta(_Monetario):
    def __init__(self, facturas: Facturas) -> None:
        super().__init__(facturas, "mes_falta")

    def actualizar(self) -> None:
        r = logica.resumen_mes(self.facturas.datos, self.facturas.hoy())
        self._attr_extra_state_attributes = {
            **self._totales(r["falta"]),
            "periodo": r["periodo"],
            "cantidad": r["cantidad"]["pendientes"],
            "vencido": r["vencido"],
            "vencidos_anteriores": r["vencidos_anteriores"],
            "cantidad_vencidos_anteriores": len(r["pagos_vencidos_anteriores"]),
        }


class AnioPagado(_Monetario):
    def __init__(self, facturas: Facturas) -> None:
        super().__init__(facturas, "anio_pagado")

    def actualizar(self) -> None:
        hoy = self.facturas.hoy()
        r = logica.resumen_anio(self.facturas.datos, hoy)
        self._attr_last_reset = _inicio(date(hoy.year, 1, 1))
        self._attr_extra_state_attributes = {
            **self._totales(r["pagado"]),
            "anio": r["anio"],
            "media_mensual": r["media_mensual"],
        }


class Proxima(EntidadFacturas, SensorEntity):
    """Fecha del próximo vencimiento de pago manual pendiente."""

    _attr_device_class = SensorDeviceClass.DATE
    _attr_translation_key = "proxima"

    def __init__(self, facturas: Facturas) -> None:
        super().__init__(facturas, "proxima", "sensor", "facturas_proxima")

    def actualizar(self) -> None:
        hoy = self.facturas.hoy()
        proxima = logica.proximo_vencimiento(self.facturas.datos, hoy)
        if proxima is None:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
            return
        vence = date.fromisoformat(proxima["vence"])
        dias = (vence - hoy).days
        self._attr_native_value = vence
        self._attr_extra_state_attributes = {
            "servicio": proxima["nombre"],
            "servicio_id": proxima["servicio_id"],
            "periodo": proxima["periodo"],
            "importe": proxima["importe"],
            "moneda": proxima["moneda"],
            "previsto": proxima["previsto"],
            "dias": dias,
            "avisar": dias <= self.facturas.dias_aviso,
        }
