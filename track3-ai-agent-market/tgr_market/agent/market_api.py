"""
market_api.py  (TGR2026 Track 3 · ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran ESID CUEE)
ไฟล์เดียวที่ "คุยกับตลาด" วันที่ 17 เมื่อเห็น API จริงของผู้จัด ให้แก้เฉพาะไฟล์นี้
ฟังก์ชันทุกตัวคืนค่าเป็น dict/list ของ Python ในรูปแบบเดียวกับตลาดจำลอง
"""
import time

import requests


class MarketAPI:
    def __init__(self, base_url, token, timeout=10, retries=3):
        self.base = base_url.rstrip('/')
        self.h = {'X-Team-Token': token}
        self.timeout, self.retries = timeout, retries

    def _req(self, method, path, **kw):
        last = None
        for i in range(self.retries):
            try:
                r = requests.request(method, self.base + path, headers=self.h, timeout=self.timeout, **kw)
                if r.status_code >= 500:                     # เซิร์ฟเวอร์ผิดพลาด ลองใหม่
                    raise RuntimeError(f'{r.status_code} {r.text[:200]}')
                if r.status_code >= 400:                     # คำขอผิด ลองใหม่ก็ไม่หาย แจ้งทันที
                    raise ValueError(f'{method} {path} -> {r.status_code}: {r.text[:300]}')
                return r.json()
            except ValueError:
                raise
            except Exception as e:                           # timeout / หลุด / 5xx
                last = e
                time.sleep(0.5 * (i + 1))
        raise ConnectionError(f'{method} {path} ล้มเหลว {self.retries} ครั้ง: {last}')

    def state(self):
        return self._req('GET', '/api/state')

    def buyers(self):
        return self._req('GET', '/api/buyers')

    def lots(self):
        return self._req('GET', '/api/lots')

    def results(self, round_no):
        return self._req('GET', '/api/results', params={'round': round_no})

    def leaderboard(self):
        return self._req('GET', '/api/leaderboard')

    def submit(self, round_no, offers):
        return self._req('POST', '/api/offers', json={'round': round_no, 'offers': offers})
