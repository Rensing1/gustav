/**
 * Task kind toggle (Teacher UI)
 *
 * Why:
 * - The task create page supports multiple task kinds (native|h5p|visual|scratch).
 * - The UI needs to show/hide the correct field groups without relying on
 *   inline <script> blocks (CSP: `script-src 'self'`).
 *
 * Behavior:
 * - When the teacher selects "H5P", hide the native fields and show the H5P editor block.
 * - For "native", "visual", and "scratch", show the native fields and hide the H5P editor block.
 *
 * Notes:
 * - This script is safe to include globally; it no-ops when the expected elements
 *   are not present on the page.
 */

(() => {
  const sel = document.getElementById('task_kind');
  const nativeFields = document.getElementById('native-task-fields');
  const h5pFields = document.getElementById('h5p-task-fields');
  const instruction = document.getElementById('instruction_md');

  if (!sel || !nativeFields || !h5pFields || !instruction) return;

  const apply = () => {
    const kind = (sel.value || 'native');
    const showNative = kind !== 'h5p';
    const showH5P = kind === 'h5p';
    nativeFields.hidden = !showNative;
    h5pFields.hidden = !showH5P;
    instruction.required = showNative;
  };

  sel.addEventListener('change', apply);
  apply();
})();
