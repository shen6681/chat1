import json
import threading
import unittest
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from chat_assistant.analysis import APIError, DIMENSIONS, analyze, call_chat, call_jev, endpoint, jev_analysis, jev_questions, parse_generated, post_json, validate_jev
from chat_assistant.core import Settings, parse_manual


def chat_result():
    return {"summary": "回应电影问题", "self_logic": "接住感受", "other_logic": "提出问题", "dimensions": {k: {"score": 70, "confidence": .8, "evidence": "原文有提问"} for k in DIMENSIONS}, "reply_quality": {"score": 80, "confidence": .8, "evidence": "切题"}, "sentences": [{"index": 2, "emotion": [{"label": "平静", "probability": .8}], "intent": [{"label": "提问", "probability": .9}]}], "replies": [{"style": "自然", "text": "你想看什么类型？", "reason": "先确认偏好"}], "cautions": [], "should_wait": False, "boundary": .1}


def native_result(questions):
    answers = {}
    for key, question in questions.items():
        if question["type"] == "noul":
            answers[key] = {"type": "noul", "noul": .95 if key.endswith("_sufficient") else .05}
        else:
            keys = list(question["criteria"]) if question["type"] == "choice" else [str(i) for i in range(len(question["criteria"]))]
            selected = keys[min(2, len(keys) - 1)]
            probabilities = {k: 1.0 if k == selected else 0.0 for k in keys}
            answers[key] = {"type": question["type"], "confidence": .9, "probabilities": probabilities}
            if question["type"] == "choice":
                answers[key]["choice"] = selected
            else:
                answers[key].update(score=2.0, legend={k: question["criteria"][int(k)] for k in keys})
    return {"model": "jev-test", "answers": answers, "usage": {"input_tokens": 20, "output_tokens": 0}}


class Handler(BaseHTTPRequestHandler):
    requests = []
    fault = None

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.requests.append((self.path, body, self.headers.get("Authorization")))
        if self.fault:
            self.send_response(self.fault)
            self.end_headers()
            self.wfile.write(b'private-provider-echo-secret')
            return
        if self.path.endswith("/systemone"):
            response = native_result(body["questions"])
        else:
            response = {"choices": [{"message": {"content": json.dumps(chat_result(), ensure_ascii=False)}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 12, "completion_tokens": 30}}
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Handler.requests.clear()
        Handler.fault = None
        self.transcript = parse_manual("我：今天想看电影\n对方：想看什么类型？")
        self.settings = Settings(chat_url=self.base, jev_url=self.base, chat_key="fake-test-key", jev_key="fake-jev-key")

    def test_deepseek_chat_contract(self):
        result = call_chat(self.settings, self.transcript)
        path, body, auth = Handler.requests[0]
        self.assertEqual(path, "/chat/completions")
        self.assertEqual(auth, "Bearer fake-test-key")
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertIsInstance(body["messages"][1]["content"], str)
        self.assertEqual(result.replies[0]["text"], "你想看什么类型？")

    def test_both_providers_receive_separate_history_context(self):
        from chat_assistant.core import Message
        self.transcript.history = [Message("对方", "之前说过喜欢悬疑片", timestamp="2026-09-01T00:00:00+00:00")]
        self.transcript.archive_name = "小林"
        self.transcript.archive_count = 1000
        analyze(replace(self.settings, mode="Jev + DeepSeek"), self.transcript)
        native_state = Handler.requests[0][1]["state"]
        chat_state = json.loads(Handler.requests[1][1]["messages"][1]["content"])
        for state in (native_state, chat_state):
            self.assertEqual(state["history_context"][0]["text"], "之前说过喜欢悬疑片")
            self.assertEqual(state["archive"]["total_messages"], 1000)
            self.assertEqual([m["index"] for m in state["messages"]], [1, 2])

    def test_vision_opt_in_only(self):
        from PIL import Image
        image = Image.new("RGB", (200, 100), "white")
        call_chat(self.settings, self.transcript, image)
        self.assertIsInstance(Handler.requests[-1][1]["messages"][1]["content"], str)
        call_chat(replace(self.settings, vision=True), self.transcript, image)
        content = Handler.requests[-1][1]["messages"][1]["content"]
        self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,"))

    def test_jev_uses_native_contract_and_probabilities(self):
        response = call_jev(self.settings, self.transcript)
        path, body, auth = Handler.requests[0]
        self.assertEqual(path, "/v1/systemone")
        self.assertNotIn("messages", body)
        self.assertEqual(auth, "Bearer fake-jev-key")
        result = jev_analysis(response, self.transcript)
        self.assertEqual(result.sentences[0]["emotion"][0]["probability"], 1.0)
        self.assertEqual(result.raw_jev, response)

    def test_combination_uses_both_and_native_ratings(self):
        result = analyze(replace(self.settings, mode="Jev + DeepSeek"), self.transcript)
        self.assertEqual([r[0] for r in Handler.requests], ["/v1/systemone", "/chat/completions"])
        self.assertEqual(result.dimensions["care"]["score"], 50)
        self.assertIn("jev_evaluation", json.loads(Handler.requests[1][1]["messages"][1]["content"]))

    def test_cancel_between_calls_does_not_send_second_provider(self):
        cancel = threading.Event()
        def native(*args):
            cancel.set()
            return native_result(jev_questions(self.transcript))
        with patch("chat_assistant.analysis.call_jev", side_effect=native), patch("chat_assistant.analysis.call_chat") as chat:
            with self.assertRaises(APIError):
                analyze(replace(self.settings, mode="Jev + DeepSeek"), self.transcript, cancel=cancel)
            chat.assert_not_called()

    def test_invalid_native_response_rejected(self):
        questions = jev_questions(self.transcript)
        response = native_result(questions)
        response["answers"]["care"]["probabilities"].pop("0")
        with self.assertRaises(APIError):
            validate_jev(response, questions)

    def test_missing_evidence_does_not_fabricate_signal_score(self):
        questions = jev_questions(self.transcript)
        response = native_result(questions)
        response["answers"]["care_sufficient"]["noul"] = .2
        self.assertIsNone(jev_analysis(response, self.transcript).signal_score)

    def test_explicit_boundary_caps_score_and_avoids_pushy_templates(self):
        response = native_result(jev_questions(self.transcript))
        response["answers"]["boundary"]["noul"] = .99
        result = jev_analysis(response, self.transcript)
        self.assertLessEqual(result.signal_score, 25)
        self.assertTrue(result.should_wait)
        self.assertIn("尊重", result.replies[0]["text"])

    def test_invalid_generated_scores_and_sender_indexes_rejected(self):
        for field, value in (("score", 101), ("confidence", float("nan"))):
            data = chat_result()
            data["dimensions"]["care"][field] = value
            with self.assertRaises(APIError):
                parse_generated(json.dumps(data), self.transcript)
        data = chat_result()
        data["sentences"][0]["index"] = 999
        with self.assertRaises(APIError):
            parse_generated(json.dumps(data), self.transcript)

    def test_http_error_does_not_expose_provider_echo(self):
        Handler.fault = 401
        with self.assertRaises(APIError) as context:
            post_json(self.base, "fake", {}, 5)
        self.assertIn("401", str(context.exception))
        self.assertNotIn("private-provider", str(context.exception))

    def test_endpoint_rules(self):
        self.assertEqual(endpoint("https://api.typesafe.ai/v1/", "/v1/systemone"), "https://api.typesafe.ai/v1/systemone")
        self.assertEqual(endpoint("https://api.deepseek.com/v1", "/chat/completions"), "https://api.deepseek.com/v1/chat/completions")
        for value in ("http://example.com", "https://secret@example.com", "https://example.com?key=secret"):
            with self.assertRaises(ValueError):
                endpoint(value, "/chat/completions")


if __name__ == "__main__":
    unittest.main()
