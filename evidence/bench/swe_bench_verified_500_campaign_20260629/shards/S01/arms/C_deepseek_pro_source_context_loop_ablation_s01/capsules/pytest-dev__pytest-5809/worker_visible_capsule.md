# SWE-bench Task pytest-dev__pytest-5809

Repository: pytest-dev/pytest
Base commit: 8aba863a634f40560e25055d179220f0eefabe9a
Version: 4.6
Difficulty: <15 min fix

## Problem Statement

Lexer "python3" in --pastebin feature causes HTTP errors
The `--pastebin` option currently submits the output of `pytest` to `bpaste.net` using `lexer=python3`: https://github.com/pytest-dev/pytest/blob/d47b9d04d4cf824150caef46c9c888779c1b3f58/src/_pytest/pastebin.py#L68-L73

For some `contents`, this will raise a "HTTP Error 400: Bad Request".

As an example:
~~~
>>> from urllib.request import urlopen
>>> with open("data.txt", "rb") as in_fh:
...     data = in_fh.read()
>>> url = "https://bpaste.net"
>>> urlopen(url, data=data)
HTTPError: Bad Request
~~~
with the attached [data.txt](https://github.com/pytest-dev/pytest/files/3561212/data.txt).

This is the underlying cause for the problems mentioned in #5764.

The call goes through fine if `lexer` is changed from `python3` to `text`. This would seem like the right thing to do in any case: the console output of a `pytest` run that is being uploaded is not Python code, but arbitrary text.

## Candidate Policy

Produce a worker-derived unified diff against the base commit. Use only this packet, repository inspection, and your own reasoning.

## Worker-Visible Repository Source Context

# Source Context for pytest-dev__pytest-5809

Repository: pytest-dev/pytest
Base commit: 8aba863a634f40560e25055d179220f0eefabe9a
Selection rule: worker-derived candidate diff paths only.
Forbidden fields remain excluded: gold patch, test patch, FAIL_TO_PASS, PASS_TO_PASS, hints.

## src/_pytest/pastebin.py

````text
# -*- coding: utf-8 -*-
""" submit failure or test session information to a pastebin service. """
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys
import tempfile

import six

import pytest


def pytest_addoption(parser):
    group = parser.getgroup("terminal reporting")
    group._addoption(
        "--pastebin",
        metavar="mode",
        action="store",
        dest="pastebin",
        default=None,
        choices=["failed", "all"],
        help="send failed|all info to bpaste.net pastebin service.",
    )


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    if config.option.pastebin == "all":
        tr = config.pluginmanager.getplugin("terminalreporter")
        # if no terminal reporter plugin is present, nothing we can do here;
        # this can happen when this function executes in a slave node
        # when using pytest-xdist, for example
        if tr is not None:
            # pastebin file will be utf-8 encoded binary file
            config._pastebinfile = tempfile.TemporaryFile("w+b")
            oldwrite = tr._tw.write

            def tee_write(s, **kwargs):
                oldwrite(s, **kwargs)
                if isinstance(s, six.text_type):
                    s = s.encode("utf-8")
                config._pastebinfile.write(s)

            tr._tw.write = tee_write


def pytest_unconfigure(config):
    if hasattr(config, "_pastebinfile"):
        # get terminal contents and delete file
        config._pastebinfile.seek(0)
        sessionlog = config._pastebinfile.read()
        config._pastebinfile.close()
        del config._pastebinfile
        # undo our patching in the terminal reporter
        tr = config.pluginmanager.getplugin("terminalreporter")
        del tr._tw.__dict__["write"]
        # write summary
        tr.write_sep("=", "Sending information to Paste Service")
        pastebinurl = create_new_paste(sessionlog)
        tr.write_line("pastebin session-log: %s\n" % pastebinurl)


def create_new_paste(contents):
    """
    Creates a new paste using bpaste.net service.

    :contents: paste contents as utf-8 encoded bytes
    :returns: url to the pasted contents
    """
    import re

    if sys.version_info < (3, 0):
        from urllib import urlopen, urlencode
    else:
        from urllib.request import urlopen
        from urllib.parse import urlencode

    params = {
        "code": contents,
        "lexer": "python3" if sys.version_info[0] >= 3 else "python",
        "expiry": "1week",
    }
    url = "https://bpaste.net"
    response = urlopen(url, data=urlencode(params).encode("ascii")).read()
    m = re.search(r'href="/raw/(\w+)"', response.decode("utf-8"))
    if m:
        return "%s/show/%s" % (url, m.group(1))
    else:
        return "bad response: " + response


def pytest_terminal_summary(terminalreporter):
    import _pytest.config

    if terminalreporter.config.option.pastebin != "failed":
        return
    tr = terminalreporter
    if "failed" in tr.stats:
        terminalreporter.write_sep("=", "Sending information to Paste Service")
        for rep in terminalreporter.stats.get("failed"):
            try:
                msg = rep.longrepr.reprtraceback.reprentries[-1].reprfileloc
            except AttributeError:
                msg = tr._getfailureheadline(rep)
            tw = _pytest.config.create_terminal_writer(
                terminalreporter.config, stringio=True
            )
            rep.toterminal(tw)
            s = tw.stringio.getvalue()
            assert len(s)
            pastebinurl = create_new_paste(s)
            tr.write_line("%s --> %s" % (msg, pastebinurl))
````

## TuringOS Failure-Memory Broadcast Rules
<!-- BEGIN_TURINGOS_BROADCAST_RULES -->
(none)
<!-- END_TURINGOS_BROADCAST_RULES -->
