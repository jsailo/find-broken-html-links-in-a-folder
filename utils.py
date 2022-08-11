from bs4 import BeautifulSoup
import re


def get_links_from_html(html):
    def get_link(el):
        return el["href"]

    return list(map(get_link, BeautifulSoup(html, features="html.parser").select("a[href]")))

def url_is_media_file(url):
    media_extensions = ['jpg', 'jpeg', 'png']
    return url.split('.')[-1] in media_extensions

def url_is_javascript(url):
    return "javascript:" in url

def url_is_mail(url):
    return url.startswith("mailto:")

def is_valid_link(url):
    return not any([
        url_is_javascript(url),
        url_is_media_file(url),
        url_is_mail(url)
    ])

def get_not_found_links_for_html(html, file_path):
    not_found_links = []
    links = get_links_from_html(html)
    for link in links:
        link_path = (file_path.parent/link).absolute()
        if not link_path.exists():
            not_found_links.append(link)
    return not_found_links

def get_unclosed_links_for_html(html):
    openings = list(re.finditer("<a ", html))
    closings = list(re.finditer("</a>", html))

    if len(openings) == len(closings):
        return []

    closings = iter(closings)

    unclosed_openings = []
    try:
        closing = next(closings)
    except StopIteration:
        closing = None

    if closing:
        for opening, next_opening in zip(openings, openings[1:]):
            if opening.start() < closing.start() and next_opening.start() > closing.start():
                try:
                    closing = next(closings)
                except StopIteration:
                    pass
            else:
                unclosed_openings.append(opening)

    if not closing:
        unclosed_openings.extend(openings)
    elif openings[-1].start() > closing.start():
        unclosed_openings.append(openings[-1])
    invalid_links = []
    for opening in unclosed_openings:
        from_link_html = html[opening.start():]
        closing_bracket = re.search('>', from_link_html)
        invalid_links.extend(get_links_from_html(from_link_html[:closing_bracket.end()]))
    return invalid_links
