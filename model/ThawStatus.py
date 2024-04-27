from dataclasses import dataclass


@dataclass
class ThawStatus:
    INITIATED = 'INITIATED'
    PROCESSING = 'PROCESSING'
    COMPLETED = 'COMPLETED'
