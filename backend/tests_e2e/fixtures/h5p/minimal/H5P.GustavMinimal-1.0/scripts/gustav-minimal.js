(function (H5P) {
  "use strict";

  /**
   * Extremely small H5P library used as an offline fixture for E2E tests.
   *
   * The goal is not feature completeness. We only need a runnable content type
   * that the server can import/export and the player can embed without any
   * external network requests.
   */
  H5P.GustavMinimal = function (params) {
    this.params = params || {};
  };

  H5P.GustavMinimal.prototype.attach = function ($container) {
    $container.addClass("h5p-gustav-minimal");
    const text = this.params.text || "Hello from GUSTAV";
    $container.text(text);
  };
})(H5P);
