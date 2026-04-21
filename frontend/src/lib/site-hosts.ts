function normalizeHost(rawHost?: string | null) {
  return String(rawHost || "")
    .trim()
    .toLowerCase()
    .replace(/\.$/, "");
}

export type HostingMode = "unified" | "platform" | "booking";

export function getHostingMode(): HostingMode {
  const mode = String(import.meta.env.VITE_APP_HOSTING_MODE || "unified").trim().toLowerCase();
  if (mode === "platform" || mode === "booking") {
    return mode;
  }
  return "unified";
}

function getExplicitPlatformHosts() {
  return new Set(
    String(import.meta.env.VITE_PLATFORM_HOSTS || "")
      .split(",")
      .map((value) => normalizeHost(value))
      .filter(Boolean)
  );
}

export function getCurrentHost() {
  if (typeof window === "undefined") return "";
  return normalizeHost(window.location.host);
}

export function isPlatformHost(rawHost?: string | null) {
  const host = normalizeHost(rawHost ?? getCurrentHost());
  if (!host) return true;

  const hostname = host.split(":")[0] || host;
  const defaults = new Set(["localhost", "localhost:8080", "127.0.0.1", "127.0.0.1:8080"]);
  const configured = getExplicitPlatformHosts();

  return defaults.has(host) || defaults.has(hostname) || configured.has(host) || configured.has(hostname);
}

export function shouldRenderPublicBookingAtRoot(rawHost?: string | null) {
  const mode = getHostingMode();
  if (mode === "booking") return true;
  if (mode === "platform") return false;
  return !isPlatformHost(rawHost);
}

export function supportsPlatformRoutes() {
  return getHostingMode() !== "booking";
}

export function getPublicBaseDomain() {
  const value = String(import.meta.env.VITE_PUBLIC_BASE_DOMAIN || "").trim().toLowerCase();
  return value || null;
}

export function buildTenantSiteUrl(
  subdomain?: string | null,
  domain?: string | null,
  fallbackSlug?: string | null
) {
  const customDomain = String(domain || "").trim().toLowerCase();
  if (customDomain) return `https://${customDomain}`;

  const baseDomain = getPublicBaseDomain();
  if (subdomain && baseDomain) return `https://${subdomain}.${baseDomain}`;

  if (typeof window !== "undefined" && fallbackSlug) {
    return `${window.location.origin}/book/${fallbackSlug}`;
  }

  return "";
}
