"""
Content moderation: sensitive word filtering and text safety checks.
Uses a dual-layer approach: keyword blacklist + heuristic rules.
"""
import re

# Core sensitive categories for Chinese content moderation
# 注意：不能使用 \b —— 汉字同属 \w，汉字之间不存在单词边界，
# 带 \b 的模式在典型中文句子中永不匹配。直接用子串式交替匹配。
SENSITIVE_PATTERNS = {
    'political': [
        r'(推翻|颠覆|反党|反政府|煽动|暴乱)',
    ],
    'pornographic': [
        r'(色情|淫秽|嫖娼|卖淫|裸聊|约炮)',
    ],
    'violence': [
        r'(杀人|放火|爆炸物|恐怖主义|枪支|毒品)',
    ],
    'fraud': [
        r'(诈骗|传销|洗钱|非法集资|套现)',
    ],
    'privacy': [
        r'(身份证号|银行卡号|密码|手机号).*\d{4,}',
    ],
}

# Compiled regex cache
_COMPILED = {cat: [re.compile(p, re.IGNORECASE) for p in pats] for cat, pats in SENSITIVE_PATTERNS.items()}

# Allowlist for tourism/culture domain (reduce false positives)
ALLOWLIST = {
    '白云', '广州', '文旅', '景区', '酒店', '民宿', '图书馆', '文化站',
    '非遗', '景点', '公园', '旅游', '旅行', '路线', '地图',
}


def moderate_text(text: str) -> dict:
    """
    Analyze text for sensitive content.
    Returns: {"clean": bool, "categories": [str], "reason": str}
    """
    if not text or not isinstance(text, str):
        return {"clean": True, "categories": [], "reason": ""}

    text = text.strip()
    if len(text) > 2000:
        text = text[:2000]

    hits = []
    for category, patterns in _COMPILED.items():
        for pat in patterns:
            if pat.search(text):
                hits.append(category)
                break

    if not hits:
        return {"clean": True, "categories": [], "reason": ""}

    # Check allowlist to reduce false positives
    for word in ALLOWLIST:
        if word in text and len(text) < 100:
            # Short queries with allowlisted words are usually safe
            hits = [h for h in hits if h != 'political']

    if not hits:
        return {"clean": True, "categories": [], "reason": ""}

    return {
        "clean": False,
        "categories": list(set(hits)),
        "reason": f"检测到敏感内容: {', '.join(set(hits))}",
    }


def check_question(question: str) -> tuple:
    """
    Returns (is_safe, reason_or_none).
    Safe questions pass through; unsafe are blocked with reason.
    """
    result = moderate_text(question)
    if result["clean"]:
        return True, None
    return False, result["reason"]
