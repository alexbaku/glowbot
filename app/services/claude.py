import json
import logging
from typing import Any, Dict, List

from anthropic import AsyncAnthropic
from anthropic.types import MessageParam

from app.config import Settings
from app.models.conversation_schemas import (
    ConversationContext,
    ConversationState,
    InterviewAction,
    InterviewMessage,
)

logger = logging.getLogger(__name__)


class ClaudeService:
    """Enhanced service for interacting with Claude AI"""

    def __init__(self, settings: Settings):
        self.client = AsyncAnthropic(api_key=settings.claude_api_key)
        self.history = []

        self.MODEL = "claude-sonnet-4-5-20250929"
        self.user_contexts = {}  # Store contexts for multiple users
        self.base_system_prompt = """You are Glowbot, a smart skincare assistant who helps users create personalized skincare routines. 
            Interview users naturally, asking one question at a time while maintaining a friendly, conversational tone. 
            Focus on gathering essential information: age, skin type, current concerns, health considerations (pregnancy, medications, allergies), and current skincare routine.

            Be concise in your responses, remembering this is a chat conversation. 
            Progress through information gathering logically - start with basic skin information, then health safety checks, current routine assessment, and finally provide personalized recommendations. 
            Don't move to recommendations until you have all necessary information. If users mention severe skin conditions, always recommend consulting a dermatologist.

            When making recommendations, structure them into morning and evening routines with clear usage instructions. 
            Include basic safety information like patch testing and potential product interactions. 
            Keep responses brief but informative, and don't hesitate to ask clarifying questions when needed to ensure proper recommendations.
            """

    def _get_state_specific_prompt(self, state: ConversationState) -> str:
        """Get additional prompt instructions based on the current state"""

        state_prompts = {
            ConversationState.GREETING: """
        You're starting a new conversation. Greet the user warmly, introduce yourself as GlowBot,
        and explain that you're here to help create a personalized skincare routine.
        Ask only ONE question at a time. First, confirm if they're 18 or older (for safety reasons).
        """,
            ConversationState.AGE_VERIFICATION: """
        You need to verify the user's age. Confirm if they are 18 or older.
        If they confirm, update the collected_info to include {"skin_profile": {"age_verified": true}}
        """,
            ConversationState.SKIN_TYPE: """
        You need to determine the user's skin type. Ask how they would describe their skin:
        - Dry (tight, flaky)
        - Oily (shiny, prone to breakouts)
        - Combination (oily T-zone, dry cheeks)
        - Normal
        - Not sure

        Update collected_info with {"skin_profile": {"skin_type": "their skin type"}}
        """,
            ConversationState.SKIN_CONCERNS: """
        Find out the user's primary skin concerns. They can select multiple:
        - Hyperpigmentation (dark spots, melasma)
        - Signs of aging (fine lines, wrinkles)
        - Dryness/Dehydration
        - Acne
        - Uneven texture
        - Milia
        - Rosacea
        - Enlarged pores
        - Other (let them describe)

        Update collected_info with {"skin_profile": {"concerns": ["concern1", "concern2"]}}
        """,
            ConversationState.HEALTH_CHECK: """
        Find out if the user has any important health considerations:
        - Are they pregnant, breastfeeding, or planning pregnancy?
        - Do they have any skin sensitivities or allergies?
        - Are they using prescription medications that might affect skin (retinoids, antibiotics, Accutane)?

        Update health_info in collected_info accordingly.
        """,
            ConversationState.SUN_EXPOSURE: """
        Determine the user's sun exposure level:
        - Minimal (mostly indoors)
        - Moderate (1-3 hours outside)
        - High (3+ hours outside)
        Also ask if they spend time near windows during the day.

        Update collected_info with {"skin_profile": {"sun_exposure": "their exposure level"}}
        """,
            ConversationState.CURRENT_ROUTINE: """
        Ask about their current skincare routine:
        1. Morning Routine:
        - Cleanser?
        - Treatments/Serums?
        - Moisturizer?
        - Sunscreen?
        2. Evening Routine:
        - Makeup removal method?
        - Cleanser?
        - Treatments/Serums?
        - Moisturizer?

        Update routine in collected_info with what they share.
        """,
            ConversationState.PRODUCT_PREFERENCES: """
        Find out their product preferences:
        - Budget range (budget-friendly/mid-range/high-end)
        - Vegan
        - Cruelty-free
        - Clean/natural ingredients
        - Fragrance-free
        - Any other specific requirements

        Update preferences in collected_info with their answers.
        """,
            ConversationState.SUMMARY: """
        You've collected all necessary information. Provide a summary of what you've learned about their skin:
        - Skin Profile (type, concerns, sun exposure)
        - Health Considerations 
        - Current Routine
        - Product Preferences

        Ask if there's anything they'd like to add or modify.
        Set action to "done" to complete the consultation.
        """,
            ConversationState.COMPLETE: """
        The consultation is complete. Thank the user for providing their information and let them know
        you'll create a personalized skincare routine based on what they've shared.
        Always set action to "done".
        """,
        }

        return state_prompts.get(state, "")

    def _get_or_create_context(self, user_id: str) -> ConversationContext:
        """Get an existing context or create a new one for a user"""
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = ConversationContext(user_id=user_id)
        return self.user_contexts[user_id]

    def _update_context_from_response(
        self, context: ConversationContext, response: InterviewMessage
    ) -> None:
        """Update the conversation context based on the collected information"""
        if response.collected_info:
            context.update(response.collected_info)

        # Progress the state based on collected information
        next_state = context.get_next_state()
        if next_state != context.state:
            logger.info(f"Advancing state: {context.state} -> {next_state}")
            context.state = next_state

    async def get_response(self, user_id: str, user_input: str) -> str:
        """Get a conversational response from Claude with state tracking"""
        try:
            # Get or create context for this user
            context = self._get_or_create_context(user_id)

            # Add user message to history
            if not hasattr(self, "_message_history"):
                self._message_history = {}

            if user_id not in self._message_history:
                self._message_history[user_id] = []

            self._message_history[user_id].append(
                {"role": "user", "content": user_input}
            )

            # Combine base system prompt with state-specific instructions
            full_system_prompt = (
                self.base_system_prompt + self._get_state_specific_prompt(context.state)
            )

            # Add context information to the prompt
            context_section = f"""
        CURRENT CONVERSATION STATE: {context.state}

        INFORMATION COLLECTED SO FAR:
        - Skin Profile: {context.skin_profile.model_dump_json()}
        - Health Info: {context.health_info.model_dump_json()}
        - Current Routine: {context.routine.model_dump_json()}
        - Preferences: {context.preferences.model_dump_json()}

        Based on the current state and information collected, ask the appropriate question to gather missing information.
        In your response, include ALL new information you collect in the collected_info field.
        """

            full_system_prompt += context_section

            # Get response from Claude
            response = await self.client.messages.create(
                model=self.MODEL,
                max_tokens=1024,
                messages=self._message_history[user_id],
                tools=[
                    {
                        "name": "output",
                        "input_schema": InterviewMessage.model_json_schema(),
                    }
                ],
                tool_choice={"name": "output", "type": "tool"},
                system=full_system_prompt,
            )

            # Process the structured response
            assert response.content[0].type == "tool_use"
            assistant_message = response.content[0].input
            resp = InterviewMessage.model_validate(assistant_message)

            # Update the conversation context with newly collected information
            self._update_context_from_response(context, resp)

            # Add assistant message to history
            self._message_history[user_id].append(
                {"role": "assistant", "content": resp.message}
            )

            # Log state transition
            logger.info(
                f"User: {user_id} | State: {context.state} | Action: {resp.action}"
            )

            return resp.message

        except Exception as e:
            logger.error(f"Error getting response: {str(e)}")
            return (
                "I apologize, but I'm having trouble responding. Could you try again?"
            )

    async def analyze_skin(self, image_url: str) -> str:
        """Analyze skin condition from image"""
        # TODO: Implement image analysis using Claude
        return "Skin analysis result"

    async def get_recommendations(self, user_profile: dict) -> str:
        """Get skincare recommendations based on user profile"""
        # TODO: Implement recommendation logic
        return "Skincare recommendations"
