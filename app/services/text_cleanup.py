import re
from html import unescape
from html.parser import HTMLParser


class DescriptionHTMLStripper(HTMLParser):
    block_tags = {
        "blockquote",
        "br",
        "div",
        "li",
        "ol",
        "p",
        "section",
        "table",
        "tr",
        "ul",
    }
    ignored_tags = {"script", "style"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.ignored_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.ignored_tags:
            self.ignored_depth += 1
            return
        if self.ignored_depth:
            return
        if tag == "li":
            self._ensure_break()
            self.parts.append("- ")
        elif tag in self.block_tags:
            self._ensure_break()

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.ignored_tags and self.ignored_depth:
            self.ignored_depth -= 1
            return
        if self.ignored_depth:
            return
        if tag in self.block_tags:
            self._ensure_break()

    def handle_data(self, data):
        if self.ignored_depth:
            return
        text = " ".join(data.split())
        if not text:
            return
        if self.parts and not self.parts[-1].endswith(("\n", " ", "- ")):
            self.parts.append(" ")
        self.parts.append(text)

    def get_text(self):
        text = unescape("".join(self.parts))
        text = re.sub(r"\s+([,.;:!?])", r"\1", text)
        text = text.replace("**", "")
        lines = [line.strip() for line in text.splitlines()]

        cleaned_lines = []
        previous_blank = False
        for line in lines:
            if not line:
                if cleaned_lines and not previous_blank:
                    cleaned_lines.append("")
                previous_blank = True
                continue
            cleaned_lines.append(line)
            previous_blank = False

        return "\n".join(cleaned_lines).strip()

    def _ensure_break(self):
        if not self.parts:
            return
        current = "".join(self.parts)
        if current.endswith("\n\n"):
            return
        if current.endswith("\n"):
            self.parts.append("\n")
        else:
            self.parts.append("\n\n")


def strip_description_html(value):
    if not value:
        return ""

    stripper = DescriptionHTMLStripper()
    stripper.feed(value)
    stripper.close()
    return stripper.get_text()
