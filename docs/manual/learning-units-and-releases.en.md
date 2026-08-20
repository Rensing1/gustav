# Learning units and releases

GUSTAV-Version: 0.0.4
Last verified: 2026-08-20
[Deutsche Version](learning-units-and-releases.de.md)

![Modular learning unit in the teacher view](../assets/readme/teacher-authoring.jpg)

## Purpose

Learning units bundle reusable teaching content. A teacher creates them once and can then assign them to one or more of their own courses. GUSTAV supports linear learning units and modular learning paths.

## Prerequisites

- You are signed in as a teacher.
- An active, fully configured course exists for use in lessons.
- Before assignment, the learning unit should contain enough content to prevent learners from entering empty workspaces.

## Step by step

1. Open **„Lerneinheiten“** (“Learning units”) and select **„Neue Lerneinheit“** (“New learning unit”).
2. Enter a title and choose **„Modular“** (“Modular”) or **„Linear“** (“Linear”). This basic type determines the subsequent structure.
3. In a linear learning unit, create ordered sections.
4. In a modular learning unit, add phases and **„Lernmodul“** (“Learning module”) or **„Übungsmodul“** (“Practice module”) nodes. Connect learning modules in the direction in which prerequisites should apply.
5. Select a learning module and, under **„Freischaltung“** (“Release”), set how many of its incoming prerequisites must be fulfilled.
6. Add content as described in [Materials and tasks](materials-and-tasks.en.md).
7. Then open the desired course and, under **„Lerneinheiten“**, select **„Lerneinheit hinzufügen“** (“Add learning unit”).
8. Check the learner view before using the unit in lessons.

## Learner view

Assigned learning units appear in the active course. In modular units, learners see the entire learning path as a graph. Nodes can be open, locked, or completed. The materials and tasks of an open node appear together in one workspace.

Practice modules can be repeated and are never marked as completed. Their special behavior is described in [Practice modules](practice-modules.en.md).

## How it works

A learning unit remains the property of its author. The course assignment points to this reusable unit; it does not create an independent copy. Changes to the unit therefore take effect in every course to which it is assigned.

In the modular graph, a directed connection means that the target depends on the source. The configured number of required predecessors determines whether all or only some incoming prerequisites must be fulfilled. GUSTAV calculates the state for each learner based on their own work.

## Limitations

- Linear and modular are different structural models; switching between them later is not provided as a normal editing action.
- A course assignment is not a copy. Changes can affect several ongoing courses at the same time.
- Practice modules must not have outgoing connections and cannot release other modules.
- Learners cannot bypass a locked module with a direct link.
- Removing a learning unit from a course does not delete the reusable learning unit, but it changes its availability in that course.
- Simultaneous content changes by multiple people do not have shared real-time conflict resolution.

## Common problems

- **Module remains locked:** Check the direction and number of incoming connections and the value under **„Freischaltung“**.
- **No learning unit in the course:** Assign it in the course using **„Lerneinheit hinzufügen“**.
- **A change appears in several courses:** This is intentional for a reusable learning unit.
- **A connection cannot be continued from a practice module:** Practice modules may only be the target, not the source, of a connection.

## Related chapters

- [Courses and members](courses-and-members.en.md)
- [Materials and tasks](materials-and-tasks.en.md)
- [Learning workspace](learner-workspace.en.md)
- [Practice modules](practice-modules.en.md)

Technical details: [Teaching reference](../references/teaching.md) and [Glossary](../glossary.md).
