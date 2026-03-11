#!/usr/bin/env node
/**
 * generate-kit-structure.mjs — Scan .claude/ agents and skills, produce a
 * kits-format repository in <output-dir>.
 *
 * Usage: node scripts/generate-kit-structure.mjs <version> <output-dir>
 */

import { readFileSync, writeFileSync, mkdirSync, readdirSync, statSync, cpSync } from "node:fs";
import { join, basename, dirname, relative } from "node:path";

// ---------------------------------------------------------------------------
// CLI args
// ---------------------------------------------------------------------------
const [, , version, outputDir] = process.argv;
if (!version || !outputDir) {
  console.error("Usage: generate-kit-structure.mjs <version> <output-dir>");
  process.exit(1);
}

const REPO_ROOT = join(import.meta.dirname, "..");
const AGENTS_DIR = join(REPO_ROOT, ".claude", "agents");
const SKILLS_DIR = join(REPO_ROOT, ".claude", "skills");
const KIT_NAME = "terraform-agentic-workflows";
const TODAY = new Date().toISOString().slice(0, 10);

const SCHEMA_BASE =
  "https://raw.githubusercontent.com/hashicorp-labs/kits/refs/heads/main/schemas";

// ---------------------------------------------------------------------------
// Tool template mapping
// ---------------------------------------------------------------------------
const TOOL_MAP = {
  Read: "{{tool:read}}",
  Write: "{{tool:write}}",
  Edit: "{{tool:edit}}",
  Bash: "{{tool:shell}}",
  Glob: "{{tool:glob}}",
  Grep: "{{tool:grep}}",
  LS: "{{tool:glob}}",
  WebFetch: "{{tool:web-fetch}}",
  WebSearch: "{{tool:web-search}}",
  NotebookRead: "{{tool:read}}",
  TodoWrite: "{{tool:write}}",
  KillShell: "{{tool:shell}}",
  BashOutput: "{{tool:shell}}",
  Task: "{{tool:task}}",
};

// Model template mapping (from kits model-mapping.ts)
const MODEL_MAP = {
  opus: "{{model:power}}",
  sonnet: "{{model:standard}}",
  haiku: "{{model:fast}}",
};

// ---------------------------------------------------------------------------
// YAML frontmatter parser (minimal — avoids external deps)
// ---------------------------------------------------------------------------
function parseFrontmatter(content) {
  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!match) return { meta: {}, body: content };
  const body = content.slice(match[0].length).replace(/^\r?\n/, "");
  const meta = {};
  let currentKey = null;
  let currentList = null;

  for (const line of match[1].split("\n")) {
    // Array item
    const listItem = line.match(/^\s+-\s+(.+)$/);
    if (listItem && currentKey) {
      if (!currentList) currentList = [];
      currentList.push(stripQuotes(listItem[1].trim()));
      continue;
    }

    // Flush previous list
    if (currentList && currentKey) {
      meta[currentKey] = currentList;
      currentList = null;
    }

    // Key: value
    const kv = line.match(/^([a-zA-Z$_-]+):\s*(.*)$/);
    if (kv) {
      currentKey = kv[1];
      const val = kv[2].trim();
      if (val === "") {
        // Possible start of array or empty value
        currentList = null;
      } else if (val === "true") {
        meta[currentKey] = true;
      } else if (val === "false") {
        meta[currentKey] = false;
      } else {
        meta[currentKey] = stripQuotes(val);
        currentKey = null;
      }
    }
  }

  // Flush trailing list
  if (currentList && currentKey) {
    meta[currentKey] = currentList;
  }

  return { meta, body };
}

function stripQuotes(s) {
  if ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'"))) {
    return s.slice(1, -1);
  }
  return s;
}

// ---------------------------------------------------------------------------
// Transform tools list
// ---------------------------------------------------------------------------
function mapTools(tools) {
  if (!Array.isArray(tools)) return undefined;
  const mapped = tools.map((t) => TOOL_MAP[t] || t);
  return [...new Set(mapped)];
}

// ---------------------------------------------------------------------------
// Transform model
// ---------------------------------------------------------------------------
function mapModel(model) {
  if (!model) return undefined;
  return MODEL_MAP[model] || model;
}

// ---------------------------------------------------------------------------
// Validate and transform argumentHint
// Pattern must match: ^[<\[][A-Z_]+[>\]](\s+[<\[][A-Z_]+[>\]])*$
// ---------------------------------------------------------------------------
function transformArgumentHint(hint) {
  if (!hint) return undefined;
  // Try to extract bracketed tokens from the hint
  const tokens = hint.match(/[<\[][A-Za-z_-]+[>\]]/g);
  if (!tokens || tokens.length === 0) return undefined;
  // Normalise to uppercase and rebuild
  const normalized = tokens
    .map((t) => {
      const bracket = t[0] === "<" ? ["<", ">"] : ["[", "]"];
      const inner = t.slice(1, -1).toUpperCase().replace(/-/g, "_");
      return `${bracket[0]}${inner}${bracket[1]}`;
    })
    .join(" ");
  // Verify against the schema pattern and maxLength: 50
  const pattern = /^[<\[][A-Z_]+[>\]](\s+[<\[][A-Z_]+[>\]])*$/;
  if (!pattern.test(normalized) || normalized.length > 50) return undefined;
  return normalized;
}

// ---------------------------------------------------------------------------
// Truncate description to 200 chars
// ---------------------------------------------------------------------------
function truncDesc(desc) {
  if (!desc) return "No description provided";
  if (desc.length <= 200) return desc;
  return desc.slice(0, 197) + "...";
}

// ---------------------------------------------------------------------------
// Ensure name is valid kebab-case (3-50 chars, ^[a-z0-9]+(?:-[a-z0-9]+)*$)
// ---------------------------------------------------------------------------
function normalizeKebab(name) {
  return name.toLowerCase().replace(/[^a-z0-9-]/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
}

// ---------------------------------------------------------------------------
// Scan agents → subagent primitives
// ---------------------------------------------------------------------------
function scanAgents() {
  const primitives = [];
  let files;
  try {
    files = readdirSync(AGENTS_DIR);
  } catch (err) {
    console.error(`FATAL: Failed to read agents directory '${AGENTS_DIR}': ${err.message}`);
    process.exit(1);
  }
  for (const file of files) {
    if (!file.endsWith(".md")) continue;
    const fullPath = join(AGENTS_DIR, file);
    const stat = statSync(fullPath);
    if (stat.size <= 1) continue; // Skip empty consumer stubs

    const content = readFileSync(fullPath, "utf8");
    const { meta, body } = parseFrontmatter(content);
    if (!meta.name) {
      console.warn(`WARN: Agent '${file}' has no name in frontmatter — skipping`);
      continue;
    }

    const name = normalizeKebab(meta.name);
    const description = truncDesc(meta.description);
    const allowedTools = mapTools(meta.tools);
    const model = mapModel(meta.model);

    // Build schema-compliant frontmatter
    const fm = {
      $schema: `${SCHEMA_BASE}/subagent.schema.v1.0.0.json`,
      schemaVersion: "1.0.0",
      name,
      description,
    };
    if (allowedTools && allowedTools.length > 0) fm.allowedTools = allowedTools;
    if (model) fm.model = model;
    if (meta.color) fm.color = meta.color;
    if (Array.isArray(meta.skills) && meta.skills.length > 0) fm.skills = meta.skills;

    primitives.push({ name, description, frontmatter: fm, body });
  }
  return primitives;
}

// ---------------------------------------------------------------------------
// Scan skills → skill primitives
// ---------------------------------------------------------------------------
function scanSkills() {
  const primitives = [];
  let dirs;
  try {
    dirs = readdirSync(SKILLS_DIR);
  } catch (err) {
    console.error(`FATAL: Failed to read skills directory '${SKILLS_DIR}': ${err.message}`);
    process.exit(1);
  }
  for (const dir of dirs) {
    const skillDir = join(SKILLS_DIR, dir);
    const stat = statSync(skillDir);
    if (!stat.isDirectory()) continue;

    const skillFile = join(skillDir, "SKILL.md");
    let content;
    try {
      content = readFileSync(skillFile, "utf8");
    } catch (err) {
      if (err.code === "ENOENT") {
        console.warn(`WARN: Skill directory '${dir}' has no SKILL.md — skipping`);
        continue;
      }
      console.error(`FATAL: Failed to read '${skillFile}': ${err.message}`);
      process.exit(1);
    }

    const { meta, body } = parseFrontmatter(content);
    if (!meta.name) {
      console.warn(`WARN: Skill '${dir}' has no name in frontmatter — skipping`);
      continue;
    }

    const name = normalizeKebab(meta.name);
    const description = truncDesc(meta.description);

    // Build schema-compliant frontmatter
    const fm = {
      $schema: `${SCHEMA_BASE}/skill.schema.v1.0.0.json`,
      schemaVersion: "1.0.0",
      name,
      description,
    };

    // userInvocable (from user-invocable)
    if (meta["user-invocable"] === true) fm.userInvocable = true;

    // argumentHint (from argument-hint, validated against schema pattern)
    const argHint = transformArgumentHint(meta["argument-hint"]);
    if (argHint) fm.argumentHint = argHint;

    // allowedTools — skills may have them
    const allowedTools = mapTools(meta.tools || meta.allowedTools);
    if (allowedTools && allowedTools.length > 0) fm.allowedTools = allowedTools;

    // model
    const model = mapModel(meta.model);
    if (model) fm.model = model;

    // Collect subdirectories (references/, assets/, prompts/, template/)
    const subdirs = [];
    for (const entry of readdirSync(skillDir)) {
      const entryPath = join(skillDir, entry);
      if (statSync(entryPath).isDirectory()) {
        subdirs.push(entry);
      }
    }

    primitives.push({ name, description, frontmatter: fm, body, sourceDir: skillDir, subdirs });
  }
  return primitives;
}

// ---------------------------------------------------------------------------
// Serialize frontmatter to YAML (minimal, handles scalars, arrays, booleans)
// ---------------------------------------------------------------------------
function toYamlFrontmatter(obj) {
  const lines = [];
  for (const [key, value] of Object.entries(obj)) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) {
      lines.push(`${key}:`);
      for (const item of value) {
        lines.push(`  - ${quoteYaml(String(item))}`);
      }
    } else if (typeof value === "boolean") {
      lines.push(`${key}: ${value}`);
    } else {
      lines.push(`${key}: ${quoteYaml(String(value))}`);
    }
  }
  return lines.join("\n");
}

function quoteYaml(s) {
  // Quote if contains special chars or looks like it needs quoting
  if (/[:{}\[\],&*#?|\-><!%@`"']/.test(s) || s === "" || s === "true" || s === "false") {
    return `"${s.replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
  }
  return s;
}

// ---------------------------------------------------------------------------
// Write output structure
// ---------------------------------------------------------------------------
function writeKitStructure(agents, skills) {
  mkdirSync(outputDir, { recursive: true });

  // --- Write primitive files ---
  const primitivesRegistry = { skills: {}, subagents: {} };

  // Subagents
  for (const agent of agents) {
    const primDir = join(outputDir, "primitives", "subagents", agent.name, `v${version}`);
    mkdirSync(primDir, { recursive: true });
    const mdContent = `---\n${toYamlFrontmatter(agent.frontmatter)}\n---\n\n${agent.body}`;
    writeFileSync(join(primDir, `${agent.name}.md`), mdContent);

    primitivesRegistry.subagents[agent.name] = {
      description: agent.description,
      path: `primitives/subagents/${agent.name}`,
      versions: [
        {
          version,
          released: TODAY,
          changelog: `Release ${version}`,
          path: `v${version}`,
        },
      ],
      latest: version,
    };
  }

  // Skills
  for (const skill of skills) {
    const primDir = join(outputDir, "primitives", "skills", skill.name, `v${version}`);
    mkdirSync(primDir, { recursive: true });
    const mdContent = `---\n${toYamlFrontmatter(skill.frontmatter)}\n---\n\n${skill.body}`;
    writeFileSync(join(primDir, "SKILL.md"), mdContent);

    // Copy subdirectories
    for (const subdir of skill.subdirs) {
      const srcDir = join(skill.sourceDir, subdir);
      const destDir = join(primDir, subdir);
      cpSync(srcDir, destDir, { recursive: true });
    }

    primitivesRegistry.skills[skill.name] = {
      description: skill.description,
      path: `primitives/skills/${skill.name}`,
      versions: [
        {
          version,
          released: TODAY,
          changelog: `Release ${version}`,
          path: `v${version}`,
        },
      ],
      latest: version,
    };
  }

  // --- primitives-registry.json ---
  const primRegOut = {
    $schema: `${SCHEMA_BASE}/primitives-registry.schema.v1.0.0.json`,
    schemaVersion: "1.0.0",
    primitives: {},
  };
  if (Object.keys(primitivesRegistry.skills).length > 0) {
    primRegOut.primitives.skills = primitivesRegistry.skills;
  }
  if (Object.keys(primitivesRegistry.subagents).length > 0) {
    primRegOut.primitives.subagents = primitivesRegistry.subagents;
  }
  writeFileSync(join(outputDir, "primitives-registry.json"), JSON.stringify(primRegOut, null, 2) + "\n");

  // --- kit.json ---
  const kitDir = join(outputDir, "kits", KIT_NAME);
  mkdirSync(kitDir, { recursive: true });

  const kitPrimitives = {};
  // Only require "skills" — all harnesses support skills.
  // Subagents are optional: listed in primitives but not in requires,
  // so harnesses that don't support them (e.g. codex) skip gracefully.
  const requiresPrimitives = [];

  if (skills.length > 0) {
    requiresPrimitives.push("skills");
    kitPrimitives.skills = skills.map((s) => ({ ref: `${s.name}@${version}` }));
  }
  if (agents.length > 0) {
    kitPrimitives.subagents = agents.map((a) => ({ ref: `${a.name}@${version}` }));
  }

  const kitJson = {
    $schema: `${SCHEMA_BASE}/kit.schema.v1.0.0.json`,
    schemaVersion: "1.0.0",
    name: KIT_NAME,
    version,
    description: "Terraform module development agents and skills for SDD workflows",
    products: ["terraform"],
    requires: { primitives: requiresPrimitives },
    primitives: kitPrimitives,
  };
  writeFileSync(join(kitDir, "kit.json"), JSON.stringify(kitJson, null, 2) + "\n");

  // --- kits-registry.json ---
  const kitsRegistry = {
    $schema: `${SCHEMA_BASE}/kits-registry.schema.v1.0.0.json`,
    schemaVersion: "1.0.0",
    name: KIT_NAME,
    kits: [
      {
        name: KIT_NAME,
        path: `./kits/${KIT_NAME}`,
        version,
      },
    ],
  };
  writeFileSync(join(outputDir, "kits-registry.json"), JSON.stringify(kitsRegistry, null, 2) + "\n");

  return { agentCount: agents.length, skillCount: skills.length };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
const agents = scanAgents();
const skills = scanSkills();

if (skills.length === 0) {
  console.error("FATAL: No skills found in .claude/skills/ — kit requires at least one skill primitive");
  process.exit(1);
}

const { agentCount, skillCount } = writeKitStructure(agents, skills);

console.log(`Generated kit structure in ${outputDir}`);
console.log(`  Version:   ${version}`);
console.log(`  Subagents: ${agentCount}`);
console.log(`  Skills:    ${skillCount}`);
