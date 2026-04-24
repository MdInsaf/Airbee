import { afterEach, describe, expect, it, vi } from "vitest";

import {
  buildTenantSiteUrl,
  getHostingMode,
  isPlatformHost,
  shouldRenderPublicBookingAtRoot,
  supportsPlatformRoutes,
} from "@/lib/site-hosts";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("site host helpers", () => {
  it("defaults to unified hosting mode", () => {
    expect(getHostingMode()).toBe("unified");
    expect(supportsPlatformRoutes()).toBe(true);
  });

  it("routes booking hosts to the public booking experience", () => {
    vi.stubEnv("VITE_APP_HOSTING_MODE", "unified");
    vi.stubEnv("VITE_PLATFORM_HOSTS", "app.airbee.test");

    expect(isPlatformHost("app.airbee.test")).toBe(true);
    expect(shouldRenderPublicBookingAtRoot("app.airbee.test")).toBe(false);
    expect(shouldRenderPublicBookingAtRoot("hotel.airbee.test")).toBe(true);
  });

  it("disables platform routes for booking-only builds", () => {
    vi.stubEnv("VITE_APP_HOSTING_MODE", "booking");

    expect(getHostingMode()).toBe("booking");
    expect(supportsPlatformRoutes()).toBe(false);
    expect(shouldRenderPublicBookingAtRoot("app.airbee.test")).toBe(true);
  });

  it("builds custom-domain and platform-subdomain booking URLs", () => {
    vi.stubEnv("VITE_PUBLIC_BASE_DOMAIN", "book.airbee.test");

    expect(buildTenantSiteUrl("coral", "stay.example.com", "fallback")).toBe(
      "https://stay.example.com"
    );
    expect(buildTenantSiteUrl("coral", null, "fallback")).toBe(
      "https://coral.book.airbee.test"
    );
  });
});
