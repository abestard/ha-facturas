"""Cálculo de facturas y servicios, sin depender de Home Assistant.

Todo lo que es regla de negocio vive acá: qué meses toca cada servicio, el precio
vigente en un mes, la generación de los pagos de cada mes, los cambios de precio,
los pagos y las estadísticas. No importa nada de HA, así que se prueba en la PC con
``pytest`` y la integración solo se ocupa de guardar, publicar entidades y acciones.

Convenciones:

- Un *período* es un mes con la forma ``"AAAA-MM"`` (por ejemplo ``"2026-10"``).
  Como cadenas de ese formato se ordenan igual que las fechas, se comparan con ``<``.
- Los importes son ``float`` redondeados a 2 decimales.
- Los totales se llevan siempre por moneda (``pesos`` y ``dolares``), sin convertir.
- Las funciones que necesitan "hoy" lo reciben como parámetro: nada lee el reloj.
"""

from __future__ import annotations

import calendar
from dataclasses import asdict, dataclass, field, fields
from datetime import date
from typing import Any, Iterable, Iterator

MONEDAS = ("pesos", "dolares")
FORMAS_PAGO = ("manual", "debito")
TIPOS = ("fijo", "consumo")
ESTADOS = ("pendiente", "pagado", "omitido")
ORIGENES = ("manual", "correo", "alex", "automatico")
MODOS_IMPORTAR = ("reemplazar", "combinar")
VERSION_EXPORTACION = 1
TODOS_LOS_MESES = list(range(1, 13))


class ErrorFacturas(ValueError):
    """Dato inválido o una operación que no se puede hacer (servicio inexistente...)."""


# ---------------------------------------------------------------------------
# Períodos y fechas
# ---------------------------------------------------------------------------


def periodo_de(fecha: date) -> str:
    """El período (``"AAAA-MM"``) de una fecha."""
    return f"{fecha.year:04d}-{fecha.month:02d}"


def partes(periodo: str) -> tuple[int, int]:
    """``"2026-10"`` → ``(2026, 10)``; valida el formato."""
    try:
        anio_txt, mes_txt = periodo.split("-")
        if len(anio_txt) != 4 or len(mes_txt) != 2:
            raise ValueError
        anio, mes = int(anio_txt), int(mes_txt)
    except (AttributeError, ValueError):
        raise ErrorFacturas(f"Período inválido: {periodo!r} (se espera AAAA-MM)") from None
    if not 1 <= mes <= 12:
        raise ErrorFacturas(f"Período inválido: {periodo!r} (mes fuera de 1-12)")
    return anio, mes


def validar_periodo(periodo: str) -> str:
    partes(periodo)
    return periodo


def sumar_meses(periodo: str, n: int) -> str:
    anio, mes = partes(periodo)
    total = anio * 12 + (mes - 1) + n
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def periodos_entre(desde: str, hasta: str) -> Iterator[str]:
    """Los períodos de ``desde`` a ``hasta``, ambos incluidos (vacío si desde > hasta)."""
    validar_periodo(hasta)
    actual = validar_periodo(desde)
    while actual <= hasta:
        yield actual
        actual = sumar_meses(actual, 1)


def fecha_vencimiento(periodo: str, dia: int) -> date:
    """El día ``dia`` del período; si el mes tiene menos días, el último."""
    anio, mes = partes(periodo)
    ultimo = calendar.monthrange(anio, mes)[1]
    return date(anio, mes, min(dia, ultimo))


# ---------------------------------------------------------------------------
# Periodicidad → lista de meses
# ---------------------------------------------------------------------------


def meses_mensual() -> list[int]:
    return list(TODOS_LOS_MESES)


def meses_cada(n: int, empezando: int) -> list[int]:
    """Cada ``n`` meses empezando en el mes ``empezando`` (dando la vuelta al año).

    ``meses_cada(2, 2)`` → ``[2, 4, 6, 8, 10, 12]``; ``meses_cada(3, 11)`` →
    ``[2, 5, 8, 11]``. ``n`` tiene que dividir 12 para que se repita igual cada año.
    """
    if n not in (1, 2, 3, 4, 6, 12):
        raise ErrorFacturas(f"Cada {n} meses no se repite igual cada año (usar 1, 2, 3, 4, 6 o 12)")
    _validar_mes(empezando)
    return sorted({(empezando - 1 + k * n) % 12 + 1 for k in range(12 // n)})


def meses_anual(mes: int) -> list[int]:
    _validar_mes(mes)
    return [mes]


def validar_meses(meses: Iterable[int]) -> list[int]:
    lista = sorted(set(meses))
    if not lista:
        raise ErrorFacturas("La periodicidad necesita al menos un mes")
    for mes in lista:
        _validar_mes(mes)
    return lista


def describir_meses(meses: list[int]) -> str:
    """Texto corto para mostrar la periodicidad ("mensual", "cada 2 meses", "anual (marzo)")."""
    lista = validar_meses(meses)
    if lista == TODOS_LOS_MESES:
        return "mensual"
    if len(lista) == 1:
        return f"anual ({NOMBRES_MESES[lista[0] - 1]})"
    for n in (2, 3, 4, 6):
        if len(lista) == 12 // n and lista == meses_cada(n, lista[0]):
            return f"cada {n} meses"
    return ", ".join(NOMBRES_MESES[m - 1] for m in lista)


NOMBRES_MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def _validar_mes(mes: int) -> None:
    if not isinstance(mes, int) or not 1 <= mes <= 12:
        raise ErrorFacturas(f"Mes inválido: {mes!r}")


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------


def _importe(valor: Any, nombre: str = "importe") -> float:
    try:
        numero = round(float(valor), 2)
    except (TypeError, ValueError):
        raise ErrorFacturas(f"{nombre} inválido: {valor!r}") from None
    if numero < 0:
        raise ErrorFacturas(f"{nombre} no puede ser negativo: {valor!r}")
    return numero


def _elegir(valor: str, opciones: tuple[str, ...], nombre: str) -> str:
    if valor not in opciones:
        raise ErrorFacturas(f"{nombre} inválido: {valor!r} (opciones: {', '.join(opciones)})")
    return valor


@dataclass
class Precio:
    desde: str
    importe: float


@dataclass
class Servicio:
    id: str
    nombre: str
    categoria: str = "otros"
    moneda: str = "pesos"
    pago: str = "manual"
    tipo: str = "fijo"
    dia_vence: int = 10
    meses: list[int] = field(default_factory=meses_mensual)
    precios: list[Precio] = field(default_factory=list)
    remitente: str | None = None
    activo: bool = True
    notas: str = ""
    # Solo para débito automático: el día del vencimiento el pago se marca como pagado solo.
    auto_pagar: bool = False
    # Primer período en que existe el servicio: antes no se generan pagos.
    alta: str = "2000-01"
    # Último período para el que ya se generaron sus pagos (uso interno).
    generado_hasta: str | None = None

    def validar(self) -> Servicio:
        if not self.id:
            raise ErrorFacturas("El servicio necesita un id")
        if not self.nombre or not self.nombre.strip():
            raise ErrorFacturas("El servicio necesita un nombre")
        self.nombre = self.nombre.strip()
        self.categoria = (self.categoria or "otros").strip().lower()
        _elegir(self.moneda, MONEDAS, "moneda")
        _elegir(self.pago, FORMAS_PAGO, "pago")
        _elegir(self.tipo, TIPOS, "tipo")
        self.auto_pagar = bool(self.auto_pagar)
        if not isinstance(self.dia_vence, int) or not 1 <= self.dia_vence <= 31:
            raise ErrorFacturas(f"dia_vence inválido: {self.dia_vence!r} (1-31)")
        self.meses = validar_meses(self.meses)
        validar_periodo(self.alta)
        if not self.precios:
            raise ErrorFacturas("El servicio necesita un precio")
        vistos: dict[str, Precio] = {}
        for precio in self.precios:
            validar_periodo(precio.desde)
            precio.importe = _importe(precio.importe)
            vistos[precio.desde] = precio
        self.precios = sorted(vistos.values(), key=lambda p: p.desde)
        return self

    def toca(self, periodo: str) -> bool:
        """Si al servicio le corresponde un pago en ese período (sin mirar si está activo)."""
        return periodo >= self.alta and partes(periodo)[1] in self.meses

    def precio_en(self, periodo: str) -> float | None:
        """El precio vigente en el período (la última entrada con ``desde <= periodo``)."""
        vigente = None
        for precio in self.precios:
            if precio.desde <= periodo:
                vigente = precio.importe
            else:
                break
        return vigente

    def precio_actual(self, periodo: str) -> float | None:
        """Como ``precio_en``, pero si todavía no rige ninguno devuelve el primero."""
        vigente = self.precio_en(periodo)
        if vigente is None and self.precios:
            return self.precios[0].importe
        return vigente


@dataclass
class Pago:
    servicio_id: str
    periodo: str
    vence: str  # fecha ISO
    estimado: float
    real: float | None = None
    estado: str = "pendiente"
    pagado_el: str | None = None  # fecha ISO
    nota: str = ""
    origen: str | None = None

    @property
    def importe(self) -> float:
        """El importe que cuenta: el real si ya se anotó, si no el estimado."""
        return self.real if self.real is not None else self.estimado

    @property
    def vence_fecha(self) -> date:
        return date.fromisoformat(self.vence)


@dataclass
class Datos:
    servicios: dict[str, Servicio] = field(default_factory=dict)
    pagos: list[Pago] = field(default_factory=list)

    # -- serialización (para el Store de HA) --------------------------------

    def a_dict(self) -> dict[str, Any]:
        return {
            "servicios": [asdict(s) for s in self.servicios.values()],
            "pagos": [asdict(p) for p in self.pagos],
        }

    @classmethod
    def desde_dict(cls, datos: dict[str, Any] | None) -> Datos:
        """Arma los datos desde el JSON guardado. Ignora campos que no conoce (de una versión más nueva)."""
        datos = datos or {}
        servicios: dict[str, Servicio] = {}
        for crudo in datos.get("servicios", []):
            crudo = _solo_campos(Servicio, crudo)
            crudo["precios"] = [Precio(**_solo_campos(Precio, p)) for p in crudo.get("precios", [])]
            servicio = Servicio(**crudo)
            servicios[servicio.id] = servicio
        pagos = [Pago(**_solo_campos(Pago, p)) for p in datos.get("pagos", [])]
        return cls(servicios=servicios, pagos=pagos)

    def validar(self) -> Datos:
        """Comprueba que todo sea coherente (para datos importados de un archivo)."""
        for servicio in self.servicios.values():
            servicio.validar()
        vistos = set()
        for pago in self.pagos:
            if pago.servicio_id not in self.servicios:
                raise ErrorFacturas(f"Hay un pago de un servicio que no existe: {pago.servicio_id!r}")
            validar_periodo(pago.periodo)
            _elegir(pago.estado, ESTADOS, "estado")
            if pago.origen is not None:
                _elegir(pago.origen, ORIGENES, "origen")
            try:
                date.fromisoformat(pago.vence)
                if pago.pagado_el:
                    date.fromisoformat(pago.pagado_el)
            except (TypeError, ValueError):
                raise ErrorFacturas(f"Fecha inválida en el pago {pago.servicio_id} {pago.periodo}") from None
            pago.estimado = _importe(pago.estimado, "estimado")
            if pago.real is not None:
                pago.real = _importe(pago.real, "real")
            clave = (pago.servicio_id, pago.periodo)
            if clave in vistos:
                raise ErrorFacturas(f"Pago repetido: {pago.servicio_id} {pago.periodo}")
            vistos.add(clave)
        return self

    # -- búsquedas -----------------------------------------------------------

    def servicio(self, servicio_id: str) -> Servicio:
        try:
            return self.servicios[servicio_id]
        except KeyError:
            raise ErrorFacturas(f"No existe el servicio {servicio_id!r}") from None

    def buscar_servicio(self, texto: str) -> Servicio:
        """Por id o por nombre (sin distinguir mayúsculas); para Alex ("pagué Antel")."""
        if texto in self.servicios:
            return self.servicios[texto]
        buscado = texto.strip().casefold()
        coincidencias = [s for s in self.servicios.values() if s.nombre.casefold() == buscado]
        if not coincidencias:
            coincidencias = [s for s in self.servicios.values() if buscado in s.nombre.casefold()]
        activos = [s for s in coincidencias if s.activo]
        if len(activos) == 1:
            return activos[0]
        if len(coincidencias) == 1:
            return coincidencias[0]
        if not coincidencias:
            raise ErrorFacturas(f"No hay ningún servicio que se llame {texto!r}")
        nombres = ", ".join(sorted(s.nombre for s in coincidencias))
        raise ErrorFacturas(f"{texto!r} coincide con varios servicios: {nombres}")

    def pago(self, servicio_id: str, periodo: str) -> Pago | None:
        for pago in self.pagos:
            if pago.servicio_id == servicio_id and pago.periodo == periodo:
                return pago
        return None

    def pagos_de(self, servicio_id: str) -> list[Pago]:
        return sorted((p for p in self.pagos if p.servicio_id == servicio_id), key=lambda p: p.periodo)

    def moneda_de(self, pago: Pago) -> str:
        servicio = self.servicios.get(pago.servicio_id)
        return servicio.moneda if servicio else "pesos"


def _solo_campos(clase: type, crudo: Any) -> dict[str, Any]:
    if not isinstance(crudo, dict):
        raise ErrorFacturas(f"Dato inválido: se esperaba un objeto y llegó {type(crudo).__name__}")
    nombres = {f.name for f in fields(clase)}
    return {k: v for k, v in crudo.items() if k in nombres}


def nuevo_id(nombre: str, existentes: Iterable[str]) -> str:
    """Un id legible a partir del nombre: ``"UTE casa"`` → ``"ute_casa"`` (``_2`` si ya existe)."""
    import unicodedata

    base = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode().lower()
    base = "".join(c if c.isalnum() else "_" for c in base).strip("_")
    base = "_".join(filter(None, base.split("_"))) or "servicio"
    existentes = set(existentes)
    candidato, n = base, 2
    while candidato in existentes:
        candidato, n = f"{base}_{n}", n + 1
    return candidato


# ---------------------------------------------------------------------------
# Servicios
# ---------------------------------------------------------------------------


def agregar_servicio(
    datos: Datos,
    hoy: date,
    *,
    nombre: str,
    importe: float,
    meses: Iterable[int] | None = None,
    desde: str | None = None,
    anteriores_pagados: bool = False,
    **campos: Any,
) -> Servicio:
    """Da de alta un servicio con su precio inicial y genera sus pagos hasta el mes de hoy.

    ``desde`` es el primer período del servicio (por defecto, el mes de hoy). Con
    ``anteriores_pagados``, los pagos de los meses anteriores al de hoy quedan como pagados
    (con el estimado y la fecha de vencimiento): sirve para cargar un servicio que ya se
    venía pagando sin llenar la lista de vencidos.
    """
    alta = validar_periodo(desde) if desde else periodo_de(hoy)
    servicio = Servicio(
        id=campos.pop("id", None) or nuevo_id(nombre, datos.servicios),
        nombre=nombre,
        meses=list(meses) if meses is not None else meses_mensual(),
        precios=[Precio(desde=alta, importe=importe)],
        alta=alta,
        **campos,
    ).validar()
    if servicio.id in datos.servicios:
        raise ErrorFacturas(f"Ya existe el servicio {servicio.id!r}")
    datos.servicios[servicio.id] = servicio
    generar_pagos(datos, hoy)
    if anteriores_pagados:
        actual = periodo_de(hoy)
        for pago in datos.pagos_de(servicio.id):
            if pago.periodo < actual and pago.estado == "pendiente":
                pago.estado, pago.real, pago.pagado_el, pago.origen = "pagado", pago.estimado, pago.vence, "manual"
    return servicio


EDITABLES = {
    "nombre", "categoria", "moneda", "pago", "tipo", "dia_vence", "meses", "remitente", "notas", "auto_pagar",
}


def editar_servicio(datos: Datos, hoy: date, servicio_id: str, **cambios: Any) -> Servicio:
    """Cambia datos del servicio (no el precio: para eso está ``cambiar_precio``).

    Los pagos pendientes del mes de hoy en adelante toman el nuevo día de vencimiento;
    si cambian los meses, se generan los que falten y se quitan los pendientes futuros
    (o del mes de hoy) que ya no tocan y nunca se tocaron.
    """
    desconocidos = set(cambios) - EDITABLES
    if desconocidos:
        raise ErrorFacturas(f"No se puede editar: {', '.join(sorted(desconocidos))}")
    servicio = datos.servicio(servicio_id)
    anterior = asdict(servicio)
    for clave, valor in cambios.items():
        setattr(servicio, clave, valor)
    try:
        servicio.validar()
    except ErrorFacturas:
        restaurado = Servicio(**{**anterior, "precios": [Precio(**p) for p in anterior["precios"]]})
        datos.servicios[servicio_id] = restaurado
        raise

    actual = periodo_de(hoy)
    for pago in list(datos.pagos):
        if pago.servicio_id != servicio_id or pago.periodo < actual or pago.estado != "pendiente":
            continue
        if not servicio.toca(pago.periodo) and pago.real is None:
            datos.pagos.remove(pago)
        else:
            pago.vence = fecha_vencimiento(pago.periodo, servicio.dia_vence).isoformat()
    if servicio.activo and "meses" in cambios:
        # Rellenar el mes de hoy si ahora toca y antes no.
        servicio.generado_hasta = min(servicio.generado_hasta or actual, sumar_meses(actual, -1))
        generar_pagos(datos, hoy)
    return servicio


def dar_de_baja(datos: Datos, hoy: date, servicio_id: str) -> Servicio:
    """Deja de generar pagos. El historial queda; se quitan los pendientes futuros sin importe real.

    Los pendientes del mes de hoy y anteriores se mantienen (puede que haya que pagarlos igual);
    si no, se omiten a mano.
    """
    servicio = datos.servicio(servicio_id)
    servicio.activo = False
    actual = periodo_de(hoy)
    datos.pagos = [
        p
        for p in datos.pagos
        if not (p.servicio_id == servicio_id and p.periodo > actual and p.estado == "pendiente" and p.real is None)
    ]
    return servicio


def reactivar(datos: Datos, hoy: date, servicio_id: str) -> Servicio:
    """Vuelve a activar un servicio desde el mes de hoy (no rellena los meses que estuvo de baja)."""
    servicio = datos.servicio(servicio_id)
    if not servicio.activo:
        servicio.activo = True
        servicio.generado_hasta = sumar_meses(periodo_de(hoy), -1)
        generar_pagos(datos, hoy)
    return servicio


def borrar_servicio(datos: Datos, servicio_id: str) -> Servicio:
    """Borra el servicio y todos sus pagos, para siempre (para lo cargado por error).

    Para un servicio que se dejó de pagar está ``dar_de_baja``, que conserva el historial.
    """
    servicio = datos.servicios.pop(servicio_id, None)
    if servicio is None:
        raise ErrorFacturas(f"No existe el servicio {servicio_id!r}")
    datos.pagos = [p for p in datos.pagos if p.servicio_id != servicio_id]
    return servicio


def _actualizar_estimados(datos: Datos, servicio: Servicio, desde: str) -> list[Pago]:
    """Los pendientes sin importe real desde ``desde`` toman el precio vigente en su mes."""
    actualizados = []
    for pago in datos.pagos_de(servicio.id):
        if pago.periodo >= desde and pago.estado == "pendiente" and pago.real is None:
            nuevo = servicio.precio_actual(pago.periodo)
            if nuevo is not None and nuevo != pago.estimado:
                pago.estimado = nuevo
                actualizados.append(pago)
    return actualizados


def borrar_precio(datos: Datos, servicio_id: str, desde: str) -> list[Pago]:
    """Quita una entrada del historial de precios (un precio mal cargado).

    Como en ``cambiar_precio``, solo se recalculan los pendientes sin importe real desde ese mes.
    """
    servicio = datos.servicio(servicio_id)
    if not any(p.desde == desde for p in servicio.precios):
        raise ErrorFacturas(f"{servicio.nombre} no tiene un precio desde {desde}")
    if len(servicio.precios) == 1:
        raise ErrorFacturas(f"Es el único precio de {servicio.nombre}: cambialo en lugar de quitarlo")
    servicio.precios = [p for p in servicio.precios if p.desde != desde]
    return _actualizar_estimados(datos, servicio, desde)


def cambiar_precio(datos: Datos, servicio_id: str, importe: float, desde: str) -> list[Pago]:
    """Agrega un precio desde un período (o reemplaza el que ya empezaba ese mes).

    El historial no se reescribe: solo se actualizan los pagos ya generados de ``desde``
    en adelante que sigan pendientes y sin importe real. Devuelve los pagos actualizados.
    """
    servicio = datos.servicio(servicio_id)
    validar_periodo(desde)
    importe = _importe(importe)
    servicio.precios = [p for p in servicio.precios if p.desde != desde] + [Precio(desde=desde, importe=importe)]
    servicio.validar()
    return _actualizar_estimados(datos, servicio, desde)


# ---------------------------------------------------------------------------
# Generación de pagos
# ---------------------------------------------------------------------------


def generar_pagos(datos: Datos, hoy: date, hasta: str | None = None) -> list[Pago]:
    """Genera los pagos que falten hasta el mes de hoy (o hasta ``hasta``).

    Se llama el día 1 y al arrancar HA: si estuvo apagado varios meses, rellena todos los
    que falten, cada uno con el precio vigente en su mes. Es idempotente: nunca duplica
    un pago ni toca los que ya existen. Devuelve los pagos nuevos.
    """
    hasta = validar_periodo(hasta) if hasta else periodo_de(hoy)
    nuevos: list[Pago] = []
    for servicio in datos.servicios.values():
        if not servicio.activo:
            continue
        inicio = sumar_meses(servicio.generado_hasta, 1) if servicio.generado_hasta else servicio.alta
        inicio = max(inicio, servicio.alta)
        for periodo in periodos_entre(inicio, hasta):
            if servicio.toca(periodo) and datos.pago(servicio.id, periodo) is None:
                nuevos.append(_crear_pago(datos, servicio, periodo))
        if servicio.generado_hasta is None or hasta > servicio.generado_hasta:
            servicio.generado_hasta = hasta
    return nuevos


def _crear_pago(datos: Datos, servicio: Servicio, periodo: str) -> Pago:
    pago = Pago(
        servicio_id=servicio.id,
        periodo=periodo,
        vence=fecha_vencimiento(periodo, servicio.dia_vence).isoformat(),
        estimado=servicio.precio_actual(periodo) or 0.0,
    )
    datos.pagos.append(pago)
    return pago


def pagar_debitos(datos: Datos, hoy: date) -> list[Pago]:
    """Marca como pagados los débitos automáticos (con ``auto_pagar``) que ya vencieron.

    Se registran con el importe anotado o el estimado y la fecha de vencimiento; si el
    banco cobró otra cosa, se corrige después. Es idempotente.
    """
    pagados = []
    for pago in datos.pagos:
        servicio = datos.servicios.get(pago.servicio_id)
        if (servicio and servicio.auto_pagar and servicio.pago == "debito" and pago.estado == "pendiente"
                and pago.vence <= hoy.isoformat()):
            pago.estado, pago.real, pago.pagado_el, pago.origen = "pagado", pago.importe, pago.vence, "automatico"
            pagados.append(pago)
    return pagados


def mantenimiento(datos: Datos, hoy: date) -> list[Pago]:
    """Lo que se hace al arrancar y cada medianoche: generar los pagos y pagar los débitos.

    Devuelve los pagos que cambiaron, sin repetir (uno recién generado puede también pagarse).
    """
    cambiados = generar_pagos(datos, hoy) + pagar_debitos(datos, hoy)
    return list({id(p): p for p in cambiados}.values())


# ---------------------------------------------------------------------------
# Pagos
# ---------------------------------------------------------------------------


def pendiente_mas_viejo(datos: Datos, servicio_id: str) -> Pago | None:
    for pago in datos.pagos_de(servicio_id):
        if pago.estado == "pendiente":
            return pago
    return None


def _pago_para(datos: Datos, servicio_id: str, periodo: str | None, *, crear: bool) -> Pago:
    """El pago del período (o el pendiente más viejo); con ``crear`` genera uno futuro (adelanto)."""
    servicio = datos.servicio(servicio_id)
    if periodo is None:
        pago = pendiente_mas_viejo(datos, servicio_id)
        if pago is None:
            raise ErrorFacturas(f"{servicio.nombre} no tiene pagos pendientes")
        return pago
    validar_periodo(periodo)
    pago = datos.pago(servicio_id, periodo)
    if pago is not None:
        return pago
    if crear and servicio.toca(periodo):
        if not servicio.activo:
            raise ErrorFacturas(f"{servicio.nombre} está dado de baja")
        return _crear_pago(datos, servicio, periodo)
    raise ErrorFacturas(f"{servicio.nombre} no tiene pago en {periodo}")


def registrar_pago(
    datos: Datos,
    hoy: date,
    servicio_id: str,
    *,
    periodo: str | None = None,
    real: float | None = None,
    fecha: date | None = None,
    nota: str | None = None,
    origen: str = "manual",
) -> Pago:
    """Marca un pago como hecho.

    Sin ``periodo``, el pendiente más viejo; con un período futuro que le toca al servicio,
    lo genera (pago por adelantado). Sin ``real``, el importe ya anotado o el estimado.
    """
    _elegir(origen, ORIGENES, "origen")
    pago = _pago_para(datos, servicio_id, periodo, crear=True)
    if pago.estado == "pagado":
        raise ErrorFacturas(f"El pago de {pago.periodo} ya está registrado")
    pago.real = _importe(real, "real") if real is not None else pago.importe
    pago.estado = "pagado"
    pago.pagado_el = (fecha or hoy).isoformat()
    pago.origen = origen
    if nota is not None:
        pago.nota = nota
    return pago


def registrar_pagos_hasta(
    datos: Datos,
    hoy: date,
    servicio_id: str,
    hasta: str,
    *,
    real: float | None = None,
    fecha: date | None = None,
    nota: str | None = None,
    origen: str = "manual",
) -> list[Pago]:
    """Registra juntos todos los pendientes del servicio hasta ``hasta`` (incluido).

    Si ``hasta`` es un mes futuro, genera y paga también los meses que faltan (adelanto).
    ``real`` es el importe de cada mes; sin él, el de cada pago (anotado o estimado).
    """
    validar_periodo(hasta)
    servicio = datos.servicio(servicio_id)
    pagados = []
    pendientes_hasta = [p for p in datos.pagos_de(servicio_id) if p.estado == "pendiente" and p.periodo <= hasta]
    for pago in pendientes_hasta:
        pagados.append(registrar_pago(datos, hoy, servicio_id, periodo=pago.periodo, real=real, fecha=fecha,
                                      nota=nota, origen=origen))
    # Meses futuros que todavía no se generaron.
    for periodo in periodos_entre(sumar_meses(periodo_de(hoy), 1), hasta):
        if servicio.toca(periodo) and datos.pago(servicio_id, periodo) is None:
            pagados.append(registrar_pago(datos, hoy, servicio_id, periodo=periodo, real=real, fecha=fecha,
                                          nota=nota, origen=origen))
    if not pagados:
        raise ErrorFacturas(f"{servicio.nombre} no tiene pagos pendientes hasta {hasta}")
    return sorted(pagados, key=lambda p: p.periodo)


def anotar_importe(
    datos: Datos,
    servicio_id: str,
    importe: float,
    *,
    periodo: str | None = None,
    nota: str | None = None,
    origen: str = "manual",
) -> Pago:
    """Anota el importe real de un mes antes de pagarlo (la factura que llegó)."""
    _elegir(origen, ORIGENES, "origen")
    pago = _pago_para(datos, servicio_id, periodo, crear=True)
    pago.real = _importe(importe, "importe")
    if pago.estado == "pendiente":
        pago.origen = origen
    if nota is not None:
        pago.nota = nota
    return pago


def corregir_pago(
    datos: Datos,
    servicio_id: str,
    periodo: str,
    *,
    real: float | None = None,
    fecha: date | None = None,
    nota: str | None = None,
) -> Pago:
    """Corrige el importe real, la fecha de pago o la nota de un pago ya existente."""
    pago = _pago_para(datos, servicio_id, periodo, crear=False)
    if real is not None:
        pago.real = _importe(real, "real")
    if fecha is not None:
        if pago.estado != "pagado":
            raise ErrorFacturas("Solo un pago registrado tiene fecha de pago")
        pago.pagado_el = fecha.isoformat()
    if nota is not None:
        pago.nota = nota
    return pago


def deshacer_pago(datos: Datos, servicio_id: str, periodo: str) -> Pago:
    """Vuelve a pendiente un pago registrado u omitido (borra la fecha y el importe real)."""
    pago = _pago_para(datos, servicio_id, periodo, crear=False)
    if pago.estado == "pendiente":
        raise ErrorFacturas(f"El pago de {periodo} ya está pendiente")
    pago.estado = "pendiente"
    pago.pagado_el = None
    pago.real = None
    pago.origen = None
    # Si el precio cambió mientras estaba pagado, vuelve con el vigente.
    servicio = datos.servicios.get(servicio_id)
    if servicio is not None:
        pago.estimado = servicio.precio_actual(periodo) or pago.estimado
    return pago


def omitir(datos: Datos, servicio_id: str, periodo: str | None = None, nota: str | None = None) -> Pago:
    """"Este mes no se paga": el pago queda omitido y no cuenta en los totales."""
    pago = _pago_para(datos, servicio_id, periodo, crear=True)
    if pago.estado == "pagado":
        raise ErrorFacturas(f"El pago de {pago.periodo} ya está registrado; deshacerlo primero")
    pago.estado = "omitido"
    if nota is not None:
        pago.nota = nota
    return pago


# ---------------------------------------------------------------------------
# Consultas y estadísticas
# ---------------------------------------------------------------------------


def _por_moneda() -> dict[str, float]:
    return {moneda: 0.0 for moneda in MONEDAS}


def _sumar(totales: dict[str, float], moneda: str, importe: float) -> None:
    totales[moneda] = round(totales.get(moneda, 0.0) + importe, 2)


def pendientes(datos: Datos, hoy: date) -> list[Pago]:
    """Los pagos pendientes del mes de hoy y los vencidos de meses anteriores, por vencimiento."""
    actual = periodo_de(hoy)
    return sorted(
        (p for p in datos.pagos if p.estado == "pendiente" and p.periodo <= actual),
        key=lambda p: (p.vence, p.servicio_id),
    )


def vencidos_anteriores(datos: Datos, hoy: date) -> list[Pago]:
    actual = periodo_de(hoy)
    return [p for p in pendientes(datos, hoy) if p.periodo < actual]


def resumen_mes(datos: Datos, hoy: date, periodo: str | None = None) -> dict[str, Any]:
    """Previsto, pagado, falta y vencido del mes (por moneda), más los vencidos de meses anteriores.

    - previsto: importe (real o estimado) de todos los pagos no omitidos del mes.
    - pagado: real de los pagados del mes.
    - falta: importe de los pendientes del mes.
    - vencido: de lo que falta, lo que ya venció (vence antes de hoy).
    """
    periodo = validar_periodo(periodo) if periodo else periodo_de(hoy)
    previsto, pagado, falta, vencido = _por_moneda(), _por_moneda(), _por_moneda(), _por_moneda()
    por_categoria: dict[str, dict[str, float]] = {}
    cantidad = {"total": 0, "pagados": 0, "pendientes": 0, "omitidos": 0}
    for pago in datos.pagos:
        if pago.periodo != periodo:
            continue
        cantidad["total"] += 1
        if pago.estado == "omitido":
            cantidad["omitidos"] += 1
            continue
        moneda = datos.moneda_de(pago)
        _sumar(previsto, moneda, pago.importe)
        servicio = datos.servicios.get(pago.servicio_id)
        categoria = servicio.categoria if servicio else "otros"
        _sumar(por_categoria.setdefault(categoria, _por_moneda()), moneda, pago.importe)
        if pago.estado == "pagado":
            cantidad["pagados"] += 1
            _sumar(pagado, moneda, pago.importe)
        else:
            cantidad["pendientes"] += 1
            _sumar(falta, moneda, pago.importe)
            if pago.vence_fecha < hoy:
                _sumar(vencido, moneda, pago.importe)

    anteriores = _por_moneda()
    lista_anteriores = []
    for pago in vencidos_anteriores(datos, hoy):
        if pago.periodo < periodo:
            _sumar(anteriores, datos.moneda_de(pago), pago.importe)
            lista_anteriores.append(pago)
    return {
        "periodo": periodo,
        "previsto": previsto,
        "pagado": pagado,
        "falta": falta,
        "vencido": vencido,
        "cantidad": cantidad,
        "por_categoria": por_categoria,
        "vencidos_anteriores": anteriores,
        "pagos_vencidos_anteriores": lista_anteriores,
    }


def _media(valores: list[float]) -> float | None:
    return round(sum(valores) / len(valores), 2) if valores else None


def resumen_anio(datos: Datos, hoy: date, anio: int | None = None) -> dict[str, Any]:
    """Lo pagado en el año: total y media mensual por moneda, por categoría y por servicio.

    La media mensual divide por los meses transcurridos (12 si el año ya terminó).
    Por servicio: total, media, mínimo y máximo de los reales, la diferencia contra el
    estimado (positiva = se pagó menos de lo estimado) y cuánto subió el precio en el año.
    """
    anio = anio or hoy.year
    prefijo = f"{anio:04d}-"
    if anio < hoy.year:
        meses_transcurridos = 12
    elif anio == hoy.year:
        meses_transcurridos = hoy.month
    else:
        meses_transcurridos = 0

    pagado = _por_moneda()
    ahorro = _por_moneda()
    por_categoria: dict[str, dict[str, float]] = {}
    por_mes: dict[str, dict[str, float]] = {f"{prefijo}{m:02d}": _por_moneda() for m in TODOS_LOS_MESES}
    reales: dict[str, list[float]] = {}
    for pago in datos.pagos:
        if not pago.periodo.startswith(prefijo) or pago.estado != "pagado":
            continue
        moneda = datos.moneda_de(pago)
        _sumar(pagado, moneda, pago.importe)
        _sumar(ahorro, moneda, pago.estimado - pago.importe)
        _sumar(por_mes[pago.periodo], moneda, pago.importe)
        servicio = datos.servicios.get(pago.servicio_id)
        _sumar(por_categoria.setdefault(servicio.categoria if servicio else "otros", _por_moneda()), moneda, pago.importe)
        reales.setdefault(pago.servicio_id, []).append(pago.importe)

    por_servicio = {}
    for servicio_id, valores in reales.items():
        servicio = datos.servicios.get(servicio_id)
        estimados = [p.estimado for p in datos.pagos_de(servicio_id)
                     if p.periodo.startswith(prefijo) and p.estado == "pagado"]
        por_servicio[servicio_id] = {
            "nombre": servicio.nombre if servicio else servicio_id,
            "moneda": servicio.moneda if servicio else "pesos",
            "cantidad": len(valores),
            "total": round(sum(valores), 2),
            "media": _media(valores),
            "minimo": min(valores),
            "maximo": max(valores),
            "diferencia_estimado": round(sum(estimados) - sum(valores), 2),
            "subida_precio": subida_precio(servicio, anio) if servicio else None,
        }

    media_mensual = {
        moneda: round(total / meses_transcurridos, 2) if meses_transcurridos else 0.0
        for moneda, total in pagado.items()
    }
    return {
        "anio": anio,
        "pagado": pagado,
        "media_mensual": media_mensual,
        "meses_transcurridos": meses_transcurridos,
        "ahorro": ahorro,
        "por_mes": por_mes,
        "por_categoria": por_categoria,
        "por_servicio": por_servicio,
    }


def subida_precio(servicio: Servicio, anio: int) -> dict[str, Any] | None:
    """Precio a principio y a fin de año (o el último cambio) y la variación en %."""
    inicio = servicio.precio_en(f"{anio:04d}-01")
    fin = servicio.precio_en(f"{anio:04d}-12")
    if fin is None:
        return None
    if inicio is None:  # el servicio empezó durante el año
        inicio = servicio.precio_actual(f"{anio:04d}-01")
    porcentaje = round((fin - inicio) / inicio * 100, 1) if inicio else None
    return {"inicio": inicio, "fin": fin, "diferencia": round(fin - inicio, 2), "porcentaje": porcentaje}


def historial_precios(servicio: Servicio) -> list[dict[str, Any]]:
    """Cada precio con la variación respecto del anterior."""
    resultado = []
    anterior: float | None = None
    for precio in servicio.precios:
        variacion = None
        if anterior:
            variacion = round((precio.importe - anterior) / anterior * 100, 1)
        resultado.append({"desde": precio.desde, "importe": precio.importe, "variacion": variacion})
        anterior = precio.importe
    return resultado


def estadisticas_servicio(datos: Datos, servicio_id: str) -> dict[str, Any]:
    """Todo el historial de un servicio: media, mínimo, máximo de los reales y diferencia con el estimado."""
    servicio = datos.servicio(servicio_id)
    pagados = [p for p in datos.pagos_de(servicio_id) if p.estado == "pagado"]
    reales = [p.importe for p in pagados]
    return {
        "id": servicio.id,
        "nombre": servicio.nombre,
        "moneda": servicio.moneda,
        "cantidad": len(reales),
        "total": round(sum(reales), 2),
        "media": _media(reales),
        "minimo": min(reales) if reales else None,
        "maximo": max(reales) if reales else None,
        "diferencia_estimado": round(sum(p.estimado - p.importe for p in pagados), 2),
        "precios": historial_precios(servicio),
    }


def serie_mensual(datos: Datos, hoy: date, meses: int = 12) -> list[dict[str, Any]]:
    """Los últimos ``meses`` (terminando en el mes de hoy): previsto contra pagado, por moneda.

    - previsto: los estimados de los pagos no omitidos (lo que se esperaba pagar).
    - pagado: los reales de los pagos registrados.
    """
    actual = periodo_de(hoy)
    resultado = []
    for periodo in periodos_entre(sumar_meses(actual, -(meses - 1)), actual):
        previsto, pagado = _por_moneda(), _por_moneda()
        for pago in datos.pagos:
            if pago.periodo != periodo or pago.estado == "omitido":
                continue
            moneda = datos.moneda_de(pago)
            _sumar(previsto, moneda, pago.estimado)
            if pago.estado == "pagado":
                _sumar(pagado, moneda, pago.importe)
        resultado.append({"periodo": periodo, "previsto": previsto, "pagado": pagado})
    return resultado


def prevision(datos: Datos, hoy: date, meses: int = 12) -> list[dict[str, Any]]:
    """Lo previsto para los próximos ``meses`` (empezando por el de hoy), por moneda.

    Usa los pagos ya generados (con su real si se anotó; los omitidos no cuentan) y,
    para los meses aún no generados, el precio vigente de cada servicio activo.
    """
    resultado = []
    actual = periodo_de(hoy)
    for periodo in periodos_entre(actual, sumar_meses(actual, meses - 1)):
        totales = _por_moneda()
        detalle = []
        for servicio in datos.servicios.values():
            pago = datos.pago(servicio.id, periodo)
            if pago is not None:
                if pago.estado == "omitido":
                    continue
                importe = pago.importe
            elif servicio.activo and servicio.toca(periodo):
                importe = servicio.precio_actual(periodo) or 0.0
            else:
                continue
            _sumar(totales, servicio.moneda, importe)
            detalle.append({"servicio_id": servicio.id, "importe": importe, "moneda": servicio.moneda})
        resultado.append({"periodo": periodo, "total": totales, "servicios": detalle})
    return resultado


def eventos(datos: Datos, hoy: date, desde: date, hasta: date) -> list[dict[str, Any]]:
    """Los vencimientos entre dos fechas (incluidas), para el calendario.

    Los pagos ya generados salen como están (cualquier estado); los meses aún no generados,
    desde el mes de hoy, salen como previstos con el precio vigente de cada servicio activo.
    """
    actual = periodo_de(hoy)
    inicio, fin = desde.isoformat(), hasta.isoformat()
    resultado = []
    for servicio in datos.servicios.values():
        for periodo in periodos_entre(periodo_de(desde), periodo_de(hasta)):
            pago = datos.pago(servicio.id, periodo)
            if pago is not None:
                evento = {"vence": pago.vence, "importe": pago.importe, "estado": pago.estado, "previsto": False}
            elif servicio.activo and servicio.toca(periodo) and periodo >= actual:
                evento = {
                    "vence": fecha_vencimiento(periodo, servicio.dia_vence).isoformat(),
                    "importe": servicio.precio_actual(periodo) or 0.0, "estado": "pendiente", "previsto": True,
                }
            else:
                continue
            if inicio <= evento["vence"] <= fin:
                resultado.append({
                    "servicio_id": servicio.id, "nombre": servicio.nombre, "periodo": periodo,
                    "moneda": servicio.moneda, "pago": servicio.pago, **evento,
                })
    return sorted(resultado, key=lambda v: (v["vence"], v["servicio_id"]))


def vencimientos(datos: Datos, hoy: date, meses: int = 12) -> list[dict[str, Any]]:
    """Los vencimientos de los próximos ``meses`` (desde el día 1 del mes de hoy), generados y previstos."""
    ultimo = sumar_meses(periodo_de(hoy), meses - 1)
    return eventos(datos, hoy, hoy.replace(day=1), fecha_vencimiento(ultimo, 31))


def proximo_vencimiento(datos: Datos, hoy: date) -> dict[str, Any] | None:
    """El próximo vencimiento de pago manual pendiente desde hoy (los débitos se pagan solos)."""
    for vencimiento in vencimientos(datos, hoy):
        if (vencimiento["pago"] == "manual" and vencimiento["estado"] == "pendiente"
                and vencimiento["vence"] >= hoy.isoformat()):
            return vencimiento
    return None


def descripcion_todo(datos: Datos, pago: Pago) -> str:
    """La descripción del ítem de ``todo.facturas`` en el formato que lee Alex."""
    servicio = datos.servicios.get(pago.servicio_id)
    importe = f"{pago.importe:.2f}".rstrip("0").rstrip(".")
    return (
        f"importe={importe}; moneda={servicio.moneda if servicio else 'pesos'}; "
        f"pago={servicio.pago if servicio else 'manual'}; origen={pago.origen or 'manual'}"
    )


# ---------------------------------------------------------------------------
# Copia de seguridad
# ---------------------------------------------------------------------------


def exportar(datos: Datos, hoy: date) -> dict[str, Any]:
    """Todo en un JSON que se puede guardar y volver a importar."""
    return {"facturas": VERSION_EXPORTACION, "exportado": hoy.isoformat(), "datos": datos.a_dict()}


def importar(datos: Datos, crudo: Any, modo: str = "combinar") -> dict[str, int]:
    """Carga una copia exportada (o el contenido de ``.storage/facturas``).

    - ``reemplazar``: todo lo actual se sustituye por la copia.
    - ``combinar``: se agregan los servicios de la copia que no existan (por id), con sus pagos;
      los que ya existen no se tocan.

    Valida todo antes de cambiar nada. Devuelve cuántos servicios y pagos entraron.
    """
    _elegir(modo, MODOS_IMPORTAR, "modo")
    if isinstance(crudo, dict) and isinstance(crudo.get("datos"), dict):
        if crudo.get("facturas", 1) > VERSION_EXPORTACION:
            raise ErrorFacturas("La copia es de una versión más nueva de Facturas")
        crudo = crudo["datos"]
    elif isinstance(crudo, dict) and isinstance(crudo.get("data"), dict):  # archivo de .storage
        crudo = crudo["data"]
    if not isinstance(crudo, dict) or not isinstance(crudo.get("servicios"), list):
        raise ErrorFacturas("El archivo no es una copia de Facturas")
    try:
        copia = Datos.desde_dict(crudo).validar()
    except ErrorFacturas:
        raise
    except (TypeError, ValueError, KeyError, AttributeError) as err:
        raise ErrorFacturas(f"La copia tiene datos inválidos: {err}") from None

    if modo == "reemplazar":
        datos.servicios = copia.servicios
        datos.pagos = copia.pagos
        return {"servicios": len(copia.servicios), "pagos": len(copia.pagos)}

    nuevos = {sid: s for sid, s in copia.servicios.items() if sid not in datos.servicios}
    pagos = [p for p in copia.pagos if p.servicio_id in nuevos]
    datos.servicios.update(nuevos)
    datos.pagos.extend(pagos)
    return {"servicios": len(nuevos), "pagos": len(pagos)}
