import pandas as pd

df = pd.read_csv("app/data/pokemon.csv")

LEGENDARY_IDS = {
    # Gen 1
    144, 145, 146, 150, 151,
    # Gen 2
    243, 244, 245, 249, 250, 251,
    # Gen 3
    377, 378, 379, 380, 381, 382, 383, 384, 385, 386,
    # Gen 4
    480, 481, 482, 483, 484, 485, 486, 487, 488,
    489, 490, 491, 492, 493,
    # Gen 5
    638, 639, 640, 641, 642, 643, 644, 645, 646,
    647, 648, 649,
    # Gen 6
    716, 717, 718, 719, 720, 721,
    # Gen 7: Tapus, Cosmog line, Necrozma, Ultra Beasts, Mythicals
    785, 786, 787, 788, 789, 790, 791, 792, 800,
    793, 794, 795, 796, 797, 798, 799,
    803, 804, 805, 806,
    801, 802, 807, 808, 809,
    # Gen 8
    888, 889, 890, 891, 892, 893, 894, 895, 896, 897, 898,
    # Gen 9
    1001, 1002, 1003, 1004,
    1007, 1008, 1009, 1010,
    1014, 1015, 1016, 1017,
    1020, 1021, 1022, 1023, 1024, 1025,
}

df["legendary"] = df["pokemon_id"].isin(LEGENDARY_IDS)

tagged = df[df["legendary"]]
print(f"Total tagged: {len(tagged)}")
for gen in sorted(tagged["generation"].unique()):
    names = tagged[tagged["generation"] == gen]["name"].tolist()
    print(f"Gen {gen} ({len(names)}): {', '.join(names)}")

df.to_csv("app/data/pokemon.csv", index=False)
print("\nCSV updated.")
