from flask import render_template, abort, send_from_directory, request, Response, redirect
import os
import re
import mimetypes
import threading
import pypandoc
import yaml
import glob
import datetime
import hashlib
from pathlib import Path
from rclone_python import rclone
from random import randrange
from xhtml2pdf import pisa
import ttf_opensans
from whiskey import app, flatpages

from whiskey import helpers


@app.context_processor
def inject_mode():
    return dict(editing=app.debug)

@app.context_processor
def inject_deployment():
    return dict(
            deploy_id=os.environ.get('RAILWAY_DEPLOYMENT_ID', randrange(999999))
            )

@app.after_request
def add_header(response):
    if 'Cache-Control' not in response.headers:
        response.headers['Cache-Control'] = 'no-cache'
    return response

@app.route("/")
def index():
    if app.config['SITE_STYLE'] == "static":
        p = flatpages.get("index")
        return render_template('index_static.html', post=p, site=app.config)
    elif app.config['SITE_STYLE'] == "hybrid":
        page = flatpages.get("index")
        ap = helpers.get_posts()
        fp = helpers.get_featured_posts(ap)
        featured_posts = fp[:int(app.config['FEATURED_POSTS_COUNT'])]
        all_posts = ap[:int(app.config['RECENT_POSTS_COUNT'])]
        return render_template('index_hybrid.html',
                               post=page,
                               directory=app.config['POST_DIRECTORY'],
                               featured_posts=featured_posts,
                               all_posts=all_posts,
                               site=app.config
                               )
    elif app.config['SITE_STYLE'] == "blog":
        ap = helpers.get_posts()
        p = helpers.get_featured_posts(ap)
        featured_posts = p[:int(app.config['FEATURED_POSTS_COUNT'])]
        all_posts = ap[:int(app.config['RECENT_POSTS_COUNT'])]
        return render_template('index_list.html',
                               directory=app.config['POST_DIRECTORY'],
                               featured_posts=featured_posts,
                               all_posts=all_posts, site=app.config)
    else:
        abort(404)


@app.route('/<int:year>/<int:month>/<name>.<ext>')
@app.route('/<dir>/<name>.<ext>')
def nested_content(name, ext, dir=None, year=None, month=None):
    if dir:
        path = dir
    else:
        dir = app.config['POST_DIRECTORY']
        if year and month:
            month = "{:02d}".format(month)
            path = '%s/%s/%s' % (dir, year, month)
    if ext == "html":
        if os.path.isfile('%s/%s/%s.%s' % (
                app.config['CONTENT_PATH'], path, name, ext)):
            return send_from_directory('%s/%s' % (
                app.config['CONTENT_PATH'], dir), '%s.%s' % (name, ext))
        else:
            page = flatpages.get(f"{path}/{name}")
            if helpers.is_published_or_draft(page):
                if dir == app.config['POST_DIRECTORY']:
                    return render_template('post.html', post=page,
                                           directory=dir, ext=ext,
                                           site=app.config)
                else:
                    if ('templateType' in page.meta
                            and page.meta['templateType'] == "post"):
                        template_type = "post.html"
                    else:
                        template_type = "page.html"

                    return render_template(template_type, post=page,
                                           directory=dir, ext=ext,
                                           site=app.config)
            else:
                abort(404)
    else:
        local_path = path
        path = "{}/{}".format(app.config['CONTENT_PATH'], path)
        filename = "{}.{}".format(name, ext)
        file = '{}/{}'.format(path, filename)
        if ext  == "md":
            page = flatpages.get(f"{local_path}/{name}")
            content =  pypandoc.convert_text(
                page.body,
                'gfm',
                format='markdown-smart',
                extra_args=app.config['PANDOC_ARGS']
            )
            return content, 200, {'Content-Type': 'text/plain; charset=utf-8'}

        elif ext == "txt":
            return helpers.get_flatfile_or_404(file)
        else:
            try:
                return send_from_directory(path, filename, as_attachment=True)
            except:
                abort(404)

@app.route('/cv.html')
def cv():
    with open(app.config['CONTENT_PATH'] + "/data/cv.yaml", "r") as stream:
        cv = yaml.safe_load(stream)

    return render_template("cv.html", cv=cv, site=app.config)

@app.route('/resume.pdf')
def resume():
    try:
        with open(app.config['CONTENT_PATH'] + "/data/cv.yaml", "r") as stream:
            cv = yaml.safe_load(stream)
    except:
        abort(404)

    source_html = render_template("resume.html",
                                  cv=cv,
                                  font=ttf_opensans
                                  )

    output_filename = f"{app.config['STATIC_FOLDER']}/cv.pdf"
    result_file = open(output_filename, "w+b")
    pisa_status = pisa.CreatePDF(source_html, dest=result_file)
    result_file.close()

    return send_from_directory(
        app.config['STATIC_FOLDER'], '%s.%s' % ("cv", "pdf")
    )

@app.route("/reading.html")
def reading_index():
    page = flatpages.get("reading")

    read = []

    reading_years = sorted(glob.glob(f"{app.config['DATA_PATH']}/reading-20*"))

    for y in reading_years:
        path = Path(y)
        year = path.stem.removeprefix("reading-")
        with open(y, "r") as f:
            r = yaml.safe_load(f)
        read.append({"year": year,
                    "books": r['books'],
                    "overview": r['overview']
                     })

    with open(app.config['CONTENT_PATH'] + "/data/reading-history.yaml", "r") as stream:
        history = yaml.safe_load(stream)

    return render_template('reading.html', page=page, read=read, history=history,
                           site=app.config)

@app.route('/<name>.<ext>')
def page(name, ext):
    if ext == "html":
        p = flatpages.get(name)
        if helpers.is_published(p):
            if 'footer' in p.meta:
                setattr(p, 'footer', helpers.pandoc_markdown(p.meta['footer']))
            return render_template('page.html', post=p, site=app.config)
        else:
            abort(404)
    elif ext  == "md":
        page = flatpages.get(name)
        content =  pypandoc.convert_text(
                page.body,
                'gfm',
                format='markdown-smart',
                extra_args=app.config['PANDOC_ARGS']
                )
        return content, 200, {'Content-Type': 'text/plain; charset=utf-8'}

    elif ext == "txt":
        file = '{}/{}.{}'.format(
                app.config['CONTENT_PATH'],
                name,
                ext)
        return helpers.get_flatfile_or_404(file)
    else:
        return send_from_directory(
            app.config['CONTENT_PATH'], '%s.%s' % (name, ext)
        )


if app.config['SITE_STYLE'] in ("blog", "hybrid"):

    @app.route("/log.html")
    def log_index():
        page = flatpages.get("log")
        date, entry = helpers.get_latest_log()

        if not entry:
            abort(404)

        return render_template('log.html', page=page, entry=entry, date=date,
                               site=app.config)

    @app.route("/log.txt")
    def log_txt():
        files = sorted(glob.glob("./content/data/log/*"))
        entries = []
        formatted = []


        for file in files:
            with open(file) as f:
                entries.append({
                    'date': datetime.datetime.strptime(Path(f.name).stem, '%Y%m%d%H%M%S%z'),
                    'filename': f.name,
                    'text': f.read(),
                    })

        latest_hash = hashlib.md5(str(entries).encode()).hexdigest()
        cached_txt = f"{app.config['STATIC_FOLDER']}/log.txt.{latest_hash}"

        if os.path.isfile(cached_txt):
            with open(cached_txt) as f:
                txt = f.read()
            return txt, 200, {'Content-Type': 'text/plain; charset=utf-8'}
        else:
            for e in entries:
                if Path(e['filename']).suffix == ".md":
                    t = pypandoc.convert_text(
                            e['text'],
                            'markdown_github',
                            format='markdown',
                            extra_args=app.config['PANDOC_ARGS']
                            )
                else:
                    t = pypandoc.convert_text(
                            e['text'],
                            'markdown_github',
                            format='html',
                            extra_args=app.config['PANDOC_ARGS']
                            )

                formatted.append(f"## {e['date'].strftime('%a %b %d %Y %H:%M:%S %z')}\n\n{t}")

            txt = "\n\n".join(formatted)


            caches_to_remove = glob.glob(f"{app.config['STATIC_FOLDER']}/log.txt.*")

            for c in caches_to_remove:
                os.remove(c)

            with open(cached_txt, 'w+') as f:
                f.write(txt)

            return txt, 200, {'Content-Type': 'text/plain; charset=utf-8'}



    @app.route("/archive.html")
    @app.route("/%s/index.html" % app.config['POST_DIRECTORY'])
    def archive():
        posts = helpers.get_posts()
        return render_template('archive.html', posts=posts,
                               directory=app.config['POST_DIRECTORY'],
                               site=app.config)

    from whiskey import feeds

if app.config["DEPLOY_TYPE"] == "serve":

    @app.route("/api/publish", methods = ['POST'])
    def publish():
        if app.debug and os.path.islink(app.config["CONTENT_PATH"]):
            app.logger.debug("CONTENT PATH symlinked")
            return Response("CAREFUL", status=418)

        if request.headers.get("X-API-KEY") != app.config["API_KEY"]:
            return Response("NOT AUTHORIZED", status=401)

        if app.config["CONTENT_IN_PROGRESS"] is True:
            return Response("BUSY", status=503)
        else:
            threading.Thread(target=helpers.pull_content).start()
            return Response("PUBLISH OK", status=200)

    @app.route("/api/unpublish", methods = ['POST'])
    def unpublish():
        if app.debug and os.path.islink(app.config["CONTENT_PATH"]):
            app.logger.debug("CONTENT PATH symlinked")
            return Response("CAREFUL", status=418)

        if request.headers.get("X-API-KEY") != app.config["API_KEY"]:
            return Response("NOT AUTHORIZED", status=401)

        import glob
        local_files = []
        files = glob.glob(f"{app.config['CONTENT_PATH']}/**/*", recursive=True)
        for f in files:
            if not os.path.isdir(f):
                local_files.append(f.removeprefix(app.config["CONTENT_PATH"]))

        local_set = set(local_files)
        remote_set = set(helpers.get_all_remote_files())
        unpublish = list(sorted(local_set - remote_set))

        for f in unpublish:
            app.logger.info("unpublishing " + f)
            os.remove(app.config['CONTENT_PATH'] + f)
            flatpages.reload()

        return Response("UNPUBLISH OK", status=200)



    @app.route("/healthcheck")
    def healthcheck():
        if app.debug and os.path.islink(app.config["CONTENT_PATH"]):
            app.logger.debug("CONTENT PATH symlinked")
            return Response("CAREFUL", status=418)

        if rclone.is_installed():
            target=helpers.rclone_content
        else:
            target=helpers.pull_content

        if app.config["INITIAL_CONTENT_PULLED"] is None:
            threading.Thread(target=target).start()
            return Response("NO", status=503)
        elif app.config["INITIAL_CONTENT_PULLED"] is False:
            return Response("BUSY", status=503)
        else:
            return Response("OK", status=200)


@app.errorhandler(404)
def page_not_found(e):
    if "." not in request.path:
        return redirect(f"{request.path}.html", code=301)
    else:
        return render_template('404.html', site=app.config)


@app.errorhandler(403)
def page_forbidden(e):
    return render_template('403.html', site=app.config)
