/**
 * operationDefects — identity and self-description of operations.
 *
 * Duplicate or missing operationIds break client generation. A summary that
 * contradicts the description, or either that contradicts the path, is a reliable
 * signal that an operation has drifted from what it was originally written to do —
 * which matters when you are deciding whether it can be safely changed.
 *
 * Runs against the UNRESOLVED document.
 *
 * Options: none.
 */
import { eachOperation, isObject } from './_util.js';

export default function operationDefects(input, _options, context) {
  const results = [];
  const seen = new Map();

  for (const { path, method, operation } of eachOperation(input)) {
    const base = [...context.path, 'paths', path, method];

    if (!operation.operationId) {
      results.push({
        message: `\`${method.toUpperCase()} ${path}\` has no \`operationId\`. Generated clients fall back to a name derived from the path, which changes whenever the path does.`,
        path: base,
      });
    } else {
      const id = operation.operationId;
      if (seen.has(id)) {
        results.push({
          message: `\`operationId: ${id}\` is already used by \`${seen.get(id)}\`. operationIds must be unique within a document — and, if you publish several documents through one gateway, across them too.`,
          path: [...base, 'operationId'],
        });
      } else {
        seen.set(id, `${method.toUpperCase()} ${path}`);
      }
    }

    // Summary vs description contradiction: a cheap, surprisingly effective drift signal.
    const summary = typeof operation.summary === 'string' ? operation.summary : '';
    const description = typeof operation.description === 'string' ? operation.description : '';
    if (summary && description) {
      const s = normalise(summary);
      const d = normalise(description);
      if (s !== d && sharesStem(s, d) && byDifferentQualifier(s, d)) {
        results.push({
          message: `Summary ("${summary}") and description ("${description}") describe different lookups. One of them is stale — establish which before treating either as the contract.`,
          path: [...base, 'description'],
        });
      }
    }

    if (isObject(operation.requestBody) && ['get', 'delete', 'head'].includes(method)) {
      results.push({
        message: `\`${method.toUpperCase()} ${path}\` declares a request body. Bodies on ${method.toUpperCase()} have no defined semantics and are dropped by many intermediaries.`,
        path: [...base, 'requestBody'],
      });
    }
  }

  return results;
}

const normalise = (s) => s.toLowerCase().replace(/[^a-z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();

/** Do both strings talk about the same verb+noun, e.g. "get customer"? */
function sharesStem(a, b) {
  const wordsA = a.split(' ').slice(0, 2).join(' ');
  const wordsB = b.split(' ').slice(0, 2).join(' ');
  return wordsA === wordsB && wordsA.length > 0;
}

/** …but end on different qualifiers, e.g. "by id" vs "by ssn"? */
function byDifferentQualifier(a, b) {
  const qa = a.split(' by ')[1];
  const qb = b.split(' by ')[1];
  return Boolean(qa && qb && qa !== qb);
}
