"""
High-volume fake data population command for local and development environments.
Seeds comprehensive, realistic commerce datasets including users, stores, products,
specifications, orders, tracking events, financial ledgers, reviews, coupons,
wallets, refunds, affiliates, notifications, and staff blog posts.
"""
from __future__ import annotations

import os
import random
import sys
from argparse import ArgumentParser
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from affiliates.models import (
    AffiliateWallet,
    AffiliateWalletTransaction,
    Marketer,
    Redirect,
    Referral,
    Url as AffiliateUrl,
)
from cart.models import Cart, CartItem
from core.models import (
    Address,
    Recent,
    Refund,
    Review,
    User,
    UserWallet,
    UserWalletTransaction,
    Wishlist,
)
from notification.models import Notification
from payment.models import (
    Coupon,
    CouponRedemption,
    DeliveryInfo,
    Order,
    TaxJurisdiction,
)
from payment.tax import calculate_tax, DEFAULT_US_JURISDICTIONS
from product.models import Product, Specification
from staff.models import Comment as BlogComment, Content as BlogContent, Post as BlogPost
from store.models import (
    MerchantWallet,
    Store,
    StoreAddress,
    StoreEarningsLedger,
    StoreInfo,
    StorePayout,
)


FIRST_NAMES = [
    ("Alex", "male"), ("Jordan", "male"), ("Morgan", "female"), ("Taylor", "female"),
    ("Marcus", "male"), ("Elena", "female"), ("Liam", "male"), ("Sophia", "female"),
    ("Noah", "male"), ("Olivia", "female"), ("Ethan", "male"), ("Emma", "female"),
    ("Lucas", "male"), ("Ava", "female"), ("Mason", "male"), ("Isabella", "female"),
    ("Oliver", "male"), ("Mia", "female"), ("Elijah", "male"), ("Charlotte", "female"),
    ("William", "male"), ("Amelia", "female"), ("James", "male"), ("Harper", "female"),
    ("Benjamin", "male"), ("Evelyn", "female"), ("Henry", "male"), ("Abigail", "female"),
    ("Alexander", "male"), ("Emily", "female"), ("Daniel", "male"), ("Ella", "female"),
    ("Matthew", "male"), ("Scarlett", "female"), ("Jackson", "male"), ("Grace", "female"),
    ("David", "male"), ("Chloe", "female"), ("Joseph", "male"), ("Camila", "female"),
    ("Samuel", "male"), ("Penelope", "female"), ("Sebastian", "male"), ("Riley", "female"),
    ("Aiden", "male"), ("Layla", "female"), ("Gabriel", "male"), ("Nora", "female"),
]

LAST_NAMES = [
    "Vance", "Mercer", "Sterling", "Kowalski", "Chen", "Novak", "O'Connor", "Dubois",
    "Sinclair", "Hayashi", "Lindqvist", "Alvarez", "Castillo", "Moreau", "Adler",
    "Hawthorne", "Kensington", "Blackwood", "Frost", "Winter", "Summers", "Rivers",
    "Stone", "Brooks", "Hayes", "Fletcher", "Barrett", "Sutton", "Monroe", "Mercer",
    "Gallagher", "Donovan", "Whitaker", "Preston", "Collier", "Harrington", "Vaughn",
]

US_CITIES = [
    ("100 N Tampa Street", "Tampa", "Florida", "33602", "United States"),
    ("500 Howard Street", "San Francisco", "California", "94105", "United States"),
    ("350 5th Avenue", "New York", "New York", "10118", "United States"),
    ("1200 Pine Street", "Seattle", "Washington", "98101", "United States"),
    ("200 S Michigan Ave", "Chicago", "Illinois", "60604", "United States"),
    ("111 Congress Ave", "Austin", "Texas", "78701", "United States"),
    ("1000 Brickell Ave", "Miami", "Florida", "33131", "United States"),
    ("1700 Lincoln Street", "Denver", "Colorado", "80203", "United States"),
    ("100 Federal Street", "Boston", "Massachusetts", "02110", "United States"),
    ("191 Peachtree St NE", "Atlanta", "Georgia", "30303", "United States"),
    ("700 SW 5th Ave", "Portland", "Oregon", "97204", "United States"),
    ("100 W Washington St", "Phoenix", "Arizona", "85003", "United States"),
]

STORE_BLUEPRINTS = [
    {
        "name": "ProAce Select",
        "username": "proace-select",
        "is_official": True,
        "bio": "Curated lifestyle essentials and flagship technological innovations.",
        "announcement": "Free worldwide express shipping on flagship audio this week.",
        "avatar": "1534528741775-53994a69daeb",
        "banner": "1441986300917-64674bd600d8",
        "website": "https://select.proace.local",
    },
    {
        "name": "Aura Audio & Sound",
        "username": "aura-audio",
        "is_official": False,
        "bio": "Acoustic perfection for audiophiles, creators, and everyday listeners.",
        "announcement": "New Gen 3 Noise-Cancelling Headphones now in stock!",
        "avatar": "1507003211169-0a1dd7228f2d",
        "banner": "1511671782779-c97d3d27a1d4",
        "website": "https://auraaudio.local",
    },
    {
        "name": "Apex Athletic Club",
        "username": "apex-athletics",
        "is_official": False,
        "bio": "High-performance sportswear, footwear, and conditioning equipment.",
        "announcement": "Spring marathon runner collections now shipping.",
        "avatar": "1500648767791-00dcc994a43e",
        "banner": "1461896836934-ffe607ba8211",
        "website": "https://apexathletic.local",
    },
    {
        "name": "Zenith Computing Gear",
        "username": "zenith-pc",
        "is_official": False,
        "bio": "Developer workstations, ergonomic peripherals, and high-speed NVMe storage.",
        "announcement": "Equip your home office with our ergonomic bundles.",
        "avatar": "1573496359142-b8d87734a5a2",
        "banner": "1517694712202-14dd9538aa97",
        "website": "https://zenithgear.local",
    },
    {
        "name": "Lumina Optics & Photo",
        "username": "lumina-optics",
        "is_official": False,
        "bio": "Mirrorless 4K cameras, cine lenses, and portable creator lighting rigs.",
        "announcement": "Mirrorless Cine Edition bundles 15% off with code TECH20.",
        "avatar": "1544005313-94ddf0286df2",
        "banner": "1452587925148-ce544e77e70d",
        "website": "https://luminaoptics.local",
    },
    {
        "name": "Nordic Living Essentials",
        "username": "nordic-living",
        "is_official": False,
        "bio": "Minimalist home accents, handcrafted journals, and timeless analogue watches.",
        "announcement": "Timeless Scandinavian design for mindful everyday living.",
        "avatar": "1506794778202-cad84cf45f1d",
        "banner": "1493663284031-b7e3aefcae8e",
        "website": "https://nordicliving.local",
    },
    {
        "name": "Terra Outdoor & Fishing",
        "username": "terra-outdoor",
        "is_official": False,
        "bio": "Rugged all-weather apparel, carbon fiber rods, and expedition gear.",
        "announcement": "Gear up for spring expeditions with waterproof tackle combos.",
        "avatar": "1492562080023-ab3db95bfbce",
        "banner": "1507525428034-b723cf961d3e",
        "website": "https://terraoutdoor.local",
    },
    {
        "name": "Paws & Whiskers Depot",
        "username": "paws-whiskers",
        "is_official": False,
        "bio": "Orthopedic memory foam pet beds, automated fountains, and organic treats.",
        "announcement": "Healthy pets, happy homes. All pet beds guaranteed for 2 years.",
        "avatar": "1517841905240-472988babdf9",
        "banner": "1548767797-d8c844163c4c",
        "website": "https://pawswhiskers.local",
    },
    {
        "name": "NextGen Arcade & Gaming",
        "username": "nextgen-gaming",
        "is_official": False,
        "bio": "Pro wireless gamepads, low-latency spatial headsets, and retro consoles.",
        "announcement": "Tournament edition wireless gamepads with magnetic hall triggers.",
        "avatar": "1535713875002-d1d0cf377fde",
        "banner": "1538481199705-c710c4e965fc",
        "website": "https://nextgengaming.local",
    },
    {
        "name": "Roast & Leaf Botanicals",
        "username": "roast-leaf",
        "is_official": False,
        "bio": "Single-origin Ethiopian whole bean roasts and ceremonial Uji Japanese matcha.",
        "announcement": "Freshly roasted weekly. Free sampling pack with every subscription.",
        "avatar": "1580489944761-15a19d654956",
        "banner": "1495474472287-4d71bcdd2085",
        "website": "https://roastleaf.local",
    },
    {
        "name": "MindCraft STEM & Play",
        "username": "mindcraft-play",
        "is_official": False,
        "bio": "Programmable educational robotics kits and architectural building blocks.",
        "announcement": "Empowering young builders with tactile engineering challenges.",
        "avatar": "1544717302-de2939b7ef71",
        "banner": "1587654780291-39c9404d746b",
        "website": "https://mindcraftplay.local",
    },
    {
        "name": "Silk & Pure Studio",
        "username": "silk-pure",
        "is_official": False,
        "bio": "Seamless modal bralettes, pure silk satin loungewear, and luxury basics.",
        "announcement": "Experience breathable everyday comfort with pure mulberry silk.",
        "avatar": "1494790108377-be9c29b29330",
        "banner": "1490481651871-ab68de25d43d",
        "website": "https://silkpure.local",
    },
]

MINIMUM_SEEDED_USERS = 11

PRODUCT_TEMPLATES = [
    # electronics
    ("Studio Wireless ANC Headphones", "Soundform", "electronics", "249.00", 15, 45, "1546435770-a3e426bf472b",
     "Immersive active noise-cancellation with 40mm beryllium drivers, 38-hour battery endurance, and plush memory foam ear cushions.",
     ["audio", "wireless", "anc", "bluetooth", "headphones"], 1.15, False),
    ("Classic Analogue Minimalist Watch", "Nord", "electronics", "165.00", 10, 28, "1523275335684-37898b6baf30",
     "Precision Japanese quartz movement housed in a surgical 316L stainless steel casing with interchangeable Italian leather strap.",
     ["watch", "minimalist", "accessories", "quartz"], 0.35, False),
    ("Compact Mirrorless 4K Cine Camera", "Focus", "electronics", "849.00", 5, 14, "1516035069371-29a1b244cc32",
     "Compact APS-C sensor with 10-bit 4K 60fps recording, dual native ISO, in-body stabilization, and cinematic color science.",
     ["camera", "photography", "video", "4k", "cine"], 1.85, False),
    ("Portable Waterproof Bluetooth Speaker", "Soundform", "electronics", "89.00", 20, 60, "1608043152269-423dbba4e7e1",
     "Rugged IP67 waterproof enclosure featuring dual passive bass radiators, 360-degree soundstage, and 20-hour playback.",
     ["audio", "speaker", "waterproof", "portable", "bass"], 1.45, False),
    ("Desk Companion Studio Headphones", "Soundform", "electronics", "119.00", 0, 32, "1505740420928-5e560c06d30e",
     "Open-back acoustic design delivering natural spatial sound reproduction for recording, mixing, and critical listening.",
     ["headphones", "studio", "open-back", "reference"], 0.85, False),
    ("True Wireless ANC Earbuds Pro", "Aura", "electronics", "139.00", 15, 55, "1590658268037-6bf12165a8df",
     "Custom dynamic drivers with adaptive noise cancellation, transparency audio mode, and wireless charging case.",
     ["earbuds", "audio", "wireless", "anc"], 0.25, False),
    
    # computing
    ("Ultralight Developer Laptop 14-inch", "Form", "computing", "1349.00", 8, 22, "1496181133206-80ce9b88a853",
     "Precision milled aluminum chassis, 120Hz Retina-grade display, 32GB LPDDR5X RAM, and 1TB ultra-fast PCIe Gen4 SSD.",
     ["laptop", "developer", "computing", "ultrabook"], 2.95, False),
    ("27-inch 4K UHD IPS Designer Monitor", "ViewCraft", "computing", "449.00", 12, 18, "1527443224154-c4a3942d3acf",
     "Color-accurate 99% DCI-P3 coverage, USB-C 90W single-cable power delivery, HDR400, and factory color calibration report.",
     ["monitor", "display", "4k", "designer", "usb-c"], 11.50, False),
    ("RGB Mechanical Gaming Keyboard", "KeyCraft", "computing", "129.00", 10, 40, "1587829741301-dc798b83add3",
     "Hot-swappable tactile mechanical switches, sound dampening silicone gaskets, double-shot PBT keycaps, and per-key RGB.",
     ["keyboard", "mechanical", "gaming", "rgb"], 2.20, False),
    ("Ergonomic Wireless Vertical Mouse", "LogiTech", "computing", "79.00", 15, 50, "1527864550417-7fd91fc51a46",
     "Sculpted 57-degree vertical grip that promotes natural wrist posture, thumb rest, hyper-fast scroll wheel, and multi-device pairing.",
     ["mouse", "ergonomic", "wireless", "productivity"], 0.40, False),
    ("Thunderbolt 4 Multi-Port Docking Station", "AnkerTech", "computing", "189.00", 5, 25, "1618424181497-157f25b6ddd5",
     "11-in-1 expansion hub with 85W host charging, dual 4K 60Hz video output, 2.5G Ethernet, and SD card reader.",
     ["dock", "hub", "thunderbolt", "usb-c"], 1.10, False),
    ("Ultra-Fast 2TB NVMe PCIe 4.0 SSD", "CruxMemory", "computing", "169.00", 20, 75, "1597872200969-2b65d56bd16b",
     "Sequential read speeds up to 7,400 MB/s, integrated aluminum heat sink, ideal for video editing and heavy compilation tasks.",
     ["ssd", "storage", "nvme", "pcie"], 0.20, False),
    
    # phones
    ("Everyday 5G Flagship Smartphone", "Connect", "phones", "829.00", 5, 30, "1511707171634-5f897ff02aa9",
     "Vibrant 6.7-inch OLED 120Hz display, triple computational camera array with optical zoom, and all-day intelligent battery life.",
     ["smartphone", "5g", "mobile", "oled", "camera"], 0.45, False),
    ("Ultra Slim Magnetic Power Bank 10000mAh", "VoltCore", "phones", "49.00", 10, 85, "1585338107529-13afc5f02586",
     "Strong magnetic snap-on wireless charging with 15W Qi2 output, pass-through charging, and slim aviation-grade aluminum shell.",
     ["powerbank", "magsafe", "wireless", "charger"], 0.55, False),
    ("65W GaN Dual USB-C Fast Wall Charger", "VoltCore", "phones", "36.00", 15, 95, "1583863788434-e58a36330cf0",
     "Compact gallium nitride technology capable of fast charging your laptop, phone, and tablet simultaneously without overheating.",
     ["charger", "gan", "fast-charging", "usb-c"], 0.30, False),
    ("Shockproof MagSafe Protective Armor Case", "ShieldPro", "phones", "32.00", 0, 110, "1580910051074-3eb694886505",
     "Military-grade drop certified up to 12 feet, reinforced corner airbags, tactile anodized aluminum buttons, and matte finish.",
     ["case", "phone-case", "magsafe", "protection"], 0.15, False),

    # tablets
    ("Pro Digital Drawing Tablet 12.9-inch", "StylusPro", "tablets", "899.00", 5, 16, "1544244015-0df4b3ffc6b0",
     "Laminated anti-glare screen with 8,192 levels of pressure sensitivity, tilt recognition, and seamless Bluetooth stylus support.",
     ["tablet", "drawing", "illustration", "creative"], 1.65, False),
    ("Paper-Feel E-Ink Digital Notepad", "ReadWell", "tablets", "319.00", 10, 24, "1585776245991-cf89dd7fc73a",
     "Distraction-free digital paper notebook with friction-tuned stylus feel, weeks of battery life, and cloud synchronization.",
     ["e-ink", "notepad", "reading", "productivity"], 0.85, False),
    ("Magnetic Folio Smart Keyboard Folio", "Form", "tablets", "99.00", 15, 45, "1561154464-82e9adf32764",
     "Ultra-slim magnetic keyboard folio with precision multi-touch trackpad, scissor-switch keys, and dual viewing angles.",
     ["keyboard", "folio", "tablet", "accessories"], 0.70, False),

    # sports
    ("Air Runner Performance Sneakers", "Stride", "sports", "125.00", 15, 65, "1542291026-7eec264c27ff",
     "Engineered breathable mesh upper paired with carbon fiber spring plate and high-rebound supercritical foam midsole.",
     ["running", "sneakers", "marathon", "fitness"], 1.10, False),
    ("Weekend Classic Leather Court Sneakers", "Stride", "sports", "105.00", 10, 48, "1549298916-b41d501d3772",
     "Handcrafted full-grain Italian leather, reinforced stitching, padded collar, and durable vulcanized natural rubber outsole.",
     ["sneakers", "leather", "court", "casual", "streetwear"], 1.40, False),
    ("Eco-Grip Alignment Studio Yoga Mat 6mm", "PranaFlow", "sports", "52.00", 20, 70, "1601925260368-ae2f83cf8b7f",
     "Non-slip biodegradable tree rubber base with etched body alignment lines, sweat-absorbing surface, and carrying sling.",
     ["yoga", "mat", "fitness", "eco", "pilates"], 3.20, False),
    ("Adjustable Quick-Select Dumbbell Pair", "IronGrip", "sports", "295.00", 0, 15, "1584735935682-2f2b69dff9d2",
     "Space-saving dial mechanism adjusting from 5 to 52.5 lbs per dumbbell in 2.5 lb increments with safety lock plates.",
     ["weights", "dumbbells", "strength", "homegym"], 55.00, False),
    ("Stainless Steel Insulated Sports Shaker 32oz", "HydroMax", "sports", "34.00", 15, 80, "1602143407151-7111542de6e8",
     "Double-wall vacuum insulation keeping drinks icy cold for 24 hours, leak-proof locking lid, and silent blending whisk.",
     ["shaker", "water-bottle", "gym", "insulated"], 0.65, False),

    # outwear
    ("Everyday Heavyweight Canvas Backpack", "Daytrip", "outwear", "72.00", 10, 52, "1553062407-98eeb64c6a62",
     "Waxed 16oz cotton canvas, water-resistant zippers, padded 16-inch laptop compartment, and vegetable-tanned leather accents.",
     ["backpack", "canvas", "travel", "everyday", "commute"], 1.80, False),
    ("Essential Relaxed Organic Cotton Tee", "Everyday", "outwear", "32.00", 25, 120, "1521572163474-6864f9cf17ab",
     "GOTS-certified 220 GSM heavyweight combed cotton with pre-shrunk treatment and reinforced ribbed crewneck collar.",
     ["t-shirt", "cotton", "basics", "organic", "wardrobe"], 0.45, False),
    ("All-Weather Technical Shell Windbreaker", "NorthPeak", "outwear", "125.00", 15, 38, "1551028719-00167b16eac5",
     "Three-layer waterproof breathable membrane with fully taped seams, adjustable storm hood, and zippered underarm vents.",
     ["jacket", "windbreaker", "weatherproof", "outdoor"], 1.10, False),
    ("Merino Wool Thermal Ribbed Beanie", "NorthPeak", "outwear", "28.00", 10, 65, "1576871337622-98d48d1cf531",
     "Pure Australian merino wool providing natural thermoregulation, itch-free comfort, and breathable winter warmth.",
     ["beanie", "merino-wool", "winter", "accessories"], 0.20, False),
    ("Waxed Field Utility Safari Parka", "TimberCraft", "outwear", "195.00", 5, 20, "1544022613-e87ca75a784a",
     "Rugged weatherproof construction with fleece-lined handwarmer pockets, drawstring storm waist, and heavy-duty brass hardware.",
     ["parka", "jacket", "utility", "safari", "outerwear"], 2.60, False),

    # books
    ("Designing Data-Intensive Applications", "O'Reilly", "books", "48.00", 0, 60, "1512820790803-83ca734da794",
     "The definitive handbook on reliability, scalability, and maintainability in modern distributed data architectures.",
     ["book", "programming", "software", "architecture", "tech"], 1.60, False),
    ("Atomic Habits & Daily Systems", "Penguin", "books", "24.00", 20, 95, "1544947950-fa07a98d237f",
     "Practical frameworks for forming good habits, breaking bad ones, and mastering the tiny behaviors that yield massive results.",
     ["book", "productivity", "psychology", "habits", "self-improvement"], 0.85, False),
    ("The Art of Mindful Living & Architecture", "Chronicle", "books", "38.00", 10, 30, "1543002588-bfa74002ed7e",
     "Hardcover architectural monograph exploring sustainable spatial design, natural daylighting, and tranquil domestic interiors.",
     ["book", "architecture", "design", "lifestyle", "hardcover"], 2.10, False),
    ("Full-Stack Microservices Architecture Guide", "CodeCraft", "books", "39.00", 30, 999, "1555066931-4365d14bab8c",
     "Comprehensive digital handbook including full reference projects, Docker compose recipes, and production deployment checklists.",
     ["ebook", "digital", "microservices", "python", "docker"], 0.05, True),

    # games
    ("NextGen Wireless Pro Gamepad", "Vortex", "games", "74.99", 10, 44, "1600080972464-8e5f35f63d08",
     "Hall-effect magnetic thumbsticks ensuring zero drift, tactile mechanical buttons, rear mappable paddles, and USB-C low latency.",
     ["gaming", "gamepad", "controller", "wireless", "esports"], 0.65, False),
    ("Spatial Noise-Isolating Gaming Headset", "Vortex", "games", "109.00", 15, 36, "1599669454699-248893623440",
     "53mm neodymium drivers tuned for competitive positional audio, detachable broadcast microphone, and cooling gel ear pads.",
     ["headset", "gaming", "audio", "surround-sound", "esports"], 1.10, False),
    ("Retro 16-Bit Handheld Arcade Console", "PixelPlay", "games", "58.00", 20, 60, "1550745165-9bc0b252726f",
     "IPS laminated retro display, rechargeable battery, hundreds of classic indie arcade games pre-installed with TV HDMI output.",
     ["retro", "arcade", "handheld", "console", "gaming"], 0.50, False),

    # beverages
    ("Single-Origin Ethiopian Yirgacheffe Beans 12oz", "RoastCo", "beverages", "19.50", 0, 75, "1514432324607-a09d9b4aefdd",
     "Light roast specialty coffee with floral jasmine aroma, bergamot notes, and silky citrus finish roasted in small batches.",
     ["coffee", "specialty-coffee", "ethiopia", "whole-bean"], 0.75, False),
    ("Ceremonial Grade Uji Japanese Matcha 30g", "ZenTea", "beverages", "29.00", 10, 50, "1576092768241-dec231879fc3",
     "First-harvest stone-ground tencha leaves from Kyoto with vibrant emerald green color, delicate umami, and sweet finish.",
     ["matcha", "green-tea", "japanese", "organic", "ceremonial"], 0.20, False),
    ("Botanical Nighttime Sleep Chamomile Tea", "ZenTea", "beverages", "15.00", 15, 80, "1597481499750-3e6b22637e12",
     "Hand-blended organic Egyptian chamomile blossoms, valerian root, lavender flowers, and lemon balm for restorative sleep.",
     ["tea", "herbal", "organic", "sleep", "wellness"], 0.35, False),
    ("Nitro Cold Brew Coffee Concentrate 32oz", "RoastCo", "beverages", "17.50", 10, 45, "1517701550927-30cf4ba1dba5",
     "Slow-steeped for 24 hours using filtered mountain water, creating an ultra-smooth, low-acidity base for iced beverages.",
     ["cold-brew", "coffee", "beverage", "artisan"], 2.20, False),

    # pets
    ("Orthopedic Dual-Layer Memory Foam Pet Bed", "PawComfort", "pets", "69.00", 15, 34, "1541599540903-216a46ca1dc0",
     "Medical grade orthopedic foam relieving joint pressure, waterproof inner mattress protector, and machine-washable faux suede cover.",
     ["pets", "dog-bed", "orthopedic", "comfort"], 5.40, False),
    ("Stainless Steel Ultra-Quiet Pet Fountain 2.5L", "AquaPaw", "pets", "38.00", 20, 58, "1583511655857-d19b40a7a54e",
     "Circulating triple-stage carbon filtration system providing fresh oxygenated water with ultra-quiet low-voltage submersible pump.",
     ["pets", "water-fountain", "cats", "dogs", "hydration"], 1.80, False),
    ("Interactive Brain Teaser Treat Puzzle Toy", "PawComfort", "pets", "22.50", 0, 70, "1576201836106-db1758fd1c97",
     "Engaging multi-level puzzle sliding compartments promoting mental stimulation and slowing down rapid eating habits.",
     ["pets", "toy", "puzzle", "enrichment", "training"], 0.90, False),

    # toys
    ("STEM Programmable Educational Robotics Kit", "MindBuild", "toys", "89.00", 10, 42, "1596461404969-9ae70f2830c1",
     "Build and program 8 distinct robotic models with graphical drag-and-drop code, ultrasonic sensors, and Bluetooth controller.",
     ["toys", "stem", "robotics", "educational", "coding"], 2.10, False),
    ("Magnetic Architectural 3D Building Tiles 100-Pc", "MagnaPlay", "toys", "54.00", 15, 65, "1587654780291-39c9404d746b",
     "High-transparency vibrant geometric tiles with heavy-duty internal magnets fostering spatial reasoning and creative open play.",
     ["toys", "building", "creative", "stem", "magnetic"], 3.50, False),
    ("High-Speed Off-Road RC Rock Crawler 1:16", "TurboRacer", "toys", "64.00", 10, 35, "1594787318286-3d835c1d207f",
     "Proportional steering, independent metal suspension dampers, 4WD dual high-torque motors, and all-terrain hollow rubber tires.",
     ["rc-car", "remote-control", "toys", "off-road"], 2.40, False),

    # fishing
    ("Carbon Fiber Telescopic Fishing Rod & Reel Combo", "AquaCast", "fishing", "85.00", 15, 30, "1544551763-46a013bb70d5",
     "24-ton high-density carbon fiber blank with stainless steel guides, smooth 5.2:1 gear ratio spinning reel, and travel carry case.",
     ["fishing", "rod", "reel", "outdoor", "tackle"], 1.70, False),
    ("Multi-Compartment Waterproof Tackle Bag", "AquaCast", "fishing", "42.00", 20, 45, "1507525428034-b723cf961d3e",
     "Tough 600D ripstop nylon with molded waterproof bottom, rod holder straps, and includes three utility 3600 tackle organizer boxes.",
     ["fishing", "tackle-box", "waterproof", "backpack"], 2.10, False),
    ("Polarized UV400 Angler Sunglasses", "ClearSight", "fishing", "29.00", 0, 80, "1511499767150-a48a237f0083",
     "Triacetate cellulose polarized lenses cutting water surface glare to reveal submerged structures and fish with ultra-light TR90 frames.",
     ["sunglasses", "polarized", "fishing", "uv400"], 0.15, False),

    # lingerie
    ("Seamless Wirefree Modal Lounge Bralette", "Silk & Pure", "lingerie", "35.00", 15, 90, "1515886657613-9f3515b0c78f",
     "Silky Lenzing MicroModal fabric with bonded seamless edges, removable breathable padding, and zero-dig comfort band.",
     ["lingerie", "bralette", "modal", "comfort", "seamless"], 0.25, False),
    ("Pure Silk Satin Pajama Sleepwear Set", "Silk & Pure", "lingerie", "98.00", 10, 25, "1529139574466-a303027c1d8b",
     "Grade 6A 22-momme pure mulberry silk top and drawstring lounge pants with French seam finishing and delicate contrast piping.",
     ["silk", "sleepwear", "pajamas", "luxury", "lounge"], 0.60, False),
    ("Organic Cotton High-Waist Brief 3-Pack", "Everyday", "lingerie", "26.00", 20, 110, "1489987707025-afc232f7ea0f",
     "Soft breathable organic cotton with touch of elastane, flatlock seams preventing panty lines, and gentle covered waistband.",
     ["cotton", "underwear", "basics", "soft", "pack"], 0.35, False),
]

REVIEW_COMMENTS_HIGH = [
    ("Exceptional build quality!", "Exceeded all my expectations. The materials feel remarkably high-end and it performs flawlessly every single day."),
    ("Worth every single penny", "I was hesitant at first due to the price, but after using it for weeks I can confidently say it is the best in its class."),
    ("Fast shipping & gorgeous packaging", "Arrived two days ahead of schedule in pristine condition. Super easy to set up and looks stunning on my desk."),
    ("Daily staple, highly recommend!", "I use this continuously and haven't encountered a single hiccup. Build quality and attention to detail are superb."),
    ("Fantastic customer experience", "Five stars without question. Works exactly as advertised, sleek ergonomics, and rock-solid reliability."),
    ("Game changer for my workflow", "Immediately boosted my daily productivity. Thoughtful design, comfortable feel, and stellar battery performance."),
]

REVIEW_COMMENTS_MID = [
    ("Good overall with minor caveats", "Very solid product that delivers on its core promise. A few minor software tweaks could make it perfect."),
    ("Decent value for the price", "Build quality is respectable and performance is good enough for casual everyday use. Met my expectations."),
    ("Works well, slightly delayed shipping", "The product itself is four stars, though carrier tracking was a bit slow to update. Still happy with the purchase."),
]

REVIEW_COMMENTS_LOW = [
    ("Did not match my exact expectations", "The color was slightly different in person compared to the photos, and took some time to get used to."),
    ("Average performance", "It gets the job done but feels slightly lighter than I anticipated. Adequate, but room for improvement."),
]

COUPON_BLUEPRINTS = [
    {"code": "WELCOME10", "discount": 10, "type": "order_total", "available": 1000, "category": ""},
    {"code": "SUMMER25", "discount": 25, "type": "category", "available": 500, "category": "outwear"},
    {"code": "FREESHIP", "discount": 15, "type": "order_total", "available": 800, "category": ""},
    {"code": "FLASH50", "discount": 50, "type": "order_total", "available": 200, "category": ""},
    {"code": "TECH20", "discount": 20, "type": "category", "available": 400, "category": "electronics"},
    {"code": "COMPUTE15", "discount": 15, "type": "category", "available": 300, "category": "computing"},
    {"code": "FITNESS30", "discount": 30, "type": "category", "available": 250, "category": "sports"},
    {"code": "VIPMEMBER", "discount": 35, "type": "order_total", "available": 150, "category": ""},
]

BLOG_POST_BLUEPRINTS = [
    (
        "The 2026 Developer Gear & Ergonomics Guide",
        "Exploring our curated selection of developer workstations, acoustic isolation headphones, and monitor configurations tailored for deep focused programming sessions. We break down keystroke acoustics, vertical wrist alignment, and ambient workspace lighting.",
    ),
    (
        "Sustainable Commerce: How ProAce Select Partners with Craft Studios",
        "Behind every verified partner on our platform is a story of craftsmanship. From single-origin organic coffee roasters to small-batch leather artisans, here is how our verified merchant escrow system ensures ethical supply chains and fair remuneration.",
    ),
    (
        "Running in 2026: Supercritical Foams and Biomechanical Efficiency",
        "We put the latest Stride Air Runner sneakers through laboratory force plate tests. Learn how carbon-composite plates combined with lightweight nitrogen-infused midsoles reduce metabolic cost during long distance marathon training.",
    ),
]


class Command(BaseCommand):
    help = "Populate the database with a high-volume, realistic commerce dataset for local/dev environments."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--scale",
            choices=["small", "medium", "large", "huge"],
            default="medium",
            help="Predefined scale preset (small: ~40 prods/80 orders, medium: ~150 prods/350 orders, large: ~500 prods/1500 orders, huge: ~1200 prods/4000 orders).",
        )
        parser.add_argument("--users", type=int, help="Override total user count.")
        parser.add_argument("--stores", type=int, help="Override total store count.")
        parser.add_argument("--products", type=int, help="Override total product count.")
        parser.add_argument("--orders", type=int, help="Override total order count.")
        parser.add_argument("--reviews", type=int, help="Override total review count.")
        parser.add_argument(
            "--password",
            default=None,
            help="Default password for seeded user accounts (defaults to configured development password or ProaceDemo2026!).",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Cleanly flush previous seeded data before populating.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Random seed for reproducible generation (default: 42).",
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        from django.db import connection

        if not settings.DEBUG:
            if options.get("clear"):
                raise CommandError(
                    "SAFETY BLOCK: Flushing data with --clear is permanently forbidden when DEBUG=False "
                    "to prevent accidental data loss in production."
                )
            raise CommandError(
                "SAFETY BLOCK: Fake data population is disabled when DEBUG=False. "
                "This command is strictly for local and development environments."
            )

        random.seed(options.get("seed", 42))
        env_admin_password = os.environ.get("DEFAULT_ADMIN_PASSWORD") or os.environ.get("TECHNICAL_ADMIN_PASSWORD")
        password = options.get("password") or env_admin_password or "ProaceDemo2026!"
        if len(password) < 8:
            raise CommandError("Password must be at least 8 characters long.")

        scale = options["scale"]
        scale_config = {
            "small": {"users": 25, "stores": 6, "products": 45, "orders": 90, "reviews": 70},
            "medium": {"users": 65, "stores": 12, "products": 150, "orders": 350, "reviews": 280},
            "large": {"users": 200, "stores": 25, "products": 500, "orders": 1500, "reviews": 1100},
            "huge": {"users": 500, "stores": 50, "products": 1200, "orders": 4000, "reviews": 3200},
        }[scale]

        num_users = options["users"] if options["users"] is not None else scale_config["users"]
        num_stores = options["stores"] if options["stores"] is not None else scale_config["stores"]
        num_products = options["products"] if options["products"] is not None else scale_config["products"]
        num_orders = options["orders"] if options["orders"] is not None else scale_config["orders"]
        num_reviews = options["reviews"] if options["reviews"] is not None else scale_config["reviews"]
        if min(num_users, num_stores, num_products, num_orders, num_reviews) < 1:
            raise CommandError("All volume overrides must be positive.")
        if num_users < MINIMUM_SEEDED_USERS:
            raise CommandError(
                f"At least {MINIMUM_SEEDED_USERS} users are required for the guaranteed seed accounts."
            )

        db_name = connection.settings_dict.get("NAME", "unknown")
        db_engine = connection.settings_dict.get("ENGINE", "unknown").split(".")[-1]

        self.stdout.write(self.style.MIGRATE_HEADING("=================================================="))
        self.stdout.write(self.style.MIGRATE_HEADING(f" Populating Fake Data (Scale: {scale.upper()})"))
        self.stdout.write(self.style.MIGRATE_HEADING("=================================================="))
        self.stdout.write(f"Target DB:   {db_engine} ({db_name})")
        self.stdout.write(f"Environment: DEBUG={settings.DEBUG} (Local/Dev Only)")
        self.stdout.write(
            f"Targets:     {num_users} users | {num_stores} stores | {num_products} products | {num_orders} orders | {num_reviews} reviews"
        )
        self.stdout.write("Seeded account passwords use the configured development password.\n")

        if options.get("clear"):
            self.clear_existing_data()

        # Step 1: Pre-hash password once
        self.stdout.write(self.style.HTTP_INFO("[1/11] Pre-computing password hash..."))
        hashed_password = make_password(password)

        # Step 2: Users & Profiles
        self.stdout.write(self.style.HTTP_INFO(f"[2/11] Generating {num_users} realistic users & wallets..."))
        users = self.seed_users(num_users, hashed_password)

        # Step 3: Stores & Merchant Wallets
        self.stdout.write(self.style.HTTP_INFO(f"[3/11] Generating {num_stores} active & official merchant stores..."))
        stores = self.seed_stores(num_stores, users)

        # Step 4: Product Catalog & Specs
        self.stdout.write(self.style.HTTP_INFO(f"[4/11] Cataloging {num_products} rich products across all categories..."))
        products = self.seed_products(num_products, stores)

        # Step 5: Coupons & Promo Codes
        self.stdout.write(self.style.HTTP_INFO("[5/11] Generating promotional coupons..."))
        coupons = self.seed_coupons(products, users)

        # Step 5b: Sales Tax Jurisdictions
        self.seed_tax_jurisdictions()

        # Step 6: Orders & Shipments
        self.stdout.write(self.style.HTTP_INFO(f"[6/11] Simulating {num_orders} historical orders & tracking journeys..."))
        orders = self.seed_orders(num_orders, users, products, coupons)

        # Step 7: Store Financial Ledgers & Tier Progression
        self.stdout.write(self.style.HTTP_INFO("[7/11] Computing merchant earnings ledgers, payouts & seller tiers..."))
        self.seed_financial_ledgers(stores, orders)

        # Step 8: Product Reviews & Rating Recalculation
        self.stdout.write(self.style.HTTP_INFO(f"[8/11] Generating {num_reviews} authenticated customer reviews..."))
        self.seed_reviews(num_reviews, users, products)

        # Step 9: Active Carts, Wishlists & Browsing History
        self.stdout.write(self.style.HTTP_INFO("[9/11] Populating active shopper carts, wishlists & recently viewed items..."))
        self.seed_carts_and_wishlists(users, products)

        # Step 10: Refunds, Affiliates & Marketers
        self.stdout.write(self.style.HTTP_INFO("[10/11] Setting up refund cases, affiliate marketers & referrals..."))
        self.seed_refunds_and_affiliates(users, products, orders)

        # Step 11: In-App Notifications & Blog Community
        self.stdout.write(self.style.HTTP_INFO("[11/11] Publishing staff announcements & notification history..."))
        self.seed_notifications_and_blog(users)

        self.seed_scenarios(users)
        # bulk_create bypasses Product post_save signals: publish the final catalog
        # after tags, reviews and all scenario products have been written.
        from product.search import enabled
        if enabled():
            transaction.on_commit(self.rebuild_product_index)
        self.print_summary(users, stores, products, orders, num_reviews)

    def rebuild_product_index(self) -> None:
        try:
            call_command("rebuild_product_index", stdout=self.stdout, stderr=self.stderr)
        except Exception as error:
            self.stderr.write(self.style.WARNING(
                f"Search indexing unavailable ({error}). Run rebuild_product_index after search recovers."))

    def clear_existing_data(self) -> None:
        self.stdout.write(self.style.WARNING("Clearing previously seeded test records..."))
        from django.db.models.signals import post_delete, post_save
        disconnected = False
        try:
            from product.signals import sync_product_to_search, remove_product_from_search
            post_save.disconnect(sync_product_to_search, sender=Product)
            post_delete.disconnect(remove_product_from_search, sender=Product)
            disconnected = True
            Notification.objects.all().delete()
            BlogComment.objects.all().delete()
            BlogContent.objects.all().delete()
            BlogPost.objects.all().delete()
            Referral.objects.all().delete()
            Redirect.objects.all().delete()
            AffiliateUrl.objects.all().delete()
            AffiliateWalletTransaction.objects.all().delete()
            AffiliateWallet.objects.all().delete()
            Marketer.objects.all().delete()
            Refund.objects.all().delete()
            CouponRedemption.objects.all().delete()
            Coupon.objects.all().delete()
            StorePayout.objects.all().delete()
            StoreEarningsLedger.objects.all().delete()
            MerchantWallet.objects.all().delete()
            Order.objects.all().delete()
            TaxJurisdiction.objects.all().delete()
            DeliveryInfo.objects.all().delete()
            CartItem.objects.all().delete()
            Cart.objects.all().delete()
            Review.objects.all().delete()
            Wishlist.objects.all().delete()
            Recent.objects.all().delete()
            Specification.objects.all().delete()
            Product.objects.all().delete()
            StoreAddress.objects.all().delete()
            StoreInfo.objects.all().delete()
            Store.objects.all().delete()
            UserWalletTransaction.objects.all().delete()
            UserWallet.objects.all().delete()
            Address.objects.all().delete()
            # Retain non-local users and existing technical super admin
            User.objects.filter(email__endswith="@proace.local").exclude(is_superuser=True).delete()
        finally:
            if disconnected:
                post_save.connect(sync_product_to_search, sender=Product)
                post_delete.connect(remove_product_from_search, sender=Product)
        self.stdout.write(self.style.SUCCESS("Clean slate achieved.\n"))

    def seed_users(self, count: int, hashed_password: str) -> List[User]:
        key_accounts = [
            ("admin@proace.local", "Alex", "Admin", "male", True, True, False),
            ("business-admin@proace.local", "Morgan", "BusinessAdmin", "female", True, False, True),
            ("staff@proace.local", "Jordan", "Staff", "male", True, False, False),
            ("merchant@proace.local", "Elena", "Merchant", "female", False, False, False),
            ("seller@proace.local", "Marcus", "Seller", "male", False, False, False),
            ("shopper@proace.local", "Taylor", "Shopper", "female", False, False, False),
            ("buyer@proace.local", "Sam", "Buyer", "male", False, False, False),
            ("blocked-staff@proace.local", "Blocked", "Staff", "male", True, False, False),
            ("unverified@proace.local", "Unverified", "Buyer", "female", False, False, False),
            ("pending-seller@proace.local", "Pending", "Seller", "female", False, False, False),
            ("blocked-seller@proace.local", "Blocked", "Seller", "male", False, False, False),
        ]

        users_to_create = []
        user_map: Dict[str, User] = {}
        existing_users = {u.email: u for u in User.objects.all()}

        # 1. Ensure well-known test accounts
        for idx, (email, first, last, gender, is_staff, is_superuser, is_business_admin) in enumerate(key_accounts):
            if email in existing_users:
                user = existing_users[email]
                if is_superuser and not user.is_superuser:
                    raise CommandError(
                        "admin@proace.local already belongs to a non-superuser account. "
                        "Verify that account manually before seeding; it was not promoted."
                    )
                user.is_staff = is_staff
                user.is_superuser = is_superuser
                user.is_business_admin = is_business_admin
                if not is_superuser:
                    user.password = hashed_password
                user.is_active = email not in {"blocked-staff@proace.local", "unverified@proace.local"}
                user.save()
                user_map[email] = user
            else:
                user = User(
                    email=email,
                    first_name=first,
                    last_name=last,
                    gender=gender,
                    phone1=f"+1202555{1000 + idx:04d}",
                    password=hashed_password,
                    is_staff=is_staff,
                    is_superuser=is_superuser,
                    is_business_admin=is_business_admin,
                    is_active=email not in {"blocked-staff@proace.local", "unverified@proace.local"},
                )
                users_to_create.append(user)

        # 2. Generate remaining realistic customers
        remaining = count - len(key_accounts)
        for i in range(max(0, remaining)):
            first, gender = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            email = f"{first.lower()}.{last.lower()}.{i + 1}@proace.local"
            if email in existing_users:
                user_map[email] = existing_users[email]
                continue
            phone_suffix = 2000 + (i % 8000)
            user = User(
                email=email,
                first_name=first,
                last_name=last,
                gender=gender,
                phone1=f"+1202555{phone_suffix:04d}",
                password=hashed_password,
                is_staff=False,
                is_superuser=False,
                is_active=True,
            )
            users_to_create.append(user)

        if users_to_create:
            created_users = User.objects.bulk_create(users_to_create)
            for u in created_users:
                user_map[u.email] = u

        all_users = list(user_map.values())

        # 3. Create Addresses and UserWallets
        addresses_to_create = []
        wallets_to_create = []
        wallet_transactions_to_create = []

        existing_user_ids_with_address = set(Address.objects.values_list("user_id", flat=True))
        existing_user_ids_with_wallet = set(UserWallet.objects.values_list("user_id", flat=True))

        for u in all_users:
            if u.pk not in existing_user_ids_with_address:
                street, city, state, zip_code, country = random.choice(US_CITIES)
                addresses_to_create.append(
                    Address(
                        user=u,
                        address=f"{random.randint(100, 9999)} {street.split(' ', 1)[1]}",
                        city=city,
                        state=state,
                        zip=zip_code,
                        country=country,
                        is_default=True,
                    )
                )

            if u.pk not in existing_user_ids_with_wallet:
                initial_balance = Decimal(str(random.choice([0.0, 25.0, 50.0, 100.0, 250.0])))
                wallet = UserWallet(user=u, balance=initial_balance)
                wallets_to_create.append(wallet)

        if addresses_to_create:
            Address.objects.bulk_create(addresses_to_create)
        if wallets_to_create:
            created_wallets = UserWallet.objects.bulk_create(wallets_to_create)
            for w in created_wallets:
                if w.balance > 0:
                    wallet_transactions_to_create.append(
                        UserWalletTransaction(
                            wallet=w,
                            transaction_type=UserWalletTransaction.CREDIT,
                            amount=w.balance,
                            source=UserWalletTransaction.SOURCE_DEPOSIT,
                            description="Welcome store credit deposit",
                            reference=f"DEP-{uuid4().hex[:8].upper()}",
                        )
                    )
            if wallet_transactions_to_create:
                UserWalletTransaction.objects.bulk_create(wallet_transactions_to_create)

        self.stdout.write(self.style.SUCCESS(f"  -> {len(all_users)} total active users & wallets ready."))
        return all_users

    def seed_stores(self, count: int, users: List[User]) -> List[Store]:
        # Assign merchant user
        merchant_user = next((u for u in users if u.email == "merchant@proace.local"), users[0])
        seller_user = next((u for u in users if u.email == "seller@proace.local"), users[1])
        admin_user = next((u for u in users if u.email == "admin@proace.local"), users[0])

        other_merchants = [u for u in users if u.is_active and not u.is_staff and u.email not in {"merchant@proace.local", "seller@proace.local", "shopper@proace.local", "buyer@proace.local", "pending-seller@proace.local", "blocked-seller@proace.local"}][:count] or [merchant_user]

        stores_to_create = []
        store_map: Dict[str, Store] = {}
        existing_stores = {s.username: s for s in Store.objects.all()}

        total_blueprints = STORE_BLUEPRINTS
        used_usernames = set(existing_stores.keys())

        for i in range(count):
            if i < len(total_blueprints):
                bp = total_blueprints[i]
                username = bp["username"]
                name = bp["name"]
                is_official = bp["is_official"]
            else:
                prefix = random.choice(["Apex", "Verve", "Prism", "Echo", "Atlas", "Summit", "Terra", "Nova", "Flux", "Aura", "Peak", "Zenith", "Sol", "Urban", "Craft"])
                noun = random.choice(["Goods", "Studio", "Labs", "Supply", "Outfit", "Collective", "Trading", "Gear", "Works", "Hub"])
                name = f"{prefix} {noun} {i + 1}"[:40]
                username = f"{prefix.lower()[:6]}-{noun.lower()[:5]}-{i + 1}"[:17]
                counter = 1
                while username in used_usernames:
                    username = f"{prefix.lower()[:5]}-{counter}-{i}"[:17]
                    counter += 1
                is_official = False

            owner = merchant_user if i < 2 else (seller_user if i == 2 else other_merchants[i % len(other_merchants)])
            if username in existing_stores:
                store = existing_stores[username]
                store.user = owner
                store.save(update_fields=["user"])
                store_map[username] = store
                used_usernames.add(username)
                continue

            used_usernames.add(username)

            status = Store.STATUS_ACTIVE
            verified_at = timezone.now() - timedelta(days=random.randint(60, 365))
            verified_by = admin_user

            store = Store(
                user=owner,
                username=username,
                name=name,
                status=status,
                is_official=is_official,
                verified_at=verified_at,
                verified_by=verified_by,
            )
            stores_to_create.append(store)

        if stores_to_create:
            created_stores = Store.objects.bulk_create(stores_to_create)
            for s in created_stores:
                store_map[s.username] = s

        all_stores = list(store_map.values())

        # Create StoreInfo, StoreAddress, and MerchantWallet
        store_infos_to_create = []
        store_addresses_to_create = []
        existing_info_stores = set(StoreInfo.objects.values_list("store_id", flat=True))
        existing_addr_stores = set(StoreAddress.objects.values_list("store_id", flat=True))

        for idx, store in enumerate(all_stores):
            bp = STORE_BLUEPRINTS[idx % len(STORE_BLUEPRINTS)]
            if store.pk not in existing_info_stores:
                avatar_id = bp.get("avatar", "1534528741775-53994a69daeb")
                banner_id = bp.get("banner", "1441986300917-64674bd600d8")
                store_infos_to_create.append(
                    StoreInfo(
                        store=store,
                        email=f"contact@{store.username}.local",
                        bio=bp.get("bio", f"Quality curated goods from {store.name}."),
                        announcement=bp.get("announcement", "Welcome to our official catalog store."),
                        avatar_url=f"https://images.unsplash.com/photo-{avatar_id}?auto=format&fit=crop&w=300&q=80",
                        banner_url=f"https://images.unsplash.com/photo-{banner_id}?auto=format&fit=crop&w=1200&q=80",
                        website=bp.get("website", f"https://{store.username}.local"),
                        twitter=f"https://twitter.com/{store.username}",
                        instagram=f"https://instagram.com/{store.username}",
                        phone1="+12025550199",
                    )
                )

            if store.pk not in existing_addr_stores:
                street, city, state, zip_code, country = US_CITIES[idx % len(US_CITIES)]
                store_addresses_to_create.append(
                    StoreAddress(
                        store=store,
                        address=street,
                        city=city,
                        state=state,
                        zip=zip_code,
                        country=country,
                        is_default=True,
                    )
                )

            # Ensure MerchantWallet exists
            wallet, _ = MerchantWallet.objects.get_or_create(
                user=store.user,
                defaults={
                    "stripe_account_id": "",
                    "stripe_details_submitted": False,
                    "stripe_payouts_enabled": False,
                    "available_balance": Decimal("0.00"),
                    "pending_balance": Decimal("0.00"),
                    "total_withdrawn": Decimal("0.00"),
                },
            )
            if wallet.stripe_account_id.startswith("acct_mock_"):
                wallet.stripe_account_id = ""
                wallet.stripe_details_submitted = False
                wallet.stripe_payouts_enabled = False
                wallet.save(update_fields=[
                    "stripe_account_id",
                    "stripe_details_submitted",
                    "stripe_payouts_enabled",
                    "updated",
                ])

        if store_infos_to_create:
            StoreInfo.objects.bulk_create(store_infos_to_create)
        if store_addresses_to_create:
            StoreAddress.objects.bulk_create(store_addresses_to_create)

        self.stdout.write(self.style.SUCCESS(f"  -> {len(all_stores)} active merchant stores ready."))
        return all_stores

    def seed_products(self, count: int, stores: List[Store]) -> List[Product]:
        products_to_create = []
        tags_per_product: List[Tuple[int, List[str]]] = []
        specs_to_create = []

        total_templates = len(PRODUCT_TEMPLATES)
        existing_count = Product.objects.count()

        for i in range(count):
            template_idx = i % total_templates
            (title_base, brand, category, price_str, discount, stock_base, image_id,
             desc, tags, weight_lbs, is_digital) = PRODUCT_TEMPLATES[template_idx]

            cycle = i // total_templates
            if cycle > 0:
                title = f"{title_base} (Edition {cycle + 1})"
                price = (Decimal(price_str) * Decimal(str(1.0 + (cycle * 0.05)))).quantize(Decimal("0.01"))
            else:
                title = title_base
                price = Decimal(price_str)

            store = stores[i % len(stores)]
            available = max(3, stock_base + random.randint(-5, 20))
            is_sold_out = (i % 25 == 0)
            if is_sold_out:
                available = 0
                label = "sold out"
            elif i % 5 == 0:
                label = "bestseller"
            elif i % 3 == 0:
                label = "new"
            else:
                label = ""

            sales = random.randint(25, 300) if not is_sold_out else random.randint(150, 600)
            sponsored = (i % 7 == 0)
            flash_sale = timezone.now() + timedelta(days=random.randint(2, 10)) if (i % 6 == 0) else None

            # Variants
            variants = []
            if category in ["sports", "outwear", "lingerie"]:
                for size in ["S", "M", "L", "XL"]:
                    variants.append({
                        "name": f"Size {size}",
                        "sku": f"SKU-{uuid4().hex[:6].upper()}-{size}",
                        "price_delta": "0.00",
                        "available": available // 4,
                    })
            elif category in ["electronics", "phones", "computing"]:
                for color in ["Midnight Black", "Space Silver", "Deep Blue"]:
                    variants.append({
                        "name": color,
                        "sku": f"SKU-{uuid4().hex[:6].upper()}-{color[:3].upper()}",
                        "price_delta": "0.00",
                        "available": available // 3,
                    })

            # Designate realistic ClickBank partner offers
            is_affiliate = (i % 11 == 0 and is_digital) or (i == 7) or (i == 19)
            product_type = "affiliate_clickbank" if is_affiliate else "standard"
            affiliate_hoplink = ""
            affiliate_vendor_nickname = ""
            affiliate_button_text = "Buy on Official Site"
            if is_affiliate:
                discount = 0
                flash_sale = None
                variants = []
                # Affiliate products represent platform-curated recommendations mapped under the official catalog store
                official_store = next((s for s in stores if s.is_official), stores[0])
                aff_nick = getattr(settings, "CLICKBANK_AFFILIATE_NICKNAME", "proace") or "proace"
                vendor_nick = "proace-demo-vendor"
                affiliate_hoplink = f"https://hop.clickbank.net/?affiliate={aff_nick}&vendor={vendor_nick}"
                affiliate_vendor_nickname = vendor_nick
                affiliate_button_text = random.choice([
                    "Buy on Official Site",
                    "Claim Special Offer",
                    "Access Official Portal",
                ])

            product = Product(
                store=store,
                title=title[:225],
                description=desc,
                image_url=f"https://images.unsplash.com/photo-{image_id}?auto=format&fit=crop&w=900&q=80",
                brand=brand,
                price=price,
                discount=discount,
                available=available,
                category=category,
                label=label,
                visibility=True,
                average_rating=Decimal("4.50"),
                sales=sales,
                sponsored=sponsored,
                weight=Decimal(str(weight_lbs)),
                is_digital=is_digital,
                digital_file_url="https://downloads.proace.local/files/spec-sheet.pdf" if is_digital else "",
                flash_sale_end=flash_sale,
                variants=variants,
                product_type=product_type,
                affiliate_hoplink=affiliate_hoplink,
                affiliate_vendor_nickname=affiliate_vendor_nickname,
                affiliate_button_text=affiliate_button_text,
            )
            products_to_create.append((product, tags))

        # Bulk create products
        raw_products = [p[0] for p in products_to_create]
        created_products = Product.objects.bulk_create(raw_products)

        # Attach specifications and tags
        for idx, p in enumerate(created_products):
            tags = products_to_create[idx][1]
            p.tags.add(*tags)

            specs_to_create.append(
                Specification(
                    product=p,
                    serial=f"SN-{p.pk:06d}-{uuid4().hex[:6].upper()}",
                    attributes=f"Certified {p.brand} hardware build with 1-year global limited warranty.",
                    height=Decimal(str(round(random.uniform(2.0, 25.0), 2))),
                    width=Decimal(str(round(random.uniform(5.0, 35.0), 2))),
                    breadth=Decimal(str(round(random.uniform(1.0, 15.0), 2))),
                    weight=Decimal(str(min(round(float(p.weight), 2), 99.99))),
                    color=random.choice(["Matte Black", "Space Gray", "Pure White", "Navy Blue", "Olive"]),
                )
            )

        if specs_to_create:
            Specification.objects.bulk_create(specs_to_create)

        self.stdout.write(self.style.SUCCESS(f"  -> {len(created_products)} catalog products & specifications ready."))
        return list(Product.objects.all()[:count])

    def seed_coupons(self, products: List[Product], users: Optional[List[User]] = None) -> List[Coupon]:
        coupons = []
        admin_staff = [
            u for u in (users or [])
            if getattr(u, 'is_staff', False) or getattr(u, 'is_superuser', False) or getattr(u, 'is_business_admin', False)
        ]
        if not admin_staff:
            admin_staff = list(User.objects.filter(models.Q(is_staff=True) | models.Q(is_superuser=True) | models.Q(is_business_admin=True), is_active=True))

        for idx, bp in enumerate(COUPON_BLUEPRINTS):
            code = bp["code"]
            product = products[0] if bp["type"] == "product" else None
            creator = admin_staff[idx % len(admin_staff)] if admin_staff else None
            coupon, created = Coupon.objects.get_or_create(
                code=code,
                defaults={
                    "valid_to": timezone.now() + timedelta(days=90),
                    "discount": bp["discount"],
                    "num_available": bp["available"],
                    "num_used": random.randint(10, 80),
                    "active": True,
                    "type": bp["type"],
                    "category": bp["category"],
                    "product": product,
                    "created_by": creator,
                },
            )
            if not created and coupon.created_by is None and creator:
                coupon.created_by = creator
                coupon.save(update_fields=["created_by"])
            coupons.append(coupon)

        if admin_staff:
            Coupon.objects.filter(created_by__isnull=True).update(created_by=admin_staff[0])

        return coupons

    def seed_tax_jurisdictions(self) -> None:
        self.stdout.write(self.style.HTTP_INFO("  -> Initializing US sales tax jurisdictions..."))
        jurisdictions = [
            TaxJurisdiction(
                country="US",
                state=entry["state"],
                postal_code="",
                name=entry["name"],
                rate=entry["rate"],
                tax_shipping=entry["tax_shipping"],
                tax_digital=entry["tax_digital"],
                is_active=True,
            )
            for entry in DEFAULT_US_JURISDICTIONS
        ]
        TaxJurisdiction.objects.bulk_create(jurisdictions, ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS(f"  -> {len(jurisdictions)} tax jurisdictions active."))

    def seed_orders(
        self,
        count: int,
        users: List[User],
        products: List[Product],
        coupons: List[Coupon],
    ) -> List[Order]:
        shoppers = [u for u in users if u.is_active and not (u.is_staff or u.email in ["merchant@proace.local", "seller@proace.local", "pending-seller@proace.local", "blocked-seller@proace.local"])]
        if not shoppers:
            shoppers = users

        user_addresses = {a.user_id: a for a in Address.objects.filter(user__in=shoppers, is_default=True)}

        status_pool = (
            ["delivered"] * 60 +
            ["shipped"] * 18 +
            ["confirmed"] * 10 +
            ["pending"] * 7 +
            ["refunded"] * 3 +
            ["cancelled"] * 2
        )

        orders_to_create = []
        carts_to_create = []
        deliveries_to_create = []
        raw_order_data = []

        now = timezone.now()
        for i in range(count):
            shopper = random.choice(shoppers)
            address = user_addresses.get(shopper.pk)
            if not address:
                address = Address.objects.create(
                    user=shopper,
                    address="100 N Tampa Street",
                    city="Tampa",
                    state="Florida",
                    zip="33602",
                    country="United States",
                    is_default=True,
                )
                user_addresses[shopper.pk] = address

            days_ago = random.randint(1, 90)
            order_time = now - timedelta(days=days_ago, hours=random.randint(1, 23), minutes=random.randint(0, 59))
            status = ["delivered", "shipped", "confirmed", "pending", "refunded", "cancelled"][i] if i < 6 else random.choice(status_pool)

            cart = Cart(user=shopper, ordered=True)
            carts_to_create.append(cart)

            delivery_method = random.choice(["home delivery", "pick up"])
            delivery_type = random.choice(["standard", "express"])
            shipping_fee = 0 if delivery_method == "pick up" else (3500 if delivery_type == "express" else 1500)

            delivery = DeliveryInfo(
                user=shopper,
                method=delivery_method,
                address=address,
                total=shipping_fee,
                delivery_type=delivery_type,
            )
            deliveries_to_create.append(delivery)

            # Choose 1 to 3 items
            selected_products = random.sample(products, k=random.randint(1, 3))
            raw_order_data.append((shopper, address, order_time, status, selected_products, shipping_fee))

        # Bulk create carts and deliveries
        created_carts = Cart.objects.bulk_create(carts_to_create)
        created_deliveries = DeliveryInfo.objects.bulk_create(deliveries_to_create)

        cart_items_to_create = []
        orders_to_bulk = []

        for i, (shopper, address, order_time, status, selected_products, shipping_fee) in enumerate(raw_order_data):
            cart = created_carts[i]
            delivery = created_deliveries[i]
            order_id = f"ORD{i + 1:05d}{uuid4().hex[:4].upper()}"[:15]

            items_snapshot = []
            subtotal = Decimal("0.00")

            for prod in selected_products:
                qty = random.randint(1, 2)
                cart_items_to_create.append(CartItem(cart=cart, product=prod, quantity=qty))

                unit_price = (prod.price * Decimal(100 - prod.discount) / 100).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
                line_total = unit_price * qty
                subtotal += line_total

                items_snapshot.append({
                    "product": prod.pk,
                    "store": prod.store_id,
                    "title": prod.title,
                    "image": prod.image_url,
                    "quantity": qty,
                    "unit_price": str(unit_price),
                    "is_digital": prod.is_digital,
                })

            shipping_decimal = (Decimal(shipping_fee) / Decimal("100")).quantize(Decimal(".01"))
            tax_breakdown = calculate_tax(
                items=items_snapshot,
                subtotal=subtotal,
                shipping_fee=shipping_decimal,
                address=address,
            )
            tax = tax_breakdown.amount
            total = subtotal + tax + shipping_decimal

            # Tracking metadata
            carrier = random.choice(["USPS", "FedEx", "UPS", "DHL"])
            tracking_number = f"9400{random.randint(100000000000, 999999999999)}"

            shipped_at = None
            delivered_at = None
            tracking_events = []

            if status in ["shipped", "delivered", "refunded"]:
                shipped_at = order_time + timedelta(hours=random.randint(12, 36))
                tracking_events.append({
                    "status": "Label Created",
                    "description": f"Shipping label created with {carrier}.",
                    "timestamp": shipped_at.isoformat(),
                })
                tracking_events.append({
                    "status": "In Transit",
                    "description": f"Package arrived at {carrier} regional sort facility.",
                    "timestamp": (shipped_at + timedelta(hours=14)).isoformat(),
                })

            if status in ["delivered", "refunded"]:
                delivered_at = shipped_at + timedelta(hours=random.randint(24, 72))
                tracking_events.append({
                    "status": "Out for Delivery",
                    "description": f"Out for delivery with {carrier} courier.",
                    "timestamp": (delivered_at - timedelta(hours=4)).isoformat(),
                })
                tracking_events.append({
                    "status": "Delivered",
                    "description": "Package safely delivered to resident porch/reception.",
                    "timestamp": delivered_at.isoformat(),
                })

            coupon_code = "WELCOME10" if (i % 8 == 0) else ""

            order = Order(
                user=shopper,
                cart=cart,
                delivery=delivery,
                orderId=order_id,
                coupon_code=coupon_code,
                tax=tax,
                tax_snapshot=tax_breakdown.to_dict(),
                status=status,
                ordered=True,
                payment_type='user_wallet',
                paid_total=total,
                wallet_paid=total,
                refunded_total=total if status in {'cancelled', 'refunded'} else Decimal('0'),
                wallet_refunded_total=total if status in {'cancelled', 'refunded'} else Decimal('0'),
                subtotal=subtotal,
                total=total,
                items_snapshot=items_snapshot,
                address_snapshot={
                    "address": address.address,
                    "city": address.city,
                    "state": address.state,
                    "country": address.country,
                    "zip": address.zip,
                },
                carrier=carrier,
                tracking_number=tracking_number,
                shipped_at=shipped_at,
                delivered_at=delivered_at,
                tracking_events=tracking_events,
            )
            orders_to_bulk.append((order, order_time))

        if cart_items_to_create:
            CartItem.objects.bulk_create(cart_items_to_create)

        created_orders = Order.objects.bulk_create([o[0] for o in orders_to_bulk])

        # Backdate order created times
        for idx, created_ord in enumerate(created_orders):
            past_time = orders_to_bulk[idx][1]
            Order.objects.filter(pk=created_ord.pk).update(created=past_time)

        self.stdout.write(self.style.SUCCESS(f"  -> {len(created_orders)} historical orders simulated."))
        return list(Order.objects.all().order_by("-pk")[:count])

    def seed_financial_ledgers(self, stores: List[Store], orders: List[Order]):
        store_map = {s.pk: s for s in stores}
        user_wallets = {mw.user_id: mw for mw in MerchantWallet.objects.all()}

        ledger_entries_to_create = []
        payouts_to_create = []

        now = timezone.now()
        platform_fee_rate = Decimal("0.04")

        # Accumulate store earnings
        store_sales_agg: Dict[int, Decimal] = {s.pk: Decimal("0.00") for s in stores}

        for order in orders:
            if order.status in ["cancelled"]:
                continue

            order_date = order.created
            is_past_refund_window = (now - order_date) > timedelta(days=7)

            for item in order.items_snapshot:
                store_id = item.get("store")
                if not store_id or store_id not in store_map:
                    continue

                store = store_map[store_id]
                wallet = user_wallets.get(store.user_id)
                if not wallet:
                    continue

                gross = Decimal(item.get("unit_price", "0.00")) * int(item.get("quantity", 1))
                fee = (gross * platform_fee_rate).quantize(Decimal(".01"))
                net = gross - fee

                entry_status = StoreEarningsLedger.STATUS_AVAILABLE if is_past_refund_window else StoreEarningsLedger.STATUS_PENDING

                store_sales_agg[store_id] += gross

                entry = StoreEarningsLedger(
                    wallet=wallet,
                    store=store,
                    order=order,
                    entry_type=StoreEarningsLedger.TYPE_SALE,
                    gross_amount=gross,
                    fee_amount=fee,
                    net_amount=net,
                    status=entry_status,
                    available_at=order_date + timedelta(days=7),
                    cleared_at=order_date + timedelta(days=7) if is_past_refund_window else None,
                    description=f"Revenue from Order #{order.orderId}",
                    reference=f"SALE-{order.orderId}-{uuid4().hex[:4].upper()}",
                )
                ledger_entries_to_create.append((entry, order_date))

        # Bulk create ledgers and set past dates
        created_ledgers = StoreEarningsLedger.objects.bulk_create([e[0] for e in ledger_entries_to_create])
        for idx, ledger in enumerate(created_ledgers):
            past_date = ledger_entries_to_create[idx][1]
            StoreEarningsLedger.objects.filter(pk=ledger.pk).update(created=past_date)

        # Update MerchantWallet balances and generate realistic payouts
        for wallet in MerchantWallet.objects.all():
            from store.services import calculate_merchant_financials
            financials = calculate_merchant_financials(wallet.user)
            available = Decimal(financials['available_balance'])
            pending = Decimal(financials['pending_balance'])
            withdrawn = Decimal(financials['total_withdrawn'])
            has_demo_payout = StorePayout.objects.filter(
                wallet=wallet,
                notes="Automated weekly earnings clearing payout via Stripe Connect.",
            ).exists()
            if available > Decimal("500.00") and not has_demo_payout:
                payout_amt = (available * Decimal("0.60")).quantize(Decimal(".01"))
                withdrawn += payout_amt
                available -= payout_amt

                payouts_to_create.append(
                    StorePayout(
                        wallet=wallet,
                        amount=payout_amt,
                        status=StorePayout.STATUS_COMPLETED,
                        payout_method=StorePayout.METHOD_STRIPE_CONNECT,
                        account_details={"routing_last4": "6789", "account_last4": "4321", "bank_name": "JPMorgan Chase"},
                        reference=f"PO-{uuid4().hex[:8].upper()}",
                        processed_at=now - timedelta(days=3),
                        notes="Automated weekly earnings clearing payout via Stripe Connect.",
                    )
                )

            wallet.available_balance = available
            wallet.pending_balance = pending
            wallet.total_withdrawn = withdrawn
            wallet.save()

        if payouts_to_create:
            StorePayout.objects.bulk_create(payouts_to_create)

        self.stdout.write(self.style.SUCCESS(f"  -> {len(created_ledgers)} financial transactions and merchant payouts logged."))

    def seed_reviews(self, count: int, users: List[User], products: List[Product]):
        shoppers = [u for u in users if not u.is_superuser]
        reviews_to_create = []
        reviewed_pairs = set(Review.objects.values_list("user_id", "product_id"))

        now = timezone.now()
        shuffled_products = list(products)
        random.shuffle(shuffled_products)

        product_ratings_map: Dict[int, List[int]] = {p.pk: [] for p in products}

        created_count = 0
        for p in shuffled_products:
            num_for_this_prod = random.randint(1, 6)
            for _ in range(num_for_this_prod):
                if created_count >= count:
                    break
                shopper = random.choice(shoppers)
                pair = (shopper.pk, p.pk)
                if pair in reviewed_pairs:
                    continue
                reviewed_pairs.add(pair)

                # Distribution: 70% 5-star, 20% 4-star, 7% 3-star, 3% 1-2 star
                roll = random.random()
                if roll < 0.70:
                    rating = 5
                    label, comment = random.choice(REVIEW_COMMENTS_HIGH)
                elif roll < 0.90:
                    rating = 4
                    label, comment = random.choice(REVIEW_COMMENTS_HIGH)
                elif roll < 0.97:
                    rating = 3
                    label, comment = random.choice(REVIEW_COMMENTS_MID)
                else:
                    rating = random.choice([1, 2])
                    label, comment = random.choice(REVIEW_COMMENTS_LOW)

                product_ratings_map[p.pk].append(rating)

                review_time = now - timedelta(days=random.randint(1, 60))
                reviews_to_create.append((
                    Review(
                        user=shopper,
                        product=p,
                        label=label,
                        comment=comment,
                        rating=rating,
                        images=[],
                    ),
                    review_time,
                ))
                created_count += 1

            if created_count >= count:
                break

        created_reviews = Review.objects.bulk_create([r[0] for r in reviews_to_create])
        for idx, r in enumerate(created_reviews):
            Review.objects.filter(pk=r.pk).update(created=reviews_to_create[idx][1])

        # Recalculate average ratings for reviewed products
        for prod_id, ratings in product_ratings_map.items():
            if ratings:
                avg = round(sum(ratings) / len(ratings), 2)
                Product.objects.filter(pk=prod_id).update(average_rating=Decimal(str(avg)))

        self.stdout.write(self.style.SUCCESS(f"  -> {len(created_reviews)} verified customer reviews populated."))

    def seed_carts_and_wishlists(self, users: List[User], products: List[Product]):
        shopper = next((u for u in users if u.email == "shopper@proace.local"), users[0])
        other_shoppers = random.sample(users, k=min(10, len(users)))

        active_users = list(set([shopper] + other_shoppers))

        cart_items_to_create = []
        wishlists_to_create = []
        recents_to_create = []

        existing_wishlists = set(Wishlist.objects.values_list("user_id", "product_id"))

        for u in active_users:
            cart, _ = Cart.objects.get_or_create(user=u, ordered=False)
            cart.cart_items.all().delete()

            selected = random.sample(products, k=random.randint(2, 4))
            for p in selected:
                cart_items_to_create.append(CartItem(cart=cart, product=p, quantity=random.randint(1, 2)))

            # Wishlists
            wish_prods = random.sample(products, k=random.randint(3, 6))
            for wp in wish_prods:
                if (u.pk, wp.pk) not in existing_wishlists:
                    wishlists_to_create.append(Wishlist(user=u, product=wp, liked=True))
                    existing_wishlists.add((u.pk, wp.pk))

            # Recents
            recent_prods = random.sample(products, k=random.randint(4, 8))
            for rp in recent_prods:
                recents_to_create.append(Recent(user=u, product=rp))

        if cart_items_to_create:
            CartItem.objects.bulk_create(cart_items_to_create)
        if wishlists_to_create:
            Wishlist.objects.bulk_create(wishlists_to_create)
        if recents_to_create:
            Recent.objects.bulk_create(recents_to_create)

        self.stdout.write(self.style.SUCCESS(f"  -> Active shopping carts & wishlists populated."))

    def seed_refunds_and_affiliates(self, users: List[User], products: List[Product], orders: List[Order]):
        # Refunds
        refunds_to_create = []
        eligible_orders = [o for o in orders if o.status in ["refunded", "delivered"]][:15]

        reasons = [
            "Item arrived slightly damaged during carrier transit.",
            "Wrong size selected by mistake; requested store credit exchange.",
            "Color variation differed slightly from online photographs.",
            "Order arrived after event deadline; item returned unopened.",
        ]

        for idx, ord_obj in enumerate(eligible_orders):
            is_accepted = (ord_obj.status == "refunded")
            refund_type = Refund.REFUND_TYPE_STORE_CREDIT if (idx % 2 == 0) else Refund.REFUND_TYPE_ORIGINAL_PAYMENT
            refunds_to_create.append(
                Refund(
                    email=ord_obj.user.email,
                    order=ord_obj,
                    reason=random.choice(reasons),
                    accepted=is_accepted,
                    refund_type=refund_type,
                )
            )

        if refunds_to_create:
            Refund.objects.bulk_create(refunds_to_create)

        # Affiliates
        marketer_user = next((u for u in users if u.email == "seller@proace.local"), users[0])
        marketer, _ = Marketer.objects.get_or_create(
            user=marketer_user,
            defaults={"name": "TechPulse Media Reviews", "marketer_id": "techpulse26"},
        )

        aff_wallet, _ = AffiliateWallet.objects.get_or_create(
            user=marketer_user,
            defaults={"balance": Decimal("340.50")},
        )

        for p in products[:3]:
            url_obj, _ = AffiliateUrl.objects.get_or_create(
                marketer=marketer,
                product=p,
                defaults={
                    "identifier": f"review-{p.pk}",
                    "abs_url": f"https://proace.local/aff/{marketer.marketer_id}/{p.pk}/",
                    "active": True,
                },
            )
            Redirect.objects.get_or_create(
                urlId=url_obj,
                product_url=f"https://proace.local/products/{p.pk}",
                defaults={
                    "refferal_url": f"tp-{p.pk:04d}"[:15],
                    "click_rate": random.randint(45, 620),
                },
            )

        self.stdout.write(self.style.SUCCESS(f"  -> Refunds and affiliate tracking pipelines configured."))

    def seed_notifications_and_blog(self, users: List[User]):
        staff_user = next((u for u in users if u.email == "staff@proace.local"), users[0])
        shopper = next((u for u in users if u.email == "shopper@proace.local"), users[0])
        merchant = next((u for u in users if u.email == "merchant@proace.local"), users[0])

        # Staff Blog
        for title, content_text in BLOG_POST_BLUEPRINTS:
            post, created = BlogPost.objects.get_or_create(staff=staff_user, title=title)
            if created:
                post.tags.add("lifestyle", "hardware", "engineering")
                BlogContent.objects.create(blog_id=post, content=content_text)
                BlogComment.objects.create(
                    post=post,
                    user=shopper,
                    body="Incredible breakdown! Really appreciate the transparent insights into quality standards.",
                )

        # Notifications
        user_ct = ContentType.objects.get_for_model(User)
        notifications_to_create = [
            Notification(
                recipient=shopper,
                actor_content_type=user_ct,
                actor_object_id=str(staff_user.pk),
                verb="Order Confirmed",
                description="Your recent order #ORD00042 has been confirmed and is being prepared.",
                level="info",
                unread=False,
            ),
            Notification(
                recipient=shopper,
                actor_content_type=user_ct,
                actor_object_id=str(staff_user.pk),
                verb="Package Shipped",
                description="Your package has departed the fulfillment center via USPS Priority.",
                level="success",
                unread=True,
            ),
            Notification(
                recipient=merchant,
                actor_content_type=user_ct,
                actor_object_id=str(staff_user.pk),
                verb="Weekly Payout Completed",
                description="Direct deposit payout of $1,420.50 transferred to your designated bank account.",
                level="success",
                unread=False,
            ),
        ]
        Notification.objects.bulk_create(notifications_to_create)

        self.stdout.write(self.style.SUCCESS(f"  -> In-app notifications & blog articles published."))

    def seed_scenarios(self, users):
        """Stable edge cases independent of random volume and scale presets."""
        accounts = {user.email: user for user in users}
        admin = accounts["admin@proace.local"]
        merchant = accounts["merchant@proace.local"]
        cases = [
            ("demo-starter", "Starter", merchant, Store.STATUS_ACTIVE, True, "0"),
            ("demo-booster", "Booster", merchant, Store.STATUS_ACTIVE, True, "5000"),
            ("demo-accelerator", "Accelerator", merchant, Store.STATUS_ACTIVE, True, "25000"),
            ("demo-power", "Power Seller", merchant, Store.STATUS_ACTIVE, True, "100000"),
            ("demo-mega", "Mega Seller", merchant, Store.STATUS_ACTIVE, True, "500000"),
            ("demo-legendary", "Legendary Seller", merchant, Store.STATUS_ACTIVE, True, "1000000"),
            ("demo-pending", "Pending Verification", accounts["pending-seller@proace.local"], Store.STATUS_PENDING, False, "0"),
            ("demo-unverified", "Unverified Store", accounts["pending-seller@proace.local"], Store.STATUS_ACTIVE, False, "0"),
            ("demo-blocked", "Blocked Store", accounts["blocked-seller@proace.local"], Store.STATUS_BLOCKED, True, "0"),
            ("demo-empty", "Empty Store", merchant, Store.STATUS_ACTIVE, True, "0"),
        ]
        now = timezone.now()
        for username, name, owner, status, verified, gross in cases:
            store, _ = Store.objects.update_or_create(username=username, defaults={
                "name": name, "user": owner, "status": status, "is_official": False,
                "verified_at": now if verified else None, "verified_by": admin if verified else None,
                "blocked_at": now if status == Store.STATUS_BLOCKED else None,
                "blocked_by": admin if status == Store.STATUS_BLOCKED else None,
                "blocked_reason": "Demo moderation restriction" if status == Store.STATUS_BLOCKED else "",
            })
            StoreInfo.objects.get_or_create(store=store, defaults={"email": owner.email, "bio": name + " demo scenario"})
            StoreAddress.objects.get_or_create(store=store, is_default=True, defaults={
                "address": "100 N Tampa Street", "city": "Tampa", "state": "Florida", "country": "United States", "zip": "33602"})
            wallet, _ = MerchantWallet.objects.get_or_create(user=owner)
            gross = Decimal(gross)
            fee = (gross * Decimal("0.04")).quantize(Decimal("0.01"))
            entry, created = StoreEarningsLedger.objects.update_or_create(store=store, reference="DEMO-TIER-" + username, defaults={
                "wallet": wallet, "entry_type": StoreEarningsLedger.TYPE_SALE,
                "gross_amount": gross, "fee_amount": fee, "net_amount": gross - fee,
                "status": StoreEarningsLedger.STATUS_AVAILABLE, "available_at": now, "cleared_at": now,
                "description": "Historical demo sales for seller badge coverage",
            })
            if created:
                wallet.available_balance += entry.net_amount
                wallet.save(update_fields=["available_balance"])
            if username == "demo-empty":
                continue
            for index, (label, stock, visible) in enumerate([
                ("bestseller", 40, True), ("new", 2, True), ("sold out", 0, True), ("", 20, False),
            ]):
                Product.objects.update_or_create(store=store, title=f"{name} sample {index + 1}", defaults={
                    "description": "Demo product for stock, labels and visibility scenarios.",
                    "brand": "ProAce Demo", "category": "electronics", "price": Decimal("99.00"),
                    "discount": 10 if index == 0 else 0, "available": stock, "visibility": visible,
                    "label": label, "image_url": "https://images.unsplash.com/photo-1546435770-a3e426bf472b?auto=format&fit=crop&w=900&q=80",
                })
        self.stdout.write(self.style.SUCCESS("Scenario stores ready: demo-{starter,booster,accelerator,power,mega,legendary,pending,unverified,blocked,empty}."))
        self.stdout.write("Additional accounts: pending-seller@proace.local, blocked-seller@proace.local; blocked-staff@proace.local and unverified@proace.local intentionally cannot log in.")

    def print_summary(
        self,
        users: List[User],
        stores: List[Store],
        products: List[Product],
        orders: List[Order],
        reviews_count: int,
    ) -> None:
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 65))
        self.stdout.write(self.style.SUCCESS("  DATABASE POPULATION COMPLETED SUCCESSFULLY"))
        self.stdout.write(self.style.SUCCESS("=" * 65))
        self.stdout.write(f"Total Users:               {len(users)}")
        self.stdout.write(f"Total Stores:              {Store.objects.count()}")
        self.stdout.write(f"Total Products:            {Product.objects.count()}")
        self.stdout.write(f"Total Orders Simulated:    {len(orders)}")
        self.stdout.write(f"Total Product Reviews:     {reviews_count}")
        self.stdout.write(f"Total Coupons:             {Coupon.objects.count()}")
        self.stdout.write(f"Total Ledgers:             {StoreEarningsLedger.objects.count()}")
        self.stdout.write(f"Total Payouts:             {StorePayout.objects.count()}")
        self.stdout.write("-" * 65)
        self.stdout.write(self.style.MIGRATE_LABEL("Ready-to-Use Development Accounts:"))
        self.stdout.write("  - Super Admin:     admin@proace.local           (Full Staff & Superuser rights)")
        self.stdout.write("  - Business Admin:  business-admin@proace.local  (Staff & Business Administrator rights)")
        self.stdout.write("  - Staff Member:    staff@proace.local           (Staff moderation & store audit rights)")
        self.stdout.write("  - Flagship Vendor: merchant@proace.local        (Owns ProAce Select & Aura Audio)")
        self.stdout.write("  - Active Seller:   seller@proace.local          (Owns Apex Athletics (single store))")
        self.stdout.write("  - Active Shopper:  shopper@proace.local         (Has cart items, orders, addresses)")
        self.stdout.write("  - Regular Buyer:   buyer@proace.local           (Customer account)")
        self.stdout.write("  Use the password supplied to --password or configured in the environment.")
        self.stdout.write("-" * 65)
        self.stdout.write(self.style.SUCCESS("You can now start local/dev servers and log into the client or API!\n"))
