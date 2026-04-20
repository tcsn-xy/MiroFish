from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List


DEFAULT_CONSENSUS_SIMULATION_ID = "__consensus_default_catalog__"
DEFAULT_CONSENSUS_PROJECT_ID = "__consensus_default_project__"


_DEFAULT_PERSONAS: List[Dict[str, Any]] = [
    {
        "user_id": "ai_infrastructure_engineer",
        "username": "zhou_heng",
        "name": "周衡",
        "profession": "AI 基础设施工程师",
        "bio": "长期负责大模型推理、云成本和系统稳定性，习惯先看实现难度、数据质量和上线风险。",
        "persona": "做判断时偏向工程可行性和可扩展性，不喜欢空泛愿景，会追问证据、边界条件和失败模式。",
        "interested_topics": ["AI", "Cloud", "Reliability", "Engineering"],
        "karma": 3200,
    },
    {
        "user_id": "computational_social_scientist",
        "username": "lin_zhiyuan",
        "name": "林致远",
        "profession": "计算社会科学教授",
        "bio": "研究舆论传播、行为数据和因果推断，习惯区分相关性与因果性。",
        "persona": "看问题时会先审视样本、方法和偏差，重视长期趋势，不轻易把短期噪声当结论。",
        "interested_topics": ["Research", "Data", "Public Opinion", "Methods"],
        "karma": 4100,
    },
    {
        "user_id": "investigative_journalist",
        "username": "xu_zhen",
        "name": "许真",
        "profession": "调查记者",
        "bio": "常年跟踪科技公司、公共事务和平台治理，重视消息源可靠性与时间线。",
        "persona": "倾向从公开记录、交叉信源和利益关系入手，警惕营销叙事和单一来源。",
        "interested_topics": ["Media", "Investigations", "Tech", "Governance"],
        "karma": 3600,
    },
    {
        "user_id": "public_policy_analyst",
        "username": "chen_ce",
        "name": "陈策",
        "profession": "公共政策分析师",
        "bio": "关注监管设计、执行成本和政策外溢效应，经常比较不同地区制度。",
        "persona": "判断时会衡量政策目标、执行摩擦和公众接受度，关注中长期制度影响。",
        "interested_topics": ["Policy", "Regulation", "Institutions", "Public Affairs"],
        "karma": 2900,
    },
    {
        "user_id": "startup_operator",
        "username": "song_lan",
        "name": "宋岚",
        "profession": "创业公司创始人",
        "bio": "做过产品、增长和融资，关注市场窗口、团队执行和现金流压力。",
        "persona": "看问题偏结果导向，会评估需求是否真实、机会是否足够大，以及落地速度。",
        "interested_topics": ["Startup", "Product", "Growth", "Business"],
        "karma": 2700,
    },
    {
        "user_id": "school_teacher",
        "username": "ye_qing",
        "name": "叶青",
        "profession": "一线中学教师",
        "bio": "长期在学校面对学生、家长和行政体系，重视现实约束和普遍可理解性。",
        "persona": "倾向从普通人的接受成本、教育公平和实际执行体验出发，不喜欢脱离日常生活的判断。",
        "interested_topics": ["Education", "Youth", "Society", "Communication"],
        "karma": 2300,
    },
    {
        "user_id": "technology_lawyer",
        "username": "han_lv",
        "name": "韩律",
        "profession": "科技与合规律师",
        "bio": "处理数据合规、平台责任和合同风险，习惯拆解责任边界。",
        "persona": "判断时优先看法律定义、证据链和可追责性，关注最坏情形而非理想情形。",
        "interested_topics": ["Law", "Compliance", "Platforms", "Risk"],
        "karma": 3400,
    },
    {
        "user_id": "emergency_physician",
        "username": "gu_ning",
        "name": "顾宁",
        "profession": "急诊科医生",
        "bio": "在高压场景中做快速决策，重视基线风险、误伤代价和证据等级。",
        "persona": "偏好稳健判断，宁愿承认不确定，也不会把未经验证的信息包装成确定结论。",
        "interested_topics": ["Medicine", "Evidence", "Public Health", "Risk"],
        "karma": 3800,
    },
    {
        "user_id": "value_conscious_consumer",
        "username": "wu_xiao",
        "name": "吴晓",
        "profession": "消费者研究员",
        "bio": "长期观察价格、品牌和用户口碑，关注实际体验、可负担性和信任。",
        "persona": "看问题会站在普通购买者角度，重点评估性价比、感知风险和是否值得为此改变行为。",
        "interested_topics": ["Consumer", "Pricing", "Brand", "User Experience"],
        "karma": 2500,
    },
    {
        "user_id": "industry_supply_chain_analyst",
        "username": "gao_yue",
        "name": "高越",
        "profession": "产业与供应链分析师",
        "bio": "研究制造、渠道和全球供应链波动，擅长把新闻与实际产能约束对应起来。",
        "persona": "判断时关注供给能力、替代路径和时间滞后，警惕只看需求侧的乐观推断。",
        "interested_topics": ["Industry", "Supply Chain", "Manufacturing", "Trade"],
        "karma": 3000,
    },
]


def is_default_consensus_simulation_id(simulation_id: str | None) -> bool:
    return (simulation_id or "").strip() == DEFAULT_CONSENSUS_SIMULATION_ID


def resolve_consensus_simulation_id(simulation_id: str | None) -> str:
    normalized = (simulation_id or "").strip()
    return normalized or DEFAULT_CONSENSUS_SIMULATION_ID


def get_default_consensus_personas() -> List[Dict[str, Any]]:
    return deepcopy(_DEFAULT_PERSONAS)


def get_default_consensus_catalog() -> Dict[str, Any]:
    return {
        "catalog_id": "default",
        "catalog_name": "Consensus QA Default Persona Catalog",
        "simulation_id": DEFAULT_CONSENSUS_SIMULATION_ID,
        "project_id": DEFAULT_CONSENSUS_PROJECT_ID,
        "persona_platform": "reddit",
        "source": "builtin",
        "personas": get_default_consensus_personas(),
    }
