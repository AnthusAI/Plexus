#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DASHBOARD_DIR="$ROOT_DIR/dashboard"

export SMOKE_DASHBOARD_URL="${SMOKE_DASHBOARD_URL:-http://localhost:3000}"
export PLEXUS_API_URL="${PLEXUS_API_URL:-http://localhost:18080/graphql}"
export PLEXUS_API_KEY="${PLEXUS_API_KEY:-local-smoke-key}"
export SMOKE_BROWSER_CHANNEL="${SMOKE_BROWSER_CHANNEL:-chrome}"
export SMOKE_BROWSER_OUT_DIR="${SMOKE_BROWSER_OUT_DIR:-$ROOT_DIR/tmp/local-control-plane-browser-smoke}"
export SMOKE_PROOF_DIR="${SMOKE_PROOF_DIR:-$ROOT_DIR/tmp/local-control-plane-proof}"
export SMOKE_PREDICTION_PROOF_FILE="${SMOKE_PREDICTION_PROOF_FILE:-$SMOKE_PROOF_DIR/prediction.json}"

log() {
  printf '[smoke-local-browser] %s\n' "$*"
}

ready_url="${PLEXUS_API_URL%/graphql}/readyz"
if ! curl -fsS "$ready_url" >/dev/null; then
  log "Local GraphQL proxy is not ready at $ready_url"
  exit 1
fi

if ! curl -fsS "$SMOKE_DASHBOARD_URL/lab/items/nira-demo-item-1" >/dev/null; then
  log "Dashboard is not reachable at $SMOKE_DASHBOARD_URL"
  exit 1
fi

if [[ ! -d "$DASHBOARD_DIR/node_modules/playwright" ]]; then
  log "Missing dashboard Playwright dependency. Run scripts/bootstrap-local-mvp.sh first."
  exit 1
fi

mkdir -p "$SMOKE_BROWSER_OUT_DIR"

(
  cd "$DASHBOARD_DIR"
  node <<'NODE'
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const baseUrl = process.env.SMOKE_DASHBOARD_URL || "http://localhost:3000";
const apiUrl = process.env.PLEXUS_API_URL || "http://localhost:18080/graphql";
const apiKey = process.env.PLEXUS_API_KEY || "local-smoke-key";
const outDir = process.env.SMOKE_BROWSER_OUT_DIR;
const browserChannel = process.env.SMOKE_BROWSER_CHANNEL || "chrome";
const predictionProofFile = process.env.SMOKE_PREDICTION_PROOF_FILE;
const allowedHosts = new Set([
  new URL(baseUrl).host,
  new URL(apiUrl).host,
  "localhost",
  "127.0.0.1",
  "[::1]",
]);

const forbiddenNetworkPatterns = [
  /amazonaws\.com/i,
  /appsync-api/i,
  /cognito/i,
  /amplifyapp\.com/i,
  /cloudfront\.net/i,
  /s3[.-][a-z0-9-]+\.amazonaws\.com/i,
];

const pageChecks = [
  {
    name: "nira-item",
    path: "/lab/items/nira-demo-item-1",
    requiredText: ["Demo User", "Local Demo", "Nira MVP prediction fixture transcript", "Nira Call Center QA"],
  },
  {
    name: "scorecards",
    path: "/lab/scorecards",
    requiredText: ["Demo User", "Local Demo", "Nira Call Center QA", "1 Score"],
  },
  {
    name: "evaluations",
    path: "/lab/evaluations",
    requiredText: ["Demo User", "Local Demo"],
  },
  {
    name: "reports",
    path: "/lab/reports",
    requiredText: ["Demo User", "Local Demo"],
  },
  {
    name: "procedures",
    path: "/lab/procedures",
    requiredText: ["Demo User", "Local Demo"],
  },
];

async function launchBrowser() {
  try {
    return await chromium.launch({ headless: true, channel: browserChannel });
  } catch (error) {
    if (browserChannel === "chromium") throw error;
    return await chromium.launch({ headless: true });
  }
}

async function postGraphql(query, variables = {}) {
  const response = await fetch(apiUrl, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": apiKey,
    },
    body: JSON.stringify({ query, variables }),
  });
  if (!response.ok) {
    throw new Error(`GraphQL HTTP ${response.status}`);
  }
  const body = await response.json();
  if (body.errors?.length) {
    throw new Error(`GraphQL errors: ${JSON.stringify(body.errors)}`);
  }
  return body.data;
}

function expectedScoreResultId() {
  if (process.env.SMOKE_SCORE_RESULT_ID) {
    return process.env.SMOKE_SCORE_RESULT_ID;
  }
  if (predictionProofFile && fs.existsSync(predictionProofFile)) {
    const proof = JSON.parse(fs.readFileSync(predictionProofFile, "utf8"));
    if (proof.scoreResultId) {
      return proof.scoreResultId;
    }
  }
  throw new Error(
    "No exact prediction ScoreResult ID found. Run scripts/smoke-local-predict.sh first or set SMOKE_SCORE_RESULT_ID.",
  );
}

async function assertPredictionReadback(scoreResultId) {
  const data = await postGraphql(`
    query BrowserSmokePredictionReadback($scoreResultId: ID!, $itemId: String!) {
      scoreResult: getScoreResult(id: $scoreResultId) {
        id
        itemId
        scorecardId
        scoreId
        scoreVersionId
        type
        status
      }
      byItem: listScoreResultByItemId(itemId: $itemId, limit: 25) {
        items {
          id
          itemId
          scoreId
          scoreVersionId
          type
          status
        }
        nextToken
      }
    }
  `, { scoreResultId, itemId: "nira-demo-item-1" });
  const scoreResult = data.scoreResult;
  if (!scoreResult) {
    throw new Error(`Prediction ScoreResult ${scoreResultId} was not found in local GraphQL.`);
  }
  if (
    scoreResult.id !== scoreResultId
    || scoreResult.itemId !== "nira-demo-item-1"
    || scoreResult.scorecardId !== "nira-demo-scorecard"
    || scoreResult.scoreId !== "nira-demo-score"
    || scoreResult.scoreVersionId !== "nira-demo-score-version"
    || scoreResult.type !== "prediction"
    || scoreResult.status !== "COMPLETED"
  ) {
    throw new Error(`Prediction ScoreResult ${scoreResultId} did not match the expected Nira proof shape.`);
  }
  const items = data.byItem?.items || [];
  const expected = items.find((item) => (
    item.id === scoreResultId
    && item.itemId === "nira-demo-item-1"
    && item.scoreId === "nira-demo-score"
    && item.scoreVersionId === "nira-demo-score-version"
    && item.type === "prediction"
  ));
  if (!expected) {
    throw new Error(`Prediction ScoreResult ${scoreResultId} was missing from listScoreResultByItemId readback.`);
  }
  return expected.id;
}

(async () => {
  const badRequests = [];
  const externalRequests = [];
  const consoleErrors = [];
  const browser = await launchBrowser();
  const page = await browser.newPage();

  page.on("request", (request) => {
    const url = request.url();
    if (forbiddenNetworkPatterns.some((pattern) => pattern.test(url))) {
      badRequests.push(url);
    }
    try {
      const parsedUrl = new URL(url);
      if (
        ["http:", "https:"].includes(parsedUrl.protocol)
        && !allowedHosts.has(parsedUrl.host)
      ) {
        externalRequests.push(url);
      }
    } catch (_error) {
      // Browser-internal URLs are irrelevant to hosted dependency checks.
    }
  });
  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text());
    }
  });

  try {
    const scoreResultId = await assertPredictionReadback(expectedScoreResultId());

    for (const check of pageChecks) {
      const url = `${baseUrl}${check.path}`;
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
      try {
        await page.waitForLoadState("networkidle", { timeout: 15000 });
      } catch (_error) {
        await page.waitForTimeout(2000);
      }

      const bodyText = await page.locator("body").innerText({ timeout: 10000 });
      if (/No account found/i.test(bodyText) || /^Error:/im.test(bodyText)) {
        throw new Error(`${check.path} rendered an account/error state`);
      }
      for (const text of check.requiredText) {
        if (!bodyText.includes(text)) {
          throw new Error(`${check.path} did not render required text: ${text}`);
        }
      }

      const screenshotPath = path.join(outDir, `${check.name}.png`);
      await page.screenshot({ path: screenshotPath, fullPage: true });
      console.log(`PASS ${check.path} screenshot=${screenshotPath}`);
    }

    if (badRequests.length) {
      throw new Error(`Local browser smoke made hosted AWS requests:\n${badRequests.join("\n")}`);
    }
    if (externalRequests.length) {
      throw new Error(`Local browser smoke made non-local hosted requests:\n${externalRequests.join("\n")}`);
    }

    console.log(`PASS prediction-readback scoreResultId=${scoreResultId}`);
    if (consoleErrors.length) {
      const uniqueConsoleErrors = Array.from(new Set(consoleErrors));
      throw new Error(
        `Local browser smoke observed console errors:\n${uniqueConsoleErrors.join("\n")}`,
      );
    }
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exit(1);
});
NODE
)
