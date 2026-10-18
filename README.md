# Facturas para Home Assistant

Integración personalizada para llevar los servicios que se pagan (luz, agua, internet, celular, seguros,
suscripciones...): su precio y su historial, cuándo vencen y cada cuánto, lo pagado, lo que falta y lo que
costó de verdad cada mes.

![Este mes](https://raw.githubusercontent.com/abestard/ha-facturas/main/docs/capturas/este-mes.png)

## Qué hace

- Servicios con categoría, moneda (pesos o dólares), día de vencimiento, forma de pago (manual o débito) y
  periodicidad: mensual, cada N meses, en meses concretos o anual.
- Cambios de precio **desde un mes**, sin reescribir el historial.
- Importe estimado (el precio vigente) y real (el que se pagó) de cada mes.
- Débito automático que se marca como pagado solo el día del vencimiento (opcional, por servicio).
- Estadísticas: el mes (previsto, pagado, falta, vencido), el año, por servicio y por categoría, estimado
  contra real, subidas de precio y la previsión de los próximos 12 meses. Los totales se llevan por moneda,
  sin convertir.
- Copia de seguridad completa en JSON, para exportar e importar.
- Todo local: los datos quedan en `.storage/` del propio Home Assistant, sin internet ni servicios externos.

## El panel

En la barra lateral aparece **Facturas** (solo para administradores; también en la app Companion). Cada
pestaña se puede abrir directo desde la URL: `/facturas#servicios`, `#estadisticas`, `#historial`.

- **Este mes**: previsto, pagado y lo que falta; los vencidos de meses anteriores arriba, en rojo; cada pago
  con su estado y los botones *Pagado* (importe real, fecha, nota y, si se quiere, *hasta* qué mes pagar de
  una vez), *Importe* (anotar la factura que llegó) y *Omitir*. Las flechas cambian de mes.
- **Servicios**: alta y edición (la periodicidad con casillas de meses y atajos), *Cambió el precio* desde un
  mes, dar de baja y reactivar. Al dar de alta un servicio que empezó antes, se pueden marcar los meses
  anteriores como ya pagados. En la edición está el historial de precios (con *Quitar* para uno mal cargado)
  y *Borrar servicio* para lo cargado por error.
- **Estadísticas**: pagado en el año, media mensual y lo ahorrado (o gastado de más) contra lo estimado;
  barras de los últimos 12 meses (previsto contra pagado), por categoría, una tabla por servicio (media,
  mínimo, máximo, diferencia con lo estimado y cuánto subió el precio en el año) y la previsión de los
  próximos 12 meses. Por año y por moneda; cada gráfico tiene su tooltip y una vista en tabla.
- **Historial**: todos los pagos, filtrables por servicio y año; *Exportar CSV* (separado por punto y coma,
  como lo abre una planilla en español) y la copia de seguridad: *Exportar copia* e *Importar copia*.

Es un único archivo JavaScript sin librerías externas: funciona sin internet y sigue el tema de Home
Assistant (claro u oscuro).

| Estadísticas | Servicios | En el teléfono |
|---|---|---|
| ![Estadísticas](https://raw.githubusercontent.com/abestard/ha-facturas/main/docs/capturas/estadisticas.png) | ![Servicios](https://raw.githubusercontent.com/abestard/ha-facturas/main/docs/capturas/servicios.png) | ![Teléfono](https://raw.githubusercontent.com/abestard/ha-facturas/main/docs/capturas/telefono.png) |

## Entidades

| Entidad | Estado | Atributos |
|---|---|---|
| `sensor.facturas_mes_previsto` | Total previsto del mes | Total por moneda, por categoría |
| `sensor.facturas_mes_pagado` | Pagado en el mes | Total por moneda, cantidad de pagos |
| `sensor.facturas_mes_falta` | Lo que falta pagar del mes | Vencido, vencidos de meses anteriores |
| `sensor.facturas_anio_pagado` | Pagado en el año | Media mensual |
| `sensor.facturas_proxima` | Fecha del próximo vencimiento de pago manual | Servicio, importe, días que faltan, `avisar` |
| `todo.facturas` | Pagos pendientes del mes (y vencidos) | Marcar un ítem como hecho registra el pago |
| `calendar.facturas` | Vencimientos, pagados y previstos | Aparece en el calendario de Home Assistant |

Los sensores de importes muestran la **moneda principal** (opción de la integración: pesos → UYU, dólares →
USD); el total de cada moneda va en los atributos `pesos` y `dolares`, sin convertir. Si algún servicio usa
la otra moneda, aparecen también `sensor.facturas_mes_previsto_dolares` (o `_pesos`) y sus compañeros. Todos
entran en la historia larga del registro de Home Assistant, así que se pueden graficar por años.

Si ya existe otra entidad `todo.facturas` (por ejemplo una lista local), la de la integración queda como
`todo.facturas_2` hasta que se borre la vieja y se renombre.

## Acciones

Todas aceptan el servicio por su id o por su nombre (`UTE`, `antel`). Las que cambian datos pueden devolver
lo que cambiaron; `facturas.resumen` y `facturas.exportar` siempre devuelven datos.

| Acción | Para qué |
|---|---|
| `facturas.agregar_servicio` | Alta: nombre, importe, categoría, moneda, forma de pago, tipo, día de vencimiento, meses, desde, `auto_pagar`, `anteriores_pagados` |
| `facturas.editar_servicio` | Cambiar los datos del servicio (no el precio) |
| `facturas.dar_de_baja` / `facturas.reactivar` | Dejar de generar pagos (el historial queda) / volver a generarlos |
| `facturas.cambiar_precio` | Precio nuevo desde un mes; lo anterior no cambia |
| `facturas.anotar_importe` | El importe real de un mes antes de pagarlo (llegó la factura) |
| `facturas.registrar_pago` | Marcar como pagado: período (por defecto el pendiente más viejo) o `hasta` un mes (varios de una vez), importe real, fecha, nota |
| `facturas.corregir_pago` | Corregir el importe real, la fecha o la nota de un pago |
| `facturas.deshacer_pago` / `facturas.omitir` | Volver a pendiente / "este mes no se paga" |
| `facturas.resumen` | El mes, el año, los pendientes, el próximo vencimiento y los servicios |
| `facturas.borrar_servicio` 🔒 | Borrar un servicio y todos sus pagos, para siempre |
| `facturas.borrar_precio` 🔒 | Quitar un precio mal cargado del historial |
| `facturas.exportar` 🔒 | Devuelve todos los datos en JSON (la copia de seguridad) |
| `facturas.importar` 🔒 | Carga una copia: `combinar` (agrega los servicios que no existen) o `reemplazar` (todo) |

🔒 Solo administradores.

Ejemplo, en Herramientas para desarrolladores → Acciones:

```yaml
action: facturas.agregar_servicio
data:
  nombre: UTE
  importe: 1500
  categoria: casa
  tipo: consumo
  dia_vence: 12
```

Los pagos de cada mes se generan solos el día 1 (y al arrancar Home Assistant, por si estuvo apagado); los
débitos automáticos con `auto_pagar` se marcan como pagados a medianoche del día del vencimiento. Los datos
quedan en `.storage/facturas` y entran en las copias de seguridad de Home Assistant; quitar la integración no
los borra.

Si algo no anda, en Ajustes → Dispositivos y servicios → Facturas → ⋮ → *Descargar diagnóstico* se baja un
archivo con el estado de la integración (sin los correos de los remitentes) para adjuntar a un *issue*.

## Requisitos

- Home Assistant **2025.11** o posterior (se prueba contra Core 2025.11.3, la última serie con 32 bits).
- Python puro, sin dependencias: funciona igual en 32 y 64 bits.

## Instalación

1. HACS → menú → *Repositorios personalizados* → `https://github.com/abestard/ha-facturas`, categoría
   *Integración*.
2. Descargar *Facturas* y reiniciar Home Assistant.
3. Ajustes → Dispositivos y servicios → Agregar integración → *Facturas*. Recién ahí aparece el panel en la
   barra lateral.

## Desarrollo

`custom_components/facturas/logica.py` tiene todo el cálculo y no importa nada de Home Assistant, así que sus
pruebas corren con cualquier Python ≥ 3.12; las del panel, con Node ≥ 22 y sin dependencias:

```bash
pip install pytest
pytest
node --test "tests/js/*.test.mjs"
```

Para probar contra la versión exacta de Home Assistant (2025.11.3, Python 3.13) se usa Docker, porque Home
Assistant no se instala en Windows:

```bash
docker build -f Dockerfile.pruebas -t ha-facturas-pruebas .
docker run --rm -v "$PWD:/repo" ha-facturas-pruebas
```

Los textos de las acciones y entidades (inglés y español) se editan en `scripts/generar_textos.py`, que
regenera `strings.json` y `translations/`:

```bash
python scripts/generar_textos.py
```

Para ver el panel en un Home Assistant 2025.11.3 de verdad, con la integración montada desde el repositorio
(la configuración de prueba va en `dev/ha-config/`, que git ignora):

```bash
docker run -d --name ha-facturas-dev -p 8123:8123 -v "$PWD/dev/ha-config:/config" -v "$PWD/custom_components/facturas:/config/custom_components/facturas:ro" ghcr.io/home-assistant/home-assistant:2025.11.3
```

Con este `dev/ha-config/configuration.yaml`, la PC entra sin contraseña (por la red de Docker):

```yaml
default_config:

homeassistant:
  time_zone: America/Montevideo
  language: es
  auth_providers:
    - type: trusted_networks
      trusted_networks: [127.0.0.1, ::1, 172.16.0.0/12, 192.168.0.0/16]
      allow_bypass_login: true
    - type: homeassistant
```

Después de cambiar el código Python, `docker restart ha-facturas-dev`; si solo cambió el panel, alcanza con
recargar el navegador.

### Publicar una versión

1. Subir `version` en `custom_components/facturas/manifest.json` (por ejemplo a `0.6.0`) y hacer commit.
2. Crear y subir el tag con la misma versión:

   ```bash
   git tag v0.6.0
   git push origin v0.6.0
   ```

El workflow *Release* comprueba que el tag coincide con el manifiesto, corre las pruebas y publica el
release en GitHub; HACS lo ve y avisa en Home Assistant.

## Licencia

[MIT](LICENSE)
