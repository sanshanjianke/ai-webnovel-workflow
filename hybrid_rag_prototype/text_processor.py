"""
多维度切片模块 - 笔记6核心实现

实现四个维度的切片：
- 剧情维度：按序列/事件边界切分
- 人物维度：按人物出场/退场切分
- 爽点维度：按情绪转折点切分（压抑/爆发/余韵）
- 功能维度：按叙事功能边界切分
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path
import hashlib
import json

from config import SLICE_DIMENSIONS, EMOTION_PHASES, FUNCTION_TYPES


@dataclass
class SliceMetadata:
    """切片元数据"""
    dimension: str  # 切片维度：plot/character/emotion/function
    unit_id: str  # 切片唯一ID
    name: str  # 切片名称
    text_hash: str  # 文本内容的hash值（用于关联MD文本库）
    tags: Dict[str, Any] = field(default_factory=dict)  # 标签字段
    pointer: str = ""  # 指针，指向MD文本库中的文件路径


@dataclass
class SliceUnit:
    """切片单元"""
    metadata: SliceMetadata
    summary: str  # 摘要（存入向量数据库）
    full_text: str  # 完整文本（存入MD文本库）
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "metadata": {
                "dimension": self.metadata.dimension,
                "unit_id": self.metadata.unit_id,
                "name": self.metadata.name,
                "text_hash": self.metadata.text_hash,
                "tags": self.metadata.tags,
                "pointer": self.metadata.pointer
            },
            "summary": self.summary,
            "full_text": self.full_text
        }


class MultiDimensionalSliceProcessor:
    """多维度切片处理器"""
    
    def __init__(self):
        self.dimensions = SLICE_DIMENSIONS
        
    def process_text(self, raw_text: str, annotated_data: Dict) -> Dict[str, List[SliceUnit]]:
        """
        处理原始文本，生成多维度切片
        
        Args:
            raw_text: 原始文本内容
            annotated_data: 标注数据（包含各维度的切片信息）
            
        Returns:
            各维度的切片列表
        """
        slices = {}
        
        # 处理剧情维度（完整序列）
        slices["plot"] = self._process_plot_dimension(raw_text, annotated_data.get("plot", {}))
        
        # 处理人物维度（按人物切分）
        slices["character"] = self._process_character_dimension(annotated_data.get("character", {}).get("units", []))
        
        # 处理爽点维度（按情绪阶段切分）
        slices["emotion"] = self._process_emotion_dimension(annotated_data.get("emotion", {}).get("units", []))
        
        # 处理功能维度（按叙事功能切分）
        slices["function"] = self._process_function_dimension(annotated_data.get("function", {}).get("units", []))
        
        return slices
    
    def _process_plot_dimension(self, raw_text: str, plot_data: Dict) -> List[SliceUnit]:
        """处理剧情维度"""
        if not plot_data:
            # 如果没有标注数据，将整个文本作为一个切片
            return self._create_slice(
                dimension="plot",
                unit_id="plot_auto_001",
                name="完整剧情",
                text=raw_text,
                tags={"auto_generated": True}
            )
        
        # 使用标注数据创建切片
        return self._create_slice(
            dimension="plot",
            unit_id=plot_data.get("unit_id", "plot_001"),
            name=plot_data.get("name", "剧情切片"),
            text=plot_data.get("text", raw_text),
            tags=plot_data.get("metadata", {})
        )
    
    def _process_character_dimension(self, character_units: List[Dict]) -> List[SliceUnit]:
        """处理人物维度"""
        slices = []
        
        for unit_data in character_units:
            # 将人物的多个片段合并
            full_text = "\n".join(unit_data.get("text_segments", []))
            
            slice_unit = self._create_slice(
                dimension="character",
                unit_id=unit_data.get("unit_id", "char_auto_001"),
                name=unit_data.get("name", "人物切片"),
                text=full_text,
                tags={
                    "character": unit_data.get("character", ""),
                    "role": unit_data.get("role", ""),
                    "trait": unit_data.get("trait", ""),
                    **unit_data.get("metadata", {})
                }
            )[0]
            
            slices.append(slice_unit)
        
        return slices
    
    def _process_emotion_dimension(self, emotion_units: List[Dict]) -> List[SliceUnit]:
        """处理爽点维度"""
        slices = []
        
        for unit_data in emotion_units:
            slice_unit = self._create_slice(
                dimension="emotion",
                unit_id=unit_data.get("unit_id", "emotion_auto_001"),
                name=unit_data.get("name", "情绪切片"),
                text=unit_data.get("text", ""),
                tags={
                    "phase": unit_data.get("phase", ""),
                    "intensity": unit_data.get("intensity", ""),
                    **unit_data.get("metadata", {})
                }
            )[0]
            
            slices.append(slice_unit)
        
        return slices
    
    def _process_function_dimension(self, function_units: List[Dict]) -> List[SliceUnit]:
        """处理功能维度"""
        slices = []
        
        for unit_data in function_units:
            slice_unit = self._create_slice(
                dimension="function",
                unit_id=unit_data.get("unit_id", "func_auto_001"),
                name=unit_data.get("name", "功能切片"),
                text=unit_data.get("text", ""),
                tags={
                    "function_type": unit_data.get("function_type", ""),
                    "function_role": unit_data.get("metadata", {}).get("function_role", ""),
                    "connect_to": unit_data.get("metadata", {}).get("connect_to", "")
                }
            )[0]
            
            slices.append(slice_unit)
        
        return slices
    
    def _create_slice(
        self, 
        dimension: str, 
        unit_id: str, 
        name: str, 
        text: str,
        tags: Dict[str, Any]
    ) -> List[SliceUnit]:
        """创建切片单元"""
        
        # 计算文本hash
        text_hash = hashlib.md5(text.encode()).hexdigest()
        
        # 生成摘要（这里简化处理，实际应用中可以用LLM生成）
        summary = self._generate_summary(text, dimension, name)
        
        # 创建元数据
        metadata = SliceMetadata(
            dimension=dimension,
            unit_id=unit_id,
            name=name,
            text_hash=text_hash,
            tags=tags,
            pointer=f"{dimension}/{unit_id}.md"  # 指向MD文本库的路径
        )
        
        # 创建切片单元
        slice_unit = SliceUnit(
            metadata=metadata,
            summary=summary,
            full_text=text
        )
        
        return [slice_unit]
    
    def _generate_summary(self, text: str, dimension: str, name: str) -> str:
        """
        生成切片摘要
        
        在实际应用中，这里应该调用LLM生成摘要
        目前简化处理：取前100字作为摘要
        """
        # 简化摘要：包含维度信息和前100字
        dim_name = self.dimensions.get(dimension, {}).get("name", dimension)
        text_preview = text[:100].strip().replace("\n", " ")
        
        summary = f"[{dim_name}] {name}: {text_preview}..."
        return summary


class SliceProcessorAgent:
    """
    切分Agent
    
    在实际应用中，这个Agent需要：
    1. 理解叙事学概念（序列边界、情绪转折、功能边界）
    2. 自动识别切分点
    3. 生成标注数据
    
    当前原型使用预标注数据，Agent仅做处理
    """
    
    def __init__(self, llm=None):
        """
        Args:
            llm: LangChain LLM对象（用于自动识别切分点）
        """
        self.llm = llm
        self.processor = MultiDimensionalSliceProcessor()
    
    def auto_slice(self, raw_text: str) -> Dict:
        """
        自动切片（需要LLM支持）
        
        未来功能：
        - 自动识别序列边界
        - 自动识别情绪转折点
        - 自动识别人物出场/退场
        - 自动识别叙事功能
        
        当前原型：返回提示信息
        """
        if not self.llm:
            return {
                "status": "need_annotation",
                "message": "当前原型使用预标注数据，自动切片功能需要LLM支持",
                "hint": "请提供annotated_data参数，或实现LLM自动标注"
            }
        
        # TODO: 实现LLM自动识别切分点
        # 这里需要设计专门的Prompt，让LLM识别：
        # - 序列开始/结束
        # - 压抑/爆发/余韵转折点
        # - 人物出场/退场
        # - 功能边界
        
        return {"status": "pending", "message": "LLM自动切片功能待实现"}
    
    def process_with_annotation(self, raw_text: str, annotated_data: Dict) -> Dict[str, List[SliceUnit]]:
        """使用预标注数据处理"""
        return self.processor.process_text(raw_text, annotated_data)


def save_slices_to_files(slices: Dict[str, List[SliceUnit]], output_dir: Path):
    """
    将切片保存到文件
    
    用于调试和查看切片结果
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for dimension, slice_list in slices.items():
        dim_dir = output_dir / dimension
        dim_dir.mkdir(exist_ok=True)
        
        for slice_unit in slice_list:
            file_path = dim_dir / f"{slice_unit.metadata.unit_id}.json"
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(slice_unit.to_dict(), f, ensure_ascii=False, indent=2)
    
    print(f"切片已保存到: {output_dir}")


if __name__ == "__main__":
    # 测试切片处理
    from sample_data import AUCTION_SEQUENCE, ANNOTATED_SLICES
    
    processor = SliceProcessorAgent()
    slices = processor.process_with_annotation(AUCTION_SEQUENCE, ANNOTATED_SLICES)
    
    print("=== 多维度切片结果 ===")
    for dim, slice_list in slices.items():
        print(f"\n【{SLICE_DIMENSIONS[dim]['name']}】切片数: {len(slice_list)}")
        for s in slice_list:
            print(f"  - {s.metadata.name} (ID: {s.metadata.unit_id})")
            print(f"    摘要: {s.summary[:80]}...")
            print(f"    标签: {s.metadata.tags}")
    
    # 保存切片文件（用于调试）
    save_slices_to_files(slices, Path("test_slices_output"))