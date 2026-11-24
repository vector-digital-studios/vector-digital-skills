/* registro-comidas · panel estático (sin frameworks, sin servidor, sin login)
   Lee: config.json, data/indice.json (totales por día) y data/AAAA-MM-DD.json (detalle del día).
   Rutas: #dia/AAAA-MM-DD  ·  #semana/AAAA-MM-DD   (la semana que contiene esa fecha)
   Licencia MIT. */
(function () {
  'use strict';

  var TXT = {
    es: {
      dia: 'Día', semana: 'Semana', cargando: 'Cargando…', de: 'de', kcal: 'kcal',
      restantes: 'kcal restantes', excedidas: 'kcal sobre la meta', proteina: 'Proteína', grasa: 'Grasa',
      carbos: 'Carbohidratos', reparto: 'Reparto de calorías', comidas: 'Comidas', pendiente: 'pendiente · cuéntaselo a tu agente',
      sinDia: 'No hay registro para este día.', ultimo: 'Ir al último día con registro',
      promedio: 'Promedio diario', enMeta: 'Días en meta (±10 %)', registrados: 'Días registrados', semanaTxt: 'esta semana', diasCon: 'días con registro',
      macrosProm: 'Macros promedio vs meta', detalle: 'Detalle', sinSemana: 'Sin registros en esta semana.',
      meta: 'meta', hoy: 'hoy', alimentos: 'alimentos', alimento: 'alimento',
      servidor: 'No se pudieron leer los datos. Abre el panel con un servidor local (python -m http.server) en vez de doble clic.',
      pie: 'Tus datos viven en tus propios archivos · sin cuentas',
      nota: 'Supuesto', toque: 'Toca una barra para ver el día',
      offline: 'Sin conexión y sin copia guardada de este panel. Ábrelo una vez con conexión.'
    },
    en: {
      dia: 'Day', semana: 'Week', cargando: 'Loading…', de: 'of', kcal: 'kcal',
      restantes: 'kcal left', excedidas: 'kcal over goal', proteina: 'Protein', grasa: 'Fat',
      carbos: 'Carbs', reparto: 'Calorie split', comidas: 'Meals', pendiente: 'pending · tell your agent',
      sinDia: 'Nothing logged for this day.', ultimo: 'Go to the last logged day',
      promedio: 'Daily average', enMeta: 'Days on goal (±10%)', registrados: 'Days logged', semanaTxt: 'this week', diasCon: 'logged days',
      macrosProm: 'Average macros vs goal', detalle: 'Details', sinSemana: 'Nothing logged this week.',
      meta: 'goal', hoy: 'today', alimentos: 'foods', alimento: 'food',
      servidor: 'Could not read the data. Serve the panel locally (python -m http.server) instead of double-clicking.',
      pie: 'Your data lives in your own files · no accounts',
      nota: 'Assumption', toque: 'Tap a bar to open that day',
      offline: 'Offline and no saved copy of this panel yet. Open it once while online.'
    }
  };
  var NOMBRES_COMIDA = {
    en: { Desayuno: 'Breakfast', Almuerzo: 'Lunch', Cena: 'Dinner', Snack: 'Snack' }
  };
  var SLOTS = ['Desayuno', 'Almuerzo', 'Cena'];
  var COL = { protein: '#FF6A00', fat: '#F5B83D', carbs: '#4FC3D9' };

  var S = { cfg: null, idx: {}, vista: 'dia', fecha: null, cache: {}, t: TXT.es, loc: 'es-419' };

  /* ---------------- utilidades ---------------- */
  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function fmt(n) { return Math.round(n || 0).toLocaleString(S.loc); }
  function pad(n) { return n < 10 ? '0' + n : '' + n; }
  function iso(d) { return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
  function aFecha(s) { return new Date(s + 'T12:00:00'); }
  function sumar(s, dias) { var d = aFecha(s); d.setDate(d.getDate() + dias); return iso(d); }
  function hoy() { return iso(new Date()); }
  function mayus(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }
  function unidad(q, u) {
    // plural simple en español para porciones (2 unidades, 1,5 tazas); g y ml no cambian
    if (S.cfg.idioma === 'en' || q === 1 || !u || u === 'g' || u === 'ml' || u.indexOf(' ') >= 0) return u;
    return /[aeiouáéíóú]$/i.test(u) ? u + 's' : (/[ckp]$/.test(u) ? u + 's' : u + 'es');
  }
  function num(q) { return (+q).toLocaleString(S.loc, { maximumFractionDigits: 1 }); }
  function nombreComida(n) { var m = NOMBRES_COMIDA[S.cfg.idioma] || {}; return m[n] || n; }
  function inicioSemana(s) {
    var d = aFecha(s), dow = d.getDay();
    var lunes = (S.cfg.semana_inicia || 'lunes') !== 'domingo';
    var delta = lunes ? (dow === 0 ? -6 : 1 - dow) : -dow;
    return sumar(s, delta);
  }
  function metaDe(dia) { return (dia && dia.target) || S.cfg.meta; }
  function pct(v, m) { return m > 0 ? (v / m) * 100 : 0; }

  async function getJSON(url) {
    var r = await fetch(url, { cache: 'no-cache' });
    if (!r.ok) { var e = new Error('HTTP ' + r.status); e.status = r.status; throw e; }
    return r.json();
  }
  async function cargarDia(f) {
    if (S.cache[f] !== undefined) return S.cache[f];
    try { S.cache[f] = await getJSON('data/' + f + '.json'); }
    catch (e) { S.cache[f] = null; }
    return S.cache[f];
  }

  /* ---------------- piezas visuales ---------------- */
  function anillo(valor, meta) {
    var p = pct(valor, meta), R = 84, C = 2 * Math.PI * R;
    var arco = C * Math.min(p, 100) / 100;
    var col = p > 105 ? '#EF4444' : '#FF6A00';
    return '<svg class="anillo" viewBox="0 0 200 200" role="img" aria-label="' + fmt(valor) + ' / ' + fmt(meta) + ' kcal">'
      + '<circle cx="100" cy="100" r="' + R + '" class="anillo-pista"/>'
      + '<circle cx="100" cy="100" r="' + R + '" class="anillo-arco" stroke="' + col + '" '
      + 'stroke-dasharray="' + arco.toFixed(1) + ' ' + C.toFixed(1) + '" transform="rotate(-90 100 100)"/>'
      + '<text x="100" y="98" class="anillo-num">' + fmt(valor) + '</text>'
      + '<text x="100" y="124" class="anillo-sub">' + S.t.de + ' ' + fmt(meta) + ' ' + S.t.kcal + '</text>'
      + '</svg>';
  }

  function barraMacro(nombre, clave, v, m) {
    var p = pct(v, m);
    var estado = p > 110 ? 'alto' : (p >= 85 ? 'ok' : 'bajo');
    return '<div class="macro">'
      + '<div class="macro-cab"><span><i class="punto" style="background:' + COL[clave] + '"></i>' + nombre + '</span>'
      + '<span class="macro-val">' + fmt(v) + ' <em>/ ' + fmt(m) + ' g</em></span></div>'
      + '<div class="pista"><div class="relleno" style="width:' + Math.min(p, 100).toFixed(1) + '%;background:' + COL[clave] + '"></div></div>'
      + '<div class="macro-pct macro-pct--' + estado + '">' + Math.round(p) + '%</div>'
      + '</div>';
  }

  function reparto(t) {
    var p = t.protein * 4, g = t.fat * 9, c = t.carbs * 4, tot = p + g + c || 1;
    var seg = [[S.t.proteina, p, 'protein'], [S.t.grasa, g, 'fat'], [S.t.carbos, c, 'carbs']];
    return '<div class="reparto">' + seg.map(function (s) {
      return '<div style="flex:' + (s[1] / tot).toFixed(4) + ';background:' + COL[s[2]] + '"></div>';
    }).join('') + '</div><div class="reparto-ley">' + seg.map(function (s) {
      return '<span><i class="punto" style="background:' + COL[s[2]] + '"></i>' + s[0] + ' ' + Math.round(s[1] / tot * 100) + '%</span>';
    }).join('') + '</div>';
  }

  function tarjetaComida(m) {
    var ings = m.ingredients || [];
    var chips = ings.map(function (i) {
      return '<li><span>' + esc(i.name) + ' <em>' + num(i.qty) + ' ' + esc(unidad(+i.qty, i.unit)) + '</em></span><b>' + fmt(i.kcal) + ' <small>kcal</small></b></li>';
    }).join('');
    var n = ings.length;
    return '<article class="comida">'
      + '<div class="comida-cab"><div><h3>' + esc(nombreComida(m.name)) + '</h3>'
      + '<div class="comida-meta">' + (m.time ? esc(m.time) + ' · ' : '') + n + ' ' + (n === 1 ? S.t.alimento : S.t.alimentos) + '</div></div>'
      + '<div class="comida-kcal">' + fmt(m.kcal) + '<small> kcal</small></div></div>'
      + ((m.items || []).length ? '<p class="comida-items">' + m.items.map(esc).join(' · ') + '</p>' : '')
      + '<div class="comida-macros">P ' + fmt(m.protein) + ' g · G ' + fmt(m.fat) + ' g · C ' + fmt(m.carbs) + ' g</div>'
      + (chips ? '<ul class="ings">' + chips + '</ul>' : '')
      + (m.note ? '<p class="comida-nota">' + S.t.nota + ': ' + esc(m.note) + '</p>' : '')
      + '</article>';
  }

  /* ---------------- vista Día ---------------- */
  async function vistaDia() {
    var f = S.fecha, dia = await cargarDia(f), app = $('app');
    if (!dia) {
      var fechas = Object.keys(S.idx).sort();
      app.innerHTML = '<div class="vacio">' + S.t.sinDia
        + (fechas.length ? '<br><a class="enlace" href="#dia/' + fechas[fechas.length - 1] + '">' + S.t.ultimo + '</a>' : '')
        + '</div>';
      return;
    }
    var t = dia.daily_total, m = metaDe(dia), resto = m.kcal - t.kcal;
    var html = '<section class="tarjeta heroe">' + anillo(t.kcal, m.kcal)
      + '<div class="resto ' + (resto >= 0 ? 'resto--ok' : 'resto--alto') + '">'
      + (resto >= 0 ? fmt(resto) + ' ' + S.t.restantes : fmt(-resto) + ' ' + S.t.excedidas) + '</div></section>';
    html += '<section class="tarjeta">'
      + barraMacro(S.t.proteina, 'protein', t.protein, m.protein)
      + barraMacro(S.t.grasa, 'fat', t.fat, m.fat)
      + barraMacro(S.t.carbos, 'carbs', t.carbs, m.carbs)
      + '<h2 class="subt">' + S.t.reparto + '</h2>' + reparto(t) + '</section>';
    html += '<h2 class="seccion">' + S.t.comidas + '</h2>';
    var presentes = (dia.meals || []).map(function (x) { return (x.name || '').toLowerCase(); });
    html += (dia.meals || []).map(tarjetaComida).join('');
    SLOTS.forEach(function (s) {
      if (presentes.indexOf(s.toLowerCase()) < 0) {
        html += '<article class="comida comida--pend"><h3>' + esc(nombreComida(s)) + '</h3><span>' + S.t.pendiente + '</span></article>';
      }
    });
    app.innerHTML = html;
  }

  /* ---------------- vista Semana ---------------- */
  function graficoSemana(dias, meta) {
    var W = 340, H = 220, pl = 8, pr = 8, pt = 30, pb = 30;
    var maxV = Math.max(meta.kcal * 1.12, Math.max.apply(null, dias.map(function (d) { return d.t ? d.t.kcal : 0; })) * 1.1);
    var aw = (W - pl - pr) / 7, bw = aw * 0.58;
    function y(v) { return pt + (H - pt - pb) * (1 - v / maxV); }
    var ym = y(meta.kcal);
    var s = '<svg class="graf" viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="kcal por día">';
    // línea de meta primero (debajo de las barras) con su rótulo arriba a la izquierda, fuera de las barras
    s += '<line x1="' + pl + '" x2="' + (W - pr) + '" y1="' + ym.toFixed(1) + '" y2="' + ym.toFixed(1) + '" class="graf-meta"/>';
    s += '<text x="' + pl + '" y="12" class="graf-meta-txt">- - ' + S.t.meta + ' ' + fmt(meta.kcal) + ' kcal</text>';
    dias.forEach(function (d, i) {
      var x = pl + aw * i + (aw - bw) / 2, base = H - pb;
      if (d.t) {
        var partes = [['protein', d.t.protein * 4], ['fat', d.t.fat * 9], ['carbs', d.t.carbs * 4]];
        var suma = partes.reduce(function (a, p) { return a + p[1]; }, 0) || 1;
        var alto = (H - pt - pb) * d.t.kcal / maxV, acum = 0;
        s += '<a href="#dia/' + d.f + '" class="barra-link">';
        partes.forEach(function (p) {
          var h = alto * p[1] / suma;
          s += '<rect x="' + x.toFixed(1) + '" y="' + (base - acum - h).toFixed(1) + '" width="' + bw.toFixed(1) + '" height="' + Math.max(h, 0).toFixed(1) + '" fill="' + COL[p[0]] + '" rx="1.5"/>';
          acum += h;
        });
        // si la barra termina justo bajo la meta, el rótulo sube por encima de la línea
        var tope = base - alto, ty = (tope > ym && tope - ym < 16) ? ym - 5 : tope - 6;
        s += '<text x="' + (x + bw / 2).toFixed(1) + '" y="' + ty.toFixed(1) + '" class="graf-val">' + fmt(d.t.kcal) + '</text></a>';
      } else {
        s += '<rect x="' + x.toFixed(1) + '" y="' + (base - 3) + '" width="' + bw.toFixed(1) + '" height="3" class="graf-vacio"/>';
      }
      var lab = mayus(aFecha(d.f).toLocaleDateString(S.loc, { weekday: 'short' }).replace('.', ''));
      s += '<text x="' + (x + bw / 2).toFixed(1) + '" y="' + (H - pb + 15) + '" class="graf-dia' + (d.f === hoy() ? ' graf-hoy' : '') + '">' + esc(lab) + '</text>';
      s += '<text x="' + (x + bw / 2).toFixed(1) + '" y="' + (H - pb + 27) + '" class="graf-num">' + aFecha(d.f).getDate() + '</text>';
    });
    return s + '</svg>';
  }

  async function vistaSemana() {
    var ini = inicioSemana(S.fecha), dias = [], i;
    for (i = 0; i < 7; i++) {
      var f = sumar(ini, i);
      dias.push({ f: f, t: S.idx[f] || null });
    }
    var con = dias.filter(function (d) { return d.t; });
    var meta = S.cfg.meta, app = $('app');
    if (!con.length) { app.innerHTML = '<div class="vacio">' + S.t.sinSemana + '</div>'; return; }
    var prom = { kcal: 0, protein: 0, fat: 0, carbs: 0 };
    con.forEach(function (d) { ['kcal', 'protein', 'fat', 'carbs'].forEach(function (k) { prom[k] += d.t[k] / con.length; }); });
    var enMeta = con.filter(function (d) { var p = pct(d.t.kcal, meta.kcal); return p >= 90 && p <= 110; }).length;
    var html = '<section class="kpis">'
      + '<div class="kpi"><b>' + fmt(prom.kcal) + '</b><span>' + S.t.promedio + '</span><em>kcal · ' + Math.round(pct(prom.kcal, meta.kcal)) + '% ' + S.t.de + ' ' + S.t.meta + '</em></div>'
      + '<div class="kpi"><b>' + enMeta + '<small>/' + con.length + '</small></b><span>' + S.t.enMeta + '</span><em>' + S.t.diasCon + '</em></div>'
      + '<div class="kpi"><b>' + con.length + '<small>/7</small></b><span>' + S.t.registrados + '</span><em>' + S.t.semanaTxt + '</em></div>'
      + '</section>';
    html += '<section class="tarjeta">' + graficoSemana(dias, meta)
      + '<div class="reparto-ley">'
      + '<span><i class="punto" style="background:' + COL.protein + '"></i>' + S.t.proteina + '</span>'
      + '<span><i class="punto" style="background:' + COL.fat + '"></i>' + S.t.grasa + '</span>'
      + '<span><i class="punto" style="background:' + COL.carbs + '"></i>' + S.t.carbos + '</span></div>'
      + '<p class="ayuda">' + S.t.toque + '</p></section>';
    html += '<h2 class="seccion">' + S.t.macrosProm + '</h2><section class="tarjeta">'
      + barraMacro(S.t.proteina, 'protein', prom.protein, meta.protein)
      + barraMacro(S.t.grasa, 'fat', prom.fat, meta.fat)
      + barraMacro(S.t.carbos, 'carbs', prom.carbs, meta.carbs) + '</section>';
    html += '<h2 class="seccion">' + S.t.detalle + '</h2><section class="tarjeta lista-dias">' + dias.map(function (d) {
      var lab = mayus(aFecha(d.f).toLocaleDateString(S.loc, { weekday: 'long', day: 'numeric', month: 'short' }));
      if (!d.t) return '<div class="fila fila--vacia"><span>' + esc(lab) + '</span><span>—</span></div>';
      var p = pct(d.t.kcal, meta.kcal);
      return '<a class="fila" href="#dia/' + d.f + '"><span>' + esc(lab) + '</span><span><b>' + fmt(d.t.kcal) + '</b> kcal <em class="' + (p > 110 ? 'alto' : (p >= 90 ? 'ok' : 'bajo')) + '">' + Math.round(p) + '%</em></span></a>';
    }).join('') + '</section>';
    app.innerHTML = html;
  }

  /* ---------------- cabecera y rutas ---------------- */
  function pintarCabecera() {
    $('tabDia').classList.toggle('tab--on', S.vista === 'dia');
    $('tabSemana').classList.toggle('tab--on', S.vista === 'semana');
    $('tabDia').setAttribute('aria-selected', S.vista === 'dia');
    $('tabSemana').setAttribute('aria-selected', S.vista === 'semana');
    var lab;
    if (S.vista === 'dia') {
      lab = aFecha(S.fecha).toLocaleDateString(S.loc, { weekday: 'long', day: 'numeric', month: 'long' });
      lab = S.fecha === hoy() ? mayus(S.t.hoy) + ' · ' + lab : mayus(lab);
    } else {
      var ini = inicioSemana(S.fecha), fin = sumar(ini, 6);
      lab = aFecha(ini).toLocaleDateString(S.loc, { day: 'numeric', month: 'short' }) + ' – '
        + aFecha(fin).toLocaleDateString(S.loc, { day: 'numeric', month: 'short', year: 'numeric' });
    }
    $('fechaLabel').textContent = lab;
    $('picker').value = S.fecha;
  }

  async function render() {
    pintarCabecera();
    if (S.vista === 'semana') await vistaSemana(); else await vistaDia();
  }

  function leerRuta() {
    var m = (location.hash || '').match(/^#(dia|semana)(?:\/(\d{4}-\d{2}-\d{2}))?$/);
    if (m) { S.vista = m[1]; if (m[2]) S.fecha = m[2]; }
  }
  function ir(vista, fecha) { location.hash = '#' + vista + '/' + fecha; }

  async function init() {
    try {
      S.cfg = await getJSON('config.json');
    } catch (e) {
      var t0 = TXT[(navigator.language || 'es').slice(0, 2)] || TXT.es;
      $('app').innerHTML = '<div class="vacio">' + (navigator.onLine === false ? t0.offline : t0.servidor) + '</div>';
      return;
    }
    S.cfg.meta = S.cfg.meta || { kcal: 2000, protein: 100, fat: 65, carbs: 250 };
    S.t = TXT[S.cfg.idioma] || TXT.es;
    S.loc = S.cfg.locale || (S.cfg.idioma === 'en' ? 'en-US' : 'es-419');
    document.documentElement.lang = S.cfg.idioma || 'es';
    $('titulo').textContent = S.cfg.titulo || 'Mis comidas';
    document.title = S.cfg.titulo || 'Mis comidas';
    $('tabDia').textContent = S.t.dia;
    $('tabSemana').textContent = S.t.semana;
    $('pie').textContent = S.t.pie;
    try {
      var crudo = (await getJSON('data/indice.json')).fechas || {};
      // solo claves AAAA-MM-DD: nada del índice llega al HTML sin pasar por este filtro
      Object.keys(crudo).forEach(function (k) { if (/^\d{4}-\d{2}-\d{2}$/.test(k)) S.idx[k] = crudo[k]; });
    } catch (e) { S.idx = {}; }
    var fechas = Object.keys(S.idx).sort();
    // hoy si ya hay registro (o si no hay ninguno); si no, el último día registrado
    S.fecha = (S.idx[hoy()] || !fechas.length) ? hoy() : fechas[fechas.length - 1];
    leerRuta();

    $('tabDia').onclick = function () { ir('dia', S.fecha); };
    $('tabSemana').onclick = function () { ir('semana', S.fecha); };
    $('prev').onclick = function () { ir(S.vista, sumar(S.fecha, S.vista === 'dia' ? -1 : -7)); };
    $('next').onclick = function () { ir(S.vista, sumar(S.fecha, S.vista === 'dia' ? 1 : 7)); };
    $('picker').onchange = function () { if (this.value) ir(S.vista, this.value); };
    window.addEventListener('hashchange', function () { leerRuta(); render(); });
    render();
  }

  document.addEventListener('DOMContentLoaded', init);
  if ('serviceWorker' in navigator && location.protocol !== 'file:') {
    navigator.serviceWorker.register('sw.js').catch(function () {});
  }
})();
