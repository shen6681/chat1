"""Launch routing without opening any window or browser."""
import sys
import unittest
from unittest.mock import patch
import main


class EntrypointTests(unittest.TestCase):
    def test_default_launch_opens_the_local_web_version(self):
        with patch.object(sys, 'argv', ['main.py']), \
             patch('chat_assistant.web_server.launch_web') as launch, \
             patch('chat_assistant.desktop_app.start_desktop') as desktop:
            main.main()
        launch.assert_called_once_with(open_browser=True, ready_file=None)
        desktop.assert_not_called()

    def test_server_only_start_keeps_browser_closed_and_writes_ready_file(self):
        from pathlib import Path
        with patch.object(sys, 'argv', ['main.py', '--no-browser', '--server-info', 'ready.json']), \
             patch('chat_assistant.web_server.launch_web') as launch:
            main.main()
        launch.assert_called_once_with(open_browser=False, ready_file=Path('ready.json'))
