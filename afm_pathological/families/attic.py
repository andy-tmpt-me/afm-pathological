from functools import lru_cache
from html import escape

from afm_pathological import assets
from afm_pathological.catalog import Case, section_case
from afm_pathological.content import article
from afm_pathological.model import Request, Response
from afm_pathological.pages import article_body, article_page, page
from afm_pathological.responses import html, xml
from afm_pathological.sitemaps import urlset

# A public demo video; an operator can replace it with another video ID.
YOUTUBE_VIDEO_ID = 'M7lc1UVf-VE'
_EMBEDDED = (f'<iframe src="https://www.youtube.com/embed/{YOUTUBE_VIDEO_ID}"></iframe>\n'
             '<iframe src="https://player.vimeo.com/video/76979871"></iframe>\n'
             '<audio src="/tangle/files/talk.mp3"></audio>\n'
             '<p><a href="/tangle/files/talk.mp3?utm_source=player">Download the episode</a></p>')
_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
        '<ellipse cx="32" cy="38" rx="26" ry="16" fill="#c68642"/></svg>\n')
_PRIVACY = (
    'This privacy policy explains what information we collect when you visit our website, how we use it and the '
    'choices that you have. We collect the information that you give us, such as your name and email address when '
    'you contact us, and the information that your browser sends us, such as your IP address, the type of device '
    'that you use and the pages that you open.',
    'We use this information to answer your messages, to keep the website secure and to understand how many people '
    'use it. We do not sell your personal information. We share it only with the service providers who host the '
    'website and send our email, and only to the extent that they need it to do their work for us.',
    'We keep the messages that you send us for as long as we need them to answer you and to meet our legal duties. '
    'Server logs are deleted after ninety days. When we no longer need information, we delete it or remove the '
    'details that identify you from it.',
    'You can ask us at any time to show you the personal information that we hold about you, to correct it or to '
    'delete it. You can also ask us to stop sending you email. To use any of these rights, write to the address '
    'at the end of this policy and tell us what you would like us to do. We answer each request within thirty days.',
    'Our website uses a small number of cookies. Some are needed for the website to work, and others tell us how '
    'visitors use it. Your browser lets you refuse or delete cookies, although parts of the website may then work '
    'less well. We do not use cookies to show you advertisements.',
    'Our website can link to websites that other organizations run. This policy does not apply to them, and we '
    'suggest that you read the privacy policy of each website that you visit. We can change this policy from time to '
    'time. When we do, we post the new version on this page and change the date at the top.',
    'If you have a question about this policy or about how we treat your information, or if you think that we '
    'handled your information in a way that does not follow this policy, please write to us. We take each message '
    'seriously and we reply to each one.')
_CAREERS = (
    'We are a small company that builds software for local government offices, and we are growing. Our team works '
    'from several time zones, meets once a week by video and meets in person twice a year. We value clear writing, '
    'careful testing and the habit of asking questions early. Below is the list of the jobs that are open today.',
    'Backend engineer. You will build and run the services that store and send the records of our customers. You '
    'know a modern programming language well, you have worked with a relational database and you like to find the '
    'cause of a failure instead of covering it. Experience with cloud hosting is useful but not required.',
    'Frontend engineer. You will build the screens that clerks use every day to search, edit and approve records. '
    'You care about forms that are easy to fill in, about pages that load quickly and about people who use a screen '
    'reader. You write tests for the code that you write and you review the code of your teammates.',
    'Customer support specialist. You will answer questions from the staff of our customers by email and by phone, '
    'and you will explain our software in plain words. You are patient, you write well and you pass on to the '
    'engineers what you learn from each call, so that the next customer has less trouble.',
    'Office manager. You will plan our travel, order equipment, keep our accounts in order and welcome visitors to '
    'the small office that we keep in the city. You are organized, you are calm when three things happen at once and '
    'you enjoy making a workplace run well for the people who share it.',
    'To apply, send us a short letter that tells us why you want the job and a list of the work that you are proud '
    'of. We read every application, we answer every one and we try to finish the process within three weeks. We '
    'hire people of all backgrounds and we ask for no degree for any of these jobs.')
_FRENCH = (
    'Le pain au levain est l\'un des plus anciens pains du monde, et la recette n\'a presque pas changé depuis des '
    'siècles. On mélange de la farine et de l\'eau, on attend que de petites bulles apparaissent, et l\'on obtient un '
    'levain vivant qui fait lever la pâte sans levure du commerce. Cet article explique les gestes de base pour '
    'réussir son premier pain à la maison.',
    'Pour fabriquer un levain, mélangez chaque jour la même quantité de farine et d\'eau dans un bocal propre. '
    'Après cinq à sept jours, le mélange double de volume en quelques heures et sent légèrement l\'acidité du yaourt. '
    'À ce moment, votre levain est prêt. Gardez-le au réfrigérateur et nourrissez-le une fois par semaine pour qu\'il '
    'reste en bonne santé.',
    'La veille de la cuisson, mélangez le levain avec la farine, l\'eau et le sel. Laissez reposer la pâte pendant '
    'trente minutes, puis pliez-la plusieurs fois à intervalles réguliers. Ces plis donnent de la force à la pâte et '
    'remplacent un long pétrissage. Ensuite, couvrez le saladier et laissez la pâte lever à température ambiante '
    'pendant quelques heures.',
    'Quand la pâte a bien gonflé, façonnez-la en boule ou en bâtonnet et déposez-la dans un panier fariné. Placez '
    'le panier au réfrigérateur pour la nuit. Le froid ralentit la fermentation, développe les arômes et rend la pâte '
    'plus facile à inciser le lendemain matin. C\'est le secret des boulangers pour obtenir une croûte croustillante '
    'et une mie alvéolée.',
    'Le jour de la cuisson, préchauffez le four à deux cent quarante degrés avec une cocotte en fonte à l\'intérieur. '
    'Retournez la pâte sur une feuille de papier, entaillez le dessus avec une lame bien affûtée et déposez le tout '
    'dans la cocotte brûlante. Couvrez, enfournez, et baissez la température après vingt minutes. Retirez le '
    'couvercle pour que la croûte dore pendant les vingt dernières minutes.',
    'Laissez le pain refroidir sur une grille avant de le couper, car la mie continue de cuire à l\'intérieur. '
    'Chaque pain est un peu différent du précédent. Notez ce que vous avez fait, goûtez, ajustez, et recommencez. '
    'Avec un peu de patience, le levain vous récompensera de pains délicieux pendant des années.')


def _text_page(title: str, paragraphs: tuple[str, ...]) -> Response:
    """A page of the given paragraphs."""
    return html(page(title, '\n'.join(f'<p>{escape(p)}</p>' for p in paragraphs)))


@lru_cache(maxsize=1)
def _large() -> bytes:
    """2,000 paragraphs of 2,560 characters each: 5.1 MB."""
    paragraphs = []
    for i in range(2000):
        a, b = article(f'attic-large-{i}'), article(f'attic-large-{i}-b')
        paragraphs.append(f'<p>{escape(" ".join((*a.paragraphs, *b.paragraphs))[:2560])}</p>')
    return page('Sourdough baking notes: the large page', '\n'.join(paragraphs)).encode()


def _untitled(key: str, head_html: str = '') -> str:
    """An article page with no <title> and no <h1>."""
    return (f'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n{head_html}</head>\n<body>\n'
            f'{article_body(article(key))}\n</body>\n</html>\n')


def _sitemap(request: Request) -> Response:
    """A sitemap of four absolute URLs: two pages that are not relevant and two articles."""
    paths = ('/attic/privacy-policy', '/attic/careers', '/articles/starter', '/articles/steam')
    return xml(urlset([(request.url(path), None) for path in paths]))


def _metadata(request: Request) -> Response:
    """The four metadata pages, and the SVG image of one of them."""
    name = request.path.removeprefix('/attic/')
    og = '<meta property="og:{}" content="{}">\n'
    key = f'attic-{name}'
    if name == 'loaf.svg':
        return Response(200, {'content-type': 'image/svg+xml'}, _SVG.encode())
    if name == 'no-title':
        return html(_untitled(key))
    if name == 'og-only':
        a = article(key)
        return html(_untitled(key, og.format('title', escape(a.title))
                              + og.format('description', escape(a.paragraphs[0][:150]))))
    if name == 'svg-image':
        return html(article_page(key, head_html=og.format('image', '/attic/loaf.svg')))
    return html(article_page(key, head_html='<link rel="canonical">\n'))


CASES: list[Case] = [
    section_case('attic', 'Attic: unusual content', [
        '/attic/no-text', '/attic/embedded', '/attic/paper.pdf', '/attic/paper', '/attic/no-title', '/attic/og-only',
        '/attic/svg-image', '/attic/canonical-no-href', '/attic/french']),
    Case('attic', 'no-text', ('/attic/no-text',), 'A page with one image and no text',
         lambda request: html(f'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                              f'<title>{escape(article("attic-no-text").title)}</title>\n</head>\n<body>\n'
                              '<img src="/tangle/files/photo.jpg" alt="A loaf of bread">\n</body>\n</html>\n')),
    Case('attic', 'large-page', ('/attic/large',), '5 MB of HTML: 2,000 paragraphs',
         lambda request: Response(200, {'content-type': 'text/html; charset=utf-8'}, _large()), ('own source',)),
    Case('attic', 'embedded-media', ('/attic/embedded',),
         'A YouTube frame, a Vimeo frame, an audio element with an MP3 and a download link to the same MP3 with '
         '?utm_source=player',
         lambda request: html(page(article('attic-embedded').title, article_body(article('attic-embedded')) + '\n'
                                   + _EMBEDDED))),
    Case('attic', 'pdf', ('/attic/paper.pdf', '/attic/paper'),
         'A PDF of one page; the second URL has no extension and the type application/pdf',
         lambda request: Response(200, {'content-type': 'application/pdf'},
                                  assets.pdf_bytes('Sourdough baking paper'))),
    Case('attic', 'not-relevant', ('/attic/sitemap.xml',),
         'A sitemap that lists /attic/privacy-policy, /attic/careers, /articles/starter and /articles/steam',
         _sitemap, ('own source',)),
    Case('attic', 'privacy-policy', ('/attic/privacy-policy',),
         'A privacy policy of 250 words or more, not about baking',
         lambda request: _text_page('Privacy policy of our website', _PRIVACY), ('own source',)),
    Case('attic', 'careers', ('/attic/careers',), 'A list of open jobs of 250 words or more, not about baking',
         lambda request: _text_page('Careers: open jobs at our company', _CAREERS), ('own source',)),
    Case('attic', 'metadata', ('/attic/no-title', '/attic/og-only', '/attic/svg-image', '/attic/canonical-no-href',
                               '/attic/loaf.svg'),
         'No title element; only Open Graph tags; an og:image that is an SVG; a canonical link with no href',
         _metadata),
    Case('attic', 'other-language', ('/attic/french',), 'An article in French on the same subject',
         lambda request: html(page('Le pain au levain: les gestes de base', '\n'.join(
             f'<p>{escape(p)}</p>' for p in _FRENCH)).replace('<html lang="en">', '<html lang="fr">', 1))),
]
