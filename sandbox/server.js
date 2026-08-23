const express = require("express");
const crypto = require("node:crypto");
const fs = require("node:fs/promises");
const path = require("node:path");
const { chromium } = require("playwright");
const { validateUrl } = require("./urlValidator");

const app = express();
const PORT = 3001;

const MAX_HTML_BYTES = 2 * 1024 * 1024;
const MAX_TEXT_BYTES = 1 * 1024 * 1024;
const MAX_SCREENSHOT_BYTES = 10 * 1024 * 1024;
const ANALYSIS_TIMEOUT_MS = 30000;
const ANALYSIS_STORAGE_DIR = process.env.ANALYSIS_STORAGE_DIR || "/data/analyses";
const ANALYSIS_RETENTION_HOURS = Number.parseInt(
  process.env.ANALYSIS_RETENTION_HOURS || "24",
  10
);
const CLEANUP_INTERVAL_MINUTES = Number.parseInt(
  process.env.CLEANUP_INTERVAL_MINUTES || "60",
  10
);
const ANALYSIS_DIRECTORY_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function logEvent(level, event, details = {}) {
  const entry = JSON.stringify({
    timestamp: new Date().toISOString(),
    level,
    service: "phishing-sandbox",
    event,
    ...details,
  });

  const writer = level === "ERROR" ? console.error : level === "WARN" ? console.warn : console.log;
  writer(entry);
}

function urlForLog(value) {
  try {
    const parsed = new URL(value);
    parsed.username = "";
    parsed.password = "";
    parsed.search = "";
    parsed.hash = "";
    return parsed.toString();
  } catch {
    return "INVALID_URL";
  }
}

function requirePositiveNumber(value, name) {
  if (!Number.isFinite(value) || value <= 0) {
    throw new Error(`${name}은(는) 0보다 큰 숫자여야 합니다.`);
  }

  return value;
}

const retentionMs =
  requirePositiveNumber(ANALYSIS_RETENTION_HOURS, "ANALYSIS_RETENTION_HOURS") *
  60 *
  60 *
  1000;
const cleanupIntervalMs =
  requirePositiveNumber(CLEANUP_INTERVAL_MINUTES, "CLEANUP_INTERVAL_MINUTES") *
  60 *
  1000;

async function cleanupExpiredAnalyses() {
  await fs.mkdir(ANALYSIS_STORAGE_DIR, { recursive: true });

  const storageRoot = path.resolve(ANALYSIS_STORAGE_DIR);
  const entries = await fs.readdir(storageRoot, { withFileTypes: true });
  const expiresBefore = Date.now() - retentionMs;
  let removedCount = 0;

  for (const entry of entries) {
    if (!entry.isDirectory() || !ANALYSIS_DIRECTORY_PATTERN.test(entry.name)) {
      continue;
    }

    const analysisDirectory = path.resolve(storageRoot, entry.name);

    if (!analysisDirectory.startsWith(`${storageRoot}${path.sep}`)) {
      continue;
    }

    try {
      const stats = await fs.stat(analysisDirectory);

      if (stats.mtimeMs < expiresBefore) {
        await fs.rm(analysisDirectory, { recursive: true, force: true });
        removedCount += 1;
      }
    } catch (error) {
      logEvent("WARN", "analysis_cleanup_failed", {
        analysisId: entry.name,
        errorName: error.name,
      });
    }
  }

  if (removedCount > 0) {
    logEvent("INFO", "analysis_cleanup_completed", { removedCount });
  }
}

app.use(express.json({ limit: "1mb" }));

app.get("/health", (req, res) => {
  res.json({
    status: "UP",
    service: "phishing-sandbox",
  });
});

app.post("/analyze", async (req, res) => {
  const { url } = req.body || {};
  const suppliedAnalysisId = req.body?.analysisId;
  const analysisId =
    typeof suppliedAnalysisId === "string" &&
    ANALYSIS_DIRECTORY_PATTERN.test(suppliedAnalysisId)
      ? suppliedAnalysisId
      : crypto.randomUUID();
  const startedAt = Date.now();

  if (suppliedAnalysisId != null && analysisId !== suppliedAnalysisId) {
    logEvent("WARN", "analysis_rejected", {
      analysisId,
      code: "INVALID_ANALYSIS_ID",
      durationMs: Date.now() - startedAt,
    });
    return res.status(400).json({
      analysisId,
      code: "INVALID_ANALYSIS_ID",
      message: "analysisId 형식이 올바르지 않습니다.",
    });
  }

  if (!url) {
    logEvent("WARN", "analysis_rejected", {
      analysisId,
      code: "URL_REQUIRED",
      durationMs: Date.now() - startedAt,
    });
    return res.status(400).json({
      analysisId,
      code: "URL_REQUIRED",
      message: "url을 입력해주세요.",
    });
  }

  let validatedUrl;

  try {
    validatedUrl = await validateUrl(url);
  } catch (error) {
    logEvent("WARN", "analysis_rejected", {
      analysisId,
      url: urlForLog(url),
      code: error.code || "URL_VALIDATION_FAILED",
      durationMs: Date.now() - startedAt,
    });
    return res.status(400).json({
      analysisId,
      code: error.code || "URL_VALIDATION_FAILED",
      message: error.message,
    });
  }

  let browser;
  let blockedRequestError = null;
  let analysisTimedOut = false;
  let analysisTimer = null;
  logEvent("INFO", "analysis_started", {
    analysisId,
    url: urlForLog(validatedUrl),
  });

  try {
    analysisTimer = setTimeout(() => {
      analysisTimedOut = true;

      if (browser) {
        browser.close().catch(() => {});
      }
    }, ANALYSIS_TIMEOUT_MS);
    browser = await chromium.launch({
      headless: true,
    });

    const context = await browser.newContext({
      viewport: {
        width: 1440,
        height: 900,
      },
      permissions: [],
      acceptDownloads: false,
      serviceWorkers: "block",
    });

    const validatedHosts = new Set();

    await context.route("**/*", async (route) => {
      const requestUrl = route.request().url();

      if (!requestUrl.startsWith("http://") && !requestUrl.startsWith("https://")) {
        return route.continue();
      }

      try {
        const hostname = new URL(requestUrl).hostname;

        if (!validatedHosts.has(hostname)) {
          await validateUrl(requestUrl);
          validatedHosts.add(hostname);
        }

        return route.continue();
      } catch (error) {
        blockedRequestError = error;
        logEvent("WARN", "network_request_blocked", {
          analysisId,
          url: urlForLog(requestUrl),
          code: error.code || "BLOCKED_NETWORK_REQUEST",
        });
        return route.abort("blockedbyclient");
      }
    });

    const page = await context.newPage();

    page.on("popup", async (popup) => {
      logEvent("WARN", "popup_blocked", {
        analysisId,
        url: urlForLog(popup.url()),
      });
      await popup.close().catch(() => {});
    });

    page.on("download", async (download) => {
      logEvent("WARN", "download_blocked", { analysisId });
      await download.cancel().catch(() => {});
    });

    page.on("dialog", async (dialog) => {
      logEvent("WARN", "dialog_blocked", {
        analysisId,
        dialogType: dialog.type(),
      });
      await dialog.dismiss().catch(() => {});
    });

    context.on("page", async (newPage) => {
      if (newPage !== page) {
        logEvent("WARN", "new_page_blocked", {
          analysisId,
          url: urlForLog(newPage.url()),
        });
        await newPage.close().catch(() => {});
      }
    });

    const response = await page.goto(validatedUrl, {
      waitUntil: "domcontentloaded",
      timeout: 15000,
    });

    const redirectChain = [];
    let navigationRequest = response?.request() ?? null;

    while (navigationRequest) {
      redirectChain.unshift(navigationRequest.url());
      navigationRequest = navigationRequest.redirectedFrom();
    }

    if (redirectChain.length === 0) {
      redirectChain.push(validatedUrl);
    }

    const finalUrl = page.url();

    if (redirectChain.at(-1) !== finalUrl) {
      redirectChain.push(finalUrl);
    }

    const html = await page.content();

    const htmlSize = Buffer.byteLength(html, "utf8");

    if (htmlSize > MAX_HTML_BYTES) {
      const error = new Error("HTML 크기가 2MB를 초과했습니다.");
      error.code = "HTML_TOO_LARGE";
      throw error;
    }

    let text = "";

    try {
      text = await page.locator("body").innerText({
        timeout: 5000,
      });
    } catch {
      text = "";
    }

    const normalizedText = text
      .replace(/\r\n/g, "\n")
      .replace(/[ \t]+/g, " ")
      .replace(/\n{3,}/g, "\n\n")
      .trim();

    const textSize = Buffer.byteLength(normalizedText, "utf8");

    if (textSize > MAX_TEXT_BYTES) {
      const error = new Error("페이지 Text 크기가 1MB를 초과했습니다.");
      error.code = "TEXT_TOO_LARGE";
      throw error;
    }

    const screenshot = await page.screenshot({
      fullPage: true,
      type: "png",
    });

    if (screenshot.length > MAX_SCREENSHOT_BYTES) {
      const error = new Error("스크린샷 크기가 10MB를 초과했습니다.");
      error.code = "SCREENSHOT_TOO_LARGE";
      throw error;
    }

    const analysisDirectory = path.join(ANALYSIS_STORAGE_DIR, analysisId);
    const htmlPath = path.join(analysisDirectory, "page.html");
    const textPath = path.join(analysisDirectory, "page.txt");
    const screenshotPath = path.join(analysisDirectory, "screenshot.png");
    const metadataPath = path.join(analysisDirectory, "metadata.json");

    await fs.mkdir(analysisDirectory, { recursive: true });
    await Promise.all([
      fs.writeFile(htmlPath, html, "utf8"),
      fs.writeFile(textPath, normalizedText, "utf8"),
      fs.writeFile(screenshotPath, screenshot),
      fs.writeFile(
        metadataPath,
        JSON.stringify(
          {
            analysisId,
            requestedUrl: validatedUrl,
            finalUrl,
            redirectChain,
            statusCode: response?.status() ?? null,
            title: await page.title(),
            htmlSizeBytes: htmlSize,
            textSizeBytes: textSize,
            screenshotSizeBytes: screenshot.length,
            createdAt: new Date().toISOString(),
          },
          null,
          2
        ),
        "utf8"
      ),
    ]);

    const loadTimeMs = Date.now() - startedAt;

    logEvent("INFO", "analysis_completed", {
      analysisId,
      finalUrl: urlForLog(finalUrl),
      statusCode: response?.status() ?? null,
      redirectCount: Math.max(redirectChain.length - 1, 0),
      loadTimeMs,
    });

    return res.json({
      analysisId,
      requestedUrl: validatedUrl,
      finalUrl,
      redirectChain,
      statusCode: response?.status() ?? null,
      title: await page.title(),
      html,
      htmlSizeBytes: htmlSize,
      text: normalizedText,
      textSizeBytes: textSize,
      screenshotBase64: screenshot.toString("base64"),
      screenshotSizeBytes: screenshot.length,
      htmlPath,
      textPath,
      screenshotPath,
      loadTimeMs,
      error: null,
    });
  } catch (error) {
    let status = 500;
    let code = "SANDBOX_ERROR";
    let message = "페이지 분석 중 내부 오류가 발생했습니다.";

    if (analysisTimedOut) {
      status = 504;
      code = "ANALYSIS_TIMEOUT";
      message = "전체 분석 제한 시간 30초를 초과했습니다.";
    } else if (blockedRequestError) {
      status = 400;
      code = blockedRequestError.code || "BLOCKED_NETWORK_REQUEST";
      message = blockedRequestError.message;
    } else if (
      error.code === "HTML_TOO_LARGE" ||
      error.code === "TEXT_TOO_LARGE" ||
      error.code === "SCREENSHOT_TOO_LARGE"
    ) {
      status = 413;
      code = error.code;
      message = error.message;
    } else if (error.name === "TimeoutError") {
      status = 504;
      code = "PAGE_LOAD_TIMEOUT";
      message = "페이지 로딩 제한 시간 15초를 초과했습니다.";
    }

    logEvent("ERROR", "analysis_failed", {
      analysisId,
      url: urlForLog(validatedUrl),
      code,
      status,
      durationMs: Date.now() - startedAt,
      errorName: error.name,
    });

    return res.status(status).json({ analysisId, code, message });
} finally {
    if (analysisTimer) {
      clearTimeout(analysisTimer);

    }
    if (browser) {
      await browser.close().catch(() => {});
    }
  }
});

app.use((error, req, res, next) => {
  if (res.headersSent) {
    return next(error);
  }

  const analysisId = crypto.randomUUID();
  const requestTooLarge = error.type === "entity.too.large";
  const invalidJson = error instanceof SyntaxError && "body" in error;
  const status = requestTooLarge ? 413 : invalidJson ? 400 : 500;
  const code = requestTooLarge
    ? "REQUEST_TOO_LARGE"
    : invalidJson
      ? "INVALID_JSON"
      : "SANDBOX_ERROR";
  const message = requestTooLarge
    ? "요청 본문 크기가 제한을 초과했습니다."
    : invalidJson
      ? "JSON 요청 형식이 올바르지 않습니다."
      : "요청 처리 중 내부 오류가 발생했습니다.";

  logEvent("ERROR", "request_failed", {
    analysisId,
    code,
    status,
    errorName: error.name,
  });

  return res.status(status).json({ analysisId, code, message });
});

async function startServer() {
  await cleanupExpiredAnalyses();

  const cleanupTimer = setInterval(() => {
    cleanupExpiredAnalyses().catch((error) => {
      console.error("분석 폴더 자동 정리 실패:", error.message);
    });
  }, cleanupIntervalMs);

  cleanupTimer.unref();

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Sandbox API 실행: http://localhost:${PORT}`);
    console.log(`분석 결과 보관 기간: ${ANALYSIS_RETENTION_HOURS}시간`);
  });
}

startServer().catch((error) => {
  console.error("Sandbox API 시작 실패:", error.message);
  process.exitCode = 1;
});
