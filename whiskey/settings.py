from whiskey import app
import pathlib

site_path = f"{pathlib.Path().resolve()}"
# Set defaults which can be overriden in site.conf
app.config.update(
    TIMEZONE='US/Eastern',
    FEATURED_POSTS_COUNT=3,
    RECENT_POSTS_COUNT=10,
    PANDOC_ARGS=[],
    PANDOC_FILTERS=[],
    PANDOC_MD_FORMAT="markdown",
    INITIAL_CONTENT_PULLED=None,
    CONTENT_IN_PROGRESS=False,
    CONTENT_LAST_PULL=None,
    SEND_FILE_MAX_AGE_DEFAULT=31536000,
    DEPLOY_TYPE="static",
)
app.config.from_pyfile('%s/.whiskeyconfig' % site_path)
app.config.update(
    SITE_NAME=app.config['TITLE'],
    SITE_PATH=site_path,
    CONTENT_PATH='%s/content' % site_path,
    DATA_PATH='%s/content/data' % site_path,
    BUILD_PATH='%s/build' % site_path,
    STATIC_FOLDER='%s/src/static' % site_path,
    TEMPLATE_PATH='%s/src/templates' % site_path,
)

FLATPAGES_EXTENSION = '.md'
FLATPAGES_ROOT = app.config['CONTENT_PATH']
FREEZER_DESTINATION = app.config['BUILD_PATH']
FREEZER_RELATIVE_URLS = True
FREEZER_IGNORE_MIMETYPE_WARNINGS = True
FREEZER_STATIC_IGNORE = ['*.DS_Store']
