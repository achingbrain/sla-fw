from sl1fw.wizard.group import CheckGroup
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.states.wizard import WizardState

class ShowResultsGroup(CheckGroup):
    def __init__(self):
        super().__init__()

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(
            actions, actions.show_results_done, WizardState.SHOW_RESULTS
        )
