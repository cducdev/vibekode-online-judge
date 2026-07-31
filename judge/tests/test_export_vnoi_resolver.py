import json
import os
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from judge.models import ContestSubmission, Language, Submission
from judge.models.tests.util import create_contest, create_contest_participation, create_contest_problem, \
    create_problem, create_user


class ExportVNOIResolverDataTestCase(TestCase):
    fixtures = ['language_all.json']

    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        cls.contest = create_contest(
            key='resolver_export',
            start_time=now - timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=1),
            is_visible=True,
        )
        cls.user = create_user(username='resolver_user', first_name='Resolver', last_name='User')
        cls.virtual_user = create_user(username='resolver_virtual')
        cls.problem = create_problem(code='resolver_problem', name='Resolver Problem', points=100)
        cls.contest_problem = create_contest_problem(
            contest=cls.contest,
            problem=cls.problem,
            points=100,
            order=0,
        )
        cls.participation = create_contest_participation(contest=cls.contest, user=cls.user.profile)
        cls.virtual_participation = create_contest_participation(
            contest=cls.contest,
            user=cls.virtual_user.profile,
            virtual=1,
        )
        cls.submission = cls.create_submission(cls.user, cls.participation, 'AC', 'D', 100, now)
        cls.create_submission(cls.user, cls.participation, 'CE', 'CE', 0, now + timezone.timedelta(seconds=1))
        cls.create_submission(
            cls.virtual_user,
            cls.virtual_participation,
            'AC',
            'D',
            100,
            now + timezone.timedelta(seconds=2),
        )

    @classmethod
    def create_submission(cls, user, participation, result, status, points, submitted_at):
        submission = Submission.objects.create(
            user=user.profile,
            problem=cls.problem,
            language=Language.get_python3(),
            contest_object=cls.contest,
            result=result,
            status=status,
            case_points=points,
            case_total=100,
        )
        Submission.objects.filter(id=submission.id).update(date=submitted_at)
        ContestSubmission.objects.create(
            submission=submission,
            problem=cls.contest_problem,
            participation=participation,
            points=points,
        )
        return submission

    def test_exports_live_participants_and_graded_submissions(self):
        with TemporaryDirectory() as directory:
            output = os.path.join(directory, 'resolver.json')
            call_command('export_vnoi_resolver_data', self.contest.key, output)
            with open(output, encoding='utf-8') as exported:
                data = json.load(exported)

        self.assertEqual(data['users'], [{
            'userId': self.user.id,
            'username': self.user.username,
            'fullName': 'Resolver User',
        }])
        self.assertEqual(data['problems'], [{
            'problemId': self.problem.id,
            'name': 'Resolver Problem',
            'points': 100,
        }])
        self.assertEqual(len(data['submissions']), 1)
        self.assertEqual(data['submissions'][0]['submissionId'], self.submission.id)
        self.assertEqual(data['submissions'][0]['points'], 100)

    def test_rejects_invalid_output_extension(self):
        with self.assertRaises(CommandError):
            call_command('export_vnoi_resolver_data', self.contest.key, 'resolver.txt')

    def test_rejects_unknown_contest(self):
        with self.assertRaises(CommandError):
            call_command('export_vnoi_resolver_data', 'missing', 'resolver.json')
