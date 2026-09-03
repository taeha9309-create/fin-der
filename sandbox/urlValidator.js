const dns = require("dns").promises;
const ipaddr = require("ipaddr.js");

const blockedHostnames = new Set([
  "localhost",
  "localhost.localdomain",
]);

function isBlockedHostname(hostname) {
  return (
    blockedHostnames.has(hostname) ||
    hostname.endsWith(".localhost") ||
    hostname.endsWith(".local")
  );
}

function getTestAllowedHostname() {
  const hostname = process.env.SANDBOX_TEST_ALLOW_HOST?.trim().toLowerCase();

  if (
    !hostname ||
    hostname.length > 253 ||
    ipaddr.isValid(hostname) ||
    isBlockedHostname(hostname)
  ) {
    return null;
  }

  const labels = hostname.split(".");
  const isValidHostname = labels.every(
    (label) =>
      label.length > 0 &&
      label.length <= 63 &&
      /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(label),
  );

  return isValidHostname ? hostname : null;
}

function getAddressRange(address) {
  if (!ipaddr.isValid(address)) {
    return null;
  }

  let parsedAddress = ipaddr.parse(address);

  if (parsedAddress.kind() === "ipv6" && parsedAddress.isIPv4MappedAddress()) {
    parsedAddress = parsedAddress.toIPv4Address();
  }

  return parsedAddress.range();
}

function isBlockedAddress(address) {
  const range = getAddressRange(address);

  if (range === null) {
    return true;
  }

  const blockedRanges = new Set([
    "unspecified",
    "broadcast",
    "multicast",
    "linkLocal",
    "loopback",
    "private",
    "reserved",
    "uniqueLocal",
    "carrierGradeNat",
  ]);

  return blockedRanges.has(range);
}

function isPrivateAddress(address) {
  return new Set(["private", "uniqueLocal"]).has(getAddressRange(address));
}

async function validateUrl(input) {
  let parsedUrl;

  try {
    parsedUrl = new URL(input);
  } catch {
    const error = new Error("올바른 URL 형식이 아닙니다.");
    error.code = "INVALID_URL";
    throw error;
  }

  if (!["http:", "https:"].includes(parsedUrl.protocol)) {
    const error = new Error("HTTP 또는 HTTPS URL만 사용할 수 있습니다.");
    error.code = "UNSUPPORTED_PROTOCOL";
    throw error;
  }

  const hostname = parsedUrl.hostname.toLowerCase();
  const isTestAllowedHost = hostname === getTestAllowedHostname();

  if (isBlockedHostname(hostname)) {
    const error = new Error("내부 주소에는 접속할 수 없습니다.");
    error.code = "PRIVATE_ADDRESS_BLOCKED";
    throw error;
  }

  let addresses;

  try {
    addresses = await dns.lookup(hostname, {
      all: true,
      verbatim: true,
    });
  } catch {
    const error = new Error("도메인의 IP 주소를 확인할 수 없습니다.");
    error.code = "DNS_RESOLUTION_FAILED";
    throw error;
  }

  if (
    addresses.length === 0 ||
    addresses.some(
      ({ address }) =>
        isBlockedAddress(address) &&
        !(isTestAllowedHost && isPrivateAddress(address)),
    )
  ) {
    const error = new Error("내부 또는 비공개 IP 주소에는 접속할 수 없습니다.");
    error.code = "PRIVATE_ADDRESS_BLOCKED";
    throw error;
  }

  return parsedUrl.href;
}

module.exports = {
  validateUrl,
};
