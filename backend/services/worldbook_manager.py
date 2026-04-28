import json
import re
from pathlib import Path
from typing import Optional
from datetime import datetime

from backend.modules.worldbook.st_style import STStyleWorldBook
from backend.core.protocols.worldbook import Entry
from backend.core.config import get_config
from backend.core.registry import get_module


WORLDBOOK_MANAGER_PROMPT = """你是一个世界书管理员Agent。你的职责是在每个序列/章节完成后，提取变化并更新世界书。

输入序列内容：
{sequence_content}

当前世界书状态：
{worldbook_state}

请分析并输出以下JSON格式：
{{
  "new_characters": [
    {{
      "id": "char_xxx",
      "keys": ["角色名", "别名"],
      "content": "角色描述",
      "secondary_keys": [],
      "priority": 10
    }}
  ],
  "updated_characters": [
    {{
      "id": "existing_char_id",
      "updates": {{"content": "更新后的描述"}}
    }}
  ],
  "new_foreshadowing": [
    {{
      "id": "foreshadow_xxx",
      "keys": ["伏笔关键词"],
      "content": "伏笔内容描述",
      "metadata": {{"planted_chapter": "章节号", "expected_resolve": "预计回收章节"}}
    }}
  ],
  "resolved_foreshadowing": ["已回收的伏笔ID"],
  "state_changes": [
    {{
      "character_id": "xxx",
      "field": "修为/关系/状态",
      "old_value": "旧值",
      "new_value": "新值",
      "reason": "变化原因"
    }}
  ],
  "conflicts": [
    {{
      "type": "类型",
      "description": "冲突描述",
      "suggestion": "解决建议"
    }}
  ]
}}

注意：
1. 只提取重要的变化，忽略琐碎细节
2. ID要唯一且易识别
3. 冲突检测很重要，发现矛盾要及时报告
"""


class WorldBookManager:
    def __init__(self, worldbook: STStyleWorldBook, llm=None):
        self.worldbook = worldbook
        self.llm = llm
    
    def process_sequence(self, sequence_content: str, sequence_id: str) -> dict:
        if self.llm is None:
            config = get_config()
            llm_cls = get_module("llm", config.llm.primary)
            self.llm = llm_cls()
        
        entries = self.worldbook.list_all_entries()
        worldbook_state = "\n".join([
            f"- {e.keys[0]}: {e.content}"
            for e in entries
        ]) if entries else "暂无条目"
        
        prompt = WORLDBOOK_MANAGER_PROMPT.format(
            sequence_content=sequence_content,
            worldbook_state=worldbook_state
        )
        
        response = self.llm.invoke(prompt)
        
        try:
            changes = self._parse_json_response(response)
        except json.JSONDecodeError:
            changes = {"error": "Failed to parse LLM response", "raw": response}
        
        self._apply_changes(changes, sequence_id)
        
        return changes
    
    def _parse_json_response(self, response: str) -> dict:
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            return json.loads(json_match.group())
        return {}
    
    def _apply_changes(self, changes: dict, sequence_id: str):
        if "error" in changes:
            return
        
        for char_data in changes.get("new_characters", []):
            try:
                entry = Entry(**char_data)
                self.worldbook.create_entry(entry)
            except Exception as e:
                print(f"Warning: Failed to create character: {e}")
        
        for update in changes.get("updated_characters", []):
            try:
                self.worldbook.update_entry(update["id"], update.get("updates", {}))
            except Exception as e:
                print(f"Warning: Failed to update character: {e}")
        
        for foreshadow in changes.get("new_foreshadowing", []):
            try:
                entry = Entry(**foreshadow)
                self.worldbook.create_entry(entry)
            except Exception as e:
                print(f"Warning: Failed to create foreshadowing: {e}")
        
        for resolved_id in changes.get("resolved_foreshadowing", []):
            try:
                self.worldbook.update_entry(resolved_id, {
                    "metadata": {"resolved": True, "resolved_at": datetime.now().isoformat()}
                })
            except Exception as e:
                print(f"Warning: Failed to resolve foreshadowing: {e}")
    
    def commit(self, message: str) -> str:
        return self.worldbook.commit(message)
    
    def get_conflicts(self, changes: dict) -> list[dict]:
        return changes.get("conflicts", [])
