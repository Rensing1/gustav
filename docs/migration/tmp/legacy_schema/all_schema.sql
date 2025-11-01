--
-- PostgreSQL database dump
--

\restrict 6u5sjQ37hT01U3hGCLU2QRx46PWofdnJAZEQWdxRg7UFKTiWZS6ZgLKMsWxSeVb

-- Dumped from database version 17.6
-- Dumped by pg_dump version 17.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: _realtime; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA _realtime;


ALTER SCHEMA _realtime OWNER TO postgres;

--
-- Name: auth; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA auth;


ALTER SCHEMA auth OWNER TO supabase_admin;

--
-- Name: extensions; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA extensions;


ALTER SCHEMA extensions OWNER TO postgres;

--
-- Name: graphql; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA graphql;


ALTER SCHEMA graphql OWNER TO supabase_admin;

--
-- Name: graphql_public; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA graphql_public;


ALTER SCHEMA graphql_public OWNER TO supabase_admin;

--
-- Name: pg_net; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_net WITH SCHEMA extensions;


--
-- Name: EXTENSION pg_net; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_net IS 'Async HTTP';


--
-- Name: pgbouncer; Type: SCHEMA; Schema: -; Owner: pgbouncer
--

CREATE SCHEMA pgbouncer;


ALTER SCHEMA pgbouncer OWNER TO pgbouncer;

--
-- Name: realtime; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA realtime;


ALTER SCHEMA realtime OWNER TO supabase_admin;

--
-- Name: storage; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA storage;


ALTER SCHEMA storage OWNER TO supabase_admin;

--
-- Name: supabase_functions; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA supabase_functions;


ALTER SCHEMA supabase_functions OWNER TO supabase_admin;

--
-- Name: supabase_migrations; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA supabase_migrations;


ALTER SCHEMA supabase_migrations OWNER TO postgres;

--
-- Name: vault; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA vault;


ALTER SCHEMA vault OWNER TO supabase_admin;

--
-- Name: pg_graphql; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_graphql WITH SCHEMA graphql;


--
-- Name: EXTENSION pg_graphql; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_graphql IS 'pg_graphql: GraphQL support';


--
-- Name: pg_stat_statements; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_stat_statements WITH SCHEMA extensions;


--
-- Name: EXTENSION pg_stat_statements; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_stat_statements IS 'track planning and execution statistics of all SQL statements executed';


--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: supabase_vault; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS supabase_vault WITH SCHEMA vault;


--
-- Name: EXTENSION supabase_vault; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION supabase_vault IS 'Supabase Vault Extension';


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA extensions;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: aal_level; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.aal_level AS ENUM (
    'aal1',
    'aal2',
    'aal3'
);


ALTER TYPE auth.aal_level OWNER TO supabase_auth_admin;

--
-- Name: code_challenge_method; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.code_challenge_method AS ENUM (
    's256',
    'plain'
);


ALTER TYPE auth.code_challenge_method OWNER TO supabase_auth_admin;

--
-- Name: factor_status; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.factor_status AS ENUM (
    'unverified',
    'verified'
);


ALTER TYPE auth.factor_status OWNER TO supabase_auth_admin;

--
-- Name: factor_type; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.factor_type AS ENUM (
    'totp',
    'webauthn',
    'phone'
);


ALTER TYPE auth.factor_type OWNER TO supabase_auth_admin;

--
-- Name: oauth_authorization_status; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.oauth_authorization_status AS ENUM (
    'pending',
    'approved',
    'denied',
    'expired'
);


ALTER TYPE auth.oauth_authorization_status OWNER TO supabase_auth_admin;

--
-- Name: oauth_client_type; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.oauth_client_type AS ENUM (
    'public',
    'confidential'
);


ALTER TYPE auth.oauth_client_type OWNER TO supabase_auth_admin;

--
-- Name: oauth_registration_type; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.oauth_registration_type AS ENUM (
    'dynamic',
    'manual'
);


ALTER TYPE auth.oauth_registration_type OWNER TO supabase_auth_admin;

--
-- Name: oauth_response_type; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.oauth_response_type AS ENUM (
    'code'
);


ALTER TYPE auth.oauth_response_type OWNER TO supabase_auth_admin;

--
-- Name: one_time_token_type; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.one_time_token_type AS ENUM (
    'confirmation_token',
    'reauthentication_token',
    'recovery_token',
    'email_change_token_new',
    'email_change_token_current',
    'phone_change_token'
);


ALTER TYPE auth.one_time_token_type OWNER TO supabase_auth_admin;

--
-- Name: user_role; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.user_role AS ENUM (
    'student',
    'teacher'
);


ALTER TYPE public.user_role OWNER TO postgres;

--
-- Name: action; Type: TYPE; Schema: realtime; Owner: supabase_admin
--

CREATE TYPE realtime.action AS ENUM (
    'INSERT',
    'UPDATE',
    'DELETE',
    'TRUNCATE',
    'ERROR'
);


ALTER TYPE realtime.action OWNER TO supabase_admin;

--
-- Name: equality_op; Type: TYPE; Schema: realtime; Owner: supabase_admin
--

CREATE TYPE realtime.equality_op AS ENUM (
    'eq',
    'neq',
    'lt',
    'lte',
    'gt',
    'gte',
    'in'
);


ALTER TYPE realtime.equality_op OWNER TO supabase_admin;

--
-- Name: user_defined_filter; Type: TYPE; Schema: realtime; Owner: supabase_admin
--

CREATE TYPE realtime.user_defined_filter AS (
	column_name text,
	op realtime.equality_op,
	value text
);


ALTER TYPE realtime.user_defined_filter OWNER TO supabase_admin;

--
-- Name: wal_column; Type: TYPE; Schema: realtime; Owner: supabase_admin
--

CREATE TYPE realtime.wal_column AS (
	name text,
	type_name text,
	type_oid oid,
	value jsonb,
	is_pkey boolean,
	is_selectable boolean
);


ALTER TYPE realtime.wal_column OWNER TO supabase_admin;

--
-- Name: wal_rls; Type: TYPE; Schema: realtime; Owner: supabase_admin
--

CREATE TYPE realtime.wal_rls AS (
	wal jsonb,
	is_rls_enabled boolean,
	subscription_ids uuid[],
	errors text[]
);


ALTER TYPE realtime.wal_rls OWNER TO supabase_admin;

--
-- Name: buckettype; Type: TYPE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TYPE storage.buckettype AS ENUM (
    'STANDARD',
    'ANALYTICS'
);


ALTER TYPE storage.buckettype OWNER TO supabase_storage_admin;

--
-- Name: email(); Type: FUNCTION; Schema: auth; Owner: supabase_auth_admin
--

CREATE FUNCTION auth.email() RETURNS text
    LANGUAGE sql STABLE
    AS $$
  select 
  coalesce(
    nullif(current_setting('request.jwt.claim.email', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'email')
  )::text
$$;


ALTER FUNCTION auth.email() OWNER TO supabase_auth_admin;

--
-- Name: FUNCTION email(); Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON FUNCTION auth.email() IS 'Deprecated. Use auth.jwt() -> ''email'' instead.';


--
-- Name: jwt(); Type: FUNCTION; Schema: auth; Owner: supabase_auth_admin
--

CREATE FUNCTION auth.jwt() RETURNS jsonb
    LANGUAGE sql STABLE
    AS $$
  select 
    coalesce(
        nullif(current_setting('request.jwt.claim', true), ''),
        nullif(current_setting('request.jwt.claims', true), '')
    )::jsonb
$$;


ALTER FUNCTION auth.jwt() OWNER TO supabase_auth_admin;

--
-- Name: role(); Type: FUNCTION; Schema: auth; Owner: supabase_auth_admin
--

CREATE FUNCTION auth.role() RETURNS text
    LANGUAGE sql STABLE
    AS $$
  select 
  coalesce(
    nullif(current_setting('request.jwt.claim.role', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role')
  )::text
$$;


ALTER FUNCTION auth.role() OWNER TO supabase_auth_admin;

--
-- Name: FUNCTION role(); Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON FUNCTION auth.role() IS 'Deprecated. Use auth.jwt() -> ''role'' instead.';


--
-- Name: uid(); Type: FUNCTION; Schema: auth; Owner: supabase_auth_admin
--

CREATE FUNCTION auth.uid() RETURNS uuid
    LANGUAGE sql STABLE
    AS $$
  select 
  coalesce(
    nullif(current_setting('request.jwt.claim.sub', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
  )::uuid
$$;


ALTER FUNCTION auth.uid() OWNER TO supabase_auth_admin;

--
-- Name: FUNCTION uid(); Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON FUNCTION auth.uid() IS 'Deprecated. Use auth.jwt() -> ''sub'' instead.';


--
-- Name: grant_pg_cron_access(); Type: FUNCTION; Schema: extensions; Owner: supabase_admin
--

CREATE FUNCTION extensions.grant_pg_cron_access() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF EXISTS (
    SELECT
    FROM pg_event_trigger_ddl_commands() AS ev
    JOIN pg_extension AS ext
    ON ev.objid = ext.oid
    WHERE ext.extname = 'pg_cron'
  )
  THEN
    grant usage on schema cron to postgres with grant option;

    alter default privileges in schema cron grant all on tables to postgres with grant option;
    alter default privileges in schema cron grant all on functions to postgres with grant option;
    alter default privileges in schema cron grant all on sequences to postgres with grant option;

    alter default privileges for user supabase_admin in schema cron grant all
        on sequences to postgres with grant option;
    alter default privileges for user supabase_admin in schema cron grant all
        on tables to postgres with grant option;
    alter default privileges for user supabase_admin in schema cron grant all
        on functions to postgres with grant option;

    grant all privileges on all tables in schema cron to postgres with grant option;
    revoke all on table cron.job from postgres;
    grant select on table cron.job to postgres with grant option;
  END IF;
END;
$$;


ALTER FUNCTION extensions.grant_pg_cron_access() OWNER TO supabase_admin;

--
-- Name: FUNCTION grant_pg_cron_access(); Type: COMMENT; Schema: extensions; Owner: supabase_admin
--

COMMENT ON FUNCTION extensions.grant_pg_cron_access() IS 'Grants access to pg_cron';


--
-- Name: grant_pg_graphql_access(); Type: FUNCTION; Schema: extensions; Owner: supabase_admin
--

CREATE FUNCTION extensions.grant_pg_graphql_access() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $_$
DECLARE
    func_is_graphql_resolve bool;
BEGIN
    func_is_graphql_resolve = (
        SELECT n.proname = 'resolve'
        FROM pg_event_trigger_ddl_commands() AS ev
        LEFT JOIN pg_catalog.pg_proc AS n
        ON ev.objid = n.oid
    );

    IF func_is_graphql_resolve
    THEN
        -- Update public wrapper to pass all arguments through to the pg_graphql resolve func
        DROP FUNCTION IF EXISTS graphql_public.graphql;
        create or replace function graphql_public.graphql(
            "operationName" text default null,
            query text default null,
            variables jsonb default null,
            extensions jsonb default null
        )
            returns jsonb
            language sql
        as $$
            select graphql.resolve(
                query := query,
                variables := coalesce(variables, '{}'),
                "operationName" := "operationName",
                extensions := extensions
            );
        $$;

        -- This hook executes when `graphql.resolve` is created. That is not necessarily the last
        -- function in the extension so we need to grant permissions on existing entities AND
        -- update default permissions to any others that are created after `graphql.resolve`
        grant usage on schema graphql to postgres, anon, authenticated, service_role;
        grant select on all tables in schema graphql to postgres, anon, authenticated, service_role;
        grant execute on all functions in schema graphql to postgres, anon, authenticated, service_role;
        grant all on all sequences in schema graphql to postgres, anon, authenticated, service_role;
        alter default privileges in schema graphql grant all on tables to postgres, anon, authenticated, service_role;
        alter default privileges in schema graphql grant all on functions to postgres, anon, authenticated, service_role;
        alter default privileges in schema graphql grant all on sequences to postgres, anon, authenticated, service_role;

        -- Allow postgres role to allow granting usage on graphql and graphql_public schemas to custom roles
        grant usage on schema graphql_public to postgres with grant option;
        grant usage on schema graphql to postgres with grant option;
    END IF;

END;
$_$;


ALTER FUNCTION extensions.grant_pg_graphql_access() OWNER TO supabase_admin;

--
-- Name: FUNCTION grant_pg_graphql_access(); Type: COMMENT; Schema: extensions; Owner: supabase_admin
--

COMMENT ON FUNCTION extensions.grant_pg_graphql_access() IS 'Grants access to pg_graphql';


--
-- Name: grant_pg_net_access(); Type: FUNCTION; Schema: extensions; Owner: supabase_admin
--

CREATE FUNCTION extensions.grant_pg_net_access() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_event_trigger_ddl_commands() AS ev
    JOIN pg_extension AS ext
    ON ev.objid = ext.oid
    WHERE ext.extname = 'pg_net'
  )
  THEN
    GRANT USAGE ON SCHEMA net TO supabase_functions_admin, postgres, anon, authenticated, service_role;

    ALTER function net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) SECURITY DEFINER;
    ALTER function net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) SECURITY DEFINER;

    ALTER function net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) SET search_path = net;
    ALTER function net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) SET search_path = net;

    REVOKE ALL ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) FROM PUBLIC;
    REVOKE ALL ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) FROM PUBLIC;

    GRANT EXECUTE ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) TO supabase_functions_admin, postgres, anon, authenticated, service_role;
    GRANT EXECUTE ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) TO supabase_functions_admin, postgres, anon, authenticated, service_role;
  END IF;
END;
$$;


ALTER FUNCTION extensions.grant_pg_net_access() OWNER TO supabase_admin;

--
-- Name: FUNCTION grant_pg_net_access(); Type: COMMENT; Schema: extensions; Owner: supabase_admin
--

COMMENT ON FUNCTION extensions.grant_pg_net_access() IS 'Grants access to pg_net';


--
-- Name: pgrst_ddl_watch(); Type: FUNCTION; Schema: extensions; Owner: supabase_admin
--

CREATE FUNCTION extensions.pgrst_ddl_watch() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  cmd record;
BEGIN
  FOR cmd IN SELECT * FROM pg_event_trigger_ddl_commands()
  LOOP
    IF cmd.command_tag IN (
      'CREATE SCHEMA', 'ALTER SCHEMA'
    , 'CREATE TABLE', 'CREATE TABLE AS', 'SELECT INTO', 'ALTER TABLE'
    , 'CREATE FOREIGN TABLE', 'ALTER FOREIGN TABLE'
    , 'CREATE VIEW', 'ALTER VIEW'
    , 'CREATE MATERIALIZED VIEW', 'ALTER MATERIALIZED VIEW'
    , 'CREATE FUNCTION', 'ALTER FUNCTION'
    , 'CREATE TRIGGER'
    , 'CREATE TYPE', 'ALTER TYPE'
    , 'CREATE RULE'
    , 'COMMENT'
    )
    -- don't notify in case of CREATE TEMP table or other objects created on pg_temp
    AND cmd.schema_name is distinct from 'pg_temp'
    THEN
      NOTIFY pgrst, 'reload schema';
    END IF;
  END LOOP;
END; $$;


ALTER FUNCTION extensions.pgrst_ddl_watch() OWNER TO supabase_admin;

--
-- Name: pgrst_drop_watch(); Type: FUNCTION; Schema: extensions; Owner: supabase_admin
--

CREATE FUNCTION extensions.pgrst_drop_watch() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  obj record;
BEGIN
  FOR obj IN SELECT * FROM pg_event_trigger_dropped_objects()
  LOOP
    IF obj.object_type IN (
      'schema'
    , 'table'
    , 'foreign table'
    , 'view'
    , 'materialized view'
    , 'function'
    , 'trigger'
    , 'type'
    , 'rule'
    )
    AND obj.is_temporary IS false -- no pg_temp objects
    THEN
      NOTIFY pgrst, 'reload schema';
    END IF;
  END LOOP;
END; $$;


ALTER FUNCTION extensions.pgrst_drop_watch() OWNER TO supabase_admin;

--
-- Name: set_graphql_placeholder(); Type: FUNCTION; Schema: extensions; Owner: supabase_admin
--

CREATE FUNCTION extensions.set_graphql_placeholder() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $_$
    DECLARE
    graphql_is_dropped bool;
    BEGIN
    graphql_is_dropped = (
        SELECT ev.schema_name = 'graphql_public'
        FROM pg_event_trigger_dropped_objects() AS ev
        WHERE ev.schema_name = 'graphql_public'
    );

    IF graphql_is_dropped
    THEN
        create or replace function graphql_public.graphql(
            "operationName" text default null,
            query text default null,
            variables jsonb default null,
            extensions jsonb default null
        )
            returns jsonb
            language plpgsql
        as $$
            DECLARE
                server_version float;
            BEGIN
                server_version = (SELECT (SPLIT_PART((select version()), ' ', 2))::float);

                IF server_version >= 14 THEN
                    RETURN jsonb_build_object(
                        'errors', jsonb_build_array(
                            jsonb_build_object(
                                'message', 'pg_graphql extension is not enabled.'
                            )
                        )
                    );
                ELSE
                    RETURN jsonb_build_object(
                        'errors', jsonb_build_array(
                            jsonb_build_object(
                                'message', 'pg_graphql is only available on projects running Postgres 14 onwards.'
                            )
                        )
                    );
                END IF;
            END;
        $$;
    END IF;

    END;
$_$;


ALTER FUNCTION extensions.set_graphql_placeholder() OWNER TO supabase_admin;

--
-- Name: FUNCTION set_graphql_placeholder(); Type: COMMENT; Schema: extensions; Owner: supabase_admin
--

COMMENT ON FUNCTION extensions.set_graphql_placeholder() IS 'Reintroduces placeholder function for graphql_public.graphql';


--
-- Name: get_auth(text); Type: FUNCTION; Schema: pgbouncer; Owner: supabase_admin
--

CREATE FUNCTION pgbouncer.get_auth(p_usename text) RETURNS TABLE(username text, password text)
    LANGUAGE plpgsql SECURITY DEFINER
    AS $_$
begin
    raise debug 'PgBouncer auth request: %', p_usename;

    return query
    select 
        rolname::text, 
        case when rolvaliduntil < now() 
            then null 
            else rolpassword::text 
        end 
    from pg_authid 
    where rolname=$1 and rolcanlogin;
end;
$_$;


ALTER FUNCTION pgbouncer.get_auth(p_usename text) OWNER TO supabase_admin;

--
-- Name: _get_submission_status_matrix_uncached(text, uuid, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public._get_submission_status_matrix_uncached(p_session_id text, p_course_id uuid, p_unit_id uuid) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_result JSONB;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid THEN
        RAISE EXCEPTION 'Invalid session';
    END IF;
    
    -- Check authorization
    IF v_user_role = 'teacher' THEN
        -- Teacher must be course creator
        IF NOT EXISTS (
            SELECT 1 FROM course 
            WHERE id = p_course_id AND creator_id = v_user_id
        ) THEN
            RAISE EXCEPTION 'Unauthorized access to course';
        END IF;
    ELSE
        RAISE EXCEPTION 'Only teachers can access submission matrix';
    END IF;
    
    -- Build the submission matrix
    WITH enrolled_students AS (
        SELECT 
            cs.student_id,
            COALESCE(p.full_name, u.email::text) as student_name
        FROM course_student cs
        JOIN auth.users u ON u.id = cs.student_id
        LEFT JOIN profiles p ON p.id = cs.student_id
        WHERE cs.course_id = p_course_id
    ),
    unit_tasks AS (
        SELECT 
            t.id as task_id,
            t.instruction as task_title,
            t.order_in_section,
            s.order_in_unit,
            s.id as section_id
        FROM task_base t
        JOIN unit_section s ON s.id = t.section_id
        WHERE s.unit_id = p_unit_id
    ),
    submission_status AS (
        SELECT 
            es.student_id,
            ut.task_id,
            jsonb_build_object(
                'task_id', ut.task_id,
                'task_title', ut.task_title,
                'section_id', ut.section_id,
                'has_submission', EXISTS(
                    SELECT 1 FROM submission sub 
                    WHERE sub.student_id = es.student_id 
                    AND sub.task_id = ut.task_id
                ),
                'is_correct', (
                    SELECT BOOL_OR(sub.is_correct) 
                    FROM submission sub 
                    WHERE sub.student_id = es.student_id 
                    AND sub.task_id = ut.task_id
                ),
                'latest_submission_id', (
                    SELECT sub.id 
                    FROM submission sub 
                    WHERE sub.student_id = es.student_id 
                    AND sub.task_id = ut.task_id
                    ORDER BY sub.submitted_at DESC  -- Changed from timestamp to submitted_at
                    LIMIT 1
                )
            ) as submission_info
        FROM enrolled_students es
        CROSS JOIN unit_tasks ut
    )
    SELECT jsonb_build_object(
        'students', (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'id', student_id,
                    'name', student_name
                ) ORDER BY student_name
            ) FROM enrolled_students
        ),
        'tasks', (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'id', task_id,
                    'title', task_title,
                    'section_id', section_id
                ) ORDER BY order_in_unit, order_in_section
            ) FROM unit_tasks
        ),
        'submissions', (
            SELECT jsonb_object_agg(
                student_id::text,
                (
                    SELECT jsonb_object_agg(
                        task_id::text,
                        submission_info
                    )
                    FROM submission_status ss2
                    WHERE ss2.student_id = ss.student_id
                )
            ) FROM (SELECT DISTINCT student_id FROM submission_status) ss
        )
    ) INTO v_result;
    
    RETURN COALESCE(v_result, '{}'::jsonb);
END;
$$;


ALTER FUNCTION public._get_submission_status_matrix_uncached(p_session_id text, p_course_id uuid, p_unit_id uuid) OWNER TO postgres;

--
-- Name: add_user_to_course(text, uuid, uuid, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.add_user_to_course(p_session_id text, p_user_id uuid, p_course_id uuid, p_role text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can add users to courses';
    END IF;

    -- Check if teacher is authorized for this course
    IF NOT EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id  -- Fixed: changed created_by to creator_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Dynamic table selection based on role
    IF p_role = 'student' THEN
        INSERT INTO course_student (student_id, course_id)
        VALUES (p_user_id, p_course_id)
        ON CONFLICT (student_id, course_id) DO NOTHING;
    ELSIF p_role = 'teacher' THEN
        INSERT INTO course_teacher (teacher_id, course_id)
        VALUES (p_user_id, p_course_id)
        ON CONFLICT (teacher_id, course_id) DO NOTHING;
    ELSE
        RAISE EXCEPTION 'Invalid role: %', p_role;
    END IF;
END;
$$;


ALTER FUNCTION public.add_user_to_course(p_session_id text, p_user_id uuid, p_course_id uuid, p_role text) OWNER TO postgres;

--
-- Name: assign_unit_to_course(text, uuid, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.assign_unit_to_course(p_session_id text, p_unit_id uuid, p_course_id uuid) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can assign units to courses';
    END IF;

    -- Check if teacher is authorized for this course
    IF NOT EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Insert assignment without order_in_course since it doesn't exist in schema
    INSERT INTO course_learning_unit_assignment (
        unit_id,  -- Fixed: changed from learning_unit_id
        course_id
    )
    VALUES (p_unit_id, p_course_id)
    ON CONFLICT (unit_id, course_id) DO NOTHING;
END;
$$;


ALTER FUNCTION public.assign_unit_to_course(p_session_id text, p_unit_id uuid, p_course_id uuid) OWNER TO postgres;

--
-- Name: calculate_learning_streak(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.calculate_learning_streak(p_session_id text, p_student_id uuid) RETURNS TABLE(current_streak integer, longest_streak integer, last_activity_date date)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid THEN
        RAISE EXCEPTION 'Invalid session';
    END IF;
    
    -- Check authorization
    IF v_user_id != p_student_id AND v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized access to student data';
    END IF;
    
    -- Return a single row with default values if no data
    RETURN QUERY
    SELECT 
        0::INTEGER as current_streak,
        0::INTEGER as longest_streak,
        CURRENT_DATE as last_activity_date;
END;
$$;


ALTER FUNCTION public.calculate_learning_streak(p_session_id text, p_student_id uuid) OWNER TO postgres;

--
-- Name: can_student_view_section(uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.can_student_view_section(section_id_to_check uuid) RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.course_unit_section_status cuss
    JOIN public.course_student cs ON cuss.course_id = cs.course_id
    WHERE cs.student_id = auth.uid() -- Ist der aktuelle Nutzer in einem Kurs...
      AND cuss.section_id = section_id_to_check -- ...der diesen Abschnitt enthält...
      AND cuss.is_published = true -- ...und ist dieser Abschnitt für den Kurs veröffentlicht?
  );
$$;


ALTER FUNCTION public.can_student_view_section(section_id_to_check uuid) OWNER TO postgres;

--
-- Name: can_submit_task(uuid, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.can_submit_task(p_student_id uuid, p_task_id uuid) RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
  v_max_attempts INTEGER;
  v_current_attempts INTEGER;
BEGIN
  -- Get max attempts for task
  SELECT max_attempts INTO v_max_attempts
  FROM task
  WHERE id = p_task_id;
  
  -- Get current attempt count
  v_current_attempts := get_submission_count(p_student_id, p_task_id);
  
  -- Return true if under limit
  RETURN v_current_attempts < v_max_attempts;
END;
$$;


ALTER FUNCTION public.can_submit_task(p_student_id uuid, p_task_id uuid) OWNER TO postgres;

--
-- Name: cleanup_expired_sessions(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.cleanup_expired_sessions() RETURNS integer
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'extensions'
    AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM public.auth_sessions 
    WHERE expires_at < NOW()
    OR last_activity < NOW() - INTERVAL '90 minutes'; -- Also cleanup inactive sessions
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;


ALTER FUNCTION public.cleanup_expired_sessions() OWNER TO postgres;

--
-- Name: FUNCTION cleanup_expired_sessions(); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.cleanup_expired_sessions() IS 'Removes expired and inactive sessions - returns count of deleted sessions';


--
-- Name: cleanup_session_rate_limits(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.cleanup_session_rate_limits() RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_deleted INT;
BEGIN
    DELETE FROM session_rate_limits 
    WHERE window_start < NOW() - INTERVAL '1 hour';
    
    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    RETURN v_deleted;
END;
$$;


ALTER FUNCTION public.cleanup_session_rate_limits() OWNER TO postgres;

--
-- Name: create_course(text, text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.create_course(p_session_id text, p_name text, p_description text DEFAULT NULL::text) RETURNS TABLE(id uuid, name text, created_at timestamp with time zone, success boolean, error_message text)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    -- Explicit variables to avoid column ambiguity
    result_id UUID;
    result_name TEXT;
    result_created_at TIMESTAMPTZ;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    -- Authorization: Only Teacher
    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RETURN QUERY SELECT
            NULL::UUID,
            NULL::TEXT,
            NULL::TIMESTAMPTZ,
            FALSE,
            'Keine Berechtigung fuer diese Aktion'::TEXT;
        RETURN;
    END IF;

    -- Input validation
    IF p_name IS NULL OR LENGTH(TRIM(p_name)) = 0 THEN
        RETURN QUERY SELECT
            NULL::UUID,
            NULL::TEXT,
            NULL::TIMESTAMPTZ,
            FALSE,
            'Kursname darf nicht leer sein'::TEXT;
        RETURN;
    END IF;

    -- Create record with explicit variables
    BEGIN
        INSERT INTO course (name, creator_id)
        VALUES (TRIM(p_name), v_user_id)
        RETURNING course.id, course.name, course.created_at
        INTO result_id, result_name, result_created_at;

        -- Success with explicit variable data
        RETURN QUERY SELECT
            result_id,
            result_name,
            result_created_at,
            TRUE,
            NULL::TEXT;

    EXCEPTION
        WHEN unique_violation THEN
            RETURN QUERY SELECT
                NULL::UUID,
                NULL::TEXT,
                NULL::TIMESTAMPTZ,
                FALSE,
                'Ein Kurs mit diesem Namen existiert bereits'::TEXT;
        WHEN OTHERS THEN
            RETURN QUERY SELECT
                NULL::UUID,
                NULL::TEXT,
                NULL::TIMESTAMPTZ,
                FALSE,
                'Fehler beim Erstellen des Kurses'::TEXT;
    END;
END;
$$;


ALTER FUNCTION public.create_course(p_session_id text, p_name text, p_description text) OWNER TO postgres;

--
-- Name: create_learning_unit(text, text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.create_learning_unit(p_session_id text, p_title text, p_description text DEFAULT NULL::text) RETURNS TABLE(id uuid, title text, created_at timestamp with time zone, success boolean, error_message text)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_new_id UUID;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    -- Authorization: Only Teacher
    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RETURN QUERY SELECT
            NULL::UUID,
            NULL::TEXT,
            NULL::TIMESTAMPTZ,
            FALSE,
            'Keine Berechtigung fuer diese Aktion'::TEXT;
        RETURN;
    END IF;

    -- Input validation
    IF p_title IS NULL OR LENGTH(TRIM(p_title)) = 0 THEN
        RETURN QUERY SELECT
            NULL::UUID,
            NULL::TEXT,
            NULL::TIMESTAMPTZ,
            FALSE,
            'Titel darf nicht leer sein'::TEXT;
        RETURN;
    END IF;

    -- Create record (without description column)
    BEGIN
        INSERT INTO learning_unit (title, creator_id)
        VALUES (TRIM(p_title), v_user_id)
        RETURNING learning_unit.id INTO v_new_id;

        -- Success with data (use explicit column references)
        RETURN QUERY SELECT
            v_new_id AS id,
            TRIM(p_title) AS title,
            NOW() AS created_at,
            TRUE AS success,
            NULL::TEXT AS error_message;

    EXCEPTION
        WHEN unique_violation THEN
            RETURN QUERY SELECT
                NULL::UUID,
                NULL::TEXT,
                NULL::TIMESTAMPTZ,
                FALSE,
                'Eine Lerneinheit mit diesem Titel existiert bereits'::TEXT;
        WHEN OTHERS THEN
            RETURN QUERY SELECT
                NULL::UUID,
                NULL::TEXT,
                NULL::TIMESTAMPTZ,
                FALSE,
                'Fehler beim Erstellen der Lerneinheit: ' || SQLERRM;
    END;
END;
$$;


ALTER FUNCTION public.create_learning_unit(p_session_id text, p_title text, p_description text) OWNER TO postgres;

--
-- Name: create_mastery_task(text, uuid, text, text, integer, integer, jsonb); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.create_mastery_task(p_session_id text, p_section_id uuid, p_instruction text, p_task_type text, p_order_in_section integer DEFAULT 1, p_difficulty_level integer DEFAULT 1, p_assessment_criteria jsonb DEFAULT NULL::jsonb) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_task_id UUID;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can create tasks';
    END IF;

    -- Check if teacher has access to the section
    IF NOT EXISTS (
        SELECT 1 
        FROM unit_section s
        JOIN learning_unit lu ON lu.id = s.unit_id
        WHERE s.id = p_section_id AND lu.creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
    END IF;

    -- Begin transaction
    BEGIN
        -- Step 1: Insert into task_base with instruction
        INSERT INTO task_base (section_id, instruction, task_type, order_in_section, assessment_criteria)
        VALUES (p_section_id, p_instruction, p_task_type, p_order_in_section, p_assessment_criteria)
        RETURNING id INTO v_task_id;

        -- Step 2: Insert into mastery_tasks with correct columns
        INSERT INTO mastery_tasks (task_id, difficulty_level, spaced_repetition_interval)
        VALUES (v_task_id, p_difficulty_level, 1);  -- Default interval of 1 day

        RETURN v_task_id;
    EXCEPTION
        WHEN OTHERS THEN
            -- Rollback will happen automatically
            RAISE;
    END;
END;
$$;


ALTER FUNCTION public.create_mastery_task(p_session_id text, p_section_id uuid, p_instruction text, p_task_type text, p_order_in_section integer, p_difficulty_level integer, p_assessment_criteria jsonb) OWNER TO postgres;

--
-- Name: create_regular_task(text, uuid, text, text, integer, integer, jsonb); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.create_regular_task(p_session_id text, p_section_id uuid, p_instruction text, p_task_type text, p_order_in_section integer DEFAULT 1, p_max_attempts integer DEFAULT 1, p_assessment_criteria jsonb DEFAULT NULL::jsonb) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_task_id UUID;
    v_grading_criteria TEXT[];
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can create tasks';
    END IF;

    -- Check if teacher has access to the section
    IF NOT EXISTS (
        SELECT 1 
        FROM unit_section s
        JOIN learning_unit lu ON lu.id = s.unit_id
        WHERE s.id = p_section_id AND lu.creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
    END IF;

    -- Convert JSONB array to TEXT[] for backward compatibility
    IF p_assessment_criteria IS NOT NULL AND jsonb_typeof(p_assessment_criteria) = 'array' THEN
        v_grading_criteria := ARRAY(SELECT jsonb_array_elements_text(p_assessment_criteria));
    ELSE
        v_grading_criteria := NULL;
    END IF;

    -- Begin transaction
    BEGIN
        -- Step 1: Insert into task_base with instruction
        INSERT INTO task_base (section_id, instruction, task_type, order_in_section, assessment_criteria)
        VALUES (p_section_id, p_instruction, p_task_type, p_order_in_section, p_assessment_criteria)
        RETURNING id INTO v_task_id;

        -- Step 2: Insert into regular_tasks with converted grading_criteria
        INSERT INTO regular_tasks (task_id, prompt, max_attempts, grading_criteria)
        VALUES (v_task_id, p_instruction, p_max_attempts, v_grading_criteria);

        RETURN v_task_id;
    EXCEPTION
        WHEN OTHERS THEN
            -- Rollback will happen automatically
            RAISE;
    END;
END;
$$;


ALTER FUNCTION public.create_regular_task(p_session_id text, p_section_id uuid, p_instruction text, p_task_type text, p_order_in_section integer, p_max_attempts integer, p_assessment_criteria jsonb) OWNER TO postgres;

--
-- Name: create_section(text, uuid, text, text, jsonb); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.create_section(p_session_id text, p_unit_id uuid, p_title text, p_description text DEFAULT NULL::text, p_materials jsonb DEFAULT NULL::jsonb) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_section_id UUID;
    v_order_in_unit INT;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can create sections';
    END IF;

    -- Check if teacher owns the learning unit
    IF NOT EXISTS (
        SELECT 1 FROM learning_unit 
        WHERE id = p_unit_id AND creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
    END IF;

    -- Get next order position
    SELECT COALESCE(MAX(order_in_unit), 0) + 1
    INTO v_order_in_unit
    FROM unit_section
    WHERE unit_id = p_unit_id;  -- Fixed: using unit_id

    -- Create section (without description since column doesn't exist)
    INSERT INTO unit_section (
        unit_id,  -- Fixed: using unit_id
        title,
        materials,
        order_in_unit
    )
    VALUES (
        p_unit_id,
        p_title,
        p_materials,
        v_order_in_unit
    )
    RETURNING id INTO v_section_id;

    RETURN v_section_id;
END;
$$;


ALTER FUNCTION public.create_section(p_session_id text, p_unit_id uuid, p_title text, p_description text, p_materials jsonb) OWNER TO postgres;

--
-- Name: create_session(uuid, text, text, jsonb, interval, inet, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.create_session(p_user_id uuid, p_user_email text, p_user_role text, p_data jsonb DEFAULT '{}'::jsonb, p_expires_in interval DEFAULT '01:30:00'::interval, p_ip_address inet DEFAULT NULL::inet, p_user_agent text DEFAULT NULL::text) RETURNS TABLE(session_id character varying, expires_at timestamp with time zone, created_at timestamp with time zone)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'extensions'
    AS $$
DECLARE
    v_session_id VARCHAR(255);
    v_expires_at TIMESTAMPTZ;
    v_created_at TIMESTAMPTZ;
    v_session_count INT;
    v_rate_limit RECORD;
BEGIN
    -- Rate limiting check
    INSERT INTO session_rate_limits (user_id, attempts, window_start, last_attempt)
    VALUES (p_user_id, 1, NOW(), NOW())
    ON CONFLICT (user_id) DO UPDATE
    SET 
        attempts = CASE 
            WHEN session_rate_limits.window_start < NOW() - INTERVAL '1 hour' THEN 1
            ELSE session_rate_limits.attempts + 1
        END,
        window_start = CASE 
            WHEN session_rate_limits.window_start < NOW() - INTERVAL '1 hour' THEN NOW()
            ELSE session_rate_limits.window_start
        END,
        last_attempt = NOW()
    RETURNING * INTO v_rate_limit;
    
    -- Check rate limit (max 10 attempts per hour)
    IF v_rate_limit.window_start > NOW() - INTERVAL '1 hour' AND v_rate_limit.attempts > 10 THEN
        RAISE EXCEPTION 'Rate limit exceeded. Too many session creation attempts.';
    END IF;
    
    -- Clean up old rate limits periodically
    IF random() < 0.01 THEN -- 1% chance to run cleanup
        PERFORM cleanup_session_rate_limits();
    END IF;
    
    -- Validate inputs
    IF p_user_id IS NULL THEN
        RAISE EXCEPTION 'user_id cannot be null';
    END IF;
    
    IF p_user_email IS NULL OR p_user_email = '' THEN
        RAISE EXCEPTION 'user_email cannot be empty';
    END IF;
    
    IF p_user_role NOT IN ('teacher', 'student', 'admin') THEN
        RAISE EXCEPTION 'Invalid user_role: %', p_user_role;
    END IF;
    
    -- Check if user exists in auth.users
    IF NOT EXISTS (SELECT 1 FROM auth.users WHERE id = p_user_id) THEN
        RAISE EXCEPTION 'User % does not exist', p_user_id;
    END IF;
    
    -- Generate secure session ID
    v_session_id := encode(gen_random_bytes(32), 'base64');
    v_session_id := replace(v_session_id, '+', '-');
    v_session_id := replace(v_session_id, '/', '_');
    v_session_id := rtrim(v_session_id, '=');
    
    -- Calculate expiration
    v_expires_at := NOW() + p_expires_in;
    v_created_at := NOW();
    
    -- Insert new session (trigger will handle session limit)
    INSERT INTO auth_sessions (
        session_id,
        user_id,
        user_email,
        user_role,
        data,
        expires_at,
        ip_address,
        user_agent,
        created_at,
        last_activity
    ) VALUES (
        v_session_id,
        p_user_id,
        p_user_email,
        p_user_role,
        p_data,
        v_expires_at,
        p_ip_address,
        p_user_agent,
        v_created_at,
        v_created_at
    );
    
    -- Log session creation
    RAISE LOG 'Session created for user % with role %', p_user_id, p_user_role;
    
    RETURN QUERY SELECT v_session_id, v_expires_at, v_created_at;
END;
$$;


ALTER FUNCTION public.create_session(p_user_id uuid, p_user_email text, p_user_role text, p_data jsonb, p_expires_in interval, p_ip_address inet, p_user_agent text) OWNER TO postgres;

--
-- Name: FUNCTION create_session(p_user_id uuid, p_user_email text, p_user_role text, p_data jsonb, p_expires_in interval, p_ip_address inet, p_user_agent text); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.create_session(p_user_id uuid, p_user_email text, p_user_role text, p_data jsonb, p_expires_in interval, p_ip_address inet, p_user_agent text) IS 'Creates a new session for a user with automatic session limit enforcement';


--
-- Name: create_session_for_auth_service(uuid, text, text, jsonb, interval, inet, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.create_session_for_auth_service(p_user_id uuid, p_user_email text, p_user_role text, p_data jsonb DEFAULT '{}'::jsonb, p_expires_in interval DEFAULT '01:30:00'::interval, p_ip_address inet DEFAULT NULL::inet, p_user_agent text DEFAULT NULL::text) RETURNS character varying
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'extensions'
    AS $$
DECLARE
    v_session_id VARCHAR(255);
    v_user RECORD;
    v_result RECORD;
BEGIN
    -- SECURITY: Validate that the user actually exists and email matches
    SELECT id, email INTO v_user
    FROM auth.users 
    WHERE id = p_user_id;
    
    IF v_user.id IS NULL THEN
        RAISE EXCEPTION 'Invalid user_id';
    END IF;
    
    -- SECURITY: Verify email matches (case-insensitive)
    IF lower(v_user.email) != lower(p_user_email) THEN
        RAISE EXCEPTION 'Email mismatch for user';
    END IF;
    
    -- Call the existing create_session function with elevated privileges
    SELECT session_id INTO v_session_id
    FROM create_session(
        p_user_id,
        p_user_email,
        p_user_role,
        p_data,
        p_expires_in,
        p_ip_address,
        p_user_agent
    );
    
    RETURN v_session_id;
EXCEPTION
    WHEN OTHERS THEN
        -- Log the error but don't expose internal details
        RAISE LOG 'Session creation error: %', SQLERRM;
        RAISE EXCEPTION 'Failed to create session';
END;
$$;


ALTER FUNCTION public.create_session_for_auth_service(p_user_id uuid, p_user_email text, p_user_role text, p_data jsonb, p_expires_in interval, p_ip_address inet, p_user_agent text) OWNER TO postgres;

--
-- Name: FUNCTION create_session_for_auth_service(p_user_id uuid, p_user_email text, p_user_role text, p_data jsonb, p_expires_in interval, p_ip_address inet, p_user_agent text); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.create_session_for_auth_service(p_user_id uuid, p_user_email text, p_user_role text, p_data jsonb, p_expires_in interval, p_ip_address inet, p_user_agent text) IS 'Secure session creation for auth service - validates user exists and email matches before creating session';


--
-- Name: create_session_with_api_key(text, character varying, uuid, text, text, jsonb, timestamp with time zone, inet, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.create_session_with_api_key(p_api_key text, p_session_id character varying, p_user_id uuid, p_user_email text, p_user_role text, p_data jsonb, p_expires_at timestamp with time zone, p_ip_address inet DEFAULT NULL::inet, p_user_agent text DEFAULT NULL::text) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    key_validation RECORD;
    new_session_id UUID;
BEGIN
    -- Validate API key
    SELECT * INTO key_validation FROM public.validate_auth_service_key(p_api_key);
    
    IF NOT key_validation.is_valid THEN
        RAISE EXCEPTION 'Invalid API key';
    END IF;
    
    IF NOT (key_validation.permissions ? 'manage_sessions') THEN
        RAISE EXCEPTION 'API key lacks session management permission';
    END IF;
    
    -- Create session
    INSERT INTO public.auth_sessions (
        session_id, user_id, user_email, user_role, 
        data, expires_at, ip_address, user_agent
    ) VALUES (
        p_session_id, p_user_id, p_user_email, p_user_role,
        p_data, p_expires_at, p_ip_address, p_user_agent
    ) RETURNING id INTO new_session_id;
    
    RETURN new_session_id;
END;
$$;


ALTER FUNCTION public.create_session_with_api_key(p_api_key text, p_session_id character varying, p_user_id uuid, p_user_email text, p_user_role text, p_data jsonb, p_expires_at timestamp with time zone, p_ip_address inet, p_user_agent text) OWNER TO postgres;

--
-- Name: FUNCTION create_session_with_api_key(p_api_key text, p_session_id character varying, p_user_id uuid, p_user_email text, p_user_role text, p_data jsonb, p_expires_at timestamp with time zone, p_ip_address inet, p_user_agent text); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.create_session_with_api_key(p_api_key text, p_session_id character varying, p_user_id uuid, p_user_email text, p_user_role text, p_data jsonb, p_expires_at timestamp with time zone, p_ip_address inet, p_user_agent text) IS 'Creates a session after validating API key - secure alternative to using service role';


--
-- Name: create_submission(text, uuid, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.create_submission(p_session_id text, p_task_id uuid, p_submission_text text) RETURNS json
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_user_id UUID;
    v_section_id UUID;
    v_max_attempts INT;
    v_is_mastery BOOLEAN := FALSE;
    v_attempt_count INT;
    v_submission_id UUID;
    v_submission_data JSONB;
BEGIN
    -- Get user from session using the correct auth_sessions table
    SELECT user_id INTO v_user_id
    FROM auth_sessions 
    WHERE session_id = p_session_id 
    AND expires_at > NOW();
    
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid or expired session';
    END IF;

    -- Check if task exists in regular tasks first
    SELECT 
        t.section_id,
        t.max_attempts,
        FALSE
    INTO v_section_id, v_max_attempts, v_is_mastery
    FROM all_regular_tasks t
    WHERE t.id = p_task_id;

    -- If not found in regular tasks, check mastery tasks
    IF NOT FOUND THEN
        SELECT 
            t.section_id,
            NULL::INT, -- Mastery tasks have unlimited attempts
            TRUE
        INTO v_section_id, v_max_attempts, v_is_mastery
        FROM all_mastery_tasks t
        WHERE t.id = p_task_id;
        
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Task not found';
        END IF;
    END IF;

    -- Check attempt limit ONLY for regular tasks (not mastery tasks)
    IF NOT v_is_mastery AND v_max_attempts IS NOT NULL THEN
        SELECT COUNT(*)
        INTO v_attempt_count
        FROM submission s
        WHERE s.student_id = v_user_id AND s.task_id = p_task_id;

        IF v_attempt_count >= v_max_attempts THEN
            RAISE EXCEPTION 'Maximum attempts exceeded for this task';
        END IF;
    END IF;

    -- Calculate attempt number (for both regular and mastery tasks)
    SELECT COALESCE(MAX(attempt_number), 0) + 1
    INTO v_attempt_count
    FROM submission s
    WHERE s.student_id = v_user_id AND s.task_id = p_task_id;

    -- Generate new submission ID
    v_submission_id := gen_random_uuid();

    -- Insert submission with proper defaults for queue processing
    INSERT INTO submission (
        id,
        student_id,
        task_id,
        submission_data,
        attempt_number,
        submitted_at,
        feedback_status,
        retry_count,
        last_retry_at,
        processing_started_at
    ) VALUES (
        v_submission_id,
        v_user_id,
        p_task_id,
        p_submission_text::JSONB,
        v_attempt_count,
        NOW(),
        'pending',    -- Default status for queue processing
        0,            -- Start with 0 retries
        NULL,         -- No retries yet
        NULL          -- Not processing yet
    );

    -- Return the created submission
    SELECT jsonb_build_object(
        'id', s.id,
        'student_id', s.student_id,
        'task_id', s.task_id,
        'submission_data', s.submission_data,
        'attempt_number', s.attempt_number,
        'submitted_at', s.submitted_at,
        'feedback_status', s.feedback_status,
        'is_mastery_task', v_is_mastery
    ) INTO v_submission_data
    FROM submission s
    WHERE s.id = v_submission_id;

    RETURN v_submission_data;
END;
$$;


ALTER FUNCTION public.create_submission(p_session_id text, p_task_id uuid, p_submission_text text) OWNER TO postgres;

--
-- Name: FUNCTION create_submission(p_session_id text, p_task_id uuid, p_submission_text text); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.create_submission(p_session_id text, p_task_id uuid, p_submission_text text) IS 'Creates a new submission with proper mastery task handling and correct session validation using auth_sessions table. Regular tasks respect max_attempts limits, mastery tasks have unlimited attempts for spaced repetition learning.';


--
-- Name: create_task_in_new_structure(text, uuid, text, text, text, integer, text[], integer, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.create_task_in_new_structure(p_session_id text, p_section_id uuid, p_title text, p_prompt text, p_task_type text DEFAULT 'regular'::text, p_max_attempts integer DEFAULT NULL::integer, p_grading_criteria text[] DEFAULT NULL::text[], p_difficulty_level integer DEFAULT NULL::integer, p_concept_explanation text DEFAULT NULL::text) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
            DECLARE
                v_user_id UUID;
                v_user_role TEXT;
                v_is_valid BOOLEAN;
                v_task_id UUID;
                v_order_in_section INT;
            BEGIN
                -- Session validation
                SELECT user_id, user_role, is_valid
                INTO v_user_id, v_user_role, v_is_valid
                FROM public.validate_session_and_get_user(p_session_id);

                IF NOT v_is_valid OR v_user_role != 'teacher' THEN
                    RAISE EXCEPTION 'Unauthorized: Only teachers can create tasks';
                END IF;

                -- Check ownership through section
                IF NOT EXISTS (
                    SELECT 1 
                    FROM unit_section s
                    JOIN learning_unit lu ON lu.id = s.unit_id
                    WHERE s.id = p_section_id AND lu.created_by = v_user_id
                ) THEN
                    RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
                END IF;

                -- Get next order position
                SELECT COALESCE(MAX(order_in_section), 0) + 1
                INTO v_order_in_section
                FROM task_base
                WHERE section_id = p_section_id;

                -- Create task based on type
                IF p_task_type = 'mastery' THEN
                    -- Insert into task_base with instruction
                    INSERT INTO task_base (section_id, title, instruction, task_type, order_in_section)
                    VALUES (p_section_id, p_title, p_prompt, p_task_type, v_order_in_section)
                    RETURNING id INTO v_task_id;

                    -- Insert into mastery_task
                    INSERT INTO mastery_task (task_id, difficulty_level, concept_explanation)
                    VALUES (v_task_id, COALESCE(p_difficulty_level, 1), p_concept_explanation);
                ELSE
                    -- Insert into task_base with instruction
                    INSERT INTO task_base (section_id, title, instruction, prompt, task_type, order_in_section)
                    VALUES (p_section_id, p_title, p_prompt, p_prompt, p_task_type, v_order_in_section)
                    RETURNING id INTO v_task_id;

                    -- Insert into regular_task
                    INSERT INTO regular_task (task_id, max_attempts, grading_criteria)
                    VALUES (v_task_id, COALESCE(p_max_attempts, 1), p_grading_criteria);
                END IF;

                RETURN v_task_id;
            END;
            $$;


ALTER FUNCTION public.create_task_in_new_structure(p_session_id text, p_section_id uuid, p_title text, p_prompt text, p_task_type text, p_max_attempts integer, p_grading_criteria text[], p_difficulty_level integer, p_concept_explanation text) OWNER TO postgres;

--
-- Name: create_task_in_new_structure(text, uuid, text, text, text, boolean, integer, integer, text[], integer, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.create_task_in_new_structure(p_session_id text, p_section_id uuid, p_title text, p_prompt text, p_task_type text, p_is_mastery boolean, p_order_in_section integer DEFAULT 1, p_max_attempts integer DEFAULT 1, p_grading_criteria text[] DEFAULT NULL::text[], p_difficulty_level integer DEFAULT 1, p_concept_explanation text DEFAULT NULL::text) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_task_id UUID;
BEGIN
    IF p_is_mastery THEN
        -- Create mastery task
        v_task_id := public.create_mastery_task(
            p_session_id,
            p_section_id,
            p_title,
            p_prompt,
            p_task_type,
            p_difficulty_level,
            p_concept_explanation
        );
    ELSE
        -- Create regular task
        v_task_id := public.create_regular_task(
            p_session_id,
            p_section_id,
            p_title,
            p_prompt,
            p_task_type,
            p_order_in_section,
            p_max_attempts,
            p_grading_criteria
        );
    END IF;

    RETURN v_task_id;
END;
$$;


ALTER FUNCTION public.create_task_in_new_structure(p_session_id text, p_section_id uuid, p_title text, p_prompt text, p_task_type text, p_is_mastery boolean, p_order_in_section integer, p_max_attempts integer, p_grading_criteria text[], p_difficulty_level integer, p_concept_explanation text) OWNER TO postgres;

--
-- Name: delete_course(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.delete_course(p_session_id text, p_course_id uuid) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can delete courses';
    END IF;

    -- Check if teacher is course creator
    IF NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id  -- Fixed: changed created_by to creator_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Only course creator can delete the course';
    END IF;

    -- Delete course (CASCADE will handle related records)
    DELETE FROM course
    WHERE id = p_course_id;
END;
$$;


ALTER FUNCTION public.delete_course(p_session_id text, p_course_id uuid) OWNER TO postgres;

--
-- Name: delete_learning_unit(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.delete_learning_unit(p_session_id text, p_unit_id uuid) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can delete learning units';
    END IF;

    -- Check if teacher owns the learning unit
    IF NOT EXISTS (
        SELECT 1 FROM learning_unit 
        WHERE id = p_unit_id AND creator_id = v_user_id  -- Fixed: changed created_by to creator_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Only unit creator can delete the unit';
    END IF;

    -- Delete learning unit (CASCADE will handle related records)
    DELETE FROM learning_unit
    WHERE id = p_unit_id;
END;
$$;


ALTER FUNCTION public.delete_learning_unit(p_session_id text, p_unit_id uuid) OWNER TO postgres;

--
-- Name: delete_session(character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.delete_session(p_session_id character varying) RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'extensions'
    AS $$
DECLARE
    v_deleted INT;
BEGIN
    DELETE FROM auth_sessions
    WHERE session_id = p_session_id;
    
    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    
    IF v_deleted > 0 THEN
        RAISE LOG 'Session % deleted', p_session_id;
    END IF;
    
    RETURN v_deleted > 0;
END;
$$;


ALTER FUNCTION public.delete_session(p_session_id character varying) OWNER TO postgres;

--
-- Name: FUNCTION delete_session(p_session_id character varying); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.delete_session(p_session_id character varying) IS 'Explicitly deletes a session (logout)';


--
-- Name: delete_task_in_new_structure(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.delete_task_in_new_structure(p_session_id text, p_task_id uuid) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can delete tasks';
    END IF;

    -- Check if teacher has access to the task
    IF NOT EXISTS (
        SELECT 1 
        FROM task_base t
        JOIN unit_section s ON s.id = t.section_id
        JOIN learning_unit lu ON lu.id = s.unit_id  -- Changed from s.learning_unit_id
        WHERE t.id = p_task_id AND lu.creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
    END IF;

    -- Delete from type-specific table first (due to foreign key constraints)
    DELETE FROM regular_tasks WHERE task_id = p_task_id;
    DELETE FROM mastery_tasks WHERE task_id = p_task_id;
    
    -- Then delete from base table
    DELETE FROM task_base WHERE id = p_task_id;
END;
$$;


ALTER FUNCTION public.delete_task_in_new_structure(p_session_id text, p_task_id uuid) OWNER TO postgres;

--
-- Name: enforce_session_limit(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.enforce_session_limit() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    session_count INTEGER;
    max_sessions INTEGER := 5; -- Max 5 concurrent sessions per user
BEGIN
    -- Count current active sessions for this user
    SELECT COUNT(*) INTO session_count
    FROM public.auth_sessions
    WHERE user_id = NEW.user_id
    AND expires_at > NOW();

    -- If limit exceeded, delete oldest sessions
    IF session_count >= max_sessions THEN
        DELETE FROM public.auth_sessions
        WHERE user_id = NEW.user_id
        AND id IN (
            SELECT id FROM public.auth_sessions
            WHERE user_id = NEW.user_id
            ORDER BY last_activity ASC
            LIMIT (session_count - max_sessions + 1)
        );
    END IF;

    RETURN NEW;
END;
$$;


ALTER FUNCTION public.enforce_session_limit() OWNER TO postgres;

--
-- Name: FUNCTION enforce_session_limit(); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.enforce_session_limit() IS 'Limits concurrent sessions per user to prevent flooding';


--
-- Name: ensure_feedback_consistency(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.ensure_feedback_consistency() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- If ai_feedback is set, ensure status is completed
    IF NEW.ai_feedback IS NOT NULL AND NEW.feedback_status IN ('pending', 'processing') THEN
        NEW.feedback_status = 'completed';
    END IF;
    
    -- If feed_back_text and feed_forward_text are set, ensure status is completed
    IF NEW.feed_back_text IS NOT NULL AND NEW.feed_forward_text IS NOT NULL AND NEW.feedback_status IN ('pending', 'processing') THEN
        NEW.feedback_status = 'completed';
    END IF;
    
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.ensure_feedback_consistency() OWNER TO postgres;

--
-- Name: FUNCTION ensure_feedback_consistency(); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.ensure_feedback_consistency() IS 'Ensures feedback_status is consistent with actual feedback data';


--
-- Name: get_all_feedback(text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_all_feedback(p_session_id text) RETURNS TABLE(id uuid, feedback_type text, message text, created_at timestamp with time zone)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    -- Only teachers can see all feedback
    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RETURN;
    END IF;

    -- Return all feedback using actual table schema
    RETURN QUERY
    SELECT
        f.id,
        f.feedback_type,
        f.message,
        f.created_at
    FROM feedback f
    ORDER BY f.created_at DESC;
END;
$$;


ALTER FUNCTION public.get_all_feedback(p_session_id text) OWNER TO postgres;

--
-- Name: get_course_by_id(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_course_by_id(p_session_id text, p_course_id uuid) RETURNS TABLE(id uuid, name text, creator_id uuid, created_at timestamp with time zone)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN;
    END IF;

    -- Berechtigung pruefen: User muss im Kurs sein oder Lehrer
    IF v_user_role = 'student' THEN
        IF NOT EXISTS (
            SELECT 1 FROM course_student cs
            WHERE cs.course_id = p_course_id AND cs.student_id = v_user_id
        ) THEN
            RETURN;
        END IF;
    ELSIF v_user_role = 'teacher' THEN
        -- Lehrer kuennen alle Kurse sehen (fuer Admin-Funktionen)
        NULL; -- Explizit keine Einschruenkung
    END IF;

    -- Kurs zurueckgeben
    RETURN QUERY
    SELECT
        c.id,
        c.name,
        c.creator_id,
        c.created_at
    FROM course c
    WHERE c.id = p_course_id;
END;
$$;


ALTER FUNCTION public.get_course_by_id(p_session_id text, p_course_id uuid) OWNER TO postgres;

--
-- Name: get_course_students(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_course_students(p_session_id text, p_course_id uuid) RETURNS TABLE(student_id uuid, email text, display_name text)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can view course students';
    END IF;

    -- Check if teacher is authorized for this course
    IF NOT EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id  -- Fixed: changed created_by to creator_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Return students
    RETURN QUERY
    SELECT 
        cs.student_id,
        p.email,
        COALESCE(p.full_name, SPLIT_PART(p.email, '@', 1)) as display_name
    FROM course_student cs
    JOIN profiles p ON p.id = cs.student_id
    WHERE cs.course_id = p_course_id
    ORDER BY p.email;
END;
$$;


ALTER FUNCTION public.get_course_students(p_session_id text, p_course_id uuid) OWNER TO postgres;

--
-- Name: get_course_units(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_course_units(p_session_id text, p_course_id uuid) RETURNS TABLE(id uuid, learning_unit_id uuid, learning_unit_title text, created_at timestamp with time zone)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN;
    END IF;

    -- Zugriffsberechtigung pruefen
    IF v_user_role = 'teacher' THEN
        -- Lehrer: Alle Units in eigenen Kursen
        IF NOT EXISTS (
            SELECT 1 FROM course c 
            WHERE c.id = p_course_id AND c.creator_id = v_user_id -- FIX: Use creator_id instead of created_by
            UNION
            SELECT 1 FROM course_teacher ct 
            WHERE ct.course_id = p_course_id AND ct.teacher_id = v_user_id
        ) THEN
            RETURN;
        END IF;
    ELSIF v_user_role = 'student' THEN
        -- Student: Nur Units in eigenen Kursen
        IF NOT EXISTS (
            SELECT 1 FROM course_student cs 
            WHERE cs.course_id = p_course_id AND cs.student_id = v_user_id
        ) THEN
            RETURN;
        END IF;
    END IF;

    -- Units zurueckgeben
    RETURN QUERY
    SELECT
        lu.id,
        lu.id as learning_unit_id, -- Map to expected column name in signature
        lu.title as learning_unit_title,
        clua.assigned_at as created_at
    FROM learning_unit lu
    JOIN course_learning_unit_assignment clua ON lu.id = clua.unit_id -- FIX: Use unit_id instead of learning_unit_id
    WHERE clua.course_id = p_course_id
    ORDER BY clua.assigned_at;
END;
$$;


ALTER FUNCTION public.get_course_units(p_session_id text, p_course_id uuid) OWNER TO postgres;

--
-- Name: get_courses_assigned_to_unit(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_courses_assigned_to_unit(p_session_id text, p_unit_id uuid) RETURNS TABLE(id uuid, name text, creator_id uuid, created_at timestamp with time zone)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    -- Nur Lehrer duerfen Kurszuweisungen sehen
    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RETURN;
    END IF;

    -- Kurse zurueckgeben, die diese Unit verwenden
    RETURN QUERY
    SELECT
        c.id,
        c.name,
        c.creator_id, -- FIX: Use creator_id instead of created_by (but keep in signature)
        clua.assigned_at as created_at
    FROM course c
    JOIN course_learning_unit_assignment clua ON c.id = clua.course_id
    WHERE clua.unit_id = p_unit_id -- FIX: Use unit_id instead of learning_unit_id
    ORDER BY c.name;
END;
$$;


ALTER FUNCTION public.get_courses_assigned_to_unit(p_session_id text, p_unit_id uuid) OWNER TO postgres;

--
-- Name: get_due_tomorrow_count(text, uuid, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_due_tomorrow_count(p_session_id text, p_student_id uuid, p_course_id uuid) RETURNS integer
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_count INT;
BEGIN
    -- Get user from session with role
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid or expired session';
    END IF;
    
    -- Check authorization
    IF v_user_id != p_student_id AND v_user_role NOT IN ('admin', 'teacher') THEN
        RAISE EXCEPTION 'Not authorized to view other users data';
    END IF;
    
    SELECT COUNT(*)::INT INTO v_count
    FROM student_mastery_progress smp
    JOIN mastery_tasks mt ON mt.task_id = smp.task_id
    JOIN task_base t ON t.id = mt.task_id
    JOIN unit_section us ON us.id = t.section_id
    JOIN course_learning_unit_assignment clua ON clua.unit_id = us.unit_id  -- Correct table!
    WHERE smp.student_id = p_student_id
    AND clua.course_id = p_course_id
    AND smp.next_due_date = CURRENT_DATE + INTERVAL '1 day';
    
    RETURN v_count;
END;
$$;


ALTER FUNCTION public.get_due_tomorrow_count(p_session_id text, p_student_id uuid, p_course_id uuid) OWNER TO postgres;

--
-- Name: FUNCTION get_due_tomorrow_count(p_session_id text, p_student_id uuid, p_course_id uuid); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.get_due_tomorrow_count(p_session_id text, p_student_id uuid, p_course_id uuid) IS 'Gets due tomorrow count with correct course_learning_unit_assignment table';


--
-- Name: get_learning_unit(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_learning_unit(p_session_id text, p_unit_id uuid) RETURNS TABLE(id uuid, title text, creator_id uuid, created_at timestamp with time zone, can_edit boolean)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    -- Invalid session = empty result
    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RETURN;
    END IF;

    -- Input validation
    IF p_unit_id IS NULL THEN
        RETURN;
    END IF;

    -- Load Learning Unit with authorization (OHNE description)
    RETURN QUERY
    SELECT
        lu.id,
        lu.title,
        lu.creator_id,
        lu.created_at,
        (lu.creator_id = v_user_id OR v_user_role = 'admin')::BOOLEAN as can_edit
    FROM learning_unit lu
    WHERE lu.id = p_unit_id
    AND (
        lu.creator_id = v_user_id  -- Owner
        OR v_user_role = 'admin'   -- Admin
        OR EXISTS (                -- Student with access through Course Assignment
            SELECT 1 
            FROM course_learning_unit_assignment clua
            INNER JOIN course_student cs ON cs.course_id = clua.course_id
            WHERE clua.unit_id = lu.id
            AND cs.student_id = v_user_id
        )
    );
END;
$$;


ALTER FUNCTION public.get_learning_unit(p_session_id text, p_unit_id uuid) OWNER TO postgres;

--
-- Name: get_mastery_stats_for_student(text, uuid, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_mastery_stats_for_student(p_session_id text, p_student_id uuid, p_course_id uuid) RETURNS TABLE(total_tasks integer, completed_tasks integer, due_today integer, overdue integer, upcoming integer, completion_rate double precision, average_rating double precision, streak_days integer)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Get user from session with role
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid or expired session';
    END IF;
    
    -- Check authorization (student viewing own stats or teacher)
    IF v_user_id != p_student_id AND v_user_role NOT IN ('admin', 'teacher') THEN
        RAISE EXCEPTION 'Not authorized to view other users stats';
    END IF;
    
    -- Teacher must be teaching the course
    IF v_user_id != p_student_id AND v_user_role = 'teacher' THEN
        IF NOT EXISTS (
            SELECT 1 FROM course_teachers
            WHERE teacher_id = v_user_id
            AND course_id = p_course_id
        ) THEN
            RAISE EXCEPTION 'Not authorized for this course';
        END IF;
    END IF;
    
    RETURN QUERY
    WITH task_stats AS (
        SELECT
            mt.task_id,
            smp.next_due_date,
            smp.last_reviewed_at,
            CASE
                WHEN smp.last_reviewed_at IS NOT NULL THEN 1
                ELSE 0
            END as is_completed,
            CASE
                WHEN smp.next_due_date = CURRENT_DATE THEN 1
                ELSE 0
            END as is_due_today,
            CASE
                WHEN smp.next_due_date < CURRENT_DATE THEN 1
                ELSE 0
            END as is_overdue,
            CASE
                WHEN smp.next_due_date > CURRENT_DATE THEN 1
                ELSE 0
            END as is_upcoming
        FROM mastery_tasks mt
        JOIN task_base t ON t.id = mt.task_id
        JOIN unit_section us ON us.id = t.section_id
        JOIN course_learning_unit_assignment clua ON clua.unit_id = us.unit_id  -- Correct table!
        LEFT JOIN student_mastery_progress smp ON smp.task_id = mt.task_id 
            AND smp.student_id = p_student_id
        WHERE clua.course_id = p_course_id
    ),
    recent_submissions AS (
        SELECT DISTINCT
            s.task_id,
            (s.ai_insights->>'korrektheit')::FLOAT as rating
        FROM submission s
        JOIN mastery_tasks mt ON mt.task_id = s.task_id
        JOIN task_base t ON t.id = mt.task_id
        JOIN unit_section us ON us.id = t.section_id
        JOIN course_learning_unit_assignment clua ON clua.unit_id = us.unit_id  -- Correct table!
        WHERE s.student_id = p_student_id
        AND clua.course_id = p_course_id
        AND s.submitted_at >= CURRENT_DATE - INTERVAL '30 days'
        AND s.ai_insights IS NOT NULL
    )
    SELECT
        COUNT(DISTINCT ts.task_id)::INT as total_tasks,
        SUM(ts.is_completed)::INT as completed_tasks,
        SUM(ts.is_due_today)::INT as due_today,
        SUM(ts.is_overdue)::INT as overdue,
        SUM(ts.is_upcoming)::INT as upcoming,
        CASE
            WHEN COUNT(DISTINCT ts.task_id) > 0 
            THEN (SUM(ts.is_completed)::FLOAT / COUNT(DISTINCT ts.task_id)::FLOAT)
            ELSE 0.0
        END as completion_rate,
        COALESCE(AVG(rs.rating), 0.0) as average_rating,
        0 as streak_days
    FROM task_stats ts
    LEFT JOIN recent_submissions rs ON rs.task_id = ts.task_id;
END;
$$;


ALTER FUNCTION public.get_mastery_stats_for_student(p_session_id text, p_student_id uuid, p_course_id uuid) OWNER TO postgres;

--
-- Name: FUNCTION get_mastery_stats_for_student(p_session_id text, p_student_id uuid, p_course_id uuid); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.get_mastery_stats_for_student(p_session_id text, p_student_id uuid, p_course_id uuid) IS 'Gets mastery statistics with correct course_learning_unit_assignment table';


--
-- Name: get_mastery_summary(text, uuid, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_mastery_summary(p_session_id text, p_student_id uuid, p_course_id uuid) RETURNS TABLE(total integer, mastered integer, learning integer, not_started integer, due_today integer, avg_stability double precision)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Get user from session with role
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid or expired session';
    END IF;
    
    -- Check authorization
    IF v_user_id != p_student_id AND v_user_role NOT IN ('admin', 'teacher') THEN
        RAISE EXCEPTION 'Not authorized to view other users data';
    END IF;
    
    RETURN QUERY
    WITH task_stats AS (
        SELECT
            mt.task_id,
            CASE
                WHEN smp.stability > 21 THEN 'mastered'
                WHEN smp.stability IS NOT NULL THEN 'learning'
                ELSE 'not_started'
            END as status,
            smp.stability,
            smp.next_due_date
        FROM mastery_tasks mt
        JOIN task_base t ON t.id = mt.task_id
        JOIN unit_section us ON us.id = t.section_id
        JOIN course_learning_unit_assignment clua ON clua.unit_id = us.unit_id  -- Correct table!
        LEFT JOIN student_mastery_progress smp ON smp.task_id = mt.task_id 
            AND smp.student_id = p_student_id
        WHERE clua.course_id = p_course_id
    )
    SELECT
        COUNT(*)::INT as total,
        COUNT(CASE WHEN status = 'mastered' THEN 1 END)::INT as mastered,
        COUNT(CASE WHEN status = 'learning' THEN 1 END)::INT as learning,
        COUNT(CASE WHEN status = 'not_started' THEN 1 END)::INT as not_started,
        COUNT(CASE WHEN next_due_date <= CURRENT_DATE THEN 1 END)::INT as due_today,
        COALESCE(AVG(stability), 1.0)::FLOAT as avg_stability
    FROM task_stats;
END;
$$;


ALTER FUNCTION public.get_mastery_summary(p_session_id text, p_student_id uuid, p_course_id uuid) OWNER TO postgres;

--
-- Name: FUNCTION get_mastery_summary(p_session_id text, p_student_id uuid, p_course_id uuid); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.get_mastery_summary(p_session_id text, p_student_id uuid, p_course_id uuid) IS 'Gets mastery summary with correct course_learning_unit_assignment table';


--
-- Name: get_mastery_tasks_for_course(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_mastery_tasks_for_course(p_session_id text, p_course_id uuid) RETURNS TABLE(task_id uuid, task_title text, task_type text, unit_id uuid, unit_title text, section_id uuid, section_title text, review_after timestamp with time zone, proficiency_score numeric)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid THEN
        RAISE EXCEPTION 'Invalid session';
    END IF;
    
    -- Check if user is enrolled in course or is the teacher
    IF v_user_role = 'student' THEN
        IF NOT EXISTS (
            SELECT 1 FROM course_student 
            WHERE course_id = p_course_id AND student_id = v_user_id
        ) THEN
            RAISE EXCEPTION 'Student not enrolled in course';
        END IF;
    ELSIF v_user_role = 'teacher' THEN
        IF NOT EXISTS (
            SELECT 1 FROM course 
            WHERE id = p_course_id AND creator_id = v_user_id
        ) THEN
            RAISE EXCEPTION 'Teacher does not own this course';
        END IF;
    END IF;
    
    -- Get all mastery tasks for the course
    -- Removed DISTINCT and added columns needed for ORDER BY
    RETURN QUERY
    SELECT 
        tb.id as task_id,
        tb.instruction as task_title,
        tb.task_type,
        lu.id as unit_id,
        lu.title as unit_title,
        us.id as section_id,
        us.title as section_title,
        -- Convert next_due_date to timestamp for review_after
        CASE 
            WHEN smp.next_due_date IS NOT NULL THEN 
                smp.next_due_date::timestamp AT TIME ZONE 'UTC'
            ELSE 
                NULL::timestamp with time zone
        END as review_after,
        smp.difficulty::NUMERIC as proficiency_score
    FROM task_base tb
    JOIN unit_section us ON us.id = tb.section_id
    JOIN learning_unit lu ON lu.id = us.unit_id
    JOIN course_learning_unit_assignment cla ON cla.unit_id = lu.id
    LEFT JOIN student_mastery_progress smp ON 
        smp.student_id = v_user_id AND
        smp.task_id = tb.id  
    WHERE cla.course_id = p_course_id 
        AND tb.task_type = 'mastery_task'
    ORDER BY lu.title, us.order_in_unit, tb.order_in_section;
END;
$$;


ALTER FUNCTION public.get_mastery_tasks_for_course(p_session_id text, p_course_id uuid) OWNER TO postgres;

--
-- Name: get_mastery_tasks_for_section(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_mastery_tasks_for_section(p_session_id text, p_section_id uuid) RETURNS TABLE(id uuid, section_id uuid, instruction text, task_type text, order_in_section integer, created_at timestamp with time zone, assessment_criteria jsonb, solution_hints text)
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RAISE EXCEPTION 'Invalid session';
    END IF;

    -- Check authorization based on role
    IF v_user_role = 'teacher' THEN
        -- Teacher must own the learning unit
        IF NOT EXISTS (
            SELECT 1
            FROM unit_section s
            JOIN learning_unit lu ON lu.id = s.unit_id
            WHERE s.id = p_section_id AND lu.creator_id = v_user_id
        ) THEN
            RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
        END IF;
    ELSIF v_user_role = 'student' THEN
        -- Student must be enrolled in a course with this section published
        IF NOT EXISTS (
            SELECT 1
            FROM unit_section s
            JOIN course_unit_section_status cuss ON cuss.section_id = s.id
            JOIN course_students cs ON cs.course_id = cuss.course_id
            WHERE s.id = p_section_id
            AND cs.student_id = v_user_id
            AND cuss.is_published = TRUE
        ) THEN
            RAISE EXCEPTION 'Unauthorized: Section not accessible to student';
        END IF;
    ELSE
        RAISE EXCEPTION 'Invalid user role';
    END IF;

    -- Return mastery tasks for the section including solution_hints
    RETURN QUERY
    SELECT
        t.id,
        t.section_id,
        t.instruction,
        t.task_type,
        t.order_in_section,
        t.created_at,
        t.assessment_criteria,
        t.solution_hints  -- Added solution_hints
    FROM all_mastery_tasks t
    WHERE t.section_id = p_section_id
    ORDER BY t.order_in_section;
END;
$$;


ALTER FUNCTION public.get_mastery_tasks_for_section(p_session_id text, p_section_id uuid) OWNER TO postgres;

--
-- Name: FUNCTION get_mastery_tasks_for_section(p_session_id text, p_section_id uuid); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.get_mastery_tasks_for_section(p_session_id text, p_section_id uuid) IS 'Retrieves mastery tasks for a section with proper authorization checks, now including solution_hints';


--
-- Name: get_my_role(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_my_role() RETURNS public.user_role
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
  SELECT role
  FROM public.profiles
  WHERE id = auth.uid();
$$;


ALTER FUNCTION public.get_my_role() OWNER TO postgres;

--
-- Name: get_next_due_mastery_task(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_next_due_mastery_task(p_session_id text, p_student_id uuid) RETURNS TABLE(task_id uuid, title text, instruction text, section_title text, unit_title text, due_date timestamp with time zone, days_until_due integer)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RAISE EXCEPTION 'Invalid session';
    END IF;

    -- Permission check
    IF v_user_role = 'student' AND v_user_id != p_student_id THEN
        RAISE EXCEPTION 'Unauthorized: Students can only view their own tasks';
    END IF;

    RETURN QUERY
    WITH student_courses AS (
        SELECT DISTINCT cs.course_id
        FROM course_student cs 
        WHERE cs.student_id = p_student_id
    ),
    available_mastery_tasks AS (
        SELECT DISTINCT
            tb.id,
            tb.title,
            tb.instruction,
            us.title as section_title,
            lu.title as unit_title,
            ml.next_due as due_date,
            EXTRACT(days FROM (ml.next_due - NOW()))::INT as days_until_due
        FROM task_base tb
        JOIN mastery_tasks mt ON mt.task_id = tb.id
        JOIN unit_section us ON us.id = tb.section_id
        JOIN learning_unit lu ON lu.id = us.unit_id  -- FIXED: was us.learning_unit_id
        JOIN course_learning_unit_assignment cua ON cua.unit_id = lu.id  -- FIXED: was cua.learning_unit_id
        JOIN student_courses sc ON sc.course_id = cua.course_id
        LEFT JOIN mastery_log ml ON ml.student_id = p_student_id AND ml.task_id = tb.id
        WHERE (ml.next_due IS NULL OR ml.next_due <= NOW())
        ORDER BY COALESCE(ml.next_due, NOW()) ASC
    )
    SELECT 
        amt.id as task_id,
        amt.title,
        amt.instruction,
        amt.section_title,
        amt.unit_title,
        amt.due_date,
        amt.days_until_due
    FROM available_mastery_tasks amt
    LIMIT 1;
END;
$$;


ALTER FUNCTION public.get_next_due_mastery_task(p_session_id text, p_student_id uuid) OWNER TO postgres;

--
-- Name: get_next_due_mastery_task(text, uuid, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_next_due_mastery_task(p_session_id text, p_student_id uuid, p_course_id uuid) RETURNS TABLE(task_id uuid, instruction text, difficulty_level integer, solution_hints text, section_id uuid, section_title text, unit_id uuid, unit_title text, total_attempts integer, correct_attempts integer, days_since_last_attempt integer, priority_score numeric)
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_auth_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_auth_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid OR v_auth_user_id IS NULL OR v_auth_user_id != p_student_id THEN
        RAISE EXCEPTION 'Unauthorized: Invalid session';
    END IF;

    -- Get next due mastery task using spaced repetition logic
    RETURN QUERY
    WITH course_mastery_tasks AS (
        -- Get all mastery tasks for the course
        SELECT
            t.id as task_id,
            t.section_id,
            s.title as section_title,
            s.unit_id,
            lu.title as unit_title,
            mt.difficulty_level,
            t.solution_hints,
            t.instruction
        FROM task_base t
        JOIN mastery_tasks mt ON mt.task_id = t.id
        JOIN unit_section s ON s.id = t.section_id
        JOIN learning_unit lu ON lu.id = s.unit_id
        JOIN course_learning_unit_assignment cua ON cua.unit_id = lu.id
        WHERE cua.course_id = p_course_id
    ),
    task_submission_stats AS (
        -- Get submission statistics for each task
        SELECT
            cmt.task_id,
            COUNT(sub.id) as total_attempts,
            COUNT(CASE WHEN sub.is_correct THEN 1 END) as correct_attempts,
            MAX(sub.submitted_at) as last_attempt,
            -- Calculate days since last attempt, default to very high if never attempted
            COALESCE(
                EXTRACT(EPOCH FROM (NOW() - MAX(sub.submitted_at))) / 86400.0,
                999999
            )::INTEGER as days_since_last
        FROM course_mastery_tasks cmt
        LEFT JOIN submission sub ON sub.task_id = cmt.task_id 
            AND sub.student_id = p_student_id
        GROUP BY cmt.task_id
    ),
    prioritized_tasks AS (
        -- Calculate priority score for each task
        SELECT
            cmt.*,
            tss.total_attempts::INTEGER,
            tss.correct_attempts::INTEGER,
            tss.days_since_last,
            -- Priority score calculation
            CASE
                -- Never attempted: highest priority (1000 + difficulty bonus)
                WHEN tss.total_attempts = 0 THEN 1000.0 + (cmt.difficulty_level * 10.0)
                -- Tasks with no correct attempts: high priority based on days
                WHEN tss.correct_attempts = 0 THEN 
                    500.0 + (tss.days_since_last * 10.0) + (cmt.difficulty_level * 5.0)
                -- Tasks with correct attempts: spaced repetition
                ELSE 
                    -- Base score from days since last attempt
                    (tss.days_since_last * 5.0)
                    -- Adjust by success rate (lower success = higher priority)
                    * (2.0 - (tss.correct_attempts::NUMERIC / NULLIF(tss.total_attempts, 0)::NUMERIC))
                    -- Adjust by difficulty
                    * (1.0 + (cmt.difficulty_level * 0.1))
            END as priority_score
        FROM course_mastery_tasks cmt
        JOIN task_submission_stats tss ON tss.task_id = cmt.task_id
    ),
    filtered_tasks AS (
        -- Filter out tasks that are too recent or have been mastered
        SELECT *
        FROM prioritized_tasks pt
        WHERE 
            -- Include if never attempted
            pt.total_attempts = 0
            -- Or if no correct attempts yet
            OR pt.correct_attempts = 0
            -- Or if enough time has passed based on spaced repetition
            OR pt.days_since_last >= CASE
                WHEN pt.correct_attempts = 1 THEN 1   -- 1 day after first correct
                WHEN pt.correct_attempts = 2 THEN 3   -- 3 days after second correct
                WHEN pt.correct_attempts = 3 THEN 7   -- 7 days after third correct
                WHEN pt.correct_attempts = 4 THEN 14  -- 14 days after fourth correct
                ELSE 30  -- 30 days for well-mastered tasks
            END
    )
    -- Return the highest priority task
    SELECT
        ft.task_id,
        ft.instruction,
        ft.difficulty_level,
        ft.solution_hints,
        ft.section_id,
        ft.section_title,
        ft.unit_id,
        ft.unit_title,
        ft.total_attempts,
        ft.correct_attempts,
        ft.days_since_last as days_since_last_attempt,
        ROUND(ft.priority_score, 2) as priority_score
    FROM filtered_tasks ft
    ORDER BY ft.priority_score DESC
    LIMIT 1;
END;
$$;


ALTER FUNCTION public.get_next_due_mastery_task(p_session_id text, p_student_id uuid, p_course_id uuid) OWNER TO postgres;

--
-- Name: FUNCTION get_next_due_mastery_task(p_session_id text, p_student_id uuid, p_course_id uuid); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.get_next_due_mastery_task(p_session_id text, p_student_id uuid, p_course_id uuid) IS 'Returns next mastery task. No longer uses redundant title column';


--
-- Name: get_next_feedback_submission(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_next_feedback_submission() RETURNS TABLE(id uuid, task_id uuid, student_id uuid, submission_data jsonb, retry_count integer)
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
    RETURN QUERY
    WITH next_submission AS (
        SELECT s.id
        FROM submission s
        WHERE s.feedback_status IN ('pending', 'retry')
        AND s.retry_count < 3
        AND (
            s.last_retry_at IS NULL 
            OR s.last_retry_at < NOW() - (s.retry_count * INTERVAL '5 minutes')
        )
        ORDER BY 
            CASE WHEN s.feedback_status = 'pending' THEN 0 ELSE 1 END, -- pending first
            s.created_at ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED -- Prevent race conditions
    )
    UPDATE submission s
    SET 
        feedback_status = 'processing',
        processing_started_at = NOW()
    FROM next_submission ns
    WHERE s.id = ns.id
    RETURNING 
        s.id,
        s.task_id,
        s.student_id,
        s.submission_data,
        s.retry_count;
END;
$$;


ALTER FUNCTION public.get_next_feedback_submission() OWNER TO postgres;

--
-- Name: get_next_mastery_task_or_unviewed_feedback(text, uuid, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_next_mastery_task_or_unviewed_feedback(p_session_id text, p_student_id uuid, p_course_id uuid) RETURNS json
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_submission_id UUID;
    v_task_id UUID;
    v_result JSON;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RAISE EXCEPTION 'Invalid session';
    END IF;

    -- Verify that the user is a student and matches the requested student_id
    IF v_user_role != 'student' OR v_user_id != p_student_id THEN
        RAISE EXCEPTION 'Unauthorized: Must be the student';
    END IF;

    -- Verify student is enrolled in the course
    IF NOT EXISTS (
        SELECT 1 FROM course_student 
        WHERE student_id = v_user_id 
        AND course_id = p_course_id
    ) THEN
        RAISE EXCEPTION 'Student not enrolled in course';
    END IF;

    -- Step 1: Check for unviewed feedback
    -- Find the most recent submission with feedback that hasn't been viewed
    SELECT s.id, s.task_id
    INTO v_submission_id, v_task_id
    FROM submission s
    JOIN all_mastery_tasks amt ON amt.id = s.task_id
    JOIN unit_section us ON us.id = amt.section_id
    JOIN learning_unit lu ON lu.id = us.unit_id
    JOIN course_learning_unit_assignment cua ON cua.unit_id = lu.id
    WHERE s.student_id = p_student_id
    AND cua.course_id = p_course_id
    AND s.feedback_viewed_at IS NULL
    AND (s.ai_feedback IS NOT NULL OR s.teacher_override_feedback IS NOT NULL)
    ORDER BY s.submitted_at DESC
    LIMIT 1;

    -- If unviewed feedback exists, return it with task details and mastery progress
    IF v_submission_id IS NOT NULL THEN
        SELECT json_build_object(
            'type', 'feedback',
            'submission_id', s.id,
            'task_id', s.task_id,
            'task_title', t.instruction,  -- FIX: use instruction instead of title
            'task_instruction', t.instruction,
            'section_id', amt.section_id,
            'section_title', us.title,
            'unit_id', us.unit_id,
            'unit_title', lu.title,
            'difficulty_level', amt.difficulty_level,
            'solution_hints', t.solution_hints,
            'submitted_at', s.submitted_at,
            'is_correct', s.is_correct,
            'submission_text', s.submission_text,
            'ai_feedback', s.ai_feedback,
            'ai_grade', s.ai_grade,
            'teacher_feedback', s.teacher_override_feedback,
            'teacher_grade', s.teacher_override_grade,
            'feed_back_text', s.feed_back_text,
            'feed_forward_text', s.feed_forward_text,
            -- Include mastery_progress
            'mastery_progress', CASE 
                WHEN smp.id IS NOT NULL THEN
                    json_build_object(
                        'stability', smp.stability,
                        'difficulty', smp.difficulty,
                        'next_review_date', smp.next_due_date,
                        'last_review_date', smp.last_reviewed_at,
                        'total_reviews', (SELECT COUNT(*) FROM submission WHERE task_id = s.task_id AND student_id = p_student_id),
                        'successful_reviews', (SELECT COUNT(*) FROM submission WHERE task_id = s.task_id AND student_id = p_student_id AND is_correct = true)
                    )
                ELSE NULL
            END
        ) INTO v_result
        FROM submission s
        JOIN all_mastery_tasks amt ON amt.id = s.task_id
        JOIN task_base t ON t.id = amt.id
        JOIN unit_section us ON us.id = amt.section_id
        JOIN learning_unit lu ON lu.id = us.unit_id
        LEFT JOIN student_mastery_progress smp ON smp.task_id = s.task_id AND smp.student_id = p_student_id
        WHERE s.id = v_submission_id;
        
        RETURN v_result;
    END IF;

    -- Step 2: If no unviewed feedback, get next due mastery task
    -- Calculate priority for all mastery tasks
    WITH student_progress AS (
        SELECT 
            amt.id as task_id,
            MAX(s.submitted_at) as last_submission,
            COUNT(CASE WHEN s.is_correct THEN 1 END) as correct_count,
            COUNT(s.id) as total_attempts,
            smp.next_due_date,
            smp.stability,
            smp.difficulty,
            smp.last_reviewed_at
        FROM all_mastery_tasks amt
        JOIN unit_section us ON us.id = amt.section_id
        JOIN learning_unit lu ON lu.id = us.unit_id
        JOIN course_learning_unit_assignment cua ON cua.unit_id = lu.id
        LEFT JOIN submission s ON s.task_id = amt.id AND s.student_id = p_student_id
        LEFT JOIN student_mastery_progress smp ON smp.task_id = amt.id AND smp.student_id = p_student_id
        WHERE cua.course_id = p_course_id
        GROUP BY amt.id, smp.next_due_date, smp.stability, smp.difficulty, smp.last_reviewed_at
    ),
    prioritized_tasks AS (
        SELECT 
            sp.task_id,
            sp.last_submission,
            sp.correct_count,
            sp.total_attempts,
            sp.next_due_date,
            sp.stability,
            sp.difficulty,
            sp.last_reviewed_at,
            -- Priority calculation (using DATE comparison for next_due_date)
            CASE
                -- Never attempted: highest priority
                WHEN sp.total_attempts = 0 THEN 1000
                -- Due for review (past next_due_date)
                WHEN sp.next_due_date IS NOT NULL AND sp.next_due_date <= CURRENT_DATE THEN 
                    500 + (CURRENT_DATE - sp.next_due_date)
                -- Has attempts but not yet due
                WHEN sp.next_due_date IS NOT NULL AND sp.next_due_date > CURRENT_DATE THEN
                    100 - (sp.next_due_date - CURRENT_DATE)
                -- Fallback for tasks with attempts but no review date
                ELSE 200
            END as priority_score
        FROM student_progress sp
    )
    SELECT json_build_object(
        'type', 'task',
        'task_id', amt.id,
        'task_title', t.instruction,  -- FIX: use instruction instead of title
        'task_instruction', t.instruction,
        'section_id', amt.section_id,
        'section_title', us.title,
        'unit_id', us.unit_id,
        'unit_title', lu.title,
        'difficulty_level', amt.difficulty_level,
        'solution_hints', t.solution_hints,
        'last_attempt', pt.last_submission,
        'correct_attempts', pt.correct_count,
        'total_attempts', pt.total_attempts,
        'next_review_date', pt.next_due_date,
        'priority_score', pt.priority_score,
        -- Include mastery_progress for proper display
        'mastery_progress', CASE 
            WHEN pt.stability IS NOT NULL THEN
                json_build_object(
                    'stability', pt.stability,
                    'difficulty', pt.difficulty,
                    'next_review_date', pt.next_due_date,
                    'last_review_date', pt.last_reviewed_at,
                    'total_reviews', pt.total_attempts,
                    'successful_reviews', pt.correct_count
                )
            ELSE NULL
        END
    ) INTO v_result
    FROM prioritized_tasks pt
    JOIN all_mastery_tasks amt ON amt.id = pt.task_id
    JOIN task_base t ON t.id = amt.id
    JOIN unit_section us ON us.id = amt.section_id
    JOIN learning_unit lu ON lu.id = us.unit_id
    ORDER BY pt.priority_score DESC
    LIMIT 1;

    -- If no tasks found (edge case), return null
    IF v_result IS NULL THEN
        RETURN json_build_object(
            'type', 'no_tasks',
            'message', 'Keine weiteren Aufgaben verfuegbar'
        );
    END IF;

    RETURN v_result;
END;
$$;


ALTER FUNCTION public.get_next_mastery_task_or_unviewed_feedback(p_session_id text, p_student_id uuid, p_course_id uuid) OWNER TO postgres;

--
-- Name: FUNCTION get_next_mastery_task_or_unviewed_feedback(p_session_id text, p_student_id uuid, p_course_id uuid); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.get_next_mastery_task_or_unviewed_feedback(p_session_id text, p_student_id uuid, p_course_id uuid) IS 'Returns either unviewed feedback (priority) or the next due mastery task for a student in a course. Fixed to use instruction instead of non-existent title column.';


--
-- Name: get_published_section_details_for_student(text, uuid, uuid, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_published_section_details_for_student(p_session_id text, p_course_id uuid, p_unit_id uuid, p_student_id uuid) RETURNS TABLE(section_id uuid, section_title text, section_description text, section_materials jsonb, order_in_unit integer, is_published boolean, tasks jsonb)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid THEN
        RAISE EXCEPTION 'Invalid session';
    END IF;
    
    -- For teacher, verify they own the course
    IF v_user_role = 'teacher' AND v_user_id != p_student_id THEN
        IF NOT EXISTS (
            SELECT 1 FROM course 
            WHERE id = p_course_id AND creator_id = v_user_id
        ) THEN
            RAISE EXCEPTION 'Unauthorized access to student data';
        END IF;
    -- For student, verify they can only access their own data
    ELSIF v_user_role = 'student' AND v_user_id != p_student_id THEN
        RAISE EXCEPTION 'Students can only access their own data';
    END IF;

    -- Complex query to get section details with tasks and submission status
    RETURN QUERY
    WITH published_sections AS (
        SELECT 
            s.id,
            s.title,
            NULL::TEXT as description,  -- unit_section table has no description column
            s.materials,
            s.order_in_unit,
            COALESCE(cuss.is_published, FALSE) as is_published
        FROM unit_section s
        LEFT JOIN course_unit_section_status cuss ON 
            cuss.section_id = s.id AND 
            cuss.course_id = p_course_id
        WHERE s.unit_id = p_unit_id
    ),
    section_tasks AS (
        SELECT 
            ps.id as section_id,
            jsonb_agg(
                jsonb_build_object(
                    'id', tb.id,  -- Changed from 'task_id' to 'id' for UI compatibility
                    'task_title', tb.instruction,
                    'instruction', tb.instruction,  -- Add instruction field for UI
                    'task_type', tb.task_type,
                    'order_in_section', tb.order_in_section,
                    'max_attempts', CASE 
                        WHEN tb.task_type = 'regular_task' THEN 3
                        ELSE NULL
                    END,
                    'has_submission', EXISTS(
                        SELECT 1 FROM submission sub
                        WHERE sub.task_id = tb.id 
                        AND sub.student_id = p_student_id
                    ),
                    'is_correct', (
                        SELECT is_correct
                        FROM submission sub
                        WHERE sub.task_id = tb.id 
                        AND sub.student_id = p_student_id
                        ORDER BY sub.submitted_at DESC
                        LIMIT 1
                    ),
                    'remaining_attempts', CASE 
                        WHEN tb.task_type = 'regular_task' THEN 
                            3 - COALESCE((
                                SELECT COUNT(*)
                                FROM submission sub
                                WHERE sub.task_id = tb.id 
                                AND sub.student_id = p_student_id
                            ), 0)
                        ELSE NULL
                    END
                ) ORDER BY tb.order_in_section
            ) as tasks
        FROM published_sections ps
        JOIN task_base tb ON tb.section_id = ps.id
        WHERE ps.is_published = TRUE
        GROUP BY ps.id
    )
    SELECT 
        ps.id as section_id,
        ps.title as section_title,
        ps.description as section_description,  -- Will be NULL
        ps.materials as section_materials,
        ps.order_in_unit,
        ps.is_published,
        COALESCE(st.tasks, '[]'::jsonb) as tasks
    FROM published_sections ps
    LEFT JOIN section_tasks st ON st.section_id = ps.id
    WHERE ps.is_published = TRUE
    ORDER BY ps.order_in_unit;
END;
$$;


ALTER FUNCTION public.get_published_section_details_for_student(p_session_id text, p_course_id uuid, p_unit_id uuid, p_student_id uuid) OWNER TO postgres;

--
-- Name: get_regular_tasks_for_section(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_regular_tasks_for_section(p_session_id text, p_section_id uuid) RETURNS TABLE(id uuid, section_id uuid, instruction text, task_type text, order_in_section integer, created_at timestamp with time zone, prompt text, max_attempts integer, grading_criteria text[], solution_hints text)
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RAISE EXCEPTION 'Invalid session';
    END IF;

    -- Check authorization based on role
    IF v_user_role = 'teacher' THEN
        -- Teacher must own the learning unit
        IF NOT EXISTS (
            SELECT 1
            FROM unit_section s
            JOIN learning_unit lu ON lu.id = s.unit_id
            WHERE s.id = p_section_id AND lu.creator_id = v_user_id
        ) THEN
            RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
        END IF;
    ELSIF v_user_role = 'student' THEN
        -- Student must be enrolled in a course with this section published
        IF NOT EXISTS (
            SELECT 1
            FROM unit_section s
            JOIN course_unit_section_status cuss ON cuss.section_id = s.id
            JOIN course_students cs ON cs.course_id = cuss.course_id
            WHERE s.id = p_section_id
            AND cs.student_id = v_user_id
            AND cuss.is_published = TRUE
        ) THEN
            RAISE EXCEPTION 'Unauthorized: Section not accessible to student';
        END IF;
    ELSE
        RAISE EXCEPTION 'Invalid user role';
    END IF;

    -- Return regular tasks for the section including solution_hints
    RETURN QUERY
    SELECT
        t.id,
        t.section_id,
        t.instruction,
        t.task_type,
        t.order_in_section,
        t.created_at,
        t.prompt,
        t.max_attempts,
        t.grading_criteria,
        t.solution_hints  -- Added solution_hints
    FROM all_regular_tasks t
    WHERE t.section_id = p_section_id
    ORDER BY t.order_in_section;
END;
$$;


ALTER FUNCTION public.get_regular_tasks_for_section(p_session_id text, p_section_id uuid) OWNER TO postgres;

--
-- Name: FUNCTION get_regular_tasks_for_section(p_session_id text, p_section_id uuid); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.get_regular_tasks_for_section(p_session_id text, p_section_id uuid) IS 'Retrieves regular tasks for a section with proper authorization checks, now including solution_hints';


--
-- Name: get_remaining_attempts(text, uuid, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_remaining_attempts(p_session_id text, p_student_id uuid, p_task_id uuid) RETURNS TABLE(remaining_attempts integer, max_attempts integer)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_max_attempts INT;
    v_attempt_count INT;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        -- Return NULL values for invalid session
        RETURN QUERY SELECT NULL::INT, NULL::INT;
        RETURN;
    END IF;

    -- Check permissions
    IF v_user_role = 'student' AND v_user_id != p_student_id THEN
        -- Return NULL values for unauthorized access
        RETURN QUERY SELECT NULL::INT, NULL::INT;
        RETURN;
    END IF;

    -- Get max attempts for regular task
    SELECT t.max_attempts
    INTO v_max_attempts
    FROM all_regular_tasks t
    WHERE t.id = p_task_id;

    IF NOT FOUND THEN
        -- Check if it's a mastery task (unlimited attempts)
        IF EXISTS (SELECT 1 FROM all_mastery_tasks WHERE id = p_task_id) THEN
            -- Mastery tasks have unlimited attempts - return special values
            RETURN QUERY SELECT NULL::INT as remaining_attempts, NULL::INT as max_attempts;
        ELSE
            -- Task not found - return zeros
            RETURN QUERY SELECT 0::INT as remaining_attempts, 0::INT as max_attempts;
        END IF;
        RETURN;
    END IF;

    -- Count existing attempts
    SELECT COUNT(*)::INT
    INTO v_attempt_count
    FROM submission s
    WHERE s.student_id = p_student_id AND s.task_id = p_task_id;

    -- Return both remaining attempts and max attempts
    RETURN QUERY SELECT 
        GREATEST(0, v_max_attempts - v_attempt_count)::INT as remaining_attempts,
        v_max_attempts as max_attempts;
END;
$$;


ALTER FUNCTION public.get_remaining_attempts(p_session_id text, p_student_id uuid, p_task_id uuid) OWNER TO postgres;

--
-- Name: FUNCTION get_remaining_attempts(p_session_id text, p_student_id uuid, p_task_id uuid); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.get_remaining_attempts(p_session_id text, p_student_id uuid, p_task_id uuid) IS 'Returns remaining attempts and max attempts for a student on a specific task. Returns NULL values for mastery tasks (unlimited attempts).';


--
-- Name: get_section_statuses_for_unit_in_course(text, uuid, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_section_statuses_for_unit_in_course(p_session_id text, p_unit_id uuid, p_course_id uuid) RETURNS TABLE(section_id uuid, section_title text, order_in_unit integer, is_published boolean, task_count integer, published_at timestamp with time zone)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can view section statuses';
    END IF;

    -- Check teacher authorization
    IF NOT EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Get section statuses
    RETURN QUERY
    SELECT 
        s.id as section_id,
        s.title as section_title,
        s.order_in_unit,
        COALESCE(cuss.is_published, FALSE) as is_published,
        COUNT(DISTINCT t.id)::INT as task_count,
        cuss.published_at
    FROM unit_section s
    LEFT JOIN course_unit_section_status cuss ON 
        cuss.section_id = s.id AND 
        cuss.course_id = p_course_id
    LEFT JOIN task_base t ON t.section_id = s.id
    WHERE s.unit_id = p_unit_id  -- FIX: learning_unit_id -> unit_id
    GROUP BY s.id, s.title, s.order_in_unit, cuss.is_published, cuss.published_at
    ORDER BY s.order_in_unit;
END;
$$;


ALTER FUNCTION public.get_section_statuses_for_unit_in_course(p_session_id text, p_unit_id uuid, p_course_id uuid) OWNER TO postgres;

--
-- Name: get_section_tasks(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_section_tasks(p_session_id text, p_section_id uuid) RETURNS TABLE(task_id uuid, instruction text, task_type text, order_in_section integer, created_at timestamp with time zone)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid THEN
        RAISE EXCEPTION 'Invalid session';
    END IF;
    
    -- Only teachers need explicit authorization check
    IF v_user_role = 'teacher' THEN
        IF NOT EXISTS (
            SELECT 1 FROM unit_section us
            JOIN learning_unit lu ON us.unit_id = lu.id
            WHERE us.id = p_section_id AND lu.creator_id = v_user_id
        ) THEN
            RAISE EXCEPTION 'Unauthorized access to section';
        END IF;
    END IF;
    
    -- Return tasks for the section
    RETURN QUERY
    SELECT 
        tb.id::UUID as task_id,  -- Explicit cast to UUID
        tb.instruction,
        tb.task_type,
        tb.order_in_section,
        tb.created_at
    FROM task_base tb
    WHERE tb.section_id = p_section_id
    ORDER BY tb.order_in_section;
END;
$$;


ALTER FUNCTION public.get_section_tasks(p_session_id text, p_section_id uuid) OWNER TO postgres;

--
-- Name: get_section_tasks(text, uuid, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_section_tasks(p_session_id text, p_section_id uuid, p_course_id uuid) RETURNS TABLE(id uuid, title text, instruction text, task_type text, order_in_section integer, is_mastery boolean, max_attempts integer, difficulty_level integer, solution_hints text)
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_auth_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_auth_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid OR v_auth_user_id IS NULL THEN
        RAISE EXCEPTION 'Unauthorized: Invalid session';
    END IF;

    -- Return task list
    RETURN QUERY
    SELECT 
        t.id,
        t.instruction::TEXT as title,  -- Return instruction as title for backward compatibility
        t.instruction,
        t.task_type,
        t.order_in_section,
        CASE WHEN mt.task_id IS NOT NULL THEN true ELSE false END as is_mastery,
        rt.max_attempts::INTEGER,
        mt.difficulty_level,
        t.solution_hints
    FROM task_base t
    LEFT JOIN regular_tasks rt ON rt.task_id = t.id
    LEFT JOIN mastery_tasks mt ON mt.task_id = t.id
    WHERE t.section_id = p_section_id
    ORDER BY t.order_in_section;
END;
$$;


ALTER FUNCTION public.get_section_tasks(p_session_id text, p_section_id uuid, p_course_id uuid) OWNER TO postgres;

--
-- Name: get_session(character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_session(p_session_id character varying) RETURNS TABLE(id uuid, session_id character varying, user_id uuid, user_email text, user_role text, data jsonb, expires_at timestamp with time zone, last_activity timestamp with time zone, created_at timestamp with time zone, ip_address inet, user_agent text)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'extensions'
    AS $$
BEGIN
    -- Update last_activity if session exists and not expired
    UPDATE auth_sessions s
    SET last_activity = NOW()
    WHERE s.session_id = p_session_id
      AND s.expires_at > NOW();
    
    -- Return session data
    RETURN QUERY
    SELECT 
        s.id,
        s.session_id,
        s.user_id,
        s.user_email,
        s.user_role,
        s.data,
        s.expires_at,
        s.last_activity,
        s.created_at,
        s.ip_address,
        s.user_agent
    FROM auth_sessions s
    WHERE s.session_id = p_session_id
      AND s.expires_at > NOW();
END;
$$;


ALTER FUNCTION public.get_session(p_session_id character varying) OWNER TO postgres;

--
-- Name: FUNCTION get_session(p_session_id character varying); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.get_session(p_session_id character varying) IS 'Retrieves session data and updates last activity timestamp';


--
-- Name: get_session_with_activity_update(character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_session_with_activity_update(p_session_id character varying) RETURNS TABLE(id uuid, session_id character varying, user_id uuid, user_email text, user_role text, data jsonb, expires_at timestamp with time zone, last_activity timestamp with time zone, created_at timestamp with time zone, ip_address inet, user_agent text)
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
    -- Update last_activity timestamp and extend expiration
    UPDATE public.auth_sessions
    SET 
        last_activity = NOW(),
        expires_at = GREATEST(expires_at, NOW() + INTERVAL '90 minutes')
    WHERE auth_sessions.session_id = p_session_id
    AND expires_at > NOW()
    AND last_activity > NOW() - INTERVAL '90 minutes';

    -- Return the updated session
    RETURN QUERY
    SELECT 
        s.id,
        s.session_id,
        s.user_id,
        s.user_email,
        s.user_role,
        s.data,
        s.expires_at,
        s.last_activity,
        s.created_at,
        s.ip_address,
        s.user_agent
    FROM public.auth_sessions s
    WHERE s.session_id = p_session_id
    AND s.expires_at > NOW()
    AND s.last_activity > NOW() - INTERVAL '90 minutes';
END;
$$;


ALTER FUNCTION public.get_session_with_activity_update(p_session_id character varying) OWNER TO postgres;

--
-- Name: FUNCTION get_session_with_activity_update(p_session_id character varying); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.get_session_with_activity_update(p_session_id character varying) IS 'Gets session and updates activity timestamp atomically with sliding window';


--
-- Name: get_student_courses(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_student_courses(p_session_id text, p_student_id uuid) RETURNS TABLE(id uuid, name text, creator_id uuid, created_at timestamp with time zone)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN;
    END IF;

    -- Benutzer kann nur eigene Kurse sehen, Lehrer kuennen alle sehen
    IF v_user_role = 'student' AND v_user_id != p_student_id THEN
        RETURN;
    END IF;

    -- Kurse des Studenten zurueckgeben
    RETURN QUERY
    SELECT
        c.id,
        c.name,
        c.creator_id,
        c.created_at
    FROM course c
    JOIN course_student cs ON cs.course_id = c.id
    WHERE cs.student_id = p_student_id
    ORDER BY c.created_at DESC;
END;
$$;


ALTER FUNCTION public.get_student_courses(p_session_id text, p_student_id uuid) OWNER TO postgres;

--
-- Name: get_students_in_course(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_students_in_course(p_session_id text, p_course_id uuid) RETURNS TABLE(id uuid, email text, display_name text, role text, course_id uuid)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN;
    END IF;

    -- Berechtigung pruefen: Lehrer des Kurses oder Student im Kurs
    IF v_user_role = 'teacher' THEN
        -- Lehrer muss Ersteller oder zugewiesen sein
        IF NOT EXISTS (
            SELECT 1 FROM course c
            WHERE c.id = p_course_id AND c.creator_id = v_user_id -- FIX: Use creator_id instead of created_by
        ) AND NOT EXISTS (
            SELECT 1 FROM course_teacher ct
            WHERE ct.course_id = p_course_id AND ct.teacher_id = v_user_id
        ) THEN
            RETURN;
        END IF;
    ELSIF v_user_role = 'student' THEN
        -- Student muss im Kurs sein
        IF NOT EXISTS (
            SELECT 1 FROM course_student cs
            WHERE cs.course_id = p_course_id AND cs.student_id = v_user_id
        ) THEN
            RETURN;
        END IF;
    END IF;

    -- Studenten im Kurs zurueckgeben
    RETURN QUERY
    SELECT
        p.id,
        p.email,
        COALESCE(NULLIF(p.full_name, ''), p.email) as display_name, -- FIX: Use full_name with email fallback
        p.role::text,
        cs.course_id
    FROM course_student cs
    JOIN profiles p ON p.id = cs.student_id
    WHERE cs.course_id = p_course_id
    ORDER BY COALESCE(NULLIF(p.full_name, ''), p.email), p.email; -- FIX: Order by computed display_name
END;
$$;


ALTER FUNCTION public.get_students_in_course(p_session_id text, p_course_id uuid) OWNER TO postgres;

--
-- Name: get_submission_by_id(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_submission_by_id(p_session_id text, p_submission_id uuid) RETURNS TABLE(id uuid, student_id uuid, task_id uuid, submission_text text, submission_data jsonb, is_correct boolean, submitted_at timestamp with time zone, attempt_number integer, feedback_status text, retry_count integer, processing_started_at timestamp with time zone, ai_feedback text, ai_feedback_generated_at timestamp with time zone, ai_insights jsonb, ai_criteria_analysis jsonb, feed_back_text text, feed_forward_text text, teacher_feedback text, teacher_feedback_generated_at timestamp with time zone, teacher_override_feedback text, teacher_override_grade text, override_grade boolean, feedback_viewed_at timestamp with time zone)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_student_id UUID;
BEGIN
    -- Get user from session with role
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid or expired session';
    END IF;
    
    -- Get student_id from submission
    SELECT s.student_id INTO v_student_id
    FROM submission s
    WHERE s.id = p_submission_id;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Submission not found';
    END IF;
    
    -- Authorization: student can view own submissions, teachers can view all
    IF v_user_id != v_student_id AND v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Not authorized to view this submission';
    END IF;
    
    -- Return submission details with correct column mappings
    RETURN QUERY
    SELECT 
        s.id,
        s.student_id,
        s.task_id,
        -- Handle submission_text
        COALESCE(s.submission_data::text, '') as submission_text,
        s.submission_data,
        s.is_correct,
        s.submitted_at,
        s.attempt_number,
        -- Feedback queue fields
        s.feedback_status,
        s.retry_count,
        s.processing_started_at,
        -- AI feedback fields with correct column names
        s.ai_feedback,
        s.feedback_generated_at as ai_feedback_generated_at,  -- Correct mapping!
        s.ai_insights,
        s.ai_insights as ai_criteria_analysis,  -- Same data, different alias
        s.feed_back_text,
        s.feed_forward_text,
        -- Teacher feedback fields
        s.teacher_override_feedback as teacher_feedback,
        s.grade_generated_at as teacher_feedback_generated_at,  -- Correct mapping!
        s.teacher_override_feedback,
        s.teacher_override_grade,
        CASE 
            WHEN s.teacher_override_grade IS NOT NULL THEN TRUE 
            ELSE FALSE 
        END as override_grade,
        s.feedback_viewed_at
    FROM submission s
    WHERE s.id = p_submission_id;
END;
$$;


ALTER FUNCTION public.get_submission_by_id(p_session_id text, p_submission_id uuid) OWNER TO postgres;

--
-- Name: FUNCTION get_submission_by_id(p_session_id text, p_submission_id uuid); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.get_submission_by_id(p_session_id text, p_submission_id uuid) IS 'Gets submission details with correct column mappings';


--
-- Name: get_submission_count(uuid, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_submission_count(p_student_id uuid, p_task_id uuid) RETURNS integer
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
  RETURN (
    SELECT COUNT(*)
    FROM submission
    WHERE student_id = p_student_id 
    AND task_id = p_task_id
  );
END;
$$;


ALTER FUNCTION public.get_submission_count(p_student_id uuid, p_task_id uuid) OWNER TO postgres;

--
-- Name: get_submission_for_task(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_submission_for_task(p_session_id text, p_task_id uuid) RETURNS TABLE(id uuid, task_id uuid, student_id uuid, submission_text text, submitted_at timestamp with time zone, ai_result jsonb, teacher_override_result text, is_viewed boolean, result_details jsonb)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_course_id UUID;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN;
    END IF;

    -- Get course_id for authorization check
    SELECT DISTINCT c.id INTO v_course_id
    FROM course c
    JOIN course_learning_unit_assignment clua ON clua.course_id = c.id
    JOIN unit_section us ON us.unit_id = clua.unit_id
    JOIN task_base tb ON tb.section_id = us.id
    WHERE tb.id = p_task_id;

    -- Authorization: Students see their own, teachers see all
    IF v_user_role = 'student' THEN
        -- Student can only see their own submission
        RETURN QUERY
        SELECT s.id, s.task_id, s.student_id, s.submission_text, 
               s.submitted_at, s.ai_result, s.teacher_override_result,
               s.is_viewed, s.result_details
        FROM submission s
        WHERE s.task_id = p_task_id
        AND s.student_id = v_user_id;
        
    ELSIF v_user_role = 'teacher' THEN
        -- Teacher authorization: must be course creator or assigned teacher
        IF EXISTS (
            SELECT 1 FROM course c 
            WHERE c.id = v_course_id AND c.creator_id = v_user_id  -- FIX: Use creator_id
        ) OR EXISTS (
            SELECT 1 FROM course_teacher ct 
            WHERE ct.course_id = v_course_id AND ct.teacher_id = v_user_id
        ) THEN
            RETURN QUERY
            SELECT s.id, s.task_id, s.student_id, s.submission_text, 
                   s.submitted_at, s.ai_result, s.teacher_override_result,
                   s.is_viewed, s.result_details
            FROM submission s
            WHERE s.task_id = p_task_id;
        END IF;
    END IF;
END;
$$;


ALTER FUNCTION public.get_submission_for_task(p_session_id text, p_task_id uuid) OWNER TO postgres;

--
-- Name: get_submission_for_task(text, uuid, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_submission_for_task(p_session_id text, p_student_id uuid, p_task_id uuid) RETURNS TABLE(id uuid, submission_data jsonb, is_correct boolean, submitted_at timestamp with time zone, ai_feedback text, grade text, ai_insights jsonb, feed_back_text text, feed_forward_text text, teacher_override_feedback text, teacher_override_grade text, feedback_status text, attempt_number integer)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RAISE EXCEPTION 'Invalid session';
    END IF;

    -- Permission check: students can only see their own submissions
    IF v_user_role = 'student' AND v_user_id != p_student_id THEN
        RAISE EXCEPTION 'Unauthorized: Students can only view their own submissions';
    END IF;

    -- Return the latest submission with all feedback fields
    RETURN QUERY
    SELECT 
        s.id,
        s.submission_data,
        s.is_correct,
        s.submitted_at,
        s.ai_feedback,
        COALESCE(s.teacher_override_grade, s.ai_grade) as grade,
        -- Additional feedback fields:
        s.ai_insights,
        s.feed_back_text,
        s.feed_forward_text,
        s.teacher_override_feedback,
        s.teacher_override_grade,
        s.feedback_status,
        s.attempt_number
    FROM submission s
    WHERE s.student_id = p_student_id 
    AND s.task_id = p_task_id
    ORDER BY s.submitted_at DESC
    LIMIT 1;
END;
$$;


ALTER FUNCTION public.get_submission_for_task(p_session_id text, p_student_id uuid, p_task_id uuid) OWNER TO postgres;

--
-- Name: FUNCTION get_submission_for_task(p_session_id text, p_student_id uuid, p_task_id uuid); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.get_submission_for_task(p_session_id text, p_student_id uuid, p_task_id uuid) IS 'Gets the latest submission for a student-task pair with all feedback fields including ai_insights, structured feedback, and teacher overrides';


--
-- Name: get_submission_history(text, uuid, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_submission_history(p_session_id text, p_student_id uuid, p_task_id uuid) RETURNS TABLE(id uuid, student_id uuid, task_id uuid, submission_data jsonb, submission_text text, is_correct boolean, created_at timestamp with time zone, submitted_at timestamp with time zone, ai_feedback text, ai_feedback_generated_at timestamp with time zone, teacher_feedback text, teacher_feedback_generated_at timestamp with time zone, override_grade boolean, feedback_viewed_at timestamp with time zone, attempt_number integer, feedback_status text, ai_grade text, teacher_override_feedback text, teacher_override_grade text, feed_back_text text, feed_forward_text text)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN;
    END IF;

    RETURN QUERY
    SELECT
        s.id,
        s.student_id,
        s.task_id,
        s.submission_data,
        s.submission_data::TEXT as submission_text,  -- For backwards compatibility
        s.is_correct,
        s.submitted_at as created_at,  -- Map to created_at for UI
        s.submitted_at,
        s.ai_feedback,
        s.feedback_generated_at as ai_feedback_generated_at,
        s.teacher_override_feedback as teacher_feedback,
        NULL::TIMESTAMPTZ as teacher_feedback_generated_at,  -- Column doesn't exist
        CASE WHEN s.teacher_override_grade IS NOT NULL THEN true ELSE false END as override_grade,
        s.feedback_viewed_at,
        s.attempt_number,  -- Include attempt_number!
        s.feedback_status,
        s.ai_grade,
        s.teacher_override_feedback,
        s.teacher_override_grade,
        s.feed_back_text,
        s.feed_forward_text
    FROM submission s
    WHERE s.student_id = p_student_id 
      AND s.task_id = p_task_id
      AND (
        -- Students can see their own history
        (v_user_role = 'student' AND s.student_id = v_user_id)
        OR
        -- Teachers can see history for tasks in their units  
        (v_user_role = 'teacher' AND EXISTS (
            SELECT 1
            FROM task_base tb
            JOIN unit_section us ON tb.section_id = us.id
            JOIN learning_unit lu ON us.unit_id = lu.id
            WHERE tb.id = s.task_id 
              AND lu.creator_id = v_user_id
        ))
      )
    ORDER BY s.attempt_number;  -- Sort by attempt number
END;
$$;


ALTER FUNCTION public.get_submission_history(p_session_id text, p_student_id uuid, p_task_id uuid) OWNER TO postgres;

--
-- Name: get_submission_queue_position(uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_submission_queue_position(p_submission_id uuid) RETURNS integer
    LANGUAGE plpgsql STABLE
    AS $$
DECLARE
    v_position INTEGER;
    v_created_at TIMESTAMP;
    v_status TEXT;
BEGIN
    -- Get submission details
    SELECT created_at, feedback_status INTO v_created_at, v_status
    FROM submission
    WHERE id = p_submission_id;
    
    IF NOT FOUND OR v_status NOT IN ('pending', 'retry', 'processing') THEN
        RETURN NULL;
    END IF;
    
    -- Count submissions ahead in queue
    SELECT COUNT(*) + 1 INTO v_position
    FROM submission
    WHERE feedback_status IN ('pending', 'retry', 'processing')
    AND created_at < v_created_at
    AND retry_count < 3;
    
    RETURN v_position;
END;
$$;


ALTER FUNCTION public.get_submission_queue_position(p_submission_id uuid) OWNER TO postgres;

--
-- Name: get_submission_status_matrix(text, uuid, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_submission_status_matrix(p_session_id text, p_unit_id uuid, p_course_id uuid) RETURNS TABLE(student_id uuid, student_name text, task_id uuid, task_title text, section_id uuid, section_title text, order_in_section integer, order_in_unit integer, has_submission boolean, is_correct boolean, submitted_at timestamp with time zone)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can view submission matrix';
    END IF;

    -- Check teacher authorization
    IF NOT EXISTS (
        SELECT 1 FROM learning_unit lu
        WHERE lu.id = p_unit_id AND lu.creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own this learning unit';
    END IF;

    -- Get submission status matrix
    RETURN QUERY
    WITH enrolled_students AS (
        SELECT DISTINCT cs.student_id, p.full_name as student_name  -- FIXED: was p.name
        FROM course_student cs
        JOIN profiles p ON p.id = cs.student_id
        WHERE cs.course_id = p_course_id
    ),
    unit_tasks AS (
        SELECT 
            t.id as task_id,
            t.title as task_title,
            t.section_id,
            s.title as section_title,
            rt.order_in_section,
            s.order_in_unit
        FROM task_base t
        JOIN unit_section s ON s.id = t.section_id
        JOIN regular_tasks rt ON rt.task_id = t.id
        WHERE s.unit_id = p_unit_id
    ),
    submission_status AS (
        SELECT 
            es.student_id,
            ut.task_id,
            COUNT(sub.id) > 0 as has_submission,
            BOOL_OR(sub.is_correct) as is_correct,
            MAX(sub.submitted_at) as submitted_at
        FROM enrolled_students es
        CROSS JOIN unit_tasks ut
        LEFT JOIN submission sub ON 
            sub.student_id = es.student_id AND 
            sub.task_id = ut.task_id
        GROUP BY es.student_id, ut.task_id
    )
    SELECT 
        es.student_id,
        es.student_name,
        ut.task_id,
        ut.task_title,
        ut.section_id,
        ut.section_title,
        ut.order_in_section,
        ut.order_in_unit,
        ss.has_submission,
        ss.is_correct,
        ss.submitted_at
    FROM enrolled_students es
    CROSS JOIN unit_tasks ut
    LEFT JOIN submission_status ss ON 
        ss.student_id = es.student_id AND 
        ss.task_id = ut.task_id
    ORDER BY es.student_name, ut.order_in_unit, ut.order_in_section;
END;
$$;


ALTER FUNCTION public.get_submission_status_matrix(p_session_id text, p_unit_id uuid, p_course_id uuid) OWNER TO postgres;

--
-- Name: get_submissions_for_course_and_unit(text, uuid, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_submissions_for_course_and_unit(p_session_id text, p_course_id uuid, p_unit_id uuid) RETURNS TABLE(student_id uuid, student_name text, section_id uuid, section_title text, task_id uuid, task_title text, task_type text, submission_id uuid, is_correct boolean, submitted_at timestamp with time zone, ai_feedback text, teacher_feedback text, teacher_override boolean)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid THEN
        RAISE EXCEPTION 'Invalid session';
    END IF;
    
    -- Check authorization
    IF v_user_role = 'teacher' THEN
        -- Teacher must be course creator
        IF NOT EXISTS (
            SELECT 1 FROM course 
            WHERE id = p_course_id AND creator_id = v_user_id
        ) THEN
            RAISE EXCEPTION 'Unauthorized access to course';
        END IF;
    ELSE
        RAISE EXCEPTION 'Only teachers can access all submissions';
    END IF;
    
    -- Get all submissions for the unit and course
    RETURN QUERY
    WITH course_students AS (
        SELECT 
            cs.student_id,
            COALESCE(p.full_name, u.email::text) as student_name
        FROM course_student cs
        JOIN auth.users u ON u.id = cs.student_id
        LEFT JOIN profiles p ON p.id = cs.student_id
        WHERE cs.course_id = p_course_id
    ),
    unit_tasks AS (
        SELECT 
            tb.id as task_id,
            tb.instruction as task_title,
            tb.task_type,
            tb.section_id,
            s.title as section_title
        FROM task_base tb
        JOIN unit_section s ON s.id = tb.section_id
        WHERE s.unit_id = p_unit_id
    )
    SELECT 
        cs.student_id,
        cs.student_name,
        ut.section_id,
        ut.section_title,
        ut.task_id,
        ut.task_title,
        ut.task_type,
        sub.id as submission_id,
        sub.is_correct,
        sub.submitted_at,  -- Already correct column name
        sub.ai_feedback,
        sub.teacher_override_feedback as teacher_feedback,  -- Map to correct column
        CASE WHEN sub.teacher_override_grade IS NOT NULL THEN TRUE ELSE FALSE END as teacher_override  -- Derive from grade
    FROM course_students cs
    CROSS JOIN unit_tasks ut
    LEFT JOIN submission sub ON 
        sub.student_id = cs.student_id AND 
        sub.task_id = ut.task_id
    ORDER BY cs.student_name, ut.section_id, ut.task_id, sub.submitted_at DESC;
END;
$$;


ALTER FUNCTION public.get_submissions_for_course_and_unit(p_session_id text, p_course_id uuid, p_unit_id uuid) OWNER TO postgres;

--
-- Name: get_task_by_id(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_task_by_id(p_session_id text, p_task_id uuid) RETURNS json
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_user_id uuid;
    v_user_role text;
    v_is_valid boolean;
    v_result json;
BEGIN
    -- Session validation using the standard function
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid or expired session';
    END IF;

    -- First check regular tasks
    SELECT json_build_object(
        'id', tb.id,
        'section_id', tb.section_id,
        'instruction', tb.instruction,
        'task_type', tb.task_type,
        'order_in_section', COALESCE(rt.order_in_section, tb.order_in_section),
        'max_attempts', rt.max_attempts,
        'assessment_criteria',
            CASE
                WHEN tb.assessment_criteria IS NOT NULL
                THEN ARRAY(SELECT jsonb_array_elements_text(tb.assessment_criteria))
                ELSE ARRAY[]::TEXT[]
            END,
        'solution_hints', COALESCE(rt.solution_hints, tb.solution_hints),
        'is_mastery', false,
        'type', 'regular'
    ) INTO v_result
    FROM task_base tb
    JOIN regular_tasks rt ON tb.id = rt.task_id
    WHERE tb.id = p_task_id;

    -- If found in regular tasks, return it
    IF v_result IS NOT NULL THEN
        RETURN v_result;
    END IF;

    -- Check mastery tasks
    SELECT json_build_object(
        'id', tb.id,
        'section_id', tb.section_id,
        'instruction', tb.instruction,
        'task_type', tb.task_type,
        'order_in_section', tb.order_in_section,
        'assessment_criteria',
            CASE
                WHEN tb.assessment_criteria IS NOT NULL
                THEN ARRAY(SELECT jsonb_array_elements_text(tb.assessment_criteria))
                ELSE ARRAY[]::TEXT[]
            END,
        'solution_hints', COALESCE(mt.solution_hints, tb.solution_hints),
        'difficulty_level', mt.difficulty_level,
        'is_mastery', true,
        'type', 'mastery'
    ) INTO v_result
    FROM task_base tb
    JOIN mastery_tasks mt ON tb.id = mt.task_id
    WHERE tb.id = p_task_id;

    -- If found in mastery tasks, return it
    IF v_result IS NOT NULL THEN
        RETURN v_result;
    END IF;

    -- Task not found
    RAISE EXCEPTION 'Task with ID % not found', p_task_id;
END;
$$;


ALTER FUNCTION public.get_task_by_id(p_session_id text, p_task_id uuid) OWNER TO postgres;

--
-- Name: FUNCTION get_task_by_id(p_session_id text, p_task_id uuid); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.get_task_by_id(p_session_id text, p_task_id uuid) IS 'Retrieves a single task by ID. Uses task_base for main data, with specific fields from regular_tasks or mastery_tasks.';


--
-- Name: get_task_details(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_task_details(p_session_id text, p_task_id uuid) RETURNS TABLE(id uuid, instruction text, task_type text, is_mastery boolean, max_attempts integer, difficulty_level integer, solution_hints text)
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_auth_user_id UUID;
    v_user_role user_role;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, CAST(user_role AS user_role), is_valid
    INTO v_auth_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid OR v_auth_user_id IS NULL THEN
        RAISE EXCEPTION 'Unauthorized: Invalid session';
    END IF;

    -- Return task details
    RETURN QUERY
    SELECT
        t.id,
        t.instruction,
        t.task_type,
        CASE WHEN mt.task_id IS NOT NULL THEN true ELSE false END as is_mastery,
        rt.max_attempts,
        mt.difficulty_level,
        t.solution_hints
    FROM task_base t
    LEFT JOIN regular_tasks rt ON rt.task_id = t.id
    LEFT JOIN mastery_tasks mt ON mt.task_id = t.id
    WHERE t.id = p_task_id;

    -- Additional authorization check based on role
    IF v_user_role = 'teacher' THEN
        -- Teachers must own the unit
        IF NOT EXISTS (
            SELECT 1
            FROM task_base t
            JOIN unit_section s ON s.id = t.section_id
            JOIN learning_unit lu ON lu.id = s.unit_id
            WHERE t.id = p_task_id AND lu.creator_id = v_auth_user_id
        ) THEN
            RAISE EXCEPTION 'Unauthorized: Not the owner of this task';
        END IF;
    ELSIF v_user_role = 'student' THEN
        -- Students must have access to the published section
        IF NOT EXISTS (
            SELECT 1
            FROM task_base t
            JOIN unit_section s ON s.id = t.section_id
            JOIN course_section_publication csp ON csp.section_id = s.id
            JOIN course_enrollment ce ON ce.course_id = csp.course_id
            WHERE t.id = p_task_id 
            AND ce.student_id = v_auth_user_id
            AND csp.is_published = true
        ) THEN
            RAISE EXCEPTION 'Unauthorized: Task not accessible';
        END IF;
    END IF;
END;
$$;


ALTER FUNCTION public.get_task_details(p_session_id text, p_task_id uuid) OWNER TO postgres;

--
-- Name: FUNCTION get_task_details(p_session_id text, p_task_id uuid); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.get_task_details(p_session_id text, p_task_id uuid) IS 'Returns task details without title column';


--
-- Name: get_tasks_for_section(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_tasks_for_section(p_session_id text, p_section_id uuid) RETURNS TABLE(task_id uuid, instruction text, task_type text, is_mastery boolean, solution_hints text, difficulty_level integer, max_attempts integer, order_in_section integer)
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_auth_user_id UUID;
    v_user_role user_role;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, CAST(user_role AS user_role), is_valid
    INTO v_auth_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid OR v_auth_user_id IS NULL THEN
        RAISE EXCEPTION 'Unauthorized: Invalid session';
    END IF;

    -- Check authorization
    IF v_user_role = 'teacher' THEN
        -- Teachers must own the learning unit
        IF NOT EXISTS (
            SELECT 1
            FROM unit_section s
            JOIN learning_unit lu ON lu.id = s.unit_id
            WHERE s.id = p_section_id AND lu.creator_id = v_auth_user_id
        ) THEN
            RAISE EXCEPTION 'Unauthorized: Not the owner of this unit';
        END IF;
    ELSE
        RAISE EXCEPTION 'Unauthorized: Invalid role';
    END IF;

    -- Return all tasks for the section
    RETURN QUERY
    SELECT
        t.id as task_id,
        t.instruction,
        t.task_type,
        CASE WHEN mt.task_id IS NOT NULL THEN true ELSE false END as is_mastery,
        t.solution_hints,
        mt.difficulty_level,
        rt.max_attempts,
        t.order_in_section
    FROM task_base t
    LEFT JOIN regular_tasks rt ON rt.task_id = t.id
    LEFT JOIN mastery_tasks mt ON mt.task_id = t.id
    WHERE t.section_id = p_section_id
    ORDER BY t.order_in_section;
END;
$$;


ALTER FUNCTION public.get_tasks_for_section(p_session_id text, p_section_id uuid) OWNER TO postgres;

--
-- Name: FUNCTION get_tasks_for_section(p_session_id text, p_section_id uuid); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.get_tasks_for_section(p_session_id text, p_section_id uuid) IS 'Returns tasks without title column';


--
-- Name: get_teachers_in_course(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_teachers_in_course(p_session_id text, p_course_id uuid) RETURNS TABLE(id uuid, email text, display_name text, role text, course_id uuid)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    -- Nur Lehrer duerfen andere Lehrer sehen
    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RETURN;
    END IF;

    -- Lehrer im Kurs zurueckgeben (inkl. Kursersteller)
    RETURN QUERY
    SELECT DISTINCT
        p.id,
        p.email,
        COALESCE(NULLIF(p.full_name, ''), p.email) as display_name, -- FIX: Use full_name with email fallback
        p.role::text,
        p_course_id
    FROM profiles p
    LEFT JOIN course_teacher ct ON p.id = ct.teacher_id AND ct.course_id = p_course_id
    LEFT JOIN course c ON p.id = c.creator_id AND c.id = p_course_id -- FIX: Use creator_id instead of created_by
    WHERE (ct.teacher_id IS NOT NULL OR c.id IS NOT NULL)
    ORDER BY COALESCE(NULLIF(p.full_name, ''), p.email); -- FIX: Order by computed display_name
END;
$$;


ALTER FUNCTION public.get_teachers_in_course(p_session_id text, p_course_id uuid) OWNER TO postgres;

--
-- Name: get_unit_id_from_path(text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_unit_id_from_path(p_path text) RETURNS uuid
    LANGUAGE plpgsql STABLE
    AS $$
declare
  v_unit_id_text text;
begin
  select (regexp_matches(p_path, 'unit_([a-f0-9\-]+)/'))[1] into v_unit_id_text;
  return v_unit_id_text::uuid;
exception
  when others then
    return null;
end;
$$;


ALTER FUNCTION public.get_unit_id_from_path(p_path text) OWNER TO postgres;

--
-- Name: get_unit_sections(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_unit_sections(p_session_id text, p_unit_id uuid) RETURNS TABLE(id uuid, title text, materials jsonb, order_in_unit integer, created_at timestamp with time zone)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    -- Invalid session = empty result
    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RETURN;
    END IF;

    -- Input validation
    IF p_unit_id IS NULL THEN
        RETURN;
    END IF;

    -- Check access authorization and load sections with materials
    RETURN QUERY
    SELECT
        us.id,
        us.title,
        us.materials,  -- NEU: materials JSONB-Spalte hinzugefuegt
        us.order_in_unit,
        us.created_at
    FROM unit_section us
    INNER JOIN learning_unit lu ON lu.id = us.unit_id
    WHERE us.unit_id = p_unit_id
    AND (
        lu.creator_id = v_user_id  -- Unit Owner
        OR v_user_role = 'admin'   -- Admin
        OR EXISTS (                -- Student with access through Course Assignment
            SELECT 1
            FROM course_learning_unit_assignment clua
            INNER JOIN course_student cs ON cs.course_id = clua.course_id
            WHERE clua.unit_id = p_unit_id
            AND cs.student_id = v_user_id
        )
    )
    ORDER BY us.order_in_unit ASC, us.created_at ASC;
END;
$$;


ALTER FUNCTION public.get_unit_sections(p_session_id text, p_unit_id uuid) OWNER TO postgres;

--
-- Name: get_user_course_ids(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_user_course_ids(p_session_id text, p_student_id uuid) RETURNS TABLE(course_id uuid)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN;
    END IF;

    -- Benutzer kann nur eigene Kurse sehen, Lehrer kuennen alle sehen
    IF v_user_role = 'student' AND v_user_id != p_student_id THEN
        RETURN;
    END IF;

    -- Kurs-IDs zurueckgeben
    RETURN QUERY
    SELECT cs.course_id
    FROM course_student cs
    WHERE cs.student_id = p_student_id;
END;
$$;


ALTER FUNCTION public.get_user_course_ids(p_session_id text, p_student_id uuid) OWNER TO postgres;

--
-- Name: get_user_courses(text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_user_courses(p_session_id text) RETURNS TABLE(id uuid, name text, creator_id uuid, created_at timestamp with time zone, student_count integer)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    -- Invalid session = empty result
    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RETURN;
    END IF;

    -- Role-based data return
    IF v_user_role = 'teacher' THEN
        RETURN QUERY
        SELECT
            c.id,
            c.name,
            c.creator_id,
            c.created_at,
            COUNT(DISTINCT cs.student_id)::INT as student_count
        FROM course c
        LEFT JOIN course_student cs ON cs.course_id = c.id
        WHERE c.creator_id = v_user_id
        GROUP BY c.id, c.name, c.creator_id, c.created_at
        ORDER BY c.created_at DESC;
    ELSE
        -- Student sees only assigned courses
        RETURN QUERY
        SELECT
            c.id,
            c.name,
            c.creator_id,
            c.created_at,
            COUNT(DISTINCT cs2.student_id)::INT as student_count
        FROM course c
        INNER JOIN course_student cs ON cs.course_id = c.id
        LEFT JOIN course_student cs2 ON cs2.course_id = c.id
        WHERE cs.student_id = v_user_id
        GROUP BY c.id, c.name, c.creator_id, c.created_at
        ORDER BY c.created_at DESC;
    END IF;
END;
$$;


ALTER FUNCTION public.get_user_courses(p_session_id text) OWNER TO postgres;

--
-- Name: get_user_learning_units(text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_user_learning_units(p_session_id text) RETURNS TABLE(id uuid, title text, creator_id uuid, created_at timestamp with time zone, assignment_count integer)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    -- Invalid session = empty result
    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RETURN;
    END IF;

    -- Only Teacher can see own Learning Units (OHNE description)
    IF v_user_role = 'teacher' THEN
        RETURN QUERY
        SELECT
            lu.id,
            lu.title,
            lu.creator_id,
            lu.created_at,
            COUNT(DISTINCT clua.course_id)::INT as assignment_count
        FROM learning_unit lu
        LEFT JOIN course_learning_unit_assignment clua ON clua.unit_id = lu.id
        WHERE lu.creator_id = v_user_id
        GROUP BY lu.id, lu.title, lu.creator_id, lu.created_at
        ORDER BY lu.created_at DESC;
    END IF;
    -- Students don't see Learning Units in management view
END;
$$;


ALTER FUNCTION public.get_user_learning_units(p_session_id text) OWNER TO postgres;

--
-- Name: get_user_profile_for_auth(uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_user_profile_for_auth(p_user_id uuid) RETURNS TABLE(id uuid, role public.user_role, email text, created_at timestamp with time zone, updated_at timestamp with time zone)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
BEGIN
    -- Return profile data for the given user
    RETURN QUERY
    SELECT 
        p.id,
        p.role,
        p.email,
        p.created_at,
        p.updated_at
    FROM public.profiles p
    WHERE p.id = p_user_id;
END;
$$;


ALTER FUNCTION public.get_user_profile_for_auth(p_user_id uuid) OWNER TO postgres;

--
-- Name: FUNCTION get_user_profile_for_auth(p_user_id uuid); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.get_user_profile_for_auth(p_user_id uuid) IS 'Fetches user profile for authentication service. Uses SECURITY DEFINER to bypass RLS when called with anon key. Fixed to return user_role type.';


--
-- Name: get_user_sessions(uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_user_sessions(p_user_id uuid) RETURNS TABLE(id uuid, session_id character varying, user_email text, user_role text, expires_at timestamp with time zone, last_activity timestamp with time zone, created_at timestamp with time zone, ip_address inet, user_agent text)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.id,
        s.session_id,
        s.user_email,
        s.user_role,
        s.expires_at,
        s.last_activity,
        s.created_at,
        s.ip_address,
        s.user_agent
    FROM auth_sessions s
    WHERE s.user_id = p_user_id
      AND s.expires_at > NOW()
    ORDER BY s.last_activity DESC;
END;
$$;


ALTER FUNCTION public.get_user_sessions(p_user_id uuid) OWNER TO postgres;

--
-- Name: FUNCTION get_user_sessions(p_user_id uuid); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.get_user_sessions(p_user_id uuid) IS 'Gets all active sessions for a user';


--
-- Name: get_users_by_role(text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_users_by_role(p_session_id text, p_role text) RETURNS TABLE(id uuid, email text, display_name text, role text)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    -- Nur Lehrer duerfen andere User sehen
    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RETURN;
    END IF;

    -- User mit spezifischer Rolle zurueckgeben
    RETURN QUERY
    SELECT
        p.id,
        p.email,
        COALESCE(NULLIF(p.full_name, ''), p.email) as display_name, -- FIX: Use full_name with email fallback
        p.role::text
    FROM profiles p
    WHERE p.role::text = p_role
    ORDER BY COALESCE(NULLIF(p.full_name, ''), p.email), p.email; -- FIX: Order by computed display_name
END;
$$;


ALTER FUNCTION public.get_users_by_role(p_session_id text, p_role text) OWNER TO postgres;

--
-- Name: handle_new_user(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.handle_new_user() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    AS $_$
DECLARE
    email_domain TEXT;
    is_domain_allowed BOOLEAN;
BEGIN
    -- Extract domain from email address
    email_domain := LOWER(SUBSTRING(NEW.email FROM '@[^@]+$'));
    
    -- Check if domain is allowed (with explicit public schema)
    SELECT EXISTS(
        SELECT 1 FROM public.allowed_email_domains 
        WHERE LOWER(domain) = email_domain 
        AND is_active = true
    ) INTO is_domain_allowed;
    
    -- If domain is not allowed, raise exception
    IF NOT is_domain_allowed THEN
        RAISE EXCEPTION 'Registration only allowed with school email addresses (@gymalf.de).';
    END IF;
    
    -- Create profile with default role 'student' and email
    INSERT INTO public.profiles (id, role, email)
    VALUES (NEW.id, 'student', NEW.email);
    
    RETURN NEW;
END;
$_$;


ALTER FUNCTION public.handle_new_user() OWNER TO postgres;

--
-- Name: handle_updated_at(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.handle_updated_at() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.handle_updated_at() OWNER TO postgres;

--
-- Name: invalidate_user_sessions(uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.invalidate_user_sessions(p_user_id uuid) RETURNS integer
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_deleted INT;
BEGIN
    DELETE FROM auth_sessions
    WHERE user_id = p_user_id;
    
    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    
    IF v_deleted > 0 THEN
        RAISE LOG 'Invalidated % sessions for user %', v_deleted, p_user_id;
    END IF;
    
    RETURN v_deleted;
END;
$$;


ALTER FUNCTION public.invalidate_user_sessions(p_user_id uuid) OWNER TO postgres;

--
-- Name: FUNCTION invalidate_user_sessions(p_user_id uuid); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.invalidate_user_sessions(p_user_id uuid) IS 'Deletes all sessions for a user (force logout everywhere)';


--
-- Name: is_creator_of_unit(uuid, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.is_creator_of_unit(p_user_id uuid, p_unit_id uuid) RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER
    AS $$
  select exists (
    select 1
    from public.learning_unit lu
    where lu.id = p_unit_id
    and lu.creator_id = p_user_id
  );
$$;


ALTER FUNCTION public.is_creator_of_unit(p_user_id uuid, p_unit_id uuid) OWNER TO postgres;

--
-- Name: is_enrolled_in_unit(uuid, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.is_enrolled_in_unit(p_user_id uuid, p_unit_id uuid) RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER
    AS $$
  select exists (
    select 1
    from public.course_student cs
    join public.course_learning_unit_assignment clua on cs.course_id = clua.course_id
    where cs.student_id = p_user_id
    and clua.unit_id = p_unit_id
  );
$$;


ALTER FUNCTION public.is_enrolled_in_unit(p_user_id uuid, p_unit_id uuid) OWNER TO postgres;

--
-- Name: is_teacher(uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.is_teacher(p_user_id uuid) RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER
    AS $$
  select exists (
    select 1
    from public.profiles
    where id = p_user_id and role = 'teacher'::public.user_role
  );
$$;


ALTER FUNCTION public.is_teacher(p_user_id uuid) OWNER TO postgres;

--
-- Name: is_teacher_authorized_for_course(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.is_teacher_authorized_for_course(p_session_id text, p_course_id uuid) RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN FALSE;
    END IF;

    -- Check authorization
    RETURN EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) OR EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id  -- Fixed: changed created_by to creator_id
    );
END;
$$;


ALTER FUNCTION public.is_teacher_authorized_for_course(p_session_id text, p_course_id uuid) OWNER TO postgres;

--
-- Name: is_teacher_in_course(uuid, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.is_teacher_in_course(p_teacher_id uuid, p_course_id uuid) RETURNS boolean
    LANGUAGE plpgsql STABLE SECURITY DEFINER
    AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1
    FROM public.course_teacher
    WHERE course_id = p_course_id AND teacher_id = p_teacher_id
  );
END;
$$;


ALTER FUNCTION public.is_teacher_in_course(p_teacher_id uuid, p_course_id uuid) OWNER TO postgres;

--
-- Name: is_user_role(uuid, public.user_role); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.is_user_role(user_id_to_check uuid, role_to_check public.user_role) RETURNS boolean
    LANGUAGE plpgsql STABLE SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
  real_role public.user_role;
BEGIN
  SELECT role INTO real_role FROM public.profiles WHERE id = user_id_to_check;
  RETURN real_role = role_to_check;
EXCEPTION
  -- Falls Nutzer kein Profil hat (sollte nicht passieren) oder anderer Fehler
  WHEN OTHERS THEN
    RETURN FALSE;
END;
$$;


ALTER FUNCTION public.is_user_role(user_id_to_check uuid, role_to_check public.user_role) OWNER TO postgres;

--
-- Name: mark_feedback_as_viewed(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.mark_feedback_as_viewed(p_session_id text, p_submission_id uuid) RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_updated_count INTEGER;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RAISE EXCEPTION 'Unauthorized: Invalid session';
    END IF;

    -- Mark feedback as viewed
    -- Only update if user is the student who owns the submission
    UPDATE submission
    SET feedback_viewed_at = NOW()
    WHERE id = p_submission_id
    AND student_id = v_user_id
    AND feedback_viewed_at IS NULL;
    
    -- Get the number of affected rows
    GET DIAGNOSTICS v_updated_count = ROW_COUNT;
    
    -- Return true if a row was updated
    RETURN v_updated_count > 0;
END;
$$;


ALTER FUNCTION public.mark_feedback_as_viewed(p_session_id text, p_submission_id uuid) OWNER TO postgres;

--
-- Name: FUNCTION mark_feedback_as_viewed(p_session_id text, p_submission_id uuid); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.mark_feedback_as_viewed(p_session_id text, p_submission_id uuid) IS 'Improved version of mark_feedback_as_viewed_safe that returns success status';


--
-- Name: mark_feedback_as_viewed_safe(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.mark_feedback_as_viewed_safe(p_session_id text, p_submission_id uuid) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RAISE EXCEPTION 'Unauthorized: Invalid session';
    END IF;

    -- Only students can mark their own feedback as viewed
    IF v_user_role != 'student' THEN
        RETURN;
    END IF;

    -- Update only if student owns the submission
    UPDATE submission
    SET feedback_viewed_at = NOW()
    WHERE id = p_submission_id 
    AND student_id = v_user_id
    AND feedback_viewed_at IS NULL;
END;
$$;


ALTER FUNCTION public.mark_feedback_as_viewed_safe(p_session_id text, p_submission_id uuid) OWNER TO postgres;

--
-- Name: mark_feedback_completed(uuid, text, jsonb, jsonb); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.mark_feedback_completed(p_submission_id uuid, p_feedback text, p_insights jsonb DEFAULT NULL::jsonb, p_mastery_scores jsonb DEFAULT NULL::jsonb) RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
    UPDATE submission
    SET 
        feedback_status = 'completed',
        ai_feedback = p_feedback,
        ai_insights = p_insights,
        ai_mastery_scores = p_mastery_scores
    WHERE id = p_submission_id
    AND feedback_status = 'processing';
    
    RETURN FOUND;
END;
$$;


ALTER FUNCTION public.mark_feedback_completed(p_submission_id uuid, p_feedback text, p_insights jsonb, p_mastery_scores jsonb) OWNER TO postgres;

--
-- Name: mark_feedback_failed(uuid, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.mark_feedback_failed(p_submission_id uuid, p_error_message text DEFAULT NULL::text) RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_retry_count INTEGER;
BEGIN
    -- Get current retry count
    SELECT retry_count INTO v_retry_count
    FROM submission
    WHERE id = p_submission_id
    AND feedback_status = 'processing';
    
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;
    
    -- Update based on retry count
    IF v_retry_count < 3 THEN
        UPDATE submission
        SET 
            feedback_status = 'retry',
            retry_count = retry_count + 1,
            last_retry_at = NOW(),
            processing_started_at = NULL
        WHERE id = p_submission_id;
    ELSE
        UPDATE submission
        SET 
            feedback_status = 'failed',
            ai_feedback = COALESCE(p_error_message, 'Feedback-Generierung fehlgeschlagen nach 3 Versuchen'),
            processing_started_at = NULL
        WHERE id = p_submission_id;
    END IF;
    
    RETURN TRUE;
END;
$$;


ALTER FUNCTION public.mark_feedback_failed(p_submission_id uuid, p_error_message text) OWNER TO postgres;

--
-- Name: move_task_down(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.move_task_down(p_session_id text, p_task_id uuid) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_section_id UUID;
    v_current_order INT;
    v_swap_task_id UUID;
    v_swap_order INT;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can move tasks';
    END IF;

    -- Get current task info
    SELECT t.section_id, rt.order_in_section
    INTO v_section_id, v_current_order
    FROM task_base t
    LEFT JOIN regular_tasks rt ON rt.task_id = t.id
    WHERE t.id = p_task_id;

    IF v_section_id IS NULL THEN
        RAISE EXCEPTION 'Task not found';
    END IF;

    -- Check if teacher owns the unit (FIXED: unit_id instead of learning_unit_id) 
    IF NOT EXISTS (
        SELECT 1 
        FROM unit_section s
        JOIN learning_unit lu ON lu.id = s.unit_id  -- FIXED: was s.learning_unit_id
        WHERE s.id = v_section_id AND lu.creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own this learning unit';
    END IF;

    -- Find task to swap with (next task)
    SELECT t.id, rt.order_in_section
    INTO v_swap_task_id, v_swap_order
    FROM task_base t
    JOIN regular_tasks rt ON rt.task_id = t.id
    WHERE t.section_id = v_section_id 
    AND rt.order_in_section > v_current_order
    ORDER BY rt.order_in_section ASC
    LIMIT 1;

    IF v_swap_task_id IS NULL THEN
        RETURN; -- Already at bottom
    END IF;

    -- Swap orders
    UPDATE regular_tasks SET order_in_section = v_swap_order WHERE task_id = p_task_id;
    UPDATE regular_tasks SET order_in_section = v_current_order WHERE task_id = v_swap_task_id;
END;
$$;


ALTER FUNCTION public.move_task_down(p_session_id text, p_task_id uuid) OWNER TO postgres;

--
-- Name: move_task_up(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.move_task_up(p_session_id text, p_task_id uuid) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_section_id UUID;
    v_current_order INT;
    v_swap_task_id UUID;
    v_swap_order INT;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can move tasks';
    END IF;

    -- Get current task info
    SELECT t.section_id, rt.order_in_section
    INTO v_section_id, v_current_order
    FROM task_base t
    LEFT JOIN regular_tasks rt ON rt.task_id = t.id
    WHERE t.id = p_task_id;

    IF v_section_id IS NULL THEN
        RAISE EXCEPTION 'Task not found';
    END IF;

    -- Check if teacher owns the unit (FIXED: unit_id instead of learning_unit_id)
    IF NOT EXISTS (
        SELECT 1 
        FROM unit_section s
        JOIN learning_unit lu ON lu.id = s.unit_id  -- FIXED: was s.learning_unit_id
        WHERE s.id = v_section_id AND lu.creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own this learning unit';
    END IF;

    -- Find task to swap with (previous task)
    SELECT t.id, rt.order_in_section
    INTO v_swap_task_id, v_swap_order
    FROM task_base t
    JOIN regular_tasks rt ON rt.task_id = t.id
    WHERE t.section_id = v_section_id 
    AND rt.order_in_section < v_current_order
    ORDER BY rt.order_in_section DESC
    LIMIT 1;

    IF v_swap_task_id IS NULL THEN
        RETURN; -- Already at top
    END IF;

    -- Swap orders
    UPDATE regular_tasks SET order_in_section = v_swap_order WHERE task_id = p_task_id;
    UPDATE regular_tasks SET order_in_section = v_current_order WHERE task_id = v_swap_task_id;
END;
$$;


ALTER FUNCTION public.move_task_up(p_session_id text, p_task_id uuid) OWNER TO postgres;

--
-- Name: publish_section_for_course(text, uuid, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.publish_section_for_course(p_session_id text, p_course_id uuid, p_section_id uuid) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Use standard session validation pattern
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid session';
    END IF;
    
    -- Check if user is teacher for course
    IF NOT EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Verify section belongs to a unit assigned to this course
    IF NOT EXISTS (
        SELECT 1 
        FROM unit_section s
        JOIN course_learning_unit_assignment cua ON cua.unit_id = s.unit_id
        WHERE s.id = p_section_id AND cua.course_id = p_course_id
    ) THEN
        RAISE EXCEPTION 'Section does not belong to a unit assigned to this course';
    END IF;

    -- Insert or update publish state
    INSERT INTO course_unit_section_status (
        course_id,
        section_id,
        is_published,
        published_at
    )
    VALUES (
        p_course_id,
        p_section_id,
        TRUE,
        NOW()
    )
    ON CONFLICT (course_id, section_id) 
    DO UPDATE SET
        is_published = TRUE,
        published_at = NOW();
END;
$$;


ALTER FUNCTION public.publish_section_for_course(p_session_id text, p_course_id uuid, p_section_id uuid) OWNER TO postgres;

--
-- Name: refresh_session(character varying, interval); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.refresh_session(p_session_id character varying, p_extend_by interval DEFAULT '01:30:00'::interval) RETURNS timestamp with time zone
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_new_expiry TIMESTAMPTZ;
BEGIN
    UPDATE auth_sessions
    SET 
        expires_at = NOW() + p_extend_by,
        last_activity = NOW()
    WHERE session_id = p_session_id
      AND expires_at > NOW()
    RETURNING expires_at INTO v_new_expiry;
    
    IF v_new_expiry IS NULL THEN
        RAISE EXCEPTION 'Session % not found or expired', p_session_id;
    END IF;
    
    RETURN v_new_expiry;
END;
$$;


ALTER FUNCTION public.refresh_session(p_session_id character varying, p_extend_by interval) OWNER TO postgres;

--
-- Name: FUNCTION refresh_session(p_session_id character varying, p_extend_by interval); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.refresh_session(p_session_id character varying, p_extend_by interval) IS 'Extends session expiration time';


--
-- Name: remove_user_from_course(text, uuid, uuid, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.remove_user_from_course(p_session_id text, p_user_id uuid, p_course_id uuid, p_role text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can remove users from courses';
    END IF;

    -- Check if teacher is authorized for this course
    IF NOT EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id  -- Fixed: changed created_by to creator_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Dynamic table selection based on role
    IF p_role = 'student' THEN
        DELETE FROM course_student 
        WHERE student_id = p_user_id AND course_id = p_course_id;
    ELSIF p_role = 'teacher' THEN
        -- Prevent removing course creator
        IF EXISTS (
            SELECT 1 FROM course 
            WHERE id = p_course_id AND creator_id = p_user_id  -- Fixed: changed created_by to creator_id
        ) THEN
            RAISE EXCEPTION 'Cannot remove course creator';
        END IF;
        
        DELETE FROM course_teacher 
        WHERE teacher_id = p_user_id AND course_id = p_course_id;
    ELSE
        RAISE EXCEPTION 'Invalid role: %', p_role;
    END IF;
END;
$$;


ALTER FUNCTION public.remove_user_from_course(p_session_id text, p_user_id uuid, p_course_id uuid, p_role text) OWNER TO postgres;

--
-- Name: reset_stuck_feedback_jobs(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.reset_stuck_feedback_jobs() RETURNS integer
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    rows_reset INTEGER := 0;
    rows_failed INTEGER := 0;
    total_affected INTEGER := 0;
BEGIN
    -- 1. Reset stuck jobs mit retry_count < 2 (nicht < 3!)
    -- Diese bekommen noch eine Chance
    UPDATE submission
    SET
        feedback_status = 'retry',
        retry_count = retry_count + 1,
        last_retry_at = NOW(),
        processing_started_at = NULL
    WHERE feedback_status = 'processing'
      AND processing_started_at < NOW() - INTERVAL '5 minutes'
      AND retry_count < 2;  -- Wichtig: < 2, nicht < 3!

    GET DIAGNOSTICS rows_reset = ROW_COUNT;

    -- 2. Mark as failed wenn schon 2 mal retried (wird dann retry_count = 3)
    UPDATE submission
    SET
        feedback_status = 'failed',
        ai_feedback = 'Feedback-Generierung nach 3 Versuchen fehlgeschlagen (Timeout)',
        processing_started_at = NULL
    WHERE feedback_status = 'processing'
      AND processing_started_at < NOW() - INTERVAL '5 minutes'
      AND retry_count >= 2;

    GET DIAGNOSTICS rows_failed = ROW_COUNT;

    -- 3. Cleanup: Stuck retry submissions mit retry_count >= 3
    -- Diese sollten eigentlich nie existieren, aber zur Sicherheit
    UPDATE submission
    SET
        feedback_status = 'failed',
        ai_feedback = 'Feedback-Generierung nach 3 Versuchen fehlgeschlagen',
        processing_started_at = NULL
    WHERE feedback_status = 'retry'
      AND retry_count >= 3
      AND (last_retry_at < NOW() - INTERVAL '1 hour' OR last_retry_at IS NULL);

    GET DIAGNOSTICS total_affected = ROW_COUNT;
    total_affected := rows_reset + rows_failed + total_affected;

    RETURN total_affected;
END;
$$;


ALTER FUNCTION public.reset_stuck_feedback_jobs() OWNER TO postgres;

--
-- Name: save_mastery_submission(text, uuid, uuid, boolean, integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.save_mastery_submission(p_session_id text, p_task_id uuid, p_submission_id uuid, p_is_correct boolean, p_time_spent_seconds integer) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'student' THEN
        RAISE EXCEPTION 'Unauthorized: Only students can save mastery submissions';
    END IF;

    -- Verify task is a mastery task
    IF NOT EXISTS (
        SELECT 1 FROM all_mastery_tasks t
        WHERE t.id = p_task_id
    ) THEN
        RAISE EXCEPTION 'Task is not a mastery task';
    END IF;

    -- Verify student owns the submission
    IF NOT EXISTS (
        SELECT 1 FROM submission s
        WHERE s.id = p_submission_id AND s.student_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Student does not own submission';
    END IF;

    -- Insert or update mastery submission record
    INSERT INTO mastery_submission (
        submission_id,
        time_spent_seconds,
        created_at
    )
    VALUES (
        p_submission_id,
        p_time_spent_seconds,
        NOW()
    )
    ON CONFLICT (submission_id) 
    DO UPDATE SET
        time_spent_seconds = EXCLUDED.time_spent_seconds;

    -- Update submission correctness
    UPDATE submission
    SET is_correct = p_is_correct
    WHERE id = p_submission_id;
END;
$$;


ALTER FUNCTION public.save_mastery_submission(p_session_id text, p_task_id uuid, p_submission_id uuid, p_is_correct boolean, p_time_spent_seconds integer) OWNER TO postgres;

--
-- Name: session_user_id(text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.session_user_id(p_session_id text) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Use the existing validate_session_and_get_user function
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    -- Return NULL if session is invalid
    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RETURN NULL;
    END IF;
    
    RETURN v_user_id;
END;
$$;


ALTER FUNCTION public.session_user_id(p_session_id text) OWNER TO postgres;

--
-- Name: FUNCTION session_user_id(p_session_id text); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.session_user_id(p_session_id text) IS 'Simple wrapper to get user_id from session_id for consistency across RPC functions';


--
-- Name: submit_feedback(text, text, text, text, text, jsonb); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.submit_feedback(p_session_id text, p_page_identifier text, p_feedback_type text, p_feedback_text text, p_sentiment text DEFAULT NULL::text, p_metadata jsonb DEFAULT NULL::jsonb) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_feedback_id UUID;
BEGIN
    -- Session validation (but allow anonymous feedback)
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    -- We allow anonymous feedback, so we don't check is_valid here
    
    -- Validate feedback type
    IF p_feedback_type NOT IN ('unterricht', 'plattform', 'bug') THEN
        RAISE EXCEPTION 'Invalid feedback type: %', p_feedback_type;
    END IF;
    
    -- Insert feedback (anonymous allowed)
    -- IMPORTANT: Use 'message' column to match the existing schema
    INSERT INTO feedback (
        page_identifier,
        feedback_type,
        message,           -- Changed from feedback_text to message
        feedback_text,     -- Also populate feedback_text for backwards compatibility
        sentiment,
        metadata,
        created_at
    )
    VALUES (
        p_page_identifier,
        p_feedback_type,
        p_feedback_text,   -- This goes into 'message' column (NOT NULL)
        p_feedback_text,   -- Also store in feedback_text for backwards compatibility
        p_sentiment,
        p_metadata,
        NOW()
    )
    RETURNING id INTO v_feedback_id;
    
    RETURN v_feedback_id;
END;
$$;


ALTER FUNCTION public.submit_feedback(p_session_id text, p_page_identifier text, p_feedback_type text, p_feedback_text text, p_sentiment text, p_metadata jsonb) OWNER TO postgres;

--
-- Name: submit_mastery_answer_complete(text, uuid, text, jsonb, jsonb); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.submit_mastery_answer_complete(p_session_id text, p_task_id uuid, p_submission_text text, p_ai_assessment jsonb, p_q_vec jsonb) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_submission_id UUID;
    v_attempt_number INT;
    v_current_progress RECORD;
    v_rating FLOAT;
    v_new_stability FLOAT;
    v_new_difficulty FLOAT;
    v_next_due DATE;
BEGIN
    -- Get user from session
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid or expired session';
    END IF;
    
    -- Check authorization for task - FIX: use course_student not course_students
    IF NOT EXISTS (
        SELECT 1 FROM student_mastery_progress smp
        JOIN mastery_tasks mt ON mt.task_id = p_task_id
        JOIN task_base t ON t.id = mt.task_id
        JOIN unit_section us ON us.id = t.section_id
        JOIN course_learning_unit_assignment clua ON clua.unit_id = us.unit_id
        JOIN course_student cs ON cs.course_id = clua.course_id  -- FIXED\!
        WHERE cs.student_id = v_user_id
        AND mt.task_id = p_task_id
    ) THEN
        -- Task might not have progress yet, check if student is enrolled
        IF NOT EXISTS (
            SELECT 1 FROM mastery_tasks mt
            JOIN task_base t ON t.id = mt.task_id
            JOIN unit_section us ON us.id = t.section_id
            JOIN course_learning_unit_assignment clua ON clua.unit_id = us.unit_id
            JOIN course_student cs ON cs.course_id = clua.course_id  -- FIXED\!
            WHERE cs.student_id = v_user_id
            AND mt.task_id = p_task_id
        ) THEN
            RAISE EXCEPTION 'Not authorized for this task';
        END IF;
    END IF;
    
    -- Start transaction
    BEGIN
        -- Count existing attempts
        SELECT COUNT(*) + 1 INTO v_attempt_number
        FROM submission
        WHERE student_id = v_user_id
        AND task_id = p_task_id;
        
        -- Insert submission with correct column names
        INSERT INTO submission (
            student_id,
            task_id,
            submission_data,
            ai_insights,
            feed_back_text,
            feed_forward_text,
            ai_feedback,
            attempt_number,
            submitted_at,
            feedback_status  -- Set to completed since we have the feedback
        )
        VALUES (
            v_user_id,
            p_task_id,
            p_submission_text::JSONB,
            p_q_vec,
            p_ai_assessment->>'feed_back_text',
            p_ai_assessment->>'feed_forward_text',
            p_ai_assessment->>'ai_feedback',
            v_attempt_number,
            NOW(),
            'completed'
        )
        RETURNING id INTO v_submission_id;
        
        -- Get current progress if exists
        SELECT * INTO v_current_progress
        FROM student_mastery_progress
        WHERE student_id = v_user_id
        AND task_id = p_task_id;
        
        -- Calculate rating from q_vec (using korrektheit as primary metric)
        v_rating := COALESCE((p_q_vec->>'korrektheit')::FLOAT, 0.5);
        
        -- Simple but effective spaced repetition calculation
        IF v_current_progress.stability IS NULL THEN
            -- First review
            IF v_rating >= 0.6 THEN
                v_new_stability := 2.5;
            ELSE
                v_new_stability := 1.0;
            END IF;
            v_new_difficulty := 5.0;
        ELSE
            -- Subsequent reviews
            IF v_rating >= 0.8 THEN
                v_new_stability := v_current_progress.stability * 2.5;
            ELSIF v_rating >= 0.6 THEN
                v_new_stability := v_current_progress.stability * 1.5;
            ELSIF v_rating >= 0.4 THEN
                v_new_stability := v_current_progress.stability * 1.1;
            ELSE
                v_new_stability := v_current_progress.stability * 0.5;
            END IF;
            
            v_new_stability := LEAST(v_new_stability, 90.0);
            v_new_stability := GREATEST(v_new_stability, 1.0);
            
            v_new_difficulty := v_current_progress.difficulty;
        END IF;
        
        -- Calculate next due date
        v_next_due := CURRENT_DATE + INTERVAL '1 day' * ROUND(v_new_stability);
        
        -- Upsert progress
        INSERT INTO student_mastery_progress (
            student_id,
            task_id,
            difficulty,
            stability,
            last_reviewed_at,
            next_due_date
        )
        VALUES (
            v_user_id,
            p_task_id,
            v_new_difficulty,
            v_new_stability,
            NOW(),
            v_next_due
        )
        ON CONFLICT (student_id, task_id)
        DO UPDATE SET
            difficulty = EXCLUDED.difficulty,
            stability = EXCLUDED.stability,
            last_reviewed_at = EXCLUDED.last_reviewed_at,
            next_due_date = EXCLUDED.next_due_date;
        
        RETURN jsonb_build_object(
            'submission_id', v_submission_id,
            'success', true,
            'next_review_date', v_next_due,
            'stability', v_new_stability
        );
        
    EXCEPTION WHEN OTHERS THEN
        -- Rollback will happen automatically
        RAISE;
    END;
END;
$$;


ALTER FUNCTION public.submit_mastery_answer_complete(p_session_id text, p_task_id uuid, p_submission_text text, p_ai_assessment jsonb, p_q_vec jsonb) OWNER TO postgres;

--
-- Name: FUNCTION submit_mastery_answer_complete(p_session_id text, p_task_id uuid, p_submission_text text, p_ai_assessment jsonb, p_q_vec jsonb); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.submit_mastery_answer_complete(p_session_id text, p_task_id uuid, p_submission_text text, p_ai_assessment jsonb, p_q_vec jsonb) IS 'Submits mastery answer and updates spaced repetition progress atomically';


--
-- Name: unassign_unit_from_course(text, uuid, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.unassign_unit_from_course(p_session_id text, p_unit_id uuid, p_course_id uuid) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can unassign units from courses';
    END IF;

    -- Check if teacher is authorized for this course
    IF NOT EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Delete assignment
    DELETE FROM course_learning_unit_assignment
    WHERE unit_id = p_unit_id AND course_id = p_course_id;  -- Fixed: changed from learning_unit_id
END;
$$;


ALTER FUNCTION public.unassign_unit_from_course(p_session_id text, p_unit_id uuid, p_course_id uuid) OWNER TO postgres;

--
-- Name: unpublish_section_for_course(text, uuid, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.unpublish_section_for_course(p_session_id text, p_section_id uuid, p_course_id uuid) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can unpublish sections';
    END IF;

    -- Check teacher authorization (FIX: created_by -> creator_id)
    IF NOT EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Update publish state
    UPDATE course_unit_section_status
    SET is_published = FALSE
    WHERE course_id = p_course_id 
    AND section_id = p_section_id;
END;
$$;


ALTER FUNCTION public.unpublish_section_for_course(p_session_id text, p_section_id uuid, p_course_id uuid) OWNER TO postgres;

--
-- Name: update_course(text, uuid, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_course(p_session_id text, p_course_id uuid, p_name text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can update courses';
    END IF;

    -- Check if teacher is authorized for this course
    IF NOT EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id  -- Fixed: changed created_by to creator_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Update course
    UPDATE course
    SET name = p_name,
        updated_at = NOW()
    WHERE id = p_course_id;
END;
$$;


ALTER FUNCTION public.update_course(p_session_id text, p_course_id uuid, p_name text) OWNER TO postgres;

--
-- Name: update_last_activity(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_last_activity() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.last_activity = NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_last_activity() OWNER TO postgres;

--
-- Name: update_learning_unit(text, uuid, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_learning_unit(p_session_id text, p_unit_id uuid, p_title text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can update learning units';
    END IF;

    -- Check if teacher owns the learning unit
    IF NOT EXISTS (
        SELECT 1 FROM learning_unit 
        WHERE id = p_unit_id AND creator_id = v_user_id  -- Fixed: changed created_by to creator_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Only unit creator can update the unit';
    END IF;

    -- Update learning unit
    UPDATE learning_unit
    SET title = p_title,
        updated_at = NOW()
    WHERE id = p_unit_id;
END;
$$;


ALTER FUNCTION public.update_learning_unit(p_session_id text, p_unit_id uuid, p_title text) OWNER TO postgres;

--
-- Name: update_mastery_progress(text, uuid, uuid, jsonb); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_mastery_progress(p_session_id text, p_student_id uuid, p_task_id uuid, p_q_vec jsonb) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_current_progress RECORD;
    v_rating FLOAT;
    v_new_stability FLOAT;
    v_new_difficulty FLOAT;
    v_next_due DATE;
BEGIN
    -- Get user from session
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid or expired session';
    END IF;
    
    -- Check if teacher updating for student
    IF v_user_id != p_student_id AND v_user_role NOT IN ('admin', 'teacher') THEN
        RAISE EXCEPTION 'Not authorized to update progress for other users';
    END IF;
    
    -- Get current progress
    SELECT * INTO v_current_progress
    FROM student_mastery_progress
    WHERE student_id = p_student_id
    AND task_id = p_task_id;
    
    -- Calculate rating from q_vec
    v_rating := COALESCE((p_q_vec->>'korrektheit')::FLOAT, 0.5);
    
    -- Calculate new values (same algorithm as in submit_mastery_answer_complete)
    IF v_current_progress.stability IS NULL THEN
        IF v_rating >= 0.6 THEN
            v_new_stability := 2.5;
        ELSE
            v_new_stability := 1.0;
        END IF;
        v_new_difficulty := 5.0;
    ELSE
        IF v_rating >= 0.8 THEN
            v_new_stability := v_current_progress.stability * 2.5;
        ELSIF v_rating >= 0.6 THEN
            v_new_stability := v_current_progress.stability * 1.5;
        ELSIF v_rating >= 0.4 THEN
            v_new_stability := v_current_progress.stability * 1.1;
        ELSE
            v_new_stability := v_current_progress.stability * 0.5;
        END IF;
        
        v_new_stability := LEAST(v_new_stability, 90.0);
        v_new_stability := GREATEST(v_new_stability, 1.0);
        v_new_difficulty := v_current_progress.difficulty;
    END IF;
    
    v_next_due := CURRENT_DATE + INTERVAL '1 day' * ROUND(v_new_stability);
    
    -- Update progress
    INSERT INTO student_mastery_progress (
        student_id,
        task_id,
        difficulty,
        stability,
        last_reviewed_at,
        next_due_date
    )
    VALUES (
        p_student_id,
        p_task_id,
        v_new_difficulty,
        v_new_stability,
        NOW(),
        v_next_due
    )
    ON CONFLICT (student_id, task_id)
    DO UPDATE SET
        difficulty = EXCLUDED.difficulty,
        stability = EXCLUDED.stability,
        last_reviewed_at = EXCLUDED.last_reviewed_at,
        next_due_date = EXCLUDED.next_due_date;
END;
$$;


ALTER FUNCTION public.update_mastery_progress(p_session_id text, p_student_id uuid, p_task_id uuid, p_q_vec jsonb) OWNER TO postgres;

--
-- Name: FUNCTION update_mastery_progress(p_session_id text, p_student_id uuid, p_task_id uuid, p_q_vec jsonb); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.update_mastery_progress(p_session_id text, p_student_id uuid, p_task_id uuid, p_q_vec jsonb) IS 'Updates mastery progress with correct validation';


--
-- Name: update_mastery_progress_service(uuid, uuid, jsonb); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_mastery_progress_service(p_student_id uuid, p_task_id uuid, p_q_vec jsonb) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_current_progress RECORD;
    v_rating FLOAT;
    v_new_stability FLOAT;
    v_new_difficulty FLOAT;
    v_next_due DATE;
BEGIN
    -- This function is called by service role, no session validation needed
    
    -- Get current progress if exists
    SELECT * INTO v_current_progress
    FROM student_mastery_progress
    WHERE student_id = p_student_id
    AND task_id = p_task_id;
    
    -- Calculate rating from q_vec (using korrektheit as primary metric)
    v_rating := COALESCE((p_q_vec->>'korrektheit')::FLOAT, 0.5);
    
    -- Simple but effective spaced repetition calculation (same as in submit_mastery_answer_complete)
    IF v_current_progress.stability IS NULL THEN
        -- First review
        IF v_rating >= 0.6 THEN
            v_new_stability := 2.5;
        ELSE
            v_new_stability := 1.0;
        END IF;
        v_new_difficulty := 5.0;
    ELSE
        -- Subsequent reviews
        IF v_rating >= 0.8 THEN
            v_new_stability := v_current_progress.stability * 2.5;
        ELSIF v_rating >= 0.6 THEN
            v_new_stability := v_current_progress.stability * 1.5;
        ELSIF v_rating >= 0.4 THEN
            v_new_stability := v_current_progress.stability * 1.1;
        ELSE
            v_new_stability := v_current_progress.stability * 0.5;
        END IF;
        
        v_new_stability := LEAST(v_new_stability, 90.0);
        v_new_stability := GREATEST(v_new_stability, 1.0);
        
        v_new_difficulty := v_current_progress.difficulty;
    END IF;
    
    -- Calculate next due date
    v_next_due := CURRENT_DATE + INTERVAL '1 day' * ROUND(v_new_stability);
    
    -- Upsert progress
    INSERT INTO student_mastery_progress (
        student_id,
        task_id,
        difficulty,
        stability,
        last_reviewed_at,
        next_due_date
    )
    VALUES (
        p_student_id,
        p_task_id,
        v_new_difficulty,
        v_new_stability,
        NOW(),
        v_next_due
    )
    ON CONFLICT (student_id, task_id)
    DO UPDATE SET
        difficulty = EXCLUDED.difficulty,
        stability = EXCLUDED.stability,
        last_reviewed_at = EXCLUDED.last_reviewed_at,
        next_due_date = EXCLUDED.next_due_date;
    
    RETURN jsonb_build_object(
        'success', true,
        'new_stability', v_new_stability,
        'next_due_date', v_next_due,
        'message', 'Mastery progress updated successfully'
    );
    
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'success', false,
        'error', SQLERRM
    );
END;
$$;


ALTER FUNCTION public.update_mastery_progress_service(p_student_id uuid, p_task_id uuid, p_q_vec jsonb) OWNER TO postgres;

--
-- Name: FUNCTION update_mastery_progress_service(p_student_id uuid, p_task_id uuid, p_q_vec jsonb); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.update_mastery_progress_service(p_student_id uuid, p_task_id uuid, p_q_vec jsonb) IS 'Service-role only function for updating mastery progress from background workers';


--
-- Name: update_section_materials(text, uuid, jsonb); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_section_materials(p_session_id text, p_section_id uuid, p_materials jsonb) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can update section materials';
    END IF;

    -- Check if teacher owns the section's learning unit
    IF NOT EXISTS (
        SELECT 1
        FROM unit_section s
        JOIN learning_unit lu ON lu.id = s.unit_id
        WHERE s.id = p_section_id AND lu.creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
    END IF;

    -- Update materials with explicit JSONB cast to ensure proper storage
    UPDATE unit_section
    SET
        materials = p_materials::jsonb,
        updated_at = NOW()
    WHERE id = p_section_id;

    -- Safe logging - only log if materials is an array
    IF p_materials IS NOT NULL AND jsonb_typeof(p_materials) = 'array' THEN
        RAISE NOTICE 'Updated materials for section %: % items', p_section_id, jsonb_array_length(p_materials);
    ELSE
        RAISE NOTICE 'Updated materials for section %', p_section_id;
    END IF;
END;
$$;


ALTER FUNCTION public.update_section_materials(p_session_id text, p_section_id uuid, p_materials jsonb) OWNER TO postgres;

--
-- Name: FUNCTION update_section_materials(p_session_id text, p_section_id uuid, p_materials jsonb); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.update_section_materials(p_session_id text, p_section_id uuid, p_materials jsonb) IS 'Updates section materials with proper JSONB handling and safe array length check';


--
-- Name: update_session(character varying, jsonb); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_session(p_session_id character varying, p_data jsonb) RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'extensions'
    AS $$
DECLARE
    v_updated INT;
BEGIN
    UPDATE auth_sessions
    SET 
        data = p_data,
        last_activity = NOW()
    WHERE session_id = p_session_id
      AND expires_at > NOW();
    
    GET DIAGNOSTICS v_updated = ROW_COUNT;
    
    RETURN v_updated > 0;
END;
$$;


ALTER FUNCTION public.update_session(p_session_id character varying, p_data jsonb) OWNER TO postgres;

--
-- Name: FUNCTION update_session(p_session_id character varying, p_data jsonb); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.update_session(p_session_id character varying, p_data jsonb) IS 'Updates session data (typically for storing additional metadata)';


--
-- Name: update_submission_ai_results(text, uuid, boolean, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_submission_ai_results(p_session_id text, p_submission_id uuid, p_is_correct boolean, p_ai_feedback text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RAISE EXCEPTION 'Unauthorized: Invalid session';
    END IF;

    -- This function should be called by the system after AI processing
    -- For now, we allow both students (for their own) and teachers
    IF v_user_role = 'student' THEN
        -- Verify student owns the submission
        IF NOT EXISTS (
            SELECT 1 FROM submission s
            WHERE s.id = p_submission_id AND s.student_id = v_user_id
        ) THEN
            RAISE EXCEPTION 'Unauthorized: Student does not own submission';
        END IF;
    END IF;

    -- Update submission
    UPDATE submission
    SET 
        is_correct = p_is_correct,
        ai_feedback = p_ai_feedback,
        ai_feedback_generated_at = NOW()
    WHERE id = p_submission_id;
END;
$$;


ALTER FUNCTION public.update_submission_ai_results(p_session_id text, p_submission_id uuid, p_is_correct boolean, p_ai_feedback text) OWNER TO postgres;

--
-- Name: update_submission_ai_results_extended(text, uuid, boolean, text, text, text, text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_submission_ai_results_extended(p_session_id text, p_submission_id uuid, p_is_correct boolean, p_ai_feedback text, p_criteria_analysis text DEFAULT NULL::text, p_ai_grade text DEFAULT NULL::text, p_feed_back_text text DEFAULT NULL::text, p_feed_forward_text text DEFAULT NULL::text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RAISE EXCEPTION 'Unauthorized: Invalid session';
    END IF;

    -- This function should be called by the system after AI processing
    -- For now, we allow both students (for their own) and teachers
    IF v_user_role = 'student' THEN
        -- Verify student owns the submission
        IF NOT EXISTS (
            SELECT 1 FROM submission s
            WHERE s.id = p_submission_id AND s.student_id = v_user_id
        ) THEN
            RAISE EXCEPTION 'Unauthorized: Student does not own submission';
        END IF;
    END IF;

    -- Update submission with all fields
    UPDATE submission
    SET 
        is_correct = p_is_correct,
        ai_feedback = p_ai_feedback,
        feedback_generated_at = NOW(),  -- Changed from ai_feedback_generated_at
        ai_criteria_analysis = COALESCE(p_criteria_analysis, ai_criteria_analysis),
        ai_grade = COALESCE(p_ai_grade, ai_grade),
        grade_generated_at = CASE 
            WHEN p_ai_grade IS NOT NULL THEN NOW() 
            ELSE grade_generated_at 
        END,
        feed_back_text = COALESCE(p_feed_back_text, feed_back_text),
        feed_forward_text = COALESCE(p_feed_forward_text, feed_forward_text)
    WHERE id = p_submission_id;
END;
$$;


ALTER FUNCTION public.update_submission_ai_results_extended(p_session_id text, p_submission_id uuid, p_is_correct boolean, p_ai_feedback text, p_criteria_analysis text, p_ai_grade text, p_feed_back_text text, p_feed_forward_text text) OWNER TO postgres;

--
-- Name: FUNCTION update_submission_ai_results_extended(p_session_id text, p_submission_id uuid, p_is_correct boolean, p_ai_feedback text, p_criteria_analysis text, p_ai_grade text, p_feed_back_text text, p_feed_forward_text text); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.update_submission_ai_results_extended(p_session_id text, p_submission_id uuid, p_is_correct boolean, p_ai_feedback text, p_criteria_analysis text, p_ai_grade text, p_feed_back_text text, p_feed_forward_text text) IS 'Extended version of update_submission_ai_results that supports all AI result fields including criteria analysis, grades, and feedback texts (fixed column name)';


--
-- Name: update_submission_by_teacher(uuid, text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_submission_by_teacher(submission_id_in uuid, teacher_feedback_in text, teacher_grade_in text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'extensions', 'public'
    AS $$
DECLARE
    is_authorized boolean;
BEGIN
    -- Schritt 1: Überprüfe, ob der aufrufende Benutzer (Lehrer) die Berechtigung hat.
    -- Ein Lehrer ist berechtigt, wenn er in einem Kurs unterrichtet, der die Lerneinheit
    -- enthält, zu der die Aufgabe der Einreichung gehört.
    SELECT EXISTS (
        SELECT 1
        FROM public.submission s
        -- JOIN über die Aufgaben- und Einheiten-Hierarchie zum Kurs
        JOIN public.task t ON s.task_id = t.id
        JOIN public.unit_section us ON t.section_id = us.id
        JOIN public.course_learning_unit_assignment clua ON us.unit_id = clua.unit_id
        -- JOIN zur Lehrer-Tabelle, um die Berechtigung zu prüfen
        JOIN public.course_teacher ct ON clua.course_id = ct.course_id
        WHERE
            s.id = submission_id_in
            AND ct.teacher_id = auth.uid() -- auth.uid() ist der aufrufende Benutzer
    ) INTO is_authorized;

    -- Schritt 2: Wenn nicht berechtigt, wirf einen Fehler.
    IF NOT is_authorized THEN
        RAISE EXCEPTION 'Unauthorized: Sie haben keine Berechtigung, diese Einreichung zu bearbeiten.';
    END IF;

    -- Schritt 3: Wenn berechtigt, führe das Update durch.
    UPDATE public.submission
    SET
        teacher_override_feedback = teacher_feedback_in,
        teacher_override_grade = teacher_grade_in,
        updated_at = now()
    WHERE id = submission_id_in;
END;
$$;


ALTER FUNCTION public.update_submission_by_teacher(submission_id_in uuid, teacher_feedback_in text, teacher_grade_in text) OWNER TO postgres;

--
-- Name: update_submission_from_ai(uuid, jsonb, text, text, text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_submission_from_ai(submission_id_in uuid, criteria_analysis_in jsonb, feedback_in text, rating_suggestion_in text, feed_back_text_in text, feed_forward_text_in text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'extensions', 'public'
    AS $$
BEGIN
  UPDATE public.submission
  SET
    ai_criteria_analysis = criteria_analysis_in,
    ai_feedback = feedback_in,
    feedback_generated_at = now(),
    ai_grade = rating_suggestion_in,
    grade_generated_at = now(),
    feed_back_text = feed_back_text_in,
    feed_forward_text = feed_forward_text_in
  WHERE id = submission_id_in;
END;
$$;


ALTER FUNCTION public.update_submission_from_ai(submission_id_in uuid, criteria_analysis_in jsonb, feedback_in text, rating_suggestion_in text, feed_back_text_in text, feed_forward_text_in text) OWNER TO postgres;

--
-- Name: update_submission_teacher_override(text, uuid, boolean, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_submission_teacher_override(p_session_id text, p_submission_id uuid, p_override_grade boolean, p_teacher_feedback text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_student_id UUID;
    v_task_id UUID;
    v_course_id UUID;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can override grades';
    END IF;

    -- Get submission info
    SELECT s.student_id, s.task_id
    INTO v_student_id, v_task_id
    FROM submission s
    WHERE s.id = p_submission_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Submission not found';
    END IF;

    -- Check if teacher has access to this course - FIXED: sec.unit_id instead of sec.learning_unit_id
    SELECT cua.course_id
    INTO v_course_id
    FROM task_base t
    JOIN unit_section sec ON sec.id = t.section_id
    JOIN learning_unit lu ON lu.id = sec.unit_id  -- FIXED: was sec.learning_unit_id
    JOIN course_learning_unit_assignment cua ON cua.unit_id = lu.id  -- FIXED: was cua.learning_unit_id 
    WHERE t.id = v_task_id
    LIMIT 1;

    IF NOT EXISTS (
        SELECT 1 FROM course_teacher ct
        WHERE ct.teacher_id = v_user_id AND ct.course_id = v_course_id
    ) AND NOT EXISTS (
        -- Also allow if teacher created the learning unit directly
        SELECT 1 FROM learning_unit lu
        JOIN unit_section sec ON sec.unit_id = lu.id  -- FIXED: was sec.learning_unit_id
        JOIN task_base t ON t.section_id = sec.id
        WHERE t.id = v_task_id AND lu.creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course or learning unit';
    END IF;

    -- Update submission with teacher override
    UPDATE submission
    SET 
        teacher_override_grade = CASE 
            WHEN p_override_grade THEN 'correct'::TEXT 
            ELSE 'incorrect'::TEXT 
        END,
        teacher_override_feedback = p_teacher_feedback,
        updated_at = NOW()
    WHERE id = p_submission_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Failed to update submission';
    END IF;
END;
$$;


ALTER FUNCTION public.update_submission_teacher_override(p_session_id text, p_submission_id uuid, p_override_grade boolean, p_teacher_feedback text) OWNER TO postgres;

--
-- Name: update_task_in_new_structure(text, uuid, text, text, text, integer, integer, text[], text, integer, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_task_in_new_structure(p_session_id text, p_task_id uuid, p_title text, p_prompt text, p_task_type text, p_order_in_section integer DEFAULT NULL::integer, p_max_attempts integer DEFAULT NULL::integer, p_grading_criteria text[] DEFAULT NULL::text[], p_solution_hints text DEFAULT NULL::text, p_difficulty_level integer DEFAULT NULL::integer, p_concept_explanation text DEFAULT NULL::text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_is_regular BOOLEAN;
    v_is_mastery BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can update tasks';
    END IF;

    -- Check if teacher has access to the task
    IF NOT EXISTS (
        SELECT 1
        FROM task_base t
        JOIN unit_section s ON s.id = t.section_id
        JOIN learning_unit lu ON lu.id = s.unit_id
        WHERE t.id = p_task_id AND lu.creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
    END IF;

    -- Detect task type
    SELECT EXISTS(SELECT 1 FROM regular_tasks WHERE task_id = p_task_id) INTO v_is_regular;
    SELECT EXISTS(SELECT 1 FROM mastery_tasks WHERE task_id = p_task_id) INTO v_is_mastery;

    IF NOT v_is_regular AND NOT v_is_mastery THEN
        RAISE EXCEPTION 'Task not found in either regular_tasks or mastery_tasks';
    END IF;

    -- Update task_base
    UPDATE task_base
    SET
        instruction = p_title,
        task_type = p_task_type,
        order_in_section = CASE
            WHEN v_is_regular THEN COALESCE(p_order_in_section, order_in_section)
            ELSE order_in_section -- Mastery tasks don't have order
        END,
        solution_hints = COALESCE(p_solution_hints, solution_hints)  -- Update solution_hints in task_base
    WHERE id = p_task_id;

    -- Update type-specific table
    IF v_is_regular THEN
        UPDATE regular_tasks
        SET
            prompt = p_prompt,
            max_attempts = COALESCE(p_max_attempts, max_attempts),
            grading_criteria = COALESCE(p_grading_criteria, grading_criteria),
            solution_hints = COALESCE(p_solution_hints, solution_hints)  -- Update solution_hints in regular_tasks
        WHERE task_id = p_task_id;
    ELSE
        UPDATE mastery_tasks
        SET
            prompt = p_prompt,
            difficulty_level = COALESCE(p_difficulty_level, difficulty_level),
            concept_explanation = COALESCE(p_concept_explanation, concept_explanation),
            solution_hints = COALESCE(p_solution_hints, solution_hints)  -- Update solution_hints in mastery_tasks
        WHERE task_id = p_task_id;
    END IF;
END;
$$;


ALTER FUNCTION public.update_task_in_new_structure(p_session_id text, p_task_id uuid, p_title text, p_prompt text, p_task_type text, p_order_in_section integer, p_max_attempts integer, p_grading_criteria text[], p_solution_hints text, p_difficulty_level integer, p_concept_explanation text) OWNER TO postgres;

--
-- Name: FUNCTION update_task_in_new_structure(p_session_id text, p_task_id uuid, p_title text, p_prompt text, p_task_type text, p_order_in_section integer, p_max_attempts integer, p_grading_criteria text[], p_solution_hints text, p_difficulty_level integer, p_concept_explanation text); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.update_task_in_new_structure(p_session_id text, p_task_id uuid, p_title text, p_prompt text, p_task_type text, p_order_in_section integer, p_max_attempts integer, p_grading_criteria text[], p_solution_hints text, p_difficulty_level integer, p_concept_explanation text) IS 'Updates a task (regular or mastery) including solution hints with proper session validation.';


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_updated_at_column() OWNER TO postgres;

--
-- Name: validate_auth_service_key(text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.validate_auth_service_key(api_key text) RETURNS TABLE(is_valid boolean, permissions jsonb)
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    key_record RECORD;
BEGIN
    -- In production, compare against bcrypt hash
    -- For now, simple comparison (YOU MUST USE BCRYPT IN PRODUCTION!)
    SELECT * INTO key_record 
    FROM public.auth_service_keys 
    WHERE key_hash = api_key AND is_active = true;
    
    IF FOUND THEN
        -- Update last used timestamp
        UPDATE public.auth_service_keys 
        SET last_used_at = NOW() 
        WHERE id = key_record.id;
        
        RETURN QUERY SELECT true, key_record.permissions;
    ELSE
        RETURN QUERY SELECT false, NULL::JSONB;
    END IF;
END;
$$;


ALTER FUNCTION public.validate_auth_service_key(api_key text) OWNER TO postgres;

--
-- Name: validate_session(character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.validate_session(p_session_id character varying) RETURNS TABLE(is_valid boolean, user_id uuid, user_email text, user_role text, expires_in_seconds integer)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'extensions'
    AS $$
DECLARE
    v_session RECORD;
BEGIN
    -- Optimized: Update activity and get session in one query
    WITH updated AS (
        UPDATE auth_sessions s
        SET last_activity = NOW()
        WHERE s.session_id = p_session_id
          AND s.expires_at > NOW()
        RETURNING s.*
    )
    SELECT * INTO v_session FROM updated;
    
    IF v_session.id IS NULL THEN
        RETURN QUERY SELECT 
            false::BOOLEAN,
            NULL::UUID,
            NULL::TEXT,
            NULL::TEXT,
            0::INT;
    ELSE
        RETURN QUERY SELECT
            true::BOOLEAN,
            v_session.user_id,
            v_session.user_email,
            v_session.user_role,
            EXTRACT(EPOCH FROM (v_session.expires_at - NOW()))::INT;
    END IF;
END;
$$;


ALTER FUNCTION public.validate_session(p_session_id character varying) OWNER TO postgres;

--
-- Name: FUNCTION validate_session(p_session_id character varying); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.validate_session(p_session_id character varying) IS 'Validates a session for nginx auth_request, returns user info if valid';


--
-- Name: validate_session_and_get_user(text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.validate_session_and_get_user(p_session_id text) RETURNS TABLE(user_id uuid, user_role text, is_valid boolean)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
BEGIN
    -- Security: Null/Empty Check
    IF p_session_id IS NULL OR p_session_id = '' THEN
        RETURN QUERY SELECT NULL::UUID, NULL::TEXT, FALSE;
        RETURN;
    END IF;

    -- Use existing auth_sessions table
    RETURN QUERY
    SELECT
        s.user_id,
        s.user_role,
        TRUE as is_valid
    FROM auth_sessions s
    WHERE s.session_id = p_session_id
    AND s.expires_at > NOW()
    LIMIT 1;  -- Security: Only one Row

    -- If no valid session found
    IF NOT FOUND THEN
        RETURN QUERY SELECT NULL::UUID, NULL::TEXT, FALSE;
    END IF;
END;
$$;


ALTER FUNCTION public.validate_session_and_get_user(p_session_id text) OWNER TO postgres;

--
-- Name: validate_storage_session_user(text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.validate_storage_session_user(path text) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
    v_session_id text;
    v_user_id uuid;
    v_is_valid boolean;
BEGIN
    -- Get session from cookie
    v_session_id := current_setting('request.cookies', true)::json->>'gustav_session';
    
    IF v_session_id IS NULL THEN
        RETURN NULL;
    END IF;
    
    -- Validate session and get user
    SELECT user_id, is_valid
    INTO v_user_id, v_is_valid
    FROM public.validate_session_and_get_user(v_session_id);
    
    IF NOT v_is_valid THEN
        RETURN NULL;
    END IF;
    
    RETURN v_user_id;
END;
$$;


ALTER FUNCTION public.validate_storage_session_user(path text) OWNER TO postgres;

--
-- Name: apply_rls(jsonb, integer); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
--

CREATE FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer DEFAULT (1024 * 1024)) RETURNS SETOF realtime.wal_rls
    LANGUAGE plpgsql
    AS $$
declare
-- Regclass of the table e.g. public.notes
entity_ regclass = (quote_ident(wal ->> 'schema') || '.' || quote_ident(wal ->> 'table'))::regclass;

-- I, U, D, T: insert, update ...
action realtime.action = (
    case wal ->> 'action'
        when 'I' then 'INSERT'
        when 'U' then 'UPDATE'
        when 'D' then 'DELETE'
        else 'ERROR'
    end
);

-- Is row level security enabled for the table
is_rls_enabled bool = relrowsecurity from pg_class where oid = entity_;

subscriptions realtime.subscription[] = array_agg(subs)
    from
        realtime.subscription subs
    where
        subs.entity = entity_;

-- Subscription vars
roles regrole[] = array_agg(distinct us.claims_role::text)
    from
        unnest(subscriptions) us;

working_role regrole;
claimed_role regrole;
claims jsonb;

subscription_id uuid;
subscription_has_access bool;
visible_to_subscription_ids uuid[] = '{}';

-- structured info for wal's columns
columns realtime.wal_column[];
-- previous identity values for update/delete
old_columns realtime.wal_column[];

error_record_exceeds_max_size boolean = octet_length(wal::text) > max_record_bytes;

-- Primary jsonb output for record
output jsonb;

begin
perform set_config('role', null, true);

columns =
    array_agg(
        (
            x->>'name',
            x->>'type',
            x->>'typeoid',
            realtime.cast(
                (x->'value') #>> '{}',
                coalesce(
                    (x->>'typeoid')::regtype, -- null when wal2json version <= 2.4
                    (x->>'type')::regtype
                )
            ),
            (pks ->> 'name') is not null,
            true
        )::realtime.wal_column
    )
    from
        jsonb_array_elements(wal -> 'columns') x
        left join jsonb_array_elements(wal -> 'pk') pks
            on (x ->> 'name') = (pks ->> 'name');

old_columns =
    array_agg(
        (
            x->>'name',
            x->>'type',
            x->>'typeoid',
            realtime.cast(
                (x->'value') #>> '{}',
                coalesce(
                    (x->>'typeoid')::regtype, -- null when wal2json version <= 2.4
                    (x->>'type')::regtype
                )
            ),
            (pks ->> 'name') is not null,
            true
        )::realtime.wal_column
    )
    from
        jsonb_array_elements(wal -> 'identity') x
        left join jsonb_array_elements(wal -> 'pk') pks
            on (x ->> 'name') = (pks ->> 'name');

for working_role in select * from unnest(roles) loop

    -- Update `is_selectable` for columns and old_columns
    columns =
        array_agg(
            (
                c.name,
                c.type_name,
                c.type_oid,
                c.value,
                c.is_pkey,
                pg_catalog.has_column_privilege(working_role, entity_, c.name, 'SELECT')
            )::realtime.wal_column
        )
        from
            unnest(columns) c;

    old_columns =
            array_agg(
                (
                    c.name,
                    c.type_name,
                    c.type_oid,
                    c.value,
                    c.is_pkey,
                    pg_catalog.has_column_privilege(working_role, entity_, c.name, 'SELECT')
                )::realtime.wal_column
            )
            from
                unnest(old_columns) c;

    if action <> 'DELETE' and count(1) = 0 from unnest(columns) c where c.is_pkey then
        return next (
            jsonb_build_object(
                'schema', wal ->> 'schema',
                'table', wal ->> 'table',
                'type', action
            ),
            is_rls_enabled,
            -- subscriptions is already filtered by entity
            (select array_agg(s.subscription_id) from unnest(subscriptions) as s where claims_role = working_role),
            array['Error 400: Bad Request, no primary key']
        )::realtime.wal_rls;

    -- The claims role does not have SELECT permission to the primary key of entity
    elsif action <> 'DELETE' and sum(c.is_selectable::int) <> count(1) from unnest(columns) c where c.is_pkey then
        return next (
            jsonb_build_object(
                'schema', wal ->> 'schema',
                'table', wal ->> 'table',
                'type', action
            ),
            is_rls_enabled,
            (select array_agg(s.subscription_id) from unnest(subscriptions) as s where claims_role = working_role),
            array['Error 401: Unauthorized']
        )::realtime.wal_rls;

    else
        output = jsonb_build_object(
            'schema', wal ->> 'schema',
            'table', wal ->> 'table',
            'type', action,
            'commit_timestamp', to_char(
                ((wal ->> 'timestamp')::timestamptz at time zone 'utc'),
                'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'
            ),
            'columns', (
                select
                    jsonb_agg(
                        jsonb_build_object(
                            'name', pa.attname,
                            'type', pt.typname
                        )
                        order by pa.attnum asc
                    )
                from
                    pg_attribute pa
                    join pg_type pt
                        on pa.atttypid = pt.oid
                where
                    attrelid = entity_
                    and attnum > 0
                    and pg_catalog.has_column_privilege(working_role, entity_, pa.attname, 'SELECT')
            )
        )
        -- Add "record" key for insert and update
        || case
            when action in ('INSERT', 'UPDATE') then
                jsonb_build_object(
                    'record',
                    (
                        select
                            jsonb_object_agg(
                                -- if unchanged toast, get column name and value from old record
                                coalesce((c).name, (oc).name),
                                case
                                    when (c).name is null then (oc).value
                                    else (c).value
                                end
                            )
                        from
                            unnest(columns) c
                            full outer join unnest(old_columns) oc
                                on (c).name = (oc).name
                        where
                            coalesce((c).is_selectable, (oc).is_selectable)
                            and ( not error_record_exceeds_max_size or (octet_length((c).value::text) <= 64))
                    )
                )
            else '{}'::jsonb
        end
        -- Add "old_record" key for update and delete
        || case
            when action = 'UPDATE' then
                jsonb_build_object(
                        'old_record',
                        (
                            select jsonb_object_agg((c).name, (c).value)
                            from unnest(old_columns) c
                            where
                                (c).is_selectable
                                and ( not error_record_exceeds_max_size or (octet_length((c).value::text) <= 64))
                        )
                    )
            when action = 'DELETE' then
                jsonb_build_object(
                    'old_record',
                    (
                        select jsonb_object_agg((c).name, (c).value)
                        from unnest(old_columns) c
                        where
                            (c).is_selectable
                            and ( not error_record_exceeds_max_size or (octet_length((c).value::text) <= 64))
                            and ( not is_rls_enabled or (c).is_pkey ) -- if RLS enabled, we can't secure deletes so filter to pkey
                    )
                )
            else '{}'::jsonb
        end;

        -- Create the prepared statement
        if is_rls_enabled and action <> 'DELETE' then
            if (select 1 from pg_prepared_statements where name = 'walrus_rls_stmt' limit 1) > 0 then
                deallocate walrus_rls_stmt;
            end if;
            execute realtime.build_prepared_statement_sql('walrus_rls_stmt', entity_, columns);
        end if;

        visible_to_subscription_ids = '{}';

        for subscription_id, claims in (
                select
                    subs.subscription_id,
                    subs.claims
                from
                    unnest(subscriptions) subs
                where
                    subs.entity = entity_
                    and subs.claims_role = working_role
                    and (
                        realtime.is_visible_through_filters(columns, subs.filters)
                        or (
                          action = 'DELETE'
                          and realtime.is_visible_through_filters(old_columns, subs.filters)
                        )
                    )
        ) loop

            if not is_rls_enabled or action = 'DELETE' then
                visible_to_subscription_ids = visible_to_subscription_ids || subscription_id;
            else
                -- Check if RLS allows the role to see the record
                perform
                    -- Trim leading and trailing quotes from working_role because set_config
                    -- doesn't recognize the role as valid if they are included
                    set_config('role', trim(both '"' from working_role::text), true),
                    set_config('request.jwt.claims', claims::text, true);

                execute 'execute walrus_rls_stmt' into subscription_has_access;

                if subscription_has_access then
                    visible_to_subscription_ids = visible_to_subscription_ids || subscription_id;
                end if;
            end if;
        end loop;

        perform set_config('role', null, true);

        return next (
            output,
            is_rls_enabled,
            visible_to_subscription_ids,
            case
                when error_record_exceeds_max_size then array['Error 413: Payload Too Large']
                else '{}'
            end
        )::realtime.wal_rls;

    end if;
end loop;

perform set_config('role', null, true);
end;
$$;


ALTER FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) OWNER TO supabase_admin;

--
-- Name: broadcast_changes(text, text, text, text, text, record, record, text); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
--

CREATE FUNCTION realtime.broadcast_changes(topic_name text, event_name text, operation text, table_name text, table_schema text, new record, old record, level text DEFAULT 'ROW'::text) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
    -- Declare a variable to hold the JSONB representation of the row
    row_data jsonb := '{}'::jsonb;
BEGIN
    IF level = 'STATEMENT' THEN
        RAISE EXCEPTION 'function can only be triggered for each row, not for each statement';
    END IF;
    -- Check the operation type and handle accordingly
    IF operation = 'INSERT' OR operation = 'UPDATE' OR operation = 'DELETE' THEN
        row_data := jsonb_build_object('old_record', OLD, 'record', NEW, 'operation', operation, 'table', table_name, 'schema', table_schema);
        PERFORM realtime.send (row_data, event_name, topic_name);
    ELSE
        RAISE EXCEPTION 'Unexpected operation type: %', operation;
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Failed to process the row: %', SQLERRM;
END;

$$;


ALTER FUNCTION realtime.broadcast_changes(topic_name text, event_name text, operation text, table_name text, table_schema text, new record, old record, level text) OWNER TO supabase_admin;

--
-- Name: build_prepared_statement_sql(text, regclass, realtime.wal_column[]); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
--

CREATE FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) RETURNS text
    LANGUAGE sql
    AS $$
      /*
      Builds a sql string that, if executed, creates a prepared statement to
      tests retrive a row from *entity* by its primary key columns.
      Example
          select realtime.build_prepared_statement_sql('public.notes', '{"id"}'::text[], '{"bigint"}'::text[])
      */
          select
      'prepare ' || prepared_statement_name || ' as
          select
              exists(
                  select
                      1
                  from
                      ' || entity || '
                  where
                      ' || string_agg(quote_ident(pkc.name) || '=' || quote_nullable(pkc.value #>> '{}') , ' and ') || '
              )'
          from
              unnest(columns) pkc
          where
              pkc.is_pkey
          group by
              entity
      $$;


ALTER FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) OWNER TO supabase_admin;

--
-- Name: cast(text, regtype); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
--

CREATE FUNCTION realtime."cast"(val text, type_ regtype) RETURNS jsonb
    LANGUAGE plpgsql IMMUTABLE
    AS $$
    declare
      res jsonb;
    begin
      execute format('select to_jsonb(%L::'|| type_::text || ')', val)  into res;
      return res;
    end
    $$;


ALTER FUNCTION realtime."cast"(val text, type_ regtype) OWNER TO supabase_admin;

--
-- Name: check_equality_op(realtime.equality_op, regtype, text, text); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
--

CREATE FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) RETURNS boolean
    LANGUAGE plpgsql IMMUTABLE
    AS $$
      /*
      Casts *val_1* and *val_2* as type *type_* and check the *op* condition for truthiness
      */
      declare
          op_symbol text = (
              case
                  when op = 'eq' then '='
                  when op = 'neq' then '!='
                  when op = 'lt' then '<'
                  when op = 'lte' then '<='
                  when op = 'gt' then '>'
                  when op = 'gte' then '>='
                  when op = 'in' then '= any'
                  else 'UNKNOWN OP'
              end
          );
          res boolean;
      begin
          execute format(
              'select %L::'|| type_::text || ' ' || op_symbol
              || ' ( %L::'
              || (
                  case
                      when op = 'in' then type_::text || '[]'
                      else type_::text end
              )
              || ')', val_1, val_2) into res;
          return res;
      end;
      $$;


ALTER FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) OWNER TO supabase_admin;

--
-- Name: is_visible_through_filters(realtime.wal_column[], realtime.user_defined_filter[]); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
--

CREATE FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) RETURNS boolean
    LANGUAGE sql IMMUTABLE
    AS $_$
    /*
    Should the record be visible (true) or filtered out (false) after *filters* are applied
    */
        select
            -- Default to allowed when no filters present
            $2 is null -- no filters. this should not happen because subscriptions has a default
            or array_length($2, 1) is null -- array length of an empty array is null
            or bool_and(
                coalesce(
                    realtime.check_equality_op(
                        op:=f.op,
                        type_:=coalesce(
                            col.type_oid::regtype, -- null when wal2json version <= 2.4
                            col.type_name::regtype
                        ),
                        -- cast jsonb to text
                        val_1:=col.value #>> '{}',
                        val_2:=f.value
                    ),
                    false -- if null, filter does not match
                )
            )
        from
            unnest(filters) f
            join unnest(columns) col
                on f.column_name = col.name;
    $_$;


ALTER FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) OWNER TO supabase_admin;

--
-- Name: list_changes(name, name, integer, integer); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
--

CREATE FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) RETURNS SETOF realtime.wal_rls
    LANGUAGE sql
    SET log_min_messages TO 'fatal'
    AS $$
      with pub as (
        select
          concat_ws(
            ',',
            case when bool_or(pubinsert) then 'insert' else null end,
            case when bool_or(pubupdate) then 'update' else null end,
            case when bool_or(pubdelete) then 'delete' else null end
          ) as w2j_actions,
          coalesce(
            string_agg(
              realtime.quote_wal2json(format('%I.%I', schemaname, tablename)::regclass),
              ','
            ) filter (where ppt.tablename is not null and ppt.tablename not like '% %'),
            ''
          ) w2j_add_tables
        from
          pg_publication pp
          left join pg_publication_tables ppt
            on pp.pubname = ppt.pubname
        where
          pp.pubname = publication
        group by
          pp.pubname
        limit 1
      ),
      w2j as (
        select
          x.*, pub.w2j_add_tables
        from
          pub,
          pg_logical_slot_get_changes(
            slot_name, null, max_changes,
            'include-pk', 'true',
            'include-transaction', 'false',
            'include-timestamp', 'true',
            'include-type-oids', 'true',
            'format-version', '2',
            'actions', pub.w2j_actions,
            'add-tables', pub.w2j_add_tables
          ) x
      )
      select
        xyz.wal,
        xyz.is_rls_enabled,
        xyz.subscription_ids,
        xyz.errors
      from
        w2j,
        realtime.apply_rls(
          wal := w2j.data::jsonb,
          max_record_bytes := max_record_bytes
        ) xyz(wal, is_rls_enabled, subscription_ids, errors)
      where
        w2j.w2j_add_tables <> ''
        and xyz.subscription_ids[1] is not null
    $$;


ALTER FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) OWNER TO supabase_admin;

--
-- Name: quote_wal2json(regclass); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
--

CREATE FUNCTION realtime.quote_wal2json(entity regclass) RETURNS text
    LANGUAGE sql IMMUTABLE STRICT
    AS $$
      select
        (
          select string_agg('' || ch,'')
          from unnest(string_to_array(nsp.nspname::text, null)) with ordinality x(ch, idx)
          where
            not (x.idx = 1 and x.ch = '"')
            and not (
              x.idx = array_length(string_to_array(nsp.nspname::text, null), 1)
              and x.ch = '"'
            )
        )
        || '.'
        || (
          select string_agg('' || ch,'')
          from unnest(string_to_array(pc.relname::text, null)) with ordinality x(ch, idx)
          where
            not (x.idx = 1 and x.ch = '"')
            and not (
              x.idx = array_length(string_to_array(nsp.nspname::text, null), 1)
              and x.ch = '"'
            )
          )
      from
        pg_class pc
        join pg_namespace nsp
          on pc.relnamespace = nsp.oid
      where
        pc.oid = entity
    $$;


ALTER FUNCTION realtime.quote_wal2json(entity regclass) OWNER TO supabase_admin;

--
-- Name: send(jsonb, text, text, boolean); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
--

CREATE FUNCTION realtime.send(payload jsonb, event text, topic text, private boolean DEFAULT true) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  BEGIN
    -- Set the topic configuration
    EXECUTE format('SET LOCAL realtime.topic TO %L', topic);

    -- Attempt to insert the message
    INSERT INTO realtime.messages (payload, event, topic, private, extension)
    VALUES (payload, event, topic, private, 'broadcast');
  EXCEPTION
    WHEN OTHERS THEN
      -- Capture and notify the error
      RAISE WARNING 'ErrorSendingBroadcastMessage: %', SQLERRM;
  END;
END;
$$;


ALTER FUNCTION realtime.send(payload jsonb, event text, topic text, private boolean) OWNER TO supabase_admin;

--
-- Name: subscription_check_filters(); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
--

CREATE FUNCTION realtime.subscription_check_filters() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    /*
    Validates that the user defined filters for a subscription:
    - refer to valid columns that the claimed role may access
    - values are coercable to the correct column type
    */
    declare
        col_names text[] = coalesce(
                array_agg(c.column_name order by c.ordinal_position),
                '{}'::text[]
            )
            from
                information_schema.columns c
            where
                format('%I.%I', c.table_schema, c.table_name)::regclass = new.entity
                and pg_catalog.has_column_privilege(
                    (new.claims ->> 'role'),
                    format('%I.%I', c.table_schema, c.table_name)::regclass,
                    c.column_name,
                    'SELECT'
                );
        filter realtime.user_defined_filter;
        col_type regtype;

        in_val jsonb;
    begin
        for filter in select * from unnest(new.filters) loop
            -- Filtered column is valid
            if not filter.column_name = any(col_names) then
                raise exception 'invalid column for filter %', filter.column_name;
            end if;

            -- Type is sanitized and safe for string interpolation
            col_type = (
                select atttypid::regtype
                from pg_catalog.pg_attribute
                where attrelid = new.entity
                      and attname = filter.column_name
            );
            if col_type is null then
                raise exception 'failed to lookup type for column %', filter.column_name;
            end if;

            -- Set maximum number of entries for in filter
            if filter.op = 'in'::realtime.equality_op then
                in_val = realtime.cast(filter.value, (col_type::text || '[]')::regtype);
                if coalesce(jsonb_array_length(in_val), 0) > 100 then
                    raise exception 'too many values for `in` filter. Maximum 100';
                end if;
            else
                -- raises an exception if value is not coercable to type
                perform realtime.cast(filter.value, col_type);
            end if;

        end loop;

        -- Apply consistent order to filters so the unique constraint on
        -- (subscription_id, entity, filters) can't be tricked by a different filter order
        new.filters = coalesce(
            array_agg(f order by f.column_name, f.op, f.value),
            '{}'
        ) from unnest(new.filters) f;

        return new;
    end;
    $$;


ALTER FUNCTION realtime.subscription_check_filters() OWNER TO supabase_admin;

--
-- Name: to_regrole(text); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
--

CREATE FUNCTION realtime.to_regrole(role_name text) RETURNS regrole
    LANGUAGE sql IMMUTABLE
    AS $$ select role_name::regrole $$;


ALTER FUNCTION realtime.to_regrole(role_name text) OWNER TO supabase_admin;

--
-- Name: topic(); Type: FUNCTION; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE FUNCTION realtime.topic() RETURNS text
    LANGUAGE sql STABLE
    AS $$
select nullif(current_setting('realtime.topic', true), '')::text;
$$;


ALTER FUNCTION realtime.topic() OWNER TO supabase_realtime_admin;

--
-- Name: add_prefixes(text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.add_prefixes(_bucket_id text, _name text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    prefixes text[];
BEGIN
    prefixes := "storage"."get_prefixes"("_name");

    IF array_length(prefixes, 1) > 0 THEN
        INSERT INTO storage.prefixes (name, bucket_id)
        SELECT UNNEST(prefixes) as name, "_bucket_id" ON CONFLICT DO NOTHING;
    END IF;
END;
$$;


ALTER FUNCTION storage.add_prefixes(_bucket_id text, _name text) OWNER TO supabase_storage_admin;

--
-- Name: can_insert_object(text, text, uuid, jsonb); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.can_insert_object(bucketid text, name text, owner uuid, metadata jsonb) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  INSERT INTO "storage"."objects" ("bucket_id", "name", "owner", "metadata") VALUES (bucketid, name, owner, metadata);
  -- hack to rollback the successful insert
  RAISE sqlstate 'PT200' using
  message = 'ROLLBACK',
  detail = 'rollback successful insert';
END
$$;


ALTER FUNCTION storage.can_insert_object(bucketid text, name text, owner uuid, metadata jsonb) OWNER TO supabase_storage_admin;

--
-- Name: delete_leaf_prefixes(text[], text[]); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.delete_leaf_prefixes(bucket_ids text[], names text[]) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_rows_deleted integer;
BEGIN
    LOOP
        WITH candidates AS (
            SELECT DISTINCT
                t.bucket_id,
                unnest(storage.get_prefixes(t.name)) AS name
            FROM unnest(bucket_ids, names) AS t(bucket_id, name)
        ),
        uniq AS (
             SELECT
                 bucket_id,
                 name,
                 storage.get_level(name) AS level
             FROM candidates
             WHERE name <> ''
             GROUP BY bucket_id, name
        ),
        leaf AS (
             SELECT
                 p.bucket_id,
                 p.name,
                 p.level
             FROM storage.prefixes AS p
                  JOIN uniq AS u
                       ON u.bucket_id = p.bucket_id
                           AND u.name = p.name
                           AND u.level = p.level
             WHERE NOT EXISTS (
                 SELECT 1
                 FROM storage.objects AS o
                 WHERE o.bucket_id = p.bucket_id
                   AND o.level = p.level + 1
                   AND o.name COLLATE "C" LIKE p.name || '/%'
             )
             AND NOT EXISTS (
                 SELECT 1
                 FROM storage.prefixes AS c
                 WHERE c.bucket_id = p.bucket_id
                   AND c.level = p.level + 1
                   AND c.name COLLATE "C" LIKE p.name || '/%'
             )
        )
        DELETE
        FROM storage.prefixes AS p
            USING leaf AS l
        WHERE p.bucket_id = l.bucket_id
          AND p.name = l.name
          AND p.level = l.level;

        GET DIAGNOSTICS v_rows_deleted = ROW_COUNT;
        EXIT WHEN v_rows_deleted = 0;
    END LOOP;
END;
$$;


ALTER FUNCTION storage.delete_leaf_prefixes(bucket_ids text[], names text[]) OWNER TO supabase_storage_admin;

--
-- Name: delete_prefix(text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.delete_prefix(_bucket_id text, _name text) RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
    -- Check if we can delete the prefix
    IF EXISTS(
        SELECT FROM "storage"."prefixes"
        WHERE "prefixes"."bucket_id" = "_bucket_id"
          AND level = "storage"."get_level"("_name") + 1
          AND "prefixes"."name" COLLATE "C" LIKE "_name" || '/%'
        LIMIT 1
    )
    OR EXISTS(
        SELECT FROM "storage"."objects"
        WHERE "objects"."bucket_id" = "_bucket_id"
          AND "storage"."get_level"("objects"."name") = "storage"."get_level"("_name") + 1
          AND "objects"."name" COLLATE "C" LIKE "_name" || '/%'
        LIMIT 1
    ) THEN
    -- There are sub-objects, skip deletion
    RETURN false;
    ELSE
        DELETE FROM "storage"."prefixes"
        WHERE "prefixes"."bucket_id" = "_bucket_id"
          AND level = "storage"."get_level"("_name")
          AND "prefixes"."name" = "_name";
        RETURN true;
    END IF;
END;
$$;


ALTER FUNCTION storage.delete_prefix(_bucket_id text, _name text) OWNER TO supabase_storage_admin;

--
-- Name: delete_prefix_hierarchy_trigger(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.delete_prefix_hierarchy_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    prefix text;
BEGIN
    prefix := "storage"."get_prefix"(OLD."name");

    IF coalesce(prefix, '') != '' THEN
        PERFORM "storage"."delete_prefix"(OLD."bucket_id", prefix);
    END IF;

    RETURN OLD;
END;
$$;


ALTER FUNCTION storage.delete_prefix_hierarchy_trigger() OWNER TO supabase_storage_admin;

--
-- Name: enforce_bucket_name_length(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.enforce_bucket_name_length() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin
    if length(new.name) > 100 then
        raise exception 'bucket name "%" is too long (% characters). Max is 100.', new.name, length(new.name);
    end if;
    return new;
end;
$$;


ALTER FUNCTION storage.enforce_bucket_name_length() OWNER TO supabase_storage_admin;

--
-- Name: extension(text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.extension(name text) RETURNS text
    LANGUAGE plpgsql IMMUTABLE
    AS $$
DECLARE
    _parts text[];
    _filename text;
BEGIN
    SELECT string_to_array(name, '/') INTO _parts;
    SELECT _parts[array_length(_parts,1)] INTO _filename;
    RETURN reverse(split_part(reverse(_filename), '.', 1));
END
$$;


ALTER FUNCTION storage.extension(name text) OWNER TO supabase_storage_admin;

--
-- Name: filename(text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.filename(name text) RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
_parts text[];
BEGIN
	select string_to_array(name, '/') into _parts;
	return _parts[array_length(_parts,1)];
END
$$;


ALTER FUNCTION storage.filename(name text) OWNER TO supabase_storage_admin;

--
-- Name: foldername(text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.foldername(name text) RETURNS text[]
    LANGUAGE plpgsql IMMUTABLE
    AS $$
DECLARE
    _parts text[];
BEGIN
    -- Split on "/" to get path segments
    SELECT string_to_array(name, '/') INTO _parts;
    -- Return everything except the last segment
    RETURN _parts[1 : array_length(_parts,1) - 1];
END
$$;


ALTER FUNCTION storage.foldername(name text) OWNER TO supabase_storage_admin;

--
-- Name: get_level(text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.get_level(name text) RETURNS integer
    LANGUAGE sql IMMUTABLE STRICT
    AS $$
SELECT array_length(string_to_array("name", '/'), 1);
$$;


ALTER FUNCTION storage.get_level(name text) OWNER TO supabase_storage_admin;

--
-- Name: get_prefix(text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.get_prefix(name text) RETURNS text
    LANGUAGE sql IMMUTABLE STRICT
    AS $_$
SELECT
    CASE WHEN strpos("name", '/') > 0 THEN
             regexp_replace("name", '[\/]{1}[^\/]+\/?$', '')
         ELSE
             ''
        END;
$_$;


ALTER FUNCTION storage.get_prefix(name text) OWNER TO supabase_storage_admin;

--
-- Name: get_prefixes(text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.get_prefixes(name text) RETURNS text[]
    LANGUAGE plpgsql IMMUTABLE STRICT
    AS $$
DECLARE
    parts text[];
    prefixes text[];
    prefix text;
BEGIN
    -- Split the name into parts by '/'
    parts := string_to_array("name", '/');
    prefixes := '{}';

    -- Construct the prefixes, stopping one level below the last part
    FOR i IN 1..array_length(parts, 1) - 1 LOOP
            prefix := array_to_string(parts[1:i], '/');
            prefixes := array_append(prefixes, prefix);
    END LOOP;

    RETURN prefixes;
END;
$$;


ALTER FUNCTION storage.get_prefixes(name text) OWNER TO supabase_storage_admin;

--
-- Name: get_size_by_bucket(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.get_size_by_bucket() RETURNS TABLE(size bigint, bucket_id text)
    LANGUAGE plpgsql STABLE
    AS $$
BEGIN
    return query
        select sum((metadata->>'size')::bigint) as size, obj.bucket_id
        from "storage".objects as obj
        group by obj.bucket_id;
END
$$;


ALTER FUNCTION storage.get_size_by_bucket() OWNER TO supabase_storage_admin;

--
-- Name: list_multipart_uploads_with_delimiter(text, text, text, integer, text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.list_multipart_uploads_with_delimiter(bucket_id text, prefix_param text, delimiter_param text, max_keys integer DEFAULT 100, next_key_token text DEFAULT ''::text, next_upload_token text DEFAULT ''::text) RETURNS TABLE(key text, id text, created_at timestamp with time zone)
    LANGUAGE plpgsql
    AS $_$
BEGIN
    RETURN QUERY EXECUTE
        'SELECT DISTINCT ON(key COLLATE "C") * from (
            SELECT
                CASE
                    WHEN position($2 IN substring(key from length($1) + 1)) > 0 THEN
                        substring(key from 1 for length($1) + position($2 IN substring(key from length($1) + 1)))
                    ELSE
                        key
                END AS key, id, created_at
            FROM
                storage.s3_multipart_uploads
            WHERE
                bucket_id = $5 AND
                key ILIKE $1 || ''%'' AND
                CASE
                    WHEN $4 != '''' AND $6 = '''' THEN
                        CASE
                            WHEN position($2 IN substring(key from length($1) + 1)) > 0 THEN
                                substring(key from 1 for length($1) + position($2 IN substring(key from length($1) + 1))) COLLATE "C" > $4
                            ELSE
                                key COLLATE "C" > $4
                            END
                    ELSE
                        true
                END AND
                CASE
                    WHEN $6 != '''' THEN
                        id COLLATE "C" > $6
                    ELSE
                        true
                    END
            ORDER BY
                key COLLATE "C" ASC, created_at ASC) as e order by key COLLATE "C" LIMIT $3'
        USING prefix_param, delimiter_param, max_keys, next_key_token, bucket_id, next_upload_token;
END;
$_$;


ALTER FUNCTION storage.list_multipart_uploads_with_delimiter(bucket_id text, prefix_param text, delimiter_param text, max_keys integer, next_key_token text, next_upload_token text) OWNER TO supabase_storage_admin;

--
-- Name: list_objects_with_delimiter(text, text, text, integer, text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.list_objects_with_delimiter(bucket_id text, prefix_param text, delimiter_param text, max_keys integer DEFAULT 100, start_after text DEFAULT ''::text, next_token text DEFAULT ''::text) RETURNS TABLE(name text, id uuid, metadata jsonb, updated_at timestamp with time zone)
    LANGUAGE plpgsql
    AS $_$
BEGIN
    RETURN QUERY EXECUTE
        'SELECT DISTINCT ON(name COLLATE "C") * from (
            SELECT
                CASE
                    WHEN position($2 IN substring(name from length($1) + 1)) > 0 THEN
                        substring(name from 1 for length($1) + position($2 IN substring(name from length($1) + 1)))
                    ELSE
                        name
                END AS name, id, metadata, updated_at
            FROM
                storage.objects
            WHERE
                bucket_id = $5 AND
                name ILIKE $1 || ''%'' AND
                CASE
                    WHEN $6 != '''' THEN
                    name COLLATE "C" > $6
                ELSE true END
                AND CASE
                    WHEN $4 != '''' THEN
                        CASE
                            WHEN position($2 IN substring(name from length($1) + 1)) > 0 THEN
                                substring(name from 1 for length($1) + position($2 IN substring(name from length($1) + 1))) COLLATE "C" > $4
                            ELSE
                                name COLLATE "C" > $4
                            END
                    ELSE
                        true
                END
            ORDER BY
                name COLLATE "C" ASC) as e order by name COLLATE "C" LIMIT $3'
        USING prefix_param, delimiter_param, max_keys, next_token, bucket_id, start_after;
END;
$_$;


ALTER FUNCTION storage.list_objects_with_delimiter(bucket_id text, prefix_param text, delimiter_param text, max_keys integer, start_after text, next_token text) OWNER TO supabase_storage_admin;

--
-- Name: lock_top_prefixes(text[], text[]); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.lock_top_prefixes(bucket_ids text[], names text[]) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_bucket text;
    v_top text;
BEGIN
    FOR v_bucket, v_top IN
        SELECT DISTINCT t.bucket_id,
            split_part(t.name, '/', 1) AS top
        FROM unnest(bucket_ids, names) AS t(bucket_id, name)
        WHERE t.name <> ''
        ORDER BY 1, 2
        LOOP
            PERFORM pg_advisory_xact_lock(hashtextextended(v_bucket || '/' || v_top, 0));
        END LOOP;
END;
$$;


ALTER FUNCTION storage.lock_top_prefixes(bucket_ids text[], names text[]) OWNER TO supabase_storage_admin;

--
-- Name: objects_delete_cleanup(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.objects_delete_cleanup() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_bucket_ids text[];
    v_names      text[];
BEGIN
    IF current_setting('storage.gc.prefixes', true) = '1' THEN
        RETURN NULL;
    END IF;

    PERFORM set_config('storage.gc.prefixes', '1', true);

    SELECT COALESCE(array_agg(d.bucket_id), '{}'),
           COALESCE(array_agg(d.name), '{}')
    INTO v_bucket_ids, v_names
    FROM deleted AS d
    WHERE d.name <> '';

    PERFORM storage.lock_top_prefixes(v_bucket_ids, v_names);
    PERFORM storage.delete_leaf_prefixes(v_bucket_ids, v_names);

    RETURN NULL;
END;
$$;


ALTER FUNCTION storage.objects_delete_cleanup() OWNER TO supabase_storage_admin;

--
-- Name: objects_insert_prefix_trigger(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.objects_insert_prefix_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    PERFORM "storage"."add_prefixes"(NEW."bucket_id", NEW."name");
    NEW.level := "storage"."get_level"(NEW."name");

    RETURN NEW;
END;
$$;


ALTER FUNCTION storage.objects_insert_prefix_trigger() OWNER TO supabase_storage_admin;

--
-- Name: objects_update_cleanup(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.objects_update_cleanup() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    -- NEW - OLD (destinations to create prefixes for)
    v_add_bucket_ids text[];
    v_add_names      text[];

    -- OLD - NEW (sources to prune)
    v_src_bucket_ids text[];
    v_src_names      text[];
BEGIN
    IF TG_OP <> 'UPDATE' THEN
        RETURN NULL;
    END IF;

    -- 1) Compute NEW−OLD (added paths) and OLD−NEW (moved-away paths)
    WITH added AS (
        SELECT n.bucket_id, n.name
        FROM new_rows n
        WHERE n.name <> '' AND position('/' in n.name) > 0
        EXCEPT
        SELECT o.bucket_id, o.name FROM old_rows o WHERE o.name <> ''
    ),
    moved AS (
         SELECT o.bucket_id, o.name
         FROM old_rows o
         WHERE o.name <> ''
         EXCEPT
         SELECT n.bucket_id, n.name FROM new_rows n WHERE n.name <> ''
    )
    SELECT
        -- arrays for ADDED (dest) in stable order
        COALESCE( (SELECT array_agg(a.bucket_id ORDER BY a.bucket_id, a.name) FROM added a), '{}' ),
        COALESCE( (SELECT array_agg(a.name      ORDER BY a.bucket_id, a.name) FROM added a), '{}' ),
        -- arrays for MOVED (src) in stable order
        COALESCE( (SELECT array_agg(m.bucket_id ORDER BY m.bucket_id, m.name) FROM moved m), '{}' ),
        COALESCE( (SELECT array_agg(m.name      ORDER BY m.bucket_id, m.name) FROM moved m), '{}' )
    INTO v_add_bucket_ids, v_add_names, v_src_bucket_ids, v_src_names;

    -- Nothing to do?
    IF (array_length(v_add_bucket_ids, 1) IS NULL) AND (array_length(v_src_bucket_ids, 1) IS NULL) THEN
        RETURN NULL;
    END IF;

    -- 2) Take per-(bucket, top) locks: ALL prefixes in consistent global order to prevent deadlocks
    DECLARE
        v_all_bucket_ids text[];
        v_all_names text[];
    BEGIN
        -- Combine source and destination arrays for consistent lock ordering
        v_all_bucket_ids := COALESCE(v_src_bucket_ids, '{}') || COALESCE(v_add_bucket_ids, '{}');
        v_all_names := COALESCE(v_src_names, '{}') || COALESCE(v_add_names, '{}');

        -- Single lock call ensures consistent global ordering across all transactions
        IF array_length(v_all_bucket_ids, 1) IS NOT NULL THEN
            PERFORM storage.lock_top_prefixes(v_all_bucket_ids, v_all_names);
        END IF;
    END;

    -- 3) Create destination prefixes (NEW−OLD) BEFORE pruning sources
    IF array_length(v_add_bucket_ids, 1) IS NOT NULL THEN
        WITH candidates AS (
            SELECT DISTINCT t.bucket_id, unnest(storage.get_prefixes(t.name)) AS name
            FROM unnest(v_add_bucket_ids, v_add_names) AS t(bucket_id, name)
            WHERE name <> ''
        )
        INSERT INTO storage.prefixes (bucket_id, name)
        SELECT c.bucket_id, c.name
        FROM candidates c
        ON CONFLICT DO NOTHING;
    END IF;

    -- 4) Prune source prefixes bottom-up for OLD−NEW
    IF array_length(v_src_bucket_ids, 1) IS NOT NULL THEN
        -- re-entrancy guard so DELETE on prefixes won't recurse
        IF current_setting('storage.gc.prefixes', true) <> '1' THEN
            PERFORM set_config('storage.gc.prefixes', '1', true);
        END IF;

        PERFORM storage.delete_leaf_prefixes(v_src_bucket_ids, v_src_names);
    END IF;

    RETURN NULL;
END;
$$;


ALTER FUNCTION storage.objects_update_cleanup() OWNER TO supabase_storage_admin;

--
-- Name: objects_update_level_trigger(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.objects_update_level_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Ensure this is an update operation and the name has changed
    IF TG_OP = 'UPDATE' AND (NEW."name" <> OLD."name" OR NEW."bucket_id" <> OLD."bucket_id") THEN
        -- Set the new level
        NEW."level" := "storage"."get_level"(NEW."name");
    END IF;
    RETURN NEW;
END;
$$;


ALTER FUNCTION storage.objects_update_level_trigger() OWNER TO supabase_storage_admin;

--
-- Name: objects_update_prefix_trigger(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.objects_update_prefix_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    old_prefixes TEXT[];
BEGIN
    -- Ensure this is an update operation and the name has changed
    IF TG_OP = 'UPDATE' AND (NEW."name" <> OLD."name" OR NEW."bucket_id" <> OLD."bucket_id") THEN
        -- Retrieve old prefixes
        old_prefixes := "storage"."get_prefixes"(OLD."name");

        -- Remove old prefixes that are only used by this object
        WITH all_prefixes as (
            SELECT unnest(old_prefixes) as prefix
        ),
        can_delete_prefixes as (
             SELECT prefix
             FROM all_prefixes
             WHERE NOT EXISTS (
                 SELECT 1 FROM "storage"."objects"
                 WHERE "bucket_id" = OLD."bucket_id"
                   AND "name" <> OLD."name"
                   AND "name" LIKE (prefix || '%')
             )
         )
        DELETE FROM "storage"."prefixes" WHERE name IN (SELECT prefix FROM can_delete_prefixes);

        -- Add new prefixes
        PERFORM "storage"."add_prefixes"(NEW."bucket_id", NEW."name");
    END IF;
    -- Set the new level
    NEW."level" := "storage"."get_level"(NEW."name");

    RETURN NEW;
END;
$$;


ALTER FUNCTION storage.objects_update_prefix_trigger() OWNER TO supabase_storage_admin;

--
-- Name: operation(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.operation() RETURNS text
    LANGUAGE plpgsql STABLE
    AS $$
BEGIN
    RETURN current_setting('storage.operation', true);
END;
$$;


ALTER FUNCTION storage.operation() OWNER TO supabase_storage_admin;

--
-- Name: prefixes_delete_cleanup(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.prefixes_delete_cleanup() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_bucket_ids text[];
    v_names      text[];
BEGIN
    IF current_setting('storage.gc.prefixes', true) = '1' THEN
        RETURN NULL;
    END IF;

    PERFORM set_config('storage.gc.prefixes', '1', true);

    SELECT COALESCE(array_agg(d.bucket_id), '{}'),
           COALESCE(array_agg(d.name), '{}')
    INTO v_bucket_ids, v_names
    FROM deleted AS d
    WHERE d.name <> '';

    PERFORM storage.lock_top_prefixes(v_bucket_ids, v_names);
    PERFORM storage.delete_leaf_prefixes(v_bucket_ids, v_names);

    RETURN NULL;
END;
$$;


ALTER FUNCTION storage.prefixes_delete_cleanup() OWNER TO supabase_storage_admin;

--
-- Name: prefixes_insert_trigger(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.prefixes_insert_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    PERFORM "storage"."add_prefixes"(NEW."bucket_id", NEW."name");
    RETURN NEW;
END;
$$;


ALTER FUNCTION storage.prefixes_insert_trigger() OWNER TO supabase_storage_admin;

--
-- Name: search(text, text, integer, integer, integer, text, text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.search(prefix text, bucketname text, limits integer DEFAULT 100, levels integer DEFAULT 1, offsets integer DEFAULT 0, search text DEFAULT ''::text, sortcolumn text DEFAULT 'name'::text, sortorder text DEFAULT 'asc'::text) RETURNS TABLE(name text, id uuid, updated_at timestamp with time zone, created_at timestamp with time zone, last_accessed_at timestamp with time zone, metadata jsonb)
    LANGUAGE plpgsql
    AS $$
declare
    can_bypass_rls BOOLEAN;
begin
    SELECT rolbypassrls
    INTO can_bypass_rls
    FROM pg_roles
    WHERE rolname = coalesce(nullif(current_setting('role', true), 'none'), current_user);

    IF can_bypass_rls THEN
        RETURN QUERY SELECT * FROM storage.search_v1_optimised(prefix, bucketname, limits, levels, offsets, search, sortcolumn, sortorder);
    ELSE
        RETURN QUERY SELECT * FROM storage.search_legacy_v1(prefix, bucketname, limits, levels, offsets, search, sortcolumn, sortorder);
    END IF;
end;
$$;


ALTER FUNCTION storage.search(prefix text, bucketname text, limits integer, levels integer, offsets integer, search text, sortcolumn text, sortorder text) OWNER TO supabase_storage_admin;

--
-- Name: search_legacy_v1(text, text, integer, integer, integer, text, text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.search_legacy_v1(prefix text, bucketname text, limits integer DEFAULT 100, levels integer DEFAULT 1, offsets integer DEFAULT 0, search text DEFAULT ''::text, sortcolumn text DEFAULT 'name'::text, sortorder text DEFAULT 'asc'::text) RETURNS TABLE(name text, id uuid, updated_at timestamp with time zone, created_at timestamp with time zone, last_accessed_at timestamp with time zone, metadata jsonb)
    LANGUAGE plpgsql STABLE
    AS $_$
declare
    v_order_by text;
    v_sort_order text;
begin
    case
        when sortcolumn = 'name' then
            v_order_by = 'name';
        when sortcolumn = 'updated_at' then
            v_order_by = 'updated_at';
        when sortcolumn = 'created_at' then
            v_order_by = 'created_at';
        when sortcolumn = 'last_accessed_at' then
            v_order_by = 'last_accessed_at';
        else
            v_order_by = 'name';
        end case;

    case
        when sortorder = 'asc' then
            v_sort_order = 'asc';
        when sortorder = 'desc' then
            v_sort_order = 'desc';
        else
            v_sort_order = 'asc';
        end case;

    v_order_by = v_order_by || ' ' || v_sort_order;

    return query execute
        'with folders as (
           select path_tokens[$1] as folder
           from storage.objects
             where objects.name ilike $2 || $3 || ''%''
               and bucket_id = $4
               and array_length(objects.path_tokens, 1) <> $1
           group by folder
           order by folder ' || v_sort_order || '
     )
     (select folder as "name",
            null as id,
            null as updated_at,
            null as created_at,
            null as last_accessed_at,
            null as metadata from folders)
     union all
     (select path_tokens[$1] as "name",
            id,
            updated_at,
            created_at,
            last_accessed_at,
            metadata
     from storage.objects
     where objects.name ilike $2 || $3 || ''%''
       and bucket_id = $4
       and array_length(objects.path_tokens, 1) = $1
     order by ' || v_order_by || ')
     limit $5
     offset $6' using levels, prefix, search, bucketname, limits, offsets;
end;
$_$;


ALTER FUNCTION storage.search_legacy_v1(prefix text, bucketname text, limits integer, levels integer, offsets integer, search text, sortcolumn text, sortorder text) OWNER TO supabase_storage_admin;

--
-- Name: search_v1_optimised(text, text, integer, integer, integer, text, text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.search_v1_optimised(prefix text, bucketname text, limits integer DEFAULT 100, levels integer DEFAULT 1, offsets integer DEFAULT 0, search text DEFAULT ''::text, sortcolumn text DEFAULT 'name'::text, sortorder text DEFAULT 'asc'::text) RETURNS TABLE(name text, id uuid, updated_at timestamp with time zone, created_at timestamp with time zone, last_accessed_at timestamp with time zone, metadata jsonb)
    LANGUAGE plpgsql STABLE
    AS $_$
declare
    v_order_by text;
    v_sort_order text;
begin
    case
        when sortcolumn = 'name' then
            v_order_by = 'name';
        when sortcolumn = 'updated_at' then
            v_order_by = 'updated_at';
        when sortcolumn = 'created_at' then
            v_order_by = 'created_at';
        when sortcolumn = 'last_accessed_at' then
            v_order_by = 'last_accessed_at';
        else
            v_order_by = 'name';
        end case;

    case
        when sortorder = 'asc' then
            v_sort_order = 'asc';
        when sortorder = 'desc' then
            v_sort_order = 'desc';
        else
            v_sort_order = 'asc';
        end case;

    v_order_by = v_order_by || ' ' || v_sort_order;

    return query execute
        'with folders as (
           select (string_to_array(name, ''/''))[level] as name
           from storage.prefixes
             where lower(prefixes.name) like lower($2 || $3) || ''%''
               and bucket_id = $4
               and level = $1
           order by name ' || v_sort_order || '
     )
     (select name,
            null as id,
            null as updated_at,
            null as created_at,
            null as last_accessed_at,
            null as metadata from folders)
     union all
     (select path_tokens[level] as "name",
            id,
            updated_at,
            created_at,
            last_accessed_at,
            metadata
     from storage.objects
     where lower(objects.name) like lower($2 || $3) || ''%''
       and bucket_id = $4
       and level = $1
     order by ' || v_order_by || ')
     limit $5
     offset $6' using levels, prefix, search, bucketname, limits, offsets;
end;
$_$;


ALTER FUNCTION storage.search_v1_optimised(prefix text, bucketname text, limits integer, levels integer, offsets integer, search text, sortcolumn text, sortorder text) OWNER TO supabase_storage_admin;

--
-- Name: search_v2(text, text, integer, integer, text, text, text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.search_v2(prefix text, bucket_name text, limits integer DEFAULT 100, levels integer DEFAULT 1, start_after text DEFAULT ''::text, sort_order text DEFAULT 'asc'::text, sort_column text DEFAULT 'name'::text, sort_column_after text DEFAULT ''::text) RETURNS TABLE(key text, name text, id uuid, updated_at timestamp with time zone, created_at timestamp with time zone, last_accessed_at timestamp with time zone, metadata jsonb)
    LANGUAGE plpgsql STABLE
    AS $_$
DECLARE
    sort_col text;
    sort_ord text;
    cursor_op text;
    cursor_expr text;
    sort_expr text;
BEGIN
    -- Validate sort_order
    sort_ord := lower(sort_order);
    IF sort_ord NOT IN ('asc', 'desc') THEN
        sort_ord := 'asc';
    END IF;

    -- Determine cursor comparison operator
    IF sort_ord = 'asc' THEN
        cursor_op := '>';
    ELSE
        cursor_op := '<';
    END IF;
    
    sort_col := lower(sort_column);
    -- Validate sort column  
    IF sort_col IN ('updated_at', 'created_at') THEN
        cursor_expr := format(
            '($5 = '''' OR ROW(date_trunc(''milliseconds'', %I), name COLLATE "C") %s ROW(COALESCE(NULLIF($6, '''')::timestamptz, ''epoch''::timestamptz), $5))',
            sort_col, cursor_op
        );
        sort_expr := format(
            'COALESCE(date_trunc(''milliseconds'', %I), ''epoch''::timestamptz) %s, name COLLATE "C" %s',
            sort_col, sort_ord, sort_ord
        );
    ELSE
        cursor_expr := format('($5 = '''' OR name COLLATE "C" %s $5)', cursor_op);
        sort_expr := format('name COLLATE "C" %s', sort_ord);
    END IF;

    RETURN QUERY EXECUTE format(
        $sql$
        SELECT * FROM (
            (
                SELECT
                    split_part(name, '/', $4) AS key,
                    name,
                    NULL::uuid AS id,
                    updated_at,
                    created_at,
                    NULL::timestamptz AS last_accessed_at,
                    NULL::jsonb AS metadata
                FROM storage.prefixes
                WHERE name COLLATE "C" LIKE $1 || '%%'
                    AND bucket_id = $2
                    AND level = $4
                    AND %s
                ORDER BY %s
                LIMIT $3
            )
            UNION ALL
            (
                SELECT
                    split_part(name, '/', $4) AS key,
                    name,
                    id,
                    updated_at,
                    created_at,
                    last_accessed_at,
                    metadata
                FROM storage.objects
                WHERE name COLLATE "C" LIKE $1 || '%%'
                    AND bucket_id = $2
                    AND level = $4
                    AND %s
                ORDER BY %s
                LIMIT $3
            )
        ) obj
        ORDER BY %s
        LIMIT $3
        $sql$,
        cursor_expr,    -- prefixes WHERE
        sort_expr,      -- prefixes ORDER BY
        cursor_expr,    -- objects WHERE
        sort_expr,      -- objects ORDER BY
        sort_expr       -- final ORDER BY
    )
    USING prefix, bucket_name, limits, levels, start_after, sort_column_after;
END;
$_$;


ALTER FUNCTION storage.search_v2(prefix text, bucket_name text, limits integer, levels integer, start_after text, sort_order text, sort_column text, sort_column_after text) OWNER TO supabase_storage_admin;

--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW; 
END;
$$;


ALTER FUNCTION storage.update_updated_at_column() OWNER TO supabase_storage_admin;

--
-- Name: http_request(); Type: FUNCTION; Schema: supabase_functions; Owner: supabase_functions_admin
--

CREATE FUNCTION supabase_functions.http_request() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'supabase_functions'
    AS $$
  DECLARE
    request_id bigint;
    payload jsonb;
    url text := TG_ARGV[0]::text;
    method text := TG_ARGV[1]::text;
    headers jsonb DEFAULT '{}'::jsonb;
    params jsonb DEFAULT '{}'::jsonb;
    timeout_ms integer DEFAULT 1000;
  BEGIN
    IF url IS NULL OR url = 'null' THEN
      RAISE EXCEPTION 'url argument is missing';
    END IF;

    IF method IS NULL OR method = 'null' THEN
      RAISE EXCEPTION 'method argument is missing';
    END IF;

    IF TG_ARGV[2] IS NULL OR TG_ARGV[2] = 'null' THEN
      headers = '{"Content-Type": "application/json"}'::jsonb;
    ELSE
      headers = TG_ARGV[2]::jsonb;
    END IF;

    IF TG_ARGV[3] IS NULL OR TG_ARGV[3] = 'null' THEN
      params = '{}'::jsonb;
    ELSE
      params = TG_ARGV[3]::jsonb;
    END IF;

    IF TG_ARGV[4] IS NULL OR TG_ARGV[4] = 'null' THEN
      timeout_ms = 1000;
    ELSE
      timeout_ms = TG_ARGV[4]::integer;
    END IF;

    CASE
      WHEN method = 'GET' THEN
        SELECT http_get INTO request_id FROM net.http_get(
          url,
          params,
          headers,
          timeout_ms
        );
      WHEN method = 'POST' THEN
        payload = jsonb_build_object(
          'old_record', OLD,
          'record', NEW,
          'type', TG_OP,
          'table', TG_TABLE_NAME,
          'schema', TG_TABLE_SCHEMA
        );

        SELECT http_post INTO request_id FROM net.http_post(
          url,
          payload,
          params,
          headers,
          timeout_ms
        );
      ELSE
        RAISE EXCEPTION 'method argument % is invalid', method;
    END CASE;

    INSERT INTO supabase_functions.hooks
      (hook_table_id, hook_name, request_id)
    VALUES
      (TG_RELID, TG_NAME, request_id);

    RETURN NEW;
  END
$$;


ALTER FUNCTION supabase_functions.http_request() OWNER TO supabase_functions_admin;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: extensions; Type: TABLE; Schema: _realtime; Owner: supabase_admin
--

CREATE TABLE _realtime.extensions (
    id uuid NOT NULL,
    type text,
    settings jsonb,
    tenant_external_id text,
    inserted_at timestamp(0) without time zone NOT NULL,
    updated_at timestamp(0) without time zone NOT NULL
);


ALTER TABLE _realtime.extensions OWNER TO supabase_admin;

--
-- Name: schema_migrations; Type: TABLE; Schema: _realtime; Owner: supabase_admin
--

CREATE TABLE _realtime.schema_migrations (
    version bigint NOT NULL,
    inserted_at timestamp(0) without time zone
);


ALTER TABLE _realtime.schema_migrations OWNER TO supabase_admin;

--
-- Name: tenants; Type: TABLE; Schema: _realtime; Owner: supabase_admin
--

CREATE TABLE _realtime.tenants (
    id uuid NOT NULL,
    name text,
    external_id text,
    jwt_secret text,
    max_concurrent_users integer DEFAULT 200 NOT NULL,
    inserted_at timestamp(0) without time zone NOT NULL,
    updated_at timestamp(0) without time zone NOT NULL,
    max_events_per_second integer DEFAULT 100 NOT NULL,
    postgres_cdc_default text DEFAULT 'postgres_cdc_rls'::text,
    max_bytes_per_second integer DEFAULT 100000 NOT NULL,
    max_channels_per_client integer DEFAULT 100 NOT NULL,
    max_joins_per_second integer DEFAULT 500 NOT NULL,
    suspend boolean DEFAULT false,
    jwt_jwks jsonb,
    notify_private_alpha boolean DEFAULT false,
    private_only boolean DEFAULT false NOT NULL,
    migrations_ran integer DEFAULT 0,
    broadcast_adapter character varying(255) DEFAULT 'gen_rpc'::character varying,
    max_presence_events_per_second integer DEFAULT 10000,
    max_payload_size_in_kb integer DEFAULT 3000
);


ALTER TABLE _realtime.tenants OWNER TO supabase_admin;

--
-- Name: audit_log_entries; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.audit_log_entries (
    instance_id uuid,
    id uuid NOT NULL,
    payload json,
    created_at timestamp with time zone,
    ip_address character varying(64) DEFAULT ''::character varying NOT NULL
);


ALTER TABLE auth.audit_log_entries OWNER TO supabase_auth_admin;

--
-- Name: TABLE audit_log_entries; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.audit_log_entries IS 'Auth: Audit trail for user actions.';


--
-- Name: flow_state; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.flow_state (
    id uuid NOT NULL,
    user_id uuid,
    auth_code text NOT NULL,
    code_challenge_method auth.code_challenge_method NOT NULL,
    code_challenge text NOT NULL,
    provider_type text NOT NULL,
    provider_access_token text,
    provider_refresh_token text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    authentication_method text NOT NULL,
    auth_code_issued_at timestamp with time zone
);


ALTER TABLE auth.flow_state OWNER TO supabase_auth_admin;

--
-- Name: TABLE flow_state; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.flow_state IS 'stores metadata for pkce logins';


--
-- Name: identities; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.identities (
    provider_id text NOT NULL,
    user_id uuid NOT NULL,
    identity_data jsonb NOT NULL,
    provider text NOT NULL,
    last_sign_in_at timestamp with time zone,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    email text GENERATED ALWAYS AS (lower((identity_data ->> 'email'::text))) STORED,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


ALTER TABLE auth.identities OWNER TO supabase_auth_admin;

--
-- Name: TABLE identities; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.identities IS 'Auth: Stores identities associated to a user.';


--
-- Name: COLUMN identities.email; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON COLUMN auth.identities.email IS 'Auth: Email is a generated column that references the optional email property in the identity_data';


--
-- Name: instances; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.instances (
    id uuid NOT NULL,
    uuid uuid,
    raw_base_config text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);


ALTER TABLE auth.instances OWNER TO supabase_auth_admin;

--
-- Name: TABLE instances; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.instances IS 'Auth: Manages users across multiple sites.';


--
-- Name: mfa_amr_claims; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.mfa_amr_claims (
    session_id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    authentication_method text NOT NULL,
    id uuid NOT NULL
);


ALTER TABLE auth.mfa_amr_claims OWNER TO supabase_auth_admin;

--
-- Name: TABLE mfa_amr_claims; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.mfa_amr_claims IS 'auth: stores authenticator method reference claims for multi factor authentication';


--
-- Name: mfa_challenges; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.mfa_challenges (
    id uuid NOT NULL,
    factor_id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    verified_at timestamp with time zone,
    ip_address inet NOT NULL,
    otp_code text,
    web_authn_session_data jsonb
);


ALTER TABLE auth.mfa_challenges OWNER TO supabase_auth_admin;

--
-- Name: TABLE mfa_challenges; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.mfa_challenges IS 'auth: stores metadata about challenge requests made';


--
-- Name: mfa_factors; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.mfa_factors (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    friendly_name text,
    factor_type auth.factor_type NOT NULL,
    status auth.factor_status NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    secret text,
    phone text,
    last_challenged_at timestamp with time zone,
    web_authn_credential jsonb,
    web_authn_aaguid uuid
);


ALTER TABLE auth.mfa_factors OWNER TO supabase_auth_admin;

--
-- Name: TABLE mfa_factors; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.mfa_factors IS 'auth: stores metadata about factors';


--
-- Name: oauth_authorizations; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.oauth_authorizations (
    id uuid NOT NULL,
    authorization_id text NOT NULL,
    client_id uuid NOT NULL,
    user_id uuid,
    redirect_uri text NOT NULL,
    scope text NOT NULL,
    state text,
    resource text,
    code_challenge text,
    code_challenge_method auth.code_challenge_method,
    response_type auth.oauth_response_type DEFAULT 'code'::auth.oauth_response_type NOT NULL,
    status auth.oauth_authorization_status DEFAULT 'pending'::auth.oauth_authorization_status NOT NULL,
    authorization_code text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone DEFAULT (now() + '00:03:00'::interval) NOT NULL,
    approved_at timestamp with time zone,
    CONSTRAINT oauth_authorizations_authorization_code_length CHECK ((char_length(authorization_code) <= 255)),
    CONSTRAINT oauth_authorizations_code_challenge_length CHECK ((char_length(code_challenge) <= 128)),
    CONSTRAINT oauth_authorizations_expires_at_future CHECK ((expires_at > created_at)),
    CONSTRAINT oauth_authorizations_redirect_uri_length CHECK ((char_length(redirect_uri) <= 2048)),
    CONSTRAINT oauth_authorizations_resource_length CHECK ((char_length(resource) <= 2048)),
    CONSTRAINT oauth_authorizations_scope_length CHECK ((char_length(scope) <= 4096)),
    CONSTRAINT oauth_authorizations_state_length CHECK ((char_length(state) <= 4096))
);


ALTER TABLE auth.oauth_authorizations OWNER TO supabase_auth_admin;

--
-- Name: oauth_clients; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.oauth_clients (
    id uuid NOT NULL,
    client_secret_hash text,
    registration_type auth.oauth_registration_type NOT NULL,
    redirect_uris text NOT NULL,
    grant_types text NOT NULL,
    client_name text,
    client_uri text,
    logo_uri text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    client_type auth.oauth_client_type DEFAULT 'confidential'::auth.oauth_client_type NOT NULL,
    CONSTRAINT oauth_clients_client_name_length CHECK ((char_length(client_name) <= 1024)),
    CONSTRAINT oauth_clients_client_uri_length CHECK ((char_length(client_uri) <= 2048)),
    CONSTRAINT oauth_clients_logo_uri_length CHECK ((char_length(logo_uri) <= 2048))
);


ALTER TABLE auth.oauth_clients OWNER TO supabase_auth_admin;

--
-- Name: oauth_consents; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.oauth_consents (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    client_id uuid NOT NULL,
    scopes text NOT NULL,
    granted_at timestamp with time zone DEFAULT now() NOT NULL,
    revoked_at timestamp with time zone,
    CONSTRAINT oauth_consents_revoked_after_granted CHECK (((revoked_at IS NULL) OR (revoked_at >= granted_at))),
    CONSTRAINT oauth_consents_scopes_length CHECK ((char_length(scopes) <= 2048)),
    CONSTRAINT oauth_consents_scopes_not_empty CHECK ((char_length(TRIM(BOTH FROM scopes)) > 0))
);


ALTER TABLE auth.oauth_consents OWNER TO supabase_auth_admin;

--
-- Name: one_time_tokens; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.one_time_tokens (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    token_type auth.one_time_token_type NOT NULL,
    token_hash text NOT NULL,
    relates_to text NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT one_time_tokens_token_hash_check CHECK ((char_length(token_hash) > 0))
);


ALTER TABLE auth.one_time_tokens OWNER TO supabase_auth_admin;

--
-- Name: refresh_tokens; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.refresh_tokens (
    instance_id uuid,
    id bigint NOT NULL,
    token character varying(255),
    user_id character varying(255),
    revoked boolean,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    parent character varying(255),
    session_id uuid
);


ALTER TABLE auth.refresh_tokens OWNER TO supabase_auth_admin;

--
-- Name: TABLE refresh_tokens; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.refresh_tokens IS 'Auth: Store of tokens used to refresh JWT tokens once they expire.';


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE; Schema: auth; Owner: supabase_auth_admin
--

CREATE SEQUENCE auth.refresh_tokens_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE auth.refresh_tokens_id_seq OWNER TO supabase_auth_admin;

--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: auth; Owner: supabase_auth_admin
--

ALTER SEQUENCE auth.refresh_tokens_id_seq OWNED BY auth.refresh_tokens.id;


--
-- Name: saml_providers; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.saml_providers (
    id uuid NOT NULL,
    sso_provider_id uuid NOT NULL,
    entity_id text NOT NULL,
    metadata_xml text NOT NULL,
    metadata_url text,
    attribute_mapping jsonb,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    name_id_format text,
    CONSTRAINT "entity_id not empty" CHECK ((char_length(entity_id) > 0)),
    CONSTRAINT "metadata_url not empty" CHECK (((metadata_url = NULL::text) OR (char_length(metadata_url) > 0))),
    CONSTRAINT "metadata_xml not empty" CHECK ((char_length(metadata_xml) > 0))
);


ALTER TABLE auth.saml_providers OWNER TO supabase_auth_admin;

--
-- Name: TABLE saml_providers; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.saml_providers IS 'Auth: Manages SAML Identity Provider connections.';


--
-- Name: saml_relay_states; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.saml_relay_states (
    id uuid NOT NULL,
    sso_provider_id uuid NOT NULL,
    request_id text NOT NULL,
    for_email text,
    redirect_to text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    flow_state_id uuid,
    CONSTRAINT "request_id not empty" CHECK ((char_length(request_id) > 0))
);


ALTER TABLE auth.saml_relay_states OWNER TO supabase_auth_admin;

--
-- Name: TABLE saml_relay_states; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.saml_relay_states IS 'Auth: Contains SAML Relay State information for each Service Provider initiated login.';


--
-- Name: schema_migrations; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.schema_migrations (
    version character varying(255) NOT NULL
);


ALTER TABLE auth.schema_migrations OWNER TO supabase_auth_admin;

--
-- Name: TABLE schema_migrations; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.schema_migrations IS 'Auth: Manages updates to the auth system.';


--
-- Name: sessions; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.sessions (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    factor_id uuid,
    aal auth.aal_level,
    not_after timestamp with time zone,
    refreshed_at timestamp without time zone,
    user_agent text,
    ip inet,
    tag text,
    oauth_client_id uuid
);


ALTER TABLE auth.sessions OWNER TO supabase_auth_admin;

--
-- Name: TABLE sessions; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.sessions IS 'Auth: Stores session data associated to a user.';


--
-- Name: COLUMN sessions.not_after; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON COLUMN auth.sessions.not_after IS 'Auth: Not after is a nullable column that contains a timestamp after which the session should be regarded as expired.';


--
-- Name: sso_domains; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.sso_domains (
    id uuid NOT NULL,
    sso_provider_id uuid NOT NULL,
    domain text NOT NULL,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    CONSTRAINT "domain not empty" CHECK ((char_length(domain) > 0))
);


ALTER TABLE auth.sso_domains OWNER TO supabase_auth_admin;

--
-- Name: TABLE sso_domains; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.sso_domains IS 'Auth: Manages SSO email address domain mapping to an SSO Identity Provider.';


--
-- Name: sso_providers; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.sso_providers (
    id uuid NOT NULL,
    resource_id text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    disabled boolean,
    CONSTRAINT "resource_id not empty" CHECK (((resource_id = NULL::text) OR (char_length(resource_id) > 0)))
);


ALTER TABLE auth.sso_providers OWNER TO supabase_auth_admin;

--
-- Name: TABLE sso_providers; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.sso_providers IS 'Auth: Manages SSO identity provider information; see saml_providers for SAML.';


--
-- Name: COLUMN sso_providers.resource_id; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON COLUMN auth.sso_providers.resource_id IS 'Auth: Uniquely identifies a SSO provider according to a user-chosen resource ID (case insensitive), useful in infrastructure as code.';


--
-- Name: users; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.users (
    instance_id uuid,
    id uuid NOT NULL,
    aud character varying(255),
    role character varying(255),
    email character varying(255),
    encrypted_password character varying(255),
    email_confirmed_at timestamp with time zone,
    invited_at timestamp with time zone,
    confirmation_token character varying(255),
    confirmation_sent_at timestamp with time zone,
    recovery_token character varying(255),
    recovery_sent_at timestamp with time zone,
    email_change_token_new character varying(255),
    email_change character varying(255),
    email_change_sent_at timestamp with time zone,
    last_sign_in_at timestamp with time zone,
    raw_app_meta_data jsonb,
    raw_user_meta_data jsonb,
    is_super_admin boolean,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    phone text DEFAULT NULL::character varying,
    phone_confirmed_at timestamp with time zone,
    phone_change text DEFAULT ''::character varying,
    phone_change_token character varying(255) DEFAULT ''::character varying,
    phone_change_sent_at timestamp with time zone,
    confirmed_at timestamp with time zone GENERATED ALWAYS AS (LEAST(email_confirmed_at, phone_confirmed_at)) STORED,
    email_change_token_current character varying(255) DEFAULT ''::character varying,
    email_change_confirm_status smallint DEFAULT 0,
    banned_until timestamp with time zone,
    reauthentication_token character varying(255) DEFAULT ''::character varying,
    reauthentication_sent_at timestamp with time zone,
    is_sso_user boolean DEFAULT false NOT NULL,
    deleted_at timestamp with time zone,
    is_anonymous boolean DEFAULT false NOT NULL,
    CONSTRAINT users_email_change_confirm_status_check CHECK (((email_change_confirm_status >= 0) AND (email_change_confirm_status <= 2)))
);


ALTER TABLE auth.users OWNER TO supabase_auth_admin;

--
-- Name: TABLE users; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.users IS 'Auth: Stores user login data within a secure schema.';


--
-- Name: COLUMN users.is_sso_user; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON COLUMN auth.users.is_sso_user IS 'Auth: Set this column to true when the account comes from SSO. These accounts can have duplicate emails.';


--
-- Name: mastery_tasks; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.mastery_tasks (
    task_id uuid NOT NULL,
    difficulty_level integer DEFAULT 1,
    spaced_repetition_interval integer DEFAULT 1,
    solution_hints text
);


ALTER TABLE public.mastery_tasks OWNER TO postgres;

--
-- Name: TABLE mastery_tasks; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.mastery_tasks IS 'Mastery task specific attributes. Use instruction from task_base for the task prompt.';


--
-- Name: COLUMN mastery_tasks.difficulty_level; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.mastery_tasks.difficulty_level IS 'Difficulty level (1-5) for spaced repetition';


--
-- Name: task_base; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.task_base (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    section_id uuid,
    instruction text NOT NULL,
    task_type text,
    criteria text,
    assessment_criteria jsonb,
    solution_hints text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    order_in_section integer DEFAULT 1
);


ALTER TABLE public.task_base OWNER TO postgres;

--
-- Name: TABLE task_base; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.task_base IS 'Base table for all tasks - Phase 2 of Task Type Separation. Contains shared attributes. Migrated from task table on 2025-09-03.';


--
-- Name: COLUMN task_base.instruction; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.task_base.instruction IS 'The main text/prompt of the task. This is what the student sees';


--
-- Name: COLUMN task_base.order_in_section; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.task_base.order_in_section IS 'Order within section - synchronized with regular_tasks';


--
-- Name: all_mastery_tasks; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.all_mastery_tasks AS
 SELECT t.id,
    t.section_id,
    t.instruction,
    t.task_type,
    t.order_in_section,
    t.created_at,
    t.updated_at,
    t.criteria,
    t.assessment_criteria,
    t.solution_hints,
    mt.difficulty_level,
    mt.spaced_repetition_interval,
    true AS is_mastery
   FROM (public.task_base t
     JOIN public.mastery_tasks mt ON ((mt.task_id = t.id)));


ALTER VIEW public.all_mastery_tasks OWNER TO postgres;

--
-- Name: regular_tasks; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.regular_tasks (
    task_id uuid NOT NULL,
    order_in_section integer DEFAULT 1 NOT NULL,
    max_attempts integer DEFAULT 1,
    prompt text,
    grading_criteria text[],
    solution_hints text
);


ALTER TABLE public.regular_tasks OWNER TO postgres;

--
-- Name: TABLE regular_tasks; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.regular_tasks IS 'Regular tasks with order and attempt limits - Phase 2 of Task Type Separation. Migrated from task table on 2025-09-03.';


--
-- Name: COLUMN regular_tasks.prompt; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.regular_tasks.prompt IS 'Task prompt - migrated from task_base.instruction';


--
-- Name: COLUMN regular_tasks.grading_criteria; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.regular_tasks.grading_criteria IS 'Grading criteria for automatic evaluation';


--
-- Name: all_regular_tasks; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.all_regular_tasks AS
 SELECT t.id,
    t.section_id,
    t.instruction,
    t.task_type,
    t.order_in_section,
    t.created_at,
    t.updated_at,
    t.criteria,
    t.assessment_criteria,
    t.solution_hints,
    rt.prompt,
    rt.max_attempts,
    rt.grading_criteria,
    false AS is_mastery
   FROM (public.task_base t
     JOIN public.regular_tasks rt ON ((rt.task_id = t.id)));


ALTER VIEW public.all_regular_tasks OWNER TO postgres;

--
-- Name: allowed_email_domains; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.allowed_email_domains (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    domain text NOT NULL,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);


ALTER TABLE public.allowed_email_domains OWNER TO postgres;

--
-- Name: auth_service_keys; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.auth_service_keys (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    key_hash text NOT NULL,
    name text NOT NULL,
    permissions jsonb DEFAULT '["manage_sessions"]'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    last_used_at timestamp with time zone,
    is_active boolean DEFAULT true
);


ALTER TABLE public.auth_service_keys OWNER TO postgres;

--
-- Name: auth_sessions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.auth_sessions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    session_id character varying(255) NOT NULL,
    user_id uuid NOT NULL,
    user_email text NOT NULL,
    user_role text NOT NULL,
    data jsonb DEFAULT '{}'::jsonb,
    expires_at timestamp with time zone NOT NULL,
    last_activity timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now(),
    ip_address inet,
    user_agent text,
    CONSTRAINT auth_sessions_user_role_check CHECK ((user_role = ANY (ARRAY['teacher'::text, 'student'::text, 'admin'::text]))),
    CONSTRAINT valid_expiration CHECK ((expires_at <= (created_at + '24:00:00'::interval)))
);


ALTER TABLE public.auth_sessions OWNER TO postgres;

--
-- Name: TABLE auth_sessions; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.auth_sessions IS 'Stores active user sessions for HttpOnly cookie authentication';


--
-- Name: COLUMN auth_sessions.session_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.auth_sessions.session_id IS 'Unique session identifier stored in HttpOnly cookie';


--
-- Name: COLUMN auth_sessions.user_role; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.auth_sessions.user_role IS 'User role: teacher, student, or admin';


--
-- Name: COLUMN auth_sessions.data; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.auth_sessions.data IS 'Additional session data in JSON format';


--
-- Name: COLUMN auth_sessions.expires_at; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.auth_sessions.expires_at IS 'Session expiration timestamp (max 24h from creation)';


--
-- Name: COLUMN auth_sessions.last_activity; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.auth_sessions.last_activity IS 'Last activity timestamp for sliding window timeout';


--
-- Name: COLUMN auth_sessions.ip_address; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.auth_sessions.ip_address IS 'Client IP address for security logging';


--
-- Name: COLUMN auth_sessions.user_agent; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.auth_sessions.user_agent IS 'Browser user agent for device tracking';


--
-- Name: course; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.course (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    creator_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid
);


ALTER TABLE public.course OWNER TO postgres;

--
-- Name: course_learning_unit_assignment; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.course_learning_unit_assignment (
    course_id uuid NOT NULL,
    unit_id uuid NOT NULL,
    assigned_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.course_learning_unit_assignment OWNER TO postgres;

--
-- Name: course_student; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.course_student (
    course_id uuid NOT NULL,
    student_id uuid NOT NULL,
    enrolled_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.course_student OWNER TO postgres;

--
-- Name: course_teacher; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.course_teacher (
    course_id uuid NOT NULL,
    teacher_id uuid NOT NULL,
    assigned_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.course_teacher OWNER TO postgres;

--
-- Name: course_unit_section_status; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.course_unit_section_status (
    course_id uuid NOT NULL,
    section_id uuid NOT NULL,
    is_published boolean DEFAULT false NOT NULL,
    published_at timestamp with time zone
);


ALTER TABLE public.course_unit_section_status OWNER TO postgres;

--
-- Name: feedback; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.feedback (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    feedback_type text NOT NULL,
    message text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    page_identifier text,
    feedback_text text,
    sentiment text,
    metadata jsonb DEFAULT '{}'::jsonb,
    CONSTRAINT feedback_feedback_type_check CHECK ((feedback_type = ANY (ARRAY['unterricht'::text, 'plattform'::text, 'bug'::text])))
);


ALTER TABLE public.feedback OWNER TO postgres;

--
-- Name: COLUMN feedback.feedback_type; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.feedback.feedback_type IS 'Type of feedback: unterricht (teaching), plattform (platform), or bug (bug report)';


--
-- Name: learning_unit; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.learning_unit (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    title text NOT NULL,
    creator_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.learning_unit OWNER TO postgres;

--
-- Name: mastery_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.mastery_log (
    log_id bigint NOT NULL,
    user_id uuid NOT NULL,
    task_id uuid NOT NULL,
    review_timestamp timestamp with time zone DEFAULT now() NOT NULL,
    time_since_last_review real NOT NULL,
    stability_before real NOT NULL,
    difficulty_before real NOT NULL,
    recall_outcome smallint NOT NULL,
    q_cor real,
    q_flu real,
    q_com real,
    q_err character varying(50),
    time_taken_seconds integer,
    rationale text
);


ALTER TABLE public.mastery_log OWNER TO postgres;

--
-- Name: mastery_log_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.mastery_log_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.mastery_log_log_id_seq OWNER TO postgres;

--
-- Name: mastery_log_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.mastery_log_log_id_seq OWNED BY public.mastery_log.log_id;


--
-- Name: mastery_submission; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.mastery_submission (
    id bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    student_id uuid NOT NULL,
    task_id uuid NOT NULL,
    answer_text text NOT NULL,
    korrektheit double precision NOT NULL,
    vollstaendigkeit double precision NOT NULL,
    praegnanz double precision NOT NULL,
    reasoning text
);


ALTER TABLE public.mastery_submission OWNER TO postgres;

--
-- Name: TABLE mastery_submission; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.mastery_submission IS 'Stores student answers and AI assessments for mastery tasks.';


--
-- Name: COLUMN mastery_submission.answer_text; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.mastery_submission.answer_text IS 'The verbatim answer provided by the student.';


--
-- Name: COLUMN mastery_submission.korrektheit; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.mastery_submission.korrektheit IS 'AI assessment: Correctness score (0.0 to 1.0).';


--
-- Name: COLUMN mastery_submission.vollstaendigkeit; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.mastery_submission.vollstaendigkeit IS 'AI assessment: Completeness score (0.0 to 1.0).';


--
-- Name: COLUMN mastery_submission.praegnanz; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.mastery_submission.praegnanz IS 'AI assessment: Conciseness/Clarity score (0.0 to 1.0).';


--
-- Name: COLUMN mastery_submission.reasoning; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.mastery_submission.reasoning IS 'The textual reasoning for the AI assessment.';


--
-- Name: mastery_submission_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.mastery_submission ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.mastery_submission_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: profiles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.profiles (
    id uuid NOT NULL,
    role public.user_role NOT NULL,
    full_name text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    email text
);


ALTER TABLE public.profiles OWNER TO postgres;

--
-- Name: profiles_display; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.profiles_display AS
 SELECT id,
    role,
    full_name,
    created_at,
    updated_at,
    email,
        CASE
            WHEN (role = 'teacher'::public.user_role) THEN initcap(split_part(email, '@'::text, 1))
            ELSE initcap(replace(split_part(email, '@'::text, 1), '.'::text, ' '::text))
        END AS display_name,
    split_part(email, '@'::text, 1) AS email_prefix
   FROM public.profiles p;


ALTER VIEW public.profiles_display OWNER TO postgres;

--
-- Name: session_rate_limits; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.session_rate_limits (
    user_id uuid NOT NULL,
    attempts integer DEFAULT 1,
    window_start timestamp with time zone DEFAULT now(),
    last_attempt timestamp with time zone DEFAULT now()
);


ALTER TABLE public.session_rate_limits OWNER TO postgres;

--
-- Name: student_mastery_progress; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.student_mastery_progress (
    id bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    student_id uuid NOT NULL,
    task_id uuid NOT NULL,
    stability double precision DEFAULT 1.0 NOT NULL,
    difficulty double precision DEFAULT 0.5 NOT NULL,
    last_reviewed_at timestamp with time zone,
    next_due_date date NOT NULL
);


ALTER TABLE public.student_mastery_progress OWNER TO postgres;

--
-- Name: TABLE student_mastery_progress; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.student_mastery_progress IS 'Stores student progress on mastery tasks based on the new spaced repetition algorithm.';


--
-- Name: COLUMN student_mastery_progress.stability; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.student_mastery_progress.stability IS 'S: The strength of the memory in days.';


--
-- Name: COLUMN student_mastery_progress.difficulty; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.student_mastery_progress.difficulty IS 'D: The intrinsic difficulty of the task (0.0 = easy, 1.0 = hard).';


--
-- Name: COLUMN student_mastery_progress.last_reviewed_at; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.student_mastery_progress.last_reviewed_at IS 'Timestamp of the last completed review.';


--
-- Name: COLUMN student_mastery_progress.next_due_date; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.student_mastery_progress.next_due_date IS 'The date when the task is scheduled for the next review.';


--
-- Name: student_mastery_progress_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.student_mastery_progress ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.student_mastery_progress_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: submission; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.submission (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    student_id uuid NOT NULL,
    task_id uuid NOT NULL,
    submitted_at timestamp with time zone DEFAULT now() NOT NULL,
    submission_data jsonb NOT NULL,
    ai_feedback text,
    ai_grade text,
    feedback_generated_at timestamp with time zone,
    grade_generated_at timestamp with time zone,
    teacher_override_feedback text,
    teacher_override_grade text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    ai_criteria_analysis text,
    feed_back_text text,
    feed_forward_text text,
    attempt_number integer DEFAULT 1 NOT NULL,
    feedback_status text DEFAULT 'pending'::text,
    retry_count integer DEFAULT 0,
    last_retry_at timestamp with time zone,
    processing_started_at timestamp with time zone,
    ai_insights jsonb,
    feedback_viewed_at timestamp with time zone,
    is_correct boolean,
    CONSTRAINT submission_attempt_number_check CHECK ((attempt_number >= 1)),
    CONSTRAINT submission_feedback_status_check CHECK ((feedback_status = ANY (ARRAY['pending'::text, 'processing'::text, 'completed'::text, 'failed'::text, 'retry'::text]))),
    CONSTRAINT submission_retry_count_check CHECK (((retry_count >= 0) AND (retry_count <= 3)))
);


ALTER TABLE public.submission OWNER TO postgres;

--
-- Name: COLUMN submission.ai_grade; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.submission.ai_grade IS 'Von der KI generierter Bewertungsvorschlag (z.B. 0-15 Punkte) für die Lehrkraft (intern).';


--
-- Name: COLUMN submission.ai_criteria_analysis; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.submission.ai_criteria_analysis IS 'Die detaillierte, von der KI generierte Analyse der Schülerlösung basierend auf den Lehrer-Kriterien.';


--
-- Name: COLUMN submission.feed_back_text; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.submission.feed_back_text IS 'The descriptive part of the feedback (Where am I?)';


--
-- Name: COLUMN submission.feed_forward_text; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.submission.feed_forward_text IS 'The actionable part of the feedback (Where to go next?)';


--
-- Name: COLUMN submission.attempt_number; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.submission.attempt_number IS 'Submission attempt number (1, 2, 3, ...)';


--
-- Name: COLUMN submission.feedback_status; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.submission.feedback_status IS 'Status of AI feedback generation: pending (waiting), processing (in progress), completed (done), failed (permanent failure), retry (temporary failure, will retry)';


--
-- Name: COLUMN submission.retry_count; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.submission.retry_count IS 'Number of times feedback generation has been retried (max 3)';


--
-- Name: COLUMN submission.last_retry_at; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.submission.last_retry_at IS 'Timestamp of last retry attempt, used for exponential backoff';


--
-- Name: COLUMN submission.processing_started_at; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.submission.processing_started_at IS 'When processing started, used to detect stuck jobs';


--
-- Name: COLUMN submission.ai_insights; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.submission.ai_insights IS 'Mastery-specific AI insights and analysis results';


--
-- Name: COLUMN submission.feedback_viewed_at; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.submission.feedback_viewed_at IS 'Timestamp when the student viewed the feedback (clicked Next Task button)';


--
-- Name: task; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.task (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    instruction text NOT NULL,
    task_type text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    section_id uuid,
    criteria text,
    assessment_criteria jsonb DEFAULT '[]'::jsonb,
    solution_hints text,
    CONSTRAINT task_assessment_criteria_check CHECK (((jsonb_typeof(assessment_criteria) = 'array'::text) AND (jsonb_array_length(assessment_criteria) <= 5)))
);


ALTER TABLE public.task OWNER TO postgres;

--
-- Name: TABLE task; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.task IS 'Legacy task table - Phase 4 cleanup completed. Most functionality moved to task_base + regular_tasks/mastery_tasks. This table may be dropped in future once all references are updated.';


--
-- Name: COLUMN task.criteria; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.task.criteria IS 'Vom Lehrer definierte Bewertungskriterien für diese Aufgabe (z.B. als Markdown-Liste). Wird als Kontext für die KI-Bewertung verwendet.';


--
-- Name: COLUMN task.assessment_criteria; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.task.assessment_criteria IS 'Array of assessment criteria (max 5) that will be used for AI feedback generation';


--
-- Name: COLUMN task.solution_hints; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.task.solution_hints IS 'Teacher-provided solution hints or model solution to guide the AI analysis';


--
-- Name: task_backup_phase4; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.task_backup_phase4 (
    id uuid,
    instruction text,
    task_type text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    section_id uuid,
    order_in_section integer,
    criteria text,
    assessment_criteria jsonb,
    solution_hints text,
    is_mastery boolean,
    max_attempts integer
);


ALTER TABLE public.task_backup_phase4 OWNER TO postgres;

--
-- Name: TABLE task_backup_phase4; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.task_backup_phase4 IS 'Backup of task table before Phase 4 cleanup. Can be dropped after successful migration verification.';


--
-- Name: unit_section; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.unit_section (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    unit_id uuid NOT NULL,
    title text,
    order_in_unit integer DEFAULT 0 NOT NULL,
    materials jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.unit_section OWNER TO postgres;

--
-- Name: user_model_weights; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_model_weights (
    user_id uuid NOT NULL,
    w0 real NOT NULL,
    w1 real NOT NULL,
    w2 real NOT NULL,
    w3 real NOT NULL,
    w4 real NOT NULL,
    w5 real NOT NULL,
    w6 real NOT NULL,
    w7 real NOT NULL,
    w8 real NOT NULL,
    w9 real NOT NULL,
    w10 real NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.user_model_weights OWNER TO postgres;

--
-- Name: messages; Type: TABLE; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE TABLE realtime.messages (
    topic text NOT NULL,
    extension text NOT NULL,
    payload jsonb,
    event text,
    private boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    inserted_at timestamp without time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL
)
PARTITION BY RANGE (inserted_at);


ALTER TABLE realtime.messages OWNER TO supabase_realtime_admin;

--
-- Name: messages_2025_10_27; Type: TABLE; Schema: realtime; Owner: supabase_admin
--

CREATE TABLE realtime.messages_2025_10_27 (
    topic text NOT NULL,
    extension text NOT NULL,
    payload jsonb,
    event text,
    private boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    inserted_at timestamp without time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


ALTER TABLE realtime.messages_2025_10_27 OWNER TO supabase_admin;

--
-- Name: messages_2025_10_28; Type: TABLE; Schema: realtime; Owner: supabase_admin
--

CREATE TABLE realtime.messages_2025_10_28 (
    topic text NOT NULL,
    extension text NOT NULL,
    payload jsonb,
    event text,
    private boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    inserted_at timestamp without time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


ALTER TABLE realtime.messages_2025_10_28 OWNER TO supabase_admin;

--
-- Name: messages_2025_10_29; Type: TABLE; Schema: realtime; Owner: supabase_admin
--

CREATE TABLE realtime.messages_2025_10_29 (
    topic text NOT NULL,
    extension text NOT NULL,
    payload jsonb,
    event text,
    private boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    inserted_at timestamp without time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


ALTER TABLE realtime.messages_2025_10_29 OWNER TO supabase_admin;

--
-- Name: messages_2025_10_30; Type: TABLE; Schema: realtime; Owner: supabase_admin
--

CREATE TABLE realtime.messages_2025_10_30 (
    topic text NOT NULL,
    extension text NOT NULL,
    payload jsonb,
    event text,
    private boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    inserted_at timestamp without time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


ALTER TABLE realtime.messages_2025_10_30 OWNER TO supabase_admin;

--
-- Name: messages_2025_10_31; Type: TABLE; Schema: realtime; Owner: supabase_admin
--

CREATE TABLE realtime.messages_2025_10_31 (
    topic text NOT NULL,
    extension text NOT NULL,
    payload jsonb,
    event text,
    private boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    inserted_at timestamp without time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


ALTER TABLE realtime.messages_2025_10_31 OWNER TO supabase_admin;

--
-- Name: messages_2025_11_01; Type: TABLE; Schema: realtime; Owner: supabase_admin
--

CREATE TABLE realtime.messages_2025_11_01 (
    topic text NOT NULL,
    extension text NOT NULL,
    payload jsonb,
    event text,
    private boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    inserted_at timestamp without time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


ALTER TABLE realtime.messages_2025_11_01 OWNER TO supabase_admin;

--
-- Name: messages_2025_11_02; Type: TABLE; Schema: realtime; Owner: supabase_admin
--

CREATE TABLE realtime.messages_2025_11_02 (
    topic text NOT NULL,
    extension text NOT NULL,
    payload jsonb,
    event text,
    private boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    inserted_at timestamp without time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


ALTER TABLE realtime.messages_2025_11_02 OWNER TO supabase_admin;

--
-- Name: schema_migrations; Type: TABLE; Schema: realtime; Owner: supabase_admin
--

CREATE TABLE realtime.schema_migrations (
    version bigint NOT NULL,
    inserted_at timestamp(0) without time zone
);


ALTER TABLE realtime.schema_migrations OWNER TO supabase_admin;

--
-- Name: subscription; Type: TABLE; Schema: realtime; Owner: supabase_admin
--

CREATE TABLE realtime.subscription (
    id bigint NOT NULL,
    subscription_id uuid NOT NULL,
    entity regclass NOT NULL,
    filters realtime.user_defined_filter[] DEFAULT '{}'::realtime.user_defined_filter[] NOT NULL,
    claims jsonb NOT NULL,
    claims_role regrole GENERATED ALWAYS AS (realtime.to_regrole((claims ->> 'role'::text))) STORED NOT NULL,
    created_at timestamp without time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);


ALTER TABLE realtime.subscription OWNER TO supabase_admin;

--
-- Name: subscription_id_seq; Type: SEQUENCE; Schema: realtime; Owner: supabase_admin
--

ALTER TABLE realtime.subscription ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME realtime.subscription_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: buckets; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.buckets (
    id text NOT NULL,
    name text NOT NULL,
    owner uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    public boolean DEFAULT false,
    avif_autodetection boolean DEFAULT false,
    file_size_limit bigint,
    allowed_mime_types text[],
    owner_id text,
    type storage.buckettype DEFAULT 'STANDARD'::storage.buckettype NOT NULL
);


ALTER TABLE storage.buckets OWNER TO supabase_storage_admin;

--
-- Name: COLUMN buckets.owner; Type: COMMENT; Schema: storage; Owner: supabase_storage_admin
--

COMMENT ON COLUMN storage.buckets.owner IS 'Field is deprecated, use owner_id instead';


--
-- Name: buckets_analytics; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.buckets_analytics (
    id text NOT NULL,
    type storage.buckettype DEFAULT 'ANALYTICS'::storage.buckettype NOT NULL,
    format text DEFAULT 'ICEBERG'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE storage.buckets_analytics OWNER TO supabase_storage_admin;

--
-- Name: iceberg_namespaces; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.iceberg_namespaces (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    bucket_id text NOT NULL,
    name text NOT NULL COLLATE pg_catalog."C",
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE storage.iceberg_namespaces OWNER TO supabase_storage_admin;

--
-- Name: iceberg_tables; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.iceberg_tables (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    namespace_id uuid NOT NULL,
    bucket_id text NOT NULL,
    name text NOT NULL COLLATE pg_catalog."C",
    location text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE storage.iceberg_tables OWNER TO supabase_storage_admin;

--
-- Name: migrations; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.migrations (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    hash character varying(40) NOT NULL,
    executed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE storage.migrations OWNER TO supabase_storage_admin;

--
-- Name: objects; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.objects (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    bucket_id text,
    name text,
    owner uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    last_accessed_at timestamp with time zone DEFAULT now(),
    metadata jsonb,
    path_tokens text[] GENERATED ALWAYS AS (string_to_array(name, '/'::text)) STORED,
    version text,
    owner_id text,
    user_metadata jsonb,
    level integer
);


ALTER TABLE storage.objects OWNER TO supabase_storage_admin;

--
-- Name: COLUMN objects.owner; Type: COMMENT; Schema: storage; Owner: supabase_storage_admin
--

COMMENT ON COLUMN storage.objects.owner IS 'Field is deprecated, use owner_id instead';


--
-- Name: prefixes; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.prefixes (
    bucket_id text NOT NULL,
    name text NOT NULL COLLATE pg_catalog."C",
    level integer GENERATED ALWAYS AS (storage.get_level(name)) STORED NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


ALTER TABLE storage.prefixes OWNER TO supabase_storage_admin;

--
-- Name: s3_multipart_uploads; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.s3_multipart_uploads (
    id text NOT NULL,
    in_progress_size bigint DEFAULT 0 NOT NULL,
    upload_signature text NOT NULL,
    bucket_id text NOT NULL,
    key text NOT NULL COLLATE pg_catalog."C",
    version text NOT NULL,
    owner_id text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    user_metadata jsonb
);


ALTER TABLE storage.s3_multipart_uploads OWNER TO supabase_storage_admin;

--
-- Name: s3_multipart_uploads_parts; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.s3_multipart_uploads_parts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    upload_id text NOT NULL,
    size bigint DEFAULT 0 NOT NULL,
    part_number integer NOT NULL,
    bucket_id text NOT NULL,
    key text NOT NULL COLLATE pg_catalog."C",
    etag text NOT NULL,
    owner_id text,
    version text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE storage.s3_multipart_uploads_parts OWNER TO supabase_storage_admin;

--
-- Name: hooks; Type: TABLE; Schema: supabase_functions; Owner: supabase_functions_admin
--

CREATE TABLE supabase_functions.hooks (
    id bigint NOT NULL,
    hook_table_id integer NOT NULL,
    hook_name text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    request_id bigint
);


ALTER TABLE supabase_functions.hooks OWNER TO supabase_functions_admin;

--
-- Name: TABLE hooks; Type: COMMENT; Schema: supabase_functions; Owner: supabase_functions_admin
--

COMMENT ON TABLE supabase_functions.hooks IS 'Supabase Functions Hooks: Audit trail for triggered hooks.';


--
-- Name: hooks_id_seq; Type: SEQUENCE; Schema: supabase_functions; Owner: supabase_functions_admin
--

CREATE SEQUENCE supabase_functions.hooks_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE supabase_functions.hooks_id_seq OWNER TO supabase_functions_admin;

--
-- Name: hooks_id_seq; Type: SEQUENCE OWNED BY; Schema: supabase_functions; Owner: supabase_functions_admin
--

ALTER SEQUENCE supabase_functions.hooks_id_seq OWNED BY supabase_functions.hooks.id;


--
-- Name: migrations; Type: TABLE; Schema: supabase_functions; Owner: supabase_functions_admin
--

CREATE TABLE supabase_functions.migrations (
    version text NOT NULL,
    inserted_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE supabase_functions.migrations OWNER TO supabase_functions_admin;

--
-- Name: schema_migrations; Type: TABLE; Schema: supabase_migrations; Owner: postgres
--

CREATE TABLE supabase_migrations.schema_migrations (
    version text NOT NULL,
    statements text[],
    name text
);


ALTER TABLE supabase_migrations.schema_migrations OWNER TO postgres;

--
-- Name: messages_2025_10_27; Type: TABLE ATTACH; Schema: realtime; Owner: supabase_admin
--

ALTER TABLE ONLY realtime.messages ATTACH PARTITION realtime.messages_2025_10_27 FOR VALUES FROM ('2025-10-27 00:00:00') TO ('2025-10-28 00:00:00');


--
-- Name: messages_2025_10_28; Type: TABLE ATTACH; Schema: realtime; Owner: supabase_admin
--

ALTER TABLE ONLY realtime.messages ATTACH PARTITION realtime.messages_2025_10_28 FOR VALUES FROM ('2025-10-28 00:00:00') TO ('2025-10-29 00:00:00');


--
-- Name: messages_2025_10_29; Type: TABLE ATTACH; Schema: realtime; Owner: supabase_admin
--

ALTER TABLE ONLY realtime.messages ATTACH PARTITION realtime.messages_2025_10_29 FOR VALUES FROM ('2025-10-29 00:00:00') TO ('2025-10-30 00:00:00');


--
-- Name: messages_2025_10_30; Type: TABLE ATTACH; Schema: realtime; Owner: supabase_admin
--

ALTER TABLE ONLY realtime.messages ATTACH PARTITION realtime.messages_2025_10_30 FOR VALUES FROM ('2025-10-30 00:00:00') TO ('2025-10-31 00:00:00');


--
-- Name: messages_2025_10_31; Type: TABLE ATTACH; Schema: realtime; Owner: supabase_admin
--

ALTER TABLE ONLY realtime.messages ATTACH PARTITION realtime.messages_2025_10_31 FOR VALUES FROM ('2025-10-31 00:00:00') TO ('2025-11-01 00:00:00');


--
-- Name: messages_2025_11_01; Type: TABLE ATTACH; Schema: realtime; Owner: supabase_admin
--

ALTER TABLE ONLY realtime.messages ATTACH PARTITION realtime.messages_2025_11_01 FOR VALUES FROM ('2025-11-01 00:00:00') TO ('2025-11-02 00:00:00');


--
-- Name: messages_2025_11_02; Type: TABLE ATTACH; Schema: realtime; Owner: supabase_admin
--

ALTER TABLE ONLY realtime.messages ATTACH PARTITION realtime.messages_2025_11_02 FOR VALUES FROM ('2025-11-02 00:00:00') TO ('2025-11-03 00:00:00');


--
-- Name: refresh_tokens id; Type: DEFAULT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.refresh_tokens ALTER COLUMN id SET DEFAULT nextval('auth.refresh_tokens_id_seq'::regclass);


--
-- Name: mastery_log log_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mastery_log ALTER COLUMN log_id SET DEFAULT nextval('public.mastery_log_log_id_seq'::regclass);


--
-- Name: hooks id; Type: DEFAULT; Schema: supabase_functions; Owner: supabase_functions_admin
--

ALTER TABLE ONLY supabase_functions.hooks ALTER COLUMN id SET DEFAULT nextval('supabase_functions.hooks_id_seq'::regclass);


--
-- Name: extensions extensions_pkey; Type: CONSTRAINT; Schema: _realtime; Owner: supabase_admin
--

ALTER TABLE ONLY _realtime.extensions
    ADD CONSTRAINT extensions_pkey PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: _realtime; Owner: supabase_admin
--

ALTER TABLE ONLY _realtime.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: tenants tenants_pkey; Type: CONSTRAINT; Schema: _realtime; Owner: supabase_admin
--

ALTER TABLE ONLY _realtime.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);


--
-- Name: mfa_amr_claims amr_id_pk; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_amr_claims
    ADD CONSTRAINT amr_id_pk PRIMARY KEY (id);


--
-- Name: audit_log_entries audit_log_entries_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.audit_log_entries
    ADD CONSTRAINT audit_log_entries_pkey PRIMARY KEY (id);


--
-- Name: flow_state flow_state_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.flow_state
    ADD CONSTRAINT flow_state_pkey PRIMARY KEY (id);


--
-- Name: identities identities_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.identities
    ADD CONSTRAINT identities_pkey PRIMARY KEY (id);


--
-- Name: identities identities_provider_id_provider_unique; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.identities
    ADD CONSTRAINT identities_provider_id_provider_unique UNIQUE (provider_id, provider);


--
-- Name: instances instances_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.instances
    ADD CONSTRAINT instances_pkey PRIMARY KEY (id);


--
-- Name: mfa_amr_claims mfa_amr_claims_session_id_authentication_method_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_amr_claims
    ADD CONSTRAINT mfa_amr_claims_session_id_authentication_method_pkey UNIQUE (session_id, authentication_method);


--
-- Name: mfa_challenges mfa_challenges_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_challenges
    ADD CONSTRAINT mfa_challenges_pkey PRIMARY KEY (id);


--
-- Name: mfa_factors mfa_factors_last_challenged_at_key; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_factors
    ADD CONSTRAINT mfa_factors_last_challenged_at_key UNIQUE (last_challenged_at);


--
-- Name: mfa_factors mfa_factors_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_factors
    ADD CONSTRAINT mfa_factors_pkey PRIMARY KEY (id);


--
-- Name: oauth_authorizations oauth_authorizations_authorization_code_key; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_authorization_code_key UNIQUE (authorization_code);


--
-- Name: oauth_authorizations oauth_authorizations_authorization_id_key; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_authorization_id_key UNIQUE (authorization_id);


--
-- Name: oauth_authorizations oauth_authorizations_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_pkey PRIMARY KEY (id);


--
-- Name: oauth_clients oauth_clients_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_clients
    ADD CONSTRAINT oauth_clients_pkey PRIMARY KEY (id);


--
-- Name: oauth_consents oauth_consents_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_consents
    ADD CONSTRAINT oauth_consents_pkey PRIMARY KEY (id);


--
-- Name: oauth_consents oauth_consents_user_client_unique; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_consents
    ADD CONSTRAINT oauth_consents_user_client_unique UNIQUE (user_id, client_id);


--
-- Name: one_time_tokens one_time_tokens_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.one_time_tokens
    ADD CONSTRAINT one_time_tokens_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.refresh_tokens
    ADD CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_token_unique; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.refresh_tokens
    ADD CONSTRAINT refresh_tokens_token_unique UNIQUE (token);


--
-- Name: saml_providers saml_providers_entity_id_key; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.saml_providers
    ADD CONSTRAINT saml_providers_entity_id_key UNIQUE (entity_id);


--
-- Name: saml_providers saml_providers_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.saml_providers
    ADD CONSTRAINT saml_providers_pkey PRIMARY KEY (id);


--
-- Name: saml_relay_states saml_relay_states_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.saml_relay_states
    ADD CONSTRAINT saml_relay_states_pkey PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (id);


--
-- Name: sso_domains sso_domains_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.sso_domains
    ADD CONSTRAINT sso_domains_pkey PRIMARY KEY (id);


--
-- Name: sso_providers sso_providers_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.sso_providers
    ADD CONSTRAINT sso_providers_pkey PRIMARY KEY (id);


--
-- Name: users users_phone_key; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.users
    ADD CONSTRAINT users_phone_key UNIQUE (phone);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: allowed_email_domains allowed_email_domains_domain_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.allowed_email_domains
    ADD CONSTRAINT allowed_email_domains_domain_key UNIQUE (domain);


--
-- Name: allowed_email_domains allowed_email_domains_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.allowed_email_domains
    ADD CONSTRAINT allowed_email_domains_pkey PRIMARY KEY (id);


--
-- Name: auth_service_keys auth_service_keys_key_hash_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_service_keys
    ADD CONSTRAINT auth_service_keys_key_hash_key UNIQUE (key_hash);


--
-- Name: auth_service_keys auth_service_keys_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_service_keys
    ADD CONSTRAINT auth_service_keys_pkey PRIMARY KEY (id);


--
-- Name: auth_sessions auth_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_sessions
    ADD CONSTRAINT auth_sessions_pkey PRIMARY KEY (id);


--
-- Name: auth_sessions auth_sessions_session_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_sessions
    ADD CONSTRAINT auth_sessions_session_id_key UNIQUE (session_id);


--
-- Name: course_learning_unit_assignment course_learning_unit_assignment_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.course_learning_unit_assignment
    ADD CONSTRAINT course_learning_unit_assignment_pkey PRIMARY KEY (course_id, unit_id);


--
-- Name: course course_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.course
    ADD CONSTRAINT course_pkey PRIMARY KEY (id);


--
-- Name: course_student course_student_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.course_student
    ADD CONSTRAINT course_student_pkey PRIMARY KEY (course_id, student_id);


--
-- Name: course_teacher course_teacher_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.course_teacher
    ADD CONSTRAINT course_teacher_pkey PRIMARY KEY (course_id, teacher_id);


--
-- Name: course_unit_section_status course_unit_section_status_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.course_unit_section_status
    ADD CONSTRAINT course_unit_section_status_pkey PRIMARY KEY (course_id, section_id);


--
-- Name: feedback feedback_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.feedback
    ADD CONSTRAINT feedback_pkey PRIMARY KEY (id);


--
-- Name: learning_unit learning_unit_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.learning_unit
    ADD CONSTRAINT learning_unit_pkey PRIMARY KEY (id);


--
-- Name: mastery_log mastery_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mastery_log
    ADD CONSTRAINT mastery_log_pkey PRIMARY KEY (log_id);


--
-- Name: mastery_submission mastery_submission_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mastery_submission
    ADD CONSTRAINT mastery_submission_pkey PRIMARY KEY (id);


--
-- Name: mastery_tasks mastery_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mastery_tasks
    ADD CONSTRAINT mastery_tasks_pkey PRIMARY KEY (task_id);


--
-- Name: profiles profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_pkey PRIMARY KEY (id);


--
-- Name: regular_tasks regular_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.regular_tasks
    ADD CONSTRAINT regular_tasks_pkey PRIMARY KEY (task_id);


--
-- Name: session_rate_limits session_rate_limits_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.session_rate_limits
    ADD CONSTRAINT session_rate_limits_pkey PRIMARY KEY (user_id);


--
-- Name: student_mastery_progress student_mastery_progress_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.student_mastery_progress
    ADD CONSTRAINT student_mastery_progress_pkey PRIMARY KEY (id);


--
-- Name: student_mastery_progress student_mastery_progress_student_id_task_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.student_mastery_progress
    ADD CONSTRAINT student_mastery_progress_student_id_task_id_key UNIQUE (student_id, task_id);


--
-- Name: submission submission_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.submission
    ADD CONSTRAINT submission_pkey PRIMARY KEY (id);


--
-- Name: submission submission_student_task_attempt_unique; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.submission
    ADD CONSTRAINT submission_student_task_attempt_unique UNIQUE (student_id, task_id, attempt_number);


--
-- Name: task_base task_base_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.task_base
    ADD CONSTRAINT task_base_pkey PRIMARY KEY (id);


--
-- Name: task task_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.task
    ADD CONSTRAINT task_pkey PRIMARY KEY (id);


--
-- Name: unit_section unit_section_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.unit_section
    ADD CONSTRAINT unit_section_pkey PRIMARY KEY (id);


--
-- Name: user_model_weights user_model_weights_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_model_weights
    ADD CONSTRAINT user_model_weights_pkey PRIMARY KEY (user_id);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER TABLE ONLY realtime.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: messages_2025_10_27 messages_2025_10_27_pkey; Type: CONSTRAINT; Schema: realtime; Owner: supabase_admin
--

ALTER TABLE ONLY realtime.messages_2025_10_27
    ADD CONSTRAINT messages_2025_10_27_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: messages_2025_10_28 messages_2025_10_28_pkey; Type: CONSTRAINT; Schema: realtime; Owner: supabase_admin
--

ALTER TABLE ONLY realtime.messages_2025_10_28
    ADD CONSTRAINT messages_2025_10_28_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: messages_2025_10_29 messages_2025_10_29_pkey; Type: CONSTRAINT; Schema: realtime; Owner: supabase_admin
--

ALTER TABLE ONLY realtime.messages_2025_10_29
    ADD CONSTRAINT messages_2025_10_29_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: messages_2025_10_30 messages_2025_10_30_pkey; Type: CONSTRAINT; Schema: realtime; Owner: supabase_admin
--

ALTER TABLE ONLY realtime.messages_2025_10_30
    ADD CONSTRAINT messages_2025_10_30_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: messages_2025_10_31 messages_2025_10_31_pkey; Type: CONSTRAINT; Schema: realtime; Owner: supabase_admin
--

ALTER TABLE ONLY realtime.messages_2025_10_31
    ADD CONSTRAINT messages_2025_10_31_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: messages_2025_11_01 messages_2025_11_01_pkey; Type: CONSTRAINT; Schema: realtime; Owner: supabase_admin
--

ALTER TABLE ONLY realtime.messages_2025_11_01
    ADD CONSTRAINT messages_2025_11_01_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: messages_2025_11_02 messages_2025_11_02_pkey; Type: CONSTRAINT; Schema: realtime; Owner: supabase_admin
--

ALTER TABLE ONLY realtime.messages_2025_11_02
    ADD CONSTRAINT messages_2025_11_02_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: subscription pk_subscription; Type: CONSTRAINT; Schema: realtime; Owner: supabase_admin
--

ALTER TABLE ONLY realtime.subscription
    ADD CONSTRAINT pk_subscription PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: realtime; Owner: supabase_admin
--

ALTER TABLE ONLY realtime.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: buckets_analytics buckets_analytics_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.buckets_analytics
    ADD CONSTRAINT buckets_analytics_pkey PRIMARY KEY (id);


--
-- Name: buckets buckets_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.buckets
    ADD CONSTRAINT buckets_pkey PRIMARY KEY (id);


--
-- Name: iceberg_namespaces iceberg_namespaces_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.iceberg_namespaces
    ADD CONSTRAINT iceberg_namespaces_pkey PRIMARY KEY (id);


--
-- Name: iceberg_tables iceberg_tables_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.iceberg_tables
    ADD CONSTRAINT iceberg_tables_pkey PRIMARY KEY (id);


--
-- Name: migrations migrations_name_key; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.migrations
    ADD CONSTRAINT migrations_name_key UNIQUE (name);


--
-- Name: migrations migrations_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.migrations
    ADD CONSTRAINT migrations_pkey PRIMARY KEY (id);


--
-- Name: objects objects_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.objects
    ADD CONSTRAINT objects_pkey PRIMARY KEY (id);


--
-- Name: prefixes prefixes_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.prefixes
    ADD CONSTRAINT prefixes_pkey PRIMARY KEY (bucket_id, level, name);


--
-- Name: s3_multipart_uploads_parts s3_multipart_uploads_parts_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.s3_multipart_uploads_parts
    ADD CONSTRAINT s3_multipart_uploads_parts_pkey PRIMARY KEY (id);


--
-- Name: s3_multipart_uploads s3_multipart_uploads_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.s3_multipart_uploads
    ADD CONSTRAINT s3_multipart_uploads_pkey PRIMARY KEY (id);


--
-- Name: hooks hooks_pkey; Type: CONSTRAINT; Schema: supabase_functions; Owner: supabase_functions_admin
--

ALTER TABLE ONLY supabase_functions.hooks
    ADD CONSTRAINT hooks_pkey PRIMARY KEY (id);


--
-- Name: migrations migrations_pkey; Type: CONSTRAINT; Schema: supabase_functions; Owner: supabase_functions_admin
--

ALTER TABLE ONLY supabase_functions.migrations
    ADD CONSTRAINT migrations_pkey PRIMARY KEY (version);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: supabase_migrations; Owner: postgres
--

ALTER TABLE ONLY supabase_migrations.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: extensions_tenant_external_id_index; Type: INDEX; Schema: _realtime; Owner: supabase_admin
--

CREATE INDEX extensions_tenant_external_id_index ON _realtime.extensions USING btree (tenant_external_id);


--
-- Name: extensions_tenant_external_id_type_index; Type: INDEX; Schema: _realtime; Owner: supabase_admin
--

CREATE UNIQUE INDEX extensions_tenant_external_id_type_index ON _realtime.extensions USING btree (tenant_external_id, type);


--
-- Name: tenants_external_id_index; Type: INDEX; Schema: _realtime; Owner: supabase_admin
--

CREATE UNIQUE INDEX tenants_external_id_index ON _realtime.tenants USING btree (external_id);


--
-- Name: audit_logs_instance_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX audit_logs_instance_id_idx ON auth.audit_log_entries USING btree (instance_id);


--
-- Name: confirmation_token_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX confirmation_token_idx ON auth.users USING btree (confirmation_token) WHERE ((confirmation_token)::text !~ '^[0-9 ]*$'::text);


--
-- Name: email_change_token_current_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX email_change_token_current_idx ON auth.users USING btree (email_change_token_current) WHERE ((email_change_token_current)::text !~ '^[0-9 ]*$'::text);


--
-- Name: email_change_token_new_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX email_change_token_new_idx ON auth.users USING btree (email_change_token_new) WHERE ((email_change_token_new)::text !~ '^[0-9 ]*$'::text);


--
-- Name: factor_id_created_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX factor_id_created_at_idx ON auth.mfa_factors USING btree (user_id, created_at);


--
-- Name: flow_state_created_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX flow_state_created_at_idx ON auth.flow_state USING btree (created_at DESC);


--
-- Name: identities_email_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX identities_email_idx ON auth.identities USING btree (email text_pattern_ops);


--
-- Name: INDEX identities_email_idx; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON INDEX auth.identities_email_idx IS 'Auth: Ensures indexed queries on the email column';


--
-- Name: identities_user_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX identities_user_id_idx ON auth.identities USING btree (user_id);


--
-- Name: idx_auth_code; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX idx_auth_code ON auth.flow_state USING btree (auth_code);


--
-- Name: idx_user_id_auth_method; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX idx_user_id_auth_method ON auth.flow_state USING btree (user_id, authentication_method);


--
-- Name: mfa_challenge_created_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX mfa_challenge_created_at_idx ON auth.mfa_challenges USING btree (created_at DESC);


--
-- Name: mfa_factors_user_friendly_name_unique; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX mfa_factors_user_friendly_name_unique ON auth.mfa_factors USING btree (friendly_name, user_id) WHERE (TRIM(BOTH FROM friendly_name) <> ''::text);


--
-- Name: mfa_factors_user_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX mfa_factors_user_id_idx ON auth.mfa_factors USING btree (user_id);


--
-- Name: oauth_auth_pending_exp_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX oauth_auth_pending_exp_idx ON auth.oauth_authorizations USING btree (expires_at) WHERE (status = 'pending'::auth.oauth_authorization_status);


--
-- Name: oauth_clients_deleted_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX oauth_clients_deleted_at_idx ON auth.oauth_clients USING btree (deleted_at);


--
-- Name: oauth_consents_active_client_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX oauth_consents_active_client_idx ON auth.oauth_consents USING btree (client_id) WHERE (revoked_at IS NULL);


--
-- Name: oauth_consents_active_user_client_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX oauth_consents_active_user_client_idx ON auth.oauth_consents USING btree (user_id, client_id) WHERE (revoked_at IS NULL);


--
-- Name: oauth_consents_user_order_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX oauth_consents_user_order_idx ON auth.oauth_consents USING btree (user_id, granted_at DESC);


--
-- Name: one_time_tokens_relates_to_hash_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX one_time_tokens_relates_to_hash_idx ON auth.one_time_tokens USING hash (relates_to);


--
-- Name: one_time_tokens_token_hash_hash_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX one_time_tokens_token_hash_hash_idx ON auth.one_time_tokens USING hash (token_hash);


--
-- Name: one_time_tokens_user_id_token_type_key; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX one_time_tokens_user_id_token_type_key ON auth.one_time_tokens USING btree (user_id, token_type);


--
-- Name: reauthentication_token_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX reauthentication_token_idx ON auth.users USING btree (reauthentication_token) WHERE ((reauthentication_token)::text !~ '^[0-9 ]*$'::text);


--
-- Name: recovery_token_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX recovery_token_idx ON auth.users USING btree (recovery_token) WHERE ((recovery_token)::text !~ '^[0-9 ]*$'::text);


--
-- Name: refresh_tokens_instance_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX refresh_tokens_instance_id_idx ON auth.refresh_tokens USING btree (instance_id);


--
-- Name: refresh_tokens_instance_id_user_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX refresh_tokens_instance_id_user_id_idx ON auth.refresh_tokens USING btree (instance_id, user_id);


--
-- Name: refresh_tokens_parent_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX refresh_tokens_parent_idx ON auth.refresh_tokens USING btree (parent);


--
-- Name: refresh_tokens_session_id_revoked_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX refresh_tokens_session_id_revoked_idx ON auth.refresh_tokens USING btree (session_id, revoked);


--
-- Name: refresh_tokens_updated_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX refresh_tokens_updated_at_idx ON auth.refresh_tokens USING btree (updated_at DESC);


--
-- Name: saml_providers_sso_provider_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX saml_providers_sso_provider_id_idx ON auth.saml_providers USING btree (sso_provider_id);


--
-- Name: saml_relay_states_created_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX saml_relay_states_created_at_idx ON auth.saml_relay_states USING btree (created_at DESC);


--
-- Name: saml_relay_states_for_email_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX saml_relay_states_for_email_idx ON auth.saml_relay_states USING btree (for_email);


--
-- Name: saml_relay_states_sso_provider_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX saml_relay_states_sso_provider_id_idx ON auth.saml_relay_states USING btree (sso_provider_id);


--
-- Name: sessions_not_after_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX sessions_not_after_idx ON auth.sessions USING btree (not_after DESC);


--
-- Name: sessions_oauth_client_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX sessions_oauth_client_id_idx ON auth.sessions USING btree (oauth_client_id);


--
-- Name: sessions_user_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX sessions_user_id_idx ON auth.sessions USING btree (user_id);


--
-- Name: sso_domains_domain_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX sso_domains_domain_idx ON auth.sso_domains USING btree (lower(domain));


--
-- Name: sso_domains_sso_provider_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX sso_domains_sso_provider_id_idx ON auth.sso_domains USING btree (sso_provider_id);


--
-- Name: sso_providers_resource_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX sso_providers_resource_id_idx ON auth.sso_providers USING btree (lower(resource_id));


--
-- Name: sso_providers_resource_id_pattern_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX sso_providers_resource_id_pattern_idx ON auth.sso_providers USING btree (resource_id text_pattern_ops);


--
-- Name: unique_phone_factor_per_user; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX unique_phone_factor_per_user ON auth.mfa_factors USING btree (user_id, phone);


--
-- Name: user_id_created_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX user_id_created_at_idx ON auth.sessions USING btree (user_id, created_at);


--
-- Name: users_email_partial_key; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX users_email_partial_key ON auth.users USING btree (email) WHERE (is_sso_user = false);


--
-- Name: INDEX users_email_partial_key; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON INDEX auth.users_email_partial_key IS 'Auth: A partial unique index that applies only when is_sso_user is false';


--
-- Name: users_instance_id_email_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX users_instance_id_email_idx ON auth.users USING btree (instance_id, lower((email)::text));


--
-- Name: users_instance_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX users_instance_id_idx ON auth.users USING btree (instance_id);


--
-- Name: users_is_anonymous_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX users_is_anonymous_idx ON auth.users USING btree (is_anonymous);


--
-- Name: idx_allowed_email_domains_domain; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_allowed_email_domains_domain ON public.allowed_email_domains USING btree (domain);


--
-- Name: idx_auth_sessions_expires_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_auth_sessions_expires_at ON public.auth_sessions USING btree (expires_at);


--
-- Name: idx_auth_sessions_last_activity; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_auth_sessions_last_activity ON public.auth_sessions USING btree (last_activity);


--
-- Name: idx_auth_sessions_session_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_auth_sessions_session_id ON public.auth_sessions USING btree (session_id);


--
-- Name: idx_auth_sessions_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_auth_sessions_user_id ON public.auth_sessions USING btree (user_id);


--
-- Name: idx_course_created_by; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_course_created_by ON public.course USING btree (created_by);


--
-- Name: idx_course_creator_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_course_creator_id ON public.course USING btree (creator_id);


--
-- Name: idx_course_learning_unit_assignment_unit_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_course_learning_unit_assignment_unit_id ON public.course_learning_unit_assignment USING btree (unit_id);


--
-- Name: idx_course_student_student_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_course_student_student_id ON public.course_student USING btree (student_id);


--
-- Name: idx_course_teacher_teacher_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_course_teacher_teacher_id ON public.course_teacher USING btree (teacher_id);


--
-- Name: idx_course_unit_section_status_published; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_course_unit_section_status_published ON public.course_unit_section_status USING btree (is_published);


--
-- Name: idx_course_unit_section_status_section_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_course_unit_section_status_section_id ON public.course_unit_section_status USING btree (section_id);


--
-- Name: idx_feedback_created_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_feedback_created_at ON public.feedback USING btree (created_at DESC);


--
-- Name: idx_feedback_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_feedback_type ON public.feedback USING btree (feedback_type);


--
-- Name: idx_learning_unit_creator_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_learning_unit_creator_id ON public.learning_unit USING btree (creator_id);


--
-- Name: idx_profiles_email; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_profiles_email ON public.profiles USING btree (email);


--
-- Name: idx_profiles_role; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_profiles_role ON public.profiles USING btree (role);


--
-- Name: idx_profiles_role_email; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_profiles_role_email ON public.profiles USING btree (role, email);


--
-- Name: idx_regular_tasks_order; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_regular_tasks_order ON public.regular_tasks USING btree (order_in_section);


--
-- Name: idx_session_rate_limits_window; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_session_rate_limits_window ON public.session_rate_limits USING btree (window_start);


--
-- Name: idx_submission_feedback_queue; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_submission_feedback_queue ON public.submission USING btree (feedback_status, retry_count, created_at) WHERE (feedback_status = ANY (ARRAY['pending'::text, 'retry'::text]));


--
-- Name: idx_submission_feedback_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_submission_feedback_status ON public.submission USING btree (feedback_status, created_at DESC) WHERE (feedback_status = ANY (ARRAY['pending'::text, 'processing'::text, 'retry'::text]));


--
-- Name: idx_submission_processing_timeout; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_submission_processing_timeout ON public.submission USING btree (processing_started_at) WHERE (feedback_status = 'processing'::text);


--
-- Name: idx_submission_student_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_submission_student_id ON public.submission USING btree (student_id);


--
-- Name: idx_submission_student_task_attempt; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_submission_student_task_attempt ON public.submission USING btree (student_id, task_id, attempt_number);


--
-- Name: idx_submission_task_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_submission_task_id ON public.submission USING btree (task_id);


--
-- Name: idx_task_base_order_in_section; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_task_base_order_in_section ON public.task_base USING btree (order_in_section);


--
-- Name: idx_task_base_section_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_task_base_section_id ON public.task_base USING btree (section_id);


--
-- Name: idx_task_section_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_task_section_id ON public.task USING btree (section_id);


--
-- Name: idx_unit_section_order; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_unit_section_order ON public.unit_section USING btree (unit_id, order_in_unit);


--
-- Name: idx_unit_section_unit_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_unit_section_unit_id ON public.unit_section USING btree (unit_id);


--
-- Name: ix_realtime_subscription_entity; Type: INDEX; Schema: realtime; Owner: supabase_admin
--

CREATE INDEX ix_realtime_subscription_entity ON realtime.subscription USING btree (entity);


--
-- Name: messages_inserted_at_topic_index; Type: INDEX; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE INDEX messages_inserted_at_topic_index ON ONLY realtime.messages USING btree (inserted_at DESC, topic) WHERE ((extension = 'broadcast'::text) AND (private IS TRUE));


--
-- Name: messages_2025_10_27_inserted_at_topic_idx; Type: INDEX; Schema: realtime; Owner: supabase_admin
--

CREATE INDEX messages_2025_10_27_inserted_at_topic_idx ON realtime.messages_2025_10_27 USING btree (inserted_at DESC, topic) WHERE ((extension = 'broadcast'::text) AND (private IS TRUE));


--
-- Name: messages_2025_10_28_inserted_at_topic_idx; Type: INDEX; Schema: realtime; Owner: supabase_admin
--

CREATE INDEX messages_2025_10_28_inserted_at_topic_idx ON realtime.messages_2025_10_28 USING btree (inserted_at DESC, topic) WHERE ((extension = 'broadcast'::text) AND (private IS TRUE));


--
-- Name: messages_2025_10_29_inserted_at_topic_idx; Type: INDEX; Schema: realtime; Owner: supabase_admin
--

CREATE INDEX messages_2025_10_29_inserted_at_topic_idx ON realtime.messages_2025_10_29 USING btree (inserted_at DESC, topic) WHERE ((extension = 'broadcast'::text) AND (private IS TRUE));


--
-- Name: messages_2025_10_30_inserted_at_topic_idx; Type: INDEX; Schema: realtime; Owner: supabase_admin
--

CREATE INDEX messages_2025_10_30_inserted_at_topic_idx ON realtime.messages_2025_10_30 USING btree (inserted_at DESC, topic) WHERE ((extension = 'broadcast'::text) AND (private IS TRUE));


--
-- Name: messages_2025_10_31_inserted_at_topic_idx; Type: INDEX; Schema: realtime; Owner: supabase_admin
--

CREATE INDEX messages_2025_10_31_inserted_at_topic_idx ON realtime.messages_2025_10_31 USING btree (inserted_at DESC, topic) WHERE ((extension = 'broadcast'::text) AND (private IS TRUE));


--
-- Name: messages_2025_11_01_inserted_at_topic_idx; Type: INDEX; Schema: realtime; Owner: supabase_admin
--

CREATE INDEX messages_2025_11_01_inserted_at_topic_idx ON realtime.messages_2025_11_01 USING btree (inserted_at DESC, topic) WHERE ((extension = 'broadcast'::text) AND (private IS TRUE));


--
-- Name: messages_2025_11_02_inserted_at_topic_idx; Type: INDEX; Schema: realtime; Owner: supabase_admin
--

CREATE INDEX messages_2025_11_02_inserted_at_topic_idx ON realtime.messages_2025_11_02 USING btree (inserted_at DESC, topic) WHERE ((extension = 'broadcast'::text) AND (private IS TRUE));


--
-- Name: subscription_subscription_id_entity_filters_key; Type: INDEX; Schema: realtime; Owner: supabase_admin
--

CREATE UNIQUE INDEX subscription_subscription_id_entity_filters_key ON realtime.subscription USING btree (subscription_id, entity, filters);


--
-- Name: bname; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE UNIQUE INDEX bname ON storage.buckets USING btree (name);


--
-- Name: bucketid_objname; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE UNIQUE INDEX bucketid_objname ON storage.objects USING btree (bucket_id, name);


--
-- Name: idx_iceberg_namespaces_bucket_id; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE UNIQUE INDEX idx_iceberg_namespaces_bucket_id ON storage.iceberg_namespaces USING btree (bucket_id, name);


--
-- Name: idx_iceberg_tables_namespace_id; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE UNIQUE INDEX idx_iceberg_tables_namespace_id ON storage.iceberg_tables USING btree (namespace_id, name);


--
-- Name: idx_multipart_uploads_list; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE INDEX idx_multipart_uploads_list ON storage.s3_multipart_uploads USING btree (bucket_id, key, created_at);


--
-- Name: idx_name_bucket_level_unique; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE UNIQUE INDEX idx_name_bucket_level_unique ON storage.objects USING btree (name COLLATE "C", bucket_id, level);


--
-- Name: idx_objects_bucket_id_name; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE INDEX idx_objects_bucket_id_name ON storage.objects USING btree (bucket_id, name COLLATE "C");


--
-- Name: idx_objects_lower_name; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE INDEX idx_objects_lower_name ON storage.objects USING btree ((path_tokens[level]), lower(name) text_pattern_ops, bucket_id, level);


--
-- Name: idx_prefixes_lower_name; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE INDEX idx_prefixes_lower_name ON storage.prefixes USING btree (bucket_id, level, ((string_to_array(name, '/'::text))[level]), lower(name) text_pattern_ops);


--
-- Name: name_prefix_search; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE INDEX name_prefix_search ON storage.objects USING btree (name text_pattern_ops);


--
-- Name: objects_bucket_id_level_idx; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE UNIQUE INDEX objects_bucket_id_level_idx ON storage.objects USING btree (bucket_id, level, name COLLATE "C");


--
-- Name: supabase_functions_hooks_h_table_id_h_name_idx; Type: INDEX; Schema: supabase_functions; Owner: supabase_functions_admin
--

CREATE INDEX supabase_functions_hooks_h_table_id_h_name_idx ON supabase_functions.hooks USING btree (hook_table_id, hook_name);


--
-- Name: supabase_functions_hooks_request_id_idx; Type: INDEX; Schema: supabase_functions; Owner: supabase_functions_admin
--

CREATE INDEX supabase_functions_hooks_request_id_idx ON supabase_functions.hooks USING btree (request_id);


--
-- Name: messages_2025_10_27_inserted_at_topic_idx; Type: INDEX ATTACH; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER INDEX realtime.messages_inserted_at_topic_index ATTACH PARTITION realtime.messages_2025_10_27_inserted_at_topic_idx;


--
-- Name: messages_2025_10_27_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2025_10_27_pkey;


--
-- Name: messages_2025_10_28_inserted_at_topic_idx; Type: INDEX ATTACH; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER INDEX realtime.messages_inserted_at_topic_index ATTACH PARTITION realtime.messages_2025_10_28_inserted_at_topic_idx;


--
-- Name: messages_2025_10_28_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2025_10_28_pkey;


--
-- Name: messages_2025_10_29_inserted_at_topic_idx; Type: INDEX ATTACH; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER INDEX realtime.messages_inserted_at_topic_index ATTACH PARTITION realtime.messages_2025_10_29_inserted_at_topic_idx;


--
-- Name: messages_2025_10_29_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2025_10_29_pkey;


--
-- Name: messages_2025_10_30_inserted_at_topic_idx; Type: INDEX ATTACH; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER INDEX realtime.messages_inserted_at_topic_index ATTACH PARTITION realtime.messages_2025_10_30_inserted_at_topic_idx;


--
-- Name: messages_2025_10_30_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2025_10_30_pkey;


--
-- Name: messages_2025_10_31_inserted_at_topic_idx; Type: INDEX ATTACH; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER INDEX realtime.messages_inserted_at_topic_index ATTACH PARTITION realtime.messages_2025_10_31_inserted_at_topic_idx;


--
-- Name: messages_2025_10_31_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2025_10_31_pkey;


--
-- Name: messages_2025_11_01_inserted_at_topic_idx; Type: INDEX ATTACH; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER INDEX realtime.messages_inserted_at_topic_index ATTACH PARTITION realtime.messages_2025_11_01_inserted_at_topic_idx;


--
-- Name: messages_2025_11_01_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2025_11_01_pkey;


--
-- Name: messages_2025_11_02_inserted_at_topic_idx; Type: INDEX ATTACH; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER INDEX realtime.messages_inserted_at_topic_index ATTACH PARTITION realtime.messages_2025_11_02_inserted_at_topic_idx;


--
-- Name: messages_2025_11_02_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2025_11_02_pkey;


--
-- Name: users on_auth_user_created; Type: TRIGGER; Schema: auth; Owner: supabase_auth_admin
--

CREATE TRIGGER on_auth_user_created AFTER INSERT ON auth.users FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();


--
-- Name: auth_sessions enforce_auth_session_limit; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER enforce_auth_session_limit BEFORE INSERT ON public.auth_sessions FOR EACH ROW EXECUTE FUNCTION public.enforce_session_limit();


--
-- Name: submission ensure_feedback_consistency_trigger; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER ensure_feedback_consistency_trigger BEFORE INSERT OR UPDATE ON public.submission FOR EACH ROW EXECUTE FUNCTION public.ensure_feedback_consistency();


--
-- Name: user_model_weights on_user_model_weights_updated; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER on_user_model_weights_updated BEFORE UPDATE ON public.user_model_weights FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();


--
-- Name: auth_sessions update_auth_sessions_last_activity; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER update_auth_sessions_last_activity BEFORE UPDATE ON public.auth_sessions FOR EACH ROW EXECUTE FUNCTION public.update_last_activity();


--
-- Name: subscription tr_check_filters; Type: TRIGGER; Schema: realtime; Owner: supabase_admin
--

CREATE TRIGGER tr_check_filters BEFORE INSERT OR UPDATE ON realtime.subscription FOR EACH ROW EXECUTE FUNCTION realtime.subscription_check_filters();


--
-- Name: buckets enforce_bucket_name_length_trigger; Type: TRIGGER; Schema: storage; Owner: supabase_storage_admin
--

CREATE TRIGGER enforce_bucket_name_length_trigger BEFORE INSERT OR UPDATE OF name ON storage.buckets FOR EACH ROW EXECUTE FUNCTION storage.enforce_bucket_name_length();


--
-- Name: objects objects_delete_delete_prefix; Type: TRIGGER; Schema: storage; Owner: supabase_storage_admin
--

CREATE TRIGGER objects_delete_delete_prefix AFTER DELETE ON storage.objects FOR EACH ROW EXECUTE FUNCTION storage.delete_prefix_hierarchy_trigger();


--
-- Name: objects objects_insert_create_prefix; Type: TRIGGER; Schema: storage; Owner: supabase_storage_admin
--

CREATE TRIGGER objects_insert_create_prefix BEFORE INSERT ON storage.objects FOR EACH ROW EXECUTE FUNCTION storage.objects_insert_prefix_trigger();


--
-- Name: objects objects_update_create_prefix; Type: TRIGGER; Schema: storage; Owner: supabase_storage_admin
--

CREATE TRIGGER objects_update_create_prefix BEFORE UPDATE ON storage.objects FOR EACH ROW WHEN (((new.name <> old.name) OR (new.bucket_id <> old.bucket_id))) EXECUTE FUNCTION storage.objects_update_prefix_trigger();


--
-- Name: prefixes prefixes_create_hierarchy; Type: TRIGGER; Schema: storage; Owner: supabase_storage_admin
--

CREATE TRIGGER prefixes_create_hierarchy BEFORE INSERT ON storage.prefixes FOR EACH ROW WHEN ((pg_trigger_depth() < 1)) EXECUTE FUNCTION storage.prefixes_insert_trigger();


--
-- Name: prefixes prefixes_delete_hierarchy; Type: TRIGGER; Schema: storage; Owner: supabase_storage_admin
--

CREATE TRIGGER prefixes_delete_hierarchy AFTER DELETE ON storage.prefixes FOR EACH ROW EXECUTE FUNCTION storage.delete_prefix_hierarchy_trigger();


--
-- Name: objects update_objects_updated_at; Type: TRIGGER; Schema: storage; Owner: supabase_storage_admin
--

CREATE TRIGGER update_objects_updated_at BEFORE UPDATE ON storage.objects FOR EACH ROW EXECUTE FUNCTION storage.update_updated_at_column();


--
-- Name: extensions extensions_tenant_external_id_fkey; Type: FK CONSTRAINT; Schema: _realtime; Owner: supabase_admin
--

ALTER TABLE ONLY _realtime.extensions
    ADD CONSTRAINT extensions_tenant_external_id_fkey FOREIGN KEY (tenant_external_id) REFERENCES _realtime.tenants(external_id) ON DELETE CASCADE;


--
-- Name: identities identities_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.identities
    ADD CONSTRAINT identities_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: mfa_amr_claims mfa_amr_claims_session_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_amr_claims
    ADD CONSTRAINT mfa_amr_claims_session_id_fkey FOREIGN KEY (session_id) REFERENCES auth.sessions(id) ON DELETE CASCADE;


--
-- Name: mfa_challenges mfa_challenges_auth_factor_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_challenges
    ADD CONSTRAINT mfa_challenges_auth_factor_id_fkey FOREIGN KEY (factor_id) REFERENCES auth.mfa_factors(id) ON DELETE CASCADE;


--
-- Name: mfa_factors mfa_factors_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_factors
    ADD CONSTRAINT mfa_factors_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: oauth_authorizations oauth_authorizations_client_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_client_id_fkey FOREIGN KEY (client_id) REFERENCES auth.oauth_clients(id) ON DELETE CASCADE;


--
-- Name: oauth_authorizations oauth_authorizations_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: oauth_consents oauth_consents_client_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_consents
    ADD CONSTRAINT oauth_consents_client_id_fkey FOREIGN KEY (client_id) REFERENCES auth.oauth_clients(id) ON DELETE CASCADE;


--
-- Name: oauth_consents oauth_consents_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_consents
    ADD CONSTRAINT oauth_consents_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: one_time_tokens one_time_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.one_time_tokens
    ADD CONSTRAINT one_time_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: refresh_tokens refresh_tokens_session_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.refresh_tokens
    ADD CONSTRAINT refresh_tokens_session_id_fkey FOREIGN KEY (session_id) REFERENCES auth.sessions(id) ON DELETE CASCADE;


--
-- Name: saml_providers saml_providers_sso_provider_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.saml_providers
    ADD CONSTRAINT saml_providers_sso_provider_id_fkey FOREIGN KEY (sso_provider_id) REFERENCES auth.sso_providers(id) ON DELETE CASCADE;


--
-- Name: saml_relay_states saml_relay_states_flow_state_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.saml_relay_states
    ADD CONSTRAINT saml_relay_states_flow_state_id_fkey FOREIGN KEY (flow_state_id) REFERENCES auth.flow_state(id) ON DELETE CASCADE;


--
-- Name: saml_relay_states saml_relay_states_sso_provider_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.saml_relay_states
    ADD CONSTRAINT saml_relay_states_sso_provider_id_fkey FOREIGN KEY (sso_provider_id) REFERENCES auth.sso_providers(id) ON DELETE CASCADE;


--
-- Name: sessions sessions_oauth_client_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.sessions
    ADD CONSTRAINT sessions_oauth_client_id_fkey FOREIGN KEY (oauth_client_id) REFERENCES auth.oauth_clients(id) ON DELETE CASCADE;


--
-- Name: sessions sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.sessions
    ADD CONSTRAINT sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: sso_domains sso_domains_sso_provider_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.sso_domains
    ADD CONSTRAINT sso_domains_sso_provider_id_fkey FOREIGN KEY (sso_provider_id) REFERENCES auth.sso_providers(id) ON DELETE CASCADE;


--
-- Name: auth_sessions auth_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_sessions
    ADD CONSTRAINT auth_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: course course_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.course
    ADD CONSTRAINT course_created_by_fkey FOREIGN KEY (created_by) REFERENCES auth.users(id);


--
-- Name: course course_creator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.course
    ADD CONSTRAINT course_creator_id_fkey FOREIGN KEY (creator_id) REFERENCES auth.users(id) ON DELETE SET NULL;


--
-- Name: course_learning_unit_assignment course_learning_unit_assignment_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.course_learning_unit_assignment
    ADD CONSTRAINT course_learning_unit_assignment_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.course(id) ON DELETE CASCADE;


--
-- Name: course_learning_unit_assignment course_learning_unit_assignment_unit_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.course_learning_unit_assignment
    ADD CONSTRAINT course_learning_unit_assignment_unit_id_fkey FOREIGN KEY (unit_id) REFERENCES public.learning_unit(id) ON DELETE CASCADE;


--
-- Name: course_student course_student_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.course_student
    ADD CONSTRAINT course_student_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.course(id) ON DELETE CASCADE;


--
-- Name: course_student course_student_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.course_student
    ADD CONSTRAINT course_student_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.profiles(id) ON DELETE CASCADE;


--
-- Name: course_teacher course_teacher_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.course_teacher
    ADD CONSTRAINT course_teacher_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.course(id) ON DELETE CASCADE;


--
-- Name: course_teacher course_teacher_teacher_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.course_teacher
    ADD CONSTRAINT course_teacher_teacher_id_fkey FOREIGN KEY (teacher_id) REFERENCES public.profiles(id) ON DELETE CASCADE;


--
-- Name: course_unit_section_status course_unit_section_status_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.course_unit_section_status
    ADD CONSTRAINT course_unit_section_status_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.course(id) ON DELETE CASCADE;


--
-- Name: course_unit_section_status course_unit_section_status_section_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.course_unit_section_status
    ADD CONSTRAINT course_unit_section_status_section_id_fkey FOREIGN KEY (section_id) REFERENCES public.unit_section(id) ON DELETE CASCADE;


--
-- Name: learning_unit learning_unit_creator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.learning_unit
    ADD CONSTRAINT learning_unit_creator_id_fkey FOREIGN KEY (creator_id) REFERENCES auth.users(id) ON DELETE SET NULL;


--
-- Name: mastery_log mastery_log_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mastery_log
    ADD CONSTRAINT mastery_log_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.task_base(id) ON DELETE CASCADE;


--
-- Name: mastery_log mastery_log_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mastery_log
    ADD CONSTRAINT mastery_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(id) ON DELETE CASCADE;


--
-- Name: mastery_submission mastery_submission_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mastery_submission
    ADD CONSTRAINT mastery_submission_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.profiles(id) ON DELETE CASCADE;


--
-- Name: mastery_submission mastery_submission_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mastery_submission
    ADD CONSTRAINT mastery_submission_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.task_base(id) ON DELETE CASCADE;


--
-- Name: mastery_tasks mastery_tasks_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mastery_tasks
    ADD CONSTRAINT mastery_tasks_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.task_base(id) ON DELETE CASCADE;


--
-- Name: profiles profiles_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: regular_tasks regular_tasks_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.regular_tasks
    ADD CONSTRAINT regular_tasks_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.task_base(id) ON DELETE CASCADE;


--
-- Name: student_mastery_progress student_mastery_progress_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.student_mastery_progress
    ADD CONSTRAINT student_mastery_progress_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.profiles(id) ON DELETE CASCADE;


--
-- Name: student_mastery_progress student_mastery_progress_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.student_mastery_progress
    ADD CONSTRAINT student_mastery_progress_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.task_base(id) ON DELETE CASCADE;


--
-- Name: submission submission_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.submission
    ADD CONSTRAINT submission_student_id_fkey FOREIGN KEY (student_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: submission submission_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.submission
    ADD CONSTRAINT submission_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.task_base(id) ON DELETE CASCADE;


--
-- Name: task_base task_base_section_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.task_base
    ADD CONSTRAINT task_base_section_id_fkey FOREIGN KEY (section_id) REFERENCES public.unit_section(id);


--
-- Name: task task_section_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.task
    ADD CONSTRAINT task_section_id_fkey FOREIGN KEY (section_id) REFERENCES public.unit_section(id) ON DELETE CASCADE;


--
-- Name: unit_section unit_section_unit_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.unit_section
    ADD CONSTRAINT unit_section_unit_id_fkey FOREIGN KEY (unit_id) REFERENCES public.learning_unit(id) ON DELETE CASCADE;


--
-- Name: user_model_weights user_model_weights_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_model_weights
    ADD CONSTRAINT user_model_weights_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(id) ON DELETE CASCADE;


--
-- Name: iceberg_namespaces iceberg_namespaces_bucket_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.iceberg_namespaces
    ADD CONSTRAINT iceberg_namespaces_bucket_id_fkey FOREIGN KEY (bucket_id) REFERENCES storage.buckets_analytics(id) ON DELETE CASCADE;


--
-- Name: iceberg_tables iceberg_tables_bucket_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.iceberg_tables
    ADD CONSTRAINT iceberg_tables_bucket_id_fkey FOREIGN KEY (bucket_id) REFERENCES storage.buckets_analytics(id) ON DELETE CASCADE;


--
-- Name: iceberg_tables iceberg_tables_namespace_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.iceberg_tables
    ADD CONSTRAINT iceberg_tables_namespace_id_fkey FOREIGN KEY (namespace_id) REFERENCES storage.iceberg_namespaces(id) ON DELETE CASCADE;


--
-- Name: objects objects_bucketId_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.objects
    ADD CONSTRAINT "objects_bucketId_fkey" FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


--
-- Name: prefixes prefixes_bucketId_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.prefixes
    ADD CONSTRAINT "prefixes_bucketId_fkey" FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


--
-- Name: s3_multipart_uploads s3_multipart_uploads_bucket_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.s3_multipart_uploads
    ADD CONSTRAINT s3_multipart_uploads_bucket_id_fkey FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


--
-- Name: s3_multipart_uploads_parts s3_multipart_uploads_parts_bucket_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.s3_multipart_uploads_parts
    ADD CONSTRAINT s3_multipart_uploads_parts_bucket_id_fkey FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


--
-- Name: s3_multipart_uploads_parts s3_multipart_uploads_parts_upload_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.s3_multipart_uploads_parts
    ADD CONSTRAINT s3_multipart_uploads_parts_upload_id_fkey FOREIGN KEY (upload_id) REFERENCES storage.s3_multipart_uploads(id) ON DELETE CASCADE;


--
-- Name: audit_log_entries; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.audit_log_entries ENABLE ROW LEVEL SECURITY;

--
-- Name: flow_state; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.flow_state ENABLE ROW LEVEL SECURITY;

--
-- Name: identities; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.identities ENABLE ROW LEVEL SECURITY;

--
-- Name: instances; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.instances ENABLE ROW LEVEL SECURITY;

--
-- Name: mfa_amr_claims; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.mfa_amr_claims ENABLE ROW LEVEL SECURITY;

--
-- Name: mfa_challenges; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.mfa_challenges ENABLE ROW LEVEL SECURITY;

--
-- Name: mfa_factors; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.mfa_factors ENABLE ROW LEVEL SECURITY;

--
-- Name: one_time_tokens; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.one_time_tokens ENABLE ROW LEVEL SECURITY;

--
-- Name: refresh_tokens; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.refresh_tokens ENABLE ROW LEVEL SECURITY;

--
-- Name: saml_providers; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.saml_providers ENABLE ROW LEVEL SECURITY;

--
-- Name: saml_relay_states; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.saml_relay_states ENABLE ROW LEVEL SECURITY;

--
-- Name: schema_migrations; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.schema_migrations ENABLE ROW LEVEL SECURITY;

--
-- Name: sessions; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.sessions ENABLE ROW LEVEL SECURITY;

--
-- Name: sso_domains; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.sso_domains ENABLE ROW LEVEL SECURITY;

--
-- Name: sso_providers; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.sso_providers ENABLE ROW LEVEL SECURITY;

--
-- Name: users; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.users ENABLE ROW LEVEL SECURITY;

--
-- Name: mastery_tasks Access mastery tasks via task_base; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Access mastery tasks via task_base" ON public.mastery_tasks USING ((EXISTS ( SELECT 1
   FROM public.task_base tb
  WHERE (tb.id = mastery_tasks.task_id))));


--
-- Name: regular_tasks Access regular tasks via task_base; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Access regular tasks via task_base" ON public.regular_tasks USING ((EXISTS ( SELECT 1
   FROM public.task_base tb
  WHERE (tb.id = regular_tasks.task_id))));


--
-- Name: profiles Allow individual user update to own profile; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Allow individual user update to own profile" ON public.profiles FOR UPDATE USING ((auth.uid() = id)) WITH CHECK ((auth.uid() = id));


--
-- Name: student_mastery_progress Allow student to access their own mastery progress; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Allow student to access their own mastery progress" ON public.student_mastery_progress USING ((auth.uid() = student_id)) WITH CHECK ((auth.uid() = student_id));


--
-- Name: mastery_submission Allow student to access their own mastery submissions; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Allow student to access their own mastery submissions" ON public.mastery_submission USING ((auth.uid() = student_id)) WITH CHECK ((auth.uid() = student_id));


--
-- Name: submission Allow students to insert submission for visible tasks once; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Allow students to insert submission for visible tasks once" ON public.submission FOR INSERT WITH CHECK (((public.get_my_role() = 'student'::public.user_role) AND (student_id = auth.uid()) AND (EXISTS ( SELECT 1
   FROM public.task_base tb
  WHERE ((tb.id = submission.task_id) AND (EXISTS ( SELECT 1
           FROM (((public.unit_section us
             JOIN public.learning_unit lu ON ((us.unit_id = lu.id)))
             JOIN public.course_learning_unit_assignment clua ON ((lu.id = clua.unit_id)))
             JOIN public.course_student cs ON ((clua.course_id = cs.course_id)))
          WHERE ((us.id = tb.section_id) AND (cs.student_id = auth.uid())))))))));


--
-- Name: course_learning_unit_assignment Allow students to view assignments for their courses; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Allow students to view assignments for their courses" ON public.course_learning_unit_assignment FOR SELECT USING (((public.get_my_role() = 'student'::public.user_role) AND (EXISTS ( SELECT 1
   FROM public.course_student cs
  WHERE ((cs.course_id = course_learning_unit_assignment.course_id) AND (cs.student_id = auth.uid()))))));


--
-- Name: course Allow students to view enrolled courses; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Allow students to view enrolled courses" ON public.course FOR SELECT USING (((public.get_my_role() = 'student'::public.user_role) AND (EXISTS ( SELECT 1
   FROM public.course_student cs
  WHERE ((cs.course_id = course.id) AND (cs.student_id = auth.uid()))))));


--
-- Name: course_student Allow students to view own enrollments; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Allow students to view own enrollments" ON public.course_student FOR SELECT USING (((public.get_my_role() = 'student'::public.user_role) AND (student_id = auth.uid())));


--
-- Name: unit_section Allow students to view published sections via helper; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Allow students to view published sections via helper" ON public.unit_section FOR SELECT USING (((public.get_my_role() = 'student'::public.user_role) AND public.can_student_view_section(id)));


--
-- Name: submission Allow students to view their own submissions; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Allow students to view their own submissions" ON public.submission FOR SELECT USING (((public.get_my_role() = 'student'::public.user_role) AND (student_id = auth.uid())));


--
-- Name: course_student Allow teachers full access to course_student; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Allow teachers full access to course_student" ON public.course_student USING ((public.get_my_role() = 'teacher'::public.user_role)) WITH CHECK ((public.get_my_role() = 'teacher'::public.user_role));


--
-- Name: course_teacher Allow teachers full access to course_teacher; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Allow teachers full access to course_teacher" ON public.course_teacher USING ((public.get_my_role() = 'teacher'::public.user_role)) WITH CHECK ((public.get_my_role() = 'teacher'::public.user_role));


--
-- Name: course Allow teachers full access to courses; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Allow teachers full access to courses" ON public.course USING ((public.get_my_role() = 'teacher'::public.user_role)) WITH CHECK ((public.get_my_role() = 'teacher'::public.user_role));


--
-- Name: learning_unit Allow teachers full access to learning units; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Allow teachers full access to learning units" ON public.learning_unit USING ((public.get_my_role() = 'teacher'::public.user_role)) WITH CHECK ((public.get_my_role() = 'teacher'::public.user_role));


--
-- Name: unit_section Allow teachers full access to sections in their units; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Allow teachers full access to sections in their units" ON public.unit_section USING (((public.get_my_role() = 'teacher'::public.user_role) AND (EXISTS ( SELECT 1
   FROM public.learning_unit lu
  WHERE ((lu.id = unit_section.unit_id) AND (lu.creator_id = auth.uid())))))) WITH CHECK (((public.get_my_role() = 'teacher'::public.user_role) AND (EXISTS ( SELECT 1
   FROM public.learning_unit lu
  WHERE ((lu.id = unit_section.unit_id) AND (lu.creator_id = auth.uid()))))));


--
-- Name: task Allow teachers full access to tasks in their units; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Allow teachers full access to tasks in their units" ON public.task USING (((public.get_my_role() = 'teacher'::public.user_role) AND (EXISTS ( SELECT 1
   FROM (public.unit_section us
     JOIN public.learning_unit lu ON ((us.unit_id = lu.id)))
  WHERE ((us.id = task.section_id) AND (lu.creator_id = auth.uid())))))) WITH CHECK (((public.get_my_role() = 'teacher'::public.user_role) AND (EXISTS ( SELECT 1
   FROM (public.unit_section us
     JOIN public.learning_unit lu ON ((us.unit_id = lu.id)))
  WHERE ((us.id = task.section_id) AND (lu.creator_id = auth.uid()))))));


--
-- Name: course_learning_unit_assignment Allow teachers to assign units to courses; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Allow teachers to assign units to courses" ON public.course_learning_unit_assignment USING ((public.get_my_role() = 'teacher'::public.user_role)) WITH CHECK ((public.get_my_role() = 'teacher'::public.user_role));


--
-- Name: course_unit_section_status Allow teachers to manage section status in their units; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Allow teachers to manage section status in their units" ON public.course_unit_section_status USING (((public.get_my_role() = 'teacher'::public.user_role) AND (EXISTS ( SELECT 1
   FROM (public.unit_section us
     JOIN public.learning_unit lu ON ((us.unit_id = lu.id)))
  WHERE ((us.id = course_unit_section_status.section_id) AND (lu.creator_id = auth.uid())))))) WITH CHECK (((public.get_my_role() = 'teacher'::public.user_role) AND (EXISTS ( SELECT 1
   FROM (public.unit_section us
     JOIN public.learning_unit lu ON ((us.unit_id = lu.id)))
  WHERE ((us.id = course_unit_section_status.section_id) AND (lu.creator_id = auth.uid()))))));


--
-- Name: profiles Allow users to view profiles based on role; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Allow users to view profiles based on role" ON public.profiles FOR SELECT USING (((auth.uid() = id) OR (public.get_my_role() = 'teacher'::public.user_role)));


--
-- Name: allowed_email_domains Authenticated users can view active allowed domains; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Authenticated users can view active allowed domains" ON public.allowed_email_domains FOR SELECT TO authenticated USING ((is_active = true));


--
-- Name: mastery_log Benutzer können ihre eigenen Log-Einträge sehen; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Benutzer können ihre eigenen Log-Einträge sehen" ON public.mastery_log FOR SELECT USING ((auth.uid() = user_id));


--
-- Name: user_model_weights Deny all access to user model weights; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Deny all access to user model weights" ON public.user_model_weights USING (false) WITH CHECK (false);


--
-- Name: mastery_log Keine direkten Schreib-Operationen auf Logs erlaubt; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Keine direkten Schreib-Operationen auf Logs erlaubt" ON public.mastery_log USING (false) WITH CHECK (false);


--
-- Name: mastery_log Lehrer koennen die Log-Eintraege ihrer Schueler sehen; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Lehrer koennen die Log-Eintraege ihrer Schueler sehen" ON public.mastery_log FOR SELECT USING (((public.get_my_role() = 'teacher'::public.user_role) AND (EXISTS ( SELECT 1
   FROM (((public.course_student cs
     JOIN public.task_base t ON ((t.id = mastery_log.task_id)))
     JOIN public.unit_section us ON ((t.section_id = us.id)))
     JOIN public.course_learning_unit_assignment clua ON ((us.unit_id = clua.unit_id)))
  WHERE ((cs.student_id = mastery_log.user_id) AND (cs.course_id = clua.course_id) AND public.is_teacher_in_course(auth.uid(), cs.course_id))))));


--
-- Name: mastery_log Lehrer können die Log-Einträge ihrer Schüler sehen; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Lehrer können die Log-Einträge ihrer Schüler sehen" ON public.mastery_log FOR SELECT USING ((public.is_user_role(auth.uid(), 'teacher'::public.user_role) AND (EXISTS ( SELECT 1
   FROM (((public.course_student cs
     JOIN public.task t ON ((t.id = mastery_log.task_id)))
     JOIN public.unit_section us ON ((t.section_id = us.id)))
     JOIN public.course_learning_unit_assignment clua ON ((us.unit_id = clua.unit_id)))
  WHERE ((cs.student_id = mastery_log.user_id) AND (cs.course_id = clua.course_id) AND public.is_teacher_in_course(auth.uid(), cs.course_id))))));


--
-- Name: auth_sessions Service role full access; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Service role full access" ON public.auth_sessions TO service_role USING (true) WITH CHECK (true);


--
-- Name: auth_service_keys Service role manages API keys; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Service role manages API keys" ON public.auth_service_keys TO service_role USING (true) WITH CHECK (true);


--
-- Name: auth_sessions Session manager full access; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Session manager full access" ON public.auth_sessions TO session_manager USING (true) WITH CHECK (true);


--
-- Name: submission Students can see their own submission feedback status; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Students can see their own submission feedback status" ON public.submission FOR SELECT USING ((auth.uid() = student_id));


--
-- Name: feedback Students can submit feedback; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Students can submit feedback" ON public.feedback FOR INSERT TO authenticated WITH CHECK ((EXISTS ( SELECT 1
   FROM public.profiles
  WHERE ((profiles.id = auth.uid()) AND (profiles.role = 'student'::public.user_role)))));


--
-- Name: course_unit_section_status Students can view their section statuses; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Students can view their section statuses" ON public.course_unit_section_status FOR SELECT USING (((public.get_my_role() = 'student'::public.user_role) AND (EXISTS ( SELECT 1
   FROM public.course_student cs
  WHERE ((cs.course_id = course_unit_section_status.course_id) AND (cs.student_id = auth.uid()))))));


--
-- Name: task_base Students view tasks in published sections; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Students view tasks in published sections" ON public.task_base FOR SELECT USING (((public.get_my_role() = 'student'::public.user_role) AND (EXISTS ( SELECT 1
   FROM public.unit_section us
  WHERE (us.id = task_base.section_id)))));


--
-- Name: task Students view tasks in published sections in their courses; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Students view tasks in published sections in their courses" ON public.task FOR SELECT USING (((public.get_my_role() = 'student'::public.user_role) AND (EXISTS ( SELECT 1
   FROM public.unit_section us
  WHERE (us.id = task.section_id)))));


--
-- Name: learning_unit Students view units assigned to their courses; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Students view units assigned to their courses" ON public.learning_unit FOR SELECT USING (((public.get_my_role() = 'student'::public.user_role) AND (EXISTS ( SELECT 1
   FROM (public.course_learning_unit_assignment clua
     JOIN public.course_student cs ON ((clua.course_id = cs.course_id)))
  WHERE ((clua.unit_id = learning_unit.id) AND (cs.student_id = auth.uid()))))));


--
-- Name: feedback Teachers can view feedback; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Teachers can view feedback" ON public.feedback FOR SELECT TO authenticated USING ((EXISTS ( SELECT 1
   FROM public.profiles
  WHERE ((profiles.id = auth.uid()) AND (profiles.role = 'teacher'::public.user_role)))));


--
-- Name: submission Teachers delete submissions for tasks in their units; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Teachers delete submissions for tasks in their units" ON public.submission FOR DELETE USING (((public.get_my_role() = 'teacher'::public.user_role) AND (EXISTS ( SELECT 1
   FROM ((public.task t
     JOIN public.unit_section us ON ((t.section_id = us.id)))
     JOIN public.learning_unit lu ON ((us.unit_id = lu.id)))
  WHERE ((t.id = submission.task_id) AND (lu.creator_id = auth.uid()))))));


--
-- Name: task_base Teachers manage tasks in their units; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Teachers manage tasks in their units" ON public.task_base USING (((public.get_my_role() = 'teacher'::public.user_role) AND (EXISTS ( SELECT 1
   FROM (public.unit_section us
     JOIN public.learning_unit lu ON ((us.unit_id = lu.id)))
  WHERE ((us.id = task_base.section_id) AND (lu.creator_id = auth.uid())))))) WITH CHECK (((public.get_my_role() = 'teacher'::public.user_role) AND (EXISTS ( SELECT 1
   FROM (public.unit_section us
     JOIN public.learning_unit lu ON ((us.unit_id = lu.id)))
  WHERE ((us.id = task_base.section_id) AND (lu.creator_id = auth.uid()))))));


--
-- Name: submission Teachers update submissions for tasks in their units; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Teachers update submissions for tasks in their units" ON public.submission FOR UPDATE USING (((public.get_my_role() = 'teacher'::public.user_role) AND (EXISTS ( SELECT 1
   FROM ((public.task t
     JOIN public.unit_section us ON ((t.section_id = us.id)))
     JOIN public.learning_unit lu ON ((us.unit_id = lu.id)))
  WHERE ((t.id = submission.task_id) AND (lu.creator_id = auth.uid())))))) WITH CHECK ((public.get_my_role() = 'teacher'::public.user_role));


--
-- Name: submission Teachers view submissions for tasks in their units; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Teachers view submissions for tasks in their units" ON public.submission FOR SELECT USING (((public.get_my_role() = 'teacher'::public.user_role) AND (EXISTS ( SELECT 1
   FROM ((public.task t
     JOIN public.unit_section us ON ((t.section_id = us.id)))
     JOIN public.learning_unit lu ON ((us.unit_id = lu.id)))
  WHERE ((t.id = submission.task_id) AND (lu.creator_id = auth.uid()))))));


--
-- Name: auth_sessions Users can read own sessions; Type: POLICY; Schema: public; Owner: postgres
--

CREATE POLICY "Users can read own sessions" ON public.auth_sessions FOR SELECT TO authenticated USING ((auth.uid() = user_id));


--
-- Name: allowed_email_domains; Type: ROW SECURITY; Schema: public; Owner: postgres
--

ALTER TABLE public.allowed_email_domains ENABLE ROW LEVEL SECURITY;

--
-- Name: auth_service_keys; Type: ROW SECURITY; Schema: public; Owner: postgres
--

ALTER TABLE public.auth_service_keys ENABLE ROW LEVEL SECURITY;

--
-- Name: auth_sessions; Type: ROW SECURITY; Schema: public; Owner: postgres
--

ALTER TABLE public.auth_sessions ENABLE ROW LEVEL SECURITY;

--
-- Name: course; Type: ROW SECURITY; Schema: public; Owner: postgres
--

ALTER TABLE public.course ENABLE ROW LEVEL SECURITY;

--
-- Name: course_learning_unit_assignment; Type: ROW SECURITY; Schema: public; Owner: postgres
--

ALTER TABLE public.course_learning_unit_assignment ENABLE ROW LEVEL SECURITY;

--
-- Name: course_student; Type: ROW SECURITY; Schema: public; Owner: postgres
--

ALTER TABLE public.course_student ENABLE ROW LEVEL SECURITY;

--
-- Name: course_teacher; Type: ROW SECURITY; Schema: public; Owner: postgres
--

ALTER TABLE public.course_teacher ENABLE ROW LEVEL SECURITY;

--
-- Name: course_unit_section_status; Type: ROW SECURITY; Schema: public; Owner: postgres
--

ALTER TABLE public.course_unit_section_status ENABLE ROW LEVEL SECURITY;

--
-- Name: learning_unit; Type: ROW SECURITY; Schema: public; Owner: postgres
--

ALTER TABLE public.learning_unit ENABLE ROW LEVEL SECURITY;

--
-- Name: mastery_log; Type: ROW SECURITY; Schema: public; Owner: postgres
--

ALTER TABLE public.mastery_log ENABLE ROW LEVEL SECURITY;

--
-- Name: mastery_submission; Type: ROW SECURITY; Schema: public; Owner: postgres
--

ALTER TABLE public.mastery_submission ENABLE ROW LEVEL SECURITY;

--
-- Name: mastery_tasks; Type: ROW SECURITY; Schema: public; Owner: postgres
--

ALTER TABLE public.mastery_tasks ENABLE ROW LEVEL SECURITY;

--
-- Name: profiles; Type: ROW SECURITY; Schema: public; Owner: postgres
--

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

--
-- Name: regular_tasks; Type: ROW SECURITY; Schema: public; Owner: postgres
--

ALTER TABLE public.regular_tasks ENABLE ROW LEVEL SECURITY;

--
-- Name: student_mastery_progress; Type: ROW SECURITY; Schema: public; Owner: postgres
--

ALTER TABLE public.student_mastery_progress ENABLE ROW LEVEL SECURITY;

--
-- Name: submission; Type: ROW SECURITY; Schema: public; Owner: postgres
--

ALTER TABLE public.submission ENABLE ROW LEVEL SECURITY;

--
-- Name: task; Type: ROW SECURITY; Schema: public; Owner: postgres
--

ALTER TABLE public.task ENABLE ROW LEVEL SECURITY;

--
-- Name: task_base; Type: ROW SECURITY; Schema: public; Owner: postgres
--

ALTER TABLE public.task_base ENABLE ROW LEVEL SECURITY;

--
-- Name: unit_section; Type: ROW SECURITY; Schema: public; Owner: postgres
--

ALTER TABLE public.unit_section ENABLE ROW LEVEL SECURITY;

--
-- Name: user_model_weights; Type: ROW SECURITY; Schema: public; Owner: postgres
--

ALTER TABLE public.user_model_weights ENABLE ROW LEVEL SECURITY;

--
-- Name: messages; Type: ROW SECURITY; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER TABLE realtime.messages ENABLE ROW LEVEL SECURITY;

--
-- Name: objects Allow public insert to materials bucket; Type: POLICY; Schema: storage; Owner: supabase_storage_admin
--

CREATE POLICY "Allow public insert to materials bucket" ON storage.objects FOR INSERT WITH CHECK ((bucket_id = 'materials'::text));


--
-- Name: objects Allow public select from materials bucket; Type: POLICY; Schema: storage; Owner: supabase_storage_admin
--

CREATE POLICY "Allow public select from materials bucket" ON storage.objects FOR SELECT USING ((bucket_id = 'materials'::text));


--
-- Name: objects TEMP DEBUG Allow any insert into materials bucket; Type: POLICY; Schema: storage; Owner: supabase_storage_admin
--

CREATE POLICY "TEMP DEBUG Allow any insert into materials bucket" ON storage.objects FOR INSERT WITH CHECK ((bucket_id = 'materials'::text));


--
-- Name: buckets; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.buckets ENABLE ROW LEVEL SECURITY;

--
-- Name: buckets_analytics; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.buckets_analytics ENABLE ROW LEVEL SECURITY;

--
-- Name: iceberg_namespaces; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.iceberg_namespaces ENABLE ROW LEVEL SECURITY;

--
-- Name: iceberg_tables; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.iceberg_tables ENABLE ROW LEVEL SECURITY;

--
-- Name: objects materials_delete_session_policy; Type: POLICY; Schema: storage; Owner: supabase_storage_admin
--

CREATE POLICY materials_delete_session_policy ON storage.objects FOR DELETE TO authenticated USING (((bucket_id = 'materials'::text) AND (EXISTS ( SELECT 1
   FROM public.validate_session_and_get_user(((current_setting('request.cookies'::text, true))::json ->> 'gustav_session'::text)) auth_check(user_id, user_role, is_valid)
  WHERE (auth_check.is_valid AND (auth_check.user_role = 'teacher'::text))))));


--
-- Name: objects materials_insert_session_policy; Type: POLICY; Schema: storage; Owner: supabase_storage_admin
--

CREATE POLICY materials_insert_session_policy ON storage.objects FOR INSERT TO authenticated WITH CHECK (((bucket_id = 'materials'::text) AND (EXISTS ( SELECT 1
   FROM public.validate_session_and_get_user(((current_setting('request.cookies'::text, true))::json ->> 'gustav_session'::text)) auth_check(user_id, user_role, is_valid)
  WHERE (auth_check.is_valid AND (auth_check.user_role = 'teacher'::text))))));


--
-- Name: objects materials_update_session_policy; Type: POLICY; Schema: storage; Owner: supabase_storage_admin
--

CREATE POLICY materials_update_session_policy ON storage.objects FOR UPDATE TO authenticated USING (((bucket_id = 'materials'::text) AND (EXISTS ( SELECT 1
   FROM public.validate_session_and_get_user(((current_setting('request.cookies'::text, true))::json ->> 'gustav_session'::text)) auth_check(user_id, user_role, is_valid)
  WHERE (auth_check.is_valid AND (auth_check.user_role = 'teacher'::text)))))) WITH CHECK (((bucket_id = 'materials'::text) AND (EXISTS ( SELECT 1
   FROM public.validate_session_and_get_user(((current_setting('request.cookies'::text, true))::json ->> 'gustav_session'::text)) auth_check(user_id, user_role, is_valid)
  WHERE (auth_check.is_valid AND (auth_check.user_role = 'teacher'::text))))));


--
-- Name: migrations; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.migrations ENABLE ROW LEVEL SECURITY;

--
-- Name: objects; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;

--
-- Name: prefixes; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.prefixes ENABLE ROW LEVEL SECURITY;

--
-- Name: objects public_read_section_materials; Type: POLICY; Schema: storage; Owner: supabase_storage_admin
--

CREATE POLICY public_read_section_materials ON storage.objects FOR SELECT USING ((bucket_id = 'section_materials'::text));


--
-- Name: s3_multipart_uploads; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.s3_multipart_uploads ENABLE ROW LEVEL SECURITY;

--
-- Name: s3_multipart_uploads_parts; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.s3_multipart_uploads_parts ENABLE ROW LEVEL SECURITY;

--
-- Name: objects section_materials_delete_session_policy; Type: POLICY; Schema: storage; Owner: supabase_storage_admin
--

CREATE POLICY section_materials_delete_session_policy ON storage.objects FOR DELETE TO authenticated USING (((bucket_id = 'section_materials'::text) AND (EXISTS ( SELECT 1
   FROM public.validate_session_and_get_user(((current_setting('request.cookies'::text, true))::json ->> 'gustav_session'::text)) auth_check(user_id, user_role, is_valid)
  WHERE (auth_check.is_valid AND (auth_check.user_role = 'teacher'::text) AND public.is_creator_of_unit(auth_check.user_id, public.get_unit_id_from_path(objects.name)))))));


--
-- Name: objects section_materials_insert_session_policy; Type: POLICY; Schema: storage; Owner: supabase_storage_admin
--

CREATE POLICY section_materials_insert_session_policy ON storage.objects FOR INSERT TO authenticated WITH CHECK (((bucket_id = 'section_materials'::text) AND (EXISTS ( SELECT 1
   FROM public.validate_session_and_get_user(((current_setting('request.cookies'::text, true))::json ->> 'gustav_session'::text)) auth_check(user_id, user_role, is_valid)
  WHERE (auth_check.is_valid AND (auth_check.user_role = 'teacher'::text) AND public.is_creator_of_unit(auth_check.user_id, public.get_unit_id_from_path(objects.name)))))));


--
-- Name: objects section_materials_update_session_policy; Type: POLICY; Schema: storage; Owner: supabase_storage_admin
--

CREATE POLICY section_materials_update_session_policy ON storage.objects FOR UPDATE TO authenticated USING (((bucket_id = 'section_materials'::text) AND (EXISTS ( SELECT 1
   FROM public.validate_session_and_get_user(((current_setting('request.cookies'::text, true))::json ->> 'gustav_session'::text)) auth_check(user_id, user_role, is_valid)
  WHERE (auth_check.is_valid AND (auth_check.user_role = 'teacher'::text) AND public.is_creator_of_unit(auth_check.user_id, public.get_unit_id_from_path(objects.name))))))) WITH CHECK (((bucket_id = 'section_materials'::text) AND (EXISTS ( SELECT 1
   FROM public.validate_session_and_get_user(((current_setting('request.cookies'::text, true))::json ->> 'gustav_session'::text)) auth_check(user_id, user_role, is_valid)
  WHERE (auth_check.is_valid AND (auth_check.user_role = 'teacher'::text) AND public.is_creator_of_unit(auth_check.user_id, public.get_unit_id_from_path(objects.name)))))));


--
-- Name: objects submissions_delete_session_policy; Type: POLICY; Schema: storage; Owner: supabase_storage_admin
--

CREATE POLICY submissions_delete_session_policy ON storage.objects FOR DELETE TO authenticated USING (((bucket_id = 'submissions'::text) AND ((storage.foldername(name))[1] = concat('student_', (public.validate_storage_session_user(name))::text))));


--
-- Name: objects submissions_insert_session_policy; Type: POLICY; Schema: storage; Owner: supabase_storage_admin
--

CREATE POLICY submissions_insert_session_policy ON storage.objects FOR INSERT TO authenticated WITH CHECK (((bucket_id = 'submissions'::text) AND ((storage.foldername(name))[1] = concat('student_', (public.validate_storage_session_user(name))::text))));


--
-- Name: objects submissions_select_session_policy; Type: POLICY; Schema: storage; Owner: supabase_storage_admin
--

CREATE POLICY submissions_select_session_policy ON storage.objects FOR SELECT TO authenticated USING (((bucket_id = 'submissions'::text) AND (((storage.foldername(name))[1] = concat('student_', (public.validate_storage_session_user(name))::text)) OR (EXISTS ( SELECT 1
   FROM public.validate_session_and_get_user(((current_setting('request.cookies'::text, true))::json ->> 'gustav_session'::text)) auth_check(user_id, user_role, is_valid)
  WHERE (auth_check.is_valid AND (auth_check.user_role = 'teacher'::text) AND (EXISTS ( SELECT 1
           FROM ((((public.course c
             JOIN public.course_learning_unit_assignment cla ON ((cla.course_id = c.id)))
             JOIN public.learning_unit lu ON ((lu.id = cla.unit_id)))
             JOIN public.unit_section us ON ((us.unit_id = lu.id)))
             JOIN public.task_base tb ON ((tb.section_id = us.id)))
          WHERE ((c.creator_id = auth_check.user_id) AND ((tb.id)::text = split_part((storage.foldername(c.name))[2], '_'::text, 2)))))))))));


--
-- Name: supabase_realtime; Type: PUBLICATION; Schema: -; Owner: postgres
--

CREATE PUBLICATION supabase_realtime WITH (publish = 'insert, update, delete, truncate');


ALTER PUBLICATION supabase_realtime OWNER TO postgres;

--
-- Name: SCHEMA auth; Type: ACL; Schema: -; Owner: supabase_admin
--

GRANT USAGE ON SCHEMA auth TO anon;
GRANT USAGE ON SCHEMA auth TO authenticated;
GRANT USAGE ON SCHEMA auth TO service_role;
GRANT ALL ON SCHEMA auth TO supabase_auth_admin;
GRANT ALL ON SCHEMA auth TO dashboard_user;
GRANT USAGE ON SCHEMA auth TO postgres;


--
-- Name: SCHEMA extensions; Type: ACL; Schema: -; Owner: postgres
--

GRANT USAGE ON SCHEMA extensions TO anon;
GRANT USAGE ON SCHEMA extensions TO authenticated;
GRANT USAGE ON SCHEMA extensions TO service_role;
GRANT ALL ON SCHEMA extensions TO dashboard_user;


--
-- Name: SCHEMA net; Type: ACL; Schema: -; Owner: supabase_admin
--

GRANT USAGE ON SCHEMA net TO supabase_functions_admin;
GRANT USAGE ON SCHEMA net TO postgres;
GRANT USAGE ON SCHEMA net TO anon;
GRANT USAGE ON SCHEMA net TO authenticated;
GRANT USAGE ON SCHEMA net TO service_role;


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: pg_database_owner
--

GRANT USAGE ON SCHEMA public TO postgres;
GRANT USAGE ON SCHEMA public TO anon;
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT USAGE ON SCHEMA public TO service_role;
GRANT USAGE ON SCHEMA public TO supabase_storage_admin;
GRANT USAGE ON SCHEMA public TO session_manager;


--
-- Name: SCHEMA realtime; Type: ACL; Schema: -; Owner: supabase_admin
--

GRANT USAGE ON SCHEMA realtime TO postgres;
GRANT USAGE ON SCHEMA realtime TO anon;
GRANT USAGE ON SCHEMA realtime TO authenticated;
GRANT USAGE ON SCHEMA realtime TO service_role;
GRANT ALL ON SCHEMA realtime TO supabase_realtime_admin;


--
-- Name: SCHEMA storage; Type: ACL; Schema: -; Owner: supabase_admin
--

GRANT USAGE ON SCHEMA storage TO postgres WITH GRANT OPTION;
GRANT USAGE ON SCHEMA storage TO anon;
GRANT USAGE ON SCHEMA storage TO authenticated;
GRANT USAGE ON SCHEMA storage TO service_role;
GRANT ALL ON SCHEMA storage TO supabase_storage_admin;
GRANT ALL ON SCHEMA storage TO dashboard_user;
SET SESSION AUTHORIZATION postgres;
GRANT USAGE ON SCHEMA storage TO anon;
RESET SESSION AUTHORIZATION;
SET SESSION AUTHORIZATION postgres;
GRANT USAGE ON SCHEMA storage TO authenticated;
RESET SESSION AUTHORIZATION;
SET SESSION AUTHORIZATION postgres;
GRANT USAGE ON SCHEMA storage TO service_role;
RESET SESSION AUTHORIZATION;
SET SESSION AUTHORIZATION postgres;
GRANT USAGE ON SCHEMA storage TO supabase_storage_admin;
RESET SESSION AUTHORIZATION;
SET SESSION AUTHORIZATION postgres;
GRANT USAGE ON SCHEMA storage TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: SCHEMA supabase_functions; Type: ACL; Schema: -; Owner: supabase_admin
--

GRANT USAGE ON SCHEMA supabase_functions TO postgres;
GRANT USAGE ON SCHEMA supabase_functions TO anon;
GRANT USAGE ON SCHEMA supabase_functions TO authenticated;
GRANT USAGE ON SCHEMA supabase_functions TO service_role;
GRANT ALL ON SCHEMA supabase_functions TO supabase_functions_admin;


--
-- Name: SCHEMA vault; Type: ACL; Schema: -; Owner: supabase_admin
--

GRANT USAGE ON SCHEMA vault TO postgres WITH GRANT OPTION;
GRANT USAGE ON SCHEMA vault TO service_role;
SET SESSION AUTHORIZATION postgres;
GRANT USAGE ON SCHEMA vault TO service_role;
RESET SESSION AUTHORIZATION;


--
-- Name: TYPE user_role; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TYPE public.user_role TO anon;
GRANT ALL ON TYPE public.user_role TO authenticated;
GRANT ALL ON TYPE public.user_role TO supabase_storage_admin;


--
-- Name: FUNCTION email(); Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON FUNCTION auth.email() TO dashboard_user;


--
-- Name: FUNCTION jwt(); Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON FUNCTION auth.jwt() TO postgres;
GRANT ALL ON FUNCTION auth.jwt() TO dashboard_user;


--
-- Name: FUNCTION role(); Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON FUNCTION auth.role() TO dashboard_user;


--
-- Name: FUNCTION uid(); Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON FUNCTION auth.uid() TO dashboard_user;


--
-- Name: FUNCTION armor(bytea); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.armor(bytea) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.armor(bytea) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.armor(bytea) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION armor(bytea, text[], text[]); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.armor(bytea, text[], text[]) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.armor(bytea, text[], text[]) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.armor(bytea, text[], text[]) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION crypt(text, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.crypt(text, text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.crypt(text, text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.crypt(text, text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION dearmor(text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.dearmor(text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.dearmor(text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.dearmor(text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION decrypt(bytea, bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.decrypt(bytea, bytea, text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.decrypt(bytea, bytea, text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.decrypt(bytea, bytea, text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION decrypt_iv(bytea, bytea, bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.decrypt_iv(bytea, bytea, bytea, text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.decrypt_iv(bytea, bytea, bytea, text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.decrypt_iv(bytea, bytea, bytea, text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION digest(bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.digest(bytea, text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.digest(bytea, text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.digest(bytea, text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION digest(text, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.digest(text, text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.digest(text, text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.digest(text, text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION encrypt(bytea, bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.encrypt(bytea, bytea, text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.encrypt(bytea, bytea, text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.encrypt(bytea, bytea, text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION encrypt_iv(bytea, bytea, bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.encrypt_iv(bytea, bytea, bytea, text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.encrypt_iv(bytea, bytea, bytea, text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.encrypt_iv(bytea, bytea, bytea, text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION gen_random_bytes(integer); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.gen_random_bytes(integer) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.gen_random_bytes(integer) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.gen_random_bytes(integer) TO authenticator;
RESET SESSION AUTHORIZATION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.gen_random_bytes(integer) TO authenticated;
RESET SESSION AUTHORIZATION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.gen_random_bytes(integer) TO anon;
RESET SESSION AUTHORIZATION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.gen_random_bytes(integer) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION gen_random_uuid(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.gen_random_uuid() TO dashboard_user;
GRANT ALL ON FUNCTION extensions.gen_random_uuid() TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.gen_random_uuid() TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION gen_salt(text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.gen_salt(text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.gen_salt(text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.gen_salt(text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION gen_salt(text, integer); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.gen_salt(text, integer) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.gen_salt(text, integer) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.gen_salt(text, integer) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION grant_pg_cron_access(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

REVOKE ALL ON FUNCTION extensions.grant_pg_cron_access() FROM supabase_admin;
GRANT ALL ON FUNCTION extensions.grant_pg_cron_access() TO supabase_admin WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.grant_pg_cron_access() TO dashboard_user;


--
-- Name: FUNCTION grant_pg_graphql_access(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.grant_pg_graphql_access() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION grant_pg_net_access(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

REVOKE ALL ON FUNCTION extensions.grant_pg_net_access() FROM supabase_admin;
GRANT ALL ON FUNCTION extensions.grant_pg_net_access() TO supabase_admin WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.grant_pg_net_access() TO dashboard_user;


--
-- Name: FUNCTION hmac(bytea, bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.hmac(bytea, bytea, text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.hmac(bytea, bytea, text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.hmac(bytea, bytea, text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION hmac(text, text, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.hmac(text, text, text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.hmac(text, text, text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.hmac(text, text, text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION pg_stat_statements(showtext boolean, OUT userid oid, OUT dbid oid, OUT toplevel boolean, OUT queryid bigint, OUT query text, OUT plans bigint, OUT total_plan_time double precision, OUT min_plan_time double precision, OUT max_plan_time double precision, OUT mean_plan_time double precision, OUT stddev_plan_time double precision, OUT calls bigint, OUT total_exec_time double precision, OUT min_exec_time double precision, OUT max_exec_time double precision, OUT mean_exec_time double precision, OUT stddev_exec_time double precision, OUT rows bigint, OUT shared_blks_hit bigint, OUT shared_blks_read bigint, OUT shared_blks_dirtied bigint, OUT shared_blks_written bigint, OUT local_blks_hit bigint, OUT local_blks_read bigint, OUT local_blks_dirtied bigint, OUT local_blks_written bigint, OUT temp_blks_read bigint, OUT temp_blks_written bigint, OUT shared_blk_read_time double precision, OUT shared_blk_write_time double precision, OUT local_blk_read_time double precision, OUT local_blk_write_time double precision, OUT temp_blk_read_time double precision, OUT temp_blk_write_time double precision, OUT wal_records bigint, OUT wal_fpi bigint, OUT wal_bytes numeric, OUT jit_functions bigint, OUT jit_generation_time double precision, OUT jit_inlining_count bigint, OUT jit_inlining_time double precision, OUT jit_optimization_count bigint, OUT jit_optimization_time double precision, OUT jit_emission_count bigint, OUT jit_emission_time double precision, OUT jit_deform_count bigint, OUT jit_deform_time double precision, OUT stats_since timestamp with time zone, OUT minmax_stats_since timestamp with time zone); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pg_stat_statements(showtext boolean, OUT userid oid, OUT dbid oid, OUT toplevel boolean, OUT queryid bigint, OUT query text, OUT plans bigint, OUT total_plan_time double precision, OUT min_plan_time double precision, OUT max_plan_time double precision, OUT mean_plan_time double precision, OUT stddev_plan_time double precision, OUT calls bigint, OUT total_exec_time double precision, OUT min_exec_time double precision, OUT max_exec_time double precision, OUT mean_exec_time double precision, OUT stddev_exec_time double precision, OUT rows bigint, OUT shared_blks_hit bigint, OUT shared_blks_read bigint, OUT shared_blks_dirtied bigint, OUT shared_blks_written bigint, OUT local_blks_hit bigint, OUT local_blks_read bigint, OUT local_blks_dirtied bigint, OUT local_blks_written bigint, OUT temp_blks_read bigint, OUT temp_blks_written bigint, OUT shared_blk_read_time double precision, OUT shared_blk_write_time double precision, OUT local_blk_read_time double precision, OUT local_blk_write_time double precision, OUT temp_blk_read_time double precision, OUT temp_blk_write_time double precision, OUT wal_records bigint, OUT wal_fpi bigint, OUT wal_bytes numeric, OUT jit_functions bigint, OUT jit_generation_time double precision, OUT jit_inlining_count bigint, OUT jit_inlining_time double precision, OUT jit_optimization_count bigint, OUT jit_optimization_time double precision, OUT jit_emission_count bigint, OUT jit_emission_time double precision, OUT jit_deform_count bigint, OUT jit_deform_time double precision, OUT stats_since timestamp with time zone, OUT minmax_stats_since timestamp with time zone) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pg_stat_statements_info(OUT dealloc bigint, OUT stats_reset timestamp with time zone); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pg_stat_statements_info(OUT dealloc bigint, OUT stats_reset timestamp with time zone) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pg_stat_statements_reset(userid oid, dbid oid, queryid bigint, minmax_only boolean); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pg_stat_statements_reset(userid oid, dbid oid, queryid bigint, minmax_only boolean) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgp_armor_headers(text, OUT key text, OUT value text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_armor_headers(text, OUT key text, OUT value text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.pgp_armor_headers(text, OUT key text, OUT value text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.pgp_armor_headers(text, OUT key text, OUT value text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION pgp_key_id(bytea); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_key_id(bytea) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.pgp_key_id(bytea) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.pgp_key_id(bytea) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION pgp_pub_decrypt(bytea, bytea); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION pgp_pub_decrypt(bytea, bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea, text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea, text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea, text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION pgp_pub_decrypt(bytea, bytea, text, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea, text, text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea, text, text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea, text, text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION pgp_pub_decrypt_bytea(bytea, bytea); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION pgp_pub_decrypt_bytea(bytea, bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea, text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea, text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea, text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION pgp_pub_decrypt_bytea(bytea, bytea, text, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea, text, text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea, text, text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea, text, text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION pgp_pub_encrypt(text, bytea); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt(text, bytea) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt(text, bytea) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt(text, bytea) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION pgp_pub_encrypt(text, bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt(text, bytea, text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt(text, bytea, text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt(text, bytea, text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION pgp_pub_encrypt_bytea(bytea, bytea); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt_bytea(bytea, bytea) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt_bytea(bytea, bytea) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt_bytea(bytea, bytea) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION pgp_pub_encrypt_bytea(bytea, bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt_bytea(bytea, bytea, text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt_bytea(bytea, bytea, text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt_bytea(bytea, bytea, text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION pgp_sym_decrypt(bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt(bytea, text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt(bytea, text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt(bytea, text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION pgp_sym_decrypt(bytea, text, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt(bytea, text, text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt(bytea, text, text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt(bytea, text, text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION pgp_sym_decrypt_bytea(bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt_bytea(bytea, text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt_bytea(bytea, text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt_bytea(bytea, text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION pgp_sym_decrypt_bytea(bytea, text, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt_bytea(bytea, text, text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt_bytea(bytea, text, text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt_bytea(bytea, text, text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION pgp_sym_encrypt(text, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt(text, text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt(text, text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt(text, text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION pgp_sym_encrypt(text, text, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt(text, text, text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt(text, text, text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt(text, text, text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION pgp_sym_encrypt_bytea(bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt_bytea(bytea, text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt_bytea(bytea, text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt_bytea(bytea, text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION pgp_sym_encrypt_bytea(bytea, text, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt_bytea(bytea, text, text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt_bytea(bytea, text, text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt_bytea(bytea, text, text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION pgrst_ddl_watch(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgrst_ddl_watch() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgrst_drop_watch(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgrst_drop_watch() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION set_graphql_placeholder(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.set_graphql_placeholder() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION uuid_generate_v1(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.uuid_generate_v1() TO dashboard_user;
GRANT ALL ON FUNCTION extensions.uuid_generate_v1() TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.uuid_generate_v1() TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION uuid_generate_v1mc(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.uuid_generate_v1mc() TO dashboard_user;
GRANT ALL ON FUNCTION extensions.uuid_generate_v1mc() TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.uuid_generate_v1mc() TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION uuid_generate_v3(namespace uuid, name text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.uuid_generate_v3(namespace uuid, name text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.uuid_generate_v3(namespace uuid, name text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.uuid_generate_v3(namespace uuid, name text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION uuid_generate_v4(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.uuid_generate_v4() TO dashboard_user;
GRANT ALL ON FUNCTION extensions.uuid_generate_v4() TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.uuid_generate_v4() TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION uuid_generate_v5(namespace uuid, name text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.uuid_generate_v5(namespace uuid, name text) TO dashboard_user;
GRANT ALL ON FUNCTION extensions.uuid_generate_v5(namespace uuid, name text) TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.uuid_generate_v5(namespace uuid, name text) TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION uuid_nil(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.uuid_nil() TO dashboard_user;
GRANT ALL ON FUNCTION extensions.uuid_nil() TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.uuid_nil() TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION uuid_ns_dns(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.uuid_ns_dns() TO dashboard_user;
GRANT ALL ON FUNCTION extensions.uuid_ns_dns() TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.uuid_ns_dns() TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION uuid_ns_oid(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.uuid_ns_oid() TO dashboard_user;
GRANT ALL ON FUNCTION extensions.uuid_ns_oid() TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.uuid_ns_oid() TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION uuid_ns_url(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.uuid_ns_url() TO dashboard_user;
GRANT ALL ON FUNCTION extensions.uuid_ns_url() TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.uuid_ns_url() TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION uuid_ns_x500(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.uuid_ns_x500() TO dashboard_user;
GRANT ALL ON FUNCTION extensions.uuid_ns_x500() TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION extensions.uuid_ns_x500() TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION graphql("operationName" text, query text, variables jsonb, extensions jsonb); Type: ACL; Schema: graphql_public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION graphql_public.graphql("operationName" text, query text, variables jsonb, extensions jsonb) TO postgres;
GRANT ALL ON FUNCTION graphql_public.graphql("operationName" text, query text, variables jsonb, extensions jsonb) TO anon;
GRANT ALL ON FUNCTION graphql_public.graphql("operationName" text, query text, variables jsonb, extensions jsonb) TO authenticated;
GRANT ALL ON FUNCTION graphql_public.graphql("operationName" text, query text, variables jsonb, extensions jsonb) TO service_role;


--
-- Name: FUNCTION http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer); Type: ACL; Schema: net; Owner: supabase_admin
--

REVOKE ALL ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) FROM PUBLIC;
GRANT ALL ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) TO supabase_functions_admin;
GRANT ALL ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) TO postgres;
GRANT ALL ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) TO anon;
GRANT ALL ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) TO authenticated;
GRANT ALL ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) TO service_role;


--
-- Name: FUNCTION http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer); Type: ACL; Schema: net; Owner: supabase_admin
--

REVOKE ALL ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) FROM PUBLIC;
GRANT ALL ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) TO supabase_functions_admin;
GRANT ALL ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) TO postgres;
GRANT ALL ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) TO anon;
GRANT ALL ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) TO authenticated;
GRANT ALL ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) TO service_role;


--
-- Name: FUNCTION get_auth(p_usename text); Type: ACL; Schema: pgbouncer; Owner: supabase_admin
--

REVOKE ALL ON FUNCTION pgbouncer.get_auth(p_usename text) FROM PUBLIC;
GRANT ALL ON FUNCTION pgbouncer.get_auth(p_usename text) TO pgbouncer;
GRANT ALL ON FUNCTION pgbouncer.get_auth(p_usename text) TO postgres;


--
-- Name: FUNCTION _get_submission_status_matrix_uncached(p_session_id text, p_course_id uuid, p_unit_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public._get_submission_status_matrix_uncached(p_session_id text, p_course_id uuid, p_unit_id uuid) TO anon;
GRANT ALL ON FUNCTION public._get_submission_status_matrix_uncached(p_session_id text, p_course_id uuid, p_unit_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public._get_submission_status_matrix_uncached(p_session_id text, p_course_id uuid, p_unit_id uuid) TO service_role;


--
-- Name: FUNCTION add_user_to_course(p_session_id text, p_user_id uuid, p_course_id uuid, p_role text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.add_user_to_course(p_session_id text, p_user_id uuid, p_course_id uuid, p_role text) TO anon;
GRANT ALL ON FUNCTION public.add_user_to_course(p_session_id text, p_user_id uuid, p_course_id uuid, p_role text) TO authenticated;
GRANT ALL ON FUNCTION public.add_user_to_course(p_session_id text, p_user_id uuid, p_course_id uuid, p_role text) TO service_role;


--
-- Name: FUNCTION assign_unit_to_course(p_session_id text, p_unit_id uuid, p_course_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.assign_unit_to_course(p_session_id text, p_unit_id uuid, p_course_id uuid) TO anon;
GRANT ALL ON FUNCTION public.assign_unit_to_course(p_session_id text, p_unit_id uuid, p_course_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.assign_unit_to_course(p_session_id text, p_unit_id uuid, p_course_id uuid) TO service_role;


--
-- Name: FUNCTION calculate_learning_streak(p_session_id text, p_student_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.calculate_learning_streak(p_session_id text, p_student_id uuid) TO anon;
GRANT ALL ON FUNCTION public.calculate_learning_streak(p_session_id text, p_student_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.calculate_learning_streak(p_session_id text, p_student_id uuid) TO service_role;


--
-- Name: FUNCTION can_student_view_section(section_id_to_check uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.can_student_view_section(section_id_to_check uuid) TO anon;
GRANT ALL ON FUNCTION public.can_student_view_section(section_id_to_check uuid) TO authenticated;
GRANT ALL ON FUNCTION public.can_student_view_section(section_id_to_check uuid) TO service_role;


--
-- Name: FUNCTION can_submit_task(p_student_id uuid, p_task_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.can_submit_task(p_student_id uuid, p_task_id uuid) TO anon;
GRANT ALL ON FUNCTION public.can_submit_task(p_student_id uuid, p_task_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.can_submit_task(p_student_id uuid, p_task_id uuid) TO service_role;


--
-- Name: FUNCTION cleanup_expired_sessions(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.cleanup_expired_sessions() TO anon;
GRANT ALL ON FUNCTION public.cleanup_expired_sessions() TO authenticated;
GRANT ALL ON FUNCTION public.cleanup_expired_sessions() TO service_role;
GRANT ALL ON FUNCTION public.cleanup_expired_sessions() TO session_manager;


--
-- Name: FUNCTION cleanup_session_rate_limits(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.cleanup_session_rate_limits() TO anon;
GRANT ALL ON FUNCTION public.cleanup_session_rate_limits() TO authenticated;
GRANT ALL ON FUNCTION public.cleanup_session_rate_limits() TO service_role;


--
-- Name: FUNCTION create_course(p_session_id text, p_name text, p_description text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.create_course(p_session_id text, p_name text, p_description text) TO anon;
GRANT ALL ON FUNCTION public.create_course(p_session_id text, p_name text, p_description text) TO authenticated;
GRANT ALL ON FUNCTION public.create_course(p_session_id text, p_name text, p_description text) TO service_role;


--
-- Name: FUNCTION create_learning_unit(p_session_id text, p_title text, p_description text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.create_learning_unit(p_session_id text, p_title text, p_description text) TO anon;
GRANT ALL ON FUNCTION public.create_learning_unit(p_session_id text, p_title text, p_description text) TO authenticated;
GRANT ALL ON FUNCTION public.create_learning_unit(p_session_id text, p_title text, p_description text) TO service_role;


--
-- Name: FUNCTION create_mastery_task(p_session_id text, p_section_id uuid, p_instruction text, p_task_type text, p_order_in_section integer, p_difficulty_level integer, p_assessment_criteria jsonb); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.create_mastery_task(p_session_id text, p_section_id uuid, p_instruction text, p_task_type text, p_order_in_section integer, p_difficulty_level integer, p_assessment_criteria jsonb) TO anon;
GRANT ALL ON FUNCTION public.create_mastery_task(p_session_id text, p_section_id uuid, p_instruction text, p_task_type text, p_order_in_section integer, p_difficulty_level integer, p_assessment_criteria jsonb) TO authenticated;
GRANT ALL ON FUNCTION public.create_mastery_task(p_session_id text, p_section_id uuid, p_instruction text, p_task_type text, p_order_in_section integer, p_difficulty_level integer, p_assessment_criteria jsonb) TO service_role;


--
-- Name: FUNCTION create_regular_task(p_session_id text, p_section_id uuid, p_instruction text, p_task_type text, p_order_in_section integer, p_max_attempts integer, p_assessment_criteria jsonb); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.create_regular_task(p_session_id text, p_section_id uuid, p_instruction text, p_task_type text, p_order_in_section integer, p_max_attempts integer, p_assessment_criteria jsonb) TO anon;
GRANT ALL ON FUNCTION public.create_regular_task(p_session_id text, p_section_id uuid, p_instruction text, p_task_type text, p_order_in_section integer, p_max_attempts integer, p_assessment_criteria jsonb) TO authenticated;
GRANT ALL ON FUNCTION public.create_regular_task(p_session_id text, p_section_id uuid, p_instruction text, p_task_type text, p_order_in_section integer, p_max_attempts integer, p_assessment_criteria jsonb) TO service_role;


--
-- Name: FUNCTION create_section(p_session_id text, p_unit_id uuid, p_title text, p_description text, p_materials jsonb); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.create_section(p_session_id text, p_unit_id uuid, p_title text, p_description text, p_materials jsonb) TO anon;
GRANT ALL ON FUNCTION public.create_section(p_session_id text, p_unit_id uuid, p_title text, p_description text, p_materials jsonb) TO authenticated;
GRANT ALL ON FUNCTION public.create_section(p_session_id text, p_unit_id uuid, p_title text, p_description text, p_materials jsonb) TO service_role;


--
-- Name: FUNCTION create_session(p_user_id uuid, p_user_email text, p_user_role text, p_data jsonb, p_expires_in interval, p_ip_address inet, p_user_agent text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.create_session(p_user_id uuid, p_user_email text, p_user_role text, p_data jsonb, p_expires_in interval, p_ip_address inet, p_user_agent text) TO anon;
GRANT ALL ON FUNCTION public.create_session(p_user_id uuid, p_user_email text, p_user_role text, p_data jsonb, p_expires_in interval, p_ip_address inet, p_user_agent text) TO authenticated;
GRANT ALL ON FUNCTION public.create_session(p_user_id uuid, p_user_email text, p_user_role text, p_data jsonb, p_expires_in interval, p_ip_address inet, p_user_agent text) TO service_role;


--
-- Name: FUNCTION create_session_for_auth_service(p_user_id uuid, p_user_email text, p_user_role text, p_data jsonb, p_expires_in interval, p_ip_address inet, p_user_agent text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.create_session_for_auth_service(p_user_id uuid, p_user_email text, p_user_role text, p_data jsonb, p_expires_in interval, p_ip_address inet, p_user_agent text) TO anon;
GRANT ALL ON FUNCTION public.create_session_for_auth_service(p_user_id uuid, p_user_email text, p_user_role text, p_data jsonb, p_expires_in interval, p_ip_address inet, p_user_agent text) TO authenticated;
GRANT ALL ON FUNCTION public.create_session_for_auth_service(p_user_id uuid, p_user_email text, p_user_role text, p_data jsonb, p_expires_in interval, p_ip_address inet, p_user_agent text) TO service_role;


--
-- Name: FUNCTION create_session_with_api_key(p_api_key text, p_session_id character varying, p_user_id uuid, p_user_email text, p_user_role text, p_data jsonb, p_expires_at timestamp with time zone, p_ip_address inet, p_user_agent text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.create_session_with_api_key(p_api_key text, p_session_id character varying, p_user_id uuid, p_user_email text, p_user_role text, p_data jsonb, p_expires_at timestamp with time zone, p_ip_address inet, p_user_agent text) TO anon;
GRANT ALL ON FUNCTION public.create_session_with_api_key(p_api_key text, p_session_id character varying, p_user_id uuid, p_user_email text, p_user_role text, p_data jsonb, p_expires_at timestamp with time zone, p_ip_address inet, p_user_agent text) TO authenticated;
GRANT ALL ON FUNCTION public.create_session_with_api_key(p_api_key text, p_session_id character varying, p_user_id uuid, p_user_email text, p_user_role text, p_data jsonb, p_expires_at timestamp with time zone, p_ip_address inet, p_user_agent text) TO service_role;


--
-- Name: FUNCTION create_submission(p_session_id text, p_task_id uuid, p_submission_text text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.create_submission(p_session_id text, p_task_id uuid, p_submission_text text) TO anon;
GRANT ALL ON FUNCTION public.create_submission(p_session_id text, p_task_id uuid, p_submission_text text) TO authenticated;
GRANT ALL ON FUNCTION public.create_submission(p_session_id text, p_task_id uuid, p_submission_text text) TO service_role;


--
-- Name: FUNCTION create_task_in_new_structure(p_session_id text, p_section_id uuid, p_title text, p_prompt text, p_task_type text, p_max_attempts integer, p_grading_criteria text[], p_difficulty_level integer, p_concept_explanation text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.create_task_in_new_structure(p_session_id text, p_section_id uuid, p_title text, p_prompt text, p_task_type text, p_max_attempts integer, p_grading_criteria text[], p_difficulty_level integer, p_concept_explanation text) TO anon;
GRANT ALL ON FUNCTION public.create_task_in_new_structure(p_session_id text, p_section_id uuid, p_title text, p_prompt text, p_task_type text, p_max_attempts integer, p_grading_criteria text[], p_difficulty_level integer, p_concept_explanation text) TO authenticated;
GRANT ALL ON FUNCTION public.create_task_in_new_structure(p_session_id text, p_section_id uuid, p_title text, p_prompt text, p_task_type text, p_max_attempts integer, p_grading_criteria text[], p_difficulty_level integer, p_concept_explanation text) TO service_role;


--
-- Name: FUNCTION create_task_in_new_structure(p_session_id text, p_section_id uuid, p_title text, p_prompt text, p_task_type text, p_is_mastery boolean, p_order_in_section integer, p_max_attempts integer, p_grading_criteria text[], p_difficulty_level integer, p_concept_explanation text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.create_task_in_new_structure(p_session_id text, p_section_id uuid, p_title text, p_prompt text, p_task_type text, p_is_mastery boolean, p_order_in_section integer, p_max_attempts integer, p_grading_criteria text[], p_difficulty_level integer, p_concept_explanation text) TO anon;
GRANT ALL ON FUNCTION public.create_task_in_new_structure(p_session_id text, p_section_id uuid, p_title text, p_prompt text, p_task_type text, p_is_mastery boolean, p_order_in_section integer, p_max_attempts integer, p_grading_criteria text[], p_difficulty_level integer, p_concept_explanation text) TO authenticated;
GRANT ALL ON FUNCTION public.create_task_in_new_structure(p_session_id text, p_section_id uuid, p_title text, p_prompt text, p_task_type text, p_is_mastery boolean, p_order_in_section integer, p_max_attempts integer, p_grading_criteria text[], p_difficulty_level integer, p_concept_explanation text) TO service_role;


--
-- Name: FUNCTION delete_course(p_session_id text, p_course_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.delete_course(p_session_id text, p_course_id uuid) TO anon;
GRANT ALL ON FUNCTION public.delete_course(p_session_id text, p_course_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.delete_course(p_session_id text, p_course_id uuid) TO service_role;


--
-- Name: FUNCTION delete_learning_unit(p_session_id text, p_unit_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.delete_learning_unit(p_session_id text, p_unit_id uuid) TO anon;
GRANT ALL ON FUNCTION public.delete_learning_unit(p_session_id text, p_unit_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.delete_learning_unit(p_session_id text, p_unit_id uuid) TO service_role;


--
-- Name: FUNCTION delete_session(p_session_id character varying); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.delete_session(p_session_id character varying) TO anon;
GRANT ALL ON FUNCTION public.delete_session(p_session_id character varying) TO authenticated;
GRANT ALL ON FUNCTION public.delete_session(p_session_id character varying) TO service_role;


--
-- Name: FUNCTION delete_task_in_new_structure(p_session_id text, p_task_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.delete_task_in_new_structure(p_session_id text, p_task_id uuid) TO anon;
GRANT ALL ON FUNCTION public.delete_task_in_new_structure(p_session_id text, p_task_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.delete_task_in_new_structure(p_session_id text, p_task_id uuid) TO service_role;


--
-- Name: FUNCTION enforce_session_limit(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.enforce_session_limit() TO anon;
GRANT ALL ON FUNCTION public.enforce_session_limit() TO authenticated;
GRANT ALL ON FUNCTION public.enforce_session_limit() TO service_role;


--
-- Name: FUNCTION ensure_feedback_consistency(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.ensure_feedback_consistency() TO anon;
GRANT ALL ON FUNCTION public.ensure_feedback_consistency() TO authenticated;
GRANT ALL ON FUNCTION public.ensure_feedback_consistency() TO service_role;


--
-- Name: FUNCTION get_all_feedback(p_session_id text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_all_feedback(p_session_id text) TO anon;
GRANT ALL ON FUNCTION public.get_all_feedback(p_session_id text) TO authenticated;
GRANT ALL ON FUNCTION public.get_all_feedback(p_session_id text) TO service_role;


--
-- Name: FUNCTION get_course_by_id(p_session_id text, p_course_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_course_by_id(p_session_id text, p_course_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_course_by_id(p_session_id text, p_course_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_course_by_id(p_session_id text, p_course_id uuid) TO service_role;


--
-- Name: FUNCTION get_course_students(p_session_id text, p_course_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_course_students(p_session_id text, p_course_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_course_students(p_session_id text, p_course_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_course_students(p_session_id text, p_course_id uuid) TO service_role;


--
-- Name: FUNCTION get_course_units(p_session_id text, p_course_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_course_units(p_session_id text, p_course_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_course_units(p_session_id text, p_course_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_course_units(p_session_id text, p_course_id uuid) TO service_role;


--
-- Name: FUNCTION get_courses_assigned_to_unit(p_session_id text, p_unit_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_courses_assigned_to_unit(p_session_id text, p_unit_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_courses_assigned_to_unit(p_session_id text, p_unit_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_courses_assigned_to_unit(p_session_id text, p_unit_id uuid) TO service_role;


--
-- Name: FUNCTION get_due_tomorrow_count(p_session_id text, p_student_id uuid, p_course_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_due_tomorrow_count(p_session_id text, p_student_id uuid, p_course_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_due_tomorrow_count(p_session_id text, p_student_id uuid, p_course_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_due_tomorrow_count(p_session_id text, p_student_id uuid, p_course_id uuid) TO service_role;


--
-- Name: FUNCTION get_learning_unit(p_session_id text, p_unit_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_learning_unit(p_session_id text, p_unit_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_learning_unit(p_session_id text, p_unit_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_learning_unit(p_session_id text, p_unit_id uuid) TO service_role;


--
-- Name: FUNCTION get_mastery_stats_for_student(p_session_id text, p_student_id uuid, p_course_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_mastery_stats_for_student(p_session_id text, p_student_id uuid, p_course_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_mastery_stats_for_student(p_session_id text, p_student_id uuid, p_course_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_mastery_stats_for_student(p_session_id text, p_student_id uuid, p_course_id uuid) TO service_role;


--
-- Name: FUNCTION get_mastery_summary(p_session_id text, p_student_id uuid, p_course_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_mastery_summary(p_session_id text, p_student_id uuid, p_course_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_mastery_summary(p_session_id text, p_student_id uuid, p_course_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_mastery_summary(p_session_id text, p_student_id uuid, p_course_id uuid) TO service_role;


--
-- Name: FUNCTION get_mastery_tasks_for_course(p_session_id text, p_course_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_mastery_tasks_for_course(p_session_id text, p_course_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_mastery_tasks_for_course(p_session_id text, p_course_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_mastery_tasks_for_course(p_session_id text, p_course_id uuid) TO service_role;


--
-- Name: FUNCTION get_mastery_tasks_for_section(p_session_id text, p_section_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_mastery_tasks_for_section(p_session_id text, p_section_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_mastery_tasks_for_section(p_session_id text, p_section_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_mastery_tasks_for_section(p_session_id text, p_section_id uuid) TO service_role;


--
-- Name: FUNCTION get_my_role(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_my_role() TO anon;
GRANT ALL ON FUNCTION public.get_my_role() TO authenticated;
GRANT ALL ON FUNCTION public.get_my_role() TO service_role;


--
-- Name: FUNCTION get_next_due_mastery_task(p_session_id text, p_student_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_next_due_mastery_task(p_session_id text, p_student_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_next_due_mastery_task(p_session_id text, p_student_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_next_due_mastery_task(p_session_id text, p_student_id uuid) TO service_role;


--
-- Name: FUNCTION get_next_due_mastery_task(p_session_id text, p_student_id uuid, p_course_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_next_due_mastery_task(p_session_id text, p_student_id uuid, p_course_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_next_due_mastery_task(p_session_id text, p_student_id uuid, p_course_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_next_due_mastery_task(p_session_id text, p_student_id uuid, p_course_id uuid) TO service_role;


--
-- Name: FUNCTION get_next_feedback_submission(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_next_feedback_submission() TO anon;
GRANT ALL ON FUNCTION public.get_next_feedback_submission() TO authenticated;
GRANT ALL ON FUNCTION public.get_next_feedback_submission() TO service_role;


--
-- Name: FUNCTION get_next_mastery_task_or_unviewed_feedback(p_session_id text, p_student_id uuid, p_course_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_next_mastery_task_or_unviewed_feedback(p_session_id text, p_student_id uuid, p_course_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_next_mastery_task_or_unviewed_feedback(p_session_id text, p_student_id uuid, p_course_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_next_mastery_task_or_unviewed_feedback(p_session_id text, p_student_id uuid, p_course_id uuid) TO service_role;


--
-- Name: FUNCTION get_published_section_details_for_student(p_session_id text, p_course_id uuid, p_unit_id uuid, p_student_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_published_section_details_for_student(p_session_id text, p_course_id uuid, p_unit_id uuid, p_student_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_published_section_details_for_student(p_session_id text, p_course_id uuid, p_unit_id uuid, p_student_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_published_section_details_for_student(p_session_id text, p_course_id uuid, p_unit_id uuid, p_student_id uuid) TO service_role;


--
-- Name: FUNCTION get_regular_tasks_for_section(p_session_id text, p_section_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_regular_tasks_for_section(p_session_id text, p_section_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_regular_tasks_for_section(p_session_id text, p_section_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_regular_tasks_for_section(p_session_id text, p_section_id uuid) TO service_role;


--
-- Name: FUNCTION get_remaining_attempts(p_session_id text, p_student_id uuid, p_task_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_remaining_attempts(p_session_id text, p_student_id uuid, p_task_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_remaining_attempts(p_session_id text, p_student_id uuid, p_task_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_remaining_attempts(p_session_id text, p_student_id uuid, p_task_id uuid) TO service_role;


--
-- Name: FUNCTION get_section_statuses_for_unit_in_course(p_session_id text, p_unit_id uuid, p_course_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_section_statuses_for_unit_in_course(p_session_id text, p_unit_id uuid, p_course_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_section_statuses_for_unit_in_course(p_session_id text, p_unit_id uuid, p_course_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_section_statuses_for_unit_in_course(p_session_id text, p_unit_id uuid, p_course_id uuid) TO service_role;


--
-- Name: FUNCTION get_section_tasks(p_session_id text, p_section_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_section_tasks(p_session_id text, p_section_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_section_tasks(p_session_id text, p_section_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_section_tasks(p_session_id text, p_section_id uuid) TO service_role;


--
-- Name: FUNCTION get_section_tasks(p_session_id text, p_section_id uuid, p_course_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_section_tasks(p_session_id text, p_section_id uuid, p_course_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_section_tasks(p_session_id text, p_section_id uuid, p_course_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_section_tasks(p_session_id text, p_section_id uuid, p_course_id uuid) TO service_role;


--
-- Name: FUNCTION get_session(p_session_id character varying); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_session(p_session_id character varying) TO anon;
GRANT ALL ON FUNCTION public.get_session(p_session_id character varying) TO authenticated;
GRANT ALL ON FUNCTION public.get_session(p_session_id character varying) TO service_role;


--
-- Name: FUNCTION get_session_with_activity_update(p_session_id character varying); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_session_with_activity_update(p_session_id character varying) TO anon;
GRANT ALL ON FUNCTION public.get_session_with_activity_update(p_session_id character varying) TO authenticated;
GRANT ALL ON FUNCTION public.get_session_with_activity_update(p_session_id character varying) TO service_role;
GRANT ALL ON FUNCTION public.get_session_with_activity_update(p_session_id character varying) TO session_manager;


--
-- Name: FUNCTION get_student_courses(p_session_id text, p_student_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_student_courses(p_session_id text, p_student_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_student_courses(p_session_id text, p_student_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_student_courses(p_session_id text, p_student_id uuid) TO service_role;


--
-- Name: FUNCTION get_students_in_course(p_session_id text, p_course_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_students_in_course(p_session_id text, p_course_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_students_in_course(p_session_id text, p_course_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_students_in_course(p_session_id text, p_course_id uuid) TO service_role;


--
-- Name: FUNCTION get_submission_by_id(p_session_id text, p_submission_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_submission_by_id(p_session_id text, p_submission_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_submission_by_id(p_session_id text, p_submission_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_submission_by_id(p_session_id text, p_submission_id uuid) TO service_role;


--
-- Name: FUNCTION get_submission_count(p_student_id uuid, p_task_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_submission_count(p_student_id uuid, p_task_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_submission_count(p_student_id uuid, p_task_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_submission_count(p_student_id uuid, p_task_id uuid) TO service_role;


--
-- Name: FUNCTION get_submission_for_task(p_session_id text, p_task_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_submission_for_task(p_session_id text, p_task_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_submission_for_task(p_session_id text, p_task_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_submission_for_task(p_session_id text, p_task_id uuid) TO service_role;


--
-- Name: FUNCTION get_submission_for_task(p_session_id text, p_student_id uuid, p_task_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_submission_for_task(p_session_id text, p_student_id uuid, p_task_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_submission_for_task(p_session_id text, p_student_id uuid, p_task_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_submission_for_task(p_session_id text, p_student_id uuid, p_task_id uuid) TO service_role;


--
-- Name: FUNCTION get_submission_history(p_session_id text, p_student_id uuid, p_task_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_submission_history(p_session_id text, p_student_id uuid, p_task_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_submission_history(p_session_id text, p_student_id uuid, p_task_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_submission_history(p_session_id text, p_student_id uuid, p_task_id uuid) TO service_role;


--
-- Name: FUNCTION get_submission_queue_position(p_submission_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_submission_queue_position(p_submission_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_submission_queue_position(p_submission_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_submission_queue_position(p_submission_id uuid) TO service_role;


--
-- Name: FUNCTION get_submission_status_matrix(p_session_id text, p_unit_id uuid, p_course_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_submission_status_matrix(p_session_id text, p_unit_id uuid, p_course_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_submission_status_matrix(p_session_id text, p_unit_id uuid, p_course_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_submission_status_matrix(p_session_id text, p_unit_id uuid, p_course_id uuid) TO service_role;


--
-- Name: FUNCTION get_submissions_for_course_and_unit(p_session_id text, p_course_id uuid, p_unit_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_submissions_for_course_and_unit(p_session_id text, p_course_id uuid, p_unit_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_submissions_for_course_and_unit(p_session_id text, p_course_id uuid, p_unit_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_submissions_for_course_and_unit(p_session_id text, p_course_id uuid, p_unit_id uuid) TO service_role;


--
-- Name: FUNCTION get_task_by_id(p_session_id text, p_task_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_task_by_id(p_session_id text, p_task_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_task_by_id(p_session_id text, p_task_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_task_by_id(p_session_id text, p_task_id uuid) TO service_role;


--
-- Name: FUNCTION get_task_details(p_session_id text, p_task_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_task_details(p_session_id text, p_task_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_task_details(p_session_id text, p_task_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_task_details(p_session_id text, p_task_id uuid) TO service_role;


--
-- Name: FUNCTION get_tasks_for_section(p_session_id text, p_section_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_tasks_for_section(p_session_id text, p_section_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_tasks_for_section(p_session_id text, p_section_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_tasks_for_section(p_session_id text, p_section_id uuid) TO service_role;


--
-- Name: FUNCTION get_teachers_in_course(p_session_id text, p_course_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_teachers_in_course(p_session_id text, p_course_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_teachers_in_course(p_session_id text, p_course_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_teachers_in_course(p_session_id text, p_course_id uuid) TO service_role;


--
-- Name: FUNCTION get_unit_id_from_path(p_path text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_unit_id_from_path(p_path text) TO anon;
GRANT ALL ON FUNCTION public.get_unit_id_from_path(p_path text) TO authenticated;
GRANT ALL ON FUNCTION public.get_unit_id_from_path(p_path text) TO service_role;


--
-- Name: FUNCTION get_unit_sections(p_session_id text, p_unit_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_unit_sections(p_session_id text, p_unit_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_unit_sections(p_session_id text, p_unit_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_unit_sections(p_session_id text, p_unit_id uuid) TO service_role;


--
-- Name: FUNCTION get_user_course_ids(p_session_id text, p_student_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_user_course_ids(p_session_id text, p_student_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_user_course_ids(p_session_id text, p_student_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_user_course_ids(p_session_id text, p_student_id uuid) TO service_role;


--
-- Name: FUNCTION get_user_courses(p_session_id text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_user_courses(p_session_id text) TO anon;
GRANT ALL ON FUNCTION public.get_user_courses(p_session_id text) TO authenticated;
GRANT ALL ON FUNCTION public.get_user_courses(p_session_id text) TO service_role;


--
-- Name: FUNCTION get_user_learning_units(p_session_id text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_user_learning_units(p_session_id text) TO anon;
GRANT ALL ON FUNCTION public.get_user_learning_units(p_session_id text) TO authenticated;
GRANT ALL ON FUNCTION public.get_user_learning_units(p_session_id text) TO service_role;


--
-- Name: FUNCTION get_user_profile_for_auth(p_user_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_user_profile_for_auth(p_user_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_user_profile_for_auth(p_user_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_user_profile_for_auth(p_user_id uuid) TO service_role;


--
-- Name: FUNCTION get_user_sessions(p_user_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_user_sessions(p_user_id uuid) TO anon;
GRANT ALL ON FUNCTION public.get_user_sessions(p_user_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.get_user_sessions(p_user_id uuid) TO service_role;


--
-- Name: FUNCTION get_users_by_role(p_session_id text, p_role text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.get_users_by_role(p_session_id text, p_role text) TO anon;
GRANT ALL ON FUNCTION public.get_users_by_role(p_session_id text, p_role text) TO authenticated;
GRANT ALL ON FUNCTION public.get_users_by_role(p_session_id text, p_role text) TO service_role;


--
-- Name: FUNCTION handle_new_user(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.handle_new_user() TO anon;
GRANT ALL ON FUNCTION public.handle_new_user() TO authenticated;
GRANT ALL ON FUNCTION public.handle_new_user() TO service_role;


--
-- Name: FUNCTION handle_updated_at(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.handle_updated_at() TO anon;
GRANT ALL ON FUNCTION public.handle_updated_at() TO authenticated;
GRANT ALL ON FUNCTION public.handle_updated_at() TO service_role;


--
-- Name: FUNCTION invalidate_user_sessions(p_user_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.invalidate_user_sessions(p_user_id uuid) TO anon;
GRANT ALL ON FUNCTION public.invalidate_user_sessions(p_user_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.invalidate_user_sessions(p_user_id uuid) TO service_role;


--
-- Name: FUNCTION is_creator_of_unit(p_user_id uuid, p_unit_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.is_creator_of_unit(p_user_id uuid, p_unit_id uuid) TO anon;
GRANT ALL ON FUNCTION public.is_creator_of_unit(p_user_id uuid, p_unit_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.is_creator_of_unit(p_user_id uuid, p_unit_id uuid) TO service_role;


--
-- Name: FUNCTION is_enrolled_in_unit(p_user_id uuid, p_unit_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.is_enrolled_in_unit(p_user_id uuid, p_unit_id uuid) TO anon;
GRANT ALL ON FUNCTION public.is_enrolled_in_unit(p_user_id uuid, p_unit_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.is_enrolled_in_unit(p_user_id uuid, p_unit_id uuid) TO service_role;


--
-- Name: FUNCTION is_teacher(p_user_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.is_teacher(p_user_id uuid) TO anon;
GRANT ALL ON FUNCTION public.is_teacher(p_user_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.is_teacher(p_user_id uuid) TO service_role;


--
-- Name: FUNCTION is_teacher_authorized_for_course(p_session_id text, p_course_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.is_teacher_authorized_for_course(p_session_id text, p_course_id uuid) TO anon;
GRANT ALL ON FUNCTION public.is_teacher_authorized_for_course(p_session_id text, p_course_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.is_teacher_authorized_for_course(p_session_id text, p_course_id uuid) TO service_role;


--
-- Name: FUNCTION is_teacher_in_course(p_teacher_id uuid, p_course_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.is_teacher_in_course(p_teacher_id uuid, p_course_id uuid) TO anon;
GRANT ALL ON FUNCTION public.is_teacher_in_course(p_teacher_id uuid, p_course_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.is_teacher_in_course(p_teacher_id uuid, p_course_id uuid) TO service_role;


--
-- Name: FUNCTION is_user_role(user_id_to_check uuid, role_to_check public.user_role); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.is_user_role(user_id_to_check uuid, role_to_check public.user_role) TO anon;
GRANT ALL ON FUNCTION public.is_user_role(user_id_to_check uuid, role_to_check public.user_role) TO authenticated;
GRANT ALL ON FUNCTION public.is_user_role(user_id_to_check uuid, role_to_check public.user_role) TO service_role;


--
-- Name: FUNCTION mark_feedback_as_viewed(p_session_id text, p_submission_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.mark_feedback_as_viewed(p_session_id text, p_submission_id uuid) TO anon;
GRANT ALL ON FUNCTION public.mark_feedback_as_viewed(p_session_id text, p_submission_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.mark_feedback_as_viewed(p_session_id text, p_submission_id uuid) TO service_role;


--
-- Name: FUNCTION mark_feedback_as_viewed_safe(p_session_id text, p_submission_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.mark_feedback_as_viewed_safe(p_session_id text, p_submission_id uuid) TO anon;
GRANT ALL ON FUNCTION public.mark_feedback_as_viewed_safe(p_session_id text, p_submission_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.mark_feedback_as_viewed_safe(p_session_id text, p_submission_id uuid) TO service_role;


--
-- Name: FUNCTION mark_feedback_completed(p_submission_id uuid, p_feedback text, p_insights jsonb, p_mastery_scores jsonb); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.mark_feedback_completed(p_submission_id uuid, p_feedback text, p_insights jsonb, p_mastery_scores jsonb) TO anon;
GRANT ALL ON FUNCTION public.mark_feedback_completed(p_submission_id uuid, p_feedback text, p_insights jsonb, p_mastery_scores jsonb) TO authenticated;
GRANT ALL ON FUNCTION public.mark_feedback_completed(p_submission_id uuid, p_feedback text, p_insights jsonb, p_mastery_scores jsonb) TO service_role;


--
-- Name: FUNCTION mark_feedback_failed(p_submission_id uuid, p_error_message text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.mark_feedback_failed(p_submission_id uuid, p_error_message text) TO anon;
GRANT ALL ON FUNCTION public.mark_feedback_failed(p_submission_id uuid, p_error_message text) TO authenticated;
GRANT ALL ON FUNCTION public.mark_feedback_failed(p_submission_id uuid, p_error_message text) TO service_role;


--
-- Name: FUNCTION move_task_down(p_session_id text, p_task_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.move_task_down(p_session_id text, p_task_id uuid) TO anon;
GRANT ALL ON FUNCTION public.move_task_down(p_session_id text, p_task_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.move_task_down(p_session_id text, p_task_id uuid) TO service_role;


--
-- Name: FUNCTION move_task_up(p_session_id text, p_task_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.move_task_up(p_session_id text, p_task_id uuid) TO anon;
GRANT ALL ON FUNCTION public.move_task_up(p_session_id text, p_task_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.move_task_up(p_session_id text, p_task_id uuid) TO service_role;


--
-- Name: FUNCTION publish_section_for_course(p_session_id text, p_course_id uuid, p_section_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.publish_section_for_course(p_session_id text, p_course_id uuid, p_section_id uuid) TO anon;
GRANT ALL ON FUNCTION public.publish_section_for_course(p_session_id text, p_course_id uuid, p_section_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.publish_section_for_course(p_session_id text, p_course_id uuid, p_section_id uuid) TO service_role;


--
-- Name: FUNCTION refresh_session(p_session_id character varying, p_extend_by interval); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.refresh_session(p_session_id character varying, p_extend_by interval) TO anon;
GRANT ALL ON FUNCTION public.refresh_session(p_session_id character varying, p_extend_by interval) TO authenticated;
GRANT ALL ON FUNCTION public.refresh_session(p_session_id character varying, p_extend_by interval) TO service_role;


--
-- Name: FUNCTION remove_user_from_course(p_session_id text, p_user_id uuid, p_course_id uuid, p_role text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.remove_user_from_course(p_session_id text, p_user_id uuid, p_course_id uuid, p_role text) TO anon;
GRANT ALL ON FUNCTION public.remove_user_from_course(p_session_id text, p_user_id uuid, p_course_id uuid, p_role text) TO authenticated;
GRANT ALL ON FUNCTION public.remove_user_from_course(p_session_id text, p_user_id uuid, p_course_id uuid, p_role text) TO service_role;


--
-- Name: FUNCTION reset_stuck_feedback_jobs(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.reset_stuck_feedback_jobs() TO anon;
GRANT ALL ON FUNCTION public.reset_stuck_feedback_jobs() TO authenticated;
GRANT ALL ON FUNCTION public.reset_stuck_feedback_jobs() TO service_role;


--
-- Name: FUNCTION save_mastery_submission(p_session_id text, p_task_id uuid, p_submission_id uuid, p_is_correct boolean, p_time_spent_seconds integer); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.save_mastery_submission(p_session_id text, p_task_id uuid, p_submission_id uuid, p_is_correct boolean, p_time_spent_seconds integer) TO anon;
GRANT ALL ON FUNCTION public.save_mastery_submission(p_session_id text, p_task_id uuid, p_submission_id uuid, p_is_correct boolean, p_time_spent_seconds integer) TO authenticated;
GRANT ALL ON FUNCTION public.save_mastery_submission(p_session_id text, p_task_id uuid, p_submission_id uuid, p_is_correct boolean, p_time_spent_seconds integer) TO service_role;


--
-- Name: FUNCTION session_user_id(p_session_id text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.session_user_id(p_session_id text) TO anon;
GRANT ALL ON FUNCTION public.session_user_id(p_session_id text) TO authenticated;
GRANT ALL ON FUNCTION public.session_user_id(p_session_id text) TO service_role;


--
-- Name: FUNCTION submit_feedback(p_session_id text, p_page_identifier text, p_feedback_type text, p_feedback_text text, p_sentiment text, p_metadata jsonb); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.submit_feedback(p_session_id text, p_page_identifier text, p_feedback_type text, p_feedback_text text, p_sentiment text, p_metadata jsonb) TO anon;
GRANT ALL ON FUNCTION public.submit_feedback(p_session_id text, p_page_identifier text, p_feedback_type text, p_feedback_text text, p_sentiment text, p_metadata jsonb) TO authenticated;
GRANT ALL ON FUNCTION public.submit_feedback(p_session_id text, p_page_identifier text, p_feedback_type text, p_feedback_text text, p_sentiment text, p_metadata jsonb) TO service_role;


--
-- Name: FUNCTION submit_mastery_answer_complete(p_session_id text, p_task_id uuid, p_submission_text text, p_ai_assessment jsonb, p_q_vec jsonb); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.submit_mastery_answer_complete(p_session_id text, p_task_id uuid, p_submission_text text, p_ai_assessment jsonb, p_q_vec jsonb) TO anon;
GRANT ALL ON FUNCTION public.submit_mastery_answer_complete(p_session_id text, p_task_id uuid, p_submission_text text, p_ai_assessment jsonb, p_q_vec jsonb) TO authenticated;
GRANT ALL ON FUNCTION public.submit_mastery_answer_complete(p_session_id text, p_task_id uuid, p_submission_text text, p_ai_assessment jsonb, p_q_vec jsonb) TO service_role;


--
-- Name: FUNCTION unassign_unit_from_course(p_session_id text, p_unit_id uuid, p_course_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.unassign_unit_from_course(p_session_id text, p_unit_id uuid, p_course_id uuid) TO anon;
GRANT ALL ON FUNCTION public.unassign_unit_from_course(p_session_id text, p_unit_id uuid, p_course_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.unassign_unit_from_course(p_session_id text, p_unit_id uuid, p_course_id uuid) TO service_role;


--
-- Name: FUNCTION unpublish_section_for_course(p_session_id text, p_section_id uuid, p_course_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.unpublish_section_for_course(p_session_id text, p_section_id uuid, p_course_id uuid) TO anon;
GRANT ALL ON FUNCTION public.unpublish_section_for_course(p_session_id text, p_section_id uuid, p_course_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.unpublish_section_for_course(p_session_id text, p_section_id uuid, p_course_id uuid) TO service_role;


--
-- Name: FUNCTION update_course(p_session_id text, p_course_id uuid, p_name text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.update_course(p_session_id text, p_course_id uuid, p_name text) TO anon;
GRANT ALL ON FUNCTION public.update_course(p_session_id text, p_course_id uuid, p_name text) TO authenticated;
GRANT ALL ON FUNCTION public.update_course(p_session_id text, p_course_id uuid, p_name text) TO service_role;


--
-- Name: FUNCTION update_last_activity(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.update_last_activity() TO anon;
GRANT ALL ON FUNCTION public.update_last_activity() TO authenticated;
GRANT ALL ON FUNCTION public.update_last_activity() TO service_role;


--
-- Name: FUNCTION update_learning_unit(p_session_id text, p_unit_id uuid, p_title text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.update_learning_unit(p_session_id text, p_unit_id uuid, p_title text) TO anon;
GRANT ALL ON FUNCTION public.update_learning_unit(p_session_id text, p_unit_id uuid, p_title text) TO authenticated;
GRANT ALL ON FUNCTION public.update_learning_unit(p_session_id text, p_unit_id uuid, p_title text) TO service_role;


--
-- Name: FUNCTION update_mastery_progress(p_session_id text, p_student_id uuid, p_task_id uuid, p_q_vec jsonb); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.update_mastery_progress(p_session_id text, p_student_id uuid, p_task_id uuid, p_q_vec jsonb) TO anon;
GRANT ALL ON FUNCTION public.update_mastery_progress(p_session_id text, p_student_id uuid, p_task_id uuid, p_q_vec jsonb) TO authenticated;
GRANT ALL ON FUNCTION public.update_mastery_progress(p_session_id text, p_student_id uuid, p_task_id uuid, p_q_vec jsonb) TO service_role;


--
-- Name: FUNCTION update_mastery_progress_service(p_student_id uuid, p_task_id uuid, p_q_vec jsonb); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.update_mastery_progress_service(p_student_id uuid, p_task_id uuid, p_q_vec jsonb) TO anon;
GRANT ALL ON FUNCTION public.update_mastery_progress_service(p_student_id uuid, p_task_id uuid, p_q_vec jsonb) TO authenticated;
GRANT ALL ON FUNCTION public.update_mastery_progress_service(p_student_id uuid, p_task_id uuid, p_q_vec jsonb) TO service_role;


--
-- Name: FUNCTION update_section_materials(p_session_id text, p_section_id uuid, p_materials jsonb); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.update_section_materials(p_session_id text, p_section_id uuid, p_materials jsonb) TO anon;
GRANT ALL ON FUNCTION public.update_section_materials(p_session_id text, p_section_id uuid, p_materials jsonb) TO authenticated;
GRANT ALL ON FUNCTION public.update_section_materials(p_session_id text, p_section_id uuid, p_materials jsonb) TO service_role;


--
-- Name: FUNCTION update_session(p_session_id character varying, p_data jsonb); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.update_session(p_session_id character varying, p_data jsonb) TO anon;
GRANT ALL ON FUNCTION public.update_session(p_session_id character varying, p_data jsonb) TO authenticated;
GRANT ALL ON FUNCTION public.update_session(p_session_id character varying, p_data jsonb) TO service_role;


--
-- Name: FUNCTION update_submission_ai_results(p_session_id text, p_submission_id uuid, p_is_correct boolean, p_ai_feedback text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.update_submission_ai_results(p_session_id text, p_submission_id uuid, p_is_correct boolean, p_ai_feedback text) TO anon;
GRANT ALL ON FUNCTION public.update_submission_ai_results(p_session_id text, p_submission_id uuid, p_is_correct boolean, p_ai_feedback text) TO authenticated;
GRANT ALL ON FUNCTION public.update_submission_ai_results(p_session_id text, p_submission_id uuid, p_is_correct boolean, p_ai_feedback text) TO service_role;


--
-- Name: FUNCTION update_submission_ai_results_extended(p_session_id text, p_submission_id uuid, p_is_correct boolean, p_ai_feedback text, p_criteria_analysis text, p_ai_grade text, p_feed_back_text text, p_feed_forward_text text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.update_submission_ai_results_extended(p_session_id text, p_submission_id uuid, p_is_correct boolean, p_ai_feedback text, p_criteria_analysis text, p_ai_grade text, p_feed_back_text text, p_feed_forward_text text) TO anon;
GRANT ALL ON FUNCTION public.update_submission_ai_results_extended(p_session_id text, p_submission_id uuid, p_is_correct boolean, p_ai_feedback text, p_criteria_analysis text, p_ai_grade text, p_feed_back_text text, p_feed_forward_text text) TO authenticated;
GRANT ALL ON FUNCTION public.update_submission_ai_results_extended(p_session_id text, p_submission_id uuid, p_is_correct boolean, p_ai_feedback text, p_criteria_analysis text, p_ai_grade text, p_feed_back_text text, p_feed_forward_text text) TO service_role;


--
-- Name: FUNCTION update_submission_by_teacher(submission_id_in uuid, teacher_feedback_in text, teacher_grade_in text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.update_submission_by_teacher(submission_id_in uuid, teacher_feedback_in text, teacher_grade_in text) TO anon;
GRANT ALL ON FUNCTION public.update_submission_by_teacher(submission_id_in uuid, teacher_feedback_in text, teacher_grade_in text) TO authenticated;
GRANT ALL ON FUNCTION public.update_submission_by_teacher(submission_id_in uuid, teacher_feedback_in text, teacher_grade_in text) TO service_role;


--
-- Name: FUNCTION update_submission_from_ai(submission_id_in uuid, criteria_analysis_in jsonb, feedback_in text, rating_suggestion_in text, feed_back_text_in text, feed_forward_text_in text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.update_submission_from_ai(submission_id_in uuid, criteria_analysis_in jsonb, feedback_in text, rating_suggestion_in text, feed_back_text_in text, feed_forward_text_in text) TO anon;
GRANT ALL ON FUNCTION public.update_submission_from_ai(submission_id_in uuid, criteria_analysis_in jsonb, feedback_in text, rating_suggestion_in text, feed_back_text_in text, feed_forward_text_in text) TO authenticated;
GRANT ALL ON FUNCTION public.update_submission_from_ai(submission_id_in uuid, criteria_analysis_in jsonb, feedback_in text, rating_suggestion_in text, feed_back_text_in text, feed_forward_text_in text) TO service_role;


--
-- Name: FUNCTION update_submission_teacher_override(p_session_id text, p_submission_id uuid, p_override_grade boolean, p_teacher_feedback text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.update_submission_teacher_override(p_session_id text, p_submission_id uuid, p_override_grade boolean, p_teacher_feedback text) TO anon;
GRANT ALL ON FUNCTION public.update_submission_teacher_override(p_session_id text, p_submission_id uuid, p_override_grade boolean, p_teacher_feedback text) TO authenticated;
GRANT ALL ON FUNCTION public.update_submission_teacher_override(p_session_id text, p_submission_id uuid, p_override_grade boolean, p_teacher_feedback text) TO service_role;


--
-- Name: FUNCTION update_task_in_new_structure(p_session_id text, p_task_id uuid, p_title text, p_prompt text, p_task_type text, p_order_in_section integer, p_max_attempts integer, p_grading_criteria text[], p_solution_hints text, p_difficulty_level integer, p_concept_explanation text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.update_task_in_new_structure(p_session_id text, p_task_id uuid, p_title text, p_prompt text, p_task_type text, p_order_in_section integer, p_max_attempts integer, p_grading_criteria text[], p_solution_hints text, p_difficulty_level integer, p_concept_explanation text) TO anon;
GRANT ALL ON FUNCTION public.update_task_in_new_structure(p_session_id text, p_task_id uuid, p_title text, p_prompt text, p_task_type text, p_order_in_section integer, p_max_attempts integer, p_grading_criteria text[], p_solution_hints text, p_difficulty_level integer, p_concept_explanation text) TO authenticated;
GRANT ALL ON FUNCTION public.update_task_in_new_structure(p_session_id text, p_task_id uuid, p_title text, p_prompt text, p_task_type text, p_order_in_section integer, p_max_attempts integer, p_grading_criteria text[], p_solution_hints text, p_difficulty_level integer, p_concept_explanation text) TO service_role;


--
-- Name: FUNCTION update_updated_at_column(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.update_updated_at_column() TO anon;
GRANT ALL ON FUNCTION public.update_updated_at_column() TO authenticated;
GRANT ALL ON FUNCTION public.update_updated_at_column() TO service_role;


--
-- Name: FUNCTION validate_auth_service_key(api_key text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.validate_auth_service_key(api_key text) TO anon;
GRANT ALL ON FUNCTION public.validate_auth_service_key(api_key text) TO authenticated;
GRANT ALL ON FUNCTION public.validate_auth_service_key(api_key text) TO service_role;


--
-- Name: FUNCTION validate_session(p_session_id character varying); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.validate_session(p_session_id character varying) TO anon;
GRANT ALL ON FUNCTION public.validate_session(p_session_id character varying) TO authenticated;
GRANT ALL ON FUNCTION public.validate_session(p_session_id character varying) TO service_role;


--
-- Name: FUNCTION validate_session_and_get_user(p_session_id text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.validate_session_and_get_user(p_session_id text) TO anon;
GRANT ALL ON FUNCTION public.validate_session_and_get_user(p_session_id text) TO authenticated;
GRANT ALL ON FUNCTION public.validate_session_and_get_user(p_session_id text) TO service_role;


--
-- Name: FUNCTION validate_storage_session_user(path text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.validate_storage_session_user(path text) TO anon;
GRANT ALL ON FUNCTION public.validate_storage_session_user(path text) TO authenticated;
GRANT ALL ON FUNCTION public.validate_storage_session_user(path text) TO service_role;


--
-- Name: FUNCTION apply_rls(wal jsonb, max_record_bytes integer); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) TO postgres;
GRANT ALL ON FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) TO anon;
GRANT ALL ON FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) TO authenticated;
GRANT ALL ON FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) TO service_role;
GRANT ALL ON FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) TO supabase_realtime_admin;


--
-- Name: FUNCTION broadcast_changes(topic_name text, event_name text, operation text, table_name text, table_schema text, new record, old record, level text); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.broadcast_changes(topic_name text, event_name text, operation text, table_name text, table_schema text, new record, old record, level text) TO postgres;
GRANT ALL ON FUNCTION realtime.broadcast_changes(topic_name text, event_name text, operation text, table_name text, table_schema text, new record, old record, level text) TO dashboard_user;


--
-- Name: FUNCTION build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) TO postgres;
GRANT ALL ON FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) TO anon;
GRANT ALL ON FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) TO authenticated;
GRANT ALL ON FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) TO service_role;
GRANT ALL ON FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) TO supabase_realtime_admin;


--
-- Name: FUNCTION "cast"(val text, type_ regtype); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime."cast"(val text, type_ regtype) TO postgres;
GRANT ALL ON FUNCTION realtime."cast"(val text, type_ regtype) TO dashboard_user;
GRANT ALL ON FUNCTION realtime."cast"(val text, type_ regtype) TO anon;
GRANT ALL ON FUNCTION realtime."cast"(val text, type_ regtype) TO authenticated;
GRANT ALL ON FUNCTION realtime."cast"(val text, type_ regtype) TO service_role;
GRANT ALL ON FUNCTION realtime."cast"(val text, type_ regtype) TO supabase_realtime_admin;


--
-- Name: FUNCTION check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) TO postgres;
GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) TO anon;
GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) TO authenticated;
GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) TO service_role;
GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) TO supabase_realtime_admin;


--
-- Name: FUNCTION is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) TO postgres;
GRANT ALL ON FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) TO anon;
GRANT ALL ON FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) TO authenticated;
GRANT ALL ON FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) TO service_role;
GRANT ALL ON FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) TO supabase_realtime_admin;


--
-- Name: FUNCTION list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) TO postgres;
GRANT ALL ON FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) TO anon;
GRANT ALL ON FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) TO authenticated;
GRANT ALL ON FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) TO service_role;
GRANT ALL ON FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) TO supabase_realtime_admin;


--
-- Name: FUNCTION quote_wal2json(entity regclass); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.quote_wal2json(entity regclass) TO postgres;
GRANT ALL ON FUNCTION realtime.quote_wal2json(entity regclass) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.quote_wal2json(entity regclass) TO anon;
GRANT ALL ON FUNCTION realtime.quote_wal2json(entity regclass) TO authenticated;
GRANT ALL ON FUNCTION realtime.quote_wal2json(entity regclass) TO service_role;
GRANT ALL ON FUNCTION realtime.quote_wal2json(entity regclass) TO supabase_realtime_admin;


--
-- Name: FUNCTION send(payload jsonb, event text, topic text, private boolean); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.send(payload jsonb, event text, topic text, private boolean) TO postgres;
GRANT ALL ON FUNCTION realtime.send(payload jsonb, event text, topic text, private boolean) TO dashboard_user;


--
-- Name: FUNCTION subscription_check_filters(); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.subscription_check_filters() TO postgres;
GRANT ALL ON FUNCTION realtime.subscription_check_filters() TO dashboard_user;
GRANT ALL ON FUNCTION realtime.subscription_check_filters() TO anon;
GRANT ALL ON FUNCTION realtime.subscription_check_filters() TO authenticated;
GRANT ALL ON FUNCTION realtime.subscription_check_filters() TO service_role;
GRANT ALL ON FUNCTION realtime.subscription_check_filters() TO supabase_realtime_admin;


--
-- Name: FUNCTION to_regrole(role_name text); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.to_regrole(role_name text) TO postgres;
GRANT ALL ON FUNCTION realtime.to_regrole(role_name text) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.to_regrole(role_name text) TO anon;
GRANT ALL ON FUNCTION realtime.to_regrole(role_name text) TO authenticated;
GRANT ALL ON FUNCTION realtime.to_regrole(role_name text) TO service_role;
GRANT ALL ON FUNCTION realtime.to_regrole(role_name text) TO supabase_realtime_admin;


--
-- Name: FUNCTION topic(); Type: ACL; Schema: realtime; Owner: supabase_realtime_admin
--

GRANT ALL ON FUNCTION realtime.topic() TO postgres;
GRANT ALL ON FUNCTION realtime.topic() TO dashboard_user;


--
-- Name: FUNCTION http_request(); Type: ACL; Schema: supabase_functions; Owner: supabase_functions_admin
--

REVOKE ALL ON FUNCTION supabase_functions.http_request() FROM PUBLIC;
GRANT ALL ON FUNCTION supabase_functions.http_request() TO postgres;
GRANT ALL ON FUNCTION supabase_functions.http_request() TO anon;
GRANT ALL ON FUNCTION supabase_functions.http_request() TO authenticated;
GRANT ALL ON FUNCTION supabase_functions.http_request() TO service_role;


--
-- Name: FUNCTION _crypto_aead_det_decrypt(message bytea, additional bytea, key_id bigint, context bytea, nonce bytea); Type: ACL; Schema: vault; Owner: supabase_admin
--

GRANT ALL ON FUNCTION vault._crypto_aead_det_decrypt(message bytea, additional bytea, key_id bigint, context bytea, nonce bytea) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION vault._crypto_aead_det_decrypt(message bytea, additional bytea, key_id bigint, context bytea, nonce bytea) TO service_role;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION vault._crypto_aead_det_decrypt(message bytea, additional bytea, key_id bigint, context bytea, nonce bytea) TO service_role;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION create_secret(new_secret text, new_name text, new_description text, new_key_id uuid); Type: ACL; Schema: vault; Owner: supabase_admin
--

GRANT ALL ON FUNCTION vault.create_secret(new_secret text, new_name text, new_description text, new_key_id uuid) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION vault.create_secret(new_secret text, new_name text, new_description text, new_key_id uuid) TO service_role;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION vault.create_secret(new_secret text, new_name text, new_description text, new_key_id uuid) TO service_role;
RESET SESSION AUTHORIZATION;


--
-- Name: FUNCTION update_secret(secret_id uuid, new_secret text, new_name text, new_description text, new_key_id uuid); Type: ACL; Schema: vault; Owner: supabase_admin
--

GRANT ALL ON FUNCTION vault.update_secret(secret_id uuid, new_secret text, new_name text, new_description text, new_key_id uuid) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION vault.update_secret(secret_id uuid, new_secret text, new_name text, new_description text, new_key_id uuid) TO service_role;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON FUNCTION vault.update_secret(secret_id uuid, new_secret text, new_name text, new_description text, new_key_id uuid) TO service_role;
RESET SESSION AUTHORIZATION;


--
-- Name: TABLE audit_log_entries; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.audit_log_entries TO dashboard_user;
GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.audit_log_entries TO postgres;
GRANT SELECT ON TABLE auth.audit_log_entries TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT SELECT ON TABLE auth.audit_log_entries TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: TABLE flow_state; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.flow_state TO postgres;
GRANT SELECT ON TABLE auth.flow_state TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.flow_state TO dashboard_user;
SET SESSION AUTHORIZATION postgres;
GRANT SELECT ON TABLE auth.flow_state TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: TABLE identities; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.identities TO postgres;
GRANT SELECT ON TABLE auth.identities TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.identities TO dashboard_user;
SET SESSION AUTHORIZATION postgres;
GRANT SELECT ON TABLE auth.identities TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: TABLE instances; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.instances TO dashboard_user;
GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.instances TO postgres;
GRANT SELECT ON TABLE auth.instances TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT SELECT ON TABLE auth.instances TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: TABLE mfa_amr_claims; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.mfa_amr_claims TO postgres;
GRANT SELECT ON TABLE auth.mfa_amr_claims TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.mfa_amr_claims TO dashboard_user;
SET SESSION AUTHORIZATION postgres;
GRANT SELECT ON TABLE auth.mfa_amr_claims TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: TABLE mfa_challenges; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.mfa_challenges TO postgres;
GRANT SELECT ON TABLE auth.mfa_challenges TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.mfa_challenges TO dashboard_user;
SET SESSION AUTHORIZATION postgres;
GRANT SELECT ON TABLE auth.mfa_challenges TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: TABLE mfa_factors; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.mfa_factors TO postgres;
GRANT SELECT ON TABLE auth.mfa_factors TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.mfa_factors TO dashboard_user;
SET SESSION AUTHORIZATION postgres;
GRANT SELECT ON TABLE auth.mfa_factors TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: TABLE oauth_authorizations; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.oauth_authorizations TO postgres;
GRANT ALL ON TABLE auth.oauth_authorizations TO dashboard_user;


--
-- Name: TABLE oauth_clients; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.oauth_clients TO postgres;
GRANT ALL ON TABLE auth.oauth_clients TO dashboard_user;


--
-- Name: TABLE oauth_consents; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.oauth_consents TO postgres;
GRANT ALL ON TABLE auth.oauth_consents TO dashboard_user;


--
-- Name: TABLE one_time_tokens; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.one_time_tokens TO postgres;
GRANT SELECT ON TABLE auth.one_time_tokens TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.one_time_tokens TO dashboard_user;
SET SESSION AUTHORIZATION postgres;
GRANT SELECT ON TABLE auth.one_time_tokens TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: TABLE refresh_tokens; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.refresh_tokens TO dashboard_user;
GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.refresh_tokens TO postgres;
GRANT SELECT ON TABLE auth.refresh_tokens TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT SELECT ON TABLE auth.refresh_tokens TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: SEQUENCE refresh_tokens_id_seq; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON SEQUENCE auth.refresh_tokens_id_seq TO dashboard_user;
GRANT ALL ON SEQUENCE auth.refresh_tokens_id_seq TO postgres;


--
-- Name: TABLE saml_providers; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.saml_providers TO postgres;
GRANT SELECT ON TABLE auth.saml_providers TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.saml_providers TO dashboard_user;
SET SESSION AUTHORIZATION postgres;
GRANT SELECT ON TABLE auth.saml_providers TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: TABLE saml_relay_states; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.saml_relay_states TO postgres;
GRANT SELECT ON TABLE auth.saml_relay_states TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.saml_relay_states TO dashboard_user;
SET SESSION AUTHORIZATION postgres;
GRANT SELECT ON TABLE auth.saml_relay_states TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: TABLE schema_migrations; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT SELECT ON TABLE auth.schema_migrations TO postgres WITH GRANT OPTION;


--
-- Name: TABLE sessions; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.sessions TO postgres;
GRANT SELECT ON TABLE auth.sessions TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.sessions TO dashboard_user;
SET SESSION AUTHORIZATION postgres;
GRANT SELECT ON TABLE auth.sessions TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: TABLE sso_domains; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.sso_domains TO postgres;
GRANT SELECT ON TABLE auth.sso_domains TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.sso_domains TO dashboard_user;
SET SESSION AUTHORIZATION postgres;
GRANT SELECT ON TABLE auth.sso_domains TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: TABLE sso_providers; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.sso_providers TO postgres;
GRANT SELECT ON TABLE auth.sso_providers TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.sso_providers TO dashboard_user;
SET SESSION AUTHORIZATION postgres;
GRANT SELECT ON TABLE auth.sso_providers TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: TABLE users; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.users TO dashboard_user;
GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.users TO postgres;
GRANT SELECT ON TABLE auth.users TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT SELECT ON TABLE auth.users TO dashboard_user;
RESET SESSION AUTHORIZATION;


--
-- Name: TABLE pg_stat_statements; Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON TABLE extensions.pg_stat_statements TO postgres WITH GRANT OPTION;


--
-- Name: TABLE pg_stat_statements_info; Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON TABLE extensions.pg_stat_statements_info TO postgres WITH GRANT OPTION;


--
-- Name: TABLE mastery_tasks; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.mastery_tasks TO anon;
GRANT ALL ON TABLE public.mastery_tasks TO authenticated;
GRANT ALL ON TABLE public.mastery_tasks TO service_role;


--
-- Name: TABLE task_base; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.task_base TO anon;
GRANT ALL ON TABLE public.task_base TO authenticated;
GRANT ALL ON TABLE public.task_base TO service_role;


--
-- Name: TABLE all_mastery_tasks; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.all_mastery_tasks TO anon;
GRANT ALL ON TABLE public.all_mastery_tasks TO authenticated;
GRANT ALL ON TABLE public.all_mastery_tasks TO service_role;


--
-- Name: TABLE regular_tasks; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.regular_tasks TO anon;
GRANT ALL ON TABLE public.regular_tasks TO authenticated;
GRANT ALL ON TABLE public.regular_tasks TO service_role;


--
-- Name: TABLE all_regular_tasks; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.all_regular_tasks TO anon;
GRANT ALL ON TABLE public.all_regular_tasks TO authenticated;
GRANT ALL ON TABLE public.all_regular_tasks TO service_role;


--
-- Name: TABLE allowed_email_domains; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.allowed_email_domains TO anon;
GRANT ALL ON TABLE public.allowed_email_domains TO authenticated;
GRANT ALL ON TABLE public.allowed_email_domains TO service_role;


--
-- Name: TABLE auth_service_keys; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.auth_service_keys TO anon;
GRANT ALL ON TABLE public.auth_service_keys TO authenticated;
GRANT ALL ON TABLE public.auth_service_keys TO service_role;


--
-- Name: TABLE auth_sessions; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.auth_sessions TO anon;
GRANT ALL ON TABLE public.auth_sessions TO authenticated;
GRANT ALL ON TABLE public.auth_sessions TO service_role;
GRANT ALL ON TABLE public.auth_sessions TO session_manager;


--
-- Name: TABLE course; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.course TO anon;
GRANT ALL ON TABLE public.course TO authenticated;
GRANT ALL ON TABLE public.course TO service_role;


--
-- Name: TABLE course_learning_unit_assignment; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.course_learning_unit_assignment TO anon;
GRANT ALL ON TABLE public.course_learning_unit_assignment TO authenticated;
GRANT ALL ON TABLE public.course_learning_unit_assignment TO service_role;


--
-- Name: TABLE course_student; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.course_student TO anon;
GRANT ALL ON TABLE public.course_student TO authenticated;
GRANT ALL ON TABLE public.course_student TO service_role;


--
-- Name: TABLE course_teacher; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.course_teacher TO anon;
GRANT ALL ON TABLE public.course_teacher TO authenticated;
GRANT ALL ON TABLE public.course_teacher TO service_role;


--
-- Name: TABLE course_unit_section_status; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.course_unit_section_status TO anon;
GRANT ALL ON TABLE public.course_unit_section_status TO authenticated;
GRANT ALL ON TABLE public.course_unit_section_status TO service_role;


--
-- Name: TABLE feedback; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.feedback TO anon;
GRANT ALL ON TABLE public.feedback TO authenticated;
GRANT ALL ON TABLE public.feedback TO service_role;


--
-- Name: TABLE learning_unit; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.learning_unit TO anon;
GRANT ALL ON TABLE public.learning_unit TO authenticated;
GRANT ALL ON TABLE public.learning_unit TO service_role;


--
-- Name: TABLE mastery_log; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.mastery_log TO anon;
GRANT ALL ON TABLE public.mastery_log TO authenticated;
GRANT ALL ON TABLE public.mastery_log TO service_role;


--
-- Name: SEQUENCE mastery_log_log_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.mastery_log_log_id_seq TO anon;
GRANT ALL ON SEQUENCE public.mastery_log_log_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.mastery_log_log_id_seq TO service_role;


--
-- Name: TABLE mastery_submission; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.mastery_submission TO anon;
GRANT ALL ON TABLE public.mastery_submission TO authenticated;
GRANT ALL ON TABLE public.mastery_submission TO service_role;


--
-- Name: SEQUENCE mastery_submission_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.mastery_submission_id_seq TO anon;
GRANT ALL ON SEQUENCE public.mastery_submission_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.mastery_submission_id_seq TO service_role;


--
-- Name: TABLE profiles; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.profiles TO anon;
GRANT ALL ON TABLE public.profiles TO authenticated;
GRANT ALL ON TABLE public.profiles TO service_role;
GRANT SELECT ON TABLE public.profiles TO supabase_storage_admin;


--
-- Name: TABLE profiles_display; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.profiles_display TO anon;
GRANT ALL ON TABLE public.profiles_display TO authenticated;
GRANT ALL ON TABLE public.profiles_display TO service_role;


--
-- Name: TABLE session_rate_limits; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.session_rate_limits TO anon;
GRANT ALL ON TABLE public.session_rate_limits TO authenticated;
GRANT ALL ON TABLE public.session_rate_limits TO service_role;


--
-- Name: TABLE student_mastery_progress; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.student_mastery_progress TO anon;
GRANT ALL ON TABLE public.student_mastery_progress TO authenticated;
GRANT ALL ON TABLE public.student_mastery_progress TO service_role;


--
-- Name: SEQUENCE student_mastery_progress_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.student_mastery_progress_id_seq TO anon;
GRANT ALL ON SEQUENCE public.student_mastery_progress_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.student_mastery_progress_id_seq TO service_role;


--
-- Name: TABLE submission; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.submission TO anon;
GRANT ALL ON TABLE public.submission TO authenticated;
GRANT ALL ON TABLE public.submission TO service_role;


--
-- Name: TABLE task; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.task TO anon;
GRANT ALL ON TABLE public.task TO authenticated;
GRANT ALL ON TABLE public.task TO service_role;


--
-- Name: TABLE task_backup_phase4; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.task_backup_phase4 TO anon;
GRANT ALL ON TABLE public.task_backup_phase4 TO authenticated;
GRANT ALL ON TABLE public.task_backup_phase4 TO service_role;


--
-- Name: TABLE unit_section; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.unit_section TO anon;
GRANT ALL ON TABLE public.unit_section TO authenticated;
GRANT ALL ON TABLE public.unit_section TO service_role;


--
-- Name: TABLE user_model_weights; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.user_model_weights TO anon;
GRANT ALL ON TABLE public.user_model_weights TO authenticated;
GRANT ALL ON TABLE public.user_model_weights TO service_role;


--
-- Name: TABLE messages; Type: ACL; Schema: realtime; Owner: supabase_realtime_admin
--

GRANT ALL ON TABLE realtime.messages TO postgres;
GRANT ALL ON TABLE realtime.messages TO dashboard_user;
GRANT SELECT,INSERT,UPDATE ON TABLE realtime.messages TO anon;
GRANT SELECT,INSERT,UPDATE ON TABLE realtime.messages TO authenticated;
GRANT SELECT,INSERT,UPDATE ON TABLE realtime.messages TO service_role;


--
-- Name: TABLE messages_2025_10_27; Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON TABLE realtime.messages_2025_10_27 TO postgres;
GRANT ALL ON TABLE realtime.messages_2025_10_27 TO dashboard_user;


--
-- Name: TABLE messages_2025_10_28; Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON TABLE realtime.messages_2025_10_28 TO postgres;
GRANT ALL ON TABLE realtime.messages_2025_10_28 TO dashboard_user;


--
-- Name: TABLE messages_2025_10_29; Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON TABLE realtime.messages_2025_10_29 TO postgres;
GRANT ALL ON TABLE realtime.messages_2025_10_29 TO dashboard_user;


--
-- Name: TABLE messages_2025_10_30; Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON TABLE realtime.messages_2025_10_30 TO postgres;
GRANT ALL ON TABLE realtime.messages_2025_10_30 TO dashboard_user;


--
-- Name: TABLE messages_2025_10_31; Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON TABLE realtime.messages_2025_10_31 TO postgres;
GRANT ALL ON TABLE realtime.messages_2025_10_31 TO dashboard_user;


--
-- Name: TABLE messages_2025_11_01; Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON TABLE realtime.messages_2025_11_01 TO postgres;
GRANT ALL ON TABLE realtime.messages_2025_11_01 TO dashboard_user;


--
-- Name: TABLE messages_2025_11_02; Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON TABLE realtime.messages_2025_11_02 TO postgres;
GRANT ALL ON TABLE realtime.messages_2025_11_02 TO dashboard_user;


--
-- Name: TABLE schema_migrations; Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON TABLE realtime.schema_migrations TO postgres;
GRANT ALL ON TABLE realtime.schema_migrations TO dashboard_user;
GRANT SELECT ON TABLE realtime.schema_migrations TO anon;
GRANT SELECT ON TABLE realtime.schema_migrations TO authenticated;
GRANT SELECT ON TABLE realtime.schema_migrations TO service_role;
GRANT ALL ON TABLE realtime.schema_migrations TO supabase_realtime_admin;


--
-- Name: TABLE subscription; Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON TABLE realtime.subscription TO postgres;
GRANT ALL ON TABLE realtime.subscription TO dashboard_user;
GRANT SELECT ON TABLE realtime.subscription TO anon;
GRANT SELECT ON TABLE realtime.subscription TO authenticated;
GRANT SELECT ON TABLE realtime.subscription TO service_role;
GRANT ALL ON TABLE realtime.subscription TO supabase_realtime_admin;


--
-- Name: SEQUENCE subscription_id_seq; Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON SEQUENCE realtime.subscription_id_seq TO postgres;
GRANT ALL ON SEQUENCE realtime.subscription_id_seq TO dashboard_user;
GRANT USAGE ON SEQUENCE realtime.subscription_id_seq TO anon;
GRANT USAGE ON SEQUENCE realtime.subscription_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE realtime.subscription_id_seq TO service_role;
GRANT ALL ON SEQUENCE realtime.subscription_id_seq TO supabase_realtime_admin;


--
-- Name: TABLE buckets; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

GRANT ALL ON TABLE storage.buckets TO anon;
GRANT ALL ON TABLE storage.buckets TO authenticated;
GRANT ALL ON TABLE storage.buckets TO service_role;
GRANT ALL ON TABLE storage.buckets TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON TABLE storage.buckets TO anon;
RESET SESSION AUTHORIZATION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON TABLE storage.buckets TO authenticated;
RESET SESSION AUTHORIZATION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON TABLE storage.buckets TO service_role;
RESET SESSION AUTHORIZATION;


--
-- Name: TABLE buckets_analytics; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

GRANT ALL ON TABLE storage.buckets_analytics TO service_role;
GRANT ALL ON TABLE storage.buckets_analytics TO authenticated;
GRANT ALL ON TABLE storage.buckets_analytics TO anon;


--
-- Name: TABLE iceberg_namespaces; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

GRANT ALL ON TABLE storage.iceberg_namespaces TO service_role;
GRANT SELECT ON TABLE storage.iceberg_namespaces TO authenticated;
GRANT SELECT ON TABLE storage.iceberg_namespaces TO anon;


--
-- Name: TABLE iceberg_tables; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

GRANT ALL ON TABLE storage.iceberg_tables TO service_role;
GRANT SELECT ON TABLE storage.iceberg_tables TO authenticated;
GRANT SELECT ON TABLE storage.iceberg_tables TO anon;


--
-- Name: TABLE objects; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

GRANT ALL ON TABLE storage.objects TO anon;
GRANT ALL ON TABLE storage.objects TO authenticated;
GRANT ALL ON TABLE storage.objects TO service_role;
GRANT ALL ON TABLE storage.objects TO postgres WITH GRANT OPTION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON TABLE storage.objects TO anon;
RESET SESSION AUTHORIZATION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON TABLE storage.objects TO authenticated;
RESET SESSION AUTHORIZATION;
SET SESSION AUTHORIZATION postgres;
GRANT ALL ON TABLE storage.objects TO service_role;
RESET SESSION AUTHORIZATION;


--
-- Name: TABLE prefixes; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

GRANT ALL ON TABLE storage.prefixes TO service_role;
GRANT ALL ON TABLE storage.prefixes TO authenticated;
GRANT ALL ON TABLE storage.prefixes TO anon;


--
-- Name: TABLE s3_multipart_uploads; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

GRANT ALL ON TABLE storage.s3_multipart_uploads TO service_role;
GRANT SELECT ON TABLE storage.s3_multipart_uploads TO authenticated;
GRANT SELECT ON TABLE storage.s3_multipart_uploads TO anon;


--
-- Name: TABLE s3_multipart_uploads_parts; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

GRANT ALL ON TABLE storage.s3_multipart_uploads_parts TO service_role;
GRANT SELECT ON TABLE storage.s3_multipart_uploads_parts TO authenticated;
GRANT SELECT ON TABLE storage.s3_multipart_uploads_parts TO anon;


--
-- Name: TABLE hooks; Type: ACL; Schema: supabase_functions; Owner: supabase_functions_admin
--

GRANT ALL ON TABLE supabase_functions.hooks TO postgres;
GRANT ALL ON TABLE supabase_functions.hooks TO anon;
GRANT ALL ON TABLE supabase_functions.hooks TO authenticated;
GRANT ALL ON TABLE supabase_functions.hooks TO service_role;


--
-- Name: SEQUENCE hooks_id_seq; Type: ACL; Schema: supabase_functions; Owner: supabase_functions_admin
--

GRANT ALL ON SEQUENCE supabase_functions.hooks_id_seq TO postgres;
GRANT ALL ON SEQUENCE supabase_functions.hooks_id_seq TO anon;
GRANT ALL ON SEQUENCE supabase_functions.hooks_id_seq TO authenticated;
GRANT ALL ON SEQUENCE supabase_functions.hooks_id_seq TO service_role;


--
-- Name: TABLE migrations; Type: ACL; Schema: supabase_functions; Owner: supabase_functions_admin
--

GRANT ALL ON TABLE supabase_functions.migrations TO postgres;
GRANT ALL ON TABLE supabase_functions.migrations TO anon;
GRANT ALL ON TABLE supabase_functions.migrations TO authenticated;
GRANT ALL ON TABLE supabase_functions.migrations TO service_role;


--
-- Name: TABLE secrets; Type: ACL; Schema: vault; Owner: supabase_admin
--

GRANT SELECT,REFERENCES,DELETE,TRUNCATE ON TABLE vault.secrets TO postgres WITH GRANT OPTION;
GRANT SELECT,DELETE ON TABLE vault.secrets TO service_role;
SET SESSION AUTHORIZATION postgres;
GRANT SELECT,DELETE ON TABLE vault.secrets TO service_role;
RESET SESSION AUTHORIZATION;


--
-- Name: TABLE decrypted_secrets; Type: ACL; Schema: vault; Owner: supabase_admin
--

GRANT SELECT,REFERENCES,DELETE,TRUNCATE ON TABLE vault.decrypted_secrets TO postgres WITH GRANT OPTION;
GRANT SELECT,DELETE ON TABLE vault.decrypted_secrets TO service_role;
SET SESSION AUTHORIZATION postgres;
GRANT SELECT,DELETE ON TABLE vault.decrypted_secrets TO service_role;
RESET SESSION AUTHORIZATION;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: auth; Owner: supabase_auth_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT ALL ON SEQUENCES TO dashboard_user;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: auth; Owner: supabase_auth_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT ALL ON FUNCTIONS TO dashboard_user;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: auth; Owner: supabase_auth_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT ALL ON TABLES TO dashboard_user;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: extensions; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA extensions GRANT ALL ON SEQUENCES TO postgres WITH GRANT OPTION;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: extensions; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA extensions GRANT ALL ON FUNCTIONS TO postgres WITH GRANT OPTION;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: extensions; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA extensions GRANT ALL ON TABLES TO postgres WITH GRANT OPTION;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: graphql; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON SEQUENCES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: graphql; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON FUNCTIONS TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: graphql; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON TABLES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: graphql_public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON SEQUENCES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: graphql_public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON FUNCTIONS TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: graphql_public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON TABLES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON FUNCTIONS TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON FUNCTIONS TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON TABLES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: realtime; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA realtime GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA realtime GRANT ALL ON SEQUENCES TO dashboard_user;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: realtime; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA realtime GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA realtime GRANT ALL ON FUNCTIONS TO dashboard_user;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: realtime; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA realtime GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA realtime GRANT ALL ON TABLES TO dashboard_user;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: storage; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON SEQUENCES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: storage; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON FUNCTIONS TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: storage; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON TABLES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: supabase_functions; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA supabase_functions GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA supabase_functions GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA supabase_functions GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA supabase_functions GRANT ALL ON SEQUENCES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: supabase_functions; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA supabase_functions GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA supabase_functions GRANT ALL ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA supabase_functions GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA supabase_functions GRANT ALL ON FUNCTIONS TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: supabase_functions; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA supabase_functions GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA supabase_functions GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA supabase_functions GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA supabase_functions GRANT ALL ON TABLES TO service_role;


--
-- Name: issue_graphql_placeholder; Type: EVENT TRIGGER; Schema: -; Owner: supabase_admin
--

CREATE EVENT TRIGGER issue_graphql_placeholder ON sql_drop
         WHEN TAG IN ('DROP EXTENSION')
   EXECUTE FUNCTION extensions.set_graphql_placeholder();


ALTER EVENT TRIGGER issue_graphql_placeholder OWNER TO supabase_admin;

--
-- Name: issue_pg_cron_access; Type: EVENT TRIGGER; Schema: -; Owner: supabase_admin
--

CREATE EVENT TRIGGER issue_pg_cron_access ON ddl_command_end
         WHEN TAG IN ('CREATE EXTENSION')
   EXECUTE FUNCTION extensions.grant_pg_cron_access();


ALTER EVENT TRIGGER issue_pg_cron_access OWNER TO supabase_admin;

--
-- Name: issue_pg_graphql_access; Type: EVENT TRIGGER; Schema: -; Owner: supabase_admin
--

CREATE EVENT TRIGGER issue_pg_graphql_access ON ddl_command_end
         WHEN TAG IN ('CREATE FUNCTION')
   EXECUTE FUNCTION extensions.grant_pg_graphql_access();


ALTER EVENT TRIGGER issue_pg_graphql_access OWNER TO supabase_admin;

--
-- Name: issue_pg_net_access; Type: EVENT TRIGGER; Schema: -; Owner: supabase_admin
--

CREATE EVENT TRIGGER issue_pg_net_access ON ddl_command_end
         WHEN TAG IN ('CREATE EXTENSION')
   EXECUTE FUNCTION extensions.grant_pg_net_access();


ALTER EVENT TRIGGER issue_pg_net_access OWNER TO supabase_admin;

--
-- Name: pgrst_ddl_watch; Type: EVENT TRIGGER; Schema: -; Owner: supabase_admin
--

CREATE EVENT TRIGGER pgrst_ddl_watch ON ddl_command_end
   EXECUTE FUNCTION extensions.pgrst_ddl_watch();


ALTER EVENT TRIGGER pgrst_ddl_watch OWNER TO supabase_admin;

--
-- Name: pgrst_drop_watch; Type: EVENT TRIGGER; Schema: -; Owner: supabase_admin
--

CREATE EVENT TRIGGER pgrst_drop_watch ON sql_drop
   EXECUTE FUNCTION extensions.pgrst_drop_watch();


ALTER EVENT TRIGGER pgrst_drop_watch OWNER TO supabase_admin;

--
-- PostgreSQL database dump complete
--

\unrestrict 6u5sjQ37hT01U3hGCLU2QRx46PWofdnJAZEQWdxRg7UFKTiWZS6ZgLKMsWxSeVb

