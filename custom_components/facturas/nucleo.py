"""El estado vivo de la integración: los datos cargados, el cambio de mes y el guardado."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date, datetime
import logging
from typing import Any, TypeVar

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from . import logica
from .almacen import Almacen
from .const import DIAS_AVISO_PREDETERMINADOS, MONEDA_PREDETERMINADA, OPCION_DIAS_AVISO, OPCION_MONEDA, SENAL_ACTUALIZADO
from .logica import Datos

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")

type FacturasConfigEntry = ConfigEntry[Facturas]


class Facturas:
    """Datos cargados en memoria; cada cambio pasa por ``cambiar`` y se guarda enseguida."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, almacen: Almacen, datos: Datos) -> None:
        self.hass = hass
        self.entry = entry
        self.almacen = almacen
        self.datos = datos
        self._lock = asyncio.Lock()
        self._cancelar_medianoche: CALLBACK_TYPE | None = None

    @classmethod
    async def crear(cls, hass: HomeAssistant, entry: ConfigEntry) -> Facturas:
        almacen = Almacen(hass)
        return cls(hass, entry, almacen, await almacen.cargar())

    # -- opciones ---------------------------------------------------------

    @property
    def moneda_principal(self) -> str:
        return self.entry.options.get(OPCION_MONEDA, MONEDA_PREDETERMINADA)

    @property
    def dias_aviso(self) -> int:
        return int(self.entry.options.get(OPCION_DIAS_AVISO, DIAS_AVISO_PREDETERMINADOS))

    @staticmethod
    def hoy() -> date:
        """La fecha local de HA (la zona horaria configurada, no la del sistema)."""
        return dt_util.now().date()

    # -- ciclo de vida ----------------------------------------------------

    async def iniciar(self) -> None:
        """Genera los pagos que falten (por si HA estuvo apagado) y programa el cambio de mes."""
        await self.generar()
        # Se revisa cada medianoche: generar es idempotente y solo crea algo el día 1
        # (o si se perdió un cambio de mes). Es una cuenta en memoria, no pesa.
        self._cancelar_medianoche = async_track_time_change(
            self.hass, self._medianoche, hour=0, minute=0, second=5
        )

    @callback
    def detener(self) -> None:
        if self._cancelar_medianoche is not None:
            self._cancelar_medianoche()
            self._cancelar_medianoche = None

    async def _medianoche(self, _ahora: datetime) -> None:
        await self.generar()
        # Aunque no se genere nada, cambió "hoy": vencidos y próximos vencimientos se recalculan.
        async_dispatcher_send(self.hass, SENAL_ACTUALIZADO)

    async def generar(self) -> list[logica.Pago]:
        nuevos = await self.cambiar(logica.generar_pagos, self.hoy(), guardar_si=bool)
        if nuevos:
            _LOGGER.debug("Pagos generados: %s", [(p.servicio_id, p.periodo) for p in nuevos])
        return nuevos

    # -- cambios ----------------------------------------------------------

    async def cambiar(
        self,
        funcion: Callable[..., T],
        *args: Any,
        guardar_si: Callable[[T], bool] | None = None,
        **kwargs: Any,
    ) -> T:
        """Aplica una función de ``logica`` sobre los datos, guarda y avisa a las entidades.

        Si la función falla, los datos vuelven a como estaban (no quedan cambios a medias).
        ``guardar_si`` decide según el resultado si hace falta guardar (por defecto, siempre).
        """
        async with self._lock:
            copia = self.datos.a_dict()
            try:
                resultado = funcion(self.datos, *args, **kwargs)
            except Exception:
                self.datos = Datos.desde_dict(copia)
                raise
            if guardar_si is None or guardar_si(resultado):
                await self.almacen.guardar(self.datos)
                async_dispatcher_send(self.hass, SENAL_ACTUALIZADO)
            return resultado
