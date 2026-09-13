## Genau beobachten

Ein digitales Thermometer misst die Temperatur, verarbeitet den Messwert und zeigt das Ergebnis an. Untersuche, welche Aufgabe die einzelnen Teile übernehmen.

1. Benenne die Eingabe und die Ausgabe des Systems.
2. Erkläre, weshalb der Messwert vor der Anzeige verarbeitet wird.
3. Prüfe einen Wert unterhalb, genau auf und oberhalb der Grenze.

### Ergebnisse vergleichen

| Messwert | Erwartete Anzeige | Begründung |
| --- | --- | --- |
| 19 °C | Normal | Die Grenze ist noch nicht erreicht. |
| 20 °C | Warnung | Der Grenzwert ist erreicht. |
| 21 °C | Warnung | Der Grenzwert ist überschritten. |

### Ein Programm lesen

Die Dateiendungen `.sb3`, `.hex` und `.fls` bleiben Bestandteil des Materials.

```text
wenn temperatur >= 20:
    zeige "Warnung"
sonst:
    zeige "Normal"
```

Begründe, warum der Test mit genau 20 °C besonders wichtig ist. Achte auf eine verständliche Erklärung mit eigenen Worten.
