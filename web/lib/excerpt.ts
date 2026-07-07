// Sanitized excerpt of the original posting, shown on hover.
//
// The privacy policy promises personal contact details are never published,
// so the excerpt is the poster's own words with mention tokens, emails, and
// phone numbers stripped deterministically — no rewriting.

const DISCORD_MENTION = /<@[!&]?\d+>/g; // <@123>, <@!123>, <@&role>
const DISCORD_CHANNEL = /<#\d+>/g;
const DISCORD_EMOJI = /<a?(:\w+:)\d+>/g; // <:name:123> -> :name:
const SLACK_MENTION = /<@[A-Z0-9]+>/g; // <@U12345>
const SLACK_CHANNEL = /<#[A-Z0-9]+(?:\|([^>]*))?>/g; // <#C1|general> -> #general
const SLACK_LINK = /<(https?:\/\/[^|>]+)(?:\|([^>]*))?>/g; // <url|label> -> label or url
const EMAIL = /[\w.+-]+@[\w-]+\.[\w.-]+/g;
// Phone-ish: 7+ digits allowing separators, with optional country code.
const PHONE = /(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)[\s.-]?)?\d{2,4}[\s.-]\d{2,4}[\s.-]\d{2,4}(?:[\s.-]\d{2,4})?|\+?\d{9,15}/g;

export function sanitizeExcerpt(raw: string, maxLen = 400): string {
  let text = raw
    .replace(SLACK_LINK, (_m, url, label) => label || url)
    .replace(DISCORD_EMOJI, "$1")
    .replace(DISCORD_MENTION, "")
    .replace(DISCORD_CHANNEL, "")
    .replace(SLACK_MENTION, "")
    .replace(SLACK_CHANNEL, (_m, name) => (name ? `#${name}` : ""))
    .replace(EMAIL, "[contact removed]")
    .replace(PHONE, (m) => (/\d{7,}/.test(m.replace(/\D/g, "")) ? "[contact removed]" : m));

  // Tidy: collapse runs of blank lines and intra-line whitespace.
  text = text
    .split("\n")
    .map((line) => line.replace(/[ \t]+/g, " ").trim())
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  if (text.length > maxLen) {
    const cut = text.slice(0, maxLen);
    text = cut.slice(0, Math.max(cut.lastIndexOf(" "), maxLen - 40)).trimEnd() + "…";
  }
  return text;
}
