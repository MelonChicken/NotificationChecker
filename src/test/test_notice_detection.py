import asyncio
import csv
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Util.notification_checker_base import NotificationCheckerBase
from Util.notice_identity import Notice, format_notice_display_tag, make_stable_id, notice_history_key
from api.notice_summary import (
    CSV_HEADERS,
    append_notice_history,
    load_seen_notice_keys,
    migrate_notice_history,
)
from cogs.reaction import ReactionCog


def notice(stable_id, date="2026-05-01", major=False, title=None):
    return Notice(
        source="seoultech",
        category="test",
        stable_id=stable_id,
        title=title or stable_id,
        date=date,
        url=f"https://example.test/view?bidx={stable_id}",
        is_major_notice=major,
    )


def key(stable_id):
    return notice_history_key("seoultech", "test", stable_id)


class FakeMessage:
    async def add_reaction(self, emoji):
        return None


class FakeChannel:
    def __init__(self, fail=False):
        self.fail = fail
        self.sent = []

    async def send(self, *args, **kwargs):
        if self.fail:
            raise RuntimeError("send failed")
        self.sent.append((args, kwargs))
        return FakeMessage()


class FakeChecker(NotificationCheckerBase):
    MAX_SCAN_PAGES = 10

    def __init__(self, pages, main_channel=None):
        super().__init__(
            category_key="test",
            base_url="https://example.test/list",
            settings_path="unused/res/config.toml",
            settings_toml={"DISCORD": {"EMOJIS": {"SAVE": ["S"]}}},
            main_channel=main_channel or FakeChannel(),
            log_channel=FakeChannel(),
        )
        self.pages = pages
        self.requested_pages = []

    def get_posts_page(self, page):
        self.requested_pages.append(page)
        return self.pages.get(page, [])


class NoticeDetectionTests(unittest.TestCase):
    def test_display_tag_formats_normal_bidx_as_p_tag(self):
        post = notice("bidx:893623", major=False)

        self.assertEqual(format_notice_display_tag(post), "P893623")

    def test_display_tag_formats_major_bidx_as_n_tag(self):
        post = notice("bidx:893623", major=True)

        self.assertEqual(format_notice_display_tag(post), "N893623")

    def test_discord_title_does_not_expose_stable_id_prefix(self):
        channel = FakeChannel()
        checker = FakeChecker({}, main_channel=channel)
        post = notice("bidx:893623", major=True, title="Major title")

        sent = asyncio.run(checker.send_post(post))

        self.assertTrue(sent)
        embed = channel.sent[0][1]["embed"]
        self.assertEqual(embed.title, "[N893623] Major title")
        self.assertNotIn("bidx:", embed.title)

    def test_dm_sanitizer_does_not_expose_legacy_bidx_title(self):
        cog = object.__new__(ReactionCog)
        embed = __import__("discord").Embed(title="[bidx:893623] Major title")

        sanitized = cog._sanitize_embed_for_dm(embed)

        self.assertEqual(sanitized.title, "[P893623] Major title")
        self.assertNotIn("bidx:", sanitized.title)

    def test_new_normal_notices_stop_at_first_seen_normal(self):
        checker = FakeChecker({1: [notice("A"), notice("B"), notice("C"), notice("D")]})

        result = checker.collect_new_posts({key("C"), key("D")})

        self.assertTrue(result["success"])
        self.assertEqual([post.stable_id for post in result["new_posts"]], ["A", "B"])
        self.assertEqual(checker.requested_pages, [1])

    def test_major_notices_do_not_stop_scan(self):
        checker = FakeChecker(
            {
                1: [
                    notice("A", major=True),
                    notice("B", major=True),
                    notice("C", major=True),
                    notice("D"),
                    notice("E"),
                    notice("F"),
                ]
            }
        )

        result = checker.collect_new_posts({key("A"), key("C"), key("F")})

        self.assertEqual([post.stable_id for post in result["new_posts"]], ["B", "D", "E"])

    def test_scan_multiple_pages_until_seen_normal_notice(self):
        checker = FakeChecker(
            {
                1: [notice("A", date="2026-05-03")],
                2: [notice("B", date="2026-05-02")],
                3: [notice("C", date="2026-05-01"), notice("D", date="2026-04-30")],
                4: [notice("E", date="2026-04-29")],
            }
        )

        result = checker.collect_new_posts({key("D")})

        self.assertEqual([post.stable_id for post in result["new_posts"]], ["C", "B", "A"])
        self.assertEqual(checker.requested_pages, [1, 2, 3])

    def test_major_notice_date_order_does_not_affect_dedupe_or_stop(self):
        checker = FakeChecker(
            {
                1: [
                    notice("old-major", date="2026-04-01", major=True),
                    notice("new-major", date="2026-05-05", major=True),
                    notice("seen-normal", date="2026-05-04"),
                ]
            }
        )

        result = checker.collect_new_posts({key("old-major"), key("seen-normal")})

        self.assertEqual([post.stable_id for post in result["new_posts"]], ["new-major"])

    def test_seen_normal_notice_promoted_to_major_is_not_resent(self):
        checker = FakeChecker({1: [notice("A", major=True), notice("B")]})

        result = checker.collect_new_posts({key("A")})

        self.assertEqual([post.stable_id for post in result["new_posts"]], ["B"])

    def test_failed_send_is_not_recorded_in_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = self._settings_path(tmp)
            checker = FakeChecker({1: [notice("A")]}, main_channel=FakeChannel(fail=True))
            checker.settings_path = str(settings_path)

            asyncio.run(checker.check())

            self.assertEqual(load_seen_notice_keys(str(settings_path)), set())

    def test_legacy_history_is_migrated_to_stable_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = self._settings_path(tmp)
            history_path = settings_path.parent / "notice_history.csv"
            legacy_url = "https://www.seoultech.ac.kr/service/info/notice?bidx=890714&nowpage=1"
            with history_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
                writer = csv.DictWriter(
                    csv_file,
                    fieldnames=["recorded_at", "category", "post_id", "post_date", "title", "link"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "recorded_at": "2026-05-26T23:00:00+09:00",
                        "category": "test",
                        "post_id": "P11218",
                        "post_date": "2026-05-26",
                        "title": "Legacy",
                        "link": legacy_url,
                    }
                )

            migrated = migrate_notice_history(str(settings_path))
            seen = load_seen_notice_keys(str(settings_path))

            self.assertTrue(migrated)
            self.assertIn(key("bidx:890714"), seen)
            with history_path.open("r", newline="", encoding="utf-8-sig") as csv_file:
                self.assertEqual(csv.DictReader(csv_file).fieldnames, CSV_HEADERS)

    def test_append_history_uses_new_schema_and_stable_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = self._settings_path(tmp)
            post = notice(make_stable_id("https://example.test/view?profboardidx=11218"))

            append_notice_history(str(settings_path), "test", post, datetime.now(timezone.utc))

            self.assertIn(key("profboardidx:11218"), load_seen_notice_keys(str(settings_path)))

    def _settings_path(self, tmp):
        root = Path(tmp)
        res = root / "res"
        res.mkdir(parents=True, exist_ok=True)
        settings_path = res / "config.toml"
        settings_path.write_text("", encoding="utf-8")
        return settings_path


if __name__ == "__main__":
    unittest.main()
