import os
import re
import time
import sys
from io import StringIO
import contextlib
import matplotlib.pyplot as plt
import numpy as np


@contextlib.contextmanager
def stdoutIO(stdout=None):
    old = sys.stdout
    if stdout is None:
        stdout = StringIO()
    sys.stdout = stdout
    yield stdout
    sys.stdout = old


def arr2str(arr):
    if len(arr.shape) == 1:
        return "[{}]".format(", ".join(list(map(str, arr))))
    return "[{}]".format(", ".join([arr2str(x) for x in arr]))


class Renderable(object):
    def __init__(self):
        self.content = []

    def append(self, elt):
        self.content.append(elt)

    def render(self):
        return "".join([c.render() for c in self.content])


class Parseable(Renderable):

    ATTRIBUTES = []

    def __init__(self):
        super(Parseable, self).__init__()

    @classmethod
    def parse(cls, line, f, doc):
        raise NotImplementedError()

    @classmethod
    def parse_attr(cls, line, f, doc, attrs):
        for attr, default in cls.ATTRIBUTES:
            if line.startswith(f"{attr}="):
                value = line.replace(f"{attr}=", "").strip()
                if isinstance(default, bool):
                    value = value.lower() in ("true", "yes", "t", 1, "y")
                elif isinstance(default, float):
                    value = float(value)
                elif isinstance(default, int):
                    value = int(value)
                attrs[attr] = value
                line = f.readline()
        return line

    @classmethod
    def init_attributes(cls):
        return dict(list(cls.ATTRIBUTES))

    @classmethod
    def parse_gen(cls, line, f, doc, attrs):
        if line == "":
            return line, True
        if line.startswith("["):
            return line, True
        if line.startswith("--"):
            return line, True
        line = cls.parse_attr(line, f, doc, attrs)
        if line.startswith("__nop"):
            return line.replace("__nop", ""), False
        return line, False


class HtmlElement(Renderable):
    def __init__(self, tag, attrs):
        super(HtmlElement, self).__init__()
        self.tag = tag
        self.attrs = attrs

    def render(self):
        attrs = " ".join(
            ['{}="{}"'.format(key, value) for key, value in self.attrs.items()]
        )
        html = "<{} {}>".format(self.tag, attrs)
        for c in self.content:
            if isinstance(c, str):
                html += c
            else:
                html += c.render()
        html += "</{}>".format(self.tag)
        return html


class Text(object):
    def __init__(self, text):
        self.text = text

    def render(self):
        segments = self.text.split("$$")
        for si, seg in enumerate(segments):
            if si % 2 == 1:
                # inside an equation
                continue
            sub_segments = seg.split("$")
            for sj, s in enumerate(sub_segments):
                if sj % 2 == 1:
                    # inside an equation
                    continue
                s = re.sub("`([^`]+)`", r"<code>\1</code>", s)
                s = re.sub("\*\*([^\*]+)\*\*", r"<b>\1</b>", s)
                s = re.sub("\*([^\*]+)\*", r"<i>\1</i>", s)
                # s = re.sub("_([^_]+)_", r"<u>\1</u>", s)
                s = re.sub("\[([^\]]+)\]\(([^\)]+)\)", r"<a href='\2'>\1</a>", s)
                sub_segments[sj] = s
            segments[si] = "$".join(sub_segments)
        return "$$".join(segments)


class Image(Parseable):

    ATTRIBUTES = []

    def __init__(self, src):
        super(Image, self).__init__()
        self.src = src

    def render(self):
        return '<center><br/><img src="{}" width="80%"/><br/></center>'.format(self.src)

    @classmethod
    def parse(cls, line, f, doc):
        line = f.readline()
        attrs = cls.init_attributes()
        src = ""
        while True:
            line, should_break = cls.parse_gen(line, f, doc, attrs)
            if should_break:
                break
            if line == "\n":
                line = f.readline()
            else:
                src = line.strip()
                line = f.readline()
        return line, cls(src)


class Javascript(Parseable):

    ATTRIBUTES = []

    def __init__(self):
        super(Javascript, self).__init__()

    def render(self):
        return ""

    @classmethod
    def parse(cls, line, f, doc):
        line = f.readline()
        lines = []
        attrs = cls.init_attributes()
        while True:
            line, should_break = cls.parse_gen(line, f, doc, attrs)
            if should_break:
                break
            else:
                lines.append(line)
                line = f.readline()
        doc.js += lines
        return line, cls()


class Html(Parseable):

    ATTRIBUTES = []

    def __init__(self, html):
        super(Html, self).__init__()
        self.html = html

    def render(self):
        return self.html

    @classmethod
    def parse(cls, line, f, doc):
        line = f.readline()
        lines = []
        attrs = cls.init_attributes()
        while True:
            line, should_break = cls.parse_gen(line, f, doc, attrs)
            if should_break:
                break
            else:
                lines.append(line)
                line = f.readline()
        return line, cls("".join(lines))


class Python(Parseable):

    ATTRIBUTES = [("print", "result")]

    def __init__(self, html):
        super(Python, self).__init__()
        self.html = html

    def render(self):
        return self.html

    @classmethod
    def parse(cls, line, f, doc):
        line = f.readline()
        lines = []
        attrs = cls.init_attributes()
        while True:
            line, should_break = cls.parse_gen(line, f, doc, attrs)
            if should_break:
                break
            else:
                lines.append(doc.replace_data(line))
                line = f.readline()
        pgm = "".join(lines)
        with stdoutIO() as s:
            exec(pgm)

        return line, cls(s.getvalue())


class Pyplot(Parseable):

    ATTRIBUTES = []

    def __init__(self, src):
        super(Pyplot, self).__init__()
        self.content = Image(src)

    def render(self):
        return self.content.render()

    @classmethod
    def parse(cls, line, f, doc):
        folder = os.path.join("plots", doc.name)
        if not os.path.exists(folder):
            os.makedirs(folder)
        src = os.path.join(folder, "{}.png".format(int(time.time())))
        line = f.readline()
        lines = []
        attrs = cls.init_attributes()
        while True:
            line, should_break = cls.parse_gen(line, f, doc, attrs)
            if should_break:
                break
            else:
                lines.append(doc.replace_data(line))
                line = f.readline()
        lines += ["plt.savefig('{}')\n".format(src), "plt.close()\n"]
        exec("".join(lines))

        return line, cls(src)


class Plotly(Parseable):

    ATTRIBUTES = []

    def __init__(self, container):
        super(Plotly, self).__init__()
        self.container = container

    def render(self):
        return self.container.render()

    @classmethod
    def parse(cls, line, f, doc):
        line = f.readline()
        attrs = cls.init_attributes()
        elt_id = "plot-{}".format(str(int(time.time() * 10000)))
        container = HtmlElement("div", {"class": "row", "id": elt_id})
        lines = [f"CONTAINER = document.getElementById('{elt_id}');"]
        while True:
            line, should_break = cls.parse_gen(line, f, doc, attrs)
            if should_break:
                break
            else:
                lines.append(doc.replace_data(line))
                line = f.readline()
        doc.js += lines
        return line, cls(container)


class Audio(Parseable):

    ATTRIBUTES = []

    def __init__(self, src):
        super(Audio, self).__init__()
        self.src = src

    def render(self):
        html = "<audio controls src='{}'>".format(self.src)
        html += "Your browser does not support the <code>audio</code> element."
        html += "</audio>"

    @classmethod
    def parse(cls, line, f, doc):
        line = f.readline()
        attrs = cls.init_attributes()
        src = ""
        while True:
            line, should_break = cls.parse_gen(line, f, doc, attrs)
            if should_break:
                break
            if line == "\n":
                line = f.readline()
            else:
                src = line.strip()
                line = f.readline()
        return line, cls(src)


class Video(Parseable):

    ATTRIBUTES = []

    def __init__(self, src):
        super(Video, self).__init__()
        self.src = src

    def render(self):
        html = "<video controls width='80%'>"
        for vtype, src in self.src:
            html += "<source src='{}', type='{}'>".format(src, vtype)
        html += "Your browser does not support the <code>video</code> element."
        html += "</video>"

    @classmethod
    def parse(cls, line, f, doc):
        line = f.readline()
        attrs = cls.init_attributes()
        src_types = []
        while True:
            line, should_break = cls.parse_gen(line, f, doc, attrs)
            if should_break:
                break
            if line == "\n":
                line = f.readline()
            else:
                src_types.append(line.strip().split())
                line = f.readline()
        return line, cls(src_types)


class Paragraph(Parseable):

    ATTRIBUTES = []

    def __init__(self, text):
        super(Paragraph, self).__init__()
        elt = HtmlElement("p", {})
        elt.append(Text(text))
        self.content = [elt]

    @classmethod
    def parse(cls, line, f, doc):
        line = f.readline()
        text = []
        attrs = cls.init_attributes()
        while True:
            line, should_break = cls.parse_gen(line, f, doc, attrs)
            if should_break:
                break
            text.append(line.strip())
            line = f.readline()
        return line, cls(" ".join(text))


class Alert(Parseable):

    ATTRIBUTES = [("type", "secondary")]

    def __init__(self, text, atype="secondary"):
        super(Alert, self).__init__()
        elt = HtmlElement("div", {"class": "alert alert-{}".format(atype)})
        elt.append(Text(text))
        self.content = [elt]

    @classmethod
    def parse(cls, line, f, doc):
        line = f.readline()
        text = []
        attrs = cls.init_attributes()
        while True:
            line, should_break = cls.parse_gen(line, f, doc, attrs)
            if should_break:
                break
            text.append(line)
            line = f.readline()
        return line, cls("".join(text), atype=attrs["type"])


class CodeSnippet(Parseable):

    ATTRIBUTES = [("type", "python")]

    def __init__(self, code_src, ctype="python"):
        super(CodeSnippet, self).__init__()
        self.code_src = code_src
        self.ctype = ctype

    def render(self):
        html = '<pre><code class="{}">'.format(self.ctype)
        html += self.code_src
        html += "</code></pre>"
        return html

    @classmethod
    def parse(cls, line, f, doc):
        line = f.readline()
        text = []
        attrs = cls.init_attributes()
        while True:
            line, should_break = cls.parse_gen(line, f, doc, attrs)
            if should_break:
                break
            else:
                text.append(line)
                try:
                    line = f.readline()
                except:
                    break
        i = len(text) - 1
        while i > 0 and text[i].strip() == "":
            i -= 1
        text = text[: i + 1]
        return line, cls("".join(text), ctype=attrs["type"])


class SvgList(Parseable):

    ATTRIBUTES = []

    def __init__(self, names_and_src):
        super(SvgList, self).__init__()
        self.names_and_src = names_and_src

    def render(self):
        elt = HtmlElement("div", {"class": "list-group"})
        for name, src in self.names_and_src:
            btn = HtmlElement(
                "a",
                {
                    "href": src,
                    "class": "list-group-item list-group-item-action svg-view",
                },
            )
            btn.append(Text(name))
            elt.append(btn)
        return elt.render()

    @classmethod
    def parse(cls, line, f, doc):
        line = f.readline()
        names_and_src = []
        attrs = cls.init_attributes()
        while True:
            line, should_break = cls.parse_gen(line, f, doc, attrs)
            if should_break:
                break
            if line == "\n":
                line = f.readline()
                continue
            else:
                x = line.strip().split()
                names_and_src.append((" ".join(x[1:]), x[0]))
                line = f.readline()
        return line, cls(names_and_src)


class List(Parseable):

    ATTRIBUTES = [("block", False), ("ordered", False), ("prelude", "")]

    def __init__(self, items, block=False, ordered=False, prelude=None):
        super(List, self).__init__()
        self.items = items
        self.block = block
        self.ordered = ordered
        self.prelude = prelude

    def render(self):
        if self.block:
            list_elt = HtmlElement("div", {"class": "list-group"})
        else:
            list_elt = HtmlElement("ol" if self.ordered else "ul", {})
        for item, href in self.items:
            if href is None:
                elt = HtmlElement(
                    "li", {"class": "list-group-item" if self.block else ""}
                )
                elt.append(Text(item))
            else:
                if self.block:
                    elt = HtmlElement(
                        "a",
                        {
                            "class": "list-group-item list-group-item-action",
                            "href": href,
                        },
                    )
                    elt.append(Text(item))
                else:
                    a_elt = HtmlElement(
                        "a",
                        {"href": href},
                    )
                    a_elt.append(Text(item))
                    elt = HtmlElement(
                        "li", {"class": "list-group-item" if self.block else ""}
                    )
                    elt.append(a_elt)
            list_elt.append(elt)
        html = ""
        if self.prelude is not None:
            html += Text(self.prelude).render()
        return html + list_elt.render()

    @classmethod
    def parse(cls, line, f, doc):
        line = f.readline()
        items = []
        attrs = cls.init_attributes()
        while True:
            line, should_break = cls.parse_gen(line, f, doc, attrs)
            if should_break:
                break
            if line == "\n":
                line = f.readline()
                continue
            else:
                if line.startswith("<<"):
                    m = re.match("<<([^>]+)>>(.*)", line.strip())
                    if m is not None:
                        items.append((m.group(2), m.group(1)))
                    else:
                        items.append((line.strip(), None))
                else:
                    items.append((line.strip(), None))
                line = f.readline()
        return line, cls(items, **attrs)


REGISTER = {
    "fst-list": SvgList,
    "svg-list": SvgList,
    "image": Image,
    "audio": Audio,
    "video": Video,
    "paragraph": Paragraph,
    "code": CodeSnippet,
    "alert": Alert,
    "list": List,
    "html": Html,
    "javascript": Javascript,
    "python": Python,
    "pyplot": Pyplot,
    "plotly": Plotly,
}


class Section(Renderable):
    def __init__(self, title, id, accordion=False):
        self.title = title
        self.id = id
        self.content = []
        self.accordion = accordion

    def render(self):
        this_id = self.id
        if self.accordion:
            elt = HtmlElement("div", {"class": "accordion-item"})
            btn = HtmlElement(
                "button",
                {
                    "class": "accordion-button collapsed",
                    "type": "button",
                    "data-bs-toggle": "collapse",
                    "data-bs-target": f"#collapse{this_id}",
                    "aria-expanded": "false",
                    "aria-controls": f"collapse{this_id}",
                },
            )
            btn.append(Text(self.title))
            h2 = HtmlElement(
                "h2", {"class": "accordion-header", "id": f"heading{this_id}"}
            )
            h2.append(btn)
            elt.append(h2)
            body = HtmlElement("div", {"class": "accordion-body"})
            body.content = self.content
            div = HtmlElement(
                "div",
                {
                    "id": f"collapse{this_id}",
                    "class": "accordion-collapse collapse",
                    "aria-labelledby": f"heading{this_id}",
                    "data-bs-parent": "#accordionExample",
                },
            )
            div.append(body)
            elt.append(div)
        else:
            elt = HtmlElement("div", {"class": "section"})
            h2 = HtmlElement(
                "h2", {"class": "section-header", "id": f"heading{this_id}"}
            )
            h2.append(Text(self.title))
            elt.append(h2)
            body = HtmlElement("div", {"class": "section-body"})
            body.content = self.content
            elt.append(body)
        return elt.render()

    def parse(self, line, f, doc):
        line = f.readline()
        while True:
            if line == "":
                break
            if line == "\n":
                line = f.readline()
                continue
            elif line.startswith("--"):
                cls = REGISTER[line.strip().replace("--", "").strip()]
                line, obj = cls.parse(line, f, doc)
                self.content.append(obj)
            elif line.startswith("["):
                break
            else:
                try:
                    line = f.readline()
                except:
                    break
        return line, self


class Document(Renderable):
    def __init__(self, name, data=None):
        self.content = []
        self.accordion = False
        self.template = "default"
        self.js = []
        self.name = name
        self.data = data

    def get_data(self, idstr, to_str=False):
        if self.data is None:
            raise ValueError("No data found for doc")
        assert idstr.startswith("@data.")
        s = idstr.replace("@data.", "")
        m = re.match(r"([^\[\s]+)([^\s]*)", s)
        if m is None:
            raise ValueError(f"Could not parse {idstr}")
        if m.group(1) not in self.data:
            raise ValueError("No key for {}".format(m.group(1)))
        arr = self.data[m.group(1)]
        if m.group(2) == "":
            if to_str:
                return arr2str(arr)
            return arr
        rngs = re.findall(r"\[([^\]]+)\]", m.group(2))
        for rng in rngs:
            if ":" not in rng:
                arr = arr[int(rng)]
            else:
                _slice = rng.split(":")
                if _slice[0] == "":
                    if _slice[1] == "":
                        if len(_slice) > 2:
                            arr = arr[:: int(_slice[2])]
                        else:
                            raise RuntimeError()
                    else:
                        if len(_slice) > 2:
                            arr = arr[: int(_slice[1]) : int(_slice[2])]
                        else:
                            arr = arr[: int(_slice[1])]
                else:
                    if len(_slice) == 1:
                        arr = arr[int(_slice[0])]
                    elif _slice[1] == "":
                        if len(slice) > 2:
                            arr = arr[int(_slice[0]) :: int(_slice[2])]
                        else:
                            arr = arr[int(_slice[0]) :]
                    else:
                        if len(slice) > 2:
                            arr = arr[int(_slice[0]) : int(_slice[1]) : int(_slice[2])]
                        else:
                            arr = arr[int(_slice[0]) : int(_slice[1])]
        if to_str:
            return arr2str(arr)
        return arr

    def replace_data(self, line):
        data_to_replace = re.findall(r"@data\.[a-zA-Z-_\[\]\d:]+", line)
        new_line = line
        for x in data_to_replace:
            new_line = new_line.replace(x, self.get_data(x, to_str=True))
        return new_line

    def render(self):
        css_class = "accordion" if self.accordion else ""
        elt = HtmlElement("div", {"class": css_class, "id": "accordionExample"})
        elt.content = self.content
        return elt.render()

    def parse(self, line, f):
        prelude = True
        while True:
            if line == "":
                break
            if line == "\n":
                line = f.readline()
                continue
            elif prelude and not line.startswith("["):
                if line.startswith("accordion="):
                    value = line.replace("accordion=", "").strip()
                    self.accordion = value.lower() in ("true", "1", "y", "yes")
                if line.startswith("template="):
                    self.template = line.replace("template=", "").strip()
                line = f.readline()
            elif line.startswith("["):
                prelude = False
                title = line.strip()[1:-1]
                id = "{:03d}".format(len(self.content) + 1)
                section = Section(title, id, accordion=self.accordion)
                line, _ = section.parse(line, f, self)
                self.content.append(section)
                continue
            else:
                try:
                    line = f.readline()
                except:
                    break
        return line, self

    def save(self):
        template_file = os.path.join("templates", "{}.html".format(self.template))
        source = open(template_file).read()
        source = source.replace("{{content}}", self.render())
        source = source.replace("{{script}}", "".join(self.js))
        with open(self.name + ".html", "w") as f:
            f.write(source)


def main():
    for filename in os.listdir("reports"):
        if filename.endswith(".txt"):
            basename = os.path.splitext(filename)[0]
            print(f"-- making '{basename}'")
            data = None
            if os.path.exists(os.path.join("data", basename + ".npz")):
                print("   ---> found data")
                data = np.load(os.path.join("data", basename + ".npz"))
            if os.path.exists(os.path.join("plots", basename)):
                for plot_file in os.listdir(os.path.join("plots", basename)):
                    os.remove(os.path.join("plots", basename, plot_file))
            doc = Document(basename, data=data)
            raw_file = os.path.join("reports", filename)
            output_file = f"{basename}.html"
            with open(raw_file) as f:
                line = f.readline()
                doc.parse(line, f)
            doc.save()


if __name__ == "__main__":
    main()
