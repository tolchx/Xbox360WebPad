# -*- coding: utf-8 -*-
"""
Salida MIDI
===========

Manda mensajes MIDI (notas, CC, program change) a un puerto de Windows, para
controlar en paralelo programas como **Resolume Arena** o **QLC+** mientras el
joystick virtual sigue manejando el juego.

En Windows los puertos MIDI virtuales los crea un driver externo: **loopMIDI**
(recomendado, ya suele estar instalado) o el driver teVirtualMIDI. Creado el
puerto, cualquier programa lo ve como un dispositivo MIDI más.

Requiere:  mido  +  python-rtmidi
"""

from __future__ import annotations

import collections
import threading
import time

try:
    import mido
    _MIDO_OK = True
    _MIDO_ERR = ""
except Exception as exc:                                     # pragma: no cover
    mido = None
    _MIDO_OK = False
    _MIDO_ERR = f"{type(exc).__name__}: {exc}"


def limitar(v, lo: int, hi: int) -> int:
    try:
        n = int(round(float(v)))
    except (TypeError, ValueError):
        return lo
    return lo if n < lo else hi if n > hi else n


def puertos_salida() -> list[str]:
    """Nombres de las salidas MIDI disponibles."""
    if not _MIDO_OK:
        return []
    try:
        return list(mido.get_output_names())
    except Exception:
        return []


def puertos_entrada() -> list[str]:
    """Nombres de las entradas MIDI disponibles (para MIDI learn)."""
    if not _MIDO_OK:
        return []
    try:
        return list(mido.get_input_names())
    except Exception:
        return []


def resolver_puerto(nombre: str | None, salidas: list[str] | None = None) -> str | None:
    """Encuentra la salida que corresponde al nombre pedido.

    loopMIDI expone la salida como 'loopMIDI Port 1' (y la entrada como
    'loopMIDI Port 0'), asi que hace falta coincidencia por substring.
    """
    salidas = salidas if salidas is not None else puertos_salida()
    if not salidas:
        return None
    if not nombre:
        return salidas[0]
    if nombre in salidas:
        return nombre
    bajo = nombre.lower()
    for s in salidas:                                   # igual ignorando mayusculas
        if s.lower() == bajo:
            return s
    for s in salidas:                                   # el nombre esta contenido
        if bajo in s.lower():
            return s
    for s in salidas:                                   # al reves: el puerto esta contenido
        if s.lower() in bajo:
            return s
    return None


class SalidaMidi:
    """Puerto MIDI de salida con reconexion y 'panic' (no dejar notas colgadas)."""

    def __init__(self, puerto: str | None = None, verbose: bool = True):
        self.verbose = verbose
        self.nombre_pedido = puerto or ""
        self.puerto = None
        self.nombre_abierto: str | None = None
        self._lock = threading.RLock()
        self.enviados: collections.deque = collections.deque(maxlen=64)  # filtro de eco
        self._notas_activas: set[tuple[int, int]] = set()      # (canal, nota)
        self._cc_activos: set[tuple[int, int]] = set()         # (canal, cc)
        self._mensajes = 0
        self._ultimo: dict | None = None
        self._ultimo_error = "" if _MIDO_OK else f"mido no disponible ({_MIDO_ERR})"
        self._intento = 0.0
        self._salidas: list[str] = []
        self._salidas_ts = 0.0
        if _MIDO_OK:
            self.reconectar()

    # ── listado de puertos (con cache: el panel pide estado 10 veces por segundo)
    def salidas(self, forzar: bool = False) -> list[str]:
        ahora = time.monotonic()
        if forzar or not self._salidas or ahora - self._salidas_ts > 5.0:
            self._salidas = puertos_salida()
            self._salidas_ts = ahora
        return list(self._salidas)

    # ── ciclo de vida ──────────────────────────────────────────────────────
    def reconectar(self, forzar: bool = False) -> bool:
        """Abre el puerto pedido si no esta abierto (se reintenta cada 3 s)."""
        if not _MIDO_OK:
            return False
        with self._lock:
            if self.puerto is not None and not forzar:
                return True
            ahora = time.monotonic()
            if not forzar and ahora - self._intento < 3.0:
                return False
            self._intento = ahora

            salidas = self.salidas(forzar=True)
            objetivo = resolver_puerto(self.nombre_pedido, salidas)
            if objetivo is None:
                self._ultimo_error = ("no hay salidas MIDI"
                                      if not salidas else
                                      f"no encuentro el puerto MIDI '{self.nombre_pedido}'")
                return False
            if self.puerto is not None:                        # cambiar de puerto
                try:
                    self.puerto.close()
                except Exception:
                    pass
                self.puerto = None
            try:
                self.puerto = mido.open_output(objetivo)
                self.nombre_abierto = objetivo
                self._ultimo_error = ""
                self._log(f"[midi] salida abierta: {objetivo}")
                return True
            except Exception as exc:
                self._ultimo_error = f"{type(exc).__name__}: {exc}"
                self.puerto = None
                self._log(f"[midi] no se pudo abrir '{objetivo}': {self._ultimo_error}")
                return False

    @property
    def disponible(self) -> bool:
        return self.puerto is not None

    @property
    def error(self) -> str:
        return self._ultimo_error

    def cerrar(self) -> None:
        with self._lock:
            self.panic()
            if self.puerto is not None:
                try:
                    self.puerto.close()
                except Exception:
                    pass
                self.puerto = None
                self.nombre_abierto = None

    # ── envio ──────────────────────────────────────────────────────────────
    def _mandar(self, msg) -> bool:
        with self._lock:
            if self.puerto is None and not self.reconectar():
                return False
            try:
                self.puerto.send(msg)
            except Exception as exc:
                self._ultimo_error = f"{type(exc).__name__}: {exc}"
                self._log(f"[midi] se perdio el puerto: {self._ultimo_error}")
                try:
                    self.puerto.close()
                except Exception:
                    pass
                self.puerto = None
                return False
            self._mensajes += 1
            self._recordar(msg)                     # para no confundir ecos con learn
            self._ultimo = {"tipo": msg.type, "canal": getattr(msg, "channel", 0) + 1,
                            "dato": self._resumen(msg), "hace": time.time()}
            return True

    # ── filtro de eco ──────────────────────────────────────────────────────
    # loopMIDI devuelve TODO lo que escribimos a su propia entrada, asi que al
    # escuchar el puerto (MIDI learn) hay que ignorar lo que mandamos nosotros.
    @staticmethod
    def firma(msg) -> tuple:
        tipo = msg.type
        valor = msg.velocity if tipo.startswith("note") else getattr(msg, "value", 0)
        if tipo == "note_on" and valor == 0:
            tipo = "note_off"
        numero = msg.note if tipo.startswith("note") else getattr(msg, "control", 0)
        return (tipo, msg.channel, numero, valor)

    def _recordar(self, msg) -> None:
        with self._lock:
            self.enviados.append((self.firma(msg), time.monotonic()))
            if len(self.enviados) > 64:
                self.enviados.popleft()

    def eco_reciente(self, m: dict, ventana: float = 0.35) -> bool:
        """True si este mensaje entrante es un eco de algo que mandamos nosotros."""
        tipo = {"note": "note_on", "cc": "control_change", "pc": "program_change"}.get(
            m.get("tipo", ""), "")
        if not tipo:
            return False
        objetivo = (tipo, int(m.get("canal", 1)) - 1, int(m.get("num", 0)), int(m.get("valor", 0)))
        corte = time.monotonic() - ventana
        with self._lock:
            return any(sig == objetivo and t >= corte for sig, t in self.enviados)

    @staticmethod
    def _resumen(msg) -> str:
        if msg.type in ("note_on", "note_off"):
            return f"nota {msg.note} vel {msg.velocity}"
        if msg.type == "control_change":
            return f"CC {msg.control} = {msg.value}"
        if msg.type == "program_change":
            return f"programa {msg.program}"
        return str(msg)

    def nota(self, nota, valor=127, canal=1) -> bool:
        n, v, c = limitar(nota, 0, 127), limitar(valor, 0, 127), limitar(canal, 1, 16) - 1
        if v > 0:
            self._notas_activas.add((c, n))
            return self._mandar(mido.Message("note_on", note=n, velocity=v, channel=c))
        self._notas_activas.discard((c, n))
        return self._mandar(mido.Message("note_off", note=n, velocity=0, channel=c))

    def cc(self, control, valor, canal=1) -> bool:
        ctrl, val, c = limitar(control, 0, 127), limitar(valor, 0, 127), limitar(canal, 1, 16) - 1
        self._cc_activos.add((c, ctrl))
        return self._mandar(mido.Message("control_change", control=ctrl, value=val, channel=c))

    def programa(self, num, canal=1) -> bool:
        return self._mandar(mido.Message("program_change",
                                         program=limitar(num, 0, 127),
                                         channel=limitar(canal, 1, 16) - 1))

    def enviar(self, m: dict) -> bool:
        """Envia un mensaje segun el dict que llega del pad web."""
        tipo = (m.get("tipo") or "note").lower()
        canal = m.get("canal") or 1
        if tipo == "note":
            return self.nota(m.get("num", 36), m.get("valor", 127), canal)
        if tipo == "cc":
            return self.cc(m.get("num", 7), m.get("valor", 0), canal)
        if tipo in ("pc", "programa", "program"):
            return self.programa(m.get("num", 0), canal)
        if tipo == "panic":
            self.panic()
            return True
        return False

    def panic(self) -> None:
        """Todo apagado: nota off de lo que quedó sonando + CC 120/123."""
        if self.puerto is None:
            return
        for (c, n) in list(self._notas_activas):
            # por _mandar: asi queda registrado y el MIDI learn no lo confunde con
            # una señal del usuario (loopMIDI nos devuelve lo que mandamos)
            if not self._mandar(mido.Message("note_off", note=n, velocity=0, channel=c)):
                break
        self._notas_activas.clear()
        for c in range(16):
            for ctrl in (120, 123):                        # all sound off / all notes off
                if not self._mandar(mido.Message("control_change", control=ctrl,
                                                 value=0, channel=c)):
                    self._cc_activos.clear()
                    return
        self._cc_activos.clear()

    # ── estado para el panel ───────────────────────────────────────────────
    def estado(self) -> dict:
        return {
            "disponible": self.disponible,
            "puerto": self.nombre_abierto,
            "pedido": self.nombre_pedido,
            "error": self._ultimo_error,
            "salidas": self.salidas(),
            "mensajes": self._mensajes,
            "ultimo": self._ultimo,
            "notas_activas": len(self._notas_activas),
        }

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg, flush=True)


class EntradaMidi:
    """Puerto MIDI de entrada: se usa para **MIDI learn**.

    Escucha lo que mandan otros programas (la mesa de luz, QLC+, Resolume) por el
    mismo puerto virtual, para poder asignar ese numero a un control del pad.
    """

    def __init__(self, puerto: str | None = None, verbose: bool = True):
        self.verbose = verbose
        self.nombre_pedido = puerto or ""
        self.puerto = None
        self.nombre_abierto: str | None = None
        self._lock = threading.RLock()
        self._cola: list[dict] = []
        self._max_cola = 200
        self._recibidos = 0
        self._ultimo: dict | None = None
        self._ultimo_error = "" if _MIDO_OK else f"mido no disponible ({_MIDO_ERR})"
        self._intento = 0.0
        self._entradas: list[str] = []
        self._entradas_ts = 0.0
        if _MIDO_OK:
            self.reconectar()

    # ── puertos (con cache) ────────────────────────────────────────────────
    def entradas(self, forzar: bool = False) -> list[str]:
        ahora = time.monotonic()
        if forzar or not self._entradas or ahora - self._entradas_ts > 5.0:
            self._entradas = puertos_entrada()
            self._entradas_ts = ahora
        return list(self._entradas)

    def reconectar(self, forzar: bool = False) -> bool:
        if not _MIDO_OK:
            return False
        with self._lock:
            if self.puerto is not None and not forzar:
                return True
            ahora = time.monotonic()
            if not forzar and ahora - self._intento < 5.0:
                return False
            self._intento = ahora
            objetivo = resolver_puerto(self.nombre_pedido, self.entradas(forzar=True))
            if objetivo is None:
                self._ultimo_error = ("no hay entradas MIDI"
                                      if not self.entradas() else
                                      f"no encuentro la entrada MIDI '{self.nombre_pedido}'")
                return False
            if self.puerto is not None:
                try:
                    self.puerto.close()
                except Exception:
                    pass
                self.puerto = None
            try:
                self.puerto = mido.open_input(objetivo, callback=self._al_recibir)
                self.nombre_abierto = objetivo
                self._ultimo_error = ""
                self._log(f"[midi] entrada abierta (learn): {objetivo}")
                return True
            except Exception as exc:
                self._ultimo_error = f"{type(exc).__name__}: {exc}"
                self.puerto = None
                self._log(f"[midi] no pude abrir la entrada '{objetivo}': {self._ultimo_error}")
                return False

    @property
    def disponible(self) -> bool:
        return self.puerto is not None

    @property
    def error(self) -> str:
        return self._ultimo_error

    def cerrar(self) -> None:
        with self._lock:
            if self.puerto is not None:
                try:
                    self.puerto.close()
                except Exception:
                    pass
                self.puerto = None
                self.nombre_abierto = None

    # ── recepcion ──────────────────────────────────────────────────────────
    def _al_recibir(self, mensaje) -> None:
        """Callback de rtmidi (corre en su propio hilo)."""
        datos = normalizar(mensaje)
        if datos is None:
            return
        with self._lock:
            self._cola.append(datos)
            if len(self._cola) > self._max_cola:
                del self._cola[:len(self._cola) - self._max_cola]
            self._recibidos += 1
            self._ultimo = datos

    def leer(self) -> list[dict]:
        """Drena los mensajes recibidos (no bloquea)."""
        with self._lock:
            datos = self._cola
            self._cola = []
        return datos

    def estado(self) -> dict:
        return {
            "disponible": self.disponible,
            "puerto": self.nombre_abierto,
            "pedido": self.nombre_pedido,
            "error": self._ultimo_error,
            "entradas": self.entradas(),
            "recibidos": self._recibidos,
            "ultimo": self._ultimo,
        }

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg, flush=True)


def normalizar(mensaje) -> dict | None:
    """Convierte un mensaje mido en un dict simple (o None si no nos interesa)."""
    tipo = getattr(mensaje, "type", "")
    canal = getattr(mensaje, "channel", 0) + 1
    if tipo in ("note_on", "note_off"):
        valor = getattr(mensaje, "velocity", 0)
        if tipo == "note_off":
            valor = 0
        return {"tipo": "note", "num": mensaje.note, "canal": canal, "valor": valor}
    if tipo == "control_change":
        return {"tipo": "cc", "num": mensaje.control, "canal": canal, "valor": mensaje.value}
    if tipo == "program_change":
        return {"tipo": "pc", "num": mensaje.program, "canal": canal, "valor": mensaje.program}
    return None


if __name__ == "__main__":                                   # prueba rapida
    import sys
    print("salidas MIDI:", puertos_salida() or "(ninguna)")
    s = SalidaMidi(sys.argv[1] if len(sys.argv) > 1 else None)
    print("abierto:", s.estado())
    if s.disponible:
        print("→ nota 60 (do central) 1 s")
        s.nota(60, 100, 1)
        time.sleep(1)
        s.nota(60, 0, 1)
        print("→ CC 7 = 100")
        s.cc(7, 100, 1)
        time.sleep(0.3)
        s.panic()
        print("estado final:", s.estado())
    s.cerrar()
