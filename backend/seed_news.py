"""
Заполняет БД тестовыми новостями для разработки.

Запуск:
  docker compose exec backend python seed_news.py
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.news import NewsItem
from app.models.source import Source, SourceType

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
        "summary": "ЕС продлил экономические санкции против России на полгода из-за конфликта на Украине. Следующий пересмотр состоится в октябре.",
        "url": "https://t.me/meduzalive/50001",
        "language": "ru",
        "topics": '{"politics": 0.95, "business": 0.4}',
        "importance_score": 0.82,
        "minutes_ago": 15,
    },
    {
        "source_url": "https://t.me/meduzalive",
        "title": "В Москве прошли обыски у известного журналиста",
        "body": "Силовые структуры провели обыски в квартире журналиста-расследователя Михаила Соколова. По данным источников, мероприятия связаны с уголовным делом о распространении «заведомо ложной информации» о действиях армии.",
        "summary": "Силовики провели обыски у журналиста Михаила Соколова. Мероприятия связаны с делом о распространении ложной информации о действиях армии.",
        "url": "https://t.me/meduzalive/50002",
        "language": "ru",
        "topics": '{"politics": 0.9}',
        "importance_score": 0.75,
        "minutes_ago": 40,
    },
    {
        "source_url": "https://t.me/bbcrussian",
        "title": "Украина получит новый пакет военной помощи от США",
        "body": "Администрация США объявила о выделении очередного пакета военной помощи Украине на сумму 800 миллионов долларов. В пакет входят артиллерийские снаряды, системы ПВО и бронетехника. Поставки начнутся в ближайшие недели.",
        "summary": "США выделили Украине новый пакет военной помощи на $800 млн: снаряды, системы ПВО и бронетехника. Поставки начнутся в ближайшие недели.",
        "url": "https://t.me/bbcrussian/12001",
        "language": "ru",
        "topics": '{"military": 0.95, "politics": 0.7}',
        "importance_score": 0.88,
        "minutes_ago": 60,
    },
    {
        "source_url": "https://t.me/bbcrussian",
        "title": "Цены на нефть выросли на фоне решения ОПЕК+",
        "body": "Котировки нефти марки Brent поднялись выше 90 долларов за баррель после того, как страны ОПЕК+ объявили о сокращении добычи на 500 тысяч баррелей в сутки. Решение вступает в силу с мая и вызвало волатильность на рынках.",
        "summary": "Нефть Brent превысила $90 за баррель после решения ОПЕК+ сократить добычу на 500 тыс. баррелей в сутки с мая.",
        "url": "https://t.me/bbcrussian/12002",
        "language": "ru",
        "topics": '{"business": 0.9, "politics": 0.3}',
        "importance_score": 0.71,
        "minutes_ago": 90,
    },
    {
        "source_url": "https://t.me/rbc_news",
        "title": "ЦБ оставил ключевую ставку на уровне 16%",
        "body": "Банк России по итогам заседания совета директоров сохранил ключевую ставку на уровне 16% годовых. Регулятор сослался на сохраняющееся инфляционное давление и неопределённость на внешних рынках. Следующее заседание запланировано на июнь.",
        "summary": "Банк России сохранил ключевую ставку на уровне 16% из-за инфляционного давления. Следующее заседание — в июне.",
        "url": "https://t.me/rbc_news/31001",
        "language": "ru",
        "topics": '{"business": 0.95, "politics": 0.2}',
        "importance_score": 0.79,
        "minutes_ago": 120,
    },
    {
        "source_url": "https://t.me/rbc_news",
        "title": "Рубль укрепился до 89 за доллар",
        "body": "Российский рубль укрепился на Московской бирже до отметки 89 рублей за доллар. Аналитики связывают динамику с налоговым периодом и продажей валютной выручки экспортёрами. Евро торгуется на уровне 96 рублей.",
        "summary": "Рубль укрепился до 89 за доллар на фоне налогового периода и продажи валютной выручки экспортёрами. Евро — около 96 рублей.",
        "url": "https://t.me/rbc_news/31002",
        "language": "ru",
        "topics": '{"business": 0.85}',
        "importance_score": 0.55,
        "minutes_ago": 180,
    },
    {
        "source_url": "https://t.me/rbc_news",
        "title": "Wildberries открывает склады в трёх новых регионах",
        "body": "Маркетплейс Wildberries анонсировал открытие крупных распределительных центров в Новосибирске, Екатеринбурге и Краснодаре. Инвестиции в проект составят около 15 млрд рублей. Запуск ожидается в третьем квартале 2024 года.",
        "summary": "Wildberries откроет склады в Новосибирске, Екатеринбурге и Краснодаре с инвестициями около 15 млрд рублей. Запуск — в третьем квартале 2024 года.",
        "url": "https://t.me/rbc_news/31003",
        "language": "ru",
        "topics": '{"business": 0.8, "technology": 0.3}',
        "importance_score": 0.48,
        "minutes_ago": 240,
    },
    {
        "source_url": "https://t.me/techcrunch",
        "title": "OpenAI raises $40B at $340B valuation",
        "body": "OpenAI has closed a $40 billion funding round led by SoftBank, pushing the company's valuation to $340 billion. The round also included participation from Microsoft and other strategic investors. The funds will be used to accelerate AI research and expand compute infrastructure.",
        "summary": "OpenAI raised $40B led by SoftBank, reaching a $340B valuation. The funds will accelerate AI research and expand compute infrastructure.",
        "url": "https://t.me/techcrunch/8001",
        "language": "en",
        "topics": '{"technology": 0.95, "business": 0.7}',
        "importance_score": 0.91,
        "minutes_ago": 30,
    },
    {
        "source_url": "https://t.me/techcrunch",
        "title": "Apple announces M4 MacBook Air with 30-hour battery life",
        "body": "Apple unveiled the new MacBook Air featuring the M4 chip, promising up to 30 hours of battery life and a significant performance boost over its predecessor. The laptop starts at $1,099 and will be available in four colors. Pre-orders open this Friday.",
        "summary": "Apple unveiled the M4 MacBook Air with up to 30 hours of battery life, starting at $1,099. Pre-orders open this Friday.",
        "url": "https://t.me/techcrunch/8002",
        "language": "en",
        "topics": '{"technology": 0.9}',
        "importance_score": 0.76,
        "minutes_ago": 300,
    },
    {
        "source_url": "https://t.me/meduzalive",
        "title": "Число погибших в результате землетрясения в Турции достигло 120",
        "body": "По последним данным, число жертв землетрясения магнитудой 6,8, произошедшего в провинции Малатья, возросло до 120 человек. Ещё более 400 получили ранения. Спасательные операции продолжаются, под завалами остаются люди.",
        "summary": "Число жертв землетрясения в турецкой провинции Малатья достигло 120, более 400 ранены. Спасательные работы продолжаются.",
        "url": "https://t.me/meduzalive/50003",
        "language": "ru",
        "topics": '{"health": 0.4, "politics": 0.2}',
        "importance_score": 0.85,
        "minutes_ago": 20,
    },
    {
        "source_url": "https://t.me/bbcrussian",
        "title": "ВОЗ предупреждает о новом штамме гриппа",
        "body": "Всемирная организация здравоохранения выпустила предупреждение о распространении нового штамма гриппа H3N2, зафиксированного в ряде стран Юго-Восточной Азии. Учёные рекомендуют своевременно делать прививки и следить за симптомами.",
        "summary": "ВОЗ предупредила о распространении штамма гриппа H3N2 в странах Юго-Восточной Азии. Рекомендуются своевременные прививки.",
        "url": "https://t.me/bbcrussian/12003",
        "language": "ru",
        "topics": '{"health": 0.95, "science": 0.5}',
        "importance_score": 0.69,
        "minutes_ago": 360,
    },
    {
        "source_url": "https://t.me/techcrunch",
        "title": "Google DeepMind's new model solves complex math olympiad problems",
        "body": "Google DeepMind published results showing its latest AI model can solve International Mathematical Olympiad problems at a silver-medal level. The system uses a novel approach combining formal reasoning with large language models.",
        "summary": "Google DeepMind's new AI model solves International Mathematical Olympiad problems at silver-medal level, combining formal reasoning with LLMs.",
        "url": "https://t.me/techcrunch/8003",
        "language": "en",
        "topics": '{"technology": 0.9, "science": 0.85}',
        "importance_score": 0.83,
        "minutes_ago": 150,
    },
]

engine = create_engine(settings.database_url_sync)
now = datetime.now(timezone.utc)

with Session(engine) as session:
    source_map: dict[str, Source] = {}
    for s in SOURCES:
        src = session.query(Source).filter_by(url=s["url"]).first()
        if not src:
            src = Source(name=s["name"], url=s["url"], type=SourceType.telegram,
                         language=s["language"], is_active=True)
            session.add(src)
            session.flush()
        source_map[s["url"]] = src

    added = 0
    for n in NEWS:
        exists = session.query(NewsItem).filter_by(url=n["url"]).first()
        if exists:
            continue
        published = now - timedelta(minutes=n["minutes_ago"])
        item = NewsItem(
            source_id=source_map[n["source_url"]].id,
            title=n["title"],
            body=n["body"],
            summary=n.get("summary"),
            ai_status="ok" if n.get("summary") else None,
            url=n["url"],
            language=n["language"],
            topics=n["topics"],
            importance_score=n["importance_score"],
            published_at=published,
            created_at=published,
        )
        session.add(item)
        added += 1

    session.commit()
    print(f"Готово! Добавлено {added} новостей из {len(source_map)} источников.")
