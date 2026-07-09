/**
 * Canonical site origin, from SITE_URL. Never ship a plausible-but-wrong
 * URL: a misconfigured deploy gets a reserved .invalid host so the mistake
 * is visible in the output itself.
 */
export function getSiteUrl(): string {
  const configured = process.env.SITE_URL;
  if (!configured) {
    console.error("site-url: SITE_URL is not configured");
    return "https://site-url-not-configured.invalid";
  }
  return configured.replace(/\/$/, "");
}
