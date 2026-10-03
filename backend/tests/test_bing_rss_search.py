from app.adapters.web_search.bing_rss import BingRSSSearchProvider


def test_bing_rss_parser_returns_clean_search_results() -> None:
    xml = """<?xml version="1.0"?>
    <rss><channel>
      <item>
        <title>Microsoft &amp; Windows Support</title>
        <link>https://support.microsoft.com/example</link>
        <description><![CDATA[<b>Official</b> troubleshooting guidance.]]></description>
      </item>
    </channel></rss>
    """

    results = BingRSSSearchProvider._parse_feed(xml, 5)

    assert len(results) == 1
    assert results[0].title == "Microsoft & Windows Support"
    assert results[0].url == "https://support.microsoft.com/example"
    assert results[0].snippet == "Official troubleshooting guidance."
    assert results[0].provider == "bing_rss"
