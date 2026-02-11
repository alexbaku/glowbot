from typing import Dict, List, Optional
from app.models.conversation_schemas import ConversationContext
import logging

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """Generates personalized skincare recommendations based on SOP"""
    
    def __init__(self):
        self.ingredient_rules = self._init_ingredient_rules()
        self.spf_rules = self._init_spf_rules()
        self.skin_type_products = self._init_skin_type_products()
    
    def _init_ingredient_rules(self) -> Dict:
        """Initialize ingredient rules from SOP"""
        return {
            "hyperpigmentation": {
                "safe": ["Vitamin C", "Niacinamide", "Alpha Arbutin", "Azelaic Acid"],
                "avoid_pregnancy": ["Hydroquinone"],
                "description": "brightening and evening skin tone",
                "usage": "Apply once daily in the morning or evening",
                "note": "Pair with SPF as these ingredients can make skin sun-sensitive"
            },
            "aging": {
                "safe": ["Peptides", "Antioxidants", "Hyaluronic Acid"],
                "avoid_pregnancy": ["Retinol", "Retinoids", "Tretinoin"],
                "description": "reducing fine lines and improving elasticity",
                "usage": "Start with 2-3 times per week, gradually increase to nightly",
                "note": "Retinol users must use SPF 50+ daily"
            },
            "dryness": {
                "safe": ["Hyaluronic Acid", "Ceramides", "Squalane", "Natural oils", "Glycerin"],
                "avoid_pregnancy": [],
                "description": "deep hydration and barrier repair",
                "usage": "Apply twice daily on damp skin for best absorption",
                "note": "Layer with moisturizer to seal in hydration"
            },
            "dehydration": {
                "safe": ["Hyaluronic Acid", "Glycerin", "Sodium PCA"],
                "avoid_pregnancy": [],
                "description": "restoring skin's moisture balance",
                "usage": "Apply on damp skin twice daily",
                "note": "Drink plenty of water for best results"
            },
            "acne": {
                "safe": ["Niacinamide", "Tea Tree Oil", "Azelaic Acid", "Zinc"],
                "avoid_pregnancy": ["Salicylic Acid (high concentration)", "Benzoyl Peroxide (high concentration)"],
                "pregnancy_safe_alternative": "Azelaic Acid or Tea Tree Oil",
                "description": "controlling breakouts and reducing inflammation",
                "usage": "Apply to affected areas or all over as tolerated",
                "note": "Start slowly to avoid irritation"
            },
            "texture": {
                "safe": ["PHA", "Gentle AHA", "Enzyme exfoliants", "Lactic Acid"],
                "avoid_pregnancy": ["Strong AHA/BHA combinations", "High % Glycolic Acid"],
                "description": "smoothing skin texture and refining pores",
                "usage": "2-3 times per week, not on consecutive days",
                "note": "Always follow with SPF in the morning"
            },
            "uneven texture": {
                "safe": ["PHA", "Gentle AHA", "Enzyme exfoliants"],
                "avoid_pregnancy": ["Strong AHA/BHA"],
                "description": "smoothing rough patches and improving skin feel",
                "usage": "2-3 times per week",
                "note": "Avoid over-exfoliating"
            },
            "milia": {
                "safe": ["Gentle chemical exfoliants", "Retinol (low %)", "Salicylic Acid"],
                "avoid_pregnancy": ["Retinol"],
                "description": "gentle exfoliation to prevent buildup",
                "usage": "2-3 times per week",
                "note": "If persistent, see a dermatologist for extraction"
            },
            "rosacea": {
                "safe": ["Azelaic Acid", "Centella Asiatica", "Green Tea", "Niacinamide", "Colloidal Oatmeal"],
                "avoid_pregnancy": [],
                "description": "calming redness and reducing inflammation",
                "usage": "Apply gently twice daily",
                "note": "Avoid hot water, harsh scrubs, and irritating ingredients"
            },
            "enlarged pores": {
                "safe": ["Niacinamide", "Gentle BHA", "Retinol"],
                "avoid_pregnancy": ["Retinol", "High % BHA"],
                "description": "minimizing pore appearance",
                "usage": "Once daily, preferably in the evening",
                "note": "Keep skin clean and avoid heavy comedogenic products"
            }
        }
    
    def _init_spf_rules(self) -> Dict:
        """Initialize SPF recommendations based on sun exposure"""
        return {
            "minimal": {
                "spf": "SPF 30+",
                "reapply": "Reapply if going outside",
                "notes": "Since you're mostly indoors, a daily SPF 30+ is sufficient. Apply in the morning after moisturizer.",
                "texture_guide": True
            },
            "moderate": {
                "spf": "SPF 50",
                "reapply": "Reapply every 4 hours",
                "notes": "With moderate sun exposure, use SPF 50 and set reminders to reapply every 4 hours when outdoors.",
                "texture_guide": True
            },
            "high": {
                "spf": "SPF 50+ (water-resistant)",
                "reapply": "Reapply every 2 hours",
                "notes": "High sun exposure requires SPF 50+ water-resistant formula. Reapply every 2 hours without exception, and consider additional protection like hats and shade.",
                "texture_guide": True
            }
        }
    
    def _init_skin_type_products(self) -> Dict:
        """Initialize product recommendations by skin type"""
        return {
            "cleanser": {
                "dry": {
                    "morning": "Gentle, cream-based cleanser or micellar water",
                    "evening": "Cream or oil-based cleanser",
                    "reason": "Won't strip natural oils from dry skin"
                },
                "oily": {
                    "morning": "Gel or foaming cleanser",
                    "evening": "Foaming or gel cleanser",
                    "reason": "Helps control excess oil without over-drying"
                },
                "combination": {
                    "morning": "Balanced gel cleanser",
                    "evening": "Gentle foaming cleanser",
                    "reason": "Addresses both oily and dry areas without irritation"
                },
                "normal": {
                    "morning": "Gentle daily cleanser",
                    "evening": "Gentle daily cleanser",
                    "reason": "Maintains skin's natural balance"
                }
            },
            "moisturizer": {
                "dry": {
                    "morning": "Rich hydrating cream",
                    "evening": "Intensive night cream",
                    "reason": "Provides deep hydration and barrier repair for dry skin"
                },
                "oily": {
                    "morning": "Lightweight gel moisturizer",
                    "evening": "Oil-free gel moisturizer",
                    "reason": "Hydrates without adding excess oil or clogging pores"
                },
                "combination": {
                    "morning": "Balanced lotion",
                    "evening": "Light night cream",
                    "reason": "Balances hydration across different zones"
                },
                "normal": {
                    "morning": "Light day moisturizer",
                    "evening": "Nourishing night moisturizer",
                    "reason": "Maintains skin's moisture balance"
                }
            },
            "sunscreen_texture": {
                "oily": "gel or fluid texture (non-comedogenic)",
                "dry": "cream or lotion texture (hydrating)",
                "combination": "lightweight lotion or gel-cream",
                "normal": "any comfortable texture"
            }
        }
    
    def generate_routine(self, context: ConversationContext) -> str:
        """
        Main entry point - generates complete routine message
        
        Args:
            context: User's conversation context with all collected data
            
        Returns:
            Formatted routine message ready to send via WhatsApp
        """
        try:
            logger.info(f"Generating routine for user {context.user_id}")
            logger.info(f"Profile: {context.skin_profile.skin_type}, Concerns: {context.skin_profile.concerns}")
            logger.info(f"Pregnant: {context.health_info.is_pregnant}, Nursing: {context.health_info.is_nursing}")
            
            # Check if user has shared their current routine
            # context.routine is likely a list of UserRoutine objects
            has_current_routine = False
            
            if context.routine:
                # Check if it's a list/collection with items
                if isinstance(context.routine, (list, tuple)) and len(context.routine) > 0:
                    has_current_routine = True
                    logger.info(f"User has {len(context.routine)} routine steps")
                # Or if it's a single object with a product
                elif hasattr(context.routine, 'product') and context.routine.product:
                    has_current_routine = True
                    logger.info(f"User has routine step: {context.routine.step}")
                # Or check for any string attributes with content
                elif isinstance(context.routine, str) and len(context.routine) > 0:
                    has_current_routine = True
                    logger.info("User has routine text")
            
            # FALLBACK: Check conversation state - if they've completed the conversation,
            # they've likely shared routine information even if not stored in routine table
            if not has_current_routine and hasattr(context, 'state'):
                state_str = str(context.state)
                # If in SUMMARY or COMPLETE state, they've been through full conversation
                if 'SUMMARY' in state_str or 'COMPLETE' in state_str:
                    has_current_routine = True
                    logger.info(f"User in {state_str} state - assuming routine discussed in conversation")
            
            logger.info(f"Final decision: has_current_routine = {has_current_routine}")
            
            if has_current_routine:
                # User already has a routine - give targeted advice
                logger.info("User has existing routine - generating targeted recommendations")
                return self._generate_targeted_recommendations(context)
            else:
                # User needs a full routine from scratch
                logger.info("User needs full routine - generating complete recommendations")
                return self._generate_full_routine(context)
                
        except Exception as e:
            logger.error(f"Error generating routine: {e}", exc_info=True)
            return self._get_error_message(context.language)
    
    def _generate_targeted_recommendations(self, context: ConversationContext) -> str:
        """
        Generate concise, targeted advice for users with existing routines
        """
        language = context.language
        
        # Start with acknowledgment
        if language in ["he", "hebrew"]:
            msg = "💚 *שגרה מצוינת שיש לך!*\n\n"
            msg += "הנה כמה המלצות ממוקדות:\n\n"
        else:
            msg = "💚 *Great routine you have there!*\n\n"
            msg += "Here are my targeted recommendations:\n\n"
        
        # Analyze their concerns and give 2-3 specific suggestions
        suggestions = self._get_smart_suggestions(context)
        
        for i, suggestion in enumerate(suggestions[:3], 1):
            msg += f"{i}. {suggestion}\n\n"
        
        # Add SPF reminder if relevant
        if context.skin_profile.sun_exposure:
            spf_info = self.spf_rules.get(context.skin_profile.sun_exposure.lower())
            if spf_info and language not in ["he", "hebrew"]:
                msg += f"☀️ *SPF Reminder:* {spf_info['notes']}\n\n"
            elif spf_info:
                msg += f"☀️ *תזכורת הגנה:* SPF 50 חובה! יש למרוח מחדש כל 4 שעות.\n\n"
        
        # Add safety notes if needed
        if context.health_info.is_pregnant:
            if language in ["he", "hebrew"]:
                msg += "🤰 *הריון:* הימנעי מרטינול, חומצות בריכוז גבוה והידרוקינון.\n\n"
            else:
                msg += "🤰 *Pregnancy:* Avoid retinol, high-concentration acids, and hydroquinone.\n\n"
        
        # Closing
        if language in ["he", "hebrew"]:
            msg += "💬 יש שאלות נוספות? אני כאן!"
        else:
            msg += "💬 Have more questions? I'm here to help!"
        
        logger.info(f"Generated targeted recommendations: {len(msg)} characters")
        return msg

    def _get_smart_suggestions(self, context: ConversationContext) -> List[str]:
        """
        Generate smart, specific suggestions based on concerns and existing routine
        """
        suggestions = []
        language = context.language
        
        # Get top concerns
        concerns = [c.lower() for c in context.skin_profile.concerns] if context.skin_profile.concerns else []
        
        # Generate suggestions based on concerns
        for concern in concerns[:3]:  # Top 3 concerns max
            if concern in ['hyperpigmentation', 'dark spots', 'melasma', 'pigmentation']:
                if language in ["he", "hebrew"]:
                    suggestions.append("✨ *להבהרת פיגמנטציה:* הוסיפי ויטמין C בבוקר + ניאצינמייד בערב")
                else:
                    suggestions.append("✨ *For brightening:* Add Vitamin C (AM) + Niacinamide (PM) for best results")
                    
            elif concern in ['aging', 'wrinkles', 'fine lines', 'anti-aging', 'anti aging']:
                if language in ["he", "hebrew"]:
                    suggestions.append("🌙 *נגד קמטים:* רטינול 2-3 פעמים בשבוע בערב (התחילי מאחוז נמוך)")
                else:
                    suggestions.append("🌙 *Anti-aging:* Start retinol 2-3x/week in PM (begin with low concentration)")
                    
            elif concern in ['acne', 'breakouts', 'pimples']:
                if language in ["he", "hebrew"]:
                    suggestions.append("🎯 *לאקנה:* ניאצינמייד + חומצה סליצילית (BHA) 2-3 פעמים בשבוע")
                else:
                    suggestions.append("🎯 *For acne:* Niacinamide + Salicylic acid (BHA) 2-3x/week")
                    
            elif concern in ['dryness', 'dry skin', 'dehydration']:
                if language in ["he", "hebrew"]:
                    suggestions.append("💧 *לחות:* חומצה היאלורונית על עור לח + סרום שמן בערב")
                else:
                    suggestions.append("💧 *Hydration boost:* Hyaluronic acid on damp skin + facial oil at night")
                    
            elif concern in ['texture', 'rough texture', 'bumpy', 'uneven texture']:
                if language in ["he", "hebrew"]:
                    suggestions.append("✨ *לטקסטורה:* פילינג עדין עם AHA/PHA 2-3 פעמים בשבוע")
                else:
                    suggestions.append("✨ *Smooth texture:* Gentle chemical exfoliant (AHA/PHA) 2-3x/week")
                    
            elif concern in ['pores', 'enlarged pores', 'large pores']:
                if language in ["he", "hebrew"]:
                    suggestions.append("🎯 *לנקבוביות:* ניאצינמייד יומי + רטינול בהדרגה")
                else:
                    suggestions.append("🎯 *Minimize pores:* Daily niacinamide + gradual retinol introduction")
        
        # If no specific suggestions, give general advice
        if not suggestions:
            if language in ["he", "hebrew"]:
                suggestions.append("💚 *המשיכי כך!* השגרה שלך נראית טוב. תני לה 4-6 שבועות לעבוד.")
            else:
                suggestions.append("💚 *Keep it up!* Your routine looks solid. Give it 4-6 weeks to show results.")
        
        # Add hydration tip if not already mentioned
        if 'dryness' not in ' '.join(concerns) and len(suggestions) < 3:
            if language in ["he", "hebrew"]:
                suggestions.append("💧 *טיפ נוסף:* שתי הרבה מים והשתמשי במכשיר אדים בחדר השינה")
            else:
                suggestions.append("💧 *Extra tip:* Stay hydrated and consider a bedroom humidifier")
        
        return suggestions
    
    def _generate_full_routine(self, context: ConversationContext) -> str:
        """
        Generate full routine for users without existing routines
        """
        # Build routines
        morning = self._build_morning_routine(context)
        evening = self._build_evening_routine(context)
        instructions = self._get_usage_instructions(context)
        
        # Format for WhatsApp
        message = self._format_message(morning, evening, instructions, context.language)
        
        logger.info(f"Full routine generated successfully for user {context.user_id}")
        return message
    
    def _build_morning_routine(self, context: ConversationContext) -> Dict:
        """Build morning skincare routine"""
        skin_type = context.skin_profile.skin_type or "normal"
        
        routine = {
            "cleanser": self._get_cleanser(skin_type, "morning"),
            "treatment": self._get_treatment(
                concerns=context.skin_profile.concerns,
                is_pregnant=context.health_info.is_pregnant or context.health_info.is_nursing,
                time="morning"
            ),
            "moisturizer": self._get_moisturizer(skin_type, is_night=False),
            "sunscreen": self._get_sunscreen(
                sun_exposure=context.skin_profile.sun_exposure,
                skin_type=skin_type
            )
        }
        return routine
    
    def _build_evening_routine(self, context: ConversationContext) -> Dict:
        """Build evening skincare routine"""
        skin_type = context.skin_profile.skin_type or "normal"
        
        routine = {
            "makeup_removal": self._get_makeup_removal(skin_type),
            "cleanser": self._get_cleanser(skin_type, "evening"),
            "treatment": self._get_treatment(
                concerns=context.skin_profile.concerns,
                is_pregnant=context.health_info.is_pregnant or context.health_info.is_nursing,
                time="evening"
            ),
            "moisturizer": self._get_moisturizer(skin_type, is_night=True)
        }
        return routine
    
    def _get_cleanser(self, skin_type: str, time: str) -> Dict:
        """Select appropriate cleanser"""
        cleanser_data = self.skin_type_products["cleanser"].get(
            skin_type.lower(),
            self.skin_type_products["cleanser"]["normal"]
        )
        
        return {
            "product": cleanser_data[time],
            "reason": cleanser_data["reason"]
        }
    
    def _get_makeup_removal(self, skin_type: str) -> Dict:
        """Select makeup removal method"""
        removal_map = {
            "dry": {
                "product": "Oil-based cleanser or cleansing balm",
                "reason": "Gently removes makeup while nourishing dry skin"
            },
            "oily": {
                "product": "Micellar water or gentle makeup remover",
                "reason": "Effectively removes makeup without adding oil"
            },
            "combination": {
                "product": "Micellar water or cleansing water",
                "reason": "Removes makeup gently without disrupting balance"
            },
            "normal": {
                "product": "Micellar water or cleansing oil",
                "reason": "Thoroughly removes makeup while being gentle"
            }
        }
        
        return removal_map.get(skin_type.lower(), removal_map["normal"])
    
    def _get_treatment(self, concerns: List[str], is_pregnant: bool, time: str) -> Optional[Dict]:
        """Select treatment based on primary concern"""
        if not concerns:
            # Default treatment for general skin health
            return {
                "product": "Niacinamide serum",
                "reason": "Versatile ingredient that improves overall skin health, reduces redness, and strengthens barrier",
                "usage": "Apply 2-4 drops after cleansing, before moisturizer",
                "note": None
            }
        
        # Normalize concern names
        normalized_concerns = [c.lower().strip() for c in concerns]
        
        # Get primary concern (first in list)
        primary_concern = normalized_concerns[0]
        
        # Map similar concerns
        concern_mapping = {
            "hyperpigmentation": "hyperpigmentation",
            "dark spots": "hyperpigmentation",
            "melasma": "hyperpigmentation",
            "aging": "aging",
            "fine lines": "aging",
            "wrinkles": "aging",
            "dryness": "dryness",
            "dehydration": "dehydration",
            "dry": "dryness",
            "acne": "acne",
            "breakouts": "acne",
            "pimples": "acne",
            "texture": "texture",
            "uneven texture": "uneven texture",
            "rough skin": "texture",
            "milia": "milia",
            "rosacea": "rosacea",
            "redness": "rosacea",
            "enlarged pores": "enlarged pores",
            "large pores": "enlarged pores"
        }
        
        # Find matching concern in our rules
        matched_concern = None
        for concern_variant, concern_key in concern_mapping.items():
            if concern_variant in primary_concern:
                matched_concern = concern_key
                break
        
        if not matched_concern:
            # Fallback to Niacinamide
            logger.warning(f"Unrecognized concern: {primary_concern}, using default treatment")
            matched_concern = None
        
        # Get concern data
        if matched_concern:
            concern_data = self.ingredient_rules.get(matched_concern, {})
        else:
            # Default fallback
            return {
                "product": "Niacinamide serum",
                "reason": "Versatile ingredient for overall skin health",
                "usage": "Apply 2-4 drops after cleansing",
                "note": None
            }
        
        safe_ingredients = concern_data.get("safe", ["Niacinamide"])
        avoid_pregnancy = concern_data.get("avoid_pregnancy", [])
        description = concern_data.get("description", "addressing your skin concerns")
        usage = concern_data.get("usage", "Apply as directed")
        note = concern_data.get("note", "")
        
        # Select ingredient based on pregnancy status
        if is_pregnant:
            # Filter out pregnancy-unsafe ingredients
            available = [i for i in safe_ingredients if i not in avoid_pregnancy]
            
            if not available:
                # Use pregnancy safe alternative if specified
                alternative = concern_data.get("pregnancy_safe_alternative", "Niacinamide")
                ingredient = alternative
            else:
                ingredient = available[0]
            
            pregnancy_note = "⚠️ Pregnancy/nursing safe formula"
        else:
            ingredient = safe_ingredients[0]
            pregnancy_note = None
        
        # Adjust for time of day
        if time == "morning" and matched_concern == "aging" and ingredient == "Retinol":
            # Move retinol to evening only
            ingredient = "Antioxidant serum (Vitamin C or E)"
            usage = "Apply in the morning for daytime protection"
        
        return {
            "product": f"{ingredient} serum/treatment",
            "reason": f"Targets {primary_concern} by {description}",
            "usage": usage,
            "note": pregnancy_note,
            "additional_note": note if note else None
        }
    
    def _get_moisturizer(self, skin_type: str, is_night: bool) -> Dict:
        """Select appropriate moisturizer"""
        moisturizer_data = self.skin_type_products["moisturizer"].get(
            skin_type.lower(),
            self.skin_type_products["moisturizer"]["normal"]
        )
        
        time = "evening" if is_night else "morning"
        
        return {
            "product": moisturizer_data[time],
            "reason": moisturizer_data["reason"]
        }
    
    def _get_sunscreen(self, sun_exposure: str, skin_type: str) -> Dict:
        """Select appropriate sunscreen based on sun exposure"""
        exposure = sun_exposure.lower() if sun_exposure else "moderate"
        spf_data = self.spf_rules.get(exposure, self.spf_rules["moderate"])
        
        # Get texture recommendation
        texture = self.skin_type_products["sunscreen_texture"].get(
            skin_type.lower(),
            self.skin_type_products["sunscreen_texture"]["normal"]
        )
        
        return {
            "product": f"{spf_data['spf']} sunscreen - {texture}",
            "reason": "Essential protection against sun damage, premature aging, and skin cancer",
            "usage": spf_data["reapply"],
            "note": spf_data["notes"]
        }
    
    def _get_usage_instructions(self, context: ConversationContext) -> Dict:
        """Get special usage instructions"""
        instructions = {
            "introduction": "Start with one new product at a time, waiting 1-2 weeks before adding the next",
            "patch_test": "Always patch test new products on your inner arm for 24 hours first",
            "frequency": "Start treatments 2-3 times per week, gradually increasing as your skin tolerates",
            "order": "Apply products from thinnest to thickest consistency",
            "consistency": "Give your routine 4-6 weeks to show visible results"
        }
        
        # Add pregnancy note if applicable
        if context.health_info.is_pregnant or context.health_info.is_nursing:
            instructions["pregnancy_note"] = (
                "⚠️ All recommendations are pregnancy/nursing safe. "
                "Avoid retinoids, high-concentration acids, and hydroquinone."
            )
        
        # Add medication warnings if applicable
        if context.health_info.medications:
            instructions["medication_note"] = (
                "⚠️ You mentioned using medications. Please check with your doctor "
                "before starting new skincare products to avoid interactions."
            )
        
        # Add allergy warnings if applicable
        if context.health_info.allergies:
            instructions["allergy_note"] = (
                f"⚠️ You mentioned allergies to: {', '.join(context.health_info.allergies)}. "
                "Always read ingredient lists carefully and avoid these ingredients."
            )
        
        return instructions
    
    def _format_message(self, morning: Dict, evening: Dict, instructions: Dict, language: str = "en") -> str:
        """Format routine into WhatsApp message"""
        if language == "he" or language == "hebrew":
            return self._format_hebrew(morning, evening, instructions)
        return self._format_english(morning, evening, instructions)
    
    def _format_english(self, morning: Dict, evening: Dict, instructions: Dict) -> str:
        """Format message in English"""
        msg = "🌟 *Your Personalized Skincare Routine* 🌟\n\n"
        msg += "Based on your skin profile and concerns, here's your customized routine:\n\n"
        
        # Morning Routine
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "☀️ *MORNING ROUTINE*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        step = 1
        msg += f"{step}️⃣ *Cleanser*\n"
        msg += f"   {morning['cleanser']['product']}\n"
        msg += f"   _{morning['cleanser']['reason']}_\n\n"
        
        if morning['treatment']:
            step += 1
            msg += f"{step}️⃣ *Treatment*\n"
            msg += f"   {morning['treatment']['product']}\n"
            msg += f"   _{morning['treatment']['reason']}_\n"
            msg += f"   📋 {morning['treatment']['usage']}\n"
            if morning['treatment'].get('note'):
                msg += f"   {morning['treatment']['note']}\n"
            if morning['treatment'].get('additional_note'):
                msg += f"   💡 {morning['treatment']['additional_note']}\n"
            msg += "\n"
        
        step += 1
        msg += f"{step}️⃣ *Moisturizer*\n"
        msg += f"   {morning['moisturizer']['product']}\n"
        msg += f"   _{morning['moisturizer']['reason']}_\n\n"
        
        step += 1
        msg += f"{step}️⃣ *Sunscreen* ☀️\n"
        msg += f"   {morning['sunscreen']['product']}\n"
        msg += f"   _{morning['sunscreen']['reason']}_\n"
        msg += f"   🔁 {morning['sunscreen']['usage']}\n"
        msg += f"   💡 {morning['sunscreen']['note']}\n\n"
        
        # Evening Routine
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "🌙 *EVENING ROUTINE*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        step = 1
        if evening.get('makeup_removal'):
            msg += f"{step}️⃣ *Makeup Removal*\n"
            msg += f"   {evening['makeup_removal']['product']}\n"
            msg += f"   _{evening['makeup_removal']['reason']}_\n\n"
            step += 1
        
        msg += f"{step}️⃣ *Cleanser*\n"
        msg += f"   {evening['cleanser']['product']}\n"
        msg += f"   _{evening['cleanser']['reason']}_\n\n"
        
        if evening['treatment']:
            step += 1
            msg += f"{step}️⃣ *Treatment*\n"
            msg += f"   {evening['treatment']['product']}\n"
            msg += f"   _{evening['treatment']['reason']}_\n"
            msg += f"   📋 {evening['treatment']['usage']}\n"
            if evening['treatment'].get('note'):
                msg += f"   {evening['treatment']['note']}\n"
            if evening['treatment'].get('additional_note'):
                msg += f"   💡 {evening['treatment']['additional_note']}\n"
            msg += "\n"
        
        step += 1
        msg += f"{step}️⃣ *Moisturizer*\n"
        msg += f"   {evening['moisturizer']['product']}\n"
        msg += f"   _{evening['moisturizer']['reason']}_\n\n"
        
        # Important Tips
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "⚠️ *IMPORTANT TIPS*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        msg += f"1️⃣ {instructions['introduction']}\n\n"
        msg += f"2️⃣ {instructions['patch_test']}\n\n"
        msg += f"3️⃣ {instructions['frequency']}\n\n"
        msg += f"4️⃣ {instructions['order']}\n\n"
        
        # Special warnings
        if instructions.get('pregnancy_note'):
            msg += f"\n🤰 {instructions['pregnancy_note']}\n"
        
        if instructions.get('medication_note'):
            msg += f"\n💊 {instructions['medication_note']}\n"
        
        if instructions.get('allergy_note'):
            msg += f"\n🚨 {instructions['allergy_note']}\n"
        
        msg += f"\n✨ _{instructions['consistency']}_\n"
        msg += "\n━━━━━━━━━━━━━━━━━━━━\n"
        msg += "💬 *Questions or concerns?* Feel free to ask!\n"
        msg += "📸 *Track your progress* by taking weekly photos in the same lighting.\n\n"
        msg += "_Good luck with your skincare journey!_ 🌸"
        
        return msg
    
    def _format_hebrew(self, morning: Dict, evening: Dict, instructions: Dict) -> str:
        """Format message in Hebrew"""
        msg = "🌟 *שגרת הטיפוח האישית שלך* 🌟\n\n"
        msg += "על בסיס פרופיל העור והצרכים שלך, הנה השגרה המותאמת במיוחד עבורך:\n\n"
        
        # Morning Routine
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "☀️ *שגרת בוקר*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        step = 1
        msg += f"{step}️⃣ *ניקוי*\n"
        msg += f"   {morning['cleanser']['product']}\n"
        msg += f"   _{morning['cleanser']['reason']}_\n\n"
        
        if morning['treatment']:
            step += 1
            msg += f"{step}️⃣ *טיפול*\n"
            msg += f"   {morning['treatment']['product']}\n"
            msg += f"   _{morning['treatment']['reason']}_\n"
            msg += f"   📋 {morning['treatment']['usage']}\n"
            if morning['treatment'].get('note'):
                msg += f"   {morning['treatment']['note']}\n"
            if morning['treatment'].get('additional_note'):
                msg += f"   💡 {morning['treatment']['additional_note']}\n"
            msg += "\n"
        
        step += 1
        msg += f"{step}️⃣ *לחות*\n"
        msg += f"   {morning['moisturizer']['product']}\n"
        msg += f"   _{morning['moisturizer']['reason']}_\n\n"
        
        step += 1
        msg += f"{step}️⃣ *הגנה מהשמש* ☀️\n"
        msg += f"   {morning['sunscreen']['product']}\n"
        msg += f"   _{morning['sunscreen']['reason']}_\n"
        msg += f"   🔁 {morning['sunscreen']['usage']}\n"
        msg += f"   💡 {morning['sunscreen']['note']}\n\n"
        
        # Evening Routine
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "🌙 *שגרת ערב*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        step = 1
        if evening.get('makeup_removal'):
            msg += f"{step}️⃣ *הסרת איפור*\n"
            msg += f"   {evening['makeup_removal']['product']}\n"
            msg += f"   _{evening['makeup_removal']['reason']}_\n\n"
            step += 1
        
        msg += f"{step}️⃣ *ניקוי*\n"
        msg += f"   {evening['cleanser']['product']}\n"
        msg += f"   _{evening['cleanser']['reason']}_\n\n"
        
        if evening['treatment']:
            step += 1
            msg += f"{step}️⃣ *טיפול*\n"
            msg += f"   {evening['treatment']['product']}\n"
            msg += f"   _{evening['treatment']['reason']}_\n"
            msg += f"   📋 {evening['treatment']['usage']}\n"
            if evening['treatment'].get('note'):
                msg += f"   {evening['treatment']['note']}\n"
            if evening['treatment'].get('additional_note'):
                msg += f"   💡 {evening['treatment']['additional_note']}\n"
            msg += "\n"
        
        step += 1
        msg += f"{step}️⃣ *לחות*\n"
        msg += f"   {evening['moisturizer']['product']}\n"
        msg += f"   _{evening['moisturizer']['reason']}_\n\n"
        
        # Important Tips
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "⚠️ *טיפים חשובים*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        msg += "1️⃣ התחילי מוצר אחד בכל פעם, המתיני 1-2 שבועות לפני הוספת המוצר הבא\n\n"
        msg += "2️⃣ תמיד עשי בדיקת רגישות למוצרים חדשים על האמה הפנימית למשך 24 שעות\n\n"
        msg += "3️⃣ התחילי טיפולים 2-3 פעמים בשבוע, והגבירי בהדרגה\n\n"
        msg += "4️⃣ מרחי מוצרים מהדקים לעבים ביותר\n\n"
        
        # Special warnings
        if instructions.get('pregnancy_note'):
            msg += f"\n🤰 כל ההמלצות בטוחות להריון/הנקה. הימנעי מרטינואידים, חומצות בריכוז גבוה והידרוקינון.\n"
        
        if instructions.get('medication_note'):
            msg += f"\n💊 ציינת שימוש בתרופות. אנא התייעצי עם הרופא לפני התחלת מוצרי טיפוח חדשים.\n"
        
        if instructions.get('allergy_note'):
            allergies_he = ', '.join(context.health_info.allergies) if hasattr(context, 'health_info') else ''
            msg += f"\n🚨 ציינת אלרגיות. קראי תמיד את רשימת הרכיבים והימנעי מרכיבים אלה.\n"
        
        msg += f"\n✨ _תני לשגרה 4-6 שבועות להראות תוצאות נראות לעין_\n"
        msg += "\n━━━━━━━━━━━━━━━━━━━━\n"
        msg += "💬 *שאלות או חששות?* אל תהססי לשאול!\n"
        msg += "📸 *עקבי אחרי ההתקדמות* על ידי צילום שבועי באותו תאורה.\n\n"
        msg += "_בהצלחה במסע הטיפוח שלך!_ 🌸"
        
        return msg
    
    def _get_error_message(self, language: str) -> str:
        """Get error message in appropriate language"""
        if language == "he" or language == "hebrew":
            return (
                "מצטערת, נתקלתי בבעיה ביצירת ההמלצות שלך. 😔\n\n"
                "אנא נסי שוב או פני אלי עם שאלות נוספות!"
            )
        return (
            "Sorry, I encountered an issue generating your recommendations. 😔\n\n"
            "Please try again or reach out with any questions!"
        )