# Surf-Storage Mandichosee – Logo

Logo-Dateien für den Surfclub sowie ein Werkzeug, um pixelige SVG-Nachzeichnungen zu glätten.

## Dateien

| Datei | Beschreibung |
|---|---|
| `Surf-Storage_Mandichosee.svg` | Geglättetes Logo mit echten Kurven (Ergebnis von `smooth_svg.py`) |
| `smooth_svg.py` | Skript zum Glätten der Pfade |
| `svg_to_stl.py` | Skript zum Erzeugen von STL-Dateien (3D-Druck) aus dem SVG |
| `Surf-Storage_Mandichosee.stl` | 3D-Modell des ganzen Schriftzugs (2000 mm breit, 10 mm hoch) |
| `Surf-Storage_Mandichosee.3mf` | Slicer-Projekt (Bambu/Orca) mit allen Teilen auf eigenen Platten |
| `torage.stl`, `andichosee.stl` | Schriftzüge „torage“ und „andichosee“ in Endgröße |
| `torage_teil1_tor.stl`, `torage_teil2_age.stl` | „torage“ am Rand des a geteilt |
| `andichosee_teil1_andic.stl`, `andichosee_teil2_hosee.stl` | „andichosee“ zwischen c und h geteilt (c vollständig, h glatt) |
| `holzschraube.stl` | Negativ-Schraube für Objekte, die im Slicer auf 54,262 % (XY) skaliert sind |
| `holzschraube_endgroesse.stl` | Dieselbe Schraube in Endgröße (8,97 mm) für Objekte auf 100 % |

## Skalierung im Slicer-Projekt

Die Teile aus `Surf-Storage_Mandichosee.stl` (S, urf, S, M) sind im Projekt auf 54,262 % in X/Y skaliert, Z bleibt auf 100 %. Die geteilten Teile (tor, age, andic, hosee) sind schon in Endgröße und bleiben auf 100 %. Negativ-Teile werden mitskaliert. Deshalb gilt:

- in skalierten Objekten `holzschraube.stl` verwenden,
- in Objekten auf 100 % `holzschraube_endgroesse.stl` verwenden.

In beiden Fällen ist das Schraubenloch gleich groß.

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

Das Logo wurde so erzeugt (die pixelige Nachzeichnung ist nicht mehr im Repo):

```bash
python3 smooth_svg.py Surf-Storage_Mandichosee_traced_from_render.svg Surf-Storage_Mandichosee.svg
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
.venv/bin/python svg_to_stl.py Surf-Storage_Mandichosee.svg Surf-Storage_Mandichosee.stl
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
