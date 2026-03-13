"""Seed script: injeta posts simulados para demo do dashboard."""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone

from backend.models.database import SessionLocal, init_db
from backend.models.match import Match
from backend.models.post import Post
from backend.models.team import Team
from backend.models.coach import Coach
from backend.analyzer.dictionary import swear_dictionary
from backend.analyzer.scorer import calculate_rage

# Templates de posts por faixa de raiva
TEMPLATES_LEVE = [
    "Que fase do {time}, não joga nada",
    "{time} tá de brincadeira, entregou o jogo",
    "Vergonha esse {time}, pipoqueiro demais",
    "Que decepção com o {time} hoje",
    "{time} sendo {time}, nada novo",
    "Cada dia pior esse {time}",
    "Torcedor do {time} só sofre",
]

TEMPLATES_MEDIO = [
    "FORA {tecnico}!!! Incompetente demais",
    "{time} é uma VÁRZEA, juiz ladrão ajudando",
    "Roubaram o {time}!! Esse juiz é um lixo",
    "Que time covarde esse {time}, fora {tecnico}",
    "{tecnico} é um paneleiro, demite logo",
    "{time} LIXO! Vendido! Roubaram!!",
    "Fora {tecnico}!! Tá de sacanagem esse time",
]

TEMPLATES_FORTE = [
    "VAI TOMAR NO C* {time}!!!! LIXOOOO",
    "{tecnico} FDP!!! FORA AGORA!!!",
    "PQP {time}!!!! QUE MERDA É ESSA???",
    "VSF {time}!! BANDO DE PIPOQUEIRO FDP",
    "{time} DESGRAÇADO!! VERGONHA NACIONAL!!",
    "CARALHO {time}!! TNC {tecnico}!!!",
    "QUE PORRA É ESSA {time}???? ACABOU!!!",
]


def generate_posts():
    db = SessionLocal()
    try:
        teams = db.query(Team).all()
        coaches = db.query(Coach).all()
        matches = db.query(Match).filter(
            Match.status.in_(["live", "finished"])
        ).all()

        if not matches:
            print("Nenhum match live/finished encontrado. Rode o backend primeiro.")
            return

        coach_by_team = {c.team_id: c for c in coaches}
        posts_created = 0

        for match in matches:
            home = next(t for t in teams if t.id == match.home_team_id)
            away = next(t for t in teams if t.id == match.away_team_id)

            for team in [home, away]:
                coach = coach_by_team.get(team.id)
                coach_name = coach.name.split()[-1] if coach else "técnico"

                # Gera 30-80 posts por time por jogo
                num_posts = random.randint(30, 80)
                base_time = match.started_at or datetime.now(timezone.utc) - timedelta(hours=2)

                for i in range(num_posts):
                    # Distribui ao longo dos 90 minutos
                    minute_offset = random.randint(0, 95)
                    post_time = base_time + timedelta(minutes=minute_offset)

                    # Escolhe template por peso (mais posts leves, menos fortes)
                    roll = random.random()
                    if roll < 0.4:
                        template = random.choice(TEMPLATES_LEVE)
                    elif roll < 0.8:
                        template = random.choice(TEMPLATES_MEDIO)
                    else:
                        template = random.choice(TEMPLATES_FORTE)

                    text = template.format(time=team.name, tecnico=coach_name)

                    # Variações: CAPS, exclamações, repetições
                    if random.random() < 0.3:
                        text = text.upper()
                    if random.random() < 0.4:
                        text += "!" * random.randint(1, 5)

                    # Analisa
                    swear_matches = swear_dictionary.find_matches(text)
                    rage_score = calculate_rage(text, swear_matches)

                    if rage_score == 0:
                        continue

                    post = Post(
                        source="demo",
                        external_id=f"demo/{uuid.uuid4().hex[:12]}",
                        author_handle=f"@torcedor_{random.randint(1000, 9999)}",
                        text=text,
                        team_id=team.id,
                        coach_id=coach.id if coach and random.random() < 0.4 else None,
                        match_id=match.id,
                        rage_score=rage_score,
                        swear_words=[m.word for m in swear_matches],
                        created_at=post_time,
                        analyzed_at=datetime.now(timezone.utc),
                    )
                    db.add(post)
                    posts_created += 1

        db.commit()
        print(f"✅ {posts_created} posts de demo criados!")
        print(f"   {len(matches)} jogos populados")
        print("   Recarregue o dashboard para ver os dados.")
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    generate_posts()
