/* ==========================================================================
   Mando Xbox 360 web — cliente (celular)
   Manda el estado completo del mando por WebSocket al servidor de la PC.
   ========================================================================== */
(() => {
  'use strict';

  const $ = s => document.querySelector(s);
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const ZONA_MUERTA = 0.07;

  /* ── estado del mando ─────────────────────────────────────────────────── */
  const BOTONES = ['a','b','x','y','lb','rb','start','back','guide','l3','r3','up','down','left','right'];
  const est = { ls:[0,0], rs:[0,0], lt:0, rt:0, b:{} };
  for (const k of BOTONES) est.b[k] = false;

  const objetivo = { lt:0, rt:0 };          // gatillos: rampa analógica
  let sucio = true;                          // hay cambios para mandar
  let ws = null, conectado = false, reintento = 500;

  /* ── conexión ─────────────────────────────────────────────────────────── */
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
      sucio = true;
      despertarYFullscreen();
    };

    ws.onmessage = ev => {
      let m; try { m = JSON.parse(ev.data); } catch { return; }
      if (m.t === 'hola') {
        $('#sinmando').hidden = !!m.mando;
        if (!m.mando) $('#txt').textContent = 'PC sin mando';
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

  let latencia = 0;

  /* ── feedback visual ──────────────────────────────────────────────────── */
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

  /* ── botones digitales ────────────────────────────────────────────────── */
  function engancharBoton(el) {
    const nombre = el.dataset.btn;
    const soltar = () => apretar(nombre, false);
    el.addEventListener('pointerdown', ev => {
      try { el.setPointerCapture(ev.pointerId); } catch {}
      apretar(nombre, true);
      ev.preventDefault(); ev.stopPropagation();
    });
    for (const e of ['pointerup','pointercancel']) {
      el.addEventListener(e, ev => { soltar(); ev.preventDefault(); });
    }
    el.addEventListener('contextmenu', e => e.preventDefault());
  }
  for (const el of document.querySelectorAll('[data-btn]')) {
    if (el.id !== 'bLT' && el.id !== 'bRT') engancharBoton(el);
  }

  /* ── gatillos (analógicos) ────────────────────────────────────────────── */
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

  /* ── sticks analógicos (multitáctil, cada uno su pointerId) ───────────── */
  const sticks = [];

  function crearStick(zoneSel, knobSel) {
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
      const [x, y] = pos(ev);
      sticks[zona.dataset.eje] = [x, y];
      sucio = true; ocultarHint();
      ev.preventDefault();
    });

    zona.addEventListener('pointermove', ev => {
      if (ev.pointerId !== idActivo) return;
      const [x, y] = pos(ev);
      movido += Math.hypot(x, y);
      sticks[zona.dataset.eje] = [x, y];
      sucio = true; ev.preventDefault();
    });

    for (const e of ['pointerup','pointercancel']) {
      zona.addEventListener(e, ev => {
        if (ev.pointerId !== idActivo) return;
        idActivo = null;
        knob.style.transform = 'translate(-50%,-50%)';
        sticks[zona.dataset.eje] = [0, 0];
        sucio = true;
        // toque corto casi sin movimiento = click del stick (L3 / R3)
        if (movido < 0.35 && performance.now() - t0 < 260) {
          const boton = zona.dataset.click;
          apretar(boton, true);
          setTimeout(() => apretar(boton, false), 130);
        }
      });
    }
    zona.addEventListener('contextmenu', e => e.preventDefault());
  }

  $('#zStickL').dataset.eje = 'ls';  $('#zStickL').dataset.click = 'l3';
  $('#zStickR').dataset.eje = 'rs';  $('#zStickR').dataset.click = 'r3';
  sticks.ls = [0,0]; sticks.rs = [0,0];
  crearStick('#zStickL', '#knobL');
  crearStick('#zStickR', '#knobR');

  /* ── D-Pad (deslizante, admite diagonales) ────────────────────────────── */
  (() => {
    const dpad = $('#dpad');
    let idActivo = null;
    const flechas = { up: dpad.querySelector('.f-up'), down: dpad.querySelector('.f-down'),
                      left: dpad.querySelector('.f-left'), right: dpad.querySelector('.f-right') };

    function aplicar(ev) {
      const r = dpad.getBoundingClientRect();
      const dx = (ev.clientX - (r.left + r.width / 2)) / r.width * 2;   // -1..1
      const dy = (ev.clientY - (r.top + r.height / 2)) / r.height * 2;
      const U = 0.28;                                                    // umbral
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

  /* ── bucle de envío ───────────────────────────────────────────────────── */
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

  let ultimoEnvio = 0;
  setInterval(() => {
    // rampa de los gatillos
    for (const k of ['lt','rt']) {
      const obj = objetivo[k];
      const vel = obj > est[k] ? 0.34 : 0.5;
      const nuevo = est[k] + (obj - est[k]) * vel;
      if (Math.abs(nuevo - est[k]) > 0.004) { est[k] = clamp(nuevo, 0, 1); sucio = true; }
      else if (est[k] !== obj) { est[k] = obj; sucio = true; }
      const barra = document.querySelector(`#b${k === 'lt' ? 'LT' : 'RT'} .barra`);
      if (barra) barra.style.width = (est[k] * 100).toFixed(0) + '%';
    }
    const ahora = Date.now();
    // latido: reenvía el estado completo aunque no haya cambios (mantiene vivo
    // el watchdog del servidor cuando el jugador sostiene un stick quieto)
    if (sucio || ahora - ultimoEnvio > 1000) {
      if (enviar(estadoActual())) { sucio = false; ultimoEnvio = ahora; }
    }
  }, 25);

  setInterval(() => enviar({ t:'ping', ts: performance.now() }), 2500);

  function soltarTodoLocal() {
    for (const k of BOTONES) apretar(k, false);
    objetivo.lt = objetivo.rt = 0; est.lt = est.rt = 0;
    sticks.ls = [0,0]; sticks.rs = [0,0];
    objetivo.lt = 0; objetivo.rt = 0;
    $('#knobL').style.transform = 'translate(-50%,-50%)';
    $('#knobR').style.transform = 'translate(-50%,-50%)';
    document.querySelectorAll('.flecha.on').forEach(f => f.classList.remove('on'));
    document.querySelectorAll('.gatillo .barra').forEach(b => b.style.width = '0%');
    document.querySelectorAll('.btn.act').forEach(b => b.classList.remove('act'));
  }

  /* ── pantalla despierta + pantalla completa ───────────────────────────── */
  let wakeLock = null;
  async function pedirWakeLock() {
    try {
      if ('wakeLock' in navigator) wakeLock = await navigator.wakeLock.request('screen');
    } catch {}
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

  /* ── orientación ──────────────────────────────────────────────────────── */
  function chequearOrientacion() {
    $('#rotate').classList.toggle('on', window.innerHeight > window.innerWidth && window.innerWidth < 620);
  }
  window.addEventListener('resize', chequearOrientacion);
  window.addEventListener('orientationchange', () => setTimeout(chequearOrientacion, 250));
  chequearOrientacion();

  /* ── hint ─────────────────────────────────────────────────────────────── */
  let hintOculto = false;
  function ocultarHint() {
    if (hintOculto) return;
    hintOculto = true;
    const h = $('#hint'); h.style.opacity = '0';
    setTimeout(() => h.remove(), 700);
  }
  setTimeout(ocultarHint, 7000);

  /* ── anti-zoom / anti-pinch / anti-doble-toque ────────────────────────── */
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
  window.addEventListener('beforeunload', () => enviar({ t:'soltar' }));

  /* ── arranque ─────────────────────────────────────────────────────────── */
  conectar();
})();
