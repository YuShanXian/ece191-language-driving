from pathlib import Path
import sys
root=Path(__file__).parents[1]
sys.path.insert(0,str(root/'format-tools'))
import black,jsbeautifier,cssbeautifier
for path in (root.parents[1]/'sim').rglob('*'):
    if path.suffix not in ('.py','.js','.cjs','.css'):continue
    source=path.read_text(encoding='utf-8')
    if path.suffix=='.py':formatted=black.format_str(source,mode=black.Mode(line_length=100))
    elif path.suffix=='.css':formatted=cssbeautifier.beautify(source,{'indent_size':2})+'\n'
    else:formatted=jsbeautifier.beautify(source,{'indent_size':2,'preserve_newlines':True,'max_preserve_newlines':2})+'\n'
    path.write_text(formatted,encoding='utf-8')
print('Formatted active Python, JavaScript and CSS modules')
