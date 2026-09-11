/**
 * proseConstraints — constraints stated in a description but not in the schema.
 *
 * A `description` saying "E.164 format (^\+[1-9]\d{1,14}$)" while the schema is a bare
 * `type: string` means the contract under-specifies what the server actually enforces.
 * Clients cannot validate ahead of the call, generated code has no constraint, and the
 * only way to learn the rule is to read prose — or to get a 400.
 *
 * This rule is heuristic and is deliberately `hint` severity. It will occasionally fire
 * on a description that merely mentions a format in passing. That is the accepted cost
 * of catching the far more common case.
 *
 * Runs against the UNRESOLVED document.
 *
 * Options: none.
 */
import { eachSchema, isObject } from './_util.js';

const SIGNALS = [
  { re: /\^.*\$/, missing: ['pattern'], what: 'a regular expression' },
  { re: /\be\.?164\b/i, missing: ['pattern'], what: 'the E.164 phone format' },
  { re: /\buuid\b/i, missing: ['format', 'pattern'], what: 'a UUID' },
  { re: /\bguid\b/i, missing: ['format', 'pattern'], what: 'a GUID' },
  { re: /\biso[- ]?8601\b/i, missing: ['format'], what: 'an ISO 8601 timestamp' },
  { re: /\bemail address\b/i, missing: ['format', 'pattern'], what: 'an email address' },
  { re: /\burl\b|\buri\b/i, missing: ['format', 'pattern'], what: 'a URL' },
  { re: /\b(?:max(?:imum)?|at most|no more than|up to)\s+\d+\s*(?:characters|chars)\b/i, missing: ['maxLength'], what: 'a maximum length' },
  { re: /\b(?:min(?:imum)?|at least)\s+\d+\s*(?:characters|chars)\b/i, missing: ['minLength'], what: 'a minimum length' },
  { re: /\bone of\b.*\b(?:,|or)\b/i, missing: ['enum', 'oneOf', 'anyOf'], what: 'a closed value set' },
  { re: /\bmust be (?:positive|greater than)\b/i, missing: ['minimum', 'exclusiveMinimum'], what: 'a lower bound' },
];

export default function proseConstraints(input, _options, context) {
  const results = [];
  if (!isObject(input)) return results;

  for (const { schema, path } of eachSchema(input)) {
    const description = schema.description;
    if (typeof description !== 'string' || description.length < 8) continue;
    if (schema.type === 'object' || isObject(schema.properties)) continue;

    for (const signal of SIGNALS) {
      if (!signal.re.test(description)) continue;
      if (signal.missing.some((k) => k in schema)) continue;

      results.push({
        message: `Description mentions ${signal.what} but the schema declares no \`${signal.missing.join('\`/\`')}\`. A constraint that lives only in prose cannot be validated by a client, enforced by a gateway, or generated into a type — move it into the schema.`,
        path: [...context.path, ...path, 'description'],
      });
      break;
    }
  }

  return results;
}
