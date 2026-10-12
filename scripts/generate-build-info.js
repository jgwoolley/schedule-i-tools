// Writes public/build.json with the current build's timestamp and (when
// running in GitHub Actions) the commit it was built from. Run via
// `npm run build`, normally only in CI. Locally, not running this leaves
// public/build.json absent, and the page's "Built ... ago" footer just
// stays empty (see loadBuildInfo() in index.html).
//
// GitHub Actions sets these env vars automatically for every workflow run:
// https://docs.github.com/en/actions/learn-github-actions/variables#default-environment-variables
const fs = require("fs");
const path = require("path");

const sha = process.env.GITHUB_SHA || null;
const repo = process.env.GITHUB_REPOSITORY || null; // "owner/repo"
const serverUrl = process.env.GITHUB_SERVER_URL || "https://github.com";

const commitUrl = sha && repo ? serverUrl + "/" + repo + "/commit/" + sha : null;

const buildInfo = {
  builtAt: new Date().toISOString(),
  commit: sha,
  commitUrl: commitUrl
};

const dest = path.join(__dirname, "..", "public", "build.json");
fs.writeFileSync(dest, JSON.stringify(buildInfo, null, 2) + "\n");
console.log("generate-build-info: wrote " + path.relative(process.cwd(), dest) + " " + JSON.stringify(buildInfo));
