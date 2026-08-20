import os
import stat
import zipfile
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from judge.models import ContestSubmission, Language, Submission, SubmissionSource
from judge.models.tests.util import create_contest, create_contest_participation, create_contest_problem, \
    create_problem, create_user
from judge.tasks.themis import _write_archive, prepare_contest_themis


class ContestThemisExportTaskTestCase(TestCase):
    fixtures = ['language_all.json']

    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        cls.contest = create_contest(
            key='themis_export_task',
            start_time=now - timezone.timedelta(hours=2),
            end_time=now - timezone.timedelta(hours=1),
            is_visible=True,
        )
        cls.alice = create_user(username='themis_alice')
        cls.empty_user = create_user(username='themis_empty')
        cls.virtual_user = create_user(username='themis_virtual')
        cls.alice_participation = create_contest_participation(
            contest=cls.contest,
            user=cls.alice.profile,
        )
        create_contest_participation(contest=cls.contest, user=cls.empty_user.profile)
        cls.virtual_participation = create_contest_participation(
            contest=cls.contest,
            user=cls.virtual_user.profile,
            virtual=1,
        )

        cls.problem_a = create_problem(code='themis_a', points=100)
        cls.problem_b = create_problem(code='themis_b', points=100)
        cls.contest_problem_a = create_contest_problem(
            contest=cls.contest,
            problem=cls.problem_a,
            points=100,
            order=0,
        )
        cls.contest_problem_b = create_contest_problem(
            contest=cls.contest,
            problem=cls.problem_b,
            points=100,
            order=1,
        )
        cls.python = Language.get_python3()
        cls.cpp = Language.objects.get(key='CPP17')

        cls.create_submission(
            cls.alice,
            cls.alice_participation,
            cls.problem_a,
            cls.contest_problem_a,
            cls.python,
            100,
            'best-a',
        )
        cls.create_submission(
            cls.alice,
            cls.alice_participation,
            cls.problem_a,
            cls.contest_problem_a,
            cls.cpp,
            25,
            'last-a',
        )
        cls.create_submission(
            cls.alice,
            cls.alice_participation,
            cls.problem_b,
            cls.contest_problem_b,
            cls.python,
            50,
            'older-tie-b',
        )
        cls.create_submission(
            cls.alice,
            cls.alice_participation,
            cls.problem_b,
            cls.contest_problem_b,
            cls.cpp,
            50,
            'newer-tie-b',
        )
        cls.create_submission(
            cls.virtual_user,
            cls.virtual_participation,
            cls.problem_a,
            cls.contest_problem_a,
            cls.python,
            100,
            'virtual-a',
        )

    @classmethod
    def create_submission(cls, user, participation, problem, contest_problem, language, points, source):
        submission = Submission.objects.create(
            user=user.profile,
            problem=problem,
            language=language,
            contest_object=cls.contest,
            result='AC' if points == 100 else 'PAC',
            status='D',
            case_points=points,
            case_total=100,
        )
        SubmissionSource.objects.create(submission=submission, source=source)
        ContestSubmission.objects.create(
            submission=submission,
            problem=contest_problem,
            participation=participation,
            points=points,
        )
        return submission

    def run_export(self, directory, selection):
        with override_settings(DMOJ_CONTEST_THEMIS_CACHE=directory), patch('judge.tasks.themis.Progress'):
            return prepare_contest_themis.run(self.contest.id, selection)

    def test_best_export_uses_score_then_latest_tie_and_excludes_virtual(self):
        with TemporaryDirectory() as directory:
            self.assertEqual(self.run_export(directory, 'best'), 2)
            archive_path = os.path.join(directory, '%s-best.zip' % self.contest.id)
            self.assertEqual(stat.S_IMODE(os.stat(archive_path).st_mode), 0o644)
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(set(archive.namelist()), {
                    'themis_alice/',
                    'themis_empty/',
                    'themis_alice/themis_a.py',
                    'themis_alice/themis_b.cpp',
                })
                self.assertEqual(archive.read('themis_alice/themis_a.py'), b'best-a')
                self.assertEqual(archive.read('themis_alice/themis_b.cpp'), b'newer-tie-b')

    def test_last_export_uses_latest_submission(self):
        with TemporaryDirectory() as directory:
            self.assertEqual(self.run_export(directory, 'last'), 2)
            with zipfile.ZipFile(os.path.join(directory, '%s-last.zip' % self.contest.id)) as archive:
                self.assertEqual(archive.read('themis_alice/themis_a.cpp'), b'last-a')
                self.assertEqual(archive.read('themis_alice/themis_b.cpp'), b'newer-tie-b')
                self.assertNotIn('themis_alice/$History/', archive.namelist())

    def test_file_only_submission_is_copied_into_archive(self):
        file_language = Language.objects.create(
            key='THEMISFILE',
            name='Themis file',
            short_name='FILE',
            common_name='File',
            ace='text',
            pygments='text',
            template='',
            extension='dat',
            file_only=True,
        )
        problem = create_problem(code='themis_file', points=100)
        contest_problem = create_contest_problem(
            contest=self.contest,
            problem=problem,
            points=100,
            order=2,
        )

        with TemporaryDirectory() as media_directory, TemporaryDirectory() as export_directory, \
                override_settings(MEDIA_ROOT=media_directory, DMOJ_CONTEST_THEMIS_CACHE=export_directory):
            storage_path = os.path.join(
                'submission_file',
                problem.code,
                str(self.alice.id),
                'uploaded.dat',
            )
            default_storage.save(storage_path, ContentFile(b'file-only-content'))
            self.create_submission(
                self.alice,
                self.alice_participation,
                problem,
                contest_problem,
                file_language,
                100,
                '/submission_file/%s/%s/uploaded.dat' % (problem.code, self.alice.id),
            )

            with patch('judge.tasks.themis.Progress'):
                prepare_contest_themis.run(self.contest.id, 'last')

            archive_path = os.path.join(export_directory, '%s-last.zip' % self.contest.id)
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(
                    archive.read('themis_alice/themis_file.dat'),
                    b'file-only-content',
                )

    def test_failed_export_does_not_replace_existing_archive(self):
        class NoopProgress:
            def did(self, count):
                pass

        with TemporaryDirectory() as directory, override_settings(DMOJ_CONTEST_THEMIS_CACHE=directory):
            archive_path = os.path.join(directory, '%s-best.zip' % self.contest.id)
            with open(archive_path, 'wb') as archive:
                archive.write(b'existing-archive')

            with self.assertRaises(ValueError):
                _write_archive(
                    self.contest.id,
                    'best',
                    [(self.alice.id, self.alice.username)],
                    [(self.alice.id, self.alice.username, self.problem_a.code, 'source', 'bad/ext', False)],
                    NoopProgress(),
                )

            with open(archive_path, 'rb') as archive:
                self.assertEqual(archive.read(), b'existing-archive')
            self.assertEqual(os.listdir(directory), ['%s-best.zip' % self.contest.id])

    def test_export_rejects_case_insensitive_username_collisions(self):
        class NoopProgress:
            def did(self, count):
                pass

        with TemporaryDirectory() as directory, override_settings(DMOJ_CONTEST_THEMIS_CACHE=directory):
            with self.assertRaises(ValueError):
                _write_archive(
                    self.contest.id,
                    'best',
                    [(1, 'ThemisUser'), (2, 'themisuser')],
                    [],
                    NoopProgress(),
                )
            self.assertEqual(os.listdir(directory), [])

    def test_export_does_not_touch_generic_contest_data_cache(self):
        with TemporaryDirectory() as themis_directory, TemporaryDirectory() as data_directory:
            data_path = os.path.join(data_directory, '%s.zip' % self.contest.id)
            with open(data_path, 'wb') as archive:
                archive.write(b'generic-contest-data')

            with override_settings(
                DMOJ_CONTEST_THEMIS_CACHE=themis_directory,
                DMOJ_CONTEST_DATA_CACHE=data_directory,
            ), patch('judge.tasks.themis.Progress'):
                prepare_contest_themis.run(self.contest.id, 'best')

            with open(data_path, 'rb') as archive:
                self.assertEqual(archive.read(), b'generic-contest-data')
            self.assertTrue(os.path.exists(os.path.join(themis_directory, '%s-best.zip' % self.contest.id)))


class ContestThemisExportViewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        cls.editor = create_user(
            username='themis_editor',
            is_staff=True,
            user_permissions=('edit_own_contest',),
        )
        cls.outsider = create_user(username='themis_outsider')
        cls.contest = create_contest(
            key='themis_export_view',
            start_time=now - timezone.timedelta(hours=2),
            end_time=now - timezone.timedelta(hours=1),
            is_visible=True,
            authors=(cls.editor.username,),
        )
        cls.active_contest = create_contest(
            key='themis_export_active',
            start_time=now - timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=1),
            is_visible=True,
            authors=(cls.editor.username,),
        )

    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings_override = override_settings(
            DMOJ_CONTEST_THEMIS_EXPORT=True,
            DMOJ_CONTEST_THEMIS_CACHE=self.directory.name,
            DMOJ_CONTEST_THEMIS_INTERNAL='',
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        cache.delete('celery_status_id:contest_themis_export_%s' % self.contest.id)

    def prepare_url(self, contest=None):
        return reverse('contest_prepare_themis', args=[(contest or self.contest).key])

    def test_editor_can_open_export_form_and_see_contest_button(self):
        self.client.force_login(self.editor)
        response = self.client.get(self.prepare_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="submission_selection"')

        response = self.client.get(reverse('contest_view', args=[self.contest.key]))
        self.assertContains(response, self.prepare_url())

    def test_export_requires_enabled_setting_editor_and_ended_contest(self):
        self.client.force_login(self.editor)
        with override_settings(DMOJ_CONTEST_THEMIS_EXPORT=False):
            response = self.client.get(self.prepare_url())
            self.assertContains(response, 'No such contest')

        self.client.force_login(self.outsider)
        self.assertContains(self.client.get(self.prepare_url()), 'Permission denied')

        self.client.force_login(self.editor)
        self.assertContains(self.client.get(self.prepare_url(self.active_contest)), 'Permission denied')

    def test_post_starts_dedicated_themis_task(self):
        self.client.force_login(self.editor)
        result = SimpleNamespace(id='themis-task-id')
        with patch('judge.views.contests.prepare_contest_themis.delay', return_value=result) as delay:
            response = self.client.post(self.prepare_url(), {'submission_selection': 'last'})

        self.assertEqual(response.status_code, 302)
        delay.assert_called_once_with(self.contest.id, 'last')

    def test_download_uses_separate_archive_and_filename(self):
        archive_path = os.path.join(self.directory.name, '%s-best.zip' % self.contest.id)
        with open(archive_path, 'wb') as archive:
            archive.write(b'themis-archive')

        self.client.force_login(self.editor)
        response = self.client.get(reverse('contest_download_themis', args=[self.contest.key, 'best']))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'themis-archive')
        self.assertEqual(
            response['Content-Disposition'],
            'attachment; filename="themis_export_view-themis-best.zip"',
        )

        invalid_url = reverse('contest_download_themis', args=[self.contest.key, 'invalid'])
        response = self.client.get(invalid_url)
        self.assertContains(response, 'No such contest')
