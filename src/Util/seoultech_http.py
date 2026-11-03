"""Verified HTTPS requests with Seoultech's missing intermediate certificate."""

import atexit
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

import certifi
import requests


INTERMEDIATE_CERT = (
    Path(__file__).resolve().parents[2] / "certs" / "thawte-tls-rsa-ca-g1.pem"
)
SCHOOL_HOSTS = frozenset({"www.seoultech.ac.kr", "itm.seoultech.ac.kr"})


@lru_cache(maxsize=1)
def _ca_bundle_directory():
    # Keep the TemporaryDirectory alive with the cached result. It is cleaned up
    # at process exit. Never modify certifi's installed CA bundle.
    roots = Path(certifi.where()).read_bytes()
    intermediate = INTERMEDIATE_CERT.read_bytes()
    directory = TemporaryDirectory(prefix="seoultech-ca-")
    try:
        (Path(directory.name) / "ca-bundle.pem").write_bytes(
            roots.rstrip() + b"\n" + intermediate + b"\n"
        )
    except Exception:
        directory.cleanup()
        raise
    atexit.register(directory.cleanup)
    return directory


def get_school_page(url: str):
    """Fetch a school page while preserving CA and hostname verification.

    This bundle is scoped to notice collection; Discord and OpenAI retain
    their own TLS configuration. Missing/broken certificate files fail closed.
    """
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in SCHOOL_HOSTS:
        raise ValueError("Expected an HTTPS Seoultech notice URL")
    bundle = Path(_ca_bundle_directory().name) / "ca-bundle.pem"
    return requests.get(url, verify=str(bundle), timeout=(10, 30))
