# 🎮 Xbox 360 WebPad

**Convertí un celular en un mando Xbox 360 real para cualquier juego de PC.**

Un `.bat` levanta un servidor en la PC del juego, crea un **mando Xbox 360
virtual** (que el juego ve como un joystick USB conectado) y muestra un **QR**.
El celular escanea el QR, abre el pad en el navegador y todo lo que toca llega al
juego en tiempo real. Corre **en paralelo** al juego, sin tocar sus archivos.

Pensado para juegos hechos con **Unreal Engine / Unity / cualquier cosa que use
XInput** — incluidos juegos porteados que esperan un mando de Xbox 360 físico.

```
       CELULAR                              PC DEL JUEGO                     JUEGO
  ┌─────────────────┐   WebSocket    ┌──────────────────────────┐   XInput   ┌──────────┐
  │  pad web táctil │ ─────────────► │  server.py               │ ─────────► │ Unreal / │
  │  (navegador)    │    (wifi LAN)  │   └─ mando virtual X360  │  Xbox 360  │ Unity /  │
  └─────────────────┘                └──────────────────────────┘  virtual   │ lo que   │
          ▲                                       │                          │ sea      │
          └────────── QR + panel del operador ────┘                          └──────────┘
```

---

## ✨ Qué incluye

| | |
|---|---|
| 🕹️ **Pad táctil completo** | 2 sticks analógicos, A/B/X/Y, LB/RB, gatillos analógicos LT/RT, cruceta 8 direcciones, START/BACK/GUIDE, L3/R3 |
| 📱 **Sin instalar apps** | el celular solo abre una URL (QR). Funciona en iPhone y Android |
| 🎯 **Mando virtual real** | ViGEmBus + XInput: el juego lo ve como un *Xbox 360 Controller for Windows* |
| 🖥️ **Panel del operador** | QR grande, estado en vivo (sticks, gatillos, botones, latencia) y botón *Soltar todo* |
| 🧳 **Modo portable** | carpeta autocontenida con Python + dependencias + instalador del driver: se copia y funciona |
| 🛡️ **A prueba de cuelgues** | si el celular se duerme o se corta el wifi, libera todos los controles solo (nada de sticks trabados) |
| ✅ **Verificación incluida** | una prueba de punta a punta que simula el celular y **lee XInput** (lo mismo que lee el juego) |

---

## 🚀 Inicio rápido

### Opción A — Paquete portable (recomendado para la PC del juego)

1. Copiá la carpeta **`Xbox360WebPad-Portable`** a la PC del juego (USB, red, lo que sea).
2. Doble clic en **`iniciar-mando.bat`**.
   * La primera vez pide permiso de administrador **una sola vez**: instala el
     driver ViGEmBus (viene incluido en `drivers\`) y abre el puerto en el firewall.
3. Se abre el **panel del operador** con el QR.
4. Escaneá el QR con el celular, giralo en **horizontal** y jugá.

> No hace falta instalar Python ni nada: el paquete trae su propio runtime.

### Opción B — Desde el código (desarrollo)

```bat
git clone https://github.com/tolchx/Xbox360WebPad.git
cd Xbox360WebPad
iniciar-mando.bat
```

El `.bat` detecta si falta Python, el driver o las dependencias y los resuelve.
También se puede correr a mano:

```bat
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe server.py --port 8790 --open
```

### Arrancarlo **antes** que el juego

Varios juegos solo detectan mandos que ya están conectados cuando se abren. Si el
juego no responde al mando: cerrá el juego, dejá el `.bat` andando y volvé a abrirlo.

---

## 🕹️ El mando del celular

Diseñado para usarse en **horizontal**, como un mando real: los pulgares abajo y
los índices en los gatillos.

| Control | Acción |
|---|---|
| **Stick izquierdo** | mover (analógico, 360°) |
| **Stick derecho** | cámara / apuntar |
| **Toque corto en un stick** | click del stick (L3 / R3) |
| **A / B / X / Y** | botones de acción (colores Xbox) |
| **LB / RB** | hombros |
| **LT / RT** | gatillos **analógicos** (la barra muestra el recorrido) |
| **Cruceta** | D-Pad, acepta diagonales |
| **BACK / GUIDE / START** | botones centrales |
| **Píldora de estado** | conexión y latencia en ms ("conectado · 12 ms") |

Detalles pensados para jugar de verdad:

* **Multitáctil**: los dos sticks y los botones al mismo tiempo.
* **Sin zoom accidental**: bloquea pinch, doble toque, menú contextual y selección.
* **Pantalla despierta**: pide *wake lock* y pantalla completa al primer toque.
  Aun así, si la pantalla se apaga el sistema libera todo (no queda un stick trabado).
* **Reconexión automática** si se corta el wifi, con aviso en pantalla.
* **Latido**: reenvía el estado completo cada segundo para que el servidor sepa
  que el celular sigue ahí y libere todo a los ~3 s de silencio.
* **Aviso de rotar** si el celular está en vertical.

---

## 🖥️ Panel del operador

En la PC del juego → `http://127.0.0.1:8790/`

* **QR grande** + URL del pad, con selector si la PC tiene varias placas de red.
* **Estado en vivo**: sticks, gatillos, botones apretados, mensajes recibidos,
  celulares conectados y *señal hace X ms*.
* **Probar mando (pulso A)**: aprieta A durante 250 ms para comprobar que el juego responde.
* **Soltar todo**: libera todos los ejes y botones al instante.

El servidor también dibuja el **QR en la consola** y lista las URLs al arrancar.

---

## ⚙️ Opciones

```bat
iniciar-mando.bat                 :: puerto 8790 (por defecto)
iniciar-mando.bat 9000            :: otro puerto
iniciar-mando.bat --reinstalar    :: reinstala las dependencias de Python
iniciar-mando.bat --help
```

```bat
:: servidor a mano
.venv\Scripts\python.exe server.py [--port 8790] [--ip 192.168.x.x] [--open]
                                  [--no-pad]        :: sin mando virtual (solo web/estado)
                                  [--timeout-pad 3] :: segundos sin señal antes de liberar
                                  [--quiet]
```

---

## 📁 Estructura

```
iniciar-mando.bat        lanzador: driver + firewall + runtime + servidor
empaquetar-portable.bat  arma la carpeta portable (Python + deps + driver)
server.py                HTTP + WebSocket + QR + panel + integracion con el mando
mando_virtual.py         mando Xbox 360 virtual (vgamepad/ViGEmBus): deadzone,
                         gatillos, botones, reconexion automatica
requirements.txt         aiohttp, vgamepad, qrcode
web/
  index.html             panel del operador (QR + estado en vivo)
  pad.html               mando táctil para el celular
  pad.css                layout horizontal estilo Xbox 360
  pad.js                 multitáctil, sticks, gatillos, cruceta, latido
tools/
  xinput_win.py          lectura cruda de XInput (ctypes)
  verificar_xinput.py    monitor en vivo de lo que ve el juego
  prueba_completa.py     prueba automática punta a punta
  empaquetar_portable.py armado del paquete portable
drivers/                 (solo en el portable) instalador ViGEmBus
runtime/                 (solo en el portable) Python embebido + dependencias
```

---

## 🔌 Protocolo WebSocket

Todo pasa por `ws://IP:PUERTO/ws` con mensajes JSON. Sirve para escribir tu propio
cliente (otro celular, un control MIDI, un script, un bot).

```jsonc
// celular -> servidor
{"t":"hello","role":"pad","nombre":"mi-celular"}
{"t":"in","ls":[x,y],"rs":[x,y],"lt":0..1,"rt":0..1,
 "b":{"a":true,"lb":false,...}}      // x,y en -1..1 (arriba = -1)
{"t":"ping","ts":123.45}             // devuelve {"t":"pong","ts":...} para medir latencia
{"t":"soltar"}                       // libera todos los controles

// panel -> servidor
{"t":"hello","role":"panel"}
{"t":"soltar"} | {"t":"probar"}      // probar = pulso de A

// servidor -> panel (10 Hz)
{"t":"estado","mando":true,"conectados":1,"senal_hace_ms":42,
 "estado":{"ls":[0,0],"rs":[0,0],"lt":0,"rt":0,"b":{...}}}
```

Botones válidos: `a b x y lb rb start back guide l3 r3 up down left right`.

---

## ✅ Verificación (que el mando llegue de verdad al juego)

```bat
.venv\Scripts\python.exe tools\prueba_completa.py          :: prueba punta a punta
.venv\Scripts\python.exe tools\prueba_completa.py --forzar :: aunque haya otro celular conectado
.venv\Scripts\python.exe tools\verificar_xinput.py --seguir :: monitor en vivo
```

`prueba_completa.py` **simula el celular** por WebSocket, manda cada control y
después **lee XInput** —exactamente la misma API que usa Unreal Engine— y compara
valor por valor:

```
Todo suelto · Botón A · A+B+X+Y · LB+RB · LT 100% · RT 50% · Stick izq (ambos
sentidos) · Stick der · Cruceta en diagonal · L3+R3 · START+BACK · Soltar todo ·
Liberación al desconectarse · GUIDE llega al servidor
→ 15 pruebas OK, 0 con problemas
```

También podés abrirlo desde Windows: **`joy.cpl`** → aparece
*"Xbox 360 Controller for Windows"*. Es el mando virtual.

---

## 🧳 Empaquetar el portable

```bat
empaquetar-portable.bat
python tools\empaquetar_portable.py --salida "D:\Xbox360WebPad-Portable" --forzar
```

El script baja el **Python embebido** oficial, instala las dependencias dentro de
él (`aiohttp`, `vgamepad`, `qrcode`), baja el **instalador de ViGEmBus** desde su
release oficial, copia el código y verifica el runtime. Resultado: una carpeta
(~55 MB, ZIP ~25 MB) que funciona en cualquier Windows x64 **sin instalar nada**.

> Por qué funciona: el Python embebido ignora `PYTHONPATH`, así que el script
> instala `setuptools` dentro del runtime y usa `--no-build-isolation` (el paquete
> `vgamepad` solo se publica como código fuente). El lanzador exporta
> `PYTHONNOUSERSITE=1` para que el runtime no vea los paquetes del usuario.

---

## 🧯 Solución de problemas

**El celular no conecta.**
1. Tiene que estar en la **misma red wifi** que la PC (no datos móviles; las redes
   de invitados suelen aislar a los clientes entre sí).
2. Que exista la regla de firewall:
   `netsh advfirewall firewall show rule name=Xbox360WebPad`.
   Si falta, corré el `.bat` con **botón derecho → Ejecutar como administrador** una vez.
3. Probá desde el navegador del celular: `http://IP-DE-LA-PC:8790/pad`.

**El juego no reacciona.**
* Arrancá el `.bat` **antes** que el juego.
* En el panel, apretá **Probar mando (pulso A)**: si el juego responde, el mando
  llega y el problema es de la app del celular.
* Verificá en `joy.cpl` que aparece "Xbox 360 Controller for Windows".
* Algunos juegos con anticheat bloquean mandos virtuales: probá en modo ventana o
  desactivá el anticheat.

**Los sticks quedan "pegados".**
No debería pasar: el servidor libera todo a los 3 s sin señal, al desconectarse el
último celular y con el botón *Soltar todo* del panel. Si pasa, avisá con el log.

**El driver no instala.**
Corré `drivers\ViGEmBus_*.exe` a mano (como administrador). Si Windows pide
reiniciar, reiniciá: después el `.bat` arranca normal.

**Varios celulares a la vez.**
Funciona, pero gana el último que manda (no se mezclan los controles). Para jugar,
usá uno solo.

---

## 🧠 Notas técnicas y limitaciones

* **El botón GUIDE nunca llega a un juego XInput.** No es una limitación de este
  proyecto: la API `XInput` de Microsoft no expone el botón de guía (0x0400) ni en
  `XInputGetState` ni como `XInputGetKeystroke` — está reservado para el overlay del
  sistema. El servidor lo transporta igual (por si algún juego lee HID/RawInput),
  pero para menús conviene usar START/BACK.
* **Versión del driver.** `iniciar-mando.bat` instala ViGEmBus 1.22 (estable). Con
  la 1.17 de 2020 la **primera** lectura de XInput de cada proceso nuevo devuelve
  valores basura (el juego no lo nota porque consulta en bucle, pero una prueba que
  lee una sola vez puede dar falso negativo: se descartan las primeras lecturas).
* **Latencia.** El pad manda los cambios al instante (no espera un bucle fijo) y el
  servidor vuelca al mando a ~120 Hz. En wifi normal son 5–25 ms ida y vuelta; la
  píldora del celular muestra la medición real.
* **Cómo se aplica el estado.** En cada vuelco: `reset()` + reaplicar todo +
  `update()`. Es idempotente y evita estados colgados. La zona muerta de los sticks
  es **radial** con reescalado `(d - dz) / (1 - dz) / d`, así el movimiento arranca
  suave. El cliente manda Y en coordenadas de pantalla (arriba = -1) y el servidor
  lo invierte, porque XInput usa Y+ = arriba.
* **Puertos.** Por defecto **8790**. Si está ocupado, `iniciar-mando.bat 8791`.
* **Seguridad.** El servidor escucha en la red local (`0.0.0.0`) sin autenticación:
  cualquiera en tu red que abra la URL puede manejar el mando virtual. Usalo en
  redes de confianza; para cerrarlo, cerrá la ventana del `.bat` (Ctrl+C).

---

## 🙏 Créditos

* **[ViGEmBus](https://github.com/nefarius/ViGEmBus)** — Nefarius: el driver que
  hace posible el mando virtual (licencia BSD-3-Clause).
* **[vgamepad](https://github.com/yannbouteiller/vgamepad)** — bindings Python para ViGEm.
* **[aiohttp](https://github.com/aio-libs/aiohttp)** — servidor HTTP + WebSocket.
* **[qrcode](https://github.com/lincolnloop/python-qrcode)** — generación del QR.
* Xbox es una marca de Microsoft. Este proyecto es un emulador de mando para uso
  personal y no está afiliado ni patrocinado por Microsoft.

## 📄 Licencia

MIT — ver [LICENSE](LICENSE).
