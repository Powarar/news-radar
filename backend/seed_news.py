"""
Заполняет БД тестовыми данными: источники, новости, юзер, реакции.

Запуск:
  docker compose exec backend python seed_news.py

Тестовый аккаунт:
  email: test@newsradar.dev
  password: testpass123
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User, UserTopicPreference
from app.models.source import Source, SourceType
from app.models.news import NewsItem, NewsReaction, ReactionType

SOURCES = [
    {"name": "Meduza", "url": "https://t.me/meduzalive", "language": "ru"},
    {"name": "BBC Русская служба", "url": "https://t.me/bbcrussian", "language": "ru"},
    {"name": "РБК", "url": "https://t.me/rbc_news", "language": "ru"},
    {"name": "TechCrunch", "url": "https://t.me/techcrunch", "language": "en"},
]

NEWS = [
    {
        "source_url": "https://t.me/meduzalive",
        "title": "ЕС продлил санкции против России ещё на шесть месяцев",
        "body": "Совет Европейского союза принял решение о продлении экономических санкций против России ещё на шесть месяцев. Ограничительные меры, введённые в связи с продолжающимся конфликтом на Украине, остаются в силе. Следующий пересмотр запланирован на октябрь.",
        "url": "https://t.me/meduzalive/50001",
        "language": "ru",
        "topics": '{"politics": 0.95, "business": 0.4}',
        "importance_score": 0.82,
        "minutes_ago": 15,
        "reaction": "like",
    },
    {
        "source_url": "https://t.me/meduzalive",
        "title": "В Москве прошли обыски у известного журналиста",
        "body": "Силовые структуры провели обыски в квартире журналиста-расследователя Михаила Соколова. По данным источников, мероприятия связаны с уголовным делом о распространении «заведомо ложной информации» о действиях армии.",
        "url": "https://t.me/meduzalive/50002",
        "language": "ru",
        "topics": '{"politics": 0.9}',
        "importance_score": 0.75,
        "minutes_ago": 40,
        "reaction": "like",
    },
    {
        "source_url": "https://t.me/bbcrussian",
        "title": "Украина получит новый пакет военной помощи от США",
        "body": "Администрация США объявила о выделении очередного пакета военной помощи Украине на сумму 800 миллионов долларов. В пакет входят артиллерийские снаряды, системы ПВО и бронетехника. Поставки начнутся в ближайшие недели.",
        "url": "https://t.me/bbcrussian/12001",
        "language": "ru",
        "topics": '{"military": 0.95, "politics": 0.7}',
        "importance_score": 0.88,
        "minutes_ago": 60,
        "reaction": "like",
    },
    {
        "source_url": "https://t.me/bbcrussian",
        "title": "Цены на нефть выросли на фоне решения ОПЕК+",
        "body": "Котировки нефти марки Brent поднялись выше 90 долларов за баррель после того, как страны ОПЕК+ объявили о сокращении добычи на 500 тысяч баррелей в сутки. Решение вступает в силу с мая и вызвало волатильность на рынках.",
        "url": "https://t.me/bbcrussian/12002",
        "language": "ru",
        "topics": '{"business": 0.9, "politics": 0.3}',
        "importance_score": 0.71,
        "minutes_ago": 90,
        "reaction": "dislike",
    },
    {
        "source_url": "https://t.me/rbc_news",
        "title": "ЦБ оставил ключевую ставку на уровне 16%",
        "body": "Банк России по итогам заседания совета директоров сохранил ключевую ставку на уровне 16% годовых. Регулятор сослался на сохраняющееся инфляционное давление и неопределённость на внешних рынках. Следующее заседание запланировано на июнь.",
        "url": "https://t.me/rbc_news/31001",
        "language": "ru",
        "topics": '{"business": 0.95, "politics": 0.2}',
        "importance_score": 0.79,
        "minutes_ago": 120,
        "reaction": "dislike",
    },
    {
        "source_url": "https://t.me/rbc_news",
        "title": "Рубль укрепился до 89 за доллар",
        "body": "Российский рубль укрепился на Московской бирже до отметки 89 рублей за доллар. Аналитики связывают динамику с налоговым периодом и продажей валютной выручки экспортёрами. Евро торгуется на уровне 96 рублей.",
        "url": "https://t.me/rbc_news/31002",
        "language": "ru",
        "topics": '{"business": 0.85}',
        "importance_score": 0.55,
        "minutes_ago": 180,
        "reaction": "blacklist",
    },
    {
        "source_url": "https://t.me/rbc_news",
        "title": "Wildberries открывает склады в трёх новых регионах",
        "body": "Маркетплейс Wildberries анонсировал открытие крупных распределительных центров в Новосибирске, Екатеринбурге и Краснодаре. Инвестиции в проект составят около 15 млрд рублей. Запуск ожидается в третьем квартале.",
        "url": "https://t.me/rbc_news/31003",
        "language": "ru",
        "topics": '{"business": 0.8, "technology": 0.3}',
        "importance_score": 0.48,
        "minutes_ago": 240,
        "reaction": None,
    },
    {
        "source_url": "https://t.me/techcrunch",
        "title": "OpenAI raises $40B at $340B valuation",
        "body": "OpenAI has closed a $40 billion funding round led by SoftBank, pushing the company's valuation to $340 billion. The round also included participation from Microsoft and other strategic investors. The funds will be used to accelerate AI research and expand compute infrastructure.",
        "url": "https://t.me/techcrunch/8001",
        "language": "en",
        "topics": '{"technology": 0.95, "business": 0.7}',
        "importance_score": 0.91,
        "minutes_ago": 30,
        "reaction": "like",
    },
    {
        "source_url": "https://t.me/techcrunch",
        "title": "Apple announces M4 MacBook Air with 30-hour battery life",
        "body": "Apple unveiled the new MacBook Air featuring the M4 chip, promising up to 30 hours of battery life. The laptop starts at $1,099 and will be available in four colors. Pre-orders open this Friday.",
        "url": "https://t.me/techcrunch/8002",
        "language": "en",
        "topics": '{"technology": 0.9}',
        "importance_score": 0.76,
        "minutes_ago": 300,
        "reaction": "like",
    },
    {
        "source_url": "https://t.me/meduzalive",
        "title": "Число погибших в результате землетрясения в Турции достигло 120",
        "body": "По последним данным, число жертв землетрясения магнитудой 6,8 в провинции Малатья возросло до 120 человек. Ещё более 400 получили ранения. Спасательные операции продолжаются.",
        "url": "https://t.me/meduzalive/50003",
        "language": "ru",
        "topics": '{"health": 0.4, "politics": 0.2}',
        "importance_score": 0.85,
        "minutes_ago": 20,
        "reaction": None,
    },
    {
        "source_url": "https://t.me/bbcrussian",
        "title": "ВОЗ предупреждает о новом штамме гриппа",
        "body": "Всемирная организация здравоохранения выпустила предупреждение о распространении нового штамма гриппа H3N2, зафиксированного в ряде стран Юго-Восточной Азии. Учёные рекомендуют своевременно делать прививки.",
        "url": "https://t.me/bbcrussian/12003",
        "language": "ru",
        "topics": '{"health": 0.95, "science": 0.5}',
        "importance_score": 0.69,
        "minutes_ago": 360,
        "reaction": "dislike",
    },
    {
        "source_url": "https://t.me/techcrunch",
        "title": "Google DeepMind solves math olympiad problems at silver-medal level",
        "body": "Google DeepMind published results showing its latest AI model can solve International Mathematical Olympiad problems at a silver-medal level. The system uses a novel approach combining formal reasoning with large language models.",
        "url": "https://t.me/techcrunch/8003",
        "language": "en",
        "topics": '{"technology": 0.9, "science": 0.85}',
        "importance_score": 0.83,
        "minutes_ago": 150,
        "reaction": "like",
    },
]

# Предпочтения по топикам для тестового юзера.
# Видно что юзер лайкал tech и politics → высокие веса.
# Дизлайкал business → низкий вес.
TOPIC_PREFERENCES = [
    {"topic": "technology", "weight": 0.9},
    {"topic": "politics",   "weight": 0.75},
    {"topic": "military",   "weight": 0.6},
    {"topic": "science",    "weight": 0.7},
    {"topic": "health",     "weight": 0.4},
    {"topic": "business",   "weight": 0.2},
    {"topic": "sports",     "weight": 0.3},
    {"topic": "culture",    "weight": 0.5},
    {"topic": "environment","weight": 0.5},
]

engine = create_engine(settings.database_url_sync)
now = datetime.now(timezone.utc)

with Session(engine) as session:

    # ── 1. Источники ──────────────────────────────────────────
    source_map: dict[str, Source] = {}
    for s in SOURCES:
        src = session.query(Source).filter_by(url=s["url"]).first()
        if not src:
            src = Source(name=s["name"], url=s["url"], type=SourceType.telegram,
                         language=s["language"], is_active=True)
            session.add(src)
            session.flush()
        source_map[s["url"]] = src

    # ── 2. Тестовый юзер ──────────────────────────────────────
    test_user = session.query(User).filter_by(email="test@newsradar.dev").first()
    if not test_user:
        test_user = User(
            email="test@newsradar.dev",
            username="test_user",
            hashed_password=hash_password("testpass123"),
            language="ru",
            is_active=True,
        )
        session.add(test_user)
        session.flush()
        print("  создан тестовый юзер: test@newsradar.dev / testpass123")
    else:
        print("  тестовый юзер уже есть")

    # ── 3. Предпочтения по топикам ────────────────────────────
    existing_prefs = {p.topic for p in session.query(UserTopicPreference)
                      .filter_by(user_id=test_user.id).all()}
    for pref in TOPIC_PREFERENCES:
        if pref["topic"] not in existing_prefs:
            session.add(UserTopicPreference(
                user_id=test_user.id,
                topic=pref["topic"],
                weight=pref["weight"],
            ))

    # ── 4. Новости + реакции ──────────────────────────────────
    added_news = 0
    added_reactions = 0

    for n in NEWS:
        # Создаём новость если нет
        item = session.query(NewsItem).filter_by(url=n["url"]).first()
        if not item:
            published = now - timedelta(minutes=n["minutes_ago"])
            item = NewsItem(
                source_id=source_map[n["source_url"]].id,
                title=n["title"],
                body=n["body"],
                url=n["url"],
                language=n["language"],
                topics=n["topics"],
                importance_score=n["importance_score"],
                published_at=published,
                created_at=published,
            )
            session.add(item)
            session.flush()
            added_news += 1

        # Добавляем реакцию от тестового юзера
        if n["reaction"]:
            exists_reaction = session.query(NewsReaction).filter_by(
                user_id=test_user.id, news_item_id=item.id
            ).first()
            if not exists_reaction:
                session.add(NewsReaction(
                    user_id=test_user.id,
                    news_item_id=item.id,
                    reaction=ReactionType(n["reaction"]),
                ))
                added_reactions += 1

    session.commit()
    print(f"  добавлено новостей: {added_news}")
    print(f"  добавлено реакций:  {added_reactions}")
    print("\nГотово!")
    print("Тестовый аккаунт: test@newsradar.dev / testpass123")
