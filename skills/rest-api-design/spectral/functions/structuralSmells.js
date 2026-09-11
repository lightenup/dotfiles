/**
 * structuralSmells — the three decomposition signals.
 *
 * These do not prove a representation should be split. They cannot: whether two field
 * groups belong together is a question about the domain, the consumers and the
 * authorisation model, and none of that is in the document. What they do is tell you
 * where to point the procedure in references/09-decomposition.md.
 *
 * Reported at `hint` severity for exactly that reason. A hint here means "run the
 * cohesion analysis on this representation", not "this is wrong".
 *
 * MUST run against the RESOLVED document — depth and breadth are properties of the
 * representation the client actually receives, not of the document's $ref topology.
 *
 * Options:
 *   maxDepth          number  nested object levels below the root (default 3)
 *   maxProperties     number  total leaf properties in the representation (default 40)
 *   maxNullableRatio  number  fraction of properties marked nullable (default 0.6)
 */
import { eachOperation, successResponses, responseSchema, isObject } from './_util.js';

export default function structuralSmells(input, options, context) {
  const results = [];
  const opts = options || {};
  const maxDepth = typeof opts.maxDepth === 'number' ? opts.maxDepth : 3;
  const maxProperties = typeof opts.maxProperties === 'number' ? opts.maxProperties : 40;
  const maxNullableRatio = typeof opts.maxNullableRatio === 'number' ? opts.maxNullableRatio : 0.6;

  for (const { path, method, operation } of eachOperation(input)) {
    for (const [code, response] of successResponses(operation)) {
      const found = responseSchema(response);
      if (!found) continue;

      const at = [...context.path, 'paths', path, method, 'responses', code];
      const label = `\`${method.toUpperCase()} ${path}\` → \`${code}\``;
      const stats = analyse(found.schema);

      if (stats.depth > maxDepth) {
        results.push({
          message: `${label} nests ${stats.depth} object levels deep (threshold ${maxDepth}). Deep nesting means one read is serving several resources at once — the client pays for the whole tree whether it wants it or not. Run the cohesion analysis in references/09-decomposition.md before extending this shape.`,
          path: at,
        });
      }

      if (stats.leaves > maxProperties) {
        results.push({
          message: `${label} returns ${stats.leaves} leaf properties (threshold ${maxProperties}). A representation this broad is usually several resources that were never separated. Establish which consumer reads which field before changing it.`,
          path: at,
        });
      }

      if (stats.total >= 8 && stats.nullable / stats.total > maxNullableRatio) {
        const pct = Math.round((stats.nullable / stats.total) * 100);
        results.push({
          message: `${label} marks ${pct}% of its properties nullable (threshold ${Math.round(maxNullableRatio * 100)}%). Widespread nullability usually means one representation is serving several personas, each of which populates a different subset. Apply the nullability-by-persona test in references/09-decomposition.md.`,
          path: at,
        });
      }
    }
  }

  return results;
}

/**
 * depth  — nested object levels below the root. Arrays do not count as a level of
 *          their own; an array of objects sits at the same depth as the object.
 * leaves — scalar properties, counted through the whole tree.
 * total / nullable — properties at any level, and how many are explicitly nullable.
 */
function analyse(schema) {
  const state = { depth: 0, leaves: 0, total: 0, nullable: 0 };
  walk(schema, 0, state, new WeakSet());
  return state;
}

function walk(schema, depth, state, seen) {
  if (!isObject(schema)) return;
  if (seen.has(schema)) return;
  seen.add(schema);

  if (depth > state.depth) state.depth = depth;

  for (const key of ['allOf', 'oneOf', 'anyOf']) {
    if (Array.isArray(schema[key])) {
      for (const member of schema[key]) walk(member, depth, state, seen);
    }
  }

  if (schema.type === 'array' || isObject(schema.items)) {
    walk(schema.items, depth, state, seen);
    return;
  }

  if (!isObject(schema.properties)) return;

  for (const [, prop] of Object.entries(schema.properties)) {
    if (!isObject(prop)) continue;
    state.total += 1;
    if (prop.nullable === true || prop.type === 'null' ||
        (Array.isArray(prop.type) && prop.type.includes('null'))) {
      state.nullable += 1;
    }

    const inner = (prop.type === 'array' || isObject(prop.items)) ? prop.items : prop;
    const composed = ['allOf', 'oneOf', 'anyOf'].some((k) => Array.isArray(inner?.[k]));

    if (isObject(inner) && (isObject(inner.properties) || composed)) {
      walk(inner, depth + 1, state, seen);
    } else {
      state.leaves += 1;
    }
  }
}
