import os
from hashlib import blake2b
from uuid import uuid4

import bcrypt
from codechallenge.app import StoreConfig
from codechallenge.entities.meta import Base, TableMixin, classproperty
from sqlalchemy import Column, String
from sqlalchemy.ext.hybrid import hybrid_property


class WordDigest:
    def __init__(self, word):
        self.word = word

    def value(self):
        key = os.getenv("SIGNED_KEY").encode("utf-8")
        h = blake2b(key=key, digest_size=16)
        h.update(self.word.encode("utf-8"))
        return h.hexdigest()


class UserFactory:
    def __init__(self, **kwargs):
        self.original_email = kwargs.pop("original_email", "")
        self.signed = kwargs.pop("signed", None) or self.original_email
        self.kwargs = kwargs

    def exists(self, email_digest, token_digest):
        return Users.get(email_digest=email_digest, token_digest=token_digest)

    def fetch(self):
        email = self.kwargs.get("email")
        if email:
            email_digest = WordDigest(email).value()
            password = self.kwargs.get("password")

            internal_user = Users.get(email=email)
            return (
                internal_user
                or User(
                    email=email, email_digest=email_digest, password=password
                ).save()
            )

        if not self.signed:
            email_digest = uuid4().hex
            email = f"uns-{email_digest}@progame.io"
            return User(email=email).save()

        token = self.kwargs.get("token", "")
        email_digest = WordDigest(self.original_email).value()
        token_digest = WordDigest(token).value()
        user = self.exists(email_digest, token_digest)
        if user:
            return user

        user = User()
        user.email = f"{email_digest}@progame.io"
        user.email_digest = email_digest
        user.token_digest = token_digest
        user.save()
        return user


class User(TableMixin, Base):
    __tablename__ = "user"

    email = Column(String, unique=True)
    email_digest = Column(String, nullable=True)
    token_digest = Column(String)
    name = Column(String, nullable=True)
    password_hash = Column(String)
    # reactions: implicit backward relation
    # user_rankings: implicit backward relation
    key = Column(String)

    def __init__(self, **kwargs):
        password = kwargs.pop("password", None)
        if password:
            self.set_password(password)

        super().__init__(**kwargs)

    @hybrid_property
    def signed(self):
        return self.email_digest is not None

    def set_password(self, pw):
        pwhash = bcrypt.hashpw(pw.encode("utf8"), bcrypt.gensalt())
        self.password_hash = pwhash.decode("utf8")

    def check_password(self, pw):
        if self.password_hash is not None:
            expected_hash = self.password_hash.encode("utf8")
            return bcrypt.checkpw(pw.encode("utf8"), expected_hash)
        return False

    @property
    def session(self):
        return StoreConfig().session

    def save(self):
        self.session.add(self)
        self.session.commit()
        return self


class Users:
    @classproperty
    def session(self):
        return StoreConfig().session

    @classmethod
    def count(cls):
        return cls.session.query(User).count()

    @classmethod
    def get(cls, **filters):
        return cls.session.query(User).filter_by(**filters).one_or_none()
