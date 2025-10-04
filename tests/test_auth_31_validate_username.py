import pytest


@pytest.mark.parametrize("username,expected", [
    ("valid_user", True),
    ("no", False),
    ("toolongusernameexceedinglimit", False),
    ("invalid space", False),
])
def test_auth_validates_usernames(auth_manager, username, expected):
    assert auth_manager.validate_username(username) is expected
