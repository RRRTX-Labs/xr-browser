# NEGATIVE TEST CORPUS FILE — DO NOT IMPORT.
#
# This file intentionally contains a GPL-3.0 license header so that
# tools/license_audit.py's code-path scan has a real sample to fail on
# (Plan P1 DoD: "license-scan fails on an injected GPL sample").
#
# The tools/tests/fixtures/ directory is EXCLUDED from the marker scan
# for the same reason a security scanner's test corpus is excluded from
# its own scanner: these files exist to prove the detector works.
#
# The scan failure must be demonstrated via tools/run_negatives.sh /
# pytest, never by committing this file anywhere outside fixtures/.

#
# Copyright (C) 2026 Sample Vendor
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

def sample_function():
    return 42
