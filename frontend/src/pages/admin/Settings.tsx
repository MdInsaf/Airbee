import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import { buildTenantSiteUrl } from "@/lib/site-hosts";

type BookingSiteSettings = {
  hero_title?: string;
  hero_subtitle?: string;
  support_email?: string;
  support_phone?: string;
  cta_label?: string;
};

type BookingTheme = {
  primary_color?: string;
  accent_color?: string;
  surface_style?: string;
};

type Tenant = {
  name: string;
  slug: string;
  subdomain: string | null;
  domain: string | null;
  primary_hostname: string | null;
  booking_site_enabled: boolean;
  domain_status: string | null;
  domain_verified_at?: string | null;
  domain_last_checked_at?: string | null;
  domain_last_error?: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  address: string | null;
  currency: string | null;
  timezone: string | null;
  logo_url: string | null;
  gst_enabled: boolean;
  gst_percentage: number;
  gst_number: string | null;
  service_charge_enabled: boolean;
  service_charge_percentage: number;
  settings?: {
    booking_site?: BookingSiteSettings;
  };
  booking_theme?: BookingTheme;
  domain_setup?: {
    provider?: string | null;
    platform_base_domain?: string | null;
    subdomain_fqdn?: string | null;
    platform_booking_url?: string | null;
    custom_domain_url?: string | null;
    preview_url?: string | null;
    cname_target?: string | null;
    status_message?: string | null;
    provider_status?: string | null;
    provider_update_status?: string | null;
    provider_branch?: string | null;
    provider_region?: string | null;
    dns_records?: Array<{
      label?: string | null;
      record_type?: string | null;
      record_name?: string | null;
      record_value?: string | null;
    }> | null;
    verification?: {
      record_type?: string | null;
      record_name?: string | null;
      record_value?: string | null;
    } | null;
  };
};

function parseApiError(error: unknown) {
  const fallback = error instanceof Error ? error.message : "Something went wrong";
  try {
    const parsed = JSON.parse(fallback);
    const conflictName =
      typeof parsed?.conflict?.name === "string" && parsed.conflict.name.trim()
        ? ` Conflicts with ${parsed.conflict.name}.`
        : "";

    return {
      message: `${parsed?.error || parsed?.message || fallback}${conflictName}`.trim(),
      tenant: parsed?.tenant as Tenant | undefined,
    };
  } catch {
    return { message: fallback, tenant: undefined };
  }
}

const Settings = () => {
  const { tenantId } = useAuth();
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [verifyingDomain, setVerifyingDomain] = useState(false);
  const [tenant, setTenant] = useState<Tenant | null>(null);

  useEffect(() => {
    if (!tenantId) return;
    api
      .get<{ tenant: Tenant }>("/api/settings")
      .then((data) => {
        setTenant(data.tenant);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Settings fetch error:", err);
        setLoading(false);
      });
  }, [tenantId]);

  const update = <K extends keyof Tenant>(field: K, value: Tenant[K]) =>
    setTenant((current) => (current ? { ...current, [field]: value } : current));

  const updateBookingSite = (field: keyof BookingSiteSettings, value: string) =>
    setTenant((current) =>
      current
        ? {
            ...current,
            settings: {
              ...current.settings,
              booking_site: {
                ...current.settings?.booking_site,
                [field]: value,
              },
            },
          }
        : current
    );

  const updateBookingTheme = (field: keyof BookingTheme, value: string) =>
    setTenant((current) =>
      current
        ? {
            ...current,
            booking_theme: {
              ...current.booking_theme,
              [field]: value,
            },
          }
        : current
    );

  const handleSave = async () => {
    if (!tenant) return;
    setSaving(true);
    try {
      const data = await api.put<{ tenant: Tenant; message?: string }>("/api/settings", {
        name: tenant.name,
        subdomain: tenant.subdomain,
        domain: tenant.domain,
        booking_site_enabled: tenant.booking_site_enabled,
        contact_email: tenant.contact_email,
        contact_phone: tenant.contact_phone,
        address: tenant.address,
        logo_url: tenant.logo_url,
        gst_enabled: tenant.gst_enabled,
        gst_percentage: tenant.gst_percentage,
        gst_number: tenant.gst_number,
        service_charge_enabled: tenant.service_charge_enabled,
        service_charge_percentage: tenant.service_charge_percentage,
        currency: tenant.currency,
        timezone: tenant.timezone,
        booking_site: tenant.settings?.booking_site || {},
        booking_theme: tenant.booking_theme || {},
      });
      setTenant(data.tenant);
      toast({ title: "Settings saved", description: data.message || undefined });
    } catch (err: any) {
      const parsed = parseApiError(err);
      if (parsed.tenant) setTenant(parsed.tenant);
      toast({ title: "Error", description: parsed.message, variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const handleVerifyDomain = async () => {
    if (!tenant?.domain) return;
    setVerifyingDomain(true);
    try {
      const data = await api.post<{ tenant: Tenant; message: string }>("/api/settings/domain/verify", {});
      setTenant(data.tenant);
      toast({ title: "Domain verified", description: data.message });
    } catch (err: any) {
      const parsed = parseApiError(err);
      if (parsed.tenant) setTenant(parsed.tenant);
      toast({
        title: "Verification pending",
        description: parsed.message,
        variant: "destructive",
      });
    } finally {
      setVerifyingDomain(false);
    }
  };

  if (loading) return <div className="animate-pulse text-muted-foreground">Loading settings...</div>;
  if (!tenant) return <div className="text-muted-foreground">Tenant settings unavailable.</div>;

  const bookingSite = tenant.settings?.booking_site || {};
  const bookingTheme = tenant.booking_theme || {};
  const bookingUrl =
    tenant.domain_setup?.preview_url || buildTenantSiteUrl(tenant.subdomain, tenant.domain, tenant.slug);
  const verification = tenant.domain_setup?.verification;
  const domainSetup = tenant.domain_setup;
  const dnsRecords =
    domainSetup?.dns_records ||
    (verification
      ? [
          {
            label: "Custom domain DNS record",
            record_type: verification.record_type,
            record_name: verification.record_name,
            record_value: verification.record_value,
          },
        ]
      : []);
  const verifyLabel = domainSetup?.provider === "amplify" ? "Sync Custom Domain" : "Verify Custom Domain";
  const dnsTitle = domainSetup?.provider === "amplify" ? "Amplify DNS Records" : "Custom Domain DNS Record";

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground mt-1">Configure your property and booking site</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Property Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Property Name</Label>
            <Input value={tenant.name || ""} onChange={(e) => update("name", e.target.value)} />
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Property Slug</Label>
              <Input value={tenant.slug || ""} readOnly />
            </div>
            <div className="space-y-2">
              <Label>Public Booking URL</Label>
              <Input value={bookingUrl} readOnly />
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Email</Label>
              <Input
                value={tenant.contact_email || ""}
                onChange={(e) => update("contact_email", e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Phone</Label>
              <Input
                value={tenant.contact_phone || ""}
                onChange={(e) => update("contact_phone", e.target.value)}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Address</Label>
            <Input value={tenant.address || ""} onChange={(e) => update("address", e.target.value)} />
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Currency</Label>
              <Input value={tenant.currency || "INR"} onChange={(e) => update("currency", e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Timezone</Label>
              <Input
                value={tenant.timezone || "Asia/Kolkata"}
                onChange={(e) => update("timezone", e.target.value)}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Booking Site</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-xl border p-4">
            <div>
              <p className="font-medium">Enable booking site</p>
              <p className="text-sm text-muted-foreground">
                Keep the public booking page live for this property.
              </p>
            </div>
            <Switch
              checked={tenant.booking_site_enabled}
              onCheckedChange={(value) => update("booking_site_enabled", value)}
            />
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Subdomain</Label>
              <Input
                value={tenant.subdomain || ""}
                onChange={(e) => update("subdomain", e.target.value.toLowerCase())}
                placeholder="grand-airbee"
              />
            </div>
            <div className="space-y-2">
              <Label>Custom Domain</Label>
              <Input
                value={tenant.domain || ""}
                onChange={(e) => update("domain", e.target.value.toLowerCase())}
                placeholder="stay.example.com"
              />
              {domainSetup?.provider === "amplify" ? (
                <p className="text-xs text-muted-foreground">
                  Clearing this field and saving will remove the previous Amplify custom domain mapping.
                </p>
              ) : null}
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Primary Hostname</Label>
              <Input value={tenant.primary_hostname || ""} readOnly />
            </div>
            <div className="space-y-2">
              <Label>Domain Status</Label>
              <Input value={tenant.domain_status || "none"} readOnly />
            </div>
          </div>
          <Alert>
            <AlertTitle>Domain setup</AlertTitle>
            <AlertDescription>
              {tenant.domain_setup?.status_message || "Use your platform subdomain or connect a custom domain."}
            </AlertDescription>
          </Alert>
          {domainSetup?.provider_status || domainSetup?.provider_update_status ? (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Provider Status</Label>
                <Input value={domainSetup.provider_status || "n/a"} readOnly />
              </div>
              <div className="space-y-2">
                <Label>Provider Update Status</Label>
                <Input value={domainSetup.provider_update_status || "n/a"} readOnly />
              </div>
            </div>
          ) : null}
          {tenant.domain_setup?.subdomain_fqdn ? (
            <div className="space-y-2">
              <Label>Platform Subdomain</Label>
              <Input value={tenant.domain_setup.subdomain_fqdn} readOnly />
            </div>
          ) : null}
          {dnsRecords.length ? (
            <div className="rounded-xl border bg-muted/30 p-4 space-y-4">
              <div>
                <p className="font-medium">{dnsTitle}</p>
                <p className="text-sm text-muted-foreground">
                  Add these records in your DNS provider and keep the status as pending until the platform validates them.
                </p>
              </div>
              {dnsRecords.map((record, index) => (
                <div key={`${record.label || "record"}-${index}`} className="space-y-3 rounded-lg border bg-background/70 p-3">
                  <p className="text-sm font-medium">{record.label || `DNS record ${index + 1}`}</p>
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                    <div className="space-y-2">
                      <Label>Type</Label>
                      <Input value={record.record_type || ""} readOnly />
                    </div>
                    <div className="space-y-2">
                      <Label>Name</Label>
                      <Input value={record.record_name || ""} readOnly />
                    </div>
                    <div className="space-y-2">
                      <Label>Target</Label>
                      <Input value={record.record_value || ""} readOnly />
                    </div>
                  </div>
                </div>
              ))}
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleVerifyDomain}
                  disabled={verifyingDomain || !tenant.domain}
                >
                  {verifyingDomain ? "Syncing..." : verifyLabel}
                </Button>
                <p className="text-xs text-muted-foreground">
                  Status: <span className="font-medium text-foreground">{tenant.domain_status || "none"}</span>
                </p>
              </div>
              {tenant.domain_last_checked_at ? (
                <p className="text-xs text-muted-foreground">
                  Last checked: {new Date(tenant.domain_last_checked_at).toLocaleString()}
                </p>
              ) : null}
              {tenant.domain_last_error ? (
                <Alert variant="destructive">
                  <AlertTitle>Latest verification error</AlertTitle>
                  <AlertDescription>{tenant.domain_last_error}</AlertDescription>
                </Alert>
              ) : null}
            </div>
          ) : tenant.domain ? (
            <Alert>
              <AlertTitle>Custom domain target not configured</AlertTitle>
              <AlertDescription>
                {domainSetup?.provider === "amplify"
                  ? "Set backend `AMPLIFY_APP_ID`, `AMPLIFY_BRANCH`, and `AMPLIFY_REGION` so the app can provision Amplify domain records."
                  : "Set backend `PUBLIC_CNAME_TARGET` so operators see the exact DNS record required for custom domains."}
              </AlertDescription>
            </Alert>
          ) : null}
          <div className="space-y-2">
            <Label>Logo URL</Label>
            <Input
              value={tenant.logo_url || ""}
              onChange={(e) => update("logo_url", e.target.value)}
              placeholder="https://cdn.example.com/logo.png"
            />
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Hero Title</Label>
              <Input
                value={bookingSite.hero_title || ""}
                onChange={(e) => updateBookingSite("hero_title", e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>CTA Label</Label>
              <Input
                value={bookingSite.cta_label || ""}
                onChange={(e) => updateBookingSite("cta_label", e.target.value)}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Hero Subtitle</Label>
            <Input
              value={bookingSite.hero_subtitle || ""}
              onChange={(e) => updateBookingSite("hero_subtitle", e.target.value)}
            />
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Support Email</Label>
              <Input
                value={bookingSite.support_email || ""}
                onChange={(e) => updateBookingSite("support_email", e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Support Phone</Label>
              <Input
                value={bookingSite.support_phone || ""}
                onChange={(e) => updateBookingSite("support_phone", e.target.value)}
              />
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <Label>Primary Color</Label>
              <Input
                value={bookingTheme.primary_color || ""}
                onChange={(e) => updateBookingTheme("primary_color", e.target.value)}
                placeholder="#f59e0b"
              />
            </div>
            <div className="space-y-2">
              <Label>Accent Color</Label>
              <Input
                value={bookingTheme.accent_color || ""}
                onChange={(e) => updateBookingTheme("accent_color", e.target.value)}
                placeholder="#111827"
              />
            </div>
            <div className="space-y-2">
              <Label>Surface Style</Label>
              <Input
                value={bookingTheme.surface_style || ""}
                onChange={(e) => updateBookingTheme("surface_style", e.target.value)}
                placeholder="warm"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Tax & Charges</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <Label>Enable GST</Label>
            <Switch checked={tenant.gst_enabled || false} onCheckedChange={(v) => update("gst_enabled", v)} />
          </div>
          {tenant.gst_enabled && (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>GST %</Label>
                <Input
                  type="number"
                  value={tenant.gst_percentage || 0}
                  onChange={(e) => update("gst_percentage", parseFloat(e.target.value || "0"))}
                />
              </div>
              <div className="space-y-2">
                <Label>GST Number</Label>
                <Input value={tenant.gst_number || ""} onChange={(e) => update("gst_number", e.target.value)} />
              </div>
            </div>
          )}
          <div className="flex items-center justify-between">
            <Label>Enable Service Charge</Label>
            <Switch
              checked={tenant.service_charge_enabled || false}
              onCheckedChange={(v) => update("service_charge_enabled", v)}
            />
          </div>
          {tenant.service_charge_enabled && (
            <div className="space-y-2">
              <Label>Service Charge %</Label>
              <Input
                type="number"
                value={tenant.service_charge_percentage || 0}
                onChange={(e) => update("service_charge_percentage", parseFloat(e.target.value || "0"))}
              />
            </div>
          )}
        </CardContent>
      </Card>

      <Button onClick={handleSave} disabled={saving}>
        {saving ? "Saving..." : "Save Settings"}
      </Button>
    </div>
  );
};

export default Settings;
