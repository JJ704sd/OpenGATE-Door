import os

slides_dir = r'D:\OpenGATE\ct_phantom_recon_v2\ppt_workspace\slides'

REPLACEMENTS = [
    ('\u3002', '.'),
    ('\u3001', ','),
    ('\uff0c', ','),
    ('\uff1b', ';'),
    ('\uff1a', ':'),
    ('\uff01', '!'),
    ('\uff1f', '?'),
    ('\uff08', '('),
    ('\uff09', ')'),
    ('\u2014', '--'),
    ('\u2013', '-'),
    ('\u2026', '...'),
    ('\u201c', '"'),
    ('\u201d', '"'),
    ('\u2018', "'"),
    ('\u2019', "'"),
    ('\u00a0', ' '),
]

for fn in os.listdir(slides_dir):
    if not fn.endswith('.js'):
        continue
    path = os.path.join(slides_dir, fn)
    with open(path, 'r', encoding='utf-8') as f:
        s = f.read()
    s2 = s
    for old, new in REPLACEMENTS:
        s2 = s2.replace(old, new)
    if s != s2:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(s2)
        print('Fixed:', fn)
print('Done')
