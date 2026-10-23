/* Keep H5P's final state save working when WebKit disallows synchronous XHR.
 * Only same-origin, synchronous state POSTs use Beacon. Normal Ajax still uses
 * its original transport; authentication and review checks stay on the server.
 */
(function () {
  var jquery = window.H5P && window.H5P.jQuery;
  if (!jquery || typeof navigator.sendBeacon !== 'function') return;

  jquery.ajaxTransport('+json', function (options) {
    if (options.type !== 'POST' || options.async !== false) return;
    var url = new URL(options.url, window.location.href);
    if (url.origin !== window.location.origin ||
        !/^\/h5p\/contentUserData\/[^/]+\/state\/[^/]+$/.test(url.pathname)) return;

    return {
      send: function (_headers, complete) {
        var queued = false;
        try {
          // jQuery has already encoded data/preload/invalidate as form fields.
          var body = new Blob([options.data], { type: 'application/x-www-form-urlencoded;charset=UTF-8' });
          queued = navigator.sendBeacon(url.href, body);
        } catch (_error) {
          // A rejected queue must follow jQuery's error path, never sync XHR.
        }
        // This acknowledges queuing only. Learning results use their own API.
        if (queued) complete(200, 'success', { text: '{"success":true}' }, 'Content-Type: application/json');
        else complete(0, 'error');
      },
      abort: function () { /* A queued Beacon belongs to the browser lifecycle. */ }
    };
  });
}());
