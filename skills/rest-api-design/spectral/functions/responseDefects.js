/**
 * responseDefects — what an operation promises back.
 *
 * The single most common defect in an extracted spec is an operation that declares
 * `'200': description: ''` and nothing else. Such a contract asserts nothing: the
 * response shape lives only in the implementation, so nothing detects drift between
 * the code and the published document, and consumers are coupled to an undeclared shape.
 *
 * Runs against the UNRESOLVED document — we care about what the author declared.
 *
 * Options:
 *   checks            string[]  which checks to run. Defaults to every check except
 *                               `requiredStatuses`, which needs a profile to be meaningful.
 *                               Valid: successContent, errorDeclared, requiredStatuses,
 *                               descriptions, locationHeader, requiredProperties
 *   requiredStatuses  string[]  status codes every operation must declare
 */
import { eachOperation, successResponses, errorResponses, responseSchema, isObject } from './_util.js';

const NO_BODY = new Set(['204', '205', '304']);

const DEFAULT_CHECKS = [
  'successContent', 'errorDeclared', 'descriptions', 'locationHeader', 'requiredProperties',
];

export default function responseDefects(input, options, context) {
  const results = [];
  const opts = options || {};
  const checks = new Set(Array.isArray(opts.checks) ? opts.checks : DEFAULT_CHECKS);
  const required = Array.isArray(opts.requiredStatuses) ? opts.requiredStatuses : [];

  for (const { path, method, operation } of eachOperation(input)) {
    const base = [...context.path, 'paths', path, method];
    const label = `\`${method.toUpperCase()} ${path}\``;

    if (!isObject(operation.responses) || Object.keys(operation.responses).length === 0) {
      results.push({ message: `${label} declares no responses at all.`, path: base });
      continue;
    }

    const successes = successResponses(operation);

    // 1. Success response with no content/schema.
    if (checks.has('successContent')) {
      for (const [code, response] of successes) {
        if (NO_BODY.has(code) || !isObject(response)) continue;
        const rPath = [...base, 'responses', code];

        if (!isObject(response.content)) {
          results.push({
            message: `${label} → \`${code}\` declares no \`content\`. The response body is undocumented, so the contract cannot be generated from, tested against, or checked for drift.`,
            path: rPath,
          });
        } else if (!responseSchema(response)) {
          results.push({
            message: `${label} → \`${code}\` declares \`content\` but no \`schema\` under any media type.`,
            path: [...rPath, 'content'],
          });
        }
      }
    }

    // 2. No error responses declared at all.
    if (checks.has('errorDeclared') && errorResponses(operation).length === 0) {
      results.push({
        message: `${label} declares no 4xx or 5xx response. Every operation can fail; an undeclared failure mode is one the consumer cannot handle deliberately.`,
        path: [...base, 'responses'],
      });
    }

    // 3. Specific statuses the profile requires.
    if (checks.has('requiredStatuses')) {
      for (const code of required) {
        if (!(code in operation.responses)) {
          results.push({
            message: `${label} does not declare a \`${code}\` response, which this API's style profile requires.`,
            path: [...base, 'responses'],
          });
        }
      }
    }

    // 4. Empty descriptions — the portal-export fingerprint.
    if (checks.has('descriptions')) {
      for (const [code, response] of Object.entries(operation.responses)) {
        if (isObject(response) && typeof response.description === 'string' && response.description.trim() === '') {
          results.push({
            message: `${label} → \`${code}\` has an empty description. \`description\` is required by OpenAPI and is the only place the *meaning* of a status code is recorded.`,
            path: [...base, 'responses', code, 'description'],
          });
        }
      }
    }

    // 5. 201 without a Location header.
    if (checks.has('locationHeader') && '201' in operation.responses) {
      const created = operation.responses['201'];
      const headers = isObject(created) ? created.headers : null;
      const hasLocation = isObject(headers) && Object.keys(headers).some((h) => h.toLowerCase() === 'location');
      if (!hasLocation) {
        results.push({
          message: `${label} → \`201\` declares no \`Location\` header. A creation response should tell the client where the new resource lives.`,
          path: [...base, 'responses', '201'],
        });
      }
    }

    // 6. Success schemas with no `required` — every field optional by contract.
    if (checks.has('requiredProperties')) {
      for (const [code, response] of successes) {
        const found = responseSchema(response);
        if (!found) continue;
        const schema = found.schema;
        if (schema.type === 'object' && isObject(schema.properties) && !('required' in schema)) {
          results.push({
            message: `${label} → \`${code}\` response schema declares no \`required\` properties. Consumers must then treat every field as absent-possible, which is rarely what the implementation actually guarantees. Declare what the server always returns.`,
            path: [...base, 'responses', code],
          });
        }
      }
    }
  }

  return results;
}
