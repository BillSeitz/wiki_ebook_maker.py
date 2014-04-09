"""
wiki_ebook_maker.py by BillSeitz started Oct'2013
Goal: generate an EBook from set of wiki pages (MoinMoin)
Process
 * update WikiGraph db (not in this code)
 * define chapter_pages in index.txt file - store in ebook_directory that you make beside this code
 * run other_pages_list() (on WikiGraph db server) to query WikiGraph db for related pages, add those to index.txt
 * run index_titles_gen() to create spaced-out versions of chapter names
 * manually review index.txt to cut down to list of pages to include; edit spaced-out text for odd cases (add punctuation, eliminate some caps/spaces, etc.)
 * run pages_scrape() to scrape every page, save HTML files
 * run pages_clean() to 
  * page_clean_headers(): strip headers/footers
  * page_clean_body(): clean up messy HTML (pretty specific to MoinMoin style)
  * page_clean_links(): convert HTTP links to in-links for pages included
  * page_add_twin(): add link to online-twin-page at bottom of each page
 * do something to fix weird one-word WikiNames? (no, just did a couple cases byhand)
 * generate TableOfContents index.html, manually tweak (add sections breaks, header/footer, etc.) (not in this code)
 * convert into EBook using CaLibre (EPub first, then KindLe)
"""

""" setup web.py stuff for db access """
import web
from web import utils
import config
import os

space_name = 'WebSeitzWiki'
wiki_root = 'http://webseitz.fluxent.com/wiki/'
ebook_directory = 'PrivateWikiNotebook'
chapters_file = 'index.txt'
intro_page = 'HackYourLifeWithAPrivateWikiNotebookGettingThingsDoneAndOtherSystems'
our_path = os.getcwd()

def other_pages_list(): # must run on WikiGraph/db server
    """ scrape WikiGraph for pages linked to chapter_pages to make candidate list to include in book"""
    path = os.path.join(our_path, ebook_directory)
    chapters_full = os.path.join(path, chapters_file)
    in_full = open(chapters_full, 'r')
    chapter_pages = [chapter.strip() for chapter in in_full] # as string to pass to db
    print chapter_pages
    in_full.close()
    if location == 'linode':
        pages_out = db.select('mentions', what = "DISTINCT page_mentioned", where = "space_name = $space_name AND page_name IN $chapter_pages AND page_mentioned in (SELECT name FROM pages WHERE space_name = $space_name)", vars={'space_name': space_name, 'chapter_pages': chapter_pages})
        pages_in = db.select('mentions', what = "DISTINCT page_name", where = "space_name = $space_name AND page_mentioned IN $chapter_pages", vars={'space_name': space_name, 'chapter_pages': tuple(chapter_pages)})
    else:
        print '---- no db! ----'
        return False
    other_pages = []
    for page in pages_out:
        if (page.page_mentioned not in other_pages) and (page.page_mentioned not in chapter_pages):
            other_pages.append(page.page_mentioned)
    for page in pages_in:
        if (page.page_name not in other_pages) and (page.page_name not in chapter_pages):
            other_pages.append(page.page_name)
    other_pages.sort()  
    output_full = os.path.join(path, 'other_pages.txt')
    out_f = open(chapters_full, 'a')
    for chapter in other_pages:
        out_f.write(chapter + '\n')
    print '-- Now review/change other_pages.txt --'
    return other_pages

def index_titles_gen():
    """Take index.txt list of pages and generate spaced-versions
    which I can then edit by hand for ongoing use"""
    import re
    chapters_full = os.path.join(our_path, ebook_directory, chapters_file)
    in_full = open(chapters_full, 'r')
    chapters = in_full.readlines()
    out_full = open(chapters_full, 'w')
    for chapter in chapters:
        chapter = chapter.strip()
        pat = '([a-z])([A-Z])'
        chapter_expand = re.sub(pat, r'\1 \2', chapter)
        out_full.write(chapter + ';' + chapter_expand + '\n')
        
def chapters_dict():
    """Read index.txt and parse into dictionary of pagenames and titles"""
    print 'running chapters_dict()'
    chapters_dict = {}
    chapters_full = os.path.join(our_path, ebook_directory, chapters_file)
    in_full = open(chapters_full, 'r')
    chapters = in_full.readlines()
    for chapter in chapters:
        chapter = chapter.strip()
        (pagename, page_title) = chapter.split(';')
        chapters_dict[pagename] = page_title
    return chapters_dict
        
    
def page_scrape(page_name, refetch_all=False):
    """ grab one page's HTML and write to file """
    import urllib2
    output_path = os.path.join(our_path, ebook_directory, page_name + '.html')
    if not refetch_all: # check for existing file
        if os.path.exists(output_path):
            print '-- skipping ', page_name
            return
    print 'scraping ', page_name
    page_url = wiki_root + page_name
    page_resp = urllib2.urlopen(page_url)
    page_contents = page_resp.read()
    out_f = open(output_path, 'w')
    out_f.write(page_contents)
    
def pages_scrape(refetch_all=False):
    """ grab all the pages and scrape them """
    path = os.path.join(our_path, ebook_directory)
    chapters_full = os.path.join(path, chapters_file)
    in_full = open(chapters_full, 'r')
    chapters = in_full.readlines()
    for chapter_line in chapters:
        chapter = chapter_line.strip().split(';')[0]
        page_scrape(chapter, refetch_all)

def page_clean_headers(page_name, page_contents, chapters_dict = chapters_dict()):
    """ clean 1 page's header and footers"""
    prefix = """<div id="page" lang="en" dir="ltr">
<div dir="ltr" id="content" lang="en"><span class="anchor" id="top"></span>
<span class="anchor" id="line-1"></span>"""
    suffix = """<span class="anchor" id="bottom"></span></div>"""
    title = chapters_dict[page_name]
    print 'title: ', title
    prefix_pos = page_contents.find(prefix) + len(prefix)
    if prefix_pos <= len(prefix):
        print 'bad prefix_pos'
        return page_contents
    page_contents = page_contents[prefix_pos:]
    suffix_pos = page_contents.find(suffix)
    if suffix_pos < 10:
        print 'bad suffix_pos'
    page_contents = page_contents[0:suffix_pos]
    header = """<html><head><meta http-equiv="Content-Type" content="text/html;charset=utf-8"><title>""" + title + """</title><link href="stylesheet.css" rel="stylesheet" type="text/css" /></head><body>\n"""
    title_head = "<h1>" + title + "</h1>\n"
    footer = "\n</body></html>"
    page_contents = header + title_head + page_contents + footer
    return page_contents

def page_clean_body(page_contents, chapters_dict = chapters_dict()):
    """clean body - tags, etc."""
    import re
    # clean <li><p> case
    pat = '<li><p[^>]*>'
    page_contents = re.sub(pat, '<li>', page_contents)
    # clean <li class="gap">
    pat = '<li class="gap">'
    page_contents = re.sub(pat, '<li>', page_contents)
    # remove span tags
    pat = '<span[^>]*>'
    page_contents = re.sub(pat,'', page_contents)
    pat = '</span>'
    page_contents = re.sub(pat,'', page_contents)
    # remove p class info
    pat = '<p class[^>]*>'
    page_contents = re.sub(pat, '<p>', page_contents)
    return page_contents

def wikilog_link_clean(match, chapters_dict = chapters_dict()):
    """check link against list of pages in book, output correct link type"""
    link = match.group() # whole a-href-start tag
    prefix = '<a href="'
    page_name = link[len(prefix):-2]
    #print 'page_name', page_name
    if page_name in chapters_dict.keys():
        return '<a class="inbook" href="%s.html">' % (page_name)
    else:
        return '<a class="wikilog" href="%s%s">' % (wiki_root, page_name)
    
def page_clean_links(page_contents, chapters_dict = chapters_dict()):
    """clean 1 page's links"""
    import re
    # elim 'nonexistent' hrefs
    pat = '<a class="nonexistent" href[^>]*>([^<]*)</a>'
    page_contents = re.sub(pat, r'\1', page_contents)
    # clarify interwiki links
    print 'convert interwiki links'
    pat = '<a class="interwiki" href="([^"]+)" title="([^"]+)">([^<]+)</a>'
    page_contents = re.sub(pat, r'<a class="http" href="\1">\2:\3</a>', page_contents)
    # convert WikiLog links to either http-online links or local.html links
    pat = '<a href="([^"]+)">'
    page_contents = re.sub(pat, wikilog_link_clean, page_contents)
    return page_contents
    
def page_add_twin(page_name, page_contents):
	"""add link to online-twin (plus extra closing p) at bottom of every page"""
	suffix = '</body>'
	suffix_pos = page_contents.find(suffix)
	line = '<p><a class="wikilog" href="%s%s">(Online version of page)</a><p>' % (wiki_root, page_name)
	return page_contents[0:suffix_pos] + line + page_contents[suffix_pos:]

def page_clean(page_name, chapters_dict = chapters_dict()):
    """umbrella function to call multiple cleaning functions on a page"""
    page_path = os.path.join(our_path, ebook_directory, page_name + '.html')
    page_contents = open(page_path, 'r').read()
    page_contents = page_clean_headers(page_name, page_contents, chapters_dict)
    page_contents = page_clean_body(page_contents, chapters_dict)
    page_contents = page_clean_links(page_contents, chapters_dict)
    page_contents = page_add_twin(page_name, page_contents)
    out_f = open(page_path, 'w')
    out_f.write(page_contents)
    
def pages_clean():
    """ grab all the pages listed in index.txt and clean them """
    for page_name in chapters_dict().keys():
        print 'cleaning ', page_name
        page_clean(page_name)
        
        
if __name__ == '__main__':
    #other_pages_list()
    #index_titles_gen()
    #page_scrape('HackYourLifeWithAPrivateWikiNotebookGettingThingsDoneAndOtherSystems')
    #page_scrape('PickingAWikiForYourPrivateNotebook')
    #pages_scrape()
    #page_clean_headers('TellYourLifeStoryThroughVariousFilters')
    #page_clean('PickingAWikiForYourPrivateNotebook')
    #pages_clean()
    
    

