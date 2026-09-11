/**
 * errorModel — conformance to the declared error representation.
 *
 * Which error model an API uses is a genuine choice (see references/03-errors.md).
 * Whether it uses that model consistently is not. This function only runs when a
 * profile has recorded the choice; without one it reports nothing.
 *
 * Runs against the RESOLVED document so that $ref'd error schemas are inspected.
 *
 * Options:
 *   model            'problem-details' | 'envelope' | 'bare'
 *   mediaType        string    expected media type for problem-details
 *   envelope         object    {dataField, errorsField, metaField}
 *   codeVocabulary   'closed' | 'open' | 'none'
 *   forbidMessagePassthrough boolean
 */
import { eachOperation, errorResponses, responseSchema, isObject } from './_util.js';

const PASSTHROUGH = /\b(?:exception|stack ?trace|ex\.message|raw error|internal error message)\b/i;

export default function errorModel(input, options, context) {
  const results = [];
  const opts = options || {};
  const model = opts.model;
  if (!model || model === 'bare') return results;

  const mediaType = opts.mediaType || 'application/problem+json';
  const envelope = isObject(opts.envelope) ? opts.envelope : {};
  const errorsField = envelope.errorsField || 'errors';
  const metaField = envelope.metaField || 'meta';

  for (const { path, method, operation } of eachOperation(input)) {
    for (const [code, response] of errorResponses(operation)) {
      const at = [...context.path, 'paths', path, method, 'responses', code];
      const label = `\`${method.toUpperCase()} ${path}\` → \`${code}\``;

      if (!isObject(response) || !isObject(response.content)) continue;
      const mediaTypes = Object.keys(response.content);

      if (model === 'problem-details') {
        if (!mediaTypes.includes(mediaType)) {
          results.push({
            message: `${label} returns \`${mediaTypes.join('`, `')}\` but this API's style profile specifies RFC 9457 \`${mediaType}\`. The distinct media type is what lets a client route an error body to a generic handler without inspecting the status code first.`,
            path: [...at, 'content'],
          });
          continue;
        }
        const found = responseSchema(response);
        if (found) {
          const props = collectProperties(found.schema);
          for (const required of ['type', 'title', 'status']) {
            if (!props.has(required)) {
              results.push({
                message: `${label} uses \`${mediaType}\` but its schema declares no \`${required}\`. RFC 9457 problem objects carry \`type\`, \`title\`, \`status\`, and optionally \`detail\` and \`instance\`.`,
                path: at,
              });
            }
          }
          checkCodeVocabulary(found.schema, props, opts, results, at, label);
        }
      }

      if (model === 'envelope') {
        const found = responseSchema(response);
        if (!found) continue;
        const props = collectProperties(found.schema);
        for (const field of [errorsField, metaField]) {
          if (!props.has(field)) {
            results.push({
              message: `${label} does not carry the \`${field}\` field this API's envelope model requires. An envelope that is only sometimes present is worse than none — consumers must then handle both shapes.`,
              path: at,
            });
          }
        }
        checkCodeVocabulary(found.schema, props, opts, results, at, label);
      }

      if (opts.forbidMessagePassthrough !== false) {
        const text = [response.description, JSON.stringify(response.content)].join(' ');
        if (PASSTHROUGH.test(text)) {
          results.push({
            message: `${label} appears to return raw exception text to the caller. That discloses internals, couples clients to implementation strings, and makes the message unusable as a stable contract. Return a code from a closed vocabulary and log the exception.`,
            path: at,
          });
        }
      }
    }
  }

  return results;
}

function checkCodeVocabulary(schema, props, opts, results, at, label) {
  if (opts.codeVocabulary !== 'closed') return;
  const codeSchema = findProperty(schema, 'code');
  if (!codeSchema) {
    results.push({
      message: `${label} declares no machine-readable \`code\`. This API's profile specifies a closed error vocabulary — without a code, clients must branch on human-readable messages.`,
      path: at,
    });
    return;
  }
  const hasEnum = Array.isArray(codeSchema.enum) && codeSchema.enum.length > 0;
  if (!hasEnum) {
    results.push({
      message: `${label} declares \`code\` as a free-form string. This API's profile specifies a closed vocabulary — declare the permitted values as an \`enum\` so clients can exhaustively handle them and so new codes are a visible contract change.`,
      path: at,
    });
  }
}

function collectProperties(schema, depth = 0, out = new Set()) {
  if (!isObject(schema) || depth > 4) return out;
  if (isObject(schema.properties)) {
    for (const key of Object.keys(schema.properties)) out.add(key);
  }
  for (const key of ['allOf', 'oneOf', 'anyOf']) {
    if (Array.isArray(schema[key])) {
      for (const member of schema[key]) collectProperties(member, depth + 1, out);
    }
  }
  return out;
}

function findProperty(schema, name, depth = 0) {
  if (!isObject(schema) || depth > 5) return null;
  if (isObject(schema.properties)) {
    if (isObject(schema.properties[name])) return schema.properties[name];
    for (const value of Object.values(schema.properties)) {
      if (isObject(value) && (isObject(value.items) || isObject(value.properties))) {
        const inner = findProperty(isObject(value.items) ? value.items : value, name, depth + 1);
        if (inner) return inner;
      }
    }
  }
  for (const key of ['allOf', 'oneOf', 'anyOf']) {
    if (Array.isArray(schema[key])) {
      for (const member of schema[key]) {
        const inner = findProperty(member, name, depth + 1);
        if (inner) return inner;
      }
    }
  }
  return null;
}
