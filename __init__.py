# -*- coding: utf-8 -*-

"""Sign up management handling.

   .. note::
      Views have to be registered at the end of this module because of circular dependencies.

   .. warning::
      Some code analyzers may flag view imports as unused, because they are only imported for their side effects.
"""

import os
import random
import string

from flask import Flask
from flask_assets import Environment
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_caching import Cache
from flask_wtf import CSRFProtect
from flask_babel import Babel
from flask_ckeditor import CKEditor

from jinja2 import Markup


class CustomFlask(Flask):
    """Internal customizations to the Flask class.

       This is mostly for Jinja2's whitespace and newline control, and improved template performance.
    """
    jinja_options = dict(Flask.jinja_options, trim_blocks=True, lstrip_blocks=True, auto_reload=False)


app = CustomFlask(__name__, instance_relative_config=True)



# set up CSRF protection
CSRFProtect(app)

# helper for random length, random content comment (e.g. for BREACH protection)
rlrc_rng = random.SystemRandom()


def rlrc_comment():
    """Generate a random length (32 to 64 chars), random content (lower+upper numbers + letters) HTML comment."""
    r = rlrc_rng.randrange(32, 32 + 64)
    s = ''.join(
        rlrc_rng.choice(string.ascii_lowercase + string.ascii_uppercase + string.digits)
        for _ in range(0, r)
    )
    return Markup('<!-- RND: {} -->'.format(s))


# add Jinja helpers
app.jinja_env.globals['include_raw'] = lambda filename: Markup(app.jinja_loader.get_source(app.jinja_env, filename)[0])
app.jinja_env.globals['rlrc_comment'] = rlrc_comment
app.jinja_env.globals.update(zip=zip)

# Assets handling; keep the spz.assets module in sync with the static directory
assets_env = Environment(app)


# Set up logging before anything else, in order to catch early errors
if not app.debug and app.config.get('LOGFILE', None):
    from logging import FileHandler

    file_handler = FileHandler(app.config['LOGFILE'])
    app.logger.addHandler(file_handler)

# modify app for uwsgi
if app.debug:
    from werkzeug.debug import DebuggedApplication

    app.wsgi_app = DebuggedApplication(app.wsgi_app, True)
elif app.config.get('PROFILING', False):
    from werkzeug.contrib.profiler import ProfilerMiddleware

    app.wsgi_app = ProfilerMiddleware(app.wsgi_app)
elif app.config.get('LINTING', False):
    from werkzeug.contrib.lint import LintMiddleware

    app.wsgi_app = LintMiddleware(app.wsgi_app)

# Database handling
db = SQLAlchemy(app)

# Mail sending
mail = Mail(app)

# I18n setup
babel = Babel(app)



