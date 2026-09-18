# -*- coding: utf-8 -*-
"""
Prueba de punta a punta
=======================

Simula el celular (cliente WebSocket del pad), manda una secuencia de
controles y **lee XInput** despues de cada paso: es exactamente lo que ve
Unreal Engine.  Si todo pasa, el sistema completo funciona.

Requiere el servidor corriendo:
    .venv\\Scripts\\python.exe server.py
y despues, en otra ventana:
    .venv\\Scripts\\python.exe tools\\prueba_completa.py
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xinput_win import BITS, LectorXInput        # noqa: E402

try:
    import aiohttp
except ImportError:                               # pragma: no cover
    print("Falta aiohttp. Corré:  .venv\\Scripts\\python.exe -m pip install -r requirements.txt")
    sys.exit(1)


BOTONES_TODOS = list(BITS.keys())


def in_botones(*nombres: str) -> dict:
    """Mensaje de estado con esos botones apretados y el resto suelto."""
    return {"t": "in", "b": {k: (k in nombres) for k in BOTONES_TODOS}}


def pasos() -> list[dict]:
    return [
        {"nombre": "Todo suelto", "msg": {"t": "in", **in_botones(), "ls": [0, 0], "rs": [0, 0],
                                          "lt": 0, "rt": 0},
         "espera": {"botones_no": ["a", "b", "x", "y", "lb", "rb", "up", "down", "left", "right"],
                    "lt": (0, 3), "rt": (0, 3), "lx": (-1200, 1200), "ly": (-1200, 1200)}},

        {"nombre": "Boton A", "msg": {"t": "in", **in_botones("a")},
         "espera": {"botones": ["a"]}},

        {"nombre": "A + B + X + Y", "msg": {"t": "in", **in_botones("a", "b", "x", "y")},
         "espera": {"botones": ["a", "b", "x", "y"]}},

        {"nombre": "Hombros LB + RB", "msg": {"t": "in", **in_botones("lb", "rb")},
         "espera": {"botones": ["lb", "rb"]}},

        {"nombre": "Gatillo izquierdo al 100%", "msg": {"t": "in", **in_botones(), "lt": 1.0},
         "espera": {"lt": (250, 255)}},

        {"nombre": "Gatillo derecho al 50%", "msg": {"t": "in", **in_botones(), "rt": 0.5},
         "espera": {"rt": (118, 140)}},

        {"nombre": "Stick izq: derecha + arriba", "msg": {"t": "in", **in_botones(), "ls": [0.6, -0.45]},
         "espera": {"lx": (12000, 24000), "ly": (9000, 20000)}},

        {"nombre": "Stick izq: izquierda + abajo", "msg": {"t": "in", **in_botones(), "ls": [-0.8, 0.8]},
         "espera": {"lx": (-30000, -17000), "ly": (-30000, -17000)}},

        {"nombre": "Stick der: a la derecha", "msg": {"t": "in", **in_botones(), "rs": [0.9, 0]},
         "espera": {"rx": (22000, 32000), "ry": (-3000, 3000)}},

        {"nombre": "Cruceta: arriba + izquierda",
         "msg": {"t": "in", **in_botones("up", "left")},
         "espera": {"botones": ["up", "left"]}},

        {"nombre": "Clicks de stick L3 + R3", "msg": {"t": "in", **in_botones("l3", "r3")},
         "espera": {"botones": ["l3", "r3"]}},

        {"nombre": "START + BACK",
         "msg": {"t": "in", **in_botones("start", "back")},
         "espera": {"botones": ["start", "back"]}},

        {"nombre": "Soltar todo",
         "msg": {"t": "in", **in_botones(), "ls": [0, 0], "rs": [0, 0], "lt": 0, "rt": 0},
         "espera": {"botones_no": BOTONES_TODOS, "lt": (0, 3), "rt": (0, 3)}},
    ]


def evaluar(snap: dict, espera: dict) -> list[str]:
    fallos = []
    for clave, val in espera.items():
        if clave == "botones":
            for b in val:
                if b not in snap["botones"]:
                    fallos.append(f"falta {b.upper()}")
        elif clave == "botones_no":
            for b in val:
                if b in snap["botones"]:
                    fallos.append(f"{b.upper()} quedó apretado")
        else:
            lo, hi = val
            real = snap[clave]
            if not (lo <= real <= hi):
                fallos.append(f"{clave.upper()}={real} fuera de [{lo}, {hi}]")
    return fallos


def detectar_slot(lector: LectorXInput, pedido: int | None) -> int | None:
    activos = lector.slots_activos()
    if pedido is not None:
        return pedido if pedido in activos else None
    if not activos:
        return None
    return activos[0]


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="ws://127.0.0.1:8790/ws")
    ap.add_argument("--http", default="http://127.0.0.1:8790")
    ap.add_argument("--slot", type=int, default=None)
    ap.add_argument("--forzar", action="store_true",
                    help="corre aunque haya otros celulares conectados (resultados dudosos)")
    ap.add_argument("--espera", type=float, default=0.45,
                    help="segundos de espera tras cada paso (el servidor aplica a ~120 Hz)")
    args = ap.parse_args()

    lector = LectorXInput()
    slot = detectar_slot(lector, args.slot)
    if slot is None:
        print("No hay mando virtual activo. ¿Está corriendo el servidor y el driver ViGEmBus?")
        print("slots con mando:", lector.slots_activos())
        return 1
    print(f"Usando el slot XInput {slot}  (lo mismo que leería el juego)\n")

    async def esperar_pad_listo(timeout: float = 8.0) -> bool:
        """ViGEmBus 1.17 devuelve basura (pkt=0) hasta que el mando virtual emite
        su primer reporte real: esperamos dos lecturas estables con pkt != 0."""
        anterior = None
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            s = lector.snapshot(slot)
            if s and s["paquete"] != 0:
                firma = (s["paquete"], s["lx"], s["ly"], s["rx"], s["ry"],
                         s["lt"], s["rt"], tuple(s["botones"]))
                if anterior == firma:
                    return True
                anterior = firma
            else:
                anterior = None
            await asyncio.sleep(0.25)
        return False

    if not await esperar_pad_listo():
        print("  AVISO: el mando virtual no dio lecturas estables; "
              "los resultados pueden ser falsos.\n")

    ok = fallos_total = 0
    async with aiohttp.ClientSession() as sesion:
        try:
            ws = await sesion.ws_connect(args.url)
        except Exception as exc:
            print(f"No me pude conectar a {args.url}: {exc}")
            return 1

        async with ws:
            await ws.send_str(json.dumps({"t": "hello", "role": "pad", "nombre": "prueba-automatica"}))
            bienvenida = json.loads((await ws.receive()).data)
            print(f"El servidor dice: mando virtual = {bienvenida.get('mando')}\n")
            if not bienvenida.get("mando"):
                print("El servidor no tiene mando virtual activo.")
                return 1

            print(f"{'paso':<34} {'resultado':<10} detalle")
            print("-" * 78)

            # Si hay otro pad conectado (un celular real, otra pestaña) sus
            # latidos van a pisar lo que manda esta prueba: avisamos y frenamos.
            try:
                async with sesion.get(f"{args.http}/api/estado") as r:
                    datos = await r.json()
                cuantos = datos.get("conectados", 0)
                if cuantos > 1 and not args.forzar:
                    otros = ", ".join(f"{p.get('nombre', '?')} ({p.get('ip', '?')})"
                                      for p in datos.get("pads", []))
                    print(f"Hay {cuantos} pads conectados: {otros}")
                    print("Cerrá las otras pestañas/celulares y volvé a intentar,")
                    print("o corré con --forzar (los resultados pueden ser falsos).")
                    return 1
                if cuantos > 1:
                    print(f"  AVISO: hay {cuantos} pads conectados; los resultados "
                          f"pueden ser falsos (--forzar).\n")
            except Exception:
                pass
            for paso in pasos():
                await ws.send_str(json.dumps(paso["msg"]))
                await asyncio.sleep(args.espera)
                snap = lector.snapshot(slot)
                if snap is None:
                    print(f"{paso['nombre']:<34} {'FALLA':<10} el slot desapareció")
                    fallos_total += 1
                    continue
                fallos = evaluar(snap, paso["espera"])
                if fallos:
                    fallos_total += 1
                    print(f"{paso['nombre']:<34} {'FALLA':<10} {'; '.join(fallos)}")
                else:
                    ok += 1
                    detalle = f"[{','.join(snap['botones']) or '-'}] LT={snap['lt']} RT={snap['rt']} " \
                              f"LX={snap['lx']} LY={snap['ly']} RX={snap['rx']} RY={snap['ry']}"
                    print(f"{paso['nombre']:<34} {'OK':<10} {detalle}")

            # GUIDE: XInput (y por lo tanto Unreal) NO expone el boton de guia;
            # comprobamos al menos que el celular -> servidor lo transporta bien.
            await ws.send_str(json.dumps({"t": "in", **in_botones("guide")}))
            await asyncio.sleep(0.25)
            try:
                async with sesion.get(f"{args.http}/api/estado") as r:
                    datos = await r.json()
                if datos["estado"]["b"].get("guide"):
                    ok += 1
                    print(f"{'GUIDE (llega al servidor)':<34} {'OK':<10} "
                          "XInput no lo expone: es limitación de Microsoft, no del sistema")
                else:
                    fallos_total += 1
                    print(f"{'GUIDE (llega al servidor)':<34} {'FALLA':<10} el servidor no lo registró")
            except Exception as exc:
                fallos_total += 1
                print(f"{'GUIDE (llega al servidor)':<34} {'FALLA':<10} {exc}")

            # al desconectarse el celular, el servidor tiene que liberar todo
            print("\nCerrando la conexión (como cuando el celular se duerme)...")
            await ws.close()
            await asyncio.sleep(0.8)
            snap = lector.snapshot(slot) or {"botones": ["?"], "lx": 0, "ly": 0, "lt": 0, "rt": 0}
            if snap["botones"] or snap["lt"] or snap["rt"]:
                fallos_total += 1
                print(f"{'Libera al desconectarse':<34} {'FALLA':<10} quedó [{','.join(snap['botones'])}]")
            else:
                ok += 1
                print(f"{'Libera al desconectarse':<34} {'OK':<10} todo suelto")

    print("-" * 78)
    print(f"{ok} pruebas OK, {fallos_total} con problemas")
    return 0 if fallos_total == 0 else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
