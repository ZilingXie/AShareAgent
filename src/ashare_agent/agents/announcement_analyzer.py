from __future__ import annotations

from ashare_agent.domain import AnnouncementEvent, AnnouncementItem

POSITIVE_KEYWORDS = ("增长", "提高", "分红", "回购", "获批", "中标", "增持", "盈利", "扩张")
NEGATIVE_KEYWORDS = ("风险", "诉讼", "退市", "减持", "亏损", "处罚", "暂停", "立案")
MATERIAL_CATEGORIES = ("重大事项", "风险提示", "资产重组", "融资公告", "持股变动")
MATERIAL_EVENT_CATEGORIES = (
    "distribution",
    "share_reduction",
    "litigation",
    "penalty",
    "restructuring",
    "risk",
)
EXCLUDED_EVENT_CATEGORIES = ("share_reduction", "litigation", "penalty", "risk")


class AnnouncementAnalyzer:
    def analyze(self, items: list[AnnouncementItem]) -> list[AnnouncementEvent]:
        events: list[AnnouncementEvent] = []
        for item in items:
            title = item.title
            normalized_category = self._normalize_category(item.category, title)
            positive_hits = [word for word in POSITIVE_KEYWORDS if word in title]
            negative_hits = [word for word in NEGATIVE_KEYWORDS if word in title]
            if negative_hits:
                sentiment = "negative"
            elif positive_hits:
                sentiment = "positive"
            else:
                sentiment = "neutral"
            is_material = (
                item.category in MATERIAL_CATEGORIES
                or "重大" in title
                or normalized_category in MATERIAL_EVENT_CATEGORIES
            )
            exclude = sentiment == "negative" and normalized_category in EXCLUDED_EVENT_CATEGORIES
            reasons = self._reasons(
                normalized_category=normalized_category,
                positive_hits=positive_hits,
                negative_hits=negative_hits,
            )
            events.append(
                AnnouncementEvent(
                    symbol=item.symbol,
                    trade_date=item.trade_date,
                    category=normalized_category,
                    sentiment=sentiment,
                    is_material=is_material,
                    exclude=exclude,
                    reasons=reasons,
                )
            )
        return events

    def _normalize_category(self, category: str, title: str) -> str:
        if "分红" in title:
            return "distribution"
        if "减持" in title:
            return "share_reduction"
        if "诉讼" in title:
            return "litigation"
        if "处罚" in title or "立案" in title:
            return "penalty"
        if "资产重组" in category or "资产重组" in title:
            return "restructuring"
        if "风险" in category or "风险" in title:
            return "risk"
        return "general"

    def _reasons(
        self,
        normalized_category: str,
        positive_hits: list[str],
        negative_hits: list[str],
    ) -> list[str]:
        hits = negative_hits + [word for word in positive_hits if word not in negative_hits]
        if hits:
            return [f"{hit} 关键词命中" for hit in hits]
        if normalized_category == "restructuring":
            return ["资产重组 分类命中"]
        return ["未命中明确关键词"]
