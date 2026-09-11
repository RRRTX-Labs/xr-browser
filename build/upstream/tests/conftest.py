"""build/upstream/tests/conftest.py — shared fixtures for the upstream
treadmill suites.

`corpus_setup` lived in test_upstream_suite.py until the P11-T0-e split
(the added-file canaries moved to test_upstream_t0_added_files.py and both
modules need the corpus). Module scope is preserved: pytest instantiates a
module-scoped conftest fixture once per test module, exactly as before.
"""
from __future__ import annotations

import pytest

import fixtures


@pytest.fixture(scope="module")
def corpus_setup(tmp_path_factory):
    corpus = fixtures.build_corpus()
    source = fixtures.fixture_source_for(corpus)
    root = tmp_path_factory.mktemp("fixture-xr")
    manifest = fixtures.write_manifest_tree(root, corpus)
    return corpus, source, root, manifest
