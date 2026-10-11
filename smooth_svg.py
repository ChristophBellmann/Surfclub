#!/usr/bin/env python3
"""Glättet treppenförmige (pixelige) SVG-Pfade zu Bézier-Kurven.

Die Pfade im Logo bestehen nur aus M/L/Z-Befehlen entlang der Pixelkanten.
Für jeden geschlossenen Teilpfad wird:
  1. nach scharfen Ecken gesucht (diese bleiben spitz),
  2. zwischen den Ecken mit einem Gauß-Filter geglättet (Treppen entfernen),
  3. mit dem Schneider-Algorithmus ("An Algorithm for Automatically Fitting
     Digitized Curves", Graphics Gems 1990) in kubische Béziers umgewandelt.

Beispiel:
    python3 smooth_svg.py eingabe.svg ausgabe.svg --sigma 2.0 --error 0.8
"""

import argparse
import math
import re
import xml.etree.ElementTree as ET

import numpy as np

SVG_NS = "http://www.w3.org/2000/svg"


# --------------------------------------------------------------------------- #
# Pfad einlesen
# --------------------------------------------------------------------------- #
def parse_polyline_path(d):
    """Zerlegt einen Pfad aus M/L/Z (absolut) in eine Liste von Punktlisten."""
    tokens = re.findall(r"[A-Za-z]|-?\d*\.?\d+(?:e-?\d+)?", d)
    subpaths, current, cmd, i = [], [], None, 0
    while i < len(tokens):
        t = tokens[i]
        if t.isalpha() and t not in "MLZmlz":
            raise ValueError(f"Pfadbefehl '{t}' wird nicht unterstützt (nur M/L/Z)")
        if t in "MLZmlz":
            cmd = t.upper()
            if t.islower() and t not in "zZ":
                raise ValueError("Relative Pfadbefehle werden nicht unterstützt")
            if cmd == "Z":
                if current:
                    subpaths.append(current)
                current = []
            elif cmd == "M" and current:
                subpaths.append(current)
                current = []
            i += 1
            continue
        x, y = float(tokens[i]), float(tokens[i + 1])
        current.append((x, y))
        i += 2
    if current:
        subpaths.append(current)
    return [np.array(sp, dtype=float) for sp in subpaths]


# --------------------------------------------------------------------------- #
# Vorverarbeitung
# --------------------------------------------------------------------------- #
def dedupe(pts):
    keep = [0]
    for i in range(1, len(pts)):
        if np.any(pts[i] != pts[keep[-1]]):
            keep.append(i)
    pts = pts[keep]
    if len(pts) > 1 and np.all(pts[0] == pts[-1]):
        pts = pts[:-1]
    return pts


def resample_closed(pts, step):
    """Verteilt Punkte gleichmäßig (Bogenlänge) auf dem geschlossenen Polygon."""
    closed = np.vstack([pts, pts[:1]])
    seg = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    total = cum[-1]
    n = max(int(round(total / step)), 8)
    t = np.linspace(0, total, n, endpoint=False)
    x = np.interp(t, cum, closed[:, 0])
    y = np.interp(t, cum, closed[:, 1])
    return np.column_stack([x, y])


def find_corners(pts, k, max_angle_deg):
    """Indizes von Punkten, deren Öffnungswinkel kleiner als max_angle ist."""
    n = len(pts)
    if n < 2 * k + 1:
        return []
    prev = pts[(np.arange(n) - k) % n] - pts
    nxt = pts[(np.arange(n) + k) % n] - pts
    cosang = np.einsum("ij,ij->i", prev, nxt) / (
        np.linalg.norm(prev, axis=1) * np.linalg.norm(nxt, axis=1) + 1e-12
    )
    angle = np.degrees(np.arccos(np.clip(cosang, -1, 1)))
    corners = []
    for i in range(n):
        if angle[i] >= max_angle_deg:
            continue
        window = [(i + j) % n for j in range(-k, k + 1)]
        if angle[i] == min(angle[w] for w in window) and all(
            abs(i - c) > k for c in corners
        ):
            corners.append(i)
    return corners


def gaussian_kernel(sigma):
    r = max(1, int(math.ceil(3 * sigma)))
    x = np.arange(-r, r + 1)
    k = np.exp(-(x**2) / (2 * sigma**2))
    return k / k.sum()


def smooth_closed(pts, sigma):
    if sigma <= 0:
        return pts.copy()
    k = gaussian_kernel(sigma)
    r = len(k) // 2
    padded = np.vstack([pts[-r:], pts, pts[:r]]) if r < len(pts) else pts
    if r >= len(pts):
        return pts.copy()
    out = np.column_stack(
        [np.convolve(padded[:, d], k, mode="valid") for d in range(2)]
    )
    return out


def smooth_open(pts, sigma):
    """Glättet einen offenen Abschnitt, Endpunkte bleiben fix."""
    if sigma <= 0 or len(pts) < 3:
        return pts.copy()
    k = gaussian_kernel(sigma)
    r = len(k) // 2
    # Punktspiegelung an den Enden, damit die Endpunkte nicht wandern
    head = 2 * pts[0] - pts[1 : r + 1][::-1]
    tail = 2 * pts[-1] - pts[-r - 1 : -1][::-1]
    if len(head) < r or len(tail) < r:
        return pts.copy()
    padded = np.vstack([head, pts, tail])
    out = np.column_stack(
        [np.convolve(padded[:, d], k, mode="valid") for d in range(2)]
    )
    out[0], out[-1] = pts[0], pts[-1]
    return out


# --------------------------------------------------------------------------- #
# Schneider-Bézier-Fitting
# --------------------------------------------------------------------------- #
def _bezier(ctrl, t):
    t = np.asarray(t)[:, None]
    mt = 1 - t
    return (
        mt**3 * ctrl[0]
        + 3 * mt**2 * t * ctrl[1]
        + 3 * mt * t**2 * ctrl[2]
        + t**3 * ctrl[3]
    )


def _bezier_d1(ctrl, t):
    t = np.asarray(t)[:, None]
    mt = 1 - t
    return (
        3 * mt**2 * (ctrl[1] - ctrl[0])
        + 6 * mt * t * (ctrl[2] - ctrl[1])
        + 3 * t**2 * (ctrl[3] - ctrl[2])
    )


def _bezier_d2(ctrl, t):
    t = np.asarray(t)[:, None]
    return 6 * (1 - t) * (ctrl[2] - 2 * ctrl[1] + ctrl[0]) + 6 * t * (
        ctrl[3] - 2 * ctrl[2] + ctrl[1]
    )


def _unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def _chord_params(pts):
    d = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    return d / d[-1] if d[-1] > 0 else np.linspace(0, 1, len(pts))


def _generate_bezier(pts, u, t1, t2):
    p0, p3 = pts[0], pts[-1]
    b1 = 3 * (1 - u) ** 2 * u
    b2 = 3 * (1 - u) * u**2
    a1 = b1[:, None] * t1
    a2 = b2[:, None] * t2
    c00 = np.sum(a1 * a1)
    c01 = np.sum(a1 * a2)
    c11 = np.sum(a2 * a2)
    base = _bezier(np.array([p0, p0, p3, p3]), u)
    tmp = pts - base
    x0 = np.sum(a1 * tmp)
    x1 = np.sum(a2 * tmp)
    det = c00 * c11 - c01 * c01
    seg_len = np.linalg.norm(p3 - p0)
    eps = 1e-6 * seg_len
    if abs(det) > 1e-12:
        alpha1 = (x0 * c11 - x1 * c01) / det
        alpha2 = (c00 * x1 - c01 * x0) / det
    else:
        alpha1 = alpha2 = 0
    if alpha1 < eps or alpha2 < eps:
        alpha1 = alpha2 = seg_len / 3
    return np.array([p0, p0 + alpha1 * t1, p3 + alpha2 * t2, p3])


def _reparameterize(ctrl, pts, u):
    d = _bezier(ctrl, u) - pts
    d1 = _bezier_d1(ctrl, u)
    d2 = _bezier_d2(ctrl, u)
    num = np.sum(d * d1, axis=1)
    den = np.sum(d1 * d1, axis=1) + np.sum(d * d2, axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        nu = np.where(np.abs(den) > 1e-12, u - num / den, u)
    return np.clip(nu, 0, 1)


def _max_error(ctrl, pts, u):
    d = np.sum((_bezier(ctrl, u) - pts) ** 2, axis=1)
    i = int(np.argmax(d))
    return d[i], i


def fit_cubic(pts, t1, t2, error, depth=0):
    if len(pts) == 2:
        dist = np.linalg.norm(pts[1] - pts[0]) / 3
        return [np.array([pts[0], pts[0] + t1 * dist, pts[1] + t2 * dist, pts[1]])]

    u = _chord_params(pts)
    ctrl = _generate_bezier(pts, u, t1, t2)
    err, split = _max_error(ctrl, pts, u)
    if err < error**2:
        return [ctrl]
    if err < (4 * error) ** 2:
        for _ in range(20):
            u = _reparameterize(ctrl, pts, u)
            ctrl = _generate_bezier(pts, u, t1, t2)
            err, split = _max_error(ctrl, pts, u)
            if err < error**2:
                return [ctrl]

    split = min(max(split, 1), len(pts) - 2)
    if depth > 40:
        return [ctrl]
    tc = _unit(pts[split - 1] - pts[split + 1])
    return fit_cubic(pts[: split + 1], t1, tc, error, depth + 1) + fit_cubic(
        pts[split:], -tc, t2, error, depth + 1
    )


def fit_open(pts, error, t1=None, t2=None):
    if t1 is None:
        t1 = _unit(pts[min(2, len(pts) - 1)] - pts[0])
    if t2 is None:
        t2 = _unit(pts[max(-3, -len(pts))] - pts[-1])
    return fit_cubic(pts, t1, t2, error)


# --------------------------------------------------------------------------- #
# Ein Teilpfad
# --------------------------------------------------------------------------- #
def smooth_subpath(raw, args):
    pts = dedupe(raw)
    if len(pts) < 4:
        return pts, None
    pts = resample_closed(pts, args.step)
    n = len(pts)
    k = max(2, int(round(args.corner_window / args.step)))
    corners = find_corners(pts, k, args.corner_angle)

    if not corners:
        sm = smooth_closed(pts, args.sigma / args.step)
        # Am Punkt mit der stärksten Krümmung beginnen, Tangente durchgehend
        start = 0
        sm = np.roll(sm, -start, axis=0)
        closed = np.vstack([sm, sm[:1]])
        t = _unit(sm[1] - sm[-1])
        curves = fit_open(closed, args.error, t, -t)
        return None, curves

    curves = []
    for ci, c in enumerate(corners):
        nxt = corners[(ci + 1) % len(corners)]
        idx = [(c + j) % n for j in range(((nxt - c) % n or n) + 1)]
        seg = pts[idx]
        seg = smooth_open(seg, args.sigma / args.step)
        if len(seg) >= 2:
            curves += fit_open(seg, args.error)
    return None, curves


def fmt(v, prec):
    s = f"{v:.{prec}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def curves_to_d(curves, prec):
    p = lambda pt: f"{fmt(pt[0], prec)} {fmt(pt[1], prec)}"
    out = [f"M {p(curves[0][0])}"]
    for c in curves:
        out.append(f"C {p(c[1])} {p(c[2])} {p(c[3])}")
    out.append("Z")
    return " ".join(out)


def poly_to_d(pts, prec):
    p = lambda pt: f"{fmt(pt[0], prec)} {fmt(pt[1], prec)}"
    return "M " + " L ".join(p(q) for q in pts) + " Z"


def smooth_path_d(d, args):
    parts = []
    for raw in parse_polyline_path(d):
        poly, curves = smooth_subpath(raw, args)
        parts.append(curves_to_d(curves, args.precision) if curves else poly_to_d(poly, args.precision))
    return " ".join(parts)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--sigma", type=float, default=1.5,
                    help="Glättungsstärke in Pixeln (größer = runder, weniger Details). Standard: 1.5")
    ap.add_argument("--error", type=float, default=0.5,
                    help="Max. Abweichung der Bézierkurven in Pixeln (größer = weniger Knoten). Standard: 0.5")
    ap.add_argument("--corner-angle", type=float, default=120,
                    help="Winkel in Grad, unter dem eine Ecke spitz bleibt. 0 = keine Ecken. Standard: 120")
    ap.add_argument("--corner-window", type=float, default=4,
                    help="Abstand in Pixeln für die Eckenerkennung. Standard: 4")
    ap.add_argument("--step", type=float, default=0.5,
                    help="Abtastabstand in Pixeln. Standard: 0.5")
    ap.add_argument("--precision", type=int, default=2, help="Nachkommastellen. Standard: 2")
    args = ap.parse_args()

    ET.register_namespace("", SVG_NS)
    tree = ET.parse(args.input)
    count = 0
    for el in tree.iter(f"{{{SVG_NS}}}path"):
        d = el.get("d")
        if d:
            el.set("d", smooth_path_d(d, args))
            count += 1
    tree.write(args.output, encoding="UTF-8", xml_declaration=True)
    print(f"{count} Pfade geglättet -> {args.output}")


if __name__ == "__main__":
    main()
