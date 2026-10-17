"""Comandos WebSocket para el panel: leer los datos y enterarse cuando cambian.

El panel escribe con las acciones ``facturas.*``; por acá solo lee. Solo administradores.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import logica
from .const import DOMAIN, SENAL_ACTUALIZADO
from .servicios import _facturas, pago_a_dict, resumen

_PERIODO = vol.All(str, vol.Match(r"^\d{4}-(0[1-9]|1[0-2])$"))


@callback
def registrar_comandos(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_datos)
    websocket_api.async_register_command(hass, ws_estadisticas)
    websocket_api.async_register_command(hass, ws_suscribir)


def datos_panel(hass: HomeAssistant, periodo: str | None) -> dict[str, Any]:
    """Todo lo que muestra el panel: el resumen del mes pedido, los servicios y el historial."""
    facturas = _facturas(hass)
    datos = facturas.datos
    respuesta = resumen(facturas, periodo, None, None)
    respuesta["dias_aviso"] = facturas.dias_aviso
    respuesta["historial"] = [
        pago_a_dict(datos, p) for p in sorted(datos.pagos, key=lambda p: (p.periodo, p.vence), reverse=True)
    ]
    for servicio in respuesta["servicios"]:
        servicio["historial_precios"] = logica.historial_precios(datos.servicios[servicio["id"]])
    respuesta["servicios"].sort(key=lambda s: (not s["activo"], s["nombre"].casefold()))
    respuesta["categorias"] = sorted({s.categoria for s in datos.servicios.values()})
    return respuesta


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/datos", vol.Optional("periodo"): _PERIODO})
@websocket_api.require_admin
@callback
def ws_datos(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    try:
        connection.send_result(msg["id"], datos_panel(hass, msg.get("periodo")))
    except Exception as err:  # noqa: BLE001 - se devuelve el mensaje al panel
        connection.send_error(msg["id"], "error", str(err))


def estadisticas_panel(hass: HomeAssistant, anio: int | None) -> dict[str, Any]:
    """La pestaña de estadísticas: últimos 12 meses, el año pedido y la previsión."""
    facturas = _facturas(hass)
    datos, hoy = facturas.datos, facturas.hoy()
    anios = sorted({int(p.periodo[:4]) for p in datos.pagos} | {hoy.year}, reverse=True)
    resumen_anio = logica.resumen_anio(datos, hoy, anio)
    for servicio_id, fila in resumen_anio["por_servicio"].items():
        fila["categoria"] = datos.servicios[servicio_id].categoria if servicio_id in datos.servicios else "otros"
    return {
        "hoy": hoy.isoformat(),
        "moneda_principal": facturas.moneda_principal,
        "anios": anios,
        "ultimos_meses": logica.serie_mensual(datos, hoy, 12),
        "anio": resumen_anio,
        "prevision": [
            {"periodo": m["periodo"], "total": m["total"]} for m in logica.prevision(datos, hoy, 12)
        ],
    }


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/estadisticas", vol.Optional("anio"): vol.All(int, vol.Range(min=2000, max=2100))}
)
@websocket_api.require_admin
@callback
def ws_estadisticas(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    try:
        connection.send_result(msg["id"], estadisticas_panel(hass, msg.get("anio")))
    except Exception as err:  # noqa: BLE001 - se devuelve el mensaje al panel
        connection.send_error(msg["id"], "error", str(err))


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/suscribir"})
@websocket_api.require_admin
@callback
def ws_suscribir(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Manda un evento cada vez que cambian los datos (para que el panel recargue)."""

    @callback
    def avisar() -> None:
        connection.send_message(websocket_api.event_message(msg["id"], {"actualizado": True}))

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(hass, SENAL_ACTUALIZADO, avisar)
    connection.send_result(msg["id"])
