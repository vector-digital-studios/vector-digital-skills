#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
montar.py — convierte la captura de grabar.js en un video pulido (MP4) y, opcionalmente, un GIF.

Uso rápido (montaje automático, sin configurar nada):
    python scripts/montar.py <carpeta_de_salida_de_grabar> --mp4 demo.mp4 --gif demo.gif

Uso fino (control total del ritmo, zoom y rótulos):
    python scripts/montar.py montaje.json            # ver templates/montaje-ejemplo.json

Qué hace con cada segmento (frames-<nombre>/ + frames.json + eventos.json):
  - reconstruye la línea de tiempo real (el screencast es de cadencia variable),
  - cámara con muelle críticamente amortiguado que sigue al puntero (nunca estática),
  - zoom automático hacia cada clic/escritura (o por keyframes si se indican),
  - dibuja un cursor limpio con animación de pulsación,
  - rótulos opcionales con rampas de opacidad, fundido entre segmentos,
  - codifica con ffmpeg (libx264, yuv420p) y genera GIF con paleta optimizada.

Requisitos: Python 3.9+, Pillow, ffmpeg con libx264 (ruta en "ffmpeg" del JSON, variable FFMPEG o PATH).
"""
import argparse, json, math, os, shutil, subprocess, sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:  # mensaje claro en vez de traza
    sys.exit("ERROR: falta Pillow. Ejecuta con: uv run --with pillow python scripts/montar.py …")

AQUI = Path(__file__).resolve().parent.parent
ACENTO = (255, 106, 0)


def smoothstep(a, b, x):
    if a == b:
        return float(x >= b)
    u = max(0.0, min(1.0, (x - a) / (b - a)))
    return u * u * (3.0 - 2.0 * u)


def muelle(valor, velocidad, objetivo, omega, dt):
    """Paso analítico estable de x'' + 2ωx' + ω²x = ω²·objetivo. Devuelve (valor, velocidad)."""
    d = valor - objetivo
    k = math.exp(-omega * dt)
    return (objetivo + (d + (velocidad + omega * d) * dt) * k,
            (velocidad - omega * (velocidad + omega * d) * dt) * k)


def buscar_ffmpeg(cfg):
    for c in (cfg.get("ffmpeg"), os.environ.get("FFMPEG"), shutil.which("ffmpeg")):
        if c and (Path(c).exists() or shutil.which(c)):
            return c
    sys.exit("ERROR: no encontré ffmpeg. Instálalo o indica su ruta en la variable FFMPEG.")


def cargar_fuente(cfg, tam):
    for c in (cfg.get("font"), AQUI / "templates" / "fonts" / "Sora.ttf"):
        if c and Path(c).exists():
            f = ImageFont.truetype(str(c), tam)
            try:  # fuente variable (Sora): usar un peso legible
                f.set_variation_by_name(cfg.get("font_weight", "SemiBold"))
            except Exception:
                pass
            return f
    try:
        return ImageFont.load_default(tam)
    except TypeError:
        return ImageFont.load_default()


def hacer_cursor(w, h):
    """Puntero blanco con borde oscuro fino y sombra difusa."""
    s = 4
    lienzo = Image.new("RGBA", (32 * s, 38 * s), (0, 0, 0, 0))
    pts = [(x * s, y * s) for x, y in [(3, 2), (3, 25), (9, 19), (14, 31), (19, 29), (14, 18), (24, 18)]]
    sombra = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
    ImageDraw.Draw(sombra).polygon([(x + 2 * s, y + 2 * s) for x, y in pts], fill=(0, 0, 0, 115))
    lienzo.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(1.25 * s)))
    ImageDraw.Draw(lienzo).polygon(pts, fill=(252, 252, 252, 255), outline=(20, 20, 22, 255), width=s)
    return lienzo.resize((w, h), Image.Resampling.LANCZOS)


class Segmento:
    def __init__(self, cfg, raiz, fps, glob):
        self.cfg, self.fps = cfg, fps
        self.dir = Path(raiz) / cfg["dir"]
        self.items = json.loads((self.dir / "frames.json").read_text(encoding="utf-8"))
        if not self.items:
            raise ValueError("segmento sin frames: " + str(self.dir))
        ev = self.dir / "eventos.json"
        self.eventos = json.loads(ev.read_text(encoding="utf-8")) if ev.exists() else []
        self.tiempos = [e["t"] for e in self.items]
        self.t_ini = cfg.get("desde_ms", self.tiempos[0])
        if cfg.get("time_map"):
            self.tm = cfg["time_map"]
            self.frames = round(self.tm[-1][0] * fps)
        else:
            self.tm = None
            self.speed = cfg.get("speed", glob.get("speed", 1.0))
            self.frames = round((self.tiempos[-1] - self.t_ini) / 1000.0 / self.speed * fps) + cfg.get("extra_tail", 0)
        az = cfg.get("auto_zoom", glob.get("auto_zoom", {}))
        self.az = None if az is False else {"base": 1.12, "foco": 1.5, **(az or {})}
        self.press = cfg.get("press_ms", [e["t"] for e in self.eventos if e.get("tipo") == "click"])
        self.cache = {}

    def src_ms(self, ahora):
        if self.tm:
            for (oa, sa), (ob, sb) in zip(self.tm, self.tm[1:]):
                if ahora <= ob:
                    u = 0.0 if ob == oa else (ahora - oa) / (ob - oa)
                    return sa + max(0.0, min(1.0, u)) * (sb - sa)
            return self.tm[-1][1]
        return min(self.t_ini + ahora * 1000.0 * self.speed, self.tiempos[-1])

    def zoom(self, ms):
        kf = self.cfg.get("zoom_keyframes")
        if kf:
            if ms <= kf[0][0]:
                return kf[0][1]
            for (at, az), (bt, bz) in zip(kf, kf[1:]):
                if ms <= bt:
                    return az + (bz - az) * smoothstep(at, bt, ms)
            return kf[-1][1]
        if not self.az:
            return 1.0
        env = 0.0
        for e in self.eventos:  # acercamiento antes de cada clic/escritura y suelta después
            t0 = e["t"]
            hold = 1400 if e.get("tipo") == "type" else 700
            env = max(env, smoothstep(t0 - 900, t0 - 200, ms) * (1.0 - smoothstep(t0 + hold, t0 + hold + 900, ms)))
        return self.az["base"] + (self.az["foco"] - self.az["base"]) * env

    def meta(self, ms):
        lo, hi = 0, len(self.items) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.tiempos[mid] <= ms:
                lo = mid
            else:
                hi = mid - 1
        if lo >= len(self.items) - 1:
            e = self.items[-1]
            return float(e["x"]), float(e["y"]), e["i"]
        a, b = self.items[lo], self.items[lo + 1]
        u = max(0.0, min(1.0, (ms - a["t"]) / max(1.0, b["t"] - a["t"])))
        return a["x"] + (b["x"] - a["x"]) * u, a["y"] + (b["y"] - a["y"]) * u, (a["i"] if u < 0.5 else b["i"])

    def imagen(self, idx):
        im = self.cache.get(idx)
        if im is None:
            with Image.open(self.dir / f"f{idx:05d}.jpg") as src:
                im = src.convert("RGB")
            self.cache = {idx: im}
        return im

    def pulsacion(self, ms):
        p = 0.0
        for c in self.press:
            d = abs(ms - c)
            if d < 110:
                p = max(p, (1.0 - d / 110.0) ** 2)
        return p


def dibujar_rotulo(frame, ahora, rotulos, fuente, alto):
    for ini, fin, texto in rotulos:
        a = smoothstep(ini, ini + 0.22, ahora) * (1.0 - smoothstep(fin - 0.24, fin, ahora))
        if a <= 0.001:
            continue
        capa = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(capa)
        caja = d.textbbox((0, 0), texto, font=fuente)
        tw, th = caja[2] - caja[0], caja[3] - caja[1]
        x, h = 62, th + 30
        y = alto - 60 - h
        d.rounded_rectangle((x, y, x + tw + 69, y + h), radius=14, fill=(10, 11, 13, round(218 * a)),
                            outline=(255, 255, 255, round(20 * a)), width=1)
        d.rounded_rectangle((x + 12, y + 10, x + 17, y + h - 10), radius=3, fill=ACENTO + (round(255 * a),))
        d.text((x + 31, y + 15 - caja[1]), texto, font=fuente, fill=(244, 244, 246, round(245 * a)))
        frame.paste(capa, (0, 0), capa)


def config_automatica(carpeta):
    carpeta = Path(carpeta)
    orden = carpeta / "segmentos.json"
    if orden.exists():
        nombres = json.loads(orden.read_text(encoding="utf-8"))
    else:
        nombres = sorted(p.name[len("frames-"):] for p in carpeta.glob("frames-*") if (p / "frames.json").exists())
    if not nombres:
        sys.exit(f"ERROR: no hay segmentos frames-*/frames.json en {carpeta}")
    return {"root": str(carpeta), "segments": [{"dir": "frames-" + n} for n in nombres]}


def hacer_gif(ffmpeg, mp4, gif, ancho, fps, colores=128):
    filtro = (f"fps={fps},scale={ancho}:-1:flags=lanczos,split[a][b];"
              f"[a]palettegen=max_colors={colores}:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
    subprocess.run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(mp4), "-vf", filtro, str(gif)], check=True)


def main():
    ap = argparse.ArgumentParser(description="Monta la captura de grabar.js en MP4/GIF.")
    ap.add_argument("entrada", help="carpeta de salida de grabar.js o un montaje.json")
    ap.add_argument("--mp4", help="ruta del MP4 (por defecto: demo.mp4 o 'out' del JSON)")
    ap.add_argument("--gif", help="ruta del GIF (opcional)")
    ap.add_argument("--gif-ancho", type=int, default=800)
    ap.add_argument("--gif-fps", type=int, default=12)
    ap.add_argument("--gif-colores", type=int, default=128)
    ap.add_argument("--ancho", type=int)
    ap.add_argument("--alto", type=int)
    ap.add_argument("--speed", type=float, help="acelera todos los segmentos (montaje automático)")
    ap.add_argument("--sin-zoom", action="store_true", help="desactiva el zoom automático")
    a = ap.parse_args()

    ent = Path(a.entrada)
    if ent.is_dir():
        cfg, base = config_automatica(ent), Path.cwd()
    else:
        cfg, base = json.loads(ent.read_text(encoding="utf-8")), ent.resolve().parent
    if a.speed:
        cfg["speed"] = a.speed
    if a.sin_zoom:
        cfg["auto_zoom"] = False
    fps = cfg.get("fps", 30)
    out_w, out_h = a.ancho or cfg.get("width", 1920), a.alto or cfg.get("height", 1080)
    raiz = (base / cfg.get("root", ".")).resolve()
    salida = Path(a.mp4 or (base / cfg.get("out", "demo.mp4")))
    salida.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = buscar_ffmpeg(cfg)
    fuente = cargar_fuente(cfg, cfg.get("font_size", round(22 * out_h / 1080)))
    cw0, ch0 = cfg.get("cursor_size", [16, 19])
    cursor = hacer_cursor(round(cw0 * out_h / 1080 * 1.25), round(ch0 * out_h / 1080 * 1.25))
    xf = cfg.get("crossfade_frames", 11)
    segs = [Segmento(s, raiz, fps, cfg) for s in cfg["segments"]]
    with Image.open(segs[0].dir / "f00000.jpg") as im0:
        src_w, src_h = cfg.get("src_w", im0.width), cfg.get("src_h", im0.height)
    total = sum(s.frames for s in segs)
    print(f"segmentos {[s.frames for s in segs]} · {total} frames · {total / fps:.1f} s · {out_w}x{out_h}")

    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{out_w}x{out_h}", "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", str(cfg.get("crf", 20)),
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(salida)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    z0 = segs[0].zoom(segs[0].src_ms(0))
    st = [src_w / 2.0, src_h / 2.0, z0, 0.0, 0.0, 0.0]  # cam_x, cam_y, zoom y sus velocidades
    dt = 1.0 / fps
    previa = []  # cola del segmento anterior (para el fundido)
    try:
        for si, seg in enumerate(segs):
            cola = []
            for n in range(seg.frames):
                ahora = n / fps
                ms = seg.src_ms(ahora)
                px, py, idx = seg.meta(ms)
                quiere = seg.zoom(ms)
                follow = seg.cfg.get("follow", 0.5) + 0.12 * smoothstep(1.25, 1.6, quiere)
                dx = 5.0 * math.sin(ahora * 0.71) + 2.1 * math.sin(ahora * 1.37 + 0.8)  # deriva sutil
                dy = 3.5 * math.sin(ahora * 0.57 + 1.2) + 1.4 * math.sin(ahora * 1.11)
                tx = src_w / 2 + follow * (px - src_w / 2) + dx
                ty = src_h / 2 + follow * 0.72 * (py - src_h / 2) + dy
                st[0], st[3] = muelle(st[0], st[3], tx, 5.4, dt)
                st[1], st[4] = muelle(st[1], st[4], ty, 5.4, dt)
                st[2], st[5] = muelle(st[2], st[5], quiere, 6.3, dt)
                zoom = max(1.0, st[2])
                cw, ch = src_w / zoom, src_h / zoom
                left = max(0.0, min(src_w - cw, st[0] - cw / 2))
                top = max(0.0, min(src_h - ch, st[1] - ch / 2))
                toma = seg.imagen(idx).resize((out_w, out_h), resample=Image.Resampling.BICUBIC,
                                              box=(left, top, left + cw, top + ch))
                p = seg.pulsacion(ms)
                ptr = cursor
                if p > 0.01:
                    k = 1.0 - 0.18 * p
                    ptr = cursor.resize((max(8, round(cursor.width * k)), max(9, round(cursor.height * k))), Image.Resampling.LANCZOS)
                    halo = Image.new("RGBA", toma.size, (0, 0, 0, 0))
                    r = 10 + 26 * (1 - p)
                    cx, cy = (px - left) * out_w / cw, (py - top) * out_h / ch
                    ImageDraw.Draw(halo).ellipse((cx - r, cy - r, cx + r, cy + r), outline=ACENTO + (round(200 * p),), width=3)
                    toma.paste(halo, (0, 0), halo)
                toma.paste(ptr, (round((px - left) * out_w / cw - 1), round((py - top) * out_h / ch - 1)), ptr)
                dibujar_rotulo(toma, ahora, seg.cfg.get("captions", []), fuente, out_h)
                if si < len(segs) - 1 and n >= seg.frames - xf:
                    cola.append(toma)
                    continue
                if n < len(previa):
                    toma = Image.blend(previa[n], toma, (n + 1) / (len(previa) + 1))
                proc.stdin.write(toma.convert("RGB").tobytes())
            previa = cola
    except BrokenPipeError as e:
        raise RuntimeError("ffmpeg cerró la tubería") from e
    finally:
        proc.stdin.close()
    if proc.wait():
        sys.exit("ERROR: ffmpeg falló al codificar")
    print(f"OK {salida} ({salida.stat().st_size / 1e6:.2f} MB)")
    if a.gif:
        hacer_gif(ffmpeg, salida, a.gif, a.gif_ancho, a.gif_fps, a.gif_colores)
        print(f"OK {a.gif} ({Path(a.gif).stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
