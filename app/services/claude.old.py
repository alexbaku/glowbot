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
    """ Enhanced service that integrates reasoning-based recommendations.
    
    Key changes:
    1. Uses recommendation engine for reasoning and follow-ups
    2. Less prescriptive prompts - lets Claude be more natural
    3. Focuses on data collection quality over rigid state flow"""

    def __init__(self, settings: Settings):
        self.client = AsyncAnthropic(api_key=settings.claude_api_key)
        self.conversation_repo = get_conversation_repository()
        self.user_repo = get_user_repository()
        self.MODEL = "claude-sonnet-4-5-20250929"
        self.base_system_prompt = """You are Glowbot, a smart skincare assistant who helps users create personalized skincare routines. 
            Interview users naturally, asking one question at a time while maintaining a friendly, conversational tone. 
            Focus on gathering essential information: age, skin type, current concerns, health considerations (pregnancy, medications, allergies), and current skincare routine.
            CRITICAL RESPONSE REQUIREMENTS:
            - You MUST ALWAYS provide ALL required fields in your response
            - The "message" field is MANDATORY - this is what the user will see
            - The "reflection" field is MANDATORY - summarize what you learned
            - The "action" field is MANDATORY - specify next action (ask/followup/done)
            - The "collected_info" field should contain any new data you gathered
            CORRECT RESPONSE FORMAT EXAMPLES:

            Example 1:
            {
            "reflection": "User has dry skin",
            "action": "ask",
            "message": "Thanks! What are your main skin concerns?",
            "collected_info": {"skin_profile": {"skin_type": "dry"}}
            }

            Example 2:
            {
            "reflection": "User confirmed no pregnancy",
            "action": "ask",
            "message": "Great! Tell me about your current routine.",
            "collected_info": {"health_info": {"is_pregnant": false}}
            }

            NEVER omit the "message" field - that's what the user sees!
            Be concise in your responses, remembering this is a chat conversation. 
            Progress through information gathering logically - start with basic skin information, then health safety checks, current routine assessment, and finally provide personalized recommendations. 
            Don't move to recommendations until you have all necessary information. If users mention severe skin conditions, always recommend consulting a dermatologist.

            When making recommendations, structure them into morning and evening routines with clear usage instructions. 
            Include basic safety information like patch testing and potential product interactions. 
            Keep responses brief but informative, and don't hesitate to ask clarifying questions when needed to ensure proper recommendations.
            Always match the user's language exactly and do not switch languages unless the user does.
            """
        self.recommendation_engine = RecommendationEngine()
        logger.info("Recommendation engine initialized")    

    def _detect_language(self, text: str) -> str:
        # Hebrew Unicode range
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
            
            # Check if conversation is complete - generate recommendations
            if context.state == ConversationState.COMPLETE:
                logger.info(f"Conversation complete for {phone_number}, generating recommendations")

                # Generate recommendations
                recommendations = await self.get_recommendations(context)
            
                # Save recommendations to database
                await self.conversation_repo.add_assistant_message(
                db=db,
                user_id=user.id,
                content=recommendations
            )
            
                logger.info(f"Recommendations sent to {phone_number}")
                return recommendations

            # Save user message to database
            await self.conversation_repo.add_user_message(
                db=db,
                user_id=user.id,
                content=user_input
            )
            
            # Get message history from database
            message_history = await self.conversation_repo.get_message_history(
                db=db,
                user_id=user.id,
                limit=50
            )
            
            message_history = [
                msg for msg in message_history 
                if msg.get("content") and str(msg.get("content")).strip()
            ]
            logger.info(f"Message history loaded: {len(message_history)} valid messages")

            # Add current message to history
            message_history.append({
                "role": "user",
                "content": user_input
            })
            
            language = self._detect_language(user_input)
            context.language = language

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
            
            # Get response from Claude
            response = await self.client.messages.create(
                model=self.MODEL,
                max_tokens=1024,
                messages=message_history,
                tools=[{
                    "name": "output",
                    "description": "REQUIRED: Provide structured response with ALL fields: reflection, action, message, collected_info",
                    "input_schema": InterviewMessage.model_json_schema(),
                }],
                tool_choice={"name": "output", "type": "tool"},
                system=full_system_prompt,
            )
            
            # Process the structured response
            assert response.content[0].type == "tool_use"
            assistant_message = response.content[0].input
            logger.info(f"Raw Claude response keys: {assistant_message.keys()}")
            if "message" not in assistant_message:
                logger.error(f"Missing 'message' field! Keys: {assistant_message.keys()}")
                assistant_message["message"] = "I understand. Could you tell me more?"
            if "collected_info" not in assistant_message:
                logger.warning("Missing 'collected_info' field - using empty dict")
                assistant_message["collected_info"] = {}

            resp = InterviewMessage.model_validate(assistant_message)
            user_input_lower = user_input.lower()
            wants_recommendations = any(word in user_input_lower for word in [
                'recommend', 'routine', 'products', 'suggest', 'go ahead', 'yes', 'sure', 'ok', 'ready',
                'המלצ', 'שגרת', 'מוצר', 'כן', 'בטח'
            ])

            has_enough_data = (
                context.skin_profile.skin_type is not None or 
                len(context.skin_profile.concerns) > 0
            )

            # Should we generate recommendations?
            should_generate = (
                (resp.action == InterviewAction.DONE and wants_recommendations) or
                (context.state == ConversationState.SUMMARY and wants_recommendations) or
                (wants_recommendations and has_enough_data)
            )

            if should_generate:
                logger.info("🎯 Generating personalized recommendations...")
                try:
                    recommendations = await self.get_recommendations(context)
                    resp.message = recommendations
                    context.state = ConversationState.COMPLETE
                    logger.info("✅ Recommendations sent!")
                except Exception as e:
                    logger.error(f"❌ Failed: {e}", exc_info=True)
                    resp.message = "מצטערת! תגידי לי מה את צריכה?" if context.language == "hebrew" else "What do you need?"

            # Update the conversation context
            self._update_context_from_response(context, resp)
            
            # Save assistant message to database
            await self.conversation_repo.add_assistant_message(
                db=db,
                user_id=user.id,
                content=resp.message
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
                f"State: {context.state} | "
                f"Action: {resp.action}"
            )
            
            return resp.message
        
        except Exception as e:
            logger.error(f"Error getting response: {str(e)}", exc_info=True)
            return "I apologize, but I'm having trouble responding. Could you try again?"

    async def analyze_skin_image(self, image_url: str, user_context: ConversationContext = None) -> dict:
        """Analyze skin condition from image using Claude's vision"""
        try:
            # Build the analysis prompt
            analysis_prompt = """
            Analyze this skin image and provide:
            1. Skin type assessment (dry/oily/combination/normal)
            2. Visible concerns (acne, hyperpigmentation, texture issues, etc.)
            3. Overall skin condition
            4. Recommendations for what to focus on
            
            Be professional, encouraging, and specific. Format your response clearly.
            """
            
            # If we have user context, personalize the analysis
            if user_context:
                analysis_prompt += f"""
                
                Additional context about this user:
                - They mentioned concerns about: {', '.join(user_context.skin_profile.concerns) if user_context.skin_profile.concerns else 'none specified'}
                - Current skin type assessment: {user_context.skin_profile.skin_type or 'not yet determined'}
                """
            
            # Call Claude with image
            response = await self.client.messages.create(
                model=self.MODEL,
                max_tokens=1024,
                messages=[
                    {
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
                    }
                ],
            )
            
            # Extract the analysis
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

    async def get_recommendations(self, context: ConversationContext) -> str:
        """
        Generate skincare recommendations based on user profile
        
        Args:
            context: Complete conversation context with all user data
            
        Returns:
            Formatted recommendation message ready for WhatsApp
        """
        try:
            logger.info(f"Generating recommendations for user {context.user_id}")
            recommendations = self.recommendation_engine.generate_routine(context) 
            MAX_LENGTH = 1500 

            if len(recommendations) > MAX_LENGTH:
                logger.warning(f"Recommendations too long ({len(recommendations)} chars), truncating...")
                # Truncate and add continuation message
                recommendations = recommendations[:MAX_LENGTH] + "\n\n... (המשך בהודעה הבאה / continued in next message)" # ← Uses correct variable
            logger.info(f"Recommendations generated successfully")
            return recommendations
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}", exc_info=True)
            # Return error message in user's language
            if context.language == "he":
                return "מצטערת, נתקלתי בבעיה ביצירת ההמלצות. אנא נסי שוב."
            return "Sorry, I encountered an issue generating your recommendations. Please try again."
