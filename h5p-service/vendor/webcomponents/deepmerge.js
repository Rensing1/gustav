/**
 * Minimal ESM replacement for the `deepmerge` NPM package.
 *
 * Why:
 * - `@lumieducation/h5p-webcomponents` ships an ES2015 build that contains
 *   `import merge from 'deepmerge'`.
 * - Browsers cannot resolve bare module specifiers without a bundler/import map.
 * - We run the webcomponents directly (no frontend bundling) in the H5P service,
 *   so we provide a small local ESM module and map `deepmerge` via import maps.
 *
 * Behavior:
 * - Deep-merges plain objects.
 * - Concatenates arrays (matching deepmerge's default behavior).
 * - For all other values, the source value replaces the target value.
 */

function isPlainObject(value) {
  if (!value || typeof value !== "object") return false;
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}

function clone(value) {
  if (Array.isArray(value)) return value.map(clone);
  if (isPlainObject(value)) return merge({}, value);
  return value;
}

function merge(target, source) {
  if (Array.isArray(target) && Array.isArray(source)) {
    return [...target.map(clone), ...source.map(clone)];
  }
  if (isPlainObject(target) && isPlainObject(source)) {
    const out = { ...target };
    for (const [key, srcValue] of Object.entries(source)) {
      if (Object.prototype.hasOwnProperty.call(out, key)) {
        out[key] = merge(out[key], srcValue);
      } else {
        out[key] = clone(srcValue);
      }
    }
    return out;
  }
  return clone(source);
}

export default merge;

