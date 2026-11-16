from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.domain import RiskAssessment


REDLINE_REPLY = (
    "抱歉，我不能进行医疗诊断、疗效承诺以及医疗相关诊疗操作。"
    "我仅作为理疗养护辅助工具，相关情况建议到正规医院就诊检查。"
)

DISCLAIMER = (
    "免责：以上仅理疗养护参考，不构成医疗诊断，"
    "不能替代医院检查与医生诊疗，最终操作由理疗师线下风险评估后决定。"
)


@dataclass(frozen=True, slots=True)
class RedlineRule:
    code: str
    label: str
    pattern: re.Pattern[str]


@dataclass(slots=True)
class SafetyDecision:
    blocked: bool = False
    redline_code: str | None = None
    redline_label: str | None = None
    risk: RiskAssessment = field(default_factory=RiskAssessment)


def _rule(code: str, label: str, pattern: str) -> RedlineRule:
    return RedlineRule(code=code, label=label, pattern=re.compile(pattern, re.I))


REDLINE_RULES: tuple[RedlineRule, ...] = (
    _rule(
        "diagnosis",
        "医疗诊断或疾病推断",
        r"(?:帮我|请你|直接|给我)?\s*(?:诊断|确诊|判断|推断|看看|看一下)"
        r".{0,30}(?:是什么病|什么病|啥病|什么原因|哪种病|病名)"
        r"|(?:是不是|是否为|像不像|会不会是|是不是得了).{0,20}"
        r"(?:滑膜炎|椎间盘突出|腰突|椎管狭窄|强直性脊柱炎|类风湿|"
        r"骨折|骨裂|肿瘤|感染|坐骨神经痛)"
        r"|(?:判断|诊断|评估|确认).{0,16}(?:突出|压迫|侧弯).{0,10}(?:程度|几度|严重)",
    ),
    _rule(
        "imaging",
        "影像或检查报告解读",
        r"(?:帮我|给我|直接|看看|看一下|解读|分析|读|看)"
        r".{0,18}(?:CT|MRI|核磁|X光|X线|片子|影像|检查报告|报告单)"
        r"|(?:CT|MRI|核磁|X光|X线|片子|影像|检查报告|报告单).{0,20}"
        r"(?:怎么看|什么意思|有问题吗|诊断|判断|解读|分析)",
    ),
    _rule(
        "promise",
        "疗效承诺",
        r"(?:保证|承诺|必须).{0,14}(?:治好|治愈|根治|不痛|不疼|不复发|矫正成功|完全恢复)"
        r"|(?:正骨|调理|手法|复位).{0,18}(?:一定|绝对|肯定|完全|彻底)"
        r".{0,12}(?:治好|治愈|根治|不痛|不疼|不复发)"
        r"|(?:正骨|调理).{0,16}(?:保证|包治|根治).{0,12}"
        r"(?:好|不痛|不疼|不复发|痊愈)"
        r"|(?:正骨|调理|手法|复位).{0,12}(?:能不能|可以|能|会)"
        r".{0,6}(?:治好|治愈|根治|纠正|矫正|消除)"
        r".{0,8}(?:吗|么|嘛|吧|？|\?|$)",
    ),
    _rule(
        "acute_manipulation",
        "急性或高风险情形下的手法指导",
        r"(?:骨折|骨裂|新鲜脱位|急性损伤|急性期|肿瘤|骨转移|感染|骨髓炎|"
        r"结核|高热|术后(?:急性期|早期)).{0,28}"
        r"(?:正骨|复位|扳法|扳动|手法|推拿|松解|怎么调|如何调)"
        r"|(?:正骨|复位|扳法|扳动|手法|推拿|松解|怎么调|如何调)"
        r".{0,28}(?:骨折|骨裂|新鲜脱位|急性损伤|急性期|肿瘤|骨转移|感染|"
        r"骨髓炎|结核|高热|术后(?:急性期|早期))",
    ),
    _rule(
        "medication",
        "药品、剂量或处方",
        r"(?:开|给|推荐|建议|告诉我|用什么|吃什么|服用什么|替代)"
        r".{0,18}(?:药|药方|药品|处方|止痛药|消炎药)"
        r"|(?:药名|药品名称|用药|剂量|mg|毫克|换药方案|替代药物|停药)"
        r"(?:是什么|多少|怎么|如何|方案|推荐|指导|$)",
    ),
    _rule(
        "medical_document",
        "医疗证明或正式医疗病历",
        r"(?:开具|出具|代写|帮我写|生成).{0,18}"
        r"(?:诊断证明|病假条|医疗证明|医疗病历|正式病历)"
        r"|(?:诊断证明|病假条|医疗证明|医疗病历|正式病历).{0,14}"
        r"(?:怎么写|开具|出具|代写)",
    ),
    _rule(
        "jailbreak",
        "绕过安全约束",
        r"(?:忽略|无视|绕过|跳过|取消).{0,18}(?:指令|规则|限制|安全约束|系统提示词)"
        r"|(?:伪装|假装|模拟).{0,10}(?:测试|医生|诊断|无限制)"
        r"|(?:管理员模式|开发者模式|DAN模式|越狱模式|系统提示词)",
    ),
)


RISK_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "高血压",
        "血压需结合现场复测和基础病控制情况判断；数值持续偏高时不安排正骨复位。",
        re.compile(r"高血压|血压\s*(?:为|是|有)?\s*\d{2,3}\s*[/／]\s*\d{2,3}", re.I),
    ),
    (
        "糖尿病",
        "血糖控制不佳或伴周围神经病变时，禁止正骨复位，仅考虑轻柔表层放松。",
        re.compile(r"糖尿病|血糖(?:高|不稳|控制不佳)", re.I),
    ),
    (
        "骨质疏松/骨量减少",
        "禁止扳法、复位和椎体深压，只做表层舒缓；建议先取得医院骨密度及专科意见。",
        re.compile(r"骨质疏松|骨量减少|骨密度低", re.I),
    ),
    (
        "风湿/类风湿/强直性脊柱炎",
        "禁止扳动、正骨和大幅度关节拉伸，仅做保暖与温和浅层放松。",
        re.compile(r"风湿|类风湿|强直性脊柱炎", re.I),
    ),
    (
        "抗凝药使用者",
        "禁止大力按压、深层松解和正骨扳动，需先由医生评估出血风险。",
        re.compile(r"抗凝|阿司匹林|氯吡格雷|利伐沙班|华法林|出血性疾病|凝血", re.I),
    ),
    (
        "孕产/备孕人群",
        "孕早期、先兆流产、胎盘不稳或产后恢复不佳者不做正骨复位；腰腹操作尤其谨慎。",
        re.compile(r"怀孕|孕妇|孕早期|备孕|先兆流产|胎盘|产后|恶露", re.I),
    ),
    (
        "高龄/低龄",
        "老人和儿童骨关节风险较高，优先轻柔放松，避免扳法复位。",
        re.compile(r"高龄|(?:7[5-9]|[89]\d|\d{3})\s*岁|老人|儿童|小孩", re.I),
    ),
)

URGENT_RISK_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "夜间静息痛",
        "存在夜间痛或静息痛时，优先建议医院排查，不提供调理方案。",
        re.compile(
            r"(?:晚上|夜间|睡觉|静息|安静时).{0,12}(?:痛|疼)"
            r"|(?:痛|疼).{0,12}(?:晚上|夜间|睡觉|静息|安静时)",
            re.I,
        ),
    ),
    (
        "持续放射麻木或无力",
        "持续放射麻木、进行性无力属于高风险信号，优先建议医院排查。",
        re.compile(
            r"(?:持续|一直|越来越|进行性).{0,12}(?:麻木|放射|串麻|无力|发软)"
            r"|(?:麻木|放射|串麻|无力|发软).{0,12}(?:持续|一直|越来越|加重)",
            re.I,
        ),
    ),
    (
        "大小便异常",
        "大小便控制异常需立即就医，不进行任何正骨或调理操作。",
        re.compile(r"大小便.*(?:异常|失禁|困难|憋不住)|尿失禁|排便失禁", re.I),
    ),
    (
        "不明原因消瘦",
        "不明原因体重下降需优先排查器质性问题，不做调理方案推荐。",
        re.compile(r"(?:不明原因|突然|持续).{0,8}(?:消瘦|体重下降|瘦了)", re.I),
    ),
)


class SafetyGuard:
    def inspect_input(self, text: str) -> SafetyDecision:
        normalized = re.sub(r"\s+", " ", text).strip()
        for rule in REDLINE_RULES:
            if rule.pattern.search(normalized):
                return SafetyDecision(
                    blocked=True,
                    redline_code=rule.code,
                    redline_label=rule.label,
                )

        labels: list[str] = []
        actions: list[str] = []

        for label, action, pattern in RISK_PATTERNS:
            if pattern.search(normalized):
                labels.append(label)
                actions.append(action)

        blood_pressure = re.search(
            r"血压\s*(?:为|是|有)?\s*(\d{2,3})\s*[/／]\s*(\d{2,3})",
            normalized,
            re.I,
        )
        if blood_pressure:
            systolic, diastolic = map(int, blood_pressure.groups())
            if systolic > 160 or diastolic > 100:
                if "高血压" not in labels:
                    labels.append("血压持续偏高")
                actions.insert(
                    0,
                    "血压高于160/100mmHg时不安排正骨复位，仅做浅层舒缓或建议就医。",
                )

        for label, action, pattern in URGENT_RISK_PATTERNS:
            if pattern.search(normalized):
                labels.append(label)
                actions.append(action)

        if any(
            pattern.search(normalized)
            for _, _, pattern in URGENT_RISK_PATTERNS
        ):
            level = "high"
        elif labels:
            level = "caution"
        else:
            level = "none"

        return SafetyDecision(
            blocked=False,
            risk=RiskAssessment(level=level, labels=labels, actions=actions),
        )

    def enforce_output(
        self, reply: str, risk: RiskAssessment
    ) -> tuple[str, list[str]]:
        warnings: list[str] = []
        normalized = re.sub(r"\s+", " ", reply).strip()

        has_unsafe_operation = risk.level != "none" and self._has_unnegated_match(
            r"(?:建议|可以|可以安排|适合|能够).{0,16}"
            r"(?:正骨|扳法|复位|正骨复位)",
            normalized,
        )
        has_unsafe_claim = any(
            self._has_unnegated_match(pattern, normalized)
            for pattern in (
                r"(?:可以|能够|一定能|保证|肯定).{0,10}"
                r"(?:治好|治愈|根治|不再复发)",
                r"(?:无需|不用).{0,8}(?:医院|就医|检查)",
                r"(?:诊断为|确诊为).{0,16}"
                r"(?:突出|狭窄|滑膜炎|类风湿|强直)",
            )
        )

        if has_unsafe_operation:
            warnings.append("输出包含风险情形下不适宜的操作建议，已替换为安全回复。")
            risk_actions = "\n".join(f"- {action}" for action in risk.actions)
            risk_labels = "、".join(risk.labels)
            reply = (
                f"【风险提醒】当前情况涉及{risk_labels}，需要线下核验。\n\n"
                f"{risk_actions}\n\n"
                "不能仅凭文字信息确认是否适合具体手法，禁止安排正骨复位；"
                "请先结合现场风险筛查及医院检查意见，仅考虑温和养护舒缓。"
            )
        elif has_unsafe_claim:
            warnings.append("输出包含诊断或疗效承诺风险词，已替换为安全回复。")
            reply = (
                "该问题涉及医疗判断或效果承诺，不适合由理疗养护辅助助手回答。"
                "建议由正规医疗机构检查评估，门店仅能提供合规的养护沟通参考。"
            )

        if DISCLAIMER not in reply:
            reply = f"{reply.rstrip()}\n\n{DISCLAIMER}"

        return reply, warnings

    @staticmethod
    def _has_unnegated_match(pattern: str, text: str) -> bool:
        for match in re.finditer(pattern, text):
            context = text[max(0, match.start() - 6) : match.end() + 6]
            if not re.search(r"不|禁|勿|别|避免|不可|不能|不宜", context):
                return True
        return False

