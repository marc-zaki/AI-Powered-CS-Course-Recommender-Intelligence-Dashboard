import time
import pandas as pd

t0 = time.time()
df = pd.read_json("datasets/CS_Dataset_Phase2.json")
t1 = time.time()
print(f"JSON load: {t1-t0:.2f}s")
