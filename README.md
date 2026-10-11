# Surf-Storage Mandichosee – Logo

Logo-Dateien für den Surfclub sowie ein Werkzeug, um pixelige SVG-Nachzeichnungen zu glätten.

## Dateien

| Datei | Beschreibung |
|---|---|
| `Surf-Storage Mandichosee Logo.png` | Original-Logo als Rastergrafik |
| `Surf-Storage_Mandichosee_traced_from_render.svg` | Vektorisierte Nachzeichnung – Kanten folgen den Pixeln (treppenförmig) |
| `Surf-Storage_Mandichosee_smooth.svg` | Geglättete Version mit echten Kurven (Ergebnis von `smooth_svg.py`) |
| `smooth_svg.py` | Skript zum Glätten der Pfade |
| `svg_to_stl.py` | Skript zum Erzeugen von STL-Dateien (3D-Druck) aus dem SVG |
| `Surf-Storage_Mandichosee.stl` | 3D-Modell der schwarzen Schrift (100 mm breit, 3 mm hoch) |

## Einrichtung

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## smooth_svg.py

Wandelt Pfade aus geraden Linienstücken (`M`/`L`/`Z`) entlang von Pixelkanten in glatte kubische Bézierkurven um.

Ablauf pro geschlossener Kontur:

1. Scharfe Ecken erkennen – diese bleiben spitz.
2. Zwischen den Ecken mit einem Gauß-Filter glätten (entfernt die Treppenstufen).
3. Mit dem Schneider-Algorithmus (Graphics Gems, 1990) Bézierkurven einpassen.

### Benutzung

```bash
python3 smooth_svg.py eingabe.svg ausgabe.svg
```

Das Logo wurde so erzeugt:

```bash
python3 smooth_svg.py Surf-Storage_Mandichosee_traced_from_render.svg Surf-Storage_Mandichosee_smooth.svg
```

### Optionen

| Option | Standard | Wirkung |
|---|---|---|
| `--sigma` | 1.5 | Glättungsstärke in Pixeln. Höher = runder, aber feine Details gehen verloren. |
| `--error` | 0.5 | Maximale Abweichung der Kurven in Pixeln. Höher = weniger Knoten, kleinere Datei. |
| `--corner-angle` | 120 | Ecken spitzer als dieser Winkel (Grad) bleiben spitz. `0` = alles abrunden. |
| `--corner-window` | 4 | Abstand in Pixeln, über den der Eckwinkel gemessen wird. |
| `--step` | 0.5 | Abtastabstand in Pixeln. |
| `--precision` | 2 | Nachkommastellen der Koordinaten. |

### Einschränkungen

Es werden nur absolute Pfade aus geraden Linienstücken unterstützt (wie sie Tracing-Tools pixelgenau erzeugen). SVGs mit relativen Befehlen brechen mit einer Fehlermeldung ab; vorhandene Kurvenbefehle (`C`, `Q`, `A` …) werden nicht unterstützt.

## svg_to_stl.py

Erzeugt aus einem SVG STL-Dateien für den 3D-Druck – getrennt nach Füllfarbe. Jede Farbe wird als flacher Körper extrudiert; Weiß (der Hintergrund) wird standardmäßig ignoriert. Bei nur einer Farbe entsteht eine STL-Datei, bei mehreren eine pro Farbe (`<name>_<farbe>.stl`, z. B. für Mehrfarbdruck). Alle Farben werden gleich skaliert und positioniert, damit sie zusammenpassen.

- Löcher (z. B. in o, a, e) bleiben erhalten (`fill-rule`).
- Die y-Achse wird gespiegelt, damit die Schrift im Slicer richtig herum liegt.
- Kurven werden abgetastet und anschließend vereinfacht.

### Benutzung

```bash
.venv/bin/python svg_to_stl.py Surf-Storage_Mandichosee_smooth.svg Surf-Storage_Mandichosee.stl
```

### Optionen

| Option | Standard | Wirkung |
|---|---|---|
| `--width` | 100 | Breite des Modells in mm |
| `--scale` | – | Alternativ zu `--width`: mm pro SVG-Einheit |
| `--height` | 3 | Extrusionshöhe in mm |
| `--exclude` | `#ffffff` | Farben, die ignoriert werden |
| `--only` | – | Nur diese Farben exportieren, z. B. `--only '#000000'` |
| `--tolerance` | 0.5 | Genauigkeit der Kurven in SVG-Einheiten. Kleiner = feiner, größere Datei |
