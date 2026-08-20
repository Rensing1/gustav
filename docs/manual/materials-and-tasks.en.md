# Materials and tasks

GUSTAV-Version: 0.0.4
Last verified: 2026-08-20
[Deutsche Version](materials-and-tasks.de.md)

## Purpose

Materials present content; tasks require learners to produce their own work and can trigger formative feedback. Both are created in a section or learning module and arranged in an understandable order.

## Prerequisites

- A linear or modular learning unit exists.
- You have opened the section or node in which the content should appear.
- Clear subject-specific criteria and sufficient teacher context have been prepared for tasks evaluated by AI.
- A suitable H5P file or the H5P editor is available for H5P content.

## Step by step

1. Open a learning unit and then the desired section or node.
2. Select **„Material hinzufügen“** (“Add material”) and choose Markdown text, **„Datei“** (“File”), or **„Interaktive Simulation“** (“Interactive simulation”).
3. Enter a clear title. For images, add alternative text. Upload a simulation as a fully self-contained HTML file and check it using **„Vorschau starten“** (“Start preview”).
4. Select **„Aufgabe hinzufügen“** (“Add task”) and the appropriate task type: **„Normale Aufgabe“** (“Standard task”), **„H5P“**, **„Visuelle Aufgabe“** (“Visual task”), **„Scratch“**, **„Calliope“**, **„Filius“**, or **„KI-Dialog“** (“AI dialogue”).
5. Write the task prompt and add the criteria required for the type, the **„Lehrkraft-Kontext“** (“Teacher context”), a **„Musterlösung“** (“Sample solution”) where applicable, and any further settings.
6. Check H5P content in the editor. For an AI dialogue, you can test the most recently saved version with a sample response.
7. Arrange materials and tasks in the order in which learners should work through them.

## Learner view

Learners see only content that has been released and is accessible to them. Markdown is displayed with formatting, files can be opened after an authorization check, and simulations start only after a deliberate action. Internal criteria, teacher context, and sample solutions are not visible in the normal task view.

Depending on the task type, learners write text, upload a suitable file, work on H5P content, or conduct a limited AI dialogue. Details about submissions and evaluation are provided in [Submissions and feedback](submissions-and-feedback.en.md).

## How it works

Private files are not delivered through permanent public storage paths. When files are uploaded, GUSTAV checks their type, size, and contextual association, among other things. Simulations run in an isolated offline environment.

Criteria describe the subject-specific aspects the AI should analyze. The teacher context supports subject-specific interpretation but is not shown to learners as a task hint. The AI generates a formative analysis; pedagogical responsibility remains with the teacher.

## Limitations

- Simulations do not send results to GUSTAV and have no network access. They do not replace a task when evidence of learning is required.
- Not every file can be displayed directly in the browser; in that case, only opening or downloading is available.
- An H5P task requires functional H5P content. An H5P task that has been created but not yet edited is not ready for learners.
- Practice modules allow only native free-text and H5P tasks; materials and other task types are rejected there.
- AI feedback is not a reliable final judgment and must not be used as a grade without review.
- In AI dialogues, learners see neither the internal role nor the learning objective or teacher context.

## Common problems

- **File must be selected again:** Browsers cannot restore local file selections after a page reload.
- **Simulation is rejected:** Use a fully self-contained HTML file of no more than 5 MiB without external resources.
- **H5P is “not ready yet”:** Open the task again in the H5P editor and save complete content.
- **Feedback is too general in subject terms:** Make the criteria, task prompt, and teacher context more precise.
- **Task type is missing in the practice module:** Use only **„Normale Aufgabe“** or **„H5P“** there.

## Related chapters

- [Learning units and releases](learning-units-and-releases.en.md)
- [Learning workspace](learner-workspace.en.md)
- [Submissions and feedback](submissions-and-feedback.en.md)
- [Practice modules](practice-modules.en.md)

Technical details: [Teaching reference](../references/teaching.md) and [Learning reference](../references/learning.md).
