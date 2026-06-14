"""Test that the FileResponse Content-Length patch is applied correctly."""

import os
import tempfile


def test_fileresponse_no_content_length_with_stat_result():
    """FileResponse should not set Content-Length even when stat_result is provided."""
    from starlette.responses import FileResponse

    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
        f.write(b"x" * 1024)
        tmp = f.name

    try:
        stat_result = os.stat(tmp)
        fr = FileResponse(tmp, filename="test.zip", stat_result=stat_result)
        headers_lower = {k.lower(): v for k, v in fr.headers.items()}
        assert "content-length" not in headers_lower, (
            f"FileResponse should not set Content-Length. Headers: {fr.headers}"
        )
        # But last-modified and etag should still be set
        assert "last-modified" in headers_lower
        assert "etag" in headers_lower
    finally:
        os.unlink(tmp)


def test_fileresponse_no_content_length_without_stat_result():
    """FileResponse should not set Content-Length when stat_result is None."""
    from starlette.responses import FileResponse

    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
        f.write(b"x" * 512)
        tmp = f.name

    try:
        fr = FileResponse(tmp, filename="test2.zip", stat_result=None)
        headers_lower = {k.lower(): v for k, v in fr.headers.items()}
        assert "content-length" not in headers_lower, (
            f"FileResponse should not set Content-Length. Headers: {fr.headers}"
        )
    finally:
        os.unlink(tmp)


def test_gradio_modules_use_patched_fileresponse():
    """Gradio's route_utils and routes modules should reference the patched FileResponse."""
    import gradio.route_utils as ru
    import gradio.routes as rt

    from starlette.responses import FileResponse

    if hasattr(ru, "FileResponse"):
        assert ru.FileResponse is FileResponse, (
            f"route_utils.FileResponse is not the patched class: {ru.FileResponse}"
        )
    if hasattr(rt, "FileResponse"):
        assert rt.FileResponse is FileResponse, (
            f"routes.FileResponse is not the patched class: {rt.FileResponse}"
        )
