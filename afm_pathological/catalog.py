import importlib
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Optional, Sequence

from afm_pathological.content import article
from afm_pathological.model import Request, Response
from afm_pathological.pages import article_body, page
from afm_pathological.responses import html

TAGS = ('first', 'own source', 'local only', 'production only')  # 'first' is a build-order mark, not in READMEs
FAMILIES = ('regulars', 'chameleons', 'tangle', 'doppelgangers', 'detours', 'speakeasy', 'potholes', 'bouncer',
            'holograms', 'labyrinth', 'attic', 'feeds')


@dataclass(frozen=True)
class Case:
    """One case of the spec: the paths that it serves and the handler that answers them."""
    family: str  # 'regulars', 'chameleons', ...
    name: str  # the case name of the spec, for example 'honest-edit'
    # URL paths; a segment such as '<date>' matches one non-empty path segment, and a final segment such as
    # '<tokens...>' matches the rest of the path: one or more segments, also the empty one after a final slash
    paths: tuple[str, ...]
    behavior: str  # one sentence for the README
    handler: Callable[[Request], Optional[Response]]  # None means "not found"
    tags: tuple[str, ...] = ()  # any of TAGS


@lru_cache(maxsize=1)
def _all_cases() -> tuple[Case, ...]:
    """The cases of all family modules; imported here because the family modules import this one."""
    modules = [importlib.import_module(f'afm_pathological.families.{name}') for name in FAMILIES]
    return tuple(case for module in modules for case in module.CASES)


def cases() -> list[Case]:
    """All cases of all family modules, in family order."""
    return list(_all_cases())


def _matches(pattern: str, path: str) -> bool:
    """True when each '<name>' segment matches one non-empty segment and a final '<name...>' the rest of the path."""
    want, have = pattern.split('/'), path.split('/')
    if want[-1].endswith('...>'):
        if len(have) < len(want):
            return False
        want, have = want[:-1], have[:len(want) - 1]
    return len(want) == len(have) and all(
        w == h or (w.startswith('<') and w.endswith('>') and h) for w, h in zip(want, have))


def find(path: str) -> Optional[Case]:
    """The case that serves a path: exact paths first, then patterns."""
    all_cases = _all_cases()
    exact = next((c for c in all_cases if path in c.paths), None)
    return exact or next((c for c in all_cases if any(_matches(p, path) for p in c.paths if '<' in p)), None)


def section_case(family: str, title: str, links: Sequence[str | tuple[str, str]]) -> Case:
    """The section page at /<family>/: the article of the family name under the title, followed by the links."""
    body = page(title, article_body(article(family), links))
    return Case(family, 'section', (f'/{family}/',), f'Section page: links to the {family} cases',
                lambda request: html(body))
