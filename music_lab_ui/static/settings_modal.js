/*
 * Escape and backdrop-click close the settings dialog.
 *
 * Visibility itself is Gradio's: the panel is a Column whose `visible` flag a
 * Python callback toggles. This script never hides anything directly — it
 * clicks the same close button a user would, so there is exactly one path that
 * changes the state and Python's idea of it cannot drift from the DOM's.
 */
(function () {
  "use strict";

  // Every detector has a dialog of its own, so this has to find the open one
  // rather than the first one: querySelector would keep returning the hidden
  // muscriptor panel and Escape would do nothing for the others.
  function openModal() {
    var modals = document.querySelectorAll(".settings-modal");
    for (var i = 0; i < modals.length; i += 1) {
      // Not offsetParent: that is always null on a fixed-position element,
      // which these are, so the usual visibility check never sees them open.
      if (modals[i].getClientRects().length) return modals[i];
    }
    return null;
  }

  function close(modal) {
    var button = modal.querySelector(".settings-close button, button.settings-close");
    if (button) button.click();
  }

  /*
   * Badge disclosures open as popovers. Native <details> has no light dismiss,
   * so one is supplied — otherwise every explanation you glance at stays open
   * over the chart it explains.
   */
  function openPopovers() {
    return document.querySelectorAll(".lab-disclosure.layout-badge[open]");
  }

  function closePopovers(except) {
    var open = openPopovers();
    for (var i = 0; i < open.length; i += 1) {
      if (open[i] !== except) open[i].removeAttribute("open");
    }
  }

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    var modal = openModal();
    if (modal) {
      close(modal);
      return;
    }
    closePopovers(null);
  });

  // The backdrop is the modal's own ::before, so a click that lands on the
  // element itself rather than on anything inside it came from the backdrop.
  document.addEventListener("click", function (event) {
    var modal = openModal();
    if (modal && event.target === modal) {
      close(modal);
      return;
    }
    // `closest` keeps the popover open when the click was inside it — links in
    // a body have to stay clickable.
    var inside = event.target.closest
      ? event.target.closest(".lab-disclosure.layout-badge")
      : null;
    closePopovers(inside);
  });
})();
