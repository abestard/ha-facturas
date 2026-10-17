"""Pruebas de logica.py (Fase 1)."""

from datetime import date

import pytest

import logica as L
from logica import Datos, ErrorFacturas


def _datos_con(hoy, **servicios):
    """Datos con servicios dados como nombre → kwargs de agregar_servicio."""
    datos = Datos()
    for nombre, campos in servicios.items():
        L.agregar_servicio(datos, hoy, nombre=nombre, **campos)
    return datos


# ---------------------------------------------------------------------------
# Períodos y fechas
# ---------------------------------------------------------------------------


class TestPeriodos:
    def test_periodo_de(self):
        assert L.periodo_de(date(2026, 3, 5)) == "2026-03"

    @pytest.mark.parametrize(
        ("periodo", "n", "esperado"),
        [("2026-10", 1, "2026-11"), ("2026-12", 1, "2027-01"), ("2026-01", -1, "2025-12"),
         ("2026-05", 24, "2028-05"), ("2026-05", 0, "2026-05")],
    )
    def test_sumar_meses(self, periodo, n, esperado):
        assert L.sumar_meses(periodo, n) == esperado

    def test_periodos_entre_cruza_el_anio(self):
        assert list(L.periodos_entre("2026-11", "2027-02")) == ["2026-11", "2026-12", "2027-01", "2027-02"]
        assert list(L.periodos_entre("2026-05", "2026-04")) == []

    @pytest.mark.parametrize("malo", ["2026-13", "2026-00", "26-01", "2026/01", "", None, "2026-1"])
    def test_periodo_invalido(self, malo):
        with pytest.raises(ErrorFacturas):
            L.validar_periodo(malo)

    @pytest.mark.parametrize(
        ("periodo", "dia", "esperado"),
        [("2026-02", 31, date(2026, 2, 28)), ("2028-02", 31, date(2028, 2, 29)),
         ("2026-04", 31, date(2026, 4, 30)), ("2026-01", 31, date(2026, 1, 31)),
         ("2026-02", 29, date(2026, 2, 28)), ("2026-06", 12, date(2026, 6, 12))],
    )
    def test_vencimiento_meses_cortos(self, periodo, dia, esperado):
        assert L.fecha_vencimiento(periodo, dia) == esperado


# ---------------------------------------------------------------------------
# Periodicidad
# ---------------------------------------------------------------------------


class TestPeriodicidad:
    def test_mensual(self):
        assert L.meses_mensual() == list(range(1, 13))

    def test_cada_2_desde_febrero(self):
        assert L.meses_cada(2, 2) == [2, 4, 6, 8, 10, 12]

    def test_cada_3_da_la_vuelta(self):
        assert L.meses_cada(3, 11) == [2, 5, 8, 11]

    def test_cada_6_y_12(self):
        assert L.meses_cada(6, 3) == [3, 9]
        assert L.meses_cada(12, 7) == [7]

    def test_cada_n_que_no_divide_12(self):
        with pytest.raises(ErrorFacturas):
            L.meses_cada(5, 1)

    def test_anual(self):
        assert L.meses_anual(3) == [3]
        with pytest.raises(ErrorFacturas):
            L.meses_anual(13)

    def test_meses_concretos_se_ordenan_sin_repetir(self):
        assert L.validar_meses([4, 1, 4, 10]) == [1, 4, 10]

    @pytest.mark.parametrize("malo", [[], [0], [13], ["3"]])
    def test_meses_invalidos(self, malo):
        with pytest.raises(ErrorFacturas):
            L.validar_meses(malo)

    @pytest.mark.parametrize(
        ("meses", "texto"),
        [(list(range(1, 13)), "mensual"), ([3], "anual (marzo)"), ([2, 4, 6, 8, 10, 12], "cada 2 meses"),
         ([1, 4, 7, 10], "cada 3 meses"), ([1, 4, 10], "enero, abril, octubre")],
    )
    def test_describir(self, meses, texto):
        assert L.describir_meses(meses) == texto


# ---------------------------------------------------------------------------
# Servicios y precios
# ---------------------------------------------------------------------------


HOY = date(2026, 10, 5)


class TestServicios:
    def test_alta_genera_el_pago_del_mes(self):
        datos = _datos_con(HOY, UTE={"importe": 1500, "dia_vence": 12, "categoria": "Casa"})
        servicio = datos.servicio("ute")
        assert servicio.categoria == "casa"
        assert servicio.alta == "2026-10"
        [pago] = datos.pagos
        assert (pago.periodo, pago.vence, pago.estimado, pago.estado) == ("2026-10", "2026-10-12", 1500, "pendiente")

    def test_alta_en_un_mes_que_no_toca_no_genera(self):
        datos = _datos_con(HOY, Seguro={"importe": 9000, "meses": [3]})
        assert datos.pagos == []

    def test_alta_desde_un_mes_pasado_rellena(self):
        datos = _datos_con(HOY, Antel={"importe": 1890, "desde": "2026-08"})
        assert [p.periodo for p in datos.pagos] == ["2026-08", "2026-09", "2026-10"]

    def test_ids_unicos_y_sin_tildes(self):
        datos = _datos_con(HOY, **{"Teléfono Mamá": {"importe": 1}})
        L.agregar_servicio(datos, HOY, nombre="Teléfono mamá", importe=1)
        assert sorted(datos.servicios) == ["telefono_mama", "telefono_mama_2"]

    @pytest.mark.parametrize(
        "campos",
        [{"importe": -1}, {"importe": "mucho"}, {"importe": 1, "moneda": "euros"}, {"importe": 1, "pago": "tarjeta"},
         {"importe": 1, "dia_vence": 0}, {"importe": 1, "dia_vence": 32}, {"importe": 1, "meses": []},
         {"importe": 1, "tipo": "variable"}],
    )
    def test_alta_invalida(self, campos):
        datos = Datos()
        with pytest.raises(ErrorFacturas):
            L.agregar_servicio(datos, HOY, nombre="X", **campos)
        assert datos.servicios == {}

    def test_nombre_vacio(self):
        with pytest.raises(ErrorFacturas):
            L.agregar_servicio(Datos(), HOY, nombre="  ", importe=1)

    def test_buscar_servicio(self):
        datos = _datos_con(HOY, UTE={"importe": 1}, Antel={"importe": 1}, **{"Antel celular": {"importe": 1}})
        assert L.Datos.buscar_servicio(datos, "ute").id == "ute"
        assert datos.buscar_servicio("antel").id == "antel"  # nombre exacto gana
        assert datos.buscar_servicio("celu").id == "antel_celular"
        with pytest.raises(ErrorFacturas):
            datos.buscar_servicio("gas")

    def test_buscar_servicio_ambiguo(self):
        datos = _datos_con(HOY, **{"Seguro auto": {"importe": 1}, "Seguro casa": {"importe": 1}})
        with pytest.raises(ErrorFacturas, match="varios"):
            datos.buscar_servicio("seguro")

    def test_editar_dia_actualiza_pendientes_desde_hoy(self):
        datos = _datos_con(HOY, UTE={"importe": 1500, "dia_vence": 12, "desde": "2026-09"})
        L.editar_servicio(datos, HOY, "ute", dia_vence=20)
        assert datos.pago("ute", "2026-09").vence == "2026-09-12"  # el pasado no se toca
        assert datos.pago("ute", "2026-10").vence == "2026-10-20"

    def test_editar_meses_quita_y_agrega(self):
        datos = _datos_con(HOY, Seguro={"importe": 100, "meses": [3]})
        L.editar_servicio(datos, HOY, "seguro", meses=[10])
        assert [p.periodo for p in datos.pagos] == ["2026-10"]
        L.editar_servicio(datos, HOY, "seguro", meses=[11])
        assert datos.pagos == []

    def test_editar_invalido_no_cambia_nada(self):
        datos = _datos_con(HOY, UTE={"importe": 1500})
        with pytest.raises(ErrorFacturas):
            L.editar_servicio(datos, HOY, "ute", moneda="euros", nombre="Otro")
        assert datos.servicio("ute").nombre == "UTE"
        assert datos.servicio("ute").moneda == "pesos"
        with pytest.raises(ErrorFacturas):
            L.editar_servicio(datos, HOY, "ute", precios=[])

    def test_baja_conserva_historial_y_deja_de_generar(self):
        datos = _datos_con(HOY, Netflix={"importe": 12, "moneda": "dolares", "desde": "2026-09"})
        L.registrar_pago(datos, HOY, "netflix", periodo="2026-09")
        L.registrar_pago(datos, HOY, "netflix", periodo="2026-11")  # adelantado
        L.anotar_importe(datos, "netflix", 13, periodo="2026-12")  # futuro con real
        L.generar_pagos(datos, HOY, hasta="2027-01")
        L.dar_de_baja(datos, HOY, "netflix")
        periodos = [p.periodo for p in datos.pagos_de("netflix")]
        assert periodos == ["2026-09", "2026-10", "2026-11", "2026-12"]  # sale enero (futuro, sin real)
        assert L.generar_pagos(datos, date(2027, 3, 1)) == []
        with pytest.raises(ErrorFacturas, match="baja"):
            L.registrar_pago(datos, HOY, "netflix", periodo="2027-05")

    def test_reactivar_no_rellena_los_meses_de_baja(self):
        datos = _datos_con(HOY, Netflix={"importe": 12})
        L.dar_de_baja(datos, HOY, "netflix")
        L.reactivar(datos, date(2027, 2, 3), "netflix")
        assert [p.periodo for p in datos.pagos] == ["2026-10", "2027-02"]


class TestPrecios:
    def test_precio_vigente(self):
        datos = _datos_con(HOY, UTE={"importe": 1500, "desde": "2026-01"})
        servicio = datos.servicio("ute")
        L.cambiar_precio(datos, "ute", 1650, "2026-09")
        L.cambiar_precio(datos, "ute", 1800, "2027-03")
        assert servicio.precio_en("2025-12") is None
        assert servicio.precio_actual("2025-12") == 1500
        assert servicio.precio_en("2026-01") == 1500
        assert servicio.precio_en("2026-08") == 1500
        assert servicio.precio_en("2026-09") == 1650
        assert servicio.precio_en("2027-02") == 1650
        assert servicio.precio_en("2030-01") == 1800

    def test_cambio_no_reescribe_el_historial(self):
        datos = _datos_con(HOY, UTE={"importe": 1500, "desde": "2026-07"})
        L.registrar_pago(datos, HOY, "ute", periodo="2026-07", real=1490)  # pagado
        L.anotar_importe(datos, "ute", 1520, periodo="2026-09")  # pendiente con real
        actualizados = L.cambiar_precio(datos, "ute", 1650, "2026-08")
        assert [p.periodo for p in actualizados] == ["2026-08", "2026-10"]
        assert datos.pago("ute", "2026-07").estimado == 1500
        assert datos.pago("ute", "2026-08").estimado == 1650
        assert datos.pago("ute", "2026-09").estimado == 1500  # tenía real: no se toca
        assert datos.pago("ute", "2026-09").real == 1520
        assert datos.pago("ute", "2026-10").estimado == 1650

    def test_pagado_desde_el_mes_del_cambio_no_se_toca(self):
        datos = _datos_con(HOY, UTE={"importe": 1500})
        L.registrar_pago(datos, HOY, "ute")
        assert L.cambiar_precio(datos, "ute", 1650, "2026-10") == []
        assert datos.pago("ute", "2026-10").estimado == 1500
        assert datos.pago("ute", "2026-10").real == 1500

    def test_mismo_desde_reemplaza(self):
        datos = _datos_con(HOY, UTE={"importe": 1500})
        L.cambiar_precio(datos, "ute", 1700, "2026-11")
        L.cambiar_precio(datos, "ute", 1650, "2026-11")
        assert [(p.desde, p.importe) for p in datos.servicio("ute").precios] == [("2026-10", 1500), ("2026-11", 1650)]

    def test_meses_siguientes_usan_el_precio_nuevo(self):
        datos = _datos_con(HOY, UTE={"importe": 1500})
        L.cambiar_precio(datos, "ute", 1650, "2026-12")
        L.generar_pagos(datos, date(2027, 1, 1))
        assert [p.estimado for p in datos.pagos] == [1500, 1500, 1650, 1650]

    def test_precio_invalido(self):
        datos = _datos_con(HOY, UTE={"importe": 1500})
        with pytest.raises(ErrorFacturas):
            L.cambiar_precio(datos, "ute", -3, "2026-11")
        with pytest.raises(ErrorFacturas):
            L.cambiar_precio(datos, "ute", 3, "2026-13")
        with pytest.raises(ErrorFacturas):
            L.cambiar_precio(datos, "gas", 3, "2026-11")

    def test_historial_y_subida(self):
        datos = _datos_con(HOY, UTE={"importe": 1000, "desde": "2026-01"})
        L.cambiar_precio(datos, "ute", 1100, "2026-05")
        L.cambiar_precio(datos, "ute", 1210, "2026-09")
        servicio = datos.servicio("ute")
        assert L.historial_precios(servicio) == [
            {"desde": "2026-01", "importe": 1000, "variacion": None},
            {"desde": "2026-05", "importe": 1100, "variacion": 10.0},
            {"desde": "2026-09", "importe": 1210, "variacion": 10.0},
        ]
        assert L.subida_precio(servicio, 2026) == {"inicio": 1000, "fin": 1210, "diferencia": 210, "porcentaje": 21.0}
        assert L.subida_precio(servicio, 2025) is None


# ---------------------------------------------------------------------------
# Generación de pagos
# ---------------------------------------------------------------------------


class TestGeneracion:
    def test_idempotente(self):
        datos = _datos_con(HOY, UTE={"importe": 1500})
        assert L.generar_pagos(datos, HOY) == []
        assert L.generar_pagos(datos, date(2026, 10, 31)) == []
        assert len(datos.pagos) == 1

    def test_dia_1_genera_el_mes_nuevo(self):
        datos = _datos_con(HOY, UTE={"importe": 1500})
        nuevos = L.generar_pagos(datos, date(2026, 11, 1))
        assert [p.periodo for p in nuevos] == ["2026-11"]

    def test_ha_apagado_varios_meses_y_cambio_de_anio(self):
        datos = _datos_con(HOY, UTE={"importe": 1500, "dia_vence": 31}, Seguro={"importe": 900, "meses": [1, 7]})
        L.cambiar_precio(datos, "ute", 1600, "2027-01")
        nuevos = L.generar_pagos(datos, date(2027, 2, 4))
        assert [(p.servicio_id, p.periodo, p.vence, p.estimado) for p in nuevos] == [
            ("ute", "2026-11", "2026-11-30", 1500),
            ("ute", "2026-12", "2026-12-31", 1500),
            ("ute", "2027-01", "2027-01-31", 1600),
            ("ute", "2027-02", "2027-02-28", 1600),
            ("seguro", "2027-01", "2027-01-10", 900),
        ]

    def test_el_estimado_se_fija_al_generar(self):
        # Generado con un precio: un cambio posterior "desde" un mes futuro no lo afecta.
        datos = _datos_con(HOY, UTE={"importe": 1500})
        L.cambiar_precio(datos, "ute", 1650, "2026-11")
        assert datos.pago("ute", "2026-10").estimado == 1500

    def test_no_duplica_un_adelanto(self):
        datos = _datos_con(HOY, UTE={"importe": 1500})
        L.registrar_pago(datos, HOY, "ute", periodo="2026-12")
        L.generar_pagos(datos, date(2027, 1, 1))
        assert [p.periodo for p in datos.pagos_de("ute")] == ["2026-10", "2026-11", "2026-12", "2027-01"]
        assert datos.pago("ute", "2026-12").estado == "pagado"

    def test_hacia_atras_no_hace_nada(self):
        datos = _datos_con(HOY, UTE={"importe": 1500})
        assert L.generar_pagos(datos, date(2026, 5, 1)) == []
        assert datos.servicio("ute").generado_hasta == "2026-10"


# ---------------------------------------------------------------------------
# Pagos
# ---------------------------------------------------------------------------


class TestPagos:
    def test_registrar_por_defecto_el_mas_viejo_con_el_estimado(self):
        datos = _datos_con(HOY, Antel={"importe": 1890, "desde": "2026-09"})
        pago = L.registrar_pago(datos, HOY, "antel", origen="alex")
        assert (pago.periodo, pago.real, pago.estado, pago.pagado_el, pago.origen) == (
            "2026-09", 1890, "pagado", "2026-10-05", "alex")
        assert L.registrar_pago(datos, HOY, "antel").periodo == "2026-10"
        with pytest.raises(ErrorFacturas, match="pendientes"):
            L.registrar_pago(datos, HOY, "antel")

    def test_registrar_con_real_fecha_y_nota(self):
        datos = _datos_con(HOY, UTE={"importe": 1650, "tipo": "consumo"})
        pago = L.registrar_pago(datos, HOY, "ute", real="1490.5", fecha=date(2026, 10, 3), nota="descuento por débito")
        assert (pago.real, pago.estimado, pago.pagado_el, pago.nota) == (1490.5, 1650, "2026-10-03", "descuento por débito")

    def test_registrar_usa_el_importe_anotado(self):
        datos = _datos_con(HOY, UTE={"importe": 1650, "tipo": "consumo"})
        L.anotar_importe(datos, "ute", 1720, origen="correo")
        assert datos.pago("ute", "2026-10").origen == "correo"
        assert L.registrar_pago(datos, HOY, "ute").real == 1720

    def test_no_se_paga_dos_veces(self):
        datos = _datos_con(HOY, UTE={"importe": 1650})
        L.registrar_pago(datos, HOY, "ute", periodo="2026-10")
        with pytest.raises(ErrorFacturas, match="ya está"):
            L.registrar_pago(datos, HOY, "ute", periodo="2026-10")

    def test_periodo_que_no_toca(self):
        datos = _datos_con(HOY, Seguro={"importe": 900, "meses": [1, 7]})
        with pytest.raises(ErrorFacturas):
            L.registrar_pago(datos, HOY, "seguro", periodo="2026-11")
        assert L.registrar_pago(datos, HOY, "seguro", periodo="2027-01").estimado == 900

    def test_origen_invalido(self):
        datos = _datos_con(HOY, UTE={"importe": 1650})
        with pytest.raises(ErrorFacturas):
            L.registrar_pago(datos, HOY, "ute", origen="paloma")

    def test_corregir(self):
        datos = _datos_con(HOY, UTE={"importe": 1650})
        L.registrar_pago(datos, HOY, "ute", real=1890)
        pago = L.corregir_pago(datos, "ute", "2026-10", real=1809, fecha=date(2026, 10, 4), nota="tipeo")
        assert (pago.real, pago.pagado_el, pago.nota) == (1809, "2026-10-04", "tipeo")

    def test_corregir_fecha_de_pendiente(self):
        datos = _datos_con(HOY, UTE={"importe": 1650})
        with pytest.raises(ErrorFacturas):
            L.corregir_pago(datos, "ute", "2026-10", fecha=HOY)
        with pytest.raises(ErrorFacturas):
            L.corregir_pago(datos, "ute", "2026-12", real=1)  # no existe y no se crea

    def test_deshacer(self):
        datos = _datos_con(HOY, UTE={"importe": 1500})
        L.registrar_pago(datos, HOY, "ute", real=1400)
        L.cambiar_precio(datos, "ute", 1650, "2026-10")  # mientras estaba pagado
        pago = L.deshacer_pago(datos, "ute", "2026-10")
        assert (pago.estado, pago.real, pago.pagado_el, pago.estimado) == ("pendiente", None, None, 1650)
        with pytest.raises(ErrorFacturas):
            L.deshacer_pago(datos, "ute", "2026-10")

    def test_omitir_y_deshacer(self):
        datos = _datos_con(HOY, Gym={"importe": 1200})
        L.omitir(datos, "gym", nota="vacaciones")
        assert datos.pago("gym", "2026-10").estado == "omitido"
        assert L.resumen_mes(datos, HOY)["previsto"]["pesos"] == 0
        assert L.deshacer_pago(datos, "gym", "2026-10").estado == "pendiente"

    def test_no_se_omite_un_pagado(self):
        datos = _datos_con(HOY, Gym={"importe": 1200})
        L.registrar_pago(datos, HOY, "gym")
        with pytest.raises(ErrorFacturas):
            L.omitir(datos, "gym", "2026-10")


# ---------------------------------------------------------------------------
# Resúmenes y estadísticas
# ---------------------------------------------------------------------------


@pytest.fixture
def casa():
    """Una casa con servicios en pesos y dólares, pagos de dos meses y uno vencido."""
    hoy_alta = date(2026, 9, 1)
    datos = _datos_con(
        hoy_alta,
        UTE={"importe": 1500, "dia_vence": 12, "categoria": "casa", "tipo": "consumo"},
        Antel={"importe": 1890, "dia_vence": 3, "categoria": "comunicaciones"},
        Netflix={"importe": 12, "moneda": "dolares", "pago": "debito", "dia_vence": 20, "categoria": "suscripciones"},
        Seguro={"importe": 9000, "meses": [3, 9], "dia_vence": 25, "categoria": "seguros"},
    )
    L.registrar_pago(datos, hoy_alta, "ute", real=1400, fecha=date(2026, 9, 10))
    L.registrar_pago(datos, hoy_alta, "netflix", fecha=date(2026, 9, 20))
    L.registrar_pago(datos, hoy_alta, "seguro", real=9000, fecha=date(2026, 9, 25))
    # Antel de septiembre queda sin pagar: vencido.
    L.generar_pagos(datos, HOY)
    L.registrar_pago(datos, HOY, "netflix")
    L.anotar_importe(datos, "ute", 1700)
    return datos


class TestResumenes:
    def test_resumen_mes(self, casa):
        hoy = date(2026, 10, 15)
        r = L.resumen_mes(casa, hoy)
        assert r["previsto"] == {"pesos": 1700 + 1890, "dolares": 12}
        assert r["pagado"] == {"pesos": 0, "dolares": 12}
        assert r["falta"] == {"pesos": 1700 + 1890, "dolares": 0}
        assert r["vencido"] == {"pesos": 1700 + 1890, "dolares": 0}  # UTE vence el 12, Antel el 3
        assert r["cantidad"] == {"total": 3, "pagados": 1, "pendientes": 2, "omitidos": 0}
        assert r["vencidos_anteriores"] == {"pesos": 1890, "dolares": 0}
        assert [(p.servicio_id, p.periodo) for p in r["pagos_vencidos_anteriores"]] == [("antel", "2026-09")]
        assert r["por_categoria"]["casa"] == {"pesos": 1700, "dolares": 0}

    def test_vencido_depende_de_hoy(self, casa):
        r = L.resumen_mes(casa, date(2026, 10, 5))
        assert r["vencido"]["pesos"] == 1890  # solo Antel (vence el 3)

    def test_resumen_de_un_mes_pasado(self, casa):
        r = L.resumen_mes(casa, HOY, "2026-09")
        assert r["previsto"] == {"pesos": 1400 + 1890 + 9000, "dolares": 12}
        assert r["pagado"] == {"pesos": 10400, "dolares": 12}
        assert r["falta"]["pesos"] == 1890
        assert r["vencidos_anteriores"]["pesos"] == 0  # nada antes de septiembre

    def test_pendientes_para_todo(self, casa):
        assert [(p.servicio_id, p.periodo) for p in L.pendientes(casa, HOY)] == [
            ("antel", "2026-09"), ("antel", "2026-10"), ("ute", "2026-10")]

    def test_resumen_anio(self, casa):
        L.registrar_pago(casa, HOY, "ute", real=1700)
        r = L.resumen_anio(casa, HOY)
        assert r["pagado"] == {"pesos": 1400 + 9000 + 1700, "dolares": 24}
        assert r["meses_transcurridos"] == 10
        assert r["media_mensual"] == {"pesos": 1210.0, "dolares": 2.4}
        assert r["ahorro"] == {"pesos": 100 - 200, "dolares": 0}
        assert r["por_mes"]["2026-09"] == {"pesos": 10400, "dolares": 12}
        assert r["por_mes"]["2026-01"] == {"pesos": 0, "dolares": 0}
        assert r["por_categoria"]["seguros"]["pesos"] == 9000
        ute = r["por_servicio"]["ute"]
        assert (ute["cantidad"], ute["total"], ute["media"], ute["minimo"], ute["maximo"], ute["diferencia_estimado"]) == (
            2, 3100, 1550, 1400, 1700, -100)
        assert "antel" not in r["por_servicio"]  # nada pagado

    def test_media_de_un_anio_cerrado_y_futuro(self, casa):
        assert L.resumen_anio(casa, date(2027, 3, 1), 2026)["meses_transcurridos"] == 12
        futuro = L.resumen_anio(casa, HOY, 2027)
        assert futuro["media_mensual"] == {"pesos": 0, "dolares": 0}

    def test_estadisticas_servicio(self, casa):
        r = L.estadisticas_servicio(casa, "ute")
        assert (r["cantidad"], r["media"], r["diferencia_estimado"]) == (1, 1400, 100)
        sin = L.estadisticas_servicio(casa, "antel")
        assert (sin["cantidad"], sin["media"], sin["minimo"]) == (0, None, None)

    def test_serie_mensual(self, casa):
        L.omitir(casa, "antel", "2026-09")
        serie = L.serie_mensual(casa, HOY, 3)
        assert [m["periodo"] for m in serie] == ["2026-08", "2026-09", "2026-10"]
        assert serie[0] == {"periodo": "2026-08", "previsto": {"pesos": 0, "dolares": 0},
                            "pagado": {"pesos": 0, "dolares": 0}}
        # Septiembre: Antel omitido no cuenta; UTE se estimó 1500 y se pagó 1400.
        assert serie[1]["previsto"] == {"pesos": 1500 + 9000, "dolares": 12}
        assert serie[1]["pagado"] == {"pesos": 1400 + 9000, "dolares": 12}
        # Octubre: el real anotado de UTE (sin pagar) no cambia el previsto.
        assert serie[2]["previsto"] == {"pesos": 1500 + 1890, "dolares": 12}
        assert serie[2]["pagado"] == {"pesos": 0, "dolares": 12}
        assert len(L.serie_mensual(casa, HOY)) == 12

    def test_prevision_12_meses(self, casa):
        L.cambiar_precio(casa, "ute", 1600, "2027-01")
        L.omitir(casa, "netflix", "2026-11")
        p = L.prevision(casa, HOY)
        assert [m["periodo"] for m in p][:3] == ["2026-10", "2026-11", "2026-12"]
        assert len(p) == 12
        meses = {m["periodo"]: m["total"] for m in p}
        assert meses["2026-10"] == {"pesos": 1700 + 1890, "dolares": 12}  # real anotado de UTE
        assert meses["2026-11"] == {"pesos": 1500 + 1890, "dolares": 0}  # Netflix omitido
        assert meses["2027-01"] == {"pesos": 1600 + 1890, "dolares": 12}
        assert meses["2027-03"] == {"pesos": 1600 + 1890 + 9000, "dolares": 12}

    def test_prevision_ignora_dados_de_baja(self, casa):
        L.dar_de_baja(casa, HOY, "netflix")
        p = L.prevision(casa, HOY, 3)
        assert [m["total"]["dolares"] for m in p] == [12, 0, 0]  # octubre ya estaba pagado

    def test_proximo_vencimiento_manual(self, casa):
        prox = L.proximo_vencimiento(casa, date(2026, 10, 13))
        # UTE vence el 12 (ya pasó), Netflix es débito: el próximo es Antel de noviembre (previsto).
        assert (prox["servicio_id"], prox["vence"], prox["previsto"]) == ("antel", "2026-11-03", True)
        prox = L.proximo_vencimiento(casa, date(2026, 10, 6))
        assert (prox["servicio_id"], prox["vence"], prox["importe"]) == ("ute", "2026-10-12", 1700)

    def test_vencimientos_incluye_previstos(self, casa):
        v = L.vencimientos(casa, HOY, 6)
        seguros = [x for x in v if x["servicio_id"] == "seguro"]
        assert [(x["vence"], x["previsto"]) for x in seguros] == [("2027-03-25", True)]

    def test_eventos_entre_fechas(self, casa):
        hoy = date(2026, 10, 15)
        e = L.eventos(casa, hoy, date(2026, 9, 1), date(2026, 11, 5))
        assert [(x["servicio_id"], x["vence"], x["estado"], x["previsto"]) for x in e] == [
            ("antel", "2026-09-03", "pendiente", False),
            ("ute", "2026-09-12", "pagado", False),
            ("netflix", "2026-09-20", "pagado", False),
            ("seguro", "2026-09-25", "pagado", False),
            ("antel", "2026-10-03", "pendiente", False),
            ("ute", "2026-10-12", "pendiente", False),
            ("netflix", "2026-10-20", "pagado", False),
            ("antel", "2026-11-03", "pendiente", True),
        ]
        assert e[0]["nombre"] == "Antel"

    def test_eventos_no_preve_el_pasado(self, casa):
        # Un mes pasado sin pago generado (antes del alta) no aparece como previsto.
        assert L.eventos(casa, HOY, date(2026, 7, 1), date(2026, 8, 31)) == []

    def test_descripcion_todo(self, casa):
        assert L.descripcion_todo(casa, casa.pago("ute", "2026-10")) == (
            "importe=1700; moneda=pesos; pago=manual; origen=manual")
        L.anotar_importe(casa, "antel", 1890.5, periodo="2026-10", origen="correo")
        assert L.descripcion_todo(casa, casa.pago("antel", "2026-10")) == (
            "importe=1890.5; moneda=pesos; pago=manual; origen=correo")


class TestSerializacion:
    def test_ida_y_vuelta(self, casa):
        import json

        crudo = json.loads(json.dumps(casa.a_dict()))
        otra = Datos.desde_dict(crudo)
        assert otra.a_dict() == casa.a_dict()
        assert otra.servicio("ute").precio_en("2026-10") == 1500
        assert L.resumen_mes(otra, HOY) == L.resumen_mes(casa, HOY)

    def test_vacio(self):
        assert Datos.desde_dict(None).a_dict() == {"servicios": [], "pagos": []}
