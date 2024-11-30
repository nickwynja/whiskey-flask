#!/usr/bin/env python3
"""Whiskey makes writing happen."""

import os
import sys
import pypandoc
import logging
from flask import Flask
from flask_frozen import Freezer
from flask_flatpages import FlatPages
from flask_babel import Babel
from flask_compress import Compress
from whiskey.flatpandoc import FlatPagesPandoc

app = Flask(__name__)
app.config.from_pyfile('settings.py')
app.static_folder = app.config['STATIC_FOLDER']

if not app.debug:
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)

try:
    pypandoc.get_pandoc_version()
except OSError as e:
    from pypandoc.pandoc_download import download_pandoc
    download_pandoc()

babel = Babel(app)
flatpages = FlatPages(app)
FlatPagesPandoc(app.config['PANDOC_MD_FORMAT'],
                app,
                pandoc_args=app.config['PANDOC_ARGS'],
                filters=app.config['PANDOC_FILTERS']
                )
freezer = Freezer(app)
Compress(app)

import whiskey.templates
import whiskey.views
import whiskey.commands
from whiskey import helpers, freeze
