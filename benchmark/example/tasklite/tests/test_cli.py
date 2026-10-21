import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from tasklite.cli import main
from tasklite.store import Store


class CliTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = Store(os.path.join(self.dir.name, "tasks.json"))

    def tearDown(self):
        self.dir.cleanup()

    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(list(argv), store=self.store)
        return code, out.getvalue()

    def test_add_list_done(self):
        self.run_cli("add", "buy milk")
        self.run_cli("done", "1")
        self.assertEqual(self.run_cli("list")[1], "[x] 1 buy milk\n")
