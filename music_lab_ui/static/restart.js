/*
 * The confirm-and-wait half of the restart button.
 *
 * `window.aiLabConfirmRestart` is called by the button's own `js=` handler and
 * its return value decides whether Python restarts anything — the dialog has to
 * be answered before the process is replaced, not after.
 *
 * `window.aiLabAwaitRestart` then waits for the port to answer again. A fixed
 * timeout would either reload too early onto a connection refused, or make you
 * stare at a dead page for longer than the restart took; polling reloads the
 * moment the new process is listening.
 */
(function () {
  "use strict";

  var POLL_INTERVAL_MS = 400;
  var GIVE_UP_AFTER_MS = 30000;

  window.aiLabConfirmRestart = function (message) {
    return window.confirm(message);
  };

  window.aiLabAwaitRestart = function () {
    var startedAt = Date.now();
    var here = window.location.href;

    function attempt() {
      if (Date.now() - startedAt > GIVE_UP_AFTER_MS) {
        // Reload anyway: a visible error page beats an interface that silently
        // stopped matching the code behind it.
        window.location.reload();
        return;
      }
      // `cache: no-store` so a cached 200 cannot be mistaken for the new
      // process having come up.
      fetch(here, { method: "HEAD", cache: "no-store" })
        .then(function () {
          window.location.reload();
        })
        .catch(function () {
          window.setTimeout(attempt, POLL_INTERVAL_MS);
        });
    }

    // The old process is still answering for a moment; give it time to go away
    // before the first probe, or the very first fetch succeeds against it.
    window.setTimeout(attempt, 1200);
  };
})();
