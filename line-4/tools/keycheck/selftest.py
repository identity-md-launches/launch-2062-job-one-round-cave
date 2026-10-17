#!/usr/bin/env python3
"""KeyCheck integration regressions and independently evaluated key domains."""
import contextlib
import copy
import io
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import keycheck as tool

MISSING = object()


def doc(policy=MISSING, direction='response', version='3.1.0'):
    schema = {'type': 'object'}
    if policy is not MISSING:
        schema['propertyNames'] = copy.deepcopy(policy)
    media = {'application/json': {'schema': schema}}
    op = {'responses': {}}
    if direction == 'response':
        op['responses']['200'] = {'description': 'test', 'content': media}
    else:
        op['requestBody'] = {'content': media}
    return {'openapi': version, 'paths': {'/probe': {'post': op}}}


def root(d, direction='response'):
    op = d['paths']['/probe']['post']
    body = op['responses']['200'] if direction == 'response' else op['requestBody']
    return body['content']['application/json']['schema']


def codes(report):
    return {f['code'] for f in report['findings']}


def incompatible(report):
    return 'property_names_incompatible' in codes(report)


def allows(schema, key):
    """Independent direct predicate; does not call KeyCheck policy/subset."""
    if schema is MISSING or schema is True:
        return True
    if schema is False:
        return False
    types = schema.get('type', 'string')
    if isinstance(types, str):
        types = [types]
    if 'string' not in types:
        return False
    if 'enum' in schema and key not in schema['enum']:
        return False
    if 'const' in schema and key != schema['const']:
        return False
    return len(key) >= schema.get('minLength', 0) and len(key) <= schema.get('maxLength', 100)


class Tests(unittest.TestCase):
    def test_exhaustive_representative_key_domains(self):
        policies = [MISSING, True, False, {}, {'type': 'string'}, {'type': 'integer'},
                    {'enum': ['a']}, {'enum': ['a', 'b']}, {'enum': ['', 'a', 1]},
                    {'const': 'b'}, {'const': 3}, {'minLength': 1}, {'maxLength': 1},
                    {'maxLength': 0}, {'minLength': 2, 'maxLength': 1},
                    {'enum': ['a', 'ab'], 'minLength': 2},
                    {'enum': ['a'], 'const': 'b'}, {'minLength': 1, 'maxLength': 2}]
        # These representatives distinguish every supported domain above;
        # single-key objects suffice to witness propertyNames incompatibility.
        keys = ['', 'a', 'b', 'c', 'ab', 'bc', 'abc', 'abcd', 'é', '🐸', 'e\u0301']
        count = 0
        for direction, a, b in itertools.product(('request', 'response'), policies, policies):
            before = {k for k in keys if allows(a, k)}
            after = {k for k in keys if allows(b, k)}
            unsafe = bool(before - after) if direction == 'request' else bool(after - before)
            report = tool.compare(doc(a, direction), doc(b, direction))
            self.assertEqual(incompatible(report), unsafe, (direction, a, b))
            count += 1
        self.assertEqual(count, 648)

    def test_unchanged_reference_changed_target_both_directions(self):
        for direction in ('request', 'response'):
            a = doc({'$ref': '#/components/schemas/Names'}, direction)
            a['components'] = {'schemas': {'Names': {'enum': ['a', 'b']}}}
            b = copy.deepcopy(a)
            b['components']['schemas']['Names']['enum'] = ['a'] if direction == 'request' else ['a', 'b', 'c']
            prior = tool.previous.compare(a, b)
            report = tool.compare(a, b)
            self.assertFalse(incompatible(prior))
            self.assertTrue(incompatible(report))
            self.assertTrue(all(f in report['findings'] for f in prior['findings']))
            self.assertIn('property_name_schema_changed', codes(report))
            self.assertEqual(root(a, direction), root(b, direction))

    def test_unicode_lengths_are_code_points(self):
        a, b = doc({'enum': ['🐸', 'é', 'e\u0301']}, 'request'), doc({'maxLength': 1}, 'request')
        self.assertTrue(incompatible(tool.compare(a, b)))
        a = doc({'enum': ['🐸', 'é']}, 'request')
        self.assertFalse(incompatible(tool.compare(a, b)))

    def test_key_types_and_nonstring_literals_are_intersected(self):
        for a, b in (({}, {'type': 'string'}), ({'enum': [1, 'a']}, {'enum': ['a']}),
                     ({'const': 1}, False), ({'type': ['integer', 'string']}, {}),
                     ({'enum': ['a'], 'const': 'b'}, False), ({'type': 'integer'}, False)):
            for direction in ('request', 'response'):
                self.assertFalse(incompatible(tool.compare(doc(a, direction), doc(b, direction))))
                self.assertFalse(incompatible(tool.compare(doc(b, direction), doc(a, direction))))

    def test_empty_string_only_domain(self):
        for a, b in (({'maxLength': 0}, {'const': ''}),
                     ({'minLength': 1, 'maxLength': 0}, False)):
            for direction in ('request', 'response'):
                self.assertFalse(incompatible(tool.compare(doc(a, direction), doc(b, direction))))
                self.assertFalse(incompatible(tool.compare(doc(b, direction), doc(a, direction))))
        self.assertTrue(incompatible(tool.compare(doc({'maxLength': 0}), doc({'maxLength': 1}))))

    def test_unknown_keywords_review_even_when_unchanged(self):
        for schema in ({'pattern': '^a'}, {'format': 'uuid'}, {'allOf': [{'const': 'a'}]},
                       {'minLength': 1, 'x-policy': 'custom'}):
            report = tool.compare(doc(schema), doc(schema))
            self.assertEqual(report['status'], 'review_required')
            self.assertIn('property_name_constraints_unchecked', codes(report))
        a = doc({'$ref': '#/components/schemas/Names'})
        a['components'] = {'schemas': {'Names': {'pattern': '^a'}}}
        b = copy.deepcopy(a)
        b['components']['schemas']['Names']['pattern'] = '^b'
        self.assertIn('property_name_schema_changed', codes(tool.compare(a, b)))

    def test_openapi30_and_cross_version_remain_review(self):
        for va, vb in (('3.0.3', '3.0.3'), ('3.0.3', '3.1.0'), ('3.1.0', '3.0.3')):
            report = tool.compare(doc({'enum': ['a']}, version=va), doc({'enum': ['a', 'b']}, version=vb))
            self.assertFalse(incompatible(report))
            self.assertIn('property_names_dialect_unchecked', codes(report))

    def test_annotations_do_not_become_unchecked_constraints(self):
        a = doc({'enum': ['a'], 'description': 'old'})
        b = doc({'enum': ['a'], 'description': 'new'})
        report = tool.compare(a, b)
        self.assertFalse(incompatible(report))
        self.assertNotIn('property_name_constraints_unchecked', codes(report))
        self.assertIn('property_name_schema_changed', codes(report))

    def test_nested_maps_arrays_properties_and_precise_pointer(self):
        a = doc()
        root(a).update(properties={'a/~': {'type': 'array', 'items': {'type': 'object',
            'additionalProperties': {'type': 'object', 'propertyNames': {'enum': ['a']}}}}})
        b = copy.deepcopy(a)
        root(b)['properties']['a/~']['items']['additionalProperties']['propertyNames']['enum'].append('b')
        report = tool.compare(a, b)
        self.assertTrue(incompatible(report))
        self.assertTrue(any('/properties/a~1~0/items/additionalProperties/propertyNames' in f['location']
                            for f in report['findings'] if f['code'] == 'property_names_incompatible'))
        self.assertEqual(len(report['map_pairs']), 1)

    def test_recursive_local_graph_terminates(self):
        a = doc()
        root(a)['additionalProperties'] = {'$ref': '#/components/schemas/Node'}
        a['components'] = {'schemas': {'Node': {'type': 'object',
            'propertyNames': {'enum': ['next', 'value']},
            'additionalProperties': {'$ref': '#/components/schemas/Node'}}}}
        b = copy.deepcopy(a)
        b['components']['schemas']['Node']['propertyNames']['enum'].append('other')
        report = tool.compare(a, b)
        self.assertTrue(incompatible(report))
        self.assertLess(report['schema_visits'], 30)
        self.assertEqual(len(report['key_pairs']), 1)

    def test_remapped_response_header_and_request_parameter(self):
        a = doc()
        op = a['paths']['/probe']['post']
        op['responses'] = {'2XX': {'description': 'test', 'headers': {'X-Names': {
            'schema': {'type': 'object', 'propertyNames': {'enum': ['a']}}}}}}
        b = copy.deepcopy(a)
        bop = b['paths']['/probe']['post']
        bop['responses'] = {'200': copy.deepcopy(op['responses']['2XX'])}
        bop['responses']['200']['headers']['X-Names']['schema']['propertyNames']['enum'].append('b')
        report = tool.compare(a, b)
        self.assertTrue(incompatible(report))
        self.assertTrue(any('/headers/x-names/schema/propertyNames' in f['location']
                            for f in report['findings']))
        a = doc()
        a['paths']['/probe']['post']['parameters'] = [{'name': 'names', 'in': 'query',
            'schema': {'type': 'object', 'propertyNames': {'enum': ['a', 'b']}}}]
        b = copy.deepcopy(a)
        b['paths']['/probe']['post']['parameters'][0]['schema']['propertyNames']['enum'].pop()
        self.assertTrue(incompatible(tool.compare(a, b)))

    def test_discriminator_target_is_visited(self):
        a = doc()
        root(a).update(oneOf=[{'$ref': '#/components/schemas/N'}],
                       discriminator={'propertyName': 'kind', 'mapping': {'n': 'N'}})
        a['components'] = {'schemas': {'N': {'type': 'object', 'propertyNames': {'enum': ['kind']}}}}
        b = copy.deepcopy(a)
        b['components']['schemas']['N']['propertyNames']['enum'].append('other')
        report = tool.compare(a, b)
        self.assertTrue(incompatible(report))
        self.assertEqual(len(report['dispatch_pairs']), 1)

    def test_invalid_policies_and_references_refuse(self):
        for value in (None, 0, 'string', [], {'type': []}, {'type': ['string', 3]},
                      {'enum': []}, {'enum': 'a'}, {'minLength': True}, {'maxLength': None},
                      {'maxLength': -1}, {'minLength': 1.5}, {'$ref': 'https://example.invalid/key'},
                      {'$ref': '#/missing'}, {'$ref': '#/a~2'}, {'$ref': '#/a', 'const': 'a'}):
            with self.subTest(value=value), self.assertRaises(tool.api.Invalid):
                tool.compare(doc(value), doc(value))
        a = doc({'$ref': '#/components/schemas/K'})
        a['components'] = {'schemas': {'K': {'$ref': '#/components/schemas/K'}}}
        with self.assertRaises(tool.api.Invalid):
            tool.compare(a, a)
        a['components']['schemas']['K'] = []
        with self.assertRaises(tool.api.Invalid):
            tool.compare(a, a)

    def test_budgets_refuse_no_partial_success(self):
        a = doc({'enum': ['a', 'b']})
        for owner, field in ((tool, 'MAX_KEY_PAIRS'), (tool.api, 'MAX_STEPS')):
            with patch.object(owner, field, 0), self.assertRaises(tool.api.Invalid):
                tool.compare(a, a)
        with patch.object(tool, 'MAX_ENUM_NAMES', 1), self.assertRaises(tool.api.Invalid):
            tool.compare(a, a)
        with patch.object(tool.api, 'MAX_FINDINGS', 0), self.assertRaises(tool.api.Invalid):
            tool.compare(a, doc(False))

    def test_unchanged_real_capture_determinism_and_nonmutation(self):
        capture = Path(__file__).resolve().parents[1] / 'apidelta/imd-openapi.json'
        a, _ = tool.api.load(capture)
        snapshot = copy.deepcopy(a)
        report = tool.compare(a, a)
        self.assertEqual(report['operations_compared'], 5)
        self.assertEqual(report['findings'], [])
        self.assertEqual(a, snapshot)
        a = doc({'enum': ['a']})
        b = doc({'enum': ['a', 'b']})
        aa, bb = copy.deepcopy(a), copy.deepcopy(b)
        self.assertEqual(tool.compare(a, b), tool.compare(a, b))
        self.assertEqual((a, b), (aa, bb))

    def test_cli_demo_and_all_exit_states(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(tool.main(['demo']), 0)
        scratch = Path('test/scratch')
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as folder:
            p, q = Path(folder) / 'old.json', Path(folder) / 'new.json'
            a = doc({'enum': ['a']})
            p.write_text(json.dumps(a))
            for b, expected in ((a, 0), (doc({'enum': ['a', 'b']}), 1),
                                (doc({'enum': ['a'], 'description': 'new'}), 3), ({}, 2)):
                q.write_text(json.dumps(b))
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(tool.main(['compare', str(p), str(q)]), expected)


if __name__ == '__main__':
    unittest.main()
