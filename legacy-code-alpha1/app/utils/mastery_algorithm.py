"""
Spaced Repetition Algorithm "Athena 2.0" for the Wissensfestiger module.
Based on the FSRS (Free Spaced Repetition Scheduler) principles,
adapted from the logic in `Wissensfestiger-Implementierung.md`.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List

# Import config from the new location
from mastery.mastery_config import (
    FORGETTING_EXPONENT_K,
    TARGET_RETRIEVABILITY,
    SUCCESS_THRESHOLD,
    INITIAL_DIFFICULTY,
    INITIAL_STABILITY,
    STABILITY_GROWTH_FACTOR,
    DIFFICULTY_MEAN_REVERSION
)

logger = logging.getLogger(__name__)


class ReviewState:
    """Represents the outcome of a single review calculation."""

    def __init__(
        self,
        new_stability: float,
        new_difficulty: float,
        state: str,
        last_review_date: datetime,
        next_due_date: datetime,
        review_history: List[Dict]
    ):
        self.new_stability = new_stability
        self.new_difficulty = new_difficulty
        self.state = state
        self.last_review_date = last_review_date
        self.next_due_date = next_due_date
        self.review_history = review_history

    def to_dict(self) -> Dict:
        return {
            "stability": self.new_stability,
            "difficulty": self.new_difficulty,
            "state": self.state,
            "last_review_date": self.last_review_date.isoformat(),
            "next_due_date": self.next_due_date.isoformat(),
            "review_history": self.review_history
        }


def calculate_next_review_state(
    current_progress: Optional[Dict],  # None für neue Aufgaben
    rating: int,  # AI-Bewertung 1–5 (für Kompatibilität)
    q_vec: Optional[Dict] = None  # Detaillierte KI-Bewertung {korrektheit, vollstaendigkeit, praegnanz}
) -> ReviewState:
    """
    Calculates the next review state based on the FSRS-like "Athena 2.0" algorithm.

    Args:
        current_progress: Aktueller Fortschritts-Datensatz aus `student_mastery_progress` oder None.
        rating: Schülerbewertung für die Aufgabe (1–5) - wird für Rückwärtskompatibilität beibehalten.
        q_vec: Detaillierte KI-Bewertung mit korrektheit, vollstaendigkeit, praegnanz (0.0-1.0).

    Returns:
        ReviewState-Objekt mit neuer Stabilität, Schwierigkeit und nächstem Fälligkeitsdatum.
    """
    # Standardwerte für neue Aufgaben
    current_stability = INITIAL_STABILITY  # Initial stability gemäß Spezifikation
    current_difficulty = INITIAL_DIFFICULTY
    last_reviewed_at = None
    current_state = "new"
    review_history = []

    if current_progress:
        current_stability = current_progress.get("stability", INITIAL_STABILITY)  # Default stability = INITIAL_STABILITY
        current_difficulty = current_progress.get("difficulty", INITIAL_DIFFICULTY)
        if current_progress.get("last_reviewed_at"):
            # Handle PostgreSQL timestamps with microseconds
            timestamp_str = current_progress["last_reviewed_at"]
            # Python's fromisoformat can't handle more than 6 decimal places
            # PostgreSQL sometimes returns more (e.g., .87793 instead of .877930)
            if '.' in timestamp_str:
                # Split at the decimal point
                base_part, decimal_part = timestamp_str.split('.')
                # Extract timezone part if present
                if '+' in decimal_part:
                    microseconds, tz_part = decimal_part.split('+')
                    # Ensure microseconds are exactly 6 digits
                    microseconds = microseconds[:6].ljust(6, '0')
                    timestamp_str = f"{base_part}.{microseconds}+{tz_part}"
                elif '-' in decimal_part and len(decimal_part) > 6:
                    microseconds, tz_part = decimal_part.split('-')
                    microseconds = microseconds[:6].ljust(6, '0')
                    timestamp_str = f"{base_part}.{microseconds}-{tz_part}"
                else:
                    # No timezone, just truncate microseconds
                    microseconds = decimal_part[:6].ljust(6, '0')
                    timestamp_str = f"{base_part}.{microseconds}"
            last_reviewed_at = datetime.fromisoformat(timestamp_str)
        current_state = current_progress.get("state", "new")  # Falls später hinzugefügt
        review_history = current_progress.get("review_history", [])  # Falls später hinzugefügt

    # Falls noch nie überprüft, jetzt als "letzte Überprüfung" setzen
    if last_reviewed_at is None:
        last_reviewed_at = datetime.now(timezone.utc)

    logger.info(
        f"Calculating next review state: S={current_stability}, "
        f"D={current_difficulty}, Rating={rating}"
    )

    # 1. Zeitdifferenz in Tagen
    t_elapsed_days = (datetime.now(timezone.utc) - last_reviewed_at).total_seconds() / (24 * 3600)
    t_elapsed_days = max(0.0, t_elapsed_days)

    # 2. Erfolg oder Misserfolg? (nutze q_vec falls verfügbar, sonst rating)
    if q_vec:
        korrektheit = q_vec.get('korrektheit', 0.0)
        is_success = korrektheit >= SUCCESS_THRESHOLD
    else:
        # Fallback für Rückwärtskompatibilität
        is_success = rating >= SUCCESS_THRESHOLD
        korrektheit = (rating - 1) / 4.0  # Konvertiere rating (1-5) zu korrektheit (0-1)

    # 3. Update der Werte basierend auf Erfolg/Misserfolg
    new_stability = current_stability
    new_difficulty = current_difficulty
    is_lapse = False

    if is_success:
        # --- Erfolgspfad ---
        if t_elapsed_days == 0:
            retrievability_before_review = 1.0
        else:
            retrievability_before_review = (
                (1 + t_elapsed_days / current_stability) ** -FORGETTING_EXPONENT_K
            )

        desirable_difficulty_bonus = 1.2 - 0.4 * retrievability_before_review

        stability_gain = (
            STABILITY_GROWTH_FACTOR * (1 - 0.8 * current_difficulty) * desirable_difficulty_bonus * ((current_stability / 100) ** -0.2)
        )
        new_stability = current_stability * (1 + stability_gain)
        new_stability = max(1.0, new_stability)

        # Erweiterte Schwierigkeitsberechnung nach Spezifikation
        if q_vec:
            korrektheit = q_vec.get('korrektheit', 0.0)
            vollstaendigkeit = q_vec.get('vollstaendigkeit', 0.0)
            difficulty_delta = -0.1 * (korrektheit - 0.7) - 0.05 * (vollstaendigkeit - 0.5)
        else:
            # Fallback für Rückwärtskompatibilität
            difficulty_delta = (rating - 3) * -0.1

        logger.info(
            f"SUCCESS -> New Stability: {new_stability:.2f}, "
            f"Difficulty Delta: {difficulty_delta:.3f}"
        )

    else:
        # --- Misserfolgspfad (Lapse) ---
        new_stability = max(1.0, current_stability * (0.5 - 0.3 * current_difficulty))
        difficulty_delta = 0.15
        is_lapse = True
        logger.info(
            f"LAPSE -> New Stability: {new_stability:.2f}, "
            f"Difficulty Delta: {difficulty_delta:.3f}"
        )

    # 4. Finale Difficulty
    unbounded_difficulty = current_difficulty + difficulty_delta
    mean_reverted_difficulty = (
        (1 - DIFFICULTY_MEAN_REVERSION) * unbounded_difficulty
        + DIFFICULTY_MEAN_REVERSION * INITIAL_DIFFICULTY
    )
    new_difficulty = max(0.0, min(1.0, mean_reverted_difficulty))

    # 5. Nächstes Intervall und State
    next_interval_days = 0.0
    new_state = current_state

    if is_lapse:
        next_interval_days = 1.0
        new_state = "relearning"
    elif current_state == "new":
        next_interval_days = 1.0
        new_state = "learning"
    else:
        interval_calc_factor = (TARGET_RETRIEVABILITY ** (-1 / FORGETTING_EXPONENT_K) - 1)
        next_interval_days = new_stability * interval_calc_factor
        new_state = "review"

    next_interval_days = max(1.0, round(next_interval_days))

    # 6. Nächstes Datum und History
    new_last_review_date = datetime.now(timezone.utc)
    new_next_due_date = new_last_review_date + timedelta(days=next_interval_days)

    review_history.append({
        "date": new_last_review_date.isoformat(),
        "rating": rating,
        "stability": round(new_stability, 2),
        "difficulty": round(new_difficulty, 2),
        "interval": next_interval_days
    })

    logger.info(
        f"Final state: S={new_stability:.2f}, D={new_difficulty:.2f}, "
        f"Next review in {next_interval_days} days. State: {new_state}"
    )

    return ReviewState(
        new_stability=new_stability,
        new_difficulty=new_difficulty,
        state=new_state,
        last_review_date=new_last_review_date,
        next_due_date=new_next_due_date,
        review_history=review_history
    )

