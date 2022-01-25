from codechallenge.endpoints.match import MatchEndPoints
from codechallenge.entities import Match
from codechallenge.tests.fixtures import TEST_1


class TestCaseMatchCreation:
    def t_successfulCreationOfAMatch(self, auth_request, config):
        request = auth_request
        request.method = "POST"
        view_obj = MatchEndPoints(request)

        match_name = "New Sunday Match"
        request.json = {"name": match_name, "questions": TEST_1}
        response = view_obj.create_match()
        match = Match().with_name(match_name)
        assert len(match.questions) == 4
        questions = response.json["match"]["questions"]
        assert questions[0]["text"] == TEST_1[0]["text"]
