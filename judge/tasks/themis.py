import os
import posixpath
import shutil
import tempfile
import zipfile
from urllib.parse import urlsplit

from celery import shared_task
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import default_storage
from django.utils.translation import gettext as _

from judge.models import Contest, ContestParticipation, ContestSubmission
from judge.utils.celery import Progress
from judge.utils.themis import THEMIS_SELECTION_BEST, get_themis_archive_path, safe_themis_path_component, \
    validate_themis_selection

__all__ = ('prepare_contest_themis',)


def _get_export_data(contest, selection):
    validate_themis_selection(selection)

    participants = list(
        ContestParticipation.objects.filter(contest=contest, virtual=ContestParticipation.LIVE)
        .order_by('user__user__username')
        .values_list('user__user__id', 'user__user__username'),
    )

    ordering = ['submission__user__user__username', 'problem__problem__code']
    if selection == THEMIS_SELECTION_BEST:
        ordering.extend(('-points', '-submission__id'))
    else:
        ordering.append('-submission__id')

    queryset = ContestSubmission.objects.filter(
        participation__contest=contest,
        participation__virtual=ContestParticipation.LIVE,
    ).order_by(*ordering).values_list(
        'submission__user__user__id',
        'submission__user__user__username',
        'problem__problem__code',
        'submission__source__source',
        'submission__language__extension',
        'submission__language__file_only',
    )

    submissions = []
    selected = set()
    for submission in queryset.iterator():
        key = submission[0], submission[2]
        if key not in selected:
            selected.add(key)
            submissions.append(submission)

    return participants, submissions


def _archive_path(contest_id, selection):
    cache_dir = settings.DMOJ_CONTEST_THEMIS_CACHE
    if not cache_dir:
        raise ImproperlyConfigured('DMOJ_CONTEST_THEMIS_CACHE must be configured')
    return get_themis_archive_path(cache_dir, contest_id, selection)


def _write_archive(contest_id, selection, participants, submissions, progress):
    archive_path = _archive_path(contest_id, selection)
    cache_dir = os.path.dirname(archive_path)
    os.makedirs(cache_dir, exist_ok=True)
    descriptor, temporary_path = tempfile.mkstemp(
        prefix='.%s-%s-' % (contest_id, selection),
        suffix='.zip',
        dir=cache_dir,
    )
    os.close(descriptor)

    try:
        with zipfile.ZipFile(temporary_path, mode='w', compression=zipfile.ZIP_DEFLATED) as archive:
            exported_usernames = set()
            for _user_id, username in participants:
                username = safe_themis_path_component(username, 'username')
                normalized_username = username.casefold()
                if normalized_username in exported_usernames:
                    raise ValueError('Duplicate username for Themis export: %r' % username)
                exported_usernames.add(normalized_username)
                archive.writestr('%s/' % username, b'')
                progress.did(1)

            for user_id, username, problem, source, extension, file_only in submissions:
                username = safe_themis_path_component(username, 'username')
                problem = safe_themis_path_component(problem, 'problem code')
                extension = safe_themis_path_component(
                    extension.lstrip('.') if extension else extension,
                    'language extension',
                )
                export_path = posixpath.join(username, '%s.%s' % (problem, extension))

                if file_only:
                    if not source:
                        raise ValueError('File-only submission source cannot be empty')
                    filename = posixpath.basename(urlsplit(source).path)
                    storage_path = os.path.join(
                        settings.SUBMISSION_FILE_UPLOAD_MEDIA_DIR,
                        problem,
                        str(user_id),
                        filename,
                    )
                    with default_storage.open(storage_path, 'rb') as source_file, \
                            archive.open(export_path, 'w') as export_file:
                        shutil.copyfileobj(source_file, export_file)
                else:
                    if source is None:
                        raise ValueError('Submission source cannot be empty')
                    archive.writestr(export_path, source)

                progress.did(1)

        os.chmod(temporary_path, 0o644)
        os.replace(temporary_path, archive_path)
    finally:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass


@shared_task(bind=True)
def prepare_contest_themis(self, contest_id, selection):
    with Progress(self, 1, stage=_('Selecting submissions for Themis')) as progress:
        progress.done = 0
        contest = Contest.objects.get(id=contest_id)
        participants, submissions = _get_export_data(contest, selection)
        progress.did(1)

    with Progress(
        self,
        len(participants) + len(submissions),
        stage=_('Preparing Themis submission package'),
    ) as progress:
        _write_archive(contest_id, selection, participants, submissions, progress)

    return len(submissions)
