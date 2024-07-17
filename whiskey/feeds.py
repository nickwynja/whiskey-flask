from whiskey import app, flatpages, helpers
import urllib.parse
import glob
import datetime
import os
import pypandoc
import feedparser
from flask import url_for, Response, redirect, send_from_directory
from pytz import timezone
from feedgen.feed import FeedGenerator
from pathlib import Path
import hashlib


@app.route('/rss')
@app.route('/feed')
@app.route('/feed.rss')
def feed_redirect():
    return redirect(url_for('feed'), code=301)

@app.route('/feed.xml')
def feed():
    tz = app.config['TIMEZONE']
    posts = helpers.get_posts()

    feed = FeedGenerator()
    feed.title('%s' % app.config['TITLE'])
    feed.link(href=app.config['BASE_URL'], rel='self')
    feed.subtitle(app.config.get('DESCRIPTION', ""))
    feed.author(name=app.config.get('AUTHOR', ""))

    for p in posts[:10]:
        post = flatpages.get(p.path)
        if ('POST_LINK_STYLE' in app.config
                and app.config['POST_LINK_STYLE'] == "date"):
            url = "%s/%s" % (app.config['BASE_URL'], p.slug)
        else:
            url = "{}{}".format(
                app.config['BASE_URL'],
                url_for('nested_content', name=p.slug,
                        dir=app.config['POST_DIRECTORY'], ext='html'))

        entry = feed.add_entry()
        entry.title(p.meta['title'])
        entry.guid(guid=url, permalink=True)
        entry.author(name=p.meta.get('author', app.config.get('AUTHOR', "")))
        entry.link(href=url)
        entry.updated(timezone(tz).localize(
            p.meta.get('updated', p.meta['date'])))
        entry.published(timezone(tz).localize(p.meta['date']))
        entry.description(post.meta.get('description', ''))
        # It takes a while to render all of the HTML here but
        # then at least it is in memory and the rest of the
        # build process goes quickly. The rendering has to
        # happen anyway so there isn't any performance increase
        # by not including the full HTML here in content.
        entry.content(post.html)

    return Response(feed.rss_str(pretty=True), mimetype="application/rss+xml")

@app.route('/log.xml')
def log():
    files = sorted(glob.glob("./content/data/log/*"))
    page = flatpages.get("log")
    cache_name = "log.xml"

    p = []

    for file in files:
        with open(file) as f:
            p.append({
                "filename": f.name,
                "date": Path(f.name).stem,
                "content": f.read(),
                })


    latest_hash = hashlib.md5(str(p).encode()).hexdigest()

    try:
        cached_xml = feedparser.parse(f"{app.config['STATIC_FOLDER']}/{cache_name}")
        cached_hash = cached_xml['feed']['generator'].split(":")[1]
    except KeyError as e:
        cached_hash = None

    if latest_hash != cached_hash:
        feed = FeedGenerator()
        feed.title(f"{app.config.get('AUTHOR')}'s Log")
        feed.link(href=app.config['BASE_URL'] + "/log.html", rel='self')
        feed.subtitle(page.meta.get('description', app.config.get("DESCRIPTION")))
        feed.author(name=app.config.get('AUTHOR', ""))
        feed.id(feed.title())
        feed.generator(generator=f"whiskey-feed-cache:{latest_hash}")

        for i in reversed(p):
            entry = feed.add_entry()
            entry.id(i['date'].split("-")[0])
            entry.published(i['date'])
            entry.author(name=app.config.get('AUTHOR', ""))
            if Path(i['filename']).suffix == ".md":
                entry.content(pypandoc.convert_text(
                    i['content'],
                    'html',
                    format='md',
                    extra_args=app.config['PANDOC_ARGS']
                    ), type="html")



            else:
                entry.content(i['content'], type="html")

        feed.rss_file(f"{app.config['STATIC_FOLDER']}/{cache_name}", pretty=True)

    return send_from_directory(
        app.config['STATIC_FOLDER'],
        cache_name,
        mimetype="application/rss+xml"
    )
