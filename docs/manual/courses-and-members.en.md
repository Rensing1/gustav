# Courses and members

GUSTAV-Version: 0.0.4
Last verified: 2026-08-20
[Deutsche Version](courses-and-members.de.md)

![Teacher's course overview](../assets/readme/teacher-course-overview.jpg)

## Purpose

A course represents a specific learning group. It connects members with the learning units used in lessons. Teachers can manage active courses, invite classes, and archive completed courses.

## Prerequisites

- You are signed in as a teacher.
- The course must be active for invitations and changes.
- The title, subject, grade level, and school year must be entered in full before members, invitations, and learning units can be managed reliably.

## Step by step

1. Open **„Kurse“** (“Courses”) and select **„Neuer Kurs“** (“New course”).
2. Enter a title, subject, grade level, and school year, then select **„Kurs anlegen“** (“Create course”).
3. Open the course. Under **„Mitglieder“** (“Members”), you can use **„Mitglied hinzufügen“** (“Add member”) to search for and add individual existing learners.
4. To invite an entire class, select **„Klasse einladen“** (“Invite class”). The shared link is valid for 24 hours. You can copy it, display or download it as a QR code, and send invitations to permitted school email addresses.
5. Under **„Lerneinheiten“** (“Learning units”), assign existing content to the course. Creating content is explained in [Learning units and releases](learning-units-and-releases.en.md).
6. At the end of the teaching period, you can archive the course under **„Kurs bearbeiten“** (“Edit course”). You can undo an accidental archive in **„Archiv“** (“Archive”) by selecting **„Wiederherstellen“** (“Restore”).

![Invitation with link and QR code](../assets/readme/course-invitation.jpg)

## Learner view

Members see an active course under **„Aktuelle Kurse“** (“Current courses”) in the learning workspace. Archived courses appear as past courses and are no longer intended for active work. Anyone who redeems a valid class link after signing in or registering joins exactly this course.

## How it works

Only the teacher who owns a course may change it. There is at most one active class link per course. Generating a new link revokes the previous one; archiving the course also invalidates any existing link. If a member who joined via the link is later removed, the same link does not allow them to rejoin unintentionally.

Learning records are retained when a course is archived, but the course becomes read-only. Before permanent deletion, GUSTAV shows how many memberships, submissions, dialogues, and files are affected.

## Limitations

- A shared invitation is always valid for exactly 24 hours; the teacher cannot choose a different duration.
- An archived or incompletely configured course cannot be edited normally.
- Removed members lose access to the course. A new membership must be created deliberately.
- Permanently deleting a course cannot be undone and also removes the associated learning records.
- A class link does not make a course public: signing in or registering and having the learner role are still required.

## Common problems

- **„Kursdaten unvollständig“** (“Course data incomplete”): Open **„Kurs bearbeiten“** and add the missing subject, grade level, or school year.
- **No valid class link:** Open **„Klasse einladen“** and generate a new link.
- **Learning unit is missing from the selection:** You must own the learning unit, and it must not already be assigned to the course.
- **Course is read-only:** Restore a course that was archived accidentally before changing it.

## Related chapters

- [Learning units and releases](learning-units-and-releases.en.md)
- [Learning workspace](learner-workspace.en.md)
- [Live view](live-view.en.md)
- [Diagnostics](diagnostics.en.md)

Technical details: [Teaching reference](../references/teaching.md) and [User management](../references/user_management.md).
