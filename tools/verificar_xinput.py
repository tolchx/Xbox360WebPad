# -*- coding: utf-8 -*-
"""
Monitor de XInput: muestra en vivo lo que ve el juego (Unreal Engine, etc.).

Uso:
    python tools/verificar_xinput.py            # foto de los 4 slots
    python tools/verificar_xinput.py --seguir   # monitor en vivo (Ctrl+C sale)
    python tools/verificar_xinput.py --slot 1 --seguir
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xinput_win import LectorXInput          # noqa: E402


def dibujar(snap: dict | None, anterior: str | None) -> str:
    if snap is None:
        return "(sin mando en este slot)"
    b = ",".join(snap["botones"]) or "-"
    barras = "".join("#" if snap["botones"] else "")
    return (f"pkt={snap['paquete']:<7} "
            f"LX={snap['lx']:>7} LY={snap['ly']:>7} RX={snap['rx']:>7} RY={snap['ry']:>7} "
            f"LT={snap['lt']:>3} RT={snap['rt']:>3}  [{b}]{barras}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", type=int, default=None)
    ap.add_argument("--seguir", action="store_true")
    ap.add_argument("--hz", type=float, default=10.0)
    args = ap.parse_args()

    lector = LectorXInput()
    activos = lector.slots_activos()
    print(f"slots con mando: {activos or 'ninguno'}")
    if not activos:
        print("Conectá el mando virtual (corré el servidor) y volvé a intentar.")
        return 1

    slots = [args.slot] if args.slot is not None else activos

    if not args.seguir:
        for s in slots:
            print(" ", lector.resumen(s))
        return 0

    print("Monitor en vivo (Ctrl+C para salir)\n")
    try:
        while True:
            for s in slots:
                linea = dibujar(lector.snapshot(s), None)
                print(f"  slot {s}: {linea}\033[K")
            sys.stdout.write(f"\033[{len(slots)}A")
            sys.stdout.flush()
            time.sleep(1.0 / max(args.hz, 1))
    except KeyboardInterrupt:
        print("\nchau")
    return 0


if __name__ == "__main__":
    sys.exit(main())
