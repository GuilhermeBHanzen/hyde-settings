from hyde_settings import mime


def test_strip_field_codes():
    assert mime.strip_field_codes("/usr/bin/code --unity-launch %F") == "/usr/bin/code --unity-launch"
    assert mime.strip_field_codes("dolphin %u") == "dolphin"
    assert mime.strip_field_codes("app --pct 100%%") == "app --pct 100%"


def test_query_default(fake_runner):
    runner = fake_runner({("xdg-mime", "query", "default", "text/plain"): ("featherpad.desktop\n", None)})
    assert mime.query_default("text/plain", runner) == "featherpad.desktop"
    empty = fake_runner({("xdg-mime", "query", "default", "text/plain"): ("\n", None)})
    assert mime.query_default("text/plain", empty) is None
    failing = fake_runner({("xdg-mime", "query", "default", "text/plain"): (None, "boom")})
    assert mime.query_default("text/plain", failing) is None


def test_set_default_passes_all_types(fake_runner):
    runner = fake_runner()
    assert mime.set_default("com.microsoft.VSCode.desktop", ("text/plain", "text/x-python"), runner) is None
    assert runner.calls == [["xdg-mime", "default", "com.microsoft.VSCode.desktop", "text/plain", "text/x-python"]]


def test_file_types_cover_spec():
    labels = [label for label, _types in mime.FILE_TYPES]
    assert labels == ["Texto", "Código", "PDF", "Imagem", "Vídeo", "Pasta"]
    code = dict(mime.FILE_TYPES)["Código"]
    assert {"text/x-csrc", "text/x-python", "text/x-shellscript", "application/json", "text/markdown"} <= set(code)
