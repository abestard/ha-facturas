"""``todo.facturas``: los pagos pendientes del mes y los vencidos, más los ya pagados del mes.

Marcar un ítem como hecho registra el pago con el importe anotado o el estimado (el exacto se
corrige después); desmarcarlo lo deshace. No se crean ni borran ítems a mano: salen de los servicios.
"""

from __future__ import annotations

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity, TodoListEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import logica
from .entidad import EntidadFacturas
from .logica import ErrorFacturas
from .nucleo import Facturas, FacturasConfigEntry


async def async_setup_entry(
    hass: HomeAssistant, entry: FacturasConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([ListaFacturas(entry.runtime_data)])


def uid(pago: logica.Pago) -> str:
    return f"{pago.servicio_id}|{pago.periodo}"


class ListaFacturas(EntidadFacturas, TodoListEntity):
    _attr_name = None  # toma el nombre del dispositivo: "Facturas"
    _attr_supported_features = TodoListEntityFeature.UPDATE_TODO_ITEM

    def __init__(self, facturas: Facturas) -> None:
        super().__init__(facturas, "lista", "todo", "facturas")

    def actualizar(self) -> None:
        datos, hoy = self.facturas.datos, self.facturas.hoy()
        actual = logica.periodo_de(hoy)
        pagos = logica.pendientes(datos, hoy) + sorted(
            (p for p in datos.pagos if p.periodo == actual and p.estado == "pagado"),
            key=lambda p: (p.vence, p.servicio_id),
        )
        items = []
        for pago in pagos:
            servicio = datos.servicios.get(pago.servicio_id)
            nombre = servicio.nombre if servicio else pago.servicio_id
            items.append(
                TodoItem(
                    uid=uid(pago),
                    summary=nombre if pago.periodo == actual else f"{nombre} ({pago.periodo})",
                    status=TodoItemStatus.COMPLETED if pago.estado == "pagado" else TodoItemStatus.NEEDS_ACTION,
                    due=pago.vence_fecha,
                    description=logica.descripcion_todo(datos, pago),
                )
            )
        self._attr_todo_items = items

    async def async_update_todo_item(self, item: TodoItem) -> None:
        servicio_id, _, periodo = (item.uid or "").partition("|")
        pago = self.facturas.datos.pago(servicio_id, periodo)
        if pago is None:
            raise ServiceValidationError(f"No existe el pago {item.uid!r}")
        try:
            if item.status == TodoItemStatus.COMPLETED and pago.estado != "pagado":
                await self.facturas.cambiar(logica.registrar_pago, self.facturas.hoy(), servicio_id, periodo=periodo)
            elif item.status == TodoItemStatus.NEEDS_ACTION and pago.estado == "pagado":
                await self.facturas.cambiar(logica.deshacer_pago, servicio_id, periodo)
        except ErrorFacturas as err:
            raise ServiceValidationError(str(err)) from err
