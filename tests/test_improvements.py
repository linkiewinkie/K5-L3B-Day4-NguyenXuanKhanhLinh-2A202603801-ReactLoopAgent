"""Tests offline cho các cải tiến Bài 4 và bonus trong agent.py (không gọi LLM API)."""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'evals'))
sys.path.insert(0, str(ROOT / 'tests'))
from agent import run_agent, NOTE_RETRY, NOTE_UNAVAILABLE, MAX_RETRY_WAIT_SECONDS
from scenarios import ScenarioTools
from status_tools import StatusTools
from bonus.tools import BonusTools
from test_lab import FakeProvider, tool_call, final

LINKED_FROM = {'provider': 'github', 'incident_id': 'h02n9572mx9y'}   # update trỏ sang xr3myzj7ms51
LINKED_TO = {'provider': 'github', 'incident_id': 'xr3myzj7ms51'}


def details_url(args):
    return StatusTools().get_incident_details(**args)['url']


def events(result):
    return [e['event'] for e in result['trace']]


def tool_names(result):
    return [e['name'] for e in result['trace'] if e['event'] == 'tool']


class FakeTools:
    """Tool registry giả lập trả kết quả cố định theo thứ tự."""
    def __init__(self, results):
        self.results = iter(results)
        self.calls = 0
    def execute(self, name, args):
        self.calls += 1
        return next(self.results)


class LinkedIncidentTests(unittest.TestCase):
    def test_note_and_reminder_lead_to_reading_linked_incident(self):
        answer = 'Xong ' + details_url(LINKED_FROM)
        fake = FakeProvider([tool_call('1', 'get_incident_details', json.dumps(LINKED_FROM)), final(answer),
                             tool_call('2', 'get_incident_details', json.dumps(LINKED_TO)), final(answer)])
        result = run_agent('Điều tra', fake, ScenarioTools(), max_steps=6)
        self.assertEqual(result['status'], 'completed')
        observation = json.loads(fake.histories[1][-1]['content'])
        self.assertIn('github/xr3myzj7ms51', observation['agent_note_linked'])
        self.assertIn('validation_unfollowed_link', events(result))
        self.assertIn('xr3myzj7ms51', fake.histories[2][-1]['content'])   # lời nhắc gửi cho model
        self.assertEqual(tool_names(result), ['get_incident_details', 'get_incident_details'])

    def test_reminder_is_sent_only_once(self):
        answer = 'Bỏ qua liên kết ' + details_url(LINKED_FROM)
        fake = FakeProvider([tool_call('1', 'get_incident_details', json.dumps(LINKED_FROM)), final(answer), final(answer)])
        result = run_agent('x', fake, ScenarioTools(), max_steps=6)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(events(result).count('validation_unfollowed_link'), 1)

    def test_no_reminder_when_budget_is_exhausted(self):
        answer = 'Xong ' + details_url(LINKED_FROM)
        fake = FakeProvider([tool_call('1', 'get_incident_details', json.dumps(LINKED_FROM)), final(answer)])
        result = run_agent('x', fake, ScenarioTools(), max_steps=2)
        self.assertEqual(result['status'], 'completed')
        self.assertNotIn('validation_unfollowed_link', events(result))

    def test_no_reminder_when_linked_incident_already_read(self):
        answer = 'Xong ' + details_url(LINKED_FROM)
        fake = FakeProvider([tool_call('1', 'get_incident_details', json.dumps(LINKED_TO)),
                             tool_call('2', 'get_incident_details', json.dumps(LINKED_FROM)), final(answer)])
        result = run_agent('x', fake, ScenarioTools(), max_steps=6)
        self.assertEqual(result['status'], 'completed')
        self.assertNotIn('validation_unfollowed_link', events(result))
        self.assertNotIn('agent_note_linked', json.loads(fake.histories[2][-1]['content']))


class ToolErrorNoteTests(unittest.TestCase):
    def test_timeout_observation_warns_not_to_infer_status(self):
        fake = FakeProvider([tool_call('1', 'get_status', '{"provider":"cloudflare"}'), final('Chưa kiểm tra được Cloudflare')])
        result = run_agent('x', fake, ScenarioTools('cloudflare_timeout'))
        self.assertEqual(result['status'], 'completed')
        observation = json.loads(fake.histories[1][-1]['content'])
        self.assertEqual(observation['error'], 'TimeoutError')
        self.assertEqual(observation['agent_note'], NOTE_UNAVAILABLE)

    def test_successful_tool_has_no_error_note(self):
        fake = FakeProvider([tool_call('1', 'get_status', '{"provider":"github"}'), final()])
        run_agent('x', fake, ScenarioTools('cloudflare_timeout'))
        self.assertNotIn('agent_note', json.loads(fake.histories[1][-1]['content']))


class RetryTests(unittest.TestCase):
    def test_pending_429_triggers_one_retry_reminder(self):
        fake = FakeProvider([tool_call('a', 'get_vercel_status', '{}'), final('Vercel lỗi'),
                             tool_call('b', 'get_vercel_status', '{}'), final('Vercel ổn')])
        result = run_agent('x', fake, BonusTools(scenario='rate_limit_once'), max_steps=6)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(json.loads(fake.histories[1][-1]['content'])['agent_note'], NOTE_RETRY)
        self.assertIn('validation_pending_retry', events(result))
        self.assertEqual(tool_names(result).count('get_vercel_status'), 2)
        self.assertEqual(json.loads(fake.histories[3][-1]['content'])['provider'], 'vercel')

    def test_persistent_429_is_capped_and_blocked(self):
        fake = FakeProvider([tool_call(str(i), 'get_vercel_status', '{}') for i in range(3)] + [final('Vercel chưa kiểm tra được')])
        tools = BonusTools(scenario='rate_limit_always')
        result = run_agent('x', fake, tools, max_steps=6)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(tool_names(result).count('get_vercel_status'), 2)      # chỉ 2 lần gọi thật
        self.assertEqual(tools.calls[('get_vercel_status', 'vercel')], 2)
        self.assertEqual(json.loads(fake.histories[2][-1]['content'])['agent_note'], NOTE_UNAVAILABLE)
        blocked = json.loads(fake.histories[3][-1]['content'])
        self.assertEqual(blocked['error'], 'RETRY_BUDGET_EXHAUSTED')
        self.assertIn('tool_blocked', events(result))
        self.assertNotIn('validation_pending_retry', events(result))           # đã hết budget, không nhắc

    def test_short_retry_after_waits_within_budget(self):
        tools = FakeTools([{'ok': False, 'error': 'RATE_LIMITED', 'retry_after': '2'}, {'ok': True, 'provider': 'npm'}])
        fake = FakeProvider([tool_call('a', 'get_npm_status', '{}'), tool_call('b', 'get_npm_status', '{}'), final()])
        with patch('agent.time.sleep') as sleep:
            result = run_agent('x', fake, tools, max_steps=5)
        sleep.assert_called_once_with(2.0)
        self.assertIn('retry_wait', events(result))

    def test_long_retry_after_stops_retrying_without_sleeping(self):
        wait = str(MAX_RETRY_WAIT_SECONDS + 55)
        tools = FakeTools([{'ok': False, 'error': 'RATE_LIMITED', 'retry_after': wait}])
        fake = FakeProvider([tool_call('a', 'get_npm_status', '{}'), tool_call('b', 'get_npm_status', '{}'), final('npm bị rate limit')])
        with patch('agent.time.sleep') as sleep:
            result = run_agent('x', fake, tools, max_steps=5)
        sleep.assert_not_called()
        self.assertEqual(tools.calls, 1)
        self.assertEqual(json.loads(fake.histories[2][-1]['content'])['error'], 'RETRY_BUDGET_EXHAUSTED')
        self.assertEqual(result['status'], 'completed')


class ContextTests(unittest.TestCase):
    def test_noisy_lists_are_compacted_in_context_and_trace(self):
        fake = FakeProvider([tool_call('1', 'get_status', '{"provider":"github","component":"Actions"}'), final()])
        result = run_agent('x', fake, ScenarioTools('noisy_status'))
        observation = json.loads(fake.histories[1][-1]['content'])
        self.assertEqual(len(observation['distractors']), 3)
        self.assertIn('37/40', observation['distractors_omitted'])
        self.assertTrue(observation['incidents'])                              # list ngắn giữ nguyên
        traced = next(e for e in result['trace'] if e['event'] == 'tool')['result']
        self.assertEqual(len(traced['distractors']), 3)


class BaselineAndStopTests(unittest.TestCase):
    def test_baseline_mode_disables_improvements(self):
        fake = FakeProvider([tool_call('1', 'get_incident_details', json.dumps(LINKED_FROM)), final('Không có URL')])
        with patch.dict(os.environ, {'AGENT_IMPROVEMENTS': '0'}):
            result = run_agent('x', fake, ScenarioTools(), max_steps=6)
        self.assertEqual(result['status'], 'completed')
        self.assertFalse(any(e.startswith('validation') for e in events(result)))
        self.assertNotIn('agent_note_linked', json.loads(fake.histories[1][-1]['content']))
        self.assertNotIn('Quy tắc bắt buộc', fake.histories[0][0]['content'])

    def test_unexpected_finish_reason_is_error(self):
        odd = final('?')
        odd['finish'] = 'content_filter'
        result = run_agent('x', FakeProvider([odd]), StatusTools())
        self.assertEqual(result['status'], 'error')
        self.assertIn('unexpected_finish', events(result))

    def test_provider_exception_is_error_without_crash(self):
        class Broken:
            def complete(self, messages, schemas):
                raise RuntimeError('Provider trả HTTP 500')
        result = run_agent('x', Broken(), StatusTools())
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['trace'][-1]['event'], 'provider_error')

    def test_non_object_arguments_are_invalid(self):
        fake = FakeProvider([tool_call('1', 'get_status', '["github"]'), final()])
        run_agent('x', fake, StatusTools())
        self.assertEqual(json.loads(fake.histories[1][-1]['content'])['error'], 'INVALID_ARGUMENTS')


if __name__ == '__main__':
    unittest.main()
