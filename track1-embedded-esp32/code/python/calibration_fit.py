import numpy as np
raw = np.array([1000, 1600, 2300, 3100, 4000])   # ค่าเฉลี่ย raw_net
mc  = np.array([8.0, 10.0, 12.0, 14.0, 16.0])     # ความชื้นอ้างอิง
a, b = np.polyfit(raw, mc, 1)
pred = a * raw + b
r2 = 1 - ((mc - pred) ** 2).sum() / ((mc - mc.mean()) ** 2).sum()
print(f"mc = {a:.5f} * raw + {b:.3f}   R2 = {r2:.3f}   max err = {abs(mc - pred).max():.2f} %")
