"""Download supercronic for the target architecture and verify it against a pinned SHA-256."""

import hashlib
import sys
import urllib.request
from pathlib import Path

VERSION = "v0.2.49"  # released 2026-08-14; MIT
SHA256 = {
    "amd64": "a53ae236602c7338aba3fbaff40bda6300eae3b9fedb8261eb06cfe3724430c1",
    "arm64": "02aa0cb229ba09050cba6638059dadb9eedc2276632ea43d6a57a2f8c1629dd5",
}

arch = sys.argv[1]
if arch not in SHA256:
    sys.exit(f"no pinned supercronic build for architecture {arch!r}")
url = f"https://github.com/aptible/supercronic/releases/download/{VERSION}/supercronic-linux-{arch}"
with urllib.request.urlopen(url, timeout=60) as response:
    binary = response.read()
digest = hashlib.sha256(binary).hexdigest()
if digest != SHA256[arch]:
    sys.exit(f"supercronic {arch}: sha256 {digest} does not match the pinned {SHA256[arch]}")
target = Path("/usr/local/bin/supercronic")
target.write_bytes(binary)
target.chmod(0o755)
