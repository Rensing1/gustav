import { expect, type Page } from "@playwright/test";

import { currentUserSub } from "./auth";
import { apiHeaders, expectApiOk } from "./api";
import { webBase } from "./e2e-env";

export type TeacherVisualSmokeUnit = {
  unitId: string;
  title: string;
  moduleIds: string[];
};

export type TeacherDialogAuthoringUnit = {
  unitId: string;
  moduleId: string;
};

export type LearnerVisualSmokeCourse = {
  courseId: string;
  unitId: string;
  sectionId: string;
  taskId: string;
  courseTitle: string;
  unitTitle: string;
};

export type LearnerNavigationCourse = LearnerVisualSmokeCourse & {
  graphModuleId: string;
};

async function createCourse(page: Page, title: string): Promise<string> {
  const response = await page.request.post(`${webBase}/api/teaching/courses`, {
    headers: apiHeaders("/teaching/courses"),
    data: { title }
  });
  await expectApiOk(response, 201);
  const payload = await response.json();
  return payload.id as string;
}

async function createUnit(page: Page, title: string, unitType: "linear" | "modular" = "linear"): Promise<string> {
  const response = await page.request.post(`${webBase}/api/teaching/units`, {
    headers: apiHeaders("/teaching/units"),
    data: { title, unit_type: unitType }
  });
  await expectApiOk(response, 201);
  const payload = await response.json();
  return payload.id as string;
}

async function createSection(page: Page, unitId: string, title: string): Promise<string> {
  const response = await page.request.post(`${webBase}/api/teaching/units/${unitId}/sections`, {
    headers: apiHeaders(`/teaching/units/${unitId}`),
    data: { title }
  });
  await expectApiOk(response, 201);
  const payload = await response.json();
  return payload.id as string;
}

async function createTask(page: Page, unitId: string, sectionId: string, data: Record<string, unknown>): Promise<string> {
  const response = await page.request.post(`${webBase}/api/teaching/units/${unitId}/sections/${sectionId}/tasks`, {
    headers: apiHeaders(`/teaching/units/${unitId}`),
    data
  });
  await expectApiOk(response, 201);
  const payload = await response.json();
  return payload.id as string;
}

async function createMarkdownMaterial(
  page: Page,
  unitId: string,
  sectionId: string,
  title: string,
  bodyMd: string
): Promise<string> {
  const response = await page.request.post(
    `${webBase}/api/teaching/units/${unitId}/sections/${sectionId}/materials`,
    {
      headers: apiHeaders(`/teaching/units/${unitId}`),
      data: { title, body_md: bodyMd }
    }
  );
  await expectApiOk(response, 201);
  return (await response.json()).id as string;
}

async function attachUnitToCourse(page: Page, courseId: string, unitId: string): Promise<string> {
  const response = await page.request.post(`${webBase}/api/teaching/courses/${courseId}/modules`, {
    headers: apiHeaders(`/teaching/courses/${courseId}`),
    data: { unit_id: unitId }
  });
  await expectApiOk(response, 201);
  const payload = await response.json();
  return payload.id as string;
}

async function releaseSection(page: Page, courseId: string, moduleId: string, sectionId: string): Promise<void> {
  const response = await page.request.patch(
    `${webBase}/api/teaching/courses/${courseId}/modules/${moduleId}/sections/${sectionId}/visibility`,
    {
      headers: apiHeaders(`/teaching/courses/${courseId}`),
      data: { visible: true }
    }
  );
  await expectApiOk(response, 200);
}

async function addCurrentLearnerToCourse(page: Page, courseId: string, learnerSub: string): Promise<void> {
  const response = await page.request.post(`${webBase}/api/teaching/courses/${courseId}/members`, {
    headers: apiHeaders(`/teaching/courses/${courseId}`),
    data: { student_sub: learnerSub }
  });
  if (![201, 204].includes(response.status())) {
    await expectApiOk(response);
  }
}

export async function seedTeacherVisualSmokeUnit(page: Page, title: string): Promise<TeacherVisualSmokeUnit> {
  const unitId = await createUnit(page, title, "modular");
  const moduleIds: string[] = [];

  const phasesResponse = await page.request.get(`${webBase}/api/teaching/units/${unitId}/phases`);
  await expectApiOk(phasesResponse);
  const phases = await phasesResponse.json();
  const phaseId = phases[0]?.id as string | undefined;

  for (const moduleTitle of ["Startmodul", "Zielmodul"]) {
    const moduleResponse = await page.request.post(`${webBase}/api/teaching/units/${unitId}/modules`, {
      headers: apiHeaders(`/teaching/units/${unitId}`),
      data: { title: moduleTitle, phase_id: phaseId }
    });
    await expectApiOk(moduleResponse, 201);
    const modulePayload = await moduleResponse.json();
    moduleIds.push(modulePayload.id as string);
  }

  return { unitId, title, moduleIds };
}

export async function seedTeacherDialogAuthoringUnit(
  page: Page,
  title: string
): Promise<TeacherDialogAuthoringUnit> {
  const seeded = await seedTeacherVisualSmokeUnit(page, title);
  const moduleId = seeded.moduleIds[0];
  expect(moduleId).toBeTruthy();

  const sectionResponse = await page.request.get(
    `${webBase}/api/teaching/units/${seeded.unitId}/modules/${moduleId}/content-target`
  );
  await expectApiOk(sectionResponse);
  const sectionPayload = await sectionResponse.json();
  const sectionId = sectionPayload.section_id as string;

  await createTask(page, seeded.unitId, sectionId, {
    instruction_md: "Bereits vorhandene Aufgabe",
    criteria: []
  });

  return { unitId: seeded.unitId, moduleId };
}

export async function seedLearnerVisualSmokeCourse(
  teacherPage: Page,
  learnerPage: Page,
  titlePrefix: string
): Promise<LearnerVisualSmokeCourse> {
  const learnerSub = await currentUserSub(learnerPage);
  const courseTitle = `${titlePrefix} Kurs`;
  const unitTitle = `${titlePrefix} Einheit`;
  const courseId = await createCourse(teacherPage, courseTitle);
  const unitId = await createUnit(teacherPage, unitTitle);
  const sectionId = await createSection(teacherPage, unitId, "Start");
  await createMarkdownMaterial(
    teacherPage,
    unitId,
    sectionId,
    "Grundrechte und digitale Kommunikation",
    [
      "## Ausgangslage",
      "Digitale Kommunikation berührt zugleich den Schutz von Kindern, die Privatsphäre und das Recht auf vertrauliche Gespräche.",
      "## Perspektiven",
      "Eine sorgfältige Abwägung unterscheidet zwischen legitimen Schutzzielen, der technischen Wirksamkeit und möglichen Eingriffen in Grundrechte.",
      "## Prüfauftrag",
      "Achte darauf, welche Annahmen belegt werden, welche Gruppen betroffen sind und ob mildere Mittel genannt werden.",
      "## Vertiefung",
      "Längere Materialien bleiben in einer eigenen Lesefläche mit begrenzter Zeilenlänge und unabhängigem Bildlauf verfügbar. So bleibt die Aufgabe gleichzeitig erhalten."
    ].join("\n\n")
  );
  const taskId = await createTask(teacherPage, unitId, sectionId, {
    instruction_md: "Beschreibe in zwei Sätzen, was du auf dieser Seite siehst.",
    criteria: ["Antwort ist verständlich."]
  });
  const moduleId = await attachUnitToCourse(teacherPage, courseId, unitId);
  await releaseSection(teacherPage, courseId, moduleId, sectionId);
  await addCurrentLearnerToCourse(teacherPage, courseId, learnerSub);
  return { courseId, unitId, sectionId, taskId, courseTitle, unitTitle };
}

export async function seedLearnerNavigationCourse(
  teacherPage: Page,
  learnerPage: Page,
  titlePrefix: string
): Promise<LearnerNavigationCourse> {
  const learnerSub = await currentUserSub(learnerPage);
  const courseTitle = `${titlePrefix} Kurs`;
  const unitTitle = `${titlePrefix} Einheit`;
  const courseId = await createCourse(teacherPage, courseTitle);
  const unitId = await createUnit(teacherPage, unitTitle, "modular");

  const phasesResponse = await teacherPage.request.get(`${webBase}/api/teaching/units/${unitId}/phases`);
  await expectApiOk(phasesResponse);
  const phaseId = (await phasesResponse.json())[0]?.id as string;
  const moduleResponse = await teacherPage.request.post(`${webBase}/api/teaching/units/${unitId}/modules`, {
    headers: apiHeaders(`/teaching/units/${unitId}`),
    data: { title: "Grundlagen", phase_id: phaseId }
  });
  await expectApiOk(moduleResponse, 201);
  const graphModuleId = (await moduleResponse.json()).id as string;

  const targetResponse = await teacherPage.request.get(
    `${webBase}/api/teaching/units/${unitId}/modules/${graphModuleId}/content-target`
  );
  await expectApiOk(targetResponse);
  const sectionId = (await targetResponse.json()).section_id as string;
  await createMarkdownMaterial(
    teacherPage,
    unitId,
    sectionId,
    "Grundrechte und digitale Kommunikation",
    "## Ausgangslage\n\nDieses Material ist beim ersten Lesen vollständig geöffnet."
  );
  const taskId = await createTask(teacherPage, unitId, sectionId, {
    instruction_md: "Ordne das Material in zwei Sätzen ein.",
    criteria: []
  });

  const courseModuleId = await attachUnitToCourse(teacherPage, courseId, unitId);
  await releaseSection(teacherPage, courseId, courseModuleId, sectionId);
  await addCurrentLearnerToCourse(teacherPage, courseId, learnerSub);
  return { courseId, unitId, sectionId, taskId, graphModuleId, courseTitle, unitTitle };
}

export async function seedLearnerDialogCourse(
  teacherPage: Page,
  learnerPage: Page,
  titlePrefix: string
): Promise<LearnerVisualSmokeCourse> {
  const learnerSub = await currentUserSub(learnerPage);
  const courseTitle = `${titlePrefix} Kurs`;
  const unitTitle = `${titlePrefix} Einheit`;
  const courseId = await createCourse(teacherPage, courseTitle);
  const unitId = await createUnit(teacherPage, unitTitle);
  const sectionId = await createSection(teacherPage, unitId, "Dialog");
  const taskId = await createTask(teacherPage, unitId, sectionId, {
    instruction_md: "Untersuche die Quelle im Gespräch und begründe deine Beobachtung.",
    criteria: [],
    dialog: {
      partner_name: "Archivarin Ada",
      partner_description_md: "Ada hilft dir, die Quelle genau zu untersuchen.",
      role_md: "Frage sachlich nach Belegen in der Quelle.",
      learning_goal_md: "Der Schüler begründet eine Beobachtung an der Quelle.",
      opening_message_md: "Welche Beobachtung möchtest du zuerst untersuchen?",
      response_mode: "free_text",
      max_rounds: 2,
      closing_prompt_md: "Fasse deine wichtigste Erkenntnis zusammen."
    }
  });
  const moduleId = await attachUnitToCourse(teacherPage, courseId, unitId);
  await releaseSection(teacherPage, courseId, moduleId, sectionId);
  await addCurrentLearnerToCourse(teacherPage, courseId, learnerSub);
  return { courseId, unitId, sectionId, taskId, courseTitle, unitTitle };
}

export async function seedH5pVisualSmokeUnit(
  teacherPage: Page,
  learnerPage: Page,
  titlePrefix: string
): Promise<LearnerVisualSmokeCourse> {
  const learnerSub = await currentUserSub(learnerPage);
  const courseTitle = `${titlePrefix} H5P-Kurs`;
  const unitTitle = `${titlePrefix} H5P-Einheit`;
  const courseId = await createCourse(teacherPage, courseTitle);
  const unitId = await createUnit(teacherPage, unitTitle);
  const sectionId = await createSection(teacherPage, unitId, "Interaktiv");
  const taskId = await createTask(teacherPage, unitId, sectionId, {
    instruction_md: "H5P-Aufgabe",
    h5p: { content_id: null, display_options: {} }
  });
  const moduleId = await attachUnitToCourse(teacherPage, courseId, unitId);
  await releaseSection(teacherPage, courseId, moduleId, sectionId);
  await addCurrentLearnerToCourse(teacherPage, courseId, learnerSub);
  return { courseId, unitId, sectionId, taskId, courseTitle, unitTitle };
}
