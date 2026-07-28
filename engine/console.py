"""Make stdout able to carry Kannada.

Several entry points print corpus names, and about a sixth of them are in
Kannada. On Windows the console encoding defaults to a legacy code page, so the
first Kannada name raises UnicodeEncodeError and takes the whole run down.
`make all` then fails at the audit step on a machine where nothing is wrong
except the terminal.

Reconfiguring the stream is the correct fix rather than stripping the names,
because the names are the evidence. A corpus audit that could not print the
scripts it is auditing would be missing its own point.

Call `configure()` at the top of any entry point that prints a record.
"""

from __future__ import annotations

import sys


def configure() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            # A stream that cannot be reconfigured is one we did not open,
            # such as a pipe already wrapped by a caller. Leaving it alone is
            # correct, and `errors="replace"` above means the worst case is a
            # substituted glyph rather than a crash.
            pass
