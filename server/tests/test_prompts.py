"""BDD tests: tutor prompt/mode resolution."""

from prompts import MODES, get_prompt
from tests.expectations import expect


class DescribeGetPrompt:
    def it_returns_a_known_modes_prompt(self):
        prompt = get_prompt("free_chat")
        expect(prompt).to_equal(MODES["free_chat"].system_prompt)

    def it_falls_back_to_free_chat_for_unknown_mode(self):
        prompt = get_prompt("does_not_exist")
        expect(prompt).to_equal(MODES["free_chat"].system_prompt)

    def it_prefers_a_custom_prompt_over_mode(self):
        custom = "Be a pirate captain who only speaks in pirate slang."
        expect(get_prompt("free_chat", custom)).to_equal(custom)

    def it_returns_custom_prompt_even_for_unknown_mode(self):
        expect(get_prompt("zzz", "custom text")).to_equal("custom text")


class DescribeModes:
    def it_exposes_the_four_core_modes(self):
        expect(set(MODES.keys())).to_equal(
            {"free_chat", "interview", "travel", "debate"}
        )

    def it_every_mode_has_a_non_empty_prompt(self):
        for mode in MODES.values():
            expect(mode.system_prompt).to_be_truthy()
            expect(mode.label).to_be_truthy()
