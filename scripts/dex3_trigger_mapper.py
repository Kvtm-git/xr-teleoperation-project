class Dex3TriggerMapper:
    def __init__(self, open_pos, closed_pos, threshold=None):
        """
        open_pos: liste med joint værdier for åben hånd
        closed_pos: liste med joint værdier for lukket hånd
        threshold: hvis sat -> binary mode (open/close)
                   hvis None -> smooth interpolation
        """
        self.open_pos = open_pos
        self.closed_pos = closed_pos
        self.threshold = threshold

    def map(self, trigger_value):
        # Clamp mellem 0 og 1
        trigger_value = max(0.0, min(1.0, trigger_value))

        # Binary mode (klik open/close)
        if self.threshold is not None:
            if trigger_value >= self.threshold:
                return self.closed_pos
            return self.open_pos

        # Smooth mode (glidende bevægelse)
        return [
            o + trigger_value * (c - o)
            for o, c in zip(self.open_pos, self.closed_pos)
        ]
    
if __name__ == "__main__":
    DEX3_OPEN = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    DEX3_CLOSED = [0.8, 0.9, 0.9, 0.8, 0.7, 0.7]

    mapper = Dex3TriggerMapper(
        DEX3_OPEN,
        DEX3_CLOSED,
        threshold=None  # sæt fx 0.5 for binary
    )

    test_values = [0.0, 0.25, 0.5, 0.75, 1.0]

    for t in test_values:
        result = mapper.map(t)
        print(f"Trigger: {t} -> {result}")