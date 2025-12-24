/**
 * Minimal ESM replacement for the `await-lock` NPM package.
 *
 * Why:
 * - `@lumieducation/h5p-webcomponents` ships an ES2015 build that contains
 *   `import AwaitLock from 'await-lock'`.
 * - The published `await-lock` package is CommonJS, which can't be imported
 *   directly from browsers as an ES module.
 *
 * This implementation covers the subset used by Lumi's `dom-utils.js`:
 * - `acquireAsync()` to await the lock.
 * - `release()` to hand over the lock to the next waiter.
 */

export default class AwaitLock {
  #acquired = false;
  #queue = [];

  get acquired() {
    return this.#acquired;
  }

  acquireAsync({ timeout } = {}) {
    if (!this.#acquired) {
      this.#acquired = true;
      return Promise.resolve();
    }

    return new Promise((resolve, reject) => {
      const entry = { resolve, reject, timer: null };
      this.#queue.push(entry);
      if (timeout == null) return;
      entry.timer = setTimeout(() => {
        const idx = this.#queue.indexOf(entry);
        if (idx >= 0) this.#queue.splice(idx, 1);
        reject(new Error("timeout"));
      }, timeout);
    });
  }

  release() {
    if (!this.#acquired) return;
    const next = this.#queue.shift();
    if (!next) {
      this.#acquired = false;
      return;
    }
    if (next.timer) clearTimeout(next.timer);
    // Keep the lock acquired, hand it over to the next waiter.
    next.resolve();
  }
}

