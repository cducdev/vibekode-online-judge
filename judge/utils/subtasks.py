from itertools import groupby
from operator import attrgetter

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def parse_subtask_numbers(value):
    subtasks = set()
    if not value:
        return subtasks

    for item in str(value).split(','):
        item = item.strip()
        if not item:
            continue
        try:
            subtask = int(item)
        except ValueError:
            continue
        if subtask > 0:
            subtasks.add(subtask)
    return subtasks


def clean_subtask_numbers(value):
    subtasks = []
    if not value:
        return ''

    for item in str(value).split(','):
        item = item.strip()
        if not item:
            continue
        try:
            subtask = int(item)
        except ValueError:
            raise ValidationError(_('Enter positive subtask numbers separated by commas.'))
        if subtask <= 0:
            raise ValidationError(_('Enter positive subtask numbers separated by commas.'))
        subtasks.append(str(subtask))
    return ','.join(subtasks)


def get_hidden_subtasks_by_problem(contest):
    return {
        str(problem_id): parse_subtask_numbers(hidden_subtasks)
        for problem_id, hidden_subtasks in contest.contest_problems.values_list('id', 'hidden_subtasks')
    }


def get_batch_scorings(problem):
    return {
        i + 1: scoring
        for i, scoring in enumerate(
            problem.cases.filter(type='S').order_by('order')
            .values_list('batch_scoring', flat=True),
        )
    }


def calculate_batch_score(cases, batch_scoring='min'):
    cases = list(cases)
    if not cases:
        return 0.0, 0.0

    if batch_scoring == 'min':
        return (
            min(case.points or 0.0 for case in cases),
            max(case.total or 0.0 for case in cases),
        )

    return (
        sum(case.points or 0.0 for case in cases),
        sum(case.total or 0.0 for case in cases),
    )


def calculate_visible_problem_score(cases, batch_scorings, hidden_subtasks, problem_points):
    visible_points = 0.0
    total_points = 0.0

    for batch, batch_cases in groupby(cases, key=attrgetter('batch')):
        scoring = batch_scorings.get(batch, 'sum') if batch else 'sum'
        points, total = calculate_batch_score(batch_cases, scoring)
        total_points += total
        if batch not in hidden_subtasks:
            visible_points += points

    if not total_points:
        return 0.0
    return round(visible_points / total_points * problem_points, 3)
