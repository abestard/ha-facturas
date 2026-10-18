"""Pruebas del panel: registro en la barra lateral, archivo JS y comandos WebSocket (Fase 4)."""

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.core import HomeAssistant  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.facturas.const import DOMAIN  # noqa: E402

ZONA = "America/Montevideo"


@pytest.fixture
async def entrada(hass: HomeAssistant, freezer):
    await hass.config.async_set_time_zone(ZONA)
    freezer.move_to("2026-10-05 09:00:00-03:00")
    entrada = MockConfigEntry(domain=DOMAIN, title="Facturas", options={"moneda_principal": "pesos", "dias_aviso": 3})
    entrada.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entrada.entry_id)
    await hass.async_block_till_done()

    async def accion(accion, /, **datos):
        await hass.services.async_call(DOMAIN, accion, datos, blocking=True)

    await accion("agregar_servicio", nombre="UTE", importe=1500, dia_vence=12, categoria="casa", desde="2026-09")
    await accion("agregar_servicio", nombre="Netflix", importe=12, moneda="dolares", pago="debito", categoria="ocio")
    await accion("cambiar_precio", servicio="ute", importe=1650, desde="2026-10")
    await accion("registrar_pago", servicio="ute", periodo="2026-09", importe=1450, nota="descuento")
    return entrada


async def test_panel_registrado_solo_para_administradores(hass: HomeAssistant, entrada) -> None:
    panel = hass.data["frontend_panels"]["facturas"]
    assert panel.sidebar_title == "Facturas"
    assert panel.require_admin is True
    config = panel.config["_panel_custom"]
    assert config["name"] == "facturas-panel"
    assert config["module_url"] == "/facturas_panel/facturas-panel.js?v=0.5.0"


async def test_panel_se_quita_al_descargar(hass: HomeAssistant, entrada) -> None:
    assert await hass.config_entries.async_unload(entrada.entry_id)
    assert "facturas" not in hass.data.get("frontend_panels", {})
    # Al volver a cargar no falla aunque la ruta del JS ya esté registrada.
    assert await hass.config_entries.async_setup(entrada.entry_id)
    await hass.async_block_till_done()
    assert "facturas" in hass.data["frontend_panels"]


async def test_sirve_el_js(hass: HomeAssistant, entrada, hass_client) -> None:
    cliente = await hass_client()
    respuesta = await cliente.get("/facturas_panel/facturas-panel.js")
    assert respuesta.status == 200
    texto = await respuesta.text()
    assert 'customElements.define("facturas-panel"' in texto


async def test_ws_datos(hass: HomeAssistant, entrada, hass_ws_client) -> None:
    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "facturas/datos"})
    r = await ws.receive_json()
    assert r["success"], r
    d = r["result"]
    assert d["hoy"] == "2026-10-05"
    assert d["moneda_principal"] == "pesos"
    assert d["mes"]["periodo"] == "2026-10"
    assert d["mes"]["previsto"] == {"pesos": 1650, "dolares": 12}
    assert [(p["nombre"], p["estado"]) for p in d["mes"]["pagos"]] == [("Netflix", "pendiente"), ("UTE", "pendiente")]
    assert [(p["servicio_id"], p["periodo"]) for p in d["historial"]] == [
        ("ute", "2026-10"), ("netflix", "2026-10"), ("ute", "2026-09")]  # más nuevo primero
    assert d["historial"][-1]["nota"] == "descuento"
    ute = next(s for s in d["servicios"] if s["id"] == "ute")
    assert ute["precio_actual"] == 1650
    assert ute["historial_precios"][-1] == {"desde": "2026-10", "importe": 1650, "variacion": 10.0}
    assert d["categorias"] == ["casa", "ocio"]

    await ws.send_json({"id": 2, "type": "facturas/datos", "periodo": "2026-09"})
    r = await ws.receive_json()
    assert r["result"]["mes"]["pagado"] == {"pesos": 1450, "dolares": 0}

    await ws.send_json({"id": 3, "type": "facturas/datos", "periodo": "2026-13"})
    r = await ws.receive_json()
    assert not r["success"]


async def test_ws_suscribir_avisa_los_cambios(hass: HomeAssistant, entrada, hass_ws_client) -> None:
    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "facturas/suscribir"})
    r = await ws.receive_json()
    assert r["success"]

    await hass.services.async_call(DOMAIN, "registrar_pago", {"servicio": "netflix"}, blocking=True)
    evento = await ws.receive_json()
    assert evento == {"id": 1, "type": "event", "event": {"actualizado": True}}


async def test_ws_solo_administradores(hass: HomeAssistant, entrada, hass_ws_client, hass_read_only_access_token):
    ws = await hass_ws_client(hass, hass_read_only_access_token)
    await ws.send_json({"id": 1, "type": "facturas/datos"})
    r = await ws.receive_json()
    assert not r["success"]
    assert r["error"]["code"] == "unauthorized"
