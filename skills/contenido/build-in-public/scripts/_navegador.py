# -*- coding: utf-8 -*-
"""_navegador.py — localiza Chrome/Chromium/Edge y hace capturas headless de un HTML local."""
from __future__ import annotations

import os, shutil, subprocess, sys, tempfile
from pathlib import Path


def buscar_chrome(explicito: str | None = None) -> str | None:
    cand = [explicito, os.environ.get("CHROME_PATH")]
    if sys.platform == "win32":
        for base in filter(None, (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA"))):
            cand += [os.path.join(base, "Google/Chrome/Application/chrome.exe"),
                     os.path.join(base, "Chromium/Application/chrome.exe"),
                     os.path.join(base, "Microsoft/Edge/Application/msedge.exe")]
    elif sys.platform == "darwin":
        cand += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Chromium.app/Contents/MacOS/Chromium"]
    else:
        cand += [shutil.which(n) for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")]
    return next((c for c in cand if c and Path(c).exists()), None)


def capturar(html: Path, png: Path, ancho: int, alto: int, chrome: str | None = None) -> None:
    exe = buscar_chrome(chrome)
    if not exe:
        raise RuntimeError("No encontré Chrome/Chromium/Edge: indica la ruta con CHROME_PATH")
    perfil = tempfile.mkdtemp(prefix="bip-chrome-", dir=os.environ.get("BIP_TMP"))
    try:
        subprocess.run([exe, "--headless=new", "--hide-scrollbars", "--force-device-scale-factor=1", "--no-first-run",
                        f"--window-size={ancho},{alto}", f"--user-data-dir={perfil}", f"--screenshot={Path(png).resolve()}",
                        "--virtual-time-budget=2000", Path(html).resolve().as_uri()], check=True, capture_output=True, timeout=90)
    finally:
        shutil.rmtree(perfil, ignore_errors=True)
