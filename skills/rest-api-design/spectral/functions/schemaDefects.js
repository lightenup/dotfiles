/**
 * schemaDefects — structural defects in schema declarations.
 *
 * These are the fingerprints of a spec that was authored in a gateway portal UI
 * and exported, rather than written spec-first. None of them are style choices;
 * every one produces a schema that a code generator cannot use.
 *
 * Runs against the UNRESOLVED document so that $ref'd schemas are reported once,
 * at their definition site, rather than at every use.
 *
 * Options: none.
 */
import { eachSchema, VALID_TYPES, isObject } from './_util.js';

const PLACEHOLDER_ENUM = (e) =>
  Array.isArray(e) && e.length > 0 && e.every((v) => v === '' || v === null);

export default function schemaDefects(input, _options, context) {
  const results = [];
  if (!isObject(input)) return results;

  for (const { schema, path } of eachSchema(input)) {
    const abs = [...context.path, ...path];

    // 1. type: '' or an invented type name (GUID, Integer, Number, Date…).
    if ('type' in schema) {
      const t = schema.type;
      if (typeof t === 'string' && !VALID_TYPES.has(t)) {
        results.push({
          message: t === ''
            ? 'Schema declares `type: \'\'`, which is not a JSON Schema type. This is a gateway-portal placeholder — a code generator produces nothing usable from it.'
            : `Schema declares \`type: ${t}\`, which is not a JSON Schema type. Use one of ${[...VALID_TYPES].join(', ')} and express the refinement with \`format\` (e.g. \`type: string, format: uuid\`).`,
          path: [...abs, 'type'],
        });
      }
    }

    // 2. enum that only permits the empty string, or that is really an example.
    if ('enum' in schema) {
      if (PLACEHOLDER_ENUM(schema.enum)) {
        results.push({
          message: 'Enum permits only the empty string. This is a portal placeholder, not a constraint — either declare the real value set or remove the enum.',
          path: [...abs, 'enum'],
        });
      } else if (Array.isArray(schema.enum) && schema.enum.length === 1 && typeof schema.enum[0] === 'string' && schema.enum[0] !== '') {
        results.push({
          message: `Single-value enum \`[${JSON.stringify(schema.enum[0])}]\` is almost always an example that was pasted into the enum field. If it is genuinely the only permitted value, say so in the description; otherwise move it to \`example\`.`,
          path: [...abs, 'enum'],
        });
      }
    }

    // 3. array with no items — the element type is undocumented.
    if (schema.type === 'array' && !('items' in schema)) {
      results.push({
        message: 'Array schema declares no `items`. The element type is undocumented, so the contract says nothing about what the collection contains.',
        path: abs,
      });
    }

    // 4. object with no properties and no composition — an empty contract.
    if (schema.type === 'object') {
      const hasShape = ['properties', 'allOf', 'oneOf', 'anyOf', '$ref', 'additionalProperties', 'patternProperties']
        .some((k) => k in schema);
      if (!hasShape) {
        results.push({
          message: 'Schema is `type: object` with no properties and no composition. It asserts nothing. If the payload is genuinely free-form, say so with `additionalProperties: true` and explain why in the description.',
          path: abs,
        });
      }
    }

    // 5. nullable: true alongside null inside a type: string enum (OAS 3.0 ambiguity).
    if (Array.isArray(schema.enum) && schema.enum.includes(null) && schema.type && schema.type !== 'null') {
      results.push({
        message: `Enum contains \`null\` while \`type\` is \`${schema.type}\`. In OpenAPI 3.0 this is ambiguous — use \`nullable: true\` and leave \`null\` out of the enum. In 3.1 use \`type: [${schema.type}, 'null']\`.`,
        path: [...abs, 'enum'],
      });
    }

    // 6. A JSON Schema pasted into a type field: { type: { type: 'string' } }.
    if (isObject(schema.type)) {
      results.push({
        message: 'The `type` field holds an object rather than a type name — a JSON Schema was pasted into a schema editor. Replace with the type name.',
        path: [...abs, 'type'],
      });
    }
  }

  return results;
}
