// Cliente del panel. Sin scripts en línea (la CSP solo permite script-src 'self').
// La cookie de sesión es HttpOnly: JavaScript no puede leerla. Para saber si hay sesión se piden los datos:
// 200 = hay sesión, 401 = hay que entrar.
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var ARCHIVO = '/data/resumen.json';

  function mostrar(id) {
    ['comprobando', 'acceso', 'panel'].forEach(function (x) { $(x).hidden = x !== id; });
  }

  function texto(etiqueta, clase, contenido) {
    var el = document.createElement(etiqueta);
    if (clase) el.className = clase;
    el.textContent = contenido; // textContent, nunca innerHTML: los datos no pueden inyectar HTML
    return el;
  }

  function pintar(d) {
    $('titulo').textContent = d.titulo || 'Panel';
    $('actualizado').textContent = d.actualizado ? 'Actualizado: ' + d.actualizado : '';
    var cifras = $('cifras');
    cifras.textContent = '';
    (d.cifras || []).forEach(function (c) {
      var caja = texto('div', 'cifra', '');
      caja.appendChild(texto('span', 'valor', c.valor));
      caja.appendChild(texto('span', 'etiqueta', c.etiqueta));
      cifras.appendChild(caja);
    });
    var lista = $('entradas');
    lista.textContent = '';
    (d.entradas || []).forEach(function (e) {
      var li = texto('li', '', '');
      li.appendChild(texto('span', 'fecha', e.fecha));
      li.appendChild(texto('span', '', e.texto));
      lista.appendChild(li);
    });
    mostrar('panel');
  }

  function cargar() {
    return fetch(ARCHIVO, { credentials: 'same-origin', cache: 'no-store' }).then(function (r) {
      if (r.status === 200) return r.json().then(pintar).then(function () { return true; });
      return false;
    });
  }

  function error(msg) {
    var e = $('error');
    e.textContent = msg;
    e.hidden = false;
    $('clave').setAttribute('aria-invalid', 'true');
  }

  document.addEventListener('DOMContentLoaded', function () {
    var form = $('formAcceso');
    var boton = form.querySelector('button');
    $('clave').addEventListener('input', function () { this.removeAttribute('aria-invalid'); $('error').hidden = true; });

    cargar().then(function (ok) { if (!ok) { mostrar('acceso'); $('clave').focus(); } })
      .catch(function () { mostrar('acceso'); error('Sin conexión. Reintenta.'); });

    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var clave = $('clave');
      if (!clave.value || boton.disabled) return;
      boton.disabled = true;
      boton.textContent = 'Verificando…';
      fetch('/api/login', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: clave.value, remember: $('recordar').checked })
      }).then(function (r) {
        boton.disabled = false;
        boton.textContent = 'Entrar';
        if (r.ok) { clave.value = ''; clave.removeAttribute('aria-invalid'); $('error').hidden = true; return cargar(); }
        if (r.status === 429) {
          var s = Number(r.headers.get('Retry-After')) || 900;
          error('Demasiados intentos. Espera ' + Math.ceil(s / 60) + ' min.');
        } else if (r.status === 401) {
          error('Contraseña incorrecta.');
          clave.select();
        } else {
          error('El servidor no está configurado (código ' + r.status + ').');
        }
      }).catch(function () {
        boton.disabled = false;
        boton.textContent = 'Entrar';
        error('Sin conexión. Reintenta.');
      });
    });

    $('salir').addEventListener('click', function () {
      fetch('/api/logout', { method: 'POST', credentials: 'same-origin' }).finally(function () {
        mostrar('acceso');
        $('clave').focus();
      });
    });
  });
})();
