"""
Configuration for the Mastery Learning Module (Wissensfestiger)
Parameters for the FSRS-like spaced repetition algorithm.
"""

from typing import Dict

# ============================================================================
# SPACED REPETITION ALGORITHM PARAMETERS ("Wissensfestiger")
# ============================================================================

# Based on the formulas in `Wissensfestiger-Implementierung.md`

FORGETTING_EXPONENT_K: float = 0.8
"""k in the power-law forgetting curve: R = (1 + t/S)^-k"""

TARGET_RETRIEVABILITY: float = 0.9
"""R_ziel: The desired probability of recall (90%)."""

SUCCESS_THRESHOLD: float = 0.7
"""q_vec.korrektheit value above which an answer is considered a success."""

INITIAL_DIFFICULTY: float = 0.5
"""The starting difficulty for new cards (0.0 to 1.0)."""

INITIAL_STABILITY: float = 1.0
"""The starting stability for new cards (days)."""

STABILITY_GROWTH_FACTOR: float = 0.8
"""Global learning speed factor for successful reviews."""

DIFFICULTY_MEAN_REVERSION: float = 0.05
"""How strongly difficulty reverts to the mean (1.0 - 0.95)."""


# ============================================================================
# UI AND DISPLAY CONFIGURATION (Still relevant)
# ============================================================================

# These can be adapted to show progress based on stability/difficulty

def get_learning_level_label(stability: float) -> str:
    """Get a display label based on memory stability."""
    if stability < 2:
        return "🌱 Erste Schritte"
    elif stability < 7:
        return "🌿 Ansatz erkannt"
    elif stability < 21:
        return "🌳 Fundament gelegt"
    elif stability < 100:
        return "💪 Sicher angewendet"
    else:
        return "⭐ Gemeistert"

def get_learning_level_color(stability: float) -> str:
    """Get a display color based on memory stability."""
    if stability < 2:
        return "#ff4b4b"  # Red
    elif stability < 7:
        return "#ff8c00"  # Orange
    elif stability < 21:
        return "#ffd700"  # Gold
    elif stability < 100:
        return "#90ee90"  # Light green
    else:
        return "#00c851"  # Green
