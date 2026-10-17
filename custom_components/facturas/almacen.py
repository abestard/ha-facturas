"""Guardado de los datos en ``.storage/facturas`` (JSON versionado)."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import CLAVE_ALMACEN, VERSION_ALMACEN, VERSION_MENOR_ALMACEN
from .logica import Datos


class _Store(Store[dict[str, Any]]):
    """Store con las migraciones de versión del formato."""

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        # Versión 1 es la primera: todavía no hay migraciones. Cuando cambie el formato,
        # se sube VERSION_ALMACEN (o la menor, si es compatible) y se transforma acá.
        if old_major_version > VERSION_ALMACEN:
            raise NotImplementedError("Los datos son de una versión más nueva de Facturas")
        return old_data


class Almacen:
    """Carga y guarda los ``Datos`` de la lógica."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store = _Store(
            hass, VERSION_ALMACEN, CLAVE_ALMACEN, minor_version=VERSION_MENOR_ALMACEN, private=True
        )

    async def cargar(self) -> Datos:
        return Datos.desde_dict(await self._store.async_load())

    async def guardar(self, datos: Datos) -> None:
        await self._store.async_save(datos.a_dict())
