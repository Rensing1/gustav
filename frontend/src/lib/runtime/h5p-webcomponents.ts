export type H5PWebcomponentsModule = {
  defineElements?: (names: string[]) => void;
};

export async function loadH5PWebcomponentsModule(): Promise<H5PWebcomponentsModule> {
  const entry = "/h5p/webcomponents/index.js";
  return (await import(/* @vite-ignore */ entry)) as H5PWebcomponentsModule;
}
