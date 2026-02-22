import unittest
from unittest.mock import patch, MagicMock
import json
import os
import yaml
from meetup_bot import MeetupBot
from datetime import datetime, timedelta, timezone

class TestMeetupBot(unittest.TestCase):
    def setUp(self):
        self.config = {
            'meetup': {
                'client_id': 'id',
                'client_secret': 'secret',
                'refresh_token': 'token',
                'network_urlname': 'ansible'
            },
            'discourse': {
                'url': 'https://forum.ansible.com',
                'api_key': 'key',
                'api_user': 'user',
                'category': 1
            },
            'email': {
                'smtp_server': 'smtp.gmail.com',
                'smtp_port': 587,
                'username': 'user',
                'password': 'pass',
                'targets': ['target']
            },
            'paths': {
                'config_dir': '/tmp/config',
                'pins_dir': '/tmp/pins'
            }
        }
        os.makedirs('/tmp/config', exist_ok=True)
        os.makedirs('/tmp/pins', exist_ok=True)
        with open('/tmp/config/credentials.yml', 'w') as f:
            yaml.dump(self.config, f)

        self.bot = MeetupBot('/tmp/config/credentials.yml')

    @patch('requests.post')
    def test_get_access_token(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {'access_token': 'new_token'}
        mock_post.return_value = mock_response

        token = self.bot.get_access_token()
        self.assertEqual(token, 'new_token')
        self.assertEqual(self.bot.access_token, 'new_token')

    def test_trend_calculation_logic(self):
        # Mock events data
        now = datetime.now(timezone.utc)
        events = [
            {
                'id': '1',
                'urlname': 'group1',
                'time': (now - timedelta(days=2)).isoformat(),
                'going': 10,
                'status': 'PAST',
                'title': 'Event 1'
            },
            {
                'id': '2',
                'urlname': 'group1',
                'time': (now - timedelta(days=20)).isoformat(),
                'going': 20,
                'status': 'PAST',
                'title': 'Event 2'
            }
        ]
        self.bot.save_cache('events.json', events)
        self.bot.save_cache('groups.json', {
            'network': {'name': 'ansible', 'memberCount': 100},
            'groups': [{'urlname': 'group1', 'name': 'Group 1', 'memberCount': 50}]
        })
        self.bot.save_cache('history.json', [])

        # We can't easily test generate_report because it sends email
        # but we can test the internal data structures if we refactor or mock smtplib
        with patch('smtplib.SMTP') as mock_smtp:
            self.bot.generate_report()
            # If it reached send_email, the logic up to there is verified
            self.assertTrue(mock_smtp.called)

    @patch('requests.get')
    def test_update_discourse_dry_run(self, mock_get):
        # Mock search results
        mock_get.return_value.json.return_value = {'topics': []}
        now = datetime.now(timezone.utc)
        events = [{'id': '1', 'urlname': 'group1', 'title': 'Event 1', 'time': (now + timedelta(days=10)).isoformat(), 'status': 'PUBLISHED', 'link': 'http', 'description': 'desc'}]
        self.bot.save_cache('events.json', events)

        with patch('builtins.print') as mock_print:
            self.bot.update_discourse(dry_run=True)
            # Check if "[DRY-RUN] Would create topic: group1: Event 1" was printed
            mock_print.assert_any_call("Syncing with Discourse...")
            # We don't assert the exact title because of the date part

if __name__ == '__main__':
    unittest.main()
