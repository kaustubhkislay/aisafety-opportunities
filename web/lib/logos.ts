// Partner community logos, sourced from aisafety.com's communities directory
// (university Discord/Slack groups), converted to webp. A logo renders only
// when a community with a matching server/workspace name actually connects.
//
// Matching is alias-based because ingest attributes records by the exact
// Discord guild / Slack workspace name, which rarely matches the directory
// listing verbatim: each entry matches its full listed name, the name without
// the parenthetical, and the acronym — compared case- and punctuation-
// insensitively. Regenerated from the directory scrape; edit aliases freely.

interface LogoEntry {
  file: string;
  aliases: string[];
}

const LOGO_ENTRIES: LogoEntry[] = [
  { file: "/logos/university-of-bayes.webp", aliases: ["University of Bayes"] },
  { file: "/waisi-full.png", aliases: ["WAISI", "Wisconsin AI Safety Initiative", "Wisconsin AI Safety Initiative (WAISI)"] },
  { file: "/logos/ai-alignment-illinois.webp", aliases: ["AI Alignment @ Illinois"] },
  { file: "/logos/columbia-ai-alignment-club.webp", aliases: ["CAIAC", "Columbia AI Alignment Club", "Columbia AI Alignment Club (CAIAC)"] },
  { file: "/logos/toronto-ai-safety-initiative.webp", aliases: ["Toronto AI Safety Initiative"] },
  { file: "/logos/carnegie-mellon-ai-safety-initiative.webp", aliases: ["CASI", "Carnegie Mellon AI Safety Initiative", "Carnegie Mellon AI Safety Initiative (CASI)"] },
  { file: "/logos/ai-safety-at-ucsb.webp", aliases: ["AI Safety at UCSB"] },
  { file: "/logos/ai-security-and-risk-association-at-uf.webp", aliases: ["AI Security and Risk Association at UF", "AI Security and Risk Association at UF (AISRA)", "AISRA"] },
  { file: "/logos/virginia-ai-security-initiative.webp", aliases: ["VAISI", "Virginia AI Security Initiative", "Virginia AI Security Initiative (VAISI)"] },
  { file: "/logos/ai-safety-at-ucla.webp", aliases: ["AI Safety at UCLA"] },
  { file: "/logos/michigan-ai-safety-initiative.webp", aliases: ["MAISI", "Michigan AI Safety Initiative", "Michigan AI Safety Initiative (MAISI)"] },
  { file: "/logos/princeton-ai-alignment.webp", aliases: ["PAIA", "Princeton AI Alignment", "Princeton AI Alignment (PAIA)"] },
  { file: "/logos/uvic-ai.webp", aliases: ["UVic AI"] },
  { file: "/logos/stanford-ai-alignment.webp", aliases: ["SAIA", "Stanford AI Alignment", "Stanford AI Alignment (SAIA)"] },
  { file: "/logos/ai-safety-hub-edinburgh.webp", aliases: ["AI Safety Hub Edinburgh", "AI Safety Hub Edinburgh (AISHED)", "AISHED"] },
  { file: "/logos/antoan-ai.webp", aliases: ["AI Safety Vietnam", "AnTo\u00e0n.AI", "AnTo\u00e0n.AI (AI Safety Vietnam)"] },
  { file: "/logos/cornell-ai-alignment.webp", aliases: ["CAIA", "Cornell AI Alignment", "Cornell AI Alignment (CAIA)"] },
  { file: "/logos/hanoi-ai-safety-network.webp", aliases: ["HAISN", "Hanoi AI Safety Network", "Hanoi AI Safety Network (HAISN)"] },
  { file: "/logos/berkeley-ai-safety-initiative.webp", aliases: ["BASIS", "Berkeley AI Safety Initiative", "Berkeley AI Safety Initiative (BASIS)"] },
  { file: "/logos/yale-ai-policy-initiative.webp", aliases: ["YAIPI", "Yale AI Policy Initiative", "Yale AI Policy Initiative (YAIPI)"] },
  { file: "/logos/ai-alignment-mcgill.webp", aliases: ["AI Alignment McGill", "AI Alignment McGill (AIAM)", "AIAM"] },
  { file: "/logos/ubc-ai-safety.webp", aliases: ["UBC AI Safety"] },
  { file: "/logos/ai-safety-purdue.webp", aliases: ["AI Safety Purdue"] },
  { file: "/logos/austin-ai-alignment.webp", aliases: ["Austin AI Alignment"] },
  { file: "/logos/northwestern-ai-safety-and-governance.webp", aliases: ["NUAIS", "Northwestern AI Safety and Governance", "Northwestern AI Safety and Governance (NUAIS)"] },
  { file: "/logos/safeai-penn-labs.webp", aliases: ["SafeAI@Penn Labs"] },
  { file: "/logos/caltech-ai-alignment.webp", aliases: ["CAIA", "Caltech AI Alignment", "Caltech AI Alignment (CAIA)"] },
  { file: "/logos/yale-ai-alignment.webp", aliases: ["YAIA", "Yale AI Alignment", "Yale AI Alignment (YAIA)"] },
  { file: "/logos/ai-safety-bergen.webp", aliases: ["AI Safety Bergen"] },
];

function normalize(name: string): string {
  return name
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

const LOOKUP = new Map<string, string>();
for (const entry of LOGO_ENTRIES) {
  for (const alias of entry.aliases) {
    LOOKUP.set(normalize(alias), entry.file);
  }
}

/** Logo path for a connected community's server name, or null. */
export function logoFor(serverName: string): string | null {
  return LOOKUP.get(normalize(serverName)) ?? null;
}
