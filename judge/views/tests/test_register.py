import hashlib
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils.translation import override as translation_override

from judge.checks import registration_security_check
from judge.models import Language
from judge.utils.turnstile import TURNSTILE_VERIFY_URL, TurnstileField
from judge.views.register import RegistrationView


def turnstile_response(**overrides):
    result = {
        'success': True,
        'action': 'register',
        'hostname': 'oj.example.test',
        'error-codes': [],
    }
    result.update(overrides)
    response = Mock()
    response.json.return_value = result
    return response


class TurnstileFieldTestCase(SimpleTestCase):
    def create_field(self):
        return TurnstileField(
            site_key='unit-test-site-key',
            secret_key='unit-test-secret-key',
            action='register',
            expected_hostnames=('oj.example.test',),
            remote_ip='192.0.2.10',
            timeout=3,
        )

    @patch('judge.utils.turnstile.requests.post')
    def test_valid_token_is_checked_server_side(self, post):
        post.return_value = turnstile_response()

        self.assertEqual(self.create_field().clean('valid-token'), 'valid-token')
        post.assert_called_once_with(
            TURNSTILE_VERIFY_URL,
            data={
                'secret': 'unit-test-secret-key',
                'response': 'valid-token',
                'remoteip': '192.0.2.10',
            },
            timeout=3,
        )

    @patch('judge.utils.turnstile.requests.post')
    def test_rejected_token_is_invalid(self, post):
        post.return_value = turnstile_response(success=False, **{'error-codes': ['invalid-input-response']})

        with self.assertRaisesMessage(ValidationError, 'We could not verify the security check'):
            self.create_field().clean('invalid-token')

    @patch('judge.utils.turnstile.logger')
    @patch('judge.utils.turnstile.requests.post')
    def test_unexpected_action_or_hostname_is_invalid(self, post, logger):
        for result in (
            turnstile_response(action='login'),
            turnstile_response(hostname='attacker.example'),
        ):
            with self.subTest(result=result.json.return_value):
                post.return_value = result
                with self.assertRaisesMessage(ValidationError, 'We could not verify the security check'):
                    self.create_field().clean('invalid-context-token')

    @patch('judge.utils.turnstile.logger')
    @patch('judge.utils.turnstile.requests.post', side_effect=requests.Timeout)
    def test_verification_outage_fails_closed(self, post, logger):
        with self.assertRaisesMessage(ValidationError, 'temporarily unavailable'):
            self.create_field().clean('unverified-token')


class ActivationEmailTemplateTestCase(SimpleTestCase):
    def test_activation_email_uses_https_and_clean_subject(self):
        context = {
            'activation_key': 'activation-key',
            'expiration_days': 7,
            'misc_config': SimpleNamespace(discord_invite_link='', discord_invite_shieldio=''),
            'site': SimpleNamespace(domain='oj.example.test', name='VKOJ'),
            'SITE_ADMIN_EMAIL': 'support@example.test',
            'SITE_NAME': 'VKOJ',
        }

        subject = render_to_string('registration/activation_email_subject.txt', context).strip()
        body = render_to_string('registration/activation_email.txt', context)
        html = render_to_string('registration/activation_email.html', context)

        self.assertEqual(subject, 'Activate your VKOJ account')
        self.assertIn('https://oj.example.test/accounts/activate/activation-key/', body)
        self.assertIn('https://oj.example.test/accounts/activate/activation-key/', html)
        self.assertNotIn('http://oj.example.test', body)
        self.assertNotIn('reply to this message', body)
        self.assertIn('mailto:support@example.test', html)

        with translation_override('vi'):
            vietnamese_body = render_to_string('registration/activation_email.txt', context)
        self.assertIn('Vui lòng kích hoạt tài khoản VKOJ của bạn trong vòng 7 ngày tới.', vietnamese_body)


@override_settings(
    ALLOWED_HOSTS=('oj.example.test', 'vkoj.example.test'),
    AUTH_PASSWORD_VALIDATORS=[],
    DEFAULT_USER_LANGUAGE='PY3',
    REGISTRATION_OPEN=True,
    REGISTRATION_REQUIRE_EMAIL_VERIFICATION=False,
    REGISTRATION_REQUIRE_TURNSTILE=True,
    SEND_ACTIVATION_EMAIL=False,
    TURNSTILE_SITE_KEY='unit-test-site-key',
    TURNSTILE_SECRET_KEY='unit-test-secret-key',
    TURNSTILE_EXPECTED_HOSTNAMES=('oj.example.test', 'vkoj.example.test'),
    TURNSTILE_REGISTRATION_ACTION='register',
)
class RegistrationViewTestCase(TestCase):
    fixtures = ['language_all.json']
    remote_ip = '192.0.2.20'

    def setUp(self):
        remote_ip_hash = hashlib.sha256(self.remote_ip.encode()).hexdigest()
        self.rate_limit_key = 'registration!%s' % remote_ip_hash
        cache.delete(self.rate_limit_key)
        self.addCleanup(cache.delete, self.rate_limit_key)

    def test_registration_form_renders_turnstile(self):
        response = self.client.get(reverse('registration_register'), HTTP_HOST='oj.example.test')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="cf-turnstile"')
        self.assertContains(response, 'data-sitekey="unit-test-site-key"')
        self.assertContains(response, 'challenges.cloudflare.com/turnstile/v0/api.js')

    @override_settings(TURNSTILE_SITE_KEY='', TURNSTILE_SECRET_KEY='', TURNSTILE_EXPECTED_HOSTNAMES=())
    def test_registration_stays_closed_without_turnstile_configuration(self):
        response = self.client.get(reverse('registration_register'), HTTP_HOST='oj.example.test')

        self.assertRedirects(response, reverse('registration_disallowed'))

    @override_settings(DMOJ_REGISTRATION_LIMIT_COUNT=1, DMOJ_REGISTRATION_LIMIT_WINDOW=120)
    def test_registration_post_is_rate_limited(self):
        url = reverse('registration_register')
        first = self.client.post(url, {}, REMOTE_ADDR=self.remote_ip, HTTP_HOST='oj.example.test')
        second = self.client.post(url, {}, REMOTE_ADDR=self.remote_ip, HTTP_HOST='oj.example.test')

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second['Retry-After'], '120')

    @patch('judge.utils.turnstile.requests.post')
    def test_valid_registration_creates_profile(self, post):
        post.return_value = turnstile_response()
        language = Language.objects.get(key=settings.DEFAULT_USER_LANGUAGE)

        response = self.client.post(
            reverse('registration_register'),
            {
                'username': 'new_student',
                'full_name': 'New Student',
                'email': 'new-student@example.test',
                'password1': 'A-strong-unit-test-password-2026',
                'password2': 'A-strong-unit-test-password-2026',
                'timezone': 'Asia/Ho_Chi_Minh',
                'language': language.pk,
                'cf-turnstile-response': 'valid-token',
            },
            REMOTE_ADDR=self.remote_ip,
            HTTP_HOST='oj.example.test',
        )

        self.assertRedirects(response, reverse('registration_complete'))
        user = User.objects.get(username='new_student')
        self.assertTrue(user.is_active)
        self.assertEqual(user.first_name, 'New Student')
        self.assertEqual(user.profile.timezone, 'Asia/Ho_Chi_Minh')
        self.assertEqual(user.profile.language, language)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        REGISTRATION_REQUIRE_EMAIL_VERIFICATION=True,
        SEND_ACTIVATION_EMAIL=True,
    )
    @patch.object(RegistrationView, 'SEND_ACTIVATION_EMAIL', True)
    @patch('judge.utils.turnstile.requests.post')
    def test_activation_email_uses_registration_request_host(self, post):
        post.return_value = turnstile_response(hostname='vkoj.example.test')
        language = Language.objects.get(key=settings.DEFAULT_USER_LANGUAGE)
        site = Site.objects.get_current()
        site.domain = 'oj.example.test'
        site.name = 'VKOJ'
        site.save()

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('registration_register'),
                {
                    'username': 'inactive_student',
                    'full_name': 'Inactive Student',
                    'email': 'inactive-student@example.test',
                    'password1': 'A-strong-unit-test-password-2026',
                    'password2': 'A-strong-unit-test-password-2026',
                    'timezone': 'Asia/Ho_Chi_Minh',
                    'language': language.pk,
                    'cf-turnstile-response': 'valid-token',
                },
                REMOTE_ADDR=self.remote_ip,
                HTTP_HOST='vkoj.example.test',
            )

        self.assertRedirects(response, reverse('registration_complete'))
        user = User.objects.get(username='inactive_student')
        self.assertFalse(user.is_active)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['inactive-student@example.test'])
        self.assertIn('https://vkoj.example.test/accounts/activate/', mail.outbox[0].body)
        self.assertNotIn('https://oj.example.test/accounts/activate/', mail.outbox[0].body)


class RegistrationSecurityCheckTestCase(SimpleTestCase):
    @override_settings(
        REGISTRATION_OPEN=True,
        REGISTRATION_REQUIRE_EMAIL_VERIFICATION=True,
        REGISTRATION_REQUIRE_TURNSTILE=True,
        SEND_ACTIVATION_EMAIL=False,
        TURNSTILE_SITE_KEY='',
        TURNSTILE_SECRET_KEY='',
        TURNSTILE_EXPECTED_HOSTNAMES=(),
    )
    def test_open_registration_reports_missing_security_configuration(self):
        errors = registration_security_check(None)

        self.assertEqual({error.id for error in errors}, {'judge.E001', 'judge.E002', 'judge.E003'})

    @override_settings(
        REGISTRATION_OPEN=True,
        REGISTRATION_REQUIRE_EMAIL_VERIFICATION=True,
        REGISTRATION_REQUIRE_TURNSTILE=True,
        SEND_ACTIVATION_EMAIL=True,
        TURNSTILE_SITE_KEY='unit-test-site-key',
        TURNSTILE_SECRET_KEY='unit-test-secret-key',
        TURNSTILE_EXPECTED_HOSTNAMES=('oj.example.test',),
    )
    def test_complete_public_registration_configuration_passes(self):
        self.assertEqual(registration_security_check(None), [])
