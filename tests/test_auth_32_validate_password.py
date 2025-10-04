import pytest


@pytest.mark.parametrize(
    "password,expected",
    [
        ("Short1", False),
        ("alllowercase123", False),
        ("ALLUPPERCASE123", False),
        ("NoDigitsHere", False),
        ("ValidPass123", True),
    ],
)
def test_auth_validates_password_strength(auth_manager, password, expected):
    is_valid, _ = auth_manager.validate_password(password)
    assert is_valid is expected
