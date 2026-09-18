# -*- coding: utf-8 -*-
"""
¿Hay puerto MIDI listo?
=======================

Lo llama iniciar-mando.bat antes de arrancar el servidor. Deja pronto un
**puerto MIDI virtual** (loopMIDI) para el modo MIDI del pad:

  1. Si ya hay un puerto virtual, listo.
  2. Si loopMIDI esta instalado pero no tiene puertos, le crea "loopMIDI Port"
     en su configuracion del usuario y lo abre.
  3. Si loopMIDI no esta instalado, sale con codigo 3 para que el .bat lo
     instale desde la carpeta drivers\\ (paquete portable).

Ojo: los puertos de loopMIDI existen **solo mientras loopMIDI.exe esta
corriendo**, por eso tambien lo arranca.

Codigos de salida:  0 = hay puerto   3 = falta instalar loopMIDI
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

CLAVE_PUERTOS = r"Software\Tobias Erichsen\loopMIDI\Ports"
PUERTO_POR_DEFECTO = "loopMIDI Port"


def puertos() -> list[str]:
    try:
        import mido
        return [n for n in mido.get_output_names() if "wavetable" not in n.lower()]
    except Exception as exc:
        print(f"   (no pude consultar los puertos MIDI: {exc})")
        return []


def esperar_puerto(segundos: float = 12.0) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < segundos:
        if puertos():
            return True
        time.sleep(0.6)
    return False


def puertos_configurados() -> list[str]:
    """Nombres que loopMIDI tiene guardados en la config del usuario."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLAVE_PUERTOS) as k:
            nombres = []
            i = 0
            while True:
                try:
                    nombre, valor, _ = winreg.EnumValue(k, i)
                except OSError:
                    break
                i += 1
                if int(valor or 0) != 0:
                    nombres.append(nombre)
            return nombres
    except Exception:
        return []


def crear_puerto(nombre: str = PUERTO_POR_DEFECTO) -> bool:
    """Escribe el puerto en la config de loopMIDI (es lo que hace el boton +)."""
    try:
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, CLAVE_PUERTOS, 0,
                                winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, nombre, 0, winreg.REG_DWORD, 1)
        return True
    except Exception as exc:
        print(f"   No pude crear el puerto MIDI: {exc}")
        return False


def abrir_loopmidi() -> None:
    exe = next((r for r in RUTAS_LOOPMIDI if os.path.exists(r)), None)
    if not exe:
        return
    try:
        subprocess.Popen([exe], close_fds=True)
    except Exception as exc:
        print(f"   No pude abrir loopMIDI: {exc}")


def main() -> int:
    print("   Puerto MIDI para Resolume / QLC+ ...")
    disponibles = puertos()
    if disponibles:
        print(f"   OK: {', '.join(disponibles)}")
        return 0

    instalado = any(os.path.exists(r) for r in RUTAS_LOOPMIDI)
    if not instalado:
        print("   loopMIDI no esta instalado (el .bat lo instala desde drivers\\ si existe).")
        return 3

    # instalado pero sin puertos: crearlo y arrancar la app
    if not puertos_configurados():
        print(f"   Creando el puerto '{PUERTO_POR_DEFECTO}' ...")
        crear_puerto()

    print("   Abriendo loopMIDI (los puertos existen solo mientras corre)...")
    abrir_loopmidi()
    if esperar_puerto():
        print(f"   OK: {', '.join(puertos())}")
        return 0

    print("   loopMIDI esta instalado pero no veo el puerto todavia.")
    print("   Abrelo, revisa que tenga un puerto (boton +, nombre 'loopMIDI Port')")
    print("   y elegi ese puerto desde el panel, en la tarjeta MIDI.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
