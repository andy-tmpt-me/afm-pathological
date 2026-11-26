from afm_pathological.catalog import TAGS, _matches, cases, find


def test_one_segment_pattern():
    """'<name>' matches one non-empty segment."""
    assert _matches('/a/<n>', '/a/1') and not _matches('/a/<n>', '/a/') and not _matches('/a/<n>', '/a/1/2')


def test_rest_pattern():
    """A final '<name...>' matches the rest of the path: one or more segments, also the empty one of a slash."""
    for path in ('/a/', '/a/1', '/a/1/', '/a/1/2/3/'):
        assert _matches('/a/<rest...>', path), path
    for path in ('/a', '/b/1', '/'):
        assert not _matches('/a/<rest...>', path), path


def test_exact_paths_before_patterns():
    """An exact path wins over a pattern that also matches it."""
    assert find('/tangle/odd').name == 'odd-urls' and find('/tangle/files').name == 'files'
    assert find('/feeds/long.xml').name == 'long-feed' and find('/labyrinth/session/').name == 'session-path'


def test_tags_are_tuples_of_known_tags():
    """Each case has a tuple of tags, each one of TAGS."""
    for case in cases():
        assert isinstance(case.tags, tuple) and set(case.tags) <= set(TAGS), (case.family, case.name, case.tags)
