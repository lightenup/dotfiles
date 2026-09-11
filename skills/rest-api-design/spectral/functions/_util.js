/**
 * Shared helpers for the rest-api-design Spectral functions.
 *
 * Kept dependency-free on purpose: these are bundled by Spectral's ruleset bundler
 * when run through `npx @stoplight/spectral-cli`, and importing from
 * @stoplight/spectral-core would tie us to whatever version npx happens to resolve.
 */

export const HTTP_METHODS = [
  'get', 'put', 'post', 'delete', 'options', 'head', 'patch', 'trace',
];

/** JSON Schema types that are actually valid. Anything else is a portal artefact. */
export const VALID_TYPES = new Set([
  'string', 'number', 'integer', 'boolean', 'array', 'object', 'null',
]);

export const isObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);

/** Iterate the operations of an OpenAPI document: yields { path, method, operation }. */
export function* eachOperation(doc) {
  if (!isObject(doc) || !isObject(doc.paths)) return;
  for (const [path, item] of Object.entries(doc.paths)) {
    if (!isObject(item)) continue;
    for (const method of HTTP_METHODS) {
      if (isObject(item[method])) {
        yield { path, method, operation: item[method], pathItem: item };
      }
    }
  }
}

/** Keywords whose value is a single subschema. */
const SCHEMA_CHILD_KEYS = ['items', 'not', 'contains', 'propertyNames', 'additionalProperties'];
/** Keywords whose value is a map of name → subschema. */
const SCHEMA_MAP_KEYS = ['properties', 'patternProperties', 'definitions', '$defs'];
/** Keywords whose value is a list of subschemas. */
const SCHEMA_LIST_KEYS = ['allOf', 'oneOf', 'anyOf', 'prefixItems'];

/**
 * Walk every schema in an OpenAPI document, yielding { schema, path } with `path`
 * absolute within the document.
 *
 * Schema-aware rather than a generic object walk. A generic walk cannot tell a schema
 * from a map of schemas, so a property legitimately named `type`, `items` or `enum`
 * makes its containing `properties` map look like a schema. That produces confident,
 * wrong findings — the worst kind.
 *
 * Guards against the circular structures Spectral's resolver produces for
 * self-referencing $refs.
 */
export function* eachSchema(doc) {
  if (!isObject(doc)) return;
  const seen = new WeakSet();

  if (isObject(doc.components) && isObject(doc.components.schemas)) {
    for (const [name, schema] of Object.entries(doc.components.schemas)) {
      yield* walkSchema(schema, ['components', 'schemas', name], seen);
    }
  }

  for (const { schema, path } of findSchemaKeys(doc, [], null, new WeakSet())) {
    yield* walkSchema(schema, path, seen);
  }
}

/** Find every `schema:` keyword — parameters, media types, headers, encodings. */
function* findSchemaKeys(node, path, parentKey, visited) {
  if (!isObject(node) || visited.has(node)) return;
  visited.add(node);

  for (const [key, value] of Object.entries(node)) {
    if (!isObject(value) && !Array.isArray(value)) continue;

    if (Array.isArray(value)) {
      for (let i = 0; i < value.length; i++) {
        yield* findSchemaKeys(value[i], [...path, key, i], key, visited);
      }
      continue;
    }

    // A property legitimately named "schema" is not a schema keyword.
    if (key === 'schema' && parentKey !== 'properties') {
      yield { schema: value, path: [...path, key] };
      continue;
    }

    yield* findSchemaKeys(value, [...path, key], key, visited);
  }
}

function* walkSchema(schema, path, seen) {
  if (!isObject(schema) || seen.has(schema)) return;
  seen.add(schema);

  yield { schema, path };

  for (const key of SCHEMA_MAP_KEYS) {
    if (!isObject(schema[key])) continue;
    for (const [name, sub] of Object.entries(schema[key])) {
      yield* walkSchema(sub, [...path, key, name], seen);
    }
  }

  for (const key of SCHEMA_LIST_KEYS) {
    if (!Array.isArray(schema[key])) continue;
    for (let i = 0; i < schema[key].length; i++) {
      yield* walkSchema(schema[key][i], [...path, key, i], seen);
    }
  }

  for (const key of SCHEMA_CHILD_KEYS) {
    const value = schema[key];
    if (Array.isArray(value)) {
      for (let i = 0; i < value.length; i++) {
        yield* walkSchema(value[i], [...path, key, i], seen);
      }
    } else if (isObject(value)) {
      yield* walkSchema(value, [...path, key], seen);
    }
  }
}

/** The 2xx responses of an operation, as [statusCode, responseObject] pairs. */
export function successResponses(operation) {
  if (!isObject(operation) || !isObject(operation.responses)) return [];
  return Object.entries(operation.responses).filter(
    ([code]) => /^2\d\d$/.test(code) || code === '2XX',
  );
}

/** The non-2xx responses of an operation, as [statusCode, responseObject] pairs. */
export function errorResponses(operation) {
  if (!isObject(operation) || !isObject(operation.responses)) return [];
  return Object.entries(operation.responses).filter(
    ([code]) => /^[45]\d\d$/.test(code) || code === '4XX' || code === '5XX',
  );
}

/** First response schema found for a response object, with its media type. */
export function responseSchema(response) {
  if (!isObject(response) || !isObject(response.content)) return null;
  for (const [mediaType, media] of Object.entries(response.content)) {
    if (isObject(media) && isObject(media.schema)) {
      return { mediaType, schema: media.schema };
    }
  }
  return null;
}

/** All parameters visible to an operation (its own plus the path item's). */
export function allParameters(operation, pathItem) {
  const own = Array.isArray(operation?.parameters) ? operation.parameters : [];
  const shared = Array.isArray(pathItem?.parameters) ? pathItem.parameters : [];
  return [...shared, ...own].filter(isObject);
}

/** Unwrap allOf/oneOf/anyOf into the list of member schemas, plus the node itself. */
export function composedMembers(schema) {
  if (!isObject(schema)) return [];
  const members = [schema];
  for (const key of ['allOf', 'oneOf', 'anyOf']) {
    if (Array.isArray(schema[key])) members.push(...schema[key].filter(isObject));
  }
  return members;
}

/** Case detectors. Segments containing path templating ({id}) are ignored by callers. */
export const CASE_TESTS = {
  'kebab-case': (s) => /^[a-z0-9]+(-[a-z0-9]+)*$/.test(s),
  'camelCase': (s) => /^[a-z0-9]+([A-Z][a-z0-9]*)*$/.test(s),
  'snake_case': (s) => /^[a-z0-9]+(_[a-z0-9]+)*$/.test(s),
  'PascalCase': (s) => /^([A-Z][a-z0-9]*)+$/.test(s),
  'lowercase': (s) => /^[a-z0-9]+$/.test(s),
  'Hyphenated-Pascal': (s) => /^([A-Z][A-Za-z0-9]*)(-[A-Z][A-Za-z0-9]*)*$/.test(s),
  'lowercase-hyphenated': (s) => /^[a-z0-9]+(-[a-z0-9]+)*$/.test(s),
};

/** Verbs that signal an RPC-style path segment. Deliberately conservative. */
export const RPC_VERBS = [
  'get', 'create', 'update', 'delete', 'remove', 'set', 'fetch', 'list',
  'submit', 'send', 'approve', 'reject', 'process', 'insert', 'add',
  'sign', 'upload', 'download', 'search', 'find', 'validate', 'check',
];

/** Build an absolute Spectral result path from the rule's match path plus a relative one. */
export const at = (context, ...rest) => [...context.path, ...rest.flat()];
