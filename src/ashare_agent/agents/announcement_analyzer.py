from __future__ import annotations

from ashare_agent.domain import AnnouncementEvent, AnnouncementItem

POSITIVE_KEYWORDS = ("增长", "提高", "分红", "回购", "获批", "中标", "增持", "盈利", "扩张")
NEGATIVE_KEYWORDS = ("风险", "诉讼", "退市", "减持", "亏损", "处罚", "暂停", "立案")
MATERIAL_CATEGORIES = ("重大事项", "风险提示", "资产重组", "融资公告")


class AnnouncementAnalyzer:
    def analyze(self, items: list[AnnouncementItem]) -> list[AnnouncementEvent]:
        events: list[AnnouncementEvent] = []
        for item in items:
            title = item.title
            positive_hits = [word for word in POSITIVE_KEYWORDS if word in title]
            negative_hits = [word for word in NEGATIVE_KEYWORDS if word in title]
            if negative_hits:
                sentiment = "negative"
            elif positive_hits:
                sentiment = "positive"
            else:
                sentiment = "neutral"
            is_material = item.category in MATERIAL_CATEGORIES or "重大" in title
            exclude = sentiment == "negative" and any(
                word in title for word in ("风险", "退市", "诉讼")
            )
            reasons = positive_hits or negative_hits or ["未命中明确关键词"]
            events.append(
                AnnouncementEvent(
                    symbol=item.symbol,
                    trade_date=item.trade_date,
                    category=self._normalize_category(item.category, title),
                    sentiment=sentiment,
                    is_material=is_material,
                    exclude=exclude,
                    reasons=[f"{reason} 关键词命中" for reason in reasons],
                )
            )
        return events

    def _normalize_category(self, category: str, title: str) -> str:
        if "分红" in title:
            return "distribution"
        if "风险" in category or "风险" in title:
            return "risk"
        if "资产重组" in category:
            return "restructuring"
        return "general"
