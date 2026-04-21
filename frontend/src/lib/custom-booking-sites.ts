import { coralBeachBookingSite } from "@/data/coralBeachBooking";

function normalizeHost(rawHost?: string | null) {
  return String(rawHost || "")
    .trim()
    .toLowerCase()
    .split(":")[0]
    .replace(/\.$/, "");
}

export type CustomBookingSite = "coral-beach" | null;

export function getCustomBookingSite(rawHost?: string | null): CustomBookingSite {
  const host = normalizeHost(rawHost);
  if (!host) return null;

  if (coralBeachBookingSite.hostnames.some((hostname) => normalizeHost(hostname) === host)) {
    return "coral-beach";
  }

  return null;
}

export function isCoralBeachBookingHost(rawHost?: string | null) {
  return getCustomBookingSite(rawHost) === "coral-beach";
}
