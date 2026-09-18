/* ==========================================================================
   Mando Xbox 360 web + botonera MIDI — cliente (celular)
   Dos modos:  JOYSTICK (mando virtual en la PC)  |  MIDI (Resolume / QLC+)
   ========================================================================== */
(() => {
  'use strict';

  const $ = s => document.querySelector(s);
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const ZONA_MUERTA = 0.07;

  /* ══════════════════ estado general ══════════════════ */
  let ws = null, conectado = false, reintento = 500, latencia = 0;
  let modo = 'joy';                       // joy | midi
  let mapa = null, pagina = 0;
  const toggles = {};                     // id -> bool (botones MIDI en modo toggle)

  /* ══════════════════ MODO JOYSTICK ══════════════════ */
  const BOTONES = ['a','b','x','y','lb','rb','start','back','guide','l3','r3','up','down','left','right'];
  const est = { ls:[0,0], rs:[0,0], lt:0, rt:0, b:{} };
  for (const k of BOTONES) est.b[k] = false;
  const objetivo = { lt:0, rt:0 };
  let sucio = false;

  const sticks = { ls:[0,0], rs:[0,0] };

  function pintarBoton(nombre, apretado) {
    const el = document.querySelector(`[data-btn="${nombre}"]`);
    if (el) el.classList.toggle('act', apretado);
  }

  function apretar(nombre, valor) {
    if (!(nombre in est.b) || est.b[nombre] === valor) return;
    est.b[nombre] = valor;
    pintarBoton(nombre, valor);
    sucio = true;
    if (valor && navigator.vibrate) { try { navigator.vibrate(8); } catch {} }
  }

  function engancharBoton(el) {
    const nombre = el.dataset.btn;
    el.addEventListener('pointerdown', ev => {
      try { el.setPointerCapture(ev.pointerId); } catch {}
      apretar(nombre, true);
      ev.preventDefault(); ev.stopPropagation();
    });
    for (const e of ['pointerup','pointercancel']) {
      el.addEventListener(e, ev => { apretar(nombre, false); ev.preventDefault(); });
    }
    el.addEventListener('contextmenu', e => e.preventDefault());
  }
  for (const el of document.querySelectorAll('[data-btn]')) {
    if (el.id !== 'bLT' && el.id !== 'bRT') engancharBoton(el);
  }

  for (const [id, clave] of [['#bLT','lt'], ['#bRT','rt']]) {
    const el = $(id);
    el.addEventListener('pointerdown', ev => {
      try { el.setPointerCapture(ev.pointerId); } catch {}
      objetivo[clave] = 1; el.classList.add('act');
      if (navigator.vibrate) { try { navigator.vibrate(8); } catch {} }
      ev.preventDefault(); ev.stopPropagation();
    });
    for (const e of ['pointerup','pointercancel']) {
      el.addEventListener(e, () => { objetivo[clave] = 0; el.classList.remove('act'); });
    }
    el.addEventListener('contextmenu', e => e.preventDefault());
  }

  function crearStick(zoneSel, knobSel, eje, boton) {
    const zona = $(zoneSel), knob = $(knobSel);
    let idActivo = null, movido = 0, t0 = 0;
    const radio = () => zona.clientWidth / 2;

    function pos(ev) {
      const r = zona.getBoundingClientRect();
      const R = radio();
      let dx = ev.clientX - (r.left + r.width / 2);
      let dy = ev.clientY - (r.top + r.height / 2);
      const d = Math.hypot(dx, dy);
      if (d > R) { dx = dx / d * R; dy = dy / d * R; }
      knob.style.transform = `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px))`;
      return [dx / R, dy / R];
    }

    zona.addEventListener('pointerdown', ev => {
      if (idActivo !== null) return;
      idActivo = ev.pointerId; movido = 0; t0 = performance.now();
      try { zona.setPointerCapture(ev.pointerId); } catch {}
      sticks[eje] = pos(ev);
      sucio = true; ocultarHint();
      ev.preventDefault();
    });
    zona.addEventListener('pointermove', ev => {
      if (ev.pointerId !== idActivo) return;
      const [x, y] = pos(ev);
      movido += Math.hypot(x, y);
      sticks[eje] = [x, y];
      sucio = true; ev.preventDefault();
    });
    for (const e of ['pointerup','pointercancel']) {
      zona.addEventListener(e, ev => {
        if (ev.pointerId !== idActivo) return;
        idActivo = null;
        knob.style.transform = 'translate(-50%,-50%)';
        sticks[eje] = [0, 0];
        sucio = true;
        if (movido < 0.35 && performance.now() - t0 < 260) {   // toque corto = L3/R3
          apretar(boton, true);
          setTimeout(() => apretar(boton, false), 130);
        }
      });
    }
    zona.addEventListener('contextmenu', e => e.preventDefault());
  }
  crearStick('#zStickL', '#knobL', 'ls', 'l3');
  crearStick('#zStickR', '#knobR', 'rs', 'r3');

  (() => {                                       // cruceta deslizante
    const dpad = $('#dpad');
    let idActivo = null;
    const flechas = { up: dpad.querySelector('.f-up'), down: dpad.querySelector('.f-down'),
                      left: dpad.querySelector('.f-left'), right: dpad.querySelector('.f-right') };
    function aplicar(ev) {
      const r = dpad.getBoundingClientRect();
      const dx = (ev.clientX - (r.left + r.width / 2)) / r.width * 2;
      const dy = (ev.clientY - (r.top + r.height / 2)) / r.height * 2;
      const U = 0.28;
      const d = { up: dy < -U, down: dy > U, left: dx < -U, right: dx > U };
      for (const k in d) {
        if (est.b[k] !== d[k]) apretar(k, d[k]);
        flechas[k].classList.toggle('on', d[k]);
      }
    }
    function soltar() {
      idActivo = null;
      for (const k of ['up','down','left','right']) {
        apretar(k, false);
        flechas[k].classList.remove('on');
      }
    }
    dpad.addEventListener('pointerdown', ev => {
      if (idActivo !== null) return;
      idActivo = ev.pointerId;
      try { dpad.setPointerCapture(ev.pointerId); } catch {}
      aplicar(ev); ocultarHint();
      ev.preventDefault();
    });
    dpad.addEventListener('pointermove', ev => { if (ev.pointerId === idActivo) { aplicar(ev); ev.preventDefault(); } });
    for (const e of ['pointerup','pointercancel']) {
      dpad.addEventListener(e, ev => { if (ev.pointerId === idActivo) soltar(); });
    }
  })();

  const z = v => Math.abs(v) < ZONA_MUERTA ? 0 : v;

  function estadoActual() {
    return {
      t:'in',
      ls:[+z(sticks.ls[0]).toFixed(3), +z(sticks.ls[1]).toFixed(3)],
      rs:[+z(sticks.rs[0]).toFixed(3), +z(sticks.rs[1]).toFixed(3)],
      lt:+est.lt.toFixed(2),
      rt:+est.rt.toFixed(2),
      b: Object.assign({}, est.b)
    };
  }

  /* ══════════════════ MODO MIDI ══════════════════ */
  function paginaActual() {
    if (!mapa || !mapa.paginas || !mapa.paginas.length) return null;
    return mapa.paginas[clamp(pagina, 0, mapa.paginas.length - 1)];
  }

  function pintarPaginas() {
    const cont = $('#midi-paginas');
    cont.innerHTML = '';
    if (!mapa) return;
    mapa.paginas.forEach((p, i) => {
      const d = document.createElement('div');
      d.className = 'pag' + (i === pagina ? ' sel' : '');
      d.textContent = p.nombre || `BANCO ${i + 1}`;
      d.addEventListener('pointerdown', ev => {
        ev.preventDefault();
        pagina = i;
        pintarPaginas(); pintarBotonera();
      });
      cont.appendChild(d);
    });
  }

  function pintarBotonera() {
    const pag = paginaActual();
    const cont = $('#midi-botones');
    const contF = $('#midi-faders');
    cont.innerHTML = ''; contF.innerHTML = '';
    if (!pag) return;

    for (const b of (pag.botones || [])) {
      const d = document.createElement('div');
      d.className = 'mbot' + (toggles[b.id] ? ' on' : '');
      d.style.borderColor = b.color || '';
      d.style.boxShadow = toggles[b.id] ? '' : `inset 0 0 26px ${(b.color || '#7aa2ff')}22`;
      d.innerHTML = `<span>${b.etiqueta || '—'}</span>`;
      d.title = `${b.tipo.toUpperCase()} ${b.num} · ch ${b.canal} · ${b.modo}`;

      let activo = false;
      const on = ev => {
        if (activo) return;
        activo = true;
        try { d.setPointerCapture(ev.pointerId); } catch {}
        enviar({ t:'midi', accion:'press', id:b.id });
        if (b.modo !== 'toggle') d.classList.add('on');
        if (navigator.vibrate) { try { navigator.vibrate(10); } catch {} }
        ev.preventDefault(); ev.stopPropagation();
      };
      const off = ev => {
        if (!activo) return;
        activo = false;
        enviar({ t:'midi', accion:'release', id:b.id });
        if (b.modo !== 'toggle') d.classList.remove('on');
        if (ev) ev.preventDefault();
      };
      d.addEventListener('pointerdown', on);
      for (const e of ['pointerup','pointercancel']) d.addEventListener(e, off);
      d.addEventListener('contextmenu', e => e.preventDefault());
      cont.appendChild(d);
    }

    for (const f of (pag.faders || [])) {
      const caja = document.createElement('div');
      caja.className = 'mfader';
      caja.innerHTML = `<div class="val">0</div><div class="riel"><i class="relleno"></i></div><div class="etq">${f.etiqueta || '—'}</div>`;
      const riel = caja.querySelector('.riel');
      const relleno = caja.querySelector('.relleno');
      const val = caja.querySelector('.val');
      let idActivo = null, ultimo = -1, ultimoEnvio = 0;

      const aplicar = (ev, forzar) => {
        const r = riel.getBoundingClientRect();
        const v = clamp(Math.round((1 - (ev.clientY - r.top) / r.height) * 127), 0, 127);
        relleno.style.height = (v / 127 * 100).toFixed(1) + '%';
        val.textContent = v;
        const ahora = performance.now();
        if (v !== ultimo && (forzar || ahora - ultimoEnvio > 25)) {
          ultimo = v; ultimoEnvio = ahora;
          enviar({ t:'midi', accion:'cc', id:f.id, valor:v });
        }
      };
      riel.addEventListener('pointerdown', ev => {
        idActivo = ev.pointerId;
        try { riel.setPointerCapture(ev.pointerId); } catch {}
        aplicar(ev, true); ev.preventDefault();
      });
      riel.addEventListener('pointermove', ev => { if (ev.pointerId === idActivo) { aplicar(ev); ev.preventDefault(); } });
      for (const e of ['pointerup','pointercancel']) {
        riel.addEventListener(e, ev => { if (ev.pointerId === idActivo) idActivo = null; });
      }
      riel.addEventListener('contextmenu', e => e.preventDefault());
      caja.dataset.fader = f.id;
      contF.appendChild(caja);
    }
  }

  function infoMidi(datos) {
    const partes = [];
    if (datos && datos.puerto) partes.push(`puerto: ${datos.puerto}`);
    else if (datos && datos.disponible === false) partes.push('sin puerto MIDI en la PC');
    const pag = paginaActual();
    if (pag) partes.push(`banco: ${pag.nombre}`);
    if (mapa && mapa.puerto) partes.push(`config: ${mapa.puerto}`);
    $('#midi-info').textContent = partes.join('  ·  ') || 'MIDI';
    $('#sinmidi').hidden = !(datos && datos.disponible === false);
  }

  function setModo(nuevo, avisar = true) {
    if (nuevo === modo) return;
    modo = nuevo;
    $('#capa-joy').hidden = (modo !== 'joy');
    $('#capa-midi').hidden = (modo !== 'midi');
    $('#mJoy').classList.toggle('sel', modo === 'joy');
    $('#mMidi').classList.toggle('sel', modo === 'midi');
    if (modo === 'midi') {
      soltarTodoLocal();                 // dejar el mando virtual en neutro
      if (avisar) enviar({ t:'soltar' });
      pintarPaginas(); pintarBotonera(); ocultarHint();
    } else {
      for (const k in toggles) delete toggles[k];
      if (avisar) enviar({ t:'midi-panic' });
    }
    if (avisar) enviar({ t:'modo', modo });
  }

  /* ══════════════════ conexión ══════════════════ */
  function conectar() {
    if (ws && (ws.readyState === 0 || ws.readyState === 1)) return;
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    try { ws = new WebSocket(`${proto}://${location.host}/ws`); }
    catch { return programarReintento(); }

    ws.onopen = () => {
      conectado = true; reintento = 500;
      $('#dot').classList.add('on');
      $('#txt').textContent = 'conectado';
      ws.send(JSON.stringify({ t:'hello', role:'pad', nombre: navigator.platform || 'celular' }));
      sucio = modo === 'joy';
      despertarYFullscreen();
    };

    ws.onmessage = ev => {
      let m; try { m = JSON.parse(ev.data); } catch { return; }
      if (m.t === 'hola') {
        $('#sinmando').hidden = !!m.mando;
        if (!m.mando) $('#txt').textContent = 'PC sin mando';
        if (m.mapa) { mapa = m.mapa; pintarPaginas(); pintarBotonera(); }
        if (m.toggles) { for (const k in m.toggles) toggles[k] = m.toggles[k]; pintarBotonera(); }
        infoMidi({ disponible: m.midi, puerto: m.puerto_midi });
        if (m.modo && m.modo !== modo) setModo(m.modo, false);
      } else if (m.t === 'mapa') {
        mapa = m.mapa;
        pintarPaginas(); pintarBotonera();
        infoMidi({ disponible: m.midi, puerto: m.puerto_midi });
      } else if (m.t === 'midi-estado') {
        toggles[m.id] = !!m.on;
        const pag = paginaActual();
        if (pag) {
          const i = (pag.botones || []).findIndex(b => b.id === m.id);
          const el = $('#midi-botones').children[i];
          if (el) el.classList.toggle('on', !!m.on);
        }
      } else if (m.t === 'midi-estado-reset') {
        for (const k in toggles) delete toggles[k];
        pintarBotonera();
      } else if (m.t === 'pong' && typeof m.ts === 'number') {
        latencia = Math.round(performance.now() - m.ts);
        $('#ping').textContent = latencia + ' ms';
      }
    };

    ws.onclose = () => {
      conectado = false;
      $('#dot').classList.remove('on');
      $('#txt').textContent = 'reconectando…';
      $('#ping').textContent = '';
      soltarTodoLocal();
      programarReintento();
    };
    ws.onerror = () => { try { ws.close(); } catch {} };
  }

  function programarReintento() {
    setTimeout(conectar, reintento = Math.min(reintento * 1.6, 4000));
  }

  function enviar(o) {
    if (conectado && ws && ws.readyState === 1) {
      try { ws.send(JSON.stringify(o)); return true; } catch {}
    }
    return false;
  }

  /* ══════════════════ bucle de envío ══════════════════ */
  let ultimoEnvio = 0;
  setInterval(() => {
    for (const k of ['lt','rt']) {                       // rampa de gatillos
      const obj = objetivo[k];
      const vel = obj > est[k] ? 0.34 : 0.5;
      const nuevo = est[k] + (obj - est[k]) * vel;
      if (Math.abs(nuevo - est[k]) > 0.004) { est[k] = clamp(nuevo, 0, 1); sucio = true; }
      else if (est[k] !== obj) { est[k] = obj; sucio = true; }
      const barra = document.querySelector(`#b${k === 'lt' ? 'LT' : 'RT'} .barra`);
      if (barra) barra.style.width = (est[k] * 100).toFixed(0) + '%';
    }
    if (modo !== 'joy') return;                          // en modo MIDI no hay joystick
    const ahora = Date.now();
    if (sucio || ahora - ultimoEnvio > 1000) {
      if (enviar(estadoActual())) { sucio = false; ultimoEnvio = ahora; }
    }
  }, 25);

  setInterval(() => enviar({ t:'ping', ts: performance.now() }), 2500);

  function soltarTodoLocal() {
    for (const k of BOTONES) apretar(k, false);
    objetivo.lt = objetivo.rt = 0; est.lt = est.rt = 0;
    sticks.ls = [0,0]; sticks.rs = [0,0];
    $('#knobL').style.transform = 'translate(-50%,-50%)';
    $('#knobR').style.transform = 'translate(-50%,-50%)';
    document.querySelectorAll('.flecha.on').forEach(f => f.classList.remove('on'));
    document.querySelectorAll('.gatillo .barra').forEach(b => b.style.width = '0%');
    document.querySelectorAll('.btn.act, .mbot.on').forEach(b => b.classList.remove('on'));
  }

  /* ══════════════════ switch de modo ══════════════════ */
  for (const el of document.querySelectorAll('#modos .modo')) {
    el.addEventListener('pointerdown', ev => {
      setModo(el.dataset.modo);
      ev.preventDefault(); ev.stopPropagation();
    });
  }
  $('#midiPanic').addEventListener('pointerdown', ev => {
    enviar({ t:'midi-panic' });
    for (const k in toggles) delete toggles[k];
    pintarBotonera();
    const b = $('#midiPanic');
    b.classList.add('act');
    setTimeout(() => b.classList.remove('act'), 250);
    ev.preventDefault();
  });

  /* ══════════════════ pantalla despierta + fullscreen ══════════════════ */
  let wakeLock = null;
  async function pedirWakeLock() {
    try { if ('wakeLock' in navigator) wakeLock = await navigator.wakeLock.request('screen'); } catch {}
  }
  function despertarYFullscreen() {
    pedirWakeLock();
    const el = document.documentElement;
    if (!document.fullscreenElement && el.requestFullscreen) {
      el.requestFullscreen({ navigationUI:'hide' }).catch(() => {});
    } else if (el.webkitRequestFullscreen && !document.webkitFullscreenElement) {
      try { el.webkitRequestFullscreen(); } catch {}
    }
  }
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
      if (!conectado) conectar();
      pedirWakeLock();
    }
  });
  document.addEventListener('pointerdown', despertarYFullscreen, { once:true });

  /* ══════════════════ orientación ══════════════════ */
  function chequearOrientacion() {
    $('#rotate').classList.toggle('on', window.innerHeight > window.innerWidth && window.innerWidth < 620);
  }
  window.addEventListener('resize', chequearOrientacion);
  window.addEventListener('orientationchange', () => setTimeout(chequearOrientacion, 250));
  chequearOrientacion();

  /* ══════════════════ hint ══════════════════ */
  let hintOculto = false;
  function ocultarHint() {
    if (hintOculto) return;
    hintOculto = true;
    const h = $('#hint');
    if (h) { h.style.opacity = '0'; setTimeout(() => h.remove(), 700); }
  }
  setTimeout(ocultarHint, 7000);

  /* ══════════════════ anti-zoom / anti-pinch ══════════════════ */
  document.addEventListener('touchstart', e => { if (e.touches.length > 1) e.preventDefault(); }, { passive:false });
  document.addEventListener('touchmove',  e => { if (e.touches.length > 1) e.preventDefault(); }, { passive:false });
  let ultimoTap = 0;
  document.addEventListener('touchend', e => {
    const ahora = Date.now();
    if (ahora - ultimoTap < 320 && e.touches.length === 0) e.preventDefault();
    ultimoTap = ahora;
  }, { passive:false });
  for (const ev of ['gesturestart','gesturechange','gestureend']) {
    document.addEventListener(ev, e => e.preventDefault(), { passive:false });
  }
  document.addEventListener('dblclick', e => e.preventDefault(), { passive:false });
  document.addEventListener('contextmenu', e => e.preventDefault());
  window.addEventListener('beforeunload', () => { enviar({ t:'soltar' }); enviar({ t:'midi-panic' }); });

  conectar();
})();
