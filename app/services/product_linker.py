"""
ProductLinkerService — generates plain-text product recommendations for a completed routine.

Calls the product linker agent and formats the results as WhatsApp-friendly message strings.
No affiliate links — just specific product name suggestions per routine step.
"""

import logging

from app.agents.product_linker import ProductLinkerDeps, product_linker_agent
from app.config import Settings
from app.schemas import ShoppingList, SkincareRoutine, UserProfile
from app.services.message_splitter import split_for_whatsapp

logger = logging.getLogger(__name__)


def _format_shopping_list(shopping_list: ShoppingList) -> str:
    """Render a ShoppingList as a single WhatsApp-formatted string."""
    lines: list[str] = []

    lines.append(f"🛒 {shopping_list.intro}")
    lines.append("")

    current_time = None
    for rec in shopping_list.recommendations:
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
        for product in rec.product_suggestions:
            lines.append(f"• {product}")
        lines.append("")

    lines.append(f"💡 {shopping_list.outro}")
    return "\n".join(lines)


class ProductLinkerService:
    """Generates personalised product recommendations for a completed routine."""

    def __init__(self, settings: Settings):
        pass

    async def generate_shopping_list(
        self,
        routine: SkincareRoutine,
        profile: UserProfile,
    ) -> list[str]:
        """
        Run the product linker agent and return WhatsApp-ready message strings.

        Returns an empty list if something goes wrong — the routine has already
        been sent, so a failure here should never block the user.
        """
        try:
            deps = ProductLinkerDeps(routine=routine, profile=profile)
            result = await product_linker_agent.run(
                "Generate product recommendations for this routine.",
                deps=deps,
            )
            formatted = _format_shopping_list(result.output)
            return split_for_whatsapp(formatted)

        except Exception as e:
            logger.error(f"Product linker failed: {e}", exc_info=True)
            return []
