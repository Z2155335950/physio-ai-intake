from __future__ import annotations

from pathlib import Path

from app.domain import ChatMessage, RiskAssessment
from app.knowledge.base import KnowledgeConflict


class PromptBuilder:
    def __init__(self, system_prompt_file: Path) -> None:
        if not system_prompt_file.exists():
            raise FileNotFoundError(
                f"系统提示词文件不存在: {system_prompt_file}"
            )
        self._base_prompt = system_prompt_file.read_text(encoding="utf-8-sig").strip()

    def build(
        self,
        history: list[ChatMessage],
        risk: RiskAssessment,
        customer_memory: str | None = None,
        knowledge_conflicts: list[KnowledgeConflict] | None = None,
    ) -> tuple[str, list[ChatMessage]]:
        runtime_rules = """

## 运行期回答规则
1. 你是在为门店理疗师提供工作辅助，不直接面向顾客做诊疗。
2. 必须依据当前提供的门店知识上下文回答。上下文没有的信息，直接回答：
   “该内容不在门店知识库范围内，无法提供参考。”
3. 不根据症状推断或暗示疾病名称，不解读影像/检查报告，不承诺或暗示疗效。
4. 涉及评估、风险、方案或话术时，先列风险提醒，再给参考思路；
   禁止把“参考思路”写成确定结论，禁止指导高风险人群进行正骨或复位。
5. 若问题包含夜间静息痛、持续放射麻木、进行性无力、大小便异常等信号，
   只提示优先到正规医院排查，不提供手法或居家调理方案。
6. 引用门店信息时保留来源名称；不要补充不存在的项目、价格、规则或套餐。
7. 用简洁、可执行的中文回答。不要输出思维链或内部推理过程。
8. 客户纵向记忆只属于当前已选择客户。严禁引用、推断或混用其他客户的信息；
   历史记录不等于当前诊断，引用时注明接诊日期，并区分既往记录与本次描述。
9. 门店知识存在权威等级：A 为安全/经营规则，B 为门店模板/宣教，C 为内部学习笔记。
   同主题来源冲突时，遵循更高权威来源，不平均折中；同等级时采用限制更强、
   适用范围更保守的表述，并明确说明来源存在条件差异或不确定性。
""".strip()

        risk_rules: list[str] = []
        if risk.level != "none":
            risk_rules.append(
                f"当前服务端风险等级：{risk.level}；"
                f"标记：{'、'.join(risk.labels)}。"
            )
            risk_rules.extend(f"- {action}" for action in risk.actions)
            risk_rules.append(
                "回答开头先用【风险提醒】明确风险，再给知识库内的参考内容。"
            )
            if risk.level == "high":
                risk_rules.append(
                    "高风险情形不得给出正骨、复位、扳法或具体调理方案，"
                    "只引导医院排查并说明门店可做的合规沟通。"
                )

        parts = [self._base_prompt, runtime_rules]
        if risk_rules:
            parts.append("## 本次请求风险管控\n" + "\n".join(risk_rules))
        if customer_memory:
            parts.append(customer_memory)
        if knowledge_conflicts:
            conflict_lines = ["## 本次检索发现的知识冲突"]
            for conflict in knowledge_conflicts:
                conflict_lines.append(
                    f"- 主题：{conflict.topic}；优先来源："
                    f"{conflict.preferred_source}（{conflict.preferred_authority} 级）；"
                    f"处理：{conflict.resolution}"
                )
            parts.append("\n".join(conflict_lines))
        return "\n\n".join(parts), history

