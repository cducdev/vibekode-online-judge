from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from judge.utils.subtasks import clean_subtask_numbers, parse_subtask_numbers


class SubtaskUtilsTestCase(SimpleTestCase):
    def test_parse_subtask_numbers_ignores_invalid_values(self):
        self.assertEqual(parse_subtask_numbers('1, 2, bad, 0, -3'), {1, 2})

    def test_clean_subtask_numbers_normalizes_values(self):
        self.assertEqual(clean_subtask_numbers('1, 2, 3'), '1,2,3')

    def test_clean_subtask_numbers_rejects_invalid_values(self):
        with self.assertRaises(ValidationError):
            clean_subtask_numbers('1, bad')

        with self.assertRaises(ValidationError):
            clean_subtask_numbers('0')
