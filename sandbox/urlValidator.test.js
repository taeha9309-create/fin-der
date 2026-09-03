const assert = require("node:assert/strict");
const test = require("node:test");
const dns = require("dns").promises;
const { validateUrl } = require("./urlValidator");

const originalLookup = dns.lookup;
const originalAllowedHost = process.env.SANDBOX_TEST_ALLOW_HOST;

function resolveTo(address) {
  dns.lookup = async () => [{ address, family: address.includes(":") ? 6 : 4 }];
}

test.afterEach(() => {
  dns.lookup = originalLookup;

  if (originalAllowedHost === undefined) {
    delete process.env.SANDBOX_TEST_ALLOW_HOST;
  } else {
    process.env.SANDBOX_TEST_ALLOW_HOST = originalAllowedHost;
  }
});

test("blocks a private address by default", async () => {
  delete process.env.SANDBOX_TEST_ALLOW_HOST;
  resolveTo("192.168.1.20");

  await assert.rejects(validateUrl("http://test-page.example/"), {
    code: "PRIVATE_ADDRESS_BLOCKED",
  });
});

test("allows a private address only for the exact configured hostname", async () => {
  process.env.SANDBOX_TEST_ALLOW_HOST = "host.docker.internal";
  resolveTo("192.168.65.254");

  assert.equal(
    await validateUrl("http://host.docker.internal:9000/"),
    "http://host.docker.internal:9000/",
  );

  await assert.rejects(validateUrl("http://other.docker.internal:9000/"), {
    code: "PRIVATE_ADDRESS_BLOCKED",
  });
});

test("still blocks loopback resolution for the configured hostname", async () => {
  process.env.SANDBOX_TEST_ALLOW_HOST = "host.docker.internal";
  resolveTo("127.0.0.1");

  await assert.rejects(validateUrl("http://host.docker.internal:9000/"), {
    code: "PRIVATE_ADDRESS_BLOCKED",
  });
});

test("never allows localhost through the test exception", async () => {
  process.env.SANDBOX_TEST_ALLOW_HOST = "localhost";

  await assert.rejects(validateUrl("http://localhost:9000/"), {
    code: "PRIVATE_ADDRESS_BLOCKED",
  });
});

test("does not accept an IP address as the test hostname", async () => {
  process.env.SANDBOX_TEST_ALLOW_HOST = "127.0.0.1";
  resolveTo("127.0.0.1");

  await assert.rejects(validateUrl("http://127.0.0.1:9000/"), {
    code: "PRIVATE_ADDRESS_BLOCKED",
  });
});

test("does not accept a CIDR or wildcard test hostname", async () => {
  resolveTo("10.0.0.8");

  for (const configuredHost of ["10.0.0.0/8", "*.docker.internal"]) {
    process.env.SANDBOX_TEST_ALLOW_HOST = configuredHost;
    await assert.rejects(validateUrl("http://private.example/"), {
      code: "PRIVATE_ADDRESS_BLOCKED",
    });
  }
});

test("continues to allow a public address", async () => {
  delete process.env.SANDBOX_TEST_ALLOW_HOST;
  resolveTo("93.184.216.34");

  assert.equal(
    await validateUrl("https://example.com/"),
    "https://example.com/",
  );
});
