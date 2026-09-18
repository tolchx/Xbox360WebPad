# -*- coding: utf-8 -*-
"""
Prueba MIDI de punta a punta
============================

Simula el celular en **modo MIDI**, manda los toques por WebSocket y escucha
lo que sale de verdad por el **puerto MIDI virtual** (loopMIDI). Es la cadena
completa: celular -> servidor -> puerto MIDI -> (Resolume / QLC+).

Requiere que el servidor este corriendo y que exista un puerto virtual
(loopMIDI abierto). Uso:

    .venv\\Scripts\\python.exe tools\\prueba_midi.py
    .venv\\Scripts\\python.exe tools\\prueba_midi.py --url ws://127.0.0.1:8790/ws
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import aiohttp
    import mido
except ImportError:                                       # pragma: no cover
    print("Faltan dependencias. Corré: pip install -r requirements.txt")
    sys.exit(1)


def elegir_entrada() -> str | None:
    """Entrada MIDI del puerto virtual (loopMIDI expone '... Port 0')."""
    entradas = mido.get_input_names()
    for nombre in entradas:
        if "loopmidi" in nombre.lower():
            return nombre
    return entradas[0] if entradas else None


def puerto_salida_virtual() -> str | None:
    """Salida del mismo puerto virtual (para inyectar señales en el MIDI learn)."""
    salidas = mido.get_output_names()
    for nombre in salidas:
        if "loopmidi" in nombre.lower():
            return nombre
    return salidas[0] if salidas else None


def elegir_control(mapa: dict, **cond) -> dict | None:
    for pag in mapa.get("paginas", []):
        for b in pag.get("botones", []):
            if all(b.get(k) == v for k, v in cond.items()):
                return b
    return None


def primer_fader(mapa: dict) -> dict | None:
    for pag in mapa.get("paginas", []):
        if pag.get("faders"):
            return pag["faders"][0]
    return None


class Escucha:
    """Junta lo que llega por el puerto MIDI."""

    def __init__(self, puerto: str):
        self.entrada = mido.open_input(puerto)
        self.mensajes: list[mido.Message] = []

    async def recoger(self, espera: float = 0.35) -> list[mido.Message]:
        """Junta lo que llega durante 'espera' segundos.

        Es async a proposito: si bloqueamos el event loop con time.sleep(), el
        WebSocket del cliente no alcanza a vaciar el buffer y el servidor recibe
        el mensaje recien despues (falso negativo en las pruebas).
        """
        t0 = time.monotonic()
        while time.monotonic() - t0 < espera:
            for m in self.entrada.iter_pending():
                self.mensajes.append(m)
            await asyncio.sleep(0.01)
        return list(self.mensajes)

    async def limpiar(self) -> None:
        await self.recoger(0.05)
        self.mensajes.clear()

    def cerrar(self) -> None:
        try:
            self.entrada.close()
        except Exception:
            pass


def describir(m: mido.Message) -> str:
    if m.type in ("note_on", "note_off"):
        return f"{m.type} n={m.note} v={m.velocity} ch={m.channel + 1}"
    if m.type == "control_change":
        return f"cc {m.control}={m.value} ch={m.channel + 1}"
    return f"{m.type} ch={getattr(m, 'channel', 0) + 1}"


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="ws://127.0.0.1:8790/ws")
    ap.add_argument("--http", default="http://127.0.0.1:8790")
    ap.add_argument("--espera", type=float, default=0.4)
    args = ap.parse_args()

    puerto = elegir_entrada()
    if not puerto:
        print("No hay ninguna entrada MIDI. Abrí loopMIDI para crear el puerto virtual.")
        return 1
    print(f"Escuchando el puerto MIDI: {puerto}\n")

    escucha = Escucha(puerto)
    ok = fallos = 0
    async with aiohttp.ClientSession() as sesion:
        async with sesion.get(f"{args.http}/api/midi") as r:
            datos = await r.json()
        mapa = datos["mapa"]
        print(f"Servidor MIDI: {'puerto ' + str(datos['midi']['puerto']) if datos['midi']['disponible'] else 'SIN PUERTO (' + str(datos['midi']['error']) + ')'}")
        if not datos["midi"]["disponible"]:
            escucha.cerrar()
            return 1

        b_momento = elegir_control(mapa, modo="momento", tipo="note")
        b_toggle = elegir_control(mapa, modo="toggle", tipo="note")
        b_disparo = elegir_control(mapa, modo="disparo", tipo="note")
        fader = primer_fader(mapa)
        print(f"Controles del mapeo: momento={b_momento and b_momento['id']} "
              f"toggle={b_toggle and b_toggle['id']} disparo={b_disparo and b_disparo['id']} "
              f"fader={fader and fader['id']}\n")

        try:
            ws = await sesion.ws_connect(args.url)
        except Exception as exc:
            print(f"No me pude conectar a {args.url}: {exc}")
            escucha.cerrar()
            return 1

        print(f"{'prueba':<36} {'resultado':<10} detalle")
        print("-" * 80)

        async def chequear(nombre: str, esperados, espera: float | None = None) -> None:
            """esperados: texto (o lista de alternativas) que tiene que aparecer."""
            nonlocal ok, fallos
            if isinstance(esperados, str):
                esperados = [esperados]
            desde = len(escucha.mensajes)
            await escucha.recoger(espera or args.espera)
            todos = [describir(m) for m in escucha.mensajes]
            nuevos = todos[desde:] or ["(nada nuevo)"]
            if any(any(e in r for r in todos) for e in esperados):
                ok += 1
                print(f"{nombre:<36} {'OK':<10} {', '.join(nuevos)}")
            else:
                fallos += 1
                print(f"{nombre:<36} {'FALLA':<10} esperaba {esperados}, llegó: {', '.join(nuevos)}")

        async with ws:
            await ws.send_str(json.dumps({"t": "hello", "role": "pad",
                                          "nombre": "prueba-midi"}))
            bienvenida = json.loads((await ws.receive()).data)
            if not bienvenida.get("mapa"):
                print("El servidor no mandó el mapeo MIDI.")
                escucha.cerrar()
                return 1
            await ws.send_str(json.dumps({"t": "modo", "modo": "midi"}))
            await asyncio.sleep(0.3)
            await escucha.limpiar()

            if b_momento:
                nota = b_momento["num"]
                await ws.send_str(json.dumps({"t": "midi", "accion": "press",
                                              "id": b_momento["id"]}))
                await chequear(f"botón momento {b_momento['id']} (apretar)",
                               f"note_on n={nota}")
                await ws.send_str(json.dumps({"t": "midi", "accion": "release",
                                              "id": b_momento["id"]}))
                await chequear(f"botón momento {b_momento['id']} (soltar)",
                               f"note_off n={nota}")

            if b_toggle:
                nota = b_toggle["num"]
                await ws.send_str(json.dumps({"t": "midi", "accion": "press",
                                              "id": b_toggle["id"]}))
                await chequear(f"toggle {b_toggle['id']} (encender)", f"note_on n={nota}")
                await ws.send_str(json.dumps({"t": "midi", "accion": "release",
                                              "id": b_toggle["id"]}))
                await escucha.recoger(0.2)
                await ws.send_str(json.dumps({"t": "midi", "accion": "press",
                                              "id": b_toggle["id"]}))
                await chequear(f"toggle {b_toggle['id']} (apagar)",
                               [f"note_off n={nota}", f"note_on n={nota} v=0"])

            if b_disparo:
                nota = b_disparo["num"]
                await ws.send_str(json.dumps({"t": "midi", "accion": "press",
                                              "id": b_disparo["id"]}))
                recibidos = [describir(m) for m in await escucha.recoger(0.6)]
                tiene_on = any(f"note_on n={nota}" in r and "v=0" not in r for r in recibidos)
                tiene_off = any((f"note_off n={nota}" in r) or (f"note_on n={nota} v=0" in r)
                                for r in recibidos)
                if tiene_on and tiene_off:
                    ok += 1
                    print(f"{'disparo ' + b_disparo['id'] + ' (auto-off)':<36} {'OK':<10} {', '.join(recibidos)}")
                else:
                    fallos += 1
                    print(f"{'disparo ' + b_disparo['id'] + ' (auto-off)':<36} {'FALLA':<10} {', '.join(recibidos) or '(nada)'}")

            if fader:
                await ws.send_str(json.dumps({"t": "midi", "accion": "cc",
                                              "id": fader["id"], "valor": 99}))
                await chequear(f"fader {fader['id']} -> CC {fader['num']}",
                               f"cc {fader['num']}=99")

            # ── guardas de la UI del celular ──────────────────────────────
            # Bug real: #capa-midi tiene display:flex y eso le gana al atributo
            # hidden → la botonera MIDI se dibujaba SOBRE el mando Xbox y el
            # switch no la ocultaba. Con la regla [hidden]{display:none !important}
            # el atributo vuelve a mandar.
            async with sesion.get(f"{args.http}/static/pad.css") as r:
                css = (await r.text()).replace(" ", "").replace("\n", "")
            async with sesion.get(f"{args.http}/static/pad.html") as r:
                html_pad = await r.text()
            tiene_regla = "[hidden]{display:none!important" in css
            tiene_capas = 'id="capa-jo' in html_pad and 'id="capa-midi"' in html_pad
            if tiene_regla and tiene_capas:
                ok += 1
                print(f"{'UI: hidden le gana a display:flex':<36} {'OK':<10} capas del celular en orden")
            else:
                fallos += 1
                print(f"{'UI: hidden le gana a display:flex':<36} {'FALLA':<10} "
                      f"regla={tiene_regla} capas={tiene_capas}")

            # ── joystick -> MIDI ─────────────────────────────────────────
            async def restaurar(etiqueta: str = "mapeo original restaurado") -> None:
                nonlocal ok, fallos
                async with sesion.post(f"{args.http}/api/midi/mapa",
                                       json={"mapa": mapa}) as r:
                    await r.json()
                async with sesion.get(f"{args.http}/api/midi") as r:
                    vuelto = (await r.json())["mapa"]
                # el mapeo original puede traer filas de joystick: comparamos con lo
                # que había antes en vez de exigir una lista vacía
                if (len(vuelto.get("joystick") or []) == len(mapa.get("joystick") or [])
                        and vuelto["paginas"][0]["botones"][0]["num"]
                        == mapa["paginas"][0]["botones"][0]["num"]):
                    ok += 1
                    print(f"{etiqueta:<36} {'OK':<10} sin cambios permanentes")
                else:
                    fallos += 1
                    print(f"{etiqueta:<36} {'FALLA':<10} revisar midi-mapa.json")

            mapa_prueba = json.loads(json.dumps(mapa))
            mapa_prueba["joystick_activo"] = True
            mapa_prueba["joystick"] = [
                {"id": "jtest1", "control": "a", "tipo": "note", "num": 40, "canal": 1,
                 "modo": "momento", "umbral": 0.5, "invertir": False},
                {"id": "jtest2", "control": "rt", "tipo": "cc", "num": 20, "canal": 1,
                 "modo": "momento", "umbral": 0.6, "invertir": False},
                {"id": "jtest3", "control": "ls_x", "tipo": "cc", "num": 21, "canal": 1,
                 "modo": "momento", "umbral": 0.6, "invertir": False},
            ]
            async with sesion.post(f"{args.http}/api/midi/mapa",
                                   json={"mapa": mapa_prueba}) as r:
                await r.json()
            await asyncio.sleep(0.3)
            await ws.send_str(json.dumps({"t": "modo", "modo": "joy"}))
            await asyncio.sleep(0.3)
            await escucha.limpiar()

            await ws.send_str(json.dumps({"t": "in", "b": {"a": True}}))
            await chequear("joystick: A -> nota 40", "note_on n=40", espera=0.5)
            await ws.send_str(json.dumps({"t": "in", "b": {"a": False}}))
            await chequear("joystick: soltar A -> note off", "note_off n=40", espera=0.5)

            await ws.send_str(json.dumps({"t": "in", "rt": 1.0}))
            await chequear("joystick: gatillo RT -> CC 20 al maximo", "cc 20=127", espera=0.5)
            await ws.send_str(json.dumps({"t": "in", "ls": [0.9, 0.0]}))
            recibidos = [describir(m) for m in await escucha.recoger(0.5)]
            valores = [int(r.split("=")[1].split(" ")[0])
                       for r in recibidos if r.startswith("cc 21=")]
            if valores and max(valores) >= 100:
                ok += 1
                print(f"{'joystick: stick izq -> CC 21':<36} {'OK':<10} llegó {max(valores)}")
            else:
                fallos += 1
                print(f"{'joystick: stick izq -> CC 21':<36} {'FALLA':<10} {recibidos or '(nada)'}")
            await ws.send_str(json.dumps({"t": "in", "b": {"a": False}, "rt": 0, "ls": [0, 0]}))
            await asyncio.sleep(0.3)
            await restaurar("joystick sin cambios permanentes")

            # ── MIDI learn ───────────────────────────────────────────────
            # 1) el eco de lo que manda el propio server (el panic CC120) NO se aprende
            await sesion.post(f"{args.http}/api/midi/learn", json={"id": "r1"})
            await asyncio.sleep(0.3)
            await sesion.post(f"{args.http}/api/midi/panic")
            await asyncio.sleep(0.8)
            async with sesion.get(f"{args.http}/api/midi") as r:
                sigue = (await r.json()).get("aprender")
            if sigue == "r1":
                ok += 1
                print(f"{'learn: ignora el eco del panic':<36} {'OK':<10} sigue esperando")
            else:
                fallos += 1
                print(f"{'learn: ignora el eco del panic':<36} {'FALLA':<10} capturó el eco ({sigue})")

            original_r1 = json.loads(json.dumps(mapa_prueba["paginas"][0]["botones"][0]))
            async with sesion.post(f"{args.http}/api/midi/learn",
                                   json={"id": original_r1["id"]}) as r:
                armado = (await r.json()).get("ok")
            await asyncio.sleep(0.2)
            # mandamos una señal MIDI "desde afuera" (como si fuera la mesa de luz)
            with mido.open_output(puerto_salida_virtual()) as salida_aux:
                salida_aux.send(mido.Message("note_on", note=77, velocity=110, channel=2))
                await asyncio.sleep(0.8)
            async with sesion.get(f"{args.http}/api/midi") as r:
                mapa_nuevo = (await r.json())["mapa"]
            boton = mapa_nuevo["paginas"][0]["botones"][0]
            if armado and boton["num"] == 77 and boton["canal"] == 3 and boton["tipo"] == "note":
                ok += 1
                print(f"{'MIDI learn desde el puerto':<36} {'OK':<10} "
                      f"{original_r1['etiqueta']}: {original_r1['num']} -> nota 77 ch 3")
            else:
                fallos += 1
                print(f"{'MIDI learn desde el puerto':<36} {'FALLA':<10} "
                      f"quedó {boton['tipo']} {boton['num']} ch {boton['canal']}")

            # restaurar el mapeo original
            await restaurar("lear n sin cambios permanentes")

            # ── MIDI learn en una fila del joystick (control del mando) ──
            mapa_j = json.loads(json.dumps(mapa))
            mapa_j["joystick_activo"] = False              # sin motor: solo probamos el learn
            mapa_j["joystick"] = [{"id": "jtest9", "control": "a", "tipo": "note", "num": 36,
                                   "canal": 1, "modo": "momento", "umbral": 0.6,
                                   "invertir": False}]
            async with sesion.post(f"{args.http}/api/midi/mapa", json={"mapa": mapa_j}) as r:
                await r.json()
            await asyncio.sleep(0.3)
            async with sesion.post(f"{args.http}/api/midi/learn",
                                   json={"id": "jtest9"}) as r:
                armado = (await r.json()).get("ok")
            if not armado:
                fallos += 1
                print(f"{'learn en fila del joystick':<36} {'FALLA':<10} no pudo armar")
            else:
                with mido.open_output(puerto_salida_virtual()) as salida_aux:
                    salida_aux.send(mido.Message("note_on", note=64, velocity=100, channel=3))
                await asyncio.sleep(0.8)
                async with sesion.get(f"{args.http}/api/midi") as r:
                    vuelto_j = (await r.json())["mapa"]
                it = next((x for x in (vuelto_j.get("joystick") or [])
                           if x["id"] == "jtest9"), {})
                if it.get("num") == 64 and it.get("canal") == 4:
                    ok += 1
                    print(f"{'learn en fila del joystick':<36} {'OK':<10} A: 36 -> nota 64 ch 4")
                else:
                    fallos += 1
                    print(f"{'learn en fila del joystick':<36} {'FALLA':<10} quedó {it}")
            await restaurar("joystick learn sin cambios")

            # vuelta a modo joystick: tiene que mandar el panic
            await ws.send_str(json.dumps({"t": "modo", "modo": "midi"}))
            await asyncio.sleep(0.3)
            await escucha.limpiar()
            await ws.send_str(json.dumps({"t": "modo", "modo": "joy"}))
            recibidos = [describir(m) for m in await escucha.recoger(0.5)]
            if any("cc 123=" in r or "cc 120=" in r for r in recibidos):
                ok += 1
                print(f"{'vuelta a joystick (panic)':<36} {'OK':<10} {', '.join(recibidos)}")
            else:
                fallos += 1
                print(f"{'vuelta a joystick (panic)':<36} {'FALLA':<10} {', '.join(recibidos) or '(nada)'}")

            # desconectar con una nota apretada: el servidor debe soltarla
            await ws.send_str(json.dumps({"t": "modo", "modo": "midi"}))
            await asyncio.sleep(0.2)
            if b_momento:
                await ws.send_str(json.dumps({"t": "midi", "accion": "press",
                                              "id": b_momento["id"]}))
                await escucha.recoger(0.3)
            await ws.close()
            recibidos = [describir(m) for m in await escucha.recoger(1.0)]
            if (not b_momento) or any("cc 123=" in r or "note_off" in r or "cc 120=" in r
                                      for r in recibidos):
                ok += 1
                print(f"{'libera al desconectarse':<36} {'OK':<10} {', '.join(recibidos) or '(nada)'}")
            else:
                fallos += 1
                print(f"{'libera al desconectarse':<36} {'FALLA':<10} {', '.join(recibidos) or '(nada)'}")

    escucha.cerrar()
    print("-" * 80)
    print(f"{ok} pruebas OK, {fallos} con problemas")
    return 0 if fallos == 0 else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
