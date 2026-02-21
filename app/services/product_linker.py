"""
ProductLinkerService — generates an iHerb shopping list for a completed routine.

Calls the product linker agent, backfills iHerb URLs into each recommendation
(the agent leaves iherb_url as "" so URL construction stays in Python, not the LLM),
then formats everything as WhatsApp-friendly message strings.
"""

import logging

from app.agents.product_linker import ProductLinkerDeps, build_iherb_url, product_linker_agent
from app.config import Settings
from app.schemas import ShoppingList, SkincareRoutine, UserProfile
from app.services.message_splitter import split_for_whatsapp

logger = logging.getLogger(__name__)


def _format_shopping_list(shopping_list: ShoppingList) -> str:
    """Render a ShoppingList as a single WhatsApp-formatted string."""
    lines: list[str] = []

    lines.append(f"🛒 {shopping_list.intro}")
    lines.append("")

    # Group morning vs evening based on step order in the recommendations.
    # The agent mirrors the routine order, so we just render sequentially
    # and insert a divider when the label switches.
    current_time = None
    for rec in shopping_list.recommendations:
        # Detect time-of-day from step name prefix if present, else just list
        time_label = None
        name_lower = rec.step_name.lower()
        if any(k in name_lower for k in ("morning", "am", "day")):
            time_label = "morning"
        elif any(k in name_lower for k in ("evening", "pm", "night")):
            time_label = "evening"

        if time_label and time_label != current_time:
            current_time = time_label
            emoji = "☀️" if time_label == "morning" else "🌙"
            lines.append(f"*{emoji} {time_label.capitalize()}*")
            lines.append("")

        lines.append(f"*{rec.step_name}*")
        lines.append(f"_{rec.note}_")
        lines.append(f"🔗 {rec.iherb_url}")
        lines.append("")

    lines.append(f"💡 {shopping_list.outro}")
    return "\n".join(lines)


class ProductLinkerService:
    """Generates a personalised iHerb shopping list for a completed routine."""

    def __init__(self, settings: Settings):
        self._template = settings.iherb_search_template

    async def generate_shopping_list(
        self,
        routine: SkincareRoutine,
        profile: UserProfile,
    ) -> list[str]:
        """
        Run the product linker agent and return WhatsApp-ready message strings.

        Returns an empty list if something goes wrong — the routine has already
        been sent, so a shopping list failure should never block the user.
        """
        try:
            deps = ProductLinkerDeps(
                routine=routine,
                profile=profile,
                search_template=self._template,
            )
            result = await product_linker_agent.run(
                "Generate the shopping list for this routine.",
                deps=deps,
            )
            shopping_list = result.output

            # Backfill iHerb URLs — the agent leaves them blank intentionally
            for rec in shopping_list.recommendations:
                rec.iherb_url = build_iherb_url(self._template, rec.search_query)

            formatted = _format_shopping_list(shopping_list)
            return split_for_whatsapp(formatted)

        except Exception as e:
            logger.error(f"Product linker failed: {e}", exc_info=True)
            return []
