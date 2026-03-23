"""Tests for datafactory_priogrid.land_mask."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from datafactory_priogrid.land_mask import fetch_land_pgids


class TestLandMaskGreen:

    def test_fetches_from_api(self, tmp_path: Path) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "cells": [
                {"gid": 100, "value": 50.0},
                {"gid": 200, "value": 30.0},
            ]
        }
        mock_resp.raise_for_status = MagicMock()

        cache = tmp_path / "land_pgids.json"
        with patch("requests.get", return_value=mock_resp):
            result = fetch_land_pgids(cache_path=cache)

        assert result == {100, 200}
        assert cache.exists()

    def test_uses_cache_on_second_call(
        self, tmp_path: Path
    ) -> None:
        cache = tmp_path / "land_pgids.json"
        cache.write_text(json.dumps([1, 2, 3]))

        result = fetch_land_pgids(cache_path=cache)
        assert result == {1, 2, 3}

    def test_force_refresh_bypasses_cache(
        self, tmp_path: Path
    ) -> None:
        cache = tmp_path / "land_pgids.json"
        cache.write_text(json.dumps([1, 2]))

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "cells": [{"gid": 10, "value": 1.0}]
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_resp):
            result = fetch_land_pgids(
                cache_path=cache, force_refresh=True
            )

        assert result == {10}


class TestLandMaskBeige:

    def test_empty_cache_creates_new(
        self, tmp_path: Path
    ) -> None:
        cache = tmp_path / "subdir" / "land_pgids.json"
        assert not cache.exists()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "cells": [{"gid": 42, "value": 1.0}]
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_resp):
            result = fetch_land_pgids(cache_path=cache)

        assert result == {42}
        assert cache.parent.exists()
