-- Migration: Complete File Upload Feature Rollback
-- Datum: 2025-08-27
-- Zweck: Vervollstaendigung des File-Upload Rollbacks (nach teilweise fehlgeschlagener vorheriger Migration)

-- 1. Loesche alle Objekte im submissions Bucket, dann den Bucket selbst
DELETE FROM storage.objects WHERE bucket_id = 'submissions';
DELETE FROM storage.buckets WHERE id = 'submissions';

-- 2. Entferne Indizes fuer File-Upload (falls noch vorhanden)
DROP INDEX IF EXISTS idx_submission_processing;
DROP INDEX IF EXISTS idx_submission_type_created;

-- 3. Die Spalten wurden bereits entfernt, daher ist keine weitere Aktion noetig

-- Rollback abgeschlossen