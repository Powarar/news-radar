"""
Keyword-based topic classifier — fallback when external AI API is unavailable.
Returns the same format as the HF classifier: {topic: score}.
"""

import re

KEYWORDS: dict[str, list[str]] = {
    "politics": [
        "политик", "парламент", "правительств", "президент", "выбор", "депутат",
        "закон", "министр", "санкц", "дипломат", "кремл", "госдум", "сенат",
        "оппозиц", "партия", "референдум", "конституц", "государств", "власт",
        "саммит", "переговор", "соглашен", "договор", "визит", "встреч",
        "путин", "зеленск", "трамп", "байден", "макрон", "шольц",
        "election", "government", "president", "parliament", "senate", "congress",
        "democrat", "republican", "policy", "diplomat", "sanction",
        "summit", "negotiations", "treaty", "ceasefire", "bilateral", "foreign minister",
        "zelensky", "putin", "trump", "biden", "macron",
    ],
    "military": [
        "армия", "войск", "военн", "удар", "обстрел", "наступлен", "оборон",
        "фронт", "бригад", "батальон", "ракет", "дрон", "беспилотн", "нато",
        "мобилизац", "генерал", "офицер", "потер", "взрыв", "бомб",
        "крушен", "катастроф", "самолёт упал", "сбит",
        "military", "army", "troops", "attack", "defense", "weapon", "missile",
        "drone", "nato", "combat", "soldier", "war", "conflict",
        "bomber", "warplane", "aircraft crash", "airstrike", "artillery",
        "explosion", "blast", "shelling", "ammunition", "nuclear",
    ],
    "technology": [
        "технолог", "искусственн интеллект", "нейросет", "программ", "разработ",
        "стартап", "цифров", "платформ", "приложен", "смартфон", "интернет",
        "облак", "кибер", "хакер", "процессор", "чипс", "робот",
        "ai", "artificial intelligence", "software", "startup", "digital",
        "cybersecurity", "cloud", "blockchain", "crypto", "tech", "app",
    ],
    "health": [
        "здоровь", "болезн", "лечен", "медицин", "врач", "больниц", "вакцин",
        "пандем", "вирус", "инфекц", "онкол", "рак", "препарат", "фармацевт",
        "здравоохранен", "эпидем", "пациент",
        "health", "medical", "hospital", "vaccine", "disease", "treatment",
        "cancer", "virus", "pandemic", "doctor", "medicine",
    ],
    "science": [
        "наук", "исследован", "учён", "открыт", "эксперимент", "физик",
        "химия", "биолог", "генетик", "космос", "планет", "астроном",
        "квантов", "ядерн", "лаборатор",
        "science", "research", "discovery", "experiment", "physics",
        "biology", "genetics", "space", "nasa", "astronomy", "quantum",
    ],
    "business": [
        "бизнес", "компани", "рынок", "акци", "инвест", "экономик", "банк",
        "финанс", "прибыл", "выручк", "ввп", "инфляц", "бирж", "торгов",
        "экспорт", "импорт", "слияни", "сделк", "миллиард", "миллион",
        "business", "company", "market", "stock", "invest", "economy",
        "bank", "finance", "profit", "revenue", "trade", "merger",
    ],
    "sports": [
        "спорт", "футбол", "хоккей", "баскетбол", "теннис", "олимпиад",
        "чемпионат", "турнир", "матч", "команд", "игрок", "тренер",
        "победа", "поражен", "гол", "очко",
        "sport", "football", "soccer", "hockey", "basketball", "tennis",
        "olympic", "championship", "tournament", "match", "team", "player",
    ],
    "culture": [
        "культур", "кино", "фильм", "музык", "театр", "выставк", "искусств",
        "книг", "литератур", "концерт", "фестивал", "режиссёр", "актёр",
        "художник", "музей", "галере",
        "culture", "film", "movie", "music", "theater", "art", "book",
        "concert", "festival", "director", "actor", "museum",
    ],
    "environment": [
        "экологи", "климат", "природ", "загрязнен", "выброс", "co2",
        "парников", "лес", "океан", "вид животн", "возобновляем", "солнечн",
        "ветров", "зелён", "наводнен", "потоп", "паводк", "шторм", "землетряс",
        "пожар", "засух", "ураган",
        "environment", "climate", "nature", "pollution", "emission",
        "renewable", "solar", "wind", "forest", "ocean", "green",
        "flood", "flooding", "storm", "hurricane", "earthquake", "wildfire",
        "drought", "disaster", "heatwave",
    ],
}

_BASE_SCORE = 0.6
_PER_MATCH = 0.08


def classify_keywords(text: str) -> dict[str, float]:
    text_lower = text.lower()
    scores: dict[str, float] = {}

    for topic, keywords in KEYWORDS.items():
        matches = sum(
            1 for kw in keywords
            if re.search(r"\b" + re.escape(kw), text_lower)
        )
        if matches > 0:
            score = min(_BASE_SCORE + (matches - 1) * _PER_MATCH, 0.95)
            scores[topic] = round(score, 3)

    return scores
