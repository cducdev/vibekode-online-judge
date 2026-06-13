import csv
import io
import re
import secrets

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils.translation import gettext as _

from judge.models import Organization, Profile

PASSWORD_ALPHABET = 'abcdefghkqtxyz' + 'abcdefghkqtxyz'.upper() + '23456789'
USER_IMPORT_MAX_ROWS = 1000
ORGANIZATION_COLUMNS = ('organizations', 'organization', 'orga', 'org')
ORGANIZATION_SPLIT_RE = re.compile(r'[;,\s]+')


def can_import_users(request):
    if not request.user.is_authenticated:
        return False
    return request.user.has_perm('auth.add_user')


def generate_import_password():
    return ''.join(secrets.choice(PASSWORD_ALPHABET) for _ in range(8))


def build_sample_csv():
    output = io.StringIO()
    fieldnames = ['username', 'fullname', 'email', 'organizations']

    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    row = {
        'username': 'student01',
        'fullname': 'Nguyen Van A',
        'email': 'student01@example.com',
        'organizations': '',
    }
    writer.writerow(row)
    return output.getvalue()


class UserImportForm(forms.Form):
    csv_file = forms.FileField(
        label=_('CSV file'),
        help_text=_(
            'Upload a UTF-8 CSV file with columns: username, fullname, organizations. '
            'The email and organizations columns are optional.'
        ),
    )


class UserCsvImporter:
    def __init__(self, request):
        self.request = request

    def parse_csv(self, csv_file):
        try:
            content = csv_file.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            raise forms.ValidationError(_('CSV file must be UTF-8 encoded.'))

        if not content.strip():
            raise forms.ValidationError(_('CSV file is empty.'))

        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames:
            raise forms.ValidationError(_('CSV file must include a header row.'))

        headers = {
            header.strip().lower(): header
            for header in reader.fieldnames
            if header and header.strip()
        }
        missing = sorted({'username', 'fullname'} - set(headers))
        if missing:
            raise forms.ValidationError(_('CSV file is missing required columns: %s.') % ', '.join(missing))

        organization_header = None
        for column in ORGANIZATION_COLUMNS:
            if column in headers:
                organization_header = headers[column]
                break

        username_field = User._meta.get_field(User.USERNAME_FIELD)
        first_name_field = User._meta.get_field('first_name')
        email_field = User._meta.get_field('email')
        rows = []
        seen_usernames = set()

        for line_number, row in enumerate(reader, start=2):
            parsed = {
                'line': line_number,
                'username': self.get_csv_cell(row, headers, 'username'),
                'fullname': self.get_csv_cell(row, headers, 'fullname'),
                'email': self.get_csv_cell(row, headers, 'email'),
                'organization_slugs': self.get_organization_slugs(row, organization_header),
            }
            if not any((parsed['username'], parsed['fullname'], parsed['email'], parsed['organization_slugs'])):
                continue

            errors = self.validate_user_row(parsed, username_field, first_name_field, email_field, seen_usernames)
            organizations, organization_errors = self.resolve_organizations(parsed['organization_slugs'])
            errors.extend(organization_errors)

            if errors:
                raise forms.ValidationError(_('Line %(line)d: %(errors)s') % {
                    'line': line_number,
                    'errors': '; '.join(errors),
                })
            parsed['organizations'] = organizations
            rows.append(parsed)

        if not rows:
            raise forms.ValidationError(_('CSV file does not contain any users.'))
        if len(rows) > USER_IMPORT_MAX_ROWS:
            raise forms.ValidationError(_('CSV file cannot contain more than %d users.') % USER_IMPORT_MAX_ROWS)
        return rows

    @staticmethod
    def get_csv_cell(row, headers, key):
        header = headers.get(key)
        return (row.get(header) or '').strip() if header else ''

    def get_organization_slugs(self, row, organization_header):
        if organization_header is None:
            return []
        value = (row.get(organization_header) or '').strip()
        slugs = []
        seen = set()
        for slug in ORGANIZATION_SPLIT_RE.split(value):
            if slug and slug not in seen:
                slugs.append(slug)
                seen.add(slug)
        return slugs

    def validate_user_row(self, row, username_field, first_name_field, email_field, seen_usernames):
        errors = []
        username_key = row['username'].lower()
        if not row['username']:
            errors.append(_('username is required'))
        elif username_key in seen_usernames:
            errors.append(_('username is duplicated in this CSV'))
        else:
            seen_usernames.add(username_key)
            if len(row['username']) > username_field.max_length:
                errors.append(_('username is too long'))
            for validator in username_field.validators:
                try:
                    validator(row['username'])
                except DjangoValidationError as error:
                    errors.extend(error.messages)

        if len(row['fullname']) > first_name_field.max_length:
            errors.append(_('fullname is too long'))

        if row['email']:
            if len(row['email']) > email_field.max_length:
                errors.append(_('email is too long'))
            try:
                validate_email(row['email'])
            except DjangoValidationError as error:
                errors.extend(error.messages)
        return errors

    def resolve_organizations(self, slugs):
        organizations = []
        errors = []
        for slug in slugs:
            try:
                organization = Organization.objects.get(slug=slug)
            except Organization.DoesNotExist:
                errors.append(_('organization "%s" does not exist') % slug)
                continue

            if not self.can_manage_organization(organization):
                errors.append(_('you are not allowed to import users into organization "%s"') % slug)
            else:
                organizations.append(organization)
        return organizations, errors

    def can_manage_organization(self, organization):
        if self.request.user.has_perm('judge.edit_all_organization'):
            return True
        return hasattr(self.request, 'profile') and organization.is_admin(self.request.profile)

    def validate_slots(self, rows):
        by_organization = {}
        for row in rows:
            for organization in row['organizations']:
                by_organization.setdefault(organization, set()).add(row['username'])

        for organization, usernames in by_organization.items():
            if organization.slots is None:
                continue

            existing_members = set(
                organization.members.filter(user__username__in=usernames).values_list('user__username', flat=True),
            )
            memberships_to_add = sum(username not in existing_members for username in usernames)
            remaining_slots = organization.slots - organization.members.count()
            if memberships_to_add > remaining_slots:
                raise forms.ValidationError(
                    _('Organization "%(organization)s" only has %(remaining)d member slots left, but this CSV would '
                      'add %(count)d members.') % {
                        'organization': organization.slug,
                        'remaining': remaining_slots,
                        'count': memberships_to_add,
                    },
                )

    def import_rows(self, rows):
        results = []
        with transaction.atomic():
            for row in rows:
                user = User.objects.filter(username=row['username']).first()
                created = False
                password = ''

                if user is None:
                    password = generate_import_password()
                    user = User(username=row['username'], first_name=row['fullname'],
                                email=row['email'], is_active=True)
                    user.set_password(password)
                    user.save()
                    profile = Profile.objects.create(user=user)
                    created = True
                else:
                    profile, _ = Profile.objects.get_or_create(user=user)
                    self.update_existing_user(user, row)

                added_organizations = []
                existing_organizations = []
                for organization in row['organizations']:
                    if profile.organizations.filter(id=organization.id).exists():
                        existing_organizations.append(organization)
                    else:
                        profile.organizations.add(organization)
                        added_organizations.append(organization)

                results.append({
                    'line': row['line'],
                    'username': user.username,
                    'fullname': user.first_name,
                    'email': user.email,
                    'password': password,
                    'organizations': ', '.join(organization.slug for organization in row['organizations']),
                    'created': created,
                    'added': bool(added_organizations),
                    'status': self.get_result_status(created, added_organizations, existing_organizations),
                })
        return results

    @staticmethod
    def update_existing_user(user, row):
        update_fields = []
        if row['fullname'] and not user.first_name:
            user.first_name = row['fullname']
            update_fields.append('first_name')
        if row['email'] and not user.email:
            user.email = row['email']
            update_fields.append('email')
        if update_fields:
            user.save(update_fields=update_fields)

    @staticmethod
    def get_result_status(created, added_organizations, existing_organizations):
        if created and added_organizations:
            return _('Created and added')
        if created:
            return _('Created')
        if added_organizations:
            return _('Added existing user')
        if existing_organizations:
            return _('Already a member')
        return _('Existing user')


def build_credential_csv(results):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['username', 'fullname', 'email', 'password', 'organizations', 'status'])
    writer.writeheader()
    for result in results:
        writer.writerow({
            'username': result['username'],
            'fullname': result['fullname'],
            'email': result['email'],
            'password': result['password'],
            'organizations': result['organizations'],
            'status': result['status'],
        })
    return output.getvalue()
