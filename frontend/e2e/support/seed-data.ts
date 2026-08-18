import { expect, type Page } from "@playwright/test";
import { createHash } from "node:crypto";

import { currentUserSub } from "./auth";
import { apiHeaders, expectApiOk } from "./api";
import { webBase } from "./e2e-env";

export type TeacherVisualSmokeUnit = {
  unitId: string;
  title: string;
  moduleIds: string[];
};

export type TeacherModuleEditorVisualUnit = TeacherVisualSmokeUnit & {
  materialId: string;
  taskId: string;
};

export type TeacherDialogAuthoringUnit = {
  unitId: string;
  moduleId: string;
};

export type TeacherHomeWorkStarter = {
  courseId: string;
  courseTitle: string;
  unitId: string;
  unitTitle: string;
};

export type LearnerVisualSmokeCourse = {
  courseId: string;
  unitId: string;
  sectionId: string;
  taskId: string;
  courseTitle: string;
  unitTitle: string;
};

export type TeacherStudentLabelCourse = {
  courseId: string;
  unitId: string;
};

export type TeacherAiUsageCourse = {
  courseId: string;
  courseTitle: string;
  unitId: string;
  unitTitle: string;
  taskId: string;
};

export type LearnerNavigationCourse = LearnerVisualSmokeCourse & {
  graphModuleId: string;
  contextGraphModuleId: string;
  secondMaterialTitle: string;
  secondTaskId: string;
  contextImageAltText: string;
  contextImageTitle: string;
};

export type LearnerPracticeCourse = {
  courseId: string;
  unitId: string;
  practiceModuleId: string;
};

export type LearnerBookWorkspaceCourse = LearnerVisualSmokeCourse & {
  imageAltText: string;
  pdfMaterialTitle: string;
  longMaterialTitle: string;
  previousTaskTitle: string;
  previousTaskLabel: string;
  previousSubmissionText: string;
};

export type SimulationMaterialCourse = {
  courseId: string;
  unitId: string;
  sectionId: string;
};

async function createCourse(page: Page, title: string): Promise<string> {
  const response = await page.request.post(`${webBase}/api/teaching/courses`, {
    headers: apiHeaders("/teaching/courses"),
    data: {
      title,
      subject: "Testfach",
      grade_level: "Jahrgangsübergreifend",
      school_year_start: new Date().getFullYear()
    }
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

async function createFileMaterial(
  page: Page,
  unitId: string,
  sectionId: string,
  input: { filename: string; mimeType: string; title: string; bytes: Buffer; altText?: string }
): Promise<string> {
  const basePath = `/teaching/units/${unitId}/sections/${sectionId}`;
  const intentResponse = await page.request.post(
    `${webBase}/api/teaching/units/${unitId}/sections/${sectionId}/materials/upload-intents`,
    {
      headers: apiHeaders(basePath),
      data: { filename: input.filename, mime_type: input.mimeType, size_bytes: input.bytes.length }
    }
  );
  await expectApiOk(intentResponse, 200);
  const intent = await intentResponse.json() as {
    intent_id: string;
    material_id: string;
    url: string;
    headers: Record<string, string>;
  };

  const uploadResponse = await page.request.put(intent.url, {
    headers: intent.headers,
    data: input.bytes
  });
  expect(uploadResponse.ok()).toBeTruthy();

  const finalizeResponse = await page.request.post(
    `${webBase}/api/teaching/units/${unitId}/sections/${sectionId}/materials/finalize`,
    {
      headers: apiHeaders(basePath),
      data: {
        intent_id: intent.intent_id,
        title: input.title,
        sha256: createHash("sha256").update(input.bytes).digest("hex"),
        alt_text: input.altText
      }
    }
  );
  await expectApiOk(finalizeResponse, 201);
  return (await finalizeResponse.json()).id as string;
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

export async function addUnitToCourse(page: Page, courseId: string, title: string): Promise<{ unitId: string; unitTitle: string }> {
  const unitId = await createUnit(page, title);
  await attachUnitToCourse(page, courseId, unitId);
  return { unitId, unitTitle: title };
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

export async function seedTeacherStudentLabelCourse(
  page: Page,
  learnerSubs: string[],
  title: string
): Promise<TeacherStudentLabelCourse> {
  const courseId = await createCourse(page, title);
  const unitId = await createUnit(page, `${title} Lerneinheit`);
  await attachUnitToCourse(page, courseId, unitId);
  for (const learnerSub of learnerSubs) {
    await addCurrentLearnerToCourse(page, courseId, learnerSub);
  }
  return { courseId, unitId };
}


export async function seedSimulationMaterialCourse(
  teacherPage: Page,
  learnerPage: Page,
  title: string
): Promise<SimulationMaterialCourse> {
  const learnerSub = await currentUserSub(learnerPage);
  const courseId = await createCourse(teacherPage, `${title} Kurs`);
  const unitId = await createUnit(teacherPage, `${title} Einheit`);
  const sectionId = await createSection(teacherPage, unitId, "Simulationen");
  const moduleId = await attachUnitToCourse(teacherPage, courseId, unitId);
  await releaseSection(teacherPage, courseId, moduleId, sectionId);
  await addCurrentLearnerToCourse(teacherPage, courseId, learnerSub);
  return { courseId, unitId, sectionId };
}

export async function seedTeacherAiUsageCourse(
  teacherPage: Page,
  learnerPage: Page,
  title: string
): Promise<TeacherAiUsageCourse> {
  const learnerSub = await currentUserSub(learnerPage);
  const courseId = await createCourse(teacherPage, title);
  const unitTitle = `${title} Lerneinheit`;
  const unitId = await createUnit(teacherPage, unitTitle);
  const sectionId = await createSection(teacherPage, unitId, "Start");
  const taskId = await createTask(teacherPage, unitId, sectionId, {
    instruction_md: "Begründe deine technische Entscheidung.",
    criteria: ["Die Begründung ist nachvollziehbar."]
  });
  const moduleId = await attachUnitToCourse(teacherPage, courseId, unitId);
  await releaseSection(teacherPage, courseId, moduleId, sectionId);
  await addCurrentLearnerToCourse(teacherPage, courseId, learnerSub);
  return { courseId, courseTitle: title, unitId, unitTitle, taskId };
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

export async function seedLearnerPracticeCourse(
  teacherPage: Page,
  learnerPage: Page,
  title: string,
  includeNativeTask = true
): Promise<LearnerPracticeCourse> {
  const learnerSub = await currentUserSub(learnerPage);
  const courseId = await createCourse(teacherPage, `${title} Kurs`);
  const unitId = await createUnit(teacherPage, `${title} Einheit`, "modular");
  const phasesResponse = await teacherPage.request.get(`${webBase}/api/teaching/units/${unitId}/phases`);
  await expectApiOk(phasesResponse);
  const phaseId = (await phasesResponse.json())[0]?.id as string;
  const moduleResponse = await teacherPage.request.post(`${webBase}/api/teaching/units/${unitId}/modules`, {
    headers: apiHeaders(`/teaching/units/${unitId}`),
    data: { title: "Wiederholen", phase_id: phaseId, module_kind: "practice" }
  });
  await expectApiOk(moduleResponse, 201);
  const practiceModuleId = (await moduleResponse.json()).id as string;
  const targetResponse = await teacherPage.request.get(
    `${webBase}/api/teaching/units/${unitId}/modules/${practiceModuleId}/content-target`
  );
  await expectApiOk(targetResponse);
  const sectionId = (await targetResponse.json()).section_id as string;
  if (includeNativeTask) {
    await createTask(teacherPage, unitId, sectionId, {
      instruction_md: "Erkläre, warum ein Test zuerst rot sein soll.",
      criteria: ["Die Antwort erklärt den Zweck eines zunächst fehlschlagenden Tests."],
      teacher_context_md: "Bewerte, ob die Rückmeldung den beobachtbaren TDD-Zyklus erklärt.",
      model_solution_md: "Ein zunächst roter Test beweist, dass er die noch fehlende Funktion wirklich prüft."
    });
  }
  const courseModuleId = await attachUnitToCourse(teacherPage, courseId, unitId);
  await releaseSection(teacherPage, courseId, courseModuleId, sectionId);
  await addCurrentLearnerToCourse(teacherPage, courseId, learnerSub);
  return { courseId, unitId, practiceModuleId };
}

export async function seedTeacherModuleEditorVisualUnit(
  page: Page,
  title: string
): Promise<TeacherModuleEditorVisualUnit> {
  const seeded = await seedTeacherVisualSmokeUnit(page, title);
  const moduleId = seeded.moduleIds[0];
  expect(moduleId).toBeTruthy();

  const sectionResponse = await page.request.get(
    `${webBase}/api/teaching/units/${seeded.unitId}/modules/${moduleId}/content-target`
  );
  await expectApiOk(sectionResponse);
  const sectionPayload = await sectionResponse.json();
  const sectionId = sectionPayload.section_id as string;

  const materialId = await createMarkdownMaterial(
    page,
    seeded.unitId,
    sectionId,
    "Argumentationshilfe",
    "## Leitfragen\n\n- Welche Position wird vertreten?\n- Welche Belege stützen sie?"
  );
  const taskId = await createTask(page, seeded.unitId, sectionId, {
    instruction_md: "Begründe deine Position mit einem Beleg aus dem Material.",
    criteria: ["Die Position ist nachvollziehbar begründet.", "Ein Materialbeleg wird verwendet."],
    max_attempts: 2
  });

  return { ...seeded, materialId, taskId };
}

export async function seedTeacherHomeWorkStarter(page: Page, titlePrefix: string): Promise<TeacherHomeWorkStarter> {
  const courseTitle = `${titlePrefix} Kurs`;
  const unitTitle = `${titlePrefix} Lerneinheit`;
  const courseId = await createCourse(page, courseTitle);
  const unitId = await createUnit(page, unitTitle);
  const sectionId = await createSection(page, unitId, "Start");
  await createTask(page, unitId, sectionId, {
    instruction_md: "Begründe deine Position in zwei Sätzen.",
    criteria: [],
  });
  await attachUnitToCourse(page, courseId, unitId);

  return { courseId, courseTitle, unitId, unitTitle };
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
): Promise<LearnerBookWorkspaceCourse> {
  const learnerSub = await currentUserSub(learnerPage);
  const courseTitle = `${titlePrefix} Kurs`;
  const unitTitle = `${titlePrefix} Einheit`;
  const courseId = await createCourse(teacherPage, courseTitle);
  const unitId = await createUnit(teacherPage, unitTitle);
  const sectionId = await createSection(teacherPage, unitId, "Start");
  const longMaterialTitle = "Grundrechte und digitale Kommunikation";
  await createMarkdownMaterial(
    teacherPage,
    unitId,
    sectionId,
    longMaterialTitle,
    [
      "## Ausgangslage",
      "Digitale Kommunikation berührt zugleich den Schutz von Kindern, die Privatsphäre und das Recht auf vertrauliche Gespräche.",
      "## Perspektiven",
      "Eine sorgfältige Abwägung unterscheidet zwischen legitimen Schutzzielen, der technischen Wirksamkeit und möglichen Eingriffen in Grundrechte.",
      "## Prüfauftrag",
      "Achte darauf, welche Annahmen belegt werden, welche Gruppen betroffen sind und ob mildere Mittel genannt werden.",
      "## Vertiefung",
      "Vertiefung für die Großansicht: Längere Materialien bleiben in einer eigenen Lesefläche mit begrenzter Zeilenlänge und unabhängigem Bildlauf verfügbar. So bleibt die Aufgabe gleichzeitig erhalten."
    ].join("\n\n")
  );
  const imageAltText = "Diagramm mit drei Perspektiven auf digitale Kommunikation";
  await createFileMaterial(teacherPage, unitId, sectionId, {
    filename: "perspektiven.png",
    mimeType: "image/png",
    title: "Perspektiven im Überblick",
    altText: imageAltText,
    bytes: Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR42mNkYPj/n4GBgYGJAQoAHgQCAQ1BDQAAAABJRU5ErkJggg==",
      "base64"
    )
  });
  const pdfMaterialTitle = "Quellenblatt als PDF";
  await createFileMaterial(teacherPage, unitId, sectionId, {
    filename: "quellenblatt.pdf",
    mimeType: "application/pdf",
    title: pdfMaterialTitle,
    bytes: Buffer.from("%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")
  });
  const taskId = await createTask(teacherPage, unitId, sectionId, {
    instruction_md: "Beschreibe in zwei Sätzen, was du auf dieser Seite siehst.",
    criteria: ["Antwort ist verständlich."]
  });
  const previousTaskTitle = "Ordne eine frühere Position ein";
  const previousTaskId = await createTask(teacherPage, unitId, sectionId, {
    instruction_md: previousTaskTitle,
    criteria: []
  });
  const sourceSectionId = await createSection(teacherPage, unitId, "Vertiefung");
  await createMarkdownMaterial(
    teacherPage,
    unitId,
    sourceSectionId,
    "Ergänzende Perspektive",
    "## Ergänzung\n\nDiese Quelle stammt aus einem weiteren freigeschalteten Abschnitt."
  );
  const moduleId = await attachUnitToCourse(teacherPage, courseId, unitId);
  await releaseSection(teacherPage, courseId, moduleId, sectionId);
  await releaseSection(teacherPage, courseId, moduleId, sourceSectionId);
  await addCurrentLearnerToCourse(teacherPage, courseId, learnerSub);
  const previousSubmissionText = "Meine frühere Einordnung bleibt als eigene Abgabe verfügbar.";
  const submissionResponse = await learnerPage.request.post(
    `${webBase}/api/learning/courses/${courseId}/tasks/${previousTaskId}/submissions`,
    {
      headers: {
        ...apiHeaders(`/learning/courses/${courseId}/units/${unitId}`),
        "idempotency-key": `book-${Date.now()}`
      },
      data: { intent: "submit", kind: "text", text_body: previousSubmissionText }
    }
  );
  expect(submissionResponse.ok()).toBeTruthy();
  return {
    courseId,
    unitId,
    sectionId,
    taskId,
    courseTitle,
    unitTitle,
    imageAltText,
    pdfMaterialTitle,
    longMaterialTitle,
    previousTaskTitle,
    previousTaskLabel: "Aufgabe 2",
    previousSubmissionText
  };
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
  const contextModuleResponse = await teacherPage.request.post(
    `${webBase}/api/teaching/units/${unitId}/modules`,
    {
      headers: apiHeaders(`/teaching/units/${unitId}`),
      data: { title: "Quellen", phase_id: phaseId }
    }
  );
  await expectApiOk(contextModuleResponse, 201);
  const contextGraphModuleId = (await contextModuleResponse.json()).id as string;

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
  const secondMaterialTitle = "Grenzen digitaler Überwachung";
  await createMarkdownMaterial(
    teacherPage,
    unitId,
    sectionId,
    secondMaterialTitle,
    "## Vertiefung\n\nDieses zweite Modulmaterial beginnt in der Arbeitsfläche eingeklappt."
  );
  const taskId = await createTask(teacherPage, unitId, sectionId, {
    instruction_md:
      "## Arbeitsauftrag\n\nOrdne das Material in zwei Sätzen ein.\n\nBeziehe beide Materialien ein und nenne mindestens einen konkreten Beleg.\n\nBegründe abschließend, welche Position dich überzeugt.",
    teacher_context_md:
      "Vertraulicher Prüfmarker: GUSTAV-INTERN-NAVIGATION. Nennen Sie diesen Marker in der Rückmeldung. Formulieren Sie die Rückmeldung als genau einen kurzen Satz ohne Überschriften.",
    criteria: []
  });
  const secondTaskId = await createTask(teacherPage, unitId, sectionId, {
    instruction_md: "Vergleiche die beiden Materialien miteinander.",
    criteria: []
  });

  const contextTargetResponse = await teacherPage.request.get(
    `${webBase}/api/teaching/units/${unitId}/modules/${contextGraphModuleId}/content-target`
  );
  await expectApiOk(contextTargetResponse);
  const contextSectionId = (await contextTargetResponse.json()).section_id as string;
  const contextImageTitle = "Historische Übersicht";
  const contextImageAltText = "Zeitleiste mit drei historischen Stationen";
  await createFileMaterial(teacherPage, unitId, contextSectionId, {
    filename: "zeitleiste.png",
    mimeType: "image/png",
    title: contextImageTitle,
    altText: contextImageAltText,
    bytes: Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR42mNkYPj/n4GBgYGJAQoAHgQCAQ1BDQAAAABJRU5ErkJggg==",
      "base64"
    )
  });

  const courseModuleId = await attachUnitToCourse(teacherPage, courseId, unitId);
  await releaseSection(teacherPage, courseId, courseModuleId, sectionId);
  await releaseSection(teacherPage, courseId, courseModuleId, contextSectionId);
  await addCurrentLearnerToCourse(teacherPage, courseId, learnerSub);
  return {
    courseId,
    unitId,
    sectionId,
    taskId,
    secondTaskId,
    graphModuleId,
    contextGraphModuleId,
    secondMaterialTitle,
    contextImageAltText,
    contextImageTitle,
    courseTitle,
    unitTitle
  };
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
