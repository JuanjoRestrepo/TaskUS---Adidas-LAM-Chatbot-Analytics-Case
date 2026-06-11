import json
from pathlib import Path

nb_path = Path(r'notebooks\notebooks\01_data_understanding.ipynb')
with open(nb_path, encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb.get('cells', []):
    if cell.get('cell_type') == 'markdown':
        src = "".join(cell.get('source', []))
        if '[Imagen: Árbol Causal De los Hallazgos a los KPIs]' in src:
            fixed = src.replace('[Imagen: Árbol Causal De los Hallazgos a los KPIs]', 
                                '<img src="../../data/images/Árbol Causal De los Hallazgos a los KPIs.png" alt="Árbol Causal" width="1000"/>')
            cell['source'] = [fixed]

with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print('Imagen vinculada correctamente.')
