"""Pruebas de las mejoras de logica.py: borrar, meses anteriores pagados, débito automático,
varios meses juntos y copia de seguridad."""

import json
from datetime import date

import pytest

import logica as L
from logica import Datos, ErrorFacturas

HOY = date(2026, 10, 5)


def _datos(**servicios):
    datos = Datos()
    for nombre, campos in servicios.items():
        L.agregar_servicio(datos, HOY, nombre=nombre, **campos)
    return datos


class TestBorrar:
    def test_borrar_servicio_y_sus_pagos(self):
        datos = _datos(UTE={"importe": 1500, "desde": "2026-08"}, Antel={"importe": 1890})
        L.registrar_pago(datos, HOY, "ute")
        L.borrar_servicio(datos, "ute")
        assert list(datos.servicios) == ["antel"]
        assert {p.servicio_id for p in datos.pagos} == {"antel"}
        with pytest.raises(ErrorFacturas):
            L.borrar_servicio(datos, "ute")

    def test_borrar_precio_recalcula_pendientes(self):
        datos = _datos(UTE={"importe": 1500, "desde": "2026-08"})
        L.cambiar_precio(datos, "ute", 1700, "2026-09")
        L.registrar_pago(datos, HOY, "ute", periodo="2026-09")  # pagado con 1700: no se toca
        assert datos.pago("ute", "2026-10").estimado == 1700
        actualizados = L.borrar_precio(datos, "ute", "2026-09")
        assert [p.periodo for p in actualizados] == ["2026-10"]
        assert datos.pago("ute", "2026-10").estimado == 1500
        assert datos.pago("ute", "2026-09").real == 1700
        assert [(p.desde, p.importe) for p in datos.servicio("ute").precios] == [("2026-08", 1500)]

    def test_no_se_borra_el_unico_precio_ni_uno_que_no_existe(self):
        datos = _datos(UTE={"importe": 1500})
        with pytest.raises(ErrorFacturas, match="único"):
            L.borrar_precio(datos, "ute", "2026-10")
        with pytest.raises(ErrorFacturas, match="no tiene un precio"):
            L.borrar_precio(datos, "ute", "2026-01")


class TestAnterioresPagados:
    def test_los_meses_anteriores_quedan_pagados(self):
        datos = _datos(UTE={"importe": 1500, "dia_vence": 12, "desde": "2026-07", "anteriores_pagados": True})
        estados = [(p.periodo, p.estado, p.real, p.pagado_el) for p in datos.pagos_de("ute")]
        assert estados == [
            ("2026-07", "pagado", 1500, "2026-07-12"),
            ("2026-08", "pagado", 1500, "2026-08-12"),
            ("2026-09", "pagado", 1500, "2026-09-12"),
            ("2026-10", "pendiente", None, None),  # el mes de hoy no
        ]
        assert L.vencidos_anteriores(datos, HOY) == []

    def test_sin_la_opcion_quedan_vencidos(self):
        datos = _datos(UTE={"importe": 1500, "desde": "2026-07"})
        assert len(L.vencidos_anteriores(datos, HOY)) == 3


class TestDebitoAutomatico:
    def test_paga_los_vencidos_con_el_importe_anotado_o_estimado(self):
        datos = _datos(
            Celular={"importe": 690, "pago": "debito", "auto_pagar": True, "dia_vence": 3, "desde": "2026-09"},
            Netflix={"importe": 12, "pago": "debito", "auto_pagar": True, "dia_vence": 20},
            Antel={"importe": 1890, "dia_vence": 3, "auto_pagar": True},  # manual: no se paga solo
            Gym={"importe": 900, "pago": "debito", "dia_vence": 1},  # débito sin auto_pagar
        )
        L.anotar_importe(datos, "celular", 720, periodo="2026-10")
        pagados = L.pagar_debitos(datos, HOY)
        assert [(p.servicio_id, p.periodo, p.real, p.pagado_el, p.origen) for p in pagados] == [
            ("celular", "2026-09", 690, "2026-09-03", "automatico"),
            ("celular", "2026-10", 720, "2026-10-03", "automatico"),
        ]
        assert datos.pago("netflix", "2026-10").estado == "pendiente"  # vence el 20
        assert L.pagar_debitos(datos, HOY) == []  # idempotente
        assert [p.servicio_id for p in L.pagar_debitos(datos, date(2026, 10, 20))] == ["netflix"]

    def test_mantenimiento_genera_y_paga(self):
        datos = _datos(Celular={"importe": 690, "pago": "debito", "auto_pagar": True, "dia_vence": 3})
        cambios = L.mantenimiento(datos, date(2026, 11, 3))
        assert sorted((p.periodo, p.estado) for p in cambios) == [("2026-10", "pagado"), ("2026-11", "pagado")]

    def test_se_puede_activar_editando(self):
        datos = _datos(Celular={"importe": 690, "pago": "debito", "dia_vence": 3})
        L.editar_servicio(datos, HOY, "celular", auto_pagar=True)
        assert datos.servicio("celular").auto_pagar is True
        assert len(L.pagar_debitos(datos, HOY)) == 1


class TestVariosMeses:
    def test_pendientes_y_adelanto_hasta_un_mes(self):
        datos = _datos(Gym={"importe": 1200, "desde": "2026-08"})
        L.registrar_pago(datos, HOY, "gym", periodo="2026-09")
        pagados = L.registrar_pagos_hasta(datos, HOY, "gym", "2026-12", real=1100, nota="trimestre")
        assert [(p.periodo, p.real, p.nota) for p in pagados] == [
            ("2026-08", 1100, "trimestre"), ("2026-10", 1100, "trimestre"),
            ("2026-11", 1100, "trimestre"), ("2026-12", 1100, "trimestre"),
        ]
        assert datos.pago("gym", "2026-09").real == 1200  # ya estaba pagado: no se toca

    def test_respeta_los_meses_que_tocan(self):
        datos = _datos(Seguro={"importe": 9000, "meses": [3, 9], "desde": "2026-09"})
        pagados = L.registrar_pagos_hasta(datos, HOY, "seguro", "2027-12")
        assert [p.periodo for p in pagados] == ["2026-09", "2027-03", "2027-09"]

    def test_sin_nada_pendiente(self):
        datos = _datos(Gym={"importe": 1200})
        L.registrar_pago(datos, HOY, "gym")
        with pytest.raises(ErrorFacturas, match="no tiene pagos pendientes"):
            L.registrar_pagos_hasta(datos, HOY, "gym", "2026-10")


class TestCopia:
    def test_exportar_e_importar_reemplazando(self):
        origen = _datos(UTE={"importe": 1500, "desde": "2026-09"}, Netflix={"importe": 12, "moneda": "dolares"})
        L.registrar_pago(origen, HOY, "ute", real=1450)
        copia = json.loads(json.dumps(L.exportar(origen, HOY)))
        assert copia["facturas"] == 1 and copia["exportado"] == "2026-10-05"

        destino = _datos(Gas={"importe": 500})
        assert L.importar(destino, copia, "reemplazar") == {"servicios": 2, "pagos": 3}
        assert destino.a_dict() == origen.a_dict()

    def test_combinar_agrega_solo_lo_nuevo(self):
        origen = _datos(UTE={"importe": 1500}, Netflix={"importe": 12})
        destino = _datos(UTE={"importe": 9999})
        assert L.importar(destino, L.exportar(origen, HOY)) == {"servicios": 1, "pagos": 1}
        assert destino.servicio("ute").precios[0].importe == 9999  # el existente no se toca
        assert "netflix" in destino.servicios

    def test_acepta_el_archivo_de_storage_y_campos_desconocidos(self):
        origen = _datos(UTE={"importe": 1500})
        crudo = {"version": 1, "key": "facturas", "data": origen.a_dict()}
        crudo["data"]["servicios"][0]["campo_del_futuro"] = 1
        destino = Datos()
        assert L.importar(destino, crudo, "reemplazar")["servicios"] == 1

    @pytest.mark.parametrize(
        "malo",
        [
            {"cualquier": "cosa"},
            [],
            {"servicios": [{"id": "x"}], "pagos": []},  # sin nombre ni precio
            {"servicios": [], "pagos": [{"servicio_id": "fantasma", "periodo": "2026-10", "vence": "2026-10-10",
                                         "estimado": 1}]},
            {"facturas": 99, "datos": {"servicios": [], "pagos": []}},
        ],
    )
    def test_copias_invalidas_no_cambian_nada(self, malo):
        destino = _datos(UTE={"importe": 1500})
        antes = destino.a_dict()
        with pytest.raises(ErrorFacturas):
            L.importar(destino, malo, "reemplazar")
        assert destino.a_dict() == antes

    def test_pago_repetido_o_estado_invalido(self):
        origen = _datos(UTE={"importe": 1500})
        crudo = origen.a_dict()
        crudo["pagos"].append(dict(crudo["pagos"][0]))
        with pytest.raises(ErrorFacturas, match="repetido"):
            L.importar(Datos(), crudo, "reemplazar")
        crudo["pagos"] = [dict(crudo["pagos"][0], estado="perdido")]
        with pytest.raises(ErrorFacturas, match="estado"):
            L.importar(Datos(), crudo, "reemplazar")

    def test_modo_invalido(self):
        with pytest.raises(ErrorFacturas):
            L.importar(Datos(), {"servicios": [], "pagos": []}, "pisar")
