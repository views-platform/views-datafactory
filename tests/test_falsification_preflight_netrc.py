"""Falsification stubs for preflight netrc check (F4).

F4 (original): preflight checked ~/.netrc entry existence but did
NOT verify the credentials were valid. Wrong password passed
preflight, then failed 30 min later at step 12 with a 401.

Fix applied: preflight now does an HTTP HEAD against the zarr
server endpoint. 401 → FAIL (bad credentials). ConnectionError
or Timeout → WARN (credentials present, server unreachable).
"""

from __future__ import annotations

import pytest


class TestPreflightNetrcValidation:

    def test_wrong_password_detected_at_preflight(self) -> None:
        """Preflight should fail when ~/.netrc has wrong credentials.

        Creates a temp ~/.netrc with a bogus password and runs
        preflight.py. The HTTP HEAD to the zarr server should
        return 401, causing preflight to exit 1.
        """
        pytest.skip(
            "Requires live server access and temp HOME override. "
            "Run manually: HOME=/tmp/test_home uv run python scripts/preflight.py"
        )
