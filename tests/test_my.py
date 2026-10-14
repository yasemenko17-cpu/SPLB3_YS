import pytest
from conftest import load

lab08 = load(8)

def test_my_parse_limits_custom():
    text = "Limit                     Soft Limit             Hard Limit             Units\n" \
           "Max cpu time              unlimited              unlimited              seconds\n" \
           "Max open files            1024                   524288                 files\n"
    res = lab08.parse_limits(text)
    assert res == {
        'Max cpu time': (None, None),
        'Max open files': (1024, 524288)
    }

def test_my_run_limited_success():
    code, sig = lab08.run_limited(lambda: 42, {})
    assert code == 42
    assert sig is None

def test_my_run_limited_invalid_limit():
    with pytest.raises(ValueError):
        lab08.run_limited(lambda: 0, {'INVALID_LIMIT_NAME': 100})