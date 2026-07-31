from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from judge.models import Contest, ContestSubmission, Language, Solution, Submission, SubmissionTestCase
from judge.models.tests.util import (
    create_contest,
    create_contest_participation,
    create_contest_problem,
    create_organization,
    create_problem,
    create_solution,
    create_user,
)


class ContestLiveSubmissionsTestCase(TestCase):
    fixtures = ['language_all.json']

    @classmethod
    def setUpTestData(cls):
        cls.now = timezone.now()
        cls.editor = create_user(
            username='live_editor',
            is_staff=True,
            user_permissions=('edit_own_contest',),
        )
        cls.contestant = create_user(username='live_contestant', first_name='Live', last_name='Contestant')
        cls.virtual_user = create_user(username='live_virtual')
        cls.outsider = create_user(username='live_outsider')
        cls.language = Language.get_python3()
        cls.organization = create_organization(
            name='Live School',
            slug='live-school',
            short_name='LS',
            is_unlisted=False,
        )
        cls.contestant.profile.organizations.add(cls.organization)

        cls.contest = create_contest(
            key='live_feed',
            start_time=cls.now - timezone.timedelta(hours=1),
            end_time=cls.now + timezone.timedelta(hours=1),
            is_visible=True,
            scoreboard_visibility=Contest.SCOREBOARD_HIDDEN,
            ranking_access_code='broadcast-code',
            authors=('live_editor',),
        )
        cls.problem = create_problem(code='live_problem', points=100)
        cls.contest_problem = create_contest_problem(
            contest=cls.contest,
            problem=cls.problem,
            points=100,
            order=0,
        )
        cls.participation = create_contest_participation(
            contest=cls.contest,
            user=cls.contestant.profile,
        )
        cls.virtual_participation = create_contest_participation(
            contest=cls.contest,
            user=cls.virtual_user.profile,
            virtual=1,
        )

        cls.live_submission = cls.create_submission(
            cls.contestant,
            cls.participation,
            result='AC',
            points=100,
            submitted_at=cls.now - timezone.timedelta(seconds=30),
        )
        cls.pending_submission = cls.create_submission(
            cls.contestant,
            cls.participation,
            result=None,
            status='G',
            points=0,
            submitted_at=cls.now - timezone.timedelta(seconds=10),
        )
        cls.create_submission(
            cls.virtual_user,
            cls.virtual_participation,
            result='WA',
            points=0,
            submitted_at=cls.now - timezone.timedelta(seconds=5),
        )
        cls.create_submission(
            cls.contestant,
            cls.participation,
            result='WA',
            points=0,
            submitted_at=cls.now - timezone.timedelta(minutes=10),
        )

        cls.frozen_contest = create_contest(
            key='live_feed_frozen',
            format_name='vnoj',
            format_config={},
            start_time=cls.now - timezone.timedelta(hours=1),
            end_time=cls.now + timezone.timedelta(minutes=2),
            frozen_last_minutes=3,
            is_visible=True,
            scoreboard_visibility=Contest.SCOREBOARD_HIDDEN,
            authors=('live_editor',),
        )
        cls.frozen_problem = create_problem(code='live_frozen_problem', points=100)
        cls.frozen_contest_problem = create_contest_problem(
            contest=cls.frozen_contest,
            problem=cls.frozen_problem,
            points=100,
            order=0,
        )
        cls.frozen_participation = create_contest_participation(
            contest=cls.frozen_contest,
            user=cls.contestant.profile,
        )
        cls.before_freeze = cls.create_submission(
            cls.contestant,
            cls.frozen_participation,
            contest=cls.frozen_contest,
            problem=cls.frozen_problem,
            contest_problem=cls.frozen_contest_problem,
            result='AC',
            points=100,
            submitted_at=cls.now - timezone.timedelta(minutes=2),
        )
        cls.create_submission(
            cls.contestant,
            cls.frozen_participation,
            contest=cls.frozen_contest,
            problem=cls.frozen_problem,
            contest_problem=cls.frozen_contest_problem,
            result='WA',
            points=0,
            submitted_at=cls.now - timezone.timedelta(seconds=30),
        )

        cls.hidden_contest = create_contest(
            key='live_feed_hidden',
            format_name='new_ioi',
            format_config={},
            start_time=cls.now - timezone.timedelta(hours=1),
            end_time=cls.now + timezone.timedelta(hours=1),
            is_visible=True,
            scoreboard_visibility=Contest.SCOREBOARD_HIDDEN,
            ranking_access_code='hidden-broadcast-code',
            authors=('live_editor',),
        )
        cls.hidden_problem = create_problem(code='live_hidden_problem', points=100)
        cls.hidden_contest_problem = create_contest_problem(
            contest=cls.hidden_contest,
            problem=cls.hidden_problem,
            points=100,
            order=0,
            hidden_subtasks='1',
        )
        cls.hidden_participation = create_contest_participation(
            contest=cls.hidden_contest,
            user=cls.contestant.profile,
        )
        cls.hidden_submission = cls.create_submission(
            cls.contestant,
            cls.hidden_participation,
            contest=cls.hidden_contest,
            problem=cls.hidden_problem,
            contest_problem=cls.hidden_contest_problem,
            result='AC',
            points=100,
            submitted_at=cls.now - timezone.timedelta(seconds=20),
        )
        SubmissionTestCase.objects.bulk_create([
            SubmissionTestCase(
                submission=cls.hidden_submission,
                case=1,
                batch=1,
                status='AC',
                points=70,
                total=70,
                time=0.01,
                memory=1024,
            ),
            SubmissionTestCase(
                submission=cls.hidden_submission,
                case=2,
                batch=2,
                status='AC',
                points=30,
                total=30,
                time=0.01,
                memory=1024,
            ),
        ])
        cls.visible_problem = create_problem(code='live_visible_problem', points=100)
        cls.visible_contest_problem = create_contest_problem(
            contest=cls.hidden_contest,
            problem=cls.visible_problem,
            points=100,
            order=1,
        )
        cls.visible_submission = cls.create_submission(
            cls.contestant,
            cls.hidden_participation,
            contest=cls.hidden_contest,
            problem=cls.visible_problem,
            contest_problem=cls.visible_contest_problem,
            result='WA',
            points=0,
            submitted_at=cls.now - timezone.timedelta(seconds=25),
        )

    @classmethod
    def create_submission(cls, user, participation, result, points, submitted_at, status='D',
                          contest=None, problem=None, contest_problem=None):
        contest = contest or cls.contest
        problem = problem or cls.problem
        contest_problem = contest_problem or cls.contest_problem
        submission = Submission.objects.create(
            user=user.profile,
            problem=problem,
            language=cls.language,
            contest_object=contest,
            result=result,
            status=status,
            case_points=points,
            case_total=100,
        )
        Submission.objects.filter(id=submission.id).update(date=submitted_at)
        submission.date = submitted_at
        ContestSubmission.objects.create(
            submission=submission,
            problem=contest_problem,
            participation=participation,
            points=points,
        )
        return submission

    def feed_url(self, contest=None):
        return reverse('contest_submission_feed', args=[(contest or self.contest).key])

    def page_url(self, contest=None):
        return reverse('contest_submission_live', args=[(contest or self.contest).key])

    def test_feed_requires_scoreboard_access(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.feed_url()).status_code, 403)

        self.client.force_login(self.editor)
        self.assertEqual(self.client.get(self.feed_url()).status_code, 200)

    def test_ranking_access_code_grants_feed_and_page_access(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.feed_url(), {'code': 'wrong'}).status_code, 403)
        self.assertEqual(self.client.get(self.feed_url(), {'code': 'broadcast-code'}).status_code, 200)
        self.assertEqual(self.client.get(self.page_url(), {'code': 'broadcast-code'}).status_code, 200)

    def test_feed_returns_recent_live_submissions_only(self):
        self.client.force_login(self.editor)
        response = self.client.get(self.feed_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
        payload = response.json()
        self.assertEqual(
            [submission['id'] for submission in payload['submissions']],
            [self.pending_submission.id, self.live_submission.id],
        )
        self.assertIsNone(payload['submissions'][0]['points'])
        self.assertEqual(payload['submissions'][1]['points'], 100)
        self.assertEqual(payload['submissions'][1]['problem']['label'], '1')
        user = payload['submissions'][1]['user']
        self.assertEqual(user['username'], 'live_contestant')
        self.assertEqual(user['name'], 'live_contestant')
        self.assertEqual(user['display_name'], 'live_contestant')
        self.assertEqual(user['full_name'], 'Live Contestant')
        self.assertIsNone(user['badge'])
        self.assertEqual(user['organization']['short_name'], 'LS')
        self.assertEqual(payload['next_poll_ms'], 1500)

    def test_feed_hides_submissions_after_freeze(self):
        self.client.force_login(self.editor)
        response = self.client.get(self.feed_url(self.frozen_contest))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['frozen'])
        self.assertEqual([submission['id'] for submission in payload['submissions']], [self.before_freeze.id])

    def test_feed_masks_hidden_subtask_results_for_public_broadcast(self):
        self.client.logout()
        response = self.client.get(
            self.feed_url(self.hidden_contest),
            {'code': 'hidden-broadcast-code'},
        )

        self.assertEqual(response.status_code, 200)
        submissions = {
            submission['id']: submission for submission in response.json()['submissions']
        }
        submission = submissions[self.hidden_submission.id]
        self.assertEqual(submission['id'], self.hidden_submission.id)
        self.assertEqual(submission['status_display'], 'Hidden')
        self.assertEqual(submission['result_class'], 'masked')
        self.assertEqual(submission['points'], 30)
        self.assertTrue(submission['is_masked'])
        visible_submission = submissions[self.visible_submission.id]
        self.assertEqual(visible_submission['status_display'], 'WA')
        self.assertEqual(visible_submission['points'], 0)
        self.assertFalse(visible_submission['is_masked'])

        self.client.force_login(self.editor)
        submissions = {
            submission['id']: submission
            for submission in self.client.get(self.feed_url(self.hidden_contest)).json()['submissions']
        }
        submission = submissions[self.hidden_submission.id]
        self.assertEqual(submission['status_display'], 'AC')
        self.assertEqual(submission['points'], 100)
        self.assertFalse(submission['is_masked'])

    def test_embed_page_has_no_site_chrome(self):
        self.client.force_login(self.editor)
        response = self.client.get(self.page_url(), {'embed': '1', 'theme': 'dark'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="contest-live-submissions-embed"')
        self.assertContains(response, 'contest-live-submissions.js')
        self.assertContains(response, f'data-event-channel="contest_{self.contest.id}"')
        self.assertNotContains(response, 'id="navigation"')


class ContestProblemMakePublicTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls._now = timezone.now()

        cls.staff_editor = create_user(
            username='staff_editor',
            is_staff=True,
            is_superuser=True,
        )

        cls.normal_user = create_user(
            username='normal_user',
        )

        cls.contest = create_contest(
            key='test_publish',
            start_time=cls._now - timezone.timedelta(days=10),
            end_time=cls._now - timezone.timedelta(days=1),
            is_visible=True,
            authors=('staff_editor',),
        )

        # Private problem WITH editorial
        cls.problem_with_editorial = create_problem(
            code='prob_with_editorial',
            is_public=False,
            authors=('staff_editor',),
        )
        cls.solution = create_solution(
            problem=cls.problem_with_editorial,
            is_public=False,
            publish_on=cls._now + timezone.timedelta(days=100),
            content='Editorial content',
        )
        create_contest_problem(
            contest=cls.contest,
            problem=cls.problem_with_editorial,
            order=1,
        )

        # Private problem WITHOUT editorial
        cls.problem_without_editorial = create_problem(
            code='prob_no_editorial',
            is_public=False,
            authors=('staff_editor',),
        )
        create_contest_problem(
            contest=cls.contest,
            problem=cls.problem_without_editorial,
            order=2,
        )

        # Already-public problem with unpublished editorial
        cls.public_problem = create_problem(
            code='prob_already_public',
            is_public=True,
            authors=('staff_editor',),
        )
        cls.public_problem_solution = create_solution(
            problem=cls.public_problem,
            is_public=False,
            publish_on=cls._now + timezone.timedelta(days=100),
            content='Hidden editorial for public problem',
        )
        create_contest_problem(
            contest=cls.contest,
            problem=cls.public_problem,
            order=3,
        )

    def _get_url(self):
        return reverse('contest_problems_make_public', args=[self.contest.key])

    @patch('judge.views.contests.rescore_problem')
    def test_publishes_problems_and_editorials(self, mock_rescore):
        self.client.force_login(self.staff_editor)
        response = self.client.post(self._get_url())

        self.assertEqual(response.status_code, 302)

        self.problem_with_editorial.refresh_from_db()
        self.assertTrue(self.problem_with_editorial.is_public)

        self.solution.refresh_from_db()
        self.assertTrue(self.solution.is_public)
        self.assertLessEqual(self.solution.publish_on, timezone.now())

    @patch('judge.views.contests.rescore_problem')
    def test_no_editorial_does_not_break(self, mock_rescore):
        self.client.force_login(self.staff_editor)
        response = self.client.post(self._get_url())

        self.assertEqual(response.status_code, 302)

        self.problem_without_editorial.refresh_from_db()
        self.assertTrue(self.problem_without_editorial.is_public)
        self.assertFalse(Solution.objects.filter(problem=self.problem_without_editorial).exists())

    @patch('judge.views.contests.rescore_problem')
    def test_already_public_problem_editorial_should_be_published(self, mock_rescore):
        self.client.force_login(self.staff_editor)
        self.client.post(self._get_url())

        self.public_problem_solution.refresh_from_db()
        self.assertTrue(self.public_problem_solution.is_public)
        self.assertLessEqual(self.public_problem_solution.publish_on, timezone.now())

    @patch('judge.views.contests.rescore_problem')
    def test_rescore_called_for_published_problems(self, mock_rescore):
        self.client.force_login(self.staff_editor)
        self.client.post(self._get_url())

        rescore_ids = {call.args[0] for call in mock_rescore.delay.call_args_list}
        self.assertIn(self.problem_with_editorial.id, rescore_ids)
        self.assertIn(self.problem_without_editorial.id, rescore_ids)
        self.assertNotIn(self.public_problem.id, rescore_ids)

    def test_get_request_forbidden(self):
        self.client.force_login(self.staff_editor)
        response = self.client.get(self._get_url())
        self.assertEqual(response.status_code, 403)

    @patch('judge.views.contests.rescore_problem')
    def test_normal_user_permission_denied(self, mock_rescore):
        self.client.force_login(self.normal_user)
        self.client.post(self._get_url())

        self.problem_with_editorial.refresh_from_db()
        self.assertFalse(self.problem_with_editorial.is_public)
        mock_rescore.delay.assert_not_called()
