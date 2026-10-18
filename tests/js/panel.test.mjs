// Pruebas de las funciones puras del panel. Sin dependencias: node --test "tests/js/*.test.mjs"
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  compacto,
  csvHistorial,
  dinero,
  escala,
  esc,
  graficoColumnas,
  limpiarDatos,
  mesesAtajo,
  nombreMes,
  sumarMeses,
} from "../../custom_components/facturas/panel/facturas-panel.js";

const marcar = (...meses) => Array.from({ length: 12 }, (_, i) => meses.includes(i + 1));
const marcados = (lista) => lista.flatMap((v, i) => (v ? [i + 1] : []));

describe("formatos", () => {
  it("escapa HTML", () => {
    assert.equal(esc(`<b>"Tom" & 'Jerry'</b>`), "&lt;b&gt;&quot;Tom&quot; &amp; &#39;Jerry&#39;&lt;/b&gt;");
    assert.equal(esc(null), "");
  });

  it("importes en pesos y dólares", () => {
    assert.equal(dinero(1650, "pesos"), "$ 1.650");
    assert.equal(dinero(12.99, "dolares"), "US$ 12,99");
    assert.equal(dinero(null, "pesos"), "$ 0");
  });

  it("nombres de mes y suma de meses", () => {
    assert.equal(nombreMes("2026-03"), "marzo 2026");
    assert.equal(sumarMeses("2026-12", 1), "2027-01");
    assert.equal(sumarMeses("2026-01", -1), "2025-12");
  });

  it("marcas compactas del eje", () => {
    assert.equal(compacto(0), "0");
    assert.equal(compacto(500), "500");
    assert.equal(compacto(5000), "5 mil");
    assert.equal(compacto(12500), "12,5 mil");
    assert.equal(compacto(1200000), "1,2 M");
  });
});

describe("atajos de meses", () => {
  it("sin nada marcado empieza en enero", () => {
    assert.deepEqual(marcados(mesesAtajo(marcar(), "cada2")), [1, 3, 5, 7, 9, 11]);
  });

  it("empieza en el primer mes marcado", () => {
    assert.deepEqual(marcados(mesesAtajo(marcar(2, 7), "cada2")), [2, 4, 6, 8, 10, 12]);
    assert.deepEqual(marcados(mesesAtajo(marcar(3), "cada3")), [3, 6, 9, 12]);
    assert.deepEqual(marcados(mesesAtajo(marcar(9, 10), "anual")), [9]);
    assert.equal(marcados(mesesAtajo(marcar(5), "mensual")).length, 12);
  });
});

describe("limpiarDatos", () => {
  it("saca vacíos pero deja la nota vacía y los falsos", () => {
    assert.deepEqual(
      limpiarDatos({ servicio: "ute", periodo: undefined, importe: undefined, nota: "", categoria: "", auto_pagar: false }),
      { servicio: "ute", nota: "", auto_pagar: false },
    );
  });
});

describe("csvHistorial", () => {
  it("usa punto y coma, coma decimal y BOM, y escapa lo necesario", () => {
    const csv = csvHistorial([
      { periodo: "2026-10", nombre: "UTE", servicio_id: "ute", moneda: "pesos", vence: "2026-10-12",
        estimado: 1650, real: 1490.5, estado: "pagado", pagado_el: "2026-10-10", origen: "manual",
        nota: 'dijo "descuento"; ok' },
      { periodo: "2026-10", nombre: "Netflix", servicio_id: "netflix", moneda: "dolares", vence: "2026-10-20",
        estimado: 12.99, real: null, estado: "pendiente", pagado_el: null, origen: null, nota: "" },
    ], { ute: "casa" });
    assert.ok(csv.startsWith("﻿periodo;servicio;categoria;"));
    const [, primera, segunda] = csv.slice(1).split("\r\n");
    assert.equal(primera, '2026-10;UTE;casa;pesos;2026-10-12;1650;1490,5;pagado;2026-10-10;manual;"dijo ""descuento""; ok"');
    assert.equal(segunda, "2026-10;Netflix;;dolares;2026-10-20;12,99;;pendiente;;;");
  });
});

describe("gráficos", () => {
  it("escala con tope redondo", () => {
    assert.deepEqual(escala(0), { tope: 1, marcas: [0] });
    assert.deepEqual(escala(14920), { tope: 15000, marcas: [0, 5000, 10000, 15000] });
    assert.deepEqual(escala(870), { tope: 1000, marcas: [0, 250, 500, 750, 1000] });
  });

  it("columnas: una zona de toque por grupo, barras de hasta 24px y sin barras en cero", () => {
    const svg = graficoColumnas({
      ancho: 600,
      colores: ["--a", "--b"],
      grupos: [
        { etiqueta: "sep", valores: [100, 80], tip: "septiembre" },
        { etiqueta: "oct", valores: [0, 0], tip: "octubre <vacío>" },
      ],
    });
    assert.equal((svg.match(/class="zona"/g) || []).length, 2);
    assert.equal((svg.match(/<path /g) || []).length, 2); // octubre en cero no dibuja barras
    assert.match(svg, /data-tip="octubre &lt;vacío&gt;"/);
    const anchos = [...svg.matchAll(/H([\d.]+)\s/g)];
    assert.ok(anchos.length > 0);
    assert.match(svg, /viewBox="0 0 600 220"/);
  });
});
