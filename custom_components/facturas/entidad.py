"""Base común de las entidades: el dispositivo "Facturas" y la actualización por señal."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SENAL_ACTUALIZADO
from .nucleo import Facturas


class EntidadFacturas(Entity):
    """Se redibuja cada vez que cambian los datos (y a medianoche); no consulta nada."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, facturas: Facturas, clave: str, dominio: str, objeto: str) -> None:
        self.facturas = facturas
        self._attr_unique_id = f"{facturas.entry.entry_id}_{clave}"
        # Sugerencia: si el id ya está ocupado, HA agrega un sufijo (_2) en lugar de fallar.
        self.entity_id = f"{dominio}.{objeto}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, facturas.entry.entry_id)},
            name="Facturas",
            entry_type=DeviceEntryType.SERVICE,
        )
        self.actualizar()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_dispatcher_connect(self.hass, SENAL_ACTUALIZADO, self._actualizado))
        self.actualizar()

    @callback
    def _actualizado(self) -> None:
        self.actualizar()
        self.async_write_ha_state()

    def actualizar(self) -> None:
        """Recalcula estado y atributos a partir de los datos (lo implementa cada entidad)."""
