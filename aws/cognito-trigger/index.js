/**
 * Cognito PostConfirmation Lambda Trigger
 * Fires after a user confirms their email. Creates tenant + profile in RDS.
 *
 * Attach this to: Cognito User Pool → Triggers → Post confirmation
 * Env vars needed: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, COGNITO_USER_POOL_ID
 */

import pkg from "pg";
const { Pool } = pkg;
import {
  CognitoIdentityProviderClient,
  AdminUpdateUserAttributesCommand,
} from "@aws-sdk/client-cognito-identity-provider";

const pool = new Pool({
  host: process.env.DB_HOST,
  port: parseInt(process.env.DB_PORT || "5432"),
  database: process.env.DB_NAME,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  ssl: { rejectUnauthorized: false },
  max: 1,
});

const cognitoClient = new CognitoIdentityProviderClient({
  region: process.env.AWS_REGION || "us-east-1",
});

const RESERVED_SUBDOMAINS = new Set([
  "admin",
  "api",
  "app",
  "auth",
  "book",
  "booking",
  "dashboard",
  "docs",
  "help",
  "mail",
  "root",
  "settings",
  "support",
  "www",
]);

function sanitizeLabel(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/-{2,}/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 63);
}

function buildPrimaryHostname(subdomain, domain = "") {
  const customDomain = String(domain || "").trim().toLowerCase();
  if (customDomain) return customDomain;

  const baseDomain = String(process.env.PUBLIC_BASE_DOMAIN || "").trim().toLowerCase();
  if (subdomain && baseDomain) return `${subdomain}.${baseDomain}`;
  return subdomain || null;
}

async function generateUniqueSubdomain(client, fullName, suffix) {
  const base = sanitizeLabel(fullName) || "property";
  const trimmedBase = RESERVED_SUBDOMAINS.has(base) ? `${base}-hotel` : base;
  const candidates = [
    trimmedBase,
    `${trimmedBase}-${suffix}`,
    `${trimmedBase}-${suffix.slice(0, 4)}`,
  ];

  for (const candidate of candidates) {
    const normalized = sanitizeLabel(candidate);
    if (!normalized) continue;
    const candidateHost = buildPrimaryHostname(normalized) || normalized;
    const result = await client.query(
      `SELECT 1
       FROM tenants
       WHERE lower(subdomain) = lower($1)
          OR lower(COALESCE(domain, '')) = lower($2)
          OR lower(COALESCE(primary_hostname, '')) = lower($2)
       LIMIT 1`,
      [normalized, candidateHost]
    );
    if (result.rowCount === 0) return normalized;
  }

  return sanitizeLabel(`property-${suffix}`);
}

export const handler = async (event) => {
  const { userPoolId, userName, request } = event;
  const userAttributes = request.userAttributes;

  const cognitoSub = userAttributes.sub;
  const email = userAttributes.email;
  const fullName =
    userAttributes.name ||
    userAttributes["custom:full_name"] ||
    email.split("@")[0];

  const client = await pool.connect();
  try {
    await client.query("BEGIN");

    // Generate tenant slug
    const slugBase = sanitizeLabel(fullName) || "property";
    const slugSuffix = cognitoSub.substring(0, 8);
    const slug = `${slugBase}-${slugSuffix}`;
    const subdomain = await generateUniqueSubdomain(client, fullName, slugSuffix);
    const bookingTheme = {
      primary_color: "#f59e0b",
      accent_color: "#111827",
      surface_style: "warm",
    };
    const bookingSite = {
      hero_title: `${fullName}'s Property`,
      hero_subtitle: "Search live availability and accept direct bookings.",
      support_email: email,
      support_phone: "",
      cta_label: "Book your stay",
    };

    // Create tenant
    const tenantResult = await client.query(
      `INSERT INTO tenants (
         name, slug, subdomain, primary_hostname, booking_site_enabled,
         domain_status, settings, booking_theme, currency, timezone
       )
       VALUES ($1, $2, $3, $4, true, 'none', $5::jsonb, $6::jsonb, 'INR', 'Asia/Kolkata')
       RETURNING id`,
      [
        `${fullName}'s Property`,
        slug,
        subdomain,
        buildPrimaryHostname(subdomain),
        JSON.stringify({ booking_site: bookingSite }),
        JSON.stringify(bookingTheme),
      ]
    );
    const tenantId = tenantResult.rows[0].id;

    // Create profile
    await client.query(
      `INSERT INTO profiles (id, tenant_id, full_name)
       VALUES ($1, $2, $3)
       ON CONFLICT (id) DO UPDATE SET tenant_id = $2, full_name = $3`,
      [cognitoSub, tenantId, fullName]
    );

    // Create user role
    await client.query(
      `INSERT INTO user_roles (user_id, tenant_id, role)
       VALUES ($1, $2, 'owner')
       ON CONFLICT DO NOTHING`,
      [cognitoSub, tenantId]
    );

    // Create default room categories
    await client.query(
      `INSERT INTO room_categories (tenant_id, name, color, display_order) VALUES
        ($1, 'Standard', '#6B7280', 1),
        ($1, 'Deluxe',   '#3B82F6', 2),
        ($1, 'Suite',    '#8B5CF6', 3),
        ($1, 'Villa',    '#10B981', 4)`,
      [tenantId]
    );

    // Create default CMS pages
    await client.query(
      `INSERT INTO pages (tenant_id, slug, title, content_blocks, is_published) VALUES
        ($1, 'home',  'Home',     '[{"type":"hero","data":{"title":"Welcome","subtitle":"Experience comfort"}}]', true),
        ($1, 'about', 'About Us', '[{"type":"text","data":{"content":"Tell your story here."}}]', false)`,
      [tenantId]
    );

    await client.query("COMMIT");

    // Store tenant_id in Cognito custom attribute
    await cognitoClient.send(
      new AdminUpdateUserAttributesCommand({
        UserPoolId: userPoolId,
        Username: userName,
        UserAttributes: [
          { Name: "custom:tenant_id", Value: tenantId },
        ],
      })
    );

    console.log(`Provisioned tenant ${tenantId} for user ${cognitoSub}`);
  } catch (err) {
    await client.query("ROLLBACK");
    console.error("Error provisioning tenant:", err);
    throw err;
  } finally {
    client.release();
  }

  return event;
};
