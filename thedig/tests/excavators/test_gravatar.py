
import pytest
from curl_cffi.requests import AsyncSession, RequestsError

from thedig.excavators.gravatar import email_hash, gravatar


@pytest.mark.parametrize("email, expected_hash", [
    ("myemailaddress@example.com", "0bc83cb571cd1c50ba6f3e8a78ef1346"),
    ("UPPERCASE@EXAMPLE.COM", "ac4e06146e6a45a68b92d3d4a8d62f2c"),
    ("user.name+tag@example.com", "84f6c9b6e2b7e8a3b2c8a9a3a8f5c8d9"),
])
def test_email_hash(email, expected_hash):
    assert email_hash(email) == expected_hash


@pytest.mark.asyncio
async def test_gravatar_no_check():
    email = "test@example.com"
    expected_url = f"https://www.gravatar.com/avatar/{email_hash(email)}?d=404&s=400"
    result = await gravatar(email, check=False)
    assert result == expected_url


@pytest.mark.asyncio
async def test_gravatar_with_check_success(mocker):
    email = "test@example.com"
    expected_url = f"https://www.gravatar.com/avatar/{email_hash(email)}?d=404&s=400"

    mock_response = mocker.Mock()
    mock_response.ok = True

    mock_session = mocker.AsyncMock(spec=AsyncSession)
    mock_session.return_value.__aenter__.return_value.get.return_value = mock_response

    mocker.patch('thedig.excavators.gravatar.AsyncSession',
                 return_value=mock_session)

    result = await gravatar(email, check=True)
    assert result == expected_url


@pytest.mark.asyncio
async def test_gravatar_with_check_failure(mocker):
    email = "test@example.com"

    mock_response = mocker.Mock()
    mock_response.ok = False

    mock_session = mocker.AsyncMock(spec=AsyncSession)
    mock_session.return_value.__aenter__.return_value.get.return_value = mock_response

    mocker.patch('thedig.excavators.gravatar.AsyncSession',
                 return_value=mock_session)

    result = await gravatar(email, check=True)
    assert result is None


@pytest.mark.asyncio
async def test_gravatar_with_request_error(mocker):
    email = "test@example.com"

    mock_session = mocker.AsyncMock(spec=AsyncSession)
    mock_session.return_value.__aenter__.return_value.get.side_effect = RequestsError(
        "Test error")

    mocker.patch('thedig.excavators.gravatar.AsyncSession',
                 return_value=mock_session)
    mocker.patch('thedig.excavators.gravatar.log.error')

    result = await gravatar(email, check=True)
    assert result is None
