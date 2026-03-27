import { resolve } from "node:path";

/** Absolute path to packaged inspect JS (classic scripts, no bundler). */
export const WAGTAIL_INSPECT_JS_DIR = resolve(
  process.cwd(),
  "src/wagtail_inspect/static/wagtail_inspect/js",
);
