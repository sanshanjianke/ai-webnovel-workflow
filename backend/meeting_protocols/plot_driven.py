from backend.core.protocols.meeting import BaseMeetingProtocol, ExpertOpinion, Outline
from backend.core.registry import register_module


@register_module("meeting_protocol")
class PlotDriven(BaseMeetingProtocol):
    @property
    def protocol_id(self) -> str:
        return "plot_driven"
    
    def get_speaking_order(self, context: dict = None) -> list[tuple[str, str]]:
        return [
            ("architect", "main"),
            ("editor", "review"),
            ("character", "supplement"),
        ]
    
    def should_continue(self, rounds: int, consensus: float) -> bool:
        return rounds < 3
    
    def format_output(self, history: list[ExpertOpinion]) -> Outline:
        sequences = []
        characters = []
        world_notes = []
        
        for opinion in history:
            if "序列" in opinion.content:
                sequences.extend(self._extract_sequences(opinion.content))
            if "人物" in opinion.content or "角色" in opinion.content:
                characters.extend(self._extract_characters(opinion.content))
        
        return Outline(
            sequences=sequences,
            characters=characters,
            world_notes=world_notes
        )
    
    def _extract_sequences(self, content: str) -> list[dict]:
        import re
        sequences = []
        pattern = r"\*\*序列[一二三四五六七八九十]+[：:]\s*(.+?)\*\*"
        matches = re.findall(pattern, content)
        for match in matches:
            sequences.append({"name": match.strip()})
        return sequences
    
    def _extract_characters(self, content: str) -> list[dict]:
        import re
        characters = []
        pattern = r"\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|"
        matches = re.findall(pattern, content)
        for match in matches:
            if match[0].strip() and not match[0].strip().startswith("角色"):
                characters.append({
                    "name": match[0].strip(),
                    "role": match[1].strip(),
                    "traits": match[2].strip()
                })
        return characters
