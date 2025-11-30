from bs4 import BeautifulSoup
from django import template
from markdown import markdown

register = template.Library()


@register.filter
def markdownify(md):
    return markdown(md, extensions=["tables"])


@register.filter
def textify(html):
    return BeautifulSoup(html, "html.parser").get_text()
