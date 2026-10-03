import re

_VARIABLE_RE = re.compile(r'\{[+#./;?&=,!@|]?([^}]+)\}')

def variables(template):
    result = set()
    for match in _VARIABLE_RE.finditer(template):
        for part in match.group(1).split(','):
            name = part.split(':')[0].rstrip('*')
            if name:
                result.add(name)
    return result

def expand(template, variables=None, **kwargs):
    res = template
    d = dict(variables or {})
    d.update(kwargs)
    for k, v in d.items():
        res = re.sub(r'\{[+#./;?&=,!@|]?' + re.escape(k) + r'(?:\:[0-9]+)?\*?\}', str(v), res)
    return res

class URITemplate:
    def __init__(self, uri):
        self.uri = uri
        self.variable_names = variables(uri)
        self.variables = self.variable_names

    def expand(self, var_dict=None, **kwargs):
        return expand(self.uri, var_dict, **kwargs)
