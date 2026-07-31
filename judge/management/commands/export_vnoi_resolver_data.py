import json

from django.core.management.base import BaseCommand, CommandError
from django.utils import translation

from judge.models import Contest, ContestParticipation, ContestSubmission


class Command(BaseCommand):
    help = 'Export contest data for VNOI Resolver'

    def add_arguments(self, parser):
        parser.add_argument('key', help='contest key')
        parser.add_argument('output', help='output JSON file')

    def handle(self, *args, **options):
        output_file = options['output']
        if not output_file.endswith('.json'):
            raise CommandError('output file must end with .json')

        contest = Contest.objects.filter(key=options['key']).first()
        if contest is None:
            raise CommandError('contest not found')

        with translation.override('en'):
            data = self.build_data(contest)
            with open(output_file, 'w', encoding='utf-8') as output:
                json.dump(data, output, ensure_ascii=False, indent=2)
                output.write('\n')

    @staticmethod
    def build_data(contest):
        participations = contest.users.filter(virtual=ContestParticipation.LIVE) \
            .select_related('user__user').order_by('id')
        users = []
        for participation in participations:
            profile = participation.user
            user = profile.user
            users.append({
                'userId': user.id,
                'username': profile.display_name,
                'fullName': user.get_full_name() or profile.display_name,
            })

        contest_problems = contest.contest_problems.select_related('problem').order_by('order')
        problems = [{
            'problemId': contest_problem.problem_id,
            'name': contest_problem.problem.name,
            'points': contest_problem.points,
        } for contest_problem in contest_problems]

        contest_submissions = ContestSubmission.objects.filter(
            participation__contest=contest,
            participation__virtual=ContestParticipation.LIVE,
        ).exclude(
            submission__result__isnull=True,
        ).exclude(
            submission__result__in=['IE', 'CE'],
        ).select_related(
            'problem', 'submission', 'submission__user__user',
        ).order_by('submission__date', 'submission_id')

        submissions = [{
            'submissionId': contest_submission.submission_id,
            'problemId': contest_submission.problem.problem_id,
            'userId': contest_submission.submission.user.user.id,
            'time': str((contest_submission.submission.date - contest.start_time).total_seconds()),
            'points': contest_submission.points,
        } for contest_submission in contest_submissions]

        return {
            'users': users,
            'problems': problems,
            'submissions': submissions,
        }
