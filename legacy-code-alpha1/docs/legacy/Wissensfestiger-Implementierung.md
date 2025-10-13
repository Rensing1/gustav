### **Implementierungshandbuch: Spaced-Repetition-Algorithmus "Athena 2.0"**

**Dokument-Zweck:** Dieses Dokument dient als technische Spezifikation für die Implementierung des Spaced-Repetition-Algorithmus für den Wissensfestiger. Es ist für Entwickler konzipiert und fokussiert auf Datenmodelle, Konfiguration, Funktionssignaturen und die schrittweise Logik.

**TL;DR:** Wir implementieren einen State-of-the-Art Spaced-Repetition-Algorithmus, der auf festen, aber dynamischen Heuristiken basiert (kein personalisierter Optimierer). Die Kernlogik wird in einer einzigen Funktion gekapselt, die den Zustand einer Lernkarte nach einer Bewertung durch die KI aktualisiert.

#### 1. Datenmodell-Anforderungen

Die bestehende Tabelle, die den Lernfortschritt eines Schülers pro Aufgabe speichert (z.B. `student_task_progress`), muss um die folgenden Felder erweitert werden:

| Feldname | Datentyp | Standardwert | Beschreibung |
| :--- | :--- | :--- | :--- |
| `stability` | `FLOAT` | `1.0` | **(S)** Die Stärke der Erinnerung in Tagen. |
| `difficulty` | `FLOAT` | `0.5` | **(D)** Die intrinsische Schwierigkeit der Aufgabe (0.0 = einfach, 1.0 = schwer). |
| `last_reviewed_at`| `TIMESTAMP` | `NULL` | Zeitstempel der letzten abgeschlossenen Wiederholung. |

#### 2. Globale Konfigurationsparameter

Diese Konstanten sollten an einem zentralen Ort in der Anwendungskonfiguration definiert werden, um ein späteres Fine-Tuning zu ermöglichen.

| Parametername | Empfohlener Wert | Beschreibung |
| :--- | :--- | :--- |
| `FORGETTING_EXPONENT_K` | `0.8` | `k` in der Potenzgesetz-Vergessenskurve. |
| `TARGET_RETRIEVABILITY` | `0.9` | `R_ziel`: Das angestrebte Erinnerungslevel (90%). |
| `SUCCESS_THRESHOLD` | `0.7` | `q_vec.korrektheit`-Wert, ab dem eine Antwort als Erfolg gilt. |
| `INITIAL_DIFFICULTY` | `0.5` | Der Startwert für `difficulty` bei neuen Karten. |
| `STABILITY_GROWTH_FACTOR`| `0.8` | `ZUWACHSFAKTOR`: Globale Lerngeschwindigkeit bei Erfolg. |
| `DIFFICULTY_MEAN_REVERSION`| `0.05` | Stärke, mit der die Schwierigkeit zum Mittelwert zurückkehrt (1.0 - 0.95). |

#### 3. Kernfunktion: `calculateNextReviewState`

Dies ist die zentrale Funktion, die die gesamte Logik kapselt.

**Signatur:**
```
function calculateNextReviewState(
    current_stability: float,
    current_difficulty: float,
    last_reviewed_at: timestamp | null,
    q_vec: {korrektheit: float, vollstaendigkeit: float, praegnanz: float}
): {new_stability: float, new_difficulty: float, next_review_at: timestamp}
```

#### 4. Implementierungslogik: Schritt für Schritt

Die Funktion führt die folgenden Schritte aus:

**Schritt 0: Initialisierung für neue Karten**
*   Wenn `last_reviewed_at` `NULL` ist, handelt es sich um die erste Wiederholung. Überspringe die meisten Berechnungen.
*   Setze `is_first_review = true`.

**Schritt 1: Zeitdifferenz berechnen**
*   Wenn `is_first_review` `false` ist, berechne die vergangene Zeit:
    `t_elapsed_days = (NOW() - last_reviewed_at) / (24 * 3600)`
*   Ansonsten ist `t_elapsed_days = 0`.

**Schritt 2: Entscheidung: Erfolg oder Fehler?**
*   `is_success = q_vec.korrektheit >= SUCCESS_THRESHOLD`

**Schritt 3: Zustand aktualisieren (je nach Ergebnis)**

**IF `is_success`:**

1.  **Abrufbarkeit berechnen:**
    `retrievability_before_review = (1 + t_elapsed_days / current_stability) ^ -FORGETTING_EXPONENT_K`
2.  **"Wünschenswerte Erschwernis"-Bonus bestimmen:**
    `desirable_difficulty_bonus = 1.2 - 0.4 * retrievability_before_review`
3.  **Neue Stabilität berechnen:**
    `stability_gain = STABILITY_GROWTH_FACTOR * (1 - 0.8 * current_difficulty) * desirable_difficulty_bonus * (current_stability / 100) ^ -0.2`
    `new_stability = current_stability * (1 + stability_gain)`
4.  **Schwierigkeitsänderung bestimmen:**
    `difficulty_delta = -0.1 * (q_vec.korrektheit - 0.7) - 0.05 * (q_vec.vollstaendigkeit - 0.5)`
5.  Setze `is_lapse = false`.

**ELSE (Fehler):**

1.  **Neue Stabilität berechnen (Strafe):**
    `new_stability = max(1.0, current_stability * (0.5 - 0.3 * current_difficulty))`
2.  **Schwierigkeitsänderung bestimmen:**
    `difficulty_delta = 0.15`
3.  Setze `is_lapse = true`.

**Schritt 4: Finale Schwierigkeit berechnen (wird immer ausgeführt)**

1.  **Anpassung anwenden:**
    `unbounded_difficulty = current_difficulty + difficulty_delta`
2.  **Mean Reversion anwenden:**
    `mean_reverted_difficulty = (1 - DIFFICULTY_MEAN_REVERSION) * unbounded_difficulty + DIFFICULTY_MEAN_REVERSION * INITIAL_DIFFICULTY`
3.  **Wert begrenzen (Clamping):**
    `new_difficulty = max(0.0, min(1.0, mean_reverted_difficulty))`

**Schritt 5: Nächstes Wiederholungsdatum berechnen**

**IF `is_lapse`:**
*   `next_interval_days = 1` (Aufgabe wird für den nächsten Tag geplant, zusätzlich zur Intra-Session-Wiederholung).

**ELSE (Erfolg):**
*   `interval_calc_factor = (TARGET_RETRIEVABILITY ^ (-1 / FORGETTING_EXPONENT_K) - 1)`
*   `next_interval_days = new_stability * interval_calc_factor`

**Schritt 6: Ergebnis zurückgeben**

*   `next_review_at = NOW() + interval(next_interval_days, 'days')`
*   **Return:** `{new_stability, new_difficulty, next_review_at}`

---

#### 5. Beispiel-Walkthrough

**Szenario:** Eine Aufgabe wird nach 18 Tagen erfolgreich wiederholt.

*   **Input-State:**
    *   `current_stability` = 20.0
    *   `current_difficulty` = 0.3
    *   `last_reviewed_at` = (vor 18 Tagen)
    *   `q_vec` = `{korrektheit: 0.9, vollstaendigkeit: 1.0, praegnanz: 0.8}`

*   **Berechnungen:**
    1.  `t_elapsed_days` = 18
    2.  `is_success` = `0.9 >= 0.7` -> `true`
    3.  `retrievability_before_review` = `(1 + 18 / 20)^-0.8` ≈ 0.58
    4.  `desirable_difficulty_bonus` = `1.2 - 0.4 * 0.58` ≈ 0.968
    5.  `stability_gain` = `0.8 * (1 - 0.8 * 0.3) * 0.968 * (20 / 100)^-0.2` ≈ `0.8 * 0.76 * 0.968 * 1.32` ≈ 0.77
    6.  `new_stability` = `20.0 * (1 + 0.77)` ≈ 35.4
    7.  `difficulty_delta` = `-0.1 * (0.9 - 0.7) - 0.05 * (1.0 - 0.5)` = `-0.02 - 0.025` = -0.045
    8.  `unbounded_difficulty` = `0.3 - 0.045` = 0.255
    9.  `mean_reverted_difficulty` = `0.95 * 0.255 + 0.05 * 0.5` ≈ 0.267
    10. `new_difficulty` = 0.267
    11. `is_lapse` = `false`
    12. `interval_calc_factor` = `(0.9 ^ (-1 / 0.8) - 1)` ≈ 0.13
    13. `next_interval_days` = `35.4 * 0.13` ≈ 4.6 Tage

*   **Output-State:**
    *   `new_stability`: 35.4
    *   `new_difficulty`: 0.267
    *   `next_review_at`: (heute + 4.6 Tage)

Dieses Handbuch bietet eine vollständige Blaupause für die Implementierung. Der Code sollte die Logik in dieser Reihenfolge abbilden und die Konfigurationsparameter extern verwalten.
