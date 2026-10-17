"""Las acciones ``facturas.*`` (para el panel, Alex y las automatizaciones)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import asdict
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from . import logica
from .const import DOMAIN
from .logica import ErrorFacturas
from .nucleo import Facturas, FacturasConfigEntry

# Campos
SERVICIO = "servicio"
NOMBRE = "nombre"
IMPORTE = "importe"
CATEGORIA = "categoria"
MONEDA = "moneda"
PAGO = "pago"
TIPO = "tipo"
DIA_VENCE = "dia_vence"
MESES = "meses"
DESDE = "desde"
REMITENTE = "remitente"
NOTAS = "notas"
PERIODO = "periodo"
FECHA = "fecha"
NOTA = "nota"
ORIGEN = "origen"
ANIO = "anio"

_IMPORTE = vol.All(vol.Coerce(float), vol.Range(min=0))
_MESES = vol.All(cv.ensure_list, [vol.All(vol.Coerce(int), vol.Range(min=1, max=12))], vol.Length(min=1))
_PERIODO = cv.matches_regex(r"^\d{4}-(0[1-9]|1[0-2])$")
_DIA = vol.All(vol.Coerce(int), vol.Range(min=1, max=31))

_CAMPOS_SERVICIO = {
    vol.Optional(CATEGORIA): cv.string,
    vol.Optional(MONEDA): vol.In(logica.MONEDAS),
    vol.Optional(PAGO): vol.In(logica.FORMAS_PAGO),
    vol.Optional(TIPO): vol.In(logica.TIPOS),
    vol.Optional(DIA_VENCE): _DIA,
    vol.Optional(MESES): _MESES,
    vol.Optional(REMITENTE): vol.Any(None, cv.string),
    vol.Optional(NOTAS): cv.string,
}

ESQUEMAS: dict[str, vol.Schema] = {
    "agregar_servicio": vol.Schema(
        {vol.Required(NOMBRE): cv.string, vol.Required(IMPORTE): _IMPORTE, vol.Optional(DESDE): _PERIODO,
         **_CAMPOS_SERVICIO}
    ),
    "editar_servicio": vol.Schema(
        {vol.Required(SERVICIO): cv.string, vol.Optional(NOMBRE): cv.string, **_CAMPOS_SERVICIO}
    ),
    "dar_de_baja": vol.Schema({vol.Required(SERVICIO): cv.string}),
    "reactivar": vol.Schema({vol.Required(SERVICIO): cv.string}),
    "cambiar_precio": vol.Schema(
        {vol.Required(SERVICIO): cv.string, vol.Required(IMPORTE): _IMPORTE, vol.Optional(DESDE): _PERIODO}
    ),
    "anotar_importe": vol.Schema(
        {vol.Required(SERVICIO): cv.string, vol.Required(IMPORTE): _IMPORTE, vol.Optional(PERIODO): _PERIODO,
         vol.Optional(NOTA): cv.string, vol.Optional(ORIGEN): vol.In(logica.ORIGENES)}
    ),
    "registrar_pago": vol.Schema(
        {vol.Required(SERVICIO): cv.string, vol.Optional(PERIODO): _PERIODO, vol.Optional(IMPORTE): _IMPORTE,
         vol.Optional(FECHA): cv.date, vol.Optional(NOTA): cv.string, vol.Optional(ORIGEN): vol.In(logica.ORIGENES)}
    ),
    "corregir_pago": vol.Schema(
        {vol.Required(SERVICIO): cv.string, vol.Required(PERIODO): _PERIODO, vol.Optional(IMPORTE): _IMPORTE,
         vol.Optional(FECHA): cv.date, vol.Optional(NOTA): cv.string}
    ),
    "deshacer_pago": vol.Schema({vol.Required(SERVICIO): cv.string, vol.Required(PERIODO): _PERIODO}),
    "omitir": vol.Schema(
        {vol.Required(SERVICIO): cv.string, vol.Optional(PERIODO): _PERIODO, vol.Optional(NOTA): cv.string}
    ),
    "resumen": vol.Schema(
        {vol.Optional(PERIODO): _PERIODO, vol.Optional(ANIO): vol.All(vol.Coerce(int), vol.Range(min=2000, max=2100)),
         vol.Optional(SERVICIO): cv.string}
    ),
}


# ---------------------------------------------------------------------------
# Conversión a datos de respuesta (JSON)
# ---------------------------------------------------------------------------


def pago_a_dict(datos: logica.Datos, pago: logica.Pago) -> dict[str, Any]:
    servicio = datos.servicios.get(pago.servicio_id)
    return {
        **asdict(pago),
        "nombre": servicio.nombre if servicio else pago.servicio_id,
        "moneda": servicio.moneda if servicio else "pesos",
        "forma_pago": servicio.pago if servicio else "manual",
        "importe": pago.importe,
    }


def servicio_a_dict(servicio: logica.Servicio, hoy) -> dict[str, Any]:
    datos = asdict(servicio)
    datos.pop("generado_hasta", None)
    return {
        **datos,
        "precio_actual": servicio.precio_actual(logica.periodo_de(hoy)),
        "periodicidad": logica.describir_meses(servicio.meses),
    }


def resumen(facturas: Facturas, periodo: str | None, anio: int | None, servicio_id: str | None) -> dict[str, Any]:
    datos, hoy = facturas.datos, facturas.hoy()
    mes = logica.resumen_mes(datos, hoy, periodo)
    mes["pagos_vencidos_anteriores"] = [pago_a_dict(datos, p) for p in mes["pagos_vencidos_anteriores"]]
    mes["pagos"] = [pago_a_dict(datos, p) for p in sorted(datos.pagos, key=lambda p: (p.vence, p.servicio_id))
                    if p.periodo == mes["periodo"]]
    respuesta: dict[str, Any] = {
        "hoy": hoy.isoformat(),
        "moneda_principal": facturas.moneda_principal,
        "mes": mes,
        "anio": logica.resumen_anio(datos, hoy, anio),
        "pendientes": [pago_a_dict(datos, p) for p in logica.pendientes(datos, hoy)],
        "proximo_vencimiento": logica.proximo_vencimiento(datos, hoy),
        "servicios": [servicio_a_dict(s, hoy) for s in datos.servicios.values()],
    }
    if servicio_id is not None:
        respuesta["servicio"] = logica.estadisticas_servicio(datos, servicio_id)
    return respuesta


# ---------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------


def _facturas(hass: HomeAssistant) -> Facturas:
    entradas: list[FacturasConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entradas:
        raise ServiceValidationError("La integración Facturas no está configurada o no está cargada")
    return entradas[0].runtime_data


def _servicio_id(facturas: Facturas, texto: str) -> str:
    """Acepta el id o el nombre del servicio ("UTE", "antel")."""
    return facturas.datos.buscar_servicio(texto).id


async def _agregar_servicio(f: Facturas, d: dict[str, Any]) -> dict[str, Any]:
    campos = {k: v for k, v in d.items() if k not in (NOMBRE, IMPORTE, DESDE)}
    servicio = await f.cambiar(
        logica.agregar_servicio, f.hoy(), nombre=d[NOMBRE], importe=d[IMPORTE], desde=d.get(DESDE), **campos
    )
    return {"servicio": servicio_a_dict(servicio, f.hoy())}


async def _editar_servicio(f: Facturas, d: dict[str, Any]) -> dict[str, Any]:
    cambios = {k: v for k, v in d.items() if k != SERVICIO}
    servicio = await f.cambiar(logica.editar_servicio, f.hoy(), _servicio_id(f, d[SERVICIO]), **cambios)
    return {"servicio": servicio_a_dict(servicio, f.hoy())}


async def _dar_de_baja(f: Facturas, d: dict[str, Any]) -> dict[str, Any]:
    servicio = await f.cambiar(logica.dar_de_baja, f.hoy(), _servicio_id(f, d[SERVICIO]))
    return {"servicio": servicio_a_dict(servicio, f.hoy())}


async def _reactivar(f: Facturas, d: dict[str, Any]) -> dict[str, Any]:
    servicio = await f.cambiar(logica.reactivar, f.hoy(), _servicio_id(f, d[SERVICIO]))
    return {"servicio": servicio_a_dict(servicio, f.hoy())}


async def _cambiar_precio(f: Facturas, d: dict[str, Any]) -> dict[str, Any]:
    desde = d.get(DESDE) or logica.periodo_de(f.hoy())
    actualizados = await f.cambiar(logica.cambiar_precio, _servicio_id(f, d[SERVICIO]), d[IMPORTE], desde)
    return {"actualizados": [pago_a_dict(f.datos, p) for p in actualizados]}


async def _anotar_importe(f: Facturas, d: dict[str, Any]) -> dict[str, Any]:
    pago = await f.cambiar(
        logica.anotar_importe, _servicio_id(f, d[SERVICIO]), d[IMPORTE],
        periodo=d.get(PERIODO), nota=d.get(NOTA), origen=d.get(ORIGEN, "manual"),
    )
    return {"pago": pago_a_dict(f.datos, pago)}


async def _registrar_pago(f: Facturas, d: dict[str, Any]) -> dict[str, Any]:
    pago = await f.cambiar(
        logica.registrar_pago, f.hoy(), _servicio_id(f, d[SERVICIO]),
        periodo=d.get(PERIODO), real=d.get(IMPORTE), fecha=d.get(FECHA), nota=d.get(NOTA),
        origen=d.get(ORIGEN, "manual"),
    )
    return {"pago": pago_a_dict(f.datos, pago)}


async def _corregir_pago(f: Facturas, d: dict[str, Any]) -> dict[str, Any]:
    pago = await f.cambiar(
        logica.corregir_pago, _servicio_id(f, d[SERVICIO]), d[PERIODO],
        real=d.get(IMPORTE), fecha=d.get(FECHA), nota=d.get(NOTA),
    )
    return {"pago": pago_a_dict(f.datos, pago)}


async def _deshacer_pago(f: Facturas, d: dict[str, Any]) -> dict[str, Any]:
    pago = await f.cambiar(logica.deshacer_pago, _servicio_id(f, d[SERVICIO]), d[PERIODO])
    return {"pago": pago_a_dict(f.datos, pago)}


async def _omitir(f: Facturas, d: dict[str, Any]) -> dict[str, Any]:
    pago = await f.cambiar(logica.omitir, _servicio_id(f, d[SERVICIO]), d.get(PERIODO), d.get(NOTA))
    return {"pago": pago_a_dict(f.datos, pago)}


async def _resumen(f: Facturas, d: dict[str, Any]) -> dict[str, Any]:
    servicio_id = _servicio_id(f, d[SERVICIO]) if SERVICIO in d else None
    return resumen(f, d.get(PERIODO), d.get(ANIO), servicio_id)


MANEJADORES: dict[str, Callable[[Facturas, dict[str, Any]], Awaitable[dict[str, Any]]]] = {
    "agregar_servicio": _agregar_servicio,
    "editar_servicio": _editar_servicio,
    "dar_de_baja": _dar_de_baja,
    "reactivar": _reactivar,
    "cambiar_precio": _cambiar_precio,
    "anotar_importe": _anotar_importe,
    "registrar_pago": _registrar_pago,
    "corregir_pago": _corregir_pago,
    "deshacer_pago": _deshacer_pago,
    "omitir": _omitir,
    "resumen": _resumen,
}


def registrar_acciones(hass: HomeAssistant) -> None:
    """Registra todas las acciones. Se llama una vez desde ``async_setup``."""

    def envolver(manejador):
        async def accion(call: ServiceCall) -> ServiceResponse:
            facturas = _facturas(hass)
            try:
                respuesta = await manejador(facturas, dict(call.data))
            except ErrorFacturas as err:
                raise ServiceValidationError(str(err)) from err
            return respuesta if call.return_response else None

        return accion

    for nombre, manejador in MANEJADORES.items():
        hass.services.async_register(
            DOMAIN,
            nombre,
            envolver(manejador),
            schema=ESQUEMAS[nombre],
            supports_response=SupportsResponse.ONLY if nombre == "resumen" else SupportsResponse.OPTIONAL,
        )
