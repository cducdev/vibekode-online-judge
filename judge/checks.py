from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security)
def registration_security_check(app_configs, **kwargs):
    if not settings.REGISTRATION_OPEN:
        return []

    errors = []
    if settings.REGISTRATION_REQUIRE_EMAIL_VERIFICATION and not settings.SEND_ACTIVATION_EMAIL:
        errors.append(Error(
            'Public registration requires activation emails.',
            hint='Enable SEND_ACTIVATION_EMAIL and configure a working SMTP backend.',
            id='judge.E001',
        ))

    if settings.REGISTRATION_REQUIRE_TURNSTILE:
        if not settings.TURNSTILE_SITE_KEY or not settings.TURNSTILE_SECRET_KEY:
            errors.append(Error(
                'Public registration requires Cloudflare Turnstile credentials.',
                hint='Set TURNSTILE_SITE_KEY and TURNSTILE_SECRET_KEY outside version control.',
                id='judge.E002',
            ))
        if not settings.TURNSTILE_EXPECTED_HOSTNAMES:
            errors.append(Error(
                'Public registration requires an expected Turnstile hostname.',
                hint='Set TURNSTILE_EXPECTED_HOSTNAMES to the public registration hostnames.',
                id='judge.E003',
            ))

    return errors
