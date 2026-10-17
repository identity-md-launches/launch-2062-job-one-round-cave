#!/usr/bin/env python3
"""Bounded offline OpenAPI 3.1 propertyNames compatibility checks."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location('keycheck_previous',
    Path(__file__).resolve().parents[1] / 'mapcheck/mapcheck.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
api = previous.api
MAX_KEY_PAIRS = 1024
MAX_ENUM_NAMES = 1024
SUPPORTED = frozenset(('type', 'enum', 'const', 'minLength', 'maxLength'))
TYPES = frozenset(('null', 'boolean', 'object', 'array', 'number', 'integer', 'string'))


def policy(value):
    """Project a resolved schema onto string keys, without evaluating regex/code.

    names=None means all strings within inclusive code-point length bounds.
    An empty finite names set means no keys, NOT an impossible object: {} fits.
    Unknown keywords are preserved separately for unresolved review.
    """
    api.require(isinstance(value, (dict, bool)), 'propertyNames must resolve to a schema')
    if type(value) is bool:
        return (None if value else frozenset(), 0, None), []
    names = None
    if 'type' in value:
        types = value['type']
        types = [types] if isinstance(types, str) else types
        api.require(isinstance(types, list) and types and
                    all(isinstance(t, str) and t in TYPES for t in types),
                    'propertyNames type must name valid JSON Schema types')
        if 'string' not in types:
            names = frozenset()
    if 'enum' in value:
        raw = value['enum']
        api.require(isinstance(raw, list) and 0 < len(raw) <= MAX_ENUM_NAMES,
                    'propertyNames enum must have 1..1024 entries')
        declared = frozenset(v for v in raw if isinstance(v, str))
        names = declared if names is None else names & declared
    if 'const' in value:
        raw = value['const']
        declared = frozenset((raw,)) if isinstance(raw, str) else frozenset()
        names = declared if names is None else names & declared
    bounds = []
    for key, default in (('minLength', 0), ('maxLength', None)):
        bound = value.get(key, default)
        api.require((bound is None and key not in value) or
                    (type(bound) is int and bound >= 0),
                    'propertyNames ' + key + ' must be a nonnegative integer')
        bounds.append(bound)
    lower, upper = bounds
    if upper is not None and lower > upper:
        names = frozenset()
    if names is not None:
        names = frozenset(n for n in names if len(n) >= lower and
                          (upper is None or len(n) <= upper))
    elif upper == 0:
        names = frozenset(('',))  # The only string of zero code points.
    unknown = sorted(set(value) - SUPPORTED - api.ANNOTATIONS)
    return (names, lower, upper), unknown


def subset(left, right):
    """Exact containment of projected finite/length-bounded string domains."""
    a, lo, hi = left
    b, low, high = right
    if a is not None:
        if b is not None:
            return a <= b
        return all(len(n) >= low and (high is None or len(n) <= high) for n in a)
    # Every positive-length interval contains more than 1024 Unicode strings;
    # a bounded enum/const cannot contain that whole projected domain.
    if b is not None:
        return False
    return lo >= low and (high is None or (hi is not None and hi <= high))


def summary(p):
    names, lower, upper = p
    return dict(names=sorted(names) if names is not None else None,
                min_length=lower, max_length=upper)


class Analyzer(previous.Analyzer):
    def __init__(self, old, new):
        super().__init__(old, new)
        self.key_pairs = []

    def _schema(self, old, new, loc, direction):
        super()._schema(old, new, loc, direction)
        if 'propertyNames' not in old and 'propertyNames' not in new:
            return
        api.require(len(self.key_pairs) < MAX_KEY_PAIRS,
                    'propertyNames pair limit exceeded; compare a smaller description')
        a = self.old.resolve(old.get('propertyNames', True))
        b = self.new.resolve(new.get('propertyNames', True))
        pa, ua = policy(a)
        pb, ub = policy(b)
        base = loc + '/propertyNames'
        self.key_pairs.append(dict(location=base, direction=direction,
                                   old=summary(pa), new=summary(pb)))
        # Never silently drop an unchanged reference whose local target changed.
        self.changed(a, b, base, 'property_name_schema_changed',
                     'Resolved object-key schema changed; review consumers of these names.')
        if not (self.old.obj['openapi'].startswith('3.1.') and
                self.new.obj['openapi'].startswith('3.1.')):
            self.emit('review', 'property_names_dialect_unchecked', base,
                      'propertyNames analysis requires OpenAPI 3.1 on both sides.')
            return
        if ua or ub:
            self.emit('review', 'property_name_constraints_unchecked', base,
                      'Key-domain projection omits constraints: ' + ', '.join(sorted(set(ua + ub))) +
                      '. Domain findings are potential breaks; resolve these constraints manually.')
        safe = subset(pa, pb) if direction == 'request' else subset(pb, pa)
        if not safe:
            self.emit('breaking', 'property_names_incompatible', base,
                      'Potential break: projected request key domain narrowed.' if direction == 'request'
                      else 'Potential break: projected response key domain widened.')


def compare(old, new):
    analyzer = Analyzer(old, new)
    report = analyzer.run()
    report.update(extension='keycheck-v1 (includes mapcheck and earlier analyzers)',
                  key_pairs=analyzer.key_pairs, map_pairs=analyzer.map_pairs,
                  dispatch_pairs=analyzer.dispatch_pairs, schema_visits=analyzer.steps,
                  selector_groups=analyzer.selector_groups, status_visits=analyzer.status_visits,
                  remapped_header_pairs=analyzer.remapped_header_pairs,
                  key_scope='OpenAPI 3.1 propertyNames string domains: type, enum, const and '
                            'inclusive code-point lengths. Other constraints remain review. '
                            'Potential region-level breaks, not whole-object compatibility proof.')
    return report


def demo():
    capture = Path(__file__).resolve().parents[1] / 'apidelta/imd-openapi.json'
    old, digest = api.load(capture)
    old = copy.deepcopy(old)
    old['openapi'] = '3.1.0'
    path = sorted(old['paths'])[0]
    method = sorted(old['paths'][path].keys() & api.METHODS)[0]
    schemas = old.setdefault('components', {}).setdefault('schemas', {})
    api.require('KeyNames38' not in schemas, 'demo component collision')
    schemas['KeyNames38'] = {'enum': ['pending', 'done']}
    old['paths'][path][method]['responses'] = {'200': {'description': 'Hypothetical key policy',
        'content': {'application/json': {'schema': {'type': 'object',
            'propertyNames': {'$ref': '#/components/schemas/KeyNames38'}}}}}}
    new = copy.deepcopy(old)
    new['components']['schemas']['KeyNames38']['enum'].append('retry')
    report = compare(old, new)
    api.require(any(f['code'] == 'property_names_incompatible' for f in report['findings']),
                'demo failed to inspect unchanged key-schema reference')
    report.update(capture_sha256=digest, baseline_source='https://api.imd.fun/openapi.json',
                  demo='Saved real IMD operation, hypothetically using OpenAPI 3.1 and a '
                       'referenced response-key enum. Only the target expands. '
                       'This is not an observed service change; no API operation is called.')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('demo')
    diff = commands.add_parser('compare')
    diff.add_argument('old')
    diff.add_argument('new')
    args = parser.parse_args(argv)
    try:
        if args.command == 'demo':
            report = demo()
        else:
            old, oh = api.load(args.old)
            new, nh = api.load(args.new)
            report = compare(old, new)
            report.update(old_sha256=oh, new_sha256=nh)
        print(json.dumps(report, indent=2, allow_nan=False))
        return 0 if args.command == 'demo' else {
            'breaking': 1, 'review_required': 3, 'no_detected_breakage': 0}[report['status']]
    except (api.Invalid, OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        print('keycheck: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
