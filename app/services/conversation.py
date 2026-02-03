import logging
import json
from typing import Dict, Tuple, Optional, List, Any
from app.models.conversation import ConversationState, ConversationContext
from app.services.claude import ClaudeService

logger = logging.getLogger(__name__)

class ConversationService:
    """Service for managing skincare consultation conversations"""
    
    def __init__(self, claude_service: ClaudeService):
        self.claude_service = claude_service
        # In-memory storage until database is implemented
        self.contexts: Dict[str, ConversationContext] = {}
    
    def get_context(self, user_id: str) -> ConversationContext:
        """Get or create conversation context for a user"""
        if user_id not in self.contexts:
            self.contexts[user_id] = ConversationContext(user_id=user_id)
        return self.contexts[user_id]
    
    def save_context(self, context: ConversationContext) -> None:
        """Save conversation context (in-memory for now)"""
        self.contexts[context.user_id] = context
    
    def detect_language(self, text: str) -> str:
        """Detect language from text (simple implementation)"""
        # Check for Hebrew characters
        if any('\u0590' <= c <= '\u05FF' for c in text):
            return "he"
        return "en"  # Default to English
    
    async def process_message(self, user_id: str, message: str) -> str:
        """Process a user message and get appropriate response"""
        try:
            # Get current context or create new one
            context = self.get_context(user_id)
            
            # Detect language
            detected_language = self.detect_language(message)
            if context.language != detected_language:
                context.language = detected_language
            
            # Process message based on current state
            response, context_updates = await self._process_state_message(
                message, context
            )
            
            # Update context if needed
            if context_updates:
                context.update(context_updates)
            
            # Save updated context
            self.save_context(context)
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            # Return fallback response in the user's language
            return self._get_fallback_response(
                self.detect_language(message)
            )
    
    async def _process_state_message(
        self, message: str, context: ConversationContext
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Process message based on current conversation state"""
        
        # Prepare system prompt for current state
        system_prompt = self._get_state_prompt(context)
        
        # Add context information to the system prompt
        context_info = {
            "state": context.state,
            "language": context.language,
            "health_info": context.health_info.model_dump(),
            "skin_profile": context.skin_profile.model_dump(),
            "routine": context.routine.model_dump(),
            "preferences": context.preferences.model_dump(),
            "missing_info": context.missing_info
        }
        
        context_json = json.dumps(context_info, ensure_ascii=False)
        full_prompt = f"{system_prompt}\n\nCurrent context: {context_json}"
        
        # Get response from Claude
        response = await self.claude_service.get_structured_response(
            message, full_prompt
        )
        
        # Process state transition if needed
        if "next_state" in response and response["next_state"] != context.state:
            context.state = ConversationState(response["next_state"])
        
        return response["message"], response.get("context_updates")
    
    def _get_state_prompt(self, context: ConversationContext) -> str:
        """Get the appropriate prompt for the current state"""
        base_prompt = """You are Glowbot, a skincare consultation assistant. Your goal is to help users create personalized skincare routines."""
        
        state_prompts = {
            ConversationState.INITIAL: """
            You are starting a skincare consultation. Your goal is to:
            1. Warmly welcome the user (use 'שלום!' if they are using Hebrew)
            2. Verify they are 18 or older
            3. Once age is verified, ask about their skin type
            
            IMPORTANT: 
            - Keep responses brief and conversational
            - Ask only ONE question at a time
            - Always respond in the same language as the user (Hebrew or English)
            
            RESPONSE FORMAT:
            {
                "message": "Your message to the user",
                "next_state": "initial" OR "skin_type" (if age verified),
                "context_updates": {
                    "missing_info": ["list of missing info"]
                }
            }
            """,
            
            ConversationState.SKIN_TYPE: """
            Ask about the user's skin type. Your goal is to determine:
            - If their skin is dry, oily, combination, or normal
            - Make this a simple, one-question interaction
            
            IMPORTANT:
            - Keep responses conversational and brief
            - Don't move to next state until you have a clear skin type
            - Always respond in the same language as the user
            
            RESPONSE FORMAT:
            {
                "message": "Your message to the user",
                "next_state": "skin_type" OR "skin_concerns" (if skin type identified),
                "context_updates": {
                    "skin_profile": {"skin_type": "identified skin type"}
                }
            }
            """,
            
            ConversationState.SKIN_CONCERNS: """
            Ask about the user's main skin concerns. Possible options include:
            - Hyperpigmentation (dark spots, melasma)
            - Signs of aging (fine lines, wrinkles)
            - Dryness/Dehydration
            - Acne
            - Uneven texture
            - Milia
            - Rosacea
            - Other concerns

            IMPORTANT:
            - Keep responses conversational and brief
            - Allow multiple concerns
            - Always respond in the same language as the user
            
            RESPONSE FORMAT:
            {
                "message": "Your message to the user",
                "next_state": "skin_concerns" OR "health_check" (if concerns identified),
                "context_updates": {
                    "skin_profile": {"concerns": ["list of identified concerns"]}
                }
            }
            """,
            
            ConversationState.HEALTH_CHECK: """
            Ask critical health questions ONE AT A TIME:
            1. Pregnancy/nursing status
            2. Skin allergies or sensitivities
            3. Current medications that might affect skin
            
            IMPORTANT:
            - Health information is critical for safe recommendations
            - Ask questions one at a time
            - Always respond in the same language as the user
            
            RESPONSE FORMAT:
            {
                "message": "Your message to the user",
                "next_state": "health_check" OR "current_routine" (if all health info collected),
                "context_updates": {
                    "health_info": {"updated health info"}
                }
            }
            """,
            
            ConversationState.CURRENT_ROUTINE: """
            Ask about the user's current skincare routine ONE PART AT A TIME:
            1. Morning routine (cleanser, treatments, moisturizer, sunscreen)
            2. Evening routine (makeup removal, cleanser, treatments, moisturizer)
            
            IMPORTANT:
            - Ask about one product category at a time
            - Keep track of which parts of the routine you've already asked about
            - Always respond in the same language as the user
            
            RESPONSE FORMAT:
            {
                "message": "Your message to the user",
                "next_state": "current_routine" OR "preferences" (if routine fully collected),
                "context_updates": {
                    "routine": {"updated routine info"}
                }
            }
            """,
            
            ConversationState.PREFERENCES: """
            Ask about product preferences ONE AT A TIME:
            1. Budget range (budget-friendly, mid-range, high-end)
            2. Special requirements (vegan, cruelty-free, fragrance-free, etc)
            
            IMPORTANT:
            - Keep responses brief and focused
            - Always respond in the same language as the user
            
            RESPONSE FORMAT:
            {
                "message": "Your message to the user",
                "next_state": "preferences" OR "summary" (if preferences collected),
                "context_updates": {
                    "preferences": {"updated preferences"}
                }
            }
            """,
            
            ConversationState.SUMMARY: """
            Create a summary of all collected information following the KYC Summary Report format.
            Include:
            - Skin profile (type, concerns)
            - Health considerations
            - Current routine gaps
            - Goals based on concerns
            
            IMPORTANT:
            - Format the summary clearly with sections
            - Always present in the same language as the user
            
            RESPONSE FORMAT:
            {
                "message": "Your summary message to the user",
                "next_state": "complete",
                "context_updates": {}
            }
            """
        }
        
        state_prompt = state_prompts.get(context.state, "")
        return f"{base_prompt}\n\n{state_prompt}"
    
    def _get_fallback_response(self, language: str) -> str:
        """Get a fallback response in case of errors"""
        if language == "he":
            return "סליחה, נתקלתי בבעיה. אנא נסה שוב את הודעתך."
        return "I apologize, but I'm having trouble processing your message. Could you please try again?"