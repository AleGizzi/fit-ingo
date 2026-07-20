// Bumped by hand on each release, shown in Settings ▸ About.
//
// A release that changes the frontend MUST bump this AND rebuild dist/ —
// otherwise sw.js is byte-identical, the phone's service worker sees nothing
// new to install, and "check for updates" reports up-to-date forever.
export const APP_VERSION = "1.4.0";
