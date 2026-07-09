/**
 * Custom server — required so the internal/external IP gate (src/lib/ip.ts) can trust
 * `x-forwarded-for`/`x-real-ip` only when they truly came from a trusted reverse proxy.
 *
 * Next's own request pipeline only fills these headers from the real TCP peer address
 * when the client didn't already send one (`req.headers['x-forwarded-for'] ??= socket.
 * remoteAddress`). From inside proxy.ts/route handlers there is no way to tell "Next
 * filled this from the real socket" apart from "the client sent us whatever they
 * wanted" — both look identical by the time application code reads the header. The
 * only place the real, unspoofable peer address is available is here, on the raw
 * `http.IncomingMessage`, before Next ever sees the request — so this is where
 * forwarded-IP headers must be sanitized (docs/MONITOR.md "외부 접속 인증 — 보안 전제").
 */
const { createServer } = require("node:http");
const { parse } = require("node:url");
const next = require("next");

const dev = process.env.NODE_ENV !== "production";
const hostname = process.env.HOSTNAME || "0.0.0.0";
const port = Number(process.env.PORT) || 3000;

const app = next({ dev, hostname, port });
const handle = app.getRequestHandler();

function normalizePeerAddress(address) {
  if (!address) return null;
  const mapped = /^::ffff:(\d+\.\d+\.\d+\.\d+)$/i.exec(address);
  return mapped ? mapped[1] : address;
}

function isLoopback(address) {
  return address === "::1" || address === "127.0.0.1" || address.startsWith("127.");
}

function ipv4ToLong(ip) {
  const parts = ip.split(".");
  if (parts.length !== 4) return null;
  let n = 0;
  for (const part of parts) {
    if (!/^\d{1,3}$/.test(part)) return null;
    const octet = Number(part);
    if (octet < 0 || octet > 255) return null;
    n = (n << 8) | octet;
  }
  return n >>> 0;
}

function isIpv4InCidr(ip, cidr) {
  const [range, bitsStr] = cidr.split("/");
  const bits = Number(bitsStr);
  const ipLong = ipv4ToLong(ip);
  const rangeLong = ipv4ToLong(range);
  if (ipLong === null || rangeLong === null || !Number.isInteger(bits) || bits < 0 || bits > 32) return false;
  if (bits === 0) return true;
  const mask = bits === 32 ? 0xffffffff : (~0 << (32 - bits)) >>> 0;
  return (ipLong & mask) === (rangeLong & mask);
}

function trustedProxyCidrs() {
  return (process.env.MONITOR_TRUSTED_PROXY_CIDRS ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

/**
 * True only for the loopback interface or an operator-configured reverse-proxy CIDR —
 * i.e. a party that could not have reached this process's socket without already being
 * trusted (the same machine, or the address of a proxy the operator explicitly named
 * via MONITOR_TRUSTED_PROXY_CIDRS). Everyone else's forwarded-IP headers are unverifiable.
 */
function isTrustedPeer(peerAddress) {
  if (isLoopback(peerAddress)) return true;
  return trustedProxyCidrs().some((cidr) => isIpv4InCidr(peerAddress, cidr));
}

function sanitizeForwardedHeaders(req) {
  const peer = normalizePeerAddress(req.socket.remoteAddress);
  if (peer && isTrustedPeer(peer)) return; // a trusted proxy is expected to set these correctly itself

  // The request reached us directly from an untrusted peer — whatever x-forwarded-for/
  // x-real-ip it sent cannot be verified, so it must not be treated as if a proxy had
  // set it. Overwrite with the real peer address so src/lib/ip.ts sees the true origin.
  if (peer) {
    req.headers["x-forwarded-for"] = peer;
    req.headers["x-real-ip"] = peer;
  } else {
    delete req.headers["x-forwarded-for"];
    delete req.headers["x-real-ip"];
  }
}

app.prepare().then(() => {
  createServer((req, res) => {
    sanitizeForwardedHeaders(req);
    handle(req, res, parse(req.url, true));
  })
    .listen(port, hostname, () => {
      console.log(`> Ready on http://${hostname}:${port}`);
    })
    .on("error", (err) => {
      console.error(err);
      process.exit(1);
    });
});
