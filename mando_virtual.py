# -*- coding: utf-8 -*-
"""
Mando Xbox 360 virtual (ViGEmBus) para Windows
==============================================

Traduce el estado que llega desde el pad web (celular) a un gamepad XInput
real.  Unreal Engine --y practicamente cualquier juego con soporte de mando--
lo ve como un "Xbox 360 Controller for Windows" conectado por USB.

Requiere:
  * Driver ViGEmBus instalado (lo instala iniciar-mando.bat si falta).
  * Paquete `vgamepad` (Python puro + ViGEmClient.dll incluida).

Convenciones de ejes
--------------------
  * Sticks: -1.0 .. 1.0
  * En el cliente, Y es "de pantalla" (arriba = -1, abajo = +1).
    Aca se invierte para XInput (Y+ = arriba), igual que un mando fisico.
  * Gatillos: 0.0 .. 1.0
"""

from __future__ import annotations

import threading
import time

try:
    import vgamepad as vg
    _IMPORT_OK = True
    _IMPORT_ERR = ""
except Exception as exc:                                  # pragma: no cover
    vg = None
    _IMPORT_OK = False
    _IMPORT_ERR = f"{type(exc).__name__}: {exc}"


# ── botones del pad (nombres del protocolo web -> XUSB_BUTTON) ──────────────
BOTONES = [
    "a", "b", "x", "y",
    "lb", "rb",
    "start", "back", "guide",
    "l3", "r3",
    "up", "down", "left", "right",
]

_MAPA_BOTONES = {}
if _IMPORT_OK:
    _MAPA_BOTONES = {
        "a": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
        "b": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
        "x": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
        "y": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
        "lb": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
        "rb": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
        "start": vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
        "back": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
        "guide": vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
        "l3": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
        "r3": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
        "up": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
        "down": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
        "left": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
        "right": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
    }

ZONA_MUERTA = 0.08          # deadzone radial de los sticks
MS_ENTRE_UPDATE = 8         # ~120 Hz mientras hay cambios
MS_KEEPALIVE = 1000         # refresco aunque no cambie nada


def estado_neutro() -> dict:
    """Estado con todo suelto (sirve para arrancar y para el watchdog)."""
    return {
        "ls": [0.0, 0.0],
        "rs": [0.0, 0.0],
        "lt": 0.0,
        "rt": 0.0,
        "b": {k: False for k in BOTONES},
    }


def _num(v, lo=-1.0, hi=1.0, defecto=0.0) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return defecto
    if f != f:                       # NaN
        return defecto
    return lo if f < lo else hi if f > hi else f


def _deadzone(x: float, y: float) -> tuple[float, float]:
    """Deadzone radial + reescalado (evita el salto brusco al salir del centro)."""
    d = (x * x + y * y) ** 0.5
    if d <= ZONA_MUERTA:
        return 0.0, 0.0
    if d > 1.0:
        x, y, d = x / d, y / d, 1.0
    escala = (d - ZONA_MUERTA) / (1.0 - ZONA_MUERTA) / d
    return x * escala, y * escala


class MandoVirtual:
    """Mando Xbox 360 virtual con reconexion automatica.

    Uso:
        m = MandoVirtual()
        m.aplicar(estado)
        ...
        m.cerrar()
    """

    def __init__(self, verbose: bool = True, conectar: bool = True):
        self.verbose = verbose
        self._lock = threading.RLock()
        self.pad = None
        self._estado = estado_neutro()
        self._sucio = True
        self._ultimo_update = 0.0
        self._ultimo_error = "" if conectar else "modo sin mando virtual (--no-pad)"
        self._reintento = 0.0
        self._auto_conectar = conectar
        if conectar:
            self.conectar()

    # ── ciclo de vida ──────────────────────────────────────────────────────
    def conectar(self) -> bool:
        if not _IMPORT_OK:
            self._ultimo_error = f"vgamepad no disponible ({_IMPORT_ERR})"
            return False
        with self._lock:
            try:
                self.pad = vg.VX360Gamepad()
                self.pad.reset()
                self.pad.update()
                self._sucio = True
                self._ultimo_error = ""
                self._log("[mando] Xbox 360 virtual conectado (XInput)")
                return True
            except Exception as exc:
                self.pad = None
                self._ultimo_error = f"{type(exc).__name__}: {exc}"
                self._log(f"[mando] no se pudo crear el mando: {self._ultimo_error}")
                return False

    @property
    def disponible(self) -> bool:
        return self.pad is not None

    @property
    def error(self) -> str:
        return self._ultimo_error

    def cerrar(self) -> None:
        with self._lock:
            if self.pad is not None:
                try:
                    self.pad.reset()
                    self.pad.update()
                except Exception:
                    pass
                self.pad = None

    # ── estado ─────────────────────────────────────────────────────────────
    @property
    def estado(self) -> dict:
        st = self._estado
        return {
            "ls": list(st["ls"]),
            "rs": list(st["rs"]),
            "lt": st["lt"],
            "rt": st["rt"],
            "b": dict(st["b"]),
        }

    def actualizar(self, parcial: dict) -> None:
        """Fusiona un estado parcial que llego del pad web."""
        with self._lock:
            st = self._estado
            if "ls" in parcial or "rs" in parcial:
                for eje, clave in (("ls", "ls"), ("rs", "rs")):
                    v = parcial.get(eje)
                    if isinstance(v, (list, tuple)) and len(v) >= 2:
                        st[clave] = [_num(v[0]), _num(v[1])]
            for gat in ("lt", "rt"):
                if gat in parcial:
                    st[gat] = _num(parcial[gat], 0.0, 1.0)
            bs = parcial.get("b")
            if isinstance(bs, dict):
                for k, v in bs.items():
                    if k in st["b"]:
                        st["b"][k] = bool(v)
            elif isinstance(bs, list):          # comodidad: lista de apretados
                for k in BOTONES:
                    st["b"][k] = k in bs
            self._sucio = True

    def neutro(self) -> None:
        with self._lock:
            self._estado = estado_neutro()
            self._sucio = True

    # ── salida hacia XInput ────────────────────────────────────────────────
    def latir(self, forzar: bool = False) -> bool:
        """Escribe el estado en el mando si cambio (o si toca keepalive).

        Devuelve True si efectivamente se envio un reporte.
        """
        with self._lock:
            if self.pad is None:
                ahora = time.monotonic()
                if self._auto_conectar and ahora - self._reintento > 2.0:
                    self._reintento = ahora
                    threading.Thread(target=self.conectar, daemon=True).start()
                return False

            ahora = time.monotonic()
            if not forzar and not self._sucio and (ahora - self._ultimo_update) * 1000 < MS_KEEPALIVE:
                return False

            st = self._estado
            try:
                pad = self.pad
                pad.reset()

                lx, ly = _deadzone(st["ls"][0], st["ls"][1])
                rx, ry = _deadzone(st["rs"][0], st["rs"][1])
                pad.left_joystick_float(x_value_float=lx, y_value_float=-ly)
                pad.right_joystick_float(x_value_float=rx, y_value_float=-ry)

                pad.left_trigger_float(value_float=st["lt"])
                pad.right_trigger_float(value_float=st["rt"])

                for nombre, apretado in st["b"].items():
                    if apretado:
                        pad.press_button(_MAPA_BOTONES[nombre])

                pad.update()
            except Exception as exc:
                self._ultimo_error = f"{type(exc).__name__}: {exc}"
                self._log(f"[mando] se perdio el mando virtual: {self._ultimo_error}")
                self.pad = None
                self._reintento = 0.0
                return False

            self._sucio = False
            self._ultimo_update = ahora
            return True

    # ── utilidades ─────────────────────────────────────────────────────────
    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg, flush=True)


if __name__ == "__main__":                       # prueba rapida de humo
    import sys
    import time as _t

    m = MandoVirtual()
    print("disponible:", m.disponible, "| error:", m.error or "-")
    if not m.disponible:
        sys.exit(1)

    print("→ A + stick izquierdo abajo-derecha + gatillo derecho al 100% (3 s)")
    m.actualizar({"ls": [0.8, 0.8], "rt": 1.0, "b": ["a"]})
    for _ in range(int(3 / 0.05)):
        m.latir()
        _t.sleep(0.05)

    print("→ botones sueltos")
    m.neutro()
    for _ in range(10):
        m.latir()
        _t.sleep(0.05)

    m.cerrar()
    print("listo")
