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

  function openModal() {
    var modal = document.querySelector(".settings-modal");
    // Not offsetParent: that is always null on a fixed-position element, which
    // this dialog is, so the usual visibility check would never see it open.
    if (!modal || !modal.getClientRects().length) return null;
    return modal;
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
