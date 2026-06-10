from unittest import TestCase

from enrich import parse_chart_time


class ParseChartTimeTest(TestCase):
    def test_parses_lowercase_am_with_seconds(self):
        parsed = parse_chart_time("1:39:00 am")
        self.assertEqual((parsed.hour, parsed.minute, parsed.second), (1, 39, 0))

    def test_parses_24_hour_time_with_seconds(self):
        parsed = parse_chart_time("11:20:05")
        self.assertEqual((parsed.hour, parsed.minute, parsed.second), (11, 20, 5))

    def test_parses_lowercase_am_without_seconds(self):
        parsed = parse_chart_time("1:39 am")
        self.assertEqual((parsed.hour, parsed.minute, parsed.second), (1, 39, 0))

    def test_parses_24_hour_time_without_seconds(self):
        parsed = parse_chart_time("11:20")
        self.assertEqual((parsed.hour, parsed.minute, parsed.second), (11, 20, 0))
