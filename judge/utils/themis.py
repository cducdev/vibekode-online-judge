import os

THEMIS_SELECTION_BEST = 'best'
THEMIS_SELECTION_LAST = 'last'
THEMIS_SELECTIONS = (THEMIS_SELECTION_BEST, THEMIS_SELECTION_LAST)

WINDOWS_RESERVED_NAMES = {
    'CON', 'PRN', 'AUX', 'NUL',
    *(f'COM{index}' for index in range(1, 10)),
    *(f'LPT{index}' for index in range(1, 10)),
}
WINDOWS_INVALID_CHARACTERS = '<>:"/\\|?*'


def validate_themis_selection(selection):
    if selection not in THEMIS_SELECTIONS:
        raise ValueError('Invalid Themis submission selection: %r' % selection)
    return selection


def get_themis_archive_path(cache_dir, contest_id, selection):
    validate_themis_selection(selection)
    return os.path.join(cache_dir, '%s-%s.zip' % (contest_id, selection))


def safe_themis_path_component(value, component_name):
    if value is None:
        raise ValueError('%s cannot be empty' % component_name)

    value = str(value)
    reserved_name = value.split('.', 1)[0].upper()
    if (
        not value or
        value in ('.', '..') or
        value.endswith(('.', ' ')) or
        reserved_name in WINDOWS_RESERVED_NAMES or
        any(character in WINDOWS_INVALID_CHARACTERS or ord(character) < 32 for character in value)
    ):
        raise ValueError('Invalid %s for Themis export: %r' % (component_name, value))
    return value
