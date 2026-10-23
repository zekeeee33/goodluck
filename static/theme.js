"use strict";

(() => {
  const storageKey = "glfs-theme";
  const isDarkPreferred = () => window.matchMedia("(prefers-color-scheme: dark)").matches;

  function applyTheme(theme) {
    const selectedTheme = theme === "dark" ? "dark" : "light";
    document.documentElement.dataset.theme = selectedTheme;
    const button = document.querySelector("#theme-toggle");
    if (button) {
      const nextTheme = selectedTheme === "dark" ? "light" : "dark";
      const label = nextTheme === "dark" ? "Dark mode" : "Light mode";
      button.setAttribute("aria-label", `Switch to ${label.toLowerCase()}`);
      button.title = `Switch to ${label.toLowerCase()}`;
      button.querySelector(".theme-icon").textContent = nextTheme === "dark" ? "☾" : "☀";
      button.querySelector(".theme-label").textContent = label;
    }
  }

  try {
    const savedTheme = localStorage.getItem(storageKey);
    applyTheme(savedTheme === "light" || savedTheme === "dark"
      ? savedTheme
      : (isDarkPreferred() ? "dark" : "light"));
  } catch {
    applyTheme(isDarkPreferred() ? "dark" : "light");
  }

  document.addEventListener("DOMContentLoaded", () => {
    const button = document.querySelector("#theme-toggle");
    if (!button) return;
    applyTheme(document.documentElement.dataset.theme);
    button.addEventListener("click", () => {
      const nextTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      applyTheme(nextTheme);
      try {
        localStorage.setItem(storageKey, nextTheme);
      } catch {
        // Theme remains active for this page even if persistence is unavailable.
      }
    });
  });
})();
