from datetime import datetime

from codechallenge.entities import Answers, Matches, Questions, Reactions, Users
from codechallenge.entities.user import WordDigest
from codechallenge.exceptions import NotFoundObjectError, ValidateError


class RetrieveObject:
    def __init__(self, uid, otype):
        self.object_uid = uid
        self.otype = otype

    def get(self):
        klass = {
            "answer": Answers,
            "match": Matches,
            "question": Questions,
            "user": Users,
        }.get(self.otype)

        obj = klass.get(uid=self.object_uid)
        if obj:
            return obj
        raise NotFoundObjectError()


class ValidatePlayLand:
    def __init__(self, **kwargs):
        self.match_uhash = kwargs.get("match_uhash")

    def valid_match(self):
        match = Matches.get(uhash=self.match_uhash)
        if not match:
            raise NotFoundObjectError()

        if match.is_active:
            return match

        raise ValidateError("Expired match")

    def is_valid(self):
        return {"match": self.valid_match()}


class ValidatePlayCode:
    def __init__(self, **kwargs):
        self.match_code = kwargs.get("match_code")

    def valid_match(self):
        match = Matches.get(code=self.match_code)
        if not match:
            raise NotFoundObjectError()

        if match.is_active:
            return match

        raise ValidateError("Expired match")

    def is_valid(self):
        return {"match": self.valid_match()}


class ValidatePlaySign:
    def __init__(self, email, token):
        self.original_email = email
        self.token = token

    def valid_user(self):
        email_digest = WordDigest(self.original_email).value()
        token_digest = WordDigest(self.token).value()
        user = Users.get(email_digest=email_digest, token_digest=token_digest)
        if user:
            return user
        raise NotFoundObjectError("Invalid email-token")

    def is_valid(self):
        return {"user": self.valid_user()}


class ValidatePlayStart:
    def __init__(self, **kwargs):
        self.match_uid = kwargs.get("match_uid")
        self.user_uid = kwargs.get("user_uid")
        self.password = kwargs.get("password")

    def valid_user(self):
        user = Users.get(uid=self.user_uid)
        if self.user_uid and not user:
            raise NotFoundObjectError()
        return user

    def valid_match(self):
        return RetrieveObject(self.match_uid, otype="match").get()

    def is_valid(self):
        """Verifies match accessibility"""
        match = self.valid_match()
        user = self.valid_user()

        if not match.is_active:
            raise ValidateError("Expired match")

        if match.is_restricted:
            if not self.password:
                raise ValidateError("Password is required for private matches")

            if self.password != match.password:
                raise ValidateError("Password mismatch")

        if user and user.signed != match.is_restricted:
            raise ValidateError("User cannot access this match")

        data = {"match": match}
        if user:
            data.update(user=user)
        return data


class ValidatePlayNext:
    def __init__(self, **kwargs):
        self.match_uid = kwargs.get("match_uid")
        self.answer_uid = kwargs.get("answer_uid")
        self.user_uid = kwargs.get("user_uid")
        self.question_uid = kwargs.get("question_uid")
        self._data = {}

    def valid_reaction(self):
        user = self._data.get("user")
        if not user:
            user = Users.get(uid=self.user_uid)

        question = self._data.get("question")
        if not question:
            question = Questions.get(uid=self.question_uid)

        reaction = Reactions.reaction_of_user_to_question(user, question)
        if reaction and reaction.answer:
            raise ValidateError("Duplicate Reactions")

    def valid_answer(self):
        answer = Answers.get(uid=self.answer_uid)
        if answer is None:
            raise NotFoundObjectError("Unexisting answer")

        question = Questions.get(uid=self.question_uid)
        if question and answer in question.answers:
            self._data["answer"] = answer
            return

        raise ValidateError("Invalid answer")

    def valid_user(self):
        user = Users.get(uid=self.user_uid)
        if user:
            self._data["user"] = user
            return

        raise NotFoundObjectError()

    def valid_match(self):
        match = RetrieveObject(self.match_uid, otype="match").get()
        self._data["match"] = match

    def is_valid(self):
        # expected to run in sequence
        self.valid_answer()
        self.valid_user()
        self.valid_match()
        self.valid_reaction()
        return self._data


class ValidateEditMatch:
    def __init__(self, match_uid):
        self.match_uid = match_uid

    def valid_match(self):
        match = RetrieveObject(self.match_uid, otype="match").get()
        if not match.is_started:
            return match

        raise ValidateError("Match started. Cannot be edited")

    def is_valid(self):
        return self.valid_match()


class ValidateNewCodeMatch:
    def __init__(self, from_time, to_time):
        self.from_time = from_time
        self.to_time = to_time

    def is_valid(self):
        now = datetime.now()
        if self.from_time < now:
            raise ValidateError("from-time must be greater than now")

        if self.to_time < self.from_time:
            raise ValidateError("to-time must be greater than from-time")
