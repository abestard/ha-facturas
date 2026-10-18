"""Pruebas de las mejoras en la integración: acciones nuevas, débito automático, sensores por
moneda y diagnóstico."""

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.exceptions import ServiceValidationError, Unauthorized  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402
from pytest_homeassistant_custom_component.common import (  # noqa: E402
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.components.diagnostics import (  # noqa: E402
    get_diagnostics_for_config_entry,
)

from custom_components.facturas.const import DOMAIN  # noqa: E402

ZONA = "America/Montevideo"


@pytest.fixture
def congelado(freezer):
    """La fecha fija va antes que los clientes (sus tokens quedarían emitidos "en el futuro")."""
    freezer.move_to("2026-10-05 09:00:00-03:00")
    return freezer


@pytest.fixture
async def entrada(hass: HomeAssistant, congelado) -> MockConfigEntry:
    await hass.config.async_set_time_zone(ZONA)
    entrada = MockConfigEntry(domain=DOMAIN, title="Facturas", options={"moneda_principal": "pesos", "dias_aviso": 3})
    entrada.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entrada.entry_id)
    await hass.async_block_till_done()
    return entrada


async def _accion(hass: HomeAssistant, accion: str, /, respuesta: bool = False, **datos):
    return await hass.services.async_call(DOMAIN, accion, datos, blocking=True, return_response=respuesta)


async def test_alta_con_meses_anteriores_pagados(hass: HomeAssistant, entrada) -> None:
    await _accion(hass, "agregar_servicio", nombre="UTE", importe=1500, desde="2026-08", anteriores_pagados=True)
    datos = entrada.runtime_data.datos
    assert [(p.periodo, p.estado) for p in datos.pagos_de("ute")] == [
        ("2026-08", "pagado"), ("2026-09", "pagado"), ("2026-10", "pendiente")]


async def test_debito_automatico_al_dar_de_alta_y_a_medianoche(hass: HomeAssistant, entrada, congelado) -> None:
    await _accion(hass, "agregar_servicio", nombre="Celular", importe=690, pago="debito", auto_pagar=True,
                  dia_vence=3)
    datos = entrada.runtime_data.datos
    pago = datos.pago("celular", "2026-10")
    assert (pago.estado, pago.origen, pago.pagado_el) == ("pagado", "automatico", "2026-10-03")

    await _accion(hass, "agregar_servicio", nombre="Netflix", importe=12, pago="debito", dia_vence=20)
    await _accion(hass, "editar_servicio", servicio="netflix", auto_pagar=True)
    assert datos.pago("netflix", "2026-10").estado == "pendiente"
    congelado.move_to("2026-10-20 00:00:06-03:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert entrada.runtime_data.datos.pago("netflix", "2026-10").estado == "pagado"


async def test_pagar_varios_meses(hass: HomeAssistant, entrada) -> None:
    await _accion(hass, "agregar_servicio", nombre="Gym", importe=1200, desde="2026-09")
    r = await _accion(hass, "registrar_pago", respuesta=True, servicio="gym", hasta="2026-12", importe=1100)
    assert [(p["periodo"], p["real"]) for p in r["pagos"]] == [
        ("2026-09", 1100), ("2026-10", 1100), ("2026-11", 1100), ("2026-12", 1100)]
    with pytest.raises(ServiceValidationError, match="no los dos"):
        await _accion(hass, "registrar_pago", servicio="gym", hasta="2027-02", periodo="2027-01")


async def test_borrar_servicio_y_precio(hass: HomeAssistant, entrada) -> None:
    await _accion(hass, "agregar_servicio", nombre="UTE", importe=1500, desde="2026-09")
    await _accion(hass, "agregar_servicio", nombre="Prueba", importe=1)
    await _accion(hass, "cambiar_precio", servicio="ute", importe=1700, desde="2026-10")
    r = await _accion(hass, "borrar_precio", respuesta=True, servicio="ute", desde="2026-10")
    assert r["actualizados"][0]["estimado"] == 1500
    await _accion(hass, "borrar_servicio", servicio="prueba")
    datos = entrada.runtime_data.datos
    assert list(datos.servicios) == ["ute"]
    assert all(p.servicio_id == "ute" for p in datos.pagos)


async def test_exportar_e_importar(hass: HomeAssistant, entrada, hass_storage) -> None:
    await _accion(hass, "agregar_servicio", nombre="UTE", importe=1500, desde="2026-09")
    await _accion(hass, "registrar_pago", servicio="ute", importe=1450)
    copia = await _accion(hass, "exportar", respuesta=True)
    assert copia["facturas"] == 1 and len(copia["datos"]["pagos"]) == 2

    await _accion(hass, "borrar_servicio", servicio="ute")
    await _accion(hass, "agregar_servicio", nombre="Gas", importe=500)
    r = await _accion(hass, "importar", respuesta=True, datos=copia, modo="combinar")
    assert r == {"servicios": 1, "pagos": 2}
    assert set(entrada.runtime_data.datos.servicios) == {"gas", "ute"}

    r = await _accion(hass, "importar", respuesta=True, datos=copia, modo="reemplazar")
    assert set(entrada.runtime_data.datos.servicios) == {"ute"}
    await hass.async_block_till_done()
    assert {s["id"] for s in hass_storage[DOMAIN]["data"]["servicios"]} == {"ute"}

    with pytest.raises(ServiceValidationError, match="no es una copia"):
        await _accion(hass, "importar", datos={"hola": 1})


async def test_borrar_e_importar_solo_administradores(hass: HomeAssistant, entrada, hass_read_only_user) -> None:
    from homeassistant.core import Context

    await _accion(hass, "agregar_servicio", nombre="UTE", importe=1500)
    contexto = Context(user_id=hass_read_only_user.id)
    for accion, datos in (("borrar_servicio", {"servicio": "ute"}), ("borrar_precio", {"servicio": "ute", "desde": "2026-10"}),
                          ("importar", {"datos": {}})):
        with pytest.raises(Unauthorized):
            await hass.services.async_call(DOMAIN, accion, datos, blocking=True, context=contexto)
    with pytest.raises(Unauthorized):
        await hass.services.async_call(DOMAIN, "exportar", {}, blocking=True, context=contexto, return_response=True)
    assert "ute" in entrada.runtime_data.datos.servicios


async def test_sensores_de_la_otra_moneda_aparecen_al_usarla(hass: HomeAssistant, entrada,
                                                            entity_registry: er.EntityRegistry) -> None:
    await _accion(hass, "agregar_servicio", nombre="UTE", importe=1500)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.facturas_mes_previsto_dolares") is None

    await _accion(hass, "agregar_servicio", nombre="Netflix", importe=12.5, moneda="dolares")
    await hass.async_block_till_done()
    estado = hass.states.get("sensor.facturas_mes_previsto_dolares")
    assert float(estado.state) == 12.5
    assert estado.attributes["unit_of_measurement"] == "USD"
    assert estado.attributes["state_class"] == "total"
    assert float(hass.states.get("sensor.facturas_mes_previsto").state) == 1500  # el principal sigue en pesos
    # No se duplican al seguir cambiando datos.
    await _accion(hass, "agregar_servicio", nombre="Spotify", importe=5, moneda="dolares")
    await hass.async_block_till_done()
    ids = [e.entity_id for e in er.async_entries_for_config_entry(entity_registry, entrada.entry_id)]
    assert ids.count("sensor.facturas_mes_previsto_dolares") == 1
    assert float(hass.states.get("sensor.facturas_mes_previsto_dolares").state) == 17.5


async def test_diagnostico(hass: HomeAssistant, entrada, hass_client) -> None:
    await _accion(hass, "agregar_servicio", nombre="UTE", importe=1500, remitente="facturas@ute.com.uy")
    diagnostico = await get_diagnostics_for_config_entry(hass, hass_client, entrada)
    assert diagnostico["cantidades"] == {"servicios": 1, "activos": 1, "pagos": 1, "pendientes": 1}
    assert diagnostico["opciones"]["moneda_principal"] == "pesos"
    assert diagnostico["datos"]["servicios"][0]["remitente"] == "**REDACTED**"
    assert diagnostico["resumen_mes"]["previsto"]["pesos"] == 1500
