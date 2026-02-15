"""
Claude Service - Integrated with Reasoning-Based Recommendation Engine

This service now acts as a bridge between WhatsApp conversation flow
and the stateful recommendation engine. It delegates reasoning and 
follow-up generation to the recommendation engine.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from anthropic import AsyncAnthropic
from anthropic.types import MessageParam
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories import get_conversation_repository, get_user_repository
from app.config import Settings
from app.services.new_recommendation import CredibleProgressiveEngine
from app.models.conversation_schemas import (
    ConversationContext,
    ConversationState,
    InterviewAction,
    InterviewMessage,
)

logger = logging.getLogger(__name__)


class ClaudeService:
    """
    Enhanced service that integrates reasoning-based recommendations.
    
    Key changes:
    1. Uses recommendation engine for reasoning and follow-ups
    2. Less prescriptive prompts - lets Claude be more natural
    3. Focuses on data collection quality over rigid state flow
    """

    def __init__(self, settings: Settings):
        self.client = AsyncAnthropic(api_key=settings.claude_api_key)
        self.conversation_repo = get_conversation_repository()
        self.user_repo = get_user_repository()
        self.MODEL = "claude-sonnet-4-5-20250929"
        
        # Initialize the credible progressive recommendation engine
        self.recommendation_engine = CredibleProgressiveEngine()
        logger.info("Credible progressive recommendation engine initialized")
        
        # Simplified base prompt - less prescriptive, more natural
        self.base_system_prompt = """You are Glowbot, a smart skincare consultant helping users build personalized routines.

Your approach:
1. Have a natural conversation - you're a consultant, not a form
2. Ask ONE question at a time
3. Reference what the user already told you in follow-ups
4. Be curious when something is unclear or contradictory
5. Always match the user's language (English or Hebrew)

CRITICAL RESPONSE REQUIREMENTS:
- "reflection" field: What did you learn from this message?
- "action" field: ask/followup/done
- "message" field: Your message to the user (MANDATORY)
- "collected_info" field: New data gathered (if any)

Example response:
{
    "reflection": "User has dry skin with some T-zone oiliness - combination type",
    "action": "followup",
    "message": "So you get dryness on your cheeks but oil in the T-zone? That's combination skin - pretty common! Do you get breakouts mostly in the oily areas or everywhere?",
    "collected_info": {"skin_profile": {"skin_type": "combination"}}
}

Be warm, professional, and genuinely interested in helping.
"""

    def _detect_language(self, text: str) -> str:
        """Detect if user is speaking Hebrew or English"""
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


    def _clean_message_history(self, raw_messages: List) -> List[Dict]:
        """
        Clean and prepare message history from database for Claude API.
        
        Filters out:
        - Empty content (None, "", whitespace)
        - Invalid roles
        - Duplicate consecutive messages from same role
        
        Returns properly formatted messages for Claude API.
        """
        import logging
        logger = logging.getLogger(__name__)
        
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
            
            # 🔥 CRITICAL: Clean the message history 🔥
            message_history = self._clean_message_history(raw_history)
            
            # Add current message
            message_history.append({
                "role": "user",
                "content": user_input
            })
            
            # DEBUG: Log the cleaned history
            logger.info(f"Sending {len(message_history)} messages to Claude")
            for idx, msg in enumerate(message_history):
                logger.debug(f"[{idx}] role={msg['role']}, content_len={len(str(msg['content']))}")
            
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
            
            # Get recommendation readiness
            readiness = self.recommendation_engine.assess_readiness(context, user_input)
            logger.info(f"Readiness: confidence={readiness.confidence_score}% ({readiness.level.value}), "
                    f"can_recommend={readiness.can_recommend}, "
                    f"critical_missing={len(readiness.critical_missing)}")
            
            # Try to get response from Claude
            try:
                response = await self.client.messages.create(
                    model=self.MODEL,
                    max_tokens=1024,
                    messages=message_history,  # Using cleaned history
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
                response_text = self.recommendation_engine.generate_response(context, user_input)
            
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
    
    async def _get_claude_data_collection(
        self,
        message_history: List[Dict],
        context: ConversationContext,
        readiness: Any
    ) -> InterviewMessage:
        """
        Use Claude to naturally collect data and respond.

        The recommendation engine handles reasoning and follow-ups.
        Claude handles natural conversation and data extraction.
        """

        # Build context-aware prompt
        context_info = {
            "known_facts": readiness.known_facts,
            "critical_missing": readiness.critical_missing,
            "confidence_score": readiness.confidence_score,
            "confidence_level": readiness.level.value,
            "can_recommend": readiness.can_recommend,
            "current_data": {
                "skin_type": context.skin_profile.skin_type,
                "concerns": context.skin_profile.concerns,
                "health_info": {
                    "pregnant": context.health_info.is_pregnant,
                    "nursing": context.health_info.is_nursing,
                    "medications": context.health_info.medications,
                    "allergies": context.health_info.allergies
                },
                "sun_exposure": context.skin_profile.sun_exposure,
                "preferences": {
                    "budget": context.preferences.budget_range,
                    "requirements": context.preferences.requirements
                }
            }
        }
        
        system_prompt = f"""{self.base_system_prompt}

CURRENT SITUATION:
{json.dumps(context_info, indent=2)}

YOUR TASK:
- If the user just provided information, acknowledge it naturally
- Extract any new data they shared
- Ask the next logical question to fill gaps
- Reference what they've already told you
- Be adaptive - if they mention something unexpected, follow up on it

Remember: You're having a conversation, not filling a form.
"""
        
        # Get Claude's response
        response = await self.client.messages.create(
            model=self.MODEL,
            max_tokens=1024,
            messages=message_history,
            tools=[{
                "name": "output",
                "description": "Structured response with all required fields",
                "input_schema": InterviewMessage.model_json_schema(),
            }],
            tool_choice={"name": "output", "type": "tool"},
            system=system_prompt,
        )
        
        # Parse response
        assert response.content[0].type == "tool_use"
        assistant_message = response.content[0].input
        
        # Validation
        if "message" not in assistant_message:
            logger.error(f"Missing 'message' field! Keys: {assistant_message.keys()}")
            assistant_message["message"] = "I understand. Could you tell me more?"
        
        if "collected_info" not in assistant_message:
            assistant_message["collected_info"] = {}
        
        return InterviewMessage.model_validate(assistant_message)
    
    def _update_context_from_response(
        self,
        context: ConversationContext,
        response: InterviewMessage
    ) -> None:
        """Update conversation context based on collected information"""
        if response.collected_info:
            context.update(response.collected_info)
        
        # Smart state progression
        next_state = context.get_next_state()
        if next_state != context.state:
            logger.info(f"State transition: {context.state} -> {next_state}")
            context.state = next_state
    
    async def _save_response(
        self,
        db: AsyncSession,
        user_id: int,
        message: str,
        context: ConversationContext
    ) -> None:
        """Save assistant message and updated context"""
        
        # Save message
        await self.conversation_repo.add_assistant_message(
            db=db,
            user_id=user_id,
            content=message
        )
        
        # Save context
        await self.conversation_repo.save_context(
            db=db,
            user_id=user_id,
            context=context
        )
    
    async def analyze_skin_image(
        self,
        image_url: str,
        user_context: ConversationContext = None
    ) -> dict:
        """
        Analyze skin condition from image using Claude's vision.
        
        This can be used to:
        1. Help determine skin type when user is unsure
        2. Validate user's stated concerns
        3. Catch concerns user didn't mention
        """
        try:
            analysis_prompt = """Analyze this skin image and provide:

1. Skin type assessment (dry/oily/combination/normal)
2. Visible concerns (acne, hyperpigmentation, texture, redness, etc.)
3. Overall condition
4. Recommendations for priority areas

Be professional, encouraging, and specific."""
            
            # Add user context if available
            if user_context:
                context_str = f"""
User mentioned:
- Concerns: {', '.join(user_context.skin_profile.concerns) if user_context.skin_profile.concerns else 'none yet'}
- Self-assessed type: {user_context.skin_profile.skin_type or 'not determined'}

Compare your visual assessment to what they told you. Note any discrepancies.
"""
                analysis_prompt += context_str
            
            response = await self.client.messages.create(
                model=self.MODEL,
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "url",
                                "url": image_url,
                            },
                        },
                        {
                            "type": "text",
                            "text": analysis_prompt
                        }
                    ],
                }],
            )
            
            assert response.content[0].type == "text"
            analysis_text = response.content[0].text
            
            return {
                "success": True,
                "analysis": analysis_text,
                "image_url": image_url
            }
            
        except Exception as e:
            logger.error(f"Error analyzing skin image: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }