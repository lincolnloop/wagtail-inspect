import { GlobalRegistrator } from "@happy-dom/global-registrator";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { WAGTAIL_INSPECT_JS_DIR } from "./static-dir.js";

// Register all DOM globals (window, document, HTMLElement, etc.) onto globalThis.
// @happy-dom/global-registrator sets window === globalThis, matching browser behaviour.
GlobalRegistrator.register();

// Stub Wagtail/Stimulus globals that the controller scripts depend on.
// inspect-core.js itself doesn't require them, but they must exist before
// any future loading of preview-inspect-controller.js or userbar-inspect.js.
Object.assign(globalThis, {
  StimulusModule: { Controller: class Controller {} },
  wagtail: { app: { register: () => {} } },
});

// Load inspect-core.js as a classic (non-module) browser script.
// new Function('window', code)(globalThis) executes the code in a function scope
// where the `window` parameter is globalThis (the happy-dom window), so all
// assignments like `window.WagtailInspectMode = ...` land on globalThis and are
// accessible in tests as plain globals.
function loadClassicScript(filename) {
  const code = readFileSync(resolve(WAGTAIL_INSPECT_JS_DIR, filename), "utf-8");
  // eslint-disable-next-line no-new-func
  new Function("window", code)(globalThis);
}

loadClassicScript("inspect-core.js");
loadClassicScript("inspect-augment.js");
loadClassicScript("preview-inspect-helpers.js");
