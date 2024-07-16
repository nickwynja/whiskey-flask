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
    feed.link(href=app.config['BASE_URL'] + url_for('feed'), rel='self')
    feed.subtitle(app.config.get('DESCRIPTION', ""))
    feed.author(name=app.config.get('AUTHOR', ""))
    feed.link(href=app.config['BASE_URL'], rel='alternate')

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
    cache_name = "log.xml"

    p = []

    for file in files:
        with open(file) as f:
            d = Path(f.name).stem
            t = datetime.datetime.strptime(d, '%Y%m%d%H%M%S%z')
            l = f.read()
            i = {
                    "filename": f.name,
                    "date": d,
                    "timestamp": t,
                    "content": l,
                }
            p.append(i)

    try:
        latest_post = p[-1]['timestamp']
    except (KeyError, IndexError) as e:
        latest_post = None

    try:
        cached_xml = feedparser.parse(f"{app.config['STATIC_FOLDER']}/{cache_name}")
        cached_time = datetime.datetime.strptime(cached_xml['feed']['updated'], "%a, %d %b %Y %H:%M:%S %z")
    except KeyError as e:
        cached_time = None

    if (
            cached_time is None
            or latest_post is None
            or latest_post > cached_time):

        ## update feed
        feed = FeedGenerator()
        feed.title(f"{app.config.get('AUTHOR')}'s Log")
        feed.link(href=app.config['BASE_URL'] + url_for('log'), rel='self')
        feed.subtitle(app.config.get('DESCRIPTION', ""))
        feed.author(name=app.config.get('AUTHOR', ""))
        feed.id(feed.title())
        feed.link(href=app.config['BASE_URL'], rel='alternate')
        feed.lastBuildDate(latest_post)


        for i in p:
            entry = feed.add_entry()
            entry.id(i['date'].split("-")[0])
            entry.published(i['timestamp'])
            entry.author(name=app.config.get('AUTHOR', ""))
            if Path(i['filename']).suffix == ".md":
                entry.content(pypandoc.convert_text(i['content'], 'html', format='md'), type="html")
            else:
                entry.content(i['content'], type="html")

        feed.rss_file(f"{app.config['STATIC_FOLDER']}/{cache_name}", pretty=True)

    return send_from_directory(
        app.config['STATIC_FOLDER'],
        cache_name,
        mimetype="application/rss+xml"
    )
