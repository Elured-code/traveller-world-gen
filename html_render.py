"""
html_render.py
==============
Jinja2 environment and render helper for HTML output cards.

All templates live in the ``templates/`` directory alongside this file.
Autoescaping is enabled for all ``.html`` templates; pass
``jinja2.Markup`` objects to inject pre-trusted HTML fragments without
double-escaping.

Licence
-------
MIT Licence — see the LICENSE file in the project root.

Traveller IP notice: This software implements rules from the Traveller
roleplaying game. Any use in connection with the Traveller IP is subject
to Mongoose Publishing's Fair Use Policy, which prohibits commercial use.
The Traveller game in all forms is owned by Mongoose Publishing.
Copyright 1977-2025 Mongoose Publishing. All rights reserved.
This is an unofficial fan work, not affiliated with Mongoose Publishing.

AI assistance disclosure: developed with Claude (Anthropic).
The human author reviewed, directed, and is responsible for the code.
"""
import pathlib

import jinja2

_TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"
_ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=True,
    keep_trailing_newline=True,
)


def render(template_name: str, **context: object) -> str:
    """Render a Jinja2 template from the ``templates/`` directory.

    Parameters
    ----------
    template_name:
        Filename within ``templates/`` (e.g. ``"world_card.html"``).
    **context:
        Template variables; all values are HTML-autoescaped by Jinja2.

    Returns
    -------
    str
        Rendered HTML string.
    """
    return _ENV.get_template(template_name).render(**context)
