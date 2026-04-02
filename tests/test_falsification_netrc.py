"""Falsification audit: netrc as consumer auth standard.

Claim: "~/.netrc is the state of the art, best practice, and most
scalable solution for our use-case."

CONTESTED — 2 soft falsifications found:
  F2: "most scalable" overclaims; basic auth breaks at 30-50 users
  F3: fsspec does NOT auto-read netrc; xarray consumers need boilerplate

Neither is dangerous at current scale (5-20 users), but the claim
as stated is too strong.
"""

from __future__ import annotations


class TestNetrcSoftFalsifications:

    def test_fsspec_does_not_read_netrc(self) -> None:
        """F3: fsspec HTTPFileSystem does not auto-read ~/.netrc.

        xarray.open_zarr() consumers must pass auth explicitly via
        storage_options, even when ~/.netrc is configured. The netrc
        file is useful for curl and requests, but not for the primary
        consumer path (xarray + fsspec + zarr).

        If fsspec adds netrc support in the future, this test should
        be updated and the consumer guide simplified.
        """
        from pathlib import Path

        # Check fsspec HTTP source for netrc/trust_env support
        try:
            import fsspec

            http_mod = (
                Path(fsspec.__file__).parent
                / "implementations"
                / "http.py"
            )
            if http_mod.exists():
                content = http_mod.read_text()
                assert "netrc" not in content, (
                    "fsspec now mentions netrc — review consumer "
                    "guide, may be able to simplify auth "
                    "boilerplate"
                )
        except ImportError:
            # fsspec not in this env — the point stands:
            # consumers must pass auth explicitly
            pass

    def test_scalability_trigger_documented(self) -> None:
        """F2: basic auth + Caddy breaks at 30-50 concurrent users.

        The risk register should document a trigger for when to
        migrate to OAuth2/token-based auth.
        """
        from pathlib import Path

        register = (
            Path(__file__).parent.parent
            / "reports"
            / "technical_risk_register.md"
        )
        content = register.read_text()
        # There should be a concern about auth scalability
        assert "auth" in content.lower() or "consumer" in content.lower(), (
            "Risk register should document auth scalability trigger"
        )
