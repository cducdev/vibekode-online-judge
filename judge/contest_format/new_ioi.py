from collections import defaultdict
from datetime import timedelta
from itertools import groupby
from operator import attrgetter

from django.db.models import Prefetch
from django.template.defaultfilters import floatformat
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _, gettext_lazy

from judge.contest_format.ioi import IOIContestFormat
from judge.contest_format.registry import register_contest_format
from judge.models.submission import SubmissionTestCase
from judge.utils.subtasks import calculate_batch_score, get_batch_scorings, get_hidden_subtasks_by_problem
from judge.utils.timedelta import nice_repr


@register_contest_format('new_ioi')
class NewIOIContestFormat(IOIContestFormat):
    name = gettext_lazy('New IOI')
    config_defaults = {'cumtime': False}
    has_hidden_subtasks = True

    def get_hidden_subtasks(self):
        return get_hidden_subtasks_by_problem(self.contest)

    def _get_submission_batches(self, contest_submission, batch_scorings):
        submission = contest_submission.submission
        for batch, cases in groupby(submission.test_cases.all(), key=attrgetter('batch')):
            cases = list(cases)
            batch_scoring = batch_scorings.get(batch, 'sum') if batch else 'sum'
            points, total = calculate_batch_score(cases, batch_scoring)
            yield batch, points, total

    def _get_best_subtasks(self, participation):
        batch_scorings_cache = {}
        best_subtasks = {}
        submissions = (
            participation.submissions
            .filter(submission__status='D')
            .select_related('problem__problem', 'submission')
            .prefetch_related(Prefetch(
                'submission__test_cases',
                queryset=SubmissionTestCase.objects.order_by('case'),
            ))
        )

        for contest_submission in submissions:
            contest_problem = contest_submission.problem
            problem = contest_problem.problem
            problem_id = problem.id
            if problem_id not in batch_scorings_cache:
                batch_scorings_cache[problem_id] = get_batch_scorings(problem)
            batch_scorings = batch_scorings_cache[problem_id]

            for subtask, points, total in self._get_submission_batches(contest_submission, batch_scorings):
                key = (contest_problem.id, subtask)
                current = best_subtasks.get(key)
                if current is not None:
                    if points < current['points']:
                        continue
                    if points == current['points'] and contest_submission.submission.date >= current['time']:
                        continue

                best_subtasks[key] = {
                    'problem_id': contest_problem.id,
                    'problem_points': contest_problem.points,
                    'subtask': subtask,
                    'points': points,
                    'total': total,
                    'time': contest_submission.submission.date,
                }

        return best_subtasks.values()

    def _build_format_data(self, participation, include_hidden):
        hidden_subtasks = self.get_hidden_subtasks()
        format_data = defaultdict(lambda: {
            'points': 0,
            'total_points': 0,
            'time': 0,
            'problem_points': 0,
        })

        for result in self._get_best_subtasks(participation):
            problem_id = str(result['problem_id'])
            subtask = result['subtask']
            is_hidden = subtask in hidden_subtasks.get(problem_id, set())
            data = format_data[problem_id]
            data['problem_points'] = result['problem_points']
            data['total_points'] += result['total']

            if include_hidden or not is_hidden:
                data['points'] += result['points']
                if self.config['cumtime']:
                    dt = (result['time'] - participation.start).total_seconds()
                    data['time'] = max(dt, data['time'])

        for data in format_data.values():
            if data['total_points']:
                data['points'] = data['points'] / data['total_points'] * data['problem_points']

        return dict(format_data)

    def _compute_score(self, format_data):
        return sum(data['points'] for data in format_data.values())

    def _compute_cumtime(self, format_data):
        if not self.config['cumtime']:
            return 0
        return max(sum(data['time'] for data in format_data.values() if data['points']), 0)

    def update_participation(self, participation):
        format_data = self._build_format_data(participation, include_hidden=False)
        format_data_final = self._build_format_data(participation, include_hidden=True)

        participation.score = round(self._compute_score(format_data), self.contest.points_precision)
        participation.cumtime = self._compute_cumtime(format_data)
        participation.tiebreaker = 0
        participation.format_data = format_data

        participation.score_final = round(self._compute_score(format_data_final), self.contest.points_precision)
        participation.cumtime_final = self._compute_cumtime(format_data_final)
        participation.format_data_final = format_data_final
        participation.save()

    def _show_final(self, frozen=False):
        return self.contest.ended and not frozen

    def display_user_problem(self, participation, contest_problem, first_solves, frozen=False):
        if self._show_final(frozen):
            format_data = (participation.format_data_final or {}).get(str(contest_problem.id))
        else:
            format_data = (participation.format_data or {}).get(str(contest_problem.id))

        if format_data:
            show_time = self.config['cumtime']
            return format_html(
                '<td class="{state}"><a href="{url}">{points}<div class="solving-time">{time}</div></a></td>',
                state=(('pretest-' if self.contest.run_pretests_only and contest_problem.is_pretested else '') +
                       ('first-solve ' if first_solves.get(str(contest_problem.id), None) == participation.id else '') +
                       self.best_solution_state(format_data['points'], contest_problem.points)),
                url=reverse('contest_user_submissions',
                            args=[self.contest.key, participation.user.user.username, contest_problem.problem.code]),
                points=floatformat(format_data['points'], -self.contest.points_precision),
                time=nice_repr(timedelta(seconds=format_data['time']), 'noday') if show_time else '',
            )
        else:
            return mark_safe('<td></td>')

    def display_participation_result(self, participation, frozen=False):
        show_time = self.config['cumtime']
        if self._show_final(frozen):
            points = participation.score_final
            cumtime = participation.cumtime_final
        else:
            points = participation.score if not frozen else participation.frozen_score
            cumtime = participation.cumtime if not frozen else participation.frozen_cumtime

        return format_html(
            '<td class="user-points"><a href="{url}">{points}<div class="solving-time">{cumtime}</div></a></td>',
            url=reverse('contest_all_user_submissions',
                        args=[self.contest.key, participation.user.user.username]),
            points=floatformat(points, -self.contest.points_precision),
            cumtime=nice_repr(timedelta(seconds=cumtime), 'noday') if show_time else '',
        )

    def get_short_form_display(self):
        yield _('New IOI mode scores each batch independently and can hide selected subtasks while the contest is '
                'running.')
        yield _('The maximum score for each problem batch will be used.')
        yield _('Hidden subtasks are excluded from public scores until the contest ends.')

        if self.config['cumtime']:
            yield _('Ties will be broken by the sum of the last score altering submission time on problems with a '
                    'non-zero score.')
        else:
            yield _('Ties by score will **not** be broken.')
