"""The account script's non-interactive password input."""

import io

import pytest

from scripts.create_user import read_password


def test_the_first_line_is_the_password() -> None:
    assert read_password(io.StringIO("correct horse battery\nignored\n")) == (
        "correct horse battery"
    )


def test_a_windows_line_ending_is_not_part_of_it() -> None:
    assert read_password(io.StringIO("password-one\r\n")) == "password-one"


def test_nothing_on_standard_input_is_refused() -> None:
    with pytest.raises(SystemExit):
        read_password(io.StringIO(""))
