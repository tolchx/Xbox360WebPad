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
  │  (navegador)    │    (wifi LAN)  │   ├─ mando virtual X360  │  Xbox 360  │ Unity /  │
  └─────────────────┘                │   └─ salida MIDI         │  virtual   │ lo que   │
          ▲                          └────────────┬─────────────┘            │ sea      │
          │                                       │ puerto MIDI virtual      └──────────┘
          └─── QR + panel del operador ────┐      ▼
                                           │  Resolume Arena / QLC+  (luces y video,
                                           └─ en paralelo al juego)
```

Hay **dos modos** en el mismo celular: 🎮 **JOYSTICK** (mando virtual para el juego) y
🎛️ **MIDI** (botonera con pads y faders para Resolume / QLC+), y además el joystick puede
mandar MIDI **mientras jugás** (ver *Modo MIDI* más abajo).

---

## ✨ Qué incluye

| | |
|---|---|
| 🕹️ **Pad táctil completo** | 2 sticks analógicos, A/B/X/Y, LB/RB, gatillos analógicos LT/RT, cruceta 8 direcciones, START/BACK/GUIDE, L3/R3 |
| 🎛️ **Botonera MIDI** | el mismo celular, con un toque, se convierte en una **botonera MIDI personalizable** (pads + faders) para manejar **Resolume** o **QLC+** en paralelo al juego |
| 🎯 **MIDI learn** | en vez de tipear el número: armás el control en el panel (botones, faders y las filas del joystick) y mandás la señal (mesa de luz, QLC+, Resolume) y queda aprendida |
| 🕹️ **Joystick → MIDI** | mientras jugás, botones, gatillos y sticks también mandan MIDI (sticks/gatillos como CC continuos, botones como notas) |
| 📱 **Sin instalar apps** | el celular solo abre una URL (QR). Funciona en iPhone y Android |
| 🎯 **Mando virtual real** | ViGEmBus + XInput: el juego lo ve como un *Xbox 360 Controller for Windows* |
| 🖥️ **Panel del operador** | QR grande, estado en vivo (sticks, gatillos, botones, latencia) y botón *Soltar todo* |
| 🧳 **Modo portable** | carpeta autocontenida con Python + dependencias + instaladores de **ViGEmBus y loopMIDI**: se copia y funciona |
| 🛡️ **A prueba de cuelgues** | si el celular se duerme o se corta el wifi, libera todos los controles solo (nada de sticks trabados) |
| ✅ **Verificación incluida** | pruebas de punta a punta que simulan el celular: **15 del joystick** (leyendo XInput, lo mismo que lee el juego) y **19 de MIDI** (escuchando el puerto virtual) |

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

## 🎛️ Modo MIDI (luces y video)

Arriba de todo, en el celular, hay dos modos: **🎮 JOYSTICK** y **🎛️ MIDI**. En
modo MIDI el mando se convierte en una **botonera personalizable** que manda
mensajes MIDI reales por un puerto virtual de Windows, así podés manejar
**Resolume Arena** y **QLC+** mientras el joystick sigue manejando el juego.

```
CELULAR (botonera MIDI) ──WebSocket──► server.py ──► puerto MIDI virtual ──► Resolume / QLC+
```

### Puesta en marcha (una sola vez)

1. **loopMIDI** (https://www.tobias-erichsen.de/software/loopmidi.html) — gratis,
   crea los puertos MIDI virtuales en Windows. En el **paquete portable ya viene el
   instalador** (`drivers\loopMIDISetup*.zip`): el `.bat` lo instala solo la primera
   vez (pide admin), **crea el puerto** `loopMIDI Port` y lo abre.
2. Dejar **loopMIDI corriendo** (se abre solo): los puertos existen solo mientras la
   aplicación está abierta. Si no hay puerto, el modo MIDI queda sin salida y la PC
   igual funciona con el joystick.
3. En **Resolume**: *Preferences → MIDI* → elegir `loopMIDI Port` como input, activar
   **MIDI map** y tocar en pantalla el control que quieras asignar; después apretás
   el botón en el celular.
4. En **QLC+**: *Inputs/Outputs* → agregar el mismo puerto como **Input** → usar el
   asistente de mapeo (o el *Virtual Console* con botones).
5. En el **panel** de la PC hay una tarjeta **MIDI** para elegir el puerto, probar
   (`Probar MIDI`), silenciar todo (`panic`) y **editar el mapeo**.

### Mapeo (qué manda cada botón)

Cada banco tiene hasta 24 botones y 10 faders. Cada botón define:

| Campo | Qué es |
|---|---|
| **Etiqueta** | el texto que se ve en el celular (ej. `COL 1`) |
| **Tipo** | `note` (nota MIDI), `cc` (control continuo), `pc` (program change) |
| **N°** | número MIDI (0–127) |
| **Canal** | 1–16 |
| **Modo** | `momento` (suena mientras apretás) · `toggle` (prende/apaga) · `disparo` (pulso corto automático) · `fijo` (solo encender) |
| **Color** | color del botón en el celular |

Los **faders** mandan CC de 0 a 127 de forma continua mientras los arrastrás
(ideal para opacidad, velocidad de clip, dimmer de luces).

Vienen dos bancos de fábrica listos para mapear: **RESOLUME** (notas 36–51 + CC 7–10)
y **QLC+** (notas 60–75 + CC 11–14). Se editan desde el panel de la PC
(tarjeta *3 · MIDI*) y se guardan en `midi-mapa.json`:

```jsonc
{
  "version": 1,
  "puerto": "loopMIDI Port",       // puerto virtual de salida
  "joystick_activo": true,         // ¿el joystick manda MIDI mientras jugás?
  "joystick": [                    // mapeo del mando -> MIDI
    {"control": "a",  "tipo": "note", "num": 36, "canal": 1, "modo": "momento", "umbral": 0.6},
    {"control": "rt", "tipo": "cc",   "num": 8,  "canal": 1, "modo": "momento", "invertir": false}
  ],
  "paginas": [                     // bancos de la botonera del celular
    {"nombre": "RESOLUME",
     "botones": [{"id": "r1", "etiqueta": "COL 1", "tipo": "note", "num": 36,
                  "canal": 1, "modo": "momento", "color": "#ff5c7a"}],
     "faders":  [{"id": "rf1", "etiqueta": "OPACIDAD", "tipo": "cc", "num": 7, "canal": 1}]}
  ]
}
```

Botón **SILENCIAR** (panic): manda *all notes off* en los 16 canales y apaga todo
lo que haya quedado prendido. El servidor también lo hace solo cuando cerrás el
mando, cuando el celular se desconecta o cuando volvés al modo joystick: **nunca
queda una luz o un clip colgado**.

---

### 🎯 MIDI learn (aprender el número en vez de tipearlo)

En cada fila del mapeo hay un botón **🎯**. Lo apretás, el panel (y el celular)
muestran *"aprendiendo: COL 5"* y quedan esperando la próxima señal MIDI:

- **desde otro programa**: activá MIDI-mapping en Resolume o QLC+, tocá el control
  en pantalla → la señal vuelve por el puerto virtual y el panel la captura;
- **desde la mesa de luz / controlador físico**: movés el fader o tocás el pad y
  listo, queda con ese número, canal y tipo;
- **desde el celular**: apretás un pad y el control armado **copia** el número de
  ese pad.

Se guarda solo y el celular se actualiza. `cancelar` aborta el aprendizaje (y a los
60 s se cancela solo).

Funciona igual en **las filas del joystick → MIDI**: armás el 🎯 de *A* y la próxima
señal que llegue define qué nota manda el botón A mientras jugás.

> Para que funcione, el servidor abre el **puerto virtual como entrada**
> (`loopMIDI Port 0`); el panel muestra su estado en la píldora *entrada (learn)*.
> El learn ignora los mensajes que manda el propio servidor: loopMIDI devuelve todo
> lo que se le escribe, así que sin ese filtro se "aprendía" el panic (`CC 120`).

### 🕹️ Joystick → MIDI (controlar el juego **y** las luces a la vez)

Mientras jugás con el mando, cada control puede disparar MIDI en paralelo. Se
configura en la tarjeta MIDI del panel: **switch de encendido** + tabla de mapeos.

| Columna | Qué hace |
|---|---|
| **Control** | A, B, X, Y, LB, RB, START, BACK, L3, R3, cruceta, gatillos LT/RT, sticks (↔ ↕) |
| **Tipo** | `note` (con umbral), `cc` (continuo 0-127) o `pc` |
| **N° / Canal** | número MIDI y canal 1-16 |
| **Modo** | `momento`, `toggle`, `disparo` (pulso corto), `fijo` |
| **Umbral** | para gatillos/sticks: a partir de qué valor se considera "apretado" (0.05-0.95) |
| **Inv.** | invierte el eje/gatillo |

Ejemplos útiles:

- **A/B/X/Y → notas** 36-39: disparar clips de Resolume mientras jugás.
- **LT/RT → CC 7/8**: opacidad/velocidad continuas con los gatillos.
- **Stick izquierdo ↔ → CC 9**: crossfader de Resolume manejado con el stick.
- **Umbral alto + modo `disparo`**: un golpe de gatillo = un pulso, sin dejar nada prendido.

El botón **preset** carga de una: sticks y gatillos como CC 7-12 + A/B/X/Y/LB/RB como
notas 36-41. El mapeo viene **listo pero apagado** (`"joystick_activo": false`): hasta
que no prendas el switch, el joystick solo maneja el juego y no manda MIDI.

### 🔌 El puerto virtual (loopMIDI)

El `.bat` se encarga: si no hay puerto MIDI, **instala loopMIDI** desde
`drivers\loopMIDISetup*.zip` (pide admin una vez), **crea el puerto** `loopMIDI Port`
en la configuración del usuario y **abre loopMIDI**, que tiene que quedar corriendo
(los puertos existen solo mientras la app está abierta).

### 🎛️ Panel del operador

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
iniciar-mando.bat        lanzador: driver + firewall + runtime + puerto MIDI + servidor
empaquetar-portable.bat  arma la carpeta portable (Python + deps + instaladores)
server.py                HTTP + WebSocket + QR + panel + mando virtual + MIDI
mando_virtual.py         mando Xbox 360 virtual (vgamepad/ViGEmBus): deadzone,
                         gatillos, botones, reconexion automatica
midi_salida.py           MIDI (mido/rtmidi): salida de notas/CC + panic + reconexion,
                         y entrada para MIDI learn (escucha el puerto virtual)
midi-mapa.json           mapeo MIDI (bancos, botones, faders, joystick -> MIDI)
requirements.txt         aiohttp, vgamepad, qrcode, mido, python-rtmidi
web/
  index.html             panel del operador (QR + estado + editor de mapeo MIDI)
  pad.html               mando táctil (joystick + botonera MIDI)
  pad.css                layout horizontal estilo Xbox 360 + botonera
  pad.js                 multitáctil, sticks, gatillos, cruceta, MIDI, latido
tools/
  xinput_win.py          lectura cruda de XInput (ctypes)
  verificar_xinput.py    monitor en vivo de lo que ve el juego
  prueba_completa.py     prueba automática punta a punta (joystick)
  prueba_midi.py         prueba MIDI punta a punta (loopback por el puerto virtual)
  midi_listo.py          asegura que haya un puerto MIDI virtual
  empaquetar_portable.py armado del paquete portable
drivers/                 (solo en el portable) instaladores ViGEmBus + loopMIDI
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
{"t":"modo","modo":"joy"|"midi"}     // cambia de modo (libera lo que estaba activo)
{"t":"midi","accion":"press","id":"r1"}          // apretar un botón del mapeo
{"t":"midi","accion":"release","id":"r1"}        // soltarlo
{"t":"midi","accion":"cc","id":"rf1","valor":99} // fader (0-127)
{"t":"midi-panic"}                   // all notes off

// panel -> servidor
{"t":"hello","role":"panel"}
{"t":"soltar"} | {"t":"probar"}                  // joystick
{"t":"midi-probar"} | {"t":"midi-panic"}
{"t":"midi-puerto","puerto":"loopMIDI Port"}     // elegir puerto MIDI
{"t":"midi-mapa","mapa":{...}}                   // guardar el mapeo (incluye joystick -> MIDI)
{"t":"midi-learn","id":"r5"}                     // MIDI learn: capturar la próxima señal
{"t":"midi-learn","id":null}                     // cancelar el aprendizaje

// servidor -> panel (10 Hz)
{"t":"estado","mando":true,"conectados":1,"senal_hace_ms":42,"modo":"midi",
 "midi":{"disponible":true,"puerto":"loopMIDI Port 1","mensajes":12,...},
 "midi_in":{"disponible":true,"puerto":"loopMIDI Port 0",...},   // entrada (learn)
 "aprender":"r5",                                                // control en learn o null
 "estado":{"ls":[0,0],"rs":[0,0],"lt":0,"rt":0,"b":{...}}}

// servidor -> celular
{"t":"hola","mapa":{...},"modo":"joy","toggles":{"r9":true}}
{"t":"mapa","mapa":{...}}            // el mapeo cambió en el panel
{"t":"midi-estado","id":"r9","on":true}   // estado de un botón toggle
{"t":"aprender","id":"r5","etiqueta":"COL 5"}   // hay un control en MIDI learn (o id null)
```

Botones del joystick: `a b x y lb rb start back guide l3 r3 up down left right`.

HTTP: `GET /api/midi` (estado + mapeo) · `POST /api/midi/puerto` ·
`POST /api/midi/mapa` · `POST /api/midi/probar` · `POST /api/midi/panic`.

---

## ✅ Verificación (que el mando llegue de verdad al juego)

```bat
.venv\Scripts\python.exe tools\prueba_completa.py          :: joystick: 15 pruebas
.venv\Scripts\python.exe tools\prueba_completa.py --forzar :: aunque haya otro celular conectado
.venv\Scripts\python.exe tools\verificar_xinput.py --seguir :: monitor en vivo
.venv\Scripts\python.exe tools\prueba_midi.py              :: MIDI: 19 pruebas (loopback real)
.venv\Scripts\python.exe tools\midi_listo.py               :: ¿hay puerto MIDI listo?
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

`prueba_midi.py` hace lo mismo que la anterior pero para el **modo MIDI**: escucha
el puerto MIDI virtual y comprueba que los toques del celular salgan de verdad como
`note_on` / `note_off` / `CC`, que los botones *toggle* y *disparo* se comporten
como corresponde y que al desconectarse no quede ninguna nota sonando:

```
botón momento (apretar/soltar) · toggle (encender/apagar) · disparo (auto-off)
fader -> CC · joystick -> MIDI (nota y CC continuo, con umbral y deadband)
MIDI learn desde el puerto · MIDI learn en una fila del joystick
learn: ignora el eco de lo que manda el propio servidor
vuelta a joystick (panic) · libera al desconectarse · UI: `hidden` le gana a `display:flex`
→ 19 pruebas OK, 0 con problemas
```

Ninguna prueba deja el mapeo tocado: guardan `midi-mapa.json` al empezar y lo
restauran al terminar (si no, quedarían los números de prueba).

---

## 🧳 Empaquetar el portable

```bat
empaquetar-portable.bat
python tools\empaquetar_portable.py --salida "D:\Xbox360WebPad-Portable" --forzar
```

El script baja el **Python embebido** oficial, instala las dependencias dentro de
él (`aiohttp`, `vgamepad`, `qrcode`, `mido`, `python-rtmidi`), baja el **instalador de
ViGEmBus** desde su release oficial y el de **loopMIDI** (el puerto MIDI virtual),
copia el código y verifica el runtime. Resultado: una carpeta (~61 MB, ZIP ~33 MB) que
funciona en cualquier Windows x64 **sin instalar nada**.

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

**"El puerto 8790 ya está en uso".**
El `.bat` se niega a arrancar un segundo mando a propósito: Windows deja que **dos
servidores escuchen el mismo puerto a la vez** y entonces los celulares se reparten
entre los dos (síntoma raro: el mando "a veces" no responde). Cerrá la otra ventana
del `Xbox360WebPad`, o arrancá este en otro puerto: `iniciar-mando.bat 8791`.

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

**El MIDI no llega a Resolume / QLC+.**
1. Tiene que existir el puerto virtual: abrí **loopMIDI** y creá un puerto (o dejá
   el que trae por defecto). El panel muestra el estado: si dice *sin puerto*,
   todavía no está.
2. En el panel, elegí el puerto en la lista y apretá **Usar ese puerto**; después
   `Probar MIDI (nota 60)`: si el programa tiene el puerto como input, vas a verlo
   entrar en su indicador de MIDI.
3. En Resolume/QLC+ hay que **activar el input** y mapear: el pad no adivina los
   controles, solo manda las notas/CC que definas en el mapeo.
4. Verificá la cadena completa sin los programas:
   `tools\prueba_midi.py` (escucha el puerto virtual y reporta 19/19: botones, faders,
joystick->MIDI, MIDI learn y panic).

**El botón 🎯 no aprende nada.**
1. Mirá la píldora **entrada (learn)** del panel: si dice *sin entrada*, el servidor no
   pudo abrir el puerto virtual como entrada → cerrá el programa que lo tenga tomado en
   exclusivo (o reiniciá loopMIDI) y volvé a intentar.
2. La señal tiene que **llegar** al puerto virtual: si estás tocando el control en
   Resolume/QLC+, activá primero su *MIDI map / output*; si usás una mesa de luz, tiene
   que estar ruteada a ese puerto.
3. El learn se cancela solo a los 60 s. Si dice *aprendiendo* y no pasa nada, mandá la
   señal otra vez.

**El celular parece tener la versión vieja** (dos capas superpuestas, un botón que no
existe en el panel).
El servidor manda `no-store` en `/static/`, pero algunos navegadores móviles igual
guardan: cerrá la pestaña, reabrí el QR o hacé una recarga forzada (en iOS: mantener
recargar; en Android: borrar datos del sitio). Si tocaste el CSS del pad y ves el mando
y la botonera MIDI encimados, falta la regla `[hidden]{display:none !important}`
(ver *Notas técnicas*).

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
* **`hidden` vs `display:flex` (si tocás el CSS del pad).** Las capas del celular
  (`#capa-joy` / `#capa-midi`) se muestran y ocultan con el atributo `hidden`, pero
  un `display:flex` en la clase **le gana** al `hidden`: sin la regla
  `[hidden]{display:none !important}` la botonera MIDI queda dibujada encima del
  mando Xbox y el switch parece no hacer nada. Es un bug que ya pasó una vez; la
  guarda de UI de `prueba_midi.py` lo vigila.
* **Puertos.** Por defecto **8790**. Si está ocupado, `iniciar-mando.bat 8791`.
* **Seguridad.** El servidor escucha en la red local (`0.0.0.0`) sin autenticación:
  cualquiera en tu red que abra la URL puede manejar el mando virtual. Usalo en
  redes de confianza; para cerrarlo, cerrá la ventana del `.bat` (Ctrl+C).

---

## 🆕 Cambios recientes

**18/09/2026 — MIDI completo (aprender mapeos y manejar luces mientras jugás)**

* **🎯 MIDI learn**: cada fila del mapeo (botones, faders y las del joystick) tiene un
  botón para *aprender* la próxima señal en vez de tipear el número.
* **🕹️ Joystick → MIDI**: el mando manda notas/CC en paralelo al juego (sticks y
  gatillos continuos, botones con umbral y modos), con preset incluido y **apagado
  por defecto**.
* **🔌 loopMIDI automático**: el paquete portable trae el instalador; el `.bat` lo
  instala si falta, crea el puerto `loopMIDI Port` y abre la app (los puertos existen
  solo mientras corre).
* **Robustez MIDI**: *panic* automático al desconectarse, filtro de eco (loopMIDI
  devuelve lo que uno mismo escribe) y reconexión sola si se cae el puerto.
* **Fixes**: el `.bat` no arranca un segundo servidor si el puerto ya está en uso (en
  Windows dos servidores pueden escuchar el mismo puerto y repartirse los celulares);
  la botonera MIDI ya no se superpone al mando (`hidden` vs `display:flex`);
  el celular ya no se queda con `pad.js` viejo en caché tras una actualización.
* **Pruebas**: 19 casos MIDI (con loopback real por el puerto virtual) + 15 del joystick.

**17/09/2026 — versión inicial**

* Mando Xbox 360 virtual controlado por celular: ViGEmBus + XInput, pad táctil por QR
  y WebSocket, panel del operador con estado en vivo.
* Modo MIDI (botonera para Resolume / QLC+ en paralelo al juego).
* Paquete portable autocontenido: Python embebido + dependencias + instaladores.

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
