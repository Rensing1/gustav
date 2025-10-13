# scripts/optimize_global_weights.py

import torch
import torch.nn as nn
import pandas as pd
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import numpy as np

# Lade Umgebungsvariablen für Supabase-Verbindung
load_dotenv(dotenv_path='../.env')

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError("Supabase URL und Service Key müssen in der .env Datei gesetzt sein.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def load_mastery_log_data() -> pd.DataFrame:
    """Lädt die relevanten Daten aus der mastery_log Tabelle."""
    print("Lade Daten aus der mastery_log Tabelle...")
    response = supabase.table('mastery_log').select(
        "time_since_last_review",
        "stability_before",
        "difficulty_before",
        "recall_outcome",
        "q_cor", "q_flu", "q_com"
    ).execute()
    
    if response.data:
        df = pd.DataFrame(response.data)
        print(f"{len(df)} Einträge erfolgreich geladen.")
        return df
    else:
        print("Keine Daten im mastery_log gefunden.")
        return pd.DataFrame()


class DSRKI_Model(nn.Module):
    """Ein PyTorch-Modell, das den DSRKI-Algorithmus kapselt, um die Gewichte zu optimieren."""
    def __init__(self, initial_weights):
        super().__init__()
        # Definiere die 11 Gewichte als lernbare Parameter
        self.weights = nn.Parameter(torch.tensor(initial_weights, dtype=torch.float32))

    def forward(self, data: torch.Tensor) -> torch.Tensor:
        """Berechnet die vorhergesagte Abrufwahrscheinlichkeit (R) für einen Batch von Daten."""
        s_alt = data[:, 0]
        d_alt = data[:, 1]
        t_since_last = data[:, 2]
        
        # Berechne R basierend auf den Formeln und aktuellen Gewichten
        # Dies ist die Kernformel, die wir optimieren
        r_predicted = (1 + t_since_last / (s_alt * 9)).pow(-1)
        
        return r_predicted


def loss_function(r_predicted: torch.Tensor, recall_outcome: torch.Tensor) -> torch.Tensor:
    """Berechnet den Binary Cross-Entropy Loss (Log-Loss)."""
    # Fügt eine kleine Epsilon-Konstante hinzu, um Log(0) zu vermeiden
    epsilon = 1e-7
    loss = -torch.mean(
        recall_outcome * torch.log(r_predicted + epsilon) + 
        (1 - recall_outcome) * torch.log(1 - r_predicted + epsilon)
    )
    return loss


def main():
    """Hauptfunktion zur Ausführung des Optimierungsprozesses."""
    # Lade die Daten
    df = load_mastery_log_data()
    if df.empty:
        return

    # Konvertiere Daten in PyTorch-Tensoren
    # Wir brauchen: Stabilität, Schwierigkeit, Zeit seit letzter Wiederholung
    X = torch.tensor(df[['stability_before', 'difficulty_before', 'time_since_last_review']].values, dtype=torch.float32)
    # Das Ziel, das wir vorhersagen wollen: der tatsächliche Abruferfolg
    y = torch.tensor(df['recall_outcome'].values, dtype=torch.float32).unsqueeze(1)

    # Initialgewichte (aus der mastery_config)
    # TODO: Lade diese dynamisch aus der Datei
    initial_weights = [
        2.5, 1.0, 0.2, 4.0, 1.0, 1.0, 0.8, 0.5, 0.2, 0.8, 0.9
    ]

    model = DSRKI_Model(initial_weights)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    num_epochs = 1000

    print("Beginne mit der Optimierung der Gewichte...")
    for epoch in range(num_epochs):
        optimizer.zero_grad()
        
        # Forward-Pass: Berechne die vorhergesagte Abrufwahrscheinlichkeit
        r_predicted = model(X)
        
        # Berechne den Loss
        loss = loss_function(r_predicted, y)
        
        # Backward-Pass: Berechne die Gradienten
        loss.backward()
        
        # Aktualisiere die Gewichte
        optimizer.step()

        if (epoch + 1) % 100 == 0:
            print(f'Epoch [{epoch+1}/{num_epochs}], Loss: {loss.item():.4f}')

    print("\nOptimierung abgeschlossen.")
    optimized_weights = model.weights.detach().numpy()
    
    print("\n--- Startgewichte ---")
    print(np.round(initial_weights, 4))
    
    print("\n--- Optimierte Gewichte ---")
    print(np.round(optimized_weights, 4))


if __name__ == "__main__":
    main()
