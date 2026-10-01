"""Check minimo: python3 script_from_edt_and_aldo/test_edt_to_csv.py"""
from edt_to_csv import ore_occupate

assert ore_occupate('1h00', '08h00') == [1]
assert ore_occupate('2h00', '08h00') == [1, 2]
assert ore_occupate('3h00', '10h00') == [3, 4, 5]
assert ore_occupate('2h00', '14h00') == [7, 8]
print("ok")
