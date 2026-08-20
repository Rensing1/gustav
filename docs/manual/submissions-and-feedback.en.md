# Submissions and feedback

GUSTAV-Version: 0.0.4
Last verified: 2026-08-20
[Deutsche Version](submissions-and-feedback.de.md)

![Formative feedback in the learning workspace](../assets/readme/formative-feedback.jpg)

## Purpose

GUSTAV separates formative feedback from final submission. Learners can have a version reviewed, reflect on the feedback, and revise it before submitting that exact version as final.

## Prerequisites

- The task is accessible to the learner.
- The task type supports the intended text or file submission.
- For AI feedback, the analysis and feedback services are operational.
- Before a final submission, feedback has already been requested for the current version.

## Step by step

1. The learner writes an answer or selects a suitable file.
2. **„Rückmeldung einholen“** (“Request feedback”) saves the current version as an immutable attempt and queues it for evaluation.
3. While processing is underway, GUSTAV displays an in-progress state. When processing is complete, **„Auswertung“** (“Evaluation”) and **„Rückmeldung“** (“Feedback”) appear.
4. The learner reads the feedback and continues editing the draft. A changed version requires feedback again.
5. **„Endgültig abgeben“** (“Submit as final”) becomes available only when the current draft exactly matches the most recently reviewed version.
6. The saved attempt remains available after final submission. Depending on the task, further editing may then be possible or an attempt limit may apply.

## Learner view

The interface distinguishes the editable draft from saved attempts. Previous submissions can be opened together with their evaluation and feedback. For file tasks, the file name, type, and available preview are displayed. In AI dialogues, final submission ends the dialogue and triggers the final evaluation.

## How it works

Every version sent to the server is saved as an immutable attempt. Duplicate transmissions are handled through repeatable requests. Before analysis, file uploads are checked for size, type, signature, and association with the task.

Processing runs in the background. GUSTAV publishes an evaluation and feedback only after they have been fully validated. A technical error does not change a saved answer; instead, the interface displays a sanitised error state.

AI feedback is formative. It is intended to encourage revision and is neither a grade nor an indisputable subject-matter judgement.

## Limitations

- An unsent editor draft is available only in the current browser tab.
- Final submission is possible only for the unchanged version most recently saved for feedback.
- Partial AI results are not displayed. If processing fails, feedback may be missing even though the answer has been saved securely.
- Permitted file formats and sizes depend on the task type; an unsuitable file is not accepted merely because it has been renamed with a different extension.
- Attempt limits are enforced by the server and cannot be bypassed by reloading the page or opening a second tab.
- The AI must not make a final pedagogical decision in place of the teacher.

## Common problems

- **„Für diese Fassung zuerst Rückmeldung einholen“** (“Request feedback for this version first”): The draft was changed after the last feedback request.
- **Evaluation does not appear:** First wait while the in-progress state is displayed. If a persistent error occurs, the version can be submitted for feedback again.
- **File is rejected:** Use the original format expected for the task type and select the file again.
- **Double-clicking does not create a second submission:** This is intentional protection against duplicate attempts.
- **Session has expired:** Sign in again. GUSTAV attempts to restore the secure working context; nevertheless, check the draft before sending it again.

## Related chapters

- [Materials and tasks](materials-and-tasks.en.md)
- [Learning workspace](learner-workspace.en.md)
- [Live view](live-view.en.md)
- [Diagnostics](diagnostics.en.md)

Technical details: [Learning reference](../references/learning.md) and [Learning AI reference](../references/learning_ai.md).
