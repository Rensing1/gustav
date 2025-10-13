-- 1. Erstelle die Hilfsfunktion, um updated_at automatisch zu verwalten.
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 2. Erstelle die Tabelle zur Speicherung der personalisierten DSRKI-Gewichte.
CREATE TABLE public.user_model_weights (
    user_id UUID PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE,
    w0 REAL NOT NULL,
    w1 REAL NOT NULL,
    w2 REAL NOT NULL,
    w3 REAL NOT NULL,
    w4 REAL NOT NULL,
    w5 REAL NOT NULL,
    w6 REAL NOT NULL,
    w7 REAL NOT NULL,
    w8 REAL NOT NULL,
    w9 REAL NOT NULL,
    w10 REAL NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. RLS-Richtlinien, um die Tabelle standardmäßig zu sperren.
ALTER TABLE public.user_model_weights ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Deny all access to user model weights" 
ON public.user_model_weights FOR ALL
USING (false) WITH CHECK (false);

-- 4. Trigger, um das updated_at-Feld automatisch zu aktualisieren.
CREATE TRIGGER on_user_model_weights_updated
BEFORE UPDATE ON public.user_model_weights
FOR EACH ROW
EXECUTE PROCEDURE public.handle_updated_at();