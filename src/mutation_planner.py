import json
import re
from collections import namedtuple
from typing import Optional
from src.llm_client import LLMClient

MutationPlan = namedtuple("MutationPlan", ["description", "line_number", "original_line", "mutated_line"])

class MutationPlanner:
    def __init__(self, client: LLMClient, prompt_template_path: str):
        self.client = client
        with open(prompt_template_path, "r", encoding="utf-8") as f:
            self.prompt_template = f.read()

    def _prepend_line_numbers(self, ir_text: str) -> str:
        lines = ir_text.splitlines()
        numbered_lines = [f"{i+1}: {line}" for i, line in enumerate(lines)]
        return "\n".join(numbered_lines)

    def _extract_json(self, text: str) -> Optional[str]:
        """Extracts JSON block from markdown formatted text if present."""
        match = re.search(r'```json\n(.*?)\n```', text, re.DOTALL)
        if match:
            return match.group(1)
        
        match = re.search(r'```\n(.*?)\n```', text, re.DOTALL)
        if match:
            return match.group(1)
            
        return text

    def plan(self, seed_ir: str) -> Optional[MutationPlan]:
        numbered_ir = self._prepend_line_numbers(seed_ir)
        prompt = self.prompt_template.replace("{numbered_ir}", numbered_ir)
        
        response_text = self.client.generate(prompt)
        if not response_text:
            return None
            
        json_str = self._extract_json(response_text)
        
        try:
            data = json.loads(json_str)
            return MutationPlan(
                description=data["description"],
                line_number=data["line_number"],
                original_line=data["original_line"],
                mutated_line=data["mutated_line"]
            )
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[MutationPlanner] Failed to parse JSON or missing keys: {e}")
            return None
