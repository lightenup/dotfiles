/**
 * crossCuttingDefects — correlation, idempotency and version consistency.
 *
 * Three small profile-driven checks that share a shape, kept together because each is
 * a handful of lines and none is worth its own function file.
 *
 * Correlation. An id that is read and logged but never returned to the caller cannot
 * tie a client-side failure to a server-side log line, which is the only reason to
 * have one. The check is therefore on the *response* header, not the request.
 *
 * Idempotency. Any operation that is neither safe nor naturally idempotent needs a way
 * for the client to retry without double-effect. Without it, every network timeout
 * becomes a business decision.
 *
 * Version consistency. `info.version: "0.1"` alongside a `/v1` path is the usual sign
 * that the document version and the wire version have drifted apart and nobody is sure
 * which one clients are pinned to.
 *
 * Runs against the UNRESOLVED document.
 *
 * Options:
 *   correlationHeader   string
 *   correlationEcho     'required' | 'optional' | 'none'
 *   idempotencyScope    'unsafe-non-idempotent' | 'all-writes' | 'none'
 *   idempotencyHeader   string
 *   versionStrategy     'path' | 'header' | 'query' | 'media-type' | 'none'
 *   versionCurrent      string
 *   requireVersionMatch boolean
 */
import { eachOperation, allParameters, isObject } from './_util.js';

export default function crossCuttingDefects(input, options, context) {
  const results = [];
  const opts = options || {};

  // ── Version consistency ─────────────────────────────────────────────────────
  if (opts.versionStrategy === 'path' && opts.requireVersionMatch !== false && opts.versionCurrent) {
    const token = String(opts.versionCurrent);
    const infoVersion = isObject(input.info) ? String(input.info.version ?? '') : '';
    const major = infoVersion.split('.')[0];
    const tokenMajor = token.replace(/^v/i, '').split('.')[0];

    if (infoVersion && major !== tokenMajor) {
      results.push({
        message: `\`info.version\` is \`${infoVersion}\` but the wire version is \`${token}\`. Two version numbers that disagree leave nobody sure which one a client is pinned to — either align them, or state in the description that \`info.version\` tracks the document and \`${token}\` tracks the contract.`,
        path: [...context.path, 'info', 'version'],
      });
    }

    const inServer = Array.isArray(input.servers) &&
      input.servers.some((s) => isObject(s) && typeof s.url === 'string' && s.url.includes(`/${token}`));
    const inPaths = isObject(input.paths) &&
      Object.keys(input.paths).every((p) => p.split('/').filter(Boolean)[0] === token);

    if (!inServer && !inPaths && isObject(input.paths) && Object.keys(input.paths).length > 0) {
      results.push({
        message: `This API's profile specifies path versioning at \`${token}\`, but neither the \`servers\` URLs nor the paths carry it consistently. An unversioned path cannot be evolved without breaking its callers.`,
        path: [...context.path, 'paths'],
      });
    }
  }

  for (const { path, method, operation, pathItem } of eachOperation(input)) {
    const at = [...context.path, 'paths', path, method];
    const label = `\`${method.toUpperCase()} ${path}\``;

    // ── Correlation id echoed on responses ────────────────────────────────────
    if (opts.correlationEcho === 'required' && opts.correlationHeader && isObject(operation.responses)) {
      const header = opts.correlationHeader.toLowerCase();
      for (const [code, response] of Object.entries(operation.responses)) {
        if (!isObject(response)) continue;
        const declared = isObject(response.headers) &&
          Object.keys(response.headers).some((h) => h.toLowerCase() === header);
        if (!declared) {
          results.push({
            message: `${label} → \`${code}\` does not declare the \`${opts.correlationHeader}\` response header. A correlation id that is accepted and logged but never returned cannot tie a client-side failure to a server-side log line.`,
            path: [...at, 'responses', code],
          });
        }
      }
    }

    // ── Idempotency key on unsafe operations ──────────────────────────────────
    const scope = opts.idempotencyScope;
    const needsKey =
      (scope === 'unsafe-non-idempotent' && method === 'post') ||
      (scope === 'all-writes' && ['post', 'put', 'patch', 'delete'].includes(method));

    if (needsKey && opts.idempotencyHeader) {
      const header = opts.idempotencyHeader.toLowerCase();
      const present = allParameters(operation, pathItem)
        .some((p) => p.in === 'header' && String(p.name || '').toLowerCase() === header);
      if (!present) {
        results.push({
          message: `${label} declares no \`${opts.idempotencyHeader}\` header. Without one, a client that times out cannot distinguish "not applied" from "applied but the response was lost", so every retry risks a duplicate.`,
          path: at,
        });
      }
    }
  }

  return results;
}
