# Facturas para Home Assistant

Integración personalizada para llevar los servicios que se pagan (luz, agua, internet, celular, seguros,
suscripciones...): su precio y su historial, cuándo vencen y cada cuánto, lo pagado, lo que falta y lo que
costó de verdad cada mes.

> **Estado: en desarrollo.** La lógica de cálculo está hecha y probada; la integración (entidades, acciones y
> panel) todavía no. No instalar aún.

## Qué hace

- Servicios con categoría, moneda (pesos o dólares), día de vencimiento, forma de pago (manual o débito) y
  periodicidad: mensual, cada N meses, en meses concretos o anual.
- Cambios de precio **desde un mes**, sin reescribir el historial.
- Importe estimado (el precio vigente) y real (el que se pagó) de cada mes.
- Estadísticas: el mes (previsto, pagado, falta, vencido), el año, por servicio y por categoría, estimado
  contra real, subidas de precio y la previsión de los próximos 12 meses. Los totales se llevan por moneda,
  sin convertir.
- Todo local: los datos quedan en `.storage/` del propio Home Assistant, sin internet ni servicios externos.

## Requisitos

- Home Assistant **2025.11** o posterior (se prueba contra Core 2025.11.3, la última serie con 32 bits).
- Python puro, sin dependencias: funciona igual en 32 y 64 bits.

## Instalación (cuando haya un release)

1. HACS → menú → *Repositorios personalizados* → `https://github.com/abestard/ha-facturas`, categoría
   *Integración*.
2. Descargar *Facturas* y reiniciar Home Assistant.
3. Ajustes → Dispositivos y servicios → Agregar integración → *Facturas*.

## Desarrollo

`custom_components/facturas/logica.py` tiene todo el cálculo y no importa nada de Home Assistant, así que sus
pruebas corren con cualquier Python ≥ 3.12:

```bash
pip install pytest
pytest
```

Para probar contra la versión exacta de Home Assistant (2025.11.3, Python 3.13) se usa Docker, porque Home
Assistant no se instala en Windows:

```bash
docker build -f Dockerfile.pruebas -t ha-facturas-pruebas .
docker run --rm -v "$PWD:/repo" ha-facturas-pruebas
```

## Licencia

[MIT](LICENSE)
