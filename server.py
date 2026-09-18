#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Xbox 360 WebPad -- servidor
===========================

Corre en la PC donde esta el juego (Unreal Engine u otro).  Hace tres cosas:

  1. Crea un mando **Xbox 360 virtual** (ViGEmBus/XInput) que el juego ve como
     un joystick fisico conectado por USB.
  2. Sirve el **pad web** (celular) y el **panel del operador** (esta PC).
  3. Escucha por WebSocket lo que hace el celular y lo vuelca al mando virtual,
     en tiempo real.

Uso:
    python server.py                 # puerto 8790
    python server.py --port 9000 --open
    python server.py --no-pad        # sin driver: sirve la web y muestra el estado

Rutas:
    /            panel del operador (QR + estado en vivo)
    /pad         mando para el celular
    /qr.svg      QR (SVG) de la URL del pad
    /api/net     IPs de la red local
    /api/estado  estado actual del mando virtual
    /api/salud   {ok, mando}
    /ws          WebSocket (pad <-> servidor <-> panel)
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import socket
import sys
import time
import webbrowser
from pathlib import Path

from aiohttp import WSMsgType, web

import qrcode
import qrcode.image.svg

# En el runtime portable (Python embebido) el directorio del script NO entra en
# sys.path, asi que lo agregamos a mano para que encuentre mando_virtual.py.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mando_virtual import BOTONES, MandoVirtual   # noqa: E402

WEB_DIR = Path(__file__).resolve().parent / "web"

# ── consola UTF-8 en Windows (para el QR de bloques) ───────────────────────
for flujo in (sys.stdout, sys.stderr):
    try:
        flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ── red ────────────────────────────────────────────────────────────────────
def ips_locales() -> list[dict]:
    """IPv4 no-internas, ordenadas por probabilidad de ser la red del celular."""
    out: list[dict] = []
    try:
        import psutil  # opcional
        for iface, addrs in psutil.net_if_addrs().items():
            for a in addrs:
                if a.family.name == "AF_INET" and not a.address.startswith("127."):
                    out.append({"ip": a.address, "iface": iface})
    except Exception:
        # sin psutil: ipconfig --route no esta en stdlib, usamos el truco del socket
        out = _ips_por_socket()
    if not out:
        out = _ips_por_socket()
    unicos: dict[str, dict] = {}
    for it in out:
        unicos.setdefault(it["ip"], it)
    lista = list(unicos.values())

    def peso(it: dict) -> tuple:
        ip = it["ip"]
        if ip.startswith("192.168."):
            return (0, ip)
        if ip.startswith("10."):
            return (1, ip)
        if ip.startswith("172."):
            return (2, ip)
        return (3, ip)

    lista.sort(key=peso)
    return lista


def _ips_por_socket() -> list[dict]:
    """Descubre la IP de salida abriendo un socket UDP (no manda nada)."""
    out = []
    for destino in (("8.8.8.8", 80), ("1.1.1.1", 80)):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.4)
            s.connect(destino)
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith("127."):
                out.append({"ip": ip, "iface": "red principal"})
                break
        except Exception:
            continue
    try:
        host = socket.gethostname()
        for info in socket.getaddrinfo(host, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                out.append({"ip": ip, "iface": host})
    except Exception:
        pass
    return out


def ip_principal() -> str:
    ips = ips_locales()
    return ips[0]["ip"] if ips else "127.0.0.1"


# ── QR ─────────────────────────────────────────────────────────────────────
def qr_svg(datos: str) -> bytes:
    img = qrcode.make(datos, image_factory=qrcode.image.svg.SvgPathImage, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue()


def imprimir_qr_consola(datos: str) -> None:
    qr = qrcode.QRCode(border=1)
    qr.add_data(datos)
    qr.make(fit=True)
    qr.print_ascii(invert=True)


# ── aplicacion ─────────────────────────────────────────────────────────────
class App:
    """Estado compartido: mando virtual, celulares conectados y paneles."""

    def __init__(self, mando: MandoVirtual, puerto: int, timeout_pad: float = 3.0):
        self.mando = mando
        self.puerto = puerto
        self.timeout_pad = timeout_pad
        self.pads: dict[web.WebSocketResponse, dict] = {}
        self.paneles: set[web.WebSocketResponse] = set()
        self.ultimo_input = 0.0
        self.mensajes_pad = 0
        self.ultimo_aviso = 0.0
        self.arranque = time.monotonic()

    # ── estado que se manda al panel ───────────────────────────────────────
    def instantanea(self) -> dict:
        ahora = time.monotonic()
        # sin celulares conectados no hay "señal" que reportar
        hace = None if (not self.pads or not self.ultimo_input) else round((ahora - self.ultimo_input) * 1000)
        return {
            "t": "estado",
            "mando": self.mando.disponible,
            "error": self.mando.error,
            "conectados": len(self.pads),
            "pads": [
                {"ip": d.get("ip", "?"), "nombre": d.get("nombre", "celular")}
                for d in self.pads.values()
            ],
            "senal_hace_ms": hace,
            "mensajes": self.mensajes_pad,
            "estado": self.mando.estado,
            "botones": BOTONES,
            "uptime_s": round(ahora - self.arranque, 1),
        }

    async def difundir_paneles(self, msg: dict | None = None) -> None:
        if not self.paneles:
            return
        datos = json.dumps(msg or self.instantanea())
        muertos = []
        for ws in self.paneles:
            try:
                await ws.send_str(datos)
            except Exception:
                muertos.append(ws)
        for ws in muertos:
            self.paneles.discard(ws)

    # ── WebSocket ──────────────────────────────────────────────────────────
    async def ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=20, max_msg_size=8192)
        await ws.prepare(request)
        ip = request.remote or "?"
        rol = None

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        m = json.loads(msg.data)
                    except Exception:
                        continue
                    if not isinstance(m, dict):
                        continue

                    # ── saludo ─────────────────────────────────────────────
                    if m.get("t") == "hello":
                        rol = "panel" if m.get("role") == "panel" else "pad"
                        if rol == "panel":
                            self.paneles.add(ws)
                            await ws.send_str(json.dumps(self.instantanea()))
                            print(f"[panel] conectado desde {ip}", flush=True)
                        else:
                            self.pads[ws] = {
                                "ip": ip,
                                "nombre": str(m.get("nombre") or "celular")[:32],
                                "ultimo": time.monotonic(),
                            }
                            self.ultimo_input = time.monotonic()
                            await ws.send_str(json.dumps({
                                "t": "hola",
                                "mando": self.mando.disponible,
                                "botones": BOTONES,
                                "pad": True,
                            }))
                            print(f"[pad] {ip} conectado  ({len(self.pads)} celular/es)", flush=True)
                            await self.difundir_paneles()
                        continue

                    # ── mensajes del celular ───────────────────────────────
                    if rol == "pad":
                        if ws in self.pads:
                            self.pads[ws]["ultimo"] = time.monotonic()
                        if m.get("t") == "in":
                            self.ultimo_input = time.monotonic()
                            self.mensajes_pad += 1
                            self.mando.actualizar(m)
                        elif m.get("t") == "ping":
                            await ws.send_str(json.dumps({"t": "pong", "ts": m.get("ts")}))
                        elif m.get("t") == "soltar":
                            self.mando.neutro()
                            self.mando.latir(forzar=True)
                        continue

                    # ── mensajes del panel (esta PC) ───────────────────────
                    if rol == "panel":
                        t = m.get("t")
                        if t == "soltar":
                            self.mando.neutro()
                            self.mando.latir(forzar=True)
                            print("[panel] soltar todo", flush=True)
                        elif t == "probar":
                            await self.pulso_prueba()
                        elif t == "salud":
                            await ws.send_str(json.dumps(self.instantanea()))
                        continue

                elif msg.type == WSMsgType.ERROR:
                    break
        finally:
            self.paneles.discard(ws)
            if ws in self.pads:
                self.pads.pop(ws, None)
                print(f"[pad] {ip} desconectado ({len(self.pads)} activo/s)", flush=True)
                if not self.pads:
                    self.mando.neutro()
                    self.mando.latir(forzar=True)
                    print("[mando] sin celulares: estado liberado", flush=True)
                await self.difundir_paneles()
        return ws

    async def pulso_prueba(self) -> None:
        """Aprieta A durante 250 ms para comprobar que el juego responde."""
        print("[panel] pulso de prueba (A)", flush=True)
        self.mando.actualizar({"b": ["a"]})
        self.mando.latir(forzar=True)
        await asyncio.sleep(0.25)
        self.mando.actualizar({"b": {k: False for k in BOTONES}})
        self.mando.latir(forzar=True)

    # ── tareas de fondo ────────────────────────────────────────────────────
    async def tarea_latido(self) -> None:
        """Vuelca el estado al mando virtual (rapido y parejo)."""
        while True:
            self.mando.latir()
            await asyncio.sleep(0.008)

    async def tarea_guardian(self) -> None:
        """Dos tareas: liberar todo si el celular se calla y podar pads caidos."""
        while True:
            await asyncio.sleep(0.5)
            ahora = time.monotonic()

            # Pads que dejaron de dar señales (pantalla apagada, app cerrada,
            # wifi cortado sin cierre limpio): se sacan de la lista.
            vencidos = [ws for ws, d in self.pads.items()
                        if ahora - d.get("ultimo", ahora) > 15.0]
            for ws in vencidos:
                info = self.pads.pop(ws, None)
                try:
                    await ws.close()
                except Exception:
                    pass
                print(f"[pad] {info.get('ip', '?') if info else '?'} "
                      f"sin señales: desconectado", flush=True)
            if vencidos:
                await self.difundir_paneles()

            if self.pads and self.ultimo_input:
                silencio = ahora - self.ultimo_input
                if silencio > self.timeout_pad:
                    self.mando.neutro()
                    self.mando.latir(forzar=True)
                    if ahora - self.ultimo_aviso > 10:
                        self.ultimo_aviso = ahora
                        print(f"[mando] {silencio:.1f}s sin señal del celular: liberado", flush=True)
                    self.ultimo_input = ahora

    async def tarea_paneles(self) -> None:
        """Manda el estado al panel ~10 veces por segundo."""
        while True:
            await self.difundir_paneles()
            await asyncio.sleep(0.1)

    # ── HTTP ───────────────────────────────────────────────────────────────
    async def panel(self, request: web.Request) -> web.StreamResponse:
        return web.FileResponse(WEB_DIR / "index.html")

    async def pad(self, request: web.Request) -> web.StreamResponse:
        return web.FileResponse(WEB_DIR / "pad.html")

    async def qr(self, request: web.Request) -> web.StreamResponse:
        destino = request.query.get("d")
        if not destino:
            destino = f"http://{ip_principal()}:{self.puerto}/pad"
        return web.Response(body=qr_svg(destino), content_type="image/svg+xml",
                            headers={"cache-control": "no-store"})

    async def api_net(self, request: web.Request) -> web.StreamResponse:
        return web.json_response({
            "ips": ips_locales(),
            "puerto": self.puerto,
            "host": request.host,
        })

    async def api_estado(self, request: web.Request) -> web.StreamResponse:
        return web.json_response(self.instantanea())

    async def api_salud(self, request: web.Request) -> web.StreamResponse:
        return web.json_response({"ok": True, "mando": self.mando.disponible,
                                  "error": self.mando.error, "pads": len(self.pads)})


def construir_app(mando: MandoVirtual, puerto: int, timeout_pad: float) -> web.Application:
    app_estado = App(mando, puerto, timeout_pad)

    @web.middleware
    async def sin_cache(request, handler):
        resp = await handler(request)
        if isinstance(resp, web.FileResponse):
            resp.headers["cache-control"] = "no-cache"
        return resp

    app = web.Application(middlewares=[sin_cache])
    app["estado"] = app_estado

    app.router.add_get("/", app_estado.panel)
    app.router.add_get("/pad", app_estado.pad)
    app.router.add_get("/qr.svg", app_estado.qr)
    app.router.add_get("/api/net", app_estado.api_net)
    app.router.add_get("/api/estado", app_estado.api_estado)
    app.router.add_get("/api/salud", app_estado.api_salud)
    app.router.add_get("/ws", app_estado.ws)
    app.router.add_static("/static", WEB_DIR, show_index=False)

    async def inicio(app: web.Application) -> None:
        # El celular corta la conexión seguido (pantalla que se apaga, WiFi que
        # salta). En Windows eso genera tracebacks de ConnectionResetError que
        # ensucian la ventana: los silenciamos.
        loop = asyncio.get_running_loop()
        anterior = loop.get_exception_handler()

        def manejador(loop, contexto):
            exc = contexto.get("exception")
            if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
                return
            if anterior is not None:
                anterior(loop, contexto)
            else:
                loop.default_exception_handler(contexto)

        loop.set_exception_handler(manejador)
        app["tareas"] = [
            asyncio.create_task(app_estado.tarea_latido()),
            asyncio.create_task(app_estado.tarea_guardian()),
            asyncio.create_task(app_estado.tarea_paneles()),
        ]

    async def cierre(app: web.Application) -> None:
        for t in app.get("tareas", []):
            t.cancel()
        mando.neutro()
        mando.latir(forzar=True)
        mando.cerrar()

    app.on_startup.append(inicio)
    app.on_cleanup.append(cierre)
    return app


# ── arranque ───────────────────────────────────────────────────────────────
def banner(puerto: int, ip: str) -> None:
    print("")
    print("  ==============================================================")
    print("   Xbox 360 WebPad  --  mando virtual por celular")
    print("  ==============================================================")
    print(f"   Panel (esta PC)    :  http://127.0.0.1:{puerto}/")
    print(f"   Mando (celular)    :  http://{ip}:{puerto}/pad")
    print("")
    print("   Escanea este QR desde el celular (misma red wifi):")
    print("")
    try:
        imprimir_qr_consola(f"http://{ip}:{puerto}/pad")
    except Exception:
        print(f"   (no se pudo dibujar el QR; usa la URL de arriba)")
    print("")
    print("   Deja esta ventana abierta mientras jugas.")
    print("   Para liberar todo: Ctrl+C  (o el boton del panel).")
    print("")


def main() -> int:
    ap = argparse.ArgumentParser(description="Mando Xbox 360 virtual controlado por celular")
    ap.add_argument("--port", "--puerto", dest="puerto", type=int, default=8790)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--ip", default=None, help="fuerza la IP que va en el QR")
    ap.add_argument("--no-pad", action="store_true",
                    help="no crea el mando virtual (solo web/estado, para probar)")
    ap.add_argument("--open", action="store_true", help="abre el panel en el navegador")
    ap.add_argument("--timeout-pad", type=float, default=3.0,
                    help="segundos sin señal del celular antes de liberar todo")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    mando = MandoVirtual(verbose=not args.quiet, conectar=not args.no_pad)
    if args.no_pad:
        print("[mando] modo --no-pad: no se crea el mando virtual")

    ip = args.ip or ip_principal()
    app = construir_app(mando, args.puerto, args.timeout_pad)

    if not args.quiet:
        banner(args.puerto, ip)
        if not mando.disponible:
            print(f"  ATENCION: el mando virtual no esta activo ({mando.error})")
            print("  Revisa que el driver ViGEmBus este instalado.")
            print("")

    if args.open:
        try:
            webbrowser.open(f"http://127.0.0.1:{args.puerto}/")
        except Exception:
            pass

    try:
        web.run_app(app, host=args.host, port=args.puerto,
                    print=None, access_log=None)
    except OSError as exc:
        print(f"\n  No se pudo abrir el puerto {args.puerto}: {exc}")
        print("  Proba con otro puerto:  python server.py --port 8791\n")
        return 2
    except KeyboardInterrupt:
        pass
    finally:
        mando.cerrar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
