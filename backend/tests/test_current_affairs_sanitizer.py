from src.current_affairs.sanitizer import contamination_reason, sanitize_current_affairs_text


def test_valid_article_text_and_entities_are_preserved():
    value = "<p>RBI retained the repo rate at 6.5% &amp; explained inflation risks.</p>"
    assert sanitize_current_affairs_text(value) == "RBI retained the repo rate at 6.5% & explained inflation risks."


def test_script_blocks_and_html_are_removed():
    value = "<script>document.addEventListener('click', function() {})</script><p>PIB announced a clean policy update.</p>"
    assert sanitize_current_affairs_text(value) == "PIB announced a clean policy update."


def test_javascript_and_navigation_fragments_are_rejected():
    assert sanitize_current_affairs_text("Screen Reader Access querySelector('.menu')") == ""
    assert contamination_reason("Subscribe Release PIB Delhi PIB Mumbai PIB Hyderabad")


def test_ministry_and_archive_directories_are_rejected():
    ministries = "Ministry of Finance Ministry of Defence Ministry of Education Ministry of Health"
    archive = "January February March April May 2026 2025 2024"
    assert sanitize_current_affairs_text(ministries) == ""
    assert sanitize_current_affairs_text(archive) == ""

