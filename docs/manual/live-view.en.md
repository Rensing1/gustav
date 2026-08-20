# Live view

GUSTAV-Version: 0.0.4
Last verified: 2026-08-20
[Deutsche Version](live-view.de.md)

## Purpose

The live view supports the teacher during an ongoing lesson. It shows the current work status for a selected learning unit and allows a quick transition from the class overview to an individual learner's most recent submission.

![Live view with class overview and learner detail](assets/live-view.jpg)

## Prerequisites

- You are the teacher who owns the course.
- The course exists and has at least one learning unit assigned to it.
- Members and tasks exist; meaningful detail data becomes available only after submissions have been made.

## Step by step

1. Open **„Unterrichten“** (“Teaching”) or go directly to **„Live“** (“Live”).
2. Under **„Kurs“** (“Course”), select the desired course and then select the current unit under **„Lerneinheit“** (“Learning unit”).
3. Select **„Live öffnen“** (“Open live view”). The table displays learners, progress, average, and most recent submission.
4. If necessary, sort the overview by learner label or most recent submission.
5. Select a learner row. The task bar and detail view appear on the right.
6. Switch between **„Abgabe“** (“Submission”) and **„Rückmeldung“** (“Feedback”). For dialogue tasks, the permission-checked dialogue history may also appear.
7. Keep the view open during the lesson; new states are reloaded regularly.

## Learner view

Learners do not see the class matrix. They continue working in the learning workspace and receive their own feedback there. The live view is a separate teacher projection and does not permit access to work from other courses.

## How it works

The overview reads specially prepared data for exactly one course and one learning unit. It regularly refreshes changed rows and detail states without rebuilding the entire page for every change. The detail view shows the most recent authorised submission for the selected task together with any available feedback.

Average and progress provide orientation during lessons. They summarise available task states and are intended to make notable support needs visible.

## Limitations

- Live view shows a current snapshot and is not a long-term learning progress analysis.
- The detail area focuses on the most recent submission; it does not replace a complete submission history.
- An average is not an automatically generated grade and must not be used without professional interpretation.
- Without an assigned learning unit or submissions, the view remains empty or displays **„Noch keine Abgabe“** (“No submission yet”).
- Practice states do not currently have their own live evaluation.
- Updates occur regularly but are not guaranteed to be transmitted in real time to the second.

## Common problems

- **„Keine Lerneinheiten verfügbar“** (“No learning units available”): First assign a learning unit to the course.
- **„Noch keine Kurse für den Live-Raum verfügbar“** (“No courses available for the live space yet”): Create your own course or check its status.
- **„Noch keine Abgabe“**: The selected learner has not yet saved a visible submission for this task.
- **Feedback is missing:** Analysis may still be running or may have failed; the saved submission may nevertheless be available.
- **Values do not change immediately:** Wait for the next refresh or reload the view.

## Related chapters

- [Courses and members](courses-and-members.en.md)
- [Submissions and feedback](submissions-and-feedback.en.md)
- [Diagnostics](diagnostics.en.md)

Technical details: [Live reference](../references/teaching_live.md).
