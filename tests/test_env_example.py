import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read_names():
    code = (ROOT / "src" / "storylens" / "config.py").read_text() + (ROOT / "wsgi.py").read_text()
    return set(re.findall(r'(?:_value|_number)\(\s*env,\s*"([A-Z_]+)"', code)) | set(
        re.findall(r'environ\.get\("([A-Z_]+)"', code)
    )


def example_names():
    found = set()
    for line in (ROOT / ".env.example").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            found.add(line.split("=", 1)[0].strip())
    return found


def test_every_variable_the_app_reads_is_documented():
    assert read_names() - example_names() == set()


def test_the_example_names_no_unknown_variable():
    assert example_names() - read_names() == set()
