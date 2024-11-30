from whiskey import app, tasks, flatpages, helpers
import click
import os


@app.cli.command()
def drafts():
    """List files in post directory marked as draft"""
    drafts = [
        p for p in flatpages
        if p.path.startswith(app.config['POST_DIRECTORY'] if 'POST_DIRECTORY'
                             in app.config else '')
        and helpers.is_draft(p)
    ]
    for d in drafts:
        print('{}.md'.format(d.path))


@app.cli.command()
@click.confirmation_option(
    prompt='Do you want to build and publish \"%s\" site?'
    % (app.config['SITE_NAME']))
@click.option('-s', '--skip-existing',
              is_flag=True,
              default=False)
def publish(skip_existing):
    """Builds the site and deploys to server"""
    tasks.clean_assets()
    tasks.freeze_to_build(skip_existing)
    tasks.deploy_using_rsync()


@app.cli.command()
@click.option('-s', '--skip-existing',
              is_flag=True,
              default=False)
def build(skip_existing):
    """Builds the site and all files"""
    tasks.clean_assets()
    tasks.freeze_to_build(skip_existing)


@app.cli.command()
def reload():
    """Runs a livereload server"""
    from livereload import Server
    server = Server(app.wsgi_app)
    if 'WATCH_FILES' in app.config:
        for f in app.config['WATCH_FILES']:
            server.watch(os.path.expanduser(f))
    server.watch(app.config['CONTENT_PATH'])
    server.serve(host='0.0.0.0', port=5001, debug=True)

@app.cli.command()
def log():
    """Creates log entry"""
    tasks.add_entry()
