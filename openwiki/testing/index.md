# Files

- [Tests and verification](tests-and-verification.md) - How the Worker and frontend are verified without touching the physical frame. Node's built-in test runner exercises worker/*.test.js with mocked fetch, KV and Durable Objects, while frontend changes are checked in a headless 1280×720 browser using demo mode and the ?diag overlay.
