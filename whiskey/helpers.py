import yaml
import glob
import os
import tarfile
import pypandoc
import datetime
import shutil
import json
import re
from flask import abort
from flask_babel import format_datetime
from whiskey import app, flatpages
from pathlib import Path
from webdav3.client import Client
from webdav3.exceptions import RemoteResourceNotFound
from rclone_python import rclone
from rclone_python.remote_types import RemoteTypes


def get_posts():
    '''returns list of published posts ordered newest first'''
    all_posts = []
    posts = [p for p in flatpages
        if (p.path.startswith(app.config['POST_DIRECTORY'])
            and is_published(p)
            and not is_archived(p))]
    posts.sort(key=lambda item: item['date'], reverse=True)
    for p in posts:
        d = os.path.dirname(p.path)
        slug = os.path.basename(p.path)
        if re.compile(r'\d{4}').search(d):
            path = d.removeprefix(app.config['POST_DIRECTORY'])
        else:
            path = app.config['POST_DIRECTORY']

        setattr(p, 'page_path', path)
        setattr(p, 'slug', slug)
        setattr(p, 'year', p['date'].strftime('%Y'))
        all_posts.append(p)
    return all_posts


def get_featured_posts(posts):
    '''returns list of posts marked `featured` in post metadata'''
    return [p for p in posts if p.meta and p.meta.get('featured', False) is True]


def pandoc_markdown(md):
    return pypandoc.convert_text(
        md,
        'html',
        format='md',
        filters=app.config['PANDOC_FILTERS']
    )

def get_latest_log():
    files = sorted(glob.glob(f"{app.config['DATA_PATH']}/log/*"))

    if len(files) == 0:
        return (None, None)

    with open(files[-1], 'r') as f:
        date = Path(f.name).stem
        content = f.read()
        if Path(f.name).suffix == ".md":
            entry = pypandoc.convert_text(
                    content,
                    'html',
                    format='md',
                    extra_args=app.config['PANDOC_ARGS']
                    )
        else:
            entry = l

    return (date,entry)

def format_date(value):
    '''takes a date obj and returns in November 22, 2016 format'''
    return format_datetime(value, 'LLLL d, yyyy')


def format_month_year(value):
    '''takes a date obj and returns in November 2016 format'''
    return format_datetime(value, 'LLLL yyyy')

def format_date_tz(value):
    date = datetime.datetime.strptime(value, '%Y%m%d%H%M%S%z')
    return date.strftime("<span class='date'>%B %-d, %Y</span> <span class='time'>%H:%M %z</span>")

def is_published(post):
    '''returns True/False based on `published` metadata in post'''
    return post and 'published' in post.meta and post.meta['published'] is True


def is_archived(post):
    '''returns True/False based on `hidden` metadata in post'''
    return post and 'archived' in post.meta and post.meta['archived'] is True


def is_published_or_draft(post):
    '''returns True/False based on `published` metadata in post'''
    if (post is not None
            and (post.meta.get('published', False) is True
                 or post.meta.get('status', "").lower() == "draft"
                 )):
        return post


def is_draft(post):
    '''returns True/False based on `published` metadata in post'''
    if (post is not None
            and (('published' in post.meta
                  and post.meta['published'] is False)
                 or ('status' in post.meta
                     and post.meta['status'].lower() == "draft")
                 or ('published' not in post.meta))):
        return post


def list_files_in_dir(dir, root_only=None):
    pages = []
    files_to_yield = []
    if root_only:
        files = glob.glob("%s/*.md" % dir)
        files.extend(glob.glob("%s/*.txt" % dir))
        files.extend(glob.glob("%s/*.pdf" % dir))
    else:
        files = glob.glob("%s/**/*.md" % dir, recursive=True)
        files.extend(glob.glob("%s/**/*.txt" % dir, recursive=True))
        files.extend(glob.glob("%s/**/*.epub" % dir, recursive=True))
        files.extend(glob.glob("%s/**/*.pdf" % dir, recursive=True))
    for file in files:
        files_to_yield.append(file.replace('%s/' % dir, ''))
    for page in files_to_yield:
        path, filename = os.path.split(page)
        name, extension = filename.split('.')[-2:]
        if extension == 'md':
            if path:
                p = flatpages.get("%s/%s" % (path, name))
            elif name != "index":  # Don't include or it'll override actual
                p = flatpages.get("%s" % (name))
            else:
                p = None
            if p and is_published(p):
                if ('POST_LINK_STYLE' in app.config
                        and app.config['POST_LINK_STYLE'] == "date"
                        and path.startswith(app.config['POST_DIRECTORY'])):
                    path = path.replace("%s/" % app.config['POST_DIRECTORY'],
                                        '')
                pages.append({'name': name, 'dir': path, 'ext': 'html'})
                pages.append({'name': name, 'dir': path, 'ext': 'md'})
        else:
            pages.append({'name': name, 'dir': path, 'ext': extension})
    return pages


def get_flatfile_or_404(file):
    if os.path.isfile(file):
        with open(file, 'r') as f:
            content = f.read()
        return content, 200, {'Content-Type': 'text/plain; charset=utf-8'}
    else:
        abort(404)


def make_tarfile(output_filename, source_dir):
    with tarfile.open(output_filename, "w:gz") as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))


def pull_content():
    client = Client(app.config["WEBDAV_ARGS"])
    status = get_sync_status()

    try:
        os.mkdir(app.config['CONTENT_PATH'])
    except FileExistsError:
        pass

    if app.config['CONTENT_IN_PROGRESS'] is not True:
        init_pull_config()
        file_list = []
        try:
            all_files = client.list(app.config["WEBDAV_DIR"],
                                    get_info=True,
                                    recursive=True,
                                    )
        except RemoteResourceNotFound as e:
            app.config["CONTENT_IN_PROGRESS"] = False
            app.logger.error(e)
            return False


        for f in all_files:
            if f['isdir'] is False:
                if status["CONTENT_LAST_PULL"] is not None:
                    date_modified = datetime.datetime.strptime(
                            f['modified'], "%a, %d %b %Y %H:%M:%S %Z")
                    # get everything with changes within the last 1h to avoid races
                    if date_modified > (status["CONTENT_LAST_PULL"] - datetime.timedelta(hours=1)):
                        app.logger.debug(f"{f['name']} modified at {date_modified}")
                        file_list.append(f)
                else:
                    file_list.append(f)
            else:
                dir_name = f['path'].removeprefix("/" + app.config["WEBDAV_DIR"])

                try:
                    os.mkdir(app.config["CONTENT_PATH"] + dir_name)
                except FileExistsError:
                    pass

        file_list.sort(key=lambda f: f['modified'], reverse=True)

        if file_list != []:
            from multiprocessing.dummy import Pool as ThreadPool
            pool = ThreadPool(4)
            results = pool.map(download_item, file_list)
            app.logger.info(f"pull complete")
        else:
            app.logger.info("no content changes to pull")


        close_pull_config()


def download_item(item):
    client = Client(app.config["WEBDAV_ARGS"])

    rel_path = item['path'].removeprefix(
            "/" + app.config["WEBDAV_DIR"])

    local_path = app.config['CONTENT_PATH'] + rel_path

    app.logger.debug(f"downloading {rel_path}")

    kwargs = {
            'remote_path': item['path'],
            'local_path':  local_path,
            }
    client.download_sync(**kwargs)
    flatpages.reload()
    return True

def get_all_remote_files():
    client = Client(app.config["WEBDAV_ARGS"])
    file_list = []

    try:
        all_files = client.list(app.config["WEBDAV_DIR"],
                                get_info=True,
                                recursive=True,
                                )
    except RemoteResourceNotFound as e:
        app.logger.error(e)
        return []

    for f in all_files:
        if f['isdir'] is False:
            file_list.append(f['path'].removeprefix("/" + app.config["WEBDAV_DIR"]))
    return file_list


def store_sync_status():
    with open (f"{app.config['SITE_PATH']}/sync.json", 'w') as conf:
        conf.write(json.dumps({
            "CONTENT_LAST_PULL": str(app.config["CONTENT_LAST_PULL"]),
            "INITIAL_CONTENT_PULLED": app.config["INITIAL_CONTENT_PULLED"],
            }))

def get_sync_status():
    default_status =  {
            "CONTENT_LAST_PULL": app.config["CONTENT_LAST_PULL"],
            "INITIAL_CONTENT_PULLED": app.config["INITIAL_CONTENT_PULLED"],
            }

    try:
        with open (f"{app.config['SITE_PATH']}/sync.json", 'r') as conf:
            f = conf.read()
            if f:
                status = json.loads(f)
                status["CONTENT_LAST_PULL"] = datetime.datetime.strptime(
                        status["CONTENT_LAST_PULL"],
                        "%Y-%m-%d %H:%M:%S.%f")
                return status
            else:
                return default_status
    except FileNotFoundError as e:
        app.logger.info("no sync status yet")
        return default_status

def init_pull_config():
    status = get_sync_status()
    app.logger.info("pull initiated")
    app.config["INITIAL_CONTENT_PULLED"] = False
    app.config["CONTENT_IN_PROGRESS"] = True
    app.logger.debug(f"last pull at: {status['CONTENT_LAST_PULL']}")

def close_pull_config():
    app.config["CONTENT_LAST_PULL"] = datetime.datetime.utcnow()
    app.config["INITIAL_CONTENT_PULLED"] = True
    app.config["CONTENT_IN_PROGRESS"] = False
    store_sync_status()

def rclone_content():
    if app.config['CONTENT_IN_PROGRESS'] is not True:
        init_pull_config()

        rclone.copy(
                f"fastmail:{app.config['WEBDAV_DIR']}",
                app.config['CONTENT_PATH'],
                ignore_existing=True, args=['--create-empty-src-dirs'])

        app.logger.info(f"pull complete")
        flatpages.reload()
        close_pull_config()
