# Surf-Storage Mandichosee – Logo

Logo-Dateien für den Surfclub sowie ein Werkzeug, um pixelige SVG-Nachzeichnungen zu glätten.

## Dateien

| Datei | Beschreibung |
|---|---|
| `Surf-Storage Mandichosee Logo.png` | Original-Logo als Rastergrafik |
| `Surf-Storage_Mandichosee_traced_from_render.svg` | Vektorisierte Nachzeichnung – Kanten folgen den Pixeln (treppenförmig) |
| `Surf-Storage_Mandichosee_smooth.svg` | Geglättete Version mit echten Kurven (Ergebnis von `smooth_svg.py`) |
| `smooth_svg.py` | Skript zum Glätten der Pfade |

## smooth_svg.py

Wandelt Pfade aus geraden Linienstücken (`M`/`L`/`Z`) entlang von Pixelkanten in glatte kubische Bézierkurven um.

Ablauf pro geschlossener Kontur:

1. Scharfe Ecken erkennen – diese bleiben spitz.
2. Zwischen den Ecken mit einem Gauß-Filter glätten (entfernt die Treppenstufen).
3. Mit dem Schneider-Algorithmus (Graphics Gems, 1990) Bézierkurven einpassen.

### Voraussetzungen

- Python 3
- `numpy`

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
