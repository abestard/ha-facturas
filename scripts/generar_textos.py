"""Genera strings.json, translations/en.json y translations/es.json de Facturas.

Los textos de las acciones, campos y entidades se editan acá (inglés y español juntos) y
se regeneran los tres archivos, así no se desincronizan:

    python scripts/generar_textos.py
"""
import json
from pathlib import Path

destino = Path(__file__).resolve().parent.parent / "custom_components" / "facturas"

# campo -> (en_nombre, en_desc, es_nombre, es_desc)
C = {
    "servicio": ("Service", "Id or name of the service.", "Servicio", "Id o nombre del servicio."),
    "nombre": ("Name", "Name of the service.", "Nombre", "Nombre del servicio."),
    "importe": ("Amount", "Amount.", "Importe", "Importe."),
    "categoria": ("Category", "Category (home, communications, insurance, subscriptions...).", "Categoría",
                  "Categoría (casa, comunicaciones, seguros, suscripciones...)."),
    "moneda": ("Currency", "Currency of the service.", "Moneda", "Moneda del servicio."),
    "pago": ("Payment method", "Manual payment or automatic debit.", "Forma de pago", "Pago manual o débito automático."),
    "tipo": ("Type", "Fixed amount or consumption-based (the real amount usually changes).", "Tipo",
             "Importe fijo o por consumo (el real suele cambiar)."),
    "dia_vence": ("Due day", "Approximate due day (the last day if the month is shorter).", "Día de vencimiento",
                  "Día aproximado de vencimiento (el último si el mes tiene menos días)."),
    "meses": ("Months", "Months when it is paid (all of them = monthly).", "Meses", "Meses en que se paga (todos = mensual)."),
    "desde": ("From", "Month (YYYY-MM). Defaults to the current month.", "Desde", "Mes (AAAA-MM). Por defecto, el mes actual."),
    "remitente": ("Sender", "Email address the bills come from.", "Remitente", "Correo desde el que llega la factura."),
    "notas": ("Notes", "Free notes.", "Notas", "Notas libres."),
    "periodo": ("Period", "Month (YYYY-MM). Defaults to the oldest pending one.", "Período",
                "Mes (AAAA-MM). Por defecto, el pendiente más viejo."),
    "fecha": ("Date", "Payment date. Defaults to today.", "Fecha", "Fecha de pago. Por defecto, hoy."),
    "nota": ("Note", "Note (discount, surcharge...).", "Nota", "Nota (descuento, recargo...)."),
    "origen": ("Source", "Where the data came from.", "Origen", "De dónde salió el dato."),
    "anio": ("Year", "Year for the yearly summary. Defaults to the current year.", "Año",
             "Año del resumen anual. Por defecto, el actual."),
    "auto_pagar": ("Pay automatically", "Automatic debit only: on the due date the payment is marked as paid.",
                   "Pagar solo", "Solo débito automático: el día del vencimiento el pago se marca como pagado."),
    "anteriores_pagados": ("Previous months paid", "Payments of months before the current one are marked as paid.",
                           "Meses anteriores pagados",
                           "Los pagos de los meses anteriores al actual quedan como pagados."),
    "hasta": ("Until", "Pay every pending month up to this one (YYYY-MM), including future months.",
              "Hasta", "Paga todos los meses pendientes hasta este (AAAA-MM), incluso meses futuros."),
    "datos": ("Data", "The exported copy (the JSON of Export).", "Datos", "La copia exportada (el JSON de Exportar)."),
    "modo": ("Mode", "Merge adds only new services; replace swaps everything.", "Modo",
             "Combinar agrega solo los servicios nuevos; reemplazar sustituye todo."),
}

# acción -> (campos, en_nombre, en_desc, es_nombre, es_desc, {campo: (en_desc, es_desc)})
S = {
    "agregar_servicio": (
        ["nombre", "importe", "categoria", "moneda", "pago", "tipo", "dia_vence", "meses", "desde", "remitente", "notas",
         "auto_pagar", "anteriores_pagados"],
        "Add service", "Adds a service to pay and generates its payments up to this month.",
        "Agregar servicio", "Da de alta un servicio a pagar y genera sus pagos hasta este mes.",
        {"importe": ("Current price.", "Precio actual."),
         "desde": ("First month of the service (YYYY-MM). Defaults to this month.",
                   "Primer mes del servicio (AAAA-MM). Por defecto, este mes.")}),
    "editar_servicio": (
        ["servicio", "nombre", "categoria", "moneda", "pago", "tipo", "dia_vence", "meses", "remitente", "notas",
         "auto_pagar"],
        "Edit service", "Changes the data of a service (not the price: use Change price).",
        "Editar servicio", "Cambia los datos de un servicio (no el precio: para eso está Cambiar precio).", {}),
    "dar_de_baja": (["servicio"], "Deactivate service", "Stops generating payments; the history is kept.",
                    "Dar de baja", "Deja de generar pagos; el historial se conserva.", {}),
    "reactivar": (["servicio"], "Reactivate service", "Activates a deactivated service again from this month.",
                  "Reactivar", "Vuelve a activar un servicio dado de baja, desde este mes.", {}),
    "cambiar_precio": (["servicio", "importe", "desde"], "Change price",
                       "New price from a month on. Past months keep their price.",
                       "Cambiar precio", "Precio nuevo desde un mes. Los meses anteriores quedan como estaban.",
                       {"importe": ("New price.", "Precio nuevo.")}),
    "anotar_importe": (["servicio", "importe", "periodo", "nota", "origen"], "Record amount",
                       "Records the real amount of a month before paying it (the bill arrived).",
                       "Anotar importe", "Anota el importe real de un mes antes de pagarlo (llegó la factura).",
                       {"importe": ("Real amount of the bill.", "Importe real de la factura.")}),
    "registrar_pago": (["servicio", "periodo", "hasta", "importe", "fecha", "nota", "origen"], "Register payment",
                       "Marks a payment as done (or several, with Until). Also for paying in advance.",
                       "Registrar pago",
                       "Marca un pago como hecho (o varios, con Hasta). También sirve para pagar por adelantado.",
                       {"importe": ("Real amount paid (per month). Defaults to the recorded or estimated amount.",
                                    "Importe real pagado (por mes). Por defecto, el anotado o el estimado.")}),
    "corregir_pago": (["servicio", "periodo", "importe", "fecha", "nota"], "Correct payment",
                      "Corrects the real amount, payment date or note.",
                      "Corregir pago", "Corrige el importe real, la fecha de pago o la nota.",
                      {"periodo": ("Month (YYYY-MM).", "Mes (AAAA-MM)."), "importe": ("Real amount.", "Importe real."),
                       "fecha": ("Payment date.", "Fecha de pago.")}),
    "deshacer_pago": (["servicio", "periodo"], "Undo payment", "Sets a paid or skipped payment back to pending.",
                      "Deshacer pago", "Vuelve a pendiente un pago registrado u omitido.",
                      {"periodo": ("Month (YYYY-MM).", "Mes (AAAA-MM).")}),
    "omitir": (["servicio", "periodo", "nota"], "Skip", "This month is not paid: it does not count in the totals.",
               "Omitir", "Este mes no se paga: no cuenta en los totales.", {}),
    "resumen": (["periodo", "anio", "servicio"], "Summary",
                "Returns the month, the year, the pending payments and the services.",
                "Resumen", "Devuelve el mes, el año, los pagos pendientes y los servicios.",
                {"periodo": ("Month (YYYY-MM). Defaults to this month.", "Mes (AAAA-MM). Por defecto, este mes."),
                 "servicio": ("Also returns the statistics of this service.",
                              "Además devuelve las estadísticas de este servicio.")}),
    "borrar_servicio": (["servicio"], "Delete service",
                        "Deletes the service and all its payments forever (admins only). To stop paying it, use Deactivate.",
                        "Borrar servicio",
                        "Borra el servicio y todos sus pagos para siempre (solo administradores). Para dejar de "
                        "pagarlo está Dar de baja.", {}),
    "borrar_precio": (["servicio", "desde"], "Delete price",
                      "Removes a wrongly entered price from the history (admins only).",
                      "Quitar precio", "Quita un precio mal cargado del historial (solo administradores).",
                      {"desde": ("Month the price starts (YYYY-MM).", "Mes desde el que rige ese precio (AAAA-MM).")}),
    "exportar": ([], "Export", "Returns all the data as JSON, to keep a copy (admins only).",
                 "Exportar", "Devuelve todos los datos en JSON, para guardar una copia (solo administradores).", {}),
    "importar": (["datos", "modo"], "Import", "Loads an exported copy (admins only).",
                 "Importar", "Carga una copia exportada (solo administradores).", {}),
}

SEL = {
    "moneda": ({"pesos": "Pesos", "dolares": "Dollars"}, {"pesos": "Pesos", "dolares": "Dólares"}),
    "pago": ({"manual": "Manual", "debito": "Automatic debit"}, {"manual": "Manual", "debito": "Débito automático"}),
    "tipo": ({"fijo": "Fixed", "consumo": "Consumption"}, {"fijo": "Fijo", "consumo": "Por consumo"}),
    "origen": ({"manual": "Manual", "correo": "Email", "alex": "Alex", "automatico": "Automatic"},
               {"manual": "Manual", "correo": "Correo", "alex": "Alex", "automatico": "Automático"}),
    "moneda_principal": ({"pesos": "Pesos", "dolares": "Dollars"}, {"pesos": "Pesos", "dolares": "Dólares"}),
    "modo": ({"combinar": "Merge", "reemplazar": "Replace"}, {"combinar": "Combinar", "reemplazar": "Reemplazar"}),
}
MES_EN = "January February March April May June July August September October November December".split()
MES_ES = "Enero Febrero Marzo Abril Mayo Junio Julio Agosto Septiembre Octubre Noviembre Diciembre".split()


def armar(en: bool) -> dict:
    opciones = {
        "data": {"moneda_principal": "Main currency" if en else "Moneda principal",
                 "dias_aviso": "Reminder days" if en else "Días de aviso"},
        "data_description": {
            "moneda_principal": "Currency shown first in the summaries." if en
            else "La moneda que se muestra primero en los resúmenes.",
            "dias_aviso": "How many days before the due date to remind." if en
            else "Cuántos días antes del vencimiento avisar."},
    }
    servicios = {}
    for clave, (campos, en_n, en_d, es_n, es_d, extra) in S.items():
        fields = {}
        for campo in campos:
            nombre = C[campo][0 if en else 2]
            desc = extra[campo][0 if en else 1] if campo in extra else C[campo][1 if en else 3]
            fields[campo] = {"name": nombre, "description": desc}
        servicios[clave] = {"name": en_n if en else es_n, "description": en_d if en else es_d, "fields": fields}
    selector = {k: {"options": v[0 if en else 1]} for k, v in SEL.items()}
    selector["meses"] = {"options": {str(m + 1): (MES_EN if en else MES_ES)[m] for m in range(12)}}
    return {
        "config": {
            "step": {"user": {
                "title": "Facturas",
                "description": "Bills and services: prices, due dates and payments." if en
                else "Facturas y servicios: precios, vencimientos y pagos.",
                **opciones}},
            "abort": {"single_instance_allowed": "Facturas is already configured." if en
                      else "Facturas ya está configurada."},
        },
        "options": {"step": {"init": {"title": "Facturas", **opciones}}},
        "entity": {"sensor": {
            clave: {"name": textos[0 if en else 1]}
            for clave, textos in {
                "mes_previsto": ("Month expected", "Mes previsto"),
                "mes_pagado": ("Month paid", "Mes pagado"),
                "mes_falta": ("Month remaining", "Mes falta"),
                "anio_pagado": ("Year paid", "Año pagado"),
                "proxima": ("Next due date", "Próximo vencimiento"),
                "mes_previsto_pesos": ("Month expected (pesos)", "Mes previsto (pesos)"),
                "mes_pagado_pesos": ("Month paid (pesos)", "Mes pagado (pesos)"),
                "mes_falta_pesos": ("Month remaining (pesos)", "Mes falta (pesos)"),
                "anio_pagado_pesos": ("Year paid (pesos)", "Año pagado (pesos)"),
                "mes_previsto_dolares": ("Month expected (dollars)", "Mes previsto (dólares)"),
                "mes_pagado_dolares": ("Month paid (dollars)", "Mes pagado (dólares)"),
                "mes_falta_dolares": ("Month remaining (dollars)", "Mes falta (dólares)"),
                "anio_pagado_dolares": ("Year paid (dollars)", "Año pagado (dólares)"),
            }.items()
        }},
        "selector": selector,
        "services": servicios,
    }


def escribir(ruta: Path, datos: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(datos, ensure_ascii=False, indent=2) + "\n")


escribir(destino / "strings.json", armar(True))
escribir(destino / "translations" / "en.json", armar(True))
escribir(destino / "translations" / "es.json", armar(False))
print("ok")
