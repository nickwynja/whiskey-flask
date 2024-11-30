import os
import subprocess
import click
import datetime
import yaml
import shutil
import sys
import pypandoc
from whiskey import app, freezer, helpers


class literal_unicode(str):
    pass


def literal_unicode_representer(dumper, data):
    return dumper.represent_scalar(u'tag:yaml.org,2002:str', data, style='|')


yaml.add_representer(literal_unicode, literal_unicode_representer)


def freeze_to_build(skip_existing):
    app.config.update(FREEZER_SKIP_EXISTING=skip_existing)

    pages = [u for u in freezer.all_urls()]
    deduped_pages = []
    for i in pages:
        if i not in deduped_pages:
            deduped_pages.append(i)

    if sys.stdout.isatty():
        with click.progressbar(
                freezer.freeze_yield(),
                length=len(deduped_pages),
                show_pos=True,
                width=30,
                show_eta=False,
                show_percent=True,
                # item_show_func=lambda p: p.url if p else 'Done!'
        ) as urls:
            for url in urls:
                # everything is already happening, just pass
                pass
    else:
        print("Freezing site...")
        for g in freezer.freeze_yield():
            # everything is already happening, just pass
            pass
        print("frozen!")


def add_entry():
    n = datetime.datetime.now().astimezone().strftime("%Y%m%d%H%M%S%z")
    print(f"{app.config['DATA_PATH']}/log/{n}.md")

def clean_assets():
    paths_to_clean = [
        'src/static/.webassets-cache',
        'src/static/gen',
    ]
    for path in paths_to_clean:
        if os.path.exists(path):
            shutil.rmtree(path)
