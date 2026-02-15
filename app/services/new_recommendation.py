"""
Credible Progressive Recommendation Engine

PHILOSOPHY:
- Bot is a SKINCARE EXPERT, not a generic template generator
- Won't give recommendations without sufficient data (maintains credibility)
- BUT will honor explicit user requests with transparency
- Progressive quality: GROWING (40%+) → REFINED (60%+) → COMPLETE (80%+)

CONFIDENCE THRESHOLDS:
- Below 40%: "I need more information" - Ask questions, don't guess
- 40-59% (GROWING): Good recommendations with documented assumptions
- 60-79% (REFINED): High-quality personalized recommendations  
- 80%+ (COMPLETE): Expert-level comprehensive routine

SAFE RULE:
- If bot says "I'll create recommendations" → Must deliver in THAT message
- Never promise without delivering
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from app.models.conversation_schemas import ConversationContext
import logging

logger = logging.getLogger(__name__)


class ConfidenceLevel(Enum):
    """Credible confidence levels - no fake expertise"""
    INSUFFICIENT = "insufficient"  # <40%: Need more data
    GROWING = "growing"            # 40-59%: Good with assumptions
    REFINED = "refined"            # 60-79%: High quality
    COMPLETE = "complete"          # 80%+: Expert comprehensive


@dataclass
class RecommendationReadiness:
    """
    Assessment of whether we can responsibly give recommendations.
    Maintains expert credibility.
    """
    confidence_score: int  # 0-100
    level: ConfidenceLevel
    
    can_recommend: bool
    reason: str
    
    # What we have
    known_facts: List[str]
    
    # What's missing (critical for credibility)
    critical_missing: List[str]
    nice_to_have_missing: List[str]
    
    # Next steps
    next_questions: List[str]
    
    # User override
    user_explicitly_requested: bool = False
    can_override: bool = False  # Can user request override the threshold?


@dataclass
class ProgressiveRecommendation:
    """
    Recommendation that maintains expert credibility.
    Only generated when confidence >= 40% OR user explicitly requests with minimum data.
    """
    level: ConfidenceLevel
    confidence_score: int
    
    # Deliverables
    morning_routine: List[Dict]
    evening_routine: List[Dict]
    key_notes: List[str]
    
    # Transparency (CRITICAL for credibility)
    based_on: List[str]        # What we're certain about
    assumed: List[str]          # What we're inferring
    limitations: List[str]      # What we can't address without more info
    
    # Quality indicators
    quality_level: str          # "Good", "High", "Expert"
    can_improve_with: List[str]
    
    def to_whatsapp_message(self, language: str = "english") -> str:
        """Format as expert consultation message"""
        if language == "hebrew":
            return self._format_hebrew()
        return self._format_english()
    
    def _format_english(self) -> str:
        """Format with expert credibility"""
        msg = f"🌟 *Your Personalized Skincare Routine* 🌟\n"
        msg += f"_{self.quality_level} Recommendations • {self.confidence_score}% Confidence_\n\n"
        
        # Show expertise: What we're basing this on
        if self.based_on:
            msg += "✅ *Based on your profile:*\n"
            for item in self.based_on:
                msg += f"  • {item}\n"
            msg += "\n"
        
        # Be transparent about assumptions
        if self.assumed:
            msg += "📝 *Working assumptions:*\n"
            for assumption in self.assumed:
                msg += f"  • {assumption}\n"
            msg += "\n"
        
        # MORNING ROUTINE
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "☀️ *MORNING ROUTINE*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, step in enumerate(self.morning_routine, 1):
            msg += f"{i}️⃣ *{step['step']}*\n"
            msg += f"   {step['product']}\n"
            if step.get('reason'):
                msg += f"   _{step['reason']}_\n"
            if step.get('usage'):
                msg += f"   💡 {step['usage']}\n"
            msg += "\n"
        
        # EVENING ROUTINE
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "🌙 *EVENING ROUTINE*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, step in enumerate(self.evening_routine, 1):
            msg += f"{i}️⃣ *{step['step']}*\n"
            msg += f"   {step['product']}\n"
            if step.get('reason'):
                msg += f"   _{step['reason']}_\n"
            if step.get('timeline'):
                msg += f"   ⏰ {step['timeline']}\n"
            msg += "\n"
        
        # IMPORTANT NOTES
        if self.key_notes:
            msg += "━━━━━━━━━━━━━━━━━━━━\n"
            msg += "⚠️ *IMPORTANT NOTES*\n"
            msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
            for note in self.key_notes:
                msg += f"  {note}\n\n"
        
        # Limitations (Expert honesty)
        if self.limitations:
            msg += "━━━━━━━━━━━━━━━━━━━━\n"
            msg += "📋 *CURRENT LIMITATIONS*\n"
            msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
            msg += "_To give you more targeted recommendations, I still need:_\n"
            for limitation in self.limitations[:3]:
                msg += f"  • {limitation}\n"
            msg += "\n"
        
        # Improvement path
        if self.can_improve_with:
            msg += "📈 *UPGRADE YOUR ROUTINE*\n"
            msg += "Tell me about:\n"
            for item in self.can_improve_with[:2]:
                msg += f"  • {item}\n"
            msg += "\n"
        
        msg += "💬 Questions or adjustments? Just ask!\n"
        
        return msg
    
    def _format_hebrew(self) -> str:
        """Hebrew format"""
        return self._format_english()  # Placeholder


class CredibleProgressiveEngine:
    """
    Progressive engine that maintains expert credibility.
    
    KEY PRINCIPLES:
    1. Below 40% confidence → Don't recommend, ask questions
    2. 40%+ confidence → Can recommend with transparency
    3. User explicitly requests + minimum data → Override with warnings
    4. Never promise without delivering
    5. Always honest about limitations
    """
    
    def __init__(self):
        # Import existing knowledge base
        from app.recommendation import RecommendationEngine
        base_engine = RecommendationEngine()
        self.contraindications = base_engine.contraindications
        self.ingredients = base_engine.ingredients
    
    def assess_readiness(
        self,
        context: ConversationContext,
        user_message: str = ""
    ) -> RecommendationReadiness:
        """
        Assess if we can responsibly give recommendations.
        This is the credibility gatekeeper.
        """
        # Calculate confidence
        score = self._calculate_confidence_score(context)
        level = self._get_confidence_level(score)
        
        # What do we know?
        known_facts = self._extract_known_facts(context)
        
        # What's missing?
        critical_missing, nice_to_have = self._identify_missing_data(context, level)
        
        # Is user explicitly requesting?
        user_requesting = self._detect_user_request(user_message)
        
        # Can we recommend?
        can_recommend, reason = self._can_recommend(
            score, 
            level, 
            critical_missing,
            user_requesting,
            context
        )
        
        # What questions to ask?
        next_questions = self._generate_next_questions(critical_missing, context)
        
        # Can user override?
        has_absolute_minimum = self._has_absolute_minimum(context)
        can_override = user_requesting and has_absolute_minimum and score >= 30
        
        return RecommendationReadiness(
            confidence_score=score,
            level=level,
            can_recommend=can_recommend,
            reason=reason,
            known_facts=known_facts,
            critical_missing=critical_missing,
            nice_to_have_missing=nice_to_have,
            next_questions=next_questions,
            user_explicitly_requested=user_requesting,
            can_override=can_override
        )
    
    def _calculate_confidence_score(self, context: ConversationContext) -> int:
        """
        Calculate confidence score (0-100).
        More strict than before - focuses on quality data.
        """
        points = 0
        
        # CRITICAL DATA (50 points) - Can't recommend without these
        if context.skin_profile.skin_type:
            points += 20  # Essential for product selection
        
        if len(context.skin_profile.concerns) > 0:
            points += 20  # Need to know what we're treating
        
        if (context.health_info.is_pregnant is not None or 
            context.health_info.is_nursing is not None or
            len(context.health_info.medications) > 0):
            points += 10  # Safety critical
        
        # IMPORTANT DATA (30 points) - Needed for quality
        if context.skin_profile.sun_exposure:
            points += 10  # SPF recommendations
        
        if len(context.skin_profile.concerns) > 1:
            points += 10  # Multiple concerns = better targeting
        
        if context.preferences.budget_range:
            points += 10  # Product tier recommendations
        
        # OPTIMIZATION DATA (20 points) - Nice to have
        if context.routine.morning_sunscreen is not None:
            points += 5
        
        if context.routine.morning_cleanser:
            points += 5
        
        if len(context.health_info.allergies) > 0:
            points += 5
        
        if context.skin_profile.climate:
            points += 5
        
        return min(100, points)
    
    def _get_confidence_level(self, score: int) -> ConfidenceLevel:
        """Map score to level - higher thresholds for credibility"""
        if score >= 80:
            return ConfidenceLevel.COMPLETE
        elif score >= 60:
            return ConfidenceLevel.REFINED
        elif score >= 40:
            return ConfidenceLevel.GROWING
        else:
            return ConfidenceLevel.INSUFFICIENT
    
    def _can_recommend(
        self,
        score: int,
        level: ConfidenceLevel,
        critical_missing: List[str],
        user_requesting: bool,
        context: ConversationContext
    ) -> Tuple[bool, str]:
        """
        Decide if we can responsibly recommend.
        This maintains expert credibility.
        """
        # THRESHOLD: 40% minimum for recommendations
        if score >= 40:
            if score >= 60:
                return True, "High confidence - comprehensive data available"
            else:
                return True, "Good confidence - can recommend with some assumptions"
        
        # Below 40%: Generally don't recommend
        if score < 40:
            # Check for absolute minimum
            has_minimum = self._has_absolute_minimum(context)
            
            if user_requesting and has_minimum and score >= 30:
                # User insists + we have bare minimum (30-39%)
                return True, "User requested - providing basic recommendations with significant assumptions"
            
            # Not enough data
            missing_str = ", ".join(critical_missing[:2])
            return False, f"Need more information: {missing_str}"
        
        return False, "Insufficient data for quality recommendations"
    
    def _has_absolute_minimum(self, context: ConversationContext) -> bool:
        """
        Check if we have the ABSOLUTE BARE MINIMUM to say anything useful.
        This is the floor - won't recommend without this.
        """
        has_concern_or_goal = (
            len(context.skin_profile.concerns) > 0 or
            context.skin_profile.skin_type is not None
        )
        
        # Safety: If we don't know pregnancy status, assume unsafe
        # (We'll use pregnancy-safe options by default)
        
        return has_concern_or_goal
    
    def _extract_known_facts(self, context: ConversationContext) -> List[str]:
        """What we definitively know"""
        facts = []
        
        if context.skin_profile.skin_type:
            facts.append(f"{context.skin_profile.skin_type.title()} skin type")
        
        if context.skin_profile.concerns:
            concerns = ", ".join(context.skin_profile.concerns[:3])
            if len(context.skin_profile.concerns) > 3:
                concerns += f" (+{len(context.skin_profile.concerns)-3} more)"
            facts.append(f"Concerns: {concerns}")
        
        if context.skin_profile.sun_exposure:
            facts.append(f"{context.skin_profile.sun_exposure.title()} sun exposure")
        
        if context.health_info.is_pregnant:
            facts.append("Pregnant (using pregnancy-safe ingredients)")
        elif context.health_info.is_nursing:
            facts.append("Nursing (using nursing-safe ingredients)")
        
        if context.preferences.budget_range:
            facts.append(f"{context.preferences.budget_range.title()} budget preference")
        
        if context.skin_profile.climate:
            facts.append(f"{context.skin_profile.climate.title()} climate")
        
        return facts
    
    def _identify_missing_data(
        self,
        context: ConversationContext,
        level: ConfidenceLevel
    ) -> Tuple[List[str], List[str]]:
        """
        Identify what's missing.
        Returns: (critical_missing, nice_to_have_missing)
        """
        critical = []
        nice_to_have = []
        
        # CRITICAL for any recommendation
        if not context.skin_profile.skin_type:
            critical.append("skin_type")
        
        if len(context.skin_profile.concerns) == 0:
            critical.append("primary_concerns")
        
        # IMPORTANT for quality (40%+ threshold)
        if not context.skin_profile.sun_exposure:
            if level == ConfidenceLevel.INSUFFICIENT:
                critical.append("sun_exposure")
            else:
                nice_to_have.append("sun_exposure")
        
        if (context.health_info.is_pregnant is None and 
            context.health_info.is_nursing is None and
            len(context.health_info.medications) == 0):
            if level == ConfidenceLevel.INSUFFICIENT:
                critical.append("health_safety")
            else:
                nice_to_have.append("health_safety")
        
        # OPTIMIZATION (60%+ threshold)
        if not context.preferences.budget_range:
            nice_to_have.append("budget_preference")
        
        if not context.routine.morning_cleanser:
            nice_to_have.append("current_routine")
        
        if not context.skin_profile.climate:
            nice_to_have.append("climate")
        
        return critical, nice_to_have
    
    def _generate_next_questions(
        self,
        critical_missing: List[str],
        context: ConversationContext
    ) -> List[str]:
        """Generate smart follow-up questions"""
        questions = []
        
        for item in critical_missing[:2]:  # Top 2 priorities
            if item == "skin_type":
                if context.skin_profile.concerns:
                    # Contextual question based on concerns
                    concern = context.skin_profile.concerns[0].lower()
                    if "acne" in concern:
                        questions.append(
                            "Does your skin tend to get oily/shiny during the day, "
                            "or do you experience breakouts on dry skin?"
                        )
                    else:
                        questions.append("What's your skin type? (dry, oily, combination, or sensitive)")
                else:
                    questions.append("What's your skin type? (dry, oily, combination, or sensitive)")
            
            elif item == "primary_concerns":
                questions.append(
                    "What are your main skin concerns? "
                    "(e.g., acne, aging, dark spots, dryness, sensitivity)"
                )
            
            elif item == "sun_exposure":
                questions.append(
                    "How much time do you typically spend in the sun? "
                    "(minimal, moderate, or high exposure)"
                )
            
            elif item == "health_safety":
                questions.append(
                    "Important safety question: Are you currently pregnant, nursing, "
                    "or taking any medications that affect your skin?"
                )
        
        return questions
    
    def _detect_user_request(self, message: str) -> bool:
        """Detect if user is explicitly requesting recommendations"""
        if not message:
            return False
        
        request_phrases = [
            "recommendation", "routine", "give me", "show me", "create",
            "suggest", "what should i use", "help me choose", "build",
            "generate", "make me", "product recommendations"
        ]
        
        message_lower = message.lower()
        return any(phrase in message_lower for phrase in request_phrases)
    
    def generate_response(
        self,
        context: ConversationContext,
        user_message: str = ""
    ) -> str:
        """
        Main entry point - decides whether to recommend or ask questions.
        
        SAFE RULE: If we say "I'll create recommendations" → Must deliver
        """
        # Assess readiness
        readiness = self.assess_readiness(context, user_message)
        
        logger.info(
            f"Confidence: {readiness.confidence_score}% ({readiness.level.value}), "
            f"Can recommend: {readiness.can_recommend}, "
            f"User requested: {readiness.user_explicitly_requested}"
        )
        
        # Decision tree
        if readiness.can_recommend:
            # DELIVER RECOMMENDATIONS (never just promise)
            recommendation = self._generate_recommendation(context, readiness)
            return recommendation.to_whatsapp_message()
        
        elif readiness.can_override and readiness.user_explicitly_requested:
            # User insists but data is borderline (30-39%)
            # Deliver WITH strong warnings
            recommendation = self._generate_recommendation(context, readiness)
            warning = (
                f"⚠️ *Important Note*\n"
                f"I'm providing recommendations at {readiness.confidence_score}% confidence "
                f"because you requested them. However, I need more information for optimal results.\n\n"
            )
            return warning + recommendation.to_whatsapp_message()
        
        else:
            # DON'T RECOMMEND - Ask for more information
            return self._generate_need_more_info_message(readiness, context)
    
    def _generate_recommendation(
        self,
        context: ConversationContext,
        readiness: RecommendationReadiness
    ) -> ProgressiveRecommendation:
        """
        Generate recommendations at appropriate quality level.
        Only called when confidence >= 40% (or user override at 30%+)
        """
        score = readiness.confidence_score
        level = readiness.level
        
        # Fill essential defaults
        context, assumptions = self._fill_essential_defaults(context, level)
        
        # Generate routine based on level
        if level == ConfidenceLevel.COMPLETE:
            morning, evening, notes, quality = self._generate_complete_routine(context)
        elif level == ConfidenceLevel.REFINED:
            morning, evening, notes, quality = self._generate_refined_routine(context)
        else:  # GROWING or user override
            morning, evening, notes, quality = self._generate_growing_routine(context)
        
        # Identify limitations
        limitations = self._identify_limitations(context, readiness.critical_missing)
        
        # Improvement path
        can_improve = self._get_improvement_suggestions(context, level)
        
        return ProgressiveRecommendation(
            level=level,
            confidence_score=score,
            morning_routine=morning,
            evening_routine=evening,
            key_notes=notes,
            based_on=readiness.known_facts,
            assumed=assumptions,
            limitations=limitations,
            quality_level=quality,
            can_improve_with=can_improve
        )
    
    def _generate_need_more_info_message(
        self,
        readiness: RecommendationReadiness,
        context: ConversationContext
    ) -> str:
        """
        Generate message when we can't recommend yet.
        Expert consultation style - not generic rejection.
        """
        msg = "🔬 *Let me gather more information first* 🔬\n\n"
        
        msg += (
            "To give you quality skincare recommendations that actually work "
            "for YOUR skin, I need a bit more information.\n\n"
        )
        
        # Show what we already know
        if readiness.known_facts:
            msg += "✅ *What I know so far:*\n"
            for fact in readiness.known_facts[:3]:
                msg += f"  • {fact}\n"
            msg += "\n"
        
        # Ask specific questions
        if readiness.next_questions:
            msg += "❓ *Quick questions:*\n\n"
            for i, question in enumerate(readiness.next_questions, 1):
                msg += f"{i}. {question}\n\n"
        else:
            # Generic fallback
            msg += "Tell me about:\n"
            msg += "  • Your skin type (dry, oily, combination, sensitive)\n"
            msg += "  • Your main skin concerns\n\n"
        
        msg += (
            "_Once I have this information, I can create a personalized routine "
            "that's safe and effective for you!_ 💙"
        )
        
        return msg
    
    def _fill_essential_defaults(
        self,
        context: ConversationContext,
        level: ConfidenceLevel
    ) -> Tuple[ConversationContext, List[str]]:
        """
        Fill ONLY essential missing data with reasonable defaults.
        Much more conservative than before.
        """
        assumptions = []
        
        # Skin type - try to infer, otherwise use normal
        if not context.skin_profile.skin_type:
            if self._can_infer_skin_type(context):
                context.skin_profile.skin_type = self._infer_skin_type(context)
                assumptions.append(
                    f"Inferred {context.skin_profile.skin_type} skin type from your concerns - "
                    "let me know if this doesn't match"
                )
            else:
                context.skin_profile.skin_type = "normal"
                assumptions.append(
                    "Working with normal skin type assumption - "
                    "tell me if your skin is dry, oily, or sensitive"
                )
        
        # Sun exposure - default to moderate
        if not context.skin_profile.sun_exposure:
            context.skin_profile.sun_exposure = "moderate"
            assumptions.append(
                "Assumed moderate sun exposure - adjust SPF usage if you're outdoors frequently"
            )
        
        # Health/Safety - use safe defaults
        if (context.health_info.is_pregnant is None and 
            context.health_info.is_nursing is None):
            # Use pregnancy-safe ingredients by default
            assumptions.append(
                "⚠️ Using pregnancy-safe ingredients by default - "
                "let me know if you're planning pregnancy"
            )
        
        # Budget - only fill at REFINED+ level
        if level in [ConfidenceLevel.REFINED, ConfidenceLevel.COMPLETE]:
            if not context.preferences.budget_range:
                context.preferences.budget_range = "moderate"
                assumptions.append(
                    "Recommending moderate-priced options - "
                    "can adjust to budget or premium ranges"
                )
        
        return context, assumptions
    
    def _can_infer_skin_type(self, context: ConversationContext) -> bool:
        """Can we safely infer skin type?"""
        concerns = [c.lower() for c in context.skin_profile.concerns]
        concerns_str = " ".join(concerns)
        
        oily_indicators = ["acne", "breakouts", "pores", "oily", "shiny"]
        dry_indicators = ["dryness", "flaky", "tight", "dehydrated"]
        
        has_oily = any(ind in concerns_str for ind in oily_indicators)
        has_dry = any(ind in concerns_str for ind in dry_indicators)
        
        # Can infer if clear signals
        return has_oily or has_dry
    
    def _infer_skin_type(self, context: ConversationContext) -> str:
        """Infer skin type from concerns"""
        concerns = [c.lower() for c in context.skin_profile.concerns]
        concerns_str = " ".join(concerns)
        
        oily_indicators = ["acne", "breakouts", "pores", "oily", "shiny"]
        dry_indicators = ["dryness", "flaky", "tight", "dehydrated"]
        
        has_oily = any(ind in concerns_str for ind in oily_indicators)
        has_dry = any(ind in concerns_str for ind in dry_indicators)
        
        if has_oily and has_dry:
            return "combination"
        elif has_oily:
            return "oily"
        elif has_dry:
            return "dry"
        
        return "normal"
    
    def _identify_limitations(
        self,
        context: ConversationContext,
        critical_missing: List[str]
    ) -> List[str]:
        """What can't we address without more info?"""
        limitations = []
        
        if "current_routine" in critical_missing or not context.routine.morning_cleanser:
            limitations.append(
                "Your current products - can't advise on what to keep/replace without knowing what you use"
            )
        
        if "budget_preference" in critical_missing or not context.preferences.budget_range:
            limitations.append(
                "Specific product brands - need to know your budget range for targeted recommendations"
            )
        
        if len(context.skin_profile.concerns) == 1:
            limitations.append(
                "Multi-concern optimization - focusing on your primary concern only"
            )
        
        return limitations
    
    def _get_improvement_suggestions(
        self,
        context: ConversationContext,
        level: ConfidenceLevel
    ) -> List[str]:
        """How to improve recommendations"""
        suggestions = []
        
        if not context.routine.morning_cleanser:
            suggestions.append("What products you currently use")
        
        if not context.preferences.budget_range:
            suggestions.append("Your budget range (budget-friendly, moderate, or premium)")
        
        if not context.skin_profile.climate:
            suggestions.append("Your climate (humid, dry, or moderate)")
        
        if len(context.skin_profile.concerns) == 1:
            suggestions.append("Any other skin concerns you want to address")
        
        return suggestions[:3]  # Top 3
    
    # ========================================================================
    # ROUTINE GENERATORS
    # ========================================================================
    
    def _generate_growing_routine(
        self,
        context: ConversationContext
    ) -> Tuple[List[Dict], List[Dict], List[str], str]:
        """
        GROWING level (40-59%): Good recommendations with assumptions.
        Focus on primary concern.
        """
        skin_type = context.skin_profile.skin_type
        primary_concern = context.skin_profile.concerns[0] if context.skin_profile.concerns else None
        
        morning = []
        evening = []
        
        # Morning routine
        morning.append({
            "step": "Cleanser",
            "product": self._get_cleanser(skin_type, primary_concern),
            "reason": f"Gentle cleansing for {skin_type} skin"
        })
        
        # Add morning treatment if applicable
        morning_treatment = self._get_treatment(primary_concern, context, "morning")
        if morning_treatment:
            morning.append(morning_treatment)
        
        morning.extend([
            {
                "step": "Moisturizer",
                "product": self._get_moisturizer(skin_type, "morning"),
                "reason": "Hydration and skin barrier support"
            },
            {
                "step": "Sunscreen",
                "product": f"SPF {self._get_spf_level(context)} broad spectrum",
                "reason": "Essential protection - prevents aging and pigmentation",
                "usage": "Apply daily, reapply every 2 hours if outdoors"
            }
        ])
        
        # Evening routine
        evening.append({
            "step": "Cleanser",
            "product": self._get_cleanser(skin_type, primary_concern),
            "reason": "Remove SPF, makeup, and daily buildup"
        })
        
        # Evening treatment
        evening_treatment = self._get_treatment(primary_concern, context, "evening")
        if evening_treatment:
            evening.append(evening_treatment)
        
        evening.append({
            "step": "Moisturizer",
            "product": self._get_moisturizer(skin_type, "evening"),
            "reason": "Overnight hydration and repair"
        })
        
        notes = [
            "🔄 Introduce new products one at a time, 1-2 weeks apart",
            "🧪 Patch test on inner forearm before full face application",
            "⏰ Give routine 4-6 weeks to show results",
            "📸 Take before photos in consistent lighting to track progress"
        ]
        
        if primary_concern:
            timeline = self._get_concern_timeline(primary_concern)
            notes.append(f"⏳ {primary_concern.title()}: Expect results in {timeline}")
        
        quality = "Good"
        
        return morning, evening, notes, quality
    
    def _generate_refined_routine(
        self,
        context: ConversationContext
    ) -> Tuple[List[Dict], List[Dict], List[str], str]:
        """
        REFINED level (60-79%): High-quality personalized routine.
        Can address multiple concerns with optimization.
        """
        # Build on GROWING but add:
        # - Multiple concern targeting
        # - Budget-specific recommendations
        # - More detailed usage instructions
        
        morning, evening, notes, _ = self._generate_growing_routine(context)
        
        # Enhance with budget-specific examples if available
        if context.preferences.budget_range:
            # Add product examples
            pass
        
        # Multi-concern optimization
        if len(context.skin_profile.concerns) > 1:
            notes.append(
                f"📋 Addressing: {', '.join(context.skin_profile.concerns[:3])}"
            )
        
        quality = "High"
        
        return morning, evening, notes, quality
    
    def _generate_complete_routine(
        self,
        context: ConversationContext
    ) -> Tuple[List[Dict], List[Dict], List[str], str]:
        """
        COMPLETE level (80%+): Expert comprehensive routine.
        Fully optimized for user's unique profile.
        """
        # Build on REFINED but add:
        # - Climate adjustments
        # - Age-appropriate ingredients
        # - Specific brand recommendations
        # - Advanced layering instructions
        
        morning, evening, notes, _ = self._generate_refined_routine(context)
        
        # Climate-specific notes
        if context.skin_profile.climate:
            if context.skin_profile.climate == "humid":
                notes.append("🌡️ Humid climate: Lighter textures recommended")
            elif context.skin_profile.climate == "dry":
                notes.append("🌡️ Dry climate: Extra hydration focus")
        
        quality = "Expert"
        
        return morning, evening, notes, quality
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _get_cleanser(self, skin_type: str, concern: Optional[str] = None) -> str:
        """Get cleanser recommendation"""
        if concern and "acne" in concern.lower():
            return "Salicylic acid cleanser (2%)" if skin_type == "oily" else "Gentle BHA cleanser"
        
        cleansers = {
            "oily": "Gel or foaming cleanser",
            "dry": "Cream or milk cleanser",
            "combination": "Balanced gel cleanser",
            "normal": "Gentle daily cleanser",
            "sensitive": "Ultra-gentle, fragrance-free cleanser"
        }
        return cleansers.get(skin_type, "Gentle cleanser")
    
    def _get_moisturizer(self, skin_type: str, time: str) -> str:
        """Get moisturizer recommendation"""
        if time == "morning":
            moisturizers = {
                "oily": "Lightweight gel moisturizer",
                "dry": "Rich hydrating cream",
                "combination": "Gel-cream hybrid",
                "normal": "Light daily lotion",
                "sensitive": "Gentle, barrier-supporting cream"
            }
        else:  # evening
            moisturizers = {
                "oily": "Gel moisturizer or light cream",
                "dry": "Rich night cream or sleeping mask",
                "combination": "Medium-weight night cream",
                "normal": "Nourishing night moisturizer",
                "sensitive": "Rich, gentle repair cream"
            }
        return moisturizers.get(skin_type, "Moisturizer")
    
    def _get_treatment(
        self,
        concern: Optional[str],
        context: ConversationContext,
        time: str
    ) -> Optional[Dict]:
        """Get treatment for concern"""
        if not concern:
            return None
        
        concern_lower = concern.lower()
        
        # Check safety
        is_safe = self._is_ingredient_safe(concern_lower, context)
        
        if time == "morning":
            # Morning treatments (antioxidants)
            if "pigmentation" in concern_lower or "dark spots" in concern_lower or "dull" in concern_lower:
                return {
                    "step": "Vitamin C Serum",
                    "product": "Vitamin C serum (10-20% L-Ascorbic Acid)",
                    "reason": f"Brightening and antioxidant for {concern}",
                    "usage": "Apply after cleansing, wait 1-2 min before moisturizer",
                    "timeline": "Results in 4-8 weeks"
                }
        else:
            # Evening treatments
            if "acne" in concern_lower or "breakouts" in concern_lower:
                return {
                    "step": "Acne Treatment",
                    "product": "Niacinamide serum (5-10%) or Azelaic Acid (10%)",
                    "reason": f"Reduces inflammation and prevents {concern}",
                    "usage": "Apply nightly after cleansing",
                    "timeline": "Results in 6-8 weeks"
                }
            
            elif "aging" in concern_lower or "wrinkles" in concern_lower or "fine lines" in concern_lower:
                if is_safe:
                    return {
                        "step": "Retinol Treatment",
                        "product": "Retinol serum (start 0.25-0.5%)",
                        "reason": "Gold standard for anti-aging",
                        "usage": "Start 2x per week, build to nightly. Use pea-sized amount.",
                        "timeline": "Results in 8-12 weeks"
                    }
                else:
                    return {
                        "step": "Anti-Aging Treatment",
                        "product": "Bakuchiol serum or Peptide complex",
                        "reason": "Pregnancy-safe alternative for anti-aging",
                        "usage": "Apply nightly",
                        "timeline": "Results in 8-12 weeks"
                    }
        
        return None
    
    def _is_ingredient_safe(self, concern: str, context: ConversationContext) -> bool:
        """Check if standard treatment is safe for this user"""
        if context.health_info.is_pregnant or context.health_info.is_nursing:
            # Avoid retinoids for aging
            if concern in ["aging", "wrinkles"]:
                return False
        return True
    
    def _get_spf_level(self, context: ConversationContext) -> str:
        """Determine appropriate SPF level"""
        sun_exposure = context.skin_profile.sun_exposure or "moderate"
        
        levels = {
            "high": "50+",
            "moderate": "30-50",
            "low": "30"
        }
        return levels.get(sun_exposure, "30-50")
    
    def _get_concern_timeline(self, concern: str) -> str:
        """Expected timeline for concern"""
        timelines = {
            "acne": "6-8 weeks",
            "hyperpigmentation": "4-8 weeks",
            "aging": "8-12 weeks",
            "dryness": "2-4 weeks",
            "texture": "4-6 weeks"
        }
        
        concern_lower = concern.lower()
        for key, timeline in timelines.items():
            if key in concern_lower:
                return timeline
        
        return "4-8 weeks"