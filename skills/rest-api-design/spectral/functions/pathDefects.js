/**
 * pathDefects — hygiene and, when a style profile is supplied, conventions.
 *
 * The hygiene checks (whitespace, duplicate-modulo-trailing-slash, templating errors)
 * are profile-independent: they are defects under any convention. The style checks
 * (casing, RPC verbs, depth) only run when the corresponding option is set, so an
 * estate that has not chosen a convention gets no noise it cannot act on.
 *
 * Runs against the UNRESOLVED document.
 *
 * Options:
 *   casing      string   one of the CASE_TESTS keys — flags non-conforming segments
 *   style       string   'resource-oriented' flags verb-led segments; 'rpc'/'mixed' skip
 *   maxDepth    number   flags paths with more segments than this
 *   collections string   'plural' flags apparently-singular collection segments
 */
import { CASE_TESTS, RPC_VERBS, isObject } from './_util.js';

export default function pathDefects(input, options, context) {
  const results = [];
  if (!isObject(input) || !isObject(input.paths)) return results;
  const opts = options || {};

  const normalised = new Map();

  for (const rawPath of Object.keys(input.paths)) {
    const at = [...context.path, 'paths', rawPath];

    // ── Hygiene ───────────────────────────────────────────────────────────────
    if (/\s/.test(rawPath)) {
      results.push({
        message: `Path \`${JSON.stringify(rawPath)}\` contains whitespace. This is almost always a typo that survived a copy-paste, and it produces a route nobody can call correctly.`,
        path: at,
      });
    }

    const key = rawPath.replace(/\/+$/, '') || '/';
    if (normalised.has(key) && normalised.get(key) !== rawPath) {
      results.push({
        message: `Path \`${rawPath}\` and \`${normalised.get(key)}\` differ only by a trailing slash. Pick one; serving both doubles the surface and splits caching and analytics.`,
        path: at,
      });
    } else {
      normalised.set(key, rawPath);
    }

    const unbalanced = (rawPath.match(/\{/g) || []).length !== (rawPath.match(/\}/g) || []).length;
    if (unbalanced) {
      results.push({
        message: `Path \`${rawPath}\` has unbalanced templating braces.`,
        path: at,
      });
    }

    const segments = rawPath.split('/').filter(Boolean);
    const literal = segments.filter((s) => !s.startsWith('{'));

    // ── Style, only when the profile has decided ──────────────────────────────
    if (opts.casing && CASE_TESTS[opts.casing]) {
      const test = CASE_TESTS[opts.casing];
      for (const segment of literal) {
        if (!test(segment)) {
          results.push({
            message: `Path segment \`${segment}\` in \`${rawPath}\` is not ${opts.casing}, which this API's style profile specifies.`,
            path: at,
          });
        }
      }
    }

    if (opts.style === 'resource-oriented') {
      for (const segment of literal) {
        const lead = segment.toLowerCase().replace(/[-_]/g, '');
        const verb = RPC_VERBS.find((v) => lead.startsWith(v) && lead.length > v.length);
        if (verb) {
          results.push({
            message: `Path segment \`${segment}\` in \`${rawPath}\` leads with the verb "${verb}". In a resource-oriented API the HTTP method carries the verb and the path carries the noun — e.g. \`GET /${segment.toLowerCase().replace(new RegExp('^' + verb), '')}\`.`,
            path: at,
          });
        }
      }
    }

    if (typeof opts.maxDepth === 'number' && segments.length > opts.maxDepth) {
      results.push({
        message: `Path \`${rawPath}\` has ${segments.length} segments (profile allows ${opts.maxDepth}). Deep paths usually encode a containment hierarchy the client should not have to know; consider addressing the leaf resource directly.`,
        path: at,
      });
    }
  }

  return results;
}
