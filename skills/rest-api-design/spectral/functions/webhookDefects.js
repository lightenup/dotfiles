/**
 * webhookDefects — outbound callbacks as a contract.
 *
 * Webhooks are the part of an estate most often left undocumented, because the provider
 * thinks of them as "just a POST we make". They are an API: the consumer has to
 * authenticate them, deduplicate them, and cope with them arriving out of order.
 *
 * Inspects OpenAPI 3.1 `webhooks` and 3.0 operation `callbacks`.
 *
 * Runs against the RESOLVED document.
 *
 * Options:
 *   signature        'hmac-sha256' | 'jws' | 'mtls' | 'none'
 *   signatureHeader  string
 *   timestampHeader  string
 *   delivery         'at-least-once' | 'at-most-once'
 *   payloadStyle     'notification' | 'full-payload' | 'hybrid'
 *   sensitivePatterns string[]
 */
import { eachOperation, HTTP_METHODS, isObject } from './_util.js';


const DEFAULT_SENSITIVE = ['ssn', 'nationalid', 'personalnumber', 'dateofbirth', 'taxid'];

export default function webhookDefects(input, options, context) {
  const results = [];
  const opts = options || {};
  if (!opts.signature && !opts.delivery && !opts.payloadStyle) return results;

  const patterns = (Array.isArray(opts.sensitivePatterns) && opts.sensitivePatterns.length
    ? opts.sensitivePatterns
    : DEFAULT_SENSITIVE).map((p) => p.toLowerCase().replace(/[-_]/g, ''));

  for (const { name, operation, path } of eachWebhook(input, context)) {
    const label = `Webhook \`${name}\``;

    // ── Signature ─────────────────────────────────────────────────────────────
    if (opts.signature && opts.signature !== 'none' && opts.signatureHeader) {
      const headers = headerNames(operation);
      if (!headers.includes(opts.signatureHeader.toLowerCase())) {
        results.push({
          message: `${label} declares no \`${opts.signatureHeader}\` header. An unsigned callback is an unauthenticated write to the consumer — anyone who learns the endpoint can forge events.`,
          path,
        });
      }
      if (opts.signature === 'hmac-sha256' && opts.timestampHeader &&
          !headers.includes(opts.timestampHeader.toLowerCase())) {
        results.push({
          message: `${label} is HMAC-signed but declares no \`${opts.timestampHeader}\`. Without a signed timestamp the signature is replayable indefinitely — a captured delivery can be resent at any time and still verify.`,
          path,
        });
      }
    }

    // ── At-least-once delivery implies deduplication ──────────────────────────
    if (opts.delivery === 'at-least-once') {
      const props = bodyProperties(operation);
      const hasEventId = [...props].some((p) => /^(event)?id$|eventid|deliveryid|messageid/.test(p.toLowerCase().replace(/[-_]/g, '')));
      if (!hasEventId) {
        results.push({
          message: `${label} is delivered at-least-once but its payload carries no stable event id. The consumer cannot deduplicate, so every retry is indistinguishable from a genuine second event.`,
          path,
        });
      }
      const hasOrdering = [...props].some((p) => /sequence|occurredat|timestamp|version|revision/.test(p.toLowerCase().replace(/[-_]/g, '')));
      if (!hasOrdering) {
        results.push({
          message: `${label} carries no sequence number or occurrence timestamp. At-least-once delivery is also out-of-order delivery — without one the consumer cannot tell a stale event from a current one.`,
          path,
        });
      }
    }

    // ── Payload style ─────────────────────────────────────────────────────────
    if (opts.payloadStyle === 'notification') {
      const props = bodyProperties(operation);
      const sensitive = [...props].filter((p) =>
        patterns.some((pat) => p.toLowerCase().replace(/[-_]/g, '').includes(pat)));
      if (sensitive.length > 0) {
        results.push({
          message: `${label} carries personal data (${sensitive.map((s) => `\`${s}\``).join(', ')}) in the event body, but this API's profile specifies notification-style events. Notifications should carry an id and a link; the consumer then reads the resource over an authenticated, authorised channel. Event bodies are frequently persisted in consumer logs and queues.`,
          path,
        });
      }
    }
  }

  return results;
}

function* eachWebhook(input, context) {
  if (isObject(input.webhooks)) {
    for (const [name, item] of Object.entries(input.webhooks)) {
      if (!isObject(item)) continue;
      for (const method of HTTP_METHODS) {
        if (isObject(item[method])) {
          yield { name, operation: item[method], path: [...context.path, 'webhooks', name, method] };
        }
      }
    }
  }

  for (const { path: p, method: m, operation } of eachOperation(input)) {
    if (!isObject(operation.callbacks)) continue;
    for (const [cbName, cb] of Object.entries(operation.callbacks)) {
      if (!isObject(cb)) continue;
      for (const [expr, item] of Object.entries(cb)) {
        if (!isObject(item)) continue;
        for (const method of HTTP_METHODS) {
          if (isObject(item[method])) {
            yield {
              name: `${cbName} (${m.toUpperCase()} ${p})`,
              operation: item[method],
              path: [...context.path, 'paths', p, m, 'callbacks', cbName, expr, method],
            };
          }
        }
      }
    }
  }
}

function headerNames(operation) {
  const params = Array.isArray(operation.parameters) ? operation.parameters : [];
  return params
    .filter((p) => isObject(p) && p.in === 'header' && typeof p.name === 'string')
    .map((p) => p.name.toLowerCase());
}

function bodyProperties(operation) {
  const out = new Set();
  const content = operation?.requestBody?.content;
  if (!isObject(content)) return out;
  for (const media of Object.values(content)) {
    if (!isObject(media) || !isObject(media.schema)) continue;
    collect(media.schema, out, 0);
  }
  return out;
}

function collect(schema, out, depth) {
  if (!isObject(schema) || depth > 4) return;
  if (isObject(schema.properties)) {
    for (const [name, prop] of Object.entries(schema.properties)) {
      out.add(name);
      collect(isObject(prop?.items) ? prop.items : prop, out, depth + 1);
    }
  }
  for (const key of ['allOf', 'oneOf', 'anyOf']) {
    if (Array.isArray(schema[key])) for (const m of schema[key]) collect(m, out, depth + 1);
  }
  if (isObject(schema.items)) collect(schema.items, out, depth + 1);
}
