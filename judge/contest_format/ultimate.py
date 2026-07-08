from django.db.models import OuterRef, Prefetch, Subquery
from django.utils.functional import cached_property
from django.utils.translation import gettext as _, gettext_lazy

from judge.contest_format.new_ioi import NewIOIContestFormat
from judge.contest_format.registry import register_contest_format
from judge.models.submission import SubmissionTestCase
from judge.utils.subtasks import get_batch_scorings


@register_contest_format('ultimate')
class UltimateContestFormat(NewIOIContestFormat):
    name = gettext_lazy('Ultimate')
    config_defaults = {'cumtime': False}

    @cached_property
    def has_hidden_subtasks(self):
        return any(self.get_hidden_subtasks().values())

    def _get_best_subtasks(self, participation):
        batch_scorings_cache = {}
        submissions = participation.submissions
        latest_submission = submissions.filter(problem_id=OuterRef('problem_id')) \
            .order_by('-submission__date', '-id') \
            .values('id')[:1]
        submissions = (
            submissions
            .filter(id=Subquery(latest_submission))
            .select_related('problem__problem', 'submission')
            .prefetch_related(Prefetch(
                'submission__test_cases',
                queryset=SubmissionTestCase.objects.order_by('case'),
            ))
        )

        for contest_submission in submissions:
            contest_problem = contest_submission.problem
            submission = contest_submission.submission
            cases = list(submission.test_cases.all())

            if not cases:
                yield {
                    'problem_id': contest_problem.id,
                    'problem_points': contest_problem.points,
                    'subtask': None,
                    'points': contest_submission.points,
                    'total': contest_problem.points,
                    'time': submission.date,
                }
                continue

            problem = contest_problem.problem
            problem_id = problem.id
            if problem_id not in batch_scorings_cache:
                batch_scorings_cache[problem_id] = get_batch_scorings(problem)
            batch_scorings = batch_scorings_cache[problem_id]

            for subtask, points, total in self._get_submission_batches(contest_submission, batch_scorings):
                yield {
                    'problem_id': contest_problem.id,
                    'problem_points': contest_problem.points,
                    'subtask': subtask,
                    'points': points,
                    'total': total,
                    'time': submission.date,
                }

    def get_short_form_display(self):
        yield _('Ultimate mode uses only the latest submission on each problem, even if it scores lower than earlier '
                'submissions.')
        if self.has_hidden_subtasks:
            yield _('Hidden subtasks are excluded from public scores until the contest ends.')

        if self.config['cumtime']:
            yield _('Ties will be broken by the sum of the last submission time on problems with a non-zero score.')
        else:
            yield _('Ties by score will **not** be broken.')
