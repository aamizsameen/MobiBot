from __future__ import annotations
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, Boolean
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


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, index=True)       # who created the schedule
    target_phone = Column(String)               # phone number to send to (e.g. 919876543210)
    message = Column(Text)                      # message text to send
    scheduled_at = Column(DateTime, index=True) # when to send (UTC)
    is_done = Column(Boolean, default=False)    # whether it has been executed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


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


# --- Scheduled Tasks ---

def create_scheduled_task(user_id: str, target_phone: str, message: str,
                          scheduled_at: datetime.datetime) -> ScheduledTask:
    db = SessionLocal()
    task = ScheduledTask(
        user_id=user_id,
        target_phone=target_phone,
        message=message,
        scheduled_at=scheduled_at,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    db.close()
    return task


def list_scheduled_tasks(user_id: str) -> list[ScheduledTask]:
    db = SessionLocal()
    tasks = (db.query(ScheduledTask)
             .filter_by(user_id=user_id, is_done=False)
             .order_by(ScheduledTask.scheduled_at.asc())
             .all())
    db.close()
    return tasks


def delete_scheduled_task(user_id: str, task_id: int) -> bool:
    db = SessionLocal()
    task = db.query(ScheduledTask).filter_by(id=task_id, user_id=user_id, is_done=False).first()
    if task:
        db.delete(task)
        db.commit()
        db.close()
        return True
    db.close()
    return False


def get_due_tasks() -> list[ScheduledTask]:
    """Get all tasks that are due (scheduled_at <= now and not done)."""
    db = SessionLocal()
    now = datetime.datetime.utcnow()
    tasks = (db.query(ScheduledTask)
             .filter(ScheduledTask.scheduled_at <= now, ScheduledTask.is_done == False)
             .all())
    db.close()
    return tasks


def mark_task_done(task_id: int):
    db = SessionLocal()
    task = db.query(ScheduledTask).filter_by(id=task_id).first()
    if task:
        task.is_done = True
        db.commit()
    db.close()
