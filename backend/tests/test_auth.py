import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models import Admin
from tests.conftest import TestSession


@pytest.mark.asyncio
async def test_hash_and_verify():
    h = hash_password("secret-pass")
    from app.core.security import verify_password

    assert h != "secret-pass"
    assert verify_password("secret-pass", h)
    assert not verify_password("wrong", h)
