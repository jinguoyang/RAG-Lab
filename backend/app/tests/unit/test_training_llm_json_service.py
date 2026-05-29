"""training_llm_json_service 单元测试。"""

import pytest

from app.services.training_llm_json_service import (
    TrainingLLMOutputError,
    parse_training_json,
)


class TestParseTrainingJson:
    """parse_training_json 测试集。"""

    def test_plain_json_object(self):
        result = parse_training_json('{"a": 1, "b": "hello"}')
        assert result == {"a": 1, "b": "hello"}

    def test_fenced_json_block(self):
        text = '```json\n{"key": "value"}\n```'
        result = parse_training_json(text)
        assert result == {"key": "value"}

    def test_fenced_block_without_json_marker(self):
        text = '```\n{"key": "value"}\n```'
        result = parse_training_json(text)
        assert result == {"key": "value"}

    def test_required_keys_present(self):
        result = parse_training_json(
            '{"name": "test", "score": 90}',
            required_keys={"name", "score"},
        )
        assert result == {"name": "test", "score": 90}

    def test_missing_required_keys_raises(self):
        with pytest.raises(TrainingLLMOutputError, match="缺少必需字段"):
            parse_training_json(
                '{"name": "test"}',
                required_keys={"name", "score"},
            )

    def test_non_object_with_required_keys_raises(self):
        with pytest.raises(TrainingLLMOutputError, match="必须是 JSON object"):
            parse_training_json(
                '[1, 2, 3]',
                required_keys={"a"},
            )

    def test_empty_text_raises(self):
        with pytest.raises(TrainingLLMOutputError, match="为空"):
            parse_training_json("")

    def test_whitespace_only_raises(self):
        with pytest.raises(TrainingLLMOutputError, match="为空"):
            parse_training_json("   \n\t  ")

    def test_invalid_json_raises(self):
        with pytest.raises(TrainingLLMOutputError, match="不是有效的 JSON"):
            parse_training_json("{not valid json}")

    def test_array_allowed_when_no_required_keys(self):
        result = parse_training_json('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_array_allowed_when_required_keys_empty_set(self):
        result = parse_training_json('[{"a": 1}]', required_keys=set())
        assert result == [{"a": 1}]

    def test_fenced_array(self):
        text = '```json\n[1, 2, 3]\n```'
        result = parse_training_json(text)
        assert result == [1, 2, 3]

    def test_required_keys_subset_present(self):
        """只需包含指定 key，多余字段不影响。"""
        result = parse_training_json(
            '{"a": 1, "b": 2, "c": 3}',
            required_keys={"a", "b"},
        )
        assert result["a"] == 1
        assert result["b"] == 2
