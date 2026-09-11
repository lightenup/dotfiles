/**
 * paginationDefects — unbounded collections.
 *
 * A collection endpoint with no way to bound the result set is the most reliable
 * latency and cost defect in a REST estate. It works in test, where the fixture has
 * three rows, and degrades silently in production as data accumulates. Adding
 * pagination later is a breaking change for every consumer that assumed a full list.
 *
 * With no style profile the rule is permissive: any recognisable bounding parameter
 * satisfies it. With a profile it also checks that the API uses the parameters it said
 * it would, so one estate does not end up with three pagination dialects.
 *
 * MUST run against the RESOLVED document so that $ref'd array responses are seen.
 *
 * Options:
 *   params        string[]  parameter names that count as bounding (default: a generic set)
 *   strictParams  boolean   also flag bounding params outside `params` (default false)
 *   style         string    named style, used only in the message (default: none)
 */
import { eachOperation, successResponses, responseSchema, allParameters, isObject } from './_util.js';

const GENERIC = [
  'limit', 'top', '$top', 'pagesize', 'page_size', 'per_page', 'perpage', 'count',
  'cursor', 'offset', 'skip', '$skip', 'page', 'after', 'before',
  'continuationtoken', 'continuation_token', 'nexttoken', 'next_token',
];

export default function paginationDefects(input, options, context) {
  const results = [];
  const opts = options || {};
  const declared = Array.isArray(opts.params) && opts.params.length > 0
    ? opts.params.map((p) => p.toLowerCase())
    : null;
  const accepted = declared || GENERIC;

  for (const { path, method, operation, pathItem } of eachOperation(input)) {
    if (method !== 'get') continue;

    for (const [code, response] of successResponses(operation)) {
      const found = responseSchema(response);
      if (!found) continue;
      if (!returnsCollection(found.schema)) continue;

      const at = [...context.path, 'paths', path, method];
      const label = `\`${method.toUpperCase()} ${path}\` → \`${code}\``;
      const names = allParameters(operation, pathItem)
        .filter((p) => p.in === 'query' && typeof p.name === 'string')
        .map((p) => p.name.toLowerCase());

      const bounding = names.filter((n) => accepted.includes(n));

      if (bounding.length === 0) {
        const foreign = names.filter((n) => GENERIC.includes(n));
        if (declared && foreign.length > 0) {
          results.push({
            message: `${label} returns a collection bounded by \`${foreign.join('`, `')}\`, but this API's style profile specifies ${opts.style ? `${opts.style} pagination using ` : ''}\`${declared.join('`, `')}\`. Mixed pagination dialects in one estate force every client to special-case per endpoint.`,
            path: at,
          });
        } else {
          results.push({
            message: `${label} returns an unbounded collection — no \`limit\`, \`cursor\`, \`page\` or equivalent. Response size then grows with the data, and adding pagination later breaks every existing consumer.`,
            path: at,
          });
        }
      }
    }
  }

  return results;
}

/** Does this schema represent a collection — either a bare array or an obvious wrapper? */
function returnsCollection(schema, depth = 0) {
  if (!isObject(schema) || depth > 3) return false;
  if (schema.type === 'array' || isObject(schema.items)) return true;

  for (const key of ['allOf', 'oneOf', 'anyOf']) {
    if (Array.isArray(schema[key]) && schema[key].some((m) => returnsCollection(m, depth + 1))) {
      return true;
    }
  }

  // Envelope wrappers: {data: [...]}, {items: [...]}, {results: [...]}.
  if (isObject(schema.properties)) {
    for (const name of ['data', 'items', 'results', 'value', 'records', 'content']) {
      const prop = schema.properties[name];
      if (isObject(prop) && (prop.type === 'array' || isObject(prop.items))) return true;
    }
  }

  return false;
}
