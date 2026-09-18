# -*- coding: utf-8 -*-
"""
Empaquetar el sistema como carpeta portable
===========================================

Arma una carpeta (y un ZIP) que se puede copiar a cualquier PC Windows y
funciona **sin instalar nada**: trae su propio Python, las dependencias y el
instalador del driver ViGEmBus.

Uso (desde la raiz del proyecto, con cualquier Python 3.9+):

    python tools/empaquetar_portable.py
    python tools/empaquetar_portable.py --salida "D:\\Xbox360WebPad-Portable"
    python tools/empaquetar_portable.py --sin-driver      (no baja el instalador)
    python tools/empaquetar_portable.py --sin-zip

Requiere internet solo para bajar el Python embebido, las dependencias y (si
corresponde) el instalador ViGEmBus.  Una vez armado, el paquete es 100 % offline.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

PY_VERSION = "3.12.10"                       # misma rama que los wheels cp312
PY_URL = (f"https://www.python.org/ftp/python/{PY_VERSION}/"
          f"python-{PY_VERSION}-embed-amd64.zip")
GETPIP_URL = "https://bootstrap.pypa.io/get-pip.py"
VIGEM_API = "https://api.github.com/repos/nefarius/ViGEmBus/releases/latest"

ARCHIVOS = [
    "server.py",
    "mando_virtual.py",
    "requirements.txt",
    "iniciar-mando.bat",
    "README.md",
]
CARPETAS = ["web", "tools"]


def log(msg: str) -> None:
    print(f"  {msg}", flush=True)


def bajar(url: str, destino: Path) -> None:
    log(f"bajando {url}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as r, open(destino, "wb") as f:
        shutil.copyfileobj(r, f)
    log(f"  -> {destino.name} ({destino.stat().st_size / 1024 / 1024:.1f} MB)")


def json_url(url: str) -> dict:
    import json
    req = urllib.request.Request(url, headers={"User-Agent": "Xbox360WebPad-packager"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def correr(args: list[str], env: dict | None = None, cwd: Path | None = None) -> None:
    log("> " + " ".join(str(a) for a in args))
    subprocess.run(args, check=True, env=env, cwd=str(cwd or RAIZ))


def preparar_python(salida: Path) -> Path:
    """Python embebido + pip + dependencias dentro de runtime/python."""
    runtime = salida / "runtime" / "python"
    exe = runtime / "python.exe"
    cache = salida / "tmp"

    if not exe.exists():
        zip_tmp = cache / f"python-{PY_VERSION}-embed-amd64.zip"
        if not zip_tmp.exists():
            bajar(PY_URL, zip_tmp)
        log(f"extrayendo Python {PY_VERSION} embebido")
        runtime.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_tmp) as z:
            z.extractall(runtime)
        # habilitar site-packages + site (sin esto no se importan las libs)
        pth = next(runtime.glob("python*._pth"))
        mayor, menor = PY_VERSION.split(".")[:2]
        pth.write_text(f"python{mayor}{menor}.zip\n.\nLib\\site-packages\nimport site\n",
                       encoding="utf-8")
        (runtime / "Lib" / "site-packages").mkdir(parents=True, exist_ok=True)
    else:
        log("Python embebido ya presente")

    # pip dentro del runtime embebido
    tiene_pip = subprocess.run([str(exe), "-m", "pip", "--version"],
                               capture_output=True).returncode == 0
    if not tiene_pip:
        getpip = cache / "get-pip.py"
        if not getpip.exists():
            bajar(GETPIP_URL, getpip)
        correr([str(exe), str(getpip), "--no-warn-script-location"])

    # setuptools/wheel: vgamepad solo publica sdist y el embebido ignora PYTHONPATH
    correr([str(exe), "-m", "pip", "install", "--disable-pip-version-check", "-q",
            "--ignore-installed", "setuptools", "wheel"], env=entorno())

    # las dependencias del proyecto
    correr([str(exe), "-m", "pip", "install", "--disable-pip-version-check", "-q",
            "--no-build-isolation", "--ignore-installed", "-r",
            str(RAIZ / "requirements.txt")], env=entorno())
    return runtime


def entorno() -> dict:
    """PYTHONNOUSERSITE: que el runtime portable no vea los paquetes del usuario."""
    env = dict(os.environ)
    env["PYTHONNOUSERSITE"] = "1"
    return env


def preparar_driver(salida: Path) -> None:
    destino = salida / "drivers"
    destino.mkdir(parents=True, exist_ok=True)
    if any(destino.glob("ViGEmBus*.exe")):
        log("instalador ViGEmBus ya presente")
        return
    try:
        datos = json_url(VIGEM_API)
        exe = next(a for a in datos["assets"] if a["name"].lower().endswith(".exe"))
        bajar(exe["browser_download_url"], destino / exe["name"])
    except Exception as exc:                     # pragma: no cover
        log(f"AVISO: no pude bajar el instalador ViGEmBus ({exc})")
        log("       el .bat va a intentar instalarlo con winget")


def copiar_codigo(salida: Path) -> None:
    for nombre in ARCHIVOS:
        origen = RAIZ / nombre
        if origen.exists():
            shutil.copy2(origen, salida / nombre)
    for carpeta in CARPETAS:
        origen = RAIZ / carpeta
        if not origen.exists():
            continue
        destino = salida / carpeta
        if destino.exists():
            shutil.rmtree(destino)
        shutil.copytree(origen, destino,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def verificar(salida: Path) -> bool:
    exe = salida / "runtime" / "python" / "python.exe"
    if not exe.exists():
        log("ERROR: falta el runtime")
        return False
    prueba = ("import aiohttp, vgamepad, qrcode;"
              "vgamepad.VX360Gamepad();"
              "print('runtime OK -> aiohttp', aiohttp.__version__)")
    r = subprocess.run([str(exe), "-c", prueba], env=entorno(), cwd=str(salida),
                       capture_output=True, text=True)
    salida_prueba = (r.stdout or "").strip() or (r.stderr or "").strip().splitlines()[-1:] 
    if isinstance(salida_prueba, list):
        salida_prueba = salida_prueba[0] if salida_prueba else ""
    print(f"   {salida_prueba}")
    return r.returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Arma el paquete portable de Xbox 360 WebPad")
    ap.add_argument("--salida", default=str(RAIZ.parent / "Xbox360WebPad-Portable"))
    ap.add_argument("--sin-driver", action="store_true")
    ap.add_argument("--sin-zip", action="store_true")
    ap.add_argument("--forzar", action="store_true", help="borra la salida y la rehace")
    args = ap.parse_args()

    salida = Path(args.salida).resolve()
    print(f"\n  Empaquetando Xbox 360 WebPad portable en:\n  {salida}\n")

    if args.forzar and salida.exists():
        log("borrando salida anterior")
        shutil.rmtree(salida)
    salida.mkdir(parents=True, exist_ok=True)

    log("[1/5] Python embebido + dependencias")
    preparar_python(salida)

    log("[2/5] Instalador del driver ViGEmBus")
    if args.sin_driver:
        log("omitido (--sin-driver)")
    else:
        preparar_driver(salida)

    log("[3/5] Copiando el codigo del proyecto")
    copiar_codigo(salida)

    log("[4/5] Verificando el runtime portable")
    ok = verificar(salida)

    # los zip/pip de armado no van al paquete final
    shutil.rmtree(salida / "tmp", ignore_errors=True)

    if not args.sin_zip:
        log("[5/5] Comprimiendo")
        archivo = shutil.make_archive(str(salida) + "-" + PY_VERSION, "zip",
                                      root_dir=salida.parent, base_dir=salida.name)
        log(f"ZIP: {archivo} ({Path(archivo).stat().st_size / 1024 / 1024:.1f} MB)")

    total = sum(f.stat().st_size for f in salida.rglob("*") if f.is_file())
    print(f"\n  Listo. Carpeta: {salida}")
    print(f"  Tamano: {total / 1024 / 1024:.1f} MB  |  runtime {'OK' if ok else 'CON PROBLEMAS'}")
    print("\n  Para usarlo en la PC del juego: copiar la carpeta y doble clic en iniciar-mando.bat\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
