import os
from base64 import b64encode

import alembic
import alembic.command
import alembic.config
import pytest
import transaction
import webtest
from codechallenge.app import main
from codechallenge.entities import Game, Match, Question, User
from codechallenge.entities.meta import Base, get_engine, get_tm_session
from codechallenge.security import SecurityPolicy
from codechallenge.tests.fixtures import TEST_1
from pyramid.paster import get_appsettings
from pyramid.testing import DummyRequest, testConfig
from sqlalchemy import event
from webob.cookies import Cookie


class TestApp(webtest.TestApp):
    def get_cookie(self, name, default=None):
        # webtest currently doesn't expose the unescaped cookie values
        # so we're using webob to parse them for us
        # see https://github.com/Pylons/webtest/issues/171
        cookie = Cookie(
            " ".join(
                "%s=%s" % (c.name, c.value) for c in self.cookiejar if c.name == name
            )
        )
        return next(
            (m.value.decode("latin-1") for m in cookie.values()),
            default,
        )

    def get_csrf_token(self):
        """
        Convenience method to get the current CSRF token.

        This value must be passed to POST/PUT/DELETE requests in either the
        "X-CSRF-Token" header or the "csrf_token" form value.

        testapp.post(..., headers={'X-CSRF-Token': testapp.get_csrf_token()})

        or

        testapp.post(..., {'csrf_token': testapp.get_csrf_token()})

        """
        return self.get_cookie("csrf_token")

    def login(self, params, status=303, **kw):
        """Convenience method to login the client."""
        body = {"csrf_token": self.get_csrf_token()}
        body.update(params)
        return self.post("/login", body, **kw)


def pytest_addoption(parser):
    parser.addoption("--ini", action="store", metavar="INI_FILE")


@pytest.fixture(scope="session")
def ini_file(request):
    # potentially grab this path from a pytest option
    return os.path.abspath("pytest.ini")


@pytest.fixture(scope="session")
def alembic_ini_file(request):
    return os.path.abspath("alembic.ini")


@pytest.fixture(scope="session")
def app_settings(ini_file):
    _sett = get_appsettings(ini_file)
    yield _sett


@pytest.fixture
def dbengine(app_settings, ini_file, alembic_ini_file):
    engine = get_engine(app_settings)

    alembic_cfg = alembic.config.Config(alembic_ini_file)
    Base.metadata.drop_all(bind=engine)
    alembic.command.stamp(alembic_cfg, None, purge=True)

    # run migrations to initialize the database
    # depending on how we want to initialize the database from scratch
    # we could alternatively call:
    Base.metadata.create_all(bind=engine)
    # alembic.command.stamp(alembic_cfg, "head")
    # alembic.command.upgrade(alembic_cfg, "head")

    yield engine

    Base.metadata.drop_all(bind=engine)
    # alembic.command.stamp(alembic_cfg, None, purge=True)


@pytest.fixture
def app(app_settings, dbengine):
    return main({}, dbengine=dbengine, **app_settings)


@pytest.fixture
def testapp(app, tm, dbsession, mocker):
    # override request.dbsession and request.tm with our own
    # externally-controlled values that are shared across requests but aborted
    # at the end
    _testapp = TestApp(
        app,
        extra_environ={
            "HTTP_HOST": "example.com",
            "tm.active": True,
            "tm.manager": tm,
            "app.dbsession": dbsession,
        },
    )

    # initialize a csrf token instead of running an initial request to get one
    # from the actual app - this only works using the CookieCSRFStoragePolicy
    _testapp.set_cookie("csrf_token", "dummy_csrf_token")
    # stub to bypass authentication check
    mocker.patch("pyramid.request.Request.is_authenticated", return_value=True)
    return _testapp


@pytest.fixture
def tm():
    tm = transaction.TransactionManager(explicit=True)
    tm.begin()
    tm.doom()

    yield tm

    tm.abort()


@pytest.fixture
def dbsession(app, tm):

    session_factory = app.registry["dbsession_factory"]
    _session = get_tm_session(session_factory, tm)

    yield _session


@pytest.fixture
def fillTestingDB(app):
    tm = transaction.TransactionManager(explicit=True)
    dbsession = get_tm_session(app.registry["dbsession_factory"], tm)
    with tm:
        dbsession.add_all(
            [
                Question(text="q1.text", position=0),
                Question(text="q2.text", position=1),
                Question(text="q3.text", position=2),
            ]
        )

    yield


class AuthenticatedRequest(DummyRequest):
    @property
    def is_authenticated(self):
        return True

    @property
    def identity(self):
        credentials = {
            "email": "testing_user@test.com",
            "password": "p@ss",
        }
        return User(**credentials).save()


@pytest.fixture
def dummy_request(tm, dbsession):
    """
    A lightweight dummy request.

    This request is ultra-lightweight and should be used only when the request
    itself is not a large focus in the call-stack.  It is much easier to mock
    and control side-effects using this object, however:

    - It does not have request extensions applied.
    - Threadlocals are not properly pushed.

    """
    request = DummyRequest()
    request.domain = "codechallenge.project"
    request.host = "codechallenge.project"
    request.dbsession = dbsession
    request.tm = tm

    return request


@pytest.fixture
def config(dummy_request, app_settings):
    with testConfig(request=dummy_request) as config:
        config.include("codechallenge.endpoints.routes")

        config.set_security_policy(SecurityPolicy(app_settings["auth.secret"]))
        yield config


@pytest.fixture(name="emitted_queries")
def count_database_queries(dbengine):
    """
    Return a list of the SQL statement executed by the code under test

    To be used in accordance with len() to count the number of queries
    executed
    """
    queries = []

    def before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        sql_t = (statement, parameters)
        if sql_t not in queries:
            queries.append(sql_t)

    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        sql_t = (statement, parameters)
        if sql_t not in queries:
            queries.append(sql_t)

    event.listen(dbengine, "before_cursor_execute", before_cursor_execute)
    event.listen(dbengine, "after_cursor_execute", after_cursor_execute)

    yield queries

    event.remove(dbengine, "before_cursor_execute", before_cursor_execute)
    event.listen(dbengine, "after_cursor_execute", after_cursor_execute)


@pytest.fixture(name="trivia_match")
def create_fixture_test(dbsession):
    match = Match().save()
    first_game = Game(match_uid=match.uid, index=1).save()
    second_game = Game(match_uid=match.uid, index=2).save()
    for i, q in enumerate(TEST_1, start=1):
        if i < 3:
            new_question = Question(game_uid=first_game.uid, text=q["text"], position=i)
        else:
            new_question = Question(
                game_uid=second_game.uid, text=q["text"], position=(i - 2)
            )
        new_question.create_with_answers(q["answers"])

    yield match


@pytest.fixture
def yaml_file_handler():
    with open("codechallenge/tests/files/file.yaml", "rb") as fp:
        b64content = b64encode(fp.read()).decode()
        b64string = f"data:application/x-yaml;base64,{b64content}"
        yield b64string, "file.yaml"


@pytest.fixture
def excel_file_handler():
    with open("codechallenge/tests/files/file.xlsx", "rb") as fp:
        yield fp, "file.xlsx"
