/**
 * securityDefects — identity, authorisation subject and personal data in the contract.
 *
 * Two failures dominate real estates, and both are visible in the document:
 *
 *   1. The client names the subject. A parameter or header like `customerId`,
 *      `x-account-id` or `identifier` tells the server who the request is about.
 *      Unless the server independently authorises that value against the credential,
 *      any caller can request anyone's data. Estates that do this rarely have the check.
 *
 *   2. Personal data of third parties in a subject-scoped response. If a response about
 *      *me* contains someone else's identifiers, the authorisation subject of that field
 *      differs from the authorisation subject of the operation. That is a decomposition
 *      problem as much as a privacy one — see references/09-decomposition.md.
 *
 * Runs against the RESOLVED document.
 *
 * Options:
 *   clientAssertedId  'forbidden' | 'allowed-with-authz-check' | 'allowed'
 *   subjectHeader     string    header the gateway injects, exempt from the above
 *   selfSegment       string    e.g. '/me' — marks an operation as subject-scoped
 *   sensitivePatterns string[]  property-name fragments treated as personal data
 *   masking           'response-level' | 'logging-only' | 'none'
 *   thirdPartyPii     'forbidden' | 'allowed-with-separate-authz' | 'allowed'
 */
import { eachOperation, successResponses, responseSchema, allParameters, isObject } from './_util.js';

const SUBJECT_NAMES = [
  'userid', 'user_id', 'customerid', 'customer_id', 'accountid', 'account_id',
  'contactid', 'contact_id', 'personid', 'person_id', 'memberid', 'member_id',
  'subjectid', 'subject_id', 'identifier', 'ssn', 'personalnumber', 'nationalid',
];

const DEFAULT_SENSITIVE = ['ssn', 'nationalid', 'personalnumber', 'dateofbirth', 'taxid'];

export default function securityDefects(input, options, context) {
  const results = [];
  const opts = options || {};
  const patterns = (Array.isArray(opts.sensitivePatterns) && opts.sensitivePatterns.length
    ? opts.sensitivePatterns
    : DEFAULT_SENSITIVE).map((p) => p.toLowerCase().replace(/[-_]/g, ''));
  const subjectHeader = (opts.subjectHeader || '').toLowerCase();
  const selfSegment = (opts.selfSegment || '/me').replace(/^\//, '').toLowerCase();

  for (const { path, method, operation, pathItem } of eachOperation(input)) {
    const at = [...context.path, 'paths', path, method];
    const label = `\`${method.toUpperCase()} ${path}\``;

    // ── 1. Client-asserted subject ────────────────────────────────────────────
    if (opts.clientAssertedId && opts.clientAssertedId !== 'allowed') {
      for (const param of allParameters(operation, pathItem)) {
        if (!['query', 'header'].includes(param.in)) continue;
        const name = String(param.name || '').toLowerCase().replace(/[-_]/g, '');
        if (subjectHeader && String(param.name || '').toLowerCase() === subjectHeader) continue;
        if (!SUBJECT_NAMES.map((n) => n.replace(/[-_]/g, '')).includes(name)) continue;

        const strict = opts.clientAssertedId === 'forbidden';
        results.push({
          message: strict
            ? `${label} lets the client name the subject via the \`${param.in}\` parameter \`${param.name}\`. This API's profile forbids client-asserted identity: the authorisation subject must come from the validated credential, otherwise any caller can request any subject's data.`
            : `${label} accepts a client-asserted subject via \`${param.name}\`. The profile permits this only with an explicit authorisation check — confirm the server verifies the caller is entitled to that subject, and document it here.`,
          path: at,
        });
      }
    }

    // ── 2. Personal data in responses ─────────────────────────────────────────
    const isSelfScoped = path.toLowerCase().split('/').filter(Boolean).includes(selfSegment);

    for (const [code, response] of successResponses(operation)) {
      const found = responseSchema(response);
      if (!found) continue;

      const hits = findSensitive(found.schema, patterns);
      if (hits.length === 0) continue;
      const rAt = [...at, 'responses', code];

      if (opts.masking === 'response-level') {
        const unmasked = hits.filter((h) => !mentionsMasking(h.schema));
        if (unmasked.length > 0) {
          results.push({
            message: `${label} → \`${code}\` returns ${unmasked.map((h) => `\`${h.name}\``).join(', ')} with no indication of masking. This API's profile requires response-level masking of personal identifiers — state the masking in the schema (pattern, example and description), so the contract records what is actually returned.`,
            path: rAt,
          });
        }
      }

      if (opts.thirdPartyPii === 'forbidden' && isSelfScoped) {
        const nested = hits.filter((h) => h.depth > 0);
        if (nested.length > 0) {
          results.push({
            message: `${label} is scoped to the caller (\`/${selfSegment}\`) but its response nests personal identifiers belonging to other parties: ${nested.map((h) => `\`${h.path}\``).join(', ')}. Those fields have a different authorisation subject from the operation. Move them behind a resource with its own authorisation — see references/09-decomposition.md, cohesion axis 3.`,
            path: rAt,
          });
        }
      }
    }
  }

  return results;
}

const MASK_HINT = /\bmask(?:ed|ing)?\b|\bredact(?:ed|ion)?\b|\bpartial(?:ly)?\b|\blast (?:four|4)\b|\*{2,}/i;

function mentionsMasking(schema) {
  if (!isObject(schema)) return false;
  const text = [schema.description, schema.example, schema.pattern].filter(Boolean).join(' ');
  return MASK_HINT.test(String(text));
}

function findSensitive(schema, patterns, depth = 0, prefix = '', seen = new WeakSet(), out = []) {
  if (!isObject(schema) || depth > 8) return out;
  if (seen.has(schema)) return out;
  seen.add(schema);

  for (const key of ['allOf', 'oneOf', 'anyOf']) {
    if (Array.isArray(schema[key])) {
      for (const member of schema[key]) findSensitive(member, patterns, depth, prefix, seen, out);
    }
  }

  const target = (schema.type === 'array' || isObject(schema.items)) ? schema.items : schema;
  if (target !== schema) {
    findSensitive(target, patterns, depth, prefix ? `${prefix}[]` : '[]', seen, out);
    return out;
  }

  if (!isObject(schema.properties)) return out;

  for (const [name, prop] of Object.entries(schema.properties)) {
    if (!isObject(prop)) continue;
    const flat = name.toLowerCase().replace(/[-_]/g, '');
    const dotted = prefix ? `${prefix}.${name}` : name;

    if (patterns.some((p) => flat.includes(p))) {
      out.push({ name, path: dotted, depth, schema: prop });
    }

    const inner = (prop.type === 'array' || isObject(prop.items)) ? prop.items : prop;
    if (isObject(inner) && (isObject(inner.properties) || ['allOf', 'oneOf', 'anyOf'].some((k) => Array.isArray(inner[k])))) {
      findSensitive(inner, patterns, depth + 1, dotted + (prop.type === 'array' ? '[]' : ''), seen, out);
    }
  }

  return out;
}
