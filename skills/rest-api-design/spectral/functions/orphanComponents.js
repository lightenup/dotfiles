/**
 * orphanComponents — components defined but never referenced.
 *
 * An orphaned schema is worse than no schema: it looks authoritative, it is often an
 * early approximation of a shape that later diverged, and readers reasonably assume
 * it describes something. Either wire it to the operation it belongs to, or delete it.
 *
 * MUST run against the UNRESOLVED document — the resolver replaces $refs, so on a
 * resolved document every component looks orphaned.
 *
 * Options: none.
 */
import { isObject } from './_util.js';

const REFERENCEABLE = [
  'schemas', 'responses', 'parameters', 'examples',
  'requestBodies', 'headers', 'links', 'callbacks',
];

export default function orphanComponents(input, _options, context) {
  const results = [];
  if (!isObject(input) || !isObject(input.components)) return results;

  const refs = new Set();
  collectRefs(input, refs);

  for (const bucket of REFERENCEABLE) {
    const group = input.components[bucket];
    if (!isObject(group)) continue;
    for (const name of Object.keys(group)) {
      const pointer = `#/components/${bucket}/${name}`;
      if (refs.has(pointer)) continue;
      // A schema can also be reached by composition from another schema that IS used;
      // collectRefs already sees those, so anything left really is unreferenced.
      results.push({
        message: `\`components.${bucket}.${name}\` is defined but never referenced. An unused component is usually a stale approximation of a shape that has since diverged — wire it up or remove it.`,
        path: [...context.path, 'components', bucket, name],
      });
    }
  }

  return results;
}

function collectRefs(node, out, seen = new WeakSet()) {
  if (!isObject(node) && !Array.isArray(node)) return;
  if (typeof node === 'object' && node !== null) {
    if (seen.has(node)) return;
    seen.add(node);
  }
  if (Array.isArray(node)) {
    for (const item of node) collectRefs(item, out, seen);
    return;
  }
  for (const [key, value] of Object.entries(node)) {
    if (key === '$ref' && typeof value === 'string') {
      out.add(value);
    } else {
      collectRefs(value, out, seen);
    }
  }
}
