import pytest


@pytest.fixture(autouse=True)
def isolated_media_root(settings, tmp_path):
    """Uploaded files in tests go to a temporary folder, not to ./media."""
    settings.MEDIA_ROOT = tmp_path / "media"
