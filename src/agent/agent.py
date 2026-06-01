import json
import re
from typing import List, Dict, Any, Optional
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.tools.commute_tools import execute_tool as dispatch_tool

class ReActAgent:
    """
    SKELETON: A ReAct-style Agent that follows the Thought-Action-Observation loop.
    Students should implement the core loop logic and tool execution.
    """
    
    def __init__(self, llm: LLMProvider, tools: List[Dict[str, Any]], max_steps: int = 5):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.history = []

    def get_system_prompt(self) -> str:
        """
        TODO: Implement the system prompt that instructs the agent to follow ReAct.
        Should include:
        1.  Available tools and their descriptions.
        2.  Format instructions: Thought, Action, Observation.
        """
        tool_descriptions = "\n".join([f"- {t['name']}: {t['description']}" for t in self.tools])
        return ("Bạn là trợ lý thông minh chuyên giúp người dùng lập lịch trình đi làm hoặc đi học trong ngày.\n\n"
            f"Bạn có các công cụ sau:\n{tool_descriptions}\n\n"
            "Mục tiêu:\n"
            "- Hiểu nhu cầu di chuyển/lịch trình trong ngày của người dùng.\n"
            "- Khi cần lập lịch trình tổng thể, ưu tiên dùng tool plan_day_schedule.\n"
            "- Nếu dùng plan_day_schedule, hãy truyền tham số JSON đầy đủ với các trường cần thiết như:\n"
            '  - date: ngày thực hiện kế hoạch\n'
            '  - home: địa điểm xuất phát\n'
            '  - stops: danh sách các điểm dừng / điểm đến trong ngày\n\n'
            "Quy tắc phản hồi:\n"
            "- Chỉ trả về RAW TEXT.\n"
            "- KHÔNG bọc Action trong code block.\n"
            "- Mỗi bước chỉ dùng đúng một trong hai dạng sau:\n\n"
            "Dạng 1:\n"
            "Thought: <lý do suy nghĩ>\n"
            'Action: tool_name({"key": "value"})\n\n'
            "Dạng 2:\n"
            "Thought: <lý do suy nghĩ>\n"
            "Final Answer: <câu trả lời cuối cùng cho người dùng>\n\n"
            "Ví dụ:\n"
            "Thought: Người dùng muốn lên lịch đi học trong ngày, cần lập kế hoạch đầy đủ từ nhà tới các điểm dừng.\n"
            'Action: plan_day_schedule({"date": "2026-06-01", "home": "Vinhomes Ocean Park", "stops": ["VinUniversity"]})\n\n'
            "Khi đã đủ thông tin, hãy đưa ra Final Answer bằng tiếng Việt, ngắn gọn và rõ ràng, nên tóm tắt:\n"
            "- thời tiết (nếu có từ công cụ),\n"
            "- phương tiện phù hợp,\n"
            "- giờ nên rời nhà,\n"
            "- các điểm dừng chính,\n"
            "- lưu ý quan trọng nếu có.\n\n"
            "Không được bịa kết quả công cụ.\n"
            "Chỉ dùng các tool có trong danh sách."
        )


    def run(self, user_input: str) -> str:
        """
        TODO: Implement the ReAct loop logic.
        1. Generate Thought + Action.
        2. Parse Action and execute Tool.
        3. Append Observation to prompt and repeat until Final Answer.
        """
        logger.log_event("AGENT_START", {"input": user_input, "model": self.llm.model_name})
        
        current_prompt = user_input
        steps = 0

        while steps < self.max_steps:
            # TODO: Generate LLM response
            # result = self.llm.generate(current_prompt, system_prompt=self.get_system_prompt())
            result = self.llm.generate(current_prompt, system_prompt=self.get_system_prompt())
            # TODO: Parse Thought/Action from result
            thought, action = self._parse_result(result)
            # TODO: If Action found -> Call tool -> Append Observation
            if action:
                observation = self._execute_tool(action["name"], action["args"])
                current_prompt = f"{current_prompt}\nObservation: {observation}"
            # TODO: If Final Answer found -> Break loop
            if thought == "Final Answer":
                current_prompt = f"{current_prompt}\nThought: {thought}"
            steps += 1

        logger.log_event("AGENT_END", {"steps": steps})
        return "Not implemented. Fill in the TODOs!"

    def _parse_action_args(self, args_str: str) -> Dict[str, Any]:
        """Parse Action arguments: JSON object or key=value pairs."""
        args_str = (args_str or "").strip()
        if not args_str:
            return {}
        if args_str.startswith("{"):
            return json.loads(args_str)
        result: Dict[str, Any] = {}
        for part in re.split(r",\s*", args_str):
            if "=" not in part:
                continue
            key, _, value = part.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            if value.lower() in ("true", "false"):
                result[key] = value.lower() == "true"
            else:
                try:
                    result[key] = int(value) if value.isdigit() else float(value)
                except ValueError:
                    result[key] = value
        return result

    def _execute_tool(self, tool_name: str, args: str) -> str:
        """Execute a registered tool handler by name."""
        try:
            arguments = self._parse_action_args(args)
        except json.JSONDecodeError as e:
            logger.log_event("TOOL_PARSE_ERROR", {"tool": tool_name, "args": args, "error": str(e)})
            return json.dumps({"ok": False, "error": f"Could not parse arguments: {e}"})

        result = dispatch_tool(tool_name, arguments)
        logger.log_event("TOOL_EXEC", {"tool": tool_name, "arguments": arguments, "result_preview": result[:200]})
        return result
