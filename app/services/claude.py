"""
COMPLETE ClaudeService with all required methods
Copy this ENTIRE file to app/services/claude.py
"""

import json
import logging
from typing import Any, Dict, List, Optional
from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.conversation_schemas import (
    ConversationContext,
    ConversationState,
    InterviewAction,
    InterviewMessage,
)
from app.services.recommendation import RecommendationEngine
from app.repositories.conversation import ConversationRepository
from app.repositories.user import UserRepository

logger = logging.getLogger(__name__)


class ClaudeService:
    """Enhanced service for interacting with Claude AI"""

    def __init__(self, settings: Settings):
        self.client = AsyncAnthropic(api_key=settings.claude_api_key)
        self.recommendation_engine = RecommendationEngine()
        
        # You'll need to import these from your app
        from app.repositories import get_conversation_repository, get_user_repository
        self.conversation_repo = get_conversation_repository()
        self.user_repo = get_user_repository()
        
        self.MODEL = "claude-sonnet-4-5-20250929"
        self.base_system_prompt = """You are Glowbot, a smart skincare assistant who helps users create personalized skincare routines. 
Interview users naturally, asking one question at a time while maintaining a friendly, conversational tone. 
Focus on gathering essential information: age, skin type, current concerns, health considerations (pregnancy, medications, allergies), and current skincare routine.

Be concise in your responses, remembering this is a chat conversation. 
Progress through information gathering logically - start with basic skin information, then health safety checks, current routine assessment, and finally provide personalized recommendations. 
Don't move to recommendations until you have all necessary information. If users mention severe skin conditions, always recommend consulting a dermatologist.

When making recommendations, structure them into morning and evening routines with clear usage instructions. 
Include basic safety information like patch testing and potential product interactions. 
Keep responses brief but informative, and don't hesitate to ask clarifying questions when needed to ensure proper recommendations.
Always match the user's language exactly and do not switch languages unless the user does.
"""

    def _detect_language(self, text: str) -> str:
        """Detect if text is Hebrew or English"""
        for char in text:
            if "\u0590" <= char <= "\u05FF":
                return "hebrew"
        return "english"

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

    def _clean_message_history(self, raw_messages: List) -> List[Dict]:
        """
        Clean and prepare message history from database for Claude API.
        
        Filters out:
        - Empty content (None, "", whitespace)
        - Invalid roles
        - Duplicate consecutive messages from same role
        
        Returns properly formatted messages for Claude API.
        """
        cleaned = []
        
        for idx, msg in enumerate(raw_messages):
            # Extract role and content (handle both ORM objects and dicts)
            if hasattr(msg, 'role'):  # ORM object
                role = msg.role.value if hasattr(msg.role, 'value') else str(msg.role)
                content = msg.content
            else:  # Dictionary
                role = msg.get('role')
                content = msg.get('content')
            
            # Normalize role to lowercase
            role = role.lower() if role else None
            
            # FILTER 1: Skip if no role or content
            if not role:
                logger.warning(f"Skipping message {idx}: missing role")
                continue
            
            if content is None:
                logger.warning(f"Skipping message {idx}: content is None")
                continue
            
            # FILTER 2: Only allow user and assistant roles
            if role not in ['user', 'assistant']:
                logger.warning(f"Skipping message {idx}: invalid role '{role}'")
                continue
            
            # FILTER 3: Skip empty strings or whitespace-only content
            if isinstance(content, str):
                if not content.strip():
                    logger.warning(f"Skipping message {idx}: empty or whitespace-only content")
                    continue
                
                # Add valid message
                cleaned.append({
                    "role": role,
                    "content": content.strip()
                })
            
            # FILTER 4: Handle list content (multimodal)
            elif isinstance(content, list):
                # Filter out empty text blocks
                filtered_content = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get('type') == 'text' and item.get('text', '').strip():
                            filtered_content.append(item)
                        elif item.get('type') != 'text':
                            filtered_content.append(item)
                
                if filtered_content:
                    cleaned.append({
                        "role": role,
                        "content": filtered_content
                    })
                else:
                    logger.warning(f"Skipping message {idx}: empty content list")
            
            else:
                logger.warning(f"Skipping message {idx}: unexpected content type {type(content)}")
        
        # FILTER 5: Remove consecutive messages from the same role
        final = []
        last_role = None
        
        for msg in cleaned:
            if msg['role'] != last_role:
                final.append(msg)
                last_role = msg['role']
            else:
                logger.warning(f"Skipping consecutive {msg['role']} message")
        
        # FILTER 6: Ensure conversation starts with user
        if final and final[0]['role'] != 'user':
            logger.warning(f"Removing leading {final[0]['role']} message")
            final = final[1:]
        
        logger.info(f"Cleaned message history: {len(raw_messages)} -> {len(final)} messages")
        
        return final

    async def get_response(self, db: AsyncSession, phone_number: str, user_input: str) -> str:
        """Get a conversational response from Claude with database persistence"""
        try:
            # Get or create user in database
            user = await self.user_repo.get_or_create(db, phone_number)
            
            # Load context from database
            context = await self.conversation_repo.load_context(
                db=db,
                user_id=user.id,
                phone_number=phone_number
            )
            
            # Save user message to database
            await self.conversation_repo.add_user_message(
                db=db,
                user_id=user.id,
                content=user_input
            )
            
            # Get message history from database
            raw_history = await self.conversation_repo.get_message_history(
                db=db,
                user_id=user.id,
                limit=50
            )
            
            # Clean the message history (remove empty messages, etc.)
            message_history = self._clean_message_history(raw_history)
            
            # Add current message
            message_history.append({
                "role": "user",
                "content": user_input
            })
            
            # Log for debugging
            logger.info(f"Sending {len(message_history)} messages to Claude")
            
            # Detect language
            language = self._detect_language(user_input)

            # Build system prompt
            full_system_prompt = (
                self.base_system_prompt + 
                self._get_state_specific_prompt(context.state)
            )
            
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
            
            # Get reasoning state
            reasoning_state = self.recommendation_engine.reason_about_user(context)
            logger.info(f"Reasoning state: confidence={reasoning_state.confidence_level}, "
                       f"missing_critical={len(reasoning_state.missing_critical)}, "
                       f"safety_flags={len(reasoning_state.safety_flags)}")
            
            # Try to get response from Claude
            try:
                response = await self.client.messages.create(
                    model=self.MODEL,
                    max_tokens=1024,
                    messages=message_history,
                    tools=[{
                        "name": "output",
                        "input_schema": InterviewMessage.model_json_schema(),
                    }],
                    tool_choice={"name": "output", "type": "tool"},
                    system=full_system_prompt,
                )
                
                # Process the structured response
                assert response.content[0].type == "tool_use"
                assistant_message = response.content[0].input
                resp = InterviewMessage.model_validate(assistant_message)
                
                # Update the conversation context
                self._update_context_from_response(context, resp)
                
                response_text = resp.message
                
            except Exception as e:
                logger.error(f"Error calling Claude API: {str(e)}")
                # Fallback: Use recommendation engine directly
                if reasoning_state.is_ready_for_recommendation():
                    response_text = self.recommendation_engine.generate_recommendations(context, reasoning_state)
                else:
                    response_text = self.recommendation_engine.generate_next_question(context, reasoning_state)
            
            # Save assistant message to database
            await self.conversation_repo.add_assistant_message(
                db=db,
                user_id=user.id,
                content=response_text
            )
            
            # Save updated context to database
            await self.conversation_repo.save_context(
                db=db,
                user_id=user.id,
                context=context
            )
            
            # Log state transition
            logger.info(
                f"User: {phone_number} (ID: {user.id}) | "
                f"State: {context.state}"
            )
            
            return response_text
        
        except Exception as e:
            logger.error(f"Error in get_response: {str(e)}", exc_info=True)
            return "I apologize, but I'm having trouble responding. Could you try again?"