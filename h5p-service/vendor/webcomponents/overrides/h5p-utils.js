import merge from './vendor/deepmerge.js';

/**
 * This file is a small, browser-compatible override for
 * `@lumieducation/h5p-webcomponents/build/es2015/h5p-utils.js`.
 *
 * Why:
 * - Upstream uses a bare import `deepmerge`, which requires import maps/bundlers.
 * - We serve webcomponents directly from our H5P service and want them to work
 *   even when import maps don't apply (browser differences, caching, etc.).
 *
 * The implementation is otherwise identical to the upstream module.
 */

/**
 * Merges the new IIntegration object with the global one.
 * @param newIntegration
 * @param contentId
 */
export function mergeH5PIntegration(newIntegration, contentId) {
  if (!window.H5PIntegration) {
    window.H5PIntegration = newIntegration;
    return;
  }
  if (contentId && newIntegration.contents && newIntegration.contents[`cid-${contentId}`]) {
    if (!window.H5PIntegration.contents) {
      window.H5PIntegration.contents = {};
    }
    window.H5PIntegration.contents[`cid-${contentId}`] = newIntegration.contents[`cid-${contentId}`];
  }
  // We don't want to mutate the newIntegration parameter, so we shallow clone
  // it.
  const newIntegrationDup = { ...newIntegration };
  // We don't merge content object information, as there might be issues with
  // this.
  delete newIntegrationDup.contents;
  window.H5PIntegration = merge(window.H5PIntegration, newIntegrationDup);
}

/**
 * Removes the data about the content from the global H5PIntegration object.
 * @param contentId
 */
export function removeUnusedContent(contentId) {
  if (window.H5PIntegration?.contents && window.H5PIntegration.contents[`cid-${contentId}`]) {
    delete window.H5PIntegration.contents[`cid-${contentId}`];
  }
}

