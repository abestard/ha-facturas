"""Pruebas de las entidades: sensores, todo.facturas y calendar.facturas (Fase 3)."""

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.components.todo import DOMAIN as TODO  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.exceptions import ServiceValidationError  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402
from pytest_homeassistant_custom_component.common import (  # noqa: E402
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.facturas.calendar import formato_importe  # noqa: E402
from custom_components.facturas.const import DOMAIN  # noqa: E402

ZONA = "America/Montevideo"


@pytest.fixture
async def facturas(hass: HomeAssistant, freezer):
    """Integración instalada el 2026-10-05 con UTE (con septiembre pagado), Antel, Netflix y un seguro."""
    await hass.config.async_set_time_zone(ZONA)
    hass.config.language = "es"
    freezer.move_to("2026-10-05 09:00:00-03:00")
    entrada = MockConfigEntry(domain=DOMAIN, title="Facturas", options={"moneda_principal": "pesos", "dias_aviso": 3})
    entrada.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entrada.entry_id)
    await hass.async_block_till_done()

    async def accion(accion, /, **datos):
        await hass.services.async_call(DOMAIN, accion, datos, blocking=True)

    await accion("agregar_servicio", nombre="UTE", importe=1500, dia_vence=12, categoria="casa", desde="2026-09")
    await accion("agregar_servicio", nombre="Antel", importe=1890, dia_vence=3, categoria="comunicaciones")
    await accion("agregar_servicio", nombre="Netflix", importe=12, moneda="dolares", pago="debito", dia_vence=20)
    await accion("agregar_servicio", nombre="Seguro", importe=9000, meses=[3, 9], dia_vence=25, desde="2026-09")
    await accion("registrar_pago", servicio="ute", periodo="2026-09", importe=1450)
    await accion("registrar_pago", servicio="seguro", periodo="2026-09")
    await hass.async_block_till_done()
    return entrada


def _estado(hass: HomeAssistant, entity_id: str):
    estado = hass.states.get(entity_id)
    assert estado is not None, f"{entity_id} no existe"
    return estado


async def test_ids_y_dispositivo(hass: HomeAssistant, facturas, entity_registry: er.EntityRegistry) -> None:
    ids = sorted(e.entity_id for e in er.async_entries_for_config_entry(entity_registry, facturas.entry_id))
    assert ids == [
        "calendar.facturas",
        "sensor.facturas_anio_pagado",
        "sensor.facturas_mes_falta",
        "sensor.facturas_mes_pagado",
        "sensor.facturas_mes_previsto",
        "sensor.facturas_proxima",
        "todo.facturas",
    ]


async def test_si_todo_facturas_ya_existe_no_falla(hass: HomeAssistant, entity_registry: er.EntityRegistry, freezer):
    # La lista vieja (Fase 6 la reemplaza) ocupa todo.facturas: la nueva queda como todo.facturas_2.
    entity_registry.async_get_or_create("todo", "local_todo", "vieja", suggested_object_id="facturas")
    await hass.config.async_set_time_zone(ZONA)
    entrada = MockConfigEntry(domain=DOMAIN, title="Facturas", options={})
    entrada.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entrada.entry_id)
    await hass.async_block_till_done()
    assert entity_registry.async_get_entity_id("todo", DOMAIN, f"{entrada.entry_id}_lista") == "todo.facturas_2"
    assert hass.states.get("todo.facturas_2") is not None


async def test_sensores_del_mes(hass: HomeAssistant, facturas) -> None:
    previsto = _estado(hass, "sensor.facturas_mes_previsto")
    assert float(previsto.state) == 1500 + 1890
    assert previsto.attributes["unit_of_measurement"] == "UYU"
    assert previsto.attributes["device_class"] == "monetary"
    assert previsto.attributes["state_class"] == "total"
    assert previsto.attributes["dolares"] == 12
    assert previsto.attributes["periodo"] == "2026-10"
    assert previsto.attributes["friendly_name"] == "Facturas Mes previsto"

    pagado = _estado(hass, "sensor.facturas_mes_pagado")
    assert float(pagado.state) == 0
    assert pagado.attributes["cantidad_pagos"] == 0
    assert pagado.attributes["last_reset"].startswith("2026-10-01T00:00:00")

    falta = _estado(hass, "sensor.facturas_mes_falta")
    assert float(falta.state) == 1500 + 1890
    assert falta.attributes["vencido"] == {"pesos": 1890, "dolares": 0}  # Antel vence el 3
    assert falta.attributes["vencidos_anteriores"] == {"pesos": 0, "dolares": 0}
    assert falta.attributes["dolares"] == 12

    anio = _estado(hass, "sensor.facturas_anio_pagado")
    assert float(anio.state) == 1450 + 9000
    assert anio.attributes["media_mensual"]["pesos"] == 1045.0
    assert anio.attributes["last_reset"].startswith("2026-01-01T00:00:00")


async def test_sensores_se_actualizan_al_pagar(hass: HomeAssistant, facturas) -> None:
    await hass.services.async_call(DOMAIN, "registrar_pago", {"servicio": "antel", "importe": 1800}, blocking=True)
    await hass.async_block_till_done()
    assert float(_estado(hass, "sensor.facturas_mes_pagado").state) == 1800
    assert float(_estado(hass, "sensor.facturas_mes_falta").state) == 1500
    assert float(_estado(hass, "sensor.facturas_mes_previsto").state) == 1500 + 1800


async def test_proxima(hass: HomeAssistant, facturas, freezer) -> None:
    proxima = _estado(hass, "sensor.facturas_proxima")
    assert proxima.state == "2026-10-12"  # UTE; Antel ya venció y Netflix es débito
    assert proxima.attributes["servicio"] == "UTE"
    assert proxima.attributes["dias"] == 7
    assert proxima.attributes["avisar"] is False

    # A medianoche cambia "hoy": faltan 3 días → avisar.
    freezer.move_to("2026-10-09 00:00:06-03:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    proxima = _estado(hass, "sensor.facturas_proxima")
    assert (proxima.attributes["dias"], proxima.attributes["avisar"]) == (3, True)


async def test_moneda_principal_dolares(hass: HomeAssistant, facturas) -> None:
    hass.config_entries.async_update_entry(facturas, options={"moneda_principal": "dolares", "dias_aviso": 3})
    assert await hass.config_entries.async_reload(facturas.entry_id)
    await hass.async_block_till_done()
    previsto = _estado(hass, "sensor.facturas_mes_previsto")
    assert (float(previsto.state), previsto.attributes["unit_of_measurement"]) == (12, "USD")
    assert previsto.attributes["pesos"] == 1500 + 1890


# ---------------------------------------------------------------------------
# todo.facturas
# ---------------------------------------------------------------------------


async def _items(hass: HomeAssistant) -> list[dict]:
    r = await hass.services.async_call(
        TODO, "get_items", {"status": ["needs_action", "completed"]},
        target={"entity_id": "todo.facturas"}, blocking=True, return_response=True,
    )
    return r["todo.facturas"]["items"]


async def test_todo_lista_pendientes_y_vencidos(hass: HomeAssistant, facturas, freezer) -> None:
    assert _estado(hass, "todo.facturas").state == "3"  # pendientes del mes
    items = await _items(hass)
    assert [(i["summary"], i["status"], i["due"]) for i in items] == [
        ("Antel", "needs_action", "2026-10-03"),
        ("UTE", "needs_action", "2026-10-12"),
        ("Netflix", "needs_action", "2026-10-20"),
    ]
    assert items[1]["description"] == "importe=1500; moneda=pesos; pago=manual; origen=manual"

    # En noviembre, lo de octubre sin pagar aparece como vencido, con el mes en el nombre.
    freezer.move_to("2026-11-01 00:00:06-03:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    resumen = [i["summary"] for i in await _items(hass)]
    assert resumen[:3] == ["Antel (2026-10)", "UTE (2026-10)", "Netflix (2026-10)"]
    assert "UTE" in resumen and "Antel" in resumen


async def test_todo_marcar_registra_y_desmarcar_deshace(hass: HomeAssistant, facturas) -> None:
    entrada = facturas
    await hass.services.async_call(
        TODO, "update_item", {"item": "UTE", "status": "completed"},
        target={"entity_id": "todo.facturas"}, blocking=True,
    )
    pago = entrada.runtime_data.datos.pago("ute", "2026-10")
    assert (pago.estado, pago.real, pago.pagado_el) == ("pagado", 1500, "2026-10-05")
    items = await _items(hass)
    assert ("UTE", "completed") in [(i["summary"], i["status"]) for i in items]
    assert _estado(hass, "todo.facturas").state == "2"

    await hass.services.async_call(
        TODO, "update_item", {"item": "UTE", "status": "needs_action"},
        target={"entity_id": "todo.facturas"}, blocking=True,
    )
    assert entrada.runtime_data.datos.pago("ute", "2026-10").estado == "pendiente"


async def test_todo_no_permite_agregar(hass: HomeAssistant, facturas) -> None:
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            TODO, "add_item", {"item": "Gas"}, target={"entity_id": "todo.facturas"}, blocking=True
        )


# ---------------------------------------------------------------------------
# calendar.facturas
# ---------------------------------------------------------------------------


async def test_calendario(hass: HomeAssistant, facturas) -> None:
    estado = _estado(hass, "calendar.facturas")
    assert estado.attributes["message"] == "UTE: $ 1.500"  # el próximo pendiente desde hoy
    assert estado.attributes["start_time"].startswith("2026-10-12")
    assert estado.state == "off"

    r = await hass.services.async_call(
        "calendar", "get_events", {"start_date_time": "2026-09-01 00:00:00", "end_date_time": "2027-04-01 00:00:00"},
        target={"entity_id": "calendar.facturas"}, blocking=True, return_response=True,
    )
    eventos = r["calendar.facturas"]["events"]
    resumen = [(e["start"], e["summary"]) for e in eventos]
    assert resumen[:5] == [
        ("2026-09-12", "UTE: $ 1.450"),
        ("2026-09-25", "Seguro: $ 9.000"),
        ("2026-10-03", "Antel: $ 1.890"),
        ("2026-10-12", "UTE: $ 1.500"),
        ("2026-10-20", "Netflix: US$ 12"),
    ]
    assert ("2027-03-25", "Seguro: $ 9.000") in resumen  # previsto
    assert eventos[0]["description"] == "Período 2026-09. Estado: pagado. Pago manual."
    assert "Estado: previsto" in eventos[-1]["description"]
    assert all(e["start"] < "2027-04-01" for e in eventos)


async def test_calendario_fin_exclusivo(hass: HomeAssistant, facturas) -> None:
    r = await hass.services.async_call(
        "calendar", "get_events", {"start_date_time": "2026-10-03 00:00:00", "end_date_time": "2026-10-12 00:00:00"},
        target={"entity_id": "calendar.facturas"}, blocking=True, return_response=True,
    )
    assert [e["start"] for e in r["calendar.facturas"]["events"]] == ["2026-10-03"]


@pytest.mark.parametrize(
    ("valor", "texto"), [(1650, "1.650"), (1490.5, "1.490,5"), (12, "12"), (1234567.89, "1.234.567,89"), (0, "0")]
)
def test_formato_importe(valor, texto) -> None:
    assert formato_importe(valor) == texto
