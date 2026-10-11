import pandas as pd

def find_donors(blood_group):
    donors = pd.read_csv("data/donors.csv")

    matched = donors[
        (donors["blood_group"] == blood_group) &
        (donors["hemoglobin"] > 12.5) &
        (donors["availability"] == 1)
    ]

    return matched