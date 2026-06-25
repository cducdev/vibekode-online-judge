from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from judge.models import GeneralIssue, Ticket, TicketMessage
from judge.models.tests.util import create_user


class TicketViewTestCase(TestCase):
    def setUp(self):
        self.owner = create_user(username='ticket_owner')
        self.staff = create_user(username='ticket_staff', is_staff=True, is_superuser=True)
        self.issue = GeneralIssue.objects.create(issue_url='https://example.invalid/ticket')
        self.ticket = Ticket.objects.create(
            title='Ticket render test',
            user=self.owner.profile,
            content_type=ContentType.objects.get_for_model(GeneralIssue),
            object_id=self.issue.id,
        )
        TicketMessage.objects.create(ticket=self.ticket, user=self.owner.profile, body='Initial message')

    def test_staff_ticket_autofill_json_is_not_html_escaped(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse('ticket', args=[self.ticket.id]))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        start = content.index('const AUTOFILL_OPTIONS = ')
        autofill_script = content[start:content.index('\n', start)]
        self.assertIn('const AUTOFILL_OPTIONS = [{"en": "No comments"', autofill_script)
        self.assertNotIn('&#34;', autofill_script)
        self.assertNotIn('&quot;', autofill_script)
