--
-- PostgreSQL database dump
--

-- Dumped from database version 17.4
-- Dumped by pg_dump version 17.4

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
-- Data for Name: allowed_email_domains; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.allowed_email_domains (id, domain, is_active, created_at, updated_at) FROM stdin;
ac112728-3491-4609-855c-ea752e51bbad	@gymalf.de	t	2025-08-07 22:04:24.913657+00	2025-08-07 22:04:24.913657+00
3f97f8b2-abcd-4e4a-9825-93562126b267	@test.de	t	2025-08-11 06:38:39.102778+00	2025-08-11 06:38:39.102778+00
\.


--
-- Data for Name: course; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.course (id, name, creator_id, created_at, updated_at) FROM stdin;
ff01a644-7328-4151-9e45-a92f49502aa6	Informatik I	7673ad14-cd77-409b-9105-5ab5559cb3ed	2025-08-09 15:27:01.54838+00	2025-08-09 15:27:01.54838+00
\.


--
-- Data for Name: learning_unit; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.learning_unit (id, title, creator_id, created_at, updated_at) FROM stdin;
02f80bbb-b393-408d-bb66-58fd362a1df3	Digitaltechnik	7673ad14-cd77-409b-9105-5ab5559cb3ed	2025-08-10 07:39:23.228022+00	2025-08-10 07:39:23.228022+00
\.


--
-- Data for Name: course_learning_unit_assignment; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.course_learning_unit_assignment (course_id, unit_id, assigned_at) FROM stdin;
ff01a644-7328-4151-9e45-a92f49502aa6	02f80bbb-b393-408d-bb66-58fd362a1df3	2025-08-10 07:39:35.878206+00
\.


--
-- Data for Name: profiles; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.profiles (id, role, full_name, created_at, updated_at, email) FROM stdin;
7673ad14-cd77-409b-9105-5ab5559cb3ed	teacher	\N	2025-08-09 15:04:02.261785+00	2025-08-09 15:04:02.261785+00	hennecke@gymalf.de
de70c0c4-f095-47d6-a35a-dbec3f1f8cd4	student	\N	2025-08-11 06:38:39.147923+00	2025-08-11 06:38:39.147923+00	test1@test.de
0ab06125-4dc7-4dc5-b063-2b515dff7076	student	\N	2025-08-11 06:38:39.194247+00	2025-08-11 06:38:39.194247+00	test2@test.de
\.


--
-- Data for Name: course_student; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.course_student (course_id, student_id, enrolled_at) FROM stdin;
ff01a644-7328-4151-9e45-a92f49502aa6	de70c0c4-f095-47d6-a35a-dbec3f1f8cd4	2025-08-11 09:04:49.894034+00
ff01a644-7328-4151-9e45-a92f49502aa6	0ab06125-4dc7-4dc5-b063-2b515dff7076	2025-08-11 09:04:49.897205+00
\.


--
-- Data for Name: course_teacher; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.course_teacher (course_id, teacher_id, assigned_at) FROM stdin;
\.


--
-- Data for Name: unit_section; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.unit_section (id, unit_id, title, order_in_unit, materials, created_at, updated_at) FROM stdin;
2981d11f-d795-442e-b7cc-3e1e1017e5b3	02f80bbb-b393-408d-bb66-58fd362a1df3	Logikgatter	0	[{"id": "8589a05a-44a8-4b89-8f13-f8703e0d620b", "type": "markdown", "title": "Logische Verknüpfungen", "content": "Logische Verknüpfungen von Wahrheitswerten bzw. Bits werden technisch durch verschiedene Gatter realisiert. Dabei wird falsch und wahr bzw. 0 und 1 durch die beiden Zustände\\n\\n- Signal an bzw. wahr\\n- Signal aus bzw. falsch\\n\\nrealisiert. Die Schaltbausteine nennt man Gatter. Alle Gatter haben gemeinsam, dass die Grundform ein Rechteck ist. Links sind die Eingänge, rechts die Ausgänge.\\n\\nDie Beschriftung des Gatters gibt dann an, um welches Gatter - also welche logische Verknüpfung - es sich handelt. Im Folgenden werden die verschiedenen Gatter einzeln vorgestellt. Bei der Beschriftung von Gattereingängen und -ausgängen beachten wir folgende Regeln:\\n\\n- Eingangssignale werden mit Kleinbuchstaben beschrieben (z. B. a, b)\\n- Ausgangssignale dementsprechend mit Großbuchstaben (z. B. A)"}]	2025-08-10 07:40:41.315436+00	2025-08-10 07:40:41.315436+00
\.


--
-- Data for Name: course_unit_section_status; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.course_unit_section_status (course_id, section_id, is_published, published_at) FROM stdin;
ff01a644-7328-4151-9e45-a92f49502aa6	2981d11f-d795-442e-b7cc-3e1e1017e5b3	t	2025-08-11 09:09:15.559961+00
\.


--
-- Data for Name: feedback; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.feedback (id, feedback_type, message, created_at) FROM stdin;
d2051740-7ad6-4dd6-8bbf-05726876b400	unterricht	Du stinkst	2025-08-06 09:14:00.198469+00
5cd32622-4da1-4604-a8a4-d989b81f5e48	unterricht	Du stinkst	2025-08-06 09:14:02.184949+00
1e4ec6a9-a20f-43ef-91d0-11b55c27982c	unterricht	Du stinkst	2025-08-06 09:14:03.60466+00
cfcf55b0-6a2d-4757-b678-dd5b4a4b4dd9	plattform	Du stinkst	2025-08-06 09:14:05.122074+00
4bd428d0-1b3e-4ca5-87cc-99fec069ac6b	unterricht	Du stinkst!	2025-08-06 09:19:32.346844+00
59c10b36-ca33-446f-b125-f451b334489a	plattform	Du stinkst! nicht	2025-08-06 09:19:38.828336+00
\.


--
-- Data for Name: task; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.task (id, instruction, task_type, created_at, updated_at, section_id, order_in_section, criteria, assessment_criteria, solution_hints, is_mastery, max_attempts) FROM stdin;
3d8d6f5c-fe7c-4167-b222-ef1b573d7142	(a) Beschreibe in eigenen Worten, wie die Türsteuerung technisch umgesetzt werden soll.	text	2025-08-11 06:28:51.727915+00	2025-08-11 06:28:51.727915+00	2981d11f-d795-442e-b7cc-3e1e1017e5b3	0	\N	["Fachliche Korrektheit"]	Die Türsteuerung wird technisch durch ein ODER-Gatter umgesetzt. Es gibt zwei Eingänge (die Türöffner im 1. und 2. Stock) sowie einen Ausgang (die Haustür). Wenn Türöffner 1 *oder* Türöffner 2 gedrückt wird, öffnet sich die Haustür.	f	2
\.


--
-- Data for Name: student_mastery_progress; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.student_mastery_progress (student_id, task_id, current_interval, next_due_date, ease_factor, repetition_count, status, learning_step_index, relearning_step_index, last_attempt_date, last_score, total_attempts, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: submission; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.submission (id, student_id, task_id, submitted_at, solution_data, ai_feedback, ai_grade, feedback_generated_at, grade_generated_at, teacher_override_feedback, teacher_override_grade, created_at, updated_at, ai_criteria_analysis, feed_back_text, feed_forward_text, attempt_number) FROM stdin;
ede742b3-1404-4ada-afa6-d88f34e137f6	de70c0c4-f095-47d6-a35a-dbec3f1f8cd4	3d8d6f5c-fe7c-4167-b222-ef1b573d7142	2025-08-11 09:10:02.603414+00	{"text": "Da gibt es zwei Knöpfe und wenn einer davon gedrückt wird gehtn die Tür auf."}	Es ist super, dass du die grundlegende Funktion des Systems erkannt hast und beschrieben hast, dass das Drücken eines Knopfes die Tür öffnet! Allerdings fehlt in deiner Beschreibung die technische Umsetzung. Du schreibst "Da gibt es zwei Knöpfe und wenn einer davon gedrückt wird gehtn die Tür auf", aber die Musterlösung erwähnt ein ODER-Gatter, das für diese Funktion notwendig wäre. Das ist ein wichtiger Punkt, um die technische Seite besser zu verstehen.\n\nÜberlege dir, welche logischen Bausteine (wie z.B. ein ODER-Gatter) dafür notwendig wären, damit die Tür nur dann aufgeht, wenn *mindestens* einer der beiden Knöpfe gedrückt wird. Das hilft dir, die technische Umsetzung besser zu verstehen! Bleib dran, du bist schon auf einem guten Weg!	\N	2025-08-11 09:10:18.653657+00	\N	\N	\N	2025-08-11 09:10:02.603414+00	2025-08-11 09:10:02.603414+00	{"analysis_text": "**Kriterium: Fachliche Korrektheit**\\nStatus: nicht erfüllt\\nBeleg: \\"Da gibt es zwei Knöpfe und wenn einer davon gedrückt wird gehtn die Tür auf.\\"\\nAnalyse: Die Schülerlösung beschreibt zwar die grundlegende Funktionalität (Drücken eines Knopfes öffnet die Tür), geht aber nicht auf die technische Umsetzung ein. Die Musterlösung erwähnt ein ODER-Gatter, was ein wichtiger Bestandteil der technischen Realisierung wäre. Die Schülerlösung ist also fachlich unzureichend, da sie die technische Komponente völlig auslässt.", "method": "holistic"}	Es ist super, dass du die grundlegende Funktion des Systems erkannt hast und beschrieben hast, dass das Drücken eines Knopfes die Tür öffnet! Allerdings fehlt in deiner Beschreibung die technische Umsetzung. Du schreibst "Da gibt es zwei Knöpfe und wenn einer davon gedrückt wird gehtn die Tür auf", aber die Musterlösung erwähnt ein ODER-Gatter, das für diese Funktion notwendig wäre. Das ist ein wichtiger Punkt, um die technische Seite besser zu verstehen.	Überlege dir, welche logischen Bausteine (wie z.B. ein ODER-Gatter) dafür notwendig wären, damit die Tür nur dann aufgeht, wenn *mindestens* einer der beiden Knöpfe gedrückt wird. Das hilft dir, die technische Umsetzung besser zu verstehen! Bleib dran, du bist schon auf einem guten Weg!	1
2cb40ad7-e325-4878-95f1-432941a2614b	de70c0c4-f095-47d6-a35a-dbec3f1f8cd4	3d8d6f5c-fe7c-4167-b222-ef1b573d7142	2025-08-11 10:30:30.253786+00	{"text": "Man muss ein ODER-Gatter verwenden."}	Super, dass du erkannt hast, dass ein ODER-Gatter für die Türsteuerung benötigt wird! Das ist ein wichtiger Schritt nach vorne. Im Vergleich zum letzten Mal, wo du die Tür nur durch Drücken eines Knopfes öffnen konntest, hast du jetzt schon ein viel besseres Verständnis für die benötigte Logik. Um die fachliche Korrektheit noch weiter zu verbessern, könntest du genauer erklären, *warum* ein ODER-Gatter benötigt wird und wie es in diesem Fall funktioniert.\n\nÜberlege dir, was passieren soll, wenn *beide* Knöpfe gedrückt werden. Wie müsste das ODER-Gatter konfiguriert sein, um das gewünschte Ergebnis zu erzielen? Ich bin gespannt auf deine nächste Version!	\N	2025-08-11 10:30:43.644189+00	\N	\N	\N	2025-08-11 10:30:30.253786+00	2025-08-11 10:30:30.253786+00	{"analysis_text": "**Kriterium: Fachliche Korrektheit**\\nStatus: überwiegend erfüllt\\nBeleg: \\"Man muss ein ODER-Gatter verwenden.\\"\\nAnalyse: Die Schülerlösung identifiziert korrekt die Verwendung eines ODER-Gatters als grundlegende Komponente der Türsteuerung. Die Erklärung ist jedoch sehr kurz und lässt Details aus, was die Vollständigkeit der fachlichen Korrektheit einschränkt.", "method": "holistic_v3_history_prev_only"}	Super, dass du erkannt hast, dass ein ODER-Gatter für die Türsteuerung benötigt wird! Das ist ein wichtiger Schritt nach vorne. Im Vergleich zum letzten Mal, wo du die Tür nur durch Drücken eines Knopfes öffnen konntest, hast du jetzt schon ein viel besseres Verständnis für die benötigte Logik. Um die fachliche Korrektheit noch weiter zu verbessern, könntest du genauer erklären, *warum* ein ODER-Gatter benötigt wird und wie es in diesem Fall funktioniert.	Überlege dir, was passieren soll, wenn *beide* Knöpfe gedrückt werden. Wie müsste das ODER-Gatter konfiguriert sein, um das gewünschte Ergebnis zu erzielen? Ich bin gespannt auf deine nächste Version!	2
\.


--
-- PostgreSQL database dump complete
--

