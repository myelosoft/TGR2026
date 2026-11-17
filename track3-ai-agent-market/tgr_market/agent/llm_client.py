"""
llm_client.py  (TGR2026 Track 3 · ออกแบบเนื้อหาโดย Dr. Natthakorn Kasamsumran ESID CUEE)
เรียก LLM ผ่าน API แบบ OpenAI-compatible (/v1/chat/completions)
ใช้ได้ทั้ง Ollama บนเครื่องตัวเอง และ endpoint ของผู้จัด (เปลี่ยน base_url / model / api_key ใน config.json)
ทุกฟังก์ชันคืน None เมื่อ LLM ไม่ตอบหรือตอบผิดรูป ผู้เรียกต้องมีทางสำรองเสมอ
"""
import json, re, time

import requests


class LLM:
    def __init__(self, cfg):
        self.cfg = cfg
        self.calls, self.fails, self.total_s = 0, 0, 0.0

    def chat(self, system, user, json_mode=True):
        if not self.cfg.get('enabled'):
            return None
        body = {'model': self.cfg['model'], 'temperature': 0,
                'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]}
        if json_mode:
            body['response_format'] = {'type': 'json_object'}
        t0 = time.time()
        self.calls += 1
        try:
            r = requests.post(self.cfg['base_url'].rstrip('/') + '/chat/completions', json=body,
                              headers={'Authorization': f"Bearer {self.cfg.get('api_key', 'none')}"},
                              timeout=self.cfg.get('timeout_s', 20))
            r.raise_for_status()
            return r.json()['choices'][0]['message']['content']
        except Exception as e:
            self.fails += 1
            print(f'  [LLM] ไม่ตอบ: {type(e).__name__}: {str(e)[:120]}')
            return None
        finally:
            self.total_s += time.time() - t0

    def chat_json(self, system, user):
        """คืน dict หรือ None (ดึง {...} ก้อนแรกออกมา เผื่อโมเดลตอบข้อความปนมา)"""
        txt = self.chat(system, user, json_mode=True)
        if not txt:
            return None
        m = re.search(r'\{.*\}', txt, re.S)
        try:
            return json.loads(m.group(0)) if m else None
        except json.JSONDecodeError:
            self.fails += 1
            return None
