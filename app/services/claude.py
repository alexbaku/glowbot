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
from app.services.recommendation import RecommendationEngine
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
        
        # Initialize the reasoning-based recommendation engine
        self.recommendation_engine = RecommendationEngine()
        logger.info("Reasoning-based recommendation engine initialized")
        
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
    
    async def get_response(self, db: AsyncSession, phone_number: str, user_input: str) -> str:
        """
        Main conversation flow with integrated reasoning engine.
        
        Flow:
        1. Load user context from database
        2. Let recommendation engine reason about what we know
        3. If ready for recommendations → generate them
        4. Otherwise → get next targeted question
        5. Save everything to database
        """
        try:
            # Get or create user in database
            user = await self.user_repo.get_or_create(db, phone_number)
            
            # Load conversation context
            context = await self.conversation_repo.load_context(
                db=db,
                user_id=user.id,
                phone_number=phone_number
            )
            
            # Detect language
            language = self._detect_language(user_input)
            context.language = language
            
            # Save user message
            await self.conversation_repo.add_user_message(
                db=db,
                user_id=user.id,
                content=user_input
            )
            
            # Get message history
            message_history = await self.conversation_repo.get_message_history(
                db=db,
                user_id=user.id,
                limit=50
            )
            
            # Add current message
            message_history.append({
                "role": "user",
                "content": user_input
            })
            
            # === REASONING PHASE ===
            # Let the recommendation engine analyze what we know
            reasoning_state = self.recommendation_engine.reason_about_user(context)
            
            logger.info(
                f"Reasoning state: confidence={reasoning_state.confidence_level}, "
                f"missing_critical={len(reasoning_state.missing_critical)}, "
                f"safety_flags={len(reasoning_state.safety_flags)}"
            )
            
            # === DECISION POINT ===
            # Check if user is asking for recommendations
            user_input_lower = user_input.lower()
            wants_recommendations = any(word in user_input_lower for word in [
                'recommend', 'routine', 'products', 'suggest', 'go ahead', 
                'yes', 'sure', 'ok', 'ready', 'המלצ', 'שגרת', 'מוצר', 
                'כן', 'בטח', 'נכון', 'correct'
            ])
            
            # Can we recommend?
            ready_to_recommend = reasoning_state.is_ready_for_recommendation()
            
            if wants_recommendations and ready_to_recommend:
                # === GENERATE RECOMMENDATIONS ===
                logger.info("🎯 User wants recommendations and we have enough data")
                
                recommendations = self.recommendation_engine.generate_recommendations(
                    context=context,
                    state=reasoning_state
                )
                
                # Save and return
                await self._save_response(db, user.id, recommendations, context)
                context.state = ConversationState.COMPLETE
                
                logger.info(f"✅ Recommendations sent to user {phone_number}")
                return recommendations
            
            elif wants_recommendations and not ready_to_recommend:
                # === USER WANTS RECS BUT WE'RE NOT READY ===
                logger.info("User wants recommendations but data insufficient")
                
                # Generate adaptive follow-up
                follow_up = self.recommendation_engine.generate_next_question(
                    context=context,
                    state=reasoning_state
                )
                
                await self._save_response(db, user.id, follow_up, context)
                return follow_up
            
            else:
                # === CONTINUE DATA COLLECTION ===
                # Use Claude to process the response and collect data
                response = await self._get_claude_data_collection(
                    message_history=message_history,
                    context=context,
                    reasoning_state=reasoning_state
                )
                
                # Update context with collected info
                if response.collected_info:
                    context.update(response.collected_info)
                
                # Progress state
                self._update_context_from_response(context, response)
                
                # Save to database
                await self._save_response(db, user.id, response.message, context)
                
                logger.info(
                    f"User: {phone_number} | State: {context.state} | "
                    f"Action: {response.action} | Confidence: {reasoning_state.confidence_level}"
                )
                
                return response.message
        
        except Exception as e:
            logger.error(f"Error in get_response: {str(e)}", exc_info=True)
            
            # Graceful error in user's language
            language = self._detect_language(user_input)
            if language == "hebrew":
                return "סליחה, נתקלתי בבעיה. אפשר לנסות שוב?"
            return "I apologize, I encountered an issue. Could you try again?"
    
    async def _get_claude_data_collection(
        self,
        message_history: List[Dict],
        context: ConversationContext,
        reasoning_state: Any
    ) -> InterviewMessage:
        """
        Use Claude to naturally collect data and respond.
        
        The recommendation engine handles reasoning and follow-ups.
        Claude handles natural conversation and data extraction.
        """
        
        # Build context-aware prompt
        context_info = {
            "known_facts": reasoning_state.known_facts,
            "missing_critical": [gap.value for gap in reasoning_state.missing_critical],
            "confidence": reasoning_state.confidence_level,
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