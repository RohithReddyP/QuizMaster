class ScoreTracker:
    def __init__(self, total):
        self.total = total
        self.correct = 0

    def increment(self):
        self.correct += 1

    def get_score(self):
        return self.correct