import os
import json


result = {
    'max': {
        '1': list(),
        '50': list(),
        '100': list(),
        '150': list(),
        '200': list(),
        '250': list(),
    },
    'min': {
        '1': list(),
        '50': list(),
        '100': list(),
        '150': list(),
        '200': list(),
        '250': list(),
    }
}


def read_text_file(file, file_path):
    with open(file_path, 'r') as f:
        parts = file.split('_')
        parsed = json.load(f)
        result['max'][parts[0]].append(parsed[0])
        result['min'][parts[0]].append(parsed[1])


for file in os.listdir():
    # Check whether file is in text format or not
    if file.endswith(".txt"):
        file_path = f"{file}"

        # call read text file function
        read_text_file(file, file_path)


for key in ['1', '50', '100', '150', '200', '250']:
    print(key)
    parsed_result = {
        'max': 0,
        'min': 1000,
        'avg': 0
    }
    items = result['max'][key]
    for item in items:
        parsed_result['avg'] += item['avg']
        parsed_result['max'] = max(parsed_result['max'], item['max'])
        parsed_result['min'] = min(parsed_result['min'], item['min'])
    parsed_result['avg'] = parsed_result['avg'] / len(items)
    print('Write')
    print(parsed_result)

    items = result['min'][key]
    parsed_result = {
        'max': 0,
        'min': 1000,
        'avg': 0
    }
    for item in items:
        parsed_result['avg'] += item['avg']
        parsed_result['max'] = max(parsed_result['max'], item['max'])
        parsed_result['min'] = min(parsed_result['min'], item['min'])
    parsed_result['avg'] = parsed_result['avg'] / len(items)
    print('Read')
    print(parsed_result)