import unittest
from copy import deepcopy
from unittest import mock
from unittest.mock import patch

from reiteration.cache import OverridableKwargs, OverrideOnlyKwargs
from reiteration.cache import _update_dicts, _get_overrides, _get_key_args, cache_decorator
from reiteration.storage import MemoryStore


def with_args(a, b, c):
    pass


def with_kwargs(x=None, y=None, z=None):
    pass


def with_both(arg1, arg2, kwarg1=None, kwarg2=None):
    pass


class Md5Patch:

    def __init__(self, data):
        self.data = data

    def hexdigest(self):
        if not self.data:
            return 'None'
        return self.data.decode("utf-8")


class TestGetArgs(unittest.TestCase):

    def setUp(self):
        self.md5_patch = patch('reiteration.cache.md5', Md5Patch)
        self.md5_patch.start()

    def tearDown(self):
        self.md5_patch.stop()

    def obj_method(self):
        pass

    def test_obj_method(self):
        self.assertEqual('(1, 2, 3)', _get_key_args(self.obj_method, None, None, [self, 1, 2, 3], {}))

    def test_use_all(self):
        self.assertEqual('(x, y, z)', _get_key_args(with_args, None, None, ['x', 'y', 'z'], {}))
        self.assertEqual('(kwarg1 = 1, kwarg2 = 2)',
                         _get_key_args(with_kwargs, None, None, [], {'kwarg1': '1', 'kwarg2': '2'}))
        self.assertEqual('(v1, v2, kwarg1 = 1, kwarg2 = 2)',
                         _get_key_args(with_both, None, None, ['v1', 'v2'], {'kwarg1': 1, 'kwarg2': 2}))

    def test_no_args(self):
        self.assertEqual('()', _get_key_args(with_args, [], None, [], {}))
        self.assertEqual('()', _get_key_args(with_kwargs, [], None, [], {}))
        self.assertEqual('()', _get_key_args(with_both, [], None, [], {}))

    def test_use_some(self):
        self.assertEqual('(first)', _get_key_args(with_args, ['a'], None, ['first', 'second', 'third'], {'hello': 1}))
        self.assertEqual('(arg1v, kwarg1 = v)',
                         _get_key_args(with_both, ['arg1', 'kwarg1'], None, ['arg1v'], {'kwarg1': 'v'}))

    def test_ignore_some(self):
        self.assertEqual('(3)', _get_key_args(with_args, None, ['a', 'b'], ['1', '2', '3'], None))
        self.assertEqual('(x = 3, y = 2)', _get_key_args(with_kwargs, None, ['z'], None, {'x': 3, 'y': 2}))
        self.assertEqual('(hello, kwarg2 = kw2)',
                         _get_key_args(with_both,
                                       None,
                                       ['arg1', 'kwarg1'],
                                       ['yo', 'hello'],
                                       {'kwarg1': 'kw1', 'kwarg2': 'kw2'}))

    def test_wrong_args(self):
        self.assertEqual('()', _get_key_args(with_args, ['a1', 'b1'], ['yes', 'yep'], {}, []))


class TestUpdateDicts(unittest.TestCase):

    def test_simple(self):
        o = {1: 'a', 2: 'b'}
        t = {2: 'c', 4: 'd'}
        copy_o = deepcopy(o)
        copy_t = deepcopy(t)
        c = _update_dicts(o, t)
        copy_o.update(copy_t)
        self.assertEqual(c, copy_o)

    def test_recursive_negative_case(self):
        o = {1: 'a', 2: 'b'}
        t = {2: 'c', 4: 'd'}
        n1 = {5: 'e', 6: 'f', 'n': o}
        n2 = {5: 'f', 6: 'f', 'n': t}
        c = _update_dicts(n1, n2)
        n1.update(n2)
        self.assertNotEqual(c, n1)

    def test_recursive(self):
        o = {1: 'a', 2: 'b'}
        t = {2: 'c', 4: 'd'}
        n1 = {5: 'e', 6: 'f', 'n': o}
        n2 = {5: 'f', 6: 'f', 'n': t}
        c = _update_dicts(n1, n2)
        n2.pop('n')
        n1.update(n2)
        o.update(t)
        self.assertEqual(c, n1)


class TestCacheDecorator(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.stash = mock.patch('reiteration.cache.stash', self.store)
        self.stash.start()
        self.mock = mock.Mock()
        self.mock.__qualname__ = 'qualname'
        self.mock.__name__ = 'unit_test'

    def tearDown(self):
        self.stash.stop()

    def test_works(self):
        decorated = cache_decorator(enabled=True)(self.mock)
        self.mock.return_value = 3
        decorated('hello')
        decorated('hello')
        self.mock.assert_called_once()

    def test_enabled(self):
        decorated = cache_decorator(enabled=False)(self.mock)
        self.mock.return_value = 3
        decorated('hello')
        decorated('hello')
        self.assertEqual(self.mock.call_count, 2)

    def test_use_cache(self):
        decorated = cache_decorator(use_cache=True)(self.mock)
        self.mock.return_value = 3
        decorated('hello')
        decorated('hello')
        self.assertEqual(self.mock.call_count, 1)
        self.mock.reset_mock()
        decorated = cache_decorator(use_cache=False)(self.mock)
        decorated('hello')
        decorated('hello')
        self.assertEqual(self.mock.call_count, 2)

    def test_reset(self):
        decorated = cache_decorator(use_cache=True, overrides={OverrideOnlyKwargs.Reset: False})(self.mock)
        self.mock.return_value = 3
        decorated('hello')
        decorated('hello')
        self.assertEqual(self.mock.call_count, 1)
        self.mock.reset_mock()
        decorated = cache_decorator(use_cache=True, overrides={OverrideOnlyKwargs.Reset: True})(self.mock)
        self.mock.return_value = 32
        decorated('hello')
        decorated('hello')
        self.assertEqual(self.mock.call_count, 2)

    def test_args(self):
        decorated = cache_decorator()(self.mock)
        self.mock.return_value = 3
        decorated('hello')
        decorated('hello again')
        self.assertEqual(self.mock.call_count, 2)
        self.assertEqual(len(self.store.data), 2)

    def test_key_prefix(self):
        decorated = cache_decorator(key_prefix='yo')(self.mock)
        self.mock.return_value = 3
        decorated('hello')
        decorated('hello again')
        self.assertTrue(all([x.startswith('yo') for x in self.store.data]))


class TestGetOverrides(unittest.TestCase):

    def test_overrides(self):
        overrides = {OverridableKwargs.Use_Cache: True}
        group_overrides = {'A': {OverridableKwargs.Use_Cache: False}}
        o = _get_overrides(overrides, group_overrides, 'A')
        self.assertFalse(o[OverridableKwargs.Use_Cache])


if __name__ == '__main__':
    unittest.main()
