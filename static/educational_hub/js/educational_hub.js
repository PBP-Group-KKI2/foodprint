/* FoodPrint – Educational Hub
 * HTMX sends the requests; this file shows errors, opens the delete modal,
 * and updates Like/Save buttons optimistically.
 */
(function () {
  "use strict";

  var errorBox = document.getElementById("educational-hub-error");
  var hideTimer = null;

  function showError(message) {
    if (!errorBox) return;
    errorBox.textContent = message;
    errorBox.hidden = false;
    clearTimeout(hideTimer);
    hideTimer = setTimeout(function () { errorBox.hidden = true; }, 5000);
  }

  function messageFor(status) {
    if (status === 401) return "Please log in to do that.";
    if (status === 403) return "You don't have permission to do that.";
    if (status === 404) return "That article no longer exists.";
    if (status === 429) return "You're doing that too many times. Please wait a moment and try again.";
    return "Something went wrong. Please try again.";
  }

  // Server answered with an error status (4xx/5xx). HTMX leaves the page as it was.
  document.body.addEventListener("htmx:responseError", function (e) {
    showError(messageFor(e.detail.xhr.status));
  });

  // Request never reached the server (offline, server down).
  document.body.addEventListener("htmx:sendError", function () {
    showError("Couldn't reach FoodPrint. Check your connection and try again.");
  });

  // Confirmation modals: a link with data-eh-open-dialog="<id>" opens that <dialog>.
  // If the browser has no <dialog> support, the link just opens its fallback page.
  document.addEventListener("click", function (e) {
    var trigger = e.target.closest("[data-eh-open-dialog]");
    if (!trigger) return;
    var dialog = document.getElementById(trigger.dataset.ehOpenDialog);
    if (!dialog || typeof dialog.showModal !== "function") return;
    e.preventDefault();
    dialog.showModal();
  });

  // Clicking the dark backdrop (outside the modal box) closes it, like Escape does.
  document.querySelectorAll(".educational-hub__dialog").forEach(function (dialog) {
    dialog.addEventListener("click", function (e) {
      if (e.target === dialog) dialog.close();
    });
  });

  // Mark the updating region as busy for screen readers.
  document.body.addEventListener("htmx:beforeRequest", function (e) {
    var target = e.detail.target;
    if (target) target.setAttribute("aria-busy", "true");
  });
  document.body.addEventListener("htmx:afterRequest", function (e) {
    var target = e.detail.target;
    if (target && target.isConnected) target.removeAttribute("aria-busy");
  });

  // Optimistic Like/Save: flip the button as soon as it is clicked. A successful
  // response swaps in the server's version; a failed one flips it back.
  function reactionButton(elt) {
    var form = elt && elt.closest && elt.closest(".educational-hub__reactions form");
    return form ? form.querySelector(".educational-hub__reaction") : null;
  }

  function flip(button) {
    var on = button.getAttribute("aria-pressed") !== "true";
    button.setAttribute("aria-pressed", String(on));
    button.classList.toggle("educational-hub__reaction--active", on);
    var label = button.querySelector("[data-on-label]");
    if (label) label.textContent = on ? label.dataset.onLabel : label.dataset.offLabel;
    var count = button.querySelector(".educational-hub__reaction-count");
    if (count) count.textContent = Math.max(0, parseInt(count.textContent, 10) + (on ? 1 : -1));
  }

  document.body.addEventListener("htmx:beforeRequest", function (e) {
    var button = reactionButton(e.detail.elt);
    if (button) flip(button);
  });
  ["htmx:responseError", "htmx:sendError"].forEach(function (name) {
    document.body.addEventListener(name, function (e) {
      var button = reactionButton(e.detail.elt);
      if (button && button.isConnected) flip(button);
    });
  });
})();
