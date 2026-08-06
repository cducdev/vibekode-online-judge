import logging

import requests
from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

TURNSTILE_SCRIPT_URL = 'https://challenges.cloudflare.com/turnstile/v0/api.js'
TURNSTILE_VERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'


class TurnstileWidget(forms.Widget):
    def __init__(self, site_key, action, attrs=None):
        super().__init__(attrs)
        self.site_key = site_key
        self.action = action

    @property
    def media(self):
        return forms.Media(js=(TURNSTILE_SCRIPT_URL,))

    def render(self, name, value, attrs=None, renderer=None):
        return format_html(
            '<div class="cf-turnstile" data-sitekey="{}" data-action="{}" '
            'data-theme="auto" data-size="flexible"></div>',
            self.site_key,
            self.action,
        )

    def value_from_datadict(self, data, files, name):
        return data.get('cf-turnstile-response', '')


class TurnstileField(forms.CharField):
    default_error_messages = {
        'required': _('Please complete the security check.'),
        'invalid': _('We could not verify the security check. Please try again.'),
        'unavailable': _('The security verification service is temporarily unavailable. Please try again.'),
    }

    def __init__(self, *, site_key, secret_key, action, expected_hostnames=(), remote_ip=None, timeout=5):
        super().__init__(
            label='',
            max_length=2048,
            required=True,
            strip=True,
            widget=TurnstileWidget(site_key=site_key, action=action),
        )
        self.secret_key = secret_key
        self.action = action
        if isinstance(expected_hostnames, str):
            expected_hostnames = (expected_hostnames,)
        self.expected_hostnames = set(expected_hostnames)
        self.remote_ip = remote_ip
        self.timeout = timeout

    def clean(self, value):
        value = super().clean(value)
        if not self.secret_key:
            raise ValidationError(self.error_messages['unavailable'], code='unavailable')

        data = {
            'secret': self.secret_key,
            'response': value,
        }
        if self.remote_ip:
            data['remoteip'] = self.remote_ip

        try:
            response = requests.post(TURNSTILE_VERIFY_URL, data=data, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError('Unexpected Turnstile response')
        except (requests.RequestException, ValueError):
            logger.warning('Turnstile verification service unavailable', exc_info=True)
            raise ValidationError(self.error_messages['unavailable'], code='unavailable')

        if not result.get('success'):
            logger.info('Turnstile verification rejected: %s', result.get('error-codes', ()))
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        if result.get('action') != self.action:
            logger.warning('Turnstile verification returned an unexpected action')
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        if self.expected_hostnames and result.get('hostname') not in self.expected_hostnames:
            logger.warning('Turnstile verification returned an unexpected hostname')
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        return value
