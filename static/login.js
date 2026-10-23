"use strict";

const form = document.querySelector("#login-form");
const submit = document.querySelector("#login-submit");
const errorMessage = document.querySelector("#login-error");
const inactivityNotice = document.querySelector("#inactivity-notice");

if (new URLSearchParams(window.location.search).get("expired") === "1") {
  inactivityNotice.hidden = false;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!form.reportValidity()) return;

  submit.disabled = true;
  errorMessage.hidden = true;
  try {
    const csrfResponse = await fetch("/api/auth/csrf");
    const csrfPayload = await csrfResponse.json();
    if (!csrfResponse.ok || !csrfPayload.csrf_token) {
      throw new Error(csrfPayload.error || "Could not start a secure sign-in session.");
    }

    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfPayload.csrf_token,
      },
      body: JSON.stringify({
        email: form.elements.email.value.trim(),
        password: form.elements.password.value,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Sign-in failed.");
    window.location.replace(payload.redirect || "/");
  } catch (error) {
    errorMessage.textContent = error.message || "Unable to sign in. Please try again.";
    errorMessage.hidden = false;
    submit.disabled = false;
  }
});