from datetime import datetime, timezone

from codechallenge.app import StoreConfig
from codechallenge.models.meta import Base, TableMixin, classproperty
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint


class Reaction(TableMixin, Base):
    __tablename__ = "reaction"

    match_uid = Column(Integer, ForeignKey("match.uid"), nullable=False)
    match = relationship("Match", back_populates="reactions")
    question_uid = Column(Integer, ForeignKey("question.uid"), nullable=False)
    question = relationship("Question", back_populates="reactions")
    answer_uid = Column(Integer, ForeignKey("answer.uid"), nullable=True)
    answer = relationship("Answer", back_populates="reactions")
    user_uid = Column(Integer, ForeignKey("user.uid"), nullable=False)
    user = relationship("User", back_populates="reactions")

    # used to mark reactions of a user when drops out of a match
    dirty = Column(Boolean, default=False)
    answer_time = Column(DateTime(timezone=True), nullable=True)
    score = Column(Float)

    __table_args__ = (
        UniqueConstraint(
            "question_uid", "answer_uid", "user_uid", "match_uid", "create_timestamp"
        ),
    )

    @property
    def session(self):
        return StoreConfig().session

    def create(self):
        self.session.add(self)
        self.session.commit()
        return self

    def save(self):
        self.session.add(self)
        self.session.commit()
        return self

    def record_answer(self, answer):
        response_datetime = datetime.now(tz=timezone.utc)
        response_time_in_secs = (
            response_datetime - self.create_timestamp
        ).total_seconds()
        if (
            self.question.time is not None
            and self.question.time - response_time_in_secs < 0
        ):
            return self

        # TODO to fix. The update_timestamp should be updated via handler
        self.update_timestamp = response_datetime
        self.answer = answer
        self.answer_time = self.update_timestamp
        self.session.commit()
        return self

    @property
    def json(self):
        return {"text": self.text, "code": self.code, "position": self.position}


class Reactions:
    @classproperty
    def session(self):
        return StoreConfig().session

    @classmethod
    def count(cls):
        return cls.session.query(Reaction).count()

    @classmethod
    def reaction_of_user_to_question(cls, user, question):
        return (
            cls.session.query(Reaction)
            .filter_by(user=user, question=question)
            .one_or_none()
        )
