import re
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


_IMAGE_LINK_RE = re.compile(r"!\[([^\]]+)\]\(([^)]+)\)")
_NORMAL_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")


def _normalize_base(base: str) -> str:
    return base if base.endswith("/") else base + "/"


def _is_external_or_ignored(url: str) -> bool:
    return (
        url.startswith("#")
        or url.startswith("//")
        or (re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", url) is not None)
    )


def _append_raw_true(url: str) -> str:
    if "#" in url:
        main, frag = url.split("#", 1)
        suffix = f"#{frag}"
    else:
        main, suffix = url, ""

    sep = "&" if "?" in main else "?"
    return f"{main}{sep}raw=True{suffix}"


def relative_preview_links(content: str, base: str) -> str:
    """Replace relative preview links with absolute links with `raw=True`."""
    base = _normalize_base(base)

    def repl(m: re.Match[str]) -> str:
        alt, url = m.group(1), m.group(2)
        if _is_external_or_ignored(url):
            return m.group(0)
        return f"![{alt}]({_append_raw_true(base + url)})"

    return _IMAGE_LINK_RE.sub(repl, content)


def relative_non_preview_links(content: str, base: str) -> str:
    """Replace relative non-image links with absolute links."""
    base = _normalize_base(base)

    def repl(m: re.Match[str]) -> str:
        text, url = m.group(1), m.group(2)
        if _is_external_or_ignored(url):
            return m.group(0)
        return f"[{text}]({base}{url})"

    return _NORMAL_LINK_RE.sub(repl, content)


class ReadmeLinksRewriteBuildHook(BuildHookInterface):
    """Rewrite README links during build, then restore the original file."""

    PLUGIN_NAME = "custom"
    BASE_URL = "https://github.com/maida-ai/maida/blob/"
    README_FILE = Path("README.md")
    README_BACKUP_FILE = Path("_README.md")

    def initialize(self, version, build_data):
        if not self.README_FILE.exists():
            raise RuntimeError("README.md was not found.")

        if self.README_BACKUP_FILE.exists():
            raise RuntimeError(
                "_README.md already exists. Refusing to continue to avoid clobbering a backup."
            )

        version = self.metadata.version
        ref = "main" if ".dev" in version else f"v{version}"
        base = f"{self.BASE_URL}{ref}/"

        original = self.README_FILE.read_text(encoding="utf-8")
        rewritten = relative_non_preview_links(original, base)
        rewritten = relative_preview_links(rewritten, base)

        try:
            self.README_FILE.rename(self.README_BACKUP_FILE)
            self.README_FILE.write_text(rewritten, encoding="utf-8")
        except Exception:
            if self.README_FILE.exists():
                self.README_FILE.unlink()
            self.README_BACKUP_FILE.rename(self.README_FILE)
            raise

    def finalize(self, version, build_data, artifact_path):
        if self.README_BACKUP_FILE.exists():
            if self.README_FILE.exists():
                self.README_FILE.unlink()
            self.README_BACKUP_FILE.rename(self.README_FILE)
