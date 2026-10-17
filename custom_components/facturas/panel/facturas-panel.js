// Panel "Facturas" para Home Assistant.
//
// Un único archivo sin compilar ni librerías externas (funciona sin internet). Lee con los
// comandos WebSocket facturas/datos y facturas/suscribir, y escribe con las acciones facturas.*.
// Solo usa variables de tema de HA, así que sigue el tema claro u oscuro.

const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
  "septiembre", "octubre", "noviembre", "diciembre"];
const MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const MONEDAS = { pesos: "$", dolares: "US$" };
const ESTADOS = { pendiente: "Pendiente", pagado: "Pagado", omitido: "Omitido" };
const NUMERO = new Intl.NumberFormat("es-UY", { maximumFractionDigits: 2 });

const esc = (valor) => String(valor ?? "").replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[c]));
const dinero = (importe, moneda) => `${MONEDAS[moneda] || "$"} ${NUMERO.format(importe ?? 0)}`;
const nombreMes = (periodo) => {
  const [anio, mes] = periodo.split("-").map(Number);
  return `${MESES[mes - 1]} ${anio}`;
};
const fechaCorta = (iso) => {
  if (!iso) return "";
  const [anio, mes, dia] = iso.split("-").map(Number);
  return `${dia} ${MESES_CORTOS[mes - 1]}${anio === new Date().getFullYear() ? "" : ` ${anio}`}`;
};
const sumarMeses = (periodo, n) => {
  const [anio, mes] = periodo.split("-").map(Number);
  const total = anio * 12 + (mes - 1) + n;
  return `${Math.floor(total / 12)}-${String((total % 12) + 1).padStart(2, "0")}`;
};
const totales = (porMoneda, principal) => {
  // La moneda principal siempre; la otra solo si tiene algo.
  const orden = [principal, ...Object.keys(MONEDAS).filter((m) => m !== principal)];
  return orden.filter((m, i) => i === 0 || porMoneda[m])
    .map((m) => `<div class="total">${dinero(porMoneda[m], m)}</div>`).join("");
};

const ESTILOS = `
  :host { display: block; min-height: 100vh; background: var(--primary-background-color);
    color: var(--primary-text-color); font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif); }
  * { box-sizing: border-box; }
  header { position: sticky; top: 0; z-index: 2; display: flex; align-items: center; gap: 4px;
    height: var(--header-height, 56px); padding: 0 12px;
    background: var(--app-header-background-color, var(--primary-color));
    color: var(--app-header-text-color, var(--text-primary-color, #fff));
    border-bottom: var(--app-header-border-bottom, none); }
  header h1 { flex: 1; margin: 0 0 0 8px; font-size: 20px; font-weight: 400; }
  .icono { background: none; border: none; color: inherit; width: 40px; height: 40px; border-radius: 50%;
    cursor: pointer; display: inline-flex; align-items: center; justify-content: center; padding: 0; }
  .icono:hover { background: rgba(127, 127, 127, .15); }
  .icono svg { width: 24px; height: 24px; fill: currentColor; }
  nav { display: flex; gap: 4px; padding: 0 12px; background: var(--app-header-background-color, var(--primary-color));
    color: var(--app-header-text-color, #fff); overflow-x: auto; }
  nav button { background: none; border: none; color: inherit; opacity: .75; padding: 12px 14px; font: inherit;
    font-size: 14px; text-transform: uppercase; letter-spacing: .05em; cursor: pointer;
    border-bottom: 2px solid transparent; white-space: nowrap; }
  nav button.activa { opacity: 1; border-bottom-color: currentColor; }
  main { max-width: 1000px; margin: 0 auto; padding: 16px; }
  .tarjeta { background: var(--card-background-color, #fff); border-radius: var(--ha-card-border-radius, 12px);
    border: 1px solid var(--divider-color); box-shadow: var(--ha-card-box-shadow, none); margin-bottom: 16px; }
  .tarjeta > h2 { margin: 0; padding: 16px 16px 8px; font-size: 18px; font-weight: 500; }
  .resumen { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px; }
  .resumen .tarjeta { margin: 0; padding: 12px 16px; }
  .etiqueta { color: var(--secondary-text-color); font-size: 13px; }
  .total { font-size: 22px; font-weight: 500; margin-top: 2px; }
  .resumen .falta .total:first-of-type { color: var(--warning-color, #ff9800); }
  .barra-mes { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; gap: 8px; }
  .barra-mes h2 { margin: 0; font-size: 20px; font-weight: 400; text-transform: capitalize; }
  .fila { display: flex; align-items: center; gap: 12px; padding: 12px 16px; border-top: 1px solid var(--divider-color);
    flex-wrap: wrap; }
  .fila:first-of-type { border-top: none; }
  .fila .info { flex: 1 1 200px; min-width: 0; }
  .fila .nombre { font-weight: 500; }
  .fila .detalle { color: var(--secondary-text-color); font-size: 13px; margin-top: 2px; }
  .fila .importe { text-align: right; min-width: 110px; }
  .fila .importe .principal { font-weight: 500; }
  .fila .importe .secundario { color: var(--secondary-text-color); font-size: 12px; }
  .acciones { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
  .chip { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: 500;
    background: rgba(127, 127, 127, .15); }
  .chip.pagado { background: rgba(76, 175, 80, .18); color: var(--success-color, #43a047); }
  .chip.pendiente { background: rgba(255, 152, 0, .18); color: var(--warning-color, #ef6c00); }
  .chip.vencido { background: rgba(219, 68, 55, .18); color: var(--error-color, #db4437); }
  .chip.inactivo { opacity: .7; }
  .vencidos { border-color: var(--error-color, #db4437); }
  .vencidos > h2 { color: var(--error-color, #db4437); }
  button.boton { font: inherit; font-size: 14px; font-weight: 500; padding: 7px 14px; border-radius: 18px; cursor: pointer;
    border: 1px solid var(--divider-color); background: none; color: var(--primary-color); }
  button.boton:hover { background: rgba(127, 127, 127, .1); }
  button.boton.lleno { background: var(--primary-color); color: var(--text-primary-color, #fff); border-color: transparent; }
  button.boton.peligro { color: var(--error-color, #db4437); }
  button.boton:disabled { opacity: .5; cursor: default; }
  .vacio { padding: 24px 16px; color: var(--secondary-text-color); text-align: center; }
  .error { margin-bottom: 16px; padding: 12px 16px; border-radius: 8px; color: var(--error-color, #db4437);
    background: rgba(219, 68, 55, .12); }
  .cabecera-lista { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 12px 16px 4px; }
  .cabecera-lista h2 { margin: 0; font-size: 18px; font-weight: 500; }
  .filtros { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; padding: 12px 16px; }
  .tabla { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { padding: 8px 12px; text-align: left; border-top: 1px solid var(--divider-color); white-space: nowrap; }
  th { color: var(--secondary-text-color); font-weight: 500; font-size: 12px; border-top: none; }
  td.num, th.num { text-align: right; }
  select, input, textarea { font: inherit; font-size: 15px; color: var(--primary-text-color);
    background: var(--input-fill-color, var(--secondary-background-color, transparent));
    border: 1px solid var(--divider-color); border-radius: 6px; padding: 8px 10px; max-width: 100%; }
  dialog { border: none; border-radius: var(--ha-dialog-border-radius, 16px); padding: 0; width: min(520px, calc(100vw - 32px));
    max-height: calc(100vh - 32px); background: var(--card-background-color, #fff); color: var(--primary-text-color);
    box-shadow: 0 8px 32px rgba(0, 0, 0, .35); }
  dialog::backdrop { background: rgba(0, 0, 0, .45); }
  dialog form { display: flex; flex-direction: column; max-height: calc(100vh - 32px); }
  dialog h2 { margin: 0; padding: 20px 24px 8px; font-size: 20px; font-weight: 400; }
  .cuerpo { padding: 8px 24px; overflow-y: auto; display: flex; flex-direction: column; gap: 14px; }
  .campo { display: flex; flex-direction: column; gap: 4px; }
  .campo > span { font-size: 13px; color: var(--secondary-text-color); }
  .campos { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .meses { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px 8px; }
  .meses label { display: flex; align-items: center; gap: 6px; font-size: 14px; text-transform: capitalize; }
  .meses input { width: 18px; height: 18px; padding: 0; }
  .atajos { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
  .pie { display: flex; justify-content: flex-end; gap: 8px; padding: 12px 24px 20px; }
  .ayuda { font-size: 13px; color: var(--secondary-text-color); margin: 0; }
  /* Estadísticas. Serie 1 (azul) = pagado, serie 2 (naranja) = previsto: paleta de referencia validada
     (claro y oscuro) para visión normal y daltonismo. */
  :host { --serie-pagado: #2a78d6; --serie-previsto: #eb6834; }
  :host([oscuro]) { --serie-pagado: #3987e5; --serie-previsto: #d95926; }
  .tarjeta .contenido { padding: 0 16px 16px; }
  .cifras { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px; }
  .cifras .tarjeta { margin: 0; padding: 12px 16px; }
  .cifras .nota { color: var(--secondary-text-color); font-size: 12px; margin-top: 2px; }
  .leyenda { display: flex; gap: 16px; flex-wrap: wrap; font-size: 13px; color: var(--secondary-text-color);
    padding: 0 16px 8px; }
  .leyenda span::before { content: ""; display: inline-block; width: 10px; height: 10px; border-radius: 2px;
    margin-right: 6px; vertical-align: -1px; background: var(--color); }
  svg.grafico { display: block; overflow: visible; }
  svg.grafico text { fill: var(--secondary-text-color); font-size: 11px; }
  svg.grafico .grilla { stroke: var(--divider-color); stroke-width: 1; }
  svg.grafico .base { stroke: var(--secondary-text-color); stroke-width: 1; opacity: .6; }
  svg.grafico .zona { fill: transparent; }
  svg.grafico .zona:hover { fill: rgba(127, 127, 127, .08); }
  .barras { display: flex; flex-direction: column; gap: 10px; }
  .barras .fila-barra { display: grid; grid-template-columns: minmax(80px, 30%) 1fr auto; gap: 10px;
    align-items: center; font-size: 14px; }
  .barras .barra { height: 14px; border-radius: 0 4px 4px 0; background: var(--serie-pagado); min-width: 2px; }
  .barras .valor { color: var(--primary-text-color); font-variant-numeric: tabular-nums; }
  details.tabla-alt summary { cursor: pointer; color: var(--primary-color); font-size: 13px; padding: 8px 0 0; }
  td.sube { color: var(--error-color, #db4437); }
  td.baja { color: var(--success-color, #43a047); }
  #tip { position: fixed; z-index: 10; pointer-events: none; padding: 8px 10px; border-radius: 8px; font-size: 13px;
    background: var(--card-background-color, #fff); color: var(--primary-text-color); white-space: pre;
    border: 1px solid var(--divider-color); box-shadow: 0 4px 16px rgba(0, 0, 0, .25); }
  @media (max-width: 600px) {
    .cifras { grid-template-columns: 1fr; gap: 8px; }
    main { padding: 12px; }
    .resumen { grid-template-columns: 1fr; gap: 8px; }
    .resumen .tarjeta { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
    .total { font-size: 18px; text-align: right; }
    .campos { grid-template-columns: 1fr; }
    .meses { grid-template-columns: repeat(3, 1fr); }
    .fila .importe { min-width: 0; }
  }
`;

const ICONOS = {
  menu: "M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z",
  anterior: "M15.41,16.58L10.83,12L15.41,7.41L14,6L8,12L14,18L15.41,16.58Z",
  siguiente: "M8.59,16.58L13.17,12L8.59,7.41L10,6L16,12L10,18L8.59,16.58Z",
};
const icono = (nombre) => `<svg viewBox="0 0 24 24"><path d="${ICONOS[nombre]}"/></svg>`;

// ------------------------------------------------------------------ gráficos (SVG hecho a mano)

// Marcas del eje: "5 mil", "1,2 M" (el formato compacto del navegador mezcla "K" y "k" en español).
const compacto = (v) => (v >= 1e6 ? `${NUMERO.format(v / 1e6)} M` : v >= 1e3 ? `${NUMERO.format(v / 1e3)} mil` : NUMERO.format(v));

// Tope "redondo" del eje y sus marcas (0, paso, 2·paso…).
function escala(maximo) {
  if (!(maximo > 0)) return { tope: 1, marcas: [0] };
  const bruto = maximo / 4;
  const magnitud = 10 ** Math.floor(Math.log10(bruto));
  const paso = [1, 2, 2.5, 5, 10].map((f) => f * magnitud).find((p) => p >= bruto);
  const tope = Math.ceil(maximo / paso) * paso;
  const marcas = [];
  for (let v = 0; v <= tope + paso / 2; v += paso) marcas.push(v);
  return { tope, marcas };
}

// Columna con el extremo de datos redondeado (4px) y la base recta.
function columna(x, y, ancho, alto, color) {
  if (alto <= 0) return "";
  const r = Math.min(4, ancho / 2, alto);
  const base = y + alto;
  return `<path fill="${color}" d="M${x},${base} V${y + r} Q${x},${y} ${x + r},${y} H${x + ancho - r}
    Q${x + ancho},${y} ${x + ancho},${y + r} V${base} Z"/>`;
}

// Columnas agrupadas: grupos = [{etiqueta, valores: [..], tip}], colores = una variable CSS por serie.
function graficoColumnas({ ancho, alto = 220, grupos, colores }) {
  const izq = 40;
  const der = 4;
  const arriba = 10;
  const abajo = 24;
  const anchoUtil = Math.max(ancho - izq - der, 10);
  const altoUtil = alto - arriba - abajo;
  const { tope, marcas } = escala(Math.max(0, ...grupos.flatMap((g) => g.valores)));
  const banda = anchoUtil / grupos.length;
  const k = colores.length;
  const separacion = 2;
  const barra = Math.max(2, Math.min(24, (banda * 0.7 - separacion * (k - 1)) / k));
  const cadaCuanto = banda >= 34 ? 1 : banda >= 17 ? 2 : 3;
  const y = (v) => arriba + altoUtil - (v / tope) * altoUtil;
  let svg = marcas.map((v) => `
    <line class="${v === 0 ? "base" : "grilla"}" x1="${izq}" x2="${ancho - der}" y1="${y(v)}" y2="${y(v)}"/>
    <text x="${izq - 6}" y="${y(v) + 4}" text-anchor="end">${compacto(v)}</text>`).join("");
  grupos.forEach((g, i) => {
    const centro = izq + banda * i + banda / 2;
    const inicio = centro - (barra * k + separacion * (k - 1)) / 2;
    g.valores.forEach((v, j) => {
      svg += columna(inicio + j * (barra + separacion), y(v), barra, y(0) - y(v), `var(${colores[j]})`);
    });
    if (i % cadaCuanto === 0) {
      svg += `<text x="${centro}" y="${alto - 6}" text-anchor="middle">${esc(g.etiqueta)}</text>`;
    }
    // Zona de toque más grande que la marca: toda la banda.
    svg += `<rect class="zona" x="${izq + banda * i}" y="${arriba}" width="${banda}" height="${altoUtil}"
      data-tip="${esc(g.tip)}"/>`;
  });
  return `<svg class="grafico" viewBox="0 0 ${ancho} ${alto}" width="${ancho}" height="${alto}" role="img">${svg}</svg>`;
}

class FacturasPanel extends HTMLElement {
  constructor() {
    super();
    this._pestana = "mes";
    this._periodo = null;
    this._datos = null;
    this._error = null;
    this._filtro = { servicio: "", anio: "" };
    this._dialogo = null;
    this._estadisticas = null;
    this._anio = null;
    this._moneda = null;
  }

  set hass(hass) {
    const primero = !this._hass;
    this._hass = hass;
    this.toggleAttribute("oscuro", Boolean(hass.themes?.darkMode));
    if (primero) this._iniciar();
  }

  get hass() {
    return this._hass;
  }

  set narrow(valor) {
    this._narrow = valor;
    if (this.shadowRoot) this._dibujar();
  }

  set panel(_valor) {}

  connectedCallback() {
    if (this._hass && !this._desuscribir) this._suscribir();
  }

  disconnectedCallback() {
    this._cancelarSuscripcion();
  }

  async _iniciar() {
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      this.shadowRoot.innerHTML = `<style>${ESTILOS}</style><div id="contenido"></div><dialog id="dialogo"></dialog>
        <div id="tip" hidden></div>`;
      this.shadowRoot.addEventListener("click", (e) => this._click(e));
      this.shadowRoot.addEventListener("pointermove", (e) => this._tip(e));
      this.shadowRoot.addEventListener("pointerdown", (e) => this._tip(e));
      this.shadowRoot.addEventListener("pointerout", (e) => {
        if (e.target.dataset?.tip !== undefined) this.shadowRoot.getElementById("tip").hidden = true;
      });
      // Los gráficos se dibujan al ancho real: si cambia mucho (girar el teléfono), se redibujan.
      new ResizeObserver(() => {
        const ancho = this.clientWidth;
        if (this._pestana === "estadisticas" && Math.abs(ancho - (this._anchoDibujado || 0)) > 24) this._dibujar();
      }).observe(this);
      this.shadowRoot.addEventListener("change", (e) => this._cambio(e));
      const dialogo = this.shadowRoot.getElementById("dialogo");
      dialogo.addEventListener("submit", (e) => this._enviar(e));
      dialogo.addEventListener("close", () => { this._dialogo = null; });
    }
    this._dibujar();
    await this._cargar();
    this._suscribir();
  }

  async _suscribir() {
    if (this._desuscribir || !this._hass) return;
    try {
      this._desuscribir = await this._hass.connection.subscribeMessage(
        () => this._cargar(), { type: "facturas/suscribir" });
    } catch (err) {
      this._mostrarError(err);
    }
  }

  _cancelarSuscripcion() {
    if (this._desuscribir) {
      const desuscribir = this._desuscribir;
      this._desuscribir = null;
      Promise.resolve(desuscribir).then((f) => f && f()).catch(() => {});
    }
  }

  async _cargar() {
    // Si llegan varios avisos juntos, una sola carga.
    if (this._cargando) {
      this._otraCarga = true;
      return;
    }
    this._cargando = true;
    try {
      const pedido = { type: "facturas/datos" };
      if (this._periodo) pedido.periodo = this._periodo;
      this._datos = await this._hass.callWS(pedido);
      this._periodo = this._datos.mes.periodo;
      this._error = null;
      if (this._pestana === "estadisticas") await this._cargarEstadisticas(false);
      else this._estadisticas = null; // se piden de nuevo al abrir la pestaña
    } catch (err) {
      this._error = err.message || String(err);
    } finally {
      this._cargando = false;
    }
    this._dibujar();
    if (this._otraCarga) {
      this._otraCarga = false;
      this._cargar();
    }
  }

  async _cargarEstadisticas(dibujar = true) {
    try {
      const pedido = { type: "facturas/estadisticas" };
      if (this._anio) pedido.anio = Number(this._anio);
      this._estadisticas = await this._hass.callWS(pedido);
    } catch (err) {
      this._error = err.message || String(err);
    }
    if (dibujar) this._dibujar();
  }

  _tip(evento) {
    const tip = this.shadowRoot.getElementById("tip");
    const texto = evento.target.dataset?.tip;
    if (texto === undefined) {
      if (evento.type === "pointerdown") tip.hidden = true;
      return;
    }
    tip.textContent = texto;
    tip.hidden = false;
    const x = Math.min(evento.clientX + 12, window.innerWidth - tip.offsetWidth - 8);
    const y = evento.clientY - tip.offsetHeight - 12;
    tip.style.left = `${Math.max(8, x)}px`;
    tip.style.top = `${y < 8 ? evento.clientY + 16 : y}px`;
  }

  _mostrarError(err) {
    this._error = err?.message || String(err);
    this._dibujar();
  }

  // ---------------------------------------------------------------- dibujo

  _dibujar() {
    const contenido = this.shadowRoot?.getElementById("contenido");
    if (!contenido) return;
    const pestanas = [["mes", "Este mes"], ["servicios", "Servicios"], ["estadisticas", "Estadísticas"],
      ["historial", "Historial"]];
    let cuerpo;
    if (!this._datos) {
      cuerpo = this._error ? "" : `<div class="vacio">Cargando…</div>`;
    } else if (this._pestana === "servicios") {
      cuerpo = this._dibujarServicios();
    } else if (this._pestana === "historial") {
      cuerpo = this._dibujarHistorial();
    } else if (this._pestana === "estadisticas") {
      cuerpo = this._dibujarEstadisticas();
    } else {
      cuerpo = this._dibujarMes();
    }
    contenido.innerHTML = `
      <header>
        ${this._narrow ? `<button class="icono" data-accion="menu" title="Menú" aria-label="Menú">${icono("menu")}</button>` : ""}
        <h1>Facturas</h1>
      </header>
      <nav>${pestanas.map(([clave, texto]) =>
        `<button data-pestana="${clave}" class="${this._pestana === clave ? "activa" : ""}">${texto}</button>`).join("")}
      </nav>
      <main>
        ${this._error ? `<div class="error">${esc(this._error)}</div>` : ""}
        ${cuerpo}
      </main>`;
  }

  _dibujarMes() {
    const d = this._datos;
    const mes = d.mes;
    const principal = d.moneda_principal;
    const esActual = mes.periodo === d.hoy.slice(0, 7);
    const vencidos = mes.pagos_vencidos_anteriores;
    const pagos = mes.pagos;
    return `
      <div class="barra-mes">
        <button class="icono" data-accion="mes-anterior" title="Mes anterior" aria-label="Mes anterior">${icono("anterior")}</button>
        <h2>${nombreMes(mes.periodo)}</h2>
        <div>
          ${esActual ? "" : `<button class="boton" data-accion="mes-actual">Hoy</button>`}
          <button class="icono" data-accion="mes-siguiente" title="Mes siguiente" aria-label="Mes siguiente">${icono("siguiente")}</button>
        </div>
      </div>
      <div class="resumen">
        <div class="tarjeta"><div class="etiqueta">Previsto</div><div>${totales(mes.previsto, principal)}</div></div>
        <div class="tarjeta"><div class="etiqueta">Pagado</div><div>${totales(mes.pagado, principal)}</div></div>
        <div class="tarjeta falta"><div class="etiqueta">Falta${
          Object.values(mes.vencido).some(Boolean) ? ` (vencido ${dinero(mes.vencido[principal], principal)})` : ""
        }</div><div>${totales(mes.falta, principal)}</div></div>
      </div>
      ${vencidos.length ? `
        <div class="tarjeta vencidos">
          <h2>Vencidos de meses anteriores</h2>
          ${vencidos.map((p) => this._filaPago(p, true)).join("")}
        </div>` : ""}
      <div class="tarjeta">
        ${pagos.length ? pagos.map((p) => this._filaPago(p, false)).join("")
          : `<div class="vacio">No hay pagos este mes.${d.servicios.length ? "" : " Empezá agregando un servicio."}</div>`}
      </div>
      ${d.servicios.length ? "" : `<button class="boton lleno" data-accion="servicio-nuevo">Agregar servicio</button>`}`;
  }

  _filaPago(p, conMes) {
    const hoy = this._datos.hoy;
    const debito = p.forma_pago === "debito";
    const vencido = p.estado === "pendiente" && p.vence < hoy;
    // Un débito automático se paga solo: pasada la fecha no es una alarma, falta confirmarlo.
    const chip = vencido && debito ? `<span class="chip pendiente">Débito</span>`
      : vencido ? `<span class="chip vencido">Vencido</span>`
        : `<span class="chip ${p.estado}">${ESTADOS[p.estado]}</span>`;
    const clave = `data-servicio="${esc(p.servicio_id)}" data-periodo="${esc(p.periodo)}"`;
    let acciones;
    if (p.estado === "pendiente") {
      acciones = `
        <button class="boton lleno" data-accion="pagar" ${clave}>Pagado</button>
        <button class="boton" data-accion="anotar" ${clave}>Importe</button>
        <button class="boton" data-accion="omitir" ${clave}>Omitir</button>`;
    } else if (p.estado === "pagado") {
      acciones = `
        <button class="boton" data-accion="corregir" ${clave}>Corregir</button>
        <button class="boton" data-accion="deshacer" ${clave}>Deshacer</button>`;
    } else {
      acciones = `<button class="boton" data-accion="deshacer" ${clave}>Deshacer</button>`;
    }
    const detalle = [
      conMes ? nombreMes(p.periodo) : null,
      `vence ${fechaCorta(p.vence)}`,
      debito ? "débito automático" : null,
      p.estado === "pagado" && p.pagado_el ? `pagado el ${fechaCorta(p.pagado_el)}` : null,
      p.nota ? esc(p.nota) : null,
    ].filter(Boolean).join(" · ");
    const secundario = p.real !== null && p.real !== p.estimado
      ? `<div class="secundario">estimado ${dinero(p.estimado, p.moneda)}</div>`
      : p.real === null && p.estado === "pendiente" ? `<div class="secundario">estimado</div>` : "";
    return `
      <div class="fila">
        <div class="info">
          <div class="nombre">${esc(p.nombre)} ${chip}</div>
          <div class="detalle">${detalle}</div>
        </div>
        <div class="importe"><div class="principal">${dinero(p.importe, p.moneda)}</div>${secundario}</div>
        <div class="acciones">${acciones}</div>
      </div>`;
  }

  _dibujarServicios() {
    const servicios = this._datos.servicios;
    return `
      <div class="tarjeta">
        <div class="cabecera-lista">
          <h2>${servicios.length} ${servicios.length === 1 ? "servicio" : "servicios"}</h2>
          <button class="boton lleno" data-accion="servicio-nuevo">Agregar</button>
        </div>
        ${servicios.length ? servicios.map((s) => this._filaServicio(s)).join("")
          : `<div class="vacio">Todavía no hay servicios.</div>`}
      </div>`;
  }

  _filaServicio(s) {
    const clave = `data-servicio="${esc(s.id)}"`;
    const precios = s.historial_precios;
    const ultimo = precios[precios.length - 1];
    const subida = precios.length > 1 && ultimo.variacion !== null
      ? ` · ${ultimo.variacion > 0 ? "+" : ""}${NUMERO.format(ultimo.variacion)} % desde ${nombreMes(ultimo.desde)}` : "";
    const detalle = [
      esc(s.categoria),
      s.periodicidad,
      `vence el ${s.dia_vence}`,
      s.pago === "debito" ? "débito automático" : "pago manual",
      s.tipo === "consumo" ? "por consumo" : null,
    ].filter(Boolean).join(" · ");
    return `
      <div class="fila">
        <div class="info">
          <div class="nombre">${esc(s.nombre)} ${s.activo ? "" : `<span class="chip inactivo">De baja</span>`}</div>
          <div class="detalle">${detalle}${subida}</div>
        </div>
        <div class="importe"><div class="principal">${dinero(s.precio_actual, s.moneda)}</div></div>
        <div class="acciones">
          <button class="boton" data-accion="servicio-editar" ${clave}>Editar</button>
          ${s.activo ? `
            <button class="boton" data-accion="precio" ${clave}>Cambió el precio</button>
            <button class="boton peligro" data-accion="baja" ${clave}>Dar de baja</button>`
            : `<button class="boton" data-accion="reactivar" ${clave}>Reactivar</button>`}
        </div>
      </div>`;
  }

  _dibujarEstadisticas() {
    const e = this._estadisticas;
    if (!e) return `<div class="vacio">Cargando…</div>`;
    const anio = e.anio;
    // Las monedas que aparecen en algún lado; la principal primero.
    const usadas = Object.keys(MONEDAS).filter((m) => m === e.moneda_principal
      || e.ultimos_meses.some((x) => x.previsto[m] || x.pagado[m]) || e.prevision.some((x) => x.total[m])
      || anio.pagado[m]).sort((a, b) => (b === e.moneda_principal) - (a === e.moneda_principal));
    const moneda = usadas.includes(this._moneda) ? this._moneda : e.moneda_principal;
    const plata = (v) => dinero(v, moneda);
    // Ancho útil: el del panel menos los márgenes de la página y de la tarjeta.
    const anchoPanel = this.clientWidth || 640;
    const ancho = Math.min(anchoPanel - (anchoPanel <= 600 ? 24 : 32), 1000 - 32) - 32;
    this._anchoDibujado = anchoPanel;
    const etiquetaMes = (periodo) => MESES_CORTOS[Number(periodo.slice(5)) - 1];

    const ultimos = graficoColumnas({
      ancho,
      colores: ["--serie-previsto", "--serie-pagado"],
      grupos: e.ultimos_meses.map((m) => ({
        etiqueta: etiquetaMes(m.periodo),
        valores: [m.previsto[moneda], m.pagado[moneda]],
        tip: `${nombreMes(m.periodo)}\nPrevisto: ${plata(m.previsto[moneda])}\nPagado: ${plata(m.pagado[moneda])}`,
      })),
    });
    const prevision = graficoColumnas({
      ancho,
      alto: 180,
      colores: ["--serie-previsto"],
      grupos: e.prevision.map((m) => ({
        etiqueta: etiquetaMes(m.periodo),
        valores: [m.total[moneda]],
        tip: `${nombreMes(m.periodo)}\nPrevisto: ${plata(m.total[moneda])}`,
      })),
    });
    const totalPrevision = e.prevision.reduce((suma, m) => suma + m.total[moneda], 0);

    const categorias = Object.entries(anio.por_categoria)
      .map(([nombre, t]) => [nombre, t[moneda]]).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
    const maxCategoria = Math.max(1, ...categorias.map(([, v]) => v));
    const servicios = Object.values(anio.por_servicio).filter((s) => s.moneda === moneda)
      .sort((a, b) => b.total - a.total);
    const ahorro = anio.ahorro[moneda];
    const opcion = (valor, texto, actual) =>
      `<option value="${esc(valor)}" ${String(valor) === String(actual) ? "selected" : ""}>${esc(texto)}</option>`;
    const signo = (v) => (v > 0 ? "+" : "") + NUMERO.format(v);

    return `
      <div class="filtros" style="padding: 0 0 12px">
        <select data-estadistica="anio" aria-label="Año">
          ${e.anios.map((a) => opcion(a, a, anio.anio)).join("")}</select>
        ${usadas.length > 1 ? `<select data-estadistica="moneda" aria-label="Moneda">
          ${usadas.map((m) => opcion(m, m === "pesos" ? "Pesos" : "Dólares", moneda)).join("")}</select>` : ""}
      </div>
      <div class="cifras">
        <div class="tarjeta"><div class="etiqueta">Pagado en ${anio.anio}</div>
          <div class="total">${plata(anio.pagado[moneda])}</div></div>
        <div class="tarjeta"><div class="etiqueta">Media mensual</div>
          <div class="total">${plata(anio.media_mensual[moneda])}</div>
          <div class="nota">${anio.meses_transcurridos} ${anio.meses_transcurridos === 1 ? "mes" : "meses"}</div></div>
        <div class="tarjeta"><div class="etiqueta">${ahorro >= 0 ? "Ahorrado" : "Gastado de más"} contra lo estimado</div>
          <div class="total">${plata(Math.abs(ahorro))}</div>
          <div class="nota">en los pagos registrados del año</div></div>
      </div>
      <div class="tarjeta">
        <h2>Últimos 12 meses</h2>
        <div class="leyenda"><span style="--color: var(--serie-previsto)">Previsto</span>
          <span style="--color: var(--serie-pagado)">Pagado</span></div>
        <div class="contenido">${ultimos}
          <details class="tabla-alt"><summary>Ver como tabla</summary><div class="tabla"><table>
            <thead><tr><th>Mes</th><th class="num">Previsto</th><th class="num">Pagado</th></tr></thead>
            <tbody>${e.ultimos_meses.map((m) => `<tr><td>${nombreMes(m.periodo)}</td>
              <td class="num">${plata(m.previsto[moneda])}</td><td class="num">${plata(m.pagado[moneda])}</td></tr>`).join("")}
            </tbody></table></div></details>
        </div>
      </div>
      <div class="tarjeta">
        <h2>Por categoría (${anio.anio})</h2>
        <div class="contenido">${categorias.length ? `<div class="barras">${categorias.map(([nombre, v]) => `
          <div class="fila-barra"><span>${esc(nombre)}</span>
            <div><div class="barra" style="width: ${(v / maxCategoria) * 100}%"
              data-tip="${esc(`${nombre}: ${plata(v)}`)}"></div></div>
            <span class="valor">${plata(v)}</span></div>`).join("")}</div>`
          : `<div class="vacio">No hay pagos registrados en ${anio.anio}.</div>`}
        </div>
      </div>
      <div class="tarjeta">
        <h2>Por servicio (${anio.anio})</h2>
        ${servicios.length ? `<div class="tabla"><table>
          <thead><tr><th>Servicio</th><th class="num">Total</th><th class="num">Media</th><th class="num">Mínimo</th>
            <th class="num">Máximo</th><th class="num">Contra estimado</th><th class="num">Precio en el año</th></tr></thead>
          <tbody>${servicios.map((s) => {
            const subida = s.subida_precio?.porcentaje;
            return `<tr><td>${esc(s.nombre)}</td><td class="num">${plata(s.total)}</td>
              <td class="num">${plata(s.media)}</td><td class="num">${plata(s.minimo)}</td>
              <td class="num">${plata(s.maximo)}</td>
              <td class="num ${s.diferencia_estimado > 0 ? "baja" : s.diferencia_estimado < 0 ? "sube" : ""}">${
                s.diferencia_estimado ? signo(-s.diferencia_estimado) : "="}</td>
              <td class="num ${subida > 0 ? "sube" : subida < 0 ? "baja" : ""}">${
                subida ? `${signo(subida)} %` : "="}</td></tr>`;
          }).join("")}</tbody></table></div>
          <p class="ayuda" style="padding: 8px 16px 16px">“Contra estimado”: lo pagado menos lo estimado (negativo:
            se pagó menos). “Precio en el año”: cuánto subió el precio configurado entre enero y diciembre.</p>`
          : `<div class="vacio">No hay pagos registrados en ${anio.anio}.</div>`}
      </div>
      <div class="tarjeta">
        <h2>Próximos 12 meses</h2>
        <div class="leyenda">Previsto en total: ${plata(totalPrevision)}</div>
        <div class="contenido">${prevision}</div>
      </div>`;
  }

  _historialFiltrado() {
    const { servicio, anio } = this._filtro;
    return this._datos.historial.filter((p) =>
      (!servicio || p.servicio_id === servicio) && (!anio || p.periodo.startsWith(`${anio}-`)));
  }

  _dibujarHistorial() {
    const d = this._datos;
    const anios = [...new Set(d.historial.map((p) => p.periodo.slice(0, 4)))].sort().reverse();
    const filas = this._historialFiltrado();
    const opcion = (valor, texto, actual) =>
      `<option value="${esc(valor)}" ${valor === actual ? "selected" : ""}>${esc(texto)}</option>`;
    return `
      <div class="tarjeta">
        <div class="filtros">
          <select data-filtro="servicio">
            ${opcion("", "Todos los servicios", this._filtro.servicio)}
            ${d.servicios.map((s) => opcion(s.id, s.nombre, this._filtro.servicio)).join("")}
          </select>
          <select data-filtro="anio">
            ${opcion("", "Todos los años", this._filtro.anio)}
            ${anios.map((a) => opcion(a, a, this._filtro.anio)).join("")}
          </select>
          <span style="flex:1"></span>
          <button class="boton" data-accion="csv" ${filas.length ? "" : "disabled"}>Exportar CSV</button>
        </div>
        ${filas.length ? `
          <div class="tabla"><table>
            <thead><tr><th>Mes</th><th>Servicio</th><th>Vence</th><th class="num">Estimado</th>
              <th class="num">Real</th><th>Estado</th><th>Pagado el</th><th>Nota</th></tr></thead>
            <tbody>${filas.map((p) => `
              <tr>
                <td>${esc(p.periodo)}</td><td>${esc(p.nombre)}</td><td>${fechaCorta(p.vence)}</td>
                <td class="num">${dinero(p.estimado, p.moneda)}</td>
                <td class="num">${p.real === null ? "" : dinero(p.real, p.moneda)}</td>
                <td>${ESTADOS[p.estado]}</td><td>${fechaCorta(p.pagado_el)}</td><td>${esc(p.nota)}</td>
              </tr>`).join("")}
            </tbody>
          </table></div>` : `<div class="vacio">No hay pagos con estos filtros.</div>`}
      </div>`;
  }

  // ------------------------------------------------------------- eventos

  _click(evento) {
    const objetivo = evento.target.closest("[data-accion], [data-pestana]");
    if (!objetivo) return;
    if (objetivo.dataset.pestana) {
      this._pestana = objetivo.dataset.pestana;
      this._dibujar();
      if (this._pestana === "estadisticas" && !this._estadisticas) this._cargarEstadisticas();
      return;
    }
    const { accion, servicio, periodo } = objetivo.dataset;
    switch (accion) {
      case "menu":
        this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true }));
        break;
      case "mes-anterior":
      case "mes-siguiente":
        this._periodo = sumarMeses(this._periodo, accion === "mes-anterior" ? -1 : 1);
        this._cargar();
        break;
      case "mes-actual":
        this._periodo = null;
        this._cargar();
        break;
      case "csv":
        this._exportarCsv();
        break;
      case "cancelar":
        this.shadowRoot.getElementById("dialogo").close();
        break;
      case "atajo":
        this._atajoMeses(objetivo.dataset.atajo);
        break;
      default:
        this._abrir(accion, servicio, periodo);
    }
  }

  _cambio(evento) {
    const opcion = evento.target.dataset?.estadistica;
    if (opcion === "anio") {
      this._anio = evento.target.value;
      this._cargarEstadisticas();
      return;
    }
    if (opcion === "moneda") {
      this._moneda = evento.target.value;
      this._dibujar();
      return;
    }
    const filtro = evento.target.dataset?.filtro;
    if (filtro) {
      this._filtro[filtro] = evento.target.value;
      this._dibujar();
    }
  }

  _pago(servicioId, periodo) {
    const d = this._datos;
    return [...d.mes.pagos, ...d.mes.pagos_vencidos_anteriores, ...d.historial]
      .find((p) => p.servicio_id === servicioId && p.periodo === periodo);
  }

  _servicio(id) {
    return this._datos.servicios.find((s) => s.id === id);
  }

  // ------------------------------------------------------------ diálogos

  _abrir(accion, servicioId, periodo) {
    const pago = periodo ? this._pago(servicioId, periodo) : null;
    const servicio = servicioId ? this._servicio(servicioId) : null;
    const hoy = this._datos.hoy;
    const titulo = pago ? `${esc(pago.nombre)} · ${nombreMes(pago.periodo)}` : servicio ? esc(servicio.nombre) : "";
    const importe = (valor, nombre = "importe", requerido = true) => `
      <label class="campo"><span>Importe (${MONEDAS[(pago || servicio)?.moneda] || "$"})</span>
        <input name="${nombre}" type="number" inputmode="decimal" min="0" step="0.01" value="${valor ?? ""}"
          ${requerido ? "required" : ""}></label>`;
    const nota = (valor) => `
      <label class="campo"><span>Nota (opcional)</span><input name="nota" value="${esc(valor)}"
        placeholder="descuento, recargo…"></label>`;
    let html;
    switch (accion) {
      case "pagar":
        html = this._formulario(`Pagado: ${titulo}`, `
          ${importe(pago.importe)}
          <label class="campo"><span>Fecha de pago</span><input name="fecha" type="date" value="${hoy}" required></label>
          ${nota(pago.nota)}`, "Registrar pago");
        break;
      case "anotar":
        html = this._formulario(`Importe de la factura: ${titulo}`, `
          <p class="ayuda">El importe real de este mes, antes de pagarlo (por ejemplo, cuando llega la factura).</p>
          ${importe(pago.real ?? pago.estimado)}${nota(pago.nota)}`, "Guardar");
        break;
      case "corregir":
        html = this._formulario(`Corregir: ${titulo}`, `
          ${importe(pago.real)}
          <label class="campo"><span>Fecha de pago</span>
            <input name="fecha" type="date" value="${esc(pago.pagado_el)}" required></label>
          ${nota(pago.nota)}`, "Guardar");
        break;
      case "omitir":
        html = this._formulario(`Omitir: ${titulo}`, `
          <p class="ayuda">Este mes no se paga: no cuenta en los totales. Se puede deshacer.</p>${nota(pago.nota)}`,
          "Omitir");
        break;
      case "deshacer":
        html = this._formulario(`Deshacer: ${titulo}`, `
          <p class="ayuda">El pago vuelve a pendiente y se borran la fecha y el importe real.</p>`, "Deshacer", true);
        break;
      case "precio":
        html = this._formulario(`Cambió el precio: ${titulo}`, `
          <p class="ayuda">Precio actual: ${dinero(servicio.precio_actual, servicio.moneda)}. Los meses anteriores
            quedan como estaban; los pendientes desde ese mes toman el precio nuevo.</p>
          <div class="campos">
            ${importe("")}
            <label class="campo"><span>Desde</span>
              <input name="desde" type="month" value="${hoy.slice(0, 7)}" required></label>
          </div>`, "Cambiar precio");
        break;
      case "baja":
        html = this._formulario(`Dar de baja: ${titulo}`, `
          <p class="ayuda">Deja de generar pagos. El historial se conserva y se puede reactivar.</p>`,
          "Dar de baja", true);
        break;
      case "reactivar":
        html = this._formulario(`Reactivar: ${titulo}`, `
          <p class="ayuda">Vuelve a generar pagos desde este mes.</p>`, "Reactivar");
        break;
      case "servicio-nuevo":
      case "servicio-editar":
        html = this._formularioServicio(servicio);
        break;
      default:
        return;
    }
    this._dialogo = { accion, servicioId, periodo };
    const dialogo = this.shadowRoot.getElementById("dialogo");
    dialogo.innerHTML = html;
    if (!dialogo.open) dialogo.showModal();
    dialogo.querySelector("input:not([type=checkbox]), select")?.focus();
  }

  _formulario(titulo, cuerpo, boton, peligro = false) {
    return `
      <form>
        <h2>${titulo}</h2>
        <div class="cuerpo">
          <div class="error" id="error-dialogo" hidden></div>
          ${cuerpo}
        </div>
        <div class="pie">
          <button type="button" class="boton" data-accion="cancelar">Cancelar</button>
          <button type="submit" class="boton lleno ${peligro ? "peligro" : ""}">${boton}</button>
        </div>
      </form>`;
  }

  _formularioServicio(s) {
    const nuevo = !s;
    const valor = (campo, defecto = "") => esc(s ? s[campo] ?? defecto : defecto);
    const opciones = (campo, lista, defecto) => lista.map(([v, t]) =>
      `<option value="${v}" ${(s ? s[campo] : defecto) === v ? "selected" : ""}>${t}</option>`).join("");
    const meses = s ? s.meses : [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
    const categorias = this._datos.categorias;
    return this._formulario(nuevo ? "Agregar servicio" : `Editar: ${esc(s.nombre)}`, `
      <label class="campo"><span>Nombre</span><input name="nombre" value="${valor("nombre")}" required></label>
      <div class="campos">
        <label class="campo"><span>Categoría</span>
          <input name="categoria" list="categorias" value="${valor("categoria", "")}" placeholder="casa, seguros…">
          <datalist id="categorias">${categorias.map((c) => `<option value="${esc(c)}">`).join("")}</datalist>
        </label>
        <label class="campo"><span>Moneda</span><select name="moneda">
          ${opciones("moneda", [["pesos", "Pesos"], ["dolares", "Dólares"]], "pesos")}</select></label>
        ${nuevo ? `
          <label class="campo"><span>Importe</span>
            <input name="importe" type="number" inputmode="decimal" min="0" step="0.01" required></label>
          <label class="campo"><span>Desde</span>
            <input name="desde" type="month" value="${this._datos.hoy.slice(0, 7)}" required></label>` : ""}
        <label class="campo"><span>Día de vencimiento</span>
          <input name="dia_vence" type="number" min="1" max="31" value="${valor("dia_vence", 10)}" required></label>
        <label class="campo"><span>Forma de pago</span><select name="pago">
          ${opciones("pago", [["manual", "Manual"], ["debito", "Débito automático"]], "manual")}</select></label>
        <label class="campo"><span>Tipo</span><select name="tipo">
          ${opciones("tipo", [["fijo", "Fijo"], ["consumo", "Por consumo"]], "fijo")}</select></label>
      </div>
      <div class="campo"><span>Meses en que se paga</span>
        <div class="atajos">
          <button type="button" class="boton" data-accion="atajo" data-atajo="mensual">Mensual</button>
          <button type="button" class="boton" data-accion="atajo" data-atajo="cada2">Cada 2 meses</button>
          <button type="button" class="boton" data-accion="atajo" data-atajo="cada3">Cada 3</button>
          <button type="button" class="boton" data-accion="atajo" data-atajo="anual">Anual</button>
        </div>
        <p class="ayuda">Los atajos empiezan en el primer mes marcado.</p>
        <div class="meses">${MESES.map((m, i) => `
          <label><input type="checkbox" name="mes" value="${i + 1}" ${meses.includes(i + 1) ? "checked" : ""}>
            ${MESES_CORTOS[i]}</label>`).join("")}
        </div>
      </div>
      <label class="campo"><span>Remitente de la factura (opcional)</span>
        <input name="remitente" type="email" value="${valor("remitente")}" placeholder="facturas@empresa.com"></label>
      <label class="campo"><span>Notas</span><textarea name="notas" rows="2">${valor("notas")}</textarea></label>`,
      nuevo ? "Agregar" : "Guardar");
  }

  _atajoMeses(atajo) {
    const casillas = [...this.shadowRoot.querySelectorAll("dialog input[name=mes]")];
    const marcado = casillas.findIndex((c) => c.checked);
    const primero = marcado < 0 ? 0 : marcado; // sin marcar → enero
    const paso = { mensual: 1, cada2: 2, cada3: 3, anual: 12 }[atajo];
    casillas.forEach((c, i) => { c.checked = (i - primero + 12) % paso === 0; });
  }

  async _enviar(evento) {
    evento.preventDefault();
    if (!this._dialogo) return;
    const formulario = evento.target;
    const f = new FormData(formulario);
    const texto = (campo) => (f.get(campo) ?? "").toString().trim();
    const numero = (campo) => (texto(campo) === "" ? undefined : Number(texto(campo)));
    const { accion, servicioId, periodo } = this._dialogo;
    const base = { servicio: servicioId, periodo };
    let servicio;
    let datos;
    switch (accion) {
      case "pagar":
        [servicio, datos] = ["registrar_pago", { ...base, importe: numero("importe"), fecha: texto("fecha"), nota: texto("nota") }];
        break;
      case "anotar":
        [servicio, datos] = ["anotar_importe", { ...base, importe: numero("importe"), nota: texto("nota") }];
        break;
      case "corregir":
        [servicio, datos] = ["corregir_pago", { ...base, importe: numero("importe"), fecha: texto("fecha"), nota: texto("nota") }];
        break;
      case "omitir":
        [servicio, datos] = ["omitir", { ...base, nota: texto("nota") }];
        break;
      case "deshacer":
        [servicio, datos] = ["deshacer_pago", base];
        break;
      case "precio":
        [servicio, datos] = ["cambiar_precio", { servicio: servicioId, importe: numero("importe"), desde: texto("desde") }];
        break;
      case "baja":
        [servicio, datos] = ["dar_de_baja", { servicio: servicioId }];
        break;
      case "reactivar":
        [servicio, datos] = ["reactivar", { servicio: servicioId }];
        break;
      case "servicio-nuevo":
      case "servicio-editar": {
        const meses = f.getAll("mes").map(Number);
        if (!meses.length) {
          this._errorDialogo("Marcá al menos un mes.");
          return;
        }
        datos = {
          nombre: texto("nombre"), categoria: texto("categoria") || "otros", moneda: texto("moneda"),
          pago: texto("pago"), tipo: texto("tipo"), dia_vence: numero("dia_vence"), meses,
          remitente: texto("remitente") || null, notas: texto("notas"),
        };
        if (accion === "servicio-nuevo") {
          servicio = "agregar_servicio";
          Object.assign(datos, { importe: numero("importe"), desde: texto("desde") });
        } else {
          servicio = "editar_servicio";
          datos.servicio = servicioId;
        }
        break;
      }
      default:
        return;
    }
    // Sin campos vacíos (la acción usa sus valores por defecto); la nota vacía sí se manda, para borrarla.
    for (const [clave, valor] of Object.entries(datos)) {
      if (valor === undefined || (valor === "" && clave !== "nota" && clave !== "notas")) delete datos[clave];
    }
    const boton = formulario.querySelector("button[type=submit]");
    boton.disabled = true;
    try {
      await this._hass.callService("facturas", servicio, datos);
      this.shadowRoot.getElementById("dialogo").close();
      this._cargar();
    } catch (err) {
      this._errorDialogo(err.message || String(err));
      boton.disabled = false;
    }
  }

  _errorDialogo(mensaje) {
    const caja = this.shadowRoot.getElementById("error-dialogo");
    if (caja) {
      caja.textContent = mensaje;
      caja.hidden = false;
    }
  }

  _exportarCsv() {
    const columnas = ["periodo", "servicio", "categoria", "moneda", "vence", "estimado", "real", "estado",
      "pagado_el", "origen", "nota"];
    const categorias = Object.fromEntries(this._datos.servicios.map((s) => [s.id, s.categoria]));
    const celda = (valor) => {
      const texto = valor === null || valor === undefined ? "" : String(valor);
      return /[";\n]/.test(texto) ? `"${texto.replace(/"/g, '""')}"` : texto;
    };
    const numero = (valor) => (valor === null || valor === undefined ? "" : String(valor).replace(".", ","));
    const filas = this._historialFiltrado().map((p) => [
      p.periodo, p.nombre, categorias[p.servicio_id] || "", p.moneda, p.vence, numero(p.estimado), numero(p.real),
      p.estado, p.pagado_el, p.origen, p.nota,
    ].map(celda).join(";"));
    // Punto y coma y coma decimal: así lo abre bien una planilla en español. El BOM es para los acentos.
    const csv = "﻿" + [columnas.join(";"), ...filas].join("\r\n");
    const enlace = document.createElement("a");
    enlace.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    enlace.download = `facturas${this._filtro.anio ? `-${this._filtro.anio}` : ""}.csv`;
    document.body.appendChild(enlace);
    enlace.click();
    enlace.remove();
    setTimeout(() => URL.revokeObjectURL(enlace.href), 1000);
  }
}

if (!customElements.get("facturas-panel")) {
  customElements.define("facturas-panel", FacturasPanel);
}
