# -*- coding: utf-8 -*-
"""Lectura cruda de XInput (lo que ve el juego) — Windows.

Sirve para comprobar que el mando virtual realmente llega al juego: lee
XINPUT_STATE de cada slot igual que lo hace Unreal Engine / DirectX.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes


class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ("wButtons", wintypes.WORD),
        ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]


class XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ("dwPacketNumber", wintypes.DWORD),
        ("Gamepad", XINPUT_GAMEPAD),
    ]


BITS = {
    "up": 0x0001, "down": 0x0002, "left": 0x0004, "right": 0x0008,
    "start": 0x0010, "back": 0x0020, "l3": 0x0040, "r3": 0x0080,
    "lb": 0x0100, "rb": 0x0200, "guide": 0x0400,
    "a": 0x1000, "b": 0x2000, "x": 0x4000, "y": 0x8000,
}


def _dll():
    for nombre in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
        try:
            return ctypes.WinDLL(nombre)
        except OSError:
            continue
    raise OSError("no encontre ninguna xinput*.dll")


class LectorXInput:
    """Lee el estado de los 4 slots de XInput."""

    def __init__(self):
        self.dll = _dll()

    def leer(self, slot: int = 0) -> XINPUT_STATE | None:
        st = XINPUT_STATE()
        rc = self.dll.XInputGetState(slot, ctypes.byref(st))
        return st if rc == 0 else None

    def slots_activos(self) -> list[int]:
        return [s for s in range(4) if self.leer(s) is not None]

    def snapshot(self, slot: int = 0) -> dict | None:
        st = self.leer(slot)
        if st is None:
            return None
        g = st.Gamepad
        return {
            "slot": slot,
            "paquete": st.dwPacketNumber,
            "botones_raw": g.wButtons,
            "botones": [k for k, b in BITS.items() if g.wButtons & b],
            "lt": g.bLeftTrigger,
            "rt": g.bRightTrigger,
            "lx": g.sThumbLX,
            "ly": g.sThumbLY,
            "rx": g.sThumbRX,
            "ry": g.sThumbRY,
        }

    def resumen(self, slot: int = 0) -> str:
        d = self.snapshot(slot)
        if d is None:
            return f"slot {slot}: (sin mando)"
        b = ",".join(d["botones"]) or "-"
        return (f"slot {slot}: pkt={d['paquete']:<6} LT={d['lt']:>3} RT={d['rt']:>3} "
                f"LX={d['lx']:>6} LY={d['ly']:>6} RX={d['rx']:>6} RY={d['ry']:>6}  [{b}]")


if __name__ == "__main__":
    lector = LectorXInput()
    activos = lector.slots_activos()
    print("slots con mando:", activos or "ninguno")
    for s in range(4):
        print(" ", lector.resumen(s))
