from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from app.models.conversation_schemas import ConversationContext
import logging

logger = logging.getLogger(__name__)


class DataGap(Enum):
    """Types of missing data that need follow-up"""
    SKIN_TYPE_AMBIGUOUS = "skin_type_ambiguous"
    CONCERN_PRIORITY_UNCLEAR = "concern_priority_unclear"
    LIFESTYLE_CONTEXT_MISSING = "lifestyle_context_missing"
    SENSITIVITY_RISK = "sensitivity_risk"
    CURRENT_ROUTINE_INCOMPLETE = "current_routine_incomplete"
    BUDGET_UNDEFINED = "budget_undefined"
    USAGE_PREFERENCE_UNCLEAR = "usage_preference_unclear"
    CONFLICTING_INFORMATION = "conflicting_information"


@dataclass
class ReasoningState:
    """Internal reasoning state - not shown to user"""
    known_facts: List[str] = field(default_factory=list)
    missing_critical: List[DataGap] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)
    safety_flags: List[str] = field(default_factory=list)
    priority_concerns: List[str] = field(default_factory=list)
    confidence_level: str = "low"  # low, medium, high
    
    def is_ready_for_recommendation(self) -> bool:
        """Determine if we have enough data to recommend"""
        # Must have high confidence and no critical gaps or safety flags
        return (
            self.confidence_level == "high" and 
            len(self.missing_critical) == 0 and
            len(self.safety_flags) == 0
        )
    
    def get_next_question_priority(self) -> Optional[DataGap]:
        """Get the highest priority data gap to address next"""
        # Safety first
        if self.safety_flags:
            return DataGap.SENSITIVITY_RISK
        
        # Then critical gaps
        if self.missing_critical:
            return self.missing_critical[0]
        
        return None


@dataclass  
class UserSnapshot:
    """Mid-conversation summary of user state"""
    primary_goals: List[str]
    secondary_goals: List[str]
    current_routine: Dict[str, List[str]]
    skin_context: Dict[str, str]
    preferences: Dict[str, str]
    restrictions: List[str]
    key_gaps: List[str]
    
    def to_confirmation_message(self, language: str = "english") -> str:
        """Generate confirmation message for user"""
        if language == "hebrew":
            return self._format_hebrew()
        return self._format_english()
    
    def _format_english(self) -> str:
        msg = "📋 *Let me confirm what I've learned about your skin:*\n\n"
        
        if self.primary_goals:
            msg += "🎯 *Primary goals:*\n"
            for goal in self.primary_goals:
                msg += f"  • {goal}\n"
            msg += "\n"
        
        if self.secondary_goals:
            msg += "🎯 *Also working on:*\n"
            for goal in self.secondary_goals:
                msg += f"  • {goal}\n"
            msg += "\n"
        
        if self.skin_context:
            msg += "👤 *Your skin:*\n"
            for key, value in self.skin_context.items():
                msg += f"  • {key.replace('_', ' ').title()}: {value}\n"
            msg += "\n"
        
        if self.current_routine:
            msg += "🧴 *Current routine:*\n"
            for time, products in self.current_routine.items():
                if products:
                    msg += f"  {time}: {', '.join(products)}\n"
            msg += "\n"
        
        if self.preferences:
            msg += "✨ *Preferences:*\n"
            for key, value in self.preferences.items():
                msg += f"  • {key.replace('_', ' ').title()}: {value}\n"
            msg += "\n"
        
        if self.restrictions:
            msg += "⚠️ *Important restrictions:*\n"
            for restriction in self.restrictions:
                msg += f"  • {restriction}\n"
            msg += "\n"
        
        if self.key_gaps:
            msg += "❓ *Still need to clarify:*\n"
            for gap in self.key_gaps:
                msg += f"  • {gap}\n"
            msg += "\n"
        
        msg += "_Is this accurate? Any corrections before I create your routine?_"
        return msg
    
    def _format_hebrew(self) -> str:
        msg = "📋 *בואי נוודא שהבנתי נכון:*\n\n"
        
        if self.primary_goals:
            msg += "🎯 *מטרות עיקריות:*\n"
            for goal in self.primary_goals:
                msg += f"  • {goal}\n"
            msg += "\n"
        
        if self.secondary_goals:
            msg += "🎯 *גם עובדת על:*\n"
            for goal in self.secondary_goals:
                msg += f"  • {goal}\n"
            msg += "\n"
        
        if self.skin_context:
            msg += "👤 *העור שלך:*\n"
            for key, value in self.skin_context.items():
                msg += f"  • {key}: {value}\n"
            msg += "\n"
        
        if self.current_routine:
            msg += "🧴 *שגרה נוכחית:*\n"
            for time, products in self.current_routine.items():
                if products:
                    msg += f"  {time}: {', '.join(products)}\n"
            msg += "\n"
        
        if self.preferences:
            msg += "✨ *העדפות:*\n"
            for key, value in self.preferences.items():
                msg += f"  • {key}: {value}\n"
            msg += "\n"
        
        if self.restrictions:
            msg += "⚠️ *מגבלות חשובות:*\n"
            for restriction in self.restrictions:
                msg += f"  • {restriction}\n"
            msg += "\n"
        
        if self.key_gaps:
            msg += "❓ *עדיין צריך להבהיר:*\n"
            for gap in self.key_gaps:
                msg += f"  • {gap}\n"
            msg += "\n"
        
        msg += "_האם זה נכון? יש תיקונים לפני שאכין את השגרה?_"
        return msg


class RecommendationEngine:
    """
    Stateful recommendation engine that reasons before responding.
    
    This is NOT a template filler. Every output must be:
    1. Traceable to user inputs
    2. Contextually aware
    3. Safety-validated
    4. Personalized (two users = two different outputs)
    """
    
    def __init__(self):
        # Safety rules - these override everything
        self.contraindications = self._init_contraindications()
        
        # Ingredient knowledge base
        self.ingredients = self._init_ingredient_knowledge()
        
    def _init_contraindications(self) -> Dict:
        """Hard safety rules - never compromise on these"""
        return {
            "pregnancy": {
                "forbidden": [
                    "Retinol", "Retinoids", "Tretinoin", "Adapalene",
                    "Hydroquinone", "High-dose Salicylic Acid (>2%)",
                    "Benzoyl Peroxide (>5%)", "Essential oils (high concentration)"
                ],
                "safe_alternatives": {
                    "Retinol": "Bakuchiol, Peptides",
                    "Hydroquinone": "Vitamin C, Azelaic Acid, Niacinamide",
                    "Salicylic Acid": "Azelaic Acid, Lactic Acid (low %)",
                }
            },
            "nursing": {
                "forbidden": [
                    "Retinol", "Retinoids", "Hydroquinone"
                ],
                "safe_alternatives": {
                    "Retinol": "Bakuchiol, Peptides",
                    "Hydroquinone": "Vitamin C, Azelaic Acid"
                }
            },
            "medications": {
                "Accutane": "Avoid all exfoliants and actives - skin is extremely sensitive",
                "Retinoids": "No additional vitamin A products",
                "Antibiotics": "Avoid additional harsh actives"
            }
        }
    
    def _init_ingredient_knowledge(self) -> Dict:
        """Ingredient solutions mapped to specific concerns"""
        return {
            "hyperpigmentation": {
                "primary": ["Vitamin C", "Niacinamide", "Azelaic Acid", "Alpha Arbutin"],
                "supporting": ["Tranexamic Acid", "Kojic Acid", "Licorice Root"],
                "usage": "Apply in morning or evening, always pair with SPF",
                "timeline": "4-8 weeks for visible improvement",
                "notes": "Consistency is key, results accumulate over time"
            },
            "aging": {
                "primary": ["Retinol", "Peptides", "Vitamin C"],
                "supporting": ["Hyaluronic Acid", "Antioxidants", "Ceramides"],
                "usage": "Retinol: Start 2-3x/week evenings, build to nightly",
                "timeline": "8-12 weeks for visible results",
                "notes": "SPF 50+ non-negotiable with retinol"
            },
            "dryness": {
                "primary": ["Hyaluronic Acid", "Ceramides", "Squalane"],
                "supporting": ["Glycerin", "Fatty acids", "Urea"],
                "usage": "Apply to damp skin, layer with occlusive",
                "timeline": "2-4 weeks",
                "notes": "Hydration vs occlusion - need both"
            },
            "dehydration": {
                "primary": ["Hyaluronic Acid", "Glycerin", "Sodium PCA"],
                "supporting": ["Aloe", "Panthenol"],
                "usage": "Apply on damp skin morning and evening",
                "timeline": "1-2 weeks",
                "notes": "Drink water, humidifier helps"
            },
            "acne": {
                "primary": ["Niacinamide", "Azelaic Acid", "Salicylic Acid"],
                "supporting": ["Zinc", "Tea Tree (low %)", "Sulfur"],
                "usage": "Start slowly, build tolerance",
                "timeline": "6-8 weeks for improvement",
                "notes": "Hormonal acne may need medical support"
            },
            "texture": {
                "primary": ["Gentle AHA", "PHA", "Enzyme exfoliants"],
                "supporting": ["Retinol (low start)"],
                "usage": "2-3x per week, not consecutive days",
                "timeline": "4-6 weeks",
                "notes": "Over-exfoliation makes it worse"
            },
            "rosacea": {
                "primary": ["Azelaic Acid", "Centella Asiatica", "Niacinamide"],
                "supporting": ["Green Tea", "Oatmeal", "Zinc"],
                "usage": "Gentle application, avoid triggers",
                "timeline": "4-8 weeks",
                "notes": "Avoid fragrance, essential oils, alcohol"
            },
            "enlarged_pores": {
                "primary": ["Niacinamide", "Gentle BHA", "Retinol"],
                "supporting": ["Clay masks (occasional)"],
                "usage": "Daily niacinamide, exfoliants 2-3x/week",
                "timeline": "6-8 weeks",
                "notes": "Can't shrink pores, can minimize appearance"
            }
        }
    
    def reason_about_user(self, context: ConversationContext) -> ReasoningState:
        """
        Deep reasoning phase - analyze what we know and what's missing.
        This is the critical thinking engine.
        """
        state = ReasoningState()
        
        # 1. Extract what we definitively know
        state.known_facts = self._extract_known_facts(context)
        
        # 2. Identify critical data gaps
        state.missing_critical = self._identify_critical_gaps(context)
        
        # 3. Check for contradictions
        state.contradictions = self._detect_contradictions(context)
        
        # 4. Safety flags (pregnancy, meds, allergies)
        state.safety_flags = self._check_safety_concerns(context)
        
        # 5. Determine concern priority
        state.priority_concerns = self._rank_concerns(context)
        
        # 6. Assess confidence
        state.confidence_level = self._assess_confidence(state, context)
        
        logger.info(f"Reasoning state: {state}")
        return state
    
    def _extract_known_facts(self, context: ConversationContext) -> List[str]:
        """Extract definitive facts we know about the user"""
        facts = []
        
        if context.skin_profile.skin_type:
            facts.append(f"Skin type: {context.skin_profile.skin_type}")
        
        if context.skin_profile.concerns:
            facts.append(f"Concerns: {', '.join(context.skin_profile.concerns)}")
        
        if context.skin_profile.sun_exposure:
            facts.append(f"Sun exposure: {context.skin_profile.sun_exposure}")
        
        if context.health_info.is_pregnant or context.health_info.is_nursing:
            facts.append("Pregnancy/nursing status affects ingredient safety")
        
        if context.health_info.medications:
            facts.append(f"Medications: {', '.join(context.health_info.medications)}")
        
        if context.health_info.allergies:
            facts.append(f"Allergies: {', '.join(context.health_info.allergies)}")
        
        if context.preferences.budget_range:
            facts.append(f"Budget: {context.preferences.budget_range}")
        
        return facts
    
    def _identify_critical_gaps(self, context: ConversationContext) -> List[DataGap]:
        """Identify missing information that prevents good recommendations"""
        gaps = []
        
        # Skin type ambiguity
        if not context.skin_profile.skin_type or context.skin_profile.skin_type == "not sure":
            # Check if we have enough clues to infer
            if not self._can_infer_skin_type(context):
                gaps.append(DataGap.SKIN_TYPE_AMBIGUOUS)
        
        # No clear priority among concerns
        if len(context.skin_profile.concerns) > 2:
            gaps.append(DataGap.CONCERN_PRIORITY_UNCLEAR)
        
        # Missing lifestyle context
        if not context.skin_profile.sun_exposure:
            gaps.append(DataGap.LIFESTYLE_CONTEXT_MISSING)
        
        # Health safety unclear
        if (context.health_info.is_pregnant is None and 
            context.health_info.is_nursing is None):
            gaps.append(DataGap.SENSITIVITY_RISK)
        
        # Incomplete routine understanding
        if not self._has_routine_context(context):
            gaps.append(DataGap.CURRENT_ROUTINE_INCOMPLETE)
        
        # Budget undefined (impacts recommendations)
        if not context.preferences.budget_range:
            gaps.append(DataGap.BUDGET_UNDEFINED)
        
        return gaps
    
    def _can_infer_skin_type(self, context: ConversationContext) -> bool:
        """Try to infer skin type from concerns and routine"""
        # If they mention dryness + no oil concerns = probably dry
        # If they mention breakouts + shine = probably oily
        # etc. This is heuristic inference
        
        concerns = [c.lower() for c in context.skin_profile.concerns]
        
        if "dryness" in concerns or "dehydration" in concerns:
            if not any(x in concerns for x in ["acne", "oily"]):
                return True  # Can infer dry
        
        if "acne" in concerns:
            # Might be oily, but could also be hormonal on dry skin
            return False  # Can't safely infer
        
        return False
    
    def _has_routine_context(self, context: ConversationContext) -> bool:
        """Check if we understand their current routine enough"""
        # At minimum, need to know morning cleanser and SPF status
        has_morning_info = (
            context.routine.morning_cleanser is not None or
            context.routine.morning_sunscreen is not None
        )
        return has_morning_info
    
    def _detect_contradictions(self, context: ConversationContext) -> List[str]:
        """Find contradictory information that needs clarification"""
        contradictions = []
        
        # Example: Says skin is dry but uses foaming cleanser twice daily
        if context.skin_profile.skin_type == "dry":
            if context.routine.morning_cleanser and "foaming" in context.routine.morning_cleanser.lower():
                contradictions.append(
                    "Mentioned dry skin but using foaming cleanser (can be stripping)"
                )
        
        # Says concerned about aging but no SPF
        if "aging" in [c.lower() for c in context.skin_profile.concerns]:
            if not context.routine.morning_sunscreen:
                contradictions.append(
                    "Anti-aging goal but no SPF mentioned (SPF is #1 anti-aging step)"
                )
        
        return contradictions
    
    def _check_safety_concerns(self, context: ConversationContext) -> List[str]:
        """Flag any safety issues that need attention"""
        flags = []
        
        if context.health_info.is_pregnant or context.health_info.is_nursing:
            flags.append("Pregnancy/nursing: Must avoid certain ingredients")
        
        if context.health_info.medications:
            for med in context.health_info.medications:
                if any(x in med.lower() for x in ["accutane", "isotretinoin", "tretinoin"]):
                    flags.append(f"Medication alert: {med} - extreme sensitivity risk")
        
        if context.health_info.allergies:
            flags.append(f"Allergies documented: {', '.join(context.health_info.allergies)}")
        
        return flags
    
    def _rank_concerns(self, context: ConversationContext) -> List[str]:
        """Prioritize concerns based on safety and user goals"""
        concerns = context.skin_profile.concerns.copy()
        
        # Safety-critical concerns first
        priority_order = ["rosacea", "acne", "sensitivity"]
        
        prioritized = []
        for priority in priority_order:
            for concern in concerns:
                if priority in concern.lower():
                    prioritized.append(concern)
                    concerns.remove(concern)
                    break
        
        # Then add remaining in order mentioned
        prioritized.extend(concerns)
        
        return prioritized
    
    def _assess_confidence(self, state: ReasoningState, context: ConversationContext) -> str:
        """Determine confidence level for making recommendations"""
        
        # Can't be high confidence with critical gaps or safety flags unresolved
        if state.missing_critical or state.safety_flags:
            return "low"
        
        # Medium if we have basics but some minor gaps
        if state.contradictions:
            return "medium"
        
        # High if we have solid data across all dimensions
        has_skin_type = context.skin_profile.skin_type is not None
        has_concerns = len(context.skin_profile.concerns) > 0
        has_health_info = (
            context.health_info.is_pregnant is not None or
            context.health_info.is_nursing is not None
        )
        has_sun_exposure = context.skin_profile.sun_exposure is not None
        
        if all([has_skin_type, has_concerns, has_health_info, has_sun_exposure]):
            return "high"
        
        return "medium"
    
    def generate_next_question(
        self, 
        context: ConversationContext,
        state: ReasoningState
    ) -> str:
        """
        Generate targeted follow-up question based on reasoning.
        This is adaptive, not scripted.
        """
        language = context.language
        
        # Get highest priority gap
        next_gap = state.get_next_question_priority()
        
        if not next_gap:
            # No gaps - ready for summary confirmation
            return self._generate_summary_confirmation(context)
        
        # Generate question for specific gap
        if next_gap == DataGap.SKIN_TYPE_AMBIGUOUS:
            return self._ask_skin_type_followup(context, language)
        
        elif next_gap == DataGap.CONCERN_PRIORITY_UNCLEAR:
            return self._ask_priority_followup(context, language)
        
        elif next_gap == DataGap.LIFESTYLE_CONTEXT_MISSING:
            return self._ask_lifestyle_followup(context, language)
        
        elif next_gap == DataGap.SENSITIVITY_RISK:
            return self._ask_health_safety(context, language)
        
        elif next_gap == DataGap.CURRENT_ROUTINE_INCOMPLETE:
            return self._ask_routine_followup(context, language)
        
        elif next_gap == DataGap.BUDGET_UNDEFINED:
            return self._ask_budget(context, language)
        
        # Fallback
        return self._generic_followup(language)
    
    def _ask_skin_type_followup(self, context: ConversationContext, language: str) -> str:
        """Contextual question about skin type"""
        concerns = context.skin_profile.concerns
        
        if language == "hebrew":
            if "dryness" in [c.lower() for c in concerns]:
                return (
                    "ציינת יובש - האם העור שלך מרגיש מתוח וקשקש, "
                    "או שזה יותר תחושת חוסר לחות?"
                )
            elif "acne" in [c.lower() for c in concerns]:
                return (
                    "לגבי הפצעונים - האם העור שלך נוטה להיות מבריק במהלך היום, "
                    "או שהפצעונים מופיעים בעור יבש?"
                )
            return "איך היית מתארת את סוג העור שלך - יבש, שמן, או מעורב?"
        
        else:  # English
            if "dryness" in [c.lower() for c in concerns]:
                return (
                    "You mentioned dryness - does your skin feel tight and flaky, "
                    "or is it more of a dehydrated feeling?"
                )
            elif "acne" in [c.lower() for c in concerns]:
                return (
                    "For the breakouts you're experiencing - does your skin tend to get "
                    "shiny during the day, or do you get acne on dry skin?"
                )
            return "How would you describe your skin type - dry, oily, or combination?"
    
    def _ask_priority_followup(self, context: ConversationContext, language: str) -> str:
        """Ask user to prioritize concerns"""
        concerns = context.skin_profile.concerns
        
        if language == "hebrew":
            concerns_list = "\n".join([f"  • {c}" for c in concerns])
            return (
                f"ציינת כמה בעיות:\n{concerns_list}\n\n"
                f"מה הכי מפריע לך? במה נתמקד בשגרה?"
            )
        else:
            concerns_list = "\n".join([f"  • {c}" for c in concerns])
            return (
                f"You mentioned several concerns:\n{concerns_list}\n\n"
                f"Which bothers you most? What should we prioritize in your routine?"
            )
    
    def _ask_lifestyle_followup(self, context: ConversationContext, language: str) -> str:
        """Ask about sun exposure and lifestyle"""
        if language == "hebrew":
            return (
                "כמה זמן את נמצאת בשמש במהלך היום? "
                "זה חשוב לקביעת ההגנה מהשמש שתצטרכי."
            )
        else:
            return (
                "How much time do you spend in the sun during a typical day? "
                "This helps me recommend the right sun protection."
            )
    
    def _ask_health_safety(self, context: ConversationContext, language: str) -> str:
        """Ask critical health safety questions"""
        if language == "hebrew":
            return (
                "שאלת בטיחות חשובה: "
                "האם את בהריון, מניקה, או מתכננת הריון בקרוב? "
                "זה משפיע על המרכיבים שבטוחים עבורך."
            )
        else:
            return (
                "Important safety question: "
                "Are you currently pregnant, nursing, or planning pregnancy soon? "
                "This affects which ingredients are safe for you."
            )
    
    def _ask_routine_followup(self, context: ConversationContext, language: str) -> str:
        """Ask about current routine gaps"""
        if language == "hebrew":
            if not context.routine.morning_sunscreen:
                return "האם את משתמשת בהגנה מהשמש בבוקר?"
            return "ספרי לי על שגרת הבוקר שלך - במה את משתמשת?"
        else:
            if not context.routine.morning_sunscreen:
                return "Do you currently use sunscreen in the morning?"
            return "Tell me about your morning routine - what products do you use?"
    
    def _ask_budget(self, context: ConversationContext, language: str) -> str:
        """Ask about budget preferences"""
        if language == "hebrew":
            return (
                "מה תקציב הטיפוח שלך? "
                "זה עוזר לי להמליץ על מוצרים שמתאימים לך:\n"
                "  • חסכוני\n"
                "  • בינוני\n"
                "  • פרימיום"
            )
        else:
            return (
                "What's your skincare budget? "
                "This helps me recommend products that work for you:\n"
                "  • Budget-friendly\n"
                "  • Mid-range\n"
                "  • Premium"
            )
    
    def _generic_followup(self, language: str) -> str:
        """Generic follow-up if no specific gap identified"""
        if language == "hebrew":
            return "יש עוד משהו שחשוב לך שאדע לפני שאכין את השגרה?"
        else:
            return "Is there anything else important I should know before creating your routine?"
    
    def _generate_summary_confirmation(self, context: ConversationContext) -> str:
        """Generate mid-conversation summary for user confirmation"""
        snapshot = self._create_user_snapshot(context)
        return snapshot.to_confirmation_message(context.language)
    
    def _create_user_snapshot(self, context: ConversationContext) -> UserSnapshot:
        """Create structured snapshot of user state"""
        
        # Extract primary vs secondary goals
        concerns = context.skin_profile.concerns
        primary = concerns[:1] if concerns else []
        secondary = concerns[1:] if len(concerns) > 1 else []
        
        # Map concerns to goals
        primary_goals = [self._concern_to_goal(c) for c in primary]
        secondary_goals = [self._concern_to_goal(c) for c in secondary]
        
        # Current routine summary
        routine = {
            "Morning": self._summarize_routine_time(context, "morning"),
            "Evening": self._summarize_routine_time(context, "evening")
        }
        
        # Skin context
        skin_context = {}
        if context.skin_profile.skin_type:
            skin_context["skin_type"] = context.skin_profile.skin_type
        if context.skin_profile.sun_exposure:
            skin_context["sun_exposure"] = context.skin_profile.sun_exposure
        
        # Preferences
        preferences = {}
        if context.preferences.budget_range:
            preferences["budget"] = context.preferences.budget_range
        if context.preferences.requirements:
            preferences["requirements"] = ", ".join(context.preferences.requirements)
        
        # Restrictions
        restrictions = []
        if context.health_info.is_pregnant:
            restrictions.append("Pregnancy - avoiding unsafe ingredients")
        if context.health_info.is_nursing:
            restrictions.append("Nursing - avoiding unsafe ingredients")
        if context.health_info.medications:
            restrictions.extend([f"Medication: {m}" for m in context.health_info.medications])
        if context.health_info.allergies:
            restrictions.extend([f"Allergy: {a}" for a in context.health_info.allergies])
        
        # Key gaps still remaining
        state = self.reason_about_user(context)
        key_gaps = [gap.value.replace('_', ' ').title() for gap in state.missing_critical]
        
        return UserSnapshot(
            primary_goals=primary_goals,
            secondary_goals=secondary_goals,
            current_routine=routine,
            skin_context=skin_context,
            preferences=preferences,
            restrictions=restrictions,
            key_gaps=key_gaps
        )
    
    def _concern_to_goal(self, concern: str) -> str:
        """Convert concern to user-friendly goal"""
        mapping = {
            "hyperpigmentation": "Even out dark spots and skin tone",
            "aging": "Reduce fine lines and maintain youthful skin",
            "dryness": "Deep hydration and comfort",
            "dehydration": "Restore moisture balance",
            "acne": "Clear breakouts and prevent new ones",
            "texture": "Smooth and refine skin texture",
            "rosacea": "Calm redness and sensitivity",
            "enlarged_pores": "Minimize pore appearance"
        }
        concern_lower = concern.lower()
        for key, goal in mapping.items():
            if key in concern_lower:
                return goal
        return concern
    
    def _summarize_routine_time(self, context: ConversationContext, time: str) -> List[str]:
        """Summarize routine products for a time of day"""
        products = []
        
        if time == "morning":
            if context.routine.morning_cleanser:
                products.append(f"Cleanser: {context.routine.morning_cleanser}")
            if context.routine.morning_treatments:
                products.extend([f"Treatment: {t}" for t in context.routine.morning_treatments])
            if context.routine.morning_moisturizer:
                products.append(f"Moisturizer: {context.routine.morning_moisturizer}")
            if context.routine.morning_sunscreen:
                products.append(f"SPF: {context.routine.morning_sunscreen}")
        
        elif time == "evening":
            if context.routine.evening_makeup_removal:
                products.append(f"Makeup removal: {context.routine.evening_makeup_removal}")
            if context.routine.evening_cleanser:
                products.append(f"Cleanser: {context.routine.evening_cleanser}")
            if context.routine.evening_treatments:
                products.extend([f"Treatment: {t}" for t in context.routine.evening_treatments])
            if context.routine.evening_moisturizer:
                products.append(f"Moisturizer: {context.routine.evening_moisturizer}")
        
        return products if products else ["None mentioned"]
    
    def generate_recommendations(
        self,
        context: ConversationContext,
        state: ReasoningState
    ) -> str:
        """
        Generate final recommendations with full traceability.
        
        CRITICAL: Every recommendation must explicitly reference user inputs.
        """
        language = context.language
        
        # Safety check
        if not state.is_ready_for_recommendation():
            logger.warning("Attempted to generate recommendations without sufficient data")
            return self.generate_next_question(context, state)
        
        # Build traceable recommendations
        recommendations = self._build_traceable_routine(context, state)
        
        # Format for WhatsApp
        if language == "hebrew":
            return self._format_recommendations_hebrew(recommendations, context)
        else:
            return self._format_recommendations_english(recommendations, context)
    
    def _build_traceable_routine(
        self,
        context: ConversationContext,
        state: ReasoningState
    ) -> Dict:
        """
        Build routine where every step traces back to user input.
        This is the core personalization engine.
        """
        routine = {
            "morning": [],
            "evening": [],
            "notes": [],
            "timeline": []
        }
        
        # Start with foundations - cleanser
        routine["morning"].append(self._recommend_cleanser(context, "morning"))
        routine["evening"].append(self._recommend_cleanser(context, "evening"))
        
        # Address priority concerns with treatments
        for concern in state.priority_concerns[:2]:  # Max 2 concerns to avoid overwhelming
            treatment = self._recommend_treatment(concern, context)
            if treatment:
                # Decide morning vs evening based on ingredient
                if self._is_photosensitive(treatment["ingredients"]):
                    routine["evening"].append(treatment)
                else:
                    routine["morning"].append(treatment)
        
        # Moisturizer
        routine["morning"].append(self._recommend_moisturizer(context, "morning"))
        routine["evening"].append(self._recommend_moisturizer(context, "evening"))
        
        # SPF (morning only)
        routine["morning"].append(self._recommend_spf(context))
        
        # Add usage notes and timeline
        routine["notes"] = self._generate_usage_notes(context, state)
        routine["timeline"] = self._generate_timeline(state.priority_concerns)
        
        return routine
    
    def _recommend_cleanser(self, context: ConversationContext, time: str) -> Dict:
        """Recommend cleanser with explicit reasoning"""
        skin_type = context.skin_profile.skin_type
        
        # Map to recommendation with reasoning
        cleansers = {
            "dry": {
                "type": "Cream or oil-based cleanser",
                "reason": f"Because you mentioned your skin is {skin_type}, this won't strip natural oils",
                "example": "CeraVe Hydrating Cleanser or similar cream cleanser"
            },
            "oily": {
                "type": "Gel or foaming cleanser",
                "reason": f"Since you have {skin_type} skin, this helps control excess oil",
                "example": "La Roche-Posay Effaclar or similar gel cleanser"
            },
            "combination": {
                "type": "Balanced gel cleanser",
                "reason": f"For your {skin_type} skin, this addresses both oily and dry areas",
                "example": "CeraVe Foaming Facial Cleanser or similar balanced formula"
            },
            "normal": {
                "type": "Gentle daily cleanser",
                "reason": f"Your {skin_type} skin needs maintenance without disruption",
                "example": "Cetaphil Gentle Skin Cleanser or similar"
            }
        }
        
        # Get recommendation or default
        rec = cleansers.get(skin_type, cleansers["normal"])
        
        return {
            "step": "Cleanser",
            "product": rec["type"],
            "reason": rec["reason"],
            "example": rec["example"],
            "time": time
        }
    
    def _recommend_treatment(self, concern: str, context: ConversationContext) -> Optional[Dict]:
        """Recommend treatment with safety checks and reasoning"""
        
        # Safety first - check contraindications
        is_safe, alternative = self._check_ingredient_safety(concern, context)
        
        if not is_safe:
            if not alternative:
                return None  # Skip this concern if no safe alternative
            # Use alternative
            ingredient_info = alternative
            safety_note = " (pregnancy-safe alternative)"
        else:
            ingredient_info = self.ingredients.get(concern.lower(), {})
            safety_note = ""
        
        if not ingredient_info:
            return None
        
        primary = ingredient_info.get("primary", [])
        usage = ingredient_info.get("usage", "Apply as directed")
        timeline = ingredient_info.get("timeline", "4-8 weeks")
        
        # Build recommendation with explicit tracing
        return {
            "step": "Treatment",
            "concern": concern,
            "ingredients": primary,
            "reason": f"To address the {concern} you mentioned{safety_note}",
            "usage": usage,
            "timeline": f"Expect results in {timeline}",
            "product": f"Serum or treatment with {' or '.join(primary[:2])}"
        }
    
    def _check_ingredient_safety(
        self,
        concern: str,
        context: ConversationContext
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Check if standard treatment is safe, provide alternative if not.
        Returns: (is_safe, alternative_ingredient_info)
        """
        is_pregnant = context.health_info.is_pregnant
        is_nursing = context.health_info.is_nursing
        medications = context.health_info.medications
        
        # Check pregnancy/nursing
        if is_pregnant or is_nursing:
            concern_lower = concern.lower()
            ingredient_info = self.ingredients.get(concern_lower, {})
            primary_ingredients = ingredient_info.get("primary", [])
            
            # Check if any primary ingredient is contraindicated
            forbidden = self.contraindications["pregnancy"]["forbidden"]
            
            for ingredient in primary_ingredients:
                if any(forbidden_ing.lower() in ingredient.lower() for forbidden_ing in forbidden):
                    # Need alternative
                    alternatives = self.contraindications["pregnancy"]["safe_alternatives"]
                    
                    # Find safe alternative for this concern
                    for forbidden_ing, safe_alt in alternatives.items():
                        if forbidden_ing.lower() in ingredient.lower():
                            # Build alternative ingredient info
                            return False, {
                                "primary": [safe_alt],
                                "usage": "Apply as directed - pregnancy safe",
                                "timeline": ingredient_info.get("timeline", "6-8 weeks"),
                                "notes": f"Alternative to {ingredient} for pregnancy safety"
                            }
            
            return True, None  # Safe
        
        # Check medications
        if medications:
            for med in medications:
                if "accutane" in med.lower() or "isotretinoin" in med.lower():
                    # Extreme sensitivity - avoid all actives
                    return False, None
        
        return True, None
    
    def _is_photosensitive(self, ingredients: List[str]) -> bool:
        """Check if ingredients increase sun sensitivity"""
        photosensitive = ["retinol", "aha", "bha", "vitamin c"]
        
        for ingredient in ingredients:
            ing_lower = ingredient.lower()
            if any(ps in ing_lower for ps in photosensitive):
                return True
        
        return False
    
    def _recommend_moisturizer(self, context: ConversationContext, time: str) -> Dict:
        """Recommend moisturizer with reasoning"""
        skin_type = context.skin_profile.skin_type
        
        moisturizers = {
            "dry": {
                "morning": "Rich hydrating cream",
                "evening": "Intensive night cream",
                "reason": f"Your {skin_type} skin needs deep hydration and barrier repair"
            },
            "oily": {
                "morning": "Lightweight gel moisturizer",
                "evening": "Oil-free gel moisturizer",
                "reason": f"For {skin_type} skin, this hydrates without adding excess oil"
            },
            "combination": {
                "morning": "Balanced lotion",
                "evening": "Light night cream",
                "reason": f"Balances hydration across your {skin_type} skin zones"
            },
            "normal": {
                "morning": "Light day moisturizer",
                "evening": "Nourishing night moisturizer",
                "reason": f"Maintains your {skin_type} skin's natural balance"
            }
        }
        
        rec = moisturizers.get(skin_type, moisturizers["normal"])
        
        return {
            "step": "Moisturizer",
            "product": rec[time],
            "reason": rec["reason"],
            "time": time
        }
    
    def _recommend_spf(self, context: ConversationContext) -> Dict:
        """Recommend SPF with explicit reasoning"""
        sun_exposure = context.skin_profile.sun_exposure or "moderate"
        skin_type = context.skin_profile.skin_type
        
        spf_levels = {
            "minimal": {
                "spf": "SPF 30+",
                "reapply": "Reapply if going outside",
                "reason": f"Since you're mostly indoors with {sun_exposure} sun exposure"
            },
            "moderate": {
                "spf": "SPF 50",
                "reapply": "Reapply every 4 hours outdoors",
                "reason": f"With your {sun_exposure} sun exposure, this protects adequately"
            },
            "high": {
                "spf": "SPF 50+ (water-resistant)",
                "reapply": "Reapply every 2 hours",
                "reason": f"Your {sun_exposure} sun exposure requires maximum protection"
            }
        }
        
        rec = spf_levels.get(sun_exposure, spf_levels["moderate"])
        
        # Add texture recommendation based on skin type
        textures = {
            "oily": "gel or fluid texture",
            "dry": "cream texture (adds hydration)",
            "combination": "lightweight lotion",
            "normal": "any comfortable texture"
        }
        texture = textures.get(skin_type, "lotion")
        
        return {
            "step": "Sunscreen",
            "product": f"{rec['spf']} - {texture}",
            "reason": rec["reason"],
            "usage": rec["reapply"],
            "note": "Non-negotiable step - protects against all concerns"
        }
    
    def _generate_usage_notes(
        self,
        context: ConversationContext,
        state: ReasoningState
    ) -> List[str]:
        """Generate personalized usage notes"""
        notes = []
        
        # Introduction pace
        notes.append(
            "Introduce one new product every 1-2 weeks to identify any reactions"
        )
        
        # Patch testing
        notes.append(
            "Always patch test new products on your inner forearm for 24 hours"
        )
        
        # Start slowly
        if any("retinol" in str(state).lower() for state in state.known_facts):
            notes.append(
                "Start active treatments 2-3x per week, gradually increase to nightly as tolerated"
            )
        
        # Pregnancy notes
        if context.health_info.is_pregnant or context.health_info.is_nursing:
            notes.append(
                "⚠️ All recommendations are pregnancy/nursing safe. "
                "We've avoided retinoids, hydroquinone, and high-concentration acids"
            )
        
        # Medication notes
        if context.health_info.medications:
            notes.append(
                "💊 You mentioned medications - please consult your doctor "
                "before starting new skincare actives"
            )
        
        # Allergy notes
        if context.health_info.allergies:
            allergies_str = ", ".join(context.health_info.allergies)
            notes.append(
                f"🚨 Check ingredient lists carefully to avoid your documented allergies: {allergies_str}"
            )
        
        return notes
    
    def _generate_timeline(self, priority_concerns: List[str]) -> List[str]:
        """Generate realistic timeline expectations"""
        timelines = []
        
        for concern in priority_concerns[:2]:
            concern_lower = concern.lower()
            ingredient_info = self.ingredients.get(concern_lower, {})
            timeline = ingredient_info.get("timeline", "4-8 weeks")
            
            timelines.append(f"{concern}: Expect visible results in {timeline}")
        
        timelines.append("Consistency is key - give your routine 4-6 weeks minimum")
        
        return timelines
    
    def _format_recommendations_english(
        self,
        recommendations: Dict,
        context: ConversationContext
    ) -> str:
        """Format final recommendations in English - WhatsApp friendly"""
        msg = "🌟 *Your Personalized Skincare Routine* 🌟\n\n"
        msg += "_Based on everything you've shared with me:_\n\n"
        
        # Morning routine
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "☀️ *MORNING ROUTINE*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, step in enumerate(recommendations["morning"], 1):
            msg += f"{i}️⃣ *{step['step']}*\n"
            msg += f"   {step['product']}\n"
            msg += f"   _{step['reason']}_\n"
            if step.get('usage'):
                msg += f"   📋 {step['usage']}\n"
            if step.get('note'):
                msg += f"   💡 {step['note']}\n"
            msg += "\n"
        
        # Evening routine
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "🌙 *EVENING ROUTINE*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, step in enumerate(recommendations["evening"], 1):
            msg += f"{i}️⃣ *{step['step']}*\n"
            msg += f"   {step['product']}\n"
            msg += f"   _{step['reason']}_\n"
            if step.get('usage'):
                msg += f"   📋 {step['usage']}\n"
            if step.get('timeline'):
                msg += f"   ⏰ {step['timeline']}\n"
            msg += "\n"
        
        # Important notes
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "⚠️ *IMPORTANT NOTES*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, note in enumerate(recommendations["notes"], 1):
            msg += f"{i}️⃣ {note}\n\n"
        
        # Timeline
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "📅 *TIMELINE & EXPECTATIONS*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for timeline in recommendations["timeline"]:
            msg += f"• {timeline}\n"
        
        msg += "\n━━━━━━━━━━━━━━━━━━━━\n"
        msg += "💬 Questions? Want to adjust anything? Just ask!\n"
        msg += "📸 Track progress with weekly photos in same lighting\n\n"
        msg += "_Good luck with your skincare journey!_ 🌸"
        
        return msg
    
    def _format_recommendations_hebrew(
        self,
        recommendations: Dict,
        context: ConversationContext
    ) -> str:
        """Format final recommendations in Hebrew - WhatsApp friendly"""
        msg = "🌟 *שגרת הטיפוח האישית שלך* 🌟\n\n"
        msg += "_על בסיס כל מה ששיתפת איתי:_\n\n"
        
        # Morning routine
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "☀️ *שגרת בוקר*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, step in enumerate(recommendations["morning"], 1):
            msg += f"{i}️⃣ *{self._translate_step(step['step'])}*\n"
            msg += f"   {step['product']}\n"
            msg += f"   _{step['reason']}_\n"
            if step.get('usage'):
                msg += f"   📋 {step['usage']}\n"
            if step.get('note'):
                msg += f"   💡 {step['note']}\n"
            msg += "\n"
        
        # Evening routine
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "🌙 *שגרת ערב*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, step in enumerate(recommendations["evening"], 1):
            msg += f"{i}️⃣ *{self._translate_step(step['step'])}*\n"
            msg += f"   {step['product']}\n"
            msg += f"   _{step['reason']}_\n"
            if step.get('usage'):
                msg += f"   📋 {step['usage']}\n"
            if step.get('timeline'):
                msg += f"   ⏰ {step['timeline']}\n"
            msg += "\n"
        
        # Important notes
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "⚠️ *הערות חשובות*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, note in enumerate(recommendations["notes"], 1):
            msg += f"{i}️⃣ {note}\n\n"
        
        # Timeline
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "📅 *ציר זמן וציפיות*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for timeline in recommendations["timeline"]:
            msg += f"• {timeline}\n"
        
        msg += "\n━━━━━━━━━━━━━━━━━━━━\n"
        msg += "💬 שאלות? רוצה לשנות משהו? רק תגידי!\n"
        msg += "📸 עקבי אחרי ההתקדמות עם תמונות שבועיות באותה תאורה\n\n"
        msg += "_בהצלחה במסע הטיפוח!_ 🌸"
        
        return msg
    
    def _translate_step(self, step: str) -> str:
        """Translate step name to Hebrew"""
        translations = {
            "Cleanser": "ניקוי",
            "Treatment": "טיפול",
            "Moisturizer": "לחות",
            "Sunscreen": "הגנה מהשמש"
        }
        return translations.get(step, step)