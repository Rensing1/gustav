# Practice modules

GUSTAV-Version: 0.0.4
Last verified: 2026-08-20
[Deutsche Version](practice-modules.de.md)

![Selection of practice stacks](../assets/readme/practice-progress.jpg)

## Purpose

Practice modules support active recall and spaced practice. A teacher assembles repeatable tasks for this purpose. GUSTAV presents new or due tasks again later without marking the practice module as permanently completed.

## Prerequisites

- The learning unit is modular; linear learning units do not have practice modules.
- The practice module is open to the learner through its incoming prerequisites.
- It contains at least one valid native free-text or H5P task.
- A native practice task has a prompt, at least one criterion, teacher context, and a model answer written by the teacher.

## Step by step

1. Open a modular learning unit and, when adding a node, select **„Übungsmodul“** (“Practice module”) as the **„Modultyp“** (“Module type”).
2. Connect preceding learning modules to the practice module and, under **„Freischaltung“** (“Release”), set how many prerequisites must be fulfilled.
3. Open the practice module and select **„Aufgabe hinzufügen“** (“Add task”).
4. Create a **„Normale Aufgabe“** (“Standard task”) with criteria, **„Lehrkraft-Kontext“** (“Teacher context”), and **„Musterlösung“** (“Model answer”), or create a complete **„H5P“** task.
5. Check that the course is assigned to the learning unit. An open, non-empty practice module appears in the **„Üben“** (“Practice”) area.
6. Learners select one or more stacks and either **„Fällige Wiederholungen“** (“Due reviews”) or **„Alle Aufgaben üben“** (“Practise all tasks”).
7. During the session, they work through one task at a time, receive feedback, and can skip a task for that session or deliberately end the session.

![Native practice task with criteria, teacher context, and model answer](assets/practice-module-authoring.jpg)

## Learner view

Under **„Üben“**, learners see only open practice stacks containing valid tasks. **„Fällige Wiederholungen“** contains new tasks and tasks currently due; **„Alle Aufgaben üben“** supports targeted exam preparation with all tasks from the selected stacks.

Native answers receive a concise evaluation. Learners see **„Sicher beantwortet“** (“Answered confidently”), **„Teilweise beantwortet“** (“Partially answered”), or **„Noch nicht sicher“** (“Not yet confident”), as well as the next review time. After the first completed attempt, the model answer can be opened deliberately. H5P tasks use their score and do not display a separate model-answer button.

## How it works

When a session starts, its set of tasks is saved. Later changes to content or due dates do not silently add tasks to this active session. Each learner can have no more than one active session; returning to practice resumes it.

Tasks answered partially or inadequately are presented again no more than once within the same session. Skipping does not change the learner's individual review state. Opening the model answer marks exactly the next attempt as supported and prevents it from being counted as an independent, confident recall.

GUSTAV schedules reviews with the versioned `gustav-practice-v1` scheduler. It repeats the same task created by the teacher; GUSTAV does not generate new task variants.

## Limitations

- Practice modules cannot contain materials and cannot have outgoing connections.
- They are never marked as completed and do not release subsequent modules.
- Visual, Scratch, Calliope, Filius, and dialogue tasks are not supported.
- Submission deadlines and maximum attempt counts are not permitted for practice tasks.
- Changes to the task, criteria, model answer, or H5P content do not reset existing review states.
- Repeating the same task does not demonstrate transfer to new situations. Additional tasks with a different focus must be created for this purpose.
- Dedicated teacher diagnostics for practice states are not yet available in this version.
- Microphone input and transcription are not part of practice modules.
- A session is technically limited to 50 stacks and 1,000 snapshot tasks.

## Common problems

- **Practice stack does not appear:** The module is locked, empty, or does not contain a valid task.
- **Native task cannot be saved:** Add criteria, teacher context, and a model answer, and remove the submission deadline or attempt limit.
- **Nothing is due today:** If needed, select **„Alle Aufgaben üben“**; genuine early recall attempts will affect subsequent scheduling.
- **A task appears again:** Partially answered or insufficiently answered tasks can be repeated exactly once within the same session.
- **Session does not start again:** An active session already exists. Resume it or deliberately end it.

## Related chapters

- [Learning units and releases](learning-units-and-releases.en.md)
- [Materials and tasks](materials-and-tasks.en.md)
- [Learning workspace](learner-workspace.en.md)
- [Diagnostics](diagnostics.en.md)

Technical details: [Learning reference](../references/learning.md), [Teaching reference](../references/teaching.md), and [Scheduler concept](../research/practice_scheduler_concept.md).
