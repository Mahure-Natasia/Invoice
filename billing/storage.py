from pathlib import PurePosixPath
from uuid import uuid4
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class DatabaseStorage(Storage):
    """Private uploads; delivery remains in the existing authenticated logo view."""

    def _open(self, name, mode='rb'):
        from .models import StoredUpload
        try:
            upload = StoredUpload.objects.get(name=name)
        except StoredUpload.DoesNotExist as exc:
            raise FileNotFoundError(name) from exc
        return ContentFile(bytes(upload.content), name=name)

    def _save(self, name, content):
        from .models import StoredUpload
        name = 'logos/' + uuid4().hex + PurePosixPath(name).suffix.lower()
        StoredUpload.objects.create(name=name, content=b''.join(content.chunks()))
        return name

    def exists(self, name):
        from .models import StoredUpload
        return StoredUpload.objects.filter(name=name).exists()

    def delete(self, name):
        from .models import StoredUpload
        StoredUpload.objects.filter(name=name).delete()

    def size(self, name):
        with self.open(name) as content:
            return content.size
