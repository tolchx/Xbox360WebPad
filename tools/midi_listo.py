# -*- coding: utf-8 -*-
"""
¿Hay puerto MIDI listo?
=======================

Lo llama iniciar-mando.bat antes de arrancar el servidor. Se asegura de que
exista un **puerto MIDI virtual** (loopMIDI / teVirtualMIDI) para el modo MIDI
del pad:

  1. Si ya hay un puerto virtual, no hace nada.
  2. Si no hay y loopMIDI esta instalado, lo abre y espera unos segundos.
  3. Si no esta instalado, explica como conseguirlo.

Nunca falla: el pad sigue funcionando en modo joystick aunque no haya MIDI.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

RUTAS_LOOPMIDI = [
    r"C:\Program Files (x86)\Tobias Erichsen\loopMIDI\loopMIDI.exe",
    r"C:\Program Files\Tobias Erichsen\loopMIDI\loopMIDI.exe",
]


def puertos() -> list[str]:
    try:
        import mido
        return [n for n in mido.get_output_names() if "wavetable" not in n.lower()]
    except Exception as exc:
        print(f"  (no pude consultar los puertos MIDI: {exc})")
        return []


def esperar_puerto(segundos: float = 12.0) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < segundos:
        if puertos():
            return True
        time.sleep(0.6)
    return False


def main() -> int:
    print("   Puerto MIDI para Resolume / QLC+ ...")
    disponibles = puertos()
    if disponibles:
        print(f"   OK: {', '.join(disponibles)}")
        return 0

    exe = next((r for r in RUTAS_LOOPMIDI if os.path.exists(r)), None)
    if exe:
        print("   Abriendo loopMIDI (crea el puerto virtual)...")
        try:
            subprocess.Popen([exe], close_fds=True)
        except Exception as exc:
            print(f"   No pude abrirlo: {exc}")
        if esperar_puerto():
            print(f"   OK: {', '.join(puertos())}")
            return 0
        print("   loopMIDI se abrio pero todavia no veo el puerto.")
        print("   Revisá que tenga un puerto creado (boton +, nombre 'loopMIDI Port').")
        return 0

    print("   No encontre loopMIDI instalado. El modo MIDI va a quedar sin puerto.")
    print("   Para usarlo: instalar loopMIDI (https://www.tobias-erichsen.de/software/loopmidi.html),")
    print("   abrirlo y crear un puerto llamado 'loopMIDI Port'.")
    print("   Tambien podes elegir otro puerto desde el panel, en la tarjeta MIDI.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
