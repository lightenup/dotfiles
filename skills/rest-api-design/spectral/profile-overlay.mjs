#!/usr/bin/env node
/**
 * profile-overlay.mjs — derive a Spectral ruleset from an api-style.yaml profile.
 *
 * The base ruleset checks what is a defect under any convention. This script adds the
 * rules that only make sense once a team has decided something: casing, versioning,
 * error model, pagination dialect, identity source, PII handling, webhook semantics.
 *
 * The derived ruleset is written to a file rather than composed in memory on purpose —
 * when a rule fires and someone disagrees, they need to be able to read exactly what
 * was checked and why. `lint-api.sh` prints its location.
 *
 * Usage:
 *   node profile-overlay.mjs --profile api-style.yaml --out /tmp/derived.yaml
 *
 * Exits 0 and writes a ruleset that simply extends base.yaml if no profile is found:
 * an estate with no recorded decisions should get no style findings.
 */

import { writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { resolve, dirname, isAbsolute } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const BASE = resolve(HERE, 'base.yaml');

// ── Argument parsing ─────────────────────────────────────────────────────────
const args = process.argv.slice(2);
const argOf = (name) => {
  const i = args.indexOf(name);
  return i >= 0 && i + 1 < args.length ? args[i + 1] : null;
};
const profilePath = argOf('--profile');
const outPath = argOf('--out') || resolve(HERE, '.derived-ruleset.yaml');

// ── YAML → JSON ──────────────────────────────────────────────────────────────
// Delegated to a real parser rather than hand-rolled. `yq` is preferred; PyYAML is the
// fallback. Both are common enough that requiring one is reasonable, and a subtly wrong
// profile parse would produce silently wrong lint rules — the worst possible failure
// mode for a tool whose output people are meant to act on.
function readProfile(path) {
  const attempts = [
    () => execFileSync('yq', ['-o=json', '.', path], { encoding: 'utf8' }),
    () => execFileSync('python3', [
      '-c',
      'import yaml,json,sys; json.dump(yaml.safe_load(open(sys.argv[1])), sys.stdout)',
      path,
    ], { encoding: 'utf8' }),
  ];

  for (const attempt of attempts) {
    try {
      return JSON.parse(attempt());
    } catch {
      // try the next parser
    }
  }

  throw new Error(
    'no YAML parser available — install yq (`brew install yq`) or PyYAML (`pip install pyyaml`)',
  );
}


// ── Ruleset generation ───────────────────────────────────────────────────────
const y = (v) => (typeof v === 'string' ? JSON.stringify(v) : String(v));
const list = (a) => `[${a.map((v) => y(v)).join(', ')}]`;

function buildRuleset(profile) {
  const rules = [];
  const functions = new Set();
  const get = (section, key, fallback) => {
    const s = profile[section];
    if (!s || typeof s !== 'object') return fallback;
    return s[key] === undefined || s[key] === null ? fallback : s[key];
  };

  // ── Paths: casing, resource orientation, depth ─────────────────────────────
  const casing = get('naming', 'paths', null);
  const routingStyle = get('routing', 'style', null);
  const maxPathDepth = get('routing', 'max-path-depth', null);

  if (casing || routingStyle === 'resource-oriented' || maxPathDepth) {
    functions.add('pathDefects');
    const opts = [];
    if (casing) opts.push(`        casing: ${y(casing)}`);
    if (routingStyle) opts.push(`        style: ${y(routingStyle)}`);
    if (maxPathDepth) opts.push(`        maxDepth: ${maxPathDepth}`);
    rules.push(rule('rad-path-style', {
      description: 'Path conventions this API recorded in its style profile.',
      severity: 'info',
      resolved: false,
      fn: 'pathDefects',
      options: opts,
    }));
  }

  // ── Errors ─────────────────────────────────────────────────────────────────
  const errorModelChoice = get('errors', 'model', null);
  if (errorModelChoice && errorModelChoice !== 'bare') {
    functions.add('errorModel');
    const opts = [`        model: ${y(errorModelChoice)}`];
    const mediaType = get('errors', 'media-type', null);
    if (mediaType) opts.push(`        mediaType: ${y(mediaType)}`);
    const vocabulary = get('errors', 'code-vocabulary', null);
    if (vocabulary) opts.push(`        codeVocabulary: ${y(vocabulary)}`);
    const passthrough = get('errors', 'forbid-message-passthrough', true);
    opts.push(`        forbidMessagePassthrough: ${passthrough}`);
    const env = profile.errors && profile.errors.envelope;
    if (env && typeof env === 'object') {
      opts.push('        envelope:');
      opts.push(`          dataField: ${y(env['data-field'] || 'data')}`);
      opts.push(`          errorsField: ${y(env['errors-field'] || 'errors')}`);
      opts.push(`          metaField: ${y(env['meta-field'] || 'meta')}`);
    }
    rules.push(rule('rad-error-model', {
      description: `Conformance to the ${errorModelChoice} error model this API recorded.`,
      severity: 'warn',
      resolved: true,
      fn: 'errorModel',
      options: opts,
    }));
  }

  // ── Statuses every operation must declare ──────────────────────────────────
  const requiredStatuses = get('errors', 'require-declared-statuses', null);
  if (Array.isArray(requiredStatuses) && requiredStatuses.length > 0) {
    functions.add('responseDefects');
    rules.push(rule('rad-required-statuses', {
      description: 'Status codes this API decided every operation must declare.',
      severity: 'warn',
      resolved: false,
      fn: 'responseDefects',
      options: [
        `        checks: ["requiredStatuses"]`,
        `        requiredStatuses: ${list(requiredStatuses.map(String))}`,
      ],
    }));
  }

  // ── Pagination dialect ─────────────────────────────────────────────────────
  const pageStyle = get('pagination', 'style', null);
  const pageParams = profile.pagination && profile.pagination.params;
  if (pageStyle && pageStyle !== 'none' && pageParams && typeof pageParams === 'object') {
    functions.add('paginationDefects');
    const names = Object.values(pageParams).filter((v) => typeof v === 'string');
    if (names.length > 0) {
      rules.push(rule('rad-pagination-style', {
        description: `Collections must use the ${pageStyle} pagination parameters this API recorded.`,
        severity: 'info',
        resolved: true,
        fn: 'paginationDefects',
        options: [
          `        style: ${y(pageStyle)}`,
          `        params: ${list(names)}`,
        ],
      }));
    }
  }

  // ── Identity and personal data ─────────────────────────────────────────────
  const clientAsserted = get('identity', 'client-asserted-id', null);
  const masking = get('pii', 'masking', null);
  const thirdParty = get('pii', 'third-party-pii', null);
  const sensitive = get('pii', 'sensitive-field-patterns', null);

  if (clientAsserted || masking || thirdParty) {
    functions.add('securityDefects');
    const opts = [];
    if (clientAsserted) opts.push(`        clientAssertedId: ${y(clientAsserted)}`);
    const subjectHeader = get('identity', 'subject-header', null);
    if (subjectHeader) opts.push(`        subjectHeader: ${y(subjectHeader)}`);
    const selfSegment = get('routing', 'singleton-self', '/me');
    if (selfSegment) opts.push(`        selfSegment: ${y(selfSegment)}`);
    if (masking) opts.push(`        masking: ${y(masking)}`);
    if (thirdParty) opts.push(`        thirdPartyPii: ${y(thirdParty)}`);
    if (Array.isArray(sensitive) && sensitive.length) {
      opts.push(`        sensitivePatterns: ${list(sensitive)}`);
    }
    rules.push(rule('rad-security', {
      description: 'Identity source and personal-data handling, as recorded in the style profile.',
      severity: 'error',
      resolved: true,
      fn: 'securityDefects',
      options: opts,
    }));
  }

  // ── Correlation, idempotency, versioning ───────────────────────────────────
  const correlationHeader = get('correlation', 'header', null);
  const correlationEcho = get('correlation', 'echo', null);
  const idempotencyScope = get('idempotency', 'scope', null);
  const idempotencyHeader = get('idempotency', 'header', null);
  const versionStrategy = get('versioning', 'strategy', null);
  const versionCurrent = get('versioning', 'current', null);

  const crossOpts = [];
  if (correlationHeader) crossOpts.push(`        correlationHeader: ${y(correlationHeader)}`);
  if (correlationEcho) crossOpts.push(`        correlationEcho: ${y(correlationEcho)}`);
  if (idempotencyScope) crossOpts.push(`        idempotencyScope: ${y(idempotencyScope)}`);
  if (idempotencyHeader) crossOpts.push(`        idempotencyHeader: ${y(idempotencyHeader)}`);
  if (versionStrategy) crossOpts.push(`        versionStrategy: ${y(versionStrategy)}`);
  if (versionCurrent) crossOpts.push(`        versionCurrent: ${y(versionCurrent)}`);
  const requireMatch = get('versioning', 'require-info-version-match', true);
  crossOpts.push(`        requireVersionMatch: ${requireMatch}`);

  if (crossOpts.length > 1) {
    functions.add('crossCuttingDefects');
    rules.push(rule('rad-cross-cutting', {
      description: 'Correlation, idempotency and version consistency, as recorded in the style profile.',
      severity: 'warn',
      // Resolved: shared $ref'd responses and parameters are the normal way to declare
      // correlation headers and idempotency keys, and must be seen through.
      resolved: true,
      fn: 'crossCuttingDefects',
      options: crossOpts,
    }));
  }

  // ── Webhooks ───────────────────────────────────────────────────────────────
  if (profile.webhooks && typeof profile.webhooks === 'object') {
    functions.add('webhookDefects');
    const opts = [];
    const map = {
      signature: 'signature',
      'signature-header': 'signatureHeader',
      'timestamp-header': 'timestampHeader',
      delivery: 'delivery',
      'payload-style': 'payloadStyle',
    };
    for (const [from, to] of Object.entries(map)) {
      const v = profile.webhooks[from];
      if (v !== undefined && v !== null) opts.push(`        ${to}: ${y(v)}`);
    }
    if (Array.isArray(sensitive) && sensitive.length) {
      opts.push(`        sensitivePatterns: ${list(sensitive)}`);
    }
    if (opts.length > 0) {
      rules.push(rule('rad-webhooks', {
        description: 'Webhook signing, deduplication and payload conventions.',
        severity: 'warn',
        resolved: true,
        fn: 'webhookDefects',
        options: opts,
      }));
    }
  }

  // ── Smell threshold overrides ──────────────────────────────────────────────
  const smells = profile.smells;
  if (smells && typeof smells === 'object') {
    functions.add('structuralSmells');
    const opts = [];
    if (smells['max-response-depth'] != null) opts.push(`        maxDepth: ${smells['max-response-depth']}`);
    if (smells['max-response-properties'] != null) opts.push(`        maxProperties: ${smells['max-response-properties']}`);
    if (smells['max-nullable-ratio'] != null) opts.push(`        maxNullableRatio: ${smells['max-nullable-ratio']}`);
    if (opts.length > 0) {
      rules.push(rule('rad-decomposition-smell', {
        description: 'Decomposition signals, using this API\'s configured thresholds.',
        severity: 'hint',
        resolved: true,
        fn: 'structuralSmells',
        options: opts,
      }));
    }
  }

  return { rules, functions: [...functions] };
}

function rule(name, { description, severity, resolved, fn, options }) {
  const lines = [
    `  ${name}:`,
    `    description: >-`,
    `      ${description}`,
    `    message: "{{error}}"`,
    `    severity: ${severity}`,
    `    given: "$"`,
    `    resolved: ${resolved}`,
    `    then:`,
    `      function: ${fn}`,
  ];
  if (options && options.length > 0) {
    lines.push('      functionOptions:');
    lines.push(...options);
  }
  return lines.join('\n');
}

// ── Main ─────────────────────────────────────────────────────────────────────
let profile = null;
let source = 'none';

if (profilePath) {
  const abs = isAbsolute(profilePath) ? profilePath : resolve(process.cwd(), profilePath);
  try {
    profile = readProfile(abs);
    source = abs;
  } catch (err) {
    console.error(`profile-overlay: could not read ${abs}: ${err.message}`);
    process.exit(1);
  }
}

const header = [
  '# GENERATED FILE — do not edit.',
  '#',
  `# Derived by profile-overlay.mjs from: ${source}`,
  `# Generated: ${new Date().toISOString()}`,
  '#',
  '# Style rules appear here only for decisions the profile actually records. An estate',
  '# that has not chosen a convention gets no findings it cannot act on.',
  '',
  'extends:',
  `  - ${JSON.stringify(BASE)}`,
  '',
];

if (!profile) {
  writeFileSync(outPath, header.concat([
    '# No style profile supplied — base rules only.',
    '',
  ]).join('\n'));
  console.error('profile-overlay: no profile supplied; emitted base rules only.');
  process.exit(0);
}

const { rules, functions } = buildRuleset(profile);

// `functionsDir` is written relative: Spectral resolves it against the directory holding
// this generated file, so the caller must place a `functions` symlink beside it.
// lint-api.sh does that; --out callers doing it by hand need to as well.
const body = [
  'functionsDir: "./functions"',
  '',
  'functions:',
  ...functions.map((f) => `  - ${f}`),
  '',
  'rules:',
  '',
  ...rules.map((r) => r + '\n'),
];

writeFileSync(outPath, header.concat(body).join('\n'));
console.error(`profile-overlay: ${rules.length} profile rule(s) derived from ${source}`);
