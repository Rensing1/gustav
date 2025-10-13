-- SQL Test-Skript für RLS-Debugging bei Submissions  
-- Direkt in der Datenbank ausführen

-- Test 1: Nur ursprüngliche 4 Spalten
DO $$
DECLARE
    test_submission_id UUID;
BEGIN
    RAISE NOTICE '=== Test 1: Nur ursprüngliche 4 Spalten ===';
    
    -- Test Insert
    INSERT INTO submission (student_id, task_id, submission_data, attempt_number)
    VALUES (
        '814094e1-a5df-4195-8ad1-ac634bf6ebf1',
        '426487ca-3ba0-4a75-bcfc-e66e61f8c969',
        '{"text": "Minimal test"}',
        99
    ) RETURNING id INTO test_submission_id;
    
    RAISE NOTICE '✅ Erfolg Test 1: Submission % erstellt', test_submission_id;
    
    -- Cleanup
    DELETE FROM submission WHERE id = test_submission_id;
    RAISE NOTICE '🗑️ Test-Submission % gelöscht', test_submission_id;
    
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE '❌ Fehler Test 1: %', SQLERRM;
END $$;

-- Test 2: Mit Queue-Feldern
DO $$
DECLARE
    test_submission_id UUID;
BEGIN
    RAISE NOTICE '=== Test 2: Mit Queue-Feldern ===';
    
    -- Test Insert
    INSERT INTO submission (student_id, task_id, submission_data, attempt_number, feedback_status, retry_count)
    VALUES (
        '814094e1-a5df-4195-8ad1-ac634bf6ebf1',
        '426487ca-3ba0-4a75-bcfc-e66e61f8c969',
        '{"text": "Queue test"}',
        99,
        'pending',
        0
    ) RETURNING id INTO test_submission_id;
    
    RAISE NOTICE '✅ Erfolg Test 2: Submission % erstellt', test_submission_id;
    
    -- Cleanup
    DELETE FROM submission WHERE id = test_submission_id;
    RAISE NOTICE '🗑️ Test-Submission % gelöscht', test_submission_id;
    
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE '❌ Fehler Test 2: %', SQLERRM;
END $$;

-- Test 3: Mit expliziten NULL-Werten
DO $$
DECLARE
    test_submission_id UUID;
BEGIN
    RAISE NOTICE '=== Test 3: Mit expliziten NULL-Werten ===';
    
    -- Test Insert
    INSERT INTO submission (student_id, task_id, submission_data, attempt_number, feedback_status, retry_count, last_retry_at, processing_started_at)
    VALUES (
        '814094e1-a5df-4195-8ad1-ac634bf6ebf1',
        '426487ca-3ba0-4a75-bcfc-e66e61f8c969',
        '{"text": "NULL test"}',
        99,
        'pending',
        0,
        NULL,
        NULL
    ) RETURNING id INTO test_submission_id;
    
    RAISE NOTICE '✅ Erfolg Test 3: Submission % erstellt', test_submission_id;
    
    -- Cleanup
    DELETE FROM submission WHERE id = test_submission_id;
    RAISE NOTICE '🗑️ Test-Submission % gelöscht', test_submission_id;
    
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE '❌ Fehler Test 3: %', SQLERRM;
END $$;