"""``calendar.facturas``: los vencimientos (pagos generados y la previsión) como eventos de día completo."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import logica
from .entidad import EntidadFacturas
from .nucleo import Facturas, FacturasConfigEntry


async def async_setup_entry(
    hass: HomeAssistant, entry: FacturasConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([CalendarioFacturas(entry.runtime_data)])


def formato_importe(valor: float) -> str:
    """1650 → "1.650"; 1490.5 → "1.490,5" (como se escribe en Uruguay)."""
    entero, _, decimales = f"{valor:.2f}".partition(".")
    con_puntos = f"{int(entero):,}".replace(",", ".")
    decimales = decimales.rstrip("0")
    return f"{con_puntos},{decimales}" if decimales else con_puntos


def _evento(datos: dict[str, Any]) -> CalendarEvent:
    vence = date.fromisoformat(datos["vence"])
    estado = "previsto" if datos["previsto"] else datos["estado"]
    simbolo = "US$" if datos["moneda"] == "dolares" else "$"
    forma = "débito automático" if datos["pago"] == "debito" else "manual"
    return CalendarEvent(
        start=vence,
        end=vence + timedelta(days=1),
        summary=f"{datos['nombre']}: {simbolo} {formato_importe(datos['importe'])}",
        description=f"Período {datos['periodo']}. Estado: {estado}. Pago {forma}.",
        uid=f"{datos['servicio_id']}|{datos['periodo']}",
    )


class CalendarioFacturas(EntidadFacturas, CalendarEntity):
    _attr_name = None  # toma el nombre del dispositivo: "Facturas"

    def __init__(self, facturas: Facturas) -> None:
        self._proximo: CalendarEvent | None = None
        super().__init__(facturas, "calendario", "calendar", "facturas")

    def actualizar(self) -> None:
        hoy = self.facturas.hoy()
        proximos = [
            e
            for e in logica.eventos(self.facturas.datos, hoy, hoy, hoy + timedelta(days=400))
            if e["estado"] == "pendiente"
        ]
        self._proximo = _evento(proximos[0]) if proximos else None

    @property
    def event(self) -> CalendarEvent | None:
        """El próximo vencimiento pendiente (el calendario está "on" durante ese día)."""
        return self._proximo

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        desde = dt_util.as_local(start_date).date()
        # end_date es exclusivo: un evento de día completo que empieza justo ahí no entra.
        hasta = (dt_util.as_local(end_date) - timedelta(microseconds=1)).date()
        if hasta < desde:
            return []
        return [_evento(e) for e in logica.eventos(self.facturas.datos, self.facturas.hoy(), desde, hasta)]
