const SESSION_USER_KEY = "interview-copilot.session-user.v1";

// These values are temporary workflow data, not durable account storage.
const PRIVATE_SESSION_KEYS = [
  "interview-copilot.setup-state.v1",
  "interview-copilot.review-material.v1",
  "interview-copilot.retraining-focus.v1",
  "interview-copilot.question-selection.v1",
  "interview-copilot.coaching-question-selection.v1",
  "interview-copilot.resume-extraction.v1",
  "interview-copilot.interview-session.v1",
] as const;

export function clearPrivateSessionData() {
  for (const key of PRIVATE_SESSION_KEYS) sessionStorage.removeItem(key);
}

export function syncPrivateSessionUser(userId: string | null) {
  const previousUserId = sessionStorage.getItem(SESSION_USER_KEY);
  if (previousUserId !== userId) clearPrivateSessionData();
  if (userId) sessionStorage.setItem(SESSION_USER_KEY, userId);
  else sessionStorage.removeItem(SESSION_USER_KEY);
}
