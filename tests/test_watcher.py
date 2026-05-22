
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import time
from glia.watcher import GLIAUpdateHandler

class TestWatcher(unittest.TestCase):
    def setUp(self):
        self.brain = MagicMock()
        self.workspace = Path("/tmp/glia_test")
        self.handler = GLIAUpdateHandler(self.brain, self.workspace, debounce_seconds=0.1)

    def test_process_file_filtering(self):
        # Test that hidden files are ignored
        event = MagicMock()
        event.is_directory = False
        event.src_path = "/tmp/glia_test/.hidden_file"
        self.handler.process_file(event)
        self.brain.learn.assert_not_called()

        # Test that pycache is ignored
        event.src_path = "/tmp/glia_test/__pycache__/some.pyc"
        self.handler.process_file(event)
        self.brain.learn.assert_not_called()

        # Test that non-source files are ignored
        event.src_path = "/tmp/glia_test/image.png"
        self.handler.process_file(event)
        self.brain.learn.assert_not_called()

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_process_file_learning(self, mock_read, mock_exists):
        mock_exists.return_value = True
        mock_read.return_value = "print('hello')"
        
        event = MagicMock()
        event.is_directory = False
        event.src_path = str(self.workspace / "main.py")
        
        self.handler.process_file(event)
        
        self.brain.learn.assert_called_once_with("print('hello')", source="main.py")

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_debounce(self, mock_read, mock_exists):
        mock_exists.return_value = True
        mock_read.return_value = "content"
        
        event = MagicMock()
        event.is_directory = False
        event.src_path = str(self.workspace / "main.py")
        
        # First call
        self.handler.process_file(event)
        self.assertEqual(self.brain.learn.call_count, 1)
        
        # Immediate second call (debounced)
        self.handler.process_file(event)
        self.assertEqual(self.brain.learn.call_count, 1)
        
        # Wait for debounce
        time.sleep(0.15)
        self.handler.process_file(event)
        self.assertEqual(self.brain.learn.call_count, 2)

if __name__ == "__main__":
    unittest.main()
