from app.config import DEFAULT_APP_CONFIG, _deep_merge, parse_jdbc_mysql_url
from app.world_info.utils import (
    chunk_preview,
    compute_content_hash,
    format_world_info_hits_text,
    normalize_text,
    split_text,
    trim_results_by_budget,
)


def test_deep_merge_prefers_override_values():
    merged = _deep_merge(
        DEFAULT_APP_CONFIG,
        {"world_info": {"world_info_injection_chars": 42}, "llm": {"model_name": "foo"}},
    )
    assert merged["world_info"]["world_info_injection_chars"] == 42
    assert merged["llm"]["model_name"] == "foo"
    assert merged["embedding"]["batch_size"] == DEFAULT_APP_CONFIG["embedding"]["batch_size"]


def test_parse_jdbc_mysql_url():
    parsed = parse_jdbc_mysql_url(
        "jdbc:mysql://127.0.0.1:3306/demo_db?useUnicode=true&characterEncoding=utf8&serverTimezone=Asia/Shanghai"
    )
    assert parsed == {
        "host": "127.0.0.1",
        "port": 3306,
        "database": "demo_db",
        "charset": "utf8",
    }


def test_normalize_text_and_hash_are_stable():
    text = "\ufeffhello\r\nworld\r\n"
    normalized = normalize_text(text)
    assert normalized == "hello\nworld"
    assert compute_content_hash(normalized) == compute_content_hash("hello\nworld")


def test_split_text_with_overlap():
    chunks = split_text("abcdefghij", chunk_size=4, chunk_overlap=1)
    assert chunks == ["abcd", "defg", "ghij"]


def test_chunk_preview_and_budget_trim():
    assert chunk_preview("a " * 30, 20).endswith("...")
    items = trim_results_by_budget(["12345", "67890", "abcde"], budget_chars=12, separator="|")
    assert items == ["12345", "67890"]


def test_format_world_info_hits_text():
    text = format_world_info_hits_text(
        [
            {
                "item_id": 1,
                "title": "测试标题",
                "source": "测试来源",
                "published_at": "2026-04-15T10:30:00",
                "score": 0.98765,
                "chunk_text": "这是测试片段",
            }
        ],
        budget_chars=500,
    )
    assert "世界信息补充" in text
    assert "测试标题" in text
    assert "这是测试片段" in text
