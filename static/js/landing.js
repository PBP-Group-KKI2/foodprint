/* FoodPrint – landing page
 * Scroll reveals, count-up numbers and the waste chart.
 * Content is only hidden once this script adds .reveal-ready, so it stays
 * visible if JavaScript fails or the visitor prefers reduced motion.
 */
(function () {
  "use strict";

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const canObserve = "IntersectionObserver" in window;

  function onFirstView(elements, callback, threshold) {
    if (!canObserve) {
      elements.forEach(callback);
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        observer.unobserve(entry.target);
        callback(entry.target);
      });
    }, { threshold: threshold, rootMargin: "0px 0px -8% 0px" });
    elements.forEach((el) => observer.observe(el));
  }

  // ---------- Scroll reveals ----------
  if (!reduceMotion && canObserve) {
    const targets = [...document.querySelectorAll("[data-reveal]")];
    document.querySelectorAll("[data-reveal-group]").forEach((group) => {
      [...group.children].forEach((child, index) => {
        child.style.setProperty("--i", index);
        targets.push(child);
      });
    });
    document.documentElement.classList.add("reveal-ready");
    onFirstView(targets, (el) => el.classList.add("is-visible"), 0.15);
  }

  // ---------- Count-up for real totals ----------
  function countUp(el) {
    const target = parseInt(el.dataset.countTo, 10);
    if (!target) return;
    const duration = 1200;
    const start = performance.now();
    const step = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = Math.round(target * eased).toLocaleString();
      if (progress < 1) requestAnimationFrame(step);
    };
    el.textContent = "0";
    requestAnimationFrame(step);
  }
  if (!reduceMotion) {
    onFirstView([...document.querySelectorAll("[data-count-to]")], countUp, 0.6);
  }

  // ---------- Waste chart (drawn when scrolled into view so its animation is seen) ----------
  const canvas = document.getElementById("wasteChart");
  const dataScript = document.getElementById("landing-chart-data");
  if (canvas && dataScript && window.Chart) {
    const chartData = JSON.parse(dataScript.textContent);
    onFirstView([canvas], () => {
      new window.Chart(canvas.getContext("2d"), {
        type: "doughnut",
        data: {
          labels: chartData.labels,
          datasets: [{
            label: "% of Global Food Waste",
            data: chartData.values,
            backgroundColor: chartData.colors,
            borderWidth: 2,
            borderColor: "#ffffff",
          }],
        },
        options: {
          responsive: true,
          animation: reduceMotion ? false : { duration: 900 },
          plugins: { legend: { position: "bottom" } },
          cutout: "65%",
        },
      });
    }, 0.3);
  }
})();
