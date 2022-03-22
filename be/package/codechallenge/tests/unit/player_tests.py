from datetime import datetime, timedelta

import pytest
from codechallenge.entities import (
    Answer,
    Game,
    Match,
    Question,
    Reaction,
    Reactions,
    User,
)
from codechallenge.exceptions import (
    GameError,
    GameOver,
    MatchError,
    MatchNotPlayableError,
    MatchOver,
)
from codechallenge.play.single_player import (
    GameFactory,
    PlayerStatus,
    QuestionFactory,
    SinglePlayer,
)


class TestCaseQuestionFactory:
    def t_nextQuestionWhenNotOrdered(self, dbsession):
        match = Match().save()
        game = Game(match_uid=match.uid, index=1, order=False).save()
        q_berlin = Question(
            text="Where is Berlin?", game_uid=game.uid, position=0
        ).save()
        q_zurich = Question(
            text="Where is Zurich?", game_uid=game.uid, position=1
        ).save()

        question_factory = QuestionFactory(game, *())
        assert question_factory.next() == q_berlin
        assert question_factory.next() == q_zurich
        assert question_factory.current == q_zurich

    def t_nextQuestionWhenOrdered(self, dbsession):
        """Questions are inversely created
        to make the ordering meaningful.
        """
        match = Match().save()
        game = Game(match_uid=match.uid, index=1).save()
        second = Question(text="Where is London?", game_uid=game.uid, position=1).save()
        first = Question(text="Where is Paris?", game_uid=game.uid, position=0).save()

        question_factory = QuestionFactory(game, *())
        assert question_factory.next() == first
        assert question_factory.next() == second

    def t_gameOverWhenThereAreNoQuestions(self, dbsession):
        match = Match().save()
        game = Game(match_uid=match.uid, index=1).save()

        question_factory = QuestionFactory(game, *())
        with pytest.raises(GameOver):
            question_factory.next()

    def t_gameIsOverAfterLastQuestion(self, dbsession):
        match = Match().save()
        game = Game(match_uid=match.uid, index=1).save()
        Question(text="Where is Paris?", game_uid=game.uid, position=0).save()

        question_factory = QuestionFactory(game, *())
        question_factory.next()
        with pytest.raises(GameOver):
            question_factory.next()

    def t_isLastQuestion(self, dbsession):
        match = Match().save()
        game = Game(match_uid=match.uid, index=1).save()
        Question(text="Where is Amsterdam?", game_uid=game.uid, position=0).save()
        Question(text="Where is Lion?", game_uid=game.uid, position=1).save()

        question_factory = QuestionFactory(game)
        question_factory.next()
        assert not question_factory.is_last_question
        question_factory.next()
        assert question_factory.is_last_question

    def t_previousQuestion(self, dbsession):
        match = Match().save()
        game = Game(match_uid=match.uid, index=1).save()
        first = Question(
            text="Where is Amsterdam?", game_uid=game.uid, position=0
        ).save()
        Question(text="Where is Lion?", game_uid=game.uid, position=1).save()

        question_factory = QuestionFactory(game)
        question_factory.next()
        question_factory.next()
        assert question_factory.previous() == first

    def t_callingPreviousWithoutNext(self, dbsession):
        match = Match().save()
        game = Game(match_uid=match.uid, index=1).save()
        Question(text="Where is Amsterdam?", game_uid=game.uid, position=0).save()
        Question(text="Where is Lion?", game_uid=game.uid, position=1).save()

        question_factory = QuestionFactory(game)
        with pytest.raises(GameError):
            question_factory.previous()

    def t_callingPreviousRightAfterFirstNext(self, dbsession):
        match = Match().save()
        game = Game(match_uid=match.uid, index=1).save()
        Question(text="Where is Amsterdam?", game_uid=game.uid, position=0).save()
        Question(text="Where is Lion?", game_uid=game.uid, position=1).save()

        question_factory = QuestionFactory(game)
        question_factory.next()
        with pytest.raises(GameError):
            question_factory.previous()


class TestCaseGameFactory:
    def t_nextGameWhenOrdered(self, dbsession):
        match = Match(order=True).save()
        second = Game(match_uid=match.uid, index=2).save()
        first = Game(match_uid=match.uid, index=1).save()

        game_factory = GameFactory(match, *())
        assert game_factory.next() == first
        assert game_factory.next() == second

    def t_matchWithoutGamesThrowsError(self, dbsession):
        match = Match().save()
        game_factory = GameFactory(match, *())

        with pytest.raises(MatchOver):
            game_factory.next()

        dbsession.rollback()

    def t_matchStarted(self, dbsession):
        match = Match().save()
        Game(match_uid=match.uid, index=1).save()
        game_factory = GameFactory(match, *())

        assert not game_factory.match_started

    def t_isLastGame(self, dbsession):
        match = Match().save()
        Game(match_uid=match.uid, index=0).save()
        Game(match_uid=match.uid, index=1).save()
        game_factory = GameFactory(match, *())

        game_factory.next()
        assert not game_factory.is_last_game
        game_factory.next()
        assert game_factory.is_last_game

    def t_nextOverTwoSessions(self, dbsession):
        match = Match().save()
        g1 = Game(match_uid=match.uid, index=0).save()
        Game(match_uid=match.uid, index=1).save()
        game_factory = GameFactory(match, g1.uid)

        game_factory.next()
        assert game_factory.is_last_game

    def t_callingPreviousRightAfterFirstNext(self, dbsession):
        match = Match().save()
        Game(match_uid=match.uid, index=0).save()
        Game(match_uid=match.uid, index=1).save()
        game_factory = GameFactory(match, *())

        game_factory.next()
        with pytest.raises(MatchError):
            game_factory.previous()

    def t_callingPreviousWithoutNext(self, dbsession):
        match = Match().save()
        Game(match_uid=match.uid, index=0).save()
        Game(match_uid=match.uid, index=1).save()
        game_factory = GameFactory(match, *())

        with pytest.raises(MatchError):
            game_factory.previous()


class TestCaseStatus:
    def t_questionsDisplayed(self, dbsession, emitted_queries):
        match = Match().save()
        game = Game(match_uid=match.uid, index=0).save()
        q1 = Question(text="Where is Miami", position=0, game=game).save()
        q2 = Question(text="Where is London", position=1, game=game).save()
        q3 = Question(text="Where is Paris", position=2, game=game).save()
        user = User(email="user@test.project").save()

        Reaction(match=match, question=q1, user=user, game_uid=game.uid).save()

        Reaction(match=match, question=q2, user=user, game_uid=game.uid).save()
        Reaction(match=Match().save(), question=q3, user=user, game_uid=game.uid).save()
        status = PlayerStatus(user, match)
        before = len(emitted_queries)
        assert status.questions_displayed() == {q2.uid: q2, q1.uid: q1}
        assert len(emitted_queries) == before + 1

    def t_questionDisplayedByGame(self, dbsession):
        match = Match().save()
        game = Game(match_uid=match.uid, index=0).save()
        q1 = Question(text="Where is Miami", position=0, game=game).save()
        q2 = Question(text="Where is London", position=1, game=game).save()
        q3 = Question(text="Where is Paris", position=2, game=game).save()
        user = User(email="user@test.project").save()

        Reaction(match=match, question=q1, user=user, game_uid=game.uid).save()

        Reaction(match=match, question=q2, user=user, game_uid=game.uid).save()
        Reaction(match=Match().save(), question=q3, user=user, game_uid=game.uid).save()
        status = PlayerStatus(user, match)
        assert status.questions_displayed_by_game(game) == {q2.uid: q2, q1.uid: q1}

    def t_allGamesPlayed(self, dbsession):
        match = Match().save()
        g1 = Game(match_uid=match.uid, index=0).save()
        g2 = Game(match_uid=match.uid, index=1).save()
        q1 = Question(text="Where is Miami", position=0, game=g1).save()
        q2 = Question(text="Where is London", position=0, game=g2).save()
        user = User(email="user@test.project").save()
        Reaction(match=match, question=q1, user=user, game_uid=g1.uid).save()
        Reaction(match=match, question=q2, user=user, game_uid=g2.uid).save()

        status = PlayerStatus(user, match)
        assert status.all_games_played() == {g1.uid: g1, g2.uid: g2}


class TestCaseSinglePlayer:
    def t_reactionIsCreatedAsSoonAsQuestionIsReturned(self, dbsession):
        match = Match().save()
        first_game = Game(match_uid=match.uid, index=1).save()
        question = Question(
            text="Where is London?", game_uid=first_game.uid, position=0
        ).save()
        user = User(email="user@test.project").save()

        status = PlayerStatus(user, match)
        player = SinglePlayer(status, user, match)
        question_displayed = player.start()

        assert question_displayed == question
        assert player.current == question_displayed
        assert Reactions.count() == 1

    def t_reactToFirstQuestion(self, dbsession):
        match = Match().save()
        first_game = Game(match_uid=match.uid, index=1).save()
        first = Question(
            text="Where is London?", game_uid=first_game.uid, position=0
        ).save()
        answer = Answer(question=first, text="UK", position=1).save()
        second = Question(
            text="Where is Paris?", game_uid=first_game.uid, position=1
        ).save()
        user = User(email="user@test.project").save()

        status = PlayerStatus(user, match)
        player = SinglePlayer(status, user, match)
        player.start()
        next_q = player.react(answer)

        assert len(user.reactions)
        assert next_q == second

    def t_matchAtStartTime(self, dbsession):
        match = Match(to_time=datetime.now() - timedelta(microseconds=10)).save()
        first_game = Game(match_uid=match.uid, index=1).save()
        Question(text="Where is London?", game_uid=first_game.uid, position=0).save()
        user = User(email="user@test.project").save()

        status = PlayerStatus(user, match)
        player = SinglePlayer(status, user, match)
        with pytest.raises(MatchError) as e:
            player.start()

        assert e.value.message == "Expired match"

    def t_matchRightBeforeReaction(self, dbsession):
        # the to_time attribute is set right before the player initialisation
        # to bypass the is_active check inside start() and fail at reaction
        # time (where is expected)
        match = Match().save()
        first_game = Game(match_uid=match.uid, index=1).save()
        question = Question(
            text="Where is London?", game_uid=first_game.uid, position=0
        ).save()
        answer = Answer(question=question, text="UK", position=1).save()
        user = User(email="user@test.project").save()

        match.to_time = datetime.now() + timedelta(microseconds=5000)
        match.save()
        status = PlayerStatus(user, match)
        player = SinglePlayer(status, user, match)
        player.start()
        with pytest.raises(MatchError) as e:
            player.react(answer)

        assert e.value.message == "Expired match"

    def t_matchCannotBePlayedMoreThanMatchTimes(self, dbsession):
        match = Match().save()
        user = User(email="user@test.project").save()
        game = Game(match_uid=match.uid, index=1).save()
        question = Question(
            text="Where is London?", game_uid=game.uid, position=0
        ).save()

        status = PlayerStatus(user, match)
        player = SinglePlayer(status, user, match)
        assert player.start() == question

        with pytest.raises(MatchNotPlayableError):
            player.start()

        assert match.reactions
        dbsession.rollback()

    def t_matchOver(self, dbsession):
        match = Match().save()
        first_game = Game(match_uid=match.uid, index=0).save()
        question = Question(
            text="Where is London?", game_uid=first_game.uid, position=0, time=2
        ).save()
        answer = Answer(question=question, text="UK", position=1, level=2).save()
        user = User(email="user@test.project").save()

        status = PlayerStatus(user, match)
        player = SinglePlayer(status, user, match)
        player.start()
        with pytest.raises(MatchOver):
            player.react(answer)

        assert user.reactions[0].score > 0

    def t_playMatchOverMultipleRequests(self, dbsession):
        # the SinglePlayer is instanced multiple times
        match = Match().save()
        first_game = Game(match_uid=match.uid, index=1, order=False).save()
        first = Question(
            text="Where is London?", game_uid=first_game.uid, position=0
        ).save()
        first_answer = Answer(question=first, text="UK", position=1).save()
        second = Question(
            text="Where is Paris?", game_uid=first_game.uid, position=1
        ).save()
        second_answer = Answer(question=second, text="France", position=1).save()
        third = Question(
            text="Where is Dublin?", game_uid=first_game.uid, position=2
        ).save()
        third_answer = Answer(question=third, text="Ireland", position=1).save()

        user = User(email="user@test.project").save()

        status = PlayerStatus(user, match)
        player = SinglePlayer(status, user, match)
        assert player.start() == first
        next_q = player.react(first_answer)
        assert next_q == second

        status = PlayerStatus(user, match)
        player = SinglePlayer(status, user, match)
        next_q = player.react(second_answer)

        assert user.reactions[1].question == second
        assert next_q == third
        player = SinglePlayer(status, user, match)
        with pytest.raises(MatchOver):
            player.react(third_answer)


class TestCaseResumeMatch:
    def t_matchCanBeResumedWhenThereIsStillOneQuestionToDisplay(self, dbsession):
        match = Match().save()
        first_game = Game(match_uid=match.uid, index=0).save()
        question = Question(
            text="Where is London?", game_uid=first_game.uid, position=0
        ).save()
        Question(text="Where is Moscow?", game_uid=first_game.uid, position=1).save()
        answer = Answer(question=question, text="UK", position=1).save()
        user = User(email="user@test.project").save()

        status = PlayerStatus(user, match)
        player = SinglePlayer(status, user, match)
        player.start()
        player.react(answer)
        assert player.match_can_be_resumed

    def t_matchCanNotBeResumedBecausePublic(self, dbsession):
        match = Match(is_restricted=False).save()
        user = User(email="user@test.project").save()

        status = PlayerStatus(user, match)
        player = SinglePlayer(status, user, match)
        assert not player.match_can_be_resumed
