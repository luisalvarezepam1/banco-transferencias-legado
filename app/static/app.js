// Pantalla del módulo de transferencias: consume la misma API /api que usan otros sistemas.
(function () {
  var $ = function (s) { return document.querySelector(s); };
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  var dinero = function (t) { var p = String(t).split('.'), e = p[0].replace('-', ''); return (p[0][0] === '-' ? '-' : '') + Number(e).toLocaleString('en-US') + '.' + (p[1] || '00'); };
  var fecha = function (iso) { if (!iso) return ''; var d = iso.split('T'); var f = d[0].split('-'); return f[2] + '/' + f[1] + '/' + f[0] + ' ' + (d[1] || '').slice(0, 5); };
  var api = function (ruta, opciones) {
    return fetch('/api' + ruta, opciones).then(function (r) {
      return r.json().then(function (cuerpo) { if (!r.ok) { var e = new Error((cuerpo.error || {}).mensaje || 'Error'); e.codigo = (cuerpo.error || {}).codigo; throw e; } return cuerpo; });
    });
  };

  function cargarCuentas() {
    return api('/cuentas').then(function (cuentas) {
      $('#cuentas').innerHTML = cuentas.map(function (c) {
        return '<li><div><b class="num-cta">' + esc(c.numero) + '</b><span class="dim">' + esc(c.titular) + '</span></div>' +
          '<div class="der"><b>' + esc(c.moneda) + ' ' + dinero(c.saldo) + '</b>' + (c.estado !== 'ACTIVA' ? '<span class="chip chip--error">' + esc(c.estado) + '</span>' : '') + '</div></li>';
      }).join('');
      var opciones = cuentas.map(function (c) { return '<option value="' + esc(c.numero) + '">' + esc(c.numero) + ' · ' + esc(c.titular) + '</option>'; }).join('');
      var o = $('#origen').value, d = $('#destino').value;
      $('#origen').innerHTML = opciones; $('#destino').innerHTML = opciones;
      $('#origen').value = o || cuentas[0].numero; $('#destino').value = d || (cuentas[2] || cuentas[0]).numero;
    });
  }

  function cargarHistorial() {
    return api('/transferencias?limite=10').then(function (ts) {
      $('#historial').innerHTML = ts.length ? ts.map(function (t) {
        return '<tr><td>' + esc(t.id) + '</td><td class="nowrap">' + fecha(t.fecha) + '</td><td class="nowrap">' + esc(t.cuenta_origen) + ' → ' + esc(t.cuenta_destino) + '</td><td><span class="chip">' + esc(t.tipo) + '</span></td>' +
          '<td class="num">' + dinero(t.monto) + '</td><td class="num">' + dinero(t.comision) + '</td><td class="num">' + dinero(t.impuesto) + '</td><td class="num"><b>' + dinero(t.total_debitado) + '</b></td></tr>';
      }).join('') : '<tr><td colspan="8" class="dim">Sin transferencias todavía.</td></tr>';
    });
  }

  $('#form').addEventListener('submit', function (ev) {
    ev.preventDefault();
    var datos = Object.fromEntries(new FormData(ev.target).entries());
    var clave = (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now());
    var r = $('#resultado'); r.hidden = false; r.className = 'resultado'; r.textContent = 'Enviando…';
    api('/transferencias', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': clave }, body: JSON.stringify(datos) })
      .then(function (t) {
        r.className = 'resultado resultado--ok';
        r.innerHTML = '<b>Transferencia ' + esc(t.id) + ' aplicada</b><br>Monto DOP ' + dinero(t.monto) + ' · comisión ' + dinero(t.comision) + ' · impuesto ' + dinero(t.impuesto) + ' · <b>total debitado DOP ' + dinero(t.total_debitado) + '</b>';
        ev.target.monto.value = ''; ev.target.concepto.value = '';
        return Promise.all([cargarCuentas(), cargarHistorial()]);
      })
      .catch(function (e) { r.className = 'resultado resultado--error'; r.innerHTML = '<b>' + esc(e.codigo || 'ERROR') + '</b> · ' + esc(e.message); });
  });

  api('/salud').then(function (s) { $('#version').textContent = 'v' + s.version + ' · legado'; }).catch(function () {});
  cargarCuentas().then(cargarHistorial);
})();
