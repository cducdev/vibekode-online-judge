from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from judge.models import Contest, ContestParticipation, ContestSubmission, ContestTag, Language, ProblemTestCase, \
    Submission, SubmissionTestCase
from judge.models.contest import MinValueOrNoneValidator
from judge.models.tests.util import CommonDataMixin, create_contest, create_contest_participation, \
    create_contest_problem, create_problem, create_user


class ContestTestCase(CommonDataMixin, TestCase):
    @classmethod
    def setUpTestData(self):
        super().setUpTestData()
        self.users.update({
            'staff_contest_edit_own': create_user(
                username='staff_contest_edit_own',
                is_staff=True,
                user_permissions=('edit_own_contest',),
            ),
            'staff_contest_see_all': create_user(
                username='staff_contest_see_all',
                user_permissions=('see_private_contest',),
            ),
            'staff_contest_edit_all': create_user(
                username='staff_contest_edit_all',
                is_staff=True,
                user_permissions=('edit_own_contest', 'edit_all_contest'),
            ),
            'normal_during_window': create_user(
                username='normal_during_window',
            ),
            'normal_after_window': create_user(
                username='normal_after_window',
            ),
            'normal_before_window': create_user(
                username='normal_before_window',
            ),
            'non_staff_author': create_user(
                username='non_staff_author',
                is_staff=False,
            ),
            'non_staff_tester': create_user(
                username='non_staff_tester',
                is_staff=False,
            ),
        })

        _now = timezone.now()

        self.basic_contest = create_contest(
            key='basic',
            start_time=_now - timezone.timedelta(days=1),
            end_time=_now + timezone.timedelta(days=100),
            authors=('superuser', 'staff_contest_edit_own'),
            testers=('non_staff_tester',),
        )

        self.hidden_scoreboard_contest = create_contest(
            key='hidden_scoreboard',
            start_time=_now - timezone.timedelta(days=1),
            end_time=_now + timezone.timedelta(days=100),
            is_visible=True,
            scoreboard_visibility=Contest.SCOREBOARD_AFTER_CONTEST,
            problem_label_script="""
                function(n)
                    return tostring(math.floor(n))
                end
            """,
        )

        self.hidden_scoreboard_non_staff_author = create_contest(
            key='non_staff_author',
            start_time=_now - timezone.timedelta(days=1),
            end_time=_now + timezone.timedelta(days=100),
            is_visible=True,
            scoreboard_visibility=Contest.SCOREBOARD_AFTER_CONTEST,
            authors=('non_staff_author',),
            curators=('staff_contest_edit_own',),
        )

        self.contest_hidden_scoreboard_contest = create_contest(
            key='contest_scoreboard',
            start_time=_now - timezone.timedelta(days=10),
            end_time=_now + timezone.timedelta(days=100),
            time_limit=timezone.timedelta(days=1),
            is_visible=True,
            scoreboard_visibility=Contest.SCOREBOARD_AFTER_CONTEST,
            testers=('non_staff_tester',),
        )

        self.particip_hidden_scoreboard_contest = create_contest(
            key='particip_scoreboard',
            start_time=_now - timezone.timedelta(days=10),
            end_time=_now + timezone.timedelta(days=100),
            time_limit=timezone.timedelta(days=1),
            is_visible=True,
            scoreboard_visibility=Contest.SCOREBOARD_AFTER_PARTICIPATION,
            testers=('non_staff_tester',),
        )

        self.visible_scoreboard_contest = create_contest(
            key='visible_scoreboard',
            start_time=_now - timezone.timedelta(days=10),
            end_time=_now + timezone.timedelta(days=100),
            time_limit=timezone.timedelta(days=1),
            is_visible=True,
            scoreboard_visibility=Contest.SCOREBOARD_VISIBLE,
            testers=('non_staff_tester',),
        )

        for contest_key in ('contest_scoreboard', 'particip_scoreboard', 'visible_scoreboard'):
            create_contest_participation(
                contest=contest_key,
                user='normal_during_window',
                real_start=_now - timezone.timedelta(hours=1),
                virtual=ContestParticipation.LIVE,
            )

            create_contest_participation(
                contest=contest_key,
                user='normal_after_window',
                real_start=_now - timezone.timedelta(days=3),
                virtual=ContestParticipation.LIVE,
            )

        create_contest_participation(
            contest='particip_scoreboard',
            user='normal',
            real_start=_now - timezone.timedelta(days=3),
            virtual=ContestParticipation.LIVE,
        )

        create_contest_participation(
            contest='particip_scoreboard',
            user='normal',
            real_start=_now + timezone.timedelta(days=101),
            virtual=ContestParticipation.SPECTATE,
        )

        self.users['normal'].profile.current_contest = create_contest_participation(
            contest='hidden_scoreboard',
            user='normal',
        )
        self.users['normal'].profile.save()

        self.hidden_scoreboard_contest.update_user_count()

        self.private_contest = create_contest(
            key='private',
            start_time=_now - timezone.timedelta(days=5),
            end_time=_now - timezone.timedelta(days=3),
            is_visible=True,
            is_private=True,
            is_organization_private=True,
            private_contestants=('staff_contest_edit_own',),
            testers=('non_staff_tester',),
        )

        self.organization_private_contest = create_contest(
            key='organization_private',
            start_time=_now - timezone.timedelta(days=5),
            end_time=_now + timezone.timedelta(days=6),
            is_visible=True,
            is_organization_private=True,
            organization=self.organizations['open'],
            view_contest_scoreboard=('normal',),
            testers=('non_staff_tester',),
        )

        self.future_organization_private_contest = create_contest(
            key='future_org_private',
            start_time=_now + timezone.timedelta(days=3),
            end_time=_now + timezone.timedelta(days=6),
            is_visible=True,
            is_organization_private=True,
            organization=self.organizations['open'],
            view_contest_scoreboard=('normal',),
            testers=('non_staff_tester',),
        )

        self.private_user_contest = create_contest(
            key='private_user',
            start_time=_now - timezone.timedelta(days=3),
            end_time=_now + timezone.timedelta(days=6),
            is_visible=True,
            is_private=True,
            testers=('non_staff_tester',),
        )

        self.non_visible_contest = create_contest(
            key='non_visible_contest',
            start_time=_now - timezone.timedelta(days=3),
            end_time=_now + timezone.timedelta(days=6),
            is_visible=False,
        )

        self.non_visible_contest_with_tester = create_contest(
            key='non_visible_w_tester',
            start_time=_now - timezone.timedelta(days=3),
            end_time=_now + timezone.timedelta(days=6),
            is_visible=False,
            testers=('non_staff_tester',),
        )

    def setUp(self):
        self.users['normal'].profile.refresh_from_db()

    def test_basic_contest(self):
        self.assertTrue(self.basic_contest.show_scoreboard)
        self.assertEqual(self.basic_contest.contest_window_length, timezone.timedelta(days=101))
        self.assertIsInstance(self.basic_contest._now, timezone.datetime)
        self.assertTrue(self.basic_contest.can_join)
        self.assertIsNone(self.basic_contest.time_before_start)
        self.assertIsInstance(self.basic_contest.time_before_end, timezone.timedelta)
        self.assertFalse(self.basic_contest.ended)
        self.assertEqual(str(self.basic_contest), self.basic_contest.name)
        self.assertEqual(self.basic_contest.get_label_for_problem(0), '1')

    def test_hidden_scoreboard_contest(self):
        self.assertFalse(self.hidden_scoreboard_contest.show_scoreboard)
        for i in range(3):
            with self.subTest(contest_problem_index=i):
                self.assertEqual(self.hidden_scoreboard_contest.get_label_for_problem(i), str(i))
        self.assertEqual(self.hidden_scoreboard_contest.user_count, 1)

    def test_private_contest(self):
        self.assertTrue(self.private_contest.can_join)
        self.assertIsNone(self.private_contest.time_before_start)
        self.assertIsNone(self.private_contest.time_before_end)

    def test_organization_private_contest(self):
        self.assertTrue(self.organization_private_contest.can_join)
        self.assertTrue(self.organization_private_contest.show_scoreboard)
        self.assertFalse(self.organization_private_contest.ended)
        self.assertIsNone(self.organization_private_contest.time_before_start)
        self.assertIsInstance(self.organization_private_contest.time_before_end, timezone.timedelta)

    def test_future_organization_private_contest(self):
        self.assertFalse(self.future_organization_private_contest.can_join)
        self.assertFalse(self.future_organization_private_contest.show_scoreboard)
        self.assertFalse(self.future_organization_private_contest.ended)
        self.assertIsInstance(self.future_organization_private_contest.time_before_start, timezone.timedelta)
        self.assertIsInstance(self.future_organization_private_contest.time_before_end, timezone.timedelta)

    def test_basic_contest_methods(self):
        with self.assertRaises(Contest.Inaccessible):
            self.basic_contest.access_check(self.users['normal'])

        data = {
            'superuser': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertTrue,
                'is_in_contest': self.assertFalse,
            },
            'staff_contest_edit_own': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertTrue,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertTrue,
                'is_in_contest': self.assertFalse,
            },
            'staff_contest_see_all': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
            'staff_contest_edit_all': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertTrue,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertTrue,
                'is_in_contest': self.assertFalse,
            },
            'normal': {
                # scoreboard checks don't do accessibility checks
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertFalse,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
            'non_staff_tester': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
            'anonymous': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertFalse,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
        }
        self._test_object_methods_with_users(self.basic_contest, data)

    def test_hidden_scoreboard_contest_methods(self):
        data = {
            'staff_contest_edit_own': {
                'can_see_own_scoreboard': self.assertFalse,
                'can_see_full_scoreboard': self.assertFalse,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
            'staff_contest_see_all': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
            'staff_contest_edit_all': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertTrue,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertTrue,
                'is_in_contest': self.assertFalse,
            },
            'normal': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertFalse,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertTrue,
            },
            'anonymous': {
                'can_see_own_scoreboard': self.assertFalse,
                'can_see_full_scoreboard': self.assertFalse,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
        }
        self._test_object_methods_with_users(self.hidden_scoreboard_contest, data)

    def test_contest_hidden_scoreboard_non_staff_author_contest_methods(self):
        data = {
            'staff_contest_edit_own': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertTrue,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertTrue,
                'is_in_contest': self.assertFalse,
            },
            'non_staff_author': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertTrue,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
        }
        self._test_object_methods_with_users(self.hidden_scoreboard_non_staff_author, data)

    def test_contest_hidden_scoreboard_contest_methods(self):
        data = {
            'normal_before_window': {
                'can_see_own_scoreboard': self.assertFalse,
                'can_see_full_scoreboard': self.assertFalse,
                'can_see_full_submission_list': self.assertFalse,
                'has_completed_contest': self.assertFalse,
            },
            'normal_during_window': {
                'can_see_own_scoreboard': self.assertFalse,
                'can_see_full_scoreboard': self.assertFalse,
                'can_see_full_submission_list': self.assertFalse,
                'has_completed_contest': self.assertFalse,
            },
            'normal_after_window': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertFalse,
                'can_see_full_submission_list': self.assertFalse,
                'has_completed_contest': self.assertTrue,
            },
            'non_staff_tester': {
                'can_see_own_scoreboard': self.assertFalse,
                'can_see_full_scoreboard': self.assertFalse,
                'can_see_full_submission_list': self.assertFalse,
                'has_completed_contest': self.assertFalse,
            },
        }
        self._test_object_methods_with_users(self.contest_hidden_scoreboard_contest, data)

    def test_particip_hidden_scoreboard_contest_methods(self):
        data = {
            'normal_before_window': {
                'can_see_own_scoreboard': self.assertFalse,
                'can_see_full_scoreboard': self.assertFalse,
                'can_see_full_submission_list': self.assertFalse,
                'has_completed_contest': self.assertFalse,
            },
            'normal_during_window': {
                'can_see_own_scoreboard': self.assertFalse,
                'can_see_full_scoreboard': self.assertFalse,
                'can_see_full_submission_list': self.assertFalse,
                'has_completed_contest': self.assertFalse,
            },
            'normal_after_window': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'has_completed_contest': self.assertTrue,
            },
            'normal': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'has_completed_contest': self.assertTrue,
            },
            'non_staff_tester': {
                'can_see_own_scoreboard': self.assertFalse,
                'can_see_full_scoreboard': self.assertFalse,
                'can_see_full_submission_list': self.assertFalse,
                'has_completed_contest': self.assertFalse,
            },
        }
        self._test_object_methods_with_users(self.particip_hidden_scoreboard_contest, data)

    def test_visible_scoreboard_contest_methods(self):
        data = {
            'normal_before_window': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'has_completed_contest': self.assertFalse,
            },
            'normal_during_window': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'has_completed_contest': self.assertFalse,
            },
            'normal_after_window': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'has_completed_contest': self.assertTrue,
            },
            'non_staff_tester': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'has_completed_contest': self.assertFalse,
            },
        }
        self._test_object_methods_with_users(self.visible_scoreboard_contest, data)

    def test_private_contest_methods(self):
        with self.assertRaises(Contest.PrivateContest):
            self.private_contest.access_check(self.users['normal'])
        self.private_contest.private_contestants.add(self.users['normal'].profile)
        with self.assertRaises(Contest.PrivateContest):
            self.private_contest.access_check(self.users['normal'])
        self.private_contest.organization = self.organizations['open']
        self.private_contest.save()
        self.users['normal'].profile.organizations.add(self.organizations['open'])

        data = {
            'normal': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertTrue,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
            'staff_contest_see_all': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertTrue,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
            'anonymous': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertTrue,
                'is_accessible_by': self.assertFalse,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
            'non_staff_tester': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertTrue,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
        }
        self._test_object_methods_with_users(self.private_contest, data)

    def test_organization_private_contest_methods(self):
        data = {
            'staff_contest_edit_own': {
                # scoreboard checks don't do accessibility checks
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertFalse,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
            'staff_contest_see_all': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
            'staff_contest_edit_all': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertTrue,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertTrue,
                'is_in_contest': self.assertFalse,
            },
            'normal': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
            'non_staff_tester': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
            'anonymous': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertFalse,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
        }
        self._test_object_methods_with_users(self.organization_private_contest, data)

    def test_future_organization_private_contest_methods(self):
        data = {
            'staff_contest_edit_own': {
                'can_see_own_scoreboard': self.assertFalse,
                'can_see_full_scoreboard': self.assertFalse,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertFalse,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
            'staff_contest_see_all': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
            'staff_contest_edit_all': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertTrue,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertTrue,
                'is_in_contest': self.assertFalse,
            },
            'normal': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
            'non_staff_tester': {
                # False because contest has not begun
                'can_see_own_scoreboard': self.assertFalse,
                'can_see_full_scoreboard': self.assertFalse,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
            'anonymous': {
                # False because contest has not begun
                'can_see_own_scoreboard': self.assertFalse,
                'can_see_full_scoreboard': self.assertFalse,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertFalse,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
        }
        self._test_object_methods_with_users(self.future_organization_private_contest, data)

    def test_private_user_contest_methods(self):
        data = {
            'superuser': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertTrue,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertTrue,
                'is_in_contest': self.assertFalse,
            },
            'normal': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertFalse,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
            'non_staff_tester': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
            'anonymous': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertFalse,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
        }
        self._test_object_methods_with_users(self.private_user_contest, data)

    def test_non_visible_contest_contest_methods(self):
        data = {
            'superuser': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertTrue,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertTrue,
                'is_in_contest': self.assertFalse,
            },
            'normal': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertFalse,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
            # not set as tester, in case something silly is happening
            'non_staff_tester': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertFalse,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
            'anonymous': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertFalse,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
        }
        self._test_object_methods_with_users(self.non_visible_contest, data)

    def test_non_visible_contest_with_tester_contest_methods(self):
        data = {
            'superuser': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertTrue,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertTrue,
                'is_in_contest': self.assertFalse,
            },
            'normal': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertFalse,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
            'non_staff_tester': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertTrue,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
            'anonymous': {
                'can_see_own_scoreboard': self.assertTrue,
                'can_see_full_scoreboard': self.assertTrue,
                'can_see_full_submission_list': self.assertFalse,
                'is_accessible_by': self.assertFalse,
                'is_editable_by': self.assertFalse,
                'is_in_contest': self.assertFalse,
            },
        }
        self._test_object_methods_with_users(self.non_visible_contest_with_tester, data)

    def test_contests_list(self):
        for name, user in self.users.items():
            with self.subTest(user=name):
                # We only care about consistency between Contest.is_accessible_by and Contest.get_visible_contests
                contest_keys = []
                for contest in Contest.objects.prefetch_related('testers', 'private_contestants', 'organization'):
                    if contest.is_accessible_by(user):
                        contest_keys.append(contest.key)

                self.assertCountEqual(
                    Contest.get_visible_contests(user).values_list('key', flat=True),
                    contest_keys,
                )

    def test_contest_clean(self):
        _now = timezone.now()
        contest = create_contest(
            key='contest',
            start_time=_now,
            end_time=_now - timezone.timedelta(days=1),
            problem_label_script='invalid',
            format_config={'invalid': 'invalid'},
        )
        with self.assertRaisesRegex(ValidationError, 'ended before it starts'):
            contest.full_clean()
        contest.end_time = _now
        with self.assertRaisesRegex(ValidationError, 'ended before it starts'):
            contest.full_clean()
        contest.end_time = _now + timezone.timedelta(days=1)
        with self.assertRaisesRegex(ValidationError, 'default contest expects'):
            contest.full_clean()
        contest.format_config = {}
        with self.assertRaisesRegex(ValidationError, 'Contest problem label script'):
            contest.full_clean()
        contest.problem_label_script = """
            function(n)
                return n
            end
        """
        # Test for bad problem label script caching
        with self.assertRaisesRegex(ValidationError, 'Contest problem label script'):
            contest.full_clean()
        del contest.get_label_for_problem
        with self.assertRaisesRegex(ValidationError, 'should return a string'):
            contest.full_clean()
        contest.problem_label_script = ''
        del contest.get_label_for_problem
        contest.full_clean()

    def test_normal_user_current_contest(self):
        current_contest = self.users['normal'].profile.current_contest
        self.assertIsNotNone(current_contest)

        current_contest.set_disqualified(True)
        self.users['normal'].profile.refresh_from_db()
        self.assertTrue(current_contest.is_disqualified)
        self.assertIsNone(self.users['normal'].profile.current_contest)
        self.assertEqual(current_contest.score, -9999)

        current_contest.set_disqualified(False)
        self.users['normal'].profile.refresh_from_db()
        self.assertFalse(current_contest.is_disqualified)
        self.assertIsNone(self.users['normal'].profile.current_contest)
        self.assertEqual(current_contest.score, 0)

    def test_live_participation(self):
        participation = ContestParticipation.objects.get(
            contest=self.hidden_scoreboard_contest,
            user=self.users['normal'].profile,
            virtual=ContestParticipation.LIVE,
        )
        self.assertTrue(participation.live)
        self.assertFalse(participation.spectate)
        self.assertEqual(participation.end_time, participation.contest.end_time)
        self.assertFalse(participation.ended)
        self.assertIsInstance(participation.time_remaining, timezone.timedelta)

    def test_spectating_participation(self):
        participation = create_contest_participation(
            contest='hidden_scoreboard',
            user='superuser',
            virtual=ContestParticipation.SPECTATE,
        )

        self.assertFalse(participation.live)
        self.assertTrue(participation.spectate)
        self.assertEqual(participation.start, participation.contest.start_time)
        self.assertEqual(participation.end_time, participation.contest.end_time)

    def test_virtual_participation(self):
        participation = create_contest_participation(
            contest='private',
            user='superuser',
            virtual=1,
        )

        self.assertFalse(participation.live)
        self.assertFalse(participation.spectate)
        self.assertEqual(participation.start, participation.real_start)
        self.assertIsInstance(participation.end_time, timezone.datetime)


class NewIOIContestFormatTestCase(CommonDataMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        now = timezone.now()
        cls.contest = create_contest(
            key='new_ioi_hidden',
            format_name='new_ioi',
            format_config={},
            start_time=now - timezone.timedelta(days=1),
            end_time=now + timezone.timedelta(days=1),
            scoreboard_visibility=Contest.SCOREBOARD_VISIBLE,
        )
        cls.problem = create_problem(code='new_ioi_problem', points=100)
        cls.contest_problem = create_contest_problem(
            contest=cls.contest,
            problem=cls.problem,
            points=100,
            hidden_subtasks='2',
        )
        cls.participation = create_contest_participation(contest=cls.contest, user='normal')

        ProblemTestCase.objects.create(
            dataset=cls.problem, order=1, type='S', points=50, is_pretest=False, batch_scoring='sum',
        )
        ProblemTestCase.objects.create(dataset=cls.problem, order=2, type='C', points=50, is_pretest=False)
        ProblemTestCase.objects.create(dataset=cls.problem, order=3, type='E', is_pretest=False)
        ProblemTestCase.objects.create(
            dataset=cls.problem, order=4, type='S', points=50, is_pretest=False, batch_scoring='sum',
        )
        ProblemTestCase.objects.create(dataset=cls.problem, order=5, type='C', points=50, is_pretest=False)
        ProblemTestCase.objects.create(dataset=cls.problem, order=6, type='E', is_pretest=False)

        cls.submission = Submission.objects.create(
            user=cls.users['normal'].profile,
            problem=cls.problem,
            language=Language.get_python3(),
            result='PAC',
            status='D',
            points=90,
            case_points=90,
            case_total=100,
            date=now,
        )
        SubmissionTestCase.objects.create(
            submission=cls.submission, case=1, status='PAC', points=40, total=50, batch=1, time=0.01, memory=1024,
        )
        SubmissionTestCase.objects.create(
            submission=cls.submission, case=2, status='AC', points=50, total=50, batch=2, time=0.01, memory=1024,
        )
        ContestSubmission.objects.create(
            submission=cls.submission,
            problem=cls.contest_problem,
            participation=cls.participation,
            points=90,
        )

    def test_hidden_subtasks_are_excluded_from_public_score(self):
        self.participation.recompute_results()

        self.assertEqual(self.participation.score, 40)
        self.assertEqual(self.participation.score_final, 90)
        self.assertEqual(self.participation.format_data[str(self.contest_problem.id)]['points'], 40)
        self.assertEqual(self.participation.format_data_final[str(self.contest_problem.id)]['points'], 90)


class UltimateContestFormatTestCase(CommonDataMixin, TestCase):
    @staticmethod
    def _create_submission_cases(submission, case_results):
        for case, (batch, points, total, status) in enumerate(case_results, 1):
            SubmissionTestCase.objects.create(
                submission=submission,
                case=case,
                status=status,
                points=points,
                total=total,
                batch=batch,
                time=0.01,
                memory=1024,
            )

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        now = timezone.now()
        cls.contest = create_contest(
            key='ultimate_last_submission',
            format_name='ultimate',
            format_config={},
            start_time=now - timezone.timedelta(days=1),
            end_time=now + timezone.timedelta(days=1),
            scoreboard_visibility=Contest.SCOREBOARD_VISIBLE,
        )
        cls.problem = create_problem(code='ultimate_problem', points=100)
        cls.contest_problem = create_contest_problem(
            contest=cls.contest,
            problem=cls.problem,
            points=100,
        )
        cls.participation = create_contest_participation(contest=cls.contest, user='normal')

        cls.older_better_submission = Submission.objects.create(
            user=cls.users['normal'].profile,
            problem=cls.problem,
            language=Language.get_python3(),
            result='AC',
            status='D',
            points=100,
            case_points=4,
            case_total=4,
            date=now,
        )
        cls._create_submission_cases(cls.older_better_submission, [
            (None, 1, 1, 'AC'),
            (None, 1, 1, 'AC'),
            (None, 1, 1, 'AC'),
            (None, 1, 1, 'AC'),
        ])
        ContestSubmission.objects.create(
            submission=cls.older_better_submission,
            problem=cls.contest_problem,
            participation=cls.participation,
            points=100,
        )

        cls.newer_worse_submission = Submission.objects.create(
            user=cls.users['normal'].profile,
            problem=cls.problem,
            language=Language.get_python3(),
            result='PAC',
            status='D',
            points=25,
            case_points=1,
            case_total=4,
            date=now + timezone.timedelta(minutes=5),
        )
        cls._create_submission_cases(cls.newer_worse_submission, [
            (None, 1, 1, 'AC'),
            (None, 0, 1, 'WA'),
            (None, 0, 1, 'WA'),
            (None, 0, 1, 'WA'),
        ])
        ContestSubmission.objects.create(
            submission=cls.newer_worse_submission,
            problem=cls.contest_problem,
            participation=cls.participation,
            points=25,
        )

        cls.hidden_contest = create_contest(
            key='ultimate_hidden',
            format_name='ultimate',
            format_config={},
            start_time=now - timezone.timedelta(days=1),
            end_time=now + timezone.timedelta(days=1),
            scoreboard_visibility=Contest.SCOREBOARD_VISIBLE,
        )
        cls.hidden_problem = create_problem(code='ultimate_hidden_problem', points=100)
        cls.hidden_contest_problem = create_contest_problem(
            contest=cls.hidden_contest,
            problem=cls.hidden_problem,
            points=100,
            hidden_subtasks='2',
        )
        cls.hidden_participation = create_contest_participation(contest=cls.hidden_contest, user='normal')
        cls.hidden_submission = Submission.objects.create(
            user=cls.users['normal'].profile,
            problem=cls.hidden_problem,
            language=Language.get_python3(),
            result='PAC',
            status='D',
            points=70,
            case_points=7,
            case_total=10,
            date=now,
        )
        cls._create_submission_cases(cls.hidden_submission, [
            (1, 5, 5, 'AC'),
            (2, 2, 5, 'PAC'),
        ])
        ContestSubmission.objects.create(
            submission=cls.hidden_submission,
            problem=cls.hidden_contest_problem,
            participation=cls.hidden_participation,
            points=70,
        )

    def test_latest_submission_is_used_even_if_score_is_lower(self):
        self.participation.recompute_results()

        self.assertFalse(self.contest.format.has_hidden_subtasks)
        self.assertEqual(self.participation.score, 25)
        self.assertEqual(self.participation.format_data[str(self.contest_problem.id)]['points'], 25)

    def test_hidden_subtasks_are_excluded_from_public_score(self):
        self.hidden_participation.recompute_results()

        self.assertTrue(self.hidden_contest.format.has_hidden_subtasks)
        self.assertEqual(self.hidden_participation.score, 50)
        self.assertEqual(self.hidden_participation.score_final, 70)
        self.assertEqual(self.hidden_participation.format_data[str(self.hidden_contest_problem.id)]['points'], 50)
        self.assertEqual(
            self.hidden_participation.format_data_final[str(self.hidden_contest_problem.id)]['points'], 70,
        )


class ContestTagTestCase(TestCase):
    @classmethod
    def setUpTestData(self):
        self.basic_tag = ContestTag.objects.create(
            name='basic',
            color='#fff',
        )
        self.dark_tag = ContestTag.objects.create(
            name='dark',
            color='#010001',
        )

    def test_basic_tag(self):
        self.assertEqual(str(self.basic_tag), self.basic_tag.name)
        self.assertEqual(self.basic_tag.text_color, '#000')

    def test_dark_tag(self):
        self.assertEqual(self.dark_tag.text_color, '#fff')


class MinValueOrNoneValidatorTestCase(SimpleTestCase):
    def test_both_integers(self):
        self.assertIsNone(MinValueOrNoneValidator(-1)(100))
        self.assertIsNone(MinValueOrNoneValidator(0)(0))
        self.assertIsNone(MinValueOrNoneValidator(100)(100))

    def test_integer_bound_none_value(self):
        self.assertIsNone(MinValueOrNoneValidator(-100)(None))
        self.assertIsNone(MinValueOrNoneValidator(0)(None))
        self.assertIsNone(MinValueOrNoneValidator(100)(None))

    def test_none_bound_integer_value(self):
        self.assertIsNone(MinValueOrNoneValidator(None)(-100))
        self.assertIsNone(MinValueOrNoneValidator(None)(0))
        self.assertIsNone(MinValueOrNoneValidator(None)(100))

    def test_both_none(self):
        self.assertIsNone(MinValueOrNoneValidator(None)(None))

    def test_fail(self):
        with self.assertRaises(ValidationError):
            MinValueOrNoneValidator(0)(-1)

        with self.assertRaises(ValidationError):
            MinValueOrNoneValidator(100)(0)
