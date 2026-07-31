"""Import-purity guards: pandas is an OPTIONAL extra, never a foundational import.

Across views_platform pandas is being phased out. `views-pipeline-core` declares
no pandas at all and carries the same tripwire (its
`tests/test_import_purity.py`, epic #300); `views-frames` is numpy-only with
optional extras. This repo's contribution to that goal is that importing any
consumer-facing package must not drag pandas in — pandas is paid for only by
callers who actually ask for `output_format="dataframe"` (or `"country_month"`).

Before 2026-07-31 the opposite was true: `import datafactory_query.defaults` —
a stdlib-only module holding a URL constant, and the single most common
datafactory import across views-models — loaded pandas via the eager
re-exports in `__init__.py`. `views-pipeline-core`'s purity guard stayed green
only because it imports us lazily inside a function; it was green by luck of
the call site, not because we were clean.

All probes run in a SUBPROCESS: the pytest process has pandas loaded (dev
group, other suites), so in-process assertions would be meaningless.
"""

from __future__ import annotations

import subprocess
import sys

PROBE = (
    "import sys; {imports}; "
    "loaded = sorted(m for m in sys.modules "
    "if m == 'pandas' or m.startswith('pandas.')); "
    "assert not loaded, f'pandas loaded: {{loaded[:3]}}'"
)


def _run_probe(imports: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", PROBE.format(imports=imports)],
        capture_output=True,
        text=True,
        check=False,
    )


class TestPandasIsNotAFoundationalImport:
    """Red: the consumer packages must import without loading pandas."""

    def test_query_package_import_is_pandas_free(self) -> None:
        """`import datafactory_query` must not load pandas."""
        result = _run_probe("import datafactory_query")
        assert result.returncode == 0, result.stderr

    def test_defaults_import_is_pandas_free(self) -> None:
        """The DEFAULT_REMOTE path must not load pandas.

        This is the one that matters most in practice: 29 of the 35
        datafactory imports across views-models are
        `from datafactory_query.defaults import DEFAULT_REMOTE`, i.e. the
        platform reading a URL constant. If this turns red, some module on
        the `datafactory_query/__init__.py` chain regained a top-level
        `import pandas` — move the import into the function that builds the
        frame, do not gate this test.
        """
        result = _run_probe(
            "from datafactory_query.defaults import DEFAULT_REMOTE"
        )
        assert result.returncode == 0, result.stderr

    def test_adapters_package_import_is_pandas_free(self) -> None:
        """`import datafactory_adapters` must not load pandas."""
        result = _run_probe("import datafactory_adapters")
        assert result.returncode == 0, result.stderr

    def test_feature_frame_path_is_pandas_free(self) -> None:
        """The FeatureFrame path is the pandas-free future (pipeline-core #161).

        views-bayesian already consumes `output_format="feature_frame"`; it
        must not pay for pandas to do so.
        """
        result = _run_probe(
            "from datafactory_adapters import FeatureFrame"
        )
        assert result.returncode == 0, result.stderr

    def test_graph_layers_are_pandas_free(self) -> None:
        """Harvest/viewpoint/compilation were already clean — keep them so."""
        result = _run_probe(
            "import datafactory_harvester, datafactory_viewpoint, "
            "datafactory_compilation"
        )
        assert result.returncode == 0, result.stderr
