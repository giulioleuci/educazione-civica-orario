import time
from datetime import datetime
import random

def create_mock_calendario(size=100000):
    dates = [f"{day:02d}/12/2024" for day in range(1, 32)]
    calendario = [{'DATA': random.choice(dates)} for _ in range(size)]
    return calendario

def original_method(calendario):
    for entry in calendario:
        if isinstance(entry['DATA'], str):
            entry['DATA'] = datetime.strptime(entry['DATA'], '%d/%m/%Y')

def optimized_method(calendario):
    date_cache = {}
    for entry in calendario:
        if isinstance(entry['DATA'], str):
            date_str = entry['DATA']
            if date_str not in date_cache:
                date_cache[date_str] = datetime.strptime(date_str, '%d/%m/%Y')
            entry['DATA'] = date_cache[date_str]

if __name__ == '__main__':
    c1 = create_mock_calendario()
    c2 = [dict(e) for e in c1]

    t0 = time.time()
    original_method(c1)
    t1 = time.time()
    print(f"Original: {t1 - t0:.4f} seconds")

    t0 = time.time()
    optimized_method(c2)
    t1 = time.time()
    print(f"Optimized: {t1 - t0:.4f} seconds")
