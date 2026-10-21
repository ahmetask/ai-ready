import os
import tempfile
import unittest

from tasklite.store import Store


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "tasks.json")

    def tearDown(self):
        self.dir.cleanup()

    def test_add_complete_and_reload(self):
        store = Store(self.path)
        store.add("write docs")
        store.add("ship it")
        store.complete(1)
        reloaded = Store(self.path)
        self.assertEqual([(t.id, t.done) for t in reloaded.all()], [(1, True), (2, False)])
