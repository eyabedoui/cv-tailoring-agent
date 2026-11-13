
"""
Fake model for testing the agent without calling a real LLM.

It returns scripted responses in sequence.
"""

from copy import deepcopy


class FakeModel:
    def __init__(self, scripted_responses: list[dict]):
        self.scripted_responses = deepcopy(scripted_responses)
        self.call_count = 0

    def call_model(self, messages: list[dict], tools: list[dict]) -> dict:
        """
        Return the next scripted model response.

        The messages and tools arguments match the interface
        that will also be used by a real model.
        """
        if self.call_count >= len(self.scripted_responses):
            raise RuntimeError("FakeModel has no scripted responses left.")

        response = deepcopy(self.scripted_responses[self.call_count])
        self.call_count += 1

        return response
