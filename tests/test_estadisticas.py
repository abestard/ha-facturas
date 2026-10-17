"""Pruebas de las estadísticas: comando WebSocket y la historia larga de los sensores (Fase 5)."""

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.core import HomeAssistant  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.facturas.const import DOMAIN  # noqa: E402

ZONA = "America/Montevideo"


async def _instalar(hass: HomeAssistant) -> MockConfigEntry:
    entrada = MockConfigEntry(domain=DOMAIN, title="Facturas", options={"moneda_principal": "pesos", "dias_aviso": 3})
    entrada.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entrada.entry_id)
    await hass.async_block_till_done()
    return entrada


async def _accion(hass: HomeAssistant, accion: str, /, **datos) -> None:
    await hass.services.async_call(DOMAIN, accion, datos, blocking=True)


@pytest.fixture
def congelado(freezer):
    """La fecha fija va antes que el cliente WebSocket: si no, su token queda emitido "en el futuro"."""
    freezer.move_to("2026-10-05 09:00:00-03:00")
    return freezer


async def test_ws_estadisticas(hass: HomeAssistant, congelado, hass_ws_client) -> None:
    await hass.config.async_set_time_zone(ZONA)
    await _instalar(hass)
    await _accion(hass, "agregar_servicio", nombre="UTE", importe=1500, categoria="casa", desde="2025-12")
    await _accion(hass, "agregar_servicio", nombre="Netflix", importe=12, moneda="dolares", categoria="ocio",
                  desde="2026-09")
    await _accion(hass, "cambiar_precio", servicio="ute", importe=1650, desde="2026-09")
    await _accion(hass, "registrar_pago", servicio="ute", periodo="2025-12", importe=1400)
    await _accion(hass, "registrar_pago", servicio="ute", periodo="2026-09", importe=1700)
    await _accion(hass, "registrar_pago", servicio="netflix", periodo="2026-09")

    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "facturas/estadisticas"})
    r = await ws.receive_json()
    assert r["success"], r
    e = r["result"]
    assert e["anios"] == [2026, 2025]
    assert e["moneda_principal"] == "pesos"

    meses = {m["periodo"]: m for m in e["ultimos_meses"]}
    assert len(e["ultimos_meses"]) == 12
    assert e["ultimos_meses"][0]["periodo"] == "2025-11"
    assert meses["2025-12"]["pagado"] == {"pesos": 1400, "dolares": 0}
    assert meses["2026-09"]["previsto"] == {"pesos": 1650, "dolares": 12}
    assert meses["2026-09"]["pagado"] == {"pesos": 1700, "dolares": 12}

    anio = e["anio"]
    assert anio["anio"] == 2026
    assert anio["pagado"] == {"pesos": 1700, "dolares": 12}
    assert anio["por_servicio"]["ute"]["categoria"] == "casa"
    assert anio["por_servicio"]["ute"]["subida_precio"]["porcentaje"] == 10.0

    assert [m["periodo"] for m in e["prevision"]][:2] == ["2026-10", "2026-11"]
    assert e["prevision"][1]["total"] == {"pesos": 1650, "dolares": 12}

    await ws.send_json({"id": 2, "type": "facturas/estadisticas", "anio": 2025})
    r = await ws.receive_json()
    assert r["result"]["anio"]["pagado"] == {"pesos": 1400, "dolares": 0}
    assert r["result"]["anio"]["meses_transcurridos"] == 12


async def test_ws_estadisticas_solo_administradores(hass: HomeAssistant, hass_ws_client,
                                                     hass_read_only_access_token) -> None:
    await _instalar(hass)
    ws = await hass_ws_client(hass, hass_read_only_access_token)
    await ws.send_json({"id": 1, "type": "facturas/estadisticas"})
    r = await ws.receive_json()
    assert r["error"]["code"] == "unauthorized"
