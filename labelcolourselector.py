class LabelColourSelector:
    def __init__(self, project):
        self._project = project

    def get_colour(self, label):
        if label == 'jira-type:epic':
            return 'ddf4dd'
        elif label.startwith('jira-type:'):
            return '7bc043'
        elif label == 'bug':
            return 'ee4035'
        # elif (label in self._project.get_components()): return 'fdf498'
        # elif (label.replace('component:', '') in self._project.get_components()): return 'fdf498'
        else:
            return 'ededed'
