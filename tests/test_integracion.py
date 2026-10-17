"""Pruebas de la integración contra Home Assistant 2025.11.3 (Fase 2)."""

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.config_entries import ConfigEntryState  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from homeassistant.exceptions import ServiceValidationError  # noqa: E402
from homeassistant.setup import async_setup_component  # noqa: E402
from pytest_homeassistant_custom_component.common import (  # noqa: E402
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.facturas.const import DOMAIN  # noqa: E402

ZONA = "America/Montevideo"


@pytest.fixture
async def zona(hass: HomeAssistant):
    await hass.config.async_set_time_zone(ZONA)


def _entrada() -> MockConfigEntry:
    return MockConfigEntry(domain=DOMAIN, title="Facturas", options={"moneda_principal": "pesos", "dias_aviso": 3})


async def _instalar(hass: HomeAssistant) -> MockConfigEntry:
    entrada = _entrada()
    entrada.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entrada.entry_id)
    await hass.async_block_till_done()
    return entrada


async def _accion(hass: HomeAssistant, accion: str, /, respuesta: bool = True, **datos):
    return await hass.services.async_call(DOMAIN, accion, datos, blocking=True, return_response=respuesta)


# ---------------------------------------------------------------------------
# Instalación
# ---------------------------------------------------------------------------


async def test_config_flow_crea_una_sola_instancia(hass: HomeAssistant) -> None:
    resultado = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert resultado["type"] is FlowResultType.FORM
    resultado = await hass.config_entries.flow.async_configure(
        resultado["flow_id"], {"moneda_principal": "dolares", "dias_aviso": 5.0}
    )
    assert resultado["type"] is FlowResultType.CREATE_ENTRY
    assert resultado["options"] == {"moneda_principal": "dolares", "dias_aviso": 5}
    await hass.async_block_till_done()

    otra = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert otra["type"] is FlowResultType.ABORT
    assert otra["reason"] == "single_instance_allowed"


async def test_opciones_recargan(hass: HomeAssistant) -> None:
    entrada = await _instalar(hass)
    flujo = await hass.config_entries.options.async_init(entrada.entry_id)
    resultado = await hass.config_entries.options.async_configure(
        flujo["flow_id"], {"moneda_principal": "dolares", "dias_aviso": 7}
    )
    assert resultado["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entrada.state is ConfigEntryState.LOADED
    assert entrada.runtime_data.dias_aviso == 7
    assert entrada.runtime_data.moneda_principal == "dolares"


async def test_descargar(hass: HomeAssistant) -> None:
    entrada = await _instalar(hass)
    assert await hass.config_entries.async_unload(entrada.entry_id)
    assert entrada.state is ConfigEntryState.NOT_LOADED


# ---------------------------------------------------------------------------
# Almacenamiento y generación de pagos
# ---------------------------------------------------------------------------


async def test_al_arrancar_rellena_los_meses_que_falten(hass: HomeAssistant, hass_storage, freezer, zona) -> None:
    hass_storage[DOMAIN] = {
        "version": 1,
        "minor_version": 1,
        "key": DOMAIN,
        "data": {
            "servicios": [{
                "id": "ute", "nombre": "UTE", "categoria": "casa", "moneda": "pesos", "pago": "manual",
                "tipo": "consumo", "dia_vence": 31, "meses": list(range(1, 13)),
                "precios": [{"desde": "2026-08", "importe": 1500}], "alta": "2026-08", "generado_hasta": "2026-08",
            }],
            "pagos": [{"servicio_id": "ute", "periodo": "2026-08", "vence": "2026-08-31", "estimado": 1500,
                       "real": 1490, "estado": "pagado", "pagado_el": "2026-08-30", "nota": "", "origen": "manual"}],
        },
    }
    freezer.move_to("2026-11-03 10:00:00-03:00")  # HA estuvo apagado septiembre y octubre
    entrada = await _instalar(hass)
    datos = entrada.runtime_data.datos
    assert [(p.periodo, p.vence, p.estado) for p in datos.pagos_de("ute")] == [
        ("2026-08", "2026-08-31", "pagado"),
        ("2026-09", "2026-09-30", "pendiente"),
        ("2026-10", "2026-10-31", "pendiente"),
        ("2026-11", "2026-11-30", "pendiente"),
    ]
    await hass.async_block_till_done()
    guardado = hass_storage[DOMAIN]
    assert guardado["version"] == 1
    assert len(guardado["data"]["pagos"]) == 4


async def test_cambio_de_mes_a_medianoche(hass: HomeAssistant, freezer, zona) -> None:
    freezer.move_to("2026-10-31 12:00:00-03:00")
    entrada = await _instalar(hass)
    await _accion(hass, "agregar_servicio", nombre="Antel", importe=1890, dia_vence=3)
    assert len(entrada.runtime_data.datos.pagos) == 1

    freezer.move_to("2026-11-01 00:00:06-03:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert [p.periodo for p in entrada.runtime_data.datos.pagos] == ["2026-10", "2026-11"]


# ---------------------------------------------------------------------------
# Acciones
# ---------------------------------------------------------------------------


async def test_flujo_completo_de_acciones(hass: HomeAssistant, hass_storage, freezer, zona) -> None:
    freezer.move_to("2026-10-05 09:00:00-03:00")
    entrada = await _instalar(hass)

    r = await _accion(hass, "agregar_servicio", nombre="UTE", importe=1500, dia_vence=12, categoria="Casa",
                      tipo="consumo", desde="2026-09")
    assert r["servicio"]["id"] == "ute"
    assert r["servicio"]["periodicidad"] == "mensual"
    await _accion(hass, "agregar_servicio", nombre="Seguro auto", importe=9000, meses=["3", "9"], categoria="seguros",
                  desde="2026-09")
    await _accion(hass, "agregar_servicio", nombre="Netflix", importe=12, moneda="dolares", pago="debito")

    # Alex: "pagué UTE, fueron 1.490" (por nombre, el pendiente más viejo = septiembre)
    r = await _accion(hass, "registrar_pago", servicio="ute", importe=1490, origen="alex", nota="descuento")
    assert (r["pago"]["periodo"], r["pago"]["real"], r["pago"]["estado"]) == ("2026-09", 1490, "pagado")

    await _accion(hass, "anotar_importe", servicio="UTE", importe=1720, origen="correo")
    r = await _accion(hass, "cambiar_precio", servicio="UTE", importe=1650, desde="2026-11")
    assert r["actualizados"] == []

    r = await _accion(hass, "resumen")
    assert r["mes"]["periodo"] == "2026-10"
    assert r["mes"]["previsto"] == {"pesos": 1720, "dolares": 12}
    assert r["mes"]["vencidos_anteriores"] == {"pesos": 9000, "dolares": 0}  # seguro de septiembre
    assert [(p["nombre"], p["periodo"]) for p in r["pendientes"]] == [
        ("Seguro auto", "2026-09"), ("Netflix", "2026-10"), ("UTE", "2026-10")]
    assert r["anio"]["pagado"]["pesos"] == 1490
    assert {s["id"]: s["precio_actual"] for s in r["servicios"]} == {"ute": 1500, "seguro_auto": 9000, "netflix": 12}

    r = await _accion(hass, "resumen", servicio="ute", anio=2026)
    assert r["servicio"]["precios"][-1] == {"desde": "2026-11", "importe": 1650, "variacion": 10.0}

    await _accion(hass, "omitir", servicio="seguro auto", periodo="2026-09")
    await _accion(hass, "deshacer_pago", servicio="ute", periodo="2026-09")
    await _accion(hass, "registrar_pago", servicio="ute", periodo="2026-09", importe=1400, fecha="2026-09-30")
    r = await _accion(hass, "corregir_pago", servicio="ute", periodo="2026-09", importe=1410)
    assert (r["pago"]["real"], r["pago"]["pagado_el"]) == (1410, "2026-09-30")

    await _accion(hass, "editar_servicio", servicio="netflix", dia_vence=20, nombre="Netflix familiar")
    await _accion(hass, "dar_de_baja", servicio="netflix familiar")
    await _accion(hass, "reactivar", servicio="netflix")  # el id no cambia al renombrar

    # Sin pedir respuesta también funciona.
    assert await _accion(hass, "registrar_pago", respuesta=False, servicio="netflix") is None

    await hass.async_block_till_done()
    guardado = hass_storage[DOMAIN]["data"]
    assert {s["id"] for s in guardado["servicios"]} == {"ute", "seguro_auto", "netflix"}
    assert next(s for s in guardado["servicios"] if s["id"] == "netflix")["nombre"] == "Netflix familiar"

    # Al recargar, los datos vuelven del almacenamiento.
    assert await hass.config_entries.async_reload(entrada.entry_id)
    await hass.async_block_till_done()
    assert hass.config_entries.async_get_entry(entrada.entry_id).runtime_data.datos.pago("ute", "2026-09").real == 1410


async def test_error_no_deja_cambios_a_medias(hass: HomeAssistant, zona) -> None:
    entrada = await _instalar(hass)
    await _accion(hass, "agregar_servicio", nombre="UTE", importe=1500, dia_vence=10)
    r = await _accion(hass, "registrar_pago", servicio="ute")
    antes = entrada.runtime_data.datos.a_dict()

    with pytest.raises(ServiceValidationError, match="ya está registrado"):
        await _accion(hass, "registrar_pago", servicio="ute", periodo=r["pago"]["periodo"])
    with pytest.raises(ServiceValidationError, match="No hay ningún servicio"):
        await _accion(hass, "registrar_pago", servicio="gas")
    # dia_vence se aplica antes de que falle el nombre: tiene que volver atrás.
    with pytest.raises(ServiceValidationError, match="nombre"):
        await _accion(hass, "editar_servicio", servicio="ute", dia_vence=25, nombre="   ")

    assert entrada.runtime_data.datos.a_dict() == antes


async def test_validacion_del_esquema(hass: HomeAssistant) -> None:
    await _instalar(hass)
    import voluptuous as vol

    with pytest.raises(vol.Invalid):
        await _accion(hass, "cambiar_precio", servicio="ute", importe=-1)
    with pytest.raises(vol.Invalid):
        await _accion(hass, "registrar_pago", servicio="ute", periodo="2026-13")
    with pytest.raises(vol.Invalid):
        await _accion(hass, "agregar_servicio", nombre="X", importe=1, moneda="euros")


async def test_acciones_sin_configurar(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, DOMAIN, {})
    assert hass.services.has_service(DOMAIN, "registrar_pago")
    with pytest.raises(ServiceValidationError, match="no está configurada"):
        await _accion(hass, "resumen")


async def test_resumen_solo_con_respuesta(hass: HomeAssistant) -> None:
    await _instalar(hass)
    with pytest.raises(ServiceValidationError):
        await _accion(hass, "resumen", respuesta=False)
