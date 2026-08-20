# Learning workspace

GUSTAV-Version: 0.0.4
Last verified: 2026-08-20
[Deutsche Version](learner-workspace.de.md)

![Learning workspace with material and task](../assets/readme/learner-workspace.jpg)

## Purpose

The learning workspace is the central workspace for learners. It keeps the course, learning path, materials, tasks, and previous work together in a shared context. This chapter helps teachers understand what learners can actually see and use.

## Prerequisites

- The learner is a member of an active course.
- At least one learning unit is assigned to the course.
- The desired section or graph node is visible and, in modular learning units, released.
- Required H5P content and files have been saved completely.

## Step by step

1. The learner opens **„Lernraum“** (“Learning workspace”) and selects a course under **„Aktuelle Kurse“** (“Current courses”).
2. They open a visible learning unit. In modular learning units, the graph shows the learning path and the states of individual nodes.
3. They select an open node or section. Materials and tasks appear in the workspace.
4. Markdown texts are read directly. Files are loaded using **„Datei öffnen“** (“Open file”). An interactive simulation is deliberately opened with **„Simulation starten“** (“Start simulation”) and can be reset or closed.
5. A task is opened in the same workspace. Learners can leave it using **„Pausieren“** (“Pause”) and resume it later where the saved state supports this.
6. For practice modules, learners use **„Üben“** (“Practice”) to enter the separate review workflow.

## Learner view

Learners see only their own active courses, assigned learning units, and accessible content. In the modular graph, locked learning steps remain visible for orientation but cannot be opened. Open and completed nodes show the individual's learning progress, not that of the entire class.

Materials, a task, the learner's own previous submissions, and feedback are displayed in context. Internal technical IDs, sample solutions, criteria, and teacher context are not delivered as hidden aids.

## How it works

Access is not protected only by hidden buttons. Course membership, assignment, and release status are checked again with every protected request. Private files and H5P content receive only short-lived access limited to the specific learning context.

For modular units, GUSTAV calculates which prerequisites each person has fulfilled. The graph also serves as an advance organizer: learners can see where they are and which steps follow without opening locked content prematurely.

## Limitations

- Locked content remains locked even when accessed through a copied direct link.
- An unsent text draft exists only in the current browser tab. It is not backed up on the server and does not automatically appear on another device or in another tab.
- Simulations run in isolation and do not send results to GUSTAV.
- Not every file format can be displayed directly as a preview.
- An H5P task that has not yet been fully configured only shows that it is not ready.
- The learning workspace does not work offline. Loading content and submitting work require a connection to the GUSTAV server.

## Common problems

- **„Noch keine Lerneinheiten sichtbar“** (“No learning units visible yet”): Check the course membership and whether the learning unit is assigned to the course.
- **Module remains locked:** In the authoring view, check the directed prerequisites and the required number of prerequisites.
- **File or H5P content does not load:** Check whether the content and course assignment still exist; an old short-lived link cannot be reused permanently.
- **Draft is missing on another device:** Unsent drafts are not synchronized between devices.
- **Past course instead of current course:** The course has been archived and is no longer intended for active work.

## Related chapters

- [Courses and members](courses-and-members.en.md)
- [Learning units and releases](learning-units-and-releases.en.md)
- [Materials and tasks](materials-and-tasks.en.md)
- [Submissions and feedback](submissions-and-feedback.en.md)
- [Practice modules](practice-modules.en.md)

Technical details: [Learning reference](../references/learning.md).
