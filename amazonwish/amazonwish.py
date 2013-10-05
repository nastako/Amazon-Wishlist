# -*- coding: utf-8 -*-
# Copyright (C) 2012 - Caio Begotti <caio1982@gmail.com>
# Distributed under the GPLv2, see the LICENSE file.

"""
Python version of the old and buggy Perl module WWW::Amazon::Wishlist.
It's written using LXML and XPaths for better readability. It supports the
Amazon stores in the US, Canda, UK, France, Spain, Italy, Germany, Japan, China
and India. Brazilian and Mexican stores also have built-in support though
they are not live yet.

You need to load the parameters of stores up before using this module:

>>> from amazonwish.config import country_params
"""

__author__ = "Caio Begotti <caio1982@gmail.com>"

import locale
import config

from lxml import etree
from lxml.html import tostring, fromstring

# only for charset detection, enforcing unicode
# when lxml is completely shitty in doing that!
from BeautifulSoup import UnicodeDammit

# that's a nice hack isn't it? i hate it
def _decoder(data):
    """Simple helper to enforce a decent charset handling."""
    converted = UnicodeDammit(data, isHTML=True)
    if not converted.unicode:
        raise UnicodeDecodeError("Failed to detect encoding, tried [%s]", ', '.join(converted.triedEncodings))
    return converted.unicode

def _parser(url):
    """Simple helper function to parse a document, returning its etree."""
    parser = etree.HTMLParser()
    try:
        page = etree.parse(url, parser)
    except IOError:
        raise IOError("Failed to download page data, check your connection")
    decoded = _decoder(tostring(page))
    tree = fromstring(decoded)
    return tree

def _stripper(string):
    """Simple string helper to get rid of nasty chars detected in tests."""
    known = [u'\u200b',
             u'\x81\x8f',
             u'\xef\xbf',
             u'\xa5']
    for char in known:
        string = string.replace(char, '')
    return string.strip()

def _read_config(country):
    """Simple helper to return the configuration dictionaries of the module"""
    return config.country_params(country)

class Search():
    """
    The Search() class is the one to be used if you don't know an
    user's wishlist ID and need to look them up by e-mail or their name.
    
    >>> from amazonwish.amazonwish import Search
    >>> search = Search('begotti', country='us')
    """
    def __init__(self, name, country):
        params = _read_config(country)
        self.currency = params['currency']
        self.domain = params['domain']
        self.symbol = params['symbol']
        self.name = name
        self.country = country
        self.page = None
        self._download()

    def _download(self):
        """Builds a search query and retrieves its result for the parser."""
        query = ['/gp/registry/search.html?',
               'ie=UTF8',
               '&type=wishlist',
               '&field-name=',
               self.name]
        url = 'http://www.amazon' + self.domain + ''.join(query)
        self.page = _parser(url)

    def list(self):
        """
        Returns a list with tuples containing all matching usernames
        and their main wishlist ID, with which you can get secondary
        lists via the Wishlist() class.
        
        >>> wishlists = search.list()
        >>> for row in wishlists:
        >>>     print row
        """
        # before pipe, page with usernames; after, single exact matches
        wishlists = self.page.xpath("//td/span/a//@href | //div[@id='sortbarDisplay']/form//@action")
        names = self.page.xpath("//td/span/a//text() | //h1[@class='visitor']//text()")
        names = [_stripper(n) for n in names]

        codes = []
        for code in wishlists:
            codes.append(_stripper(code.split('/')[3]))
        # FIXME: hack not to return empty search results,
        # whose only anchor text is not english
        if not 'tg' in codes:
            return zip(names, codes)


class Profile():
    """
    The Profile() class is the one responsible for retrieving
    information about a given user, such as name, profile photo,
    existing wishlists and their names and size.

    >>> from amazonwish.amazonwish import Profile
    >>> person = Profile('3MCYFXCFDH4FA', country='us')
    """

    def __init__(self, userid, country):
        params = _read_config(country)
        self.currency = params['currency']
        self.domain = params['domain']
        self.symbol = params['symbol']
        self.userid = userid
        self.country = country
        self.page = None
        self._download()

    def _download(self):
        """
        Retrieves and stores the profile page (i.e. first wishlist
        page plus user's information and other wishlists details).
        """
        url = 'http://www.amazon' + self.domain + '/wishlist/' + self.userid
        self.page = _parser(url)
    
    def basic_info(self):
        """
        Returns the name of the wishlist owner and, if available,
        the address of its profile picture.

        >>> info = person.basic_info()
        """
        # wishlists are supposed to show a first name, so it's safe to assume it will never be null
        namefields = self.page.xpath("//td[@id='profile-name-Field']")
        ret = []
        for name in namefields:
            ret.append(_stripper(name.text))
        photo = self.page.xpath("//div[@id='profile']/div/img/@src")
        if photo:
            filename = photo[0].split('.')
            filename = '.'.join(filename[:-2]) + '.' + filename[-1]
            ret.append(_stripper(filename))
        return ret

    def wishlists(self):
        """Returns a list of wishlists codes for a given person.

        >>> lists = person.wishlists()
        """
        lists = self.page.xpath("//div[@id='profile']/div[@id='regListpublicBlock']/div/h3/a//text()")
        return lists

    def wishlists_details(self):
        """
        Returns a tuple with lists, the first with all wishlists
        codes and the second with their total number of items
        (i.e. wishlist size).

        >>> details = person.wishlists_details()
        """
        retcodes = []
        retsizes = []
        codes = self.page.xpath("//div[@id='profile']/div[@id='regListpublicBlock']/div/@id")
        for code in codes:
            retcodes.append(_stripper(code.replace('regListsList','')))
        sizes = self.page.xpath("//div[@id='profile']/div[@id='regListpublicBlock']/div/div/span[1]")
        for size in sizes:
            retsizes.append(_stripper(size.text))
        return retcodes, retsizes


class Wishlist():
    """
    The Wishlist() class is the main class of Amazon Wishlist as
    it's here where the magic happens. This class will retrieve
    through XPATH expressions the titles of all items inside a
    wishlist, their authors and co-writers, price tags, covers
    (if books) or items picture, list which external sources your
    wishlist uses and even the total amount necessary if you were
    to buy all the items at once.

    >>> from amazonwish.amazonwish import Wishlist
    >>> wishlist = Wishlist('3MCYFXCFDH4FA', country='us')
    """

    def __init__(self, userid, country):
        params = _read_config(country)
        self.currency = params['currency']
        self.domain = params['domain']
        self.symbol = params['symbol']
        self.userid = userid
        self.country = country
        self.page = None
        self._download()
        
    def _download(self):
        """Retrieves and stores the printable version of the wishlist for later usage."""
        query = ['/ref=cm_wl_act_print_o?',
                 '_encoding=UTF8',
                 '&layout=standard-print',
                 '&disableNav=1',
                 '&visitor-view=1',
                 '&items-per-page=9999']
        url = 'http://www.amazon' + self.domain + '/wishlist/' + self.userid + ''.join(query)
        self.page = _parser(url)

    def authors(self):
        """Returns the authors names and co-writers for every item.
        
        >>> authors = wishlist.authors()
        """
        authors = self.page.xpath("//div[@class='pTitle']")
        attr = ('de ', 'di ', 'by ', 'von ')
        ret = []
        for author in authors:
            subtree = tostring(author, encoding='unicode', method='html', pretty_print=True)
            if 'span' in subtree:
                parser = etree.HTMLParser()
                div = etree.fromstring(subtree, parser)
                res = div.xpath("//span[@class='small itemByline']//text()")
                for author in res:
                    author = author.replace('~','').strip()
                    if author.startswith(tuple(attr)):
                        author = author[3:].strip()
                        ret.append(_stripper(author))
                    else:
                        ret.append(_stripper(author))
            else:
                ret.append(ur'')
        dirt = ['DVD','VHS']
        for item in dirt:
            while item in ret:
                ret.remove(item)
        return ret
    
    def titles(self):
        """
        Returns items titles, even if they are pretty long
        ones (like academic books or journals).
        
        >>> titles = wishlist.titles()
        """
        titles = self.page.xpath("//div[@class='pTitle']/strong//text()")
        ret = []
        for title in titles:
            ret.append(_stripper(title))
        return ret
    
    def prices(self):
        """Returns the price tags for every item in a wishlist.
        
        >>> prices = wishlist.prices()
        """
        prices = self.page.xpath("//td[@class='pPrice'][not(text()) and not(strong)] | //td[@class='pPrice']/strong[3] | //td[@class='pPrice']/strong[1] | //td[@class='Price']/span/strong//text()")

        # cleanups
        if 'EUR' in self.currency:
            dust = 'EUR'
        elif 'CDN' in self.currency:
            dust = 'CDN' + ur'\u0024'
        elif 'GBP' in self.currency:
            dust = ur'\u00a3'
        elif 'INR' in self.currency:
            dust = 'Rs. '
        elif 'CNY' in self.currency:
            dust = u'\xa5'
        elif 'JPY' in self.currency:
            dust = u'\x81\x8f'
        else:
            dust = self.symbol
        
        ret = []
        for price in prices:
            res = tostring(price, encoding='unicode', method='text', pretty_print=True).strip()
            if 'At' not in res:
                # TODO: how would it work out for non-english stores? quite a huge bug ahead...
                if 'Click' in res:
                    res = ''
                if 'EUR' in self.currency or 'BRL' in self.currency:
                    res = res.replace(dust, '')
                    res = res.replace('.', '')
                    res = res.replace(',', '.')
                else:
                    res = res.replace(dust, '')
                    res = res.replace(',', '')
                ret.append(_stripper(res))
        return ret
    
    def via(self):
        """
        Returns the sorted original web pages from which the wished item was
        pulled, only for Universal items not from Amazon directly.
        
        >>> via = wishlist.via()
        """
        sources = self.page.xpath("//div/form/table/tbody[*]/tr[*]/td[*]/strong[2]")
        ret = []
        for url in sources:
            ret.append(_stripper(url.text))
        ret = sorted(list(set(ret)))
        return ret
    
    def covers(self):
        """Returns the addresses of items pictures (e.g. book covers, albums pictures).
        
        >>> covers = wishlist.covers()
        """
        covers = self.page.xpath("//div/form/table/tbody[*]/tr[*]/td[*]/div[@class='pImage']/img/@src")
        ret = []
        for filename in covers:
            filename = filename.split('.')
            filename = '.'.join(filename[:-2]) + '.' + filename[-1]
            ret.append(_stripper(filename))
        return ret
   
    def urls(self):
        """Returns the page address of a given item in the wishlist, with its full details.
        
        >>> urls = wishlist.urls()
        """
        urls = self.page.xpath("//tbody[@class='itemWrapper']//@name")
        ret = []
        for url in urls:
            if 'item' in url:
                code = url.split('.')[3]
                if code:
                    res = 'http://www.amazon' + self.domain + '/dp/' + code
                else:
                    res = ''
                ret.append(_stripper(res))
        return ret

    def ideas(self):
        """Returs a list of ideas to shop for later, as reminders
        
        >>> ideas = wishlist.ideas()
        """
        ret = []
        titles = self.titles()
        prices = self.prices()
        rows = zip(titles, prices)
        for row in rows:
            if "Idea" in row[1]:
                ret.append(_stripper(row[0]))
        return ret 

    def total_expenses(self):
        """
        Returns the total sum of all prices, without currency symbols,
        might excluse unavailable items or items without price tags.
        
        >>> total = wishlist.total_expenses()
        """
        tags = []
        prices = self.prices()
        for tag in prices:
            if "Idea" in tag:
                prices.remove(tag)
        for price in filter(None, prices):
            if price.count('.') > 1:
                price = price.replace('.', '', (price.count('.') - 1))
            tags.append(float(price))
        ret = sum(tags)

        if 'EUR' in self.currency or 'BRL' in self.currency:
            locale.setlocale(locale.LC_MONETARY, 'de_DE.UTF-8')
        else:
            locale.setlocale(locale.LC_MONETARY, 'en_US.UTF-8')

        return locale.currency(ret, grouping=True, symbol=False)
