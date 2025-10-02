class ActionCollection:
    def __init__(self):
        self.actions = []

    def add_action(self, action):
        self.actions.append(action)

    def run(self):
        prev_action_success = True
        for action in self.actions:
            if action.run_while_prev_action_success and not prev_action_success:
                prev_action_success = False
                continue

            prev_action_success = action.run()