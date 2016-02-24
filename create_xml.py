from yattag import Doc

doc, tag, text = Doc().tagtext()

print('<?xml version="1.0" encoding="UTF-8"?>')
with tag('html'):
    with tag('body', id = 'hello'):
        with tag('h1'):
            text('Hello world!')

print(doc.getvalue())
