export type H5PTaskEditorMount = {
  destroy: () => void;
  whenReady?: Promise<void>;
};

export type H5PTaskEditorModule = {
  mountH5PTaskEditor: (root: HTMLElement) => H5PTaskEditorMount;
};

export async function loadH5PTaskEditorModule(): Promise<H5PTaskEditorModule> {
  const entry = "/js/h5p_task_editor.js";
  const module = (await import(/* @vite-ignore */ entry)) as Partial<H5PTaskEditorModule>;
  if (typeof module.mountH5PTaskEditor !== "function") {
    throw new Error("Der H5P-Editor konnte nicht initialisiert werden.");
  }
  return { mountH5PTaskEditor: module.mountH5PTaskEditor };
}
