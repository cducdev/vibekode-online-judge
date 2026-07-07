import io
import zipfile
from unittest.mock import patch

from django.test import TestCase

from judge.utils.codeforces_polygon import ImportPolygonError, PolygonImporter


class PolygonImporterSolutionTestCase(TestCase):
    def _package(self, solutions_xml='', solution_files=None):
        solution_files = solution_files or {}
        package = io.BytesIO()

        with zipfile.ZipFile(package, 'w') as z:
            z.writestr(
                'problem.xml',
                f"""<problem>
                    <judging>
                        <testset name="tests">
                            <time-limit>1000</time-limit>
                            <memory-limit>268435456</memory-limit>
                            <input-path-pattern>tests/%02d</input-path-pattern>
                            <answer-path-pattern>tests/%02d.a</answer-path-pattern>
                            <tests>
                                <test points="1"/>
                            </tests>
                        </testset>
                    </judging>
                    <checker type="testlib" name="std::hcmp.cpp"/>
                    {solutions_xml}
                </problem>""",
            )
            z.writestr('tests/01', '1 2\n')
            z.writestr('tests/01.a', '3\n')

            for path, source in solution_files.items():
                z.writestr(path, source)

        package.seek(0)
        return package

    def _importer(self, solutions_xml='', solution_files=None, append_solution=True):
        config = {
            'ignore_zero_point_batches': False,
            'ignore_zero_point_cases': False,
            'append_main_solution_to_tutorial': append_solution,
            'main_tutorial_language': None,
            'main_statement_language': None,
            'polygon_to_site_language_map': {},
        }

        with patch('judge.utils.codeforces_polygon.shutil.which', return_value='/usr/bin/pandoc'), \
                patch('judge.utils.codeforces_polygon.pandoc_get_version', return_value=(3, 0, 0)):
            importer = PolygonImporter(
                package=self._package(solutions_xml, solution_files),
                code='polygon_solution_test',
                interactive=False,
                config=config,
            )
        importer.meta['tutorial'] = ''
        return importer

    def test_missing_solutions_node_raises_import_error(self):
        importer = self._importer()

        with self.assertRaisesMessage(ImportPolygonError, 'main solution not found'):
            importer.parse_solutions()

    def test_missing_main_solution_raises_import_error(self):
        importer = self._importer('<solutions></solutions>')

        with self.assertRaisesMessage(ImportPolygonError, 'main solution not found'):
            importer.parse_solutions()

    def test_missing_main_solution_is_allowed_when_append_is_disabled(self):
        importer = self._importer(append_solution=False)

        importer.parse_solutions()

        self.assertEqual(importer.meta['tutorial'], '')

    def test_missing_main_solution_source_raises_import_error(self):
        importer = self._importer('<solutions><solution tag="main"/></solutions>')

        with self.assertRaisesMessage(ImportPolygonError, 'main solution source not found'):
            importer.parse_solutions()

    def test_missing_main_solution_source_file_raises_import_error(self):
        importer = self._importer("""
            <solutions>
                <solution tag="main">
                    <source path="solutions/main.cpp" type="cpp"/>
                </solution>
            </solutions>
        """)

        with self.assertRaisesMessage(
                ImportPolygonError,
                'main solution source file not found: solutions/main.cpp',
        ):
            importer.parse_solutions()

    def test_main_solution_without_language_type_is_appended(self):
        importer = self._importer(
            """
            <solutions>
                <solution tag="main">
                    <source path="solutions/main.txt"/>
                </solution>
            </solutions>
            """,
            {'solutions/main.txt': 'print("ok")\n'},
        )

        importer.parse_solutions()

        self.assertIn('print("ok")', importer.meta['tutorial'])
        self.assertIn('```', importer.meta['tutorial'])
