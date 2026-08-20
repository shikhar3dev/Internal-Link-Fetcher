from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.core.url_utils import normalize_url
from app.db.repository import Repository

# ==========================================
# 1. DEMO ARTICLES (example.com - 4 articles)
# ==========================================
SAMPLE_DEMO_ARTICLES = [
    {
        "domain": "example.com",
        "is_demo": 1,
        "url_raw": "https://example.com/blog/how-to-choose-running-shoes",
        "url_normalized": "https://example.com/blog/how-to-choose-running-shoes",
        "canonical_url": "https://example.com/blog/how-to-choose-running-shoes",
        "title": "How to Choose Running Shoes for Beginners",
        "meta_description": "A comprehensive guide on finding the right running shoes for your foot type and stride.",
        "content_text": (
            "Choosing the right footwear is one of the most important decisions a new runner can make. "
            "Your shoes should provide adequate support and comfort for the type of running you plan to do.\n\n"
            "Different running surfaces require different types of cushioning and traction. If you run primarily on asphalt or concrete, "
            "look for road running shoes with ample shock absorption.\n\n"
            "Finding the best running shoes involves understanding your gait cycle and pronation. "
            "Overpronators typically need stability shoes, while neutral runners can wear standard cushioned trainers.\n\n"
            "Always replace your shoes every 300 to 500 miles to prevent joint strain and blisters."
        ),
        "paragraphs": [
            "Choosing the right footwear is one of the most important decisions a new runner can make. Your shoes should provide adequate support and comfort for the type of running you plan to do.",
            "Different running surfaces require different types of cushioning and traction. If you run primarily on asphalt or concrete, look for road running shoes with ample shock absorption.",
            "Finding the best running shoes involves understanding your gait cycle and pronation. Overpronators typically need stability shoes, while neutral runners can wear standard cushioned trainers.",
            "Always replace your shoes every 300 to 500 miles to prevent joint strain and blisters."
        ],
        "headings": [{"level": "h1", "text": "How to Choose Running Shoes for Beginners"}],
        "word_count": 86,
        "links": [
            {
                "href_raw": "https://example.com/blog/injury-prevention",
                "href_resolved": "https://example.com/blog/injury-prevention",
                "href_normalized": "https://example.com/blog/injury-prevention",
                "anchor_text": "injury prevention",
                "is_internal": True,
                "rel_nofollow": False
            }
        ]
    },
    {
        "domain": "example.com",
        "is_demo": 1,
        "url_raw": "https://example.com/blog/running-tips-for-beginners",
        "url_normalized": "https://example.com/blog/running-tips-for-beginners",
        "canonical_url": "https://example.com/blog/running-tips-for-beginners",
        "title": "Top 10 Running Tips for Beginners",
        "meta_description": "Essential training, pacing, and recovery tips for beginner runners.",
        "content_text": (
            "Starting a running routine can transform your cardiovascular health and mental well-being. "
            "However, progressing too quickly is the most common reason beginner runners suffer from shin splints.\n\n"
            "Invest in proper gear early. Running in worn-out sneakers can lead to knee and ankle pain. "
            "Quality footwear tailored to your foot shape will keep you running consistently.\n\n"
            "Focus on running at a conversational pace where you can speak in full sentences without gasping for breath.\n\n"
            "Hydration and post-run nutrition play a vital role in muscular recovery."
        ),
        "paragraphs": [
            "Starting a running routine can transform your cardiovascular health and mental well-being. However, progressing too quickly is the most common reason beginner runners suffer from shin splints.",
            "Invest in proper gear early. Running in worn-out sneakers can lead to knee and ankle pain. Quality footwear tailored to your foot shape will keep you running consistently.",
            "Focus on running at a conversational pace where you can speak in full sentences without gasping for breath.",
            "Hydration and post-run nutrition play a vital role in muscular recovery."
        ],
        "headings": [{"level": "h1", "text": "Top 10 Running Tips for Beginners"}],
        "word_count": 78,
        "links": []
    },
    {
        "domain": "example.com",
        "is_demo": 1,
        "url_raw": "https://example.com/blog/already-linking-article",
        "url_normalized": "https://example.com/blog/already-linking-article",
        "canonical_url": "https://example.com/blog/already-linking-article",
        "title": "Footwear Round-Up 2026",
        "meta_description": "A quick round-up of athletic gear and running footwear.",
        "content_text": (
            "We have already reviewed the best running shoes on our dedicated page.\n\n"
            "Make sure to inspect the outsole wear before heading out for trail runs."
        ),
        "paragraphs": [
            "We have already reviewed the best running shoes on our dedicated page.",
            "Make sure to inspect the outsole wear before heading out for trail runs."
        ],
        "headings": [{"level": "h1", "text": "Footwear Round-Up 2026"}],
        "word_count": 27,
        "links": [
            {
                "href_raw": "https://example.com/best-running-shoes",
                "href_resolved": "https://example.com/best-running-shoes",
                "href_normalized": "https://example.com/best-running-shoes",
                "anchor_text": "best running shoes",
                "is_internal": True,
                "rel_nofollow": False
            }
        ]
    },
    {
        "domain": "example.com",
        "is_demo": 1,
        "url_raw": "https://example.com/blog/vegan-smoothie-recipes",
        "url_normalized": "https://example.com/blog/vegan-smoothie-recipes",
        "canonical_url": "https://example.com/blog/vegan-smoothie-recipes",
        "title": "5 Delicious Post-Workout Vegan Smoothies",
        "meta_description": "Nutrient-dense plant-based smoothie recipes for athletic recovery.",
        "content_text": (
            "Blending whole fruits with plant-based protein powders is an easy way to replenish glycogen stores after endurance exercise.\n\n"
            "Bananas, almond milk, and chia seeds provide essential potassium, healthy fats, and sustained energy.\n\n"
            "Spinach and kale can be added without altering the sweet flavor profile of berry smoothies."
        ),
        "paragraphs": [
            "Blending whole fruits with plant-based protein powders is an easy way to replenish glycogen stores after endurance exercise.",
            "Bananas, almond milk, and chia seeds provide essential potassium, healthy fats, and sustained energy.",
            "Spinach and kale can be added without altering the sweet flavor profile of berry smoothies."
        ],
        "headings": [{"level": "h1", "text": "5 Delicious Post-Workout Vegan Smoothies"}],
        "word_count": 48,
        "links": []
    }
]

# ==========================================
# 2. PRODUCTION ARTICLES (outdoorgearlab.com - 24 articles)
# ==========================================
OUTDOORGEARLAB_TOPICS = [
    ("road-running-shoes-review", "Road Running Shoes Comprehensive Field Test", "Finding the best running shoes involves understanding your gait cycle and pronation across daily training runs."),
    ("trail-running-shoes-guide", "Best Trail Running Shoes for Mountain Terrains", "When navigating rocky paths and alpine scrambles, trail runners need durable outsoles with aggressive lugs."),
    ("marathon-racing-shoes", "Top Carbon Plate Marathon Racing Super Shoes", "Carbon-fiber plated super shoes offer unprecedented energy return for competitive long-distance marathon racers."),
    ("cushioned-running-footwear", "Max Cushion Running Shoes for High Mileage", "Maximal cushioning absorbs impact shock and protects joints during grueling 20-mile weekend training sessions."),
    ("stability-running-shoes", "Stability Running Shoes for Overpronation", "Medial posts and guide rails gently guide your stride to prevent excessive inward ankle rolling."),
    ("wide-toe-box-running", "Zero Drop & Wide Toe Box Footwear Comparison", "Allowing your toes to splay naturally reduces the incidence of bunions and plantar fasciitis over time."),
    ("winter-running-gear", "Winter Running Gear: Waterproof Shoes & Spikes", "GORE-TEX membranes keep your socks dry during slushy winter morning runs across icy sidewalks."),
    ("treadmill-running-shoes", "Best Shoes for Treadmill and Indoor Gym Running", "Lightweight and breathable trainers prevent heat buildup during high-intensity indoor treadmill workouts."),
    ("arch-support-guide", "How to Select Running Shoes for High Arches", "Underpronators and high-arched runners benefit most from flexible midsoles with focused arch support."),
    ("plantar-fasciitis-shoes", "Best Footwear for Plantar Fasciitis Relief", "Heel cushioning and structured shank plates alleviate tension on the plantar fascia ligament."),
    ("running-shoe-rotation", "Why You Should Rotate Multiple Pairs of Running Shoes", "Alternating between different shoes allows midsole foam to decompress and strengthens diverse muscle groups."),
    ("5k-to-10k-training-gear", "Essential Gear Checklist for 5K to 10K Runners", "Building a consistent running habit requires breathable moisture-wicking apparel and dependable daily trainers."),
    ("half-marathon-footwear", "Half Marathon Shoe Selection Strategies", "Balancing lightweight responsiveness with responsive cushioning ensures fresh legs in the final miles."),
    ("ultramarathon-shoe-guide", "100-Mile Ultramarathon Footwear Survival Guide", "Foot swelling over 24-hour races necessitates sizing up and choosing shoes with adaptable lacing systems."),
    ("running-gait-analysis", "Understanding Pronation, Supination, and Gait Mechanics", "A biomechanical gait analysis on a treadmill helps pinpoint your exact footstrike and movement patterns."),
    ("running-socks-review", "Best Anti-Blister Running Socks Tested", "Seamless merino wool and synthetic blend socks prevent friction hotspots during humid summer miles."),
    ("budget-running-shoes", "Best Affordable Running Shoes Under $100", "You do not need to spend top dollar to get reliable daily trainers with durable rubber outsoles."),
    ("cross-training-shoes", "Hybrid Cross-Training and Running Footwear", "Lateral stability and dense heel counters provide versatile support for gym lifts and short warm-up sprints."),
    ("orthotic-insoles-guide", "Custom Insoles vs Factory Running Shoe Sockliners", "Upgrading to supportive aftermarket insoles can correct leg alignment and reduce knee discomfort."),
    ("waterproof-trail-shoes", "Waterproof vs Breathable Trail Running Shoes", "In muddy and wet conditions, water-resistant uppers keep grit out while maintaining foot warmth."),
    ("running-form-tips", "Cadence and Stride Optimization for Distance Runners", "Increasing your step cadence to 170-180 steps per minute decreases ground impact force."),
    ("shoe-lacing-techniques", "Running Shoe Lacing Hacks for Heel Slippage", "The runner's knot technique locks your heel securely into the collar without creating instep pressure."),
    ("daily-trainer-roundup", "The Ultimate Daily Trainer Comparison for 2026", "A versatile daily workhorse shoe should handle recovery jogs, tempo runs, and long weekend outings effortlessly."),
    ("post-run-recovery-footwear", "Best Recovery Slides and Footwear for Sore Feet", "Ergonomic arch cradles and soft EVA foams soothe tired feet immediately following hard endurance workouts.")
]

SAMPLE_OUTDOORGEARLAB_ARTICLES = []
for idx, (slug, title, lead_sentence) in enumerate(OUTDOORGEARLAB_TOPICS, start=1):
    SAMPLE_OUTDOORGEARLAB_ARTICLES.append({
        "domain": "outdoorgearlab.com",
        "is_demo": 0,
        "url_raw": f"https://www.outdoorgearlab.com/topics/shoes-and-boots/{slug}",
        "url_normalized": f"https://outdoorgearlab.com/topics/shoes-and-boots/{slug}",
        "canonical_url": f"https://outdoorgearlab.com/topics/shoes-and-boots/{slug}",
        "title": title,
        "meta_description": f"Detailed expert testing and review of {title.lower()}.",
        "content_text": (
            f"{lead_sentence}\n\n"
            f"Our team of veteran testers put dozens of top contenders through hundreds of miles of rigorous field evaluation. "
            f"We analyzed outsole durability, midsole energy return, upper breathability, and overall comfort across diverse terrains.\n\n"
            f"Proper fit is paramount when logging high weekly mileage. Make sure to allow a thumb's width of space in the toe box.\n\n"
            f"Regularly tracking your shoe mileage ensures you retire worn pairs before excessive wear leads to tendon strain."
        ),
        "paragraphs": [
            lead_sentence,
            "Our team of veteran testers put dozens of top contenders through hundreds of miles of rigorous field evaluation. We analyzed outsole durability, midsole energy return, upper breathability, and overall comfort across diverse terrains.",
            "Proper fit is paramount when logging high weekly mileage. Make sure to allow a thumb's width of space in the toe box.",
            "Regularly tracking your shoe mileage ensures you retire worn pairs before excessive wear leads to tendon strain."
        ],
        "headings": [{"level": "h1", "text": title}],
        "word_count": 92,
        "links": []
    })


def seed():
    repo = Repository(settings.database_path)
    schema_path = Path(__file__).resolve().parents[1] / "app" / "db" / "schema.sql"
    repo.init_schema(schema_path.read_text(encoding="utf-8"))
    
    # 1. Seed Demo Data (example.com - 4 articles)
    repo.delete_domain("example.com")
    for art in SAMPLE_DEMO_ARTICLES:
        art_id = repo.upsert_article(art)
        print(f"Seeded Demo: #{art_id} - {art['title']}")
        
    # 2. Seed Production Data (outdoorgearlab.com - 24 articles)
    repo.delete_domain("outdoorgearlab.com")
    for art in SAMPLE_OUTDOORGEARLAB_ARTICLES:
        art_id = repo.upsert_article(art)
        print(f"Seeded Production: #{art_id} - {art['title']}")
        
    print(f"\nSuccessfully seeded {len(SAMPLE_DEMO_ARTICLES)} demo articles and {len(SAMPLE_OUTDOORGEARLAB_ARTICLES)} production articles into {settings.database_path}")


if __name__ == "__main__":
    seed()
