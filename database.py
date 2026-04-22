from __future__ import annotations
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float
from sqlalchemy.orm import declarative_base, sessionmaker
from config import Config

engine = create_engine(Config.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Prompt(Base):
    __tablename__ = "prompts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, index=True)  # telegram/whatsapp user identifier
    name = Column(String, index=True)
    template = Column(Text)
    provider = Column(String, default="default")  # which LLM provider to use
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class ExecutionLog(Base):
    __tablename__ = "execution_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, index=True)
    prompt_name = Column(String)
    provider = Column(String)
    input_text = Column(Text, default="")
    output_text = Column(Text)
    tokens_used = Column(Integer, default=0)
    cost = Column(Float, default=0.0)
    executed_at = Column(DateTime, default=datetime.datetime.utcnow)


Base.metadata.create_all(bind=engine)


# --- CRUD Operations ---

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def save_prompt(user_id: str, name: str, template: str, provider: str = "default") -> Prompt:
    db = SessionLocal()
    existing = db.query(Prompt).filter_by(user_id=user_id, name=name).first()
    if existing:
        existing.template = template
        existing.provider = provider
        existing.version += 1
        existing.updated_at = datetime.datetime.utcnow()
        db.commit()
        db.refresh(existing)
        db.close()
        return existing
    prompt = Prompt(user_id=user_id, name=name, template=template, provider=provider)
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    db.close()
    return prompt


def get_prompt(user_id: str, name: str) -> Prompt | None:
    db = SessionLocal()
    prompt = db.query(Prompt).filter_by(user_id=user_id, name=name).first()
    db.close()
    return prompt


def list_prompts(user_id: str) -> list[Prompt]:
    db = SessionLocal()
    prompts = db.query(Prompt).filter_by(user_id=user_id).all()
    db.close()
    return prompts


def delete_prompt(user_id: str, name: str) -> bool:
    db = SessionLocal()
    prompt = db.query(Prompt).filter_by(user_id=user_id, name=name).first()
    if prompt:
        db.delete(prompt)
        db.commit()
        db.close()
        return True
    db.close()
    return False


def log_execution(user_id: str, prompt_name: str, provider: str,
                  input_text: str, output_text: str, tokens: int = 0, cost: float = 0.0) -> ExecutionLog:
    db = SessionLocal()
    log = ExecutionLog(
        user_id=user_id, prompt_name=prompt_name, provider=provider,
        input_text=input_text, output_text=output_text,
        tokens_used=tokens, cost=cost,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    db.close()
    return log


def get_history(user_id: str, limit: int = 10) -> list[ExecutionLog]:
    db = SessionLocal()
    logs = (db.query(ExecutionLog)
            .filter_by(user_id=user_id)
            .order_by(ExecutionLog.executed_at.desc())
            .limit(limit).all())
    db.close()
    return logs
