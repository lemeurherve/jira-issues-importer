class LabelColourSelector:
    def __init__(self, project):
        self._project = project

    def get_colour(self, label):
        if label in ('rfe', 'story'):
            return '7bc043'
        elif label == 'bug':
            return 'ee4035'
        elif label == 'epic':
            return 'ddf4dd'
        # elif (label in self._project.get_components()): return 'fdf498'
        # elif (label.replace('component:', '') in self._project.get_components()): return 'fdf498'
        else:
            return 'ededed'
