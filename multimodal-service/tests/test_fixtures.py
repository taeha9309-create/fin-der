import sys
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR))

from run_fixture_tests import DEFAULT_FIXTURES, load_fixture


def test_all_fixture_inputs_and_screenshot_paths_remain_loadable():
    for fixture_name in DEFAULT_FIXTURES:
        fixture = load_fixture(fixture_name)
        assert Path(fixture["screenshot_path"]).is_file()
        assert fixture["original_url"]
        assert "html" in fixture
