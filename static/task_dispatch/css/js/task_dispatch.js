/* FoodPrint – Task Dispatch
 * Claim a pending report with AJAX, so the list updates without reloading.
 * Without JavaScript the Claim buttons still work as normal form posts.
 */
(function () {
  "use strict";

  var pendingCount = document.getElementById("td-pending-count");
  var openCount = document.getElementById("td-open-count");
  var openLabel = document.getElementById("td-open-label");
  var flash = document.getElementById("td-flash");

  function showFlash(text, isError) {
    if (!flash) return;
    flash.textContent = text;
    flash.classList.toggle("td-flash--error", Boolean(isError));
    flash.hidden = false;
  }

  function updateCounts(data) {
    if (pendingCount && typeof data.pending_count === "number") pendingCount.textContent = data.pending_count;
    if (openCount && typeof data.open_task_count === "number") {
      openCount.textContent = data.open_task_count;
      if (openLabel) openLabel.textContent = data.open_task_count === 1 ? "task" : "tasks";
    }
  }

  function markClaimed(row, data) {
    // Replace the Claim button with a link to the new task.
    var form = row.querySelector("[data-ajax-claim]");
    var link = document.createElement("a");
    link.href = data.task_url;
    link.className = "rp-btn td-item__open";
    link.textContent = "Open task →";
    form.replaceWith(link);
    row.classList.add("td-item--claimed");
  }

  document.addEventListener("submit", function (e) {
    var form = e.target.closest("[data-ajax-claim]");
    if (!form) return;
    e.preventDefault();

    var row = form.closest(".td-item");
    var button = form.querySelector("button");
    var token = form.querySelector("input[name=csrfmiddlewaretoken]").value;
    button.disabled = true;
    button.textContent = "Claiming…";

    fetch(form.action, {
      method: "POST",
      headers: { "X-CSRFToken": token, "X-Requested-With": "XMLHttpRequest" },
      body: new FormData(form),
    })
      .then(function (res) {
        return res.json().then(function (data) { return { status: res.status, data: data }; });
      })
      .then(function (result) {
        updateCounts(result.data);
        if (result.status === 201) {
          markClaimed(row, result.data);
          showFlash("You claimed “" + result.data.title + "”. It’s now in My tasks.", false);
        } else if (result.status === 409) {
          // Someone else was faster: take the row off the list.
          row.remove();
          showFlash(result.data.error, true);
        } else {
          throw new Error("Unexpected response");
        }
      })
      .catch(function () {
        // Fall back to a normal form post (full page load).
        form.submit();
      });
  });
})();