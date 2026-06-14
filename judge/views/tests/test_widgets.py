import base64
import json
import os
import shutil
import tempfile

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from judge.models.tests.util import create_user


class MartorImageUploadTestCase(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_root)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(shutil.rmtree, self.media_root)

        self.staff = create_user(
            username='staff',
            is_staff=True,
            is_superuser=True,
        )

    def _upload_image(self, filename):
        self.client.force_login(self.staff)
        image = SimpleUploadedFile(filename, self._tiny_png(), content_type='image/png')
        response = self.client.post(reverse('martor_image_uploader'), {
            'markdown-image-upload': image,
        })
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content.decode())

    def test_upload_returns_media_martor_link(self):
        data = self._upload_image('tiny.png')

        self.assertEqual(data['status'], 200)
        self.assertTrue(data['link'].startswith('/media/martor/'))

        filename = data['link'].rsplit('/', 1)[-1]
        self.assertTrue(default_storage.exists(os.path.join('martor', filename)))

    def test_svg_extension_is_not_preserved(self):
        data = self._upload_image('unsafe.svg')

        self.assertFalse(data['link'].endswith('.svg'))
        self.assertTrue(data['link'].endswith('.png'))

    @staticmethod
    def _tiny_png():
        return base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=',
        )
