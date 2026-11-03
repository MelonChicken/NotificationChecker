import ssl
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, sentinel

import certifi
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Util import seoultech_http


class SeoultechHTTPTests(unittest.TestCase):
    def tearDown(self):
        if seoultech_http._ca_bundle_directory.cache_info().currsize:
            seoultech_http._ca_bundle_directory().cleanup()
        seoultech_http._ca_bundle_directory.cache_clear()

    def test_bundle_preserves_roots_and_adds_intermediate(self):
        directory = seoultech_http._ca_bundle_directory()
        bundle = Path(directory.name) / "ca-bundle.pem"
        data = bundle.read_bytes()
        self.assertTrue(data.startswith(Path(certifi.where()).read_bytes().rstrip()))
        self.assertIn(seoultech_http.INTERMEDIATE_CERT.read_bytes(), data)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cafile=str(bundle))
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertIs(directory, seoultech_http._ca_bundle_directory())

    def test_request_uses_bundle_and_timeout(self):
        url = "https://itm.seoultech.ac.kr/bachelor_of_information/notice/"
        with patch.object(seoultech_http.requests, "get", return_value=sentinel.response) as get:
            self.assertIs(seoultech_http.get_school_page(url), sentinel.response)
        args, kwargs = get.call_args
        self.assertEqual(args, (url,))
        self.assertTrue(Path(kwargs["verify"]).is_file())
        self.assertEqual(kwargs["timeout"], (10, 30))

    def test_rejects_insecure_or_unrelated_initial_url(self):
        for url in ["http://www.seoultech.ac.kr/", "https://example.com/",
                    "https://www.seoultech.ac.kr.evil.test/"]:
            with self.subTest(url=url), patch.object(seoultech_http.requests, "get") as get:
                with self.assertRaises(ValueError):
                    seoultech_http.get_school_page(url)
                get.assert_not_called()

    def test_missing_intermediate_fails_before_request(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(seoultech_http, "INTERMEDIATE_CERT", Path(directory) / "missing.pem"):
                with patch.object(seoultech_http.requests, "get") as get:
                    with self.assertRaises(FileNotFoundError):
                        seoultech_http.get_school_page("https://www.seoultech.ac.kr/")
                    get.assert_not_called()

    def test_ssl_failure_is_not_retried_without_verification(self):
        with patch.object(seoultech_http.requests, "get", side_effect=requests.exceptions.SSLError) as get:
            with self.assertRaises(requests.exceptions.SSLError):
                seoultech_http.get_school_page("https://www.seoultech.ac.kr/")
            get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
