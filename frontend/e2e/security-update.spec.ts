import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { test, expect } from "./support/feature-test";
import { newBrowserContext } from './support/browser-context';
import { currentUserSub, login } from './support/auth';
import { e2eEmail, e2ePassword, webBase } from './support/e2e-env';
import { ensureLearnerUser, ensureTeacherUser } from './support/keycloak';
import { seedLearnerNavigationCourse, seedH5pVisualSmokeUnit } from './support/seed-data';
import { registerE2EH5PContent } from './support/e2e-run-state';
import { holdProviderWorker, releaseProviderWorker, completeQueuedFeedbackDeterministically } from './support/submission-finalization-fixture';

test('@feature-acceptance security updates preserve authenticated Markdown, upload and H5P journeys', async ({ browser }) => {
  test.setTimeout(150_000);
  const teacherEmail = e2eEmail('security-teacher');
  const learnerEmail = e2eEmail('security-learner');
  await ensureTeacherUser(teacherEmail, e2ePassword);
  await ensureLearnerUser(learnerEmail, e2ePassword);
  const tc = await newBrowserContext(browser, { locale: 'de-DE' });
  const lc = await newBrowserContext(browser, { locale: 'de-DE' });
  try {
    const teacher = await tc.newPage(), learner = await lc.newPage();
    await login(teacher, teacherEmail, e2ePassword);
    await login(learner, learnerEmail, e2ePassword);
    const seeded = await seedLearnerNavigationCourse(teacher, learner, `Security ${Date.now()}`);
    await learner.goto(`/learning/courses/${seeded.courseId}/units/${seeded.unitId}?module=${seeded.graphModuleId}&task=${seeded.taskId}`);
    const editor = learner.locator('.learning-markdown-editor__surface [contenteditable=true]');
    await expect(editor).toBeVisible();
    await editor.fill('Sicherer Entwurf mit Umlauten: Größe und Rückmeldung.');
    await expect.poll(() => learner.evaluate(() => Object.entries(sessionStorage).some(
      ([key, value]) => key.startsWith('gustav.learning.submission-draft:') && value.includes('Größe und Rückmeldung')
    ))).toBe(true);
    await learner.reload();
    await expect(editor).toContainText('Größe und Rückmeldung');

    await holdProviderWorker();
    try {
      await learner.getByText('Datei hochladen', { exact: true }).click();
      await learner.getByLabel('Datei auswählen', { exact: true }).setInputFiles({
        name:'synthetic.png', mimeType:'image/png',
        buffer:execFileSync('../.venv/bin/python',['-c','from PIL import Image; import sys; Image.new("RGB",(64,64),"white").save(sys.stdout.buffer,format="PNG")']),
      });
      await learner.getByRole('button', { name:'Rückmeldung einholen', exact:true }).click();
      await expect.poll(async () => (await (await learner.request.get(`/api/learning/courses/${seeded.courseId}/tasks/${seeded.taskId}/submissions`)).json()).length).toBe(1);
      await completeQueuedFeedbackDeterministically({ courseId:seeded.courseId, taskId:seeded.taskId, learnerSub:await currentUserSub(learner) });
      await learner.reload();
      await learner.getByText('Datei hochladen', { exact:true }).click();
      await expect(learner.getByRole('region', {name:'Bisherige Datei'})).toBeVisible();
    } finally { await releaseProviderWorker(); }

    const h5p = await seedH5pVisualSmokeUnit(teacher, learner, `Security H5P ${Date.now()}`);
    const root = resolve(process.cwd(),'..');
    const pkg = execFileSync(resolve(root,'.venv/bin/python'), ['-c',
      "import io,pathlib,sys,zipfile\nb=io.BytesIO()\nwith zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:\n for p in pathlib.Path(sys.argv[1]).rglob('*'):\n  if p.is_file(): z.write(p,p.relative_to(sys.argv[1]))\nsys.stdout.buffer.write(b.getvalue())",
      resolve(root,'frontend/e2e/fixtures/h5p-multichoice-design')]);
    const imported = await teacher.request.post(`/api/teaching/units/${h5p.unitId}/sections/${h5p.sectionId}/tasks/${h5p.taskId}/h5p/import`, {
      headers:{origin:webBase}, multipart:{file:{name:'synthetic.h5p',mimeType:'application/zip',buffer:pkg}},
    });
    expect(imported.status()).toBe(200);
    registerE2EH5PContent(String((await imported.json()).h5p.content_id),teacherEmail);
    await learner.goto(`/learning/courses/${h5p.courseId}/units/${h5p.unitId}`);
    await learner.getByRole('button',{name:/beginnen/}).first().click();
    await expect(learner.locator('.h5p-multichoice')).toBeVisible({timeout:30_000});
    await learner.getByRole('radio',{name:/Vier/}).press('Space');
    await learner.locator('.h5p-question-check-answer').click();
    await expect(learner.getByText('Gespeichert (1/1).')).toBeVisible();
    expect((await learner.request.get('/h5p/auth/me')).status()).toBe(200);
  } finally { await lc.close(); await tc.close(); }
});
