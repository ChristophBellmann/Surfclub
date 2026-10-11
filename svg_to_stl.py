#!/usr/bin/env python3
"""Erzeugt aus einem SVG eine STL-Datei pro Füllfarbe.

Alle gefüllten Formen werden nach Farbe gruppiert und als flache Körper
extrudiert. Ausgeschlossene Farben (standardmäßig Weiß, also der Hintergrund)
werden ignoriert. Gibt es nur eine Farbe, entsteht genau eine STL-Datei,
sonst eine pro Farbe (<name>_<farbe>.stl) – praktisch für Mehrfarbdruck.

Beispiel:
    .venv/bin/python svg_to_stl.py logo.svg logo.stl --width 100 --height 3
"""

import argparse
import os

import numpy as np
import shapely
import trimesh
from shapely import affinity
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union
from svgelements import SVG, Close, Color, Line, Move, Path, Shape


# --------------------------------------------------------------------------- #
# SVG -> Polygone
# --------------------------------------------------------------------------- #
def subpath_rings(path, tolerance):
    """Liefert die Teilpfade als Punktlisten (Kurven werden abgetastet)."""
    rings = []
    for sub in path.as_subpaths():
        pts = []
        for seg in sub:
            if isinstance(seg, Move):
                pts.append((seg.end.x, seg.end.y))
            elif isinstance(seg, (Line, Close)):
                if seg.end is not None:
                    pts.append((seg.end.x, seg.end.y))
            else:
                n = max(2, int(np.ceil(seg.length(error=1e-3) / tolerance)))
                for t in np.linspace(0, 1, n + 1)[1:]:
                    p = seg.point(t)
                    pts.append((p.x, p.y))
        if len(pts) >= 3:
            rings.append(pts)
    return rings


def shape_to_geometry(shape, tolerance):
    """Wandelt eine SVG-Form unter Beachtung der fill-rule in eine Fläche um."""
    path = Path(shape)
    path.reify()
    geom = Polygon()
    evenodd = str(shape.values.get("fill-rule", "nonzero")).strip() == "evenodd"
    for ring in subpath_rings(path, tolerance):
        poly = shapely.make_valid(Polygon(ring))
        if poly.is_empty:
            continue
        # evenodd: überlappende Bereiche heben sich auf (Löcher in Buchstaben).
        # nonzero wird vereinfacht als Vereinigung behandelt, außer für Ringe,
        # die vollständig in einer bestehenden Fläche liegen (typische Löcher).
        if evenodd or geom.contains(poly):
            geom = geom.symmetric_difference(poly)
        else:
            geom = geom.union(poly)
    return geom


def collect_by_color(svg, tolerance, exclude):
    groups = {}
    for el in svg.elements():
        if not isinstance(el, Shape):
            continue
        fill = el.fill
        if fill is None or fill.value is None or fill.alpha == 0:
            continue
        hexcol = fill.hexrgb.lower()
        if hexcol in exclude:
            continue
        geom = shape_to_geometry(el, tolerance)
        if not geom.is_empty:
            groups.setdefault(hexcol, []).append(geom)
    # Gleichmäßig abgetastete Kurven auf die nötigen Punkte reduzieren
    return {c: unary_union(g).simplify(tolerance / 2) for c, g in groups.items()}


# --------------------------------------------------------------------------- #
# Polygone -> Mesh
# --------------------------------------------------------------------------- #
def polygons_of(geom):
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    return [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon)]


def extrude(geom, height, z0=0.0):
    meshes = [
        trimesh.creation.extrude_polygon(p, height)
        for p in polygons_of(geom)
        if p.area > 1e-9
    ]
    mesh = trimesh.util.concatenate(meshes)
    if z0:
        mesh.apply_translation([0, 0, z0])
    return mesh


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="SVG-Datei")
    ap.add_argument("output", help="STL-Datei (bei mehreren Farben wird _<farbe> angehängt)")
    size = ap.add_mutually_exclusive_group()
    size.add_argument("--width", type=float, default=100,
                      help="Breite des Ergebnisses in mm. Standard: 100")
    size.add_argument("--scale", type=float,
                      help="mm pro SVG-Einheit (statt --width)")
    ap.add_argument("--height", type=float, default=3,
                    help="Extrusionshöhe in mm. Standard: 3")
    ap.add_argument("--exclude", nargs="*", default=["#ffffff"],
                    help="Farben, die ignoriert werden (Hex). Standard: #ffffff")
    ap.add_argument("--only", nargs="*",
                    help="Nur diese Farben exportieren (Hex), z. B. --only '#000000'")
    ap.add_argument("--tolerance", type=float, default=0.5,
                    help="Abtastgenauigkeit für Kurven in SVG-Einheiten. Standard: 0.5")
    args = ap.parse_args()

    exclude = {Color(c).hexrgb.lower() for c in args.exclude}
    svg = SVG.parse(args.input)
    groups = collect_by_color(svg, args.tolerance, exclude)
    if args.only:
        only = {Color(c).hexrgb.lower() for c in args.only}
        groups = {c: g for c, g in groups.items() if c in only}
    if not groups:
        raise SystemExit("Keine passenden gefüllten Formen gefunden.")

    # Gemeinsame Skalierung für alle Farben, damit die Teile zusammenpassen.
    minx, miny, maxx, maxy = unary_union(list(groups.values())).bounds
    scale = args.scale if args.scale else args.width / (maxx - minx)

    base, ext = os.path.splitext(args.output)
    for color, geom in sorted(groups.items()):
        # Nach links unten verschieben, skalieren und y spiegeln (SVG-y zeigt nach unten)
        geom = affinity.translate(geom, -minx, -maxy)
        geom = affinity.scale(geom, scale, -scale, origin=(0, 0))
        mesh = extrude(geom, args.height)
        out = args.output if len(groups) == 1 else f"{base}_{color.lstrip('#')}{ext or '.stl'}"
        mesh.export(out)
        w, d, h = mesh.extents
        print(f"{color}: {len(polygons_of(geom))} Teile, {w:.1f} x {d:.1f} x {h:.1f} mm, "
              f"wasserdicht={mesh.is_watertight} -> {out}")


if __name__ == "__main__":
    main()
