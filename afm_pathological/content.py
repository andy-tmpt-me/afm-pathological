import hashlib
from dataclasses import dataclass
from functools import lru_cache

_SENTENCES = (
    'A healthy sourdough starter doubles in size within six hours of a feeding at room temperature.',
    'Whole rye flour gives the culture more food than white flour and speeds up fermentation.',
    'Most bakers feed their starter equal weights of flour and water once or twice each day.',
    'When the jar smells of acetone, the yeast is hungry and the next feeding is overdue.',
    'A long cold retard in the refrigerator develops a deeper and more sour flavor in the loaf.',
    'Hydration is the weight of the water divided by the weight of the flour in the dough.',
    'A dough at seventy five percent hydration is sticky at first but becomes smooth with folds.',
    'Stretch and fold the dough every thirty minutes during the first two hours of bulk fermentation.',
    'The windowpane test shows whether the gluten network is strong enough to hold the gas.',
    'Salt tightens the gluten, slows the yeast and brings out the taste of the wheat.',
    'Add the salt after the autolyse so that the flour can absorb the water without resistance.',
    'An autolyse of one hour makes the dough more extensible and easier to shape later.',
    'Bulk fermentation is complete when the dough has risen by half and shows bubbles at the edges.',
    'Shape the loaf with firm tension on the surface so that it keeps its height in the oven.',
    'A banneton dusted with rice flour stops the dough from sticking during the final proof.',
    'The poke test tells you when the proof is done: the dent should spring back slowly.',
    'Score the loaf with a sharp blade held at a low angle to get a proud ear.',
    'A single long score along the length of a batard opens the loaf in a clean curve.',
    'Steam in the first twenty minutes keeps the crust soft so that the loaf can expand fully.',
    'A covered cast iron pot traps the steam of the dough itself and needs no extra water.',
    'Bake at two hundred and fifty degrees with the lid on, then lower the heat and remove it.',
    'The internal temperature of a finished loaf is about ninety eight degrees Celsius.',
    'Let the bread cool for at least an hour, because the crumb is still setting inside.',
    'An open and glossy crumb comes from high hydration, gentle handling and a strong starter.',
    'A tight crumb with small even holes is right for sandwiches and toast in the morning.',
    'Large tunnels under the crust usually mean that the dough was underproofed before the bake.',
    'A dense and gummy crumb can mean that the starter was weak or the bake was too short.',
    'Freshly milled flour absorbs more water than old flour, so adjust the recipe by feel.',
    'Spelt flour has a weak gluten, so a spelt dough needs less mixing and a shorter proof.',
    'A baker keeps notes on time, temperature and flour for each loaf to learn from every bake.',
    'The temperature of the dough matters more than the clock when you judge the fermentation.',
    'A warm kitchen in summer can halve the time that the bulk fermentation takes.',
    'In a cold kitchen, put the dough in the oven with only the light on for gentle warmth.',
    'A levain is a portion of starter built up the night before for a single bake.',
    'Discard from the starter makes good crackers, pancakes and flatbreads with a mild tang.',
    'A starter that sits unfed in the refrigerator for weeks recovers after two or three feedings.',
    'This note on {topic} comes from many bakes of sourdough in a home kitchen.',
    'For {topic}, write down what you changed so that the next loaf can improve on it.',
    'Bakers who ask about {topic} often find that patience solves more problems than any tool.',
    'The lesson of {topic} is that small changes in sourdough baking give large differences in the loaf.',
)
_OPENERS = (
    'These notes on {topic} belong to a journal of sourdough baking at home.',
    'Every sourdough baker meets the question of {topic} sooner or later.',
    'Here is what years of sourdough loaves have taught us about {topic}.',
)
_PER_PARAGRAPH = 5
_FIXED_PARAGRAPHS = 4


@dataclass(frozen=True)
class Article:
    """The title and the paragraphs of one article."""
    title: str
    paragraphs: tuple[str, ...]


def _digest(text: str) -> int:
    """A stable integer hash of a string."""
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], 'big')


@lru_cache(maxsize=1024)
def article(key: str, variant: int = 0) -> Article:
    """A deterministic article about sourdough baking; a different variant changes only the last paragraph."""
    count = len(_SENTENCES)
    order = sorted(range(count), key=lambda i: _digest(f'{key}:{i}'))
    topic = key.replace('-', ' ')

    def paragraph(indexes) -> str:
        return ' '.join(_SENTENCES[i].format(topic=topic) for i in indexes)

    fixed = [paragraph(order[p * _PER_PARAGRAPH:(p + 1) * _PER_PARAGRAPH]) for p in range(_FIXED_PARAGRAPHS)]
    fixed[0] = _OPENERS[_digest(key) % len(_OPENERS)].format(topic=topic) + ' ' + fixed[0]
    # Each sentence of the last paragraph shifts by one digit of the variant in base `count`, so two variants
    # below count ** _PER_PARAGRAPH always give different paragraphs.
    base = order[_FIXED_PARAGRAPHS * _PER_PARAGRAPH:][:_PER_PARAGRAPH]
    last = paragraph((b + variant // count ** j) % count for j, b in enumerate(base))
    return Article(f'Sourdough baking notes: {key}', (*fixed, last))
